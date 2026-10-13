from __future__ import annotations

import argparse
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import anthropic
from openai import OpenAI, OpenAIError

from .credentials import (
    ChainedCredentialProvider,
    CredentialError,
    CredentialProvider,
    EnvCredentialProvider,
    JsonFileCredentialProvider,
    default_keys_paths,
)
from .extractor import TrafilaturaExtractor
from .fetcher import FetchError, HttpxFetcher
from .openai_compatible import OpenAICompatibleSummarizer
from .pipeline import PaperPipeline
from .summarizer import AnthropicSummarizer, Summarizer
from .writer import MarkdownPaperWriter


@dataclass(frozen=True, slots=True)
class Provider:
    base_url: str | None      # None -> SDK default
    key_env: str | None       # env-var fallback name; None -> no key needed (local)
    default_model: str | None


# Free-tier limits and model IDs change often: verify in each provider's console.
PROVIDERS: dict[str, Provider] = {
    "anthropic":  Provider(None, "ANTHROPIC_API_KEY", "claude-sonnet-5-5"),
    "openai":     Provider(None, "OPENAI_API_KEY", None),
    "xai":        Provider("https://api.x.ai/v1", "XAI_API_KEY", None),
    "gemini":     Provider("https://generativelanguage.googleapis.com/v1beta/openai/",
                           "GEMINI_API_KEY", "gemini-2.5-flash"),
    "groq":       Provider("https://api.groq.com/openai/v1", "GROQ_API_KEY", "openai/gpt-oss-120b"),
    "openrouter": Provider("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY", None),
    "ollama":     Provider("http://localhost:11434/v1", None, None),
}


def build_credentials(keys_file: Path | None) -> CredentialProvider:
    """JSON file(s) first, environment variables as a fallback (CI/Docker)."""
    if keys_file is not None:
        file_sources = [JsonFileCredentialProvider(keys_file, required=True)]
    else:
        file_sources = [JsonFileCredentialProvider(p) for p in default_keys_paths()]
    env_names = {name: p.key_env for name, p in PROVIDERS.items() if p.key_env}
    return ChainedCredentialProvider([*file_sources, EnvCredentialProvider(env_names)])


def build_summarizer(
    provider_name: str,
    model: str | None,
    max_chars: int,
    max_output_tokens: int,
    credentials: CredentialProvider,
) -> Summarizer:
    provider = PROVIDERS[provider_name]
    model = model or provider.default_model
    if not model:
        raise SystemExit(f"--model is required for provider '{provider_name}'.")

    if provider.key_env is None:  # local server, no key
        api_key = "not-needed"
    else:
        api_key = credentials.get(provider_name)
        if not api_key:
            raise CredentialError(
                f"No API key for '{provider_name}'. Add \"{provider_name}\": \"...\" to keys.json "
                f"(see keys.example.json), pass --keys-file, or set {provider.key_env}."
            )

    if provider_name == "anthropic":
        return AnthropicSummarizer(
            anthropic.Anthropic(api_key=api_key), model, max_chars, max_output_tokens
        )
    client = OpenAI(api_key=api_key, base_url=provider.base_url)
    return OpenAICompatibleSummarizer(client, model, max_chars, max_output_tokens)


def build_pipeline(summarizer: Summarizer, out_dir: Path) -> PaperPipeline:
    """Composition root: the only place concrete classes are wired together."""
    return PaperPipeline(
        fetcher=HttpxFetcher(),
        extractor=TrafilaturaExtractor(),
        summarizer=summarizer,
        writer=MarkdownPaperWriter(out_dir),
    )


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(message)s")

    parser = argparse.ArgumentParser(description="Analyse a web page and write the result to a file.")
    parser.add_argument("url")
    parser.add_argument("-o", "--out", type=Path, default=Path("papers"))
    parser.add_argument("--provider", choices=sorted(PROVIDERS), default="anthropic")
    parser.add_argument("--model", default=os.getenv("PAPER_MODEL"))
    parser.add_argument("--keys-file", type=Path, default=os.getenv("PAPER_KEYS_FILE"),
                        help="JSON file with API keys. Default search: ./keys.json, "
                             "~/.config/paper-scraper/keys.json, then environment variables.")
    parser.add_argument("--max-chars", type=int, default=120_000,
                        help="Lower this on free tiers with small context/token quotas.")
    parser.add_argument("--max-output-tokens", type=int, default=2_000,
                        help="Output cap. Some providers (e.g. Groq) count it toward the TPM limit.")
    args = parser.parse_args(argv)

    try:
        summarizer = build_summarizer(
            args.provider, args.model, args.max_chars, args.max_output_tokens,
            build_credentials(args.keys_file),
        )
        path = build_pipeline(summarizer, args.out).run(args.url)
    except CredentialError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except FetchError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except (anthropic.APIError, OpenAIError, RuntimeError) as exc:
        print(f"LLM error: {exc}", file=sys.stderr)
        return 1
    print(f"Saved: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
