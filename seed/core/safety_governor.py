# ==========================================================
# FILE: safety_governor.py
# PATH: SEED_ROOT/seed/core/safety_governor.py
# SYSTEM LAYER: Safety Governor (Pre-Actuation)
# VERSION: 1.0
# ==========================================================

import time
import logging
import threading
from typing import Dict, Any

logger = logging.getLogger("SafetyGovernor")

# ==========================================================
# SAFETY SPEC (HARD LIMITS)
# ==========================================================

DEFAULT_LIMITS = {
    "generic": {
        "min_value": 0.0,
        "max_value": 1.0,
        "rate_limit_sec": 0.05,
    },
    "motor": {
        "min_value": -1.0,
        "max_value": 1.0,
        "max_rotation_deg": 180.0,
        "rate_limit_sec": 0.1,
    },
    "led": {
        "min_value": 0.0,
        "max_value": 1.0,
        "rate_limit_sec": 0.2,
    }
}

EMERGENCY_STOP_FLAG = "__EMERGENCY_STOP__"


# ==========================================================
# SAFETY GOVERNOR
# ==========================================================

class SafetyGovernor:
    """
    Final authority before hardware actuation.
    Nothing bypasses this layer.
    """

    def __init__(self, limits: Dict[str, Dict[str, Any]] = None):
        self.limits = limits or DEFAULT_LIMITS
        self._last_emit_time = {}
        self._lock = threading.Lock()
        self._emergency_stop = False

    # ======================================================
    # CONTROL
    # ======================================================

    def emergency_stop(self, reason: str = "unspecified"):
        with self._lock:
            self._emergency_stop = True
            logger.critical(f"[SAFETY] EMERGENCY STOP ACTIVATED: {reason}")

    def clear_emergency_stop(self):
        with self._lock:
            self._emergency_stop = False
            logger.warning("[SAFETY] Emergency stop cleared")

    def is_emergency(self) -> bool:
        return self._emergency_stop

    # ======================================================
    # VALIDATION ENTRY POINT
    # ======================================================

    def validate(self, command: Dict[str, Any]) -> Dict[str, Any] | None:
        """
        Validate + clamp actuator command.
        Returns safe command or None if rejected.
        """

        if self._emergency_stop:
            logger.error("[SAFETY] Command blocked (emergency stop active)")
            return None

        actuator = command.get("actuator")
        if not actuator:
            logger.warning("[SAFETY] Missing actuator field")
            return None

        spec = self.limits.get(actuator, self.limits.get("generic", {}))

        now = time.time()
        last_ts = self._last_emit_time.get(actuator, 0.0)
        min_interval = spec.get("rate_limit_sec", 0.05)

        if now - last_ts < min_interval:
            logger.debug(f"[SAFETY] Rate limited ({actuator})")
            return None

        safe_cmd = dict(command)

        # ---------------- VALUE CLAMP ----------------
        if "value" in safe_cmd:
            min_v = spec.get("min_value", -1.0)
            max_v = spec.get("max_value", 1.0)
            safe_cmd["value"] = max(min_v, min(max_v, safe_cmd["value"]))

        # ---------------- ROTATION CLAMP ----------------
        if "rotation_deg" in safe_cmd:
            max_rot = spec.get("max_rotation_deg", 180.0)
            safe_cmd["rotation_deg"] = max(
                -max_rot, min(max_rot, safe_cmd["rotation_deg"])
            )

        # ---------------- MARK SAFE ----------------
        safe_cmd["_safety_checked"] = True
        safe_cmd["_safety_ts"] = now

        self._last_emit_time[actuator] = now
        return safe_cmd
