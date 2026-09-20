# ==========================================================
# FILE: goal_engine.py
# PATH: seed/core/cognition/goal_engine.py
#
# SYSTEM: SEED AI OS
# COMPONENT: GoalEngine
# VERSION: 2.0.0
# BUILD: PASSIVE / BOOT-GATED / SINGLE-LOOP / CLEAN-SHUTDOWN
# UPDATED: 2026-08-19
#
# PURPOSE:
# ----------------------------------------------------------
# GoalEngine generates high-level cognitive goals for SEED.
#
# GOALS:
#
#     MAP_SYSTEM
#     ANALYZE_MEMORY
#     OPTIMIZE_PIPELINE
#     REFLECT
#     EXPLORE
#
# IMPORTANT LIFECYCLE RULE:
# ----------------------------------------------------------
# GoalEngine is PASSIVE until explicitly started.
#
# It MUST NOT:
#
#   - start a thread during construction
#   - start during module import
#   - generate goals before runtime authorization
#   - create duplicate worker loops
#   - queue the same goal twice
#   - restart itself automatically
#   - continue after shutdown
#
# The owner/orchestrator controls:
#
#     start()
#     stop()
#
# Compatibility:
#
#     start_goal_engine()
#
# remains available for existing boot code.
#
# ==========================================================

from __future__ import annotations

import logging
import threading
import time
import uuid
from typing import Any, Dict, Optional


log = logging.getLogger("GoalEngine")


# ==========================================================
# GOAL ENGINE
# ==========================================================

class GoalEngine:

    VERSION = "2.0.0"
    NAME = "GoalEngine"

    DEFAULT_INTERVAL = 10.0

    GOALS = (
        "MAP_SYSTEM",
        "OPTIMIZE_PIPELINE",
        "ANALYZE_MEMORY",
        "TEST_NEW_STRATEGY",
        "REFLECT",
    )

    def __init__(
        self,
        queue_loop,
        *,
        qbit_dialer=None,
        interval: float = DEFAULT_INTERVAL,
        auto_start: bool = False,
    ):
        

        # --------------------------------------------------
        # Dependency.
        # --------------------------------------------------

        self.queue_loop = queue_loop
        self.qbit_dialer = qbit_dialer

        self.memory_graph = getattr(
            queue_loop,
            "memory_graph",
            None,
        )

        # --------------------------------------------------
        # Configuration.
        # --------------------------------------------------

        try:
            interval = float(interval)
        except (TypeError, ValueError):
            interval = self.DEFAULT_INTERVAL

        self.interval = max(
            0.1,
            interval,
        )

        self.goals = list(
            self.GOALS
        )

        # --------------------------------------------------
        # Goal timing.
        # --------------------------------------------------

        self.last_goal = 0.0

        # --------------------------------------------------
        # Lifecycle.
        # --------------------------------------------------

        self._running = False
        self._stop_requested = False

        self._thread: Optional[
            threading.Thread
        ] = None

        self._state_lock = threading.RLock()
        self._stop_event = threading.Event()

        # --------------------------------------------------
        # Diagnostics.
        # --------------------------------------------------

        self._start_count = 0
        self._stop_count = 0
        self._goal_count = 0

        self._last_goal = None
        self._last_error = None

        self.started_at = None
        self.stopped_at = None

        log.debug(
            "[GoalEngine] initialized | "
            "version=%s | interval=%.2fs | auto_start=%s",
            self.VERSION,
            self.interval,
            bool(auto_start),
        )

        # --------------------------------------------------
        # Explicit constructor start only.
        # --------------------------------------------------

        if auto_start:
            self.start()

    # ======================================================
    # TICK
    # ======================================================

    def tick(self):
        

        with self._state_lock:

            if not self._running:
                return None

            now = time.monotonic()

            if (
                now - self.last_goal
                < self.interval
            ):
                return None

            self.last_goal = now

        # --------------------------------------------------
        # Read memory graph safely.
        # --------------------------------------------------

        stats = None

        memory_graph = self.memory_graph

        if memory_graph is not None:

            try:

                stats_method = getattr(
                    memory_graph,
                    "stats",
                    None,
                )

                if callable(stats_method):
                    stats = stats_method()

            except Exception as exc:

                self._last_error = (
                    f"memory_graph.stats failed: {exc}"
                )

                log.debug(
                    "[GoalEngine] memory graph stats "
                    "unavailable: %s",
                    exc,
                )

                stats = None

        # --------------------------------------------------
        # Safely determine node count.
        # --------------------------------------------------

        nodes = 0

        if isinstance(
            stats,
            dict,
        ):

            try:
                nodes = int(
                    stats.get(
                        "nodes",
                        0,
                    )
                )
            except (
                TypeError,
                ValueError,
            ):
                nodes = 0

        # --------------------------------------------------
        # Select goal.
        # --------------------------------------------------

        goal = self._select_goal(
            nodes
        )

        # --------------------------------------------------
        # Create exactly ONE task payload.
        # --------------------------------------------------

        qbit = {
            "task_id": str(
                uuid.uuid4()
            ),

            "intent": goal,

            "timestamp": time.time(),

            "metadata": {
                "source": "GOAL_ENGINE",
                "memory_nodes": nodes,
                "goal_engine_version": (
                    self.VERSION
                ),
            },
        }

        # --------------------------------------------------
        # Queue exactly once.
        # --------------------------------------------------

        try:

            receive = getattr(self.qbit_dialer, "receive_qbit", None) if self.qbit_dialer is not None else None
            if callable(receive):
                result = receive(qbit)
                if result is False:
                    return None
                with self._state_lock:
                    self._goal_count += 1
                    self._last_goal = dict(qbit)
                    self._last_error = None
                return qbit

            put_method = getattr(
                self.queue_loop,
                "put",
                None,
            )

            if not callable(put_method):

                self._last_error = (
                    "queue_loop.put unavailable"
                )

                log.error(
                    "[GoalEngine] "
                    "queue_loop.put unavailable"
                )

                return None

            result = put_method(
                qbit,
                priority="NORMAL",
            )

            # ----------------------------------------------
            # Record successful goal generation.
            # ----------------------------------------------

            with self._state_lock:

                self._goal_count += 1

                self._last_goal = dict(
                    qbit
                )

                self._last_error = None

            log.info(
                "[GoalEngine] generated goal=%s "
                "memory_nodes=%d "
                "task_id=%s",
                goal,
                nodes,
                qbit["task_id"],
            )

            return qbit

        except Exception as exc:

            self._last_error = str(
                exc
            )

            log.exception(
                "[GoalEngine] failed to queue goal"
            )

            return None

    # ======================================================
    # GOAL SELECTION
    # ======================================================

    def _select_goal(
        self,
        nodes: int,
    ) -> str:
        

        if nodes < 200:
            return "MAP_SYSTEM"

        if nodes < 1000:
            return "ANALYZE_MEMORY"

        if nodes < 5000:
            return "OPTIMIZE_PIPELINE"

        return "REFLECT"

    # ======================================================
    # START
    # ======================================================

    def start(self) -> bool:
        

        with self._state_lock:

            # ----------------------------------------------
            # Duplicate start protection.
            # ----------------------------------------------

            if self._running:

                log.debug(
                    "[GoalEngine] start ignored | "
                    "already running"
                )

                return False

            # ----------------------------------------------
            # Do not create a second worker while the first
            # thread still exists.
            # ----------------------------------------------

            if (
                self._thread is not None
                and self._thread.is_alive()
            ):

                log.warning(
                    "[GoalEngine] start refused | "
                    "worker thread still alive"
                )

                return False

            # ----------------------------------------------
            # Reset lifecycle signals.
            # ----------------------------------------------

            self._stop_requested = False
            self._stop_event.clear()

            self.last_goal = (
                time.monotonic()
                - self.interval
            )

            self._running = True

            self.started_at = time.time()
            self.stopped_at = None

            self._start_count += 1

            # ----------------------------------------------
            # Create exactly one worker.
            # ----------------------------------------------

            thread = threading.Thread(
                target=self._run_loop,
                daemon=True,
                name="GoalEngine",
            )

            self._thread = thread

            try:

                thread.start()

            except Exception:

                self._running = False
                self._stop_requested = True
                self._thread = None

                log.exception(
                    "[GoalEngine] "
                    "failed to start worker"
                )

                return False

        log.info(
            "[GoalEngine] started | "
            "interval=%.2fs",
            self.interval,
        )

        return True

    # ======================================================
    # EXECUTION LOOP
    # ======================================================

    def _run_loop(self) -> None:
        

        log.debug(
            "[GoalEngine] execution loop online"
        )

        try:

            while not self._stop_event.wait(
                self._loop_sleep_interval()
            ):

                with self._state_lock:

                    if (
                        not self._running
                        or self._stop_requested
                    ):
                        break

                self.tick()

        except Exception:

            log.exception(
                "[GoalEngine] execution loop failure"
            )

        finally:

            with self._state_lock:

                self._running = False
                self._stop_requested = True
                self.stopped_at = time.time()

            log.debug(
                "[GoalEngine] execution loop offline"
            )

    # ======================================================
    # LOOP INTERVAL
    # ======================================================

    def _loop_sleep_interval(
        self,
    ) -> float:
     

        return max(
            0.05,
            min(
                self.interval / 4.0,
                1.0,
            ),
        )

    # ======================================================
    # STOP
    # ======================================================

    def stop(
        self,
        *,
        timeout: float = 2.0,
    ) -> bool:
        

        with self._state_lock:

            was_running = self._running

            if not was_running:

                self._stop_requested = True
                self._stop_event.set()

                return False

            self._stop_requested = True
            self._running = False

            self._stop_count += 1
            self.stopped_at = time.time()

            thread = self._thread

            self._stop_event.set()

        # --------------------------------------------------
        # Never join ourselves.
        # --------------------------------------------------

        if (
            thread is not None
            and thread.is_alive()
            and thread is not threading.current_thread()
        ):

            try:

                thread.join(
                    timeout=max(
                        0.0,
                        float(timeout),
                    )
                )

            except Exception:

                log.exception(
                    "[GoalEngine] "
                    "worker join failed"
                )

        with self._state_lock:

            if (
                self._thread is not None
                and not self._thread.is_alive()
            ):
                self._thread = None

        log.info(
            "[GoalEngine] stopped"
        )

        return True

    # ======================================================
    # SHUTDOWN ALIAS
    # ======================================================

    def shutdown(
        self,
        *,
        timeout: float = 2.0,
    ) -> bool:
       

        return self.stop(
            timeout=timeout
        )

    # ======================================================
    # RESET
    # ======================================================

    def reset(
        self,
        *,
        stop: bool = True,
    ) -> None:
      

        if stop:
            self.stop()

        with self._state_lock:

            self.last_goal = 0.0

            self._goal_count = 0
            self._last_goal = None
            self._last_error = None

            self._stop_requested = (
                not self._running
            )

        log.debug(
            "[GoalEngine] reset"
        )

    # ======================================================
    # STATE
    # ======================================================

    @property
    def running(self) -> bool:

        with self._state_lock:
            return self._running

    # ------------------------------------------------------

    @property
    def stopped(self) -> bool:

        with self._state_lock:
            return not self._running

    # ------------------------------------------------------

    @property
    def thread(self):

        with self._state_lock:
            return self._thread

    # ======================================================
    # STATUS
    # ======================================================

    def status(self) -> Dict[str, Any]:
       

        with self._state_lock:

            thread = self._thread

            return {
                "name": self.NAME,
                "version": self.VERSION,
                "running": self._running,
                "stop_requested": (
                    self._stop_requested
                ),
                "interval": self.interval,
                "goal_count": self._goal_count,
                "last_goal": (
                    dict(self._last_goal)
                    if isinstance(
                        self._last_goal,
                        dict,
                    )
                    else None
                ),
                "last_error": self._last_error,
                "start_count": self._start_count,
                "stop_count": self._stop_count,
                "thread_alive": bool(
                    thread
                    and thread.is_alive()
                ),
                "started_at": self.started_at,
                "stopped_at": self.stopped_at,
            }

    # ======================================================
    # REPRESENTATION
    # ======================================================

    def __repr__(
        self,
    ) -> str:

        with self._state_lock:

            return (
                "GoalEngine("
                f"version={self.VERSION!r}, "
                f"interval={self.interval:.2f}, "
                f"running={self._running!r}, "
                f"goals={self._goal_count}"
                ")"
            )


# ==========================================================
# COMPATIBILITY START FUNCTION
# ==========================================================

def start_goal_engine(
    queue_loop,
    *,
    interval: float = GoalEngine.DEFAULT_INTERVAL,
) -> GoalEngine:


    engine = GoalEngine(
        queue_loop,
        interval=interval,
        auto_start=False,
    )

    engine.start()

    return engine


# ==========================================================
# MODULE EXPORTS
# ==========================================================

__all__ = [
    "GoalEngine",
    "start_goal_engine",
]