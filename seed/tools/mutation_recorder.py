# ==============================================================
# FILE: SEED_ROOT/seed/tools/mutation_recorder.py
# PURPOSE: Record runtime mutations in SEED-AI system
# VERSION: 2.0.0
# ROLE: runtime-mutation observer
# ==============================================================

import logging
import threading
import time
from copy import deepcopy

from seed.tools.base_tool import BaseTool


logger = logging.getLogger("MutationRecorder")


class MutationRecorder(BaseTool):


    NODE_TYPE = "tool"
    NODE_VERSION = "2.0.0"

    def __init__(
        self,
        name="mutation_recorder",
        capabilities=None,
        dependencies=None,
        role="runtime-mutation-observer",
        version="2.0.0",
        always_on=False,
        scan_interval=0.1,
    ):
        default_capabilities = {
            "mutation_monitoring",
            "runtime_observation",
            "object_state_tracking",
            "attribute_change_detection",
            "mutation_telemetry",
            "runtime_integrity",
            "state_snapshot",
            "change_history",
        }

        if capabilities:
            default_capabilities.update(capabilities)

        super().__init__(
            name=name,
            capabilities=default_capabilities,
            dependencies=dependencies,
            role=role,
            version=version,
            always_on=always_on,
        )

        self._lock = threading.RLock()

        self._tracked_objects = {}
        self.mutations = []

        self._running = False
        self._monitor_thread = None

        self._scan_interval = max(
            float(scan_interval),
            0.01,
        )

        self._mutation_count = 0
        self._scan_count = 0
        self._tracking_count = 0

        self._last_mutation = None
        self._last_scan = None
        self._last_error = None

    # ----------------------------------------------------------
    # Lifecycle
    # ----------------------------------------------------------

    def start(self):
        with self._lock:
            if self._running:
                return self.status()

            self._running = True
            self.active = True

            self._monitor_thread = threading.Thread(
                target=self._monitor_loop,
                name="MutationRecorderMonitor",
                daemon=True,
            )

            self._monitor_thread.start()

        logger.info(
            f"[{self.name}] Started | "
            f"scan_interval={self._scan_interval}"
        )

        return self.status()

    def stop(self):
        with self._lock:
            self._running = False
            self.active = False
            self._monitor_thread = None

        logger.info(
            f"[{self.name}] Stopped"
        )

        return self.status()

    # ----------------------------------------------------------
    # Object tracking
    # ----------------------------------------------------------

    def track_object(
        self,
        obj,
        obj_name=None,
    ):
        if obj is None:
            raise ValueError(
                "obj is required"
            )

        obj_id = id(obj)

        if not hasattr(obj, "__dict__"):
            logger.warning(
                f"[{self.name}] "
                f"Object is not attribute-trackable: "
                f"{obj!r}"
            )

            return {
                "tracked": False,
                "reason": "object_has_no___dict__",
            }

        with self._lock:
            if obj_id in self._tracked_objects:
                return {
                    "tracked": True,
                    "already_tracked": True,
                    "object_id": obj_id,
                    "name": self._tracked_objects[
                        obj_id
                    ]["name"],
                }

            try:
                snapshot = deepcopy(
                    obj.__dict__
                )
            except Exception as exc:
                snapshot = dict(
                    obj.__dict__
                )

                logger.warning(
                    f"[{self.name}] "
                    f"Deepcopy failed for "
                    f"{obj!r}: {exc}"
                )

            name = (
                obj_name
                or getattr(
                    obj,
                    "name",
                    None,
                )
                or (
                    f"{obj.__class__.__module__}."
                    f"{obj.__class__.__qualname__}"
                )
            )

            self._tracked_objects[obj_id] = {
                "object": obj,
                "object_id": obj_id,
                "name": name,
                "snapshot": snapshot,
                "tracked_at": time.time(),
                "mutation_count": 0,
            }

            self._tracking_count += 1

        logger.debug(
            f"[{self.name}] "
            f"Tracking object: {name}"
        )

        return {
            "tracked": True,
            "already_tracked": False,
            "object_id": obj_id,
            "name": name,
            "timestamp": time.time(),
        }

    # ----------------------------------------------------------
    # Stop tracking an object
    # ----------------------------------------------------------

    def untrack_object(self, obj):
        obj_id = (
            id(obj)
            if not isinstance(obj, int)
            else obj
        )

        with self._lock:
            record = self._tracked_objects.pop(
                obj_id,
                None,
            )

        if record is None:
            return {
                "untracked": False,
                "object_id": obj_id,
            }

        logger.debug(
            f"[{self.name}] "
            f"Stopped tracking: "
            f"{record['name']}"
        )

        return {
            "untracked": True,
            "object_id": obj_id,
            "name": record["name"],
            "timestamp": time.time(),
        }

    # ----------------------------------------------------------
    # List tracked objects
    # ----------------------------------------------------------

    def tracked_objects(self):
        with self._lock:
            return {
                obj_id: {
                    "object_id": record[
                        "object_id"
                    ],
                    "name": record["name"],
                    "tracked_at": record[
                        "tracked_at"
                    ],
                    "mutation_count": record[
                        "mutation_count"
                    ],
                }
                for obj_id, record
                in self._tracked_objects.items()
            }

    # ----------------------------------------------------------
    # Safely snapshot an object
    # ----------------------------------------------------------

    def _snapshot_object(self, obj):
        if not hasattr(obj, "__dict__"):
            return {}

        try:
            return deepcopy(
                obj.__dict__
            )
        except Exception:
            try:
                return dict(
                    obj.__dict__
                )
            except Exception:
                return {}

    # ----------------------------------------------------------
    # Check tracked objects for mutations
    # ----------------------------------------------------------

    def _check_mutations(self):
        mutations = []

        with self._lock:
            records = list(
                self._tracked_objects.items()
            )

            self._scan_count += 1
            self._last_scan = time.time()

        for obj_id, record in records:
            obj = record.get("object")

            if obj is None:
                continue

            try:
                old_snapshot = record.get(
                    "snapshot",
                    {},
                )

                current_state = (
                    self._snapshot_object(obj)
                )

                old_keys = set(
                    old_snapshot.keys()
                )

                current_keys = set(
                    current_state.keys()
                )

                added_keys = (
                    current_keys - old_keys
                )

                removed_keys = (
                    old_keys - current_keys
                )

                changed_keys = {
                    key
                    for key in (
                        current_keys & old_keys
                    )
                    if current_state[key]
                    != old_snapshot[key]
                }

                if not (
                    added_keys
                    or removed_keys
                    or changed_keys
                ):
                    continue

                mutation = {
                    "type": "runtime_mutation",
                    "mutation_id": (
                        f"MUT.{self._mutation_count + 1:08d}"
                    ),
                    "timestamp": time.time(),
                    "source_node": self.node_id,
                    "object_id": obj_id,
                    "object": record["name"],
                    "added": sorted(
                        added_keys
                    ),
                    "removed": sorted(
                        removed_keys
                    ),
                    "changed": sorted(
                        changed_keys
                    ),
                }

                with self._lock:
                    self.mutations.append(
                        mutation
                    )

                    self._mutation_count += 1

                    tracked_record = (
                        self._tracked_objects.get(
                            obj_id
                        )
                    )

                    if tracked_record is not None:
                        tracked_record[
                            "snapshot"
                        ] = current_state

                        tracked_record[
                            "mutation_count"
                        ] += 1

                    self._last_mutation = mutation
                    self._last_error = None

                mutations.append(mutation)

                logger.warning(
                    f"[{self.name}] "
                    f"Mutation detected: "
                    f"{mutation}"
                )

            except Exception as exc:
                with self._lock:
                    self._last_error = {
                        "object_id": obj_id,
                        "object": record.get(
                            "name"
                        ),
                        "error": str(exc),
                        "error_type": (
                            type(exc).__name__
                        ),
                        "timestamp": time.time(),
                    }

                logger.error(
                    f"[{self.name}] "
                    f"Error inspecting "
                    f"{record.get('name')}: "
                    f"{exc}"
                )

        return mutations

    # ----------------------------------------------------------
    # Background monitoring loop
    # ----------------------------------------------------------

    def _monitor_loop(self):
        while True:
            with self._lock:
                if not self._running:
                    break

            try:
                self._check_mutations()
            except Exception as exc:
                with self._lock:
                    self._last_error = {
                        "error": str(exc),
                        "error_type": (
                            type(exc).__name__
                        ),
                        "timestamp": time.time(),
                    }

                logger.error(
                    f"[{self.name}] "
                    f"Mutation monitor error: "
                    f"{exc}"
                )

            time.sleep(
                self._scan_interval
            )

    # ----------------------------------------------------------
    # Manual scan
    # ----------------------------------------------------------

    def scan_now(self):
        return self._check_mutations()

    # ----------------------------------------------------------
    # Snapshot of mutation history
    # ----------------------------------------------------------

    def snapshot(self):
        with self._lock:
            return deepcopy(
                self.mutations
            )

    # ----------------------------------------------------------
    # Mutation history
    # ----------------------------------------------------------

    def mutation_history(self, limit=None):
        with self._lock:
            records = list(
                self.mutations
            )

            if limit is not None:
                if limit < 0:
                    raise ValueError(
                        "limit must be >= 0"
                    )

                records = records[-limit:]

            return deepcopy(records)

    # ----------------------------------------------------------
    # Clear mutation history
    # ----------------------------------------------------------

    def clear(self):
        with self._lock:
            cleared = len(
                self.mutations
            )

            self.mutations.clear()

        logger.info(
            f"[{self.name}] "
            f"Cleared {cleared} mutations"
        )

        return {
            "cleared": cleared,
            "timestamp": time.time(),
        }

    # ----------------------------------------------------------
    # Reset an object's observation baseline
    # ----------------------------------------------------------

    def reset_baseline(self, obj):
        obj_id = id(obj)

        with self._lock:
            record = self._tracked_objects.get(
                obj_id
            )

            if record is None:
                return {
                    "reset": False,
                    "reason": "object_not_tracked",
                    "object_id": obj_id,
                }

            record["snapshot"] = (
                self._snapshot_object(obj)
            )

            record["baseline_reset"] = (
                time.time()
            )

            return {
                "reset": True,
                "object_id": obj_id,
                "name": record["name"],
                "timestamp": (
                    record["baseline_reset"]
                ),
            }

    # ----------------------------------------------------------
    # CLI-friendly display
    # ----------------------------------------------------------

    def show_status(self, last_n=5):
        if last_n < 0:
            raise ValueError(
                "last_n must be >= 0"
            )

        with self._lock:
            records = self.mutations[-last_n:]

        for mutation in records:
            logger.info(
                f"[{self.name}] "
                f"{mutation['timestamp']:.3f} | "
                f"Object: {mutation['object']} | "
                f"Added: {mutation['added']} | "
                f"Removed: {mutation['removed']} | "
                f"Changed: {mutation['changed']}"
            )

        return deepcopy(records)

    # ----------------------------------------------------------
    # Report
    # ----------------------------------------------------------

    def build_report(self):
        with self._lock:
            return {
                "type": "mutation_recorder_report",
                "source_node": self.node_id,
                "running": self._running,
                "active": self.active,
                "tracked_object_count": len(
                    self._tracked_objects
                ),
                "mutation_count": (
                    self._mutation_count
                ),
                "scan_count": self._scan_count,
                "tracking_count": (
                    self._tracking_count
                ),
                "last_mutation": deepcopy(
                    self._last_mutation
                ),
                "last_scan": self._last_scan,
                "last_error": deepcopy(
                    self._last_error
                ),
                "timestamp": time.time(),
            }

    # ----------------------------------------------------------
    # Status
    # ----------------------------------------------------------

    def status(self):
        with self._lock:
            return {
                "node_id": self.node_id,
                "name": self.name,
                "role": self.role,
                "version": self.version,
                "running": self._running,
                "active": self.active,
                "ready": self.ready,
                "degraded": self.degraded,
                "failed": self.failed,
                "tracked_object_count": len(
                    self._tracked_objects
                ),
                "mutation_count": (
                    self._mutation_count
                ),
                "scan_count": self._scan_count,
                "scan_interval": (
                    self._scan_interval
                ),
                "last_mutation": (
                    deepcopy(
                        self._last_mutation
                    )
                ),
                "last_error": deepcopy(
                    self._last_error
                ),
            }

    # ----------------------------------------------------------
    # Health
    # ----------------------------------------------------------

    def health(self):
        with self._lock:
            if self.failed:
                state = "FAILED"
            elif self._last_error is not None:
                state = "DEGRADED"
            elif self._running:
                state = "HEALTHY"
            else:
                state = "STOPPED"

            return {
                "state": state,
                "running": self._running,
                "tracked_objects": len(
                    self._tracked_objects
                ),
                "mutation_count": (
                    self._mutation_count
                ),
                "timestamp": time.time(),
            }

    # ----------------------------------------------------------
    # Representation
    # ----------------------------------------------------------

    def __repr__(self):
        with self._lock:
            return (
                f"<MutationRecorder "
                f"name={self.name!r} "
                f"running={self._running} "
                f"tracked={len(self._tracked_objects)} "
                f"mutations={self._mutation_count}>"
            )