"""
Core synchronization engine for the Jira Fork Tool.

This module implements the main synchronization logic including sequential
issue processing, gap detection, and comprehensive data transfer.
"""

import logging
import time
import uuid
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Iterator, Set
from pathlib import Path

from ..config import Config
from ..auth import AuthManager
from ..api import JiraAPI, APIError
from ..utils import StateManager, ProgressTracker
from .content_handler import (
    truncate_summary, 
    format_description_for_cloud, 
    format_comment_for_cloud,
    merge_descriptions,
    sanitize_issue_data
)
from .link_mapper import (
    get_available_link_types,
    create_link_type_mapping,
    get_link_type_id,
    create_fallback_link
)


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
    links_created: int = 0
    links_failed: int = 0
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
        
    def fork_project(self, source_project: str, dest_project: str, start_from: Optional[str] = None) -> SyncResult:
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
                sync_id, source_project, dest_project, project_analysis, start_from
            )
            
            # Phase 5: Relationship synchronization
            logger.info("Phase 5: Synchronizing issue relationships")
            link_result = self._synchronize_relationships(sync_id, issue_result['issue_mapping'])
            
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
                links_created=link_result['links_created'],
                links_failed=link_result['links_failed'],
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
    
    def _setup_destination_project(self, project_key: str, analysis: Dict[str, Any]) -> None:
        """Set up the destination project based on source project analysis."""
        logger.info(f"Setting up destination project: {project_key}")
        
        try:
            # Get destination project information
            dest_project = self.dest_api.get_project(project_key)
            
            # Verify project exists
            if not dest_project:
                raise SyncError(f"Destination project {project_key} not found")
            
            logger.info(f"Destination project found: {dest_project.get('name')}")
            
            # Get available issue types in destination
            dest_issue_types = self.dest_api.get_issue_types_for_project(project_key)
            
            # Create issue type mapping
            issue_type_mapping = self._create_issue_type_mapping(
                analysis['issue_types'].keys(),
                dest_issue_types
            )
            
            logger.info(f"Created issue type mapping for {len(issue_type_mapping)} types")
            
            # Get available statuses in destination
            dest_statuses = self.dest_api.get_statuses_for_project(project_key)
            
            # Create status mapping
            status_mapping = self._create_status_mapping(
                analysis.get('statuses', []),
                dest_statuses
            )
            
            logger.info(f"Created status mapping for {len(status_mapping)} statuses")
            
            # Get available link types in destination
            dest_link_types = get_available_link_types(self.dest_api)
            logger.info(f"Found {len(dest_link_types)} link types in destination")
            
            # Store mappings for later use
            self.issue_type_mapping = issue_type_mapping
            self.status_mapping = status_mapping
            self.dest_link_types = dest_link_types
            
            logger.info(f"Destination project setup complete")
            
        except APIError as e:
            raise SyncError(f"Failed to set up destination project: {e}")
    
    def _create_issue_type_mapping(self, source_types: List[str], dest_types: List[Dict[str, Any]]) -> Dict[str, str]:
        """Create mapping between source and destination issue types."""
        mapping = {}
        
        # Create name-to-id mapping for destination types
        dest_type_map = {t['name'].lower(): t['id'] for t in dest_types}
        
        # Map common types directly
        common_types = ['epic', 'story', 'task', 'sub-task', 'bug']
        
        for source_type in source_types:
            source_type_lower = source_type.lower()
            
            # Direct mapping if available
            if source_type_lower in dest_type_map:
                mapping[source_type] = dest_type_map[source_type_lower]
                continue
                
            # Try common type mapping
            mapped = False
            for common_type in common_types:
                if common_type in source_type_lower and common_type in dest_type_map:
                    mapping[source_type] = dest_type_map[common_type]
                    mapped = True
                    break
            
            # Default to Task if no mapping found
            if not mapped and 'task' in dest_type_map:
                mapping[source_type] = dest_type_map['task']
            elif not mapped and dest_types:
                # Last resort: use first available type
                mapping[source_type] = dest_types[0]['id']
        
        return mapping
    
    def _create_status_mapping(self, source_statuses: List[str], dest_statuses: List[Dict[str, Any]]) -> Dict[str, str]:
        """Create mapping between source and destination statuses."""
        mapping = {}
        
        # Create name-to-id mapping for destination statuses
        dest_status_map = {s['name'].lower(): s['id'] for s in dest_statuses}
        
        # Map common statuses
        status_categories = {
            'to do': ['backlog', 'open', 'to do', 'todo', 'new', 'requirements', 'planning'],
            'in progress': ['in progress', 'development', 'coding', 'review', 'testing', 'qa', 'verification'],
            'done': ['done', 'closed', 'resolved', 'complete', 'finished', 'released', 'production']
        }
        
        for source_status in source_statuses:
            source_status_lower = source_status.lower()
            
            # Direct mapping if available
            if source_status_lower in dest_status_map:
                mapping[source_status] = dest_status_map[source_status_lower]
                continue
            
            # Try category mapping
            mapped = False
            for category, keywords in status_categories.items():
                if any(keyword in source_status_lower for keyword in keywords) and category in dest_status_map:
                    mapping[source_status] = dest_status_map[category]
                    mapped = True
                    break
            
            # Default to first status if no mapping found
            if not mapped and dest_statuses:
                mapping[source_status] = dest_statuses[0]['id']
        
        return mapping
    
    def _synchronize_users(self, analysis: Dict[str, Any]) -> Dict[str, str]:
        """Synchronize users between source and destination."""
        logger.info("Synchronizing users")
        
        # Get user mapping from config
        user_mapping = self.config.sync.user_mappings.copy()
        
        # Get all users from source project
        try:
            source_users = self.source_api.get_project_users(analysis['project_info']['key'])
            
            # Get destination users
            dest_users = self.dest_api.get_project_users(self.config.destination.project_key)
            dest_user_map = {u['emailAddress']: u['accountId'] for u in dest_users if 'emailAddress' in u}
            
            # Create mapping for users not already mapped
            for user in source_users:
                email = user.get('emailAddress')
                if email and email not in user_mapping:
                    # Try to find matching user in destination
                    if email in dest_user_map:
                        user_mapping[email] = email  # Direct mapping
                    else:
                        # Default to project lead if no match
                        user_mapping[email] = self.config.destination.auth.email
            
            logger.info(f"Created user mapping for {len(user_mapping)} users")
            return user_mapping
            
        except APIError as e:
            logger.error(f"Failed to synchronize users: {e}")
            return user_mapping
    
    def _check_unsupported_fields(self, custom_fields: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Check for custom fields that are not supported in the destination instance."""
        logger.info("Checking for unsupported custom fields")
        
        # List of field types that are known to be problematic during transfer
        problematic_types = [
            "com.atlassian.jira.plugin.system.customfieldtypes:cascadingselect",
            "com.pyxis.greenhopper.jira:gh-epic-link",
            "com.atlassian.jira.plugin.system.customfieldtypes:multicheckboxes",
            "com.atlassian.jira.plugin.system.customfieldtypes:multigrouppicker",
            "com.atlassian.jira.plugin.system.customfieldtypes:multiselect",
            "com.atlassian.jira.plugin.system.customfieldtypes:multiuserpicker",
            "com.atlassian.jira.plugin.system.customfieldtypes:project",
            "com.atlassian.jira.plugin.system.customfieldtypes:radiobuttons",
            "com.atlassian.jira.plugin.system.customfieldtypes:select",
            "com.atlassian.jira.plugin.system.customfieldtypes:textarea",
            "com.atlassian.jira.plugin.system.customfieldtypes:textfield",
            "com.atlassian.jira.plugin.system.customfieldtypes:url",
            "com.atlassian.jira.plugin.system.customfieldtypes:userpicker",
            "com.atlassian.jira.plugin.system.customfieldtypes:version"
        ]
        
        unsupported = []
        for field in custom_fields:
            if field.get('schema', {}).get('custom') in problematic_types:
                unsupported.append({
                    'id': field.get('id'),
                    'name': field.get('name'),
                    'type': field.get('schema', {}).get('custom'),
                    'reason': "Field type may not transfer correctly"
                })
        
        logger.info(f"Found {len(unsupported)} potentially unsupported fields")
        return unsupported
    
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
                                   dest_project: str, analysis: Dict[str, Any],
                                   start_from: Optional[str] = None) -> Dict[str, Any]:
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
            
            # Determine starting point if specified
            start_index = 0
            if start_from:
                for i, issue in enumerate(issues):
                    if issue['key'] == start_from:
                        start_index = i
                        logger.info(f"Resuming from issue {start_from} (index {start_index})")
                        break
            
            for i, issue in enumerate(issues[start_index:], start=start_index):
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
                    
                    # Update counters
                    issues_processed += 1
                    attachments_transferred += result['attachments_transferred']
                    comments_synchronized += result['comments_synchronized']
                    
                    # Update mapping
                    issue_mapping[issue['key']] = result['dest_key']
                    
                    # Update progress
                    self.progress_tracker.update_progress(i + 1)
                    
                except Exception as e:
                    logger.error(f"Failed to process issue {issue['key']}: {e}")
                    # Continue with next issue instead of failing the entire process
                    
                # Rate limiting
                time.sleep(self.config.sync.rate_limit_buffer)
            
            # Save the complete mapping
            self.state_manager.save_issue_mapping(sync_id, issue_mapping)
            
            return {
                'issue_mapping': issue_mapping,
                'issues_processed': issues_processed,
                'attachments_transferred': attachments_transferred,
                'comments_synchronized': comments_synchronized
            }
            
        except APIError as e:
            raise SyncError(f"Failed to process issues: {e}")
    
    def _synchronize_relationships(self, sync_id: str, issue_mapping: Dict[str, str]) -> Dict[str, int]:
        """Synchronize issue relationships after all issues are created."""
        logger.info("Synchronizing issue relationships")
        
        links_created = 0
        links_failed = 0
        
        try:
            # Get all issue links
            links = self.source_api.get_all_issue_links(list(issue_mapping.keys()))
            logger.info(f"Found {len(links)} issue links to synchronize")
            
            # Get all source link types
            source_link_types = set()
            for link in links:
                source_link_types.add(link['link_type'])
            
            # Create link type mapping
            link_type_mapping = create_link_type_mapping(source_link_types, self.dest_link_types)
            logger.info(f"Created mapping for {len(link_type_mapping)} link types")
            
            # Process links
            for link in links:
                try:
                    source_issue = link['source_issue']
                    target_issue = link['target_issue']
                    link_type = link['link_type']
                    
                    if source_issue in issue_mapping and target_issue in issue_mapping:
                        # Map link type
                        mapped_link_type = link_type_mapping.get(link_type)
                        
                        if mapped_link_type:
                            # Create link in destination
                            self.dest_api.create_issue_link(
                                issue_mapping[source_issue],
                                issue_mapping[target_issue],
                                mapped_link_type
                            )
                            links_created += 1
                            logger.info(f"Created link '{mapped_link_type}': {issue_mapping[source_issue]} -> {issue_mapping[target_issue]}")
                        else:
                            # Try fallback link
                            if create_fallback_link(
                                self.dest_api,
                                issue_mapping[source_issue],
                                issue_mapping[target_issue],
                                self.dest_link_types
                            ):
                                links_created += 1
                            else:
                                links_failed += 1
                                logger.warning(f"Could not create link for {source_issue} -> {target_issue}, no suitable link type found")
                except Exception as e:
                    links_failed += 1
                    logger.error(f"Failed to create link: {e}")
            
            # Get all epic links
            epics = self.source_api.get_all_epic_links(list(issue_mapping.keys()))
            logger.info(f"Found {len(epics)} epic links to synchronize")
            
            # Process epic links
            for epic_link in epics:
                try:
                    epic_key = epic_link['epic_key']
                    issue_key = epic_link['issue_key']
                    
                    if epic_key in issue_mapping and issue_key in issue_mapping:
                        # Create epic link in destination
                        self.dest_api.create_epic_link(
                            issue_mapping[epic_key],
                            issue_mapping[issue_key]
                        )
                        links_created += 1
                        logger.info(f"Created epic link: {issue_mapping[epic_key]} -> {issue_mapping[issue_key]}")
                except Exception as e:
                    links_failed += 1
                    logger.error(f"Failed to create epic link: {e}")
            
            logger.info(f"Relationship synchronization complete: {links_created} created, {links_failed} failed")
            return {
                'links_created': links_created,
                'links_failed': links_failed
            }
                    
        except APIError as e:
            logger.error(f"Failed to synchronize relationships: {e}")
            return {
                'links_created': links_created,
                'links_failed': links_failed
            }
    
    def _validate_synchronization(self, sync_id: str, source_project: str, dest_project: str) -> Dict[str, Any]:
        """Validate the synchronization results."""
        logger.info("Validating synchronization")
        
        try:
            # Get issue counts
            source_count = self.source_api.get_issue_count(source_project)
            dest_count = self.dest_api.get_issue_count(dest_project)
            
            # Get mapping
            mapping = self.state_manager.get_issue_mapping(sync_id)
            
            # Calculate statistics
            result = {
                'source_issues': source_count,
                'dest_issues': dest_count,
                'mapped_issues': len(mapping),
                'coverage': len(mapping) / source_count if source_count > 0 else 0,
                'validation_time': datetime.now().isoformat()
            }
            
            logger.info(f"Validation complete:")
            logger.info(f"  Source issues: {result['source_issues']}")
            logger.info(f"  Destination issues: {result['dest_issues']}")
            logger.info(f"  Mapped issues: {result['mapped_issues']}")
            logger.info(f"  Coverage: {result['coverage']:.2%}")
            
            return result
            
        except APIError as e:
            logger.error(f"Validation failed: {e}")
            return {
                'error': str(e),
                'validation_time': datetime.now().isoformat()
            }
    
    def _detect_changes_since(self, timestamp: datetime) -> List[Dict[str, Any]]:
        """Detect changes in source project since the given timestamp."""
        logger.info(f"Detecting changes since {timestamp}")
        
        try:
            # Get updated issues
            updated_issues = self.source_api.get_updated_issues(
                self.config.source.project_key,
                timestamp
            )
            
            logger.info(f"Found {len(updated_issues)} updated issues")
            return updated_issues
            
        except APIError as e:
            logger.error(f"Failed to detect changes: {e}")
            return []
    
    def _process_incremental_changes(self, sync_id: str, changes: List[Dict[str, Any]]) -> int:
        """Process incremental changes."""
        logger.info(f"Processing {len(changes)} incremental changes")
        
        changes_processed = 0
        
        try:
            # Get mapping
            mapping = self.state_manager.get_issue_mapping(sync_id)
            
            for change in changes:
                try:
                    issue_key = change['key']
                    
                    if issue_key in mapping:
                        # Update existing issue
                        dest_key = mapping[issue_key]
                        self.dest_api.update_issue(dest_key, change)
                    else:
                        # Create new issue
                        result = self._process_single_issue(
                            change,
                            self.config.destination.project_key,
                            {}
                        )
                        
                        # Update mapping
                        mapping[issue_key] = result['dest_key']
                        self.state_manager.save_issue_mapping(sync_id, mapping)
                    
                    changes_processed += 1
                    
                except Exception as e:
                    logger.error(f"Failed to process change for {change['key']}: {e}")
            
            return changes_processed
            
        except Exception as e:
            logger.error(f"Failed to process incremental changes: {e}")
            return changes_processed
    
    def _resume_issue_processing(self, sync_id: str, checkpoint: Dict[str, Any]) -> SyncResult:
        """Resume issue processing from checkpoint."""
        logger.info(f"Resuming issue processing from checkpoint")
        
        start_time = datetime.now()
        
        try:
            # Load sync state
            sync_state = self.state_manager.get_sync_session(sync_id)
            
            # Get last processed issue
            last_issue = checkpoint['data']['last_processed_issue']
            
            # Resume processing
            result = self._process_issues_sequentially(
                sync_id,
                sync_state['source_project'],
                sync_state['dest_project'],
                self.state_manager.get_project_analysis(sync_id),
                start_from=last_issue
            )
            
            # Continue with relationship synchronization
            link_result = self._synchronize_relationships(sync_id, result['issue_mapping'])
            
            # Validate
            validation_result = self._validate_synchronization(
                sync_id,
                sync_state['source_project'],
                sync_state['dest_project']
            )
            
            end_time = datetime.now()
            
            # Create result
            result = SyncResult(
                success=True,
                sync_id=sync_id,
                issues_processed=result['issues_processed'],
                attachments_transferred=result['attachments_transferred'],
                comments_synchronized=result['comments_synchronized'],
                links_created=link_result['links_created'],
                links_failed=link_result['links_failed'],
                start_time=start_time,
                end_time=end_time
            )
            
            # Update final state
            self.state_manager.complete_sync_session(sync_id, result)
            
            logger.info(f"Resume completed successfully in {result.duration}")
            return result
            
        except Exception as e:
            logger.exception(f"Resume failed: {e}")
            
            return SyncResult(
                success=False,
                sync_id=sync_id,
                error_message=str(e),
                start_time=start_time,
                end_time=datetime.now()
            )
            
    def _process_single_issue(self, issue: Dict[str, Any], dest_project: str, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single issue from source to destination."""
        logger.info(f"Processing issue {issue['key']}")
        
        try:
            # Map issue type
            issue_type_id = self.issue_type_mapping.get(
                issue.get('fields', {}).get('issuetype', {}).get('name', 'Task'),
                # Default to Task if mapping not found
                next((t['id'] for t in self.dest_api.get_issue_types_for_project(dest_project) 
                     if t['name'] == 'Task'), None)
            )
            
            if not issue_type_id:
                # Fallback to a known issue type ID for Task
                issue_type_id = "10036"  # Task ID from our analysis
                logger.warning(f"Using fallback issue type ID for {issue['key']}: {issue_type_id}")
            
            # Prepare issue data with minimal required fields
            issue_data = {
                'fields': {
                    'project': {'key': dest_project},
                    'summary': truncate_summary(issue['fields'].get('summary', f"Issue from {issue['key']}")),
                    'issuetype': {'id': issue_type_id},
                }
            }
            
            # Add description if available
            if 'description' in issue['fields']:
                # Use content handler to format and truncate if needed
                issue_data['fields']['description'] = merge_descriptions(
                    issue['key'],
                    issue['fields']['description']
                )
            
            # Sanitize the issue data to ensure it meets Jira Cloud API requirements
            issue_data = sanitize_issue_data(issue_data)
            
            # Log the issue creation payload for debugging
            logger.info(f"Issue creation payload for {issue['key']}: {json.dumps(issue_data)}")
            
            # Create issue in destination
            result = self.dest_api.create_issue(issue_data)
            
            # Process attachments if enabled
            attachments_transferred = 0
            if self.config.sync.include_attachments and 'attachment' in issue['fields']:
                attachments_transferred = self._transfer_attachments(
                    issue['fields']['attachment'],
                    result['key']
                )
            
            # Process comments if enabled
            comments_synchronized = 0
            if self.config.sync.include_comments and 'comment' in issue['fields']:
                comments_synchronized = self._transfer_comments(
                    issue['fields']['comment'].get('comments', []),
                    result['key']
                )
            
            # Update issue mapping
            self.state_manager.add_issue_mapping(
                issue['key'],
                result['key']
            )
            
            logger.info(f"Created issue {result['key']} from {issue['key']}")
            
            return {
                'source_key': issue['key'],
                'dest_key': result['key'],
                'attachments_transferred': attachments_transferred,
                'comments_synchronized': comments_synchronized
            }
            
        except APIError as e:
            logger.error(f"Failed to create issue: {e}")
            raise SyncError(f"Failed to process issue {issue['key']}: {e}")
    
    def _transfer_attachments(self, attachments: List[Dict[str, Any]], dest_key: str) -> int:
        """Transfer attachments from source issue to destination issue."""
        transferred = 0
        
        for attachment in attachments:
            try:
                # Download attachment
                content = self.source_api.download_attachment(attachment['id'])
                
                # Upload to destination
                self.dest_api.add_attachment(
                    dest_key,
                    attachment['filename'],
                    content
                )
                
                transferred += 1
                
            except Exception as e:
                logger.error(f"Failed to transfer attachment {attachment['filename']}: {e}")
        
        return transferred
    
    def _transfer_comments(self, comments: List[Dict[str, Any]], dest_key: str) -> int:
        """Transfer comments from source issue to destination issue."""
        transferred = 0
        
        for comment in comments:
            try:
                # Prepare comment data
                author = comment.get('author', {}).get('displayName', 'Unknown')
                created = comment.get('created', 'Unknown date')
                body = comment.get('body', '')
                
                # Use content handler to format and truncate if needed
                comment_data = {
                    'body': format_comment_for_cloud(
                        f"[Comment by {author} on {created}]\n\n{body}"
                    )
                }
                
                # Add comment to destination
                self.dest_api.add_comment(dest_key, comment_data)
                
                transferred += 1
                
            except Exception as e:
                logger.error(f"Failed to transfer comment: {e}")
        
        return transferred
