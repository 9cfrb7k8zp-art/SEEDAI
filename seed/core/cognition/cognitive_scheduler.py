# ==========================================================
# FILE: cognitive_scheduler.py
# PATH: SEED_ROOT/seed/core/cognition/cognitive_scheduler.py
#
# SYSTEM: SEED AI OS
# COMPONENT: Cognitive Scheduler
#
# VERSION: 4.0.0
# BUILD: LIFECYCLE-SAFE / QBIT-SYNC / GUARDIAN-AWARE /
#        PASSIVE-BOOT / STATUS-MODE / IDEMPOTENT
#
# PURPOSE:
# - Coordinate high-level cognitive modes
# - Generate controlled cognitive Qbits
# - Follow CognitiveClock when available
# - Remain subordinate to SEED system lifecycle
# - Never start during import
# - Never independently boot SEED
# - Never create uncontrolled scheduler threads
# - Respect ConstraintGuardian / runtime pressure
# - Prevent scheduler queue flooding
# - Provide explicit lifecycle/status telemetry
#
# COGNITIVE FLOW:
#
#       CognitiveClock
#             |
#             v
#     CognitiveScheduler
#             |
#       admission check
#             |
#       ConstraintGuardian
#             |
#             v
#        QbitQueueLoop
#
# IMPORTANT:
#
# CognitiveScheduler is NOT:
# - the system boot manager
# - the heartbeat
# - the Qbit brain
# - the queue loop
# - a replacement for lifecycle control
#
# It only schedules cognitive intent.
#
# BOOT RULE:
#
#     IMPORT
#        |
#        v
#     CONSTRUCT
#        |
#        v
#     WAIT
#        |
#        v
#     SYSTEM STARTED
#        |
#        v
#     scheduler.start()
#        |
#        v
#     RUNNING
#
# It must NEVER create a background thread merely because
# this module was imported or instantiated.
# ==========================================================

from __future__ import annotations

import logging
import threading
import time
import uuid
from enum import Enum
from typing import Any, Dict, Optional


log = logging.getLogger("CognitiveScheduler")


# ==========================================================
# STATUS MODES
# ==========================================================

class SchedulerStatus:
  

    CREATED = "created"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


# ==========================================================
# COGNITIVE MODES
# ==========================================================

class CognitiveMode:
    EXPLORE = "EXPLORE"
    ANALYZE = "ANALYZE"
    LEARN = "LEARN"
    REFLECT = "REFLECT"


# ==========================================================
# COGNITIVE SCHEDULER
# ==========================================================

class CognitiveScheduler:

    def __init__(
        self,
        queue_loop,
        *,
        qbit_dialer=None,
        cognitive_clock=None,
        event_bus=None,
        constraint_guardian=None,
        interval: float = 5.0,
        max_pending_scheduler_qbits: int = 1,
    ):
        """
        Construct the scheduler.

        Construction is intentionally passive.

        NO THREAD IS CREATED HERE.
        NO QBIT IS CREATED HERE.
        NO QUEUE ITEM IS CREATED HERE.
        NO SYSTEM START IS ATTEMPTED HERE.
        """

        self.queue_loop = queue_loop
        self.qbit_dialer = qbit_dialer

        self.clock = (
            cognitive_clock
            if cognitive_clock is not None
            else getattr(
                queue_loop,
                "cognitive_clock",
                None,
            )
        )

        self.event_bus = (
            event_bus
            if event_bus is not None
            else getattr(
                queue_loop,
                "event_bus",
                None,
            )
        )

        self.constraint_guardian = (
            constraint_guardian
            if constraint_guardian is not None
            else getattr(
                queue_loop,
                "constraint_guardian",
                None,
            )
        )

        # --------------------------------------------------
        # Configuration
        # --------------------------------------------------

        self.modes = [
            CognitiveMode.EXPLORE,
            CognitiveMode.ANALYZE,
            CognitiveMode.LEARN,
            CognitiveMode.REFLECT,
        ]

        self.interval = max(
            0.25,
            float(interval),
        )

        self.max_pending_scheduler_qbits = max(
            1,
            int(max_pending_scheduler_qbits),
        )

        # --------------------------------------------------
        # Lifecycle
        # --------------------------------------------------

        self._status = SchedulerStatus.CREATED

        self._stop_event = threading.Event()

        self._pause_event = threading.Event()

        self._thread: Optional[threading.Thread] = None

        self._lock = threading.RLock()

        # --------------------------------------------------
        # Scheduling state
        # --------------------------------------------------

        self.index = 0

        self.last_switch = time.monotonic()

        self.last_tick = 0.0

        self.last_qbit_id = None

        self.last_mode = None

        # --------------------------------------------------
        # Counters
        # --------------------------------------------------

        self.tick_count = 0

        self.generated_qbits = 0

        self.skipped_qbits = 0

        self.guardian_deferrals = 0

        self.lifecycle_deferrals = 0

        self.errors = 0

        self.started_at = None

        self.stopped_at = None

        # --------------------------------------------------
        # Scheduler ownership marker
        # --------------------------------------------------

        self.source = "COGNITIVE_SCHEDULER"

        log.info(
            "[CognitiveScheduler] Initialized | "
            "status=%s | interval=%.2fs",
            self._status,
            self.interval,
        )

    # ======================================================
    # LIFECYCLE DETECTION
    # ======================================================

    def _system_is_running(self) -> bool:
        

        queue = self.queue_loop

        if queue is None:
            return False

        # --------------------------------------------------
        # Explicit lifecycle methods
        # --------------------------------------------------

        for method_name in (
            "is_running",
            "is_started",
            "is_active",
        ):

            method = getattr(
                queue,
                method_name,
                None,
            )

            if callable(method):

                try:
                    result = method()

                    if result is False:
                        return False

                    if result is True:
                        return True

                except Exception:
                    pass

        # --------------------------------------------------
        # Explicit lifecycle properties
        # --------------------------------------------------

        for attr_name in (
            "running",
            "started",
            "active",
            "system_running",
        ):

            if hasattr(queue, attr_name):

                try:

                    value = getattr(
                        queue,
                        attr_name,
                    )

                    if isinstance(
                        value,
                        bool,
                    ):

                        return value

                except Exception:
                    pass

        # --------------------------------------------------
        # Lifecycle state strings
        # --------------------------------------------------

        for attr_name in (
            "status",
            "state",
            "lifecycle_state",
        ):

            value = getattr(
                queue,
                attr_name,
                None,
            )

            if isinstance(
                value,
                str,
            ):

                normalized = value.lower()

                if normalized in (
                    "running",
                    "started",
                    "active",
                    "online",
                    "ready",
                ):

                    return True

                if normalized in (
                    "created",
                    "initializing",
                    "booting",
                    "starting",
                    "stopped",
                    "shutdown",
                    "shutting_down",
                    "offline",
                ):

                    return False

        # --------------------------------------------------
        # If there is no explicit lifecycle signal, do NOT
        # assume the system is running.
        #
        # This is the important boot-safety behavior.
        # --------------------------------------------------

        return False

    # ======================================================
    # SHUTDOWN DETECTION
    # ======================================================

    def _shutdown_requested(self) -> bool:

        queue = self.queue_loop

        if queue is None:
            return True

        for attr_name in (
            "shutdown_requested",
            "shutting_down",
            "shutdown",
            "stopping",
        ):

            value = getattr(
                queue,
                attr_name,
                False,
            )

            if isinstance(
                value,
                bool,
            ) and value:

                return True

        guardian = self.constraint_guardian

        if guardian is not None:

            method = getattr(
                guardian,
                "is_shutdown_requested",
                None,
            )

            if callable(method):

                try:

                    if method():
                        return True

                except Exception:
                    pass

        return False

    # ======================================================
    # START
    # ======================================================

    def start(self) -> bool:
        """
        Explicitly start scheduler execution.

        This method is idempotent.

        Calling start repeatedly will NOT create multiple
        scheduler threads.
        """

        with self._lock:

            if self._status == SchedulerStatus.RUNNING:

                return True

            if self._status == SchedulerStatus.STARTING:

                return True

            if self._status == SchedulerStatus.STOPPING:

                return False

            if self._shutdown_requested():

                log.info(
                    "[CognitiveScheduler] Start refused | "
                    "shutdown active"
                )

                return False

            # --------------------------------------------------
            # Lifecycle gate.
            #
            # Scheduler cannot wake SEED up.
            # --------------------------------------------------

            if not self._system_is_running():

                self.lifecycle_deferrals += 1

                log.info(
                    "[CognitiveScheduler] Start deferred | "
                    "system lifecycle is not RUNNING"
                )

                return False

            self._status = (
                SchedulerStatus.STARTING
            )

            self._stop_event.clear()

            self._pause_event.clear()

            self.last_switch = time.monotonic()

            self.started_at = time.time()

            self._thread = threading.Thread(
                target=self._run_loop,
                daemon=True,
                name="CognitiveScheduler",
            )

            self._thread.start()

            self._status = (
                SchedulerStatus.RUNNING
            )

            log.info(
                "[CognitiveScheduler] RUNNING"
            )

            return True

    # ======================================================
    # STOP
    # ======================================================

    def stop(
        self,
        reason: str = "shutdown",
    ) -> None:

        with self._lock:

            if self._status in (
                SchedulerStatus.STOPPED,
                SchedulerStatus.CREATED,
            ):

                self._status = (
                    SchedulerStatus.STOPPED
                )

                self.stopped_at = time.time()

                return

            self._status = (
                SchedulerStatus.STOPPING
            )

            self._stop_event.set()

            self._pause_event.clear()

        log.info(
            "[CognitiveScheduler] STOPPING | reason=%s",
            reason,
        )

    # ======================================================
    # PAUSE
    # ======================================================

    def pause(
        self,
        reason: str = "manual_pause",
    ) -> bool:

        with self._lock:

            if self._status != SchedulerStatus.RUNNING:

                return False

            self._pause_event.set()

            self._status = (
                SchedulerStatus.PAUSED
            )

        log.info(
            "[CognitiveScheduler] PAUSED | reason=%s",
            reason,
        )

        return True

    # ======================================================
    # RESUME
    # ======================================================

    def resume(self) -> bool:

        with self._lock:

            if self._status != SchedulerStatus.PAUSED:

                return False

            if self._shutdown_requested():

                return False

            if not self._system_is_running():

                self.lifecycle_deferrals += 1

                return False

            self._pause_event.clear()

            self._status = (
                SchedulerStatus.RUNNING
            )

        log.info(
            "[CognitiveScheduler] RESUMED"
        )

        return True

    # ======================================================
    # THREAD LOOP
    # ======================================================

    def _run_loop(self) -> None:
        

        while not self._stop_event.is_set():

            try:

                # --------------------------------------------------
                # System lifecycle can disappear while running.
                # --------------------------------------------------

                if self._shutdown_requested():

                    break

                if not self._system_is_running():

                    self.lifecycle_deferrals += 1

                    time.sleep(
                        min(
                            self.interval,
                            1.0,
                        )
                    )

                    continue

                # --------------------------------------------------
                # Pause mode.
                # --------------------------------------------------

                if self._pause_event.is_set():

                    time.sleep(
                        min(
                            self.interval,
                            1.0,
                        )
                    )

                    continue

                self.tick()

            except Exception as exc:

                self.errors += 1

                log.exception(
                    "[CognitiveScheduler] Loop failure: %s",
                    exc,
                )

                # Do not spin at 100% CPU if an unexpected
                # integration error occurs.
                time.sleep(0.5)

        with self._lock:

            self._status = (
                SchedulerStatus.STOPPED
            )

            self.stopped_at = time.time()

        log.info(
            "[CognitiveScheduler] STOPPED"
        )

    # ======================================================
    # MAIN TICK
    # ======================================================

    def tick(self) -> Optional[Dict[str, Any]]:
       
        self.tick_count += 1

        now = time.monotonic()

        # --------------------------------------------------
        # Lifecycle gate
        # --------------------------------------------------

        if not self._system_is_running():

            self.lifecycle_deferrals += 1

            return None

        if self._shutdown_requested():

            return None

        # --------------------------------------------------
        # Pause gate
        # --------------------------------------------------

        if self._pause_event.is_set():

            return None

        # --------------------------------------------------
        # Timing gate
        # --------------------------------------------------

        if (
            now - self.last_switch
            < self.interval
        ):

            return None

        # --------------------------------------------------
        # Constraint Guardian admission
        # --------------------------------------------------

        if not self._allow_scheduler_work():

            self.guardian_deferrals += 1

            return None

        self.last_switch = now
        self.last_tick = now

        # --------------------------------------------------
        # Determine cognitive mode
        # --------------------------------------------------

        mode = self._next_mode()

        # --------------------------------------------------
        # Build Qbit
        # --------------------------------------------------

        qbit = self._build_qbit(
            mode
        )

        # --------------------------------------------------
        # Queue
        # --------------------------------------------------

        if not self._submit_qbit(
            qbit
        ):

            self.skipped_qbits += 1

            return None

        self.generated_qbits += 1

        self.last_mode = mode

        self.last_qbit_id = qbit.get(
            "task_id"
        )

        log.info(
            "[CognitiveScheduler] "
            "mode=%s | qbit=%s",
            mode,
            self.last_qbit_id,
        )

        return qbit

    # ======================================================
    # GUARDIAN ADMISSION
    # ======================================================

    def _allow_scheduler_work(self) -> bool:

        guardian = self.constraint_guardian

        if guardian is None:
            return True

        try:

            method = getattr(
                guardian,
                "allow_work",
                None,
            )

            if callable(method):

                try:

                    return bool(
                        method(
                            "BACKGROUND"
                        )
                    )

                except TypeError:

                    return bool(
                        method(
                            workload="background"
                        )
                    )

            method = getattr(
                guardian,
                "allow_background_work",
                None,
            )

            if callable(method):

                return bool(
                    method()
                )

        except Exception as exc:

            log.debug(
                "[CognitiveScheduler] "
                "Guardian admission error: %s",
                exc,
            )

        # Failure of the optional guardian must not make
        # scheduler logic crash.
        return True

    # ======================================================
    # NEXT COGNITIVE MODE
    # ======================================================

    def _next_mode(self) -> str:

        # --------------------------------------------------
        # If CognitiveClock is available, use its phase to
        # inform scheduling without taking ownership of it.
        # --------------------------------------------------

        phase = getattr(
            self.clock,
            "phase",
            None,
        )

        phase_map = {
            "PERCEIVE": CognitiveMode.EXPLORE,
            "ANALYZE": CognitiveMode.ANALYZE,
            "REASON": CognitiveMode.ANALYZE,
            "ACT": CognitiveMode.LEARN,
            "REFLECT": CognitiveMode.REFLECT,
        }

        if phase in phase_map:

            return phase_map[
                phase
            ]

        # --------------------------------------------------
        # Fallback deterministic rotation.
        # --------------------------------------------------

        mode = self.modes[
            self.index
            % len(self.modes)
        ]

        self.index = (
            self.index + 1
        ) % len(self.modes)

        return mode

    # ======================================================
    # QBIT CREATION
    # ======================================================

    def _build_qbit(
        self,
        mode: str,
    ) -> Dict[str, Any]:

        now = time.time()

        task_id = (
            "cognitive-"
            + str(uuid.uuid4())
        )

        return {
            "task_id": task_id,
            "intent": mode,
            "timestamp": now,

            "metadata": {
                "source": self.source,
                "component": "CognitiveScheduler",
                "scheduler_mode": mode,
                "generated": True,
                "system_owned": True,
                "boot_safe": True,
                "priority_class": "BACKGROUND",
            },
        }

    # ======================================================
    # QUEUE SUBMISSION
    # ======================================================

    def _submit_qbit(
        self,
        qbit: Dict[str, Any],
    ) -> bool:

        queue_loop = self.queue_loop

        if queue_loop is None:

            log.debug(
                "[CognitiveScheduler] "
                "No queue loop"
            )

            return False

        dialer = self.qbit_dialer
        receive = getattr(dialer, "receive_qbit", None) if dialer is not None else None
        if callable(receive):
            try:
                result = receive(qbit)
                return result is not False
            except Exception as exc:
                log.error("[CognitiveScheduler] Dialer submission failed: %s", exc)
                return False

        put = getattr(
            queue_loop,
            "put",
            None,
        )

        if not callable(put):

            log.error(
                "[CognitiveScheduler] "
                "Queue loop has no callable put()"
            )

            return False

        # --------------------------------------------------
        # Prevent scheduler self-flooding.
        # --------------------------------------------------

        pending = self._scheduler_pending_count()

        if (
            pending
            >= self.max_pending_scheduler_qbits
        ):

            self.skipped_qbits += 1

            log.debug(
                "[CognitiveScheduler] "
                "Scheduler Qbit already pending | "
                "pending=%s",
                pending,
            )

            return False

        try:

            result = put(
                qbit,
                priority="BACKGROUND",
            )

            # Some queue implementations return False when
            # admission is denied.
            if result is False:

                return False

            return True

        except TypeError:

            # Compatibility with queue implementations that
            # accept only the item.
            try:

                result = put(
                    qbit
                )

                if result is False:
                    return False

                return True

            except Exception as exc:

                log.error(
                    "[CognitiveScheduler] "
                    "Qbit submission failed: %s",
                    exc,
                )

                return False

        except Exception as exc:

            log.error(
                "[CognitiveScheduler] "
                "Qbit submission failed: %s",
                exc,
            )

            return False

    # ======================================================
    # PENDING SCHEDULER QBIT COUNT
    # ======================================================

    def _scheduler_pending_count(self) -> int:
     

        queue_loop = self.queue_loop

        # --------------------------------------------------
        # Native helper if available
        # --------------------------------------------------

        for name in (
            "count_source",
            "count_by_source",
            "pending_by_source",
        ):

            method = getattr(
                queue_loop,
                name,
                None,
            )

            if callable(method):

                try:

                    value = method(
                        self.source
                    )

                    return max(
                        0,
                        int(value),
                    )

                except Exception:
                    pass

        # --------------------------------------------------
        # Inspect priority queues if available.
        # --------------------------------------------------

        priority_queues = getattr(
            queue_loop,
            "priority_queues",
            None,
        )

        if isinstance(
            priority_queues,
            dict,
        ):

            count = 0

            try:

                for q in priority_queues.values():

                    items = getattr(
                        q,
                        "queue",
                        None,
                    )

                    if items is None:
                        continue

                    for item in list(
                        items
                    ):

                        candidate = item

                        # Priority queues may contain tuples.
                        if (
                            isinstance(
                                item,
                                tuple,
                            )
                            and len(item) > 0
                        ):

                            candidate = item[-1]

                        metadata = None

                        if isinstance(
                            candidate,
                            dict,
                        ):

                            metadata = candidate.get(
                                "metadata"
                            )

                        else:

                            metadata = getattr(
                                candidate,
                                "metadata",
                                None,
                            )

                        if isinstance(
                            metadata,
                            dict,
                        ):

                            if metadata.get(
                                "source"
                            ) == self.source:

                                count += 1

                                if count >= self.max_pending_scheduler_qbits:
                                    return count

            except Exception:
                pass

            return count

        return 0

    # ======================================================
    # STATUS
    # ======================================================

    @property
    def status(self) -> str:

        with self._lock:

            return self._status

    # ======================================================
    # RUNNING QUERY
    # ======================================================

    def is_running(self) -> bool:

        return (
            self.status
            == SchedulerStatus.RUNNING
        )

    # ======================================================
    # PAUSED QUERY
    # ======================================================

    def is_paused(self) -> bool:

        return (
            self.status
            == SchedulerStatus.PAUSED
        )

    # ======================================================
    # STOPPED QUERY
    # ======================================================

    def is_stopped(self) -> bool:

        return (
            self.status
            == SchedulerStatus.STOPPED
        )

    # ======================================================
    # DIAGNOSTICS
    # ======================================================

    def diagnostics(self) -> Dict[str, Any]:

        with self._lock:

            thread_alive = bool(
                self._thread
                and self._thread.is_alive()
            )

            return {
                "component": "CognitiveScheduler",
                "version": "4.0.0",
                "status": self._status,

                "running": (
                    self._status
                    == SchedulerStatus.RUNNING
                ),

                "paused": (
                    self._status
                    == SchedulerStatus.PAUSED
                ),

                "thread_alive": thread_alive,

                "system_running": (
                    self._system_is_running()
                ),

                "shutdown_requested": (
                    self._shutdown_requested()
                ),

                "mode": self.last_mode,

                "last_qbit_id": (
                    self.last_qbit_id
                ),

                "interval": self.interval,

                "tick_count": self.tick_count,

                "generated_qbits": (
                    self.generated_qbits
                ),

                "skipped_qbits": (
                    self.skipped_qbits
                ),

                "guardian_deferrals": (
                    self.guardian_deferrals
                ),

                "lifecycle_deferrals": (
                    self.lifecycle_deferrals
                ),

                "errors": self.errors,

                "pending_scheduler_qbits": (
                    self._scheduler_pending_count()
                ),

                "clock_phase": getattr(
                    self.clock,
                    "phase",
                    None,
                ),
            }

    # ======================================================
    # REPRESENTATION
    # ======================================================

    def __repr__(self) -> str:

        return (
            "CognitiveScheduler("
            f"status={self.status!r}, "
            f"mode={self.last_mode!r}, "
            f"generated={self.generated_qbits}, "
            f"interval={self.interval}"
            ")"
        )


# ==========================================================
# MODULE-LEVEL START FUNCTION
# ==========================================================

def start_scheduler(
    queue_loop,
    *,
    cognitive_clock=None,
    event_bus=None,
    constraint_guardian=None,
    interval: float = 5.0,
):

    # ------------------------------------------------------
    # Reuse an existing scheduler if one is already attached.
    # ------------------------------------------------------

    existing = getattr(
        queue_loop,
        "cognitive_scheduler",
        None,
    )

    if isinstance(
        existing,
        CognitiveScheduler,
    ):

        if existing.is_running():

            return existing

        # Attempt explicit start only if the runtime is
        # already known to be active.
        existing.start()

        return existing

    # ------------------------------------------------------
    # Construct passively.
    # ------------------------------------------------------

    scheduler = CognitiveScheduler(
        queue_loop,
        cognitive_clock=cognitive_clock,
        event_bus=event_bus,
        constraint_guardian=constraint_guardian,
        interval=interval,
    )

    # ------------------------------------------------------
    # Attach for system-wide discovery.
    # ------------------------------------------------------

    try:

        queue_loop.cognitive_scheduler = (
            scheduler
        )

    except Exception:

        pass

    # ------------------------------------------------------
    # Start only when lifecycle permits it.
    # ------------------------------------------------------

    scheduler.start()

    return scheduler


# ==========================================================
# MODULE EXPORTS
# ==========================================================

__all__ = [
    "SchedulerStatus",
    "CognitiveMode",
    "CognitiveScheduler",
    "start_scheduler",
]