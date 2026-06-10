from __future__ import annotations

import base64
from typing import Any
from urllib.parse import quote

import requests

from pr_retriever.http import get_json, http_error_hint
from pr_retriever.models import CommentOut, Credentials, ParsedUrl, ThreadOut
from pr_retriever.utils import format_location, is_me, norm

AZURE_API_VERSIONS = (
    "7.1",
    "6.1",
    "6.1-preview",
    "6.0",
    "6.0-preview",
    "5.1",
    "5.1-preview",
    "4.1",
    "4.1-preview",
)


def _auth_header(token: str) -> dict[str, str]:
    raw = f":{token}".encode("utf-8")
    return {"Authorization": "Basic " + base64.b64encode(raw).decode("ascii")}


def _build_session(credentials: Credentials) -> requests.Session:
    session = requests.Session()
    token = credentials.token
    username = credentials.username
    password = credentials.password

    if token:
        session.headers.update(_auth_header(token))
        return session
    if username or password:
        if not (username and password):
            raise SystemExit("Azure NTLM auth requires both --username and --password.")
        try:
            from requests_ntlm import HttpNtlmAuth
        except ImportError as exc:
            raise SystemExit(
                "NTLM auth requires requests-ntlm. Install with: pip install requests-ntlm"
            ) from exc
        session.auth = HttpNtlmAuth(username, password)
        return session
    try:
        from requests_negotiate_sspi import HttpNegotiateAuth
    except ImportError as exc:
        raise SystemExit(
            "Missing Azure credentials. Pass --token / AZURE_DEVOPS_PAT, or "
            "--username and --password for NTLM, or install requests-negotiate-sspi "
            "to use your Windows login automatically."
        ) from exc
    session.auth = HttpNegotiateAuth()
    return session


def _api_version_issue(response: requests.Response) -> str | None:
    if response.status_code != 400:
        return None
    body = response.text.casefold()
    if "vssversionoutofrangeexception" in body or "out of range for this server" in body:
        return "out_of_range"
    if "vssinvalidpreviewversionexception" in body or "-preview flag must be supplied" in body:
        return "needs_preview"
    return None


def fetch_threads(parsed: ParsedUrl, credentials: Credentials) -> list[dict[str, Any]]:
    assert parsed.project and parsed.repo and parsed.pr_id
    session = _build_session(credentials)

    api_url = (
        f"{parsed.base_url}/{quote(parsed.project, safe='')}/_apis/git/repositories/"
        f"{quote(parsed.repo, safe='')}/pullRequests/{quote(parsed.pr_id, safe='')}/threads"
    )

    api_version: str | None = None
    for candidate in AZURE_API_VERSIONS:
        probe = session.get(api_url, params={"api-version": candidate}, timeout=30)
        version_issue = _api_version_issue(probe)
        if version_issue:
            continue
        if probe.status_code >= 400:
            body = probe.text[:1000]
            raise SystemExit(
                f"HTTP {probe.status_code} for {api_url}\n{body}{http_error_hint(probe.status_code, 'azure')}"
            )
        api_version = candidate
        first_data = probe.json()
        first_headers = probe.headers
        break

    if not api_version:
        raise SystemExit(
            f"Could not find a supported Azure DevOps REST API version. Tried: {', '.join(AZURE_API_VERSIONS)}"
        )

    params: dict[str, Any] = {"api-version": api_version}
    all_threads: list[dict[str, Any]] = []
    all_threads.extend(first_data.get("value", first_data if isinstance(first_data, list) else []))
    continuation = first_headers.get("x-ms-continuationtoken") or first_headers.get("X-MS-ContinuationToken")

    while continuation:
        params["continuationToken"] = continuation
        data, headers_out = get_json(session, api_url, provider="azure", params=params)
        all_threads.extend(data.get("value", data if isinstance(data, list) else []))
        continuation = headers_out.get("x-ms-continuationtoken") or headers_out.get("X-MS-ContinuationToken")

    return all_threads


def _pos_line(pos: dict[str, Any] | None) -> str:
    if not pos:
        return ""
    line = pos.get("line")
    return "" if line is None else str(line)


def _thread_location(thread: dict[str, Any]) -> tuple[str, str, str, str, str]:
    ctx = thread.get("threadContext") or {}
    pr_ctx = thread.get("pullRequestThreadContext") or {}
    tracking = pr_ctx.get("trackingCriteria") or {}

    file_path = ctx.get("filePath") or tracking.get("origFilePath") or ""

    right_start = ctx.get("rightFileStart") or tracking.get("origRightFileStart")
    right_end = ctx.get("rightFileEnd") or tracking.get("origRightFileEnd")
    left_start = ctx.get("leftFileStart") or tracking.get("origLeftFileStart")
    left_end = ctx.get("leftFileEnd") or tracking.get("origLeftFileEnd")

    side = "new" if right_start or right_end else "old" if left_start or left_end else ""
    start = _pos_line(right_start or left_start)
    end = _pos_line(right_end or left_end)
    location = format_location(file_path, start, end)
    return location, file_path, start, end, side


def convert_threads(
    threads: list[dict[str, Any]],
    aliases: set[str],
    *,
    include_pending: bool = False,
) -> list[ThreadOut]:
    allowed_statuses = {"active"}
    if include_pending:
        allowed_statuses.add("pending")

    out: list[ThreadOut] = []
    for thread in threads:
        if thread.get("isDeleted"):
            continue
        status = norm(thread.get("status"))
        if status not in allowed_statuses:
            continue

        location, file_path, start, end, side = _thread_location(thread)
        item = ThreadOut(
            thread_id=str(thread.get("id", "")),
            status=thread.get("status", "active"),
            location=location,
            file_path=file_path,
            line_start=start,
            line_end=end,
            side=side,
        )

        for comment in thread.get("comments", []):
            if comment.get("isDeleted") or norm(comment.get("commentType")) == "system":
                continue
            body = str(comment.get("content") or "").strip()
            if not body:
                continue
            author = comment.get("author") or {}
            role = "me" if is_me(author, aliases) else "reviewer"
            item.comments.append(
                CommentOut(
                    role=role,
                    body=body,
                    author=str(author.get("displayName") or author.get("uniqueName") or author.get("id") or ""),
                    username=str(author.get("uniqueName") or author.get("directoryAlias") or author.get("id") or ""),
                    created_at=str(comment.get("publishedDate") or ""),
                    comment_id=str(comment.get("id") or ""),
                )
            )

        if item.comments:
            out.append(item)
    return out
