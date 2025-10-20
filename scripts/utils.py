"""Shared utilities for parsing and formatting helpdesk data."""

import re
from typing import Optional, Dict, List


def parse_metadata_from_issue_body(body: str) -> Optional[Dict[str, any]]:
    """
    Extract helpdesk metadata from issue body HTML comment.

    Args:
        body: Issue body text containing hidden metadata

    Returns:
        Dictionary with keys: thread_id, from, message_ids
        None if no metadata found
    """
    pattern = r'<!-- HELPDESK_METADATA\s+(.*?)\s+-->'
    match = re.search(pattern, body, re.DOTALL)

    if not match:
        return None

    metadata_text = match.group(1)
    metadata = {}

    # Parse thread_id
    thread_id_match = re.search(r'thread_id:\s*(.+)', metadata_text)
    if thread_id_match:
        metadata['thread_id'] = thread_id_match.group(1).strip()

    # Parse from
    from_match = re.search(r'from:\s*(.+)', metadata_text)
    if from_match:
        metadata['from'] = from_match.group(1).strip()

    # Parse message_ids (JSON array format)
    message_ids_match = re.search(r'message_ids:\s*(\[.*?\])', metadata_text, re.DOTALL)
    if message_ids_match:
        import json
        try:
            metadata['message_ids'] = json.loads(message_ids_match.group(1))
        except json.JSONDecodeError:
            metadata['message_ids'] = []
    else:
        metadata['message_ids'] = []

    return metadata


def format_metadata_comment(thread_id: str, from_email: str, message_ids: List[str]) -> str:
    """
    Format metadata as HTML comment for embedding in issue body.

    Args:
        thread_id: Email thread identifier
        from_email: Customer email address
        message_ids: List of Message-ID headers from email thread

    Returns:
        HTML comment string with metadata
    """
    import json
    message_ids_json = json.dumps(message_ids)

    return f"""<!-- HELPDESK_METADATA
thread_id: {thread_id}
from: {from_email}
message_ids: {message_ids_json}
-->"""


def extract_gh_number_from_subject(subject: str) -> Optional[int]:
    """
    Extract GitHub issue number from subject line.

    Args:
        subject: Email subject line (e.g., "Re: [GH-0042] Login issue")

    Returns:
        Issue number as integer, or None if not found
    """
    match = re.search(r'\[GH-(\d+)\]', subject)
    if match:
        return int(match.group(1))
    return None


def format_issue_title(issue_number: int, subject: str) -> str:
    """
    Format issue title with GH number prefix.

    Args:
        issue_number: GitHub issue number
        subject: Email subject line

    Returns:
        Formatted title like "[GH-0042] Subject"
    """
    # Remove any existing [GH-####] prefix
    clean_subject = re.sub(r'\[GH-\d+\]\s*', '', subject)
    # Remove Re:, Fwd:, etc.
    clean_subject = re.sub(r'^(Re:|RE:|Fwd:|FW:)\s*', '', clean_subject, flags=re.IGNORECASE)

    return f"[GH-{issue_number:04d}] {clean_subject.strip()}"


def sanitize_email_body(body: str) -> str:
    """
    Sanitize email body for safe display in GitHub issue.

    Args:
        body: Raw email body text

    Returns:
        Sanitized text safe for GitHub Markdown
    """
    # Basic sanitization - escape HTML tags if present
    body = body.replace('<', '&lt;').replace('>', '&gt;')

    # Limit length to prevent extremely long issues
    max_length = 50000
    if len(body) > max_length:
        body = body[:max_length] + '\n\n[Content truncated...]'

    return body


def generate_message_id(domain: str = "github-helpdesk") -> str:
    """
    Generate a unique Message-ID for email headers.

    Args:
        domain: Domain to use in Message-ID

    Returns:
        Message-ID string like "<unique-id@domain>"
    """
    import time
    import random
    import hashlib

    # Create unique identifier using timestamp + random data
    unique_str = f"{time.time()}-{random.randint(0, 999999)}"
    hash_id = hashlib.sha256(unique_str.encode()).hexdigest()[:16]

    return f"<{hash_id}@{domain}>"


def parse_email_address(addr_string: str) -> str:
    """
    Extract email address from string like "John Doe <john@example.com>".

    Args:
        addr_string: Email address string with optional display name

    Returns:
        Clean email address
    """
    # Match email in angle brackets or standalone
    match = re.search(r'<([^>]+)>|([^\s<>]+@[^\s<>]+)', addr_string)
    if match:
        return match.group(1) or match.group(2)
    return addr_string.strip()


def create_email_marker() -> str:
    """
    Create marker to identify comments that originated from email.

    Returns:
        HTML comment string
    """
    return "<!-- source:email -->"


def has_email_marker(text: str) -> bool:
    """
    Check if text contains email source marker.

    Args:
        text: Text to check

    Returns:
        True if marker is present
    """
    return "<!-- source:email -->" in text
