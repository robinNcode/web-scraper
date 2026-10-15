from __future__ import annotations

import json
import logging
import os
import stat
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Protocol

log = logging.getLogger(__name__)


class CredentialError(RuntimeError):
    """Raised when a credentials source is unreadable or malformed."""


class CredentialProvider(Protocol):
    def get(self, provider: str) -> str | None:
        """Return the API key for a provider name (e.g. 'groq'), or None."""
        ...


def default_keys_paths() -> list[Path]:
    """Search order: project-local file first, then the per-user config file."""
    return [
        Path.cwd() / "keys.json",
        Path.home() / ".config" / "paper-scraper" / "keys.json",
    ]


class JsonFileCredentialProvider:
    """Reads keys from a JSON object: {"groq": "gsk_...", "gemini": "..."}.

    - Loaded lazily and cached; the file is only touched if a key is requested.
    - Keys starting with "_" (e.g. "_comment") and blank values are ignored.
    - Key *values* are never logged or included in error messages.
    """

    def __init__(self, path: Path, required: bool = False) -> None:
        self._path = path.expanduser()
        self._required = required  # True for explicitly passed paths: typos should fail loudly
        self._keys: dict[str, str] | None = None

    def get(self, provider: str) -> str | None:
        if self._keys is None:
            self._keys = self._load()
        return self._keys.get(provider)

    def _load(self) -> dict[str, str]:
        if not self._path.is_file():
            if self._required:
                raise CredentialError(f"Keys file not found: {self._path}")
            return {}
        self._warn_if_accessible_by_others()
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CredentialError(f"Cannot read keys file {self._path}: {exc}") from exc
        if not isinstance(data, dict):
            raise CredentialError(f"{self._path}: top level must be a JSON object")

        keys: dict[str, str] = {}
        for name, value in data.items():
            if name.startswith("_"):
                continue
            if not isinstance(value, str):
                raise CredentialError(f"{self._path}: value for '{name}' must be a string")
            if value.strip():
                keys[name] = value.strip()
        return keys

    def _warn_if_accessible_by_others(self) -> None:
        if os.name != "posix":
            return
        mode = stat.S_IMODE(self._path.stat().st_mode)
        if mode & 0o077:
            log.warning(
                "%s is accessible by other users (mode %o). Run: chmod 600 %s",
                self._path, mode, self._path,
            )


class EnvCredentialProvider:
    """Fallback for CI/Docker: maps provider name -> environment variable name."""

    def __init__(self, env_names: Mapping[str, str]) -> None:
        self._env_names = dict(env_names)

    def get(self, provider: str) -> str | None:
        name = self._env_names.get(provider)
        return (os.getenv(name) or None) if name else None


class ChainedCredentialProvider:
    """Returns the first non-empty key from the providers, in order."""

    def __init__(self, providers: Iterable[CredentialProvider]) -> None:
        self._providers = list(providers)

    def get(self, provider: str) -> str | None:
        for source in self._providers:
            key = source.get(provider)
            if key:
                return key
        return None
