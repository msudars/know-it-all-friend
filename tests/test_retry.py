import httpx
import pytest

from know_it_all_friend.retry import with_retry


def test_with_retry_returns_result_on_first_success() -> None:
    calls = []

    def call():
        calls.append(1)
        return "ok"

    assert with_retry(call, attempts=3, base_delay=0) == "ok"
    assert len(calls) == 1


def test_with_retry_recovers_after_transient_failures() -> None:
    attempts_made = []

    def call():
        attempts_made.append(1)
        if len(attempts_made) < 3:
            raise httpx.ConnectError("connection refused")
        return "ok"

    assert with_retry(call, attempts=3, base_delay=0) == "ok"
    assert len(attempts_made) == 3


def test_with_retry_raises_runtime_error_after_exhausting_attempts() -> None:
    def call():
        raise httpx.ConnectError("connection refused")

    with pytest.raises(RuntimeError, match="ollama serve"):
        with_retry(call, attempts=2, base_delay=0)


def test_with_retry_does_not_retry_non_connection_errors() -> None:
    calls = []

    def call():
        calls.append(1)
        raise ValueError("bad model name")

    with pytest.raises(ValueError):
        with_retry(call, attempts=3, base_delay=0)
    assert len(calls) == 1
