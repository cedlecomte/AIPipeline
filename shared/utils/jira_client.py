"""Jira REST API client for fetching issue data."""

from typing import Any

import httpx
import structlog

from config.settings import settings

logger = structlog.get_logger()


class JiraClient:
    """Client for interacting with Jira via REST API v3."""

    def __init__(self):
        self.base_url = settings.jira_base_url.rstrip("/")
        self.auth = (settings.jira_email, settings.jira_api_token)
        self.project_key = settings.jira_project_key
        self.cloud_id = settings.jira_cloud_id
        self.logger = logger.bind(component="jira_client")

    async def get_issue(self, issue_key: str) -> dict[str, Any]:
        """Fetch a Jira issue with comments.

        Args:
            issue_key: Jira issue identifier (e.g. ANSIBLE-123)

        Returns:
            Issue data dictionary
        """
        self.logger.info("jira.fetching_issue", issue_key=issue_key)

        url = f"{self.base_url}/rest/api/3/issue/{issue_key}"
        params = {
            "expand": "renderedFields",
            "fields": "summary,description,issuetype,priority,labels,components,"
                      "status,assignee,reporter,comment,attachment,subtasks,"
                      "issuelinks,fixVersions,customfield_*",
        }

        async with httpx.AsyncClient(auth=self.auth, timeout=30.0) as client:
            response = await client.get(url, params=params, headers={"Accept": "application/json"})
            response.raise_for_status()
            data = response.json()

        self.logger.info("jira.issue_fetched", issue_key=issue_key)
        return data

    async def search_issues(self, jql: str, max_results: int = 50) -> list[dict[str, Any]]:
        """Search Jira issues using JQL.

        Args:
            jql: JQL query string
            max_results: Maximum number of results

        Returns:
            List of issue dictionaries
        """
        self.logger.info("jira.searching", jql=jql)

        url = f"{self.base_url}/rest/api/3/search"
        params = {"jql": jql, "maxResults": max_results}

        async with httpx.AsyncClient(auth=self.auth, timeout=30.0) as client:
            response = await client.get(url, params=params, headers={"Accept": "application/json"})
            response.raise_for_status()
            data = response.json()

        return data.get("issues", [])

    async def update_issue(self, issue_key: str, fields: dict[str, Any]) -> None:
        """Update a Jira issue.

        Args:
            issue_key: Issue to update
            fields: Fields to update
        """
        self.logger.info("jira.updating_issue", issue_key=issue_key)

        url = f"{self.base_url}/rest/api/3/issue/{issue_key}"

        async with httpx.AsyncClient(auth=self.auth, timeout=30.0) as client:
            response = await client.put(
                url,
                json={"fields": fields},
                headers={"Accept": "application/json", "Content-Type": "application/json"},
            )
            response.raise_for_status()

    async def add_comment(self, issue_key: str, comment: str) -> None:
        """Add a comment to a Jira issue.

        Args:
            issue_key: Issue to comment on
            comment: Comment text (Atlassian Document Format)
        """
        self.logger.info("jira.adding_comment", issue_key=issue_key)

        url = f"{self.base_url}/rest/api/3/issue/{issue_key}/comment"
        body = {
            "body": {
                "type": "doc",
                "version": 1,
                "content": [{"type": "paragraph", "content": [{"type": "text", "text": comment}]}],
            }
        }

        async with httpx.AsyncClient(auth=self.auth, timeout=30.0) as client:
            response = await client.post(
                url,
                json=body,
                headers={"Accept": "application/json", "Content-Type": "application/json"},
            )
            response.raise_for_status()

    async def transition_issue(self, issue_key: str, transition_id: str) -> None:
        """Transition a Jira issue to a new status.

        Args:
            issue_key: Issue to transition
            transition_id: ID of the transition
        """
        self.logger.info("jira.transitioning", issue_key=issue_key, transition=transition_id)

        url = f"{self.base_url}/rest/api/3/issue/{issue_key}/transitions"

        async with httpx.AsyncClient(auth=self.auth, timeout=30.0) as client:
            response = await client.post(
                url,
                json={"transition": {"id": transition_id}},
                headers={"Accept": "application/json", "Content-Type": "application/json"},
            )
            response.raise_for_status()
