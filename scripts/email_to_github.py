#!/usr/bin/env python3
"""
Email to GitHub workflow script.

Fetches emails from IMAP and creates/updates GitHub issues.
Runs on a schedule via GitHub Actions.
"""

import os
import sys
import logging
from typing import Optional

from email_helper import (
    connect_imap, fetch_unseen_emails, mark_email_as_seen, close_imap
)
from github_helper import GitHubHelper
from utils import (
    extract_gh_number_from_subject, format_issue_title, sanitize_email_body,
    format_metadata_comment, parse_email_address, create_email_marker,
    parse_metadata_from_issue_body
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


def process_email(email_msg, github: GitHubHelper, project_id: str = None) -> bool:
    """
    Process a single email message and create/update GitHub issue.

    Args:
        email_msg: EmailMessage object
        github: GitHubHelper instance
        project_id: Optional GitHub Project ID to add new issues to

    Returns:
        True if successful
    """
    logger.info(f"Processing email from {email_msg.from_addr}: '{email_msg.subject}'")

    # Extract sender email
    from_email = parse_email_address(email_msg.from_addr)
    logger.info(f"Sender email: {from_email}")

    # Get ticket prefix from environment
    ticket_prefix = os.getenv('TICKET_PREFIX', 'GH')

    # Check if this is a reply to an existing ticket
    gh_number = extract_gh_number_from_subject(email_msg.subject)

    if gh_number:
        # Reply to existing issue
        logger.info(f"[REPLY] Found {ticket_prefix}-{gh_number} in subject, adding comment to existing issue")
        return handle_reply(email_msg, gh_number, from_email, github)
    else:
        # Try to find existing issue by email metadata
        logger.info(f"[NEW/REPLY] No {ticket_prefix} number in subject, searching by thread metadata...")
        existing_issue = find_issue_by_thread(email_msg, github)

        if existing_issue:
            logger.info(f"[REPLY] Found existing issue #{existing_issue['number']} by thread ID, adding comment")
            return handle_reply(email_msg, existing_issue['number'], from_email, github)
        else:
            # Create new issue
            logger.info(f"[NEW] No existing issue found, creating new ticket for {from_email}")
            return create_new_issue(email_msg, from_email, github, project_id)


def process_attachments(attachments, github: GitHubHelper, issue_number: int = None) -> str:
    """
    Process email attachments: upload images and list non-images.

    Args:
        attachments: List of Attachment objects
        github: GitHubHelper instance
        issue_number: Issue number (for logging)

    Returns:
        Markdown string with embedded images and attachment list
    """
    if not attachments:
        return ""

    # Separate images from other files
    image_types = ['image/png', 'image/jpeg', 'image/jpg', 'image/gif', 'image/bmp', 'image/webp']
    images = [att for att in attachments if att.content_type in image_types]
    other_files = [att for att in attachments if att.content_type not in image_types]

    sections = []

    # Upload and embed images
    if images:
        sections.append("### 📷 Attached Images\n")
        for img in images:
            file_url = github.upload_attachment_to_repo(img.data, img.filename, issue_number)
            if file_url:
                sections.append(f"![{img.filename}]({file_url})\n")
                logger.info(f"✅ Embedded image: {img.filename}")
            else:
                # Fallback: add to other_files list if upload failed
                logger.warning(f"Failed to upload image: {img.filename}, adding to file list")
                other_files.append(img)

    # Upload and link non-image attachments
    if other_files:
        sections.append("### 📎 Other Attachments\n")
        for file in other_files:
            size_kb = file.size / 1024
            file_url = github.upload_attachment_to_repo(file.data, file.filename, issue_number)
            if file_url:
                sections.append(f"- [{file.filename}]({file_url}) ({size_kb:.1f} KB)\n")
                logger.info(f"✅ Uploaded attachment: {file.filename}")
            else:
                sections.append(f"- `{file.filename}` ({size_kb:.1f} KB) - ⚠️ Upload failed, check original email\n")
                logger.warning(f"Failed to upload attachment: {file.filename}")

    return "\n".join(sections)


def create_new_issue(email_msg, from_email: str, github: GitHubHelper, project_id: str = None) -> bool:
    """
    Create a new GitHub issue from email.

    Args:
        email_msg: EmailMessage object
        from_email: Sender email address
        github: GitHubHelper instance
        project_id: Optional GitHub Project ID to add issue to

    Returns:
        True if successful
    """
    # Get ticket prefix from environment
    ticket_prefix = os.getenv('TICKET_PREFIX', 'GH')

    # Get next issue number (prediction)
    issue_number = github.get_next_issue_number()

    # Format title with ticket number
    title = format_issue_title(issue_number, email_msg.subject)

    # Sanitize body
    body_text = email_msg.body if email_msg.body else email_msg.html_body
    clean_body = sanitize_email_body(body_text)

    # Process attachments
    attachments_section = process_attachments(email_msg.attachments, github, issue_number)

    # Create metadata comment
    metadata = format_metadata_comment(
        thread_id=email_msg.message_id,
        from_email=from_email,
        message_ids=[email_msg.message_id]
    )

    # Combine body with attachments and metadata
    full_body = f"{clean_body}\n\n{attachments_section}\n\n{metadata}" if attachments_section else f"{clean_body}\n\n{metadata}"

    # Create labels
    labels = ["helpdesk", f"from:{from_email}"]

    # Create issue
    issue = github.create_issue(title, full_body, labels)

    if issue:
        actual_number = issue['number']
        issue_node_id = issue.get('node_id')
        logger.info(f"✅ Successfully created issue #{actual_number}: {title}")

        # If predicted number was wrong, update the title
        if actual_number != issue_number:
            correct_title = format_issue_title(actual_number, email_msg.subject)
            github.update_issue(actual_number, title=correct_title)
            logger.info(f"Updated title to use correct issue number: [{ticket_prefix}-{actual_number:04d}]")

        # Add to project if project_id is provided
        if project_id and issue_node_id:
            logger.info(f"📋 Adding issue #{actual_number} to GitHub Project")
            if not github.add_issue_to_project(issue_node_id, project_id):
                logger.error(f"❌ Failed to add issue #{actual_number} to project {project_id}")
                return False

        return True
    else:
        logger.error(f"❌ Failed to create issue for email from {from_email}")
        return False


def handle_reply(email_msg, issue_number: int, from_email: str, github: GitHubHelper) -> bool:
    """
    Add email as comment to existing issue.

    Args:
        email_msg: EmailMessage object
        issue_number: GitHub issue number
        from_email: Sender email address
        github: GitHubHelper instance

    Returns:
        True if successful
    """
    # Get issue to check if it's closed
    issue = github.get_issue(issue_number)

    if not issue:
        logger.error(f"Issue #{issue_number} not found")
        return False

    # Reopen if closed
    if issue['state'] == 'closed':
        logger.info(f"🔓 Reopening closed issue #{issue_number} due to customer reply")
        github.reopen_issue(issue_number)

    # Sanitize body
    body_text = email_msg.body if email_msg.body else email_msg.html_body
    clean_body = sanitize_email_body(body_text)

    # Process attachments
    attachments_section = process_attachments(email_msg.attachments, github, issue_number)

    # Add email marker
    email_marker = create_email_marker()
    comment_body = f"{clean_body}\n\n{attachments_section}\n\n{email_marker}" if attachments_section else f"{clean_body}\n\n{email_marker}"

    # Add comment
    comment = github.add_comment(issue_number, comment_body)

    if comment:
        logger.info(f"✅ Successfully added comment to issue #{issue_number} from {from_email}")

        # Update issue metadata with new message ID
        update_issue_metadata(issue, email_msg.message_id, github)

        return True
    else:
        logger.error(f"❌ Failed to add comment to issue #{issue_number} for {from_email}")
        return False


def find_issue_by_thread(email_msg, github: GitHubHelper) -> Optional[dict]:
    """
    Find existing issue by checking thread metadata.

    Searches ALL open helpdesk issues and matches by email Message-ID threading headers.
    This is more reliable than matching by customer email label alone.

    Args:
        email_msg: EmailMessage object
        github: GitHubHelper instance

    Returns:
        Issue dict or None
    """
    # Search for ALL open helpdesk issues
    query = "label:helpdesk is:open"
    issues = github.search_issues(query)

    if not issues:
        logger.debug("No open helpdesk issues found")
        return None

    logger.info(f"Searching {len(issues)} open helpdesk issue(s) for matching email thread...")

    # Check each issue to find the one with matching message IDs
    for issue in issues:
        # Parse metadata from this issue
        metadata = parse_metadata_from_issue_body(issue['body'])

        if not metadata:
            continue

        stored_message_ids = metadata.get('message_ids', [])

        # Check if email references any message IDs in this issue's metadata
        if email_msg.in_reply_to and email_msg.in_reply_to in stored_message_ids:
            logger.info(f"✓ Matched issue #{issue['number']} by In-Reply-To: {email_msg.in_reply_to}")
            return issue

        for ref in email_msg.references:
            if ref in stored_message_ids:
                logger.info(f"✓ Matched issue #{issue['number']} by References: {ref}")
                return issue

    # No threading match found
    logger.debug(f"Email threading headers don't match any open issues")
    logger.debug(f"Email In-Reply-To: {email_msg.in_reply_to}")
    logger.debug(f"Email References: {email_msg.references}")
    return None


def update_issue_metadata(issue: dict, new_message_id: str, github: GitHubHelper):
    """
    Update issue metadata with new message ID.

    Args:
        issue: Issue dict
        new_message_id: Message ID to add
        github: GitHubHelper instance
    """
    try:
        metadata = parse_metadata_from_issue_body(issue['body'])

        if not metadata:
            logger.warning("Could not parse metadata from issue")
            return

        # Add new message ID
        if new_message_id not in metadata['message_ids']:
            metadata['message_ids'].append(new_message_id)

            # Replace old metadata comment with updated one
            old_metadata_comment = format_metadata_comment(
                metadata['thread_id'],
                metadata['from'],
                metadata['message_ids'][:-1]  # Old list
            )
            new_metadata_comment = format_metadata_comment(
                metadata['thread_id'],
                metadata['from'],
                metadata['message_ids']  # Updated list
            )

            new_body = issue['body'].replace(old_metadata_comment, new_metadata_comment)
            github.update_issue(issue['number'], body=new_body)
            logger.info(f"Updated metadata for issue #{issue['number']}")

    except Exception as e:
        logger.error(f"Error updating issue metadata: {e}")


def main():
    """Main workflow function."""
    logger.info("Starting email-to-github workflow")

    # Get environment variables
    imap_host = get_env_or_exit('IMAP_HOST')
    imap_port = int(get_env_or_exit('IMAP_PORT'))
    imap_user = get_env_or_exit('IMAP_USER')
    imap_password = get_env_or_exit('IMAP_PASSWORD')
    github_token = get_env_or_exit('GITHUB_TOKEN')
    github_repository = get_env_or_exit('GITHUB_REPOSITORY')

    # Optional: GitHub Project ID
    github_project_id = os.getenv('PROJECT_ID')
    if github_project_id:
        logger.info(f"📋 GitHub Project integration enabled: {github_project_id}")
    else:
        logger.info("📋 GitHub Project integration disabled (PROJECT_ID not set)")

    # Initialize GitHub helper
    github = GitHubHelper(github_token, github_repository)

    # Connect to IMAP
    try:
        mail = connect_imap(imap_host, imap_port, imap_user, imap_password)
    except Exception as e:
        logger.error(f"Failed to connect to IMAP: {e}")
        sys.exit(1)

    try:
        # Fetch unseen emails
        emails = fetch_unseen_emails(mail)
        logger.info(f"Processing {len(emails)} emails")

        # Track success/failure
        processed_count = 0
        failed_count = 0

        # Process each email
        for email_msg in emails:
            try:
                success = process_email(email_msg, github, github_project_id)

                if success:
                    # Mark as seen only if processing was successful
                    mark_email_as_seen(mail, email_msg.uid.encode())
                    processed_count += 1
                else:
                    logger.warning(f"Skipping email {email_msg.uid} due to processing error")
                    failed_count += 1

            except Exception as e:
                logger.error(f"Error processing email {email_msg.uid}: {e}")
                failed_count += 1
                continue

        logger.info("=" * 60)
        logger.info(f"📊 Email processing summary:")
        logger.info(f"   ✅ Successfully processed: {processed_count}")
        logger.info(f"   ❌ Failed: {failed_count}")
        logger.info(f"   📧 Total emails fetched: {len(emails)}")
        logger.info("=" * 60)

        # Exit with error if any emails failed to process
        if failed_count > 0:
            logger.error(f"⚠️  Workflow failed: {failed_count} email(s) could not be processed")
            logger.error("These emails remain UNSEEN and will be retried on the next run")
            sys.exit(1)

        logger.info("✅ All emails processed successfully!")

    finally:
        close_imap(mail)


if __name__ == "__main__":
    main()
