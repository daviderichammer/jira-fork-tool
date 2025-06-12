"""
Link type mapping utilities for the Jira Fork Tool.

This module provides functions for mapping link types between source and destination
Jira instances, handling missing link types, and creating fallback relationships.
"""

import logging
from typing import Dict, Any, Optional, List, Set

logger = logging.getLogger(__name__)

# Standard Jira link types and their common alternatives
STANDARD_LINK_TYPES = {
    # Primary name: [alternative names]
    "relates to": ["related to", "relates", "related"],
    "blocks": ["blocking", "blocks", "blocked"],
    "is blocked by": ["blocked by", "is blocked", "depends on"],
    "causes": ["causes", "caused", "cause"],
    "is caused by": ["caused by", "effect of", "result of"],
    "clones": ["clone", "cloned from", "duplicate"],
    "is cloned by": ["cloned by", "cloned to", "duplicated by"],
    "duplicates": ["duplicate of", "same as"],
    "is duplicated by": ["duplicated by", "copied from"],
    "parent": ["parent of", "parent task"],
    "child": ["child of", "subtask of"],
    "depends on": ["dependency", "dependent on"],
    "is required for": ["required for", "required by"],
    "follows": ["follows after", "successor of"],
    "precedes": ["precedes", "predecessor of"]
}

class LinkTypeMapper:
    """
    Maps link types between source and destination Jira instances,
    handling missing link types and providing fallback options.
    """
    
    def __init__(self, dest_link_types: List[Dict[str, Any]]):
        """
        Initialize the link type mapper.
        
        Args:
            dest_link_types: List of destination link types from JiraAPI.get_issue_link_types()
        """
        self.dest_link_types = dest_link_types
        self.link_type_map = {}
        
        # Create a mapping of link type names to their details
        self.dest_link_type_map = {}
        for link_type in dest_link_types:
            name = link_type.get('name', '').lower()
            inward = link_type.get('inward', '').lower()
            outward = link_type.get('outward', '').lower()
            
            self.dest_link_type_map[name] = link_type
            if inward and inward != name:
                self.dest_link_type_map[inward] = link_type
            if outward and outward != name and outward != inward:
                self.dest_link_type_map[outward] = link_type
    
    def map_link_type(self, source_link_type: str) -> Optional[str]:
        """
        Map a source link type to a destination link type.
        
        Args:
            source_link_type: Source link type name
            
        Returns:
            Mapped destination link type name or None if no mapping found
        """
        # Check if we've already mapped this link type
        if source_link_type in self.link_type_map:
            return self.link_type_map[source_link_type]
        
        source_link_type_lower = source_link_type.lower()
        
        # Direct match
        if source_link_type_lower in self.dest_link_type_map:
            self.link_type_map[source_link_type] = source_link_type
            return source_link_type
        
        # Try to find a standard alternative
        for standard_type, alternatives in STANDARD_LINK_TYPES.items():
            if source_link_type_lower == standard_type or source_link_type_lower in alternatives:
                if standard_type in self.dest_link_type_map:
                    self.link_type_map[source_link_type] = standard_type
                    return standard_type
                else:
                    # Try alternatives of the standard type
                    for alt in alternatives:
                        if alt in self.dest_link_type_map:
                            self.link_type_map[source_link_type] = alt
                            return alt
        
        # No mapping found
        return None
    
    def get_fallback_link_type(self) -> Optional[str]:
        """
        Get a fallback link type when no direct mapping is available.
        
        Returns:
            Fallback link type name or None if no fallback available
        """
        # Try to use "relates to" as fallback
        if "relates to" in self.dest_link_type_map:
            return "relates to"
        
        # Try any available link type
        if self.dest_link_type_map:
            return next(iter(self.dest_link_type_map.keys()))
        
        return None
    
    def get_link_type_id(self, link_type: str) -> Optional[str]:
        """
        Get the ID for a link type name.
        
        Args:
            link_type: Link type name
            
        Returns:
            Link type ID or None if not found
        """
        link_type_lower = link_type.lower()
        
        if link_type_lower in self.dest_link_type_map:
            return self.dest_link_type_map[link_type_lower].get('id')
        
        return None


def get_available_link_types(api) -> Dict[str, str]:
    """
    Get available link types from the Jira API.
    
    Args:
        api: JiraAPI instance
        
    Returns:
        Dictionary mapping link type names to IDs
    """
    try:
        link_types = api.get_issue_link_types()
        return {lt['name'].lower(): lt['id'] for lt in link_types}
    except Exception as e:
        logger.error(f"Failed to get link types: {e}")
        return {}

def create_link_type_mapping(source_types: Set[str], dest_types: Dict[str, str]) -> Dict[str, str]:
    """
    Create mapping between source and destination link types.
    
    Args:
        source_types: Set of source link type names
        dest_types: Dictionary of destination link type names to IDs
        
    Returns:
        Dictionary mapping source link type names to destination link type names
    """
    mapping = {}
    
    # Normalize all keys to lowercase for case-insensitive matching
    dest_types_lower = {k.lower(): v for k, v in dest_types.items()}
    
    for source_type in source_types:
        source_type_lower = source_type.lower()
        
        # Direct match
        if source_type_lower in dest_types_lower:
            mapping[source_type] = source_type
            continue
        
        # Try to find a standard alternative
        mapped = False
        for standard_type, alternatives in STANDARD_LINK_TYPES.items():
            if source_type_lower == standard_type or source_type_lower in alternatives:
                if standard_type in dest_types_lower:
                    mapping[source_type] = standard_type
                    mapped = True
                    break
                else:
                    # Try alternatives of the standard type
                    for alt in alternatives:
                        if alt in dest_types_lower:
                            mapping[source_type] = alt
                            mapped = True
                            break
                    if mapped:
                        break
        
        # If no mapping found, use a default "relates to" type if available
        if not mapped:
            if "relates to" in dest_types_lower:
                mapping[source_type] = "relates to"
                logger.warning(f"No direct mapping for link type '{source_type}', using 'relates to'")
            else:
                # Find any available link type as last resort
                if dest_types_lower:
                    fallback = next(iter(dest_types_lower.keys()))
                    mapping[source_type] = fallback
                    logger.warning(f"No direct mapping for link type '{source_type}', using '{fallback}'")
                else:
                    logger.error(f"No link types available in destination, cannot map '{source_type}'")
    
    return mapping

def get_link_type_id(link_type: str, available_types: Dict[str, str]) -> Optional[str]:
    """
    Get the ID for a link type name.
    
    Args:
        link_type: Link type name
        available_types: Dictionary of available link type names to IDs
        
    Returns:
        Link type ID or None if not found
    """
    link_type_lower = link_type.lower()
    
    # Direct match
    if link_type_lower in available_types:
        return available_types[link_type_lower]
    
    # Try standard alternatives
    for standard_type, alternatives in STANDARD_LINK_TYPES.items():
        if link_type_lower == standard_type or link_type_lower in alternatives:
            if standard_type in available_types:
                return available_types[standard_type]
            for alt in alternatives:
                if alt in available_types:
                    return available_types[alt]
    
    # No match found
    return None

def create_fallback_link(api, source_issue: str, target_issue: str, 
                       available_types: Dict[str, str]) -> bool:
    """
    Create a fallback link when the original link type is not available.
    
    Args:
        api: JiraAPI instance
        source_issue: Source issue key
        target_issue: Target issue key
        available_types: Dictionary of available link type names to IDs
        
    Returns:
        True if link was created, False otherwise
    """
    # Try to use "relates to" as fallback
    if "relates to" in available_types:
        try:
            api.create_issue_link(source_issue, target_issue, "relates to")
            logger.info(f"Created fallback 'relates to' link: {source_issue} -> {target_issue}")
            return True
        except Exception as e:
            logger.error(f"Failed to create fallback 'relates to' link: {e}")
    
    # Try any available link type
    if available_types:
        fallback_type = next(iter(available_types.keys()))
        try:
            api.create_issue_link(source_issue, target_issue, fallback_type)
            logger.info(f"Created fallback '{fallback_type}' link: {source_issue} -> {target_issue}")
            return True
        except Exception as e:
            logger.error(f"Failed to create fallback '{fallback_type}' link: {e}")
    
    return False
