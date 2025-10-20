# GitHub Helpdesk - Actions Edition

## Overview

A serverless email-to-GitHub-issues helpdesk system that runs entirely on GitHub Actions. **No database, no server hosting, no state files** required.

## Architecture

### Core Concept
Use GitHub Actions as the "server" and GitHub's native features for state storage:
- **GitHub Issues** = Support tickets
- **Issue comments** = Conversation history
- **Issue #1** = System state (last GitHub comment check timestamp)
- **Each issue's body** = Email thread metadata (hidden HTML comment)
- **IMAP SEEN flags** = Email deduplication (no state files needed!)
- **Workflow secrets** = Email credentials

### Components

#### 1. Email → GitHub Workflow (Scheduled)
**File**: `.github/workflows/email-to-github.yml`

- **Trigger**: Cron schedule (every 5-15 minutes)
- **Process**:
  1. Connect to IMAP inbox
  2. Fetch **UNSEEN** emails only (IMAP flag-based filtering)
  3. For each unseen email:
     - Parse subject, body, headers (In-Reply-To, References, Message-ID)
     - Check for `[GH-####]` token in subject → find existing issue by number
     - If no token, search GitHub issues by `label:from:customer@example.com` → match by thread ID in issue metadata
     - **If existing issue found**:
       - Add comment to GitHub issue with email body
       - Add hidden marker: `<!-- source:email -->`
     - **If new ticket**:
       - Get next issue number from GitHub API
       - Create issue with title: `[GH-####] Subject`
       - Add email body as issue description
       - Add hidden metadata in issue body:
         ```html
         <!-- HELPDESK_METADATA
         thread_id: AAMkAD...
         from: customer@example.com
         message_ids: ["<msg-id-1@>", "<msg-id-2@>"]
         -->
         ```
       - Add labels: `helpdesk`, `from:customer@example.com`
  4. Mark email as **SEEN** (IMAP flag) - prevents reprocessing
  5. **No state files needed** - IMAP server tracks what's been processed

#### 2. GitHub → Email Workflow (Event-Driven)
**File**: `.github/workflows/github-to-email.yml`

- **Trigger**: `issue_comment` event (created)
- **Process**:
  1. Receive webhook when comment is added to any issue
  2. **Skip if**:
     - Issue doesn't have `helpdesk` label
     - Comment author is a bot (`github.event.comment.user.type == 'Bot'`)
     - Comment contains hidden marker `<!-- source:email -->` (originated from email)
  3. **If valid team comment**:
     - Parse issue body to extract email metadata (thread_id, from, message_ids)
     - Format comment as email with proper threading:
       - `From`: support email
       - `To`: customer email (from metadata)
       - `Subject`: `Re: [GH-####] Original subject`
       - `In-Reply-To`: Most recent message_id from metadata
       - `References`: All message_ids from metadata (space-separated)
       - `Body`: Comment text (plain text + HTML)
     - Send via SMTP
     - **Update Issue #1**: Record that this comment was sent (optional, for audit)
     - **Update issue metadata**: Append new sent message_id to the list

**Alternative for GitHub → Email**: Instead of event-driven, could use scheduled polling:
- Poll GitHub for new comments since last check (timestamp in Issue #1)
- Allows batch processing and retry logic
- Trade-off: 1-5 min delay vs instant webhook response

**Recommendation**: Start with event-driven (instant), add polling as fallback if needed.

### State Storage Strategy

**✅ Chosen Approach: Issue-Based State (No Files)**

1. **Email deduplication**: IMAP SEEN flags (built-in, persistent)
2. **Thread → Issue mapping**: Search GitHub issues by label or parse metadata
3. **Issue → Email mapping**: Stored in each issue's body (HTML comment)
4. **Last GitHub poll time**: Stored in Issue #1 body (only if using polling instead of events)

**Example Issue #1 (System State):**
```markdown
# Helpdesk System State

**Do not close or delete this issue.**

Last GitHub comment check: 2025-10-20T13:45:00Z
Status: ✅ Running
```

**Example Issue #42 (Customer Ticket):**
```markdown
# [GH-0042] Customer can't login

Customer reported:
> I'm unable to log into my account. Getting error "Invalid credentials"

<!-- HELPDESK_METADATA
thread_id: AAMkADExMzU3...
from: customer@example.com
message_ids: ["<abc123@mail.gmail.com>", "<def456@mail.gmail.com>"]
-->
```

### Loop Prevention

- **Marker in email-originated comments**: `<!-- source:email -->`
- **Check comment author type**: Skip if `user.type === 'Bot'`
- **Check for helpdesk label**: Only process issues with `helpdesk` label
- **IMAP SEEN flag**: Prevents processing same email twice

### Email Threading

When replying to customers via GitHub comment:
```python
msg = MIMEMultipart('alternative')
msg['From'] = 'support@yourcompany.com'
msg['To'] = 'customer@example.com'
msg['Subject'] = 'Re: [GH-1234] Original subject'
msg['In-Reply-To'] = '<most-recent-message-id@mail.com>'
msg['References'] = '<msg1@> <msg2@> <most-recent@>'
msg['Message-ID'] = generate_message_id()  # Save this to issue metadata

# Add both plain text and HTML parts
msg.attach(MIMEText(plain_text, 'plain'))
msg.attach(MIMEText(html_content, 'html'))
```

## Project Structure

```
github-helpdesk-actions/
├── .github/
│   └── workflows/
│       ├── email-to-github.yml      # Scheduled IMAP poller
│       └── github-to-email.yml      # Event-driven responder
├── scripts/
│   ├── email_to_github.py           # Main: Process emails → create/update issues
│   ├── github_to_email.py           # Main: Send issue comments → email
│   ├── github_helper.py             # GitHub API wrapper (search, create, update)
│   ├── email_helper.py              # IMAP/SMTP helpers (fetch, send, parse)
│   └── utils.py                     # Shared utilities (parse metadata, format, etc.)
├── requirements.txt                 # Python dependencies (requests or PyGithub)
├── .gitignore
└── README.md
```

**Note**: No `.helpdesk/` directory needed! No state files to manage.

## Environment Variables (GitHub Secrets)

Required secrets to configure in repository settings:

```bash
# Email Configuration
IMAP_HOST=imap.gmail.com
IMAP_PORT=993
IMAP_USER=support@yourcompany.com
IMAP_PASSWORD=app-specific-password

SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=support@yourcompany.com
SMTP_PASSWORD=app-specific-password

# GitHub Configuration (auto-provided)
GITHUB_TOKEN=${{ secrets.GITHUB_TOKEN }}
GITHUB_REPOSITORY=${{ github.repository }}  # owner/repo
```

## Implementation Phases

### Phase 1: Foundation ✅
- [x] Create repository structure
- [x] Update architecture plan (stateless approach)
- [ ] Create `requirements.txt` (likely just `requests`)
- [ ] Create Python script stubs
- [ ] Create GitHub helper module (API wrapper)
- [ ] Create email helper module (IMAP/SMTP using stdlib)
- [ ] Create utils module (metadata parsing, formatting)

### Phase 2: Email → GitHub
- [ ] Implement `email_to_github.py`:
  - [ ] Connect to IMAP, fetch UNSEEN emails
  - [ ] Parse email (subject, body, headers, Message-ID)
  - [ ] Extract `[GH-####]` from subject if present
  - [ ] Search GitHub for existing issue (by number or label)
  - [ ] Create new issue OR add comment to existing
  - [ ] Embed metadata in issue body (HTML comment)
  - [ ] Mark email as SEEN
- [ ] Create workflow `.github/workflows/email-to-github.yml` (cron: every 5 min)
- [ ] Test: New email → Creates issue with [GH-####]
- [ ] Test: Reply email (with token) → Adds comment
- [ ] Test: Reply email (without token) → Finds issue by label/thread_id

### Phase 3: GitHub → Email
- [ ] Implement `github_to_email.py`:
  - [ ] Parse webhook payload (issue number, comment body, author)
  - [ ] Check if should skip (bot, no helpdesk label, has email marker)
  - [ ] Fetch issue, extract email metadata from body
  - [ ] Format email with threading headers
  - [ ] Send via SMTP
  - [ ] Update issue metadata with new Message-ID (optional)
- [ ] Create workflow `.github/workflows/github-to-email.yml` (on: issue_comment)
- [ ] Test: Team comment → Sends email to customer
- [ ] Test: Bot comment → Skipped
- [ ] Test: Email-originated comment → Skipped (has marker)

### Phase 4: Polish & Error Handling
- [ ] Add retry logic for SMTP failures (exponential backoff)
- [ ] Add retry logic for GitHub API rate limits
- [ ] Add error handling for malformed emails (no subject, no body)
- [ ] Add workflow status badges to README
- [ ] Add detailed logging/debugging output
- [ ] Create Issue #1 programmatically on first run (system state)
- [ ] Test edge cases:
  - [ ] Customer removes [GH-####] from subject
  - [ ] Multiple replies in quick succession
  - [ ] IMAP connection failure
  - [ ] SMTP send failure
  - [ ] GitHub API rate limit

## Benefits of This Approach

✅ **Zero infrastructure costs** (within GitHub Actions free tier: 2000 min/month)
✅ **No database to maintain** (GitHub Issues = database)
✅ **No state files** (IMAP flags + issue metadata = state)
✅ **No git commits for state** (no repo pollution)
✅ **Event-driven GitHub→Email** (instant response, no polling delay)
✅ **Built-in secrets management** (GitHub Secrets)
✅ **Native GitHub UI** (manage tickets directly in Issues)
✅ **Easy deployment** (just push to GitHub)
✅ **Python stdlib** (imaplib, smtplib built-in - minimal dependencies!)
✅ **Resilient** (IMAP SEEN flags survive workflow failures)

## Tradeoffs

⚠️ **Email→GitHub polling delay** (5-15 min based on cron schedule)
⚠️ **Issue search overhead** (GitHub API calls to find matching issues)
⚠️ **GitHub Actions minutes** (2000/month free, ~$0.008/min after)
⚠️ **API rate limits** (5000 requests/hour for authenticated - sufficient for most use cases)
⚠️ **No admin UI** (use GitHub Issues UI instead)
⚠️ **HTML comment parsing** (need to extract metadata from issue body reliably)

## Tech Stack

- **Runtime**: Python 3.11+ (pre-installed on GitHub Actions runners)
- **Language**: Python
- **Email**: `imaplib` (stdlib), `smtplib` (stdlib), `email` module (stdlib)
- **GitHub API**: `requests` (lightweight) or `PyGithub` (convenience)
- **State**: IMAP flags + GitHub Issues (no files!)
- **CI/CD**: GitHub Actions (built-in)

**Why Python?**
- ✅ Pre-installed on Actions runners (no npm install delay)
- ✅ `imaplib` and `smtplib` are stdlib (no dependencies for email!)
- ✅ Clean syntax for parsing/string manipulation
- ✅ Fast startup, simple to debug
- ✅ Great email handling libraries

## Development Workflow

```bash
# Local development (optional virtualenv)
python3 -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt

# Testing locally (set env vars)
export IMAP_HOST=imap.gmail.com
export IMAP_USER=test@example.com
export IMAP_PASSWORD=yourapppassword
export GITHUB_TOKEN=ghp_yourtoken
export GITHUB_REPOSITORY=owner/repo

python scripts/email_to_github.py      # Test email processing
python scripts/github_to_email.py      # Test email sending

# Deployment
git push origin main  # Workflows auto-deploy and run on schedule/events
```

## Security Considerations

- ✅ All credentials in GitHub Secrets (encrypted at rest)
- ✅ IMAP/SMTP over TLS (encrypted in transit)
- ✅ Sanitize email content before creating issues (prevent XSS/injection)
- ✅ Rate limit protection (GitHub Actions has built-in timeouts)
- ✅ No customer data in state files (everything in private repo issues)
- ✅ Bot detection (prevent email loops)
- ⚠️ Issue metadata is visible to repo collaborators (don't store sensitive data)
- ⚠️ Consider making repo private if handling sensitive customer info

## Future Enhancements

- **Webhook alternative for email**: Use SendGrid/Mailgun inbound parse for instant email processing (no polling)
- **Multi-repository support**: Route emails to different repos based on To: address or subject tags
- **Attachments**: Upload email attachments to GitHub issue via API
- **Rich formatting**: Convert email HTML to GitHub-flavored Markdown
- **Customer satisfaction**: Auto-send survey when issue is closed
- **Analytics**: Weekly/monthly stats (response time, tickets resolved, etc.)
- **Auto-assignment**: Assign issues to team members based on labels/keywords
- **Canned responses**: Template library for common replies
- **SLA tracking**: Alert if issues not responded to within X hours
