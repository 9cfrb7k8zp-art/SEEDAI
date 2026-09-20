# ==========================================================
# FILE: SEED_ROOT/seed/tools/invariant_guard.py
# ROLE: Passive invariant observer (flags only, no control)
# VERSION: 2.0.0
# ==========================================================

import logging
import threading
import time

from seed.tools.base_tool import BaseTool


logger = logging.getLogger("INVARIANT-GUARD")


class InvariantGuard(BaseTool):

    NODE_TYPE = "tool"
    NODE_VERSION = "2.0.0"

    NORMAL_INTERVAL = 360.0

    def __init__(
        self,
        name="InvariantGuard",
        capabilities=None,
        dependencies=None,
        role="invariant-observer",
        version="2.0.0",
        always_on=False,
        event_bus=None,
    ):
        default_capabilities = {
            "invariant_monitoring",
            "event_bus_validation",
            "passive_fault_detection",
            "dependency_observation",
            "runtime_integrity",
            "invariant_reporting",
        }

        if capabilities:
            default_capabilities.update(capabilities)

        super().__init__(
            name=name,
            capabilities=default_capabilities,
            dependencies=dependencies,
            role=role,
            version=version,
            always_on=always_on,
        )

        self._lock = threading.RLock()

        self._event_bus = None

        self._thread = None
        self._stop_flag = threading.Event()

        # One-shot flags prevent repeated spam.
        self._flagged = set()

        self._flag_history = []

        self._check_count = 0
        self._flag_count = 0

        self._last_check = None
        self._last_flag = None

        if event_bus is not None:
            self.bind("event_bus", event_bus)

    # ------------------------------------------------------
    # EventBus binding
    # ------------------------------------------------------

    def bind_event_bus(self, event_bus):
        if event_bus is None:
            self.unbind("event_bus")
            self._event_bus = None
            return False

        self.bind("event_bus", event_bus)
        self._event_bus = event_bus

        logger.info(
            f"[{self.name}] EventBus bound"
        )

        return True

    def unbind_event_bus(self):
        self.unbind("event_bus")
        self._event_bus = None

        logger.info(
            f"[{self.name}] EventBus unbound"
        )

    def get_event_bus(self):
        return self._event_bus

    # ------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------

    def start(self):
        with self._lock:
            if self.active:
                return self.status()

            self.active = True
            self._stop_flag.clear()

            self._thread = threading.Thread(
                target=self._monitor_loop,
                name="InvariantGuardMonitor",
                daemon=True,
            )

            self._thread.start()

        logger.info(
            f"[{self.name}] Passive invariant "
            f"monitoring started."
        )

        return self.status()

    def stop(self):
        self._stop_flag.set()

        with self._lock:
            self.active = False
            self._thread = None

        logger.info(
            f"[{self.name}] Stopped."
        )

        return self.status()

    # ------------------------------------------------------
    # Monitor loop
    # ------------------------------------------------------

    def _monitor_loop(self):
        while not self._stop_flag.wait(
            self.NORMAL_INTERVAL
        ):
            try:
                self._check_event_bus()
            except Exception as exc:
                with self._lock:
                    self._last_flag = time.time()

                logger.exception(
                    f"[{self.name}] "
                    f"Invariant monitoring error: {exc}"
                )

    # ------------------------------------------------------
    # Invariant checks
    # ------------------------------------------------------

    def _check_event_bus(self):
        with self._lock:
            self._check_count += 1
            self._last_check = time.time()

            bus = self._event_bus

        if bus is None:
            self._flag_once(
                "EVENT_BUS_MISSING",
                "EventBus not attached to InvariantGuard",
            )
            return False

        # --------------------------------------------------
        # emit must exist
        # --------------------------------------------------

        if not callable(
            getattr(bus, "emit", None)
        ):
            self._flag_once(
                "EVENT_BUS_EMIT_INVALID",
                "EventBus.emit is not callable",
            )

        # --------------------------------------------------
        # Subscribers registry is expected but observed only
        # --------------------------------------------------

        if not hasattr(bus, "_subscribers"):
            self._flag_once(
                "EVENT_BUS_SUBSCRIBERS_MISSING",
                "EventBus missing _subscribers attribute",
            )

        # --------------------------------------------------
        # Qbit presence is informational only
        # --------------------------------------------------

        if not hasattr(bus, "qbit") or bus.qbit is None:
            self._flag_once(
                "QBIT_NOT_ATTACHED",
                "EventBus has no Qbit attached",
            )

        return True

    # ------------------------------------------------------
    # Flag + report
    # ------------------------------------------------------

    def _flag_once(
        self,
        code,
        message,
        severity="info",
        evidence=None,
    ):
        with self._lock:
            if code in self._flagged:
                return False

            self._flagged.add(code)

            timestamp = time.time()

            record = {
                "type": "invariant_flag",
                "source": self.node_id,
                "source_name": self.name,
                "code": code,
                "message": message,
                "severity": severity,
                "evidence": evidence,
                "timestamp": timestamp,
                "execution": {
                    "executed": False,
                    "execution_owner": None,
                },
            }

            self._flag_history.append(record)
            self._flag_count += 1
            self._last_flag = timestamp

            bus = self._event_bus

        logger.warning(
            f"[{self.name}] "
            f"FLAG [{code}]: {message}"
        )

        # --------------------------------------------------
        # Observation only.
        #
        # No "action" field is injected into the event.
        # The flag is telemetry, not a command.
        # --------------------------------------------------

        if bus is not None:
            emit = getattr(bus, "emit", None)

            if callable(emit):
                try:
                    emit(
                        "INVARIANT_FLAG",
                        record.copy(),
                    )
                except Exception as exc:
                    logger.error(
                        f"[{self.name}] "
                        f"Failed to emit invariant flag: {exc}"
                    )

        return True

    # ------------------------------------------------------
    # Manual trigger
    # ------------------------------------------------------

    def check_now(self):
        result = self._check_event_bus()

        return {
            "type": "invariant_check",
            "source": self.node_id,
            "success": result,
            "timestamp": time.time(),
            "flagged": sorted(self._flagged),
        }

    # ------------------------------------------------------
    # Clear one-shot flags
    # ------------------------------------------------------

    def clear_flags(self):
        with self._lock:
            cleared = list(self._flagged)
            self._flagged.clear()

        logger.info(
            f"[{self.name}] "
            f"Cleared {len(cleared)} invariant flags"
        )

        return cleared

    # ------------------------------------------------------
    # Flag history
    # ------------------------------------------------------

    def flag_history(self, limit=None):
        with self._lock:
            history = list(self._flag_history)

            if limit is not None:
                if limit < 0:
                    raise ValueError(
                        "limit must be >= 0"
                    )

                history = history[-limit:]

            return [record.copy() for record in history]

    # ------------------------------------------------------
    # Status
    # ------------------------------------------------------

    def status(self):
        with self._lock:
            return {
                "node_id": self.node_id,
                "name": self.name,
                "role": self.role,
                "version": self.version,
                "active": self.active,
                "event_bus_bound": (
                    self._event_bus is not None
                ),
                "check_count": self._check_count,
                "flag_count": self._flag_count,
                "flags": sorted(self._flagged),
                "last_check": self._last_check,
                "last_flag": self._last_flag,
            }

    # ------------------------------------------------------
    # Health
    # ------------------------------------------------------

    def health(self):
        with self._lock:
            if self.failed:
                state = "FAILED"
            elif self._event_bus is None:
                state = "DEGRADED"
            elif self.active:
                state = "HEALTHY"
            else:
                state = "STOPPED"

            return {
                "state": state,
                "active": self.active,
                "event_bus_bound": (
                    self._event_bus is not None
                ),
                "flag_count": self._flag_count,
                "timestamp": time.time(),
            }

    # ------------------------------------------------------
    # Representation
    # ------------------------------------------------------

    def __repr__(self):
        with self._lock:
            return (
                f"<InvariantGuard "
                f"name={self.name!r} "
                f"active={self.active} "
                f"flags={len(self._flagged)}>"
            )