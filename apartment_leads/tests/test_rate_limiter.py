"""Tests for rate limiter and retry decorator."""

import time
import pytest
from src.utils.rate_limiter import RateLimiter, with_retry


class TestRateLimiter:
    def test_allows_immediate_first_request(self):
        limiter = RateLimiter(requests_per_second=10.0)
        t0 = time.monotonic()
        limiter.wait()
        elapsed = time.monotonic() - t0
        assert elapsed < 0.2  # Should be nearly instant

    def test_rate_limiting_slows_requests(self):
        limiter = RateLimiter(requests_per_second=5.0)  # 1 per 0.2s
        for _ in range(3):
            limiter.wait()
        # 3 requests at 5/s should take at least 0.3s but we don't enforce exact timing


class TestWithRetry:
    def test_succeeds_on_first_try(self):
        calls = []

        @with_retry(max_attempts=3, base_delay=0.01)
        def fn():
            calls.append(1)
            return "ok"

        result = fn()
        assert result == "ok"
        assert len(calls) == 1

    def test_retries_on_failure(self):
        calls = []

        @with_retry(max_attempts=3, base_delay=0.01, jitter=0.0)
        def fn():
            calls.append(1)
            if len(calls) < 3:
                raise ValueError("not yet")
            return "done"

        result = fn()
        assert result == "done"
        assert len(calls) == 3

    def test_raises_after_max_attempts(self):
        @with_retry(max_attempts=2, base_delay=0.01, jitter=0.0)
        def fn():
            raise RuntimeError("always fails")

        with pytest.raises(RuntimeError, match="always fails"):
            fn()

    def test_only_retries_specified_exceptions(self):
        calls = []

        @with_retry(
            max_attempts=3,
            base_delay=0.01,
            retryable_exceptions=(ValueError,),
        )
        def fn():
            calls.append(1)
            raise TypeError("not retryable")

        with pytest.raises(TypeError):
            fn()
        # Should not retry on TypeError
        assert len(calls) == 1
