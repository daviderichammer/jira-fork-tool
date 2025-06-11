"""
Main entry point for the Jira Fork Tool.

This module provides the command-line interface and orchestrates the overall
synchronization process.
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

from .config import Config, ConfigError
from .sync import SyncEngine, SyncError
from .auth import AuthManager, AuthError
from .ui import Dashboard
from .utils import setup_logging, validate_environment


def create_parser() -> argparse.ArgumentParser:
    """Create and configure the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Jira Fork Tool - Synchronize Jira projects across organizations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Fork a complete project
  jira-fork-tool fork --source-project SOURCE --dest-project DEST
  
  # Fork with custom configuration
  jira-fork-tool fork --config custom-config.yaml
  
  # Resume interrupted synchronization
  jira-fork-tool resume --sync-id abc123
  
  # Start web dashboard
  jira-fork-tool dashboard --port 8080
        """
    )
    
    parser.add_argument(
        "--config", "-c",
        type=Path,
        default="config/config.yaml",
        help="Configuration file path (default: config/config.yaml)"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="count",
        default=0,
        help="Increase verbosity (use -v, -vv, or -vvv)"
    )
    
    parser.add_argument(
        "--log-file",
        type=Path,
        help="Log file path (default: logs/jira-fork-tool.log)"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Fork command
    fork_parser = subparsers.add_parser(
        "fork",
        help="Fork a complete Jira project"
    )
    fork_parser.add_argument(
        "--source-project",
        required=True,
        help="Source project key"
    )
    fork_parser.add_argument(
        "--dest-project", 
        required=True,
        help="Destination project key"
    )
    fork_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform a dry run without making changes"
    )
    
    # Sync command
    sync_parser = subparsers.add_parser(
        "sync",
        help="Perform incremental synchronization"
    )
    sync_parser.add_argument(
        "--incremental",
        action="store_true",
        help="Sync only changes since last update"
    )
    sync_parser.add_argument(
        "--since",
        help="Sync changes since this date (YYYY-MM-DD)"
    )
    sync_parser.add_argument(
        "--until",
        help="Sync changes until this date (YYYY-MM-DD)"
    )
    
    # Resume command
    resume_parser = subparsers.add_parser(
        "resume",
        help="Resume interrupted synchronization"
    )
    resume_parser.add_argument(
        "--sync-id",
        required=True,
        help="Synchronization ID to resume"
    )
    
    # Dashboard command
    dashboard_parser = subparsers.add_parser(
        "dashboard",
        help="Start web dashboard"
    )
    dashboard_parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Dashboard port (default: 8080)"
    )
    dashboard_parser.add_argument(
        "--host",
        default="localhost",
        help="Dashboard host (default: localhost)"
    )
    
    # Validate command
    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate configuration and connectivity"
    )
    
    return parser


def handle_fork_command(args, config: Config) -> int:
    """Handle the fork command."""
    try:
        # Initialize authentication
        auth_manager = AuthManager(config)
        auth_manager.validate_credentials()
        
        # Initialize sync engine
        sync_engine = SyncEngine(config, auth_manager)
        
        # Perform the fork operation
        if args.dry_run:
            logging.info("Performing dry run - no changes will be made")
            result = sync_engine.dry_run_fork(
                args.source_project,
                args.dest_project
            )
        else:
            result = sync_engine.fork_project(
                args.source_project,
                args.dest_project
            )
        
        if result.success:
            logging.info(f"Fork completed successfully. Sync ID: {result.sync_id}")
            print(f"✓ Fork completed successfully")
            print(f"  Sync ID: {result.sync_id}")
            print(f"  Issues processed: {result.issues_processed}")
            print(f"  Attachments transferred: {result.attachments_transferred}")
            print(f"  Comments synchronized: {result.comments_synchronized}")
            return 0
        else:
            logging.error(f"Fork failed: {result.error_message}")
            print(f"✗ Fork failed: {result.error_message}")
            return 1
            
    except (AuthError, SyncError, ConfigError) as e:
        logging.error(f"Fork operation failed: {e}")
        print(f"✗ Error: {e}")
        return 1
    except Exception as e:
        logging.exception("Unexpected error during fork operation")
        print(f"✗ Unexpected error: {e}")
        return 1


def handle_sync_command(args, config: Config) -> int:
    """Handle the sync command."""
    try:
        # Initialize authentication
        auth_manager = AuthManager(config)
        auth_manager.validate_credentials()
        
        # Initialize sync engine
        sync_engine = SyncEngine(config, auth_manager)
        
        # Perform incremental sync
        if args.incremental:
            result = sync_engine.incremental_sync()
        else:
            result = sync_engine.sync_date_range(args.since, args.until)
        
        if result.success:
            logging.info("Incremental sync completed successfully")
            print(f"✓ Sync completed successfully")
            print(f"  Changes processed: {result.changes_processed}")
            return 0
        else:
            logging.error(f"Sync failed: {result.error_message}")
            print(f"✗ Sync failed: {result.error_message}")
            return 1
            
    except (AuthError, SyncError, ConfigError) as e:
        logging.error(f"Sync operation failed: {e}")
        print(f"✗ Error: {e}")
        return 1
    except Exception as e:
        logging.exception("Unexpected error during sync operation")
        print(f"✗ Unexpected error: {e}")
        return 1


def handle_resume_command(args, config: Config) -> int:
    """Handle the resume command."""
    try:
        # Initialize authentication
        auth_manager = AuthManager(config)
        auth_manager.validate_credentials()
        
        # Initialize sync engine
        sync_engine = SyncEngine(config, auth_manager)
        
        # Resume synchronization
        result = sync_engine.resume_sync(args.sync_id)
        
        if result.success:
            logging.info(f"Resume completed successfully for sync ID: {args.sync_id}")
            print(f"✓ Resume completed successfully")
            return 0
        else:
            logging.error(f"Resume failed: {result.error_message}")
            print(f"✗ Resume failed: {result.error_message}")
            return 1
            
    except (AuthError, SyncError, ConfigError) as e:
        logging.error(f"Resume operation failed: {e}")
        print(f"✗ Error: {e}")
        return 1
    except Exception as e:
        logging.exception("Unexpected error during resume operation")
        print(f"✗ Unexpected error: {e}")
        return 1


def handle_dashboard_command(args, config: Config) -> int:
    """Handle the dashboard command."""
    try:
        dashboard = Dashboard(config)
        print(f"Starting dashboard on http://{args.host}:{args.port}")
        dashboard.run(host=args.host, port=args.port)
        return 0
        
    except Exception as e:
        logging.exception("Error starting dashboard")
        print(f"✗ Dashboard error: {e}")
        return 1


def handle_validate_command(args, config: Config) -> int:
    """Handle the validate command."""
    try:
        print("Validating configuration and connectivity...")
        
        # Validate environment
        env_issues = validate_environment()
        if env_issues:
            print("✗ Environment validation failed:")
            for issue in env_issues:
                print(f"  - {issue}")
            return 1
        
        print("✓ Environment validation passed")
        
        # Validate authentication
        auth_manager = AuthManager(config)
        auth_result = auth_manager.validate_credentials()
        
        if auth_result.source_valid and auth_result.dest_valid:
            print("✓ Authentication validation passed")
            print(f"  Source: {config.source.url} - {auth_result.source_permissions}")
            print(f"  Destination: {config.destination.url} - {auth_result.dest_permissions}")
            return 0
        else:
            print("✗ Authentication validation failed:")
            if not auth_result.source_valid:
                print(f"  Source: {auth_result.source_error}")
            if not auth_result.dest_valid:
                print(f"  Destination: {auth_result.dest_error}")
            return 1
            
    except (AuthError, ConfigError) as e:
        print(f"✗ Validation error: {e}")
        return 1
    except Exception as e:
        logging.exception("Unexpected error during validation")
        print(f"✗ Unexpected error: {e}")
        return 1


def main(argv: Optional[list] = None) -> int:
    """Main entry point for the Jira Fork Tool."""
    parser = create_parser()
    args = parser.parse_args(argv)
    
    # Setup logging
    setup_logging(
        level=args.verbose,
        log_file=args.log_file
    )
    
    try:
        # Load configuration
        config = Config.load(args.config)
        logging.info(f"Loaded configuration from {args.config}")
        
        # Handle commands
        if args.command == "fork":
            return handle_fork_command(args, config)
        elif args.command == "sync":
            return handle_sync_command(args, config)
        elif args.command == "resume":
            return handle_resume_command(args, config)
        elif args.command == "dashboard":
            return handle_dashboard_command(args, config)
        elif args.command == "validate":
            return handle_validate_command(args, config)
        else:
            parser.print_help()
            return 1
            
    except ConfigError as e:
        print(f"✗ Configuration error: {e}")
        return 1
    except KeyboardInterrupt:
        print("\n✗ Operation cancelled by user")
        return 1
    except Exception as e:
        logging.exception("Unexpected error in main")
        print(f"✗ Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

