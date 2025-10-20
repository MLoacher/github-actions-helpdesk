# Using This Helpdesk System in Other Repositories

This repository provides **reusable workflows** that can be called from any other repository. This allows you to use the same helpdesk logic across multiple projects without copying code.

> **Quick Start:** Copy the example workflow files from the [`examples/`](examples/) folder to your repository's `.github/workflows/` directory and configure your secrets/variables.

## Benefits

✅ **Single source of truth** - Update logic in one place
✅ **No code duplication** - Just reference this repo
✅ **Easy updates** - Pull latest changes automatically
✅ **Multiple projects** - Use same helpdesk for different products

## Setup in Another Repository

### Step 1: Create Workflow Files

In your other repository (e.g., `MyCompany/product-support`), create these workflows:

#### `.github/workflows/email-to-github.yml`

```yaml
name: Email to GitHub Helpdesk

on:
  schedule:
    - cron: '0 */6 * * *'  # Every 6 hours
  repository_dispatch:
  workflow_dispatch:

jobs:
  process-emails:
    uses: MLoacher/github-helpdesk-actions/.github/workflows/email-to-github.yml@main
    secrets:
      IMAP_PASSWORD: ${{ secrets.IMAP_PASSWORD }}
    with:
      IMAP_HOST: ${{ vars.IMAP_HOST }}
      IMAP_PORT: ${{ vars.IMAP_PORT }}
      IMAP_USER: ${{ vars.IMAP_USER }}
      PROJECT_ID: ${{ vars.PROJECT_ID }}
```

#### `.github/workflows/github-to-email.yml`

```yaml
name: GitHub to Email Helpdesk

on:
  issue_comment:
    types: [created]

jobs:
  send-email:
    # Only run if the issue has the helpdesk label
    if: contains(github.event.issue.labels.*.name, 'helpdesk')
    uses: MLoacher/github-helpdesk-actions/.github/workflows/github-to-email.yml@main
    secrets:
      SMTP_PASSWORD: ${{ secrets.SMTP_PASSWORD }}
    with:
      SMTP_HOST: ${{ vars.SMTP_HOST }}
      SMTP_PORT: ${{ vars.SMTP_PORT }}
      SMTP_USER: ${{ vars.SMTP_USER }}
```

### Step 2: Configure Secrets and Variables

In your repository (e.g., `MyCompany/product-support`):

**Repository Variables** (Settings → Secrets and variables → Actions → Variables):
```
IMAP_HOST=imap.gmail.com
IMAP_PORT=993
IMAP_USER=support@mycompany.com

SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=support@mycompany.com

PROJECT_ID=PVT_xxx  # Optional
```

**Repository Secrets** (Settings → Secrets and variables → Actions → Secrets):
```
IMAP_PASSWORD=your-app-password
SMTP_PASSWORD=your-app-password
```

### Step 3: Enable Workflow Permissions

Go to Settings → Actions → General → Workflow permissions:
- Select "Read and write permissions"
- Check "Allow GitHub Actions to create and approve pull requests"

### Step 4: Push and Test

```bash
git add .github/workflows/
git commit -m "Add helpdesk workflows"
git push
```

Test by:
1. Manually triggering from Actions tab
2. Sending a test email
3. Commenting on an issue with `helpdesk` label

## Using Different Versions

### Use Specific Version (Recommended for Production)

```yaml
uses: MLoacher/github-helpdesk-actions/.github/workflows/email-to-github.yml@v1.0.0
```

### Use Latest Main Branch (Get Updates Automatically)

```yaml
uses: MLoacher/github-helpdesk-actions/.github/workflows/email-to-github.yml@main
```

### Use Specific Commit (Maximum Stability)

```yaml
uses: MLoacher/github-helpdesk-actions/.github/workflows/email-to-github.yml@abc1234
```

## Multiple Helpdesks Example

You can use the same helpdesk repo for multiple products:

### Product 1: `MyCompany/product-a`
```yaml
# .github/workflows/helpdesk.yml
jobs:
  emails:
    uses: MLoacher/github-helpdesk-actions/.github/workflows/email-to-github.yml@main
    with:
      IMAP_USER: ${{ vars.IMAP_USER }}  # product-a@mycompany.com
```

### Product 2: `MyCompany/product-b`
```yaml
# .github/workflows/helpdesk.yml
jobs:
  emails:
    uses: MLoacher/github-helpdesk-actions/.github/workflows/email-to-github.yml@main
    with:
      IMAP_USER: ${{ vars.IMAP_USER }}  # product-b@mycompany.com
```

Each product gets its own issues in its own repository, but uses the same helpdesk logic!

## Customizing Schedule

Adjust the cron schedule in the calling workflow:

```yaml
on:
  schedule:
    - cron: '*/15 * * * *'  # Every 15 minutes
    # - cron: '0 * * * *'   # Every hour
    # - cron: '0 */6 * * *' # Every 6 hours
```

## Webhook Triggers

To use webhooks instead of schedules, configure your webhook service (Zapier, n8n, etc.) to call:

```bash
curl -X POST \
  -H "Authorization: token YOUR_PAT" \
  https://api.github.com/repos/YOUR_USERNAME/YOUR_REPO/dispatches \
  -d '{"event_type":"trigger"}'
```

This triggers the workflow in YOUR repository, which then calls the reusable workflow.

## Troubleshooting

### "Workflow not found" Error

Make sure:
- The workflow file exists in `MLoacher/github-helpdesk-actions`
- You're using the correct branch/tag (`@main`, `@v1.0.0`)
- The repository is public (or you have access if private)

### Secrets Not Working

- Secrets must be passed explicitly: `secrets: inherit` or individual secrets
- Cannot access the calling repo's secrets directly
- Pass them as shown in examples above

### Wrong Repository for Issues

Issues are created in the **calling repository** (where the workflow runs), not in `github-helpdesk-actions`.

## Example: Complete Setup

```
MyCompany/product-support/  (Your repo)
├── .github/
│   └── workflows/
│       ├── email-to-github.yml     # Calls reusable workflow
│       └── github-to-email.yml     # Calls reusable workflow
└── (no scripts/ folder needed!)

MLoacher/github-helpdesk-actions/  (This repo)
├── .github/
│   └── workflows/
│       ├── email-to-github.yml     # Reusable workflow
│       └── github-to-email.yml     # Reusable workflow
├── scripts/
│   ├── email_to_github.py
│   ├── github_to_email.py
│   └── ...
└── requirements.txt
```

All logic lives in `github-helpdesk-actions`, but issues are created in `product-support`!
