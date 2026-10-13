from __future__ import annotations

import urllib.robotparser
from typing import Protocol
from urllib.parse import urlparse

import httpx


class FetchError(RuntimeError):
    """Raised when a page cannot (or must not) be fetched."""


class PageFetcher(Protocol):
    def fetch(self, url: str) -> str:
        """Return raw HTML for the URL."""
        ...


class HttpxFetcher:
    """HTTP fetcher that honours robots.txt and enforces basic safety limits.

    NOTE: if you ever expose this behind a public endpoint, add SSRF protection
    (block private/link-local IP ranges, re-validate after redirects).
    """

    def __init__(
        self,
        user_agent: str = "paper-scraper/0.1 (+contact: you@example.com)",
        timeout: float = 15.0,
        max_bytes: int = 5_000_000,
        respect_robots: bool = True,
        client: httpx.Client | None = None,
    ) -> None:
        self._ua = user_agent
        self._max_bytes = max_bytes
        self._respect_robots = respect_robots
        self._client = client or httpx.Client(
            headers={"User-Agent": user_agent},
            timeout=timeout,
            follow_redirects=True,
        )

    def fetch(self, url: str) -> str:
        parts = urlparse(url)
        if parts.scheme not in {"http", "https"} or not parts.netloc:
            raise FetchError(f"Unsupported or invalid URL: {url!r}")
        if self._respect_robots and not self._allowed_by_robots(url, parts):
            raise FetchError(f"Blocked by robots.txt: {url}")

        try:
            resp = self._client.get(url)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise FetchError(f"Request failed for {url}: {exc}") from exc

        content_type = resp.headers.get("content-type", "")
        if "html" not in content_type.lower():
            raise FetchError(f"Not an HTML page (content-type={content_type!r})")
        if len(resp.content) > self._max_bytes:
            raise FetchError(f"Response too large ({len(resp.content)} bytes)")
        return resp.text

    def _allowed_by_robots(self, url: str, parts) -> bool:
        robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
        parser = urllib.robotparser.RobotFileParser()
        try:
            resp = self._client.get(robots_url)
        except httpx.HTTPError:
            return True  # robots.txt unreachable: conventional behaviour is allow
        if resp.status_code != 200:
            return True
        parser.parse(resp.text.splitlines())
        return parser.can_fetch(self._ua, url)
