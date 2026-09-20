# ==========================================================
# FILE: cognitive_clock.py
# PATH: seed/core/cognition/cognitive_clock.py
#
# SYSTEM: SEED AI OS
# COMPONENT: CognitiveClock
# VERSION: 2.0.0
# BUILD: PASSIVE / BOOT-GATED / SINGLE-LOOP / CLEAN-SHUTDOWN
# UPDATED: 2026-08-19
#
# PURPOSE:
# ----------------------------------------------------------
# CognitiveClock provides the lightweight cognitive phase
# scheduler used by SEED cognition components.
#
# PHASES:
#
#     PERCEIVE
#     ANALYZE
#     REASON
#     ACT
#     REFLECT
#
# IMPORTANT LIFECYCLE RULE:
# ----------------------------------------------------------
# CognitiveClock is PASSIVE until explicitly started.
#
# It MUST NOT:
#
#   - start a thread during construction
#   - start itself during import
#   - start itself from a background callback
#   - create repeated worker threads
#   - run before SEED boot authorizes it
#   - restart itself after stop
#   - keep running after shutdown
#
# The owner/orchestrator controls:
#
#     start()
#     stop()
#
# Compatibility:
#
#     start_cognitive_clock()
#
# remains available but DOES NOT silently create multiple loops.
#
# ==========================================================

from __future__ import annotations

import logging
import threading
import time
from typing import Optional


log = logging.getLogger("CognitiveClock")


# ==========================================================
# COGNITIVE CLOCK
# ==========================================================

class CognitiveClock:

    VERSION = "2.0.0"
    NAME = "CognitiveClock"

    # ------------------------------------------------------
    # Cognitive phases.
    # ------------------------------------------------------

    PHASES = (
        "PERCEIVE",
        "ANALYZE",
        "REASON",
        "ACT",
        "REFLECT",
    )

    def __init__(
        self,
        *,
        interval: float = 0.5,
        auto_start: bool = False,
    ):
       

        # --------------------------------------------------
        # Configuration.
        # --------------------------------------------------

        try:
            interval = float(interval)
        except (TypeError, ValueError):
            interval = 0.5

        self.interval = max(
            0.01,
            interval,
        )

        self.phases = list(
            self.PHASES
        )

        # --------------------------------------------------
        # Cognitive state.
        # --------------------------------------------------

        self.cycle = 0
        self.phase = self.phases[0]

        self.last_tick = time.monotonic()

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
        self._tick_count = 0

        self.started_at = None
        self.stopped_at = None

        log.debug(
            "[CognitiveClock] initialized | "
            "version=%s | interval=%.3fs | "
            "auto_start=%s",
            self.VERSION,
            self.interval,
            bool(auto_start),
        )

        # --------------------------------------------------
        # IMPORTANT:
        #
        # auto_start is supported only as an explicit
        # constructor request. The default remains FALSE.
        #
        # SEED production boot should leave this FALSE and
        # call start() from the orchestrator after boot.
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

            elapsed = (
                now - self.last_tick
            )

            if elapsed < self.interval:
                return None

            self.last_tick = now

            self.cycle += 1

            self.phase = self.phases[
                self.cycle % len(self.phases)
            ]

            self._tick_count += 1

            phase = self.phase

        log.debug(
            "[CognitiveClock] "
            "Cognitive phase: %s | cycle=%d",
            phase,
            self.cycle,
        )

        return phase

    # ======================================================
    # START
    # ======================================================

    def start(self) -> bool:
        

        with self._state_lock:

            # ----------------------------------------------
            # Already running.
            # ----------------------------------------------

            if self._running:

                log.debug(
                    "[CognitiveClock] start ignored | "
                    "already running"
                )

                return False

            # ----------------------------------------------
            # Never reuse an active thread object.
            # ----------------------------------------------

            if (
                self._thread is not None
                and self._thread.is_alive()
            ):

                log.warning(
                    "[CognitiveClock] start refused | "
                    "worker thread is still alive"
                )

                return False

            # ----------------------------------------------
            # Clear lifecycle state.
            # ----------------------------------------------

            self._stop_requested = False
            self._stop_event.clear()

            self.last_tick = time.monotonic()

            self._running = True

            self.started_at = time.time()
            self.stopped_at = None

            self._start_count += 1

            # ----------------------------------------------
            # Create exactly one worker.
            # ----------------------------------------------

            thread = threading.Thread(
                target=self._run_loop,
                name="CognitiveClock",
                daemon=True,
            )

            self._thread = thread

            try:

                thread.start()

            except Exception:

                self._running = False
                self._stop_requested = True
                self._thread = None

                log.exception(
                    "[CognitiveClock] "
                    "failed to start worker"
                )

                return False

        log.info(
            "[CognitiveClock] started | "
            "interval=%.3fs",
            self.interval,
        )

        return True

    # ======================================================
    # RUN LOOP
    # ======================================================

    def _run_loop(self) -> None:
       

        log.debug(
            "[CognitiveClock] execution loop online"
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
                "[CognitiveClock] "
                "execution loop failure"
            )

        finally:

            with self._state_lock:

                self._running = False
                self._stop_requested = True
                self.stopped_at = time.time()

            log.debug(
                "[CognitiveClock] "
                "execution loop offline"
            )

    # ======================================================
    # LOOP INTERVAL
    # ======================================================

    def _loop_sleep_interval(self) -> float:
      

        return max(
            0.01,
            min(
                self.interval / 4.0,
                0.1,
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
                    "[CognitiveClock] "
                    "worker join failed"
                )

        with self._state_lock:

            if (
                self._thread is not None
                and not self._thread.is_alive()
            ):
                self._thread = None

        log.info(
            "[CognitiveClock] stopped"
        )

        return True

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

            self.cycle = 0

            self.phase = self.phases[0]

            self.last_tick = time.monotonic()

            self._tick_count = 0

            self._stop_requested = (
                not self._running
            )

        log.debug(
            "[CognitiveClock] reset"
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

    def status(self):
       

        with self._state_lock:

            thread = self._thread

            return {
                "name": self.NAME,
                "version": self.VERSION,
                "running": self._running,
                "stop_requested": (
                    self._stop_requested
                ),
                "cycle": self.cycle,
                "phase": self.phase,
                "interval": self.interval,
                "tick_count": self._tick_count,
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
    # REPRESENTATION
    # ======================================================

    def __repr__(self) -> str:

        with self._state_lock:

            return (
                "CognitiveClock("
                f"version={self.VERSION!r}, "
                f"cycle={self.cycle}, "
                f"phase={self.phase!r}, "
                f"interval={self.interval:.3f}, "
                f"running={self._running!r}"
                ")"
            )


# ==========================================================
# COMPATIBILITY START FUNCTION
# ==========================================================

def start_cognitive_clock(
    *,
    interval: float = 0.5,
) -> CognitiveClock:


    clock = CognitiveClock(
        interval=interval,
        auto_start=False,
    )

    clock.start()

    return clock


# ==========================================================
# MODULE EXPORTS
# ==========================================================

__all__ = [
    "CognitiveClock",
    "start_cognitive_clock",
]