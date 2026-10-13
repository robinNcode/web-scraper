from __future__ import annotations

from typing import Protocol

import trafilatura

from .fetcher import FetchError
from .models import Page


class ContentExtractor(Protocol):
    def extract(self, html: str, url: str) -> Page: ...


class TrafilaturaExtractor:
    """Boilerplate-free main-content extraction (nav, ads, footers removed)."""

    def extract(self, html: str, url: str) -> Page:
        text = trafilatura.extract(
            html,
            url=url,
            include_comments=False,
            include_tables=True,
            favor_recall=True,
        )
        if not text or not text.strip():
            raise FetchError(
                "No extractable content. The page may be JS-rendered "
                "(needs a headless browser such as Playwright)."
            )
        meta = trafilatura.extract_metadata(html, default_url=url)
        title = (meta.title if meta and meta.title else url).strip()
        return Page(url=url, title=title, text=text)
