"""
Web dashboard for the Jira Fork Tool.

This module provides a Flask-based web interface for monitoring
synchronization operations and managing configurations.
"""

import logging
from flask import Flask, render_template, jsonify, request
from typing import Dict, Any

from ..config import Config
from ..utils import StateManager


logger = logging.getLogger(__name__)


class Dashboard:
    """Web dashboard for the Jira Fork Tool."""
    
    def __init__(self, config: Config):
        """Initialize the dashboard."""
        self.config = config
        self.state_manager = StateManager(config.database)
        self.app = Flask(__name__)
        self._setup_routes()
    
    def _setup_routes(self) -> None:
        """Set up Flask routes."""
        
        @self.app.route('/')
        def index():
            """Main dashboard page."""
            return render_template('dashboard.html')
        
        @self.app.route('/api/status')
        def api_status():
            """Get current system status."""
            try:
                # Get recent sync sessions
                recent_syncs = self._get_recent_syncs()
                
                # Get system info
                system_info = self._get_system_info()
                
                return jsonify({
                    'status': 'ok',
                    'recent_syncs': recent_syncs,
                    'system_info': system_info
                })
            except Exception as e:
                logger.exception("Error getting status")
                return jsonify({'status': 'error', 'message': str(e)}), 500
        
        @self.app.route('/api/sync/<sync_id>')
        def api_sync_details(sync_id):
            """Get details for a specific sync."""
            try:
                sync_details = self.state_manager.get_sync_session(sync_id)
                if not sync_details:
                    return jsonify({'error': 'Sync not found'}), 404
                
                return jsonify(sync_details)
            except Exception as e:
                logger.exception(f"Error getting sync details for {sync_id}")
                return jsonify({'error': str(e)}), 500
    
    def _get_recent_syncs(self) -> list:
        """Get recent synchronization sessions."""
        # Implementation would query the database for recent syncs
        return []
    
    def _get_system_info(self) -> Dict[str, Any]:
        """Get system information."""
        return {
            'version': '1.0.0',
            'status': 'running'
        }
    
    def run(self, host: str = 'localhost', port: int = 8080, debug: bool = False) -> None:
        """Run the dashboard server."""
        logger.info(f"Starting dashboard on {host}:{port}")
        self.app.run(host=host, port=port, debug=debug)

