# GitHub Helpdesk - Actions Edition

[![Email to GitHub](https://github.com/MLoacher/github-actions-helpdesk/actions/workflows/email-to-github.yml/badge.svg)](https://github.com/MLoacher/github-actions-helpdesk/actions/workflows/email-to-github.yml)
[![GitHub to Email](https://github.com/MLoacher/github-actions-helpdesk/actions/workflows/github-to-email.yml/badge.svg)](https://github.com/MLoacher/github-actions-helpdesk/actions/workflows/github-to-email.yml)

A serverless email-to-GitHub-issues helpdesk system that runs entirely on GitHub Actions. **No database, no server hosting, no state files** required.

## Features

- 📧 Automatically convert emails into GitHub issues
- 💬 Reply to customers by commenting on issues
- 🔄 Proper email threading support
- 🏷️ Automatic ticket numbering with `[GH-####]` format
- 🤖 Loop prevention (no bot-to-bot conversations)
- 💾 Stateless design using IMAP flags and GitHub Issues
- 🆓 Runs on GitHub Actions free tier

## Architecture

- **GitHub Issues** = Support tickets
- **Issue comments** = Conversation history
- **IMAP SEEN flags** = Email deduplication
- **Issue metadata** = Email thread tracking (hidden HTML comments)
- **GitHub Actions** = Serverless execution

### Workflows

1. **Email → GitHub** (`.github/workflows/email-to-github.yml`)
   - Scheduled: Every 5-15 minutes
   - Fetches UNSEEN emails via IMAP
   - Creates new issues or adds comments to existing ones
   - Marks emails as SEEN to prevent reprocessing

2. **GitHub → Email** (`.github/workflows/github-to-email.yml`)
   - Event-driven: Triggers on issue comments
   - Sends team responses back to customers via SMTP
   - Maintains proper email threading

## Setup

### 1. Configure Repository Variables (Non-Sensitive)

Go to repository **Settings → Secrets and variables → Actions → Variables tab**, and add:

**Required:**
```
IMAP_HOST=imap.gmail.com
IMAP_PORT=993
IMAP_USER=CarolinJerGrp@gmail.com

SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=CarolinJerGrp@gmail.com
```

**Optional - GitHub Project Integration:**
```
PROJECT_ID=PVT_kwHOAYg_f84BFG26
```

If you want issues to be automatically added to a GitHub Project board, add the `PROJECT_ID` variable. See [How to Get Your Project ID](#how-to-get-your-github-project-id) below.

### 2. Configure Secrets (Sensitive Data Only)

Go to repository **Settings → Secrets and variables → Actions → Secrets tab**, and add:

```
IMAP_PASSWORD=your-app-specific-password
SMTP_PASSWORD=your-app-specific-password
```

**Note:** For Gmail, you'll need to create an [App Password](https://support.google.com/accounts/answer/185833).

### 3. Enable GitHub Actions

Ensure GitHub Actions is enabled for your repository in Settings → Actions → General.

### 4. Adjust Workflow Permissions

Go to Settings → Actions → General → Workflow permissions:
- Select "Read and write permissions"
- Check "Allow GitHub Actions to create and approve pull requests"

### 5. Deploy

```bash
git push origin main
```

The workflows will automatically start running on their schedules.

## Usage

### For Customers

1. **Create a ticket**: Send an email to `support@yourcompany.com`
   - A GitHub issue will be created with title `[GH-####] Your Subject`

2. **Reply to a ticket**: Reply to any email from the helpdesk
   - Your response will be added as a comment to the existing issue
   - The `[GH-####]` token helps track the conversation

### For Support Team

1. **View tickets**: Check the GitHub Issues page
   - Filter by `label:helpdesk` to see all support tickets

2. **Reply to customers**: Add a comment to the issue
   - Your comment will be automatically emailed to the customer
   - Email threading is preserved

3. **Close tickets**: Close the issue when resolved
   - Future emails from the customer will reopen it automatically

## How It Works

### Email to GitHub

1. Workflow runs on a schedule (every 5-15 minutes)
2. Connects to IMAP and fetches UNSEEN emails
3. For each email:
   - Checks for `[GH-####]` token in subject
   - If found, adds comment to existing issue
   - If not found, searches by email metadata or creates new issue
   - Embeds email metadata in issue body (HTML comment)
   - Marks email as SEEN

### GitHub to Email

1. Workflow triggers when a comment is added to any issue
2. Checks if comment should be sent:
   - Issue must have `helpdesk` label
   - Comment author must not be a bot
   - Comment must not have `<!-- source:email -->` marker
3. Extracts customer email from issue metadata
4. Sends email with proper threading headers
5. Updates issue metadata with new Message-ID

## Troubleshooting

### Emails not creating issues

- Check GitHub Actions logs in the "Actions" tab
- Verify IMAP credentials in repository secrets
- Ensure IMAP allows less secure apps / app passwords

### Replies not sending

- Check SMTP credentials
- Verify workflow has write permissions
- Check issue has `helpdesk` label

### Duplicate issues

- IMAP SEEN flags should prevent this
- Check if multiple workflows are running simultaneously

## Development

### Local Testing

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export IMAP_HOST=imap.gmail.com
export IMAP_USER=test@example.com
export IMAP_PASSWORD=yourapppassword
export GITHUB_TOKEN=ghp_yourtoken
export GITHUB_REPOSITORY=owner/repo

# Test scripts
python scripts/email_to_github.py
python scripts/github_to_email.py
```

## Project Structure

```
github-helpdesk-actions/
├── .github/
│   └── workflows/
│       ├── email-to-github.yml      # Scheduled IMAP poller
│       └── github-to-email.yml      # Event-driven responder
├── scripts/
│   ├── email_to_github.py           # Process emails → create/update issues
│   ├── github_to_email.py           # Send issue comments → email
│   ├── github_helper.py             # GitHub API wrapper
│   ├── email_helper.py              # IMAP/SMTP helpers
│   └── utils.py                     # Shared utilities
├── requirements.txt
├── .gitignore
└── README.md
```

## Benefits

✅ Zero infrastructure costs (within GitHub Actions free tier)
✅ No database to maintain
✅ No state files
✅ Event-driven responses
✅ Built-in secrets management
✅ Native GitHub UI
✅ Easy deployment
✅ Optional GitHub Projects integration

## Optional: GitHub Projects Integration

### How to Get Your GitHub Project ID

If you want new issues to be automatically added to a GitHub Project board:

1. **Create a GitHub Project** (if you don't have one):
   - Go to your repository or organization
   - Click on "Projects" tab
   - Click "New project"
   - Choose a template or start from scratch

2. **Get the Project ID**:

   **Method 1: From Project URL**
   - Open your project
   - Look at the URL: `https://github.com/users/USERNAME/projects/12`
   - Use the GitHub GraphQL API Explorer: https://docs.github.com/en/graphql/overview/explorer
   - Run this query (replace `12` with your project number):

   ```graphql
   query {
     user(login: "USERNAME") {
       projectV2(number: 12) {
         id
       }
     }
   }
   ```

   **Method 2: Using GitHub CLI**
   ```bash
   gh api graphql -f query='
     query {
       user(login: "USERNAME") {
         projectV2(number: 12) {
           id
         }
       }
     }
   '
   ```

   For organization projects, replace `user` with `organization`.

3. **Copy the Project ID**:
   - The ID will look like: `PVT_kwHOAYg_f84BFG26`
   - Add this to your repository variables as `PROJECT_ID`

4. **Grant Permissions**:
   - Go to Project Settings → Manage access
   - Ensure the repository has write access to the project

Once configured, all new helpdesk issues will automatically appear in your project board!

## License

MIT
