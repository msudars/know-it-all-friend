"""Ollama-backed chat model: answers are generated locally."""

from __future__ import annotations

import logging

from know_it_all_friend.rag.base import BaseLLM

logger = logging.getLogger(__name__)

DEFAULT_CHAT_MODEL = "llama3.2"


class OllamaLLM(BaseLLM):
    def __init__(self, model: str = DEFAULT_CHAT_MODEL, host: str | None = None):
        import ollama

        self.model = model
        self._client = ollama.Client(host=host)

    def generate(self, prompt: str, system: str | None = None) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        response = self._client.chat(model=self.model, messages=messages)
        logger.info("Generated answer with %s", self.model)
        return response["message"]["content"]
