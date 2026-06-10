from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ParsedUrl:
    provider: str
    base_url: str
    # Azure DevOps
    project: str | None = None
    repo: str | None = None
    pr_id: str | None = None
    # GitLab
    project_path: str | None = None
    mr_iid: str | None = None
    # GitHub
    owner: str | None = None
    pr_number: str | None = None
    api_base_url: str | None = None


@dataclass
class Credentials:
    token: str | None = None
    username: str | None = None
    password: str | None = None


@dataclass
class CommentOut:
    role: str
    body: str
    author: str = ""
    username: str = ""
    created_at: str = ""
    comment_id: str = ""


@dataclass
class ThreadOut:
    thread_id: str
    status: str
    location: str
    file_path: str = ""
    line_start: str = ""
    line_end: str = ""
    side: str = ""
    comments: list[CommentOut] = field(default_factory=list)
