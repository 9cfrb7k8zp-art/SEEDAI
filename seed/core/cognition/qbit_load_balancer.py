# ==========================================================
# FILE: qbit_load_balancer.py
# PATH: SEED_ROOT/seed/core/cognition/qbit_load_balancer.py
#
# SYSTEM: SEED AI OS
# COMPONENT: QbitLoadBalancer
#
# VERSION: 3.0.0
# BUILD: LIFECYCLE-SAFE / QBIT-AWARE / BOOT-SAFE /
#        PRESSURE-AWARE / FABRIC-OPTIONAL / THREAD-SAFE
#
# PURPOSE:
# - Distribute Qbit workload safely
# - Keep Qbit routing passive during boot
# - Prevent duplicate balancer threads
# - Route heavy work to an optional fabric bridge
# - Preserve local processing when fabric is unavailable
# - Respect queue-loop lifecycle
# - Support runtime pressure modes
# - Never consume the main queue before explicit startup
# - Never create autonomous work during import
#
# LIFECYCLE:
#
#     CONSTRUCTED
#          |
#          v
#        READY
#          |
#    explicit start()
#          |
#          v
#       RUNNING
#          |
#     pressure/load
#          |
#          v
#      PRESSURE
#          |
#       stop()
#          |
#          v
#       STOPPED
#
# IMPORTANT:
# - __init__ NEVER starts a thread.
# - start() is explicit.
# - start() is idempotent.
# - stop() is idempotent.
# - The balancer does NOT start QbitQueueLoop.
# - The balancer does NOT start Heartbeat.
# - The balancer does NOT start SEED.
# - The balancer does NOT create work during boot.
# - Fabric routing is optional.
# - Local fallback is always preserved.
# ==========================================================

from __future__ import annotations

import logging
import queue
import threading
import time
from collections import deque
from typing import Any, Optional


log = logging.getLogger("QbitLoadBalancer")


# ==========================================================
# STATUS MODES
# ==========================================================

class LoadBalancerStatus:
    CONSTRUCTED = "constructed"
    READY = "ready"
    RUNNING = "running"
    PRESSURE = "pressure"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


# ==========================================================
# WORKLOAD CLASSES
# ==========================================================

class WorkloadClass:
    CRITICAL = "CRITICAL"
    NORMAL = "NORMAL"
    BACKGROUND = "BACKGROUND"
    DEFERRED = "DEFERRED"


# ==========================================================
# QBIT LOAD BALANCER
# ==========================================================

class QbitLoadBalancer:

    def __init__(
        self,
        queue_loop,
        workers: int = 4,
        fabric_bridge=None,
        constraint_guardian=None,
        event_bus=None,
        auto_start: bool = False,
        poll_interval: float = 0.05,
        worker_queue_size: int = 1000,
    ):
        # --------------------------------------------------
        # Dependencies
        # --------------------------------------------------

        self.queue_loop = queue_loop
        self.fabric_bridge = fabric_bridge
        self.constraint_guardian = constraint_guardian
        self.event_bus = event_bus

        # --------------------------------------------------
        # Configuration
        # --------------------------------------------------

        self.workers = max(
            1,
            int(workers)
        )

        self.poll_interval = max(
            0.01,
            float(poll_interval)
        )

        self.worker_queue_size = max(
            1,
            int(worker_queue_size)
        )

        # --------------------------------------------------
        # Worker queues
        # --------------------------------------------------

        self.worker_queues = [
            queue.Queue(
                maxsize=self.worker_queue_size
            )
            for _ in range(self.workers)
        ]

        self.index = 0

        # --------------------------------------------------
        # Lifecycle
        # --------------------------------------------------

        self._status = LoadBalancerStatus.CONSTRUCTED

        self._stop_event = threading.Event()
        self._ready_event = threading.Event()
        self._running_event = threading.Event()

        self._dispatch_thread: Optional[threading.Thread] = None

        self._state_lock = threading.RLock()

        # --------------------------------------------------
        # Statistics
        # --------------------------------------------------

        self.total_received = 0
        self.total_local = 0
        self.total_fabric = 0
        self.total_deferred = 0
        self.total_dropped = 0
        self.total_errors = 0

        self._recent_routes = deque(
            maxlen=100
        )

        self.started_at = None
        self.stopped_at = None

        # --------------------------------------------------
        # Pressure configuration
        # --------------------------------------------------

        self.pressure_queue_threshold = max(
            1,
            int(self.worker_queue_size * 0.75)
        )

        self.critical_queue_threshold = max(
            1,
            int(self.worker_queue_size * 0.95)
        )

        # --------------------------------------------------
        # Initial readiness
        #
        # IMPORTANT:
        # This does NOT mean RUNNING.
        # It only means the object has been constructed safely.
        # --------------------------------------------------

        self._status = LoadBalancerStatus.READY
        self._ready_event.set()

        log.info(
            "[QbitLoadBalancer] READY | "
            f"workers={self.workers} | "
            f"queue_size={self.worker_queue_size} | "
            "auto_start=False"
        )

        # --------------------------------------------------
        # Explicit auto_start compatibility.
        #
        # Default is False.
        #
        # Even when explicitly requested, startup remains
        # lifecycle-safe and happens only through start().
        # --------------------------------------------------

        if auto_start:
            log.warning(
                "[QbitLoadBalancer] auto_start requested | "
                "delegating to explicit start()"
            )
            self.start()

    # ==========================================================
    # LIFECYCLE
    # ==========================================================

    def start(self) -> bool:
 

        with self._state_lock:

            if self._status == LoadBalancerStatus.RUNNING:
                return True

            if self._status == LoadBalancerStatus.STOPPING:
                return False

            # --------------------------------------------------
            # Allow restart after STOPPED.
            # --------------------------------------------------

            if self._status == LoadBalancerStatus.STOPPED:

                self._stop_event.clear()

            # --------------------------------------------------
            # Verify queue dependency.
            # --------------------------------------------------

            if self.queue_loop is None:

                self._status = LoadBalancerStatus.ERROR

                log.error(
                    "[QbitLoadBalancer] Cannot start: "
                    "queue_loop is None"
                )

                return False

            # --------------------------------------------------
            # Do NOT start if the queue loop itself is explicitly
            # stopped or shutting down.
            # --------------------------------------------------

            if self._queue_loop_is_shutdown():

                log.warning(
                    "[QbitLoadBalancer] Start refused: "
                    "queue loop is stopped/shutting down"
                )

                self._status = LoadBalancerStatus.STOPPED

                return False

            self._stop_event.clear()

            self._running_event.set()

            self._status = LoadBalancerStatus.RUNNING

            self.started_at = time.time()
            self.stopped_at = None

            self._dispatch_thread = threading.Thread(
                target=self._dispatch_loop,
                daemon=True,
                name="QbitLoadBalancer",
            )

            self._dispatch_thread.start()

        log.info(
            "[QbitLoadBalancer] RUNNING"
        )

        return True

    # ==========================================================
    # STOP
    # ==========================================================

    def stop(
        self,
        reason: str = "shutdown",
    ) -> None:

        with self._state_lock:

            if self._status in (
                LoadBalancerStatus.STOPPED,
                LoadBalancerStatus.CONSTRUCTED,
            ):
                self._status = LoadBalancerStatus.STOPPED
                return

            self._status = LoadBalancerStatus.STOPPING

            self._stop_event.set()
            self._running_event.clear()

        log.info(
            "[QbitLoadBalancer] STOPPING | "
            f"reason={reason}"
        )

        thread = self._dispatch_thread

        if (
            thread is not None
            and thread.is_alive()
            and thread is not threading.current_thread()
        ):

            thread.join(
                timeout=2.0
            )

        with self._state_lock:

            self._status = LoadBalancerStatus.STOPPED
            self.stopped_at = time.time()
            self._dispatch_thread = None

        log.info(
            "[QbitLoadBalancer] STOPPED"
        )

    # ==========================================================
    # QUEUE LOOP STATE
    # ==========================================================

    def _queue_loop_is_shutdown(self) -> bool:

        loop = self.queue_loop

        if loop is None:
            return True

        # --------------------------------------------------
        # Check common lifecycle flags without requiring any
        # particular QbitQueueLoop implementation.
        # --------------------------------------------------

        for name in (
            "shutdown_requested",
            "_shutdown_requested",
            "stopping",
            "_stopping",
            "stopped",
            "_stopped",
        ):

            try:

                value = getattr(
                    loop,
                    name,
                    False
                )

                if callable(value):
                    value = value()

                if bool(value):
                    return True

            except Exception:
                continue

        return False

    # ==========================================================
    # MAIN DISPATCH LOOP
    # ==========================================================

    def _dispatch_loop(self) -> None:

        log.info(
            "[QbitLoadBalancer] Dispatch loop started"
        )

        try:

            while not self._stop_event.is_set():

                # --------------------------------------------------
                # Never operate against a queue loop that has entered
                # shutdown.
                # --------------------------------------------------

                if self._queue_loop_is_shutdown():

                    log.info(
                        "[QbitLoadBalancer] "
                        "Queue loop shutdown detected"
                    )

                    break

                item = self._get_next_item()

                if item is None:
                    continue

                self.total_received += 1

                try:

                    self._route_item(
                        item
                    )

                except Exception as exc:

                    self.total_errors += 1

                    log.exception(
                        "[QbitLoadBalancer] "
                        "Routing failure: %s",
                        exc,
                    )

                    # --------------------------------------------------
                    # Do not destroy the Qbit because the balancer failed.
                    # Attempt local fallback.
                    # --------------------------------------------------

                    self._local_fallback(
                        item
                    )

        except Exception as exc:

            self.total_errors += 1

            with self._state_lock:
                self._status = LoadBalancerStatus.ERROR

            log.exception(
                "[QbitLoadBalancer] "
                "Dispatch loop failure: %s",
                exc,
            )

        finally:

            self._running_event.clear()

            with self._state_lock:

                if self._status != LoadBalancerStatus.ERROR:
                    self._status = LoadBalancerStatus.STOPPED

                self.stopped_at = time.time()

            log.info(
                "[QbitLoadBalancer] "
                "Dispatch loop stopped"
            )

    # ==========================================================
    # QUEUE READ
    # ==========================================================

    def _get_next_item(self):

        loop = self.queue_loop

        getter = getattr(
            loop,
            "get",
            None
        )

        if not callable(getter):

            raise RuntimeError(
                "queue_loop.get is not callable"
            )

        try:

            return getter(
                block=True,
                timeout=self.poll_interval
            )

        except TypeError:

            # --------------------------------------------------
            # Compatibility with queue implementations that do not
            # accept block/timeout.
            # --------------------------------------------------

            try:
                return getter(
                    block=False
                )

            except queue.Empty:
                return None

        except queue.Empty:

            return None

    # ==========================================================
    # ROUTING
    # ==========================================================

    def _route_item(
        self,
        qbit,
    ) -> None:

        workload = self._get_workload_class(
            qbit
        )

        # --------------------------------------------------
        # CRITICAL work always stays local.
        #
        # The load balancer must never move system-control,
        # heartbeat, shutdown, safety or recovery work to an
        # external fabric.
        # --------------------------------------------------

        if workload == WorkloadClass.CRITICAL:

            self._local_fallback(
                qbit
            )

            return

        # --------------------------------------------------
        # Heavy compute may use fabric.
        # --------------------------------------------------

        if self.is_heavy_compute(qbit):

            if self.route_qbit(qbit):

                return

        # --------------------------------------------------
        # Pressure-aware routing.
        # --------------------------------------------------

        if self._under_pressure():

            if workload == WorkloadClass.BACKGROUND:

                self.total_deferred += 1

                self._recent_routes.append(
                    ("deferred", qbit)
                )

                return

        # --------------------------------------------------
        # Normal local distribution.
        # --------------------------------------------------

        self._dispatch_to_worker(
            qbit
        )

    # ==========================================================
    # HEAVY COMPUTE DETECTION
    # ==========================================================

    def is_heavy_compute(
        self,
        qbit,
    ) -> bool:

        if qbit is None:
            return False

        metadata = self._get_metadata(
            qbit
        )

        # --------------------------------------------------
        # Explicit heavy marker.
        # --------------------------------------------------

        for key in (
            "heavy_compute",
            "requires_gpu",
            "gpu_required",
            "fabric_required",
        ):

            if self._truthy(
                self._get_value(
                    qbit,
                    key,
                    metadata,
                )
            ):
                return True

        # --------------------------------------------------
        # Workload class.
        # --------------------------------------------------

        workload = self._get_workload_class(
            qbit
        )

        if workload == "GPU":
            return True

        # --------------------------------------------------
        # Explicit compute hints.
        # --------------------------------------------------

        compute_type = self._get_value(
            qbit,
            "compute_type",
            metadata,
        )

        if isinstance(
            compute_type,
            str,
        ):

            if compute_type.upper() in (
                "GPU",
                "HEAVY",
                "VECTOR",
                "QUANTUM",
                "FABRIC",
            ):
                return True

        return False

    # ==========================================================
    # FABRIC ROUTING
    # ==========================================================

    def route_qbit(
        self,
        qbit,
    ) -> bool:

        bridge = self.fabric_bridge

        if bridge is None:

            return False

        sender = getattr(
            bridge,
            "send_qbit",
            None
        )

        if not callable(sender):

            log.debug(
                "[QbitLoadBalancer] "
                "Fabric bridge has no send_qbit()"
            )

            return False

        try:

            # --------------------------------------------------
            # Do NOT hard-code a machine-specific host.
            #
            # Let the fabric bridge decide where the Qbit goes.
            # --------------------------------------------------

            result = sender(
                qbit
            )

            # Some bridges return None on successful fire-and-forget.
            # Treat explicit False as failure.
            if result is False:

                return False

            self.total_fabric += 1

            self._recent_routes.append(
                ("fabric", qbit)
            )

            log.debug(
                "[QbitLoadBalancer] "
                "Qbit routed to fabric"
            )

            return True

        except TypeError:

            # --------------------------------------------------
            # Compatibility with older bridges requiring host/port.
            #
            # Only use configured bridge values. Never invent a
            # network endpoint here.
            # --------------------------------------------------

            host = getattr(
                bridge,
                "host",
                None
            )

            port = getattr(
                bridge,
                "port",
                None
            )

            if host is None or port is None:

                return False

            try:

                result = sender(
                    qbit,
                    host=host,
                    port=port,
                )

                if result is False:
                    return False

                self.total_fabric += 1

                self._recent_routes.append(
                    ("fabric", qbit)
                )

                return True

            except Exception as exc:

                log.warning(
                    "[QbitLoadBalancer] "
                    "Fabric routing failed: %s",
                    exc,
                )

                return False

        except Exception as exc:

            log.warning(
                "[QbitLoadBalancer] "
                "Fabric routing failed: %s",
                exc,
            )

            return False

    # ==========================================================
    # LOCAL DISTRIBUTION
    # ==========================================================

    def _dispatch_to_worker(
        self,
        qbit,
    ) -> bool:

        if not self.worker_queues:

            return self._local_fallback(
                qbit
            )

        # --------------------------------------------------
        # Find an available worker queue.
        # --------------------------------------------------

        attempts = len(
            self.worker_queues
        )

        for _ in range(attempts):

            index = (
                self.index
                % len(self.worker_queues)
            )

            self.index = (
                self.index + 1
            ) % len(self.worker_queues)

            target = self.worker_queues[
                index
            ]

            try:

                target.put_nowait(
                    qbit
                )

                self.total_local += 1

                self._recent_routes.append(
                    ("worker", index)
                )

                return True

            except queue.Full:

                continue

        # --------------------------------------------------
        # All worker queues are full.
        # Preserve the Qbit by falling back to the main
        # queue-loop handler instead of silently dropping it.
        # --------------------------------------------------

        return self._local_fallback(
            qbit
        )

    # ==========================================================
    # LOCAL FALLBACK
    # ==========================================================

    def _local_fallback(
        self,
        qbit,
    ) -> bool:

        loop = self.queue_loop

        if loop is None:
            self.total_dropped += 1
            return False

        putter = getattr(
            loop,
            "put",
            None
        )

        if not callable(putter):

            self.total_dropped += 1

            log.error(
                "[QbitLoadBalancer] "
                "No queue_loop.put() available"
            )

            return False

        # --------------------------------------------------
        # CRITICAL Qbits retain critical priority.
        # --------------------------------------------------

        workload = self._get_workload_class(
            qbit
        )

        priority = (
            "CRITICAL"
            if workload == WorkloadClass.CRITICAL
            else "NORMAL"
        )

        try:

            try:

                putter(
                    qbit,
                    priority=priority
                )

            except TypeError:

                putter(
                    qbit
                )

            self.total_local += 1

            self._recent_routes.append(
                ("local", priority)
            )

            return True

        except Exception as exc:

            self.total_errors += 1

            log.error(
                "[QbitLoadBalancer] "
                "Local fallback failed: %s",
                exc,
            )

            self.total_dropped += 1

            return False

    # ==========================================================
    # WORKLOAD CLASSIFICATION
    # ==========================================================

    def _get_workload_class(
        self,
        qbit,
    ) -> str:

        metadata = self._get_metadata(
            qbit
        )

        value = self._get_value(
            qbit,
            "workload",
            metadata,
        )

        if value is None:

            value = self._get_value(
                qbit,
                "priority",
                metadata,
            )

        if value is None:
            return WorkloadClass.NORMAL

        value = str(
            value
        ).upper()

        if value in (
            "CRITICAL",
            "SYSTEM",
            "SAFETY",
            "HEARTBEAT",
            "CONTROL",
        ):

            return WorkloadClass.CRITICAL

        if value in (
            "BACKGROUND",
            "LOW",
        ):

            return WorkloadClass.BACKGROUND

        if value in (
            "DEFERRED",
            "DEFER",
        ):

            return WorkloadClass.DEFERRED

        return WorkloadClass.NORMAL

    # ==========================================================
    # METADATA HELPERS
    # ==========================================================

    def _get_metadata(
        self,
        qbit,
    ) -> dict:

        if qbit is None:
            return {}

        metadata = self._get_value(
            qbit,
            "metadata",
            None,
        )

        if isinstance(
            metadata,
            dict,
        ):
            return metadata

        return {}

    def _get_value(
        self,
        qbit,
        key: str,
        metadata=None,
    ):

        if qbit is None:
            return None

        # --------------------------------------------------
        # Dictionary Qbits
        # --------------------------------------------------

        if isinstance(
            qbit,
            dict,
        ):

            if key in qbit:
                return qbit.get(key)

        # --------------------------------------------------
        # Object Qbits
        # --------------------------------------------------

        try:

            value = getattr(
                qbit,
                key,
                None
            )

            if value is not None:
                return value

        except Exception:
            pass

        # --------------------------------------------------
        # Metadata
        # --------------------------------------------------

        if isinstance(
            metadata,
            dict,
        ):

            return metadata.get(
                key
            )

        return None

    @staticmethod
    def _truthy(
        value,
    ) -> bool:

        if isinstance(
            value,
            str,
        ):

            return value.strip().lower() in (
                "1",
                "true",
                "yes",
                "on",
                "enabled",
            )

        return bool(
            value
        )

    # ==========================================================
    # PRESSURE
    # ==========================================================

    def _under_pressure(self) -> bool:

        # --------------------------------------------------
        # ConstraintGuardian takes precedence.
        # --------------------------------------------------

        guardian = self.constraint_guardian

        if guardian is not None:

            try:

                state = guardian.get_state()

                if str(state).lower() in (
                    "warning",
                    "block",
                ):

                    self._set_pressure_status()

                    return True

            except Exception:
                pass

        # --------------------------------------------------
        # Local worker queue pressure.
        # --------------------------------------------------

        total = sum(
            q.qsize()
            for q in self.worker_queues
        )

        if total >= self.critical_queue_threshold:

            self._set_pressure_status()

            return True

        if total >= self.pressure_queue_threshold:

            self._set_pressure_status()

            return True

        # --------------------------------------------------
        # Return to normal running mode.
        # --------------------------------------------------

        with self._state_lock:

            if self._status == LoadBalancerStatus.PRESSURE:
                self._status = LoadBalancerStatus.RUNNING

        return False

    def _set_pressure_status(self) -> None:

        with self._state_lock:

            if self._status == LoadBalancerStatus.RUNNING:

                self._status = LoadBalancerStatus.PRESSURE

                log.warning(
                    "[QbitLoadBalancer] "
                    "PRESSURE mode"
                )

    # ==========================================================
    # STATUS
    # ==========================================================

    @property
    def status(self) -> str:

        with self._state_lock:
            return self._status

    def is_running(self) -> bool:

        return (
            self.status
            in (
                LoadBalancerStatus.RUNNING,
                LoadBalancerStatus.PRESSURE,
            )
        )

    def is_ready(self) -> bool:

        return self._ready_event.is_set()

    # ==========================================================
    # DIAGNOSTICS
    # ==========================================================

    def diagnostics(self) -> dict:

        with self._state_lock:

            worker_depths = [
                q.qsize()
                for q in self.worker_queues
            ]

            return {
                "component": "QbitLoadBalancer",
                "version": "3.0.0",
                "status": self._status,
                "workers": self.workers,
                "worker_queue_depths": worker_depths,
                "worker_queue_total": sum(
                    worker_depths
                ),
                "total_received": self.total_received,
                "total_local": self.total_local,
                "total_fabric": self.total_fabric,
                "total_deferred": self.total_deferred,
                "total_dropped": self.total_dropped,
                "total_errors": self.total_errors,
                "fabric_available": (
                    self.fabric_bridge is not None
                ),
                "constraint_guardian": (
                    self.constraint_guardian is not None
                ),
                "thread_alive": (
                    self._dispatch_thread.is_alive()
                    if self._dispatch_thread is not None
                    else False
                ),
                "started_at": self.started_at,
                "stopped_at": self.stopped_at,
            }

    # ==========================================================
    # REPRESENTATION
    # ==========================================================

    def __repr__(self) -> str:

        return (
            "QbitLoadBalancer("
            f"status={self.status!r}, "
            f"workers={self.workers}, "
            f"received={self.total_received}, "
            f"local={self.total_local}, "
            f"fabric={self.total_fabric}, "
            f"dropped={self.total_dropped}"
            ")"
        )


# ==========================================================
# COMPATIBILITY EXPORT
# ==========================================================

__all__ = [
    "LoadBalancerStatus",
    "WorkloadClass",
    "QbitLoadBalancer",
]