from __future__ import annotations

from openai import OpenAI

from .models import Page, Paper
from .summarizer import SYSTEM_PROMPT, render_source


class OpenAICompatibleSummarizer:
    """Summarizer for any provider exposing the OpenAI chat-completions API.

    Works with OpenAI, xAI (Grok), Groq, OpenRouter, Gemini's compatibility
    endpoint, and local servers such as Ollama / llama.cpp / vLLM.
    """

    def __init__(
        self,
        client: OpenAI,
        model: str,
        max_input_chars: int = 120_000,
        max_output_tokens: int = 4_000,
    ) -> None:
        self._client = client
        self._model = model
        self._max_input_chars = max_input_chars
        self._max_output_tokens = max_output_tokens

    def summarize(self, page: Page) -> Paper:
        response = self._client.chat.completions.create(
            model=self._model,
            # Some newer OpenAI models want `max_completion_tokens` instead.
            max_tokens=self._max_output_tokens,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": render_source(page, self._max_input_chars)},
            ],
        )
        body = (response.choices[0].message.content or "").strip()
        if not body:
            raise RuntimeError("Model returned an empty response.")
        return Paper(source=page, body_markdown=body)
