# ==========================================================
# FILE: healthmonitor.py
# PATH: SEED_ROOT/seed/systemutils/healthmonitor.py
#
# VERSION: 5.0.0
# BUILD: PASSIVE-QBIT-SENSOR / DIALER-AUTHORITY /
#        CAUSAL-TELEMETRY / BOOT-SAFE / NO-WORKER
#
# UPDATED: 2026-08-18
#
# PURPOSE:
# - Passively observe SEED health/resource conditions
# - Produce useful, attributable Qbits
# - Feed health Qbits to QbitDialer
# - Preserve source/module/operation/track identity
# - Distinguish observation from causation
# - Track resource pressure without controlling runtime
# - Provide process-level pressure evidence when requested
# - Remain safe during boot and shutdown
#
# AUTHORITY MODEL:
#
#                 HEALTHMONITOR
#                       |
#                 OBSERVE ONLY
#                       |
#                       v
#                    QBIT
#                       |
#                       v
#                  QBIT DIALER
#                       |
#                DECISION / ACTION
#
# HealthMonitor NEVER:
#
# - starts worker threads
# - creates asyncio loops
# - starts subsystems
# - stops subsystems
# - repairs modules
# - enters limp mode
# - commands AgentManager
# - commands TrackSystem
# - commands TimeTravelEngine
# - blocks workload
# - controls QbitDialer
#
# HealthMonitor MAY:
#
# - inspect CPU
# - inspect memory
# - inspect disk
# - inspect process/resource information
# - record explicit faults supplied by another subsystem
# - create health Qbits
# - send those Qbits to QbitDialer
# - expose diagnostics
#
# IMPORTANT:
#
# A resource observation is NOT automatically a causal diagnosis.
#
# Example:
#
#   memory = 73%
#
# means:
#
#   MEMORY_PRESSURE_OBSERVED
#
# It does NOT mean:
#
#   TimeTravelEngine caused memory pressure.
#
# Causal attribution requires source/module/operation evidence.
# ==========================================================

from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from collections import deque
from typing import Any, Callable, Dict, Optional, List

import psutil

from seed.core.qbit import Qbit
from seed.core.tracked_data import TrackedData
from seed.core.track_base import TrackBase


logger = logging.getLogger("Health.Monitor")
logger.setLevel(logging.INFO)


# ==========================================================
# HEALTH STATES
# ==========================================================

OK = "OK"
YELLOW = "YELLOW"
RED = "RED"
LOCKED = "LOCKED"


# ==========================================================
# RESOURCE STATES
# ==========================================================

RESOURCE_CLEAR = "CLEAR"
RESOURCE_PRESSURE = "PRESSURE"
RESOURCE_WARNING = "WARNING"
RESOURCE_CRITICAL = "CRITICAL"


# ==========================================================
# HEALTH MONITOR
# ==========================================================

class HealthMonitor(TrackBase):

    VERSION = "5.0.0"

    # ------------------------------------------------------
    # Observation defaults
    # ------------------------------------------------------

    DEFAULT_CHECK_INTERVAL = 30.0

    CPU_THRESHOLD = 70.0
    MEMORY_THRESHOLD = 70.0
    DISK_THRESHOLD = 75.0

    # ------------------------------------------------------
    # Qbit behavior
    # ------------------------------------------------------

    QBIT_FEEDBACK_INTERVAL = 1.5
    ANALYTICS_LIMIT = 100
    RESOURCE_HISTORY_LIMIT = 100

    # ------------------------------------------------------
    # Process inspection
    # ------------------------------------------------------

    PROCESS_SAMPLE_LIMIT = 12

    # ------------------------------------------------------
    # Alert throttling
    # ------------------------------------------------------

    RESOURCE_ALERT_COOLDOWN = 5.0

    # ------------------------------------------------------
    # Module severity is retained as metadata only.
    #
    # It no longer controls repairs.
    # ------------------------------------------------------

    MODULE_SEVERITY = {
        "BuildManager": "CRITICAL",
        "QbitDialer": "HIGH",
        "SkillEngine": "MED",
        "AnalyticsEngine": "LOW",
    }

    # ======================================================
    # INIT
    # ======================================================

    def __init__(
        self,
        track_context=None,
        track=None,
        payload=None,
        emit=None,
        event_bus=None,
        qbit=None,
        qbit_dialer=None,
        agent_manager=None,
        seedcore=None,
        seed_core=None,
        check_interval=None,
        live_debug=True,
        boot_complete=False,
        *args,
        **kwargs,
    ):

        super().__init__()

        self.log = logger

        # --------------------------------------------------
        # External references
        # --------------------------------------------------

        self.event_bus = event_bus
        self.qbit = qbit
        self.qbit_dialer = qbit_dialer

        self.agent_manager = agent_manager

        self.seedcore = (
            seedcore
            if seedcore is not None
            else seed_core
        )

        self.payload = payload or {}

        self.emit = (
            emit
            if callable(emit)
            else self._safe_emit
        )

        self.track_context = (
            track_context
            if callable(track_context)
            else self._safe_track_context
        )

        self.track = (
            track
            if callable(track)
            else self._safe_track
        )

        self.check_interval = (
            float(check_interval)
            if check_interval is not None
            else self.DEFAULT_CHECK_INTERVAL
        )

        self.live_debug = bool(live_debug)

        # --------------------------------------------------
        # Lifecycle
        #
        # IMPORTANT:
        #
        # No worker threads are started here.
        # --------------------------------------------------

        self._stop_event = threading.Event()
        self._lock = threading.RLock()

        self._started = False
        self._stopped = False
        self.boot_complete = bool(boot_complete)
        self.post_complete = False

        self.started_at = time.time()
        self.last_check = 0.0

        # --------------------------------------------------
        # Resource metrics
        # --------------------------------------------------

        self.cpu_usage = 0.0
        self.memory_usage = 0.0
        self.disk_usage = 0.0

        self.cpu_percent_delta = 0.0
        self.memory_percent_delta = 0.0
        self.disk_percent_delta = 0.0

        self.previous_cpu = None
        self.previous_memory = None
        self.previous_disk = None

        # --------------------------------------------------
        # Resource classification
        # --------------------------------------------------

        self.resource_state = RESOURCE_CLEAR
        self.last_resource_cause = "initialization"

        # --------------------------------------------------
        # Attribution
        # --------------------------------------------------

        self.last_source = None
        self.last_module = None
        self.last_operation = None
        self.last_track_id = None

        # --------------------------------------------------
        # Explicit fault registry
        #
        # HealthMonitor records supplied evidence.
        # It does NOT decide what to repair.
        # --------------------------------------------------

        self.modules: Dict[str, Dict[str, Any]] = {}

        # --------------------------------------------------
        # Resource history
        # --------------------------------------------------

        self.resource_history = deque(
            maxlen=self.RESOURCE_HISTORY_LIMIT
        )

        # --------------------------------------------------
        # Qbit history
        # --------------------------------------------------

        self.qbit_history = deque(
            maxlen=self.ANALYTICS_LIMIT
        )

        # --------------------------------------------------
        # Alert control
        # --------------------------------------------------

        self._last_alert = {}

        # --------------------------------------------------
        # Counters
        # --------------------------------------------------

        self.total_observations = 0
        self.total_qbits = 0
        self.total_faults = 0
        self.total_advisories = 0
        self.total_dialer_dispatches = 0
        self.total_dialer_failures = 0

        # --------------------------------------------------
        # Dashboard
        # --------------------------------------------------

        self.dashboard: Dict[str, Any] = {}

        self.state = "INIT"

        # --------------------------------------------------
        # Explicit event subscription.
        #
        # Subscription does NOT create a worker.
        #
        # Also: HEALTH_CHECK no longer invents a
        # BuildManager fault.
        # --------------------------------------------------

        if event_bus is not None:

            subscribe = getattr(
                event_bus,
                "subscribe",
                None,
            )

            if callable(subscribe):

                try:
                    subscribe(
                        "HEALTH_CHECK",
                        callback=self._event_callback,
                    )

                except Exception as exc:

                    logger.debug(
                        "[HealthMonitor] "
                        f"HEALTH_CHECK subscription skipped: {exc}"
                    )

        logger.info(
            "[HealthMonitor] PASSIVE initialized | "
            f"version={self.VERSION} | "
            f"qbit_dialer="
            f"{type(self.qbit_dialer).__name__ if self.qbit_dialer else 'None'} | "
            "workers=0 | authority=QbitDialer"
        )

    # ======================================================
    # SAFE CALLBACKS
    # ======================================================

    @staticmethod
    def _safe_emit(
        event_type,
        payload=None,
        **kwargs,
    ):
        return None

    @staticmethod
    def _safe_track_context(
        *args,
        **kwargs,
    ):
        return {}

    @staticmethod
    def _safe_track(
        *args,
        **kwargs,
    ):
        return {}

    # ======================================================
    # LIFECYCLE
    # ======================================================

    def start(self):
        

        with self._lock:

            if self._stopped:
                return False

            self._started = True
            self.boot_complete = True
            self.state = "RUNNING"

        logger.info(
            "[HealthMonitor] Passive runtime enabled | workers=0"
        )

        return True

    # ------------------------------------------------------

    def stop(self):

        with self._lock:

            self._stop_event.set()
            self._stopped = True
            self._started = False
            self.state = "STOPPED"

        logger.info(
            "[HealthMonitor] Passive monitor stopped"
        )

    # ------------------------------------------------------

    def set_boot_complete(
        self,
        complete: bool = True,
    ):

        with self._lock:
            self.boot_complete = bool(complete)

        logger.info(
            "[HealthMonitor] boot_complete=%s",
            self.boot_complete,
        )

    # ======================================================
    # EVENT INPUT
    # ======================================================

    def _event_callback(
        self,
        *args,
        **kwargs,
    ):
       

        data = self._extract_event_data(
            args,
            kwargs,
        )

        if not data:
            return None

        return self.observe(
            source=data.get("source"),
            module=data.get("module"),
            operation=data.get("operation"),
            track_id=data.get("track_id"),
            event=data,
            emit_qbit=True,
        )

    # ------------------------------------------------------

    @staticmethod
    def _extract_event_data(
        args,
        kwargs,
    ) -> Dict[str, Any]:

        if kwargs:
            data = dict(kwargs)

            if "data" in data and isinstance(
                data["data"],
                dict,
            ):
                nested = dict(data["data"])
                nested.update(
                    {
                        k: v
                        for k, v in data.items()
                        if k != "data"
                    }
                )
                return nested

            return data

        if args:

            if isinstance(args[0], dict):
                return dict(args[0])

            if len(args) > 1 and isinstance(
                args[1],
                dict,
            ):
                return dict(args[1])

        return {}

    # ======================================================
    # RESOURCE OBSERVATION
    # ======================================================

    def observe(
        self,
        *,
        source: Optional[str] = None,
        module: Optional[str] = None,
        operation: Optional[str] = None,
        track_id: Optional[str] = None,
        event: Optional[Dict[str, Any]] = None,
        emit_qbit: bool = True,
        include_processes: bool = False,
    ) -> Dict[str, Any]:
       

        if self._stopped:
            return self.diagnostics()

        event = (
            dict(event)
            if isinstance(event, dict)
            else {}
        )

        now = time.time()

        # --------------------------------------------------
        # Attribution
        # --------------------------------------------------

        source = (
            source
            or event.get("source")
            or event.get("origin")
        )

        module = (
            module
            or event.get("module")
            or event.get("component")
        )

        operation = (
            operation
            or event.get("operation")
            or event.get("action")
        )

        track_id = (
            track_id
            or event.get("track_id")
            or event.get("track")
        )

        # --------------------------------------------------
        # System resources
        # --------------------------------------------------

        cpu = self._safe_cpu_percent()

        memory = self._safe_memory_percent()

        disk = self._safe_disk_percent()

        # --------------------------------------------------
        # Deltas
        # --------------------------------------------------

        with self._lock:

            if self.previous_cpu is not None:
                self.cpu_percent_delta = (
                    cpu - self.previous_cpu
                )

            if self.previous_memory is not None:
                self.memory_percent_delta = (
                    memory - self.previous_memory
                )

            if self.previous_disk is not None:
                self.disk_percent_delta = (
                    disk - self.previous_disk
                )

            self.previous_cpu = cpu
            self.previous_memory = memory
            self.previous_disk = disk

            self.cpu_usage = cpu
            self.memory_usage = memory
            self.disk_usage = disk

            self.last_check = now

            self.last_source = source
            self.last_module = module
            self.last_operation = operation
            self.last_track_id = track_id

            self.total_observations += 1

        # --------------------------------------------------
        # Classify pressure
        # --------------------------------------------------

        resource_state, cause = (
            self._classify_resources(
                cpu=cpu,
                memory=memory,
                disk=disk,
            )
        )

        with self._lock:

            self.resource_state = resource_state
            self.last_resource_cause = cause

        # --------------------------------------------------
        # Build evidence
        # --------------------------------------------------

        evidence = {
            "timestamp": now,

            "source": source,
            "module": module,
            "operation": operation,
            "track_id": track_id,

            "resources": {
                "cpu": round(cpu, 2),
                "memory": round(memory, 2),
                "disk": round(disk, 2),

                "cpu_delta": round(
                    self.cpu_percent_delta,
                    2,
                ),

                "memory_delta": round(
                    self.memory_percent_delta,
                    2,
                ),

                "disk_delta": round(
                    self.disk_percent_delta,
                    2,
                ),
            },

            "thresholds": {
                "cpu": self.CPU_THRESHOLD,
                "memory": self.MEMORY_THRESHOLD,
                "disk": self.DISK_THRESHOLD,
            },

            "resource_state": resource_state,

            "cause": cause,

            # Explicitly mark that this is an observation,
            # not a proven causal diagnosis.
            "causal_confidence": self._causal_confidence(
                source=source,
                module=module,
                operation=operation,
                event=event,
            ),

            "causal_basis": self._causal_basis(
                source=source,
                module=module,
                operation=operation,
                event=event,
            ),

            "event": event,
        }

        # --------------------------------------------------
        # Optional process evidence
        # --------------------------------------------------

        if include_processes:

            evidence[
                "top_processes"
            ] = self.capture_process_pressure()

        # --------------------------------------------------
        # Store
        # --------------------------------------------------

        with self._lock:

            self.resource_history.append(
                dict(evidence)
            )

            self._update_dashboard_locked(
                evidence
            )

        # --------------------------------------------------
        # Qbit
        # --------------------------------------------------

        if emit_qbit:

            qbit = self._build_health_qbit(
                evidence
            )

            self.qbit_history.append(qbit)

            self.total_qbits += 1

            self._dispatch_qbit(
                qbit
            )

        # --------------------------------------------------
        # Optional throttled telemetry.
        #
        # This is informational only.
        # --------------------------------------------------

        self._emit_observation(
            evidence
        )

        return evidence

    # ======================================================
    # RESOURCE READERS
    # ======================================================

    @staticmethod
    def _safe_cpu_percent() -> float:

        try:
            return float(
                psutil.cpu_percent(
                    interval=None
                )
            )

        except Exception:
            return 0.0

    # ------------------------------------------------------

    @staticmethod
    def _safe_memory_percent() -> float:

        try:
            return float(
                psutil.virtual_memory().percent
            )

        except Exception:
            return 0.0

    # ------------------------------------------------------

    @staticmethod
    def _safe_disk_percent() -> float:

        try:

            path = os.environ.get(
                "SystemDrive",
                "C:",
            )

            return float(
                psutil.disk_usage(path).percent
            )

        except Exception:

            try:
                return float(
                    psutil.disk_usage(
                        os.getcwd()
                    ).percent
                )

            except Exception:
                return 0.0

    # ======================================================
    # RESOURCE CLASSIFICATION
    # ======================================================

    def _classify_resources(
        self,
        *,
        cpu: float,
        memory: float,
        disk: float,
    ):

        # --------------------------------------------------
        # Critical
        # --------------------------------------------------

        if (
            cpu >= 90.0
            or memory >= 90.0
            or disk >= 95.0
        ):

            return (
                RESOURCE_CRITICAL,
                self._resource_cause(
                    cpu,
                    memory,
                    disk,
                ),
            )

        # --------------------------------------------------
        # Warning
        # --------------------------------------------------

        if (
            cpu >= 80.0
            or memory >= 80.0
            or disk >= 85.0
        ):

            return (
                RESOURCE_WARNING,
                self._resource_cause(
                    cpu,
                    memory,
                    disk,
                ),
            )

        # --------------------------------------------------
        # Pressure
        # --------------------------------------------------

        if (
            cpu >= self.CPU_THRESHOLD
            or memory >= self.MEMORY_THRESHOLD
            or disk >= self.DISK_THRESHOLD
        ):

            return (
                RESOURCE_PRESSURE,
                self._resource_cause(
                    cpu,
                    memory,
                    disk,
                ),
            )

        return (
            RESOURCE_CLEAR,
            "resources_clear",
        )

    # ------------------------------------------------------

    @staticmethod
    def _resource_cause(
        cpu: float,
        memory: float,
        disk: float,
    ) -> str:

        values = {
            "cpu_pressure": cpu,
            "memory_pressure": memory,
            "disk_pressure": disk,
        }

        dominant = max(
            values,
            key=values.get,
        )

        return dominant

    # ======================================================
    # CAUSAL ATTRIBUTION
    # ======================================================

    @staticmethod
    def _causal_confidence(
        *,
        source,
        module,
        operation,
        event,
    ) -> str:

        if (
            source
            and module
            and operation
        ):
            return "HIGH"

        if module and operation:
            return "MEDIUM"

        if module or source:
            return "LOW"

        return "NONE"

    # ------------------------------------------------------

    @staticmethod
    def _causal_basis(
        *,
        source,
        module,
        operation,
        event,
    ) -> str:

        if (
            source
            and module
            and operation
        ):
            return (
                "explicit_source_module_operation"
            )

        if module and operation:
            return (
                "explicit_module_operation"
            )

        if module:
            return "explicit_module"

        if source:
            return "explicit_source"

        if event:
            return "event_without_full_attribution"

        return "resource_observation_only"

    # ======================================================
    # QBIT CREATION
    # ======================================================

    def _build_health_qbit(
        self,
        evidence: Dict[str, Any],
    ):

        track_id = (
            evidence.get("track_id")
            or self._generate_track_id(
                evidence
            )
        )

        payload = {
            "kind": "HEALTH_OBSERVATION",

            "source": (
                evidence.get("source")
                or "HealthMonitor"
            ),

            "module": evidence.get(
                "module"
            ),

            "operation": evidence.get(
                "operation"
            ),

            "track_id": track_id,

            "resource_state": evidence.get(
                "resource_state"
            ),

            "cause": evidence.get(
                "cause"
            ),

            "resources": dict(
                evidence.get(
                    "resources",
                    {},
                )
            ),

            "thresholds": dict(
                evidence.get(
                    "thresholds",
                    {},
                )
            ),

            "causal_confidence": evidence.get(
                "causal_confidence"
            ),

            "causal_basis": evidence.get(
                "causal_basis"
            ),

            "event": dict(
                evidence.get(
                    "event",
                    {},
                )
            ),
        }

        # --------------------------------------------------
        # Prefer the project's Qbit object.
        # --------------------------------------------------

        try:

            qbit = Qbit(
                payload=payload,
                event_bus=self.event_bus,
            )

        except TypeError:

            try:

                qbit = Qbit(
                    event_bus=self.event_bus
                )

                try:
                    qbit.payload = payload
                except Exception:
                    pass

            except Exception as exc:

                logger.debug(
                    "[HealthMonitor] "
                    f"Qbit construction failed: {exc}"
                )

                # Last-resort dictionary-like signal.
                qbit = payload

        # --------------------------------------------------
        # Attach metadata without assuming a rigid Qbit API.
        # --------------------------------------------------

        self._safe_set(
            qbit,
            "track_id",
            track_id,
        )

        self._safe_set(
            qbit,
            "track",
            {
                "track_id": track_id,
                "source": evidence.get(
                    "source"
                ),
                "module": evidence.get(
                    "module"
                ),
                "operation": evidence.get(
                    "operation"
                ),
                "channel": "HEALTH",
            },
        )

        self._safe_set(
            qbit,
            "source",
            evidence.get(
                "source"
            ) or "HealthMonitor",
        )

        self._safe_set(
            qbit,
            "channel",
            "HEALTH",
        )

        self._safe_set(
            qbit,
            "flags",
            {
                "health": True,
                "resource_observation": True,
                "causal_attribution": (
                    evidence.get(
                        "causal_confidence"
                    )
                    != "NONE"
                ),
            },
        )

        return qbit

    # ------------------------------------------------------

    @staticmethod
    def _safe_set(
        obj,
        attribute,
        value,
    ):

        try:
            setattr(
                obj,
                attribute,
                value,
            )

        except Exception:
            pass

    # ------------------------------------------------------

    @staticmethod
    def _generate_track_id(
        evidence,
    ) -> str:

        module = (
            evidence.get("module")
            or "system"
        )

        return (
            "health_HEALTH_"
            f"{module}_"
            f"{uuid.uuid4().hex[:10]}"
        )
    # ======================================================
    # QBIT DIALER DISPATCH
    # ======================================================

    def _dispatch_qbit(
        self,
        qbit,
    ) -> bool:


        if qbit is None:
            logger.debug(
                "[HealthMonitor] Qbit dispatch skipped | "
                "qbit=None"
            )
            return False

        dialer = getattr(
            self,
            "qbit_dialer",
            None,
        )

        if dialer is None:
            logger.debug(
                "[HealthMonitor] Qbit dispatch skipped | "
                "QbitDialer unavailable"
            )
            return False

        # --------------------------------------------------
        # Preferred authoritative Dialer interfaces
        # --------------------------------------------------
        #
        # receive_qbit is the primary compatibility contract.
        #
        # The remaining methods are retained for existing
        # implementations already present in the SEED tree.
        # --------------------------------------------------

        methods = (
            "receive_qbit",
            "submit_qbit",
            "enqueue_qbit",
            "process_qbit",
            "handle_qbit",
            "add_qbit",
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

                method(qbit)

                self.total_dialer_dispatches += 1

                logger.debug(
                    "[HealthMonitor] Qbit dispatched to "
                    "QbitDialer | method=%s",
                    method_name,
                )

                return True

            except TypeError:

                # --------------------------------------------------
                # Compatibility with implementations expecting:
                #
                #     method(qbit=qbit)
                #
                # --------------------------------------------------

                try:

                    method(
                        qbit=qbit,
                    )

                    self.total_dialer_dispatches += 1

                    logger.debug(
                        "[HealthMonitor] Qbit dispatched to "
                        "QbitDialer | method=%s | keyword=qbit",
                        method_name,
                    )

                    return True

                except Exception as exc:

                    logger.debug(
                        "[HealthMonitor] "
                        "QbitDialer dispatch "
                        "%s keyword form failed: %s",
                        method_name,
                        exc,
                    )

                    continue

            except Exception as exc:

                self.total_dialer_failures += 1

                logger.debug(
                    "[HealthMonitor] "
                    "QbitDialer dispatch %s failed: %s",
                    method_name,
                    exc,
                )

                # A failed interface should not immediately
                # terminate the search. Another authoritative
                # compatibility interface may be available.
                continue

        # --------------------------------------------------
        # Existing Dialer queue compatibility path
        # --------------------------------------------------
        #
        # IMPORTANT:
        # We only use a queue already owned by the Dialer.
        #
        # We NEVER create:
        #
        #     Queue()
        #     QbitQueueLoop()
        #
        # here.
        # --------------------------------------------------

        queue = getattr(
            dialer,
            "qbit_queue",
            None,
        )

        if queue is not None:

            put = getattr(
                queue,
                "put",
                None,
            )

            if callable(put):

                try:

                    put(qbit)

                    self.total_dialer_dispatches += 1

                    logger.debug(
                        "[HealthMonitor] Qbit dispatched "
                        "through existing Dialer queue"
                    )

                    return True

                except Exception as exc:

                    self.total_dialer_failures += 1

                    logger.debug(
                        "[HealthMonitor] "
                        "Qbit queue dispatch failed: %s",
                        exc,
                    )

        # --------------------------------------------------
        # No authoritative dispatch path available.
        # --------------------------------------------------

        logger.debug(
            "[HealthMonitor] Qbit dispatch unavailable | "
            "QbitDialer has no supported receive interface "
            "or existing qbit_queue"
        )

        return False
    # ======================================================
    # EXPLICIT FAULT RECORDING
    # ======================================================

    def record_fault(
        self,
        module: str,
        error: Exception,
        *,
        advisory: bool = False,
        source: Optional[str] = None,
        operation: Optional[str] = None,
        track_id: Optional[str] = None,
    ):
       
        module = (
            str(module)
            if module
            else "unknown"
        )

        error_text = str(error)

        now = time.time()

        with self._lock:

            if module not in self.modules:

                self.modules[module] = {
                    "status": OK,
                    "faults": 0,
                    "advisories": 0,
                    "operational": True,
                    "locked": False,
                    "last_error": None,
                    "last_repair": None,
                    "analytics": [],
                }

            record = self.modules[module]

            if advisory:
                record["advisories"] += 1
                self.total_advisories += 1

            else:
                record["faults"] += 1
                self.total_faults += 1

            record["last_error"] = error_text

            record["analytics"].append(
                {
                    "time": now,
                    "error": error_text,
                    "advisory": bool(advisory),
                    "source": source,
                    "operation": operation,
                    "track_id": track_id,
                }
            )

            if len(
                record["analytics"]
            ) > self.ANALYTICS_LIMIT:

                record["analytics"] = (
                    record["analytics"][
                        -self.ANALYTICS_LIMIT:
                    ]
                )

            if not advisory:

                record["status"] = YELLOW

        # --------------------------------------------------
        # Build an attributed fault event.
        # --------------------------------------------------

        evidence = self.observe(
            source=(
                source
                or "HealthMonitor"
            ),
            module=module,
            operation=(
                operation
                or "fault_observation"
            ),
            track_id=track_id,
            event={
                "event_type": (
                    "HEALTH_ADVISORY"
                    if advisory
                    else "HEALTH_FAULT"
                ),
                "module": module,
                "error": error_text,
                "advisory": bool(advisory),
            },
            emit_qbit=True,
        )

        return evidence

    # ======================================================
    # PROCESS PRESSURE TRACE
    # ======================================================

    def capture_process_pressure(
        self,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        

        limit = (
            int(limit)
            if limit is not None
            else self.PROCESS_SAMPLE_LIMIT
        )

        processes = []

        try:

            for proc in psutil.process_iter(
                [
                    "pid",
                    "name",
                    "memory_percent",
                    "cpu_percent",
                ]
            ):

                try:

                    info = proc.info

                    processes.append(
                        {
                            "pid": info.get(
                                "pid"
                            ),
                            "name": info.get(
                                "name"
                            ),
                            "memory_percent": round(
                                float(
                                    info.get(
                                        "memory_percent"
                                    )
                                    or 0.0
                                ),
                                2,
                            ),
                            "cpu_percent": round(
                                float(
                                    info.get(
                                        "cpu_percent"
                                    )
                                    or 0.0
                                ),
                                2,
                            ),
                        }
                    )

                except (
                    psutil.NoSuchProcess,
                    psutil.AccessDenied,
                    psutil.ZombieProcess,
                ):
                    continue

        except Exception as exc:

            logger.debug(
                "[HealthMonitor] "
                f"Process trace failed: {exc}"
            )

            return []

        processes.sort(
            key=lambda item: (
                item["memory_percent"],
                item["cpu_percent"],
            ),
            reverse=True,
        )

        return processes[:limit]

    # ======================================================
    # TRACE PRESSURE
    # ======================================================

    def trace_pressure(
        self,
        *,
        include_processes: bool = True,
    ) -> Dict[str, Any]:
       

        evidence = self.observe(
            source="HealthMonitor",
            module="HealthMonitor",
            operation="pressure_trace",
            emit_qbit=True,
            include_processes=include_processes,
        )

        return evidence

    # ======================================================
    # RESOURCE ALERT TELEMETRY
    # ======================================================

    def _emit_observation(
        self,
        evidence: Dict[str, Any],
    ):

        state = evidence.get(
            "resource_state"
        )

        if state == RESOURCE_CLEAR:
            return

        key = (
            evidence.get("cause")
            or "resource_pressure"
        )

        now = time.time()

        last = self._last_alert.get(
            key,
            0.0,
        )

        if (
            now - last
            < self.RESOURCE_ALERT_COOLDOWN
        ):
            return

        self._last_alert[key] = now

        payload = {
            "state": state,
            "cause": evidence.get(
                "cause"
            ),
            "source": evidence.get(
                "source"
            ),
            "module": evidence.get(
                "module"
            ),
            "operation": evidence.get(
                "operation"
            ),
            "track_id": evidence.get(
                "track_id"
            ),
            "resources": evidence.get(
                "resources"
            ),
            "causal_confidence": evidence.get(
                "causal_confidence"
            ),
            "causal_basis": evidence.get(
                "causal_basis"
            ),
            "timestamp": evidence.get(
                "timestamp"
            ),
        }

        # --------------------------------------------------
        # EventBus is telemetry only.
        # --------------------------------------------------

        if self.event_bus is not None:

            publish = getattr(
                self.event_bus,
                "publish",
                None,
            )

            if callable(publish):

                try:

                    publish(
                        "HEALTH_OBSERVATION",
                        payload=payload,
                        source="HealthMonitor",
                    )

                except Exception as exc:

                    logger.debug(
                        "[HealthMonitor] "
                        f"EventBus telemetry failed: {exc}"
                    )

        logger.warning(
            "[HealthMonitor] "
            "RESOURCE OBSERVATION | "
            f"state={state} | "
            f"cause={payload['cause']} | "
            f"cpu={payload['resources']['cpu']:.1f}% | "
            f"mem={payload['resources']['memory']:.1f}% | "
            f"disk={payload['resources']['disk']:.1f}% | "
            f"source={payload['source']} | "
            f"module={payload['module']} | "
            f"operation={payload['operation']} | "
            f"track_id={payload['track_id']} | "
            f"confidence={payload['causal_confidence']}"
        )

    # ======================================================
    # DASHBOARD
    # ======================================================

    def _update_dashboard_locked(
        self,
        evidence,
    ):

        self.dashboard = {
            "version": self.VERSION,

            "state": self.state,

            "resource_state": (
                self.resource_state
            ),

            "resource_cause": (
                self.last_resource_cause
            ),

            "system": {
                "cpu": self.cpu_usage,
                "memory": self.memory_usage,
                "disk": self.disk_usage,

                "cpu_delta": (
                    self.cpu_percent_delta
                ),

                "memory_delta": (
                    self.memory_percent_delta
                ),

                "disk_delta": (
                    self.disk_percent_delta
                ),
            },

            "attribution": {
                "source": self.last_source,
                "module": self.last_module,
                "operation": self.last_operation,
                "track_id": self.last_track_id,
            },

            "causal_confidence": evidence.get(
                "causal_confidence"
            ),

            "causal_basis": evidence.get(
                "causal_basis"
            ),

            "boot_complete": (
                self.boot_complete
            ),

            "post_complete": (
                self.post_complete
            ),

            "total_observations": (
                self.total_observations
            ),

            "total_qbits": (
                self.total_qbits
            ),

            "dialer_dispatches": (
                self.total_dialer_dispatches
            ),

            "dialer_failures": (
                self.total_dialer_failures
            ),

            "timestamp": time.time(),
        }

    # ======================================================
    # LEGACY COMPATIBILITY
    # ======================================================

    def load(self):
       

        return 1.0

    # ------------------------------------------------------

    def update(
        self,
        state: str,
        **kw,
    ):
       

        with self._lock:

            self.state = str(state)
            self.last_check = time.time()

        try:

            self.track(
                "H-M",
                channel="HEALTH",
                state=state,
                **kw,
            )

        except Exception as exc:

            logger.debug(
                "[HealthMonitor] "
                f"Track update failed: {exc}"
            )

    # ------------------------------------------------------

    def _update_system_metrics(self):

        evidence = self.observe(
            source="HealthMonitor",
            module="HealthMonitor",
            operation="resource_sample",
            emit_qbit=True,
        )

        return evidence

    # ------------------------------------------------------

    def _check_resource_thresholds(self):

        evidence = self.observe(
            source="HealthMonitor",
            module="HealthMonitor",
            operation="resource_threshold_check",
            emit_qbit=True,
        )

        return evidence

    # ------------------------------------------------------

    def _monitor_loop(self):
       

        logger.debug(
            "[HealthMonitor] _monitor_loop ignored: "
            "monitor is passive"
        )

    # ------------------------------------------------------

    def _qbit_feedback_loop(self):
        

        logger.debug(
            "[HealthMonitor] "
            "_qbit_feedback_loop ignored: "
            "QbitDialer is authoritative"
        )

    # ------------------------------------------------------

    def _run_post_sequence(self):
       

        with self._lock:

            self.post_complete = True
            self.boot_complete = True

        logger.info(
            "[HealthMonitor] "
            "Passive post sequence complete"
        )

    # ------------------------------------------------------

    def _check_critical_modules(self):

        for module in (
            "BuildManager",
            "QbitDialer",
        ):

            with self._lock:

                if module not in self.modules:

                    self.modules[module] = {
                        "status": OK,
                        "faults": 0,
                        "advisories": 0,
                        "operational": True,
                        "locked": False,
                        "last_error": None,
                        "last_repair": None,
                        "analytics": [],
                    }

    # ======================================================
    # REPAIR COMPATIBILITY
    # ======================================================

    def _attempt_repair(
        self,
        module: str,
    ):
      

        logger.debug(
            "[HealthMonitor] "
            f"Repair suppressed | module={module} | "
            "authority=QbitDialer"
        )

        return False

    # ------------------------------------------------------

    def _attempt_repairs(self):
       

        return False

    # ======================================================
    # DIAGNOSTICS
    # ======================================================

    def diagnostics(self):

        with self._lock:

            uptime = (
                time.time()
                - self.started_at
            )

            return {
                "version": self.VERSION,

                "mode": "PASSIVE",

                "authority": "QbitDialer",

                "workers": 0,

                "state": self.state,

                "resource_state": (
                    self.resource_state
                ),

                "resource_cause": (
                    self.last_resource_cause
                ),

                "cpu": round(
                    self.cpu_usage,
                    2,
                ),

                "memory": round(
                    self.memory_usage,
                    2,
                ),

                "disk": round(
                    self.disk_usage,
                    2,
                ),

                "cpu_delta": round(
                    self.cpu_percent_delta,
                    2,
                ),

                "memory_delta": round(
                    self.memory_percent_delta,
                    2,
                ),

                "disk_delta": round(
                    self.disk_percent_delta,
                    2,
                ),

                "source": self.last_source,

                "module": self.last_module,

                "operation": self.last_operation,

                "track_id": self.last_track_id,

                "total_observations": (
                    self.total_observations
                ),

                "total_qbits": (
                    self.total_qbits
                ),

                "dialer_dispatches": (
                    self.total_dialer_dispatches
                ),

                "dialer_failures": (
                    self.total_dialer_failures
                ),

                "total_faults": (
                    self.total_faults
                ),

                "total_advisories": (
                    self.total_advisories
                ),

                "boot_complete": (
                    self.boot_complete
                ),

                "post_complete": (
                    self.post_complete
                ),

                "started": (
                    self._started
                ),

                "stopped": (
                    self._stopped
                ),

                "uptime": round(
                    uptime,
                    2,
                ),

                "modules": {
                    k: dict(v)
                    for k, v in self.modules.items()
                },

                "last_resource_observation": (
                    dict(
                        self.resource_history[-1]
                    )
                    if self.resource_history
                    else None
                ),

                "timestamp": time.time(),
            }

    # ======================================================
    # RESOURCE QUERY
    # ======================================================

    def get_resources(self):

        with self._lock:

            return {
                "cpu": self.cpu_usage,
                "memory": self.memory_usage,
                "disk": self.disk_usage,

                "cpu_delta": (
                    self.cpu_percent_delta
                ),

                "memory_delta": (
                    self.memory_percent_delta
                ),

                "disk_delta": (
                    self.disk_percent_delta
                ),

                "state": self.resource_state,

                "cause": (
                    self.last_resource_cause
                ),

                "source": self.last_source,

                "module": self.last_module,

                "operation": self.last_operation,

                "track_id": self.last_track_id,
            }
# ======================================================
# STABILITY QUERY
# ======================================================

    def is_stable(
        self,
    ) -> bool:

        with self._lock:

            if self._stopped:
                return False

            return (
                self.resource_state
                == RESOURCE_CLEAR
            )
    # ======================================================
    # LAST QBIT
    # ======================================================

    def get_last_qbit(self):

        with self._lock:

            if not self.qbit_history:
                return None

            return self.qbit_history[-1]

    # ======================================================
    # PRESSURE HISTORY
    # ======================================================

    def get_pressure_history(
        self,
        limit: int = 20,
    ):

        limit = max(
            1,
            int(limit),
        )

        with self._lock:

            history = list(
                self.resource_history
            )

        return history[-limit:]

    # ======================================================
    # REPRESENTATION
    # ======================================================

    def __repr__(self):

        return (
            "HealthMonitor("
            f"version={self.VERSION}, "
            "mode=PASSIVE, "
            "workers=0, "
            f"state={self.state}, "
            f"resource_state="
            f"{self.resource_state}, "
            f"memory="
            f"{self.memory_usage:.1f}%, "
            f"cpu="
            f"{self.cpu_usage:.1f}%"
            ")"
        )


# ==========================================================
# COMPATIBILITY ALIAS
# ==========================================================

Healthmonitor = HealthMonitor


# ==========================================================
# EXPORTS
# ==========================================================

__all__ = [
    "HealthMonitor",
    "Healthmonitor",
    "OK",
    "YELLOW",
    "RED",
    "LOCKED",
    "RESOURCE_CLEAR",
    "RESOURCE_PRESSURE",
    "RESOURCE_WARNING",
    "RESOURCE_CRITICAL",
]