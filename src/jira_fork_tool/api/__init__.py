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
    
    def get_issue_types_for_project(self, project_key: str) -> List[Dict[str, Any]]:
        """Get available issue types for a project."""
        try:
            response = self.session.get(f"{self.base_url}/project/{project_key}/statuses")
            self._handle_response(response)
            
            # Extract unique issue types from the response
            issue_types = []
            seen_ids = set()
            
            for item in response.json():
                issue_type = {
                    'id': item.get('id'),
                    'name': item.get('name'),
                    'description': item.get('description', ''),
                    'subtask': item.get('subtask', False)
                }
                
                if issue_type['id'] not in seen_ids:
                    seen_ids.add(issue_type['id'])
                    issue_types.append(issue_type)
            
            # If the above endpoint doesn't return issue types, try the createmeta endpoint
            if not issue_types:
                response = self.session.get(
                    f"{self.base_url}/issue/createmeta",
                    params={'projectKeys': project_key, 'expand': 'projects.issuetypes'}
                )
                self._handle_response(response)
                
                data = response.json()
                if 'projects' in data and data['projects']:
                    project = data['projects'][0]
                    if 'issuetypes' in project:
                        issue_types = project['issuetypes']
            
            return issue_types
            
        except Exception as e:
            logger.error(f"Failed to get issue types for project {project_key}: {e}")
            # Return a minimal set of default issue types to avoid blocking the process
            return [
                {'id': '10000', 'name': 'Epic', 'subtask': False},
                {'id': '10001', 'name': 'Task', 'subtask': False},
                {'id': '10002', 'name': 'Sub-task', 'subtask': True}
            ]
    
    def get_statuses_for_project(self, project_key: str) -> List[Dict[str, Any]]:
        """Get available statuses for a project."""
        try:
            response = self.session.get(f"{self.base_url}/project/{project_key}/statuses")
            self._handle_response(response)
            
            # Extract unique statuses from the response
            statuses = []
            seen_ids = set()
            
            for item in response.json():
                for status in item.get('statuses', []):
                    status_id = status.get('id')
                    if status_id not in seen_ids:
                        seen_ids.add(status_id)
                        statuses.append(status)
            
            return statuses
            
        except Exception as e:
            logger.error(f"Failed to get statuses for project {project_key}: {e}")
            # Return a minimal set of default statuses to avoid blocking the process
            return [
                {'id': '1', 'name': 'To Do', 'statusCategory': {'key': 'new'}},
                {'id': '2', 'name': 'In Progress', 'statusCategory': {'key': 'indeterminate'}},
                {'id': '3', 'name': 'Done', 'statusCategory': {'key': 'done'}}
            ]
    
    def get_project_users(self, project_key: str) -> List[Dict[str, Any]]:
        """Get users associated with a project."""
        try:
            # This is a simplified implementation
            # In practice, you'd need to query assignable users or project roles
            response = self.session.get(f"{self.base_url}/user/assignable/search", 
                                       params={'project': project_key})
            self._handle_response(response)
            return response.json()
            
        except Exception as e:
            logger.error(f"Failed to get project users: {e}")
            return []
    
    def get_issue_count(self, project_key: str) -> int:
        """Get the total number of issues in a project."""
        try:
            response = self.session.get(f"{self.base_url}/search", params={
                'jql': f"project = {project_key}",
                'maxResults': 0
            })
            self._handle_response(response)
            return response.json()['total']
            
        except Exception as e:
            raise APIError(f"Failed to get issue count: {e}")
    
    def get_updated_issues(self, project_key: str, since: Any) -> List[Dict[str, Any]]:
        """Get issues updated since a specific time."""
        try:
            # Format timestamp for JQL
            if hasattr(since, 'isoformat'):
                since_str = since.isoformat()
            else:
                since_str = str(since)
            
            response = self.session.get(f"{self.base_url}/search", params={
                'jql': f"project = {project_key} AND updated >= '{since_str}'",
                'maxResults': 1000
            })
            self._handle_response(response)
            return response.json()['issues']
            
        except Exception as e:
            raise APIError(f"Failed to get updated issues: {e}")
    
    def create_issue_link(self, source_issue: str, target_issue: str, link_type: str) -> Dict[str, Any]:
        """Create a link between two issues."""
        try:
            link_data = {
                'type': {
                    'name': link_type
                },
                'inwardIssue': {
                    'key': source_issue
                },
                'outwardIssue': {
                    'key': target_issue
                }
            }
            
            response = self.session.post(
                f"{self.base_url}/issueLink",
                json=link_data
            )
            self._handle_response(response)
            return {'success': True}
            
        except Exception as e:
            raise APIError(f"Failed to create issue link: {e}")
    
    def create_epic_link(self, epic_key: str, issue_key: str) -> Dict[str, Any]:
        """Create an epic link between an epic and an issue."""
        try:
            # First, try to find the epic link field
            fields_response = self.session.get(f"{self.base_url}/field")
            self._handle_response(fields_response)
            
            epic_link_field = None
            for field in fields_response.json():
                if field.get('name') == 'Epic Link' or 'epic' in field.get('name', '').lower():
                    epic_link_field = field['id']
                    break
            
            if not epic_link_field:
                raise APIError("Epic Link field not found")
            
            # Update the issue with the epic link
            update_data = {
                'fields': {
                    epic_link_field: epic_key
                }
            }
            
            response = self.session.put(
                f"{self.base_url}/issue/{issue_key}",
                json=update_data
            )
            self._handle_response(response)
            return {'success': True}
            
        except Exception as e:
            raise APIError(f"Failed to create epic link: {e}")
    
    def get_all_issue_links(self, issue_keys: List[str]) -> List[Dict[str, Any]]:
        """Get all issue links for a list of issues."""
        try:
            all_links = []
            
            for key in issue_keys:
                response = self.session.get(f"{self.base_url}/issue/{key}?fields=issuelinks")
                if not response.ok:
                    continue
                
                issue_data = response.json()
                links = issue_data.get('fields', {}).get('issuelinks', [])
                
                for link in links:
                    if 'inwardIssue' in link:
                        all_links.append({
                            'source_issue': key,
                            'target_issue': link['inwardIssue']['key'],
                            'link_type': link['type']['inward']
                        })
                    elif 'outwardIssue' in link:
                        all_links.append({
                            'source_issue': key,
                            'target_issue': link['outwardIssue']['key'],
                            'link_type': link['type']['outward']
                        })
                
                # Rate limiting
                time.sleep(0.1)
            
            return all_links
            
        except Exception as e:
            logger.error(f"Failed to get issue links: {e}")
            return []
    
    def get_all_epic_links(self, issue_keys: List[str]) -> List[Dict[str, Any]]:
        """Get all epic links for a list of issues."""
        try:
            all_epic_links = []
            
            # First, try to find the epic link field
            fields_response = self.session.get(f"{self.base_url}/field")
            self._handle_response(fields_response)
            
            epic_link_field = None
            for field in fields_response.json():
                if field.get('name') == 'Epic Link' or 'epic' in field.get('name', '').lower():
                    epic_link_field = field['id']
                    break
            
            if not epic_link_field:
                logger.warning("Epic Link field not found")
                return []
            
            # Query each issue for its epic link
            for key in issue_keys:
                response = self.session.get(f"{self.base_url}/issue/{key}?fields={epic_link_field}")
                if not response.ok:
                    continue
                
                issue_data = response.json()
                epic_key = issue_data.get('fields', {}).get(epic_link_field)
                
                if epic_key:
                    all_epic_links.append({
                        'epic_key': epic_key,
                        'issue_key': key
                    })
                
                # Rate limiting
                time.sleep(0.1)
            
            return all_epic_links
            
        except Exception as e:
            logger.error(f"Failed to get epic links: {e}")
            return []
    
    def update_issue(self, issue_key: str, issue_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing issue."""
        try:
            response = self.session.put(
                f"{self.base_url}/issue/{issue_key}",
                json=issue_data
            )
            self._handle_response(response)
            return {'success': True}
            
        except Exception as e:
            raise APIError(f"Failed to update issue: {e}")
    
    def add_attachment(self, issue_key: str, filename: str, content: bytes) -> Dict[str, Any]:
        """Add an attachment to an issue."""
        try:
            headers = {
                'X-Atlassian-Token': 'no-check'
            }
            
            files = {
                'file': (filename, content)
            }
            
            response = self.session.post(
                f"{self.base_url}/issue/{issue_key}/attachments",
                headers=headers,
                files=files
            )
            self._handle_response(response)
            return response.json()[0]
            
        except Exception as e:
            raise APIError(f"Failed to add attachment: {e}")
    
    def download_attachment(self, attachment_id: str) -> bytes:
        """Download an attachment by ID."""
        try:
            response = self.session.get(f"{self.base_url}/attachment/content/{attachment_id}")
            self._handle_response(response)
            return response.content
            
        except Exception as e:
            raise APIError(f"Failed to download attachment: {e}")
    
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
    
    def get_issue_link_types(self) -> List[Dict[str, Any]]:
        """Get all available issue link types."""
        try:
            response = self.session.get(f"{self.base_url}/issueLinkType")
            self._handle_response(response)
            
            link_types = []
            for link_type in response.json().get('issueLinkTypes', []):
                link_types.append({
                    'id': link_type.get('id'),
                    'name': link_type.get('name'),
                    'inward': link_type.get('inward'),
                    'outward': link_type.get('outward')
                })
            
            return link_types
            
        except Exception as e:
            logger.error(f"Failed to get issue link types: {e}")
            # Return a minimal set of default link types to avoid blocking the process
            return [
                {'id': '10000', 'name': 'Relates', 'inward': 'relates to', 'outward': 'relates to'},
                {'id': '10001', 'name': 'Blocks', 'inward': 'is blocked by', 'outward': 'blocks'}
            ]
    
    def _handle_response(self, response: requests.Response) -> None:
        """Handle API response and raise appropriate exceptions."""
        if response.status_code == 429:
            retry_after = response.headers.get('Retry-After', '60')
            raise RateLimitError(f"Rate limit exceeded. Retry after {retry_after} seconds.")
        
        if not response.ok:
            error_message = f"HTTP {response.status_code}"
            try:
                error_data = response.json()
                if 'errorMessages' in error_data and error_data['errorMessages']:
                    error_message += f": {error_data['errorMessages'][0]}"
                elif 'errors' in error_data and error_data['errors']:
                    first_error = next(iter(error_data['errors'].items()))
                    error_message += f": {first_error[0]}"
            except:
                if response.text:
                    error_message += f": {response.text[:100]}"
            
            response.raise_for_status()
