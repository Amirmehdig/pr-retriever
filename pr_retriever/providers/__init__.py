from __future__ import annotations

from typing import Callable

from pr_retriever.models import Credentials, ParsedUrl, ThreadOut
from pr_retriever.providers import azure, github, gitlab

FetchFn = Callable[[ParsedUrl, Credentials], list]
ConvertFn = Callable[..., list[ThreadOut]]

PROVIDERS: dict[str, tuple[FetchFn, ConvertFn]] = {
    "azure": (azure.fetch_threads, azure.convert_threads),
    "gitlab": (gitlab.fetch_discussions, gitlab.convert_discussions),
    "github": (github.fetch_review_threads, github.convert_review_threads),
}
