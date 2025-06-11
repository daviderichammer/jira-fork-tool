"""
Jira API integration module for the Jira Fork Tool.

This module provides comprehensive integration with Jira's REST API,
including all operations needed for project forking and synchronization.
"""

import logging
import time
from typing import Dict, List, Any, Optional, Iterator
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ..config import JiraInstanceConfig


logger = logging.getLogger(__name__)


class APIError(Exception):
    """Raised when Jira API operations fail."""
    pass


class RateLimitError(APIError):
    """Raised when API rate limits are exceeded."""
    pass


class JiraAPI:
    """Comprehensive Jira REST API client."""
    
    def __init__(self, config: JiraInstanceConfig, session: requests.Session):
        """Initialize the Jira API client."""
        self.config = config
        self.session = session
        self.base_url = f"{config.url}/rest/api/3"
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
    
    def get_project(self, project_key: str) -> Dict[str, Any]:
        """Get project information."""
        try:
            response = self.session.get(f"{self.base_url}/project/{project_key}")
            self._handle_response(response)
            return response.json()
        except Exception as e:
            raise APIError(f"Failed to get project {project_key}: {e}")
    
    def get_issue_statistics(self, project_key: str) -> Dict[str, Any]:
        """Get issue statistics for a project."""
        try:
            # Get total count
            search_url = f"{self.base_url}/search"
            jql = f"project = {project_key}"
            
            response = self.session.get(search_url, params={
                'jql': jql,
                'maxResults': 0,
                'fields': 'issuetype'
            })
            self._handle_response(response)
            data = response.json()
            
            total = data['total']
            
            # Get breakdown by issue type
            by_type = {}
            issue_types_response = self.session.get(f"{self.base_url}/project/{project_key}/statuses")
            if issue_types_response.ok:
                issue_types = issue_types_response.json()
                for issue_type in issue_types:
                    type_jql = f"project = {project_key} AND issuetype = '{issue_type['name']}'"
                    type_response = self.session.get(search_url, params={
                        'jql': type_jql,
                        'maxResults': 0
                    })
                    if type_response.ok:
                        by_type[issue_type['name']] = type_response.json()['total']
            
            return {
                'total': total,
                'by_type': by_type
            }
            
        except Exception as e:
            raise APIError(f"Failed to get issue statistics: {e}")
    
    def get_all_issue_keys(self, project_key: str) -> List[str]:
        """Get all issue keys in a project."""
        try:
            all_keys = []
            start_at = 0
            max_results = 1000
            
            while True:
                response = self.session.get(f"{self.base_url}/search", params={
                    'jql': f"project = {project_key} ORDER BY key ASC",
                    'startAt': start_at,
                    'maxResults': max_results,
                    'fields': 'key'
                })
                self._handle_response(response)
                data = response.json()
                
                keys = [issue['key'] for issue in data['issues']]
                all_keys.extend(keys)
                
                if len(keys) < max_results:
                    break
                
                start_at += max_results
            
            return all_keys
            
        except Exception as e:
            raise APIError(f"Failed to get issue keys: {e}")
    
    def get_issues_in_order(self, project_key: str) -> List[Dict[str, Any]]:
        """Get all issues in a project in key order."""
        try:
            all_issues = []
            start_at = 0
            max_results = 100
            
            while True:
                response = self.session.get(f"{self.base_url}/search", params={
                    'jql': f"project = {project_key} ORDER BY key ASC",
                    'startAt': start_at,
                    'maxResults': max_results,
                    'expand': 'changelog,attachments,comments'
                })
                self._handle_response(response)
                data = response.json()
                
                all_issues.extend(data['issues'])
                
                if len(data['issues']) < max_results:
                    break
                
                start_at += max_results
                
                # Rate limiting
                time.sleep(0.1)
            
            return all_issues
            
        except Exception as e:
            raise APIError(f"Failed to get issues: {e}")
    
    def create_issue(self, issue_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new issue."""
        try:
            response = self.session.post(
                f"{self.base_url}/issue",
                json=issue_data
            )
            self._handle_response(response)
            return response.json()
            
        except Exception as e:
            raise APIError(f"Failed to create issue: {e}")
    
    def get_custom_fields(self, project_key: str) -> List[Dict[str, Any]]:
        """Get custom fields used in a project."""
        try:
            response = self.session.get(f"{self.base_url}/field")
            self._handle_response(response)
            all_fields = response.json()
            
            # Filter to custom fields
            custom_fields = [f for f in all_fields if f['custom']]
            
            return custom_fields
            
        except Exception as e:
            raise APIError(f"Failed to get custom fields: {e}")
    
    def get_attachment_statistics(self, project_key: str) -> Dict[str, Any]:
        """Get attachment statistics for a project."""
        try:
            # This is a simplified implementation
            # In practice, you'd need to iterate through issues to count attachments
            return {
                'total': 0,
                'total_size': 0
            }
            
        except Exception as e:
            raise APIError(f"Failed to get attachment statistics: {e}")
    
    def get_comment_statistics(self, project_key: str) -> Dict[str, Any]:
        """Get comment statistics for a project."""
        try:
            # This is a simplified implementation
            # In practice, you'd need to iterate through issues to count comments
            return {
                'total': 0
            }
            
        except Exception as e:
            raise APIError(f"Failed to get comment statistics: {e}")
    
    def _handle_response(self, response: requests.Response) -> None:
        """Handle API response and check for errors."""
        if response.status_code == 429:
            # Rate limited
            retry_after = int(response.headers.get('Retry-After', 60))
            raise RateLimitError(f"Rate limited. Retry after {retry_after} seconds")
        
        if not response.ok:
            try:
                error_data = response.json()
                error_msg = error_data.get('errorMessages', [response.text])
                if isinstance(error_msg, list):
                    error_msg = '; '.join(error_msg)
            except:
                error_msg = response.text
            
            raise APIError(f"HTTP {response.status_code}: {error_msg}")
    
    def upload_attachment(self, issue_key: str, file_path: str, filename: str) -> Dict[str, Any]:
        """Upload an attachment to an issue."""
        try:
            with open(file_path, 'rb') as f:
                files = {'file': (filename, f)}
                headers = {'X-Atlassian-Token': 'no-check'}
                
                response = self.session.post(
                    f"{self.base_url}/issue/{issue_key}/attachments",
                    files=files,
                    headers=headers
                )
                self._handle_response(response)
                return response.json()
                
        except Exception as e:
            raise APIError(f"Failed to upload attachment: {e}")
    
    def add_comment(self, issue_key: str, comment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add a comment to an issue."""
        try:
            response = self.session.post(
                f"{self.base_url}/issue/{issue_key}/comment",
                json=comment_data
            )
            self._handle_response(response)
            return response.json()
            
        except Exception as e:
            raise APIError(f"Failed to add comment: {e}")

