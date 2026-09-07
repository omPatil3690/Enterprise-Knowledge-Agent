"""
Jira API Client.

Handles all network I/O with the Jira Cloud REST API (v3), including:
- Credential validation and connection testing (GET /rest/api/3/myself)
- Project discovery (GET /rest/api/3/project)
- Issue search via JQL (GET /rest/api/3/search) with startAt pagination
- Single issue retrieval (GET /rest/api/3/issue/{key})
- Resilient error recovery for individual issues/projects
"""

import base64
import os
from typing import Any, Dict, List, Optional

import dotenv
import requests

dotenv.load_dotenv()

# Standard field set requested on every issue to keep payloads lean.
DEFAULT_ISSUE_FIELDS = (
    "summary,description,status,issuetype,priority,assignee,reporter,"
    "labels,components,project,parent,resolution,created,updated"
)


class JiraClient:
    """
    Client for interacting with the Jira REST API (v3).
    Uses HTTP Basic authentication (email + API token) for Atlassian Cloud.
    """

    API_PATH = "/rest/api/3"

    def __init__(
        self,
        url: Optional[str] = None,
        username: Optional[str] = None,
        api_token: Optional[str] = None,
    ):
        """
        Initialize the Jira client.

        Args:
            url: Jira base URL (defaults to JIRA_URL in .env).
            username: Account e-mail address (defaults to JIRA_USERNAME in .env).
            api_token: Atlassian API token (defaults to JIRA_API_TOKEN in .env).
        """
        self.username = username or os.getenv("JIRA_USERNAME")
        self.api_token = api_token or os.getenv("JIRA_API_TOKEN")
        self.base_url = (url or os.getenv("JIRA_URL") or "").rstrip("/")

        if not (self.base_url and self.username and self.api_token):
            raise ValueError(
                "Jira credentials missing: Provide JIRA_URL, JIRA_USERNAME, "
                "and JIRA_API_TOKEN in .env."
            )

        basic = base64.b64encode(f"{self.username}:{self.api_token}".encode("utf-8")).decode("ascii")
        self.headers = {
            "Authorization": f"Basic {basic}",
            "Accept": "application/json",
            "X-Atlassian-Token": "no-check",
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def test_connection(self) -> bool:
        """
        Validates credentials and API reachability via GET /rest/api/3/myself.

        Returns:
            True if connection and authentication succeed, False otherwise.
        """
        try:
            url = f"{self.base_url}{self.API_PATH}/myself"
            response = self.session.get(url)
            return response.status_code == 200
        except Exception as e:
            print(f"⚠️ Jira connection test failed: {e}")
            return False

    def get_current_user(self) -> Optional[Dict[str, Any]]:
        """
        Returns the metadata of the authenticated user.
        """
        try:
            url = f"{self.base_url}{self.API_PATH}/myself"
            response = self.session.get(url)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"⚠️ Could not fetch Jira user info: {e}")
        return None

    def list_projects(self) -> List[Dict[str, Any]]:
        """
        Lists all projects visible to the authenticated account.

        Returns:
            List of project metadata dictionaries.
        """
        try:
            url = f"{self.base_url}{self.API_PATH}/project"
            response = self.session.get(url)
            if response.status_code == 200:
                return response.json()
            print(f"⚠️ Could not list Jira projects (HTTP {response.status_code}).")
        except Exception as e:
            print(f"⚠️ Could not list Jira projects: {e}")
        return []

    def get_project(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Fetches a single Jira project's full metadata.

        Args:
            key: Jira project key (e.g. 'ENG').

        Returns:
            Project metadata dictionary, or None if inaccessible.
        """
        try:
            url = f"{self.base_url}{self.API_PATH}/project/{key}"
            response = self.session.get(url)
            if response.status_code != 200:
                print(f"⚠️ Jira project '{key}' not found or inaccessible (HTTP {response.status_code}).")
                return None
            return response.json()
        except Exception as e:
            print(f"⚠️ Could not fetch Jira project {key}: {e}")
            return None

    def search_issues(
        self,
        jql: Optional[str] = None,
        project_key: Optional[str] = None,
        max_results: int = 100,
        fields: str = DEFAULT_ISSUE_FIELDS,
    ) -> List[Dict[str, Any]]:
        """
        Searches issues with cursor-style startAt pagination.

        Args:
            jql: Raw Jira Query Language filter. Overrides project_key.
            project_key: If provided, restricts the search to one project.
            max_results: Maximum numbers of issues to fetch.
            fields: Comma-separated issue fields to expand.

        Returns:
            List of issue dictionaries.
        """
        issues: List[Dict[str, Any]] = []
        if not jql:
            jql = f'project = "{project_key}"' if project_key else ""

        url = f"{self.base_url}{self.API_PATH}/search"
        start_at = 0
        page_size = min(max(max_results, 1), 100)

        while True:
            params: Dict[str, Any] = {
                "jql": jql,
                "fields": fields,
                "startAt": start_at,
                "maxResults": page_size,
            }
            response = self.session.get(url, params=params)
            if response.status_code != 200:
                print(f"⚠️ Jira search failed (HTTP {response.status_code}): {jql}")
                break

            data = response.json()
            results = data.get("issues", [])
            issues.extend(results)
            total = data.get("total", 0)

            next_start = start_at + len(results)
            if not results or next_start >= total or len(issues) >= max_results:
                break
            start_at = next_start

        return issues

    def get_issue(self, key: str, fields: str = DEFAULT_ISSUE_FIELDS) -> Optional[Dict[str, Any]]:
        """
        Fetches a single Jira issue by its key.

        Args:
            key: Issue key (e.g. 'ENG-123').
            fields: Comma-separated issue fields to expand.

        Returns:
            Issue dictionary, or None if not found / inaccessible.
        """
        try:
            url = f"{self.base_url}{self.API_PATH}/issue/{key}"
            response = self.session.get(url, params={"fields": fields})
            if response.status_code != 200:
                print(f"⚠️ Jira issue '{key}' not found or inaccessible (HTTP {response.status_code}).")
                return None
            return response.json()
        except Exception as e:
            print(f"⚠️ Could not fetch Jira issue {key}: {e}")
            return None