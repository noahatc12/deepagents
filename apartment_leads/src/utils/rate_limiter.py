"""
Token-bucket rate limiter and retry decorator with exponential back-off.
"""

import time
import functools
import random
from threading import Lock
from typing import Callable, Optional, Type, Tuple, TypeVar

F = TypeVar("F", bound=Callable)


class RateLimiter:
    """
    A simple thread-safe token-bucket rate limiter.

    Example:
        limiter = RateLimiter(requests_per_second=1.0)
        limiter.wait()   # blocks until a token is available
    """

    def __init__(self, requests_per_second: float = 1.0) -> None:
        self._rate = requests_per_second
        self._tokens: float = requests_per_second
        self._last_check = time.monotonic()
        self._lock = Lock()

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_check
            self._last_check = now
            self._tokens = min(self._rate, self._tokens + elapsed * self._rate)

            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return

            sleep_time = (1.0 - self._tokens) / self._rate
            self._tokens = 0.0

        time.sleep(sleep_time)


def with_retry(
    max_attempts: int = 4,
    base_delay: float = 2.0,
    backoff_factor: float = 2.0,
    jitter: float = 0.5,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    logger=None,
) -> Callable[[F], F]:
    """
    Decorator: retry a function with exponential back-off + jitter.

    Args:
        max_attempts:        Total attempts (including the first).
        base_delay:          Seconds to wait before first retry.
        backoff_factor:      Multiplier applied each retry.
        jitter:              Random fraction of delay added to avoid thundering herd.
        retryable_exceptions: Only retry on these exception types.
        logger:              Optional logger instance.
    """

    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            delay = base_delay
            for attempt in range(1, max_attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except retryable_exceptions as exc:
                    if attempt == max_attempts:
                        raise
                    sleep = delay + random.uniform(0, jitter * delay)
                    if logger:
                        logger.warning(
                            "Attempt %d/%d failed for %s: %s. Retrying in %.1fs.",
                            attempt,
                            max_attempts,
                            fn.__name__,
                            exc,
                            sleep,
                        )
                    time.sleep(sleep)
                    delay *= backoff_factor

        return wrapper  # type: ignore[return-value]

    return decorator
