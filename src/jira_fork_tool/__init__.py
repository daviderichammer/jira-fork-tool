"""
Jira Fork Tool - A comprehensive tool for creating and maintaining synchronized 
copies of Jira projects across different organizations.

This package provides the core functionality for:
- Ticket number synchronization
- Complete data fidelity transfer
- Gap detection and handling
- Incremental synchronization
- Robust error handling and recovery
"""

__version__ = "1.0.0"
__author__ = "Manus AI"
__email__ = "manus@example.com"
__description__ = "Comprehensive Jira project forking and synchronization tool"

from .main import main
from .config import Config
from .sync import SyncEngine
from .auth import AuthManager

__all__ = [
    "main",
    "Config", 
    "SyncEngine",
    "AuthManager",
]

