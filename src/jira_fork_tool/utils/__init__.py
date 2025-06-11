"""
Utility functions and classes for the Jira Fork Tool.

This module provides common utilities including logging setup,
state management, progress tracking, and validation functions.
"""

import logging
import logging.handlers
import sqlite3
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime


def setup_logging(level: int = 0, log_file: Optional[Path] = None) -> None:
    """Set up logging configuration."""
    # Map verbosity level to logging level
    log_levels = {
        0: logging.WARNING,
        1: logging.INFO,
        2: logging.DEBUG,
        3: logging.DEBUG
    }
    
    log_level = log_levels.get(level, logging.DEBUG)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)


def validate_environment() -> List[str]:
    """Validate the environment and return any issues found."""
    issues = []
    
    try:
        import requests
    except ImportError:
        issues.append("requests library not installed")
    
    try:
        import yaml
    except ImportError:
        issues.append("PyYAML library not installed")
    
    # Add more validation as needed
    
    return issues


class StateManager:
    """Manages persistent state for synchronization operations."""
    
    def __init__(self, db_config):
        """Initialize the state manager."""
        self.db_path = db_config.path
        self._init_database()
    
    def _init_database(self) -> None:
        """Initialize the SQLite database."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS sync_sessions (
                    sync_id TEXT PRIMARY KEY,
                    source_project TEXT NOT NULL,
                    dest_project TEXT NOT NULL,
                    sync_type TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'running',
                    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    end_time TIMESTAMP,
                    error_message TEXT,
                    metadata TEXT
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS checkpoints (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sync_id TEXT NOT NULL,
                    phase TEXT NOT NULL,
                    progress INTEGER NOT NULL,
                    total INTEGER NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    data TEXT,
                    FOREIGN KEY (sync_id) REFERENCES sync_sessions (sync_id)
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS issue_mappings (
                    sync_id TEXT NOT NULL,
                    source_key TEXT NOT NULL,
                    dest_key TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (sync_id) REFERENCES sync_sessions (sync_id),
                    PRIMARY KEY (sync_id, source_key)
                )
            ''')
    
    def create_sync_session(self, sync_id: str, source_project: str,
                          dest_project: str, sync_type: str) -> None:
        """Create a new sync session."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO sync_sessions 
                (sync_id, source_project, dest_project, sync_type)
                VALUES (?, ?, ?, ?)
            ''', (sync_id, source_project, dest_project, sync_type))
    
    def complete_sync_session(self, sync_id: str, result) -> None:
        """Mark a sync session as completed."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                UPDATE sync_sessions 
                SET status = 'completed', end_time = CURRENT_TIMESTAMP,
                    metadata = ?
                WHERE sync_id = ?
            ''', (json.dumps(result.__dict__, default=str), sync_id))
    
    def fail_sync_session(self, sync_id: str, error_message: str) -> None:
        """Mark a sync session as failed."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                UPDATE sync_sessions 
                SET status = 'failed', end_time = CURRENT_TIMESTAMP,
                    error_message = ?
                WHERE sync_id = ?
            ''', (error_message, sync_id))
    
    def get_sync_session(self, sync_id: str) -> Optional[Dict[str, Any]]:
        """Get sync session information."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('''
                SELECT * FROM sync_sessions WHERE sync_id = ?
            ''', (sync_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_last_successful_sync(self) -> Optional[Dict[str, Any]]:
        """Get the last successful sync session."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('''
                SELECT * FROM sync_sessions 
                WHERE status = 'completed'
                ORDER BY end_time DESC
                LIMIT 1
            ''')
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def create_checkpoint(self, sync_id: str, phase: str, progress: int,
                         total: int, data: Optional[Dict[str, Any]] = None) -> None:
        """Create a checkpoint for resumable operations."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO checkpoints 
                (sync_id, phase, progress, total, data)
                VALUES (?, ?, ?, ?, ?)
            ''', (sync_id, phase, progress, total, 
                  json.dumps(data) if data else None))
    
    def get_last_checkpoint(self, sync_id: str) -> Optional[Dict[str, Any]]:
        """Get the last checkpoint for a sync session."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('''
                SELECT * FROM checkpoints 
                WHERE sync_id = ?
                ORDER BY timestamp DESC
                LIMIT 1
            ''', (sync_id,))
            row = cursor.fetchone()
            if row:
                result = dict(row)
                if result['data']:
                    result['data'] = json.loads(result['data'])
                return result
            return None
    
    def save_project_analysis(self, sync_id: str, analysis: Dict[str, Any]) -> None:
        """Save project analysis data."""
        # Implementation would store analysis data
        pass
    
    def save_user_mapping(self, sync_id: str, user_mapping: Dict[str, str]) -> None:
        """Save user mapping data."""
        # Implementation would store user mapping
        pass


class ProgressTracker:
    """Tracks and reports progress of synchronization operations."""
    
    def __init__(self):
        """Initialize the progress tracker."""
        self.current_phase = None
        self.phase_progress = 0
        self.phase_total = 0
        self.start_time = None
    
    def start_phase(self, phase_name: str, total_items: int) -> None:
        """Start tracking a new phase."""
        self.current_phase = phase_name
        self.phase_progress = 0
        self.phase_total = total_items
        self.start_time = datetime.now()
        
        logging.info(f"Starting phase: {phase_name} ({total_items} items)")
    
    def update_progress(self, completed_items: int) -> None:
        """Update progress within the current phase."""
        self.phase_progress = completed_items
        
        if self.phase_total > 0:
            percentage = (completed_items / self.phase_total) * 100
            logging.info(f"Progress: {completed_items}/{self.phase_total} "
                        f"({percentage:.1f}%)")
    
    def complete_phase(self) -> None:
        """Mark the current phase as complete."""
        if self.current_phase and self.start_time:
            duration = datetime.now() - self.start_time
            logging.info(f"Completed phase: {self.current_phase} "
                        f"in {duration}")
        
        self.current_phase = None
        self.phase_progress = 0
        self.phase_total = 0
        self.start_time = None

