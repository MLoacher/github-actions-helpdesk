"""GitHub API helper functions."""

import requests
import logging
from typing import Optional, Dict, List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GitHubHelper:
    """Wrapper for GitHub API operations."""

    def __init__(self, token: str, repository: str):
        """
        Initialize GitHub helper.

        Args:
            token: GitHub personal access token
            repository: Repository in format "owner/repo"
        """
        self.token = token
        self.repository = repository
        self.base_url = "https://api.github.com"
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }

    def create_issue(self, title: str, body: str, labels: List[str] = None) -> Optional[Dict]:
        """
        Create a new GitHub issue.

        Args:
            title: Issue title
            body: Issue body
            labels: List of label names

        Returns:
            Issue data dict or None
        """
        url = f"{self.base_url}/repos/{self.repository}/issues"

        data = {
            "title": title,
            "body": body
        }

        if labels:
            data["labels"] = labels

        try:
            logger.info(f"Creating issue: {title}")
            response = requests.post(url, json=data, headers=self.headers)
            response.raise_for_status()
            issue = response.json()
            logger.info(f"Created issue #{issue['number']}")
            return issue
        except requests.exceptions.RequestException as e:
            logger.error(f"Error creating issue: {e}")
            return None

    def add_comment(self, issue_number: int, body: str) -> Optional[Dict]:
        """
        Add a comment to an issue.

        Args:
            issue_number: Issue number
            body: Comment body

        Returns:
            Comment data dict or None
        """
        url = f"{self.base_url}/repos/{self.repository}/issues/{issue_number}/comments"

        data = {"body": body}

        try:
            logger.info(f"Adding comment to issue #{issue_number}")
            response = requests.post(url, json=data, headers=self.headers)
            response.raise_for_status()
            comment = response.json()
            logger.info(f"Added comment to issue #{issue_number}")
            return comment
        except requests.exceptions.RequestException as e:
            logger.error(f"Error adding comment: {e}")
            return None

    def get_issue(self, issue_number: int) -> Optional[Dict]:
        """
        Get issue details.

        Args:
            issue_number: Issue number

        Returns:
            Issue data dict or None
        """
        url = f"{self.base_url}/repos/{self.repository}/issues/{issue_number}"

        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting issue #{issue_number}: {e}")
            return None

    def update_issue(self, issue_number: int, title: str = None, body: str = None,
                    state: str = None, labels: List[str] = None) -> Optional[Dict]:
        """
        Update issue details.

        Args:
            issue_number: Issue number
            title: New title (optional)
            body: New body (optional)
            state: New state "open" or "closed" (optional)
            labels: New labels list (optional)

        Returns:
            Updated issue data dict or None
        """
        url = f"{self.base_url}/repos/{self.repository}/issues/{issue_number}"

        data = {}
        if title is not None:
            data["title"] = title
        if body is not None:
            data["body"] = body
        if state is not None:
            data["state"] = state
        if labels is not None:
            data["labels"] = labels

        try:
            logger.info(f"Updating issue #{issue_number}")
            response = requests.patch(url, json=data, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error updating issue: {e}")
            return None

    def search_issues(self, query: str) -> List[Dict]:
        """
        Search for issues.

        Args:
            query: Search query (GitHub search syntax)

        Returns:
            List of issue data dicts
        """
        url = f"{self.base_url}/search/issues"

        # Add repository filter to query
        full_query = f"{query} repo:{self.repository}"

        params = {"q": full_query, "per_page": 100}

        try:
            logger.info(f"Searching issues: {query}")
            response = requests.get(url, params=params, headers=self.headers)
            response.raise_for_status()
            results = response.json()
            logger.info(f"Found {results['total_count']} issues")
            return results.get('items', [])
        except requests.exceptions.RequestException as e:
            logger.error(f"Error searching issues: {e}")
            return []

    def find_issue_by_email(self, email: str) -> Optional[Dict]:
        """
        Find issue by customer email address.

        Args:
            email: Customer email address

        Returns:
            Issue data dict or None
        """
        # Search for issues with label matching email
        query = f"label:helpdesk label:from:{email} is:open"
        issues = self.search_issues(query)

        if issues:
            return issues[0]

        return None

    def add_labels(self, issue_number: int, labels: List[str]) -> bool:
        """
        Add labels to an issue.

        Args:
            issue_number: Issue number
            labels: List of label names to add

        Returns:
            True if successful
        """
        url = f"{self.base_url}/repos/{self.repository}/issues/{issue_number}/labels"

        data = {"labels": labels}

        try:
            response = requests.post(url, json=data, headers=self.headers)
            response.raise_for_status()
            logger.info(f"Added labels to issue #{issue_number}: {labels}")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Error adding labels: {e}")
            return False

    def reopen_issue(self, issue_number: int) -> bool:
        """
        Reopen a closed issue.

        Args:
            issue_number: Issue number

        Returns:
            True if successful
        """
        result = self.update_issue(issue_number, state="open")
        if result:
            logger.info(f"Reopened issue #{issue_number}")
            return True
        return False

    def get_next_issue_number(self) -> int:
        """
        Get the next issue number that will be assigned.

        Note: This is a best-effort prediction. The actual number
        may differ if issues are created concurrently.

        Returns:
            Predicted next issue number
        """
        url = f"{self.base_url}/repos/{self.repository}/issues"
        params = {"state": "all", "per_page": 1, "sort": "created", "direction": "desc"}

        try:
            response = requests.get(url, params=params, headers=self.headers)
            response.raise_for_status()
            issues = response.json()

            if issues:
                return issues[0]['number'] + 1
            else:
                return 1
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting next issue number: {e}")
            return 1

    def add_issue_to_project(self, issue_id: str, project_id: str) -> bool:
        """
        Add an issue to a GitHub Project (V2).

        Args:
            issue_id: Issue node ID (not issue number)
            project_id: Project node ID (format: PVT_xxx)

        Returns:
            True if successful
        """
        if not project_id:
            logger.debug("No project ID provided, skipping project addition")
            return True

        # GitHub Projects V2 uses GraphQL API
        graphql_url = "https://api.github.com/graphql"

        query = """
        mutation($projectId: ID!, $contentId: ID!) {
          addProjectV2ItemById(input: {projectId: $projectId, contentId: $contentId}) {
            item {
              id
            }
          }
        }
        """

        variables = {
            "projectId": project_id,
            "contentId": issue_id
        }

        try:
            logger.info(f"Adding issue to project {project_id}")
            response = requests.post(
                graphql_url,
                json={"query": query, "variables": variables},
                headers=self.headers
            )
            response.raise_for_status()
            result = response.json()

            if "errors" in result:
                logger.error(f"GraphQL errors: {result['errors']}")
                return False

            logger.info(f"Successfully added issue to project")
            return True

        except requests.exceptions.RequestException as e:
            logger.error(f"Error adding issue to project: {e}")
            return False
