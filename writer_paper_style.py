from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from .models import Paper


class PaperWriter(Protocol):
    def write(self, paper: Paper) -> Path: ...


def _slugify(value: str, max_len: int = 60) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:max_len] or "paper"


class MarkdownPaperWriter:
    def __init__(self, output_dir: Path) -> None:
        self._dir = output_dir

    def write(self, paper: Paper) -> Path:
        self._dir.mkdir(parents=True, exist_ok=True)
        now = datetime.now(timezone.utc)
        path = self._dir / f"{now:%Y%m%d}-{_slugify(paper.source.title)}.md"
        document = (
            f"# {paper.source.title}\n\n"
            f"*Source:* <{paper.source.url}>  \n"
            f"*Retrieved:* {now:%Y-%m-%d %H:%M} UTC  \n"
            f"*Note:* AI-generated summary of the page above; verify against the source.\n\n"
            f"{paper.body_markdown}\n\n"
            f"## References\n\n1. {paper.source.title}. <{paper.source.url}>\n"
        )
        path.write_text(document, encoding="utf-8")
        return path
