"""
Authentication management for the Jira Fork Tool.

This module handles all authentication methods including API tokens,
OAuth 2.0, and JWT authentication for both source and destination
Jira instances.
"""

import base64
import logging
import time
from dataclasses import dataclass
from typing import Dict, Any, Optional, Tuple
import requests
from requests.auth import HTTPBasicAuth

from ..config import Config, JiraInstanceConfig, AuthConfig


logger = logging.getLogger(__name__)


class AuthError(Exception):
    """Raised when authentication fails or is invalid."""
    pass


@dataclass
class AuthResult:
    """Result of authentication validation."""
    source_valid: bool
    dest_valid: bool
    source_permissions: Optional[str] = None
    dest_permissions: Optional[str] = None
    source_error: Optional[str] = None
    dest_error: Optional[str] = None


class AuthManager:
    """Manages authentication for Jira instances."""
    
    def __init__(self, config: Config):
        """Initialize the authentication manager."""
        self.config = config
        self.source_session = None
        self.dest_session = None
        self._setup_sessions()
    
    def _setup_sessions(self) -> None:
        """Set up authenticated HTTP sessions for both instances."""
        self.source_session = self._create_session(
            self.config.source,
            "source"
        )
        self.dest_session = self._create_session(
            self.config.destination,
            "destination"
        )
    
    def _create_session(self, instance_config: JiraInstanceConfig, 
                       instance_name: str) -> requests.Session:
        """Create an authenticated session for a Jira instance."""
        session = requests.Session()
        
        # Configure SSL verification
        session.verify = instance_config.verify_ssl
        
        # Set timeout
        session.timeout = instance_config.timeout
        
        # Configure authentication
        auth_config = instance_config.auth
        
        if auth_config.type == "api_token":
            session.auth = HTTPBasicAuth(
                auth_config.email,
                auth_config.token
            )
            logger.info(f"Configured API token auth for {instance_name}")
            
        elif auth_config.type == "oauth2":
            # OAuth 2.0 implementation
            session.headers.update({
                'Authorization': f'Bearer {auth_config.access_token}'
            })
            logger.info(f"Configured OAuth 2.0 auth for {instance_name}")
            
        elif auth_config.type == "jwt":
            # JWT implementation
            session.headers.update({
                'Authorization': f'Bearer {auth_config.token}'
            })
            logger.info(f"Configured JWT auth for {instance_name}")
            
        else:
            raise AuthError(f"Unsupported auth type: {auth_config.type}")
        
        # Set common headers
        session.headers.update({
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'User-Agent': 'Jira-Fork-Tool/1.0.0'
        })
        
        return session
    
    def validate_credentials(self) -> AuthResult:
        """Validate credentials for both source and destination instances."""
        logger.info("Validating credentials for source and destination instances")
        
        # Validate source
        source_valid, source_perms, source_error = self._validate_instance(
            self.source_session,
            self.config.source,
            "source"
        )
        
        # Validate destination
        dest_valid, dest_perms, dest_error = self._validate_instance(
            self.dest_session,
            self.config.destination,
            "destination"
        )
        
        result = AuthResult(
            source_valid=source_valid,
            dest_valid=dest_valid,
            source_permissions=source_perms,
            dest_permissions=dest_perms,
            source_error=source_error,
            dest_error=dest_error
        )
        
        if not (source_valid and dest_valid):
            logger.error("Credential validation failed")
        else:
            logger.info("Credential validation successful")
        
        return result
    
    def _validate_instance(self, session: requests.Session,
                          config: JiraInstanceConfig,
                          instance_name: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """Validate credentials for a single Jira instance."""
        try:
            # Test basic connectivity and authentication
            response = session.get(f"{config.url}/rest/api/3/myself")
            
            if response.status_code == 401:
                return False, None, "Authentication failed - invalid credentials"
            elif response.status_code == 403:
                return False, None, "Authentication failed - insufficient permissions"
            elif not response.ok:
                return False, None, f"HTTP {response.status_code}: {response.text}"
            
            user_info = response.json()
            logger.info(f"Authenticated as {user_info.get('displayName')} "
                       f"({user_info.get('emailAddress')}) on {instance_name}")
            
            # Check project-specific permissions if project key is specified
            if config.project_key:
                perms = self._check_project_permissions(
                    session, config, instance_name
                )
                return True, perms, None
            else:
                return True, "Global access validated", None
                
        except requests.exceptions.SSLError as e:
            return False, None, f"SSL verification failed: {e}"
        except requests.exceptions.ConnectionError as e:
            return False, None, f"Connection failed: {e}"
        except requests.exceptions.Timeout as e:
            return False, None, f"Request timeout: {e}"
        except Exception as e:
            return False, None, f"Unexpected error: {e}"
    
    def _check_project_permissions(self, session: requests.Session,
                                  config: JiraInstanceConfig,
                                  instance_name: str) -> str:
        """Check project-specific permissions."""
        try:
            # Get project information
            response = session.get(
                f"{config.url}/rest/api/3/project/{config.project_key}"
            )
            
            if response.status_code == 404:
                raise AuthError(f"Project {config.project_key} not found")
            elif not response.ok:
                raise AuthError(f"Cannot access project: {response.text}")
            
            project_info = response.json()
            logger.info(f"Project {config.project_key} found: "
                       f"{project_info.get('name')}")
            
            # Check specific permissions
            permissions_to_check = [
                "BROWSE_PROJECTS",
                "CREATE_ISSUES",
                "EDIT_ISSUES",
                "ADD_COMMENTS",
                "ATTACH_FILES"
            ]
            
            if instance_name == "source":
                # Source only needs read permissions
                required_perms = ["BROWSE_PROJECTS"]
            else:
                # Destination needs write permissions
                required_perms = permissions_to_check
            
            # Check permissions
            perm_response = session.post(
                f"{config.url}/rest/api/3/permissions/check",
                json={
                    "projectKey": config.project_key,
                    "permissions": required_perms
                }
            )
            
            if perm_response.ok:
                perm_data = perm_response.json()
                granted_perms = [p for p in required_perms 
                               if perm_data.get(p, {}).get('havePermission', False)]
                
                if len(granted_perms) == len(required_perms):
                    return f"All required permissions granted: {', '.join(granted_perms)}"
                else:
                    missing_perms = set(required_perms) - set(granted_perms)
                    raise AuthError(f"Missing permissions: {', '.join(missing_perms)}")
            else:
                # Fallback to basic project access check
                return f"Project access confirmed (permission check unavailable)"
                
        except AuthError:
            raise
        except Exception as e:
            logger.warning(f"Permission check failed, assuming basic access: {e}")
            return "Basic project access (detailed permission check failed)"
    
    def get_source_session(self) -> requests.Session:
        """Get the authenticated session for the source instance."""
        if not self.source_session:
            raise AuthError("Source session not initialized")
        return self.source_session
    
    def get_dest_session(self) -> requests.Session:
        """Get the authenticated session for the destination instance."""
        if not self.dest_session:
            raise AuthError("Destination session not initialized")
        return self.dest_session
    
    def refresh_tokens(self) -> None:
        """Refresh OAuth tokens if needed."""
        # Refresh source tokens
        if (self.config.source.auth.type == "oauth2" and 
            self.config.source.auth.refresh_token):
            self._refresh_oauth_token(self.config.source, "source")
        
        # Refresh destination tokens
        if (self.config.destination.auth.type == "oauth2" and 
            self.config.destination.auth.refresh_token):
            self._refresh_oauth_token(self.config.destination, "destination")
    
    def _refresh_oauth_token(self, instance_config: JiraInstanceConfig,
                           instance_name: str) -> None:
        """Refresh OAuth 2.0 access token."""
        try:
            auth_config = instance_config.auth
            
            # Prepare token refresh request
            token_url = f"{instance_config.url}/oauth/token"
            data = {
                'grant_type': 'refresh_token',
                'refresh_token': auth_config.refresh_token,
                'client_id': auth_config.client_id,
                'client_secret': auth_config.client_secret
            }
            
            response = requests.post(token_url, data=data)
            
            if response.ok:
                token_data = response.json()
                auth_config.access_token = token_data['access_token']
                
                if 'refresh_token' in token_data:
                    auth_config.refresh_token = token_data['refresh_token']
                
                logger.info(f"OAuth token refreshed for {instance_name}")
                
                # Update session with new token
                if instance_name == "source":
                    self.source_session.headers.update({
                        'Authorization': f'Bearer {auth_config.access_token}'
                    })
                else:
                    self.dest_session.headers.update({
                        'Authorization': f'Bearer {auth_config.access_token}'
                    })
            else:
                logger.error(f"Failed to refresh OAuth token for {instance_name}: "
                           f"{response.text}")
                raise AuthError(f"Token refresh failed: {response.text}")
                
        except Exception as e:
            logger.error(f"Error refreshing OAuth token for {instance_name}: {e}")
            raise AuthError(f"Token refresh error: {e}")
    
    def test_api_connectivity(self) -> Dict[str, Any]:
        """Test API connectivity and gather system information."""
        results = {}
        
        # Test source
        try:
            response = self.source_session.get(
                f"{self.config.source.url}/rest/api/3/serverInfo"
            )
            if response.ok:
                results['source'] = {
                    'status': 'connected',
                    'info': response.json()
                }
            else:
                results['source'] = {
                    'status': 'error',
                    'error': f"HTTP {response.status_code}"
                }
        except Exception as e:
            results['source'] = {
                'status': 'error',
                'error': str(e)
            }
        
        # Test destination
        try:
            response = self.dest_session.get(
                f"{self.config.destination.url}/rest/api/3/serverInfo"
            )
            if response.ok:
                results['destination'] = {
                    'status': 'connected',
                    'info': response.json()
                }
            else:
                results['destination'] = {
                    'status': 'error',
                    'error': f"HTTP {response.status_code}"
                }
        except Exception as e:
            results['destination'] = {
                'status': 'error',
                'error': str(e)
            }
        
        return results

