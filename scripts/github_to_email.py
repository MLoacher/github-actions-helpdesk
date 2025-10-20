#!/usr/bin/env python3
"""
GitHub to Email workflow script.

Sends issue comments back to customers via email.
Runs on issue_comment events via GitHub Actions.
"""

import os
import sys
import json
import logging

from email_helper import send_email
from github_helper import GitHubHelper
from utils import (
    parse_metadata_from_issue_body, has_email_marker,
    generate_message_id, format_issue_title
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def get_env_or_exit(var_name: str) -> str:
    """Get environment variable or exit if not set."""
    value = os.getenv(var_name)
    if not value:
        logger.error(f"Environment variable {var_name} is not set")
        sys.exit(1)
    return value


def should_skip_comment(event_data: dict) -> tuple[bool, str]:
    """
    Check if comment should be skipped.

    Args:
        event_data: GitHub webhook event data

    Returns:
        Tuple of (should_skip, reason)
    """
    # Check if issue has helpdesk label
    issue = event_data.get('issue', {})
    labels = [label['name'] for label in issue.get('labels', [])]

    if 'helpdesk' not in labels:
        return True, "Issue does not have 'helpdesk' label"

    # Check if comment author is a bot
    comment = event_data.get('comment', {})
    user = comment.get('user', {})

    if user.get('type') == 'Bot':
        return True, "Comment author is a bot"

    # Check if comment has email marker (originated from email)
    comment_body = comment.get('body', '')

    if has_email_marker(comment_body):
        return True, "Comment originated from email (has marker)"

    return False, ""


def process_comment(event_data: dict, github: GitHubHelper, smtp_config: dict) -> bool:
    """
    Process a comment and send it via email.

    Args:
        event_data: GitHub webhook event data
        github: GitHubHelper instance
        smtp_config: SMTP configuration dict

    Returns:
        True if successful
    """
    issue = event_data['issue']
    comment = event_data['comment']

    issue_number = issue['number']
    comment_body = comment['body']

    logger.info(f"Processing comment on issue #{issue_number}")

    # Parse metadata from issue body
    metadata = parse_metadata_from_issue_body(issue['body'])

    if not metadata:
        logger.error(f"Could not parse metadata from issue #{issue_number}")
        return False

    customer_email = metadata.get('from')
    if not customer_email:
        logger.error(f"No customer email found in issue #{issue_number} metadata")
        return False

    message_ids = metadata.get('message_ids', [])
    if not message_ids:
        logger.warning(f"No message IDs found in issue #{issue_number} metadata")

    # Generate new message ID
    new_message_id = generate_message_id()

    # Prepare email
    subject = f"Re: {issue['title']}"
    in_reply_to = message_ids[-1] if message_ids else ""
    references = message_ids

    # Send email
    success = send_email(
        smtp_host=smtp_config['host'],
        smtp_port=smtp_config['port'],
        smtp_user=smtp_config['user'],
        smtp_password=smtp_config['password'],
        from_addr=smtp_config['user'],
        to_addr=customer_email,
        subject=subject,
        body=comment_body,
        in_reply_to=in_reply_to,
        references=references,
        message_id=new_message_id
    )

    if success:
        logger.info(f"Email sent to {customer_email}")

        # Update issue metadata with new message ID
        update_issue_metadata(issue, new_message_id, metadata, github)

        return True
    else:
        logger.error(f"Failed to send email to {customer_email}")
        return False


def update_issue_metadata(issue: dict, new_message_id: str, metadata: dict, github: GitHubHelper):
    """
    Update issue metadata with new message ID.

    Args:
        issue: Issue dict
        new_message_id: Message ID to add
        metadata: Parsed metadata dict
        github: GitHubHelper instance
    """
    try:
        from utils import format_metadata_comment

        # Add new message ID
        old_message_ids = metadata['message_ids'].copy()
        metadata['message_ids'].append(new_message_id)

        # Create old and new metadata comments
        old_metadata_comment = format_metadata_comment(
            metadata['thread_id'],
            metadata['from'],
            old_message_ids
        )
        new_metadata_comment = format_metadata_comment(
            metadata['thread_id'],
            metadata['from'],
            metadata['message_ids']
        )

        # Replace in issue body
        new_body = issue['body'].replace(old_metadata_comment, new_metadata_comment)

        # Update issue
        github.update_issue(issue['number'], body=new_body)
        logger.info(f"Updated metadata for issue #{issue['number']}")

    except Exception as e:
        logger.error(f"Error updating issue metadata: {e}")


def main():
    """Main workflow function."""
    logger.info("Starting github-to-email workflow")

    # Get environment variables
    smtp_host = get_env_or_exit('SMTP_HOST')
    smtp_port = int(get_env_or_exit('SMTP_PORT'))
    smtp_user = get_env_or_exit('SMTP_USER')
    smtp_password = get_env_or_exit('SMTP_PASSWORD')
    github_token = get_env_or_exit('GITHUB_TOKEN')
    github_repository = get_env_or_exit('GITHUB_REPOSITORY')
    event_path = os.getenv('GITHUB_EVENT_PATH')

    if not event_path:
        logger.error("GITHUB_EVENT_PATH not set (not running in GitHub Actions?)")
        sys.exit(1)

    # Load event data
    try:
        with open(event_path, 'r') as f:
            event_data = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load event data: {e}")
        sys.exit(1)

    # Check if we should skip this comment
    should_skip, reason = should_skip_comment(event_data)

    if should_skip:
        logger.info(f"Skipping comment: {reason}")
        sys.exit(0)

    # Initialize GitHub helper
    github = GitHubHelper(github_token, github_repository)

    # SMTP configuration
    smtp_config = {
        'host': smtp_host,
        'port': smtp_port,
        'user': smtp_user,
        'password': smtp_password
    }

    # Process comment
    try:
        success = process_comment(event_data, github, smtp_config)

        if success:
            logger.info("Comment processed successfully")
            sys.exit(0)
        else:
            logger.error("Failed to process comment")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Error processing comment: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
