import functools
import logging
import random
import re
import threading
import time
from typing import Any, Callable, TypeVar

logger = logging.getLogger("jnaara.llm.rate_limiter")

T = TypeVar("T")


class ProviderRateLimiter:
    """Thread-safe rate limiter and inter-call pacer for LLM providers."""

    def __init__(self, min_interval_seconds: float = 2.0):
        self.min_interval = max(0.0, min_interval_seconds)
        self._last_call: float = 0.0
        self._lock = threading.Lock()

    def acquire(self, provider_name: str = "LLM") -> None:
        """Enforce minimum interval between successive requests to this provider."""
        if self.min_interval <= 0:
            return

        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_call
            if self._last_call > 0 and elapsed < self.min_interval:
                wait_time = self.min_interval - elapsed
                logger.info(
                    "[RateLimiter] Pacing %s API call: waiting %.2fs to respect rate limit (min interval: %.1fs)...",
                    provider_name,
                    wait_time,
                    self.min_interval,
                )
                time.sleep(wait_time)
            self._last_call = time.monotonic()


def is_rate_limit_error(exc: Exception) -> bool:
    """Check whether an exception represents a rate limit / quota exhaustion error."""
    exc_type = type(exc).__name__.lower()
    exc_module = getattr(type(exc), "__module__", "").lower()
    exc_str = str(exc).lower()

    # Known rate limit exception types across Groq, Google GenAI, LangChain, and HTTP libraries
    if any(
        kw in exc_type
        for kw in (
            "ratelimit",
            "resourceexhausted",
            "toomanyrequests",
            "quotadeleted",
            "quotaexceeded",
        )
    ):
        return True

    if "resource_exhausted" in exc_module or "ratelimit" in exc_module:
        return True

    # HTTP Status code checks
    status_code = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    if status_code == 429:
        return True

    # Error message substring patterns
    rate_limit_keywords = [
        "429",
        "rate limit",
        "rate_limit",
        "resource has been exhausted",
        "resourceexhausted",
        "quota exceeded",
        "tokens per minute",
        "requests per minute",
        "tpm",
        "rpm",
        "too many requests",
        "please try again in",
    ]
    return any(kw in exc_str for kw in rate_limit_keywords)


def parse_retry_after(exc: Exception) -> float | None:
    """Attempt to parse explicit retry-after or wait duration from rate limit exception."""
    # Check headers
    headers = getattr(exc, "headers", None) or getattr(getattr(exc, "response", None), "headers", None)
    if headers and isinstance(headers, dict):
        retry_val = headers.get("retry-after") or headers.get("Retry-After")
        if retry_val:
            try:
                return float(retry_val)
            except ValueError:
                pass

    # Search in error message (e.g., "Please try again in 2.5s" or "try again in 4s")
    exc_str = str(exc)
    match = re.search(r"try again in (\d+(?:\.\d+)?)\s*s", exc_str, re.IGNORECASE)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass

    return None


def execute_with_rate_limit_retry(
    fn: Callable[..., T],
    *args: Any,
    max_retries: int = 5,
    initial_delay: float = 3.0,
    backoff_factor: float = 2.0,
    provider_name: str = "LLM",
    rate_limiter: ProviderRateLimiter | None = None,
    **kwargs: Any,
) -> T:
    """Execute a callable with rate limit pacing and exponential backoff retry."""
    attempt = 0
    while True:
        if rate_limiter is not None:
            rate_limiter.acquire(provider_name=provider_name)

        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            if not is_rate_limit_error(exc) or attempt >= max_retries:
                if attempt >= max_retries and is_rate_limit_error(exc):
                    logger.error(
                        "[RateLimit] %s exceeded maximum retries (%d) on rate limit: %s",
                        provider_name,
                        max_retries,
                        exc,
                    )
                raise

            parsed_delay = parse_retry_after(exc)
            if parsed_delay is not None:
                wait_time = parsed_delay + 0.5 + random.uniform(0.1, 0.4)
            else:
                wait_time = (initial_delay * (backoff_factor**attempt)) + random.uniform(0.2, 0.8)

            logger.warning(
                "[RateLimit] Rate limit (429/quota) hit on %s. Retrying in %.2fs (attempt %d/%d)... Error: %s",
                provider_name,
                wait_time,
                attempt + 1,
                max_retries,
                exc,
            )
            time.sleep(wait_time)
            attempt += 1


def rate_limited(
    provider_name: str = "LLM",
    max_retries: int = 5,
    initial_delay: float = 3.0,
    backoff_factor: float = 2.0,
):
    """Decorator to apply rate limit retry and pacing to a provider method."""

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(self: Any, *args: Any, **kwargs: Any) -> T:
            limiter = getattr(self, "rate_limiter", None)
            p_name = getattr(self, "get_provider_name", lambda: provider_name)()
            retries = getattr(self, "max_retries", max_retries)
            init_delay = getattr(self, "initial_delay", initial_delay)
            factor = getattr(self, "backoff_factor", backoff_factor)

            return execute_with_rate_limit_retry(
                func,
                self,
                *args,
                max_retries=retries,
                initial_delay=init_delay,
                backoff_factor=factor,
                provider_name=p_name,
                rate_limiter=limiter,
                **kwargs,
            )

        return wrapper

    return decorator
