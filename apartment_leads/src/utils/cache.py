"""
Disk-based HTTP response cache using a simple SQLite store.
Prevents re-fetching the same URLs within a configurable TTL.
"""

import hashlib
import json
import sqlite3
import time
from pathlib import Path
from typing import Optional


class RequestCache:
    """
    Lightweight SQLite-backed cache for HTTP responses.

    Usage:
        cache = RequestCache(Path("data/cache/requests.db"), ttl_seconds=86400)
        hit = cache.get(url)
        if hit is None:
            response = requests.get(url)
            cache.set(url, response.text)
    """

    def __init__(self, db_path: Path, ttl_seconds: int = 86_400) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ttl = ttl_seconds
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._init_db()

    def _init_db(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS cache (
                key      TEXT PRIMARY KEY,
                value    TEXT NOT NULL,
                stored_at REAL NOT NULL
            )
            """
        )
        self._conn.commit()

    @staticmethod
    def _key(url: str, params: Optional[dict] = None) -> str:
        raw = url + (json.dumps(params, sort_keys=True) if params else "")
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(self, url: str, params: Optional[dict] = None) -> Optional[str]:
        key = self._key(url, params)
        row = self._conn.execute(
            "SELECT value, stored_at FROM cache WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            return None
        value, stored_at = row
        if time.time() - stored_at > self._ttl:
            self._conn.execute("DELETE FROM cache WHERE key = ?", (key,))
            self._conn.commit()
            return None
        return value

    def set(self, url: str, value: str, params: Optional[dict] = None) -> None:
        key = self._key(url, params)
        self._conn.execute(
            "INSERT OR REPLACE INTO cache (key, value, stored_at) VALUES (?, ?, ?)",
            (key, value, time.time()),
        )
        self._conn.commit()

    def clear_expired(self) -> int:
        cutoff = time.time() - self._ttl
        cur = self._conn.execute("DELETE FROM cache WHERE stored_at < ?", (cutoff,))
        self._conn.commit()
        return cur.rowcount

    def close(self) -> None:
        self._conn.close()
