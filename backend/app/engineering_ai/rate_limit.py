"""Small in-process rate limiter for model/upload endpoints.

Project membership is checked by the router before this limiter runs.  The
limiter is deliberately dependency-free; production should replace/back it with
a shared store when multiple workers run, as noted in the agent report.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Dict, List

_BUCKETS: Dict[str, List[float]] = {}
_LOCK = threading.Lock()
_WINDOW_SECONDS = 60.0


class RateLimitExceeded(RuntimeError):
    def __init__(self, retry_after: int) -> None:
        super().__init__("Too many AI requests")
        self.retry_after = retry_after


def _limit() -> int:
    try:
        return max(1, int(os.getenv("ENGINEERING_AI_RATE_LIMIT_PER_MINUTE", "60")))
    except ValueError:
        return 60


def check_rate_limit(project_id: str, user_id: str | None, scope: str = "ai") -> None:
    limit = _limit()
    key = f"{project_id}:{user_id or 'anonymous'}:{scope}"
    now = time.monotonic()
    with _LOCK:
        bucket = [stamp for stamp in _BUCKETS.get(key, []) if now - stamp < _WINDOW_SECONDS]
        if len(bucket) >= limit:
            retry_after = max(1, int(_WINDOW_SECONDS - (now - bucket[0])))
            _BUCKETS[key] = bucket
            raise RateLimitExceeded(retry_after)
        bucket.append(now)
        _BUCKETS[key] = bucket


def reset_rate_limits() -> None:
    """Test helper; not used by production routes."""

    with _LOCK:
        _BUCKETS.clear()
