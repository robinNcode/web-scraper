from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol
from urllib.parse import unquote, urlsplit

from .models import Paper


class PaperWriter(Protocol):
    def write(self, paper: Paper) -> Path: ...


def _slugify(value: str, max_len: int = 60) -> str:
    decoded = unquote(value)
    parsed = urlsplit(decoded)
    if parsed.scheme and parsed.netloc:
        candidate = parsed.path or parsed.netloc
    else:
        candidate = decoded

    candidate = candidate.replace("\\", "/").strip("/.")
    normalized = unicodedata.normalize("NFKC", candidate)
    slug = re.sub(r"[^\w\s-]", "-", normalized, flags=re.UNICODE)
    slug = re.sub(r"[\s_-]+", "-", slug, flags=re.UNICODE).strip("-")
    slug = slug.lower() if slug.isascii() else slug
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
            f"*Note:* AI-generated critique. Verify every cited reference independently; "
            f"models can misremember or invent sources.\n\n"
            f"{paper.body_markdown}\n"
        )
        path.write_text(document, encoding="utf-8")
        return path
