from __future__ import annotations

import json
import os
from pathlib import Path

from pr_retriever.models import Credentials

_PROVIDER_KEYS = ("github", "gitlab", "azure")
_CREDENTIAL_FIELDS = ("token", "username", "password")


def find_config_path(explicit: str | None = None) -> Path | None:
    if explicit:
        path = Path(explicit).expanduser()
        if not path.is_file():
            raise SystemExit(f"Config file not found: {path}")
        return path

    env_path = os.getenv("PR_RETRIEVER_CONFIG")
    if env_path:
        path = Path(env_path).expanduser()
        if path.is_file():
            return path
        raise SystemExit(f"PR_RETRIEVER_CONFIG points to a missing file: {path}")

    for candidate in (
        Path.cwd() / "pr-retriever.json",
        Path.cwd() / ".pr-retriever.json",
        Path.home() / ".config" / "pr-retriever" / "config.json",
        Path.home() / ".pr-retriever.json",
    ):
        if candidate.is_file():
            return candidate
    return None


def _parse_provider_section(section: object, provider: str) -> Credentials:
    if section is None:
        return Credentials()
    if not isinstance(section, dict):
        raise SystemExit(f'Config section "{provider}" must be a JSON object.')

    unknown = sorted(set(section) - set(_CREDENTIAL_FIELDS))
    if unknown:
        raise SystemExit(
            f'Config section "{provider}" has unknown keys: {", ".join(unknown)}. '
            f'Allowed: {", ".join(_CREDENTIAL_FIELDS)}.'
        )

    return Credentials(
        token=_non_empty_str(section.get("token")),
        username=_non_empty_str(section.get("username")),
        password=_non_empty_str(section.get("password")),
    )


def _non_empty_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def load_config(path: Path | None) -> dict[str, Credentials]:
    if path is None:
        return {provider: Credentials() for provider in _PROVIDER_KEYS}

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in config file {path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise SystemExit(f"Config file {path} must contain a JSON object at the top level.")

    return {provider: _parse_provider_section(raw.get(provider), provider) for provider in _PROVIDER_KEYS}


def merge_credentials(
    provider: str,
    config: dict[str, Credentials],
    *,
    cli_token: str | None,
    cli_username: str | None,
    cli_password: str | None,
    env_token: str | None,
    env_username: str | None,
    env_password: str | None,
) -> Credentials:
    """Resolve credentials with precedence: CLI > environment > config file."""
    file_creds = config.get(provider, Credentials())
    return Credentials(
        token=cli_token or env_token or file_creds.token,
        username=cli_username or env_username or file_creds.username,
        password=cli_password or env_password or file_creds.password,
    )
