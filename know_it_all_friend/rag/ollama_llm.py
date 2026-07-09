"""Ollama-backed chat model: answers are generated locally."""

from __future__ import annotations

import logging
from collections.abc import Iterator

from know_it_all_friend.rag.base import BaseLLM
from know_it_all_friend.retry import with_retry

logger = logging.getLogger(__name__)

DEFAULT_CHAT_MODEL = "llama3.2"


def _build_messages(prompt: str, system: str | None) -> list[dict[str, str]]:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    return messages


class OllamaLLM(BaseLLM):
    def __init__(self, model: str = DEFAULT_CHAT_MODEL, host: str | None = None):
        import ollama

        self.model = model
        self._client = ollama.Client(host=host)

    def generate(self, prompt: str, system: str | None = None) -> str:
        response = with_retry(
            lambda: self._client.chat(model=self.model, messages=_build_messages(prompt, system))
        )
        logger.info("Generated answer with %s", self.model)
        return response["message"]["content"]

    def generate_stream(self, prompt: str, system: str | None = None) -> Iterator[str]:
        stream = with_retry(
            lambda: self._client.chat(
                model=self.model, messages=_build_messages(prompt, system), stream=True
            )
        )
        for chunk in stream:
            content = chunk["message"]["content"]
            if content:
                yield content
