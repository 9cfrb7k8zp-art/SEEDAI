# ==========================================================
# FILE: injector.py
# PATH: seed/skills/autofix/injector.py
# VERSION: 2.3 (ENABLED | HARD-BOUND | TRIPWIRED | QBIT-AWARE | TYPE-SAFE | NUMERIC-CLEAN | SPEED-AWARE)
# UPDATED: 2026-01-05
# ==========================================================

import logging
import uuid
import inspect
import time
from typing import Any, Dict, Set, Type

logger = logging.getLogger("Injector")
logger.setLevel(logging.INFO)

# ==========================================================
# HARD ENABLE (NO TOGGLE)
# ==========================================================
INJECTOR_ENABLED: bool = True

# ==========================================================
# HARD PROTECTED NUMERIC FIELDS
# ==========================================================
PROTECTED_FIELDS: Set[str] = {
    "cpu_usage",
    "memory_usage",
    "disk_usage",
    "check_interval",
    "CPU_THRESHOLD",
    "MEMORY_THRESHOLD",
    "DISK_THRESHOLD",
}

# ==========================================================
# HARD BLOCKED TYPES
# ==========================================================
BLOCKED_VALUE_TYPES: tuple = (
    dict,
    list,
    tuple,
    set,
)

BLOCKED_OBJECT_TYPES: tuple = (
    "EventBus",
    "SEEDEventBus",
)

# ==========================================================
# Injector
# ==========================================================
class Injector:
    def __init__(self, qbit_dialer=None, speed: float = 1.0):
        self.enabled = True
        self.track_id = f"INJECTOR-{uuid.uuid4().hex[:8]}"
        self.qbit_dialer = qbit_dialer
        self.speed = max(0.1, min(speed, 10.0))  # clamp speed
        self._last_injection_time = 0.0
        self._min_interval = 0.02 / self.speed  # auto-throttle interval
        logger.info(f"[Injector] ONLINE ({self.track_id}) | SPEED={self.speed}")

    # ------------------------------------------------------
    # PUBLIC API
    # ------------------------------------------------------
    def inject(
        self,
        target: Any,
        payload: Dict[str, Any],
        *,
        allow = True,
        source = "UNKNOWN",
    ) -> None:

        if not self.enabled:
            logger.critical("[Injector] DISABLED STATE REACHED (should never happen)")
            return

        now = time.time()
        if now - self._last_injection_time < self._min_interval:
            logger.info(f"[Injector:{self.track_id}] Injection throttled by SPEED={self.speed}")
            return
        self._last_injection_time = now

        if not isinstance(payload, dict):
            self._fatal(target, "payload_not_dict", payload, source)
            return

        for key, value in payload.items():
            # -------------------------------
            # FIELD PROTECTION
            # -------------------------------
            if key in PROTECTED_FIELDS:
                self._block(target, key, value, "protected_field", source)
                continue

            if key not in allow:
                self._block(target, key, value, "not_allowlisted", source)
                continue

            if not hasattr(target, key):
                self._block(target, key, value, "attribute_missing", source)
                continue

            # -------------------------------
            # TYPE GUARDS
            # -------------------------------
            if isinstance(value, BLOCKED_VALUE_TYPES):
                self._block(target, key, value, "blocked_value_type", source)
                continue

            if any(name in type(value).__name__ for name in BLOCKED_OBJECT_TYPES):
                self._block(target, key, value, "blocked_object_type", source)
                continue

            # -------------------------------
            # NUMERIC LOCK + AUTO CONVERSION
            # -------------------------------
            current = getattr(target, key)

            if isinstance(current, (int, float)):
                if isinstance(value, str):
                    try:
                        if '.' in value:
                            value = float(value)
                        else:
                            value = int(value)
                        logger.info(f"[Injector:{self.track_id}] Auto-converted {key}='{payload[key]}' -> {value}")
                    except Exception:
                        self._tripwire(target, key, value, "invalid_numeric_string", source)
                        continue
                elif not isinstance(value, (int, float)):
                    self._tripwire(target, key, value, "numeric_overwrite_attempt", source)
                    continue

            # -------------------------------
            # SAFE APPLY
            # -------------------------------
            try:
                setattr(target, key, value)
                logger.info(f"[Injector:{self.track_id}] {source} -> {type(target).__name__}.{key} = {value}")
            except Exception as e:
                self._fatal(target, key, value, f"setattr_failed:{e}", source)

        # -------------------------------
        # Qbit Feedback (Speed-aware)
        # -------------------------------
        if self.qbit_dialer and callable(getattr(self.qbit_dialer, "push_data", None)):
            try:
                self.qbit_dialer.push_data({
                    "track_id": self.track_id,
                    "source": source,
                    "speed": self.speed,
                    "target": type(target).__name__,
                    "fields": list(payload.keys()),
                })
            except Exception as e:
                logger.warning(f"[Injector:{self.track_id}] Qbit push_data failed: {e}")

    # ======================================================
    # TRIPWIRES / BLOCKS
    # ======================================================
    def _block(self, target: Any, key: str, value: Any, reason: str, source: str) -> None:
        logger.error(
            f"[Injector BLOCK] src={source} target={type(target).__name__} "
            f"field={key} value_type={type(value).__name__} reason={reason}"
        )

    def _tripwire(self, target: Any, key: str, value: Any, reason: str, source: str) -> None:
        logger.critical(
            f"[Injector TRIPWIRE] src={source} NUMERIC CORRUPTION PREVENTED "
            f"{type(target).__name__}.{key} <- {type(value).__name__} ({reason})"
        )

    def _fatal(self, target: Any, key: str, value: Any, reason: str, source: str) -> None:
        logger.critical(
            f"[Injector FATAL] src={source} target={type(target).__name__} "
            f"field={key} reason={reason}"
        )

    # ======================================================
    # ROGUE INJECTOR DETECTION
    # ======================================================
    @staticmethod
    def detect_reflection_injectors() -> None:
        for frame in inspect.stack():
            code = frame.frame.f_code.co_name
            if code in ("__dict__", "setattr", "update"):
                logger.warning(
                    f"[Injector ALERT] Possible reflection injector in {frame.filename}:{frame.lineno}"
                )

# ==========================================================
# END OF FILE
# ==========================================================
