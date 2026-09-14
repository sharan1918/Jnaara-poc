from datetime import datetime, timezone
import time
from unittest.mock import MagicMock
import pytest
from pydantic import SecretStr

from jnaara.config import Settings
from jnaara.llm.factory import create_provider
from jnaara.llm.rate_limiter import (
    ProviderRateLimiter,
    execute_with_rate_limit_retry,
    is_rate_limit_error,
    parse_retry_after,
    rate_limited,
)
from jnaara.models.domain import Fact


def test_is_rate_limit_error():
    # Exception with 429 status code
    class HTTP429Error(Exception):
        status_code = 429

    assert is_rate_limit_error(HTTP429Error("Too many requests")) is True

    # Exception with rate limit message
    assert is_rate_limit_error(Exception("Rate limit reached for model in 2.5s")) is True
    assert is_rate_limit_error(Exception("Resource has been exhausted (e.g. check quota)")) is True
    assert is_rate_limit_error(Exception("Error code: 429 - tokens per minute exceeded")) is True
    assert is_rate_limit_error(Exception("RPM limit reached")) is True

    # Standard non-rate-limit exception
    assert is_rate_limit_error(ValueError("Invalid argument")) is False
    assert is_rate_limit_error(KeyError("missing key")) is False


def test_parse_retry_after():
    # From header
    class ResponseError(Exception):
        headers = {"retry-after": "5.5"}

    assert parse_retry_after(ResponseError()) == 5.5

    # From error message text
    msg_err = Exception("Rate limit exceeded. Please try again in 3.2s.")
    assert parse_retry_after(msg_err) == 3.2

    # No retry info
    assert parse_retry_after(Exception("Unknown rate limit")) is None


def test_provider_rate_limiter_pacing():
    limiter = ProviderRateLimiter(min_interval_seconds=0.05)
    start = time.monotonic()
    limiter.acquire("test-groq")
    limiter.acquire("test-groq")
    elapsed = time.monotonic() - start
    assert elapsed >= 0.045


def test_execute_with_rate_limit_retry_success():
    calls = 0

    def mock_api_call():
        nonlocal calls
        calls += 1
        if calls < 3:
            raise Exception("429 Too Many Requests: Please try again in 0.01s")
        return "SUCCESS"

    result = execute_with_rate_limit_retry(
        mock_api_call,
        max_retries=3,
        initial_delay=0.01,
        backoff_factor=1.0,
        provider_name="Groq",
    )
    assert result == "SUCCESS"
    assert calls == 3


def test_execute_with_rate_limit_retry_max_retries_exceeded():
    calls = 0

    def failing_call():
        nonlocal calls
        calls += 1
        raise Exception("429 Resource has been exhausted")

    with pytest.raises(Exception, match="429 Resource has been exhausted"):
        execute_with_rate_limit_retry(
            failing_call,
            max_retries=2,
            initial_delay=0.01,
            backoff_factor=1.0,
            provider_name="Gemini",
        )
    assert calls == 3  # Initial try + 2 retries


def test_rate_limited_decorator():
    class DummyService:
        def __init__(self):
            self.rate_limiter = ProviderRateLimiter(min_interval_seconds=0.01)
            self.max_retries = 2
            self.initial_delay = 0.01
            self.backoff_factor = 1.0
            self.calls = 0

        def get_provider_name(self):
            return "dummy"

        @rate_limited()
        def perform_work(self, item: str):
            self.calls += 1
            if self.calls == 1:
                raise Exception("429 Rate limit reached for model")
            return f"processed: {item}"

    service = DummyService()
    res = service.perform_work("fact_1")
    assert res == "processed: fact_1"
    assert service.calls == 2


def test_process_sequence_with_delay(manager):
    facts = [
        Fact(
            id="F1",
            timestamp=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc),
            source="Source A",
            source_reliability="high",
            content="Alpha Corp revenue is $100M.",
        ),
        Fact(
            id="F2",
            timestamp=datetime(2025, 1, 2, 10, 0, tzinfo=timezone.utc),
            source="Source B",
            source_reliability="high",
            content="Alpha Corp revenue is $110M.",
        ),
    ]

    start = time.monotonic()
    results = manager.process_sequence(facts, delay_seconds=0.05)
    elapsed = time.monotonic() - start

    assert len(results) == 2
    assert elapsed >= 0.045


def test_create_provider_with_rate_limiter_config():
    settings = Settings(
        groq_api_key=SecretStr("mock_key"),
        google_api_key=SecretStr("mock_key"),
        groq_min_call_interval=1.5,
        gemini_min_call_interval=3.5,
        llm_max_retries=4,
    )

    groq = create_provider("groq", "openai/gpt-oss-120b", settings)
    assert groq.get_provider_name() == "groq"
    assert groq.rate_limiter.min_interval == 1.5
    assert groq.max_retries == 4

    gemini = create_provider("gemini", "gemini-3.6-flash", settings)
    assert gemini.get_provider_name() == "gemini"
    assert gemini.rate_limiter.min_interval == 3.5
    assert gemini.max_retries == 4
