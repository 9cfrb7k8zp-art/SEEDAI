# ==========================================================
# FILE: qbit_load_balancer.py
# PATH: SEED_ROOT/seed/core/supervisors/qbit_load_balancer.py
# VERSION: 2.0.0
# SYSTEM: QBIT SUPERVISOR / LOAD OBSERVER
# STATUS: STABILITY BUILD
#
# PURPOSE:
# Observe Qbit load around the authoritative QbitQueueLoop.
# This module is not a transport authority and never owns
# the UI queue or creates a competing Qbit transport.
#
# AUTHORITY:
# Qbit = data carrier
# QbitQueueLoop = Qbit transport authority
# QbitDialer = command admission authority
# TrackSystem = track/data-flow authority
# SRegistry/Nodes = identity/discovery authority
# ==========================================================

import logging
import threading
import time

log = logging.getLogger("QbitLoadBalancer")


class QbitLoadBalancer:

    def __init__(
        self,
        master_queue=None,
        workers=4,
        *,
        qbit_queue_loop=None,
        qbit_dialer=None,
        event_bus=None,
        track_system=None,
        registry=None,
        node_registry=None,
    ):
        self.master_queue = None
        self.qbit_queue_loop = None
        self.qbit_dialer = qbit_dialer
        self.event_bus = event_bus
        self.track_system = track_system
        self.registry = registry
        self.node_registry = node_registry
        self.workers = max(1, int(workers or 1))
        self.index = 0
        self.running = False
        self.thread = None
        self.total_observed = 0
        self.total_rejected = 0
        self.started_at = None
        self.bind_runtime(
            master_queue=master_queue,
            qbit_queue_loop=qbit_queue_loop,
            qbit_dialer=qbit_dialer,
            event_bus=event_bus,
            track_system=track_system,
            registry=registry,
            node_registry=node_registry,
        )

    def bind_runtime(self, **runtime):

        for name in (
            "qbit_queue_loop",
            "qbit_dialer",
            "event_bus",
            "track_system",
            "registry",
            "node_registry",
        ):
            value = runtime.get(name)
            if value is not None:
                setattr(self, name, value)

        loop = self.qbit_queue_loop
        if loop is not None:
            authoritative_queue = getattr(
                loop,
                "queue_loop",
                None,
            )
            if authoritative_queue is not None:
                self.master_queue = authoritative_queue

        # A supplied raw queue is never promoted when the
        # authoritative QbitQueueLoop is already available.
        if self.qbit_queue_loop is not None:
            self.master_queue = getattr(
                self.qbit_queue_loop,
                "queue_loop",
                self.master_queue,
            )

        return self

    def start(self):

        if self.running:
            return True

        if self.qbit_queue_loop is None:
            log.warning(
                "[QbitLoadBalancer] QbitQueueLoop not bound"
            )
            return False

        self.running = True
        self.started_at = time.time()
        self.thread = threading.Thread(
            target=self.monitor_loop,
            daemon=True,
            name="QbitLoadBalancer",
        )
        self.thread.start()

        log.info(
            "[QbitLoadBalancer] ONLINE | queue_loop=%s | workers=%s",
            type(self.qbit_queue_loop).__name__,
            self.workers,
        )
        return True

    def monitor_loop(self):

        # --------------------------------------------------
        # Observe only. Do not get()/put() against the live
        # QueueLoop queue because that would steal work.
        # --------------------------------------------------
        while self.running:
            try:
                loop = self.qbit_queue_loop
                if loop is None:
                    self.total_rejected += 1
                    break

                stats = getattr(loop, "stats", None)
                if callable(stats):
                    snapshot = stats() or {}
                    self.total_observed += 1
                    self._publish_load(snapshot)

                time.sleep(0.5)
            except Exception as exc:
                self.total_rejected += 1
                log.warning(
                    "[QbitLoadBalancer] monitor error | error=%s",
                    exc,
                )
                time.sleep(0.5)

    def _publish_load(self, snapshot):

        payload = {
            "module": "QbitLoadBalancer",
            "source": "QbitLoadBalancer",
            "queue_loop": type(self.qbit_queue_loop).__name__,
            "workers": self.workers,
            "load": dict(snapshot),
            "timestamp": time.time(),
        }

        bus = self.event_bus
        if bus is not None:
            for method_name in ("publish", "emit"):
                method = getattr(bus, method_name, None)
                if callable(method):
                    try:
                        method("QBIT_LOAD", payload)
                        break
                    except TypeError:
                        try:
                            method(payload)
                            break
                        except Exception:
                            pass
                    except Exception:
                        pass

    def stop(self, timeout=1.0):

        self.running = False
        thread = self.thread
        if thread is not None and thread.is_alive():
            thread.join(max(0.0, float(timeout)))
        self.thread = None
        return True

    def status(self):

        return {
            "module": "QbitLoadBalancer",
            "running": self.running,
            "qbit_queue_loop_bound": self.qbit_queue_loop is not None,
            "master_queue_is_authoritative": (
                self.master_queue is getattr(
                    self.qbit_queue_loop,
                    "queue_loop",
                    None,
                )
            ) if self.qbit_queue_loop is not None else False,
            "workers": self.workers,
            "total_observed": self.total_observed,
            "total_rejected": self.total_rejected,
        }
