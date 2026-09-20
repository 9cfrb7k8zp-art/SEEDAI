# ==========================================================
# FILE: relay_emergency_stop.py
# PATH: SEED_ROOT/seed/core/relay/relay_emergency_stop.py
# VERSION: 2.0.0
# PURPOSE: Immediate relay external-operation shutdown
# ==========================================================

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Optional


MODULE_ID = "CORE_RELAY_EMERGENCY_STOP"
MODULE_VERSION = "2.0.0"


def utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


class RelayEmergencyStop:

    def __init__(self):
        self._lock = threading.RLock()

        self._engaged = False
        self._reason: Optional[str] = None
        self._engaged_at: Optional[str] = None

    # ------------------------------------------------------
    # STOP
    # ------------------------------------------------------

    def engage(
        self,
        reason: str = "Emergency relay stop.",
    ) -> None:

        with self._lock:
            self._engaged = True
            self._reason = str(reason)
            self._engaged_at = utc_now()

    # ------------------------------------------------------
    # RESET
    # ------------------------------------------------------

    def reset(self) -> None:
        with self._lock:
            self._engaged = False
            self._reason = None
            self._engaged_at = None

    # ------------------------------------------------------
    # CHECK
    # ------------------------------------------------------

    def is_engaged(self) -> bool:
        with self._lock:
            return self._engaged

    def allow(self) -> tuple[bool, str]:

        with self._lock:
            if self._engaged:
                return (
                    False,
                    self._reason
                    or "Emergency relay stop engaged.",
                )

            return True, "EMERGENCY_STOP_CLEAR"

    # ------------------------------------------------------
    # STATUS
    # ------------------------------------------------------

    def status(self) -> dict:
        with self._lock:
            return {
                "module": MODULE_ID,
                "version": MODULE_VERSION,
                "engaged": self._engaged,
                "reason": self._reason,
                "engaged_at": self._engaged_at,
            }