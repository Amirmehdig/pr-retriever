from __future__ import annotations

from typing import Any

import requests


def http_error_hint(status_code: int, provider: str) -> str:
    if status_code == 401 and provider == "azure":
        return (
            "\n\nAzure auth failed. Provide one of:\n"
            "  --token / AZURE_DEVOPS_PAT (Personal Access Token)\n"
            "  --username and --password for NTLM (e.g. DOMAIN\\user)\n"
            "  Or run on a domain-joined Windows PC with requests-negotiate-sspi installed."
        )
    if status_code == 401 and provider == "gitlab":
        return (
            "\n\nGitLab auth failed. Provide --token / GITLAB_TOKEN, "
            "or --username and --password."
        )
    if status_code == 401 and provider == "github":
        return (
            "\n\nGitHub auth failed. Provide --token / GITHUB_TOKEN "
            "(Personal Access Token with repo or pull request read access)."
        )
    return ""


def get_json(session: requests.Session, url: str, provider: str = "", **kwargs: Any) -> tuple[Any, requests.structures.CaseInsensitiveDict]:
    response = session.get(url, timeout=30, **kwargs)
    if response.status_code >= 400:
        body = response.text[:1000]
        raise SystemExit(
            f"HTTP {response.status_code} for {url}\n{body}{http_error_hint(response.status_code, provider)}"
        )
    return response.json(), response.headers


def post_json(
    session: requests.Session,
    url: str,
    provider: str = "",
    **kwargs: Any,
) -> dict[str, Any]:
    response = session.post(url, timeout=30, **kwargs)
    if response.status_code >= 400:
        body = response.text[:1000]
        raise SystemExit(
            f"HTTP {response.status_code} for {url}\n{body}{http_error_hint(response.status_code, provider)}"
        )
    data = response.json()
    if not isinstance(data, dict):
        raise SystemExit(f"Expected JSON object from {url}, got {type(data).__name__}")
    return data
