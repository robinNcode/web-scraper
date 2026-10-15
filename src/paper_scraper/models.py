from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Page:
    """Clean, extracted content of a web page."""

    url: str
    title: str
    text: str


@dataclass(frozen=True, slots=True)
class Paper:
    """A generated paper, ready to be persisted."""

    source: Page
    body_markdown: str
