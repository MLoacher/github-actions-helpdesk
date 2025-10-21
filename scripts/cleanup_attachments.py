#!/usr/bin/env python3
"""
Cleanup old attachments from closed GitHub issues.

This script:
1. Finds all closed issues in the repository
2. Checks if they've been closed longer than DAYS_OLD
3. Deletes their attachment folders from the repository
4. Optionally runs in dry-run mode to preview deletions
"""

import os
import sys
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional
import shutil

from github_helper import GitHubHelper

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:%(name)s:%(message)s'
)
logger = logging.getLogger(__name__)


def parse_iso_date(date_str: str) -> datetime:
    """Parse ISO 8601 date string to datetime."""
    # GitHub returns dates like: "2024-10-15T12:30:45Z"
    return datetime.fromisoformat(date_str.replace('Z', '+00:00'))


def get_closed_issues_older_than(github: GitHubHelper, days: int) -> List[dict]:
    """
    Get all closed issues that were closed more than 'days' ago.

    Args:
        github: GitHubHelper instance
        days: Minimum number of days since closure

    Returns:
        List of issue dicts with issue numbers and closed dates
    """
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    logger.info(f"Finding issues closed before {cutoff_date.isoformat()}")

    # Search for closed helpdesk issues
    query = "label:helpdesk is:closed"
    issues = github.search_issues(query)

    old_issues = []
    for issue in issues:
        closed_at_str = issue.get('closed_at')
        if not closed_at_str:
            continue

        closed_at = parse_iso_date(closed_at_str)

        if closed_at < cutoff_date:
            days_closed = (datetime.now(timezone.utc) - closed_at).days
            old_issues.append({
                'number': issue['number'],
                'closed_at': closed_at,
                'days_closed': days_closed,
                'title': issue.get('title', '')
            })

    logger.info(f"Found {len(old_issues)} issues closed more than {days} days ago")
    return old_issues


def get_attachment_folders() -> List[Path]:
    """
    Get all attachment folders in the current repository.

    Returns:
        List of Path objects for attachment folders
    """
    attachments_dir = Path('attachments')

    if not attachments_dir.exists():
        logger.warning("No 'attachments' folder found in repository")
        return []

    # Find all issue-* folders
    issue_folders = []
    for item in attachments_dir.iterdir():
        if item.is_dir() and item.name.startswith('issue-'):
            issue_folders.append(item)

    logger.info(f"Found {len(issue_folders)} attachment folders")
    return issue_folders


def extract_issue_number_from_folder(folder: Path) -> Optional[int]:
    """
    Extract issue number from folder name like 'issue-123'.

    Args:
        folder: Path to folder

    Returns:
        Issue number or None if parsing fails
    """
    try:
        # folder.name is like "issue-123"
        parts = folder.name.split('-')
        if len(parts) == 2 and parts[0] == 'issue':
            return int(parts[1])
    except ValueError:
        pass

    return None


def get_folder_size(folder: Path) -> int:
    """
    Calculate total size of all files in a folder.

    Args:
        folder: Path to folder

    Returns:
        Total size in bytes
    """
    total_size = 0
    for item in folder.rglob('*'):
        if item.is_file():
            total_size += item.stat().st_size
    return total_size


def format_size(size_bytes: int) -> str:
    """Format bytes as human-readable string."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def cleanup_attachments(dry_run: bool = False):
    """
    Main cleanup function.

    Args:
        dry_run: If True, only preview deletions without actually deleting
    """
    # Get configuration from environment
    github_token = os.getenv('GITHUB_TOKEN')
    repository = os.getenv('GITHUB_REPOSITORY')
    days_old = int(os.getenv('DAYS_OLD', '180'))
    dry_run_env = os.getenv('DRY_RUN', 'false').lower() == 'true'

    if dry_run_env:
        dry_run = True

    if not github_token or not repository:
        logger.error("Missing required environment variables: GITHUB_TOKEN, GITHUB_REPOSITORY")
        sys.exit(1)

    mode = "DRY RUN" if dry_run else "LIVE"
    logger.info(f"={'='*60}")
    logger.info(f"🧹 Attachment Cleanup - {mode} MODE")
    logger.info(f"Repository: {repository}")
    logger.info(f"Deleting attachments from issues closed more than {days_old} days ago")
    logger.info(f"{'='*60}")

    # Initialize GitHub helper
    github = GitHubHelper(github_token, repository)

    # Get issues that are old enough to clean up
    old_issues = get_closed_issues_older_than(github, days_old)

    if not old_issues:
        logger.info("✅ No issues found that need cleanup")
        return

    # Create set of issue numbers for quick lookup
    issue_numbers_to_clean = {issue['number'] for issue in old_issues}

    # Get all attachment folders
    attachment_folders = get_attachment_folders()

    if not attachment_folders:
        logger.info("✅ No attachment folders found")
        return

    # Find folders to delete
    folders_to_delete = []
    total_size = 0

    for folder in attachment_folders:
        issue_number = extract_issue_number_from_folder(folder)

        if issue_number and issue_number in issue_numbers_to_clean:
            size = get_folder_size(folder)
            total_size += size

            # Find the issue details
            issue_info = next((i for i in old_issues if i['number'] == issue_number), None)

            folders_to_delete.append({
                'path': folder,
                'issue_number': issue_number,
                'size': size,
                'days_closed': issue_info['days_closed'] if issue_info else 'unknown',
                'title': issue_info['title'] if issue_info else ''
            })

    if not folders_to_delete:
        logger.info("✅ No attachment folders match the cleanup criteria")
        return

    # Display what will be deleted
    logger.info(f"\n{'='*60}")
    logger.info(f"📋 Found {len(folders_to_delete)} folder(s) to delete:")
    logger.info(f"{'='*60}")

    for folder_info in sorted(folders_to_delete, key=lambda x: x['issue_number']):
        logger.info(
            f"  #{folder_info['issue_number']} - {folder_info['title'][:50]}"
            f"\n    Closed: {folder_info['days_closed']} days ago"
            f"\n    Size: {format_size(folder_info['size'])}"
            f"\n    Path: {folder_info['path']}"
        )

    logger.info(f"\n{'='*60}")
    logger.info(f"💾 Total space to reclaim: {format_size(total_size)}")
    logger.info(f"{'='*60}\n")

    if dry_run:
        logger.info("🔍 DRY RUN - No files were deleted")
        logger.info("To actually delete these files, set DRY_RUN=false")
        return

    # Actually delete the folders
    logger.info("🗑️  Deleting folders...")
    deleted_count = 0

    for folder_info in folders_to_delete:
        try:
            shutil.rmtree(folder_info['path'])
            logger.info(f"  ✅ Deleted: {folder_info['path']}")
            deleted_count += 1
        except Exception as e:
            logger.error(f"  ❌ Failed to delete {folder_info['path']}: {e}")

    logger.info(f"\n{'='*60}")
    logger.info(f"✅ Cleanup complete!")
    logger.info(f"   Deleted: {deleted_count}/{len(folders_to_delete)} folders")
    logger.info(f"   Space reclaimed: {format_size(total_size)}")
    logger.info(f"{'='*60}")


if __name__ == "__main__":
    cleanup_attachments()
