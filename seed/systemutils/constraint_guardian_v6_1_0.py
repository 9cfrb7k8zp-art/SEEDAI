# ==========================================================
# FILE: constraint_guardian.py
# PATH: SEED_ROOT/seed/systemutils/constraint_guardian.py
#
# VERSION: 6.1.0
# BUILD: BOOT-SAFE / RUNTIME-GOVERNOR / QBIT-AWARE / LOAD-AWARE
# UPDATED: 2026-08-17
#
# PURPOSE:
# - Protect SEED runtime from CPU / memory saturation
# - Monitor Qbit/vector pressure
# - Detect sustained resource pressure
# - Gate non-critical background work
# - Defer expensive work during pressure
# - Preserve Qbit and Heartbeat operation
# - Support TimeTravel / skill scanner throttling
# - Remain async-safe
# - Avoid EventBus recursion storms
# - Provide runtime diagnostics
#
# DESIGN:
#
#   Qbit
#      |
#      v
#   ConstraintGuardian
#      |
#      +---- CPU/MEM pressure
#      |
#      +---- Qbit/vector pressure
#      |
#      +---- sustained-pressure detection
#      |
#      +---- workload admission
#      |
#      +---- deferred EventBus notification
#      |
#      v
#   Runtime Governor
#
# IMPORTANT:
# - ConstraintGuardian does NOT stop Qbit
# - ConstraintGuardian does NOT stop Heartbeat
# - ConstraintGuardian does NOT kill threads
# - ConstraintGuardian DOES tell background workloads
#   when they should yield
# ==========================================================

from __future__ import annotations

import asyncio
import inspect
import logging
import threading
import time
from collections import deque
from enum import Enum
from typing import Any, Dict, Optional


logger = logging.getLogger(
    "ConstraintGuardian"
)

logger.setLevel(
    logging.INFO
)


# ==========================================================
# CONSTRAINT STATES
# ==========================================================

class ConstraintState:
    CLEAR = "clear"
    PRESSURE = "pressure"
    WARNING = "warning"
    BLOCK = "block"


# ==========================================================
# WORKLOAD CLASSES
# ==========================================================

class WorkloadClass:
    CRITICAL = "critical"
    NORMAL = "normal"
    BACKGROUND = "background"
    DEFERRED = "deferred"


# ==========================================================
# PRESSURE LEVEL
# ==========================================================

class PressureLevel:
    CLEAR = 0.0
    PRESSURE = 0.3
    WARNING = 0.6
    BLOCK = 0.9


# ==========================================================
# CONSTRAINT GUARDIAN
# ==========================================================

class Constraint_Guardian:

    def __init__(
        self,
        *,
        cpu_limit: float = 85.0,
        mem_limit: float = 92.0,
        event_bus=None,
        limp_mode: bool = False,
        pressure_threshold: float = 0.6,
        block_threshold: float = 0.9,
        cpu_pressure_threshold: float = 0.80,
        cpu_block_threshold: float = 0.95,
        mem_pressure_threshold: float = 0.80,
        mem_block_threshold: float = 0.95,
        sustained_samples: int = 3,
        recovery_samples: int = 4,
        sample_window: int = 8,
        event_cooldown: float = 2.0,
        boot_grace_seconds: float = 45.0,
        boot_cpu_pressure_threshold: float = 0.90,
        boot_cpu_block_threshold: float = 0.98,
        boot_mem_pressure_threshold: float = 0.90,
        boot_mem_block_threshold: float = 0.98,
    ):
        # ------------------------------------------------------
        # Core configuration
        # ------------------------------------------------------

        self.event_bus = event_bus

        self.limp_mode = bool(
            limp_mode
        )

        self.cpu_limit = float(
            cpu_limit
        )

        self.mem_limit = float(
            mem_limit
        )

        self.pressure_threshold = float(
            pressure_threshold
        )

        self.block_threshold = float(
            block_threshold
        )

        # ------------------------------------------------------
        # Runtime pressure thresholds
        # ------------------------------------------------------

        self.cpu_pressure_threshold = float(
            cpu_pressure_threshold
        )

        self.cpu_block_threshold = float(
            cpu_block_threshold
        )

        self.mem_pressure_threshold = float(
            mem_pressure_threshold
        )

        self.mem_block_threshold = float(
            mem_block_threshold
        )

        # ------------------------------------------------------
        # Hysteresis / stability
        # ------------------------------------------------------

        self.sustained_samples = max(
            1,
            int(sustained_samples)
        )

        self.recovery_samples = max(
            1,
            int(recovery_samples)
        )

        self.sample_window = max(
            2,
            int(sample_window)
        )

        self.event_cooldown = max(
            0.0,
            float(event_cooldown)
        )

        # ------------------------------------------------------
        # Lifecycle / boot protection
        # ------------------------------------------------------
        # During early boot the Python process can temporarily use
        # substantially more memory while modules, registries, Qbit
        # components and device services are being constructed.
        # Resource governance remains observable during this period,
        # but it must not immediately escalate normal boot pressure
        # into a runtime BLOCK.
        self.boot_grace_seconds = max(0.0, float(boot_grace_seconds))
        self.boot_cpu_pressure_threshold = max(0.0, min(1.0, float(boot_cpu_pressure_threshold)))
        self.boot_cpu_block_threshold = max(0.0, min(1.0, float(boot_cpu_block_threshold)))
        self.boot_mem_pressure_threshold = max(0.0, min(1.0, float(boot_mem_pressure_threshold)))
        self.boot_mem_block_threshold = max(0.0, min(1.0, float(boot_mem_block_threshold)))

        self._boot_complete = False
        self._shutdown_requested = False
        self._shutdown_reason = None

        # ------------------------------------------------------
        # Async lock
        # ------------------------------------------------------

        self._lock = asyncio.Lock()

        # ------------------------------------------------------
        # Thread-safe state lock
        #
        # check() may be called from normal worker threads.
        # observe() may be called from async code.
        # ------------------------------------------------------

        self._state_lock = threading.RLock()

        # ------------------------------------------------------
        # Resource history
        # ------------------------------------------------------

        self._cpu_history = deque(
            maxlen=self.sample_window
        )

        self._mem_history = deque(
            maxlen=self.sample_window
        )

        self._pressure_history = deque(
            maxlen=self.sample_window
        )

        # ------------------------------------------------------
        # Runtime counters
        # ------------------------------------------------------

        self._pressure_count = 0
        self._recovery_count = 0

        self._total_checks = 0
        self._blocked_work = 0
        self._deferred_work = 0

        self._last_cpu = 0.0
        self._last_mem = 0.0
        self._last_pressure = 0.0

        self._state = (
            ConstraintState.CLEAR
        )

        self._last_state_change = time.monotonic()

        self._last_event_time = 0.0

        self._last_reason = (
            "initialization"
        )

        # ------------------------------------------------------
        # Async event emission guard
        # ------------------------------------------------------

        self._event_pending = False

        # ------------------------------------------------------
        # Startup timestamp
        # ------------------------------------------------------

        self.started_at = time.time()

        logger.info(
            "[ConstraintGuardian] "
            "Initialized | "
            f"cpu_limit={self.cpu_limit}% | "
            f"mem_limit={self.mem_limit}% | "
            f"pressure_threshold={self.pressure_threshold} | "
            f"block_threshold={self.block_threshold} | "
            f"boot_grace={self.boot_grace_seconds}s | "
            f"boot_mem_pressure={self.boot_mem_pressure_threshold:.2f} | "
            f"boot_mem_block={self.boot_mem_block_threshold:.2f}"
        )

    # ==========================================================
    # LIFECYCLE CONTROL
    # ==========================================================

    def is_booting(self) -> bool:
        """Return True while SEED is inside its startup grace period."""
        with self._state_lock:
            if self._shutdown_requested:
                return False
            if self._boot_complete:
                return False
            return (time.time() - self.started_at) < self.boot_grace_seconds

    def is_shutdown_requested(self) -> bool:
        """Return True after shutdown has been requested."""
        with self._state_lock:
            return self._shutdown_requested

    def set_boot_complete(self, complete: bool = True) -> None:
        """Explicitly transition from boot observation to runtime governance."""
        with self._state_lock:
            self._boot_complete = bool(complete)
            if self._boot_complete:
                logger.info(
                    "[ConstraintGuardian] Boot grace complete | runtime governance active"
                )

    def request_shutdown(self, reason: str = "shutdown_requested") -> None:
        """Put the guardian into passive shutdown mode immediately."""
        with self._state_lock:
            self._shutdown_requested = True
            self._shutdown_reason = str(reason)
            self._pressure_count = 0
            self._recovery_count = 0
            self._state = ConstraintState.CLEAR
            self._last_reason = "shutdown:" + str(reason)
            self._last_state_change = time.monotonic()

        logger.info(
            "[ConstraintGuardian] Shutdown requested | "
            f"reason={reason} | governor=PASSIVE"
        )

    def shutdown(self, reason: str = "shutdown_requested") -> None:
        """Compatibility alias used by shutdown controllers."""
        self.request_shutdown(reason)

    def resume_runtime(self) -> None:
        """Resume normal monitoring after an intentional restart/restart cycle."""
        with self._state_lock:
            self._shutdown_requested = False
            self._shutdown_reason = None
            self._boot_complete = True
            self._pressure_count = 0
            self._recovery_count = 0
            self._state = ConstraintState.CLEAR
            self._last_reason = "runtime_resumed"
            self._last_state_change = time.monotonic()

        logger.info("[ConstraintGuardian] Runtime governance resumed")

    # ==========================================================
    # ENTRY POINT — QBIT OBSERVATION
    # ==========================================================

    async def observe(
        self,
        qbit,
    ) -> ConstraintState:

        if self.is_shutdown_requested():
            return ConstraintState.CLEAR

        if self.limp_mode:

            return ConstraintState.CLEAR

        if qbit is None:

            return ConstraintState.CLEAR

        async with self._lock:

            with self._state_lock:

                state = self._evaluate(
                    qbit
                )

                self._record_state(
                    state
                )

                self._emit_state(
                    qbit,
                    state
                )

                return state

    # ==========================================================
    # RESOURCE CHECK
    # ==========================================================

    def check(
        self,
        cpu: float,
        mem: float,
    ) -> bool:

        with self._state_lock:

            self._total_checks += 1

            # Shutdown is authoritative. Do not keep evaluating pressure,
            # emitting warnings, or driving downstream governors after the
            # main process has begun its shutdown sequence.
            if self._shutdown_requested:
                self._last_reason = "shutdown_passive"
                self._state = ConstraintState.CLEAR
                return True

            try:
                cpu = float(cpu)
            except Exception:
                cpu = 0.0

            try:
                mem = float(mem)
            except Exception:
                mem = 0.0

            cpu = max(
                0.0,
                min(cpu, 100.0)
            )

            mem = max(
                0.0,
                min(mem, 100.0)
            )

            self._last_cpu = cpu
            self._last_mem = mem

            self._cpu_history.append(
                cpu
            )

            self._mem_history.append(
                mem
            )

            # --------------------------------------------------
            # Determine resource pressure
            # --------------------------------------------------

            pressure = self._resource_pressure(
                cpu,
                mem
            )

            self._last_pressure = pressure

            self._pressure_history.append(
                pressure
            )

            # --------------------------------------------------
            # Determine resource state
            # --------------------------------------------------

            state, reason = (
                self._resource_state(
                    cpu,
                    mem,
                    pressure
                )
            )

            self._last_reason = reason

            self._record_state(
                state
            )

            # --------------------------------------------------
            # Log only meaningful transitions or hard pressure.
            #
            # This prevents a warning every 500ms from becoming
            # another source of CPU pressure.
            # --------------------------------------------------

            if state in (
                ConstraintState.WARNING,
                ConstraintState.BLOCK,
            ):

                if self._should_log_state(
                    state
                ):

                    logger.warning(
                        "[ConstraintGuardian] "
                        f"Limits exceeded: "
                        f"CPU={cpu:.1f}%, "
                        f"MEM={mem:.1f}%, "
                        f"state={state}, "
                        f"pressure={pressure:.2f}, "
                        f"reason={reason}"
                    )

            return state not in (
                ConstraintState.WARNING,
                ConstraintState.BLOCK,
            )

    # ==========================================================
    # RESOURCE PRESSURE
    # ==========================================================

    def _resource_pressure(
        self,
        cpu: float,
        mem: float,
    ) -> float:

        cpu_ratio = (
            cpu / 100.0
        )

        mem_ratio = (
            mem / 100.0
        )

        pressure = max(
            cpu_ratio,
            mem_ratio
        )

        # ------------------------------------------------------
        # Add a small overload factor when configured limits
        # are exceeded.
        # ------------------------------------------------------

        if cpu > self.cpu_limit:

            pressure += min(
                (cpu - self.cpu_limit)
                / 100.0,
                0.15
            )

        if mem > self.mem_limit:

            pressure += min(
                (mem - self.mem_limit)
                / 100.0,
                0.15
            )

        return max(
            0.0,
            min(
                pressure,
                1.0
            )
        )

    # ==========================================================
    # RESOURCE STATE
    # ==========================================================

    def _resource_state(
        self,
        cpu: float,
        mem: float,
        pressure: float,
    ):

        # ------------------------------------------------------
        # Boot-safe thresholds
        # ------------------------------------------------------
        # Boot pressure is still measured, but escalation is delayed
        # until the startup grace period expires. This prevents large
        # imports/module construction from triggering LimpMode during
        # normal initialization.
        booting = (
            not self._boot_complete
            and (time.time() - self.started_at) < self.boot_grace_seconds
        )

        if booting:
            if (
                cpu >= self.boot_cpu_block_threshold * 100.0
                or mem >= self.boot_mem_block_threshold * 100.0
            ):
                # Even during boot, extreme pressure is meaningful. Keep
                # this at WARNING rather than BLOCK so boot-critical work
                # is not deadlocked by the governor.
                return (
                    ConstraintState.WARNING,
                    "boot_resource_warning"
                )

            if (
                cpu >= self.boot_cpu_pressure_threshold * 100.0
                or mem >= self.boot_mem_pressure_threshold * 100.0
            ):
                return (
                    ConstraintState.PRESSURE,
                    "boot_resource_pressure"
                )

            if pressure >= self.pressure_threshold:
                return (
                    ConstraintState.PRESSURE,
                    "boot_resource_pressure"
                )

            return (
                ConstraintState.CLEAR,
                "boot_resource_clear"
            )

        if (
            cpu >= self.cpu_block_threshold * 100.0
            or mem >= self.mem_block_threshold * 100.0
        ):

            return (
                ConstraintState.BLOCK,
                "resource_block"
            )

        if (
            cpu >= self.cpu_pressure_threshold * 100.0
            or mem >= self.mem_pressure_threshold * 100.0
        ):

            return (
                ConstraintState.WARNING,
                "resource_warning"
            )

        if (
            pressure >= self.pressure_threshold
        ):

            return (
                ConstraintState.PRESSURE,
                "resource_pressure"
            )

        return (
            ConstraintState.CLEAR,
            "resource_clear"
        )

    # ==========================================================
    # QBIT EVALUATION
    # ==========================================================

    def _evaluate(
        self,
        qbit,
    ) -> ConstraintState:

        pressure = 0.0

        # ------------------------------------------------------
        # Flags
        # ------------------------------------------------------

        flags = getattr(
            qbit,
            "flags",
            {}
        )

        if flags:

            try:

                pressure += min(
                    len(flags) * 0.15,
                    0.4
                )

            except Exception:
                pressure += 0.1

        # ------------------------------------------------------
        # Payload
        # ------------------------------------------------------

        payload = getattr(
            qbit,
            "payload",
            None
        )

        if payload is not None:

            pressure += (
                self._payload_risk(
                    payload
                )
            )

        # ------------------------------------------------------
        # State / vector imbalance
        # ------------------------------------------------------

        state = getattr(
            qbit,
            "state",
            None
        )

        if state:

            try:

                a, b = state

                imbalance = abs(
                    abs(a) - abs(b)
                )

                pressure += min(
                    imbalance,
                    0.3
                )

            except Exception:

                pressure += 0.2

        # ------------------------------------------------------
        # Resource pressure contributes to Qbit pressure.
        # ------------------------------------------------------

        pressure += min(
            self._last_pressure * 0.35,
            0.35
        )

        pressure = min(
            pressure,
            1.0
        )

        self._last_pressure = pressure

        # ------------------------------------------------------
        # State
        # ------------------------------------------------------

        if pressure >= self.block_threshold:

            return ConstraintState.BLOCK

        if pressure >= self.pressure_threshold:

            return ConstraintState.WARNING

        if pressure >= 0.3:

            return ConstraintState.PRESSURE

        return ConstraintState.CLEAR

    # ==========================================================
    # PAYLOAD RISK
    # ==========================================================

    def _payload_risk(
        self,
        payload: Any,
    ) -> float:

        try:

            if isinstance(
                payload,
                dict,
            ):

                return min(
                    len(payload) * 0.05,
                    0.3
                )

            if isinstance(
                payload,
                (list, tuple),
            ):

                return min(
                    len(payload) * 0.03,
                    0.25
                )

            if isinstance(
                payload,
                str,
            ):

                return min(
                    len(payload) / 500.0,
                    0.2
                )

        except Exception:

            return 0.1

        return 0.0

    # ==========================================================
    # STATE RECORDING
    # ==========================================================

    def _record_state(
        self,
        state: ConstraintState,
    ):

        previous = self._state

        # ------------------------------------------------------
        # Sustained pressure tracking
        # ------------------------------------------------------

        if state in (
            ConstraintState.WARNING,
            ConstraintState.BLOCK,
        ):

            self._pressure_count += 1
            self._recovery_count = 0

        elif state == ConstraintState.CLEAR:

            self._recovery_count += 1

            if (
                self._recovery_count
                >= self.recovery_samples
            ):

                self._pressure_count = 0

        else:

            self._recovery_count = 0

        # ------------------------------------------------------
        # State transition
        # ------------------------------------------------------

        if state != previous:

            self._state = state

            self._last_state_change = (
                time.monotonic()
            )

            logger.info(
                "[ConstraintGuardian] "
                f"State transition: "
                f"{previous} -> {state}"
            )

    # ==========================================================
    # SUSTAINED PRESSURE
    # ==========================================================

    def is_sustained_pressure(
        self,
    ) -> bool:

        with self._state_lock:

            return (
                self._pressure_count
                >= self.sustained_samples
            )

    # ==========================================================
    # WORKLOAD ADMISSION
    #
    # This is the main runtime-governor interface.
    #
    # Critical:
    #   Always allowed.
    #
    # Normal:
    #   Allowed unless hard block.
    #
    # Background:
    #   Deferred during sustained warning/block.
    #
    # Deferred:
    #   Only allowed when clear.
    # ==========================================================

    def allow_work(
        self,
        workload: str = WorkloadClass.NORMAL,
    ) -> bool:

        with self._state_lock:

            state = self._state

            # --------------------------------------------------
            # Shutdown is passive for governance. Critical shutdown
            # work remains admissible; background work should naturally
            # stop rather than being revived by the governor.
            # --------------------------------------------------
            if self._shutdown_requested:
                if workload == WorkloadClass.CRITICAL:
                    return True
                self._deferred_work += 1
                return False

            # --------------------------------------------------
            # Boot grace: do not gate normal/background initialization.
            # This is intentionally separate from resource measurement.
            # --------------------------------------------------
            if self.is_booting():
                return True

            # --------------------------------------------------
            # Critical work is always allowed.
            #
            # This protects:
            # - Heartbeat
            # - Qbit control
            # - shutdown
            # - safety
            # --------------------------------------------------

            if workload == WorkloadClass.CRITICAL:

                return True

            # --------------------------------------------------
            # Deferred work only runs when clear.
            # --------------------------------------------------

            if workload == WorkloadClass.DEFERRED:

                allowed = (
                    state
                    == ConstraintState.CLEAR
                )

                if not allowed:

                    self._deferred_work += 1

                return allowed

            # --------------------------------------------------
            # Background work yields during sustained pressure.
            # --------------------------------------------------

            if workload == WorkloadClass.BACKGROUND:

                if (
                    state
                    in (
                        ConstraintState.WARNING,
                        ConstraintState.BLOCK,
                    )
                    and self.is_sustained_pressure()
                ):

                    self._deferred_work += 1

                    return False

                return True

            # --------------------------------------------------
            # Normal work is blocked only during hard block.
            # --------------------------------------------------

            if workload == WorkloadClass.NORMAL:

                if state == ConstraintState.BLOCK:

                    self._blocked_work += 1

                    return False

                return True

            # --------------------------------------------------
            # Unknown workload classes are conservative.
            # --------------------------------------------------

            self._blocked_work += 1

            return False

    # ==========================================================
    # BACKGROUND ALIAS
    # ==========================================================

    def allow_background_work(
        self,
    ) -> bool:

        return self.allow_work(
            WorkloadClass.BACKGROUND
        )

    # ==========================================================
    # DEFERRED ALIAS
    # ==========================================================

    def allow_deferred_work(
        self,
    ) -> bool:

        return self.allow_work(
            WorkloadClass.DEFERRED
        )

    # ==========================================================
    # CRITICAL ALIAS
    # ==========================================================

    def allow_critical_work(
        self,
    ) -> bool:

        return True

    # ==========================================================
    # SAFE EVENT EMISSION
    # ==========================================================

    def _emit_state(
        self,
        qbit,
        state: ConstraintState,
    ) -> None:

        if self.event_bus is None:

            return

        now = time.monotonic()

        # ------------------------------------------------------
        # Prevent EventBus storms.
        # ------------------------------------------------------

        if (
            now - self._last_event_time
            < self.event_cooldown
        ):

            return

        self._last_event_time = now

        try:

            track = getattr(
                qbit,
                "track",
                {}
            )

            if not isinstance(
                track,
                dict,
            ):

                track = {}

            payload = {
                "state": state,
                "track_id": track.get(
                    "track_id"
                ),
                "flags": getattr(
                    qbit,
                    "flags",
                    {},
                ),
                "cpu": self._last_cpu,
                "mem": self._last_mem,
                "pressure": self._last_pressure,
                "sustained": (
                    self.is_sustained_pressure()
                ),
                "timestamp": time.time(),
                "source": "ConstraintGuardian",
            }

            publisher = getattr(
                self.event_bus,
                "publish",
                None,
            )

            if not callable(
                publisher
            ):

                return

            result = publisher(
                "CONSTRAINT_STATE",
                payload=payload,
                source="ConstraintGuardian",
            )

            # --------------------------------------------------
            # Support async EventBus publishers without
            # blocking this monitor.
            # --------------------------------------------------

            if inspect.isawaitable(
                result
            ):

                try:

                    loop = asyncio.get_running_loop()

                    loop.create_task(
                        result
                    )

                except RuntimeError:

                    # No running event loop.
                    # Do not create a new one here.
                    pass

        except Exception as exc:

            logger.debug(
                "[ConstraintGuardian] "
                f"emit failed: {exc}"
            )

    # ==========================================================
    # LOG THROTTLING
    # ==========================================================

    def _should_log_state(
        self,
        state: ConstraintState,
    ) -> bool:

        now = time.monotonic()

        # ------------------------------------------------------
        # State transitions should always be visible.
        # ------------------------------------------------------

        if state != self._state:

            return True

        # ------------------------------------------------------
        # Otherwise throttle repeated warnings.
        # ------------------------------------------------------

        return (
            now - self._last_state_change
            >= self.event_cooldown
        )

    # ==========================================================
    # STATE QUERY
    # ==========================================================

    def get_state(
        self,
    ) -> ConstraintState:

        with self._state_lock:

            return self._state

    # ==========================================================
    # PRESSURE QUERY
    # ==========================================================

    def get_pressure(
        self,
    ) -> float:

        with self._state_lock:

            return self._last_pressure

    # ==========================================================
    # RESOURCE QUERY
    # ==========================================================

    def get_resources(
        self,
    ) -> Dict[str, Any]:

        with self._state_lock:

            return {
                "cpu": self._last_cpu,
                "memory": self._last_mem,
                "pressure": self._last_pressure,
                "state": self._state,
                "sustained": (
                    self.is_sustained_pressure()
                ),
            }

    # ==========================================================
    # DIAGNOSTICS
    # ==========================================================

    def diagnostics(
        self,
    ) -> Dict[str, Any]:

        with self._state_lock:

            uptime = (
                time.time()
                - self.started_at
            )

            return {
                "state": self._state,
                "cpu": round(
                    self._last_cpu,
                    2
                ),
                "memory": round(
                    self._last_mem,
                    2
                ),
                "pressure": round(
                    self._last_pressure,
                    3
                ),
                "sustained_pressure": (
                    self.is_sustained_pressure()
                ),
                "pressure_samples": (
                    self._pressure_count
                ),
                "recovery_samples": (
                    self._recovery_count
                ),
                "total_checks": (
                    self._total_checks
                ),
                "blocked_work": (
                    self._blocked_work
                ),
                "deferred_work": (
                    self._deferred_work
                ),
                "uptime": round(
                    uptime,
                    2
                ),
                "limp_mode": (
                    self.limp_mode
                ),
                "boot_complete": self._boot_complete,
                "booting": self.is_booting(),
                "boot_grace_seconds": self.boot_grace_seconds,
                "shutdown_requested": self._shutdown_requested,
                "shutdown_reason": self._shutdown_reason,
                "cpu_limit": (
                    self.cpu_limit
                ),
                "memory_limit": (
                    self.mem_limit
                ),
                "last_reason": (
                    self._last_reason
                ),
            }

    # ==========================================================
    # RESET
    # ==========================================================

    def reset_pressure(
        self,
    ) -> None:

        with self._state_lock:

            self._pressure_count = 0
            self._recovery_count = 0

            self._cpu_history.clear()
            self._mem_history.clear()
            self._pressure_history.clear()

            self._last_pressure = 0.0

            self._state = (
                ConstraintState.CLEAR
            )

            self._last_reason = (
                "manual_reset"
            )

            self._last_state_change = (
                time.monotonic()
            )

            logger.info(
                "[ConstraintGuardian] "
                "Pressure state reset"
            )

    # ==========================================================
    # REPRESENTATION
    # ==========================================================

    def __repr__(
        self,
    ):

        return (
            "Constraint_Guardian("
            f"cpu_limit={self.cpu_limit}, "
            f"mem_limit={self.mem_limit}, "
            f"pressure_threshold="
            f"{self.pressure_threshold}, "
            f"block_threshold="
            f"{self.block_threshold}, "
            f"state={self._state}, "
            f"boot_complete={self._boot_complete}, "
            f"shutdown_requested={self._shutdown_requested}"
            ")"
        )


# ==========================================================
# COMPATIBILITY ALIAS
# ==========================================================

ConstraintGuardian = Constraint_Guardian


# ==========================================================
# MODULE EXPORTS
# ==========================================================

__all__ = [
    "ConstraintState",
    "WorkloadClass",
    "PressureLevel",
    "Constraint_Guardian",
    "ConstraintGuardian",
]
