from __future__ import annotations

from typing import Any, Iterable
from urllib.parse import quote

import requests

from pr_retriever.http import get_json
from pr_retriever.models import CommentOut, Credentials, ParsedUrl, ThreadOut
from pr_retriever.utils import format_location, is_me


def _oauth_token(base_url: str, username: str, password: str, session: requests.Session) -> str:
    response = session.post(
        f"{base_url}/oauth/token",
        data={
            "grant_type": "password",
            "username": username,
            "password": password,
        },
        timeout=30,
    )
    if response.status_code >= 400:
        body = response.text[:1000]
        raise SystemExit(f"GitLab login failed (HTTP {response.status_code})\n{body}")
    data = response.json()
    token = data.get("access_token")
    if not token:
        raise SystemExit(f"GitLab login did not return an access_token.\n{response.text[:1000]}")
    return str(token)


def _build_headers(
    parsed: ParsedUrl,
    credentials: Credentials,
    session: requests.Session,
) -> dict[str, str]:
    if credentials.username and credentials.password:
        oauth_token = _oauth_token(parsed.base_url, credentials.username, credentials.password, session)
        return {"Authorization": f"Bearer {oauth_token}"}
    if credentials.token:
        return {"PRIVATE-TOKEN": credentials.token}
    raise SystemExit(
        "Missing GitLab credentials. Pass --token / GITLAB_TOKEN, or --username and --password."
    )


def fetch_discussions(parsed: ParsedUrl, credentials: Credentials) -> list[dict[str, Any]]:
    assert parsed.project_path and parsed.mr_iid
    session = requests.Session()
    headers = _build_headers(parsed, credentials, session)
    project = quote(parsed.project_path, safe="")
    api_url = f"{parsed.base_url}/api/v4/projects/{project}/merge_requests/{parsed.mr_iid}/discussions"

    page = 1
    discussions: list[dict[str, Any]] = []
    while True:
        data, headers_out = get_json(
            session, api_url, provider="gitlab", headers=headers, params={"per_page": 100, "page": page}
        )
        discussions.extend(data if isinstance(data, list) else [])
        next_page = headers_out.get("X-Next-Page") or headers_out.get("x-next-page")
        if not next_page:
            break
        page = int(next_page)
    return discussions


def _discussion_location(notes: Iterable[dict[str, Any]]) -> tuple[str, str, str, str, str]:
    position = None
    for note in notes:
        if note.get("position"):
            position = note["position"]
            break

    if not position:
        return "overview", "", "", "", ""

    file_path = position.get("new_path") or position.get("old_path") or ""
    side = "new" if position.get("new_line") is not None else "old" if position.get("old_line") is not None else ""

    line_range = position.get("line_range") or {}
    start_obj = line_range.get("start") or {}
    end_obj = line_range.get("end") or {}

    start = (
        start_obj.get("new_line")
        or start_obj.get("old_line")
        or position.get("new_line")
        or position.get("old_line")
        or ""
    )
    end = (
        end_obj.get("new_line")
        or end_obj.get("old_line")
        or position.get("new_line")
        or position.get("old_line")
        or ""
    )
    start_s = str(start) if start != "" else ""
    end_s = str(end) if end != "" else ""
    location = format_location(file_path, start_s, end_s)
    return location, file_path, start_s, end_s, side


def convert_discussions(
    discussions: list[dict[str, Any]],
    aliases: set[str],
    *,
    include_non_resolvable: bool = False,
) -> list[ThreadOut]:
    out: list[ThreadOut] = []

    for discussion in discussions:
        raw_notes = [n for n in discussion.get("notes", []) if not n.get("system") and str(n.get("body") or "").strip()]
        if not raw_notes:
            continue

        resolvable_notes = [n for n in raw_notes if n.get("resolvable")]
        if resolvable_notes:
            if all(bool(n.get("resolved")) for n in resolvable_notes):
                continue
            status = "active"
        else:
            if not include_non_resolvable:
                continue
            status = "non_resolvable"

        location, file_path, start, end, side = _discussion_location(raw_notes)
        item = ThreadOut(
            thread_id=str(discussion.get("id", "")),
            status=status,
            location=location,
            file_path=file_path,
            line_start=start,
            line_end=end,
            side=side,
        )

        for note in raw_notes:
            author = note.get("author") or {}
            role = "me" if is_me(author, aliases) else "reviewer"
            item.comments.append(
                CommentOut(
                    role=role,
                    body=str(note.get("body") or "").strip(),
                    author=str(author.get("name") or author.get("username") or author.get("id") or ""),
                    username=str(author.get("username") or author.get("email") or author.get("id") or ""),
                    created_at=str(note.get("created_at") or ""),
                    comment_id=str(note.get("id") or ""),
                )
            )

        out.append(item)
    return out
