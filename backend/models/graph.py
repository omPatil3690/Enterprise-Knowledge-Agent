"""
Graph Entity & Relationship Models for Enterprise Knowledge Agent.

Defines strongly-typed node and relationship dataclasses for the GitHub
knowledge graph stored in Neo4j. These are provider-independent graph
primitives that bridge raw GitHub REST API payloads with the graph
ingestion layer.

Nodes:
    Repository  — a GitHub repo
    File        — a single file inside a repo (blob from Git Trees API)
    User        — a GitHub user or bot (author, reviewer, assignee, etc.)
    Team        — a GitHub org team with permission to a repo
    Issue       — a GitHub issue (not a PR)
    PullRequest — a GitHub pull request
    Commit      — a Git commit
    Label       — a GitHub label applied to issues/PRs

Relationships (directed edges):
    (:Repository)-[:CONTAINS]->(:File)
    (:Repository)-[:OWNED_BY]->(:User)
    (:User)-[:AUTHORED]->(:Commit)
    (:User)-[:CREATED]->(:Issue)
    (:User)-[:CREATED]->(:PullRequest)
    (:User)-[:REVIEWED]->(:PullRequest)
    (:User)-[:ASSIGNED_TO]->(:Issue)
    (:User)-[:ASSIGNED_TO]->(:PullRequest)
    (:User)-[:MEMBER_OF]->(:Team)
    (:Team)-[:HAS_ACCESS_TO]->(:Repository)
    (:Commit)-[:MODIFIES]->(:File)
    (:PullRequest)-[:MODIFIES]->(:File)
    (:PullRequest)-[:CLOSES]->(:Issue)
    (:PullRequest)-[:PART_OF]->(:Commit)
    (:Issue)-[:TAGGED_WITH]->(:Label)
    (:PullRequest)-[:TAGGED_WITH]->(:Label)

node_id format (stable MERGE key):
    github:repo:<full_name>
    github:file:<full_name>:<path>
    github:user:<login>
    github:team:<org>:<slug>
    github:issue:<full_name>:<num>
    github:pr:<full_name>:<num>
    github:commit:<full_name>:<sha>
    github:label:<full_name>:<name>
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# 1. Node Label Registry
# ---------------------------------------------------------------------------

class NodeLabel(str, Enum):
    """Canonical Neo4j node labels for GitHub entities."""
    REPOSITORY   = "Repository"
    FILE         = "File"
    USER         = "User"
    TEAM         = "Team"
    ISSUE        = "Issue"
    PULL_REQUEST = "PullRequest"
    COMMIT       = "Commit"
    LABEL        = "Label"


# ---------------------------------------------------------------------------
# 2. Relationship Type Registry
# ---------------------------------------------------------------------------

class RelType(str, Enum):
    """Canonical Neo4j relationship types for GitHub entity connections."""
    CONTAINS      = "CONTAINS"       # Repository -> File
    OWNED_BY      = "OWNED_BY"       # Repository -> User
    AUTHORED      = "AUTHORED"       # User -> Commit
    CREATED       = "CREATED"        # User -> Issue | PullRequest
    REVIEWED      = "REVIEWED"       # User -> PullRequest
    ASSIGNED_TO   = "ASSIGNED_TO"    # User -> Issue | PullRequest
    MEMBER_OF     = "MEMBER_OF"      # User -> Team
    HAS_ACCESS_TO = "HAS_ACCESS_TO"  # Team -> Repository
    MODIFIES      = "MODIFIES"       # Commit | PullRequest -> File
    CLOSES        = "CLOSES"         # PullRequest -> Issue
    PART_OF       = "PART_OF"        # Commit -> PullRequest (merge commit)
    TAGGED_WITH   = "TAGGED_WITH"    # Issue | PullRequest -> Label


# ---------------------------------------------------------------------------
# 3. Base Graph Primitives
# ---------------------------------------------------------------------------

@dataclass
class GraphNode:
    """
    Generic graph node primitive consumed by the Neo4j client.

    node_id  — stable platform-namespaced MERGE key.
    label    — maps to a Neo4j node label string.
    properties — flat dict written to the node.
    """
    label: str
    node_id: str
    properties: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GraphRelationship:
    """
    Generic directed graph relationship primitive consumed by the Neo4j client.

    rel_type   — maps to a Neo4j relationship type string.
    from_id    — source node_id.
    to_id      — target node_id.
    properties — optional edge metadata.
    """
    rel_type: str
    from_id: str
    to_id: str
    properties: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# 4. Typed Node Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class RepositoryNode:
    """
    GitHub repository node.
    Source: GET /repos/{owner}/{repo}
    """
    full_name: str
    name: str
    owner_login: str
    html_url: str
    description: Optional[str] = None
    private: bool = False
    visibility: str = "public"
    default_branch: str = "main"
    language: Optional[str] = None
    stargazers_count: int = 0
    forks_count: int = 0
    open_issues_count: int = 0
    watchers_count: int = 0
    network_count: int = 0
    size_kb: int = 0
    clone_url: Optional[str] = None
    ssh_url: Optional[str] = None
    git_url: Optional[str] = None
    homepage: Optional[str] = None
    topics: List[str] = field(default_factory=list)
    license_spdx: Optional[str] = None
    license_name: Optional[str] = None
    has_issues: bool = True
    has_projects: bool = False
    has_wiki: bool = False
    has_pages: bool = False
    has_discussions: bool = False
    is_fork: bool = False
    is_archived: bool = False
    is_disabled: bool = False
    is_template: bool = False
    allow_forking: bool = True
    pushed_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    @property
    def node_id(self) -> str:
        return f"github:repo:{self.full_name}"

    def to_graph_node(self) -> GraphNode:
        return GraphNode(
            label=NodeLabel.REPOSITORY,
            node_id=self.node_id,
            properties={k: v for k, v in asdict(self).items() if v is not None},
        )

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> "RepositoryNode":
        owner = (data.get("owner") or {}).get("login", "unknown")
        lic = data.get("license") or {}
        return cls(
            full_name=data.get("full_name", ""),
            name=data.get("name", ""),
            owner_login=owner,
            html_url=data.get("html_url", ""),
            description=data.get("description"),
            private=bool(data.get("private", False)),
            visibility=data.get("visibility", "public"),
            default_branch=data.get("default_branch", "main"),
            language=data.get("language"),
            stargazers_count=data.get("stargazers_count", 0) or 0,
            forks_count=data.get("forks_count", 0) or 0,
            open_issues_count=data.get("open_issues_count", 0) or 0,
            watchers_count=data.get("watchers_count", 0) or 0,
            network_count=data.get("network_count", 0) or 0,
            size_kb=data.get("size", 0) or 0,
            clone_url=data.get("clone_url"),
            ssh_url=data.get("ssh_url"),
            git_url=data.get("git_url"),
            homepage=data.get("homepage"),
            topics=data.get("topics", []) or [],
            license_spdx=lic.get("spdx_id"),
            license_name=lic.get("name"),
            has_issues=bool(data.get("has_issues", True)),
            has_projects=bool(data.get("has_projects", False)),
            has_wiki=bool(data.get("has_wiki", False)),
            has_pages=bool(data.get("has_pages", False)),
            has_discussions=bool(data.get("has_discussions", False)),
            is_fork=bool(data.get("fork", False)),
            is_archived=bool(data.get("archived", False)),
            is_disabled=bool(data.get("disabled", False)),
            is_template=bool(data.get("is_template", False)),
            allow_forking=bool(data.get("allow_forking", True)),
            pushed_at=data.get("pushed_at"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )


@dataclass
class UserNode:
    """
    GitHub user or bot node.
    Source: inline in any API response or GET /users/{username} (enriched).
    """
    login: str
    github_id: Optional[int] = None
    name: Optional[str] = None
    email: Optional[str] = None
    avatar_url: Optional[str] = None
    html_url: Optional[str] = None
    account_type: str = "User"
    site_admin: bool = False
    company: Optional[str] = None
    blog: Optional[str] = None
    location: Optional[str] = None
    bio: Optional[str] = None
    twitter_username: Optional[str] = None
    public_repos: Optional[int] = None
    public_gists: Optional[int] = None
    followers: Optional[int] = None
    following: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    @property
    def node_id(self) -> str:
        return f"github:user:{self.login}"

    def to_graph_node(self) -> GraphNode:
        return GraphNode(
            label=NodeLabel.USER,
            node_id=self.node_id,
            properties={k: v for k, v in asdict(self).items() if v is not None},
        )

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> "UserNode":
        return cls(
            login=data.get("login", ""),
            github_id=data.get("id"),
            name=data.get("name"),
            email=data.get("email"),
            avatar_url=data.get("avatar_url"),
            html_url=data.get("html_url"),
            account_type=data.get("type", "User"),
            site_admin=bool(data.get("site_admin", False)),
            company=data.get("company"),
            blog=data.get("blog"),
            location=data.get("location"),
            bio=data.get("bio"),
            twitter_username=data.get("twitter_username"),
            public_repos=data.get("public_repos"),
            public_gists=data.get("public_gists"),
            followers=data.get("followers"),
            following=data.get("following"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )


@dataclass
class FileNode:
    """
    A single file (blob) or directory (tree) inside a GitHub repository.
    Source: GET /repos/{owner}/{repo}/git/trees/{sha}?recursive=1
    """
    repo_full_name: str
    path: str
    sha: Optional[str] = None
    size: Optional[int] = None
    file_type: str = "blob"
    mode: Optional[str] = None
    extension: Optional[str] = None
    language: Optional[str] = None
    url: Optional[str] = None

    @property
    def node_id(self) -> str:
        return f"github:file:{self.repo_full_name}:{self.path}"

    @property
    def filename(self) -> str:
        return self.path.rsplit("/", 1)[-1]

    @property
    def directory(self) -> str:
        parts = self.path.rsplit("/", 1)
        return parts[0] if len(parts) > 1 else ""

    def to_graph_node(self) -> GraphNode:
        return GraphNode(
            label=NodeLabel.FILE,
            node_id=self.node_id,
            properties={k: v for k, v in asdict(self).items() if v is not None},
        )

    @classmethod
    def from_api(cls, data: Dict[str, Any], repo_full_name: str) -> "FileNode":
        path = data.get("path", "")
        filename = path.rsplit("/", 1)[-1]
        ext = ("." + filename.rsplit(".", 1)[-1]) if "." in filename else None
        return cls(
            repo_full_name=repo_full_name,
            path=path,
            sha=data.get("sha"),
            size=data.get("size"),
            file_type=data.get("type", "blob"),
            mode=data.get("mode"),
            extension=ext,
            url=data.get("url"),
        )


@dataclass
class IssueNode:
    """
    GitHub issue node. Pure issues only — PRs use PullRequestNode.
    Source: GET /repos/{owner}/{repo}/issues?state=all (filtered, no pull_request key)
    """
    repo_full_name: str
    number: int
    title: str
    state: str = "open"
    body: Optional[str] = None
    author_login: Optional[str] = None
    assignee_logins: List[str] = field(default_factory=list)
    label_names: List[str] = field(default_factory=list)
    milestone_title: Optional[str] = None
    milestone_number: Optional[int] = None
    comments_count: int = 0
    reactions_total: int = 0
    reactions_thumbs_up: int = 0
    reactions_thumbs_down: int = 0
    reactions_laugh: int = 0
    reactions_hooray: int = 0
    reactions_confused: int = 0
    reactions_heart: int = 0
    reactions_rocket: int = 0
    reactions_eyes: int = 0
    html_url: Optional[str] = None
    api_node_id: Optional[str] = None
    locked: bool = False
    active_lock_reason: Optional[str] = None
    closed_by_login: Optional[str] = None
    closed_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    @property
    def node_id(self) -> str:
        return f"github:issue:{self.repo_full_name}:{self.number}"

    def to_graph_node(self) -> GraphNode:
        props = {k: v for k, v in asdict(self).items() if v is not None}
        props.pop("assignee_logins", None)
        props.pop("label_names", None)
        return GraphNode(
            label=NodeLabel.ISSUE,
            node_id=self.node_id,
            properties=props,
        )

    @classmethod
    def from_api(cls, data: Dict[str, Any], repo_full_name: str) -> "IssueNode":
        reactions = data.get("reactions") or {}
        milestone = data.get("milestone") or {}
        closed_by = data.get("closed_by") or {}
        return cls(
            repo_full_name=repo_full_name,
            number=data.get("number", 0),
            title=data.get("title", ""),
            state=data.get("state", "open"),
            body=data.get("body"),
            author_login=(data.get("user") or {}).get("login"),
            assignee_logins=[
                a.get("login", "") for a in (data.get("assignees") or []) if a.get("login")
            ],
            label_names=[
                l.get("name", "") for l in (data.get("labels") or []) if l.get("name")
            ],
            milestone_title=milestone.get("title"),
            milestone_number=milestone.get("number"),
            comments_count=data.get("comments", 0) or 0,
            reactions_total=reactions.get("total_count", 0) or 0,
            reactions_thumbs_up=reactions.get("+1", 0) or 0,
            reactions_thumbs_down=reactions.get("-1", 0) or 0,
            reactions_laugh=reactions.get("laugh", 0) or 0,
            reactions_hooray=reactions.get("hooray", 0) or 0,
            reactions_confused=reactions.get("confused", 0) or 0,
            reactions_heart=reactions.get("heart", 0) or 0,
            reactions_rocket=reactions.get("rocket", 0) or 0,
            reactions_eyes=reactions.get("eyes", 0) or 0,
            html_url=data.get("html_url"),
            api_node_id=data.get("node_id"),
            locked=bool(data.get("locked", False)),
            active_lock_reason=data.get("active_lock_reason"),
            closed_by_login=closed_by.get("login"),
            closed_at=data.get("closed_at"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )


@dataclass
class PullRequestNode:
    """
    GitHub pull request node.
    Source: GET /repos/{owner}/{repo}/pulls/{number} (full) or issues endpoint (partial).
    Diff stats (additions/deletions/changed_files) are only available on full PR response.
    """
    repo_full_name: str
    number: int
    title: str
    state: str = "open"                     # "open" | "closed" | "merged"
    body: Optional[str] = None
    author_login: Optional[str] = None
    assignee_logins: List[str] = field(default_factory=list)
    reviewer_logins: List[str] = field(default_factory=list)
    label_names: List[str] = field(default_factory=list)
    # Branch context
    head_sha: Optional[str] = None
    head_ref: Optional[str] = None
    head_repo_full_name: Optional[str] = None
    base_sha: Optional[str] = None
    base_ref: Optional[str] = None
    # Merge info
    merge_commit_sha: Optional[str] = None
    merged: bool = False
    mergeable: Optional[bool] = None
    mergeable_state: Optional[str] = None
    merged_by_login: Optional[str] = None
    # Flags
    draft: bool = False
    rebaseable: Optional[bool] = None
    maintainer_can_modify: bool = False
    # Diff stats (full PR response only)
    additions: int = 0
    deletions: int = 0
    changed_files: int = 0
    commits_count: int = 0
    comments_count: int = 0
    review_comments_count: int = 0
    # Milestone
    milestone_title: Optional[str] = None
    milestone_number: Optional[int] = None
    # Linking
    linked_issue_number: Optional[int] = None
    html_url: Optional[str] = None
    api_node_id: Optional[str] = None
    # Timestamps
    closed_at: Optional[str] = None
    merged_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    @property
    def node_id(self) -> str:
        return f"github:pr:{self.repo_full_name}:{self.number}"

    def to_graph_node(self) -> GraphNode:
        props = {k: v for k, v in asdict(self).items() if v is not None}
        props.pop("assignee_logins", None)
        props.pop("reviewer_logins", None)
        props.pop("label_names", None)
        return GraphNode(
            label=NodeLabel.PULL_REQUEST,
            node_id=self.node_id,
            properties=props,
        )

    @classmethod
    def from_api(cls, data: Dict[str, Any], repo_full_name: str) -> "PullRequestNode":
        head = data.get("head") or {}
        base = data.get("base") or {}
        milestone = data.get("milestone") or {}
        merged_by = data.get("merged_by") or {}
        merged = bool(data.get("merged", False))
        return cls(
            repo_full_name=repo_full_name,
            number=data.get("number", 0),
            title=data.get("title", ""),
            state="merged" if merged else data.get("state", "open"),
            body=data.get("body"),
            author_login=(data.get("user") or {}).get("login"),
            assignee_logins=[
                a.get("login", "") for a in (data.get("assignees") or []) if a.get("login")
            ],
            reviewer_logins=[
                r.get("login", "") for r in (data.get("requested_reviewers") or []) if r.get("login")
            ],
            label_names=[
                l.get("name", "") for l in (data.get("labels") or []) if l.get("name")
            ],
            head_sha=head.get("sha"),
            head_ref=head.get("ref"),
            head_repo_full_name=(head.get("repo") or {}).get("full_name"),
            base_sha=base.get("sha"),
            base_ref=base.get("ref"),
            merge_commit_sha=data.get("merge_commit_sha"),
            merged=merged,
            mergeable=data.get("mergeable"),
            mergeable_state=data.get("mergeable_state"),
            merged_by_login=merged_by.get("login"),
            draft=bool(data.get("draft", False)),
            rebaseable=data.get("rebaseable"),
            maintainer_can_modify=bool(data.get("maintainer_can_modify", False)),
            additions=data.get("additions", 0) or 0,
            deletions=data.get("deletions", 0) or 0,
            changed_files=data.get("changed_files", 0) or 0,
            commits_count=data.get("commits", 0) or 0,
            comments_count=data.get("comments", 0) or 0,
            review_comments_count=data.get("review_comments", 0) or 0,
            milestone_title=milestone.get("title"),
            milestone_number=milestone.get("number"),
            html_url=data.get("html_url"),
            api_node_id=data.get("node_id"),
            closed_at=data.get("closed_at"),
            merged_at=data.get("merged_at"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )


@dataclass
class CommitNode:
    """
    GitHub commit node.
    Source: GET /repos/{owner}/{repo}/commits (list, metadata only)
    or GET /repos/{owner}/{repo}/commits/{sha} (full, includes file diffs).

    Note: added_files/removed_files/modified_files are populated only
    from the full single-commit response — they become :MODIFIES edges
    in the graph and are excluded from node properties.
    """
    repo_full_name: str
    sha: str
    short_sha: str = ""
    message: str = ""
    # Git-level author
    author_name: Optional[str] = None
    author_email: Optional[str] = None
    author_date: Optional[str] = None
    # Git-level committer
    committer_name: Optional[str] = None
    committer_email: Optional[str] = None
    committer_date: Optional[str] = None
    # GitHub-resolved logins
    author_login: Optional[str] = None
    committer_login: Optional[str] = None
    # Verification
    verified: bool = False
    verification_reason: Optional[str] = None
    # Parent commits
    parent_shas: List[str] = field(default_factory=list)
    is_merge_commit: bool = False
    # File diffs (full response only — stored as :MODIFIES edges, not node props)
    added_files: List[str] = field(default_factory=list)
    removed_files: List[str] = field(default_factory=list)
    modified_files: List[str] = field(default_factory=list)
    renamed_files: List[str] = field(default_factory=list)
    total_additions: int = 0
    total_deletions: int = 0
    total_changed_files: int = 0
    # URL
    html_url: Optional[str] = None
    api_node_id: Optional[str] = None

    @property
    def node_id(self) -> str:
        return f"github:commit:{self.repo_full_name}:{self.sha}"

    def to_graph_node(self) -> GraphNode:
        props = {k: v for k, v in asdict(self).items() if v is not None}
        props.pop("added_files", None)
        props.pop("removed_files", None)
        props.pop("modified_files", None)
        props.pop("renamed_files", None)
        return GraphNode(
            label=NodeLabel.COMMIT,
            node_id=self.node_id,
            properties=props,
        )

    @classmethod
    def from_api(cls, data: Dict[str, Any], repo_full_name: str) -> "CommitNode":
        commit = data.get("commit") or {}
        git_author = commit.get("author") or {}
        git_committer = commit.get("committer") or {}
        verification = commit.get("verification") or {}
        gh_author = data.get("author") or {}
        gh_committer = data.get("committer") or {}
        parents = [p.get("sha", "") for p in (data.get("parents") or []) if p.get("sha")]
        files = data.get("files") or []
        stats = data.get("stats") or {}
        sha = data.get("sha", "")
        return cls(
            repo_full_name=repo_full_name,
            sha=sha,
            short_sha=sha[:7] if sha else "",
            message=commit.get("message", ""),
            author_name=git_author.get("name"),
            author_email=git_author.get("email"),
            author_date=git_author.get("date"),
            committer_name=git_committer.get("name"),
            committer_email=git_committer.get("email"),
            committer_date=git_committer.get("date"),
            author_login=gh_author.get("login"),
            committer_login=gh_committer.get("login"),
            verified=bool(verification.get("verified", False)),
            verification_reason=verification.get("reason"),
            parent_shas=parents,
            is_merge_commit=len(parents) > 1,
            added_files=[f["filename"] for f in files if f.get("status") == "added"],
            removed_files=[f["filename"] for f in files if f.get("status") == "removed"],
            modified_files=[f["filename"] for f in files if f.get("status") == "modified"],
            renamed_files=[f["filename"] for f in files if f.get("status") == "renamed"],
            total_additions=stats.get("additions", 0) or 0,
            total_deletions=stats.get("deletions", 0) or 0,
            total_changed_files=len(files),
            html_url=data.get("html_url"),
            api_node_id=data.get("node_id"),
        )


@dataclass
class TeamNode:
    """
    GitHub organization team node.
    Source: GET /orgs/{org}/teams
    Drives RBAC edges: User -[:MEMBER_OF]-> Team -[:HAS_ACCESS_TO]-> Repository.
    Only accessible when token is authenticated as an org member.
    """
    org_login: str
    slug: str
    name: str
    github_id: Optional[int] = None
    description: Optional[str] = None
    privacy: str = "secret"
    permission: str = "pull"
    notification_setting: Optional[str] = None
    html_url: Optional[str] = None
    members_url: Optional[str] = None
    repositories_url: Optional[str] = None
    members_count: Optional[int] = None
    repos_count: Optional[int] = None
    parent_team_slug: Optional[str] = None
    parent_team_name: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    @property
    def node_id(self) -> str:
        return f"github:team:{self.org_login}:{self.slug}"

    def to_graph_node(self) -> GraphNode:
        return GraphNode(
            label=NodeLabel.TEAM,
            node_id=self.node_id,
            properties={k: v for k, v in asdict(self).items() if v is not None},
        )

    @classmethod
    def from_api(cls, data: Dict[str, Any], org_login: str) -> "TeamNode":
        parent = data.get("parent") or {}
        return cls(
            org_login=org_login,
            slug=data.get("slug", ""),
            name=data.get("name", ""),
            github_id=data.get("id"),
            description=data.get("description"),
            privacy=data.get("privacy", "secret"),
            permission=data.get("permission", "pull"),
            notification_setting=data.get("notification_setting"),
            html_url=data.get("html_url"),
            members_url=data.get("members_url"),
            repositories_url=data.get("repositories_url"),
            members_count=data.get("members_count"),
            repos_count=data.get("repos_count"),
            parent_team_slug=parent.get("slug"),
            parent_team_name=parent.get("name"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )


@dataclass
class LabelNode:
    """
    GitHub label node. Tags Issues and PRs semantically.
    Source: embedded in issue/PR responses as labels[].
    Stored as nodes so label-based graph queries can traverse edges.
    """
    repo_full_name: str
    name: str
    color: Optional[str] = None
    description: Optional[str] = None
    is_default: bool = False

    @property
    def node_id(self) -> str:
        return f"github:label:{self.repo_full_name}:{self.name}"

    def to_graph_node(self) -> GraphNode:
        return GraphNode(
            label=NodeLabel.LABEL,
            node_id=self.node_id,
            properties={k: v for k, v in asdict(self).items() if v is not None},
        )

    @classmethod
    def from_api(cls, data: Dict[str, Any], repo_full_name: str) -> "LabelNode":
        return cls(
            repo_full_name=repo_full_name,
            name=data.get("name", ""),
            color=data.get("color"),
            description=data.get("description"),
            is_default=bool(data.get("default", False)),
        )


# ---------------------------------------------------------------------------
# 5. Graph Bundle
# ---------------------------------------------------------------------------

@dataclass
class GitHubGraphBundle:
    """
    Complete set of nodes and relationships extracted from one repository pass.

    Populated by: backend/graph/github_extractor.py
    Consumed by:  backend/graph/neo4j_client.py
    """
    repository: RepositoryNode
    users: List[UserNode] = field(default_factory=list)
    files: List[FileNode] = field(default_factory=list)
    issues: List[IssueNode] = field(default_factory=list)
    pull_requests: List[PullRequestNode] = field(default_factory=list)
    commits: List[CommitNode] = field(default_factory=list)
    teams: List[TeamNode] = field(default_factory=list)
    labels: List[LabelNode] = field(default_factory=list)
    relationships: List[GraphRelationship] = field(default_factory=list)

    def all_nodes(self) -> List[GraphNode]:
        """Flatten all typed nodes into a list of generic GraphNode primitives."""
        nodes: List[GraphNode] = [self.repository.to_graph_node()]
        nodes.extend(u.to_graph_node() for u in self.users)
        nodes.extend(f.to_graph_node() for f in self.files)
        nodes.extend(i.to_graph_node() for i in self.issues)
        nodes.extend(pr.to_graph_node() for pr in self.pull_requests)
        nodes.extend(c.to_graph_node() for c in self.commits)
        nodes.extend(t.to_graph_node() for t in self.teams)
        nodes.extend(lbl.to_graph_node() for lbl in self.labels)
        return nodes

    def summary(self) -> Dict[str, int]:
        """Entity count breakdown for logging and debugging."""
        return {
            "repositories": 1,
            "users": len(self.users),
            "files": len(self.files),
            "issues": len(self.issues),
            "pull_requests": len(self.pull_requests),
            "commits": len(self.commits),
            "teams": len(self.teams),
            "labels": len(self.labels),
            "relationships": len(self.relationships),
        }
