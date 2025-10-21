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


def should_skip_comment(event_data: dict, customer_bot_username: str = None) -> tuple[bool, str]:
    """
    Check if comment should be skipped.

    Comments are only sent to customer if they mention the customer bot.
    This is an opt-in approach - safer than opt-out.

    Args:
        event_data: GitHub webhook event data
        customer_bot_username: Username of bot that represents the customer (without @)

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

    # Check if comment mentions customer bot (opt-in to send to customer)
    if customer_bot_username:
        if not mentions_customer_bot(comment_body, customer_bot_username):
            return True, f"Comment does not mention @{customer_bot_username} (internal comment)"

    return False, ""


def mentions_customer_bot(comment_body: str, customer_bot_username: str) -> bool:
    """
    Check if comment mentions the customer bot (indicating it should be sent to customer).

    Args:
        comment_body: Comment text
        customer_bot_username: Bot username to check for (without @)

    Returns:
        True if comment mentions the customer bot
    """
    if not comment_body or not customer_bot_username:
        return False

    # Check for @username mention (case insensitive)
    mention = f"@{customer_bot_username}"

    return mention.lower() in comment_body.lower()


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
    comment_author = comment['user']['login']

    logger.info(f"[SEND] Processing comment on issue #{issue_number} by @{comment_author}")

    # Parse metadata from issue body
    metadata = parse_metadata_from_issue_body(issue['body'])

    if not metadata:
        logger.error(f"❌ Could not parse metadata from issue #{issue_number} - missing helpdesk metadata")
        return False

    customer_email = metadata.get('from')
    if not customer_email:
        logger.error(f"❌ No customer email found in issue #{issue_number} metadata")
        return False

    logger.info(f"📧 Sending email to customer: {customer_email}")

    message_ids = metadata.get('message_ids', [])
    if not message_ids:
        logger.warning(f"⚠️  No message IDs found in issue #{issue_number} metadata - threading may not work")

    # Generate new message ID
    new_message_id = generate_message_id()

    # Prepare email
    subject = f"Re: {issue['title']}"
    in_reply_to = message_ids[-1] if message_ids else ""
    references = message_ids

    logger.info(f"Email subject: {subject}")
    logger.info(f"Threading: In-Reply-To={in_reply_to[:30]}..." if in_reply_to else "Threading: First message in thread")

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
        logger.info(f"✅ Email sent successfully to {customer_email}")

        # Update issue metadata with new message ID
        update_issue_metadata(issue, new_message_id, metadata, github)

        return True
    else:
        logger.error(f"❌ Failed to send email to {customer_email}")
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


def get_authenticated_user(github_token: str) -> str:
    """
    Get the username of the authenticated GitHub user.

    Args:
        github_token: GitHub token

    Returns:
        Username of the authenticated user
    """
    import requests

    try:
        response = requests.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"token {github_token}",
                "Accept": "application/vnd.github.v3+json"
            }
        )
        response.raise_for_status()
        return response.json().get('login', '')
    except Exception as e:
        logger.warning(f"Could not get authenticated user: {e}")
        return ''


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

    # Get the username of the authenticated user (customer bot)
    customer_bot_username = get_authenticated_user(github_token)
    if customer_bot_username:
        logger.info(f"📋 Customer bot: @{customer_bot_username} - comments must mention this user to be sent to customer")
    else:
        logger.warning("⚠️  Could not determine customer bot username - all comments will be sent to customer")

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
    should_skip, reason = should_skip_comment(event_data, customer_bot_username)

    if should_skip:
        logger.info(f"⏭️  Skipping comment: {reason}")
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
            logger.info("=" * 60)
            logger.info("✅ Comment processed successfully - email sent to customer")
            logger.info("=" * 60)
            sys.exit(0)
        else:
            logger.error("=" * 60)
            logger.error("❌ Failed to process comment - email not sent")
            logger.error("=" * 60)
            sys.exit(1)

    except Exception as e:
        logger.error(f"❌ Unexpected error processing comment: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
