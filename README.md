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
- 🔁 **Reusable workflows** - Use across multiple repositories

## Two Ways to Use

1. **Direct Setup** - Install in your repository (see setup below)
2. **Reusable Workflows** - Reference this repo from other repositories ([see USAGE.md](USAGE.md))

**Want to use this for multiple projects?** Check out [USAGE.md](USAGE.md) to learn how to call these workflows from other repositories without copying any code!

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

If you want issues to be automatically added to a GitHub Project board, add the `PROJECT_ID` variable. See [GitHub Projects Integration](#optional-github-projects-integration) below for complete setup instructions.

### 2. Configure Secrets (Sensitive Data Only)

Go to repository **Settings → Secrets and variables → Actions → Secrets tab**, and add:

**Required:**
```
IMAP_PASSWORD=your-app-specific-password
SMTP_PASSWORD=your-app-specific-password
```

**Note:** For Gmail, you'll need to create an [App Password](https://support.google.com/accounts/answer/185833).

**Optional - Required for GitHub Projects Integration:**
```
PROJECT_PAT=github_pat_xxxxxxxxxxxxxxxxxxxxx
```

If you want to use GitHub Projects integration, you **must** create a Personal Access Token (PAT) with `project` permissions. See [GitHub Projects Integration](#optional-github-projects-integration) for detailed instructions on creating the PAT.

### 3. Enable GitHub Actions

Ensure GitHub Actions is enabled for your repository in Settings → Actions → General.

### 4. Adjust Workflow Permissions

Go to Settings → Actions → General → Workflow permissions:
- Select "Read and write permissions"
- Check "Allow GitHub Actions to create and approve pull requests"

### 5. Choose Your Email Processing Trigger

The workflow supports three trigger options. You can use one or combine them:

**Option 1: Scheduled Polling (Default)**
- Checks for new emails every 5 minutes automatically
- Uses GitHub Actions minutes (~2000 free/month)
- To adjust frequency, edit `.github/workflows/email-to-github.yml` line 7:
  - `*/15 * * * *` = every 15 minutes
  - `*/30 * * * *` = every 30 minutes
  - `0 * * * *` = every hour
- To disable: Comment out lines 4-7 in the workflow file

**Option 2: Webhook-Driven (Recommended for minimizing Actions usage)**
- Triggered instantly when emails arrive (via external service)
- Only uses Actions minutes when emails are received
- See [Webhook Integration Guide](#webhook-integration-for-instant-email-processing) below

**Option 3: Manual Trigger**
- Go to Actions tab → "Email to GitHub" → "Run workflow"
- Useful for testing or on-demand processing

**Hybrid Approach (Recommended):**
- Use webhooks for instant processing
- Keep hourly cron as backup (in case webhook fails)

### 6. Deploy

```bash
git push origin main
```

The workflows will start running based on your chosen triggers.

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

## Webhook Integration for Instant Email Processing

To minimize GitHub Actions usage and process emails instantly, you can trigger the workflow via webhooks instead of scheduled polling.

### How It Works

1. External service receives email
2. Service calls GitHub API with `repository_dispatch` event
3. Workflow runs immediately and processes emails

### Setup Steps

#### 1. Create a Personal Access Token (PAT)

1. Go to GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Click "Generate new token (classic)"
3. Give it a name: `Helpdesk Webhook Token`
4. Select scopes: **`repo`** (full control of private repositories)
5. Click "Generate token" and **copy the token** (starts with `ghp_`)
6. Store it securely (you'll need it for the webhook service)

#### 2. Test the Webhook

Test manually first to ensure it works:

```bash
curl -X POST \
  -H "Accept: application/vnd.github.v3+json" \
  -H "Authorization: token ghp_YOUR_TOKEN_HERE" \
  https://api.github.com/repos/YOUR_USERNAME/YOUR_REPO/dispatches \
  -d '{"event_type":"trigger"}'
```

**Note:** The `event_type` can be any value - the workflow will trigger regardless.

You should see the workflow run in the Actions tab.

#### 3. Choose a Webhook Service

### Option A: Zapier (Easiest, No Code)

**Free tier:** 100 tasks/month

1. Create a Zap: **Email by Zapier** → **Webhooks by Zapier**
2. Trigger: "New Inbound Email"
   - Get your Zapier email address (e.g., `myhelp123@robot.zapier.com`)
3. Action: "POST Request"
   - URL: `https://api.github.com/repos/YOUR_USERNAME/YOUR_REPO/dispatches`
   - Headers:
     ```
     Accept: application/vnd.github.v3+json
     Authorization: token ghp_YOUR_TOKEN
     ```
   - Data:
     ```json
     {"event_type": "trigger"}
     ```
4. Forward your support emails to the Zapier email address

### Option B: Make.com (formerly Integromat)

**Free tier:** 1,000 operations/month

1. Create a scenario: **Email** → **HTTP**
2. Email module: "Watch emails"
   - Configure IMAP connection (same credentials as GitHub Actions)
3. HTTP module: "Make a request"
   - URL: `https://api.github.com/repos/YOUR_USERNAME/YOUR_REPO/dispatches`
   - Method: POST
   - Headers:
     ```
     Accept: application/vnd.github.v3+json
     Authorization: token ghp_YOUR_TOKEN
     ```
   - Body:
     ```json
     {"event_type": "trigger"}
     ```

### Option C: SendGrid Inbound Parse

**Free tier:** 100 emails/day

1. Set up SendGrid Inbound Parse webhook
2. Create a serverless function (Cloudflare Workers, AWS Lambda, etc.) to:
   - Receive webhook from SendGrid
   - Call GitHub API with `repository_dispatch`
3. Configure DNS MX records to point to SendGrid

### Option D: Custom Script (Advanced)

Run a small script on your server that uses IMAP IDLE:

```python
# webhook_trigger.py
import imaplib
import requests
import os

def trigger_github_workflow():
    requests.post(
        f"https://api.github.com/repos/{os.getenv('REPO')}/dispatches",
        headers={
            "Accept": "application/vnd.github.v3+json",
            "Authorization": f"token {os.getenv('GITHUB_TOKEN')}"
        },
        json={"event_type": "trigger"}
    )

# Use IMAP IDLE to wait for new emails
mail = imaplib.IMAP4_SSL('imap.gmail.com')
mail.login(user, password)
mail.select('INBOX')
# ... implement IDLE monitoring
# When new email arrives, call trigger_github_workflow()
```

### Recommended Setup: Hybrid Approach

1. **Primary:** Use Zapier/Make.com webhook (instant processing)
2. **Backup:** Keep hourly cron job (catches any missed emails)

To adjust cron to hourly backup, edit `.github/workflows/email-to-github.yml`:
```yaml
schedule:
  - cron: '0 * * * *'  # Every hour instead of every 5 minutes
```

This gives you instant processing with a safety net!

## Optional: GitHub Projects Integration

If you want new issues to be automatically added to a GitHub Project board, follow these steps:

### Step 1: Create a Personal Access Token (PAT)

**Why is this needed?** Organization and user-level GitHub Projects require special permissions that the default `GITHUB_TOKEN` doesn't have. You need a Personal Access Token with `project` permissions.

1. **Go to GitHub Settings**:
   - Click your profile picture (top right) → Settings
   - Scroll down to "Developer settings" (bottom left)
   - Click "Personal access tokens" → "Fine-grained tokens"
   - Click "Generate new token"

2. **Configure the token**:
   - **Token name**: `Helpdesk Project Access`
   - **Expiration**: Choose duration (90 days, 1 year, or no expiration)
   - **Repository access**:
     - Select "Only select repositories"
     - Choose the repository where your helpdesk issues are created

3. **Set Permissions**:
   - **Repository permissions**:
     - Issues: **Read and write**
     - Metadata: **Read-only** (auto-selected)
   - **Account permissions** (scroll down):
     - Projects: **Read and write**

4. **Generate and copy**:
   - Click "Generate token"
   - **Copy the token immediately** (starts with `github_pat_`)
   - You won't be able to see it again!

5. **Add to repository secrets**:
   - Go to your repository: Settings → Secrets and variables → Actions → Secrets
   - Click "New repository secret"
   - Name: `PROJECT_PAT`
   - Value: Paste the token
   - Click "Add secret"

### Step 2: Get Your GitHub Project ID

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
   - Go to: Settings → Secrets and variables → Actions → Variables tab
   - Click "New repository variable"
   - Name: `PROJECT_ID`
   - Value: `PVT_kwHOAYg_f84BFG26` (your actual ID)

### Step 3: Pass PROJECT_PAT to the Reusable Workflow

If you're using this as a reusable workflow, you need to pass the `PROJECT_PAT` secret:

**In your calling repository's workflow file:**
```yaml
jobs:
  process-emails:
    uses: MLoacher/github-actions-helpdesk/.github/workflows/email-to-github.yml@main
    secrets:
      IMAP_PASSWORD: ${{ secrets.IMAP_PASSWORD }}
      PROJECT_PAT: ${{ secrets.PROJECT_PAT }}  # Add this line!
    with:
      IMAP_HOST: ${{ vars.IMAP_HOST }}
      IMAP_PORT: ${{ vars.IMAP_PORT }}
      IMAP_USER: ${{ vars.IMAP_USER }}
      PROJECT_ID: ${{ vars.PROJECT_ID }}
```

### Troubleshooting

**Error: "Resource not accessible by integration"**
- This means you're missing the `PROJECT_PAT` or it doesn't have the right permissions
- Create a new PAT following Step 1 above
- Ensure the PAT has `Projects: Read and write` permission

**Error: "Could not resolve to a node with the global id"**
- Your `PROJECT_ID` is incorrect
- Follow Step 2 to get the correct Project ID

Once configured, all new helpdesk issues will automatically appear in your project board!

## License

MIT
