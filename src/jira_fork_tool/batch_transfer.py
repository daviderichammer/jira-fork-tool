"""
Batch transfer script for the Jira Fork Tool.

This script implements a limited batch transfer of issues from source to destination
to facilitate debugging and incremental progress.
"""

import logging
import argparse
import sys
import os
from pathlib import Path
from typing import List, Dict, Any

# Import Config class directly instead of load_config function
from .config import Config
from .auth import AuthManager
from .sync import SyncEngine
from .utils import setup_logging


logger = logging.getLogger(__name__)


def load_config() -> Config:
    """
    Load configuration from the default location or environment variable.
    
    Returns:
        Config: The loaded configuration object
    """
    # Check for config path in environment variable
    config_path_env = os.environ.get('JIRA_FORK_TOOL_CONFIG')
    
    if config_path_env:
        config_path = Path(config_path_env)
    else:
        # Default to config directory in project root
        config_path = Path('config/config.yaml')
    
    # Make path absolute if it's relative
    if not config_path.is_absolute():
        base_dir = Path(__file__).parent.parent.parent
        config_path = base_dir / config_path
    
    logger.info(f"Loading configuration from {config_path}")
    return Config.load(config_path)


def batch_transfer(source_project: str, dest_project: str, limit: int = 5) -> None:
    """
    Transfer a limited batch of issues from source to destination project.
    
    Args:
        source_project: Source project key
        dest_project: Destination project key
        limit: Maximum number of issues to transfer
    """
    logger.info(f"Starting batch transfer: {source_project} -> {dest_project} (limit: {limit})")
    
    # Load configuration
    config = load_config()
    
    # Set up authentication
    auth_manager = AuthManager(config)
    
    # Create sync engine
    sync_engine = SyncEngine(config, auth_manager)
    
    try:
        # Analyze source project
        logger.info("Analyzing source project")
        project_analysis = sync_engine._analyze_source_project(source_project)
        
        # Set up destination project
        logger.info("Setting up destination project")
        sync_engine._setup_destination_project(dest_project, project_analysis)
        
        # Get a limited batch of issues
        logger.info(f"Fetching first {limit} issues from source project")
        source_api = sync_engine.source_api
        issues = source_api.get_issues_in_order(source_project)[:limit]
        
        logger.info(f"Found {len(issues)} issues to transfer")
        
        # Process each issue
        successful_transfers = 0
        for i, issue in enumerate(issues):
            try:
                logger.info(f"Processing issue {i+1}/{len(issues)}: {issue['key']}")
                
                # Process individual issue with detailed logging
                result = process_single_issue_with_logging(sync_engine, issue, dest_project, project_analysis)
                
                # Update counters
                successful_transfers += 1
                
                logger.info(f"Successfully created issue {result['dest_key']} from {result['source_key']}")
                
            except Exception as e:
                logger.error(f"Failed to process issue {issue['key']}: {e}", exc_info=True)
        
        logger.info(f"Batch transfer completed: {successful_transfers}/{len(issues)} issues transferred successfully")
        
    except Exception as e:
        logger.error(f"Batch transfer failed: {e}", exc_info=True)


def process_single_issue_with_logging(sync_engine: SyncEngine, issue: Dict[str, Any], 
                                     dest_project: str, analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Process a single issue with detailed logging for debugging."""
    issue_key = issue['key']
    logger.info(f"Processing issue {issue_key}")
    
    try:
        # Map issue type with logging
        issue_type_name = issue.get('fields', {}).get('issuetype', {}).get('name', 'Task')
        issue_type_id = sync_engine.issue_type_mapping.get(
            issue_type_name,
            # Default to Task if mapping not found
            next((t['id'] for t in sync_engine.dest_api.get_issue_types_for_project(dest_project) 
                 if t['name'] == 'Task'), "10036")  # Fallback to known Task ID
        )
        
        logger.info(f"Mapped issue type '{issue_type_name}' to ID: {issue_type_id}")
        
        # Prepare issue data with minimal required fields
        issue_data = {
            'fields': {
                'project': {'key': dest_project},
                'summary': issue['fields'].get('summary', f"Issue from {issue_key}"),
                'issuetype': {'id': issue_type_id},
            }
        }
        
        # Add description if available
        if 'description' in issue['fields'] and issue['fields']['description']:
            # For Jira Cloud, description must be in Atlassian Document Format
            issue_data['fields']['description'] = {
                "version": 1,
                "type": "doc",
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {
                                "type": "text",
                                "text": f"Original issue: {issue_key}"
                            }
                        ]
                    },
                    {
                        "type": "paragraph",
                        "content": [
                            {
                                "type": "text",
                                "text": str(issue['fields']['description'] or "No description provided.")
                            }
                        ]
                    }
                ]
            }
        
        # Log the issue creation payload for debugging
        logger.info(f"Issue creation payload for {issue_key}: {issue_data}")
        
        # Create issue in destination
        result = sync_engine.dest_api.create_issue(issue_data)
        
        # Log the result
        logger.info(f"Issue creation result: {result}")
        
        # Add issue mapping
        dest_key = result['key']
        sync_engine.state_manager.add_issue_mapping(issue_key, dest_key)
        logger.info(f"Added mapping: {issue_key} -> {dest_key}")
        
        return {
            'source_key': issue_key,
            'dest_key': dest_key,
            'attachments_transferred': 0,
            'comments_synchronized': 0
        }
        
    except Exception as e:
        logger.error(f"Failed to create issue: {e}", exc_info=True)
        raise


def main():
    """Main entry point for the batch transfer script."""
    parser = argparse.ArgumentParser(description='Jira Fork Tool - Batch Transfer')
    parser.add_argument('--source-project', required=True, help='Source project key')
    parser.add_argument('--dest-project', required=True, help='Destination project key')
    parser.add_argument('--limit', type=int, default=5, help='Maximum number of issues to transfer')
    parser.add_argument('--verbose', '-v', action='count', default=0, help='Increase verbosity')
    
    args = parser.parse_args()
    
    # Set up logging
    setup_logging(args.verbose)
    
    # Run batch transfer
    batch_transfer(args.source_project, args.dest_project, args.limit)


if __name__ == '__main__':
    main()
