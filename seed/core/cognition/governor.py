# ==========================================================
# FILE: governor.py
# PATH: SEED_ROOT/seed/core/cognition/governor.py
#
# SYSTEM: SEED AI OS
# MODULE: Cognitive Governance / Cognition Control Node
#
# VERSION: 8.0.0
# BUILD: LIFECYCLE-SAFE / BOOT-GATED / QBIT-AWARE /
#        CONSTRAINT-AWARE / NEURAL-NODE / CONTROLLED-LOOP
# UPDATED: 2026-08-18
#
# PURPOSE:
# - Govern cognitive workload without becoming the workload engine
# - Observe Qbit flow
# - Detect sustained cognitive loops
# - Detect queue pressure
# - Detect memory pressure
# - Detect excessive Qbit throughput
# - Coordinate with ConstraintGuardian
# - Inject bounded SYSTEM_CONTROL qbits when required
# - Adjust queue throttling safely
# - Provide lifecycle/status/diagnostic information
#
# IMPORTANT ARCHITECTURE RULE:
#
#   IMPORT != START
#   CONSTRUCT != START
#   OBSERVE != START
#
# The Governor must never create a worker thread merely because
# the cognition package was imported or because the object exists.
#
# Explicit lifecycle:
#
#   CREATED
#      |
#      v
#   STARTING
#      |
#      v
#   RUNNING
#      |
#      +----> PRESSURE
#      |
#      +----> BLOCKED
#      |
#      v
#   STOPPING
#      |
#      v
#   STOPPED
#
# The Governor is NOT:
# - Heartbeat
# - QbitDialer
# - QueueLoop
# - EventBus
# - ConstraintGuardian
#
# It observes and coordinates those systems.
#
# ==========================================================

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from typing import Any, Dict, Optional


log = logging.getLogger("CognitiveGovernor")


# ==========================================================
# VERSION
# ==========================================================

__version__ = "8.0.0"
__build__ = (
    "LIFECYCLE-SAFE / BOOT-GATED / QBIT-AWARE / "
    "CONSTRAINT-AWARE / NEURAL-NODE"
)


# ==========================================================
# LIFECYCLE STATES
# ==========================================================

class GovernorState:
    CREATED = "created"
    STARTING = "starting"
    RUNNING = "running"
    PRESSURE = "pressure"
    BLOCKED = "blocked"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"


# ==========================================================
# GOVERNOR MODES
# ==========================================================

class GovernorMode:
    PASSIVE = "PASSIVE"
    MONITOR = "MONITOR"
    ADAPTIVE = "ADAPTIVE"
    PRESSURE = "PRESSURE"
    PROTECT = "PROTECT"
    SHUTDOWN = "SHUTDOWN"


# ==========================================================
# WORKLOAD LEVELS
# ==========================================================

class GovernorPriority:
    CRITICAL = "CRITICAL"
    NORMAL = "NORMAL"
    BACKGROUND = "BACKGROUND"
    DEFERRED = "DEFERRED"


# ==========================================================
# COGNITIVE GOVERNOR
# ==========================================================

class CognitiveGovernor:

    def __init__(
        self,
        queue_loop,
        memory_graph=None,
        event_bus=None,
        constraint_guardian=None,
        *,
        interval: float = 0.5,
        max_queue: int = 8000,
        max_memory_nodes: int = 10000,
        max_qbit_rate: int = 200,
        max_queue_size: int = 300,
        critical_queue_size: int = 800,
        loop_window: int = 10,
        loop_intent_limit: int = 2,
        loop_trigger_count: int = 6,
        control_cooldown: float = 3.0,
        pressure_cooldown: float = 1.0,
        boot_grace_seconds: float = 10.0,
    ):
        # --------------------------------------------------
        # Core dependencies
        # --------------------------------------------------

        self.queue_loop = queue_loop
        self.memory_graph = memory_graph
        self.event_bus = event_bus
        self.constraint_guardian = constraint_guardian

        # Automatically use the queue loop's cognition map when
        # available. This keeps the Governor synchronized with
        # CognitionMap without creating a second map.
        self.cognition_map = getattr(
            queue_loop,
            "cognition_map",
            None,
        )

        # --------------------------------------------------
        # Configuration
        # --------------------------------------------------

        self.interval = max(
            0.1,
            float(interval),
        )

        self.max_queue = max(
            1,
            int(max_queue),
        )

        self.max_memory_nodes = max(
            1,
            int(max_memory_nodes),
        )

        self.max_qbit_rate = max(
            1,
            int(max_qbit_rate),
        )

        self.max_queue_size = max(
            1,
            int(max_queue_size),
        )

        self.critical_queue_size = max(
            self.max_queue_size,
            int(critical_queue_size),
        )

        self.loop_window = max(
            4,
            int(loop_window),
        )

        self.loop_intent_limit = max(
            1,
            int(loop_intent_limit),
        )

        self.loop_trigger_count = max(
            3,
            int(loop_trigger_count),
        )

        self.control_cooldown = max(
            0.1,
            float(control_cooldown),
        )

        self.pressure_cooldown = max(
            0.1,
            float(pressure_cooldown),
        )

        self.boot_grace_seconds = max(
            0.0,
            float(boot_grace_seconds),
        )

        # --------------------------------------------------
        # Lifecycle
        # --------------------------------------------------

        self._state = GovernorState.CREATED
        self._mode = GovernorMode.PASSIVE

        self._state_lock = threading.RLock()

        self._stop_event = threading.Event()
        self._pause_event = threading.Event()

        self._thread: Optional[threading.Thread] = None

        self.started_at: Optional[float] = None
        self.running_at: Optional[float] = None
        self.stopped_at: Optional[float] = None

        self._boot_complete = False
        self._shutdown_requested = False
        self._shutdown_reason = None

        # --------------------------------------------------
        # Timing
        # --------------------------------------------------

        now = time.monotonic()

        self.last_check = now
        self.last_adjust = now
        self._last_control = 0.0
        self._last_pressure_event = 0.0

        # --------------------------------------------------
        # Qbit throughput
        # --------------------------------------------------

        self.qbit_counter = 0
        self.window_start = now

        self.total_qbits_observed = 0
        self.total_ticks = 0

        # --------------------------------------------------
        # Queue history
        # --------------------------------------------------

        self.history = deque(
            maxlen=100,
        )

        self.qbit_history = deque(
            maxlen=100,
        )

        self.intent_history = deque(
            maxlen=self.loop_window,
        )

        # --------------------------------------------------
        # Pressure state
        # --------------------------------------------------

        self.current_queue_size = 0
        self.current_qbit_rate = 0
        self.current_memory_nodes = 0

        self.pressure_level = 0.0

        self.queue_pressure = False
        self.memory_pressure = False
        self.throughput_pressure = False
        self.cognitive_loop_detected = False

        # --------------------------------------------------
        # Counters
        # --------------------------------------------------

        self.loop_events = 0
        self.queue_storm_events = 0
        self.memory_overload_events = 0
        self.cognition_spike_events = 0

        self.control_qbits_injected = 0
        self.control_qbits_suppressed = 0

        # --------------------------------------------------
        # Throttle tracking
        # --------------------------------------------------

        self._original_throttle_delay = getattr(
            queue_loop,
            "throttle_delay",
            None,
        )

        self.current_throttle_delay = (
            self._original_throttle_delay
            if self._original_throttle_delay is not None
            else 0.001
        )

        # --------------------------------------------------
        # Last reason
        # --------------------------------------------------

        self.last_reason = "initialization"

        log.info(
            "[CognitiveGovernor] Initialized | "
            "state=%s | mode=%s | interval=%.2fs | "
            "max_queue=%s | max_qbit_rate=%s",
            self._state,
            self._mode,
            self.interval,
            self.max_queue,
            self.max_qbit_rate,
        )

    # ==========================================================
    # LIFECYCLE
    # ==========================================================

    def start(self) -> bool:
       

        with self._state_lock:

            if self._shutdown_requested:
                log.warning(
                    "[CognitiveGovernor] Start rejected: shutdown requested"
                )
                return False

            if self._state in (
                GovernorState.RUNNING,
                GovernorState.STARTING,
            ):
                return True

            if self._thread is not None:
                if self._thread.is_alive():
                    return True

            self._state = GovernorState.STARTING
            self._mode = GovernorMode.MONITOR

            self.started_at = time.time()
            self._stop_event.clear()
            self._pause_event.clear()

            self._thread = threading.Thread(
                target=self._run,
                daemon=True,
                name="CognitiveGovernor",
            )

            self._thread.start()

            return True

    def stop(
        self,
        reason: str = "shutdown_requested",
        timeout: float = 2.0,
    ) -> bool:
       

        with self._state_lock:

            if self._state == GovernorState.STOPPED:
                return True

            self._shutdown_requested = True
            self._shutdown_reason = str(reason)

            self._state = GovernorState.STOPPING
            self._mode = GovernorMode.SHUTDOWN

            self._stop_event.set()
            self._pause_event.clear()

            thread = self._thread

        if (
            thread is not None
            and thread.is_alive()
            and thread is not threading.current_thread()
        ):
            thread.join(
                max(
                    0.0,
                    float(timeout),
                )
            )

        with self._state_lock:

            if (
                thread is None
                or not thread.is_alive()
            ):
                self._state = GovernorState.STOPPED
                self._mode = GovernorMode.SHUTDOWN
                self.stopped_at = time.time()

        log.info(
            "[CognitiveGovernor] Stopped | reason=%s",
            reason,
        )

        return True

    def shutdown(
        self,
        reason: str = "shutdown_requested",
    ) -> bool:
        return self.stop(reason)

    def pause(self) -> None:

        with self._state_lock:

            if self._state == GovernorState.RUNNING:

                self._state = GovernorState.PAUSED
                self._mode = GovernorMode.PASSIVE

                self._pause_event.set()

        log.info(
            "[CognitiveGovernor] Paused"
        )

    def resume(self) -> bool:

        with self._state_lock:

            if self._shutdown_requested:
                return False

            if self._state == GovernorState.PAUSED:

                self._pause_event.clear()

                self._state = GovernorState.RUNNING
                self._mode = GovernorMode.ADAPTIVE

                log.info(
                    "[CognitiveGovernor] Resumed"
                )

                return True

        return False

    def set_boot_complete(
        self,
        complete: bool = True,
    ) -> None:

        with self._state_lock:

            self._boot_complete = bool(complete)

        if complete:

            log.info(
                "[CognitiveGovernor] "
                "Boot complete | cognitive governance active"
            )

    def mark_system_ready(self) -> None:
      

        self.set_boot_complete(True)

    # ==========================================================
    # LIFECYCLE QUERIES
    # ==========================================================

    def is_running(self) -> bool:

        with self._state_lock:
            return self._state in (
                GovernorState.RUNNING,
                GovernorState.PRESSURE,
                GovernorState.BLOCKED,
            )

    def is_active(self) -> bool:
        return self.is_running()

    def is_booting(self) -> bool:

        with self._state_lock:

            if self._boot_complete:
                return False

            if self.started_at is None:
                return True

            return (
                time.time() - self.started_at
                < self.boot_grace_seconds
            )

    def is_shutdown_requested(self) -> bool:

        with self._state_lock:
            return self._shutdown_requested

    # ==========================================================
    # QBIT OBSERVATION
    # ==========================================================

    def observe_qbit(
        self,
        qbit: Any = None,
    ) -> None:
        

        with self._state_lock:

            if self._shutdown_requested:
                return

            if self._state in (
                GovernorState.CREATED,
                GovernorState.STOPPED,
                GovernorState.STOPPING,
            ):
                return

            self.qbit_counter += 1
            self.total_qbits_observed += 1

            self.qbit_history.append(
                time.monotonic()
            )

            intent = self._get_intent(qbit)

            if intent:
                self.intent_history.append(
                    intent
                )

    # ==========================================================
    # MAIN LOOP
    # ==========================================================

    def _run(self) -> None:

        with self._state_lock:

            self._state = GovernorState.RUNNING
            self._mode = GovernorMode.ADAPTIVE
            self.running_at = time.time()

        log.info(
            "[CognitiveGovernor] Worker started"
        )

        try:

            while not self._stop_event.wait(
                self.interval
            ):

                if self._pause_event.is_set():
                    continue

                if self._shutdown_requested:
                    break

                try:
                    self.tick()

                except Exception as exc:

                    log.exception(
                        "[CognitiveGovernor] "
                        "Tick failure: %s",
                        exc,
                    )

        finally:

            with self._state_lock:

                self._state = GovernorState.STOPPED
                self._mode = GovernorMode.SHUTDOWN
                self.stopped_at = time.time()

            log.info(
                "[CognitiveGovernor] Worker exited"
            )

    # ==========================================================
    # MAIN GOVERNOR TICK
    # ==========================================================

    def tick(self) -> None:
       

        with self._state_lock:

            if self._shutdown_requested:
                return

            if self._state in (
                GovernorState.CREATED,
                GovernorState.STOPPED,
                GovernorState.STOPPING,
                GovernorState.PAUSED,
            ):
                return

            self.total_ticks += 1

        now = time.monotonic()

        total = self._queue_size()

        self.current_queue_size = total
        self.history.append(total)

        self._update_throughput(now)

        # --------------------------------------------------
        # Boot gate
        #
        # During startup the Governor observes but does not
        # inject corrective cognition into a system that is
        # not fully online.
        # --------------------------------------------------

        if self.is_booting():

            self._set_mode(
                GovernorMode.MONITOR
            )

            return

        # --------------------------------------------------
        # Cognitive analysis
        # --------------------------------------------------

        self._detect_loop_behavior()
        self._adjust_pressure(total)

        # --------------------------------------------------
        # Periodic checks
        # --------------------------------------------------

        if now - self.last_check < 1.0:
            return

        self.last_check = now

        self.check_cognition_patterns()
        self.check_queue()
        self.check_memory()
        self.check_throughput()

    # ==========================================================
    # QUEUE SIZE
    # ==========================================================

    def _queue_size(self) -> int:

        try:

            priority_queues = getattr(
                self.queue_loop,
                "priority_queues",
                None,
            )

            if isinstance(
                priority_queues,
                dict,
            ):

                total = 0

                for q in priority_queues.values():

                    try:
                        total += max(
                            0,
                            int(q.qsize()),
                        )

                    except Exception:
                        continue

                return total

        except Exception as exc:

            log.debug(
                "[CognitiveGovernor] "
                "Queue size read failed: %s",
                exc,
            )

        # Fallback for queue implementations exposing qsize().
        try:

            qsize = getattr(
                self.queue_loop,
                "qsize",
                None,
            )

            if callable(qsize):
                return max(
                    0,
                    int(qsize()),
                )

        except Exception:
            pass

        return 0

    # ==========================================================
    # LOOP DETECTION
    # ==========================================================

    def _detect_loop_behavior(self) -> bool:

        if len(self.intent_history) < self.loop_trigger_count:
            return False

        recent = list(
            self.intent_history
        )[-self.loop_window:]

        meaningful = [
            value
            for value in recent
            if value
        ]

        if len(meaningful) < self.loop_trigger_count:
            return False

        unique = set(
            meaningful
        )

        detected = (
            len(unique)
            <= self.loop_intent_limit
        )

        self.cognitive_loop_detected = detected

        if not detected:
            return False

        now = time.monotonic()

        if (
            now - self._last_control
            < self.control_cooldown
        ):
            return True

        self.loop_events += 1
        self.last_reason = "cognitive_loop"

        self._set_mode(
            GovernorMode.PRESSURE
        )

        log.warning(
            "[CognitiveGovernor] "
            "Cognitive loop detected | intents=%s",
            meaningful,
        )

        self._emit(
            "COGNITIVE_LOOP",
            {
                "pattern": meaningful,
                "count": len(meaningful),
                "source": "CognitiveGovernor",
            },
        )

        self.inject_control_qbit(
            "THOUGHT_LOOP"
        )

        return True

    # ==========================================================
    # LOOP BREAKER
    # ==========================================================

    def _break_loop(self) -> None:

        self._set_throttle(
            0.01
        )

        self.last_reason = "loop_throttle"

    # ==========================================================
    # PRESSURE CONTROL
    # ==========================================================

    def _adjust_pressure(
        self,
        total: int,
    ) -> None:

        now = time.monotonic()

        if (
            now - self.last_adjust
            < 0.2
        ):
            return

        self.last_adjust = now

        # --------------------------------------------------
        # ConstraintGuardian has authority over physical
        # resource pressure. Governor should cooperate rather
        # than duplicate that logic.
        # --------------------------------------------------

        guardian_state = self._guardian_state()

        if guardian_state == "block":

            self.queue_pressure = True
            self._set_mode(
                GovernorMode.PROTECT
            )

            self._set_throttle(
                0.02
            )

            return

        if guardian_state in (
            "warning",
            "pressure",
        ):

            self.queue_pressure = True
            self._set_mode(
                GovernorMode.PRESSURE
            )

        # --------------------------------------------------
        # Queue pressure
        # --------------------------------------------------

        if total >= self.critical_queue_size:

            self.queue_pressure = True

            self._set_mode(
                GovernorMode.PROTECT
            )

            self._set_throttle(
                0.02
            )

            if (
                now - self._last_pressure_event
                >= self.pressure_cooldown
            ):

                self._last_pressure_event = now

                log.warning(
                    "[CognitiveGovernor] "
                    "Critical cognitive queue load | size=%s",
                    total,
                )

            return

        if total >= self.max_queue_size:

            self.queue_pressure = True

            self._set_mode(
                GovernorMode.PRESSURE
            )

            self._set_throttle(
                0.005
            )

            return

        # --------------------------------------------------
        # Normal operation
        # --------------------------------------------------

        self.queue_pressure = False

        if not (
            self.memory_pressure
            or self.throughput_pressure
            or self.cognitive_loop_detected
        ):

            self._set_mode(
                GovernorMode.ADAPTIVE
            )

            self._set_throttle(
                0.001
            )

    # ==========================================================
    # THROTTLE
    # ==========================================================

    def _set_throttle(
        self,
        delay: float,
    ) -> None:

        delay = max(
            0.0,
            float(delay),
        )

        try:

            if hasattr(
                self.queue_loop,
                "throttle_delay",
            ):

                self.queue_loop.throttle_delay = delay

                self.current_throttle_delay = delay

        except Exception as exc:

            log.debug(
                "[CognitiveGovernor] "
                "Throttle update failed: %s",
                exc,
            )

    # ==========================================================
    # QUEUE CHECK
    # ==========================================================

    def check_queue(self) -> None:

        size = self._queue_size()

        self.current_queue_size = size

        if size > self.max_queue:

            self.queue_storm_events += 1
            self.queue_pressure = True
            self.last_reason = "queue_storm"

            log.warning(
                "[CognitiveGovernor] "
                "Queue storm detected | size=%s",
                size,
            )

            self.inject_control_qbit(
                "QUEUE_STORM"
            )

    # ==========================================================
    # MEMORY CHECK
    # ==========================================================

    def check_memory(self) -> None:

        if self.memory_graph is None:
            return

        try:

            stats = self.memory_graph.stats()

            if not isinstance(
                stats,
                dict,
            ):
                return

            nodes = stats.get(
                "nodes",
                0,
            )

            if isinstance(
                nodes,
                dict,
            ):
                nodes = len(nodes)

            nodes = int(
                nodes or 0
            )

            self.current_memory_nodes = nodes

            if nodes > self.max_memory_nodes:

                self.memory_pressure = True
                self.memory_overload_events += 1
                self.last_reason = "memory_overload"

                log.warning(
                    "[CognitiveGovernor] "
                    "Memory overload detected | nodes=%s",
                    nodes,
                )

                self.inject_control_qbit(
                    "MEMORY_OVERLOAD"
                )

            else:

                self.memory_pressure = False

        except Exception as exc:

            log.debug(
                "[CognitiveGovernor] "
                "Memory check failed: %s",
                exc,
            )

    # ==========================================================
    # THROUGHPUT CHECK
    # ==========================================================

    def _update_throughput(
        self,
        now: float,
    ) -> None:

        elapsed = now - self.window_start

        if elapsed < 1.0:
            return

        self.current_qbit_rate = int(
            self.qbit_counter
            / max(
                elapsed,
                0.001,
            )
        )

        self.qbit_counter = 0
        self.window_start = now

    def check_throughput(self) -> None:

        rate = self.current_qbit_rate

        if rate > self.max_qbit_rate:

            self.throughput_pressure = True
            self.cognition_spike_events += 1
            self.last_reason = "cognition_spike"

            log.warning(
                "[CognitiveGovernor] "
                "Cognition spike detected | rate=%s qbits/s",
                rate,
            )

            self.inject_control_qbit(
                "COGNITION_SPIKE"
            )

        else:

            self.throughput_pressure = False

    # ==========================================================
    # COGNITION MAP CHECK
    # ==========================================================

    def check_cognition_patterns(self) -> None:

        cmap = self.cognition_map

        if cmap is None:
            return

        try:

            detector = getattr(
                cmap,
                "detect_loops",
                None,
            )

            if not callable(detector):
                return

            loops = detector()

            if not loops:
                return

            for intent, count in loops:

                log.warning(
                    "[CognitiveGovernor] "
                    "CognitionMap loop | intent=%s | count=%s",
                    intent,
                    count,
                )

                self.inject_control_qbit(
                    "THOUGHT_LOOP"
                )

                # Do not inject one control qbit for every detected
                # historical edge in a single tick.
                break

        except Exception as exc:

            log.debug(
                "[CognitiveGovernor] "
                "Cognition pattern check failed: %s",
                exc,
            )

    # ==========================================================
    # CONSTRAINT GUARDIAN
    # ==========================================================

    def _guardian_state(self) -> Optional[str]:

        guardian = self.constraint_guardian

        if guardian is None:
            return None

        try:

            getter = getattr(
                guardian,
                "get_state",
                None,
            )

            if callable(getter):
                return getter()

        except Exception as exc:

            log.debug(
                "[CognitiveGovernor] "
                "ConstraintGuardian query failed: %s",
                exc,
            )

        return None

    # ==========================================================
    # CONTROL OUTPUT
    # ==========================================================

    def inject_control_qbit(
        self,
        reason: str,
    ) -> bool:
        

        now = time.monotonic()

        with self._state_lock:

            if self._shutdown_requested:
                self.control_qbits_suppressed += 1
                return False

            if self._state in (
                GovernorState.CREATED,
                GovernorState.STOPPED,
                GovernorState.STOPPING,
            ):
                self.control_qbits_suppressed += 1
                return False

            if self.is_booting():
                self.control_qbits_suppressed += 1
                return False

            if (
                now - self._last_control
                < self.control_cooldown
            ):
                self.control_qbits_suppressed += 1
                return False

            self._last_control = now

        # --------------------------------------------------
        # Build control packet.
        #
        # Keep it dict-compatible because QbitQueueLoop in
        # this system accepts dictionary-style packets.
        # --------------------------------------------------

        qbit = {
            "intent": "SYSTEM_CONTROL",
            "task_id": (
                f"governor-{int(time.time() * 1000)}"
            ),
            "timestamp": time.time(),
            "metadata": {
                "reason": str(reason),
                "origin": "COGNITIVE_GOVERNOR",
                "governor_state": self.get_state(),
                "governor_mode": self.get_mode(),
                "queue_size": self.current_queue_size,
                "qbit_rate": self.current_qbit_rate,
                "memory_nodes": self.current_memory_nodes,
            },
        }

        try:

            putter = getattr(
                self.queue_loop,
                "put",
                None,
            )

            if not callable(putter):

                self.control_qbits_suppressed += 1

                log.error(
                    "[CognitiveGovernor] "
                    "QueueLoop has no callable put()"
                )

                return False

            # CRITICAL is intentionally explicit.
            try:

                putter(
                    qbit,
                    priority=GovernorPriority.CRITICAL,
                )

            except TypeError:

                # Compatibility with QueueLoop implementations
                # whose put() does not expose priority.
                putter(qbit)

            self.control_qbits_injected += 1

            self.last_reason = str(reason)

            self._emit(
                "GOVERNOR_CONTROL",
                qbit,
            )

            log.warning(
                "[CognitiveGovernor] "
                "Control qbit injected | reason=%s",
                reason,
            )

            return True

        except Exception as exc:

            log.exception(
                "[CognitiveGovernor] "
                "Control injection failed: %s",
                exc,
            )

            return False

    # ==========================================================
    # EVENT EMISSION
    # ==========================================================

    def _emit(
        self,
        event_name: str,
        payload: Dict[str, Any],
    ) -> None:

        bus = self.event_bus

        if bus is None:
            return

        try:

            emitter = getattr(
                bus,
                "emit",
                None,
            )

            if callable(emitter):

                emitter(
                    event_name,
                    payload,
                )

                return

            publisher = getattr(
                bus,
                "publish",
                None,
            )

            if callable(publisher):

                try:

                    publisher(
                        event_name,
                        payload=payload,
                        source="CognitiveGovernor",
                    )

                except TypeError:

                    publisher(
                        event_name,
                        payload,
                    )

        except Exception as exc:

            log.debug(
                "[CognitiveGovernor] "
                "Event emission failed: %s",
                exc,
            )

    # ==========================================================
    # STATE / MODE
    # ==========================================================

    def _set_mode(
        self,
        mode: str,
    ) -> None:

        with self._state_lock:

            self._mode = str(mode)

            if self._shutdown_requested:
                self._state = GovernorState.STOPPING
                return

            if self._state in (
                GovernorState.CREATED,
                GovernorState.STARTING,
                GovernorState.STOPPED,
            ):
                return

            if mode == GovernorMode.PROTECT:
                self._state = GovernorState.BLOCKED

            elif mode == GovernorMode.PRESSURE:
                self._state = GovernorState.PRESSURE

            elif mode == GovernorMode.PASSIVE:
                self._state = GovernorState.PAUSED

            else:
                self._state = GovernorState.RUNNING

    def get_state(self) -> str:

        with self._state_lock:
            return self._state

    def get_mode(self) -> str:

        with self._state_lock:
            return self._mode

    # ==========================================================
    # QBIT HELPERS
    # ==========================================================

    @staticmethod
    def _get_intent(
        qbit: Any,
    ) -> Optional[str]:

        if qbit is None:
            return None

        try:

            if isinstance(
                qbit,
                dict,
            ):

                value = qbit.get(
                    "intent"
                )

            else:

                value = getattr(
                    qbit,
                    "intent",
                    None,
                )

            if value is None:
                return None

            return str(value)

        except Exception:
            return None

    # ==========================================================
    # STATUS
    # ==========================================================

    def status(self) -> Dict[str, Any]:

        with self._state_lock:

            return {
                "module": "CognitiveGovernor",
                "version": __version__,
                "build": __build__,
                "state": self._state,
                "mode": self._mode,
                "active": self._state in (
                    GovernorState.RUNNING,
                    GovernorState.PRESSURE,
                    GovernorState.BLOCKED,
                ),
                "boot_complete": self._boot_complete,
                "booting": self.is_booting(),
                "shutdown_requested": (
                    self._shutdown_requested
                ),
                "queue_size": self.current_queue_size,
                "qbit_rate": self.current_qbit_rate,
                "memory_nodes": self.current_memory_nodes,
                "pressure_level": self.pressure_level,
                "queue_pressure": self.queue_pressure,
                "memory_pressure": self.memory_pressure,
                "throughput_pressure": (
                    self.throughput_pressure
                ),
                "cognitive_loop": (
                    self.cognitive_loop_detected
                ),
                "throttle_delay": (
                    self.current_throttle_delay
                ),
                "qbits_observed": (
                    self.total_qbits_observed
                ),
                "control_qbits": (
                    self.control_qbits_injected
                ),
                "control_suppressed": (
                    self.control_qbits_suppressed
                ),
                "last_reason": self.last_reason,
            }

    # ==========================================================
    # DIAGNOSTICS
    # ==========================================================

    def diagnostics(self) -> Dict[str, Any]:

        data = self.status()

        with self._state_lock:

            data.update(
                {
                    "total_ticks": self.total_ticks,
                    "loop_events": self.loop_events,
                    "queue_storm_events": (
                        self.queue_storm_events
                    ),
                    "memory_overload_events": (
                        self.memory_overload_events
                    ),
                    "cognition_spike_events": (
                        self.cognition_spike_events
                    ),
                    "history_depth": len(
                        self.history
                    ),
                    "intent_history_depth": len(
                        self.intent_history
                    ),
                    "thread_alive": bool(
                        self._thread
                        and self._thread.is_alive()
                    ),
                    "shutdown_reason": (
                        self._shutdown_reason
                    ),
                    "started_at": self.started_at,
                    "running_at": self.running_at,
                    "stopped_at": self.stopped_at,
                }
            )

        return data

    # ==========================================================
    # RESET
    # ==========================================================

    def reset_pressure(self) -> None:

        with self._state_lock:

            self.queue_pressure = False
            self.memory_pressure = False
            self.throughput_pressure = False
            self.cognitive_loop_detected = False

            self.pressure_level = 0.0

            self.last_reason = "manual_reset"

            self._set_mode(
                GovernorMode.ADAPTIVE
            )

        log.info(
            "[CognitiveGovernor] "
            "Pressure state reset"
        )

    # ==========================================================
    # REPRESENTATION
    # ==========================================================

    def __repr__(self) -> str:

        return (
            "CognitiveGovernor("
            f"state={self.get_state()}, "
            f"mode={self.get_mode()}, "
            f"queue={self.current_queue_size}, "
            f"qbit_rate={self.current_qbit_rate}, "
            f"boot_complete={self._boot_complete}, "
            f"shutdown={self._shutdown_requested}"
            ")"
        )


# ==========================================================
# MODULE-LEVEL START
# ==========================================================

def start_governor(
    queue_loop,
    memory_graph=None,
    event_bus=None,
    constraint_guardian=None,
    *,
    auto_boot_complete: bool = False,
) -> CognitiveGovernor:


    governor = CognitiveGovernor(
        queue_loop=queue_loop,
        memory_graph=memory_graph,
        event_bus=event_bus,
        constraint_guardian=constraint_guardian,
    )

    if auto_boot_complete:
        governor.set_boot_complete(True)

    governor.start()

    return governor


# ==========================================================
# COMPATIBILITY ALIASES
# ==========================================================

CognitiveGovernorController = CognitiveGovernor


# ==========================================================
# MODULE EXPORTS
# ==========================================================

__all__ = [
    "GovernorState",
    "GovernorMode",
    "GovernorPriority",
    "CognitiveGovernor",
    "CognitiveGovernorController",
    "start_governor",
]