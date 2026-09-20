# ==========================================================
# FILE: constraint_guardian.py
# PATH: SEED_ROOT/seed/systemutils/constraint_guardian.py
#
# SYSTEM: SEED AI OS
# COMPONENT: ConstraintGuardian
# VERSION: 8.0.0
# BUILD: CAUSAL-ATTRIBUTION / BOOT-GATED / HYSTERESIS /
#        RESOURCE-GOVERNOR / WORKLOAD-TRACE / PASSIVE
# UPDATED: 2026-08-18
#
# PURPOSE:
# ----------------------------------------------------------
# ConstraintGuardian is the SEED runtime constraint observer
# and admission governor.
#
# VERSION 8 changes the primary purpose from:
#
#       "CPU/MEMORY IS HIGH"
#
# to:
#
#       "THIS WORK, FROM THIS SOURCE, CAUSED/COINCIDED WITH
#        THIS RESOURCE PRESSURE, AND THIS WAS THE DECISION."
#
# The Guardian now records:
#
#   WHAT:
#       resource / qbit / workload / state transition
#
#   WHERE:
#       module / component / subsystem
#
#   WHY:
#       threshold / pressure cause / transition reason
#
#   WHO:
#       source component
#
#   WHICH WORK:
#       operation / workload class / task
#
#   TRACK:
#       track_id / channel_id / parent_id when supplied
#
#   EFFECT:
#       admitted / deferred / blocked
#
#   WHEN:
#       timestamp / duration / transition age
#
# IMPORTANT:
# ----------------------------------------------------------
# ConstraintGuardian remains PASSIVE.
#
# It DOES:
#
#   - observe resources
#   - record causal context
#   - calculate resource pressure
#   - calculate Qbit pressure separately
#   - maintain hysteresis
#   - admit/reject/defer work
#   - emit compact diagnostic events
#   - preserve causal history
#
# It DOES NOT:
#
#   - start threads
#   - create worker tasks
#   - create event loops
#   - start subsystems
#   - stop Qbit
#   - stop Heartbeat
#   - kill threads
#   - restart workloads
#   - execute commands
#   - modify actuator channels
#
# AUTHORITY:
#
#       SEED BOOT
#          |
#          v
#   ConstraintGuardian
#          |
#          +---- observation
#          +---- attribution
#          +---- admission
#          |
#          v
#     runtime workload
#
# ==========================================================

from __future__ import annotations

import asyncio
import inspect
import logging
import threading
import time
from collections import Counter, deque
from typing import Any, Dict, Optional


logger = logging.getLogger("ConstraintGuardian")
logger.setLevel(logging.INFO)

if not logger.handlers:
    logger.addHandler(logging.NullHandler())


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
# PRESSURE LEVELS
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

    VERSION = "8.0.0"
    NAME = "ConstraintGuardian"

    def __init__(
        self,
        *,
        cpu_limit: float = 85.0,
        mem_limit: float = 92.0,
        event_bus=None,
        limp_mode: bool = False,

        pressure_threshold: float = 0.60,
        block_threshold: float = 0.90,

        cpu_pressure_threshold: float = 0.80,
        cpu_block_threshold: float = 0.95,

        mem_pressure_threshold: float = 0.80,
        mem_block_threshold: float = 0.95,

        sustained_samples: int = 3,
        recovery_samples: int = 4,
        sample_window: int = 16,

        event_cooldown: float = 2.0,

        transition_dwell_seconds: float = 2.0,
        block_recovery_seconds: float = 5.0,
        recovery_pressure_margin: float = 0.10,

        boot_grace_seconds: float = 45.0,

        boot_cpu_pressure_threshold: float = 0.90,
        boot_cpu_block_threshold: float = 0.98,

        boot_mem_pressure_threshold: float = 0.90,
        boot_mem_block_threshold: float = 0.98,

        # --------------------------------------------------
        # Causal history.
        # --------------------------------------------------
        causal_history_size: int = 100,

    ):

        # ==================================================
        # CORE
        # ==================================================

        self.event_bus = event_bus
        self.limp_mode = bool(limp_mode)

        self.cpu_limit = float(cpu_limit)
        self.mem_limit = float(mem_limit)

        self.pressure_threshold = float(
            pressure_threshold
        )

        self.block_threshold = float(
            block_threshold
        )

        # ==================================================
        # RESOURCE THRESHOLDS
        # ==================================================

        self.cpu_pressure_threshold = max(
            0.0,
            min(
                1.0,
                float(cpu_pressure_threshold),
            ),
        )

        self.cpu_block_threshold = max(
            0.0,
            min(
                1.0,
                float(cpu_block_threshold),
            ),
        )

        self.mem_pressure_threshold = max(
            0.0,
            min(
                1.0,
                float(mem_pressure_threshold),
            ),
        )

        self.mem_block_threshold = max(
            0.0,
            min(
                1.0,
                float(mem_block_threshold),
            ),
        )

        # ==================================================
        # HYSTERESIS
        # ==================================================

        self.sustained_samples = max(
            1,
            int(sustained_samples),
        )

        self.recovery_samples = max(
            1,
            int(recovery_samples),
        )

        self.sample_window = max(
            2,
            int(sample_window),
        )

        self.event_cooldown = max(
            0.0,
            float(event_cooldown),
        )

        self.transition_dwell_seconds = max(
            0.0,
            float(transition_dwell_seconds),
        )

        self.block_recovery_seconds = max(
            0.0,
            float(block_recovery_seconds),
        )

        self.recovery_pressure_margin = max(
            0.0,
            min(
                0.5,
                float(recovery_pressure_margin),
            ),
        )

        # ==================================================
        # BOOT
        # ==================================================

        self.boot_grace_seconds = max(
            0.0,
            float(boot_grace_seconds),
        )

        self.boot_cpu_pressure_threshold = max(
            0.0,
            min(
                1.0,
                float(boot_cpu_pressure_threshold),
            ),
        )

        self.boot_cpu_block_threshold = max(
            0.0,
            min(
                1.0,
                float(boot_cpu_block_threshold),
            ),
        )

        self.boot_mem_pressure_threshold = max(
            0.0,
            min(
                1.0,
                float(boot_mem_pressure_threshold),
            ),
        )

        self.boot_mem_block_threshold = max(
            0.0,
            min(
                1.0,
                float(boot_mem_block_threshold),
            ),
        )

        # ==================================================
        # CAUSAL HISTORY
        # ==================================================

        self.causal_history_size = max(
            10,
            int(causal_history_size),
        )

        self._causal_history = deque(
            maxlen=self.causal_history_size
        )

        self._active_context = {
            "source": None,
            "module": None,
            "component": None,
            "operation": None,
            "workload": WorkloadClass.NORMAL,
            "track_id": None,
            "channel_id": None,
            "parent_id": None,
            "task_id": None,
        }

        self._last_cause = None
        self._last_decision = None

        self._cause_counts = Counter()
        self._source_counts = Counter()
        self._operation_counts = Counter()

        # ==================================================
        # LIFECYCLE
        # ==================================================

        self._boot_complete = False
        self._shutdown_requested = False
        self._shutdown_reason = None

        self.started_at = time.time()

        # ==================================================
        # LOCKS
        # ==================================================

        self._lock = asyncio.Lock()
        self._state_lock = threading.RLock()

        # ==================================================
        # RESOURCE HISTORY
        # ==================================================

        self._cpu_history = deque(
            maxlen=self.sample_window
        )

        self._mem_history = deque(
            maxlen=self.sample_window
        )

        self._pressure_history = deque(
            maxlen=self.sample_window
        )

        # ==================================================
        # RUNTIME COUNTERS
        # ==================================================

        self._pressure_count = 0
        self._recovery_count = 0

        self._total_checks = 0
        self._blocked_work = 0
        self._deferred_work = 0
        self._allowed_work = 0

        # ==================================================
        # LAST RESOURCE VALUES
        # ==================================================

        self._last_cpu = 0.0
        self._last_mem = 0.0
        self._last_pressure = 0.0

        # ==================================================
        # SEPARATE QBIT PRESSURE
        # ==================================================
        #
        # IMPORTANT:
        #
        # Qbit complexity does NOT directly manufacture
        # CPU/memory pressure anymore.
        #
        # It is tracked independently so we can answer:
        #
        #   "Was the Qbit itself under pressure?"
        #
        # versus:
        #
        #   "Was the machine actually under pressure?"
        #
        # ==================================================

        self._qbit_pressure = 0.0
        self._qbit_reason = "none"

        # ==================================================
        # STATE
        # ==================================================

        self._state = ConstraintState.CLEAR

        self._last_state_change = (
            time.monotonic()
        )

        self._candidate_state = (
            ConstraintState.CLEAR
        )

        self._candidate_since = (
            time.monotonic()
        )

        self._last_reason = "initialization"

        # ==================================================
        # EVENT CONTROL
        # ==================================================

        self._last_event_time = 0.0
        self._last_emitted_state = None

        # ==================================================
        # COUNTERS
        # ==================================================

        self._observation_count = 0

        logger.info(
            "[ConstraintGuardian] Initialized | "
            f"version={self.VERSION} | "
            f"cpu_limit={self.cpu_limit}% | "
            f"mem_limit={self.mem_limit}% | "
            f"boot_grace={self.boot_grace_seconds:.1f}s | "
            "causal_tracking=enabled"
        )

    # ==========================================================
    # CONTEXT / ATTRIBUTION
    # ==========================================================

    def set_context(
        self,
        *,
        source=None,
        module=None,
        component=None,
        operation=None,
        workload=None,
        track_id=None,
        channel_id=None,
        parent_id=None,
        task_id=None,
        **extra,
    ) -> Dict[str, Any]:
       

        with self._state_lock:

            context = {
                "source": source,
                "module": module,
                "component": component,
                "operation": operation,
                "workload": (
                    workload
                    if workload is not None
                    else WorkloadClass.NORMAL
                ),
                "track_id": track_id,
                "channel_id": channel_id,
                "parent_id": parent_id,
                "task_id": task_id,
            }

            if extra:
                context.update(extra)

            self._active_context = context

            return dict(context)

    # ----------------------------------------------------------

    def clear_context(self) -> None:

        with self._state_lock:

            self._active_context = {
                "source": None,
                "module": None,
                "component": None,
                "operation": None,
                "workload": WorkloadClass.NORMAL,
                "track_id": None,
                "channel_id": None,
                "parent_id": None,
                "task_id": None,
            }

    # ----------------------------------------------------------

    def get_context(self) -> Dict[str, Any]:

        with self._state_lock:
            return dict(
                self._active_context
            )

    # ----------------------------------------------------------

    def _resolve_context(
        self,
        context=None,
        **overrides,
    ) -> Dict[str, Any]:

        with self._state_lock:

            resolved = dict(
                self._active_context
            )

        if isinstance(
            context,
            dict,
        ):
            resolved.update(context)

        for key, value in overrides.items():

            if value is not None:
                resolved[key] = value

        return resolved

    # ==========================================================
    # LIFECYCLE
    # ==========================================================

    def is_booting(self) -> bool:

        with self._state_lock:

            if self._shutdown_requested:
                return False

            if self._boot_complete:
                return False

            return (
                time.time() - self.started_at
                < self.boot_grace_seconds
            )

    # ----------------------------------------------------------

    def is_shutdown_requested(self) -> bool:

        with self._state_lock:
            return self._shutdown_requested

    # ----------------------------------------------------------

    def set_boot_complete(
        self,
        complete: bool = True,
    ) -> None:

        with self._state_lock:

            self._boot_complete = bool(
                complete
            )

        if complete:

            logger.info(
                "[ConstraintGuardian] "
                "Boot complete | "
                "runtime governance active"
            )

    # ----------------------------------------------------------

    def request_shutdown(
        self,
        reason: str = "shutdown_requested",
    ) -> None:

        with self._state_lock:

            self._shutdown_requested = True
            self._shutdown_reason = str(
                reason
            )

            self._pressure_count = 0
            self._recovery_count = 0

            self._state = (
                ConstraintState.CLEAR
            )

            self._candidate_state = (
                ConstraintState.CLEAR
            )

            self._last_reason = (
                "shutdown:" + str(reason)
            )

            now = time.monotonic()

            self._last_state_change = now
            self._candidate_since = now

        logger.info(
            "[ConstraintGuardian] "
            f"Shutdown requested | reason={reason}"
        )

    # ----------------------------------------------------------

    def shutdown(
        self,
        reason: str = "shutdown_requested",
    ) -> None:

        self.request_shutdown(
            reason
        )

    # ----------------------------------------------------------

    def resume_runtime(self) -> None:

        with self._state_lock:

            self._shutdown_requested = False
            self._shutdown_reason = None
            self._boot_complete = True

            self._pressure_count = 0
            self._recovery_count = 0

            self._state = (
                ConstraintState.CLEAR
            )

            self._candidate_state = (
                ConstraintState.CLEAR
            )

            self._last_reason = (
                "runtime_resumed"
            )

            now = time.monotonic()

            self._last_state_change = now
            self._candidate_since = now

        logger.info(
            "[ConstraintGuardian] "
            "Runtime governance resumed"
        )

    # ==========================================================
    # RESOURCE CHECK
    # ==========================================================

    def check(
        self,
        cpu: float,
        mem: float,
        *,
        context=None,
        source=None,
        module=None,
        component=None,
        operation=None,
        workload=None,
        track_id=None,
        channel_id=None,
        parent_id=None,
        task_id=None,
    ) -> bool:
        

        with self._state_lock:

            self._total_checks += 1

            resolved_context = self._resolve_context(
                context,
                source=source,
                module=module,
                component=component,
                operation=operation,
                workload=workload,
                track_id=track_id,
                channel_id=channel_id,
                parent_id=parent_id,
                task_id=task_id,
            )

            # ------------------------------------------------
            # SHUTDOWN
            # ------------------------------------------------

            if self._shutdown_requested:

                self._last_reason = (
                    "shutdown_passive"
                )

                self._state = (
                    ConstraintState.CLEAR
                )

                self._record_causal_event(
                    event_type="resource_check",
                    context=resolved_context,
                    cause="shutdown_passive",
                    decision="allowed"
                    if resolved_context.get(
                        "workload"
                    ) == WorkloadClass.CRITICAL
                    else "deferred",
                )

                return (
                    resolved_context.get(
                        "workload"
                    )
                    == WorkloadClass.CRITICAL
                )

            # ------------------------------------------------
            # SANITIZE
            # ------------------------------------------------

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
                min(cpu, 100.0),
            )

            mem = max(
                0.0,
                min(mem, 100.0),
            )

            self._last_cpu = cpu
            self._last_mem = mem

            self._cpu_history.append(cpu)
            self._mem_history.append(mem)

            # ------------------------------------------------
            # RESOURCE PRESSURE
            # ------------------------------------------------

            pressure = self._resource_pressure(
                cpu,
                mem,
            )

            self._last_pressure = pressure

            self._pressure_history.append(
                pressure
            )

            # ------------------------------------------------
            # RESOURCE STATE
            # ------------------------------------------------

            desired_state, reason = (
                self._resource_state(
                    cpu,
                    mem,
                    pressure,
                )
            )

            previous_state = self._state

            self._last_reason = reason

            effective_state = (
                self._apply_state_hysteresis(
                    desired_state
                )
            )

            self._record_counters(
                effective_state
            )

            # ------------------------------------------------
            # DETERMINE CAUSE
            # ------------------------------------------------

            cause = self._determine_resource_cause(
                cpu=cpu,
                mem=mem,
                pressure=pressure,
                desired_state=desired_state,
                effective_state=effective_state,
                reason=reason,
            )

            # ------------------------------------------------
            # Record causal observation.
            # ------------------------------------------------

            decision = self._admission_decision(
                resolved_context.get(
                    "workload",
                    WorkloadClass.NORMAL,
                ),
                effective_state,
            )

            self._record_causal_event(
                event_type="resource_check",
                context=resolved_context,
                cause=cause,
                decision=decision,
                previous_state=previous_state,
                desired_state=desired_state,
                state=effective_state,
            )

            # ------------------------------------------------
            # Log useful information, not just numbers.
            # ------------------------------------------------

            if effective_state in (
                ConstraintState.PRESSURE,
                ConstraintState.WARNING,
                ConstraintState.BLOCK,
            ):

                if self._should_log_state(
                    effective_state
                ):

                    logger.warning(
                        "[ConstraintGuardian] "
                        f"RESOURCE PRESSURE | "
                        f"state={effective_state} | "
                        f"cause={cause} | "
                        f"cpu={cpu:.1f}% | "
                        f"mem={mem:.1f}% | "
                        f"pressure={pressure:.2f} | "
                        f"source="
                        f"{resolved_context.get('source')} | "
                        f"module="
                        f"{resolved_context.get('module')} | "
                        f"operation="
                        f"{resolved_context.get('operation')} | "
                        f"track_id="
                        f"{resolved_context.get('track_id')}"
                    )

            return decision in (
                "allowed",
                "critical_allowed",
            )

    # ==========================================================
    # RESOURCE PRESSURE
    # ==========================================================

    def _resource_pressure(
        self,
        cpu: float,
        mem: float,
    ) -> float:
   
        # ------------------------------------------------------
        # Sanitize inputs.
        # ------------------------------------------------------

        try:
            cpu = float(cpu)
        except (TypeError, ValueError):
            cpu = 0.0

        try:
            mem = float(mem)
        except (TypeError, ValueError):
            mem = 0.0

        cpu = max(
            0.0,
            min(cpu, 100.0),
        )

        mem = max(
            0.0,
            min(mem, 100.0),
        )

        # ------------------------------------------------------
        # Convert configured thresholds to percentages.
        # ------------------------------------------------------

        cpu_threshold = (
            self.cpu_pressure_threshold * 100.0
        )

        mem_threshold = (
            self.mem_pressure_threshold * 100.0
        )

        # ------------------------------------------------------
        # Calculate normalized pressure relative to the
        # pressure threshold.
        #
        # Below threshold:
        #
        #       pressure = 0.0
        #
        # At threshold:
        #
        #       pressure = 0.0
        #
        # Above threshold:
        #
        #       pressure increases toward 1.0
        #
        # This keeps ordinary resource utilization from being
        # mistaken for pressure.
        # ------------------------------------------------------

        if cpu_threshold > 0.0:
            cpu_excess = max(
                0.0,
                (cpu - cpu_threshold)
                / max(
                    0.000001,
                    100.0 - cpu_threshold,
                ),
            )
        else:
            cpu_excess = (
                1.0
                if cpu > 0.0
                else 0.0
            )

        if mem_threshold > 0.0:
            mem_excess = max(
                0.0,
                (mem - mem_threshold)
                / max(
                    0.000001,
                    100.0 - mem_threshold,
                ),
            )
        else:
            mem_excess = (
                1.0
                if mem > 0.0
                else 0.0
            )

        # ------------------------------------------------------
        # The highest resource pressure governs the combined
        # resource score.
        # ------------------------------------------------------

        pressure = max(
            cpu_excess,
            mem_excess,
        )

        return max(
            0.0,
            min(
                pressure,
                1.0,
            ),
        )

    # ==========================================================
    # RESOURCE CAUSE
    # ==========================================================

    def _determine_resource_cause(
        self,
        *,
        cpu: float,
        mem: float,
        pressure: float,
        desired_state: str,
        effective_state: str,
        reason: str,
    ) -> str:
       

        cpu_ratio = cpu / 100.0
        mem_ratio = mem / 100.0

        cpu_over = max(
            0.0,
            cpu_ratio
            - self.cpu_pressure_threshold,
        )

        mem_over = max(
            0.0,
            mem_ratio
            - self.mem_pressure_threshold,
        )

        if (
            cpu >= self.cpu_block_threshold * 100.0
        ):
            return "cpu_block_threshold"

        if (
            mem >= self.mem_block_threshold * 100.0
        ):
            return "memory_block_threshold"

        if cpu_over > mem_over:

            if cpu >= self.cpu_limit:
                return "cpu_limit_exceeded"

            return "cpu_pressure"

        if mem_over > cpu_over:

            if mem >= self.mem_limit:
                return "memory_limit_exceeded"

            return "memory_pressure"

        if pressure >= self.pressure_threshold:

            return "combined_resource_pressure"

        if desired_state != effective_state:

            return "hysteresis_pending"

        return reason

    # ==========================================================
    # RESOURCE STATE
    # ==========================================================

    def _resource_state(
        self,
        cpu: float,
        mem: float,
        pressure: float,
    ):

        booting = (
            not self._boot_complete
            and (
                time.time() - self.started_at
                < self.boot_grace_seconds
            )
        )

        # --------------------------------------------------
        # BOOT
        # --------------------------------------------------

        if booting:

            if (
                cpu
                >= self.boot_cpu_block_threshold
                * 100.0
                or
                mem
                >= self.boot_mem_block_threshold
                * 100.0
            ):

                return (
                    ConstraintState.WARNING,
                    "boot_resource_warning",
                )

            if (
                cpu
                >= self.boot_cpu_pressure_threshold
                * 100.0
                or
                mem
                >= self.boot_mem_pressure_threshold
                * 100.0
            ):

                return (
                    ConstraintState.PRESSURE,
                    "boot_resource_pressure",
                )

            return (
                ConstraintState.CLEAR,
                "boot_resource_clear",
            )

        # --------------------------------------------------
        # BLOCK
        # --------------------------------------------------

        if (
            cpu
            >= self.cpu_block_threshold
            * 100.0
        ):

            return (
                ConstraintState.BLOCK,
                "cpu_block_threshold",
            )

        if (
            mem
            >= self.mem_block_threshold
            * 100.0
        ):

            return (
                ConstraintState.BLOCK,
                "memory_block_threshold",
            )

        # --------------------------------------------------
        # WARNING
        # --------------------------------------------------

        if (
            cpu
            >= self.cpu_pressure_threshold
            * 100.0
        ):

            return (
                ConstraintState.WARNING,
                "cpu_pressure_threshold",
            )

        if (
            mem
            >= self.mem_pressure_threshold
            * 100.0
        ):

            return (
                ConstraintState.WARNING,
                "memory_pressure_threshold",
            )

        # --------------------------------------------------
        # PRESSURE
        # --------------------------------------------------

        if pressure >= self.pressure_threshold:

            return (
                ConstraintState.PRESSURE,
                "combined_resource_pressure",
            )

        return (
            ConstraintState.CLEAR,
            "resource_clear",
        )

    # ==========================================================
    # HYSTERESIS
    # ==========================================================

    def _apply_state_hysteresis(
        self,
        desired_state: str,
    ) -> str:

        now = time.monotonic()

        current = self._state

        if desired_state == current:

            self._candidate_state = current
            self._candidate_since = now

            return current

        if desired_state != self._candidate_state:

            self._candidate_state = (
                desired_state
            )

            self._candidate_since = now

            return current

        elapsed = (
            now - self._candidate_since
        )

        required_dwell = (
            self.transition_dwell_seconds
        )

        if (
            current == ConstraintState.BLOCK
            and desired_state
            != ConstraintState.BLOCK
        ):

            required_dwell = max(
                required_dwell,
                self.block_recovery_seconds,
            )

            if (
                desired_state
                != ConstraintState.CLEAR
            ):

                return current

        if elapsed < required_dwell:

            return current

        previous = self._state

        self._state = desired_state

        self._last_state_change = now

        self._candidate_state = (
            desired_state
        )

        self._candidate_since = now

        logger.info(
            "[ConstraintGuardian] "
            f"STATE TRANSITION | "
            f"{previous} -> {desired_state} | "
            f"reason={self._last_reason}"
        )

        return desired_state

    # ==========================================================
    # COUNTERS
    # ==========================================================

    def _record_counters(
        self,
        state: str,
    ) -> None:

        if state in (
            ConstraintState.PRESSURE,
            ConstraintState.WARNING,
            ConstraintState.BLOCK,
        ):

            self._pressure_count += 1
            self._recovery_count = 0

        else:

            self._recovery_count += 1

            if (
                self._recovery_count
                >= self.recovery_samples
            ):

                self._pressure_count = 0

    # ==========================================================
    # QBIT OBSERVATION
    # ==========================================================

    async def observe(
        self,
        qbit,
        *,
        context=None,
    ) -> ConstraintState:

        if self.is_shutdown_requested():
            return ConstraintState.CLEAR

        if self.limp_mode:
            return ConstraintState.CLEAR

        if qbit is None:
            return ConstraintState.CLEAR

        async with self._lock:

            with self._state_lock:

                self._observation_count += 1

                resolved_context = (
                    self._resolve_context(
                        context
                    )
                )

                qbit_pressure, qbit_reason = (
                    self._evaluate_qbit(
                        qbit
                    )
                )

                self._qbit_pressure = (
                    qbit_pressure
                )

                self._qbit_reason = (
                    qbit_reason
                )

                self._record_causal_event(
                    event_type="qbit_observation",
                    context=resolved_context,
                    cause=qbit_reason,
                    decision="observe",
                    state=self._state,
                )

                self._emit_state(
                    qbit,
                    self._state,
                    context=resolved_context,
                )

                return self._state

    # ==========================================================
    # QBIT EVALUATION
    # ==========================================================

    def _evaluate_qbit(
        self,
        qbit,
    ):
        

        pressure = 0.0
        reasons = []

        flags = getattr(
            qbit,
            "flags",
            {},
        )

        if flags:

            try:

                flag_count = len(flags)

                if flag_count >= 4:

                    pressure += 0.25
                    reasons.append(
                        "multiple_qbit_flags"
                    )

            except Exception:
                pass

        payload = getattr(
            qbit,
            "payload",
            None,
        )

        if isinstance(
            payload,
            dict,
        ):

            if payload.get(
                "error"
            ):

                pressure += 0.35
                reasons.append(
                    "qbit_error"
                )

            if payload.get(
                "overloaded"
            ):

                pressure += 0.35
                reasons.append(
                    "qbit_overloaded"
                )

            if payload.get(
                "degraded"
            ):

                pressure += 0.20
                reasons.append(
                    "qbit_degraded"
                )

        state = getattr(
            qbit,
            "state",
            None,
        )

        if state:

            try:

                a, b = state

                imbalance = abs(
                    abs(a) - abs(b)
                )

                if imbalance > 0.8:

                    pressure += 0.15
                    reasons.append(
                        "qbit_state_imbalance"
                    )

            except Exception:
                pass

        pressure = max(
            0.0,
            min(
                pressure,
                1.0,
            ),
        )

        if not reasons:
            reason = "qbit_clear"
        else:
            reason = "+".join(reasons)

        return pressure, reason

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
    # ==========================================================

    def allow_work(
        self,
        workload: str = WorkloadClass.NORMAL,
        *,
        source=None,
        module=None,
        component=None,
        operation=None,
        track_id=None,
        channel_id=None,
        parent_id=None,
        task_id=None,
        context=None,
    ) -> bool:
        

        with self._state_lock:

            resolved_context = (
                self._resolve_context(
                    context,
                    source=source,
                    module=module,
                    component=component,
                    operation=operation,
                    workload=workload,
                    track_id=track_id,
                    channel_id=channel_id,
                    parent_id=parent_id,
                    task_id=task_id,
                )
            )

            state = self._state

            decision = (
                self._admission_decision(
                    workload,
                    state,
                )
            )

            if decision in (
                "allowed",
                "critical_allowed",
            ):

                self._allowed_work += 1

            elif decision == "blocked":

                self._blocked_work += 1

            elif decision == "deferred":

                self._deferred_work += 1

            self._last_decision = {
                "timestamp": time.time(),
                "decision": decision,
                "state": state,
                "context": dict(
                    resolved_context
                ),
            }

            self._record_causal_event(
                event_type="work_admission",
                context=resolved_context,
                cause=self._last_reason,
                decision=decision,
                state=state,
            )

            return decision in (
                "allowed",
                "critical_allowed",
            )

    # ----------------------------------------------------------

    def _admission_decision(
        self,
        workload: str,
        state: str,
    ) -> str:

        if self._shutdown_requested:

            if workload == WorkloadClass.CRITICAL:
                return "critical_allowed"

            return "deferred"

        if self.is_booting():
            return "allowed"

        if workload == WorkloadClass.CRITICAL:
            return "critical_allowed"

        if workload == WorkloadClass.DEFERRED:

            if state != ConstraintState.CLEAR:
                return "deferred"

            return "allowed"

        if workload == WorkloadClass.BACKGROUND:

            if state in (
                ConstraintState.WARNING,
                ConstraintState.BLOCK,
            ):

                if self.is_sustained_pressure():
                    return "deferred"

            return "allowed"

        if workload == WorkloadClass.NORMAL:

            if state == ConstraintState.BLOCK:
                return "blocked"

            return "allowed"

        return "blocked"

    # ==========================================================
    # ALIASES
    # ==========================================================

    def allow_background_work(
        self,
        **context,
    ) -> bool:

        return self.allow_work(
            WorkloadClass.BACKGROUND,
            **context,
        )

    # ----------------------------------------------------------

    def allow_deferred_work(
        self,
        **context,
    ) -> bool:

        return self.allow_work(
            WorkloadClass.DEFERRED,
            **context,
        )

    # ----------------------------------------------------------

    def allow_critical_work(
        self,
        **context,
    ) -> bool:

        return self.allow_work(
            WorkloadClass.CRITICAL,
            **context,
        )

    # ==========================================================
    # CAUSAL RECORDING
    # ==========================================================

    def _record_causal_event(
        self,
        *,
        event_type: str,
        context: Optional[Dict[str, Any]],
        cause: str,
        decision: Optional[str] = None,
        previous_state: Optional[str] = None,
        desired_state: Optional[str] = None,
        state: Optional[str] = None,
    ) -> Dict[str, Any]:

        context = dict(
            context or {}
        )

        timestamp = time.time()

        record = {
            "timestamp": timestamp,

            "event_type": event_type,

            # ----------------------------------------------
            # WHERE
            # ----------------------------------------------

            "source": context.get(
                "source"
            ),

            "module": context.get(
                "module"
            ),

            "component": context.get(
                "component"
            ),

            # ----------------------------------------------
            # WHAT
            # ----------------------------------------------

            "operation": context.get(
                "operation"
            ),

            "workload": context.get(
                "workload",
                WorkloadClass.NORMAL,
            ),

            # ----------------------------------------------
            # TRACK
            # ----------------------------------------------

            "track_id": context.get(
                "track_id"
            ),

            "channel_id": context.get(
                "channel_id"
            ),

            "parent_id": context.get(
                "parent_id"
            ),

            "task_id": context.get(
                "task_id"
            ),

            # ----------------------------------------------
            # WHY
            # ----------------------------------------------

            "cause": cause,

            # ----------------------------------------------
            # EFFECT
            # ----------------------------------------------

            "decision": decision,

            "previous_state": previous_state,

            "desired_state": desired_state,

            "state": state,

            # ----------------------------------------------
            # RESOURCES
            # ----------------------------------------------

            "cpu": round(
                self._last_cpu,
                2,
            ),

            "memory": round(
                self._last_mem,
                2,
            ),

            "resource_pressure": round(
                self._last_pressure,
                4,
            ),

            "qbit_pressure": round(
                self._qbit_pressure,
                4,
            ),

            "qbit_reason": (
                self._qbit_reason
            ),
        }

        self._causal_history.append(
            record
        )

        self._last_cause = record

        self._cause_counts[
            cause
        ] += 1

        if context.get("source"):
            self._source_counts[
                str(
                    context["source"]
                )
            ] += 1

        if context.get("operation"):
            self._operation_counts[
                str(
                    context["operation"]
                )
            ] += 1

        return record

    # ==========================================================
    # CAUSAL HISTORY
    # ==========================================================

    def causal_history(
        self,
        limit: int = 20,
        *,
        source=None,
        track_id=None,
        operation=None,
        decision=None,
        state=None,
    ):

        with self._state_lock:

            records = list(
                self._causal_history
            )

        if source is not None:

            records = [
                r for r in records
                if r.get("source")
                == source
            ]

        if track_id is not None:

            records = [
                r for r in records
                if r.get("track_id")
                == track_id
            ]

        if operation is not None:

            records = [
                r for r in records
                if r.get("operation")
                == operation
            ]

        if decision is not None:

            records = [
                r for r in records
                if r.get("decision")
                == decision
            ]

        if state is not None:

            records = [
                r for r in records
                if r.get("state")
                == state
            ]

        limit = max(
            1,
            int(limit),
        )

        return records[-limit:]

    # ==========================================================
    # LAST CAUSE
    # ==========================================================

    def last_cause(self):
        with self._state_lock:
            return (
                dict(self._last_cause)
                if self._last_cause
                else None
            )

    # ==========================================================
    # CAUSAL SUMMARY
    # ==========================================================

    def causal_summary(self) -> Dict[str, Any]:

        with self._state_lock:

            return {
                "top_causes": (
                    self._cause_counts
                    .most_common(10)
                ),

                "top_sources": (
                    self._source_counts
                    .most_common(10)
                ),

                "top_operations": (
                    self._operation_counts
                    .most_common(10)
                ),

                "last_cause": (
                    dict(self._last_cause)
                    if self._last_cause
                    else None
                ),

                "last_decision": (
                    dict(self._last_decision)
                    if self._last_decision
                    else None
                ),

                "history_size": len(
                    self._causal_history
                ),
            }

    # ==========================================================
    # SAFE EVENT EMISSION
    # ==========================================================

    def _emit_state(
        self,
        qbit,
        state: ConstraintState,
        *,
        context=None,
    ) -> None:

        if self.event_bus is None:
            return

        now = time.monotonic()

        state_changed = (
            state
            != self._last_emitted_state
        )

        if (
            not state_changed
            and (
                now - self._last_event_time
                < self.event_cooldown
            )
        ):
            return

        self._last_event_time = now
        self._last_emitted_state = state

        try:

            track = getattr(
                qbit,
                "track",
                {},
            )

            if not isinstance(
                track,
                dict,
            ):
                track = {}

            resolved_context = (
                self._resolve_context(
                    context
                )
            )

            payload = {
                "version": self.VERSION,

                "state": state,

                "previous_state": (
                    self._last_cause.get(
                        "previous_state"
                    )
                    if self._last_cause
                    else None
                ),

                # ------------------------------------------
                # CAUSE
                # ------------------------------------------

                "cause": (
                    self._last_cause.get(
                        "cause"
                    )
                    if self._last_cause
                    else self._last_reason
                ),

                # ------------------------------------------
                # WHERE
                # ------------------------------------------

                "source": resolved_context.get(
                    "source"
                ),

                "module": resolved_context.get(
                    "module"
                ),

                "component": resolved_context.get(
                    "component"
                ),

                # ------------------------------------------
                # WHAT
                # ------------------------------------------

                "operation": resolved_context.get(
                    "operation"
                ),

                "workload": resolved_context.get(
                    "workload"
                ),

                # ------------------------------------------
                # TRACK
                # ------------------------------------------

                "track_id": (
                    resolved_context.get(
                        "track_id"
                    )
                    or track.get(
                        "track_id"
                    )
                ),

                "channel_id": resolved_context.get(
                    "channel_id"
                ),

                "parent_id": resolved_context.get(
                    "parent_id"
                ),

                # ------------------------------------------
                # RESOURCE
                # ------------------------------------------

                "cpu": self._last_cpu,

                "memory": self._last_mem,

                "pressure": self._last_pressure,

                "qbit_pressure": (
                    self._qbit_pressure
                ),

                "qbit_reason": (
                    self._qbit_reason
                ),

                "sustained": (
                    self.is_sustained_pressure()
                ),

                "timestamp": time.time(),

                "source_guardian": (
                    "ConstraintGuardian"
                ),
            }

            publisher = getattr(
                self.event_bus,
                "publish",
                None,
            )

            if not callable(publisher):
                return

            result = publisher(
                "CONSTRAINT_STATE",
                payload=payload,
                source="ConstraintGuardian",
            )

            if inspect.isawaitable(
                result
            ):

                try:

                    loop = (
                        asyncio.get_running_loop()
                    )

                    if loop.is_running():

                        loop.create_task(
                            result
                        )

                except RuntimeError:
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

        if state != self._state:
            return True

        return (
            now - self._last_state_change
            >= self.event_cooldown
        )

    # ==========================================================
    # STATE
    # ==========================================================

    def get_state(
        self,
    ) -> ConstraintState:

        with self._state_lock:
            return self._state

    # ==========================================================
    # PRESSURE
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

                "cpu_ratio": (
                    self._last_cpu / 100.0
                ),

                "memory_ratio": (
                    self._last_mem / 100.0
                ),

                "qbit_pressure": (
                    self._qbit_pressure
                ),

                "qbit_reason": (
                    self._qbit_reason
                ),

                "cause": (
                    self._last_cause.get(
                        "cause"
                    )
                    if self._last_cause
                    else None
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
                "version": self.VERSION,

                "name": self.NAME,

                # ------------------------------------------
                # STATE
                # ------------------------------------------

                "state": self._state,

                "candidate_state": (
                    self._candidate_state
                ),

                "candidate_age": round(
                    time.monotonic()
                    - self._candidate_since,
                    3,
                ),

                # ------------------------------------------
                # RESOURCES
                # ------------------------------------------

                "resources": {
                    "cpu": round(
                        self._last_cpu,
                        2,
                    ),

                    "memory": round(
                        self._last_mem,
                        2,
                    ),

                    "resource_pressure": round(
                        self._last_pressure,
                        4,
                    ),

                    "qbit_pressure": round(
                        self._qbit_pressure,
                        4,
                    ),

                    "qbit_reason": (
                        self._qbit_reason
                    ),
                },

                # ------------------------------------------
                # CAUSALITY
                # ------------------------------------------

                "causal": (
                    self.causal_summary()
                ),

                "active_context": dict(
                    self._active_context
                ),

                # ------------------------------------------
                # WORK
                # ------------------------------------------

                "work": {
                    "allowed": (
                        self._allowed_work
                    ),

                    "blocked": (
                        self._blocked_work
                    ),

                    "deferred": (
                        self._deferred_work
                    ),
                },

                # ------------------------------------------
                # PRESSURE
                # ------------------------------------------

                "sustained_pressure": (
                    self.is_sustained_pressure()
                ),

                "pressure_samples": (
                    self._pressure_count
                ),

                "recovery_samples": (
                    self._recovery_count
                ),

                # ------------------------------------------
                # COUNTERS
                # ------------------------------------------

                "total_checks": (
                    self._total_checks
                ),

                "observations": (
                    self._observation_count
                ),

                "uptime": round(
                    uptime,
                    2,
                ),

                # ------------------------------------------
                # LIFECYCLE
                # ------------------------------------------

                "limp_mode": (
                    self.limp_mode
                ),

                "boot_complete": (
                    self._boot_complete
                ),

                "booting": (
                    self.is_booting()
                ),

                "shutdown_requested": (
                    self._shutdown_requested
                ),

                "shutdown_reason": (
                    self._shutdown_reason
                ),

                # ------------------------------------------
                # THRESHOLDS
                # ------------------------------------------

                "thresholds": {
                    "cpu_limit": (
                        self.cpu_limit
                    ),

                    "memory_limit": (
                        self.mem_limit
                    ),

                    "cpu_pressure": (
                        self.cpu_pressure_threshold
                        * 100.0
                    ),

                    "cpu_block": (
                        self.cpu_block_threshold
                        * 100.0
                    ),

                    "memory_pressure": (
                        self.mem_pressure_threshold
                        * 100.0
                    ),

                    "memory_block": (
                        self.mem_block_threshold
                        * 100.0
                    ),
                },

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

            self._candidate_state = (
                ConstraintState.CLEAR
            )

            self._last_reason = (
                "manual_reset"
            )

            now = time.monotonic()

            self._last_state_change = now
            self._candidate_since = now

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
            f"version={self.VERSION!r}, "
            f"cpu={self._last_cpu:.1f}, "
            f"memory={self._last_mem:.1f}, "
            f"pressure={self._last_pressure:.3f}, "
            f"qbit_pressure="
            f"{self._qbit_pressure:.3f}, "
            f"state={self._state!r}, "
            f"cause="
            f"{self._last_reason!r}, "
            f"boot_complete="
            f"{self._boot_complete!r}, "
            f"shutdown_requested="
            f"{self._shutdown_requested!r}"
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