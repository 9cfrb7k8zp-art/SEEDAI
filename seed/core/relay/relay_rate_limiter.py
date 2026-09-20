# ==========================================================
# FILE: relay_rate_limiter.py
# PATH: SEED_ROOT/seed/core/relay/relay_rate_limiter.py
# VERSION: 2.0.0
# PURPOSE: Relay request rate limiting
# ==========================================================

from __future__ import annotations

import threading
import time
from collections import deque


MODULE_ID = "CORE_RELAY_RATE_LIMITER"
MODULE_VERSION = "2.0.0"


class RelayRateLimiter:


    def __init__(
        self,
        *,
        max_requests: int = 30,
        window_seconds: float = 60.0,
    ):
        if max_requests <= 0:
            raise ValueError(
                "max_requests must be greater than zero."
            )

        if window_seconds <= 0:
            raise ValueError(
                "window_seconds must be greater than zero."
            )

        self.max_requests = int(max_requests)
        self.window_seconds = float(window_seconds)

        self._events = deque()
        self._lock = threading.Lock()

        self._blocked_count = 0

    # ------------------------------------------------------
    # ADMISSION
    # ------------------------------------------------------

    def allow(self) -> bool:
        now = time.monotonic()

        with self._lock:
            self._expire(now)

            if len(self._events) >= self.max_requests:
                self._blocked_count += 1
                return False

            self._events.append(now)
            return True

    def remaining(self) -> int:
        now = time.monotonic()

        with self._lock:
            self._expire(now)
            return max(
                0,
                self.max_requests - len(self._events),
            )

    # ------------------------------------------------------
    # RESET / INTERNAL
    # ------------------------------------------------------

    def reset(self) -> None:
        with self._lock:
            self._events.clear()

    def _expire(self, now: float) -> None:
        cutoff = now - self.window_seconds

        while self._events:
            if self._events[0] > cutoff:
                break

            self._events.popleft()

    # ------------------------------------------------------
    # STATUS
    # ------------------------------------------------------

    def status(self) -> dict:
        now = time.monotonic()

        with self._lock:
            self._expire(now)

            return {
                "module": MODULE_ID,
                "version": MODULE_VERSION,
                "max_requests": self.max_requests,
                "window_seconds": self.window_seconds,
                "requests_in_window": len(
                    self._events
                ),
                "remaining": max(
                    0,
                    self.max_requests
                    - len(self._events),
                ),
                "blocked_count": self._blocked_count,
            }