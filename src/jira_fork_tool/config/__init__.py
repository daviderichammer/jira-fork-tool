"""
Configuration management for the Jira Fork Tool.

This module handles loading, validation, and management of configuration
settings from YAML files and environment variables.
"""

import os
import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse


class ConfigError(Exception):
    """Raised when configuration is invalid or cannot be loaded."""
    pass


@dataclass
class AuthConfig:
    """Authentication configuration for a Jira instance."""
    type: str  # "api_token", "oauth2", "jwt"
    email: Optional[str] = None
    token: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    
    def __post_init__(self):
        """Validate authentication configuration."""
        if self.type == "api_token":
            if not self.email or not self.token:
                raise ConfigError("API token auth requires email and token")
        elif self.type == "oauth2":
            if not self.client_id or not self.client_secret:
                raise ConfigError("OAuth2 auth requires client_id and client_secret")
        elif self.type == "jwt":
            if not self.token:
                raise ConfigError("JWT auth requires token")
        else:
            raise ConfigError(f"Unsupported auth type: {self.type}")


@dataclass
class JiraInstanceConfig:
    """Configuration for a Jira instance (source or destination)."""
    url: str
    auth: AuthConfig
    project_key: Optional[str] = None
    verify_ssl: bool = True
    timeout: int = 30
    
    def __post_init__(self):
        """Validate Jira instance configuration."""
        # Validate URL
        parsed = urlparse(self.url)
        if not parsed.scheme or not parsed.netloc:
            raise ConfigError(f"Invalid URL: {self.url}")
        
        # Ensure URL doesn't end with slash
        self.url = self.url.rstrip('/')


@dataclass
class SyncConfig:
    """Synchronization behavior configuration."""
    preserve_numbers: bool = True
    handle_gaps: bool = True
    include_attachments: bool = True
    include_comments: bool = True
    include_worklogs: bool = True
    include_links: bool = True
    batch_size: int = 100
    max_retries: int = 3
    retry_delay: int = 5
    rate_limit_buffer: float = 0.8  # Use 80% of rate limit
    
    # Field mapping configuration
    field_mappings: Dict[str, str] = field(default_factory=dict)
    user_mappings: Dict[str, str] = field(default_factory=dict)
    
    # Gap handling strategy
    gap_strategy: str = "placeholder"  # "placeholder", "skip", "error"
    placeholder_summary: str = "[PLACEHOLDER] Gap in issue numbering"
    
    # Incremental sync settings
    incremental_enabled: bool = True
    sync_interval: int = 3600  # seconds
    change_detection_method: str = "updated"  # "updated", "audit_log"


@dataclass
class DatabaseConfig:
    """Database configuration for state management."""
    type: str = "sqlite"  # "sqlite", "postgresql"
    path: Optional[str] = "data/jira_fork_tool.db"
    host: Optional[str] = None
    port: Optional[int] = None
    database: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    
    def get_connection_string(self) -> str:
        """Get database connection string."""
        if self.type == "sqlite":
            return f"sqlite:///{self.path}"
        elif self.type == "postgresql":
            return (f"postgresql://{self.username}:{self.password}"
                   f"@{self.host}:{self.port}/{self.database}")
        else:
            raise ConfigError(f"Unsupported database type: {self.type}")


@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: str = "INFO"
    file: Optional[str] = "logs/jira_fork_tool.log"
    max_size: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


@dataclass
class SecurityConfig:
    """Security configuration."""
    encrypt_credentials: bool = True
    credential_store: str = "file"  # "file", "keyring", "vault"
    audit_logging: bool = True
    session_timeout: int = 3600
    max_login_attempts: int = 3


@dataclass
class Config:
    """Main configuration class for the Jira Fork Tool."""
    source: JiraInstanceConfig
    destination: JiraInstanceConfig
    sync: SyncConfig = field(default_factory=SyncConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    
    @classmethod
    def load(cls, config_path: Path) -> 'Config':
        """Load configuration from a YAML file."""
        try:
            if not config_path.exists():
                raise ConfigError(f"Configuration file not found: {config_path}")
            
            with open(config_path, 'r') as f:
                data = yaml.safe_load(f)
            
            # Substitute environment variables
            data = cls._substitute_env_vars(data)
            
            # Parse configuration sections
            source_config = cls._parse_jira_config(data.get('source', {}))
            dest_config = cls._parse_jira_config(data.get('destination', {}))
            sync_config = cls._parse_sync_config(data.get('sync', {}))
            db_config = cls._parse_database_config(data.get('database', {}))
            log_config = cls._parse_logging_config(data.get('logging', {}))
            security_config = cls._parse_security_config(data.get('security', {}))
            
            return cls(
                source=source_config,
                destination=dest_config,
                sync=sync_config,
                database=db_config,
                logging=log_config,
                security=security_config
            )
            
        except yaml.YAMLError as e:
            raise ConfigError(f"Invalid YAML in configuration file: {e}")
        except Exception as e:
            raise ConfigError(f"Error loading configuration: {e}")
    
    @staticmethod
    def _substitute_env_vars(data: Any) -> Any:
        """Recursively substitute environment variables in configuration data."""
        if isinstance(data, dict):
            return {k: Config._substitute_env_vars(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [Config._substitute_env_vars(item) for item in data]
        elif isinstance(data, str) and data.startswith('${') and data.endswith('}'):
            env_var = data[2:-1]
            default_value = None
            if ':' in env_var:
                env_var, default_value = env_var.split(':', 1)
            return os.getenv(env_var, default_value)
        else:
            return data
    
    @staticmethod
    def _parse_jira_config(data: Dict[str, Any]) -> JiraInstanceConfig:
        """Parse Jira instance configuration."""
        if not data.get('url'):
            raise ConfigError("Jira URL is required")
        
        auth_data = data.get('auth', {})
        auth_config = AuthConfig(
            type=auth_data.get('type', 'api_token'),
            email=auth_data.get('email'),
            token=auth_data.get('token'),
            client_id=auth_data.get('client_id'),
            client_secret=auth_data.get('client_secret'),
            access_token=auth_data.get('access_token'),
            refresh_token=auth_data.get('refresh_token')
        )
        
        return JiraInstanceConfig(
            url=data['url'],
            auth=auth_config,
            project_key=data.get('project_key'),
            verify_ssl=data.get('verify_ssl', True),
            timeout=data.get('timeout', 30)
        )
    
    @staticmethod
    def _parse_sync_config(data: Dict[str, Any]) -> SyncConfig:
        """Parse synchronization configuration."""
        return SyncConfig(
            preserve_numbers=data.get('preserve_numbers', True),
            handle_gaps=data.get('handle_gaps', True),
            include_attachments=data.get('include_attachments', True),
            include_comments=data.get('include_comments', True),
            include_worklogs=data.get('include_worklogs', True),
            include_links=data.get('include_links', True),
            batch_size=data.get('batch_size', 100),
            max_retries=data.get('max_retries', 3),
            retry_delay=data.get('retry_delay', 5),
            rate_limit_buffer=data.get('rate_limit_buffer', 0.8),
            field_mappings=data.get('field_mappings', {}),
            user_mappings=data.get('user_mappings', {}),
            gap_strategy=data.get('gap_strategy', 'placeholder'),
            placeholder_summary=data.get('placeholder_summary', 
                                       '[PLACEHOLDER] Gap in issue numbering'),
            incremental_enabled=data.get('incremental_enabled', True),
            sync_interval=data.get('sync_interval', 3600),
            change_detection_method=data.get('change_detection_method', 'updated')
        )
    
    @staticmethod
    def _parse_database_config(data: Dict[str, Any]) -> DatabaseConfig:
        """Parse database configuration."""
        return DatabaseConfig(
            type=data.get('type', 'sqlite'),
            path=data.get('path', 'data/jira_fork_tool.db'),
            host=data.get('host'),
            port=data.get('port'),
            database=data.get('database'),
            username=data.get('username'),
            password=data.get('password')
        )
    
    @staticmethod
    def _parse_logging_config(data: Dict[str, Any]) -> LoggingConfig:
        """Parse logging configuration."""
        return LoggingConfig(
            level=data.get('level', 'INFO'),
            file=data.get('file', 'logs/jira_fork_tool.log'),
            max_size=data.get('max_size', 10 * 1024 * 1024),
            backup_count=data.get('backup_count', 5),
            format=data.get('format', 
                          '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        )
    
    @staticmethod
    def _parse_security_config(data: Dict[str, Any]) -> SecurityConfig:
        """Parse security configuration."""
        return SecurityConfig(
            encrypt_credentials=data.get('encrypt_credentials', True),
            credential_store=data.get('credential_store', 'file'),
            audit_logging=data.get('audit_logging', True),
            session_timeout=data.get('session_timeout', 3600),
            max_login_attempts=data.get('max_login_attempts', 3)
        )
    
    def validate(self) -> List[str]:
        """Validate the complete configuration and return any errors."""
        errors = []
        
        # Validate source and destination are different
        if self.source.url == self.destination.url:
            if self.source.project_key == self.destination.project_key:
                errors.append("Source and destination cannot be the same project")
        
        # Validate sync configuration
        if self.sync.batch_size <= 0:
            errors.append("Batch size must be positive")
        
        if self.sync.max_retries < 0:
            errors.append("Max retries cannot be negative")
        
        if not 0 < self.sync.rate_limit_buffer <= 1:
            errors.append("Rate limit buffer must be between 0 and 1")
        
        # Validate gap strategy
        valid_gap_strategies = ['placeholder', 'skip', 'error']
        if self.sync.gap_strategy not in valid_gap_strategies:
            errors.append(f"Gap strategy must be one of: {valid_gap_strategies}")
        
        return errors
    
    def save(self, config_path: Path) -> None:
        """Save configuration to a YAML file."""
        # Convert to dictionary for YAML serialization
        data = {
            'source': {
                'url': self.source.url,
                'auth': {
                    'type': self.source.auth.type,
                    'email': self.source.auth.email,
                    'token': self.source.auth.token,
                    'client_id': self.source.auth.client_id,
                    'client_secret': self.source.auth.client_secret,
                    'access_token': self.source.auth.access_token,
                    'refresh_token': self.source.auth.refresh_token
                },
                'project_key': self.source.project_key,
                'verify_ssl': self.source.verify_ssl,
                'timeout': self.source.timeout
            },
            'destination': {
                'url': self.destination.url,
                'auth': {
                    'type': self.destination.auth.type,
                    'email': self.destination.auth.email,
                    'token': self.destination.auth.token,
                    'client_id': self.destination.auth.client_id,
                    'client_secret': self.destination.auth.client_secret,
                    'access_token': self.destination.auth.access_token,
                    'refresh_token': self.destination.auth.refresh_token
                },
                'project_key': self.destination.project_key,
                'verify_ssl': self.destination.verify_ssl,
                'timeout': self.destination.timeout
            },
            'sync': {
                'preserve_numbers': self.sync.preserve_numbers,
                'handle_gaps': self.sync.handle_gaps,
                'include_attachments': self.sync.include_attachments,
                'include_comments': self.sync.include_comments,
                'include_worklogs': self.sync.include_worklogs,
                'include_links': self.sync.include_links,
                'batch_size': self.sync.batch_size,
                'max_retries': self.sync.max_retries,
                'retry_delay': self.sync.retry_delay,
                'rate_limit_buffer': self.sync.rate_limit_buffer,
                'field_mappings': self.sync.field_mappings,
                'user_mappings': self.sync.user_mappings,
                'gap_strategy': self.sync.gap_strategy,
                'placeholder_summary': self.sync.placeholder_summary,
                'incremental_enabled': self.sync.incremental_enabled,
                'sync_interval': self.sync.sync_interval,
                'change_detection_method': self.sync.change_detection_method
            }
        }
        
        # Remove None values
        data = self._remove_none_values(data)
        
        # Ensure directory exists
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write YAML file
        with open(config_path, 'w') as f:
            yaml.dump(data, f, default_flow_style=False, indent=2)
    
    @staticmethod
    def _remove_none_values(data: Any) -> Any:
        """Recursively remove None values from data structure."""
        if isinstance(data, dict):
            return {k: Config._remove_none_values(v) 
                   for k, v in data.items() if v is not None}
        elif isinstance(data, list):
            return [Config._remove_none_values(item) for item in data]
        else:
            return data

