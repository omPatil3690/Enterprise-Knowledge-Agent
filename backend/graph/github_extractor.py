"""
GitHub Graph Extractor for Enterprise Knowledge Agent.

Extracts a complete GitHubGraphBundle from a GitHub repository using the
GitHubClient. Produces all typed nodes and relationships ready for ingestion
into Neo4j by the neo4j_client.

Pipeline position:
    GitHubClient (REST API)
           ↓
    GitHubGraphExtractor      ← THIS FILE
           ↓
    GitHubGraphBundle
           ↓
    Neo4jClient (graph DB write)

What is extracted per repository:
    Nodes:
        RepositoryNode  — repo metadata
        UserNode        — repo owner + issue/PR authors + assignees + reviewers + commit authors
        FileNode        — every blob from the Git Trees API
        IssueNode       — pure issues (PR entries excluded)
        PullRequestNode — pull requests from the /pulls endpoint
        CommitNode      — recent commits up to max_commits
        LabelNode       — all unique labels found on issues and PRs

    Relationships:
        Repository -[:OWNED_BY]->   User            (repo owner)
        Repository -[:CONTAINS]->   File            (one per file blob)
        User       -[:CREATED]->    Issue           (issue author)
        User       -[:ASSIGNED_TO]->Issue           (each assignee)
        Issue      -[:TAGGED_WITH]->Label           (each label)
        User       -[:CREATED]->    PullRequest     (PR author)
        User       -[:ASSIGNED_TO]->PullRequest     (each assignee)
        User       -[:REVIEWED]->   PullRequest     (each requested reviewer)
        PullRequest-[:TAGGED_WITH]->Label           (each label)
        User       -[:AUTHORED]->   Commit          (commit author by GitHub login)

    Not yet extracted (require expensive per-item API calls):
        Commit     -[:MODIFIES]->   File            (needs /commits/{sha} per commit)
        PullRequest-[:MODIFIES]->   File            (needs /pulls/{num}/files per PR)
        PullRequest-[:CLOSES]->     Issue           (needs body parsing heuristics)
        User       -[:MEMBER_OF]->  Team            (needs org-level token)
        Team       -[:HAS_ACCESS_TO]->Repository   (needs org-level token)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# ── sys.path bootstrap ────────────────────────────────────────────────────────
# Ensures 'backend' is importable when this file is run directly
# (python3 backend/graph/github_extractor.py) as well as when imported
# as a module from the project root.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
# ─────────────────────────────────────────────────────────────────────────────

from backend.connectors.github.client import GitHubClient
from backend.models.graph import (
    CommitNode,
    FileNode,
    GitHubGraphBundle,
    GraphRelationship,
    IssueNode,
    LabelNode,
    NodeLabel,
    PullRequestNode,
    RelType,
    RepositoryNode,
    UserNode,
)

# Regex to detect GitHub "closes #N" / "fixes #N" patterns in PR bodies
_CLOSES_RE = re.compile(
    r"(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s*#(\d+)",
    re.IGNORECASE,
)

# File extensions mapped to language names (extender of FileNode.language)
_EXT_LANGUAGE: Dict[str, str] = {
    ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
    ".tsx": "TypeScript", ".jsx": "JavaScript", ".java": "Java",
    ".go": "Go", ".rs": "Rust", ".cpp": "C++", ".c": "C",
    ".cs": "C#", ".rb": "Ruby", ".php": "PHP", ".swift": "Swift",
    ".kt": "Kotlin", ".scala": "Scala", ".sh": "Shell",
    ".yaml": "YAML", ".yml": "YAML", ".json": "JSON",
    ".md": "Markdown", ".html": "HTML", ".css": "CSS",
    ".sql": "SQL", ".tf": "Terraform", ".dockerfile": "Docker",
}


class GitHubGraphExtractor:
    """
    Extracts a GitHubGraphBundle from a single GitHub repository.

    Usage:
        client = GitHubClient()
        extractor = GitHubGraphExtractor(client)
        bundle = extractor.extract("owner", "repo")
    """

    def __init__(self, client: GitHubClient) -> None:
        self.client = client

    def extract(
        self,
        owner: str,
        repo: str,
        max_files: int = 1000,
        max_commits: int = 200,
        include_issues: bool = True,
        include_prs: bool = True,
        include_commits: bool = True,
    ) -> GitHubGraphBundle:
        """
        Full extraction pass for one repository.

        Args:
            owner:           GitHub owner (user or org login).
            repo:            Repository name.
            max_files:       Cap on File nodes extracted from the tree (default 1000).
            max_commits:     Cap on Commit nodes fetched (default 200).
            include_issues:  If False, skip issue/PR label extraction.
            include_prs:     If False, skip pull request extraction.
            include_commits: If False, skip commit extraction.

        Returns:
            GitHubGraphBundle with all extracted nodes and relationships.
        """
        full_name = f"{owner}/{repo}"
        print(f"\n{'='*60}")
        print(f"🔍 GitHub Graph Extractor — {full_name}")
        print(f"{'='*60}")

        # ── 1. Repository node ────────────────────────────────────────
        print("  [1/6] Fetching repository metadata...")
        repo_data = self.client.get_repo(owner, repo)
        if not repo_data:
            raise ValueError(f"Repository {full_name} not found or inaccessible.")
        repo_node = RepositoryNode.from_api(repo_data)
        print(f"        ✅ Repository: {repo_node.full_name} ({repo_node.language or 'unknown'})")

        # Accumulator dicts — keyed by node_id to deduplicate across sources
        users: Dict[str, UserNode] = {}
        files: List[FileNode] = []
        issues: List[IssueNode] = []
        prs: List[PullRequestNode] = []
        commits: List[CommitNode] = []
        labels: Dict[str, LabelNode] = {}
        rels: List[GraphRelationship] = []

        # ── 2. Repository owner ───────────────────────────────────────
        if repo_node.owner_login:
            owner_data = (repo_data.get("owner") or {})
            owner_user = UserNode.from_api(owner_data) if owner_data else UserNode(login=repo_node.owner_login)
            users[owner_user.node_id] = owner_user
            rels.append(GraphRelationship(
                rel_type=RelType.OWNED_BY,
                from_id=repo_node.node_id,
                to_id=owner_user.node_id,
            ))

        # ── 3. File tree ──────────────────────────────────────────────
        print(f"  [2/6] Fetching file tree (cap: {max_files})...")
        tree = self.client.get_repo_file_tree(owner, repo, branch="HEAD")
        blob_count = 0
        for entry in tree:
            if entry.get("type") != "blob":
                continue
            if blob_count >= max_files:
                print(f"        ⚠️  File cap ({max_files}) reached — skipping remainder.")
                break
            file_node = FileNode.from_api(entry, full_name)
            # Enrich language from extension
            if file_node.extension and not file_node.language:
                file_node.language = _EXT_LANGUAGE.get(file_node.extension.lower())
            files.append(file_node)
            rels.append(GraphRelationship(
                rel_type=RelType.CONTAINS,
                from_id=repo_node.node_id,
                to_id=file_node.node_id,
            ))
            blob_count += 1
        print(f"        ✅ Files: {blob_count}")

        # Build a path→node_id lookup so commits/PRs can resolve MODIFIES targets
        file_id_by_path: Dict[str, str] = {f.path: f.node_id for f in files}

        # ── 4. Issues ─────────────────────────────────────────────────
        if include_issues:
            print("  [3/6] Fetching issues (state=all)...")
            raw_issues = self.client.list_issues(owner, repo, state="all")
            issue_count = 0
            for raw in raw_issues:
                # Skip pull requests — they appear here but have their own node type
                if "pull_request" in raw:
                    continue
                issue_node = IssueNode.from_api(raw, full_name)
                issues.append(issue_node)
                issue_count += 1

                # Author → CREATED → Issue
                author = _make_user_from_raw(raw.get("user"))
                if author:
                    users[author.node_id] = author
                    rels.append(GraphRelationship(
                        rel_type=RelType.CREATED,
                        from_id=author.node_id,
                        to_id=issue_node.node_id,
                    ))

                # Assignees → ASSIGNED_TO → Issue
                for assignee_data in (raw.get("assignees") or []):
                    assignee = _make_user_from_raw(assignee_data)
                    if assignee:
                        users[assignee.node_id] = assignee
                        rels.append(GraphRelationship(
                            rel_type=RelType.ASSIGNED_TO,
                            from_id=assignee.node_id,
                            to_id=issue_node.node_id,
                        ))

                # Labels → TAGGED_WITH
                for label_data in (raw.get("labels") or []):
                    label_node = LabelNode.from_api(label_data, full_name)
                    labels[label_node.node_id] = label_node
                    rels.append(GraphRelationship(
                        rel_type=RelType.TAGGED_WITH,
                        from_id=issue_node.node_id,
                        to_id=label_node.node_id,
                    ))

            print(f"        ✅ Issues: {issue_count}")
        else:
            print("  [3/6] Issues skipped.")

        # ── 5. Pull Requests ──────────────────────────────────────────
        if include_prs:
            print("  [4/6] Fetching pull requests (state=all)...")
            raw_prs = self.client.list_pull_requests(owner, repo, state="all")
            pr_count = 0
            for raw in raw_prs:
                pr_node = PullRequestNode.from_api(raw, full_name)

                # Parse "Closes #N" from body to populate linked_issue_number
                if raw.get("body"):
                    match = _CLOSES_RE.search(raw["body"])
                    if match:
                        pr_node.linked_issue_number = int(match.group(1))

                prs.append(pr_node)
                pr_count += 1

                # Author → CREATED → PullRequest
                author = _make_user_from_raw(raw.get("user"))
                if author:
                    users[author.node_id] = author
                    rels.append(GraphRelationship(
                        rel_type=RelType.CREATED,
                        from_id=author.node_id,
                        to_id=pr_node.node_id,
                    ))

                # merged_by → (set state, already in node properties)
                if raw.get("merged_by"):
                    merger = _make_user_from_raw(raw["merged_by"])
                    if merger:
                        users[merger.node_id] = merger

                # Assignees → ASSIGNED_TO → PullRequest
                for assignee_data in (raw.get("assignees") or []):
                    assignee = _make_user_from_raw(assignee_data)
                    if assignee:
                        users[assignee.node_id] = assignee
                        rels.append(GraphRelationship(
                            rel_type=RelType.ASSIGNED_TO,
                            from_id=assignee.node_id,
                            to_id=pr_node.node_id,
                        ))

                # Requested reviewers → REVIEWED → PullRequest
                for reviewer_data in (raw.get("requested_reviewers") or []):
                    reviewer = _make_user_from_raw(reviewer_data)
                    if reviewer:
                        users[reviewer.node_id] = reviewer
                        rels.append(GraphRelationship(
                            rel_type=RelType.REVIEWED,
                            from_id=reviewer.node_id,
                            to_id=pr_node.node_id,
                        ))

                # Labels → TAGGED_WITH
                for label_data in (raw.get("labels") or []):
                    label_node = LabelNode.from_api(label_data, full_name)
                    labels[label_node.node_id] = label_node
                    rels.append(GraphRelationship(
                        rel_type=RelType.TAGGED_WITH,
                        from_id=pr_node.node_id,
                        to_id=label_node.node_id,
                    ))

                # CLOSES relationship (if we parsed a linked issue number)
                if pr_node.linked_issue_number is not None:
                    issue_nid = f"github:issue:{full_name}:{pr_node.linked_issue_number}"
                    rels.append(GraphRelationship(
                        rel_type=RelType.CLOSES,
                        from_id=pr_node.node_id,
                        to_id=issue_nid,
                        properties={"merged_at": pr_node.merged_at},
                    ))

            print(f"        ✅ Pull Requests: {pr_count}")
        else:
            print("  [4/6] Pull Requests skipped.")

        # ── 6. Commits ────────────────────────────────────────────────
        if include_commits:
            print(f"  [5/6] Fetching commits (cap: {max_commits})...")
            raw_commits = self.client.list_commits(owner, repo, max_count=max_commits)
            commit_count = 0
            for raw in raw_commits:
                commit_node = CommitNode.from_api(raw, full_name)
                commits.append(commit_node)
                commit_count += 1

                # GitHub-resolved author → AUTHORED → Commit
                gh_author = raw.get("author")
                if gh_author and gh_author.get("login"):
                    author = _make_user_from_raw(gh_author)
                    if author:
                        users[author.node_id] = author
                        rels.append(GraphRelationship(
                            rel_type=RelType.AUTHORED,
                            from_id=author.node_id,
                            to_id=commit_node.node_id,
                            properties={"date": commit_node.author_date},
                        ))

            print(f"        ✅ Commits: {commit_count}")
        else:
            print("  [5/6] Commits skipped.")

        # ── 7. Teams (org-only, graceful fail) ───────────────────────
        print("  [6/6] Teams — skipped (requires org-level token scope).")

        # ── Build and return bundle ───────────────────────────────────
        bundle = GitHubGraphBundle(
            repository=repo_node,
            users=list(users.values()),
            files=files,
            issues=issues,
            pull_requests=prs,
            commits=commits,
            labels=list(labels.values()),
            relationships=rels,
        )

        summary = bundle.summary()
        print(f"\n  📦 Bundle Summary:")
        for entity, count in summary.items():
            print(f"     {entity:<20} {count:>5}")
        print(f"{'='*60}\n")

        return bundle


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_user_from_raw(data: Optional[Dict[str, Any]]) -> Optional[UserNode]:
    """
    Safely builds a minimal UserNode from any embedded GitHub user dict.
    Returns None if data is missing or has no login.
    """
    if not data or not data.get("login"):
        return None
    return UserNode.from_api(data)


# ---------------------------------------------------------------------------
# Entry point — allows running directly:
#   python3 backend/graph/github_extractor.py --repo owner/name
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import json
    import os
    import sys
    from pathlib import Path

    # Ensure project root is in sys.path regardless of where this is run from
    PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    from dotenv import find_dotenv, load_dotenv
    load_dotenv(find_dotenv())

    from backend.connectors.github.client import GitHubClient
    from backend.graph.github_extractor import GitHubGraphExtractor

    parser = argparse.ArgumentParser(
        description="Run the GitHub Graph Extractor and print bundle summary."
    )
    parser.add_argument(
        "--repo",
        required=False,
        default=None,
        help="'owner/repo' to extract (e.g. omPatil3690/Enterprise-Knowledge-Agent). "
             "Defaults to auto-discovering the first accessible repo.",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=500,
        help="Max file nodes to extract (default 500).",
    )
    parser.add_argument(
        "--max-commits",
        type=int,
        default=50,
        help="Max commit nodes to extract (default 50).",
    )
    parser.add_argument(
        "--no-issues",
        action="store_true",
        help="Skip issue extraction.",
    )
    parser.add_argument(
        "--no-prs",
        action="store_true",
        help="Skip pull request extraction.",
    )
    parser.add_argument(
        "--no-commits",
        action="store_true",
        help="Skip commit extraction.",
    )
    parser.add_argument(
        "--save-json",
        action="store_true",
        help="Save the bundle as JSON to backend/graph/test_data/bundle.json.",
    )
    args = parser.parse_args()

    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print("❌ GITHUB_TOKEN is not set in your .env file.")
        sys.exit(1)

    client = GitHubClient(token=token)

    # Auto-discover repo if not provided
    target = args.repo
    if not target:
        print("No --repo provided. Auto-discovering first accessible repo...")
        repos = client.list_repos()
        if not repos:
            print("❌ No accessible repositories found for this token.")
            sys.exit(1)
        target = repos[0].get("full_name")
        print(f"Auto-selected: {target}")

    owner_str, _, repo_str = target.partition("/")
    if not owner_str or not repo_str:
        print(f"❌ Invalid --repo format '{target}'. Expected 'owner/name'.")
        sys.exit(1)

    extractor = GitHubGraphExtractor(client)
    bundle = extractor.extract(
        owner=owner_str,
        repo=repo_str,
        max_files=args.max_files,
        max_commits=args.max_commits,
        include_issues=not args.no_issues,
        include_prs=not args.no_prs,
        include_commits=not args.no_commits,
    )

    print("RELATIONSHIP TYPE BREAKDOWN:")
    from collections import Counter
    counts = Counter(r.rel_type for r in bundle.relationships)
    for rel_type, count in sorted(counts.items()):
        print(f"  {rel_type:<30} {count}")

    if args.save_json:
        out_dir = PROJECT_ROOT / "backend" / "graph" / "test_data"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "bundle.json"
        data = {
            "repository": bundle.repository.node_id,
            "summary": bundle.summary(),
            "nodes": [n.to_dict() for n in bundle.all_nodes()],
            "relationships": [r.to_dict() for r in bundle.relationships],
        }
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"\n💾 Bundle saved to: {out_path}")
