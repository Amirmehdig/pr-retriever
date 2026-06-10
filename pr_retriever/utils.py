from __future__ import annotations

from typing import Any


def norm(value: Any) -> str:
    return str(value or "").strip().casefold()


def any_match(value: Any, aliases: set[str]) -> bool:
    v = norm(value)
    return bool(v and v in aliases)


def is_me(author: dict[str, Any], aliases: set[str]) -> bool:
    fields = [
        author.get("displayName"),      # Azure DevOps
        author.get("uniqueName"),       # Azure DevOps
        author.get("directoryAlias"),   # Azure DevOps
        author.get("id"),
        author.get("name"),             # GitLab / GitHub GraphQL
        author.get("username"),         # GitLab
        author.get("login"),            # GitHub
        author.get("email"),
    ]
    return any(any_match(v, aliases) for v in fields)


def format_location(
    file_path: str,
    start: str,
    end: str,
    *,
    overview_label: str = "overview",
) -> str:
    if file_path and start and end and start != end:
        return f"{file_path}:{start}-{end}"
    if file_path and start:
        return f"{file_path}:{start}"
    if file_path:
        return file_path
    return overview_label
