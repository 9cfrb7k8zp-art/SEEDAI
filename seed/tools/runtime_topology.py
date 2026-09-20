# ==============================================================
#
# File: runtime_topology.py
# Path: SEED_ROOT/seed/tools/runtime_topology.py
# Purpose: Map threads, asyncio loops/tasks, processes, and
#          runtime relationships for SEED-AI.
#
# VERSION: 2.0.0
# ROLE: runtime-topology-observer
#
# ARCHITECTURE:
#   RuntimeTopologyMapper
#       -> observes runtime
#       -> reports topology
#       -> feeds TrackSystem
#       -> informs SRegistry / registry_runtime
#       -> provides lifecycle evidence to NeuralBridge
#       -> provides runtime evidence to QbitDialer
#
# AUTHORITY:
#   OBSERVATION ONLY
#   QbitDialer remains the sole command authority.
#
# ==============================================================

import asyncio
import inspect
import logging
import multiprocessing
import threading
import time
from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4

try:
    from seed.tools.base_tool import BaseTool
except ImportError:
    BaseTool = object


logger = logging.getLogger("RuntimeTopology")


# ==============================================================
# Track ID helper
# ==============================================================

def gen_track_id(prefix="SEEDRuntime_Topology"):

    return f"{prefix}-{uuid4().hex[:8]}"


# ==============================================================
# Runtime Topology Mapper
# ==============================================================

class RuntimeTopologyMapper(BaseTool):

    NODE_TYPE = "tool"
    NODE_VERSION = "2.0.0"

    TOOL_NAME = "runtime_topology"
    TOOL_ROLE = "runtime-topology-observer"

    TOOL_CAPABILITIES = (
        "runtime_topology",
        "thread_observation",
        "asyncio_topology",
        "task_observation",
        "process_observation",
        "runtime_health_observation",
        "node_runtime_mapping",
        "track_telemetry",
        "registry_runtime_evidence",
        "neural_bridge_lifecycle_evidence",
        "dialer_runtime_evidence",
        "runtime_anomaly_detection",
        "topology_reporting",
    )

    TOOL_DEPENDENCIES = (
        "TrackSystem",
        "SRegistry",
        "registry_runtime",
        "NeuralBridge",
        "QbitDialer",
        "EventBus",
    )

    # Do not make this tool automatically start unless explicitly
    # requested by the tool fabric.
    TOOL_ALWAYS_ON = False

    DEFAULT_REFRESH_INTERVAL = 1.0

    # ==========================================================
    # Constructor
    # ==========================================================

    def __init__(
        self,
        refresh_interval=DEFAULT_REFRESH_INTERVAL,
        track_system=None,
        registry=None,
        registry_runtime=None,
        neural_bridge=None,
        qbit_dialer=None,
        event_bus=None,
        always_on=False,
    ):
        try:
            super().__init__(
                name=self.TOOL_NAME,
                role=self.TOOL_ROLE,
                capabilities=self.TOOL_CAPABILITIES,
                dependencies=self.TOOL_DEPENDENCIES,
                version=self.NODE_VERSION,
                always_on=always_on,
            )
        except TypeError:
            # Compatibility with older BaseTool implementations.
            try:
                super().__init__(self.TOOL_NAME)
            except TypeError:
                super().__init__()

        self.refresh_interval = max(
            0.1,
            float(refresh_interval),
        )

        self._lock = threading.RLock()
        self._stop_event = threading.Event()

        self._running = False
        self._monitor_thread = None

        self.threads = {}
        self.loops = {}
        self.tasks = {}
        self.processes = {}

        self._loop_refs = {}

        self._topology_revision = 0
        self._last_scan = None
        self._last_error = None

        self._scan_count = 0
        self._anomaly_count = 0

        self._history = []
        self._anomalies = []

        # Existing authoritative system references only.
        self._bindings = {}

        if track_system is not None:
            self.bind("TrackSystem", track_system)

        if registry is not None:
            self.bind("SRegistry", registry)

        if registry_runtime is not None:
            self.bind("registry_runtime", registry_runtime)

        if neural_bridge is not None:
            self.bind("NeuralBridge", neural_bridge)

        if qbit_dialer is not None:
            self.bind("QbitDialer", qbit_dialer)

        if event_bus is not None:
            self.bind("EventBus", event_bus)

        self._update_ready_state()

    # ==========================================================
    # Binding
    # ==========================================================

    def bind(self, name, obj):

        if obj is None:
            return False

        with self._lock:
            self._bindings[str(name)] = obj

        self._update_ready_state()

        logger.info(
            "[RuntimeTopology] Bound dependency | name=%s",
            name,
        )

        return True

    def unbind(self, name):
        with self._lock:
            removed = self._bindings.pop(str(name), None)

        self._update_ready_state()

        return removed is not None

    def get_binding(self, name):
        with self._lock:
            return self._bindings.get(str(name))

    def bindings(self):
        with self._lock:
            return dict(self._bindings)

    def _update_ready_state(self):

        if hasattr(self, "set_ready"):
            try:
                self.set_ready()
                return
            except Exception:
                pass

        if hasattr(self, "ready"):
            self.ready = True

    # ==========================================================
    # Lifecycle
    # ==========================================================

    def start(self):

        with self._lock:
            if self._running:
                return {
                    "status": "already_running",
                    "node_id": getattr(self, "node_id", None),
                }

            self._running = True
            self._stop_event.clear()

            self._monitor_thread = threading.Thread(
                target=self._update_loop,
                name="SEED-RuntimeTopology",
                daemon=True,
            )

            self._monitor_thread.start()

        logger.info(
            "[RuntimeTopology] Monitoring started | interval=%.2fs",
            self.refresh_interval,
        )

        return {
            "status": "started",
            "node_id": getattr(self, "node_id", None),
        }

    def stop(self):
        with self._lock:
            if not self._running:
                return {
                    "status": "already_stopped",
                }

            self._running = False
            self._stop_event.set()

            thread = self._monitor_thread
            self._monitor_thread = None

        if (
            thread is not None
            and thread.is_alive()
            and thread is not threading.current_thread()
        ):
            thread.join(timeout=max(1.0, self.refresh_interval + 1.0))

        logger.info("[RuntimeTopology] Monitoring stopped")

        return {
            "status": "stopped",
        }

    # ==========================================================
    # Monitoring loop
    # ==========================================================

    def _update_loop(self):
        while not self._stop_event.is_set():
            try:
                self.scan_now()
            except Exception as exc:
                self._record_error(exc)

            self._stop_event.wait(self.refresh_interval)

    # ==========================================================
    # Public scan
    # ==========================================================

    def scan_now(self):
        started = time.monotonic()

        self._scan_threads()
        self._scan_async_runtime()
        self._scan_processes()

        elapsed = time.monotonic() - started

        with self._lock:
            self._scan_count += 1
            self._topology_revision += 1
            self._last_scan = self._utc_now()

            snapshot = self._snapshot_locked()

            snapshot["scan"] = {
                "revision": self._topology_revision,
                "scan_count": self._scan_count,
                "duration_seconds": elapsed,
                "timestamp": self._last_scan,
            }

            self._history.append(
                deepcopy(snapshot)
            )

            if len(self._history) > 100:
                self._history.pop(0)

        self._publish_observation(snapshot)

        return snapshot

    # ==========================================================
    # Thread observation
    # ==========================================================

    def _scan_threads(self):
        observed = {}

        for thread in threading.enumerate():
            thread_id = thread.ident

            if thread_id is None:
                continue

            observed[thread_id] = {
                "thread_id": thread_id,
                "name": thread.name,
                "daemon": bool(thread.daemon),
                "alive": bool(thread.is_alive()),
                "ident": thread.ident,
            }

        with self._lock:
            self.threads = observed

    # ==========================================================
    # Asyncio observation
    # ==========================================================

    def _scan_async_runtime(self):

        loops = {}
        tasks = {}

        # ------------------------------------------------------
        # Registered authoritative loops
        # ------------------------------------------------------

        with self._lock:
            registered_loops = dict(self._loop_refs)

        for loop_id, loop in registered_loops.items():
            self._inspect_loop(
                loop_id,
                loop,
                loops,
                tasks,
            )

        # ------------------------------------------------------
        # Current running loop
        # ------------------------------------------------------

        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None

        if running_loop is not None:
            loop_id = id(running_loop)

            self._inspect_loop(
                loop_id,
                running_loop,
                loops,
                tasks,
            )

        with self._lock:
            self.loops = loops
            self.tasks = tasks

    def _inspect_loop(
        self,
        loop_id,
        loop,
        loops,
        tasks,
    ):
        if loop is None:
            return

        try:
            loop_running = bool(loop.is_running())
        except Exception:
            loop_running = False

        try:
            loop_closed = bool(loop.is_closed())
        except Exception:
            loop_closed = False

        loops[loop_id] = {
            "loop_id": loop_id,
            "running": loop_running,
            "closed": loop_closed,
            "thread_id": self._find_loop_thread_id(loop),
            "task_count": 0,
        }

        try:
            current_tasks = asyncio.all_tasks(loop)
        except Exception:
            current_tasks = set()

        loops[loop_id]["task_count"] = len(current_tasks)

        for task in current_tasks:
            task_id = id(task)

            try:
                task_name = task.get_name()
            except Exception:
                task_name = str(task.get_coro())

            try:
                coroutine = task.get_coro()
                coroutine_name = getattr(
                    coroutine,
                    "__qualname__",
                    type(coroutine).__name__,
                )
            except Exception:
                coroutine_name = "unknown"

            tasks[task_id] = {
                "task_id": task_id,
                "loop_id": loop_id,
                "name": task_name,
                "coroutine": coroutine_name,
                "done": bool(task.done()),
                "cancelled": bool(task.cancelled()),
            }

    def _find_loop_thread_id(self, loop):

        current_thread = threading.current_thread()

        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        if current_loop is loop:
            return current_thread.ident

        return None

    # ==========================================================
    # Register an existing authoritative loop
    # ==========================================================

    def register_loop(self, loop, name=None, authoritative=False):

        if loop is None:
            return False

        loop_id = id(loop)

        with self._lock:
            self._loop_refs[loop_id] = loop

            self.loops.setdefault(
                loop_id,
                {
                    "loop_id": loop_id,
                    "name": name,
                    "authoritative": bool(authoritative),
                },
            )

        logger.info(
            "[RuntimeTopology] Loop registered | loop_id=%s | "
            "name=%s | authoritative=%s",
            loop_id,
            name,
            authoritative,
        )

        return True

    def unregister_loop(self, loop):
        if loop is None:
            return False

        loop_id = id(loop)

        with self._lock:
            removed = self._loop_refs.pop(loop_id, None)

        return removed is not None

    # ==========================================================
    # Process observation
    # ==========================================================

    def _scan_processes(self):
        observed = {}

        for proc in multiprocessing.active_children():
            pid = proc.pid

            if pid is None:
                continue

            observed[pid] = {
                "pid": pid,
                "name": proc.name,
                "alive": bool(proc.is_alive()),
                "daemon": bool(proc.daemon),
            }

        with self._lock:
            self.processes = observed

    # ==========================================================
    # Runtime anomaly detection
    # ==========================================================

    def _detect_anomalies(self, snapshot):
        anomalies = []

        loops = snapshot.get("loops", {})
        tasks = snapshot.get("tasks", {})
        threads = snapshot.get("threads", {})
        processes = snapshot.get("processes", {})

        # ------------------------------------------------------
        # Tasks without a known loop
        # ------------------------------------------------------

        for task_id, task in tasks.items():
            loop_id = task.get("loop_id")

            if loop_id not in loops:
                anomalies.append(
                    {
                        "type": "orphan_task",
                        "severity": "warning",
                        "task_id": task_id,
                        "loop_id": loop_id,
                    }
                )

        # ------------------------------------------------------
        # Running loop with no associated thread
        # ------------------------------------------------------

        for loop_id, loop in loops.items():
            if (
                loop.get("running")
                and loop.get("thread_id") is None
            ):
                anomalies.append(
                    {
                        "type": "unresolved_loop_thread",
                        "severity": "info",
                        "loop_id": loop_id,
                    }
                )

        # ------------------------------------------------------
        # Dead threads retained by runtime references
        # ------------------------------------------------------

        for thread_id, thread in threads.items():
            if not thread.get("alive", False):
                anomalies.append(
                    {
                        "type": "dead_thread_observed",
                        "severity": "info",
                        "thread_id": thread_id,
                        "name": thread.get("name"),
                    }
                )

        # ------------------------------------------------------
        # Dead child processes
        # ------------------------------------------------------

        for pid, process in processes.items():
            if not process.get("alive", False):
                anomalies.append(
                    {
                        "type": "dead_process_observed",
                        "severity": "info",
                        "pid": pid,
                        "name": process.get("name"),
                    }
                )

        return anomalies

    # ==========================================================
    # Snapshot
    # ==========================================================

    def _snapshot_locked(self):
        return {
            "node": {
                "node_id": getattr(self, "node_id", None),
                "node_type": self.NODE_TYPE,
                "node_version": self.NODE_VERSION,
                "tool_name": self.TOOL_NAME,
                "role": self.TOOL_ROLE,
            },
            "topology_revision": self._topology_revision,
            "timestamp": self._utc_now(),
            "threads": deepcopy(self.threads),
            "loops": deepcopy(self.loops),
            "tasks": deepcopy(self.tasks),
            "processes": deepcopy(self.processes),
            "bindings": sorted(self._bindings.keys()),
        }

    def snapshot(self):
        with self._lock:
            snapshot = self._snapshot_locked()

        anomalies = self._detect_anomalies(snapshot)

        if anomalies:
            with self._lock:
                self._anomaly_count += len(anomalies)
                self._anomalies.extend(
                    deepcopy(anomalies)
                )

                if len(self._anomalies) > 200:
                    self._anomalies = self._anomalies[-200:]

        snapshot["anomalies"] = anomalies

        return snapshot

    # ==========================================================
    # Publish observation
    # ==========================================================

    def _publish_observation(self, snapshot):

        track_id = gen_track_id()

        observation = {
            "type": "runtime_topology_observation",
            "track_id": track_id,
            "source": self.TOOL_NAME,
            "node_id": getattr(self, "node_id", None),
            "topology_revision": snapshot.get(
                "topology_revision"
            ),
            "timestamp": snapshot.get("timestamp"),
            "topology": snapshot,
            "authority": {
                "owner": "RuntimeTopology",
                "executed": False,
                "command_submitted": False,
            },
        }

        self._publish_event_bus(observation)
        self._publish_track_system(observation)
        self._publish_registry_evidence(observation)
        self._publish_neural_bridge_evidence(observation)
        self._publish_dialer_evidence(observation)

    # ==========================================================
    # EventBus
    # ==========================================================

    def _publish_event_bus(self, observation):
        event_bus = self.get_binding("EventBus")

        if event_bus is None:
            return False

        try:
            emit = getattr(event_bus, "emit", None)

            if callable(emit):
                emit(
                    "RUNTIME_TOPOLOGY",
                    observation,
                )
                return True

        except Exception as exc:
            logger.debug(
                "[RuntimeTopology] EventBus publish skipped: %s",
                exc,
            )

        return False

    # ==========================================================
    # TrackSystem
    # ==========================================================

    def _publish_track_system(self, observation):
        track_system = self.get_binding("TrackSystem")

        if track_system is None:
            return False

        candidates = (
            "record_observation",
            "record_telemetry",
            "ingest_observation",
            "track",
        )

        for method_name in candidates:
            try:
                method = getattr(
                    track_system,
                    method_name,
                    None,
                )

                if not callable(method):
                    continue

                method(observation)
                return True

            except TypeError:
                continue

            except Exception as exc:
                logger.debug(
                    "[RuntimeTopology] TrackSystem "
                    "publish skipped via %s: %s",
                    method_name,
                    exc,
                )
                return False

        return False

    # ==========================================================
    # Registry evidence
    # ==========================================================

    def _publish_registry_evidence(self, observation):
        registry = self.get_binding("SRegistry")

        if registry is None:
            return False

        evidence = {
            "type": "runtime_topology_evidence",
            "source_node": getattr(
                self,
                "node_id",
                None,
            ),
            "track_id": observation["track_id"],
            "topology_revision": observation[
                "topology_revision"
            ],
            "timestamp": observation["timestamp"],
        }

        candidates = (
            "record_runtime_evidence",
            "record_observation",
            "update_runtime_state",
        )

        for method_name in candidates:
            try:
                method = getattr(
                    registry,
                    method_name,
                    None,
                )

                if not callable(method):
                    continue

                method(evidence)
                return True

            except TypeError:
                continue

            except Exception as exc:
                logger.debug(
                    "[RuntimeTopology] Registry evidence "
                    "skipped via %s: %s",
                    method_name,
                    exc,
                )
                return False

        return False

    # ==========================================================
    # NeuralBridge evidence
    # ==========================================================

    def _publish_neural_bridge_evidence(self, observation):
        bridge = self.get_binding("NeuralBridge")

        if bridge is None:
            return False

        evidence = {
            "type": "runtime_topology_evidence",
            "track_id": observation["track_id"],
            "topology": observation["topology"],
            "lifecycle": {
                "observed": True,
                "execution": False,
            },
        }

        candidates = (
            "record_observation",
            "ingest_observation",
            "observe",
            "record_telemetry",
        )

        for method_name in candidates:
            try:
                method = getattr(
                    bridge,
                    method_name,
                    None,
                )

                if not callable(method):
                    continue

                method(evidence)
                return True

            except TypeError:
                continue

            except Exception as exc:
                logger.debug(
                    "[RuntimeTopology] NeuralBridge evidence "
                    "skipped via %s: %s",
                    method_name,
                    exc,
                )
                return False

        return False

    # ==========================================================
    # QbitDialer evidence
    # ==========================================================

    def _publish_dialer_evidence(self, observation):

        dialer = self.get_binding("QbitDialer")

        if dialer is None:
            return False

        evidence = {
            "type": "runtime_topology_evidence",
            "track_id": observation["track_id"],
            "source": self.TOOL_NAME,
            "topology": observation["topology"],
            "authority": {
                "required": True,
                "owner": "QbitDialer",
                "executed": False,
                "command_submitted": False,
            },
        }

        candidates = (
            "record_runtime_evidence",
            "record_observation",
            "ingest_telemetry",
        )

        for method_name in candidates:
            try:
                method = getattr(
                    dialer,
                    method_name,
                    None,
                )

                if not callable(method):
                    continue

                method(evidence)
                return True

            except TypeError:
                continue

            except Exception as exc:
                logger.debug(
                    "[RuntimeTopology] QbitDialer evidence "
                    "skipped via %s: %s",
                    method_name,
                    exc,
                )
                return False

        return False

    # ==========================================================
    # Error handling
    # ==========================================================

    def _record_error(self, exc):
        with self._lock:
            self._last_error = {
                "type": type(exc).__name__,
                "message": str(exc),
                "timestamp": self._utc_now(),
            }

        logger.warning(
            "[RuntimeTopology] Scan error | %s: %s",
            type(exc).__name__,
            exc,
        )

    # ==========================================================
    # History
    # ==========================================================

    def topology_history(self):
        with self._lock:
            return deepcopy(self._history)

    def anomaly_history(self):
        with self._lock:
            return deepcopy(self._anomalies)

    def clear_history(self):
        with self._lock:
            self._history.clear()
            self._anomalies.clear()

        return True

    # ==========================================================
    # Reporting
    # ==========================================================

    def build_report(self):
        snapshot = self.snapshot()

        return {
            "type": "runtime_topology_report",
            "node_id": getattr(
                self,
                "node_id",
                None,
            ),
            "timestamp": self._utc_now(),
            "revision": snapshot.get(
                "topology_revision"
            ),
            "counts": {
                "threads": len(
                    snapshot.get("threads", {})
                ),
                "loops": len(
                    snapshot.get("loops", {})
                ),
                "tasks": len(
                    snapshot.get("tasks", {})
                ),
                "processes": len(
                    snapshot.get("processes", {})
                ),
                "anomalies": len(
                    snapshot.get("anomalies", [])
                ),
            },
            "bindings": snapshot.get(
                "bindings",
                [],
            ),
            "topology": snapshot,
        }

    def show_topology(self):
        report = self.build_report()

        logger.info(
            "[RuntimeTopology] "
            "Threads=%s | Loops=%s | Tasks=%s | "
            "Processes=%s | Anomalies=%s | Revision=%s",
            report["counts"]["threads"],
            report["counts"]["loops"],
            report["counts"]["tasks"],
            report["counts"]["processes"],
            report["counts"]["anomalies"],
            report["revision"],
        )

        return report

    # ==========================================================
    # Status
    # ==========================================================

    def status(self):
        with self._lock:
            return {
                "node_id": getattr(
                    self,
                    "node_id",
                    None,
                ),
                "tool": self.TOOL_NAME,
                "role": self.TOOL_ROLE,
                "version": self.NODE_VERSION,
                "running": self._running,
                "refresh_interval": self.refresh_interval,
                "scan_count": self._scan_count,
                "topology_revision": self._topology_revision,
                "last_scan": self._last_scan,
                "last_error": deepcopy(
                    self._last_error
                ),
                "anomaly_count": self._anomaly_count,
                "bindings": sorted(
                    self._bindings.keys()
                ),
                "counts": {
                    "threads": len(self.threads),
                    "loops": len(self.loops),
                    "tasks": len(self.tasks),
                    "processes": len(self.processes),
                },
                "authority": {
                    "type": "observer",
                    "command_execution": False,
                    "command_submission": False,
                },
            }

    def health(self):
        with self._lock:
            if self._last_error is not None:
                state = "degraded"
            elif not self._running:
                state = "standby"
            else:
                state = "healthy"

            return {
                "state": state,
                "running": self._running,
                "last_error": deepcopy(
                    self._last_error
                ),
                "scan_count": self._scan_count,
                "anomaly_count": self._anomaly_count,
            }

    # ==========================================================
    # Utility
    # ==========================================================

    @staticmethod
    def _utc_now():
        return datetime.now(
            timezone.utc
        ).isoformat()

    def __repr__(self):
        return (
            f"<RuntimeTopologyMapper "
            f"node_id={getattr(self, 'node_id', None)!r} "
            f"running={self._running} "
            f"threads={len(self.threads)} "
            f"loops={len(self.loops)} "
            f"tasks={len(self.tasks)} "
            f"processes={len(self.processes)}>"
        )


# ==============================================================
# Optional module metadata for dynamic tool discovery
# ==============================================================

TOOL_NAME = RuntimeTopologyMapper.TOOL_NAME
TOOL_ROLE = RuntimeTopologyMapper.TOOL_ROLE
TOOL_VERSION = RuntimeTopologyMapper.NODE_VERSION
TOOL_CAPABILITIES = RuntimeTopologyMapper.TOOL_CAPABILITIES
TOOL_DEPENDENCIES = RuntimeTopologyMapper.TOOL_DEPENDENCIES
TOOL_CLASS = "RuntimeTopologyMapper"
TOOL_ALWAYS_ON = False