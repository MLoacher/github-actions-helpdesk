"""IMAP and SMTP helper functions for email processing."""

import imaplib
import smtplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import decode_header
from typing import List, Dict, Optional, Tuple
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Attachment:
    """Represents an email attachment."""

    def __init__(self):
        self.filename: str = ""
        self.content_type: str = ""
        self.size: int = 0
        self.data: bytes = b""


class EmailMessage:
    """Represents a parsed email message."""

    def __init__(self):
        self.message_id: str = ""
        self.subject: str = ""
        self.from_addr: str = ""
        self.to_addr: str = ""
        self.body: str = ""
        self.html_body: str = ""
        self.in_reply_to: str = ""
        self.references: List[str] = []
        self.date: str = ""
        self.uid: str = ""
        self.attachments: List[Attachment] = []


def connect_imap(host: str, port: int, user: str, password: str) -> imaplib.IMAP4_SSL:
    """
    Connect to IMAP server.

    Args:
        host: IMAP server hostname
        port: IMAP server port
        user: Username
        password: Password

    Returns:
        IMAP connection object
    """
    logger.info(f"Connecting to IMAP server {host}:{port}")
    mail = imaplib.IMAP4_SSL(host, port)
    mail.login(user, password)
    return mail


def fetch_unseen_emails(mail: imaplib.IMAP4_SSL, mailbox: str = "INBOX") -> List[EmailMessage]:
    """
    Fetch all unseen emails from mailbox.

    Args:
        mail: IMAP connection object
        mailbox: Mailbox name (default: INBOX)

    Returns:
        List of EmailMessage objects
    """
    logger.info(f"Fetching unseen emails from {mailbox}")
    mail.select(mailbox)

    # Search for unseen messages
    status, messages = mail.search(None, 'UNSEEN')

    if status != 'OK':
        logger.error("Failed to search for unseen messages")
        return []

    email_ids = messages[0].split()
    logger.info(f"Found {len(email_ids)} unseen emails")

    emails = []
    for email_id in email_ids:
        try:
            msg = fetch_email_by_id(mail, email_id)
            if msg:
                emails.append(msg)
        except Exception as e:
            logger.error(f"Error fetching email {email_id}: {e}")
            continue

    return emails


def fetch_email_by_id(mail: imaplib.IMAP4_SSL, email_id: bytes) -> Optional[EmailMessage]:
    """
    Fetch and parse a single email by ID.

    Args:
        mail: IMAP connection object
        email_id: Email ID to fetch

    Returns:
        EmailMessage object or None
    """
    status, msg_data = mail.fetch(email_id, '(RFC822)')

    if status != 'OK':
        return None

    raw_email = msg_data[0][1]
    msg = email.message_from_bytes(raw_email)

    parsed = EmailMessage()
    parsed.uid = email_id.decode()

    # Parse headers
    parsed.message_id = msg.get('Message-ID', '')
    parsed.subject = decode_email_header(msg.get('Subject', ''))
    parsed.from_addr = msg.get('From', '')
    parsed.to_addr = msg.get('To', '')
    parsed.date = msg.get('Date', '')
    parsed.in_reply_to = msg.get('In-Reply-To', '')

    # Parse References header
    references = msg.get('References', '')
    if references:
        parsed.references = references.split()

    # Parse body and attachments
    parsed.body, parsed.html_body = extract_email_body(msg)
    parsed.attachments = extract_attachments(msg)

    return parsed


def decode_email_header(header: str) -> str:
    """
    Decode email header (handles encoded subjects).

    Args:
        header: Raw header string

    Returns:
        Decoded header string
    """
    if not header:
        return ""

    decoded_parts = decode_header(header)
    decoded_str = ""

    for part, encoding in decoded_parts:
        if isinstance(part, bytes):
            decoded_str += part.decode(encoding or 'utf-8', errors='ignore')
        else:
            decoded_str += part

    return decoded_str


def extract_attachments(msg: email.message.Message) -> List[Attachment]:
    """
    Extract attachments from email.

    Args:
        msg: Email message object

    Returns:
        List of Attachment objects
    """
    attachments = []

    if msg.is_multipart():
        for part in msg.walk():
            content_disposition = str(part.get("Content-Disposition", ""))

            # Check if this is an attachment
            if "attachment" in content_disposition or part.get_filename():
                try:
                    filename = part.get_filename()
                    if not filename:
                        continue

                    # Decode filename if needed
                    filename = decode_email_header(filename)

                    # Get content type
                    content_type = part.get_content_type()

                    # Get attachment data
                    data = part.get_payload(decode=True)
                    if not data:
                        continue

                    # Create attachment object
                    attachment = Attachment()
                    attachment.filename = filename
                    attachment.content_type = content_type
                    attachment.size = len(data)
                    attachment.data = data

                    attachments.append(attachment)
                    logger.info(f"Found attachment: {filename} ({content_type}, {len(data)} bytes)")

                except Exception as e:
                    logger.warning(f"Error extracting attachment: {e}")
                    continue

    return attachments


def extract_email_body(msg: email.message.Message) -> Tuple[str, str]:
    """
    Extract plain text and HTML body from email.

    Args:
        msg: Email message object

    Returns:
        Tuple of (plain_text_body, html_body)
    """
    plain_body = ""
    html_body = ""

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition", ""))

            # Skip attachments
            if "attachment" in content_disposition:
                continue

            try:
                body = part.get_payload(decode=True)
                if body is None:
                    continue

                charset = part.get_content_charset() or 'utf-8'
                body = body.decode(charset, errors='ignore')

                if content_type == "text/plain":
                    plain_body += body
                elif content_type == "text/html":
                    html_body += body
            except Exception as e:
                logger.warning(f"Error extracting email part: {e}")
                continue
    else:
        content_type = msg.get_content_type()
        try:
            body = msg.get_payload(decode=True)
            if body:
                charset = msg.get_content_charset() or 'utf-8'
                body = body.decode(charset, errors='ignore')

                if content_type == "text/html":
                    html_body = body
                else:
                    plain_body = body
        except Exception as e:
            logger.warning(f"Error extracting email body: {e}")

    return plain_body.strip(), html_body.strip()


def mark_email_as_seen(mail: imaplib.IMAP4_SSL, email_id: bytes) -> bool:
    """
    Mark email as seen/read.

    Args:
        mail: IMAP connection object
        email_id: Email ID to mark

    Returns:
        True if successful
    """
    try:
        mail.store(email_id, '+FLAGS', '\\Seen')
        logger.info(f"Marked email {email_id.decode()} as seen")
        return True
    except Exception as e:
        logger.error(f"Error marking email as seen: {e}")
        return False


def send_email(smtp_host: str, smtp_port: int, smtp_user: str, smtp_password: str,
               from_addr: str, to_addr: str, subject: str, body: str,
               in_reply_to: str = "", references: List[str] = None,
               message_id: str = "") -> bool:
    """
    Send email via SMTP.

    Args:
        smtp_host: SMTP server hostname
        smtp_port: SMTP server port
        smtp_user: SMTP username
        smtp_password: SMTP password
        from_addr: Sender email address
        to_addr: Recipient email address
        subject: Email subject
        body: Email body (plain text)
        in_reply_to: In-Reply-To header for threading
        references: List of References for threading
        message_id: Message-ID to use

    Returns:
        True if successful
    """
    logger.info(f"Sending email to {to_addr}")

    try:
        # Create message
        msg = MIMEMultipart('alternative')
        msg['From'] = from_addr
        msg['To'] = to_addr
        msg['Subject'] = subject

        if message_id:
            msg['Message-ID'] = message_id

        if in_reply_to:
            msg['In-Reply-To'] = in_reply_to

        if references:
            msg['References'] = ' '.join(references)

        # Add plain text part
        msg.attach(MIMEText(body, 'plain'))

        # TODO: Add HTML part if needed
        # html_body = markdown_to_html(body)
        # msg.attach(MIMEText(html_body, 'html'))

        # Connect and send
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)

        logger.info(f"Email sent successfully to {to_addr}")
        return True

    except Exception as e:
        logger.error(f"Error sending email: {e}")
        return False


def close_imap(mail: imaplib.IMAP4_SSL):
    """Close IMAP connection."""
    try:
        mail.close()
        mail.logout()
        logger.info("IMAP connection closed")
    except Exception as e:
        logger.warning(f"Error closing IMAP connection: {e}")
