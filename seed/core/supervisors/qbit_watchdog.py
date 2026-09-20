# ==========================================================
# FILE: qbit_watchdog.py
# PATH: C:\SEED_ROOT\seed\core\supervisors\qbit_watchdog.py
# VERSION: 2.0.0
# BUILD: AUTHORITATIVE-QBIT / SINGLE-WATCHDOG / SHUTDOWN-SAFE
#
# AUTHORITY:
#   QbitWatchdog = health/recovery supervisor only
#
# HARD RULES:
#   - Watchdog does NOT become QbitDialer.
#   - Watchdog does NOT execute commands.
#   - Watchdog creates recovery Qbits only.
#   - Recovery Qbits enter the canonical QbitQueueLoop.
#   - Watchdog never creates a heartbeat clock.
#   - Watchdog can be stopped cleanly.
#   - One watchdog instance per queue loop.
# ==========================================================

from __future__ import annotations

import logging
import threading
import time
import uuid

from seed.core.qbit.qbit import Qbit


log = logging.getLogger("QbitWatchdog")


# ==========================================================
# WATCHDOG
# ==========================================================

class QbitWatchdog:

    def __init__(
        self,
        queue_loop,
        *,
        max_idle=10.0,
        max_queue=5000,
        cooldown=5.0,
    ):

        if queue_loop is None:
            raise ValueError(
                "QbitWatchdog requires QbitQueueLoop"
            )

        self.queue_loop = queue_loop

        self.max_idle = float(max_idle)
        self.max_queue = int(max_queue)
        self.cooldown = float(cooldown)

        self.last_activity = time.monotonic()
        self.last_injection = 0.0

        self._running = False
        self._thread = None
        self._lock = threading.RLock()
        self._stop_event =threading.Event()

        self._injection_count = 0

    # ======================================================
    # STATE
    # ======================================================

    @property
    def running(self):
        return self._running

    @property
    def injection_count(self):
        return self._injection_count

    # ======================================================
    # QUEUE SIZE
    # ======================================================

    def queue_size(self):

        queues = getattr(
            self.queue_loop,
            "priority_queues",
            None,
        )

        if not isinstance(queues, dict):
            return 0

        total = 0

        for queue in queues.values():

            try:
                total += queue.qsize()

            except Exception:
                continue

        return total

    # ======================================================
    # ACTIVITY
    # ======================================================

    def record_activity(self):

        with self._lock:
            self.last_activity = time.monotonic()

    # ======================================================
    # TICK
    # ======================================================

    def tick(self):

        if not self._running:
            return

        try:

            qsize = self.queue_size()

            # --------------------------------------------------
            # A non-empty queue means the cognitive transport
            # layer is active.
            # --------------------------------------------------

            if qsize > 0:
                self.record_activity()

            now = time.monotonic()

            # --------------------------------------------------
            # Cognition stall
            # --------------------------------------------------

            if (
                now - self.last_activity
                > self.max_idle
            ):

                self.inject_recovery_qbit(
                    "COGNITION_STALL"
                )

            # --------------------------------------------------
            # Queue overflow
            # --------------------------------------------------

            elif qsize > self.max_queue:

                self.inject_recovery_qbit(
                    "QUEUE_OVERFLOW"
                )

        except Exception:

            log.exception(
                "[QbitWatchdog] tick failure"
            )

    # ======================================================
    # RECOVERY QBIT
    # ======================================================

    def inject_recovery_qbit(
        self,
        reason,
    ):

        now = time.monotonic()

        # --------------------------------------------------
        # Cooldown prevents injection storms.
        # --------------------------------------------------

        with self._lock:

            if (
                now - self.last_injection
                < self.cooldown
            ):
                return None

            self.last_injection = now

        # --------------------------------------------------
        # Canonical Qbit carrier.
        #
        # This is NOT a command execution.
        # It is a recovery work carrier.
        # --------------------------------------------------

        qbit = Qbit.create_command(

            intent="HANDLE_ERROR",

            action="WATCHDOG_RECOVERY",

            data={

                "reason": reason,

                "task_id": str(
                    uuid.uuid4()
                ),

                "timestamp": time.time(),

            },

            meta={

                "source": "QBIT_WATCHDOG",

                "reason": reason,

                "recovery": True,

            },

        )

        # --------------------------------------------------
        # Mark provenance.
        # --------------------------------------------------

        qbit.flags.update({

            "watchdog": True,

            "watchdog_reason": reason,

            "recovery_qbit": True,

        })

        qbit.mark_queued(
            queue_name=type(
                self.queue_loop
            ).__name__
        )

        log.warning(
            "[QbitWatchdog] "
            "Recovery Qbit injected | "
            "reason=%s | qbit=%s | track=%s",
            reason,
            qbit.qbit_id,
            qbit.track_id,
        )

        # --------------------------------------------------
        # CANONICAL QUEUE HANDOFF
        # --------------------------------------------------

        for method_name in (
            "enqueue_qbit",
            "submit_qbit",
            "put_qbit",
            "enqueue",
            "submit",
            "put",
        ):

            method = getattr(
                self.queue_loop,
                method_name,
                None,
            )

            if not callable(method):
                continue

            try:

                result = method(
                    qbit,
                )

                self._injection_count += 1

                return result

            except TypeError:

                continue

            except Exception:

                log.exception(
                    "[QbitWatchdog] "
                    "Recovery handoff failed | "
                    "qbit=%s",
                    qbit.qbit_id,
                )

                qbit.fail(
                    "watchdog_queue_handoff_failed"
                )

                return None

        log.error(
            "[QbitWatchdog] "
            "QbitQueueLoop has no supported "
            "Qbit enqueue API"
        )

        qbit.fail(
            "watchdog_queue_api_unavailable"
        )

        return None

    # ======================================================
    # START
    # ======================================================

    def start(self):

        with self._lock:

            if self._running:
                return self

            self._running = True

            self.last_activity = time.monotonic()

            self._thread = threading.Thread(
                target=self._run,
                daemon=True,
                name="QbitWatchdog",
            )

            self._thread.start()

        log.info(
            "[QbitWatchdog] started"
        )

        return self

    # ======================================================
    # LOOP
    # ======================================================

    def _run(self):

        while self._running:

            try:
                self.tick()

            except Exception:

                log.exception(
                    "[QbitWatchdog] "
                    "watchdog loop failure"
                )

            # --------------------------------------------------
            # Event wait allows clean shutdown instead of
            # an unmanaged infinite sleep loop.
            # --------------------------------------------------

            if self._stop_event.wait(1.0):
                break

    # ======================================================
    # STOP
    # ======================================================

    def stop(self):

        with self._lock:

            if not self._running:
                return

            self._running = False

            self._stop_event.set()

            thread = self._thread

        if (
            thread is not None
            and thread.is_alive()
            and thread is not threading.current_thread()
        ):

            thread.join(
                timeout=2.0
            )

        log.info(
            "[QbitWatchdog] stopped"
        )

    # ======================================================
    # RESET
    # ======================================================

    def reset_activity(self):

        with self._lock:

            self.last_activity = time.monotonic()

            self.last_injection = 0.0


# ==========================================================
# SINGLE INSTANCE STARTUP
# ==========================================================

_watchdog = None
_watchdog_lock = threading.RLock()


def start_watchdog(
    queue_loop,
):

    global _watchdog

    with _watchdog_lock:

        if (
            _watchdog is not None
            and _watchdog.running
        ):

            return _watchdog

        _watchdog = QbitWatchdog(
            queue_loop
        )


        _watchdog.start()

        return _watchdog


def stop_watchdog():

    global _watchdog

    with _watchdog_lock:

        if _watchdog is None:
            return

        _watchdog.stop()

        _watchdog = None


def get_watchdog():

    return _watchdog