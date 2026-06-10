from __future__ import annotations

import argparse
import os

from pr_retriever.config import find_config_path, load_config, merge_credentials
from pr_retriever.models import Credentials
from pr_retriever.providers import PROVIDERS
from pr_retriever.url_parser import detect_and_parse_url
from pr_retriever.utils import norm
from pr_retriever.xml_writer import write_xml

_TOKEN_ENV = {
    "azure": "AZURE_DEVOPS_PAT",
    "gitlab": "GITLAB_TOKEN",
    "github": "GITHUB_TOKEN",
}

_USERNAME_ENV = {
    "azure": "AZURE_DEVOPS_USERNAME",
    "gitlab": "GITLAB_USERNAME",
}

_PASSWORD_ENV = {
    "azure": "AZURE_DEVOPS_PASSWORD",
    "gitlab": "GITLAB_PASSWORD",
}


def _resolve_credentials(
    provider: str,
    args: argparse.Namespace,
    config: dict[str, Credentials],
) -> Credentials:
    credentials = merge_credentials(
        provider,
        config,
        cli_token=args.token,
        cli_username=args.username,
        cli_password=args.password,
        env_token=os.getenv(_TOKEN_ENV[provider]),
        env_username=os.getenv(_USERNAME_ENV.get(provider, "")),
        env_password=os.getenv(_PASSWORD_ENV.get(provider, "")),
    )

    if provider == "github" and not credentials.token:
        raise SystemExit(
            "Missing GitHub credentials. Pass --token, set GITHUB_TOKEN, "
            "or add a github.token entry to your config file "
            "(see pr-retriever.config.example.json)."
        )
    if provider == "gitlab" and not credentials.token and not (
        credentials.username and credentials.password
    ):
        raise SystemExit(
            "Missing GitLab credentials. Pass --token / GITLAB_TOKEN, "
            "--username and --password, or add gitlab credentials to your config file."
        )

    return credentials


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export unresolved PR/MR review threads from Azure DevOps, GitLab, or GitHub to XML."
    )
    parser.add_argument("--url", required=True, help="Pull request / merge request URL")
    parser.add_argument(
        "--me",
        nargs="+",
        required=True,
        help="Your display name, username, email, or ID. You can pass multiple aliases.",
    )
    parser.add_argument(
        "--token",
        help="Access token. Defaults to AZURE_DEVOPS_PAT, GITLAB_TOKEN, or GITHUB_TOKEN by provider.",
    )
    parser.add_argument("--username", help="Username for NTLM (Azure) or OAuth password grant (GitLab).")
    parser.add_argument("--password", help="Password for NTLM (Azure) or OAuth password grant (GitLab).")
    parser.add_argument(
        "--config",
        help="Path to JSON config file with provider tokens. "
        "Default search: ./pr-retriever.json, ~/.config/pr-retriever/config.json, ~/.pr-retriever.json",
    )
    parser.add_argument("--provider", choices=["auto", "azure", "gitlab", "github"], default="auto")
    parser.add_argument("--out", default="pr_review_threads.xml", help="Output XML path")
    parser.add_argument(
        "--include-pending-azure",
        action="store_true",
        help="Also include Azure threads with status=pending",
    )
    parser.add_argument(
        "--include-non-resolvable-gitlab",
        action="store_true",
        help="Also include GitLab overview discussions that are not resolvable",
    )
    parser.add_argument(
        "--include-resolved-github",
        action="store_true",
        help="Also include GitHub review threads that are already resolved",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    config_path = find_config_path(args.config)
    config = load_config(config_path)
    parsed = detect_and_parse_url(args.url, args.provider)
    credentials = _resolve_credentials(parsed.provider, args, config)

    aliases = {norm(x) for x in args.me if norm(x)}
    if not aliases:
        raise SystemExit("At least one --me alias is required.")

    fetch_fn, convert_fn = PROVIDERS[parsed.provider]
    raw = fetch_fn(parsed, credentials)

    if parsed.provider == "azure":
        threads = convert_fn(raw, aliases, include_pending=args.include_pending_azure)
    elif parsed.provider == "gitlab":
        threads = convert_fn(raw, aliases, include_non_resolvable=args.include_non_resolvable_gitlab)
    else:
        threads = convert_fn(raw, aliases, include_resolved=args.include_resolved_github)

    write_xml(parsed.provider, args.url, threads, args.out)
    print(f"Wrote {len(threads)} open thread(s) to {args.out}")
    return 0
