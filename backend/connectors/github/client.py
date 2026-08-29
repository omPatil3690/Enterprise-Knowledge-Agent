"""
GitHub API Client.

Handles all network I/O with the GitHub REST API, including:
- Credential validation and connection testing (GET /user)
- Repository auto-discovery (/user/repos)
- Repository metadata retrieval (GET /repos/{owner}/{repo})
- File tree & file content retrieval with cursor-style pagination
- Issue and Pull Request listing (GET /repos/{owner}/{repo}/issues)
- Resilient error recovery for private / missing resources
- Rate-limit handling (HTTP 403 with rate limit headers)
"""

import os
import time
from typing import Any, Dict, List, Optional
import requests

# GitHub REST API base URL
GITHUB_API_BASE = "https://api.github.com"


class GitHubClient:
    """
    Client for interacting with the GitHub REST API.
    Uses a Personal Access Token (GITHUB_TOKEN) for authentication and higher rate limits.
    """

    def __init__(self, token: Optional[str] = None):
        """
        Initialize the GitHub client.

        Args:
            token: GitHub Personal Access Token (defaults to GITHUB_TOKEN env var).
        """
        self.token = token or os.getenv("GITHUB_TOKEN")
        if not self.token:
            raise ValueError(
                "GitHub token must be provided or set in GITHUB_TOKEN environment variable."
            )

        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def _handle_rate_limit(self, response: requests.Response) -> None:
        """
        Sleeps until the GitHub rate limit resets when the API reports 403 or 429.
        """
        if response.status_code in (403, 429):
            reset = response.headers.get("X-RateLimit-Reset")
            if reset:
                try:
                    reset_ts = int(reset)
                    delay = max(0, reset_ts - int(time.time())) + 1
                    print(f"    ⏳ GitHub rate limit hit. Sleeping {delay}s until reset...")
                    time.sleep(delay)
                except ValueError:
                    pass

    def test_connection(self) -> bool:
        """
        Validates the personal access token and API reachability against GET /user.

        Returns:
            True if connection and authentication succeed, False otherwise.
        """
        url = f"{GITHUB_API_BASE}/user"
        try:
            response = self.session.get(url)
            if response.status_code in (403, 429):
                self._handle_rate_limit(response)
                response = self.session.get(url)
            return response.status_code == 200
        except Exception:
            return False

    def get_current_user(self) -> Optional[Dict[str, Any]]:
        """
        Returns the metadata of the authenticated user.
        """
        url = f"{GITHUB_API_BASE}/user"
        response = self.session.get(url)
        if response.status_code == 200:
            return response.json()
        return None

    def list_repos(
        self,
        affilation: str = "owner,collaborator,organization_member",
        per_page: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Lists repositories accessible to the authenticated token.
        Uses Link-header pagination to traverse all pages.

        Args:
            affilation: GitHub affiliation filter (owner, collaborator, organization_member).
            per_page: Max repos per page (GitHub max is 100).

        Returns:
            List of repository metadata dictionaries.
        """
        repos: List[Dict[str, Any]] = []
        url = f"{GITHUB_API_BASE}/user/repos"
        params: Dict[str, Any] = {"affiliation": affilation, "per_page": per_page}

        while url:
            response = self.session.get(url, params=params)
            if response.status_code in (403, 429):
                self._handle_rate_limit(response)
                response = self.session.get(url, params=params)
            if response.status_code != 200:
                break
            params = {}
            data = response.json()
            repos.extend(data)
            url = self._next_page_url(response.headers.get("Link", ""))
            if not data:
                break

        return repos

    @staticmethod
    def _next_page_url(link_header: str) -> Optional[str]:
        """
        Parses the RFC 5988 Link header to find the 'next' page URL.
        This mimics cursor-based pagination used by other connectors.
        """
        if not link_header:
            return None
        for part in link_header.split(","):
            ref, _, rel = part.partition(";")
            if "rel=\"next\"" in rel or "rel='next'" in rel:
                return ref.strip().strip("<>")
        return None

    def get_repo(self, owner: str, repo: str) -> Dict[str, Any]:
        """
        Fetches a single repository's metadata.

        Args:
            owner: GitHub owner (user or organization).
            repo: Repository name.

        Returns:
            Repository metadata dictionary.
        """
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}"
        response = self.session.get(url)
        if response.status_code in (403, 429):
            self._handle_rate_limit(response)
            response = self.session.get(url)
        if response.status_code != 200:
            return {}
        return response.json()

    def get_repo_file_tree(
        self,
        owner: str,
        repo: str,
        branch: str = "HEAD",
    ) -> List[Dict[str, Any]]:
        """
        Retrieves the full git tree of a repository to enumerate its files.

        Args:
            owner: GitHub owner (user or organization).
            repo: Repository name.
            branch: Branch or ref to enumerate (default 'HEAD').

        Returns:
            List of tree entries (files and directories) with paths, types, and sizes.
        """
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/git/trees/{branch}"
        response = self.session.get(url, params={"recursive": "1"})
        if response.status_code in (403, 429):
            self._handle_rate_limit(response)
            response = self.session.get(url, params={"recursive": "1"})
        if response.status_code != 200:
            return []
        data = response.json()
        return data.get("tree", [])

    def get_file_content(
        self,
        owner: str,
        repo: str,
        path: str,
        ref: str = "HEAD",
    ) -> Optional[Dict[str, Any]]:
        """
        Fetches the raw content of a single file via the contents API.
        Returns None for binary/large files that the API cannot base64-decode.

        Args:
            owner: GitHub owner.
            repo: Repository name.
            path: File path within the repository.
            ref: Branch or commit SHA.

        Returns:
            File metadata dict with 'content' (decoded text) or None on failure.
        """
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{path}"
        response = self.session.get(url, params={"ref": ref})
        if response.status_code in (403, 429):
            self._handle_rate_limit(response)
            response = self.session.get(url, params={"ref": ref})
        if response.status_code != 200:
            return None

        data = response.json()
        if data.get("type") != "file":
            return None

        content_b64 = data.get("content")
        if not content_b64:
            return None

        import base64
        try:
            data["content"] = base64.b64decode(content_b64).decode("utf-8", errors="replace")
        except Exception:
            data["content"] = ""
        return data

    def list_issues(
        self,
        owner: str,
        repo: str,
        state: str = "open",
        per_page: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Lists issues (and pull requests) for a repository with Link-header pagination.
        GitHub's issues endpoint includes pull requests; filter by 'pull_request' key.

        Args:
            owner: GitHub owner.
            repo: Repository name.
            state: 'open', 'closed', or 'all'.
            per_page: Max issues per page (GitHub max is 100).

        Returns:
            List of issue/PR metadata dictionaries.
        """
        issues: List[Dict[str, Any]] = []
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/issues"
        params: Dict[str, Any] = {"state": state, "per_page": per_page}

        while url:
            response = self.session.get(url, params=params)
            if response.status_code in (403, 429):
                self._handle_rate_limit(response)
                response = self.session.get(url, params=params)
            if response.status_code != 200:
                break
            params = {}
            data = response.json()
            issues.extend(data)
            url = self._next_page_url(response.headers.get("Link", ""))
            if not data:
                break

        return issues
