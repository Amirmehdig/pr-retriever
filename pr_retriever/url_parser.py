from __future__ import annotations

import re
from urllib.parse import quote, unquote, urlparse

from pr_retriever.models import ParsedUrl

_GITHUB_HOSTS = {"github.com", "www.github.com"}
_PULL_PATH_RE = re.compile(r"^/([^/]+)/([^/]+)/pull/(\d+)")


def detect_and_parse_url(raw_url: str, forced_provider: str = "auto") -> ParsedUrl:
    parsed = urlparse(raw_url)
    host = parsed.netloc.casefold()
    path = unquote(parsed.path)

    provider = forced_provider
    if provider == "auto":
        if "/-/merge_requests/" in path:
            provider = "gitlab"
        elif "/_git/" in path and "/pullrequest/" in path.casefold():
            provider = "azure"
        elif host in _GITHUB_HOSTS or _PULL_PATH_RE.match(path.rstrip("/")):
            provider = "github"
        else:
            raise SystemExit(
                "Could not detect provider from URL. Use --provider azure, gitlab, or github."
            )

    if provider == "gitlab":
        return _parse_gitlab(parsed, path)
    if provider == "azure":
        return _parse_azure(parsed, host, path)
    if provider == "github":
        return _parse_github(parsed, host, path)

    raise SystemExit(f"Unsupported provider: {provider}")


def _parse_gitlab(parsed, path: str) -> ParsedUrl:
    marker = "/-/merge_requests/"
    if marker not in path:
        raise SystemExit("GitLab URL must look like: https://host/group/project/-/merge_requests/123")
    project_part, rest = path.strip("/").split("/-/merge_requests/", 1)
    mr_iid = rest.split("/", 1)[0]
    if not mr_iid.isdigit():
        raise SystemExit("Could not find numeric GitLab merge request IID in URL.")
    return ParsedUrl(
        provider="gitlab",
        base_url=f"{parsed.scheme}://{parsed.netloc}",
        project_path=project_part,
        mr_iid=mr_iid,
    )


def _parse_azure(parsed, host: str, path: str) -> ParsedUrl:
    parts = [p for p in path.strip("/").split("/") if p]
    lower_parts = [p.casefold() for p in parts]

    try:
        git_idx = lower_parts.index("_git")
        pr_idx = lower_parts.index("pullrequest")
    except ValueError:
        raise SystemExit(
            "Azure URL must look like: https://dev.azure.com/org/project/_git/repo/pullrequest/123"
        )

    if pr_idx + 1 >= len(parts):
        raise SystemExit("Could not find Azure pull request ID in URL.")

    pr_id = parts[pr_idx + 1]
    repo = parts[git_idx + 1]

    if host.endswith("visualstudio.com"):
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        project = parts[0]
    elif host == "dev.azure.com":
        if len(parts) < 2:
            raise SystemExit("Could not find organization/project in dev.azure.com URL.")
        org = parts[0]
        project = parts[1]
        base_url = f"{parsed.scheme}://{parsed.netloc}/{quote(org, safe='')}"
    else:
        project = parts[git_idx - 1] if git_idx > 0 else None
        if not project:
            raise SystemExit("Could not infer Azure project from URL. Use a standard Azure DevOps PR URL.")
        prefix_parts = parts[: git_idx - 1]
        prefix = "/" + "/".join(quote(p, safe="") for p in prefix_parts) if prefix_parts else ""
        base_url = f"{parsed.scheme}://{parsed.netloc}{prefix}"

    return ParsedUrl(
        provider="azure",
        base_url=base_url,
        project=project,
        repo=repo,
        pr_id=pr_id,
    )


def _parse_github(parsed, host: str, path: str) -> ParsedUrl:
    clean_path = path.rstrip("/")
    match = _PULL_PATH_RE.match(clean_path)
    if not match:
        raise SystemExit(
            "GitHub URL must look like: https://github.com/owner/repo/pull/123 "
            "(or https://your-ghe-host/owner/repo/pull/123)"
        )

    owner, repo, pr_number = match.group(1), match.group(2), match.group(3)
    web_base = f"{parsed.scheme}://{parsed.netloc}"

    if host in _GITHUB_HOSTS:
        api_base_url = "https://api.github.com"
    else:
        api_base_url = f"{web_base}/api"

    return ParsedUrl(
        provider="github",
        base_url=web_base,
        api_base_url=api_base_url,
        owner=owner,
        repo=repo,
        pr_number=pr_number,
    )
