"""
Content handling utilities for the Jira Fork Tool.

This module provides functions for handling content size limits
and formatting content for Jira Cloud API compatibility.
"""

import logging
import re
from typing import Dict, Any, Optional, List, Union

logger = logging.getLogger(__name__)

# Jira Cloud API limits
MAX_DESCRIPTION_LENGTH = 32767  # Characters
MAX_COMMENT_LENGTH = 32767  # Characters
MAX_SUMMARY_LENGTH = 255  # Characters

def truncate_summary(summary: str) -> str:
    """
    Truncate summary to fit within Jira Cloud limits.
    
    Args:
        summary: The issue summary text
        
    Returns:
        Truncated summary text
    """
    if not summary:
        return "No summary provided"
        
    if len(summary) <= MAX_SUMMARY_LENGTH:
        return summary
    
    # Truncate and add indicator
    truncated = summary[:MAX_SUMMARY_LENGTH - 3] + "..."
    logger.warning(f"Summary truncated from {len(summary)} to {len(truncated)} characters")
    return truncated

def format_description_for_cloud(description: Optional[str]) -> Dict[str, Any]:
    """
    Format description text for Jira Cloud API (Atlassian Document Format).
    Handles content size limits by truncating if necessary.
    
    Args:
        description: The original description text
        
    Returns:
        Description in Atlassian Document Format
    """
    if not description:
        return create_adf_document("No description provided.")
    
    # Check if already in ADF format (JSON object)
    if isinstance(description, dict) and 'type' in description and description['type'] == 'doc':
        return description
    
    # Convert to string if not already
    description_str = str(description)
    
    # Check length and truncate if needed
    if len(description_str) > MAX_DESCRIPTION_LENGTH:
        logger.warning(f"Description exceeds size limit ({len(description_str)} chars). Truncating.")
        truncated_text = description_str[:MAX_DESCRIPTION_LENGTH - 100]
        truncated_text += "\n\n[Content truncated due to size limits]"
        return create_adf_document(truncated_text)
    
    return create_adf_document(description_str)

def format_comment_for_cloud(comment: str) -> Dict[str, Any]:
    """
    Format comment text for Jira Cloud API (Atlassian Document Format).
    Handles content size limits by truncating if necessary.
    
    Args:
        comment: The original comment text
        
    Returns:
        Comment in Atlassian Document Format
    """
    if not comment:
        return create_adf_document("No comment text")
    
    # Convert to string if not already
    comment_str = str(comment)
    
    # Check length and truncate if needed
    if len(comment_str) > MAX_COMMENT_LENGTH:
        logger.warning(f"Comment exceeds size limit ({len(comment_str)} chars). Truncating.")
        truncated_text = comment_str[:MAX_COMMENT_LENGTH - 100]
        truncated_text += "\n\n[Content truncated due to size limits]"
        return create_adf_document(truncated_text)
    
    return create_adf_document(comment_str)

def create_adf_document(text: str) -> Dict[str, Any]:
    """
    Create an Atlassian Document Format (ADF) document from plain text.
    
    Args:
        text: Plain text content
        
    Returns:
        ADF document structure
    """
    # Split text into paragraphs
    paragraphs = text.split('\n\n')
    if not paragraphs:
        paragraphs = [""]
    
    # Create content array with paragraphs
    content = []
    for para in paragraphs:
        if not para.strip():
            continue
            
        # Handle line breaks within paragraphs
        lines = para.split('\n')
        if len(lines) > 1:
            para_content = []
            for i, line in enumerate(lines):
                para_content.append({"type": "text", "text": line})
                # Add line break between lines, but not after the last line
                if i < len(lines) - 1:
                    para_content.append({"type": "hardBreak"})
            content.append({
                "type": "paragraph",
                "content": para_content
            })
        else:
            content.append({
                "type": "paragraph",
                "content": [{"type": "text", "text": para}]
            })
    
    # Create ADF document
    return {
        "version": 1,
        "type": "doc",
        "content": content
    }

def merge_descriptions(original_key: str, description: Optional[str]) -> Dict[str, Any]:
    """
    Merge original issue key reference with description content.
    
    Args:
        original_key: Original issue key
        description: Description content
        
    Returns:
        Merged description in ADF format
    """
    # Create header paragraph with original issue reference
    header = {
        "type": "paragraph",
        "content": [
            {"type": "text", "text": f"Original issue: {original_key}", "marks": [{"type": "strong"}]}
        ]
    }
    
    # Format description
    formatted_desc = format_description_for_cloud(description)
    
    # Merge content
    merged_content = [header] + formatted_desc["content"]
    
    # Create merged document
    return {
        "version": 1,
        "type": "doc",
        "content": merged_content
    }

def sanitize_issue_data(issue_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize issue data to ensure it meets Jira Cloud API requirements.
    
    Args:
        issue_data: Original issue data
        
    Returns:
        Sanitized issue data
    """
    # Create a copy to avoid modifying the original
    sanitized = issue_data.copy()
    
    # Ensure fields exist
    if 'fields' not in sanitized:
        sanitized['fields'] = {}
    
    # Sanitize summary
    if 'summary' in sanitized['fields']:
        sanitized['fields']['summary'] = truncate_summary(sanitized['fields']['summary'])
    
    # Sanitize description
    if 'description' in sanitized['fields']:
        if not isinstance(sanitized['fields']['description'], dict):
            sanitized['fields']['description'] = format_description_for_cloud(
                sanitized['fields']['description']
            )
    
    return sanitized
