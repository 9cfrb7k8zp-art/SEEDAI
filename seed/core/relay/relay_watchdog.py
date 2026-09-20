# ==========================================================
# FILE: relay_watchdog.py
# PATH: SEED_ROOT/seed/core/relay/relay_watchdog.py
# VERSION: 2.0.0
# PURPOSE: Relay health/watchdog monitoring
# ==========================================================

from __future__ import annotations

import threading
import time
from typing import Optional


MODULE_ID = "CORE_RELAY_WATCHDOG"
MODULE_VERSION = "2.0.0"


class RelayWatchdog:

    def __init__(
        self,
        relay,
        *,
        interval: float = 5.0,
    ):
        self.relay = relay
        self.interval = max(1.0, float(interval))

        self._running = False
        self._thread: Optional[
            threading.Thread
        ] = None

        self._lock = threading.RLock()

        self._checks = 0
        self._last_status: Optional[dict] = None
        self._last_error: Optional[str] = None
        self._last_check: Optional[float] = None

    # ------------------------------------------------------
    # LIFECYCLE
    # ------------------------------------------------------

    def start(self) -> None:
        with self._lock:

            if self._running:
                return

            self._running = True

            self._thread = threading.Thread(
                target=self._loop,
                name="SEEDRelayWatchdog",
                daemon=True,
            )

            self._thread.start()

    def stop(self) -> None:
        with self._lock:
            self._running = False

    # ------------------------------------------------------
    # CHECK
    # ------------------------------------------------------

    def check(self) -> dict:
        try:
            status = self.relay.status()

            healthy = bool(
                status.get("running")
            )

            self._last_status = status
            self._last_error = None
            self._checks += 1
            self._last_check = time.time()

            return {
                "healthy": healthy,
                "status": status,
            }

        except Exception as exc:
            self._last_error = str(exc)
            self._checks += 1
            self._last_check = time.time()

            return {
                "healthy": False,
                "error": str(exc),
            }

    # ------------------------------------------------------
    # LOOP
    # ------------------------------------------------------

    def _loop(self) -> None:

        while True:

            with self._lock:
                if not self._running:
                    break

            self.check()

            time.sleep(
                self.interval
            )

    # ------------------------------------------------------
    # STATUS
    # ------------------------------------------------------

    def status(self) -> dict:
        with self._lock:
            return {
                "module": MODULE_ID,
                "version": MODULE_VERSION,
                "running": self._running,
                "interval": self.interval,
                "checks": self._checks,
                "last_check": self._last_check,
                "last_error": self._last_error,
                "healthy": (
                    self._last_status is not None
                    and bool(
                        self._last_status.get(
                            "running",
                            False,
                        )
                    )
                    and self._last_error is None
                ),
            }