# ==============================================================
# FILE: SEED_ROOT/seed/tools/fault_quarantine.py
# PURPOSE: Isolate misbehaving modules dynamically for SEED-AI
# VERSION: 2.0.0
# ROLE: fault-isolation / quarantine-state node
# ==============================================================

import logging
import threading
import time
from copy import deepcopy

from seed.tools.base_tool import BaseTool


logger = logging.getLogger("FaultQuarantine")


class FaultQuarantine(BaseTool):


    NODE_TYPE = "tool"
    NODE_VERSION = "2.0.0"

    def __init__(
        self,
        name="fault_quarantine",
        capabilities=None,
        dependencies=None,
        role="fault-isolation",
        version="2.0.0",
        always_on=False,
        auto_release_ttl=None,
    ):
        default_capabilities = {
            "fault_quarantine",
            "fault_isolation",
            "module_freeze_state",
            "module_release_state",
            "fault_tracking",
            "quarantine_monitoring",
            "health_observation",
            "recovery_recommendation",
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

        self.auto_release_ttl = auto_release_ttl

        # RLock prevents nested state reads from deadlocking.
        self._lock = threading.RLock()

        self._quarantine = {}

        self._running = False
        self._monitor_thread = None

        self._quarantine_count = 0
        self._release_count = 0
        self._auto_release_count = 0

        self._last_quarantine = None
        self._last_release = None
        self._last_error = None

    # ----------------------------------------------------------
    # Lifecycle
    # ----------------------------------------------------------

    def start(self):
        with self._lock:
            if self._running:
                return self.status()

            self._running = True

            if (
                self.auto_release_ttl is not None
                and self.auto_release_ttl > 0
            ):
                self._monitor_thread = threading.Thread(
                    target=self._auto_release_loop,
                    name="FaultQuarantineMonitor",
                    daemon=True,
                )
                self._monitor_thread.start()

            self.active = True

        logger.info(
            f"[{self.name}] Started | "
            f"auto_release_ttl={self.auto_release_ttl}"
        )

        return self.status()

    def stop(self):
        with self._lock:
            self._running = False
            self.active = False
            self._monitor_thread = None

        logger.info(f"[{self.name}] Stopped")

        return self.status()

    # ----------------------------------------------------------
    # Quarantine
    # ----------------------------------------------------------

    def quarantine_module(
        self,
        module_name,
        freeze=True,
        reason=None,
        evidence=None,
        source=None,
    ):
        if not module_name:
            raise ValueError("module_name is required")

        now = time.time()

        with self._lock:
            existing = self._quarantine.get(module_name)

            record = {
                "module_name": module_name,
                "frozen": bool(freeze),
                "timestamp": now if freeze else None,
                "reason": reason,
                "evidence": deepcopy(evidence)
                if isinstance(evidence, (dict, list))
                else evidence,
                "source": source or self.name,
                "quarantine_count": (
                    existing.get("quarantine_count", 0) + 1
                    if existing
                    else 1
                ),
                "release_count": (
                    existing.get("release_count", 0)
                    if existing
                    else 0
                ),
            }

            self._quarantine[module_name] = record

            if freeze:
                self._quarantine_count += 1
                self._last_quarantine = now

        logger.warning(
            f"[{self.name}] Module '{module_name}' "
            f"quarantined={bool(freeze)}"
        )

        return deepcopy(record)

    # ----------------------------------------------------------
    # Release
    # ----------------------------------------------------------

    def release_module(self, module_name, reason=None):
        if not module_name:
            raise ValueError("module_name is required")

        now = time.time()

        with self._lock:
            record = self._quarantine.get(module_name)

            if record is None:
                return {
                    "module_name": module_name,
                    "released": False,
                    "reason": "not_quarantined",
                    "timestamp": now,
                }

            was_frozen = bool(record.get("frozen"))

            record["frozen"] = False
            record["timestamp"] = None
            record["last_release_timestamp"] = now
            record["release_count"] = (
                record.get("release_count", 0) + 1
            )

            if reason is not None:
                record["release_reason"] = reason

            if was_frozen:
                self._release_count += 1
                self._last_release = now

            result = deepcopy(record)

        logger.info(
            f"[{self.name}] Module '{module_name}' released"
        )

        return result

    # ----------------------------------------------------------
    # Query state
    # ----------------------------------------------------------

    def is_quarantined(self, module_name):
        with self._lock:
            record = self._quarantine.get(module_name)

            if not record:
                return False

            return bool(record.get("frozen", False))

    def get_quarantine(self, module_name):
        with self._lock:
            record = self._quarantine.get(module_name)

            if record is None:
                return None

            return deepcopy(record)

    def list_quarantined(self):
        with self._lock:
            return {
                name: deepcopy(record)
                for name, record in self._quarantine.items()
                if record.get("frozen", False)
            }

    def list_all(self):
        with self._lock:
            return deepcopy(self._quarantine)

    # ----------------------------------------------------------
    # Snapshot
    # ----------------------------------------------------------

    def snapshot(self):
        with self._lock:
            return {
                "node_id": self.node_id,
                "name": self.name,
                "running": self._running,
                "active": self.active,
                "auto_release_ttl": self.auto_release_ttl,
                "quarantined": self.list_quarantined(),
                "quarantine_count": len(
                    self.list_quarantined()
                ),
                "total_quarantine_events": self._quarantine_count,
                "total_release_events": self._release_count,
                "total_auto_releases": self._auto_release_count,
                "last_quarantine": self._last_quarantine,
                "last_release": self._last_release,
                "last_error": self._last_error,
                "timestamp": time.time(),
            }

    # ----------------------------------------------------------
    # Structured recommendation
    # ----------------------------------------------------------

    def recommend_recovery(
        self,
        module_name,
        reason=None,
        evidence=None,
        confidence=None,
    ):
        if not module_name:
            raise ValueError("module_name is required")

        quarantined = self.is_quarantined(module_name)

        return {
            "type": "quarantine_recommendation",
            "source_node": self.node_id,
            "module_name": module_name,
            "quarantined": quarantined,
            "action": (
                "inspect_and_recover"
                if quarantined
                else "monitor"
            ),
            "reason": reason or (
                "Module remains quarantined"
                if quarantined
                else "Module is not currently quarantined"
            ),
            "evidence": (
                deepcopy(evidence)
                if isinstance(evidence, (dict, list))
                else evidence
            ),
            "confidence": confidence,
            "authority": {
                "required": True,
                "owner": "QbitDialer",
                "executed": False,
            },
            "execution": {
                "executed": False,
                "execution_owner": "QbitDialer",
            },
            "timestamp": time.time(),
        }

    # ----------------------------------------------------------
    # CLI-friendly display
    # ----------------------------------------------------------

    def show_quarantine(self):
        with self._lock:
            quarantined = self.list_quarantined()

        for module_name, data in quarantined.items():
            timestamp = data.get("timestamp")

            if timestamp:
                logger.info(
                    f"[{self.name}] "
                    f"Quarantined module: {module_name} "
                    f"at {timestamp:.3f}"
                )
            else:
                logger.info(
                    f"[{self.name}] "
                    f"Quarantined module: {module_name}"
                )

        return quarantined

    # ----------------------------------------------------------
    # Automatic release
    # ----------------------------------------------------------

    def _auto_release_loop(self):
        while True:
            with self._lock:
                if not self._running:
                    break

                ttl = self.auto_release_ttl

            time.sleep(1.0)

            if ttl is None or ttl <= 0:
                continue

            now = time.time()
            expired = []

            with self._lock:
                for module_name, record in self._quarantine.items():
                    timestamp = record.get("timestamp")

                    if not record.get("frozen"):
                        continue

                    if timestamp is None:
                        continue

                    if now - timestamp > ttl:
                        expired.append(module_name)

            for module_name in expired:
                result = self.release_module(
                    module_name,
                    reason="auto_release_ttl_expired",
                )

                with self._lock:
                    self._auto_release_count += 1

                logger.info(
                    f"[{self.name}] "
                    f"Auto-released module: {module_name}"
                )

    # ----------------------------------------------------------
    # Status
    # ----------------------------------------------------------

    def status(self):
        with self._lock:
            quarantined = self.list_quarantined()

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
                "auto_release_ttl": self.auto_release_ttl,
                "quarantined_count": len(quarantined),
                "total_quarantine_events": self._quarantine_count,
                "total_release_events": self._release_count,
                "total_auto_releases": self._auto_release_count,
                "last_quarantine": self._last_quarantine,
                "last_release": self._last_release,
                "last_error": self._last_error,
            }

    def health(self):
        with self._lock:
            quarantined_count = len(self.list_quarantined())

            if self.failed:
                state = "FAILED"
            elif quarantined_count > 0:
                state = "DEGRADED"
            elif self._running:
                state = "HEALTHY"
            else:
                state = "STOPPED"

            return {
                "state": state,
                "running": self._running,
                "quarantined_count": quarantined_count,
                "timestamp": time.time(),
            }

    def __repr__(self):
        return (
            f"<FaultQuarantine "
            f"name={self.name!r} "
            f"running={self._running} "
            f"quarantined={len(self.list_quarantined())}>"
        )