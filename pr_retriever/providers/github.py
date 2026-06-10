from __future__ import annotations

from typing import Any

import requests

from pr_retriever.http import post_json
from pr_retriever.models import CommentOut, Credentials, ParsedUrl, ThreadOut
from pr_retriever.utils import format_location, is_me

_REVIEW_THREADS_QUERY = """
query($owner: String!, $repo: String!, $pr: Int!, $threadsAfter: String) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $pr) {
      reviewThreads(first: 100, after: $threadsAfter) {
        pageInfo {
          hasNextPage
          endCursor
        }
        nodes {
          id
          isResolved
          path
          line
          startLine
          diffSide
          comments(first: 100) {
            nodes {
              id
              body
              createdAt
              author {
                login
                name
              }
            }
          }
        }
      }
    }
  }
}
"""


def _require_token(credentials: Credentials) -> str:
    if credentials.token:
        return credentials.token
    raise SystemExit(
        "Missing GitHub credentials. Pass --token or set GITHUB_TOKEN "
        "(Personal Access Token with repo or pull request read access)."
    )


def _graphql_url(parsed: ParsedUrl) -> str:
    assert parsed.api_base_url
    return f"{parsed.api_base_url.rstrip('/')}/graphql"


def _build_session(token: str) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
    )
    return session


def _run_graphql(
    session: requests.Session,
    parsed: ParsedUrl,
    variables: dict[str, Any],
) -> dict[str, Any]:
    data = post_json(
        session,
        _graphql_url(parsed),
        provider="github",
        json={"query": _REVIEW_THREADS_QUERY, "variables": variables},
    )
    if data.get("errors"):
        messages = "; ".join(str(err.get("message", err)) for err in data["errors"])
        raise SystemExit(f"GitHub GraphQL error: {messages}")
    return data["data"]


def fetch_review_threads(parsed: ParsedUrl, credentials: Credentials) -> list[dict[str, Any]]:
    assert parsed.owner and parsed.repo and parsed.pr_number
    session = _build_session(_require_token(credentials))

    threads: list[dict[str, Any]] = []
    threads_after: str | None = None

    while True:
        variables: dict[str, Any] = {
            "owner": parsed.owner,
            "repo": parsed.repo,
            "pr": int(parsed.pr_number),
            "threadsAfter": threads_after,
        }
        data = _run_graphql(session, parsed, variables)
        pull_request = (data.get("repository") or {}).get("pullRequest")
        if not pull_request:
            raise SystemExit(
                f"GitHub pull request not found: {parsed.owner}/{parsed.repo}#{parsed.pr_number}"
            )

        review_threads = pull_request.get("reviewThreads") or {}
        threads.extend(review_threads.get("nodes") or [])

        page_info = review_threads.get("pageInfo") or {}
        if not page_info.get("hasNextPage"):
            break
        threads_after = page_info.get("endCursor")

    return threads


def _thread_location(thread: dict[str, Any]) -> tuple[str, str, str, str, str]:
    file_path = str(thread.get("path") or "")
    line = thread.get("line")
    start_line = thread.get("startLine")

    start = str(start_line if start_line is not None else line if line is not None else "")
    end = str(line if line is not None else start)
    diff_side = str(thread.get("diffSide") or "").upper()
    side = "new" if diff_side == "RIGHT" else "old" if diff_side == "LEFT" else ""

    location = format_location(file_path, start, end)
    return location, file_path, start, end, side


def convert_review_threads(
    threads: list[dict[str, Any]],
    aliases: set[str],
    *,
    include_resolved: bool = False,
) -> list[ThreadOut]:
    out: list[ThreadOut] = []

    for thread in threads:
        if thread.get("isResolved") and not include_resolved:
            continue

        comments = (thread.get("comments") or {}).get("nodes") or []
        raw_comments = [c for c in comments if str(c.get("body") or "").strip()]
        if not raw_comments:
            continue

        location, file_path, start, end, side = _thread_location(thread)
        item = ThreadOut(
            thread_id=str(thread.get("id", "")),
            status="resolved" if thread.get("isResolved") else "active",
            location=location,
            file_path=file_path,
            line_start=start,
            line_end=end,
            side=side,
        )

        for comment in raw_comments:
            author = comment.get("author") or {}
            role = "me" if is_me(author, aliases) else "reviewer"
            item.comments.append(
                CommentOut(
                    role=role,
                    body=str(comment.get("body") or "").strip(),
                    author=str(author.get("name") or author.get("login") or ""),
                    username=str(author.get("login") or ""),
                    created_at=str(comment.get("createdAt") or ""),
                    comment_id=str(comment.get("id") or ""),
                )
            )

        out.append(item)
    return out
