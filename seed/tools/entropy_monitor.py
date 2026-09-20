# =============================================================
# SEED-AI ENTROPY MONITOR NODE
#
# File: SEED_ROOT/seed/tools/entropy_monitor.py
#
# ROLE:
#   Runtime stability / entropy observation neural node.
#
# PURPOSE:
#   - Observe event timing variance
#   - Observe asynchronous task drift
#   - Estimate runtime entropy / instability
#   - Report stability state
#   - Provide structured telemetry to the tool fabric
#
# AUTHORITY:
#   OBSERVATION ONLY.
#
#   This node does NOT:
#   - execute commands
#   - control QbitDialer
#   - create QbitQueueLoop
#   - create EventBus
#   - create TrackSystem
#   - create NeuralBridge
#   - create Registry
#   - modify SEED runtime state
#
#   QbitDialer remains the command authority.
#
# DESIGN:
#   EntropyMonitor observes the runtime.
#   The higher-level tool fabric can route its observations
#   toward the appropriate SEED system components.
#
# =============================================================

import logging
import statistics
import threading
import time
import uuid
from collections import deque

from seed.tools.base_tool import BaseTool


logger = logging.getLogger("EntropyMonitor")


class EntropyMonitor(BaseTool):

    NODE_TYPE = "tool.entropy_monitor"
    NODE_VERSION = "2.0.0"

    def __init__(
        self,
        sample_size=100,
        interval=0.05,
        stability_threshold=0.3,
        auto_monitor=True,
        name="entropy_monitor",
    ):
        super().__init__(
            name=name,
            capabilities=[
                "entropy_monitoring",
                "runtime_stability",
                "event_jitter_detection",
                "task_jitter_detection",
                "runtime_health_observation",
                "chaos_detection",
                "timing_analysis",
            ],
            dependencies=[],
            role="runtime-observer",
            version=self.NODE_VERSION,
            always_on=False,
        )

        self.node_instance_id = (
            f"ENTROPY."
            f"{uuid.uuid4().hex[:12]}"
        )

        self.sample_size = max(
            2,
            int(sample_size),
        )

        self.interval = max(
            0.01,
            float(interval),
        )

        self.stability_threshold = float(
            stability_threshold
        )

        self.auto_monitor = bool(
            auto_monitor
        )

        # RLock is required because lifecycle/event methods
        # may update state while computing telemetry.
        self._lock = threading.RLock()

        self.event_intervals = deque(
            maxlen=self.sample_size
        )

        self.task_jitter = deque(
            maxlen=self.sample_size
        )

        self._last_event_time = None

        self._running = False
        self._monitor_thread = None

        self.entropy_score = 0.0

        self._event_count = 0
        self._task_count = 0
        self._compute_count = 0
        self._error_count = 0

        self._last_compute_time = None
        self._last_event_interval = None
        self._last_task_drift = None

    # =========================================================
    # START
    # =========================================================

    def start(self):

        with self._lock:

            if self._running:
                return self.status()

            self._running = True
            self.active = True
            self.ready = True
            self.failed = False
            self.degraded = False

            self.started_at = time.time()

            if self.auto_monitor:
                self._monitor_thread = threading.Thread(
                    target=self._update_loop,
                    name="SEED-EntropyMonitor",
                    daemon=True,
                )

                self._monitor_thread.start()

        logger.info(
            "[%s] Started | node_id=%s",
            self.name,
            self.node_id,
        )

        return self.status()

    # =========================================================
    # STOP
    # =========================================================

    def stop(self):

        with self._lock:
            self._running = False
            self.active = False
            self.ready = False
            self.stopped_at = time.time()

        logger.info(
            "[%s] Stopped",
            self.name,
        )

        return self.status()

    # =========================================================
    # EVENT OBSERVATION
    # =========================================================

    def log_event(self, timestamp=None):
   
        now = (
            float(timestamp)
            if timestamp is not None
            else time.time()
        )

        with self._lock:

            if self._last_event_time is not None:

                interval = (
                    now -
                    self._last_event_time
                )

                # Ignore impossible negative timestamps.
                if interval >= 0:
                    self.event_intervals.append(
                        interval
                    )

                    self._last_event_interval = (
                        interval
                    )

            self._last_event_time = now
            self._event_count += 1
            self.last_activity = now

            self._compute_entropy_locked()

        return self.entropy_score

    # =========================================================
    # ASYNC TASK OBSERVATION
    # =========================================================

    def log_task(self, task_timestamp):


        now = time.time()

        try:
            task_timestamp = float(
                task_timestamp
            )
        except (
            TypeError,
            ValueError,
        ) as exc:

            self._error_count += 1

            logger.warning(
                "[%s] Invalid task timestamp | error=%s",
                self.name,
                exc,
            )

            return self.entropy_score

        drift = now - task_timestamp

        with self._lock:

            if drift >= 0:
                self.task_jitter.append(
                    drift
                )

            self._last_task_drift = drift
            self._task_count += 1
            self.last_activity = now

            self._compute_entropy_locked()

        return self.entropy_score

    # =========================================================
    # ENTROPY COMPUTATION
    # =========================================================

    def _compute_entropy_locked(self):


        if (
            not self.event_intervals
            and not self.task_jitter
        ):
            self.entropy_score = 0.0
            return

        try:

            interval_variance = (
                statistics.variance(
                    self.event_intervals
                )
                if len(self.event_intervals) > 1
                else 0.0
            )

            jitter_variance = (
                statistics.variance(
                    self.task_jitter
                )
                if len(self.task_jitter) > 1
                else 0.0
            )

            raw_entropy = (
                interval_variance +
                jitter_variance
            ) * 10.0

            self.entropy_score = min(
                1.0,
                max(
                    0.0,
                    raw_entropy,
                ),
            )

            self._compute_count += 1
            self._last_compute_time = time.time()

        except Exception as exc:

            self._error_count += 1

            logger.warning(
                "[%s] Entropy computation failed | error=%s",
                self.name,
                exc,
            )

            # Fail-safe observation state.
            self.entropy_score = 1.0

    # =========================================================
    # PUBLIC ENTROPY COMPUTATION
    # =========================================================

    def compute_entropy(self):


        with self._lock:
            self._compute_entropy_locked()
            return self.entropy_score

    # =========================================================
    # STABILITY
    # =========================================================

    def is_stable(self, threshold=None):


        if threshold is None:
            threshold = self.stability_threshold

        try:
            threshold = float(
                threshold
            )
        except (
            TypeError,
            ValueError,
        ):
            threshold = self.stability_threshold

        with self._lock:
            return (
                self.entropy_score <= threshold
            )

    def stability_state(self):


        with self._lock:

            score = self.entropy_score
            threshold = self.stability_threshold

            if score <= threshold:
                state = "STABLE"
            elif score <= min(
                1.0,
                threshold + 0.2,
            ):
                state = "DEGRADED"
            else:
                state = "CHAOTIC"

            return {
                "state": state,
                "entropy_score": score,
                "threshold": threshold,
                "stable": score <= threshold,
                "timestamp": time.time(),
            }

    # =========================================================
    # BACKGROUND OBSERVER
    # =========================================================

    def _update_loop(self):


        while True:

            with self._lock:
                if not self._running:
                    break

                self._compute_entropy_locked()

            time.sleep(
                self.interval
            )

    # =========================================================
    # SNAPSHOT
    # =========================================================

    def snapshot(self):

        with self._lock:

            state = self.stability_state()

            return {
                "node_id": self.node_id,
                "node_instance_id": (
                    self.node_instance_id
                ),

                "entropy_score": (
                    self.entropy_score
                ),

                "stability": state,

                "recent_event_intervals": list(
                    self.event_intervals
                ),

                "recent_task_jitter": list(
                    self.task_jitter
                ),

                "event_count": (
                    self._event_count
                ),

                "task_count": (
                    self._task_count
                ),

                "compute_count": (
                    self._compute_count
                ),

                "error_count": (
                    self._error_count
                ),

                "last_event_interval": (
                    self._last_event_interval
                ),

                "last_task_drift": (
                    self._last_task_drift
                ),

                "last_compute_time": (
                    self._last_compute_time
                ),

                "timestamp": time.time(),
            }

    # =========================================================
    # STRUCTURED TELEMETRY
    # =========================================================

    def build_report(self):

        snap = self.snapshot()

        return {
            "type": "entropy_monitor_report",

            "source": {
                "node_id": self.node_id,
                "node_instance_id": (
                    self.node_instance_id
                ),
                "tool": self.name,
            },

            "observation": {
                "entropy_score": (
                    snap["entropy_score"]
                ),

                "stability_state": (
                    snap["stability"]["state"]
                ),

                "stable": (
                    snap["stability"]["stable"]
                ),

                "threshold": (
                    snap["stability"]["threshold"]
                ),
            },

            "measurements": {
                "event_count": (
                    snap["event_count"]
                ),

                "task_count": (
                    snap["task_count"]
                ),

                "event_interval_samples": len(
                    snap["recent_event_intervals"]
                ),

                "task_jitter_samples": len(
                    snap["recent_task_jitter"]
                ),

                "last_event_interval": (
                    snap["last_event_interval"]
                ),

                "last_task_drift": (
                    snap["last_task_drift"]
                ),
            },

            "health": {
                "error_count": (
                    snap["error_count"]
                ),
            },

            "timestamp": time.time(),
        }

    # =========================================================
    # STATUS
    # =========================================================

    def status(self):

        base = super().status()

        with self._lock:

            base.update(
                {
                    "running": self._running,

                    "node_instance_id": (
                        self.node_instance_id
                    ),

                    "sample_size": (
                        self.sample_size
                    ),

                    "interval": (
                        self.interval
                    ),

                    "stability_threshold": (
                        self.stability_threshold
                    ),

                    "auto_monitor": (
                        self.auto_monitor
                    ),

                    "entropy_score": (
                        self.entropy_score
                    ),

                    "stability_state": (
                        self.stability_state()[
                            "state"
                        ]
                    ),

                    "event_count": (
                        self._event_count
                    ),

                    "task_count": (
                        self._task_count
                    ),

                    "compute_count": (
                        self._compute_count
                    ),

                    "error_count": (
                        self._error_count
                    ),

                    "last_compute_time": (
                        self._last_compute_time
                    ),
                }
            )

        return base

    # =========================================================
    # DISPLAY
    # =========================================================

    def show_status(self):

        snap = self.snapshot()

        logger.info(
            "[%s] Entropy Score: %.3f | State: %s",
            self.name,
            snap["entropy_score"],
            snap["stability"]["state"],
        )

        logger.debug(
            "[%s] Event Intervals: %s",
            self.name,
            snap["recent_event_intervals"],
        )

        logger.debug(
            "[%s] Task Jitter: %s",
            self.name,
            snap["recent_task_jitter"],
        )

        return snap


__all__ = [
    "EntropyMonitor",
]