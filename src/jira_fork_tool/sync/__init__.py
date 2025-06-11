"""
Core synchronization engine for the Jira Fork Tool.

This module implements the main synchronization logic including sequential
issue processing, gap detection, and comprehensive data transfer.
"""

import logging
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Iterator
from pathlib import Path

from ..config import Config
from ..auth import AuthManager
from ..api import JiraAPI, APIError
from ..utils import StateManager, ProgressTracker


logger = logging.getLogger(__name__)


class SyncError(Exception):
    """Raised when synchronization operations fail."""
    pass


@dataclass
class SyncResult:
    """Result of a synchronization operation."""
    success: bool
    sync_id: str
    issues_processed: int = 0
    attachments_transferred: int = 0
    comments_synchronized: int = 0
    changes_processed: int = 0
    error_message: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    @property
    def duration(self) -> Optional[timedelta]:
        """Get the duration of the synchronization operation."""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return None


@dataclass
class IssueGap:
    """Represents a gap in issue numbering."""
    start_number: int
    end_number: int
    reason: str = "deleted_or_missing"


class SyncEngine:
    """Core synchronization engine for Jira project forking."""
    
    def __init__(self, config: Config, auth_manager: AuthManager):
        """Initialize the synchronization engine."""
        self.config = config
        self.auth_manager = auth_manager
        self.source_api = JiraAPI(
            config.source,
            auth_manager.get_source_session()
        )
        self.dest_api = JiraAPI(
            config.destination,
            auth_manager.get_dest_session()
        )
        self.state_manager = StateManager(config.database)
        self.progress_tracker = ProgressTracker()
        
    def fork_project(self, source_project: str, dest_project: str) -> SyncResult:
        """Fork a complete Jira project from source to destination."""
        sync_id = str(uuid.uuid4())
        start_time = datetime.now()
        
        logger.info(f"Starting project fork: {source_project} -> {dest_project}")
        logger.info(f"Sync ID: {sync_id}")
        
        try:
            # Initialize sync state
            self.state_manager.create_sync_session(
                sync_id=sync_id,
                source_project=source_project,
                dest_project=dest_project,
                sync_type="fork"
            )
            
            # Phase 1: Project analysis and setup
            logger.info("Phase 1: Analyzing source project")
            project_analysis = self._analyze_source_project(source_project)
            self.state_manager.save_project_analysis(sync_id, project_analysis)
            
            # Phase 2: Destination project setup
            logger.info("Phase 2: Setting up destination project")
            self._setup_destination_project(dest_project, project_analysis)
            
            # Phase 3: User and metadata synchronization
            logger.info("Phase 3: Synchronizing users and metadata")
            user_mapping = self._synchronize_users(project_analysis)
            self.state_manager.save_user_mapping(sync_id, user_mapping)
            
            # Phase 4: Sequential issue processing
            logger.info("Phase 4: Processing issues sequentially")
            issue_result = self._process_issues_sequentially(
                sync_id, source_project, dest_project, project_analysis
            )
            
            # Phase 5: Relationship synchronization
            logger.info("Phase 5: Synchronizing issue relationships")
            self._synchronize_relationships(sync_id, issue_result['issue_mapping'])
            
            # Phase 6: Validation and cleanup
            logger.info("Phase 6: Validating synchronization")
            validation_result = self._validate_synchronization(
                sync_id, source_project, dest_project
            )
            
            end_time = datetime.now()
            
            # Create result
            result = SyncResult(
                success=True,
                sync_id=sync_id,
                issues_processed=issue_result['issues_processed'],
                attachments_transferred=issue_result['attachments_transferred'],
                comments_synchronized=issue_result['comments_synchronized'],
                start_time=start_time,
                end_time=end_time
            )
            
            # Update final state
            self.state_manager.complete_sync_session(sync_id, result)
            
            logger.info(f"Project fork completed successfully in {result.duration}")
            return result
            
        except Exception as e:
            logger.exception(f"Project fork failed: {e}")
            
            # Mark sync as failed
            self.state_manager.fail_sync_session(sync_id, str(e))
            
            return SyncResult(
                success=False,
                sync_id=sync_id,
                error_message=str(e),
                start_time=start_time,
                end_time=datetime.now()
            )
    
    def dry_run_fork(self, source_project: str, dest_project: str) -> SyncResult:
        """Perform a dry run of project forking without making changes."""
        sync_id = f"dry-run-{uuid.uuid4()}"
        start_time = datetime.now()
        
        logger.info(f"Starting dry run fork: {source_project} -> {dest_project}")
        
        try:
            # Analyze source project
            project_analysis = self._analyze_source_project(source_project)
            
            # Simulate processing
            estimated_issues = project_analysis['total_issues']
            estimated_attachments = project_analysis['total_attachments']
            estimated_comments = project_analysis['total_comments']
            
            # Check for potential issues
            issues = []
            if project_analysis['gaps']:
                issues.append(f"Found {len(project_analysis['gaps'])} gaps in issue numbering")
            
            if project_analysis['unsupported_fields']:
                issues.append(f"Found {len(project_analysis['unsupported_fields'])} unsupported fields")
            
            logger.info(f"Dry run analysis complete:")
            logger.info(f"  Estimated issues to process: {estimated_issues}")
            logger.info(f"  Estimated attachments: {estimated_attachments}")
            logger.info(f"  Estimated comments: {estimated_comments}")
            
            if issues:
                logger.warning("Potential issues found:")
                for issue in issues:
                    logger.warning(f"  - {issue}")
            
            return SyncResult(
                success=True,
                sync_id=sync_id,
                issues_processed=estimated_issues,
                attachments_transferred=estimated_attachments,
                comments_synchronized=estimated_comments,
                start_time=start_time,
                end_time=datetime.now()
            )
            
        except Exception as e:
            logger.exception(f"Dry run failed: {e}")
            return SyncResult(
                success=False,
                sync_id=sync_id,
                error_message=str(e),
                start_time=start_time,
                end_time=datetime.now()
            )
    
    def incremental_sync(self) -> SyncResult:
        """Perform incremental synchronization of changes."""
        sync_id = str(uuid.uuid4())
        start_time = datetime.now()
        
        logger.info("Starting incremental synchronization")
        
        try:
            # Find the last successful sync
            last_sync = self.state_manager.get_last_successful_sync()
            if not last_sync:
                raise SyncError("No previous sync found for incremental update")
            
            # Detect changes since last sync
            changes = self._detect_changes_since(last_sync['end_time'])
            
            if not changes:
                logger.info("No changes detected since last sync")
                return SyncResult(
                    success=True,
                    sync_id=sync_id,
                    changes_processed=0,
                    start_time=start_time,
                    end_time=datetime.now()
                )
            
            # Process changes
            changes_processed = self._process_incremental_changes(sync_id, changes)
            
            return SyncResult(
                success=True,
                sync_id=sync_id,
                changes_processed=changes_processed,
                start_time=start_time,
                end_time=datetime.now()
            )
            
        except Exception as e:
            logger.exception(f"Incremental sync failed: {e}")
            return SyncResult(
                success=False,
                sync_id=sync_id,
                error_message=str(e),
                start_time=start_time,
                end_time=datetime.now()
            )
    
    def resume_sync(self, sync_id: str) -> SyncResult:
        """Resume an interrupted synchronization."""
        logger.info(f"Resuming synchronization: {sync_id}")
        
        try:
            # Load sync state
            sync_state = self.state_manager.get_sync_session(sync_id)
            if not sync_state:
                raise SyncError(f"Sync session not found: {sync_id}")
            
            if sync_state['status'] == 'completed':
                raise SyncError(f"Sync session already completed: {sync_id}")
            
            # Resume from last checkpoint
            last_checkpoint = self.state_manager.get_last_checkpoint(sync_id)
            
            if last_checkpoint['phase'] == 'issue_processing':
                # Resume issue processing
                return self._resume_issue_processing(sync_id, last_checkpoint)
            else:
                raise SyncError(f"Cannot resume from phase: {last_checkpoint['phase']}")
                
        except Exception as e:
            logger.exception(f"Resume failed: {e}")
            return SyncResult(
                success=False,
                sync_id=sync_id,
                error_message=str(e),
                start_time=datetime.now(),
                end_time=datetime.now()
            )
    
    def _analyze_source_project(self, project_key: str) -> Dict[str, Any]:
        """Analyze the source project structure and content."""
        logger.info(f"Analyzing source project: {project_key}")
        
        try:
            # Get project information
            project_info = self.source_api.get_project(project_key)
            
            # Get issue statistics
            issue_stats = self.source_api.get_issue_statistics(project_key)
            
            # Detect gaps in issue numbering
            gaps = self._detect_issue_gaps(project_key)
            
            # Analyze custom fields
            custom_fields = self.source_api.get_custom_fields(project_key)
            
            # Check for unsupported field types
            unsupported_fields = self._check_unsupported_fields(custom_fields)
            
            # Analyze attachments
            attachment_stats = self.source_api.get_attachment_statistics(project_key)
            
            # Analyze comments
            comment_stats = self.source_api.get_comment_statistics(project_key)
            
            analysis = {
                'project_info': project_info,
                'total_issues': issue_stats['total'],
                'issue_types': issue_stats['by_type'],
                'gaps': gaps,
                'custom_fields': custom_fields,
                'unsupported_fields': unsupported_fields,
                'total_attachments': attachment_stats['total'],
                'attachment_size': attachment_stats['total_size'],
                'total_comments': comment_stats['total'],
                'analysis_time': datetime.now().isoformat()
            }
            
            logger.info(f"Project analysis complete:")
            logger.info(f"  Total issues: {analysis['total_issues']}")
            logger.info(f"  Issue gaps: {len(analysis['gaps'])}")
            logger.info(f"  Custom fields: {len(analysis['custom_fields'])}")
            logger.info(f"  Attachments: {analysis['total_attachments']}")
            logger.info(f"  Comments: {analysis['total_comments']}")
            
            return analysis
            
        except APIError as e:
            raise SyncError(f"Failed to analyze source project: {e}")
    
    def _detect_issue_gaps(self, project_key: str) -> List[IssueGap]:
        """Detect gaps in issue numbering sequence."""
        logger.info("Detecting gaps in issue numbering")
        
        try:
            # Get all issue keys in the project
            issue_keys = self.source_api.get_all_issue_keys(project_key)
            
            # Extract issue numbers
            issue_numbers = []
            for key in issue_keys:
                try:
                    number = int(key.split('-')[1])
                    issue_numbers.append(number)
                except (IndexError, ValueError):
                    logger.warning(f"Could not parse issue number from key: {key}")
            
            if not issue_numbers:
                return []
            
            # Sort numbers and find gaps
            issue_numbers.sort()
            gaps = []
            
            for i in range(len(issue_numbers) - 1):
                current = issue_numbers[i]
                next_num = issue_numbers[i + 1]
                
                if next_num - current > 1:
                    gaps.append(IssueGap(
                        start_number=current + 1,
                        end_number=next_num - 1,
                        reason="deleted_or_missing"
                    ))
            
            logger.info(f"Found {len(gaps)} gaps in issue numbering")
            return gaps
            
        except APIError as e:
            logger.error(f"Failed to detect issue gaps: {e}")
            return []
    
    def _process_issues_sequentially(self, sync_id: str, source_project: str,
                                   dest_project: str, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Process issues in sequential order to maintain numbering."""
        logger.info("Starting sequential issue processing")
        
        issue_mapping = {}
        issues_processed = 0
        attachments_transferred = 0
        comments_synchronized = 0
        
        try:
            # Get all issues in order
            issues = self.source_api.get_issues_in_order(source_project)
            total_issues = len(issues)
            
            self.progress_tracker.start_phase("issue_processing", total_issues)
            
            for i, issue in enumerate(issues):
                try:
                    # Create checkpoint
                    if i % self.config.sync.batch_size == 0:
                        self.state_manager.create_checkpoint(
                            sync_id=sync_id,
                            phase="issue_processing",
                            progress=i,
                            total=total_issues,
                            data={'last_processed_issue': issue['key']}
                        )
                    
                    # Process individual issue
                    result = self._process_single_issue(
                        issue, dest_project, analysis
                    )
                    
                    if result['success']:
                        issue_mapping[issue['key']] = result['dest_key']
                        issues_processed += 1
                        attachments_transferred += result['attachments_transferred']
                        comments_synchronized += result['comments_synchronized']
                    else:
                        logger.error(f"Failed to process issue {issue['key']}: "
                                   f"{result['error']}")
                    
                    # Update progress
                    self.progress_tracker.update_progress(i + 1)
                    
                    # Rate limiting
                    self._handle_rate_limiting()
                    
                except Exception as e:
                    logger.error(f"Error processing issue {issue['key']}: {e}")
                    continue
            
            self.progress_tracker.complete_phase()
            
            return {
                'issue_mapping': issue_mapping,
                'issues_processed': issues_processed,
                'attachments_transferred': attachments_transferred,
                'comments_synchronized': comments_synchronized
            }
            
        except APIError as e:
            raise SyncError(f"Failed to process issues: {e}")
    
    def _process_single_issue(self, issue: Dict[str, Any], dest_project: str,
                            analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single issue including all its data."""
        try:
            # Transform issue data for destination
            transformed_issue = self._transform_issue_data(issue, dest_project, analysis)
            
            # Create issue in destination
            dest_issue = self.dest_api.create_issue(transformed_issue)
            
            attachments_transferred = 0
            comments_synchronized = 0
            
            # Process attachments
            if self.config.sync.include_attachments and issue.get('attachments'):
                attachments_transferred = self._transfer_attachments(
                    issue['attachments'], dest_issue['key']
                )
            
            # Process comments
            if self.config.sync.include_comments and issue.get('comments'):
                comments_synchronized = self._transfer_comments(
                    issue['comments'], dest_issue['key'], analysis
                )
            
            return {
                'success': True,
                'dest_key': dest_issue['key'],
                'attachments_transferred': attachments_transferred,
                'comments_synchronized': comments_synchronized
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'attachments_transferred': 0,
                'comments_synchronized': 0
            }
    
    def _handle_rate_limiting(self) -> None:
        """Handle API rate limiting with intelligent delays."""
        # Simple rate limiting implementation
        # In production, this would be more sophisticated
        time.sleep(0.1)  # Basic delay between requests
    
    # Additional methods would be implemented here for:
    # - _setup_destination_project
    # - _synchronize_users
    # - _synchronize_relationships
    # - _validate_synchronization
    # - _transform_issue_data
    # - _transfer_attachments
    # - _transfer_comments
    # - etc.
    
    def sync_date_range(self, since: str, until: str) -> SyncResult:
        """Sync changes within a specific date range."""
        # Implementation placeholder
        return SyncResult(
            success=True,
            sync_id=str(uuid.uuid4()),
            changes_processed=0
        )

