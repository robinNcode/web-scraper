from __future__ import annotations

from pathlib import Path

from .extractor import ContentExtractor
from .fetcher import PageFetcher
from .summarizer import Summarizer
from .writer import PaperWriter


class PaperPipeline:
    """Orchestrates fetch -> extract -> summarize -> write. Depends only on abstractions."""

    def __init__(
        self,
        fetcher: PageFetcher,
        extractor: ContentExtractor,
        summarizer: Summarizer,
        writer: PaperWriter,
    ) -> None:
        self._fetcher = fetcher
        self._extractor = extractor
        self._summarizer = summarizer
        self._writer = writer

    def run(self, url: str) -> Path:
        html = self._fetcher.fetch(url)
        page = self._extractor.extract(html, url)
        paper = self._summarizer.summarize(page)
        return self._writer.write(paper)
