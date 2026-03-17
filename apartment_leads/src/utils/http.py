"""
Shared HTTP session factory with polite defaults:
  - User-Agent identifies the tool
  - Respects robots.txt (caller should check via RobotsChecker)
  - Integrates with RequestCache
  - Integrates with RateLimiter
"""

import time
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests
from requests import Response, Session

from .cache import RequestCache
from .rate_limiter import RateLimiter
from .logging import get_logger

logger = get_logger(__name__)

DEFAULT_USER_AGENT = (
    "ApartmentLeadBot/1.0 (research tool; contact: see project README; "
    "respects robots.txt)"
)


class PoliteSession:
    """
    A wrapper around requests.Session that:
      - Sets a descriptive User-Agent
      - Enforces per-domain rate limiting
      - Checks robots.txt before fetching
      - Uses a disk cache to avoid redundant requests
      - Raises on HTTP errors
    """

    def __init__(
        self,
        cache: Optional[RequestCache] = None,
        requests_per_second: float = 0.5,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout: int = 30,
    ) -> None:
        self._session = Session()
        self._session.headers.update({"User-Agent": user_agent})
        self._cache = cache
        self._timeout = timeout
        self._limiters: dict[str, RateLimiter] = {}
        self._default_rps = requests_per_second
        self._robots_cache: dict[str, RobotFileParser] = {}

    def _get_limiter(self, domain: str) -> RateLimiter:
        if domain not in self._limiters:
            self._limiters[domain] = RateLimiter(self._default_rps)
        return self._limiters[domain]

    def _get_robots(self, base_url: str) -> RobotFileParser:
        parsed = urlparse(base_url)
        domain = f"{parsed.scheme}://{parsed.netloc}"
        if domain not in self._robots_cache:
            rp = RobotFileParser()
            robots_url = f"{domain}/robots.txt"
            try:
                rp.set_url(robots_url)
                rp.read()
                self._robots_cache[domain] = rp
                logger.debug("Loaded robots.txt for %s", domain)
            except Exception as exc:
                logger.warning("Could not fetch robots.txt for %s: %s", domain, exc)
                self._robots_cache[domain] = rp
        return self._robots_cache[domain]

    def can_fetch(self, url: str) -> bool:
        """Return False if robots.txt disallows this URL for our agent."""
        rp = self._get_robots(url)
        return rp.can_fetch(DEFAULT_USER_AGENT, url)

    def get(
        self,
        url: str,
        params: Optional[dict] = None,
        skip_cache: bool = False,
        force_fetch: bool = False,
    ) -> str:
        """
        Fetch URL, returning response text.
        Raises PermissionError if robots.txt disallows.
        Raises requests.HTTPError on 4xx/5xx.
        """
        if not self.can_fetch(url):
            raise PermissionError(f"robots.txt disallows fetching: {url}")

        # Cache lookup
        if self._cache and not force_fetch:
            cached = self._cache.get(url, params)
            if cached is not None:
                logger.debug("Cache hit: %s", url)
                return cached

        # Rate limit per domain
        domain = urlparse(url).netloc
        self._get_limiter(domain).wait()

        logger.debug("Fetching: %s", url)
        resp: Response = self._session.get(url, params=params, timeout=self._timeout)
        resp.raise_for_status()

        if self._cache and not skip_cache:
            self._cache.set(url, resp.text, params)

        return resp.text

    def close(self) -> None:
        self._session.close()
        if self._cache:
            self._cache.close()


def make_session(
    cache_db: Optional[Path] = None,
    cache_ttl: int = 86_400,
    requests_per_second: float = 0.5,
) -> PoliteSession:
    cache = RequestCache(cache_db, ttl_seconds=cache_ttl) if cache_db else None
    return PoliteSession(cache=cache, requests_per_second=requests_per_second)
