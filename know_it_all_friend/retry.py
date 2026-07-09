"""Small retry helper for local Ollama calls."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import TypeVar

import httpx

logger = logging.getLogger(__name__)

T = TypeVar("T")

_RETRYABLE = (httpx.ConnectError, httpx.TimeoutException, ConnectionError)


def with_retry(call: Callable[[], T], attempts: int = 3, base_delay: float = 0.5) -> T:
    """Call ``call()``, retrying on transient connection/timeout errors.

    Only connection and timeout errors are retried -- an API error (bad
    model name, malformed request) won't fix itself on retry. Raises a clear
    ``RuntimeError`` once attempts are exhausted, pointing at the likely
    cause instead of surfacing a raw connection traceback.
    """
    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return call()
        except _RETRYABLE as exc:
            last_exc = exc
            if attempt < attempts:
                delay = base_delay * (2 ** (attempt - 1))
                logger.warning(
                    "Ollama call failed (attempt %d/%d): %s -- retrying in %.1fs",
                    attempt,
                    attempts,
                    exc,
                    delay,
                )
                time.sleep(delay)
    raise RuntimeError(
        f"Could not reach Ollama after {attempts} attempt(s); is `ollama serve` running?"
    ) from last_exc
