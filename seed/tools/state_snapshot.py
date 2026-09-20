# ==============================================================
#
# File: state_snapshot.py
# Path: SEED_ROOT/seed/tools/state_snapshot.py
# Purpose: Tracks internal SEED-AI state snapshots
#
# VERSION: 2.0.0
# ROLE: state-snapshot-observer
#
# ARCHITECTURE:
#
#   Runtime / Nodes / TrackSystem / Registry
#                    |
#                    v
#              StateSnapshotTool
#                    |
#          +---------+---------+
#          |         |         |
#          v         v         v
#      TrackSystem Registry NeuralBridge
#          |
#          v
#        Oracle
#          |
#          v
#      QbitDialer
#          |
#          v
#    submit_command()
#
# AUTHORITY:
#   OBSERVATION / STATE HISTORY ONLY
#
# This tool NEVER:
#   - executes commands
#   - calls QbitDialer.submit_command()
#   - creates QbitDialer
#   - creates QbitQueueLoop
#   - creates EventBus
#   - creates TrackSystem
#   - creates SRegistry
#   - creates NeuralBridge
#   - creates Oracle
#   - starts a competing SEED runtime loop
#
# ==============================================================

import copy
import logging
import threading
import time
from collections import deque
from datetime import datetime, timezone
from uuid import uuid4

try:
    from seed.tools.base_tool import BaseTool
except ImportError:
    BaseTool = object


logger = logging.getLogger("StateSnapshotTool")


# ==============================================================
# Track ID helper
# ==============================================================

def gen_track_id(prefix="SEEDState_Snapshot"):

    return f"{prefix}-{uuid4().hex[:8]}"


# ==============================================================
# State Snapshot Tool
# ==============================================================

class StateSnapshotTool(BaseTool):

    NODE_TYPE = "tool"
    NODE_VERSION = "2.0.0"

    TOOL_NAME = "state_snapshot"
    TOOL_ROLE = "state-snapshot-observer"

    TOOL_CAPABILITIES = (
        "state_snapshot",
        "state_history",
        "state_comparison",
        "state_change_detection",
        "runtime_state_observation",
        "module_state_observation",
        "event_backlog_observation",
        "error_rate_observation",
        "memory_pressure_observation",
        "loop_state_observation",
        "node_state_observation",
        "registry_state_observation",
        "track_state_observation",
        "neural_state_observation",
        "oracle_evidence",
        "recovery_evidence",
        "snapshot_telemetry",
    )

    TOOL_DEPENDENCIES = (
        "TrackSystem",
        "SRegistry",
        "registry_runtime",
        "NeuralBridge",
        "Oracle",
        "EventBus",
        "QbitDialer",
    )

    TOOL_ALWAYS_ON = False

    DEFAULT_MAX_SNAPSHOTS = 128

    # ==========================================================
    # Constructor
    # ==========================================================

    def __init__(
        self,
        max_snapshots=DEFAULT_MAX_SNAPSHOTS,
        track_system=None,
        registry=None,
        registry_runtime=None,
        neural_bridge=None,
        oracle=None,
        event_bus=None,
        qbit_dialer=None,
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
            try:
                super().__init__(self.TOOL_NAME)
            except TypeError:
                super().__init__()

        try:
            max_snapshots = int(max_snapshots)
        except (TypeError, ValueError):
            max_snapshots = self.DEFAULT_MAX_SNAPSHOTS

        self.max_snapshots = max(
            1,
            max_snapshots,
        )

        self.snapshots = deque(
            maxlen=self.max_snapshots
        )

        self._lock = threading.RLock()

        self.last_snapshot_time = None
        self.last_snapshot_id = None
        self.last_track_id = None
        self.last_error = None

        self._running = False

        self._capture_count = 0
        self._diff_count = 0
        self._change_count = 0

        self._changes = deque(maxlen=256)

        # Existing SEED components only.
        self._bindings = {}

        if track_system is not None:
            self.bind("TrackSystem", track_system)

        if registry is not None:
            self.bind("SRegistry", registry)

        if registry_runtime is not None:
            self.bind(
                "registry_runtime",
                registry_runtime,
            )

        if neural_bridge is not None:
            self.bind(
                "NeuralBridge",
                neural_bridge,
            )

        if oracle is not None:
            self.bind("Oracle", oracle)

        if event_bus is not None:
            self.bind("EventBus", event_bus)

        if qbit_dialer is not None:
            self.bind(
                "QbitDialer",
                qbit_dialer,
            )

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
            "[%s] Bound dependency | name=%s",
            self.TOOL_NAME,
            name,
        )

        return True

    def unbind(self, name):
        with self._lock:
            removed = self._bindings.pop(
                str(name),
                None,
            )

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
                }

            self._running = True

        logger.info(
            "[%s] Started",
            self.TOOL_NAME,
        )

        return {
            "status": "started",
            "node_id": getattr(
                self,
                "node_id",
                None,
            ),
        }

    def stop(self):
        with self._lock:
            if not self._running:
                return {
                    "status": "already_stopped",
                }

            self._running = False

        logger.info(
            "[%s] Stopped",
            self.TOOL_NAME,
        )

        return {
            "status": "stopped",
        }

    # ==========================================================
    # Capture
    # ==========================================================

    def capture(
        self,
        modules=None,
        event_backlog=None,
        error_rate=None,
        memory_pressure=None,
        loops_status=None,
        runtime_topology=None,
        nodes=None,
        registry_state=None,
        track_state=None,
        neural_state=None,
        metadata=None,
        source="runtime",
        track_id=None,
    ):
        """
        Capture an immutable SEED-AI state observation.

        All supplied state is deep-copied so later mutations do not
        modify historical snapshots.
        """

        snapshot_id = (
            f"SNAP.{uuid4().hex[:12]}"
        )

        if track_id is None:
            track_id = gen_track_id()

        timestamp = time.time()

        snapshot = {
            "snapshot_id": snapshot_id,
            "track_id": track_id,
            "timestamp": timestamp,
            "timestamp_iso": self._timestamp_iso(
                timestamp
            ),

            "source": source,

            "node": {
                "node_id": getattr(
                    self,
                    "node_id",
                    None,
                ),
                "tool": self.TOOL_NAME,
                "role": self.TOOL_ROLE,
                "version": self.NODE_VERSION,
            },

            "modules": self._safe_copy(
                modules or {}
            ),

            "event_backlog": (
                0
                if event_backlog is None
                else event_backlog
            ),

            "error_rate": (
                0.0
                if error_rate is None
                else error_rate
            ),

            "memory_pressure": self._safe_copy(
                memory_pressure or {}
            ),

            "loops_status": self._safe_copy(
                loops_status or {}
            ),

            "runtime_topology": self._safe_copy(
                runtime_topology or {}
            ),

            "nodes": self._safe_copy(
                nodes or {}
            ),

            "registry_state": self._safe_copy(
                registry_state or {}
            ),

            "track_state": self._safe_copy(
                track_state or {}
            ),

            "neural_state": self._safe_copy(
                neural_state or {}
            ),

            "metadata": self._safe_copy(
                metadata or {}
            ),

            "authority": {
                "type": "observer",
                "execution": False,
                "command_submission": False,
                "owner": "StateSnapshotTool",
            },
        }

        with self._lock:
            self.snapshots.append(
                copy.deepcopy(snapshot)
            )

            self.last_snapshot_time = timestamp
            self.last_snapshot_id = snapshot_id
            self.last_track_id = track_id

            self._capture_count += 1
            self.last_error = None

        self._publish_observation(snapshot)

        logger.debug(
            "[%s] Snapshot captured | id=%s | track=%s",
            self.TOOL_NAME,
            snapshot_id,
            track_id,
        )

        return copy.deepcopy(snapshot)

    # ==========================================================
    # Snapshot retrieval
    # ==========================================================

    def latest(self):
        with self._lock:
            if not self.snapshots:
                return None

            return copy.deepcopy(
                self.snapshots[-1]
            )

    def all(self):
        with self._lock:
            return [
                copy.deepcopy(snapshot)
                for snapshot in self.snapshots
            ]

    def get(self, snapshot_id):
        with self._lock:
            for snapshot in self.snapshots:
                if (
                    snapshot.get("snapshot_id")
                    == snapshot_id
                ):
                    return copy.deepcopy(snapshot)

        return None

    # ==========================================================
    # Diff
    # ==========================================================

    def diff(
        self,
        snapshot_a,
        snapshot_b,
    ):

        if snapshot_a is None:
            snapshot_a = {}

        if snapshot_b is None:
            snapshot_b = {}

        if not isinstance(snapshot_a, dict):
            raise TypeError(
                "snapshot_a must be a dict"
            )

        if not isinstance(snapshot_b, dict):
            raise TypeError(
                "snapshot_b must be a dict"
            )

        diffs = {}

        keys = set(
            snapshot_a.keys()
        ).union(
            snapshot_b.keys()
        )

        for key in keys:
            value_a = snapshot_a.get(key)
            value_b = snapshot_b.get(key)

            if value_a != value_b:
                diffs[key] = {
                    "before": self._safe_copy(
                        value_a
                    ),
                    "after": self._safe_copy(
                        value_b
                    ),
                }

        with self._lock:
            self._diff_count += 1

            if diffs:
                self._change_count += len(diffs)

                change_record = {
                    "change_id": (
                        f"CHANGE."
                        f"{uuid4().hex[:12]}"
                    ),
                    "track_id": gen_track_id(),
                    "timestamp": time.time(),
                    "fields_changed": sorted(
                        diffs.keys()
                    ),
                    "field_count": len(diffs),
                    "before_snapshot": (
                        snapshot_a.get(
                            "snapshot_id"
                        )
                    ),
                    "after_snapshot": (
                        snapshot_b.get(
                            "snapshot_id"
                        )
                    ),
                }

                self._changes.append(
                    change_record
                )

        return diffs

    # ==========================================================
    # Compare latest snapshots
    # ==========================================================

    def diff_latest(self):
        with self._lock:
            if len(self.snapshots) < 2:
                return {}

            previous = self.snapshots[-2]
            current = self.snapshots[-1]

        return self.diff(
            previous,
            current,
        )

    # ==========================================================
    # Change history
    # ==========================================================

    def changes(self):
        with self._lock:
            return copy.deepcopy(
                list(self._changes)
            )

    def clear_changes(self):
        with self._lock:
            self._changes.clear()

        return True

    # ==========================================================
    # Publish observation
    # ==========================================================

    def _publish_observation(self, snapshot):

        observation = {
            "type": "state_snapshot",
            "track_id": snapshot.get(
                "track_id"
            ),
            "snapshot_id": snapshot.get(
                "snapshot_id"
            ),
            "source": self.TOOL_NAME,
            "timestamp": snapshot.get(
                "timestamp"
            ),
            "state": snapshot,
            "authority": {
                "owner": "StateSnapshotTool",
                "executed": False,
                "command_submitted": False,
            },
        }

        self._publish_event_bus(
            observation
        )

        self._publish_track_system(
            observation
        )

        self._publish_registry(
            observation
        )

        self._publish_neural_bridge(
            observation
        )

        self._publish_oracle(
            observation
        )

        # Deliberately evidence-only.
        self._publish_dialer_evidence(
            observation
        )

    # ==========================================================
    # EventBus
    # ==========================================================

    def _publish_event_bus(self, observation):
        event_bus = self.get_binding(
            "EventBus"
        )

        if event_bus is None:
            return False

        emit = getattr(
            event_bus,
            "emit",
            None,
        )

        if not callable(emit):
            return False

        try:
            emit(
                "STATE_SNAPSHOT",
                observation,
            )
            return True

        except Exception as exc:
            logger.debug(
                "[%s] EventBus publish skipped: %s",
                self.TOOL_NAME,
                exc,
            )

        return False

    # ==========================================================
    # TrackSystem
    # ==========================================================

    def _publish_track_system(self, observation):
        track_system = self.get_binding(
            "TrackSystem"
        )

        if track_system is None:
            return False

        methods = (
            "record_observation",
            "record_telemetry",
            "ingest_observation",
            "track",
        )

        for method_name in methods:
            method = getattr(
                track_system,
                method_name,
                None,
            )

            if not callable(method):
                continue

            try:
                method(observation)
                return True

            except TypeError:
                continue

            except Exception as exc:
                logger.debug(
                    "[%s] TrackSystem publish skipped "
                    "via %s: %s",
                    self.TOOL_NAME,
                    method_name,
                    exc,
                )
                return False

        return False

    # ==========================================================
    # Registry
    # ==========================================================

    def _publish_registry(self, observation):
        registry = self.get_binding(
            "SRegistry"
        )

        if registry is None:
            return False

        evidence = {
            "type": "state_snapshot_evidence",
            "track_id": observation.get(
                "track_id"
            ),
            "snapshot_id": observation.get(
                "snapshot_id"
            ),
            "timestamp": observation.get(
                "timestamp"
            ),
            "source": self.TOOL_NAME,
            "state": observation.get(
                "state"
            ),
        }

        methods = (
            "record_runtime_evidence",
            "record_observation",
            "update_runtime_state",
        )

        for method_name in methods:
            method = getattr(
                registry,
                method_name,
                None,
            )

            if not callable(method):
                continue

            try:
                method(evidence)
                return True

            except TypeError:
                continue

            except Exception as exc:
                logger.debug(
                    "[%s] Registry publish skipped "
                    "via %s: %s",
                    self.TOOL_NAME,
                    method_name,
                    exc,
                )
                return False

        return False

    # ==========================================================
    # NeuralBridge
    # ==========================================================

    def _publish_neural_bridge(
        self,
        observation,
    ):
        bridge = self.get_binding(
            "NeuralBridge"
        )

        if bridge is None:
            return False

        evidence = {
            "type": "state_snapshot_evidence",
            "track_id": observation.get(
                "track_id"
            ),
            "snapshot_id": observation.get(
                "snapshot_id"
            ),
            "state": observation.get(
                "state"
            ),
            "lifecycle": {
                "observed": True,
                "execution": False,
            },
        }

        methods = (
            "record_observation",
            "ingest_observation",
            "observe",
            "record_telemetry",
        )

        for method_name in methods:
            method = getattr(
                bridge,
                method_name,
                None,
            )

            if not callable(method):
                continue

            try:
                method(evidence)
                return True

            except TypeError:
                continue

            except Exception as exc:
                logger.debug(
                    "[%s] NeuralBridge publish skipped "
                    "via %s: %s",
                    self.TOOL_NAME,
                    exc,
                )
                return False

        return False

    # ==========================================================
    # Oracle
    # ==========================================================

    def _publish_oracle(self, observation):

        oracle = self.get_binding(
            "Oracle"
        )

        if oracle is None:
            return False

        evidence = {
            "type": "state_snapshot_evidence",
            "track_id": observation.get(
                "track_id"
            ),
            "snapshot_id": observation.get(
                "snapshot_id"
            ),
            "source": self.TOOL_NAME,
            "state": observation.get(
                "state"
            ),
            "authority": {
                "required": True,
                "owner": "Oracle",
                "executed": False,
            },
        }

        methods = (
            "record_evidence",
            "record_observation",
            "ingest_observation",
            "observe",
        )

        for method_name in methods:
            method = getattr(
                oracle,
                method_name,
                None,
            )

            if not callable(method):
                continue

            try:
                method(evidence)
                return True

            except TypeError:
                continue

            except Exception as exc:
                logger.debug(
                    "[%s] Oracle evidence skipped "
                    "via %s: %s",
                    self.TOOL_NAME,
                    exc,
                )
                return False

        return False

    # ==========================================================
    # QbitDialer
    # ==========================================================

    def _publish_dialer_evidence(
        self,
        observation,
    ):

        dialer = self.get_binding(
            "QbitDialer"
        )

        if dialer is None:
            return False

        evidence = {
            "type": "state_snapshot_evidence",
            "track_id": observation.get(
                "track_id"
            ),
            "snapshot_id": observation.get(
                "snapshot_id"
            ),
            "source": self.TOOL_NAME,
            "state": observation.get(
                "state"
            ),
            "authority": {
                "required": True,
                "owner": "QbitDialer",
                "executed": False,
                "command_submitted": False,
            },
        }

        methods = (
            "record_runtime_evidence",
            "record_observation",
            "ingest_telemetry",
        )

        for method_name in methods:
            method = getattr(
                dialer,
                method_name,
                None,
            )

            if not callable(method):
                continue

            try:
                method(evidence)
                return True

            except TypeError:
                continue

            except Exception as exc:
                logger.debug(
                    "[%s] QbitDialer evidence skipped "
                    "via %s: %s",
                    self.TOOL_NAME,
                    method_name,
                    exc,
                )
                return False

        return False

    # ==========================================================
    # Reports
    # ==========================================================

    def build_report(self):
        latest = self.latest()

        return {
            "type": "state_snapshot_report",
            "node_id": getattr(
                self,
                "node_id",
                None,
            ),
            "tool": self.TOOL_NAME,
            "role": self.TOOL_ROLE,
            "version": self.NODE_VERSION,
            "timestamp": self._timestamp_iso(),
            "running": self._running,
            "snapshot_count": len(
                self.snapshots
            ),
            "max_snapshots": self.max_snapshots,
            "capture_count": self._capture_count,
            "diff_count": self._diff_count,
            "change_count": self._change_count,
            "last_snapshot_id": (
                self.last_snapshot_id
            ),
            "last_track_id": self.last_track_id,
            "latest": latest,
            "bindings": sorted(
                self._bindings.keys()
            ),
            "authority": {
                "type": "observer",
                "command_execution": False,
                "command_submission": False,
            },
        }

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
                "snapshots_stored": len(
                    self.snapshots
                ),
                "max_snapshots": self.max_snapshots,
                "capture_count": self._capture_count,
                "diff_count": self._diff_count,
                "change_count": self._change_count,
                "last_snapshot_time": (
                    self.last_snapshot_time
                ),
                "last_snapshot_id": (
                    self.last_snapshot_id
                ),
                "last_track_id": (
                    self.last_track_id
                ),
                "last_error": copy.deepcopy(
                    self.last_error
                ),
                "bindings": sorted(
                    self._bindings.keys()
                ),
                "authority": {
                    "type": "observer",
                    "command_execution": False,
                    "command_submission": False,
                },
            }

    def health(self):
        with self._lock:
            if self.last_error is not None:
                state = "degraded"
            elif not self._running:
                state = "standby"
            else:
                state = "healthy"

            return {
                "state": state,
                "running": self._running,
                "snapshot_count": len(
                    self.snapshots
                ),
                "last_error": copy.deepcopy(
                    self.last_error
                ),
            }

    # ==========================================================
    # Clear
    # ==========================================================

    def clear(self):
        with self._lock:
            self.snapshots.clear()
            self._changes.clear()

            self.last_snapshot_time = None
            self.last_snapshot_id = None
            self.last_track_id = None

        logger.info(
            "[%s] Snapshot history cleared",
            self.TOOL_NAME,
        )

        return True

    # ==========================================================
    # CLI
    # ==========================================================

    def show_latest(self):
        latest_snap = self.latest()

        if not latest_snap:
            logger.info(
                "[%s] No snapshots captured yet",
                self.TOOL_NAME,
            )
            return None

        logger.info(
            "[%s] Latest snapshot | id=%s | "
            "track=%s | timestamp=%.3f | keys=%s",
            self.TOOL_NAME,
            latest_snap.get(
                "snapshot_id"
            ),
            latest_snap.get(
                "track_id"
            ),
            latest_snap.get(
                "timestamp",
                0.0,
            ),
            list(latest_snap.keys()),
        )

        return latest_snap

    # ==========================================================
    # Safe copying
    # ==========================================================

    @staticmethod
    def _safe_copy(value):
        try:
            return copy.deepcopy(value)
        except Exception:
            try:
                if isinstance(value, dict):
                    return dict(value)

                if isinstance(value, (list, tuple)):
                    return list(value)

                return repr(value)

            except Exception:
                return "<unserializable>"

    # ==========================================================
    # Timestamp
    # ==========================================================

    @staticmethod
    def _timestamp_iso(timestamp=None):
        if timestamp is None:
            timestamp = time.time()

        return datetime.fromtimestamp(
            timestamp,
            timezone.utc,
        ).isoformat()

    # ==========================================================
    # Representation
    # ==========================================================

    def __repr__(self):
        return (
            f"<StateSnapshotTool "
            f"node_id="
            f"{getattr(self, 'node_id', None)!r} "
            f"running={self._running} "
            f"snapshots={len(self.snapshots)}>"
        )


# ==============================================================
# Dynamic tool discovery metadata
# ==============================================================

TOOL_NAME = StateSnapshotTool.TOOL_NAME
TOOL_ROLE = StateSnapshotTool.TOOL_ROLE
TOOL_VERSION = StateSnapshotTool.NODE_VERSION
TOOL_CAPABILITIES = StateSnapshotTool.TOOL_CAPABILITIES
TOOL_DEPENDENCIES = StateSnapshotTool.TOOL_DEPENDENCIES
TOOL_CLASS = "StateSnapshotTool"
TOOL_ALWAYS_ON = False