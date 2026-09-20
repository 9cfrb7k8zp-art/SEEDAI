


# ==========================================================
# FILE: limp_mode.py
# PATH: SEED_ROOT/seed/core/limp_mode.py
#
# SYSTEM: SEED AI OS
# COMPONENT: LimpModeController
# VERSION: 8.0.0
# BUILD: PASSIVE-RESOURCE-TELEMETRY / QBIT-CONTROLLED
#
# AUTHORITY MODEL
# ----------------------------------------------------------
# LimpMode is NOT a control/governor layer.
#
# AUTHORITY:
#   Qbit / QbitDialer -> system control
#
# ROLE:
#   LimpMode -> resource telemetry + state reporting only
#
# DOES:
#   - Observe CPU/memory at a low frequency.
#   - Report resource telemetry.
#   - Maintain compatibility status fields.
#   - Accept explicit state requests from an external controller.
#   - Stop cleanly.
#
# DOES NOT:
#   - Control boot.
#   - Control shutdown.
#   - Gate workloads.
#   - Stop Qbit.
#   - Stop QbitQueueLoop.
#   - Control Heartbeat.
#   - Control DeviceManager.
#   - Control AgentManager.
#   - Control ConstraintGuardian.
#   - Reload Python modules.
#   - Scan skills/filesystems automatically.
#   - Start recovery workers.
#   - Start maintenance workers.
#   - Modify BuildManager state.
#   - Issue Qbit commands.
#   - Override Qbit/QbitDialer decisions.
#
# IMPORTANT:
#   This module is intentionally subordinate to Qbit/QbitDialer.
#   Resource pressure is DATA, not AUTHORITY.
# ==========================================================

from __future__ import annotations

import logging
import threading
import time
import traceback
import uuid
from typing import Optional, Callable, Dict, Any

try:
    import psutil
except Exception:
    psutil = None

try:
    from seed.core.channel_id import generate_track_id
except Exception:
    generate_track_id = None

try:
    from seed.core.event_bus import TrackedData
except Exception:
    TrackedData = None

try:
    from seed.core.trackcontext import TrackContext
except Exception:
    class TrackContext:
        @staticmethod
        def get():
            return None

logger = logging.getLogger("LimpMode")

limp_controller = None


class LimpModeController:
   
    VERSION = "8.0.0"

    # Low-frequency observation.  This keeps boot overhead negligible.
    MONITOR_INTERVAL = 5.0

    # Compatibility constants retained for callers that reference them.
    RECOVERY_POLL_INTERVAL = 0.5
    THREAD_JOIN_TIMEOUT = 3.0
    RESOURCE_CLEAR_MARGIN = 5.0

    IDLE_NORMAL_INTERVAL = 60.0
    IDLE_PRESSURE_INTERVAL = 60.0
    IDLE_WARNING_INTERVAL = 60.0
    IDLE_BLOCK_INTERVAL = 60.0

    def __init__(
        self,
        recovery_interval=10,
        cpu_limit=50,
        mem_limit=50,
        event_bus: Optional[Any] = None,
        qbit_dialer=None,
        build_manager=None,
        skills_dir=r"C:\SEED_ROOT\seed\skills",
        constraint_guardian=None,
        auto_start=False,
    ):
        global limp_controller
        limp_controller = self

        # Legacy compatibility: LimpModeController(15, event_bus)
        if event_bus is None and cpu_limit is not None and not isinstance(
            cpu_limit, (int, float)
        ):
            event_bus = cpu_limit
            cpu_limit = 50

        self.event_bus = event_bus
        self.qbit_dialer = qbit_dialer
        self.build_manager = build_manager
        self.skills_dir = skills_dir

        # Retained for API compatibility ONLY.
        # This object is never queried for authority.
        self.constraint_guardian = constraint_guardian
        self.constraintGuardian = constraint_guardian

        self.recovery_interval = max(float(recovery_interval), 1.0)
        self.cpu_limit = float(cpu_limit)
        self.mem_limit = float(mem_limit)

        self.speed = 1.0

        self.active = False
        self.reason = ""
        self.timestamp = None

        self._running = False
        self._shutdown_requested = False
        self.shutdown_flag = threading.Event()
        self._shutdown_event = self.shutdown_flag

        self._lock = threading.RLock()
        self._monitor_thread = None
        self._monitor_started = False

        self._last_cpu = 0.0
        self._last_memory = 0.0
        self._resource_state = "clear"
        self._last_resource_transition = 0.0

        self._error_log: list[str] = []
        self._max_error_log = 50
        self._last_event_time: Dict[str, float] = {}
        self._event_throttle = 5.0

        # Compatibility only. These callbacks are never executed
        # autonomously by this module.
        self._overrides: Dict[str, Optional[Callable]] = {}

        self.loop = None
        self.boot_complete = False
        self._activation_requested = False

        if auto_start:
            self.start()

    # ======================================================
    # LIFECYCLE
    # ======================================================

    def start(self):
  
        with self._lock:
            if self._shutdown_requested:
                return False
            self._activation_requested = True
            if self._running:
                return True

        if not self._system_boot_complete():
            self._log_trace("[LimpMode] START DEFERRED | waiting for SEED BOOT COMPLETE")
            return False

        return self._activate_runtime()

    def _system_boot_complete(self):
        try:
            from seed.core.track_context import TrackContext
            getter = getattr(TrackContext, "system_state", None)
            if callable(getter):
                state = getter() or {}
                if isinstance(state, dict):
                    if bool(state.get("shutdown_requested", False)):
                        return False
                    return bool(state.get("boot_complete", False))
        except Exception:
            pass
        return bool(self.boot_complete) and not bool(self._shutdown_requested)

    def _activate_runtime(self):
        with self._lock:
            if self._shutdown_requested or not self._system_boot_complete():
                return False
            if self._running:
                return True
            self._running = True
            self._shutdown_requested = False
            self.shutdown_flag.clear()

        self._log_trace(
            "[LimpMode] Passive telemetry online | "
            f"version={self.VERSION} | authority=QBIT"
        )
        self._start_monitor()
        self._publish_event(
            "LIMP_CONTROLLER_STARTED",
            message="Passive resource telemetry online",
        )
        return True

    def set_boot_complete(self, value=True):

        with self._lock:
            self.boot_complete = bool(value)
        if self.boot_complete and self._activation_requested and not self._shutdown_requested:
            return self._activate_runtime()
        if not self.boot_complete:
            with self._lock:
                self._running = False
                self.shutdown_flag.set()
        return self.boot_complete

    def is_booting(self):
        with self._lock:
            return not self.boot_complete

    def request_shutdown(self):

        return self.shutdown()

    def stop(self):
        return self.shutdown()

    def shutdown(self):

        with self._lock:
            if not self._running and self.shutdown_flag.is_set():
                return True

            self._shutdown_requested = True
            self._activation_requested = False
            self._running = False
            self.shutdown_flag.set()
            self.active = False

        thread = self._monitor_thread
        if (
            thread is not None
            and thread.is_alive()
            and thread is not threading.current_thread()
        ):
            thread.join(timeout=self.THREAD_JOIN_TIMEOUT)

        self._publish_event(
            "LIMP_CONTROLLER_STOPPED",
            message="Passive resource telemetry offline",
        )
        self._log_trace("[LimpMode] Passive telemetry offline")
        return True

    # ======================================================
    # EXPLICIT STATE REQUEST
    # ======================================================

    def enter(self, context=None, msg=None, module=None):

        context = context or "EXTERNAL"
        msg = msg or "Explicit limp-state request"
        module = module or "QBIT"

        with self._lock:
            if self._shutdown_requested:
                return False

            self.active = True
            self.reason = f"[{context}] {msg}"
            self.timestamp = time.time()

        track_id = self._generate_track_id("LIMP_REQUEST", module)

        self._log_trace(
            "Explicit limp-state recorded | "
            f"source={module} | TrackID={track_id}"
        )

        self._publish_event(
            "LIMP_REQUEST_RECORDED",
            module=module,
            message=self.reason,
            track_id=track_id,
        )

        # Feedback only. No command is sent to Qbit.
        self._qbit_feedback(
            {
                "track_id": track_id,
                "resource_state": self._resource_state,
                "cpu": self._last_cpu,
                "memory": self._last_memory,
                "limp_requested": True,
                "source": module,
                "telemetry_only": True,
            }
        )
        return True

    def clear(self, source="QBIT"):

        with self._lock:
            self.active = False
            self.reason = ""
            self.timestamp = None

        track_id = self._generate_track_id("LIMP_CLEAR", source)
        self._publish_event(
            "LIMP_STATE_CLEARED",
            module=source,
            track_id=track_id,
        )
        return True

    @staticmethod
    def safe_limp_enter(reason, details=None):
        global limp_controller

        controller = limp_controller
        if controller is None:
            return False

        return controller.enter(
            context="EXTERNAL",
            msg=f"{reason} | {details}",
            module="QBIT",
        )

    # ======================================================
    # OVERRIDE COMPATIBILITY
    # ======================================================

    def register_override(self, module_name: str, recovery_callback: Callable):

        with self._lock:
            self._overrides[module_name] = recovery_callback

        track_id = self._generate_track_id(
            "OVERRIDE_REGISTERED",
            module_name,
        )
        self._publish_event(
            "OVERRIDE_REGISTERED",
            module=module_name,
            track_id=track_id,
            message="Callback registered; execution authority remains external",
        )
        return track_id

    # ======================================================
    # MONITOR
    # ======================================================

    def _start_monitor(self):
        with self._lock:
            if self._monitor_thread is not None:
                if self._monitor_thread.is_alive():
                    return False

            if self.shutdown_flag.is_set():
                return False

            self._monitor_started = True
            self._monitor_thread = threading.Thread(
                target=self._monitor_loop,
                name="SEED-LimpMode-Telemetry",
                daemon=True,
            )
            self._monitor_thread.start()

        return True

    def _monitor_loop(self):
        self._log_trace("[LimpMode] Passive resource telemetry started")

        try:
            while self._running and not self.shutdown_flag.is_set():
                if not self._system_boot_complete():
                    self.shutdown_flag.wait(self.MONITOR_INTERVAL)
                    continue
                try:
                    cpu = self._get_cpu_usage()
                    memory = self._get_memory_usage()

                    with self._lock:
                        self._last_cpu = cpu
                        self._last_memory = memory

                    state = self._calculate_resource_state(cpu, memory)
                    self._record_resource_state(state, cpu, memory)

                except Exception as exc:
                    self._log_trace(
                        f"Telemetry cycle error: {exc}"
                    )

                if self.shutdown_flag.wait(self.MONITOR_INTERVAL):
                    break

        except Exception as exc:
            self._log_trace(
                f"Fatal telemetry loop error: {exc}"
            )

        finally:
            with self._lock:
                self._monitor_started = False

    def _get_cpu_usage(self):
        if psutil is None:
            return 0.0
        try:
            return float(psutil.cpu_percent(interval=None))
        except Exception:
            return 0.0

    def _get_memory_usage(self):
        if psutil is None:
            return 0.0
        try:
            return float(psutil.virtual_memory().percent)
        except Exception:
            return 0.0

    # ======================================================
    # RESOURCE CLASSIFICATION
    # ======================================================

    def _calculate_resource_state(self, cpu, memory):

        highest = max(float(cpu), float(memory))

        if highest >= max(self.cpu_limit + 30.0, self.mem_limit + 30.0):
            return "block"

        if highest >= max(self.cpu_limit + 15.0, self.mem_limit + 15.0):
            return "warning"

        if highest >= max(self.cpu_limit, self.mem_limit):
            return "pressure"

        clear_cpu = self.cpu_limit - self.RESOURCE_CLEAR_MARGIN
        clear_mem = self.mem_limit - self.RESOURCE_CLEAR_MARGIN

        if cpu <= clear_cpu and memory <= clear_mem:
            return "clear"

        return self._resource_state

    def _record_resource_state(self, state, cpu, memory):
        with self._lock:
            previous = self._resource_state

            if state == previous:
                return False

            self._resource_state = state
            self._last_resource_transition = time.time()

        self._log_trace(
            "[LimpMode] Resource telemetry: "
            f"{previous} -> {state} | "
            f"CPU={cpu:.1f}% | MEM={memory:.1f}% | "
            "authority=QBIT"
        )

        self._publish_event(
            "LIMP_RESOURCE_STATE",
            message=f"{previous} -> {state}",
        )

        # CRITICAL:
        # There is NO call to enter().
        # There is NO recovery.
        # There is NO reload.
        # There is NO workload control.
        return True

    # Compatibility name used by older code.
    def _apply_resource_state(self, state, cpu, memory):
        return self._record_resource_state(state, cpu, memory)

    def _monitor_interval(self):
        return self.MONITOR_INTERVAL

    # ======================================================
    # CONSTRAINT GUARDIAN COMPATIBILITY
    # ======================================================

    def _get_constraint_guardian(self):
        # Retained only so legacy callers do not crash.
        # LimpMode intentionally does not use it.
        return self.constraint_guardian

    def _get_governor_state(self):
        # This is a local telemetry value, not a governor command.
        with self._lock:
            return self._resource_state or "clear"

    # ======================================================
    # DISABLED MAINTENANCE / RECOVERY COMPATIBILITY
    # ======================================================

    def _start_recovery_thread(self):
        # Intentionally disabled in v8.
        return False

    def _recovery_loop(self):
        return False

    def _recover(self):
        # Intentionally disabled in v8.
        self._log_trace(
            "[LimpMode] Recovery request ignored: "
            "LimpMode is passive; Qbit owns recovery."
        )
        return False

    def _reload_critical_modules(self, parent_track_id=None):
        # Intentionally disabled.
        self._log_trace(
            "[LimpMode] Module reload ignored: "
            "module lifecycle belongs to Qbit/system boot."
        )
        return False

    def _start_idle_read(self):
        # Intentionally disabled.
        return False

    def _idle_read_loop(self):
        return False

    def _maintenance_scan(self):
        # Intentionally disabled.
        return False

    def _stop_idle_read(self):
        return True

    # ======================================================
    # QBIT FEEDBACK
    # ======================================================

    def _qbit_feedback(self, payload: Dict[str, Any]):

        dialer = self.qbit_dialer
        if dialer is None:
            return False

        try:
            push_data = getattr(dialer, "push_data", None)
            if callable(push_data):
                push_data(payload)
                return True
        except Exception as exc:
            self._log_trace(f"Qbit telemetry feedback failed: {exc}")

        return False

    # ======================================================
    # BUILD MANAGER COMPATIBILITY
    # ======================================================

    def _set_build_manager_limp(self, enabled: bool):
        # Deliberately disabled. LimpMode no longer controls BuildManager.
        return False

    # ======================================================
    # TRACK ID
    # ======================================================

    def _generate_track_id(self, prefix="LIMP", parent_context=None):
        try:
            if generate_track_id:
                tid = generate_track_id(skill_name=prefix)
            else:
                tid = f"{prefix}-{str(uuid.uuid4())[:8]}"
        except Exception:
            tid = f"{prefix}-{str(uuid.uuid4())[:8]}"

        if parent_context:
            tid = f"{tid}_PARENT-{parent_context}"

        return tid

    # ======================================================
    # EVENT BUS
    # ======================================================

    def _publish_event(
        self,
        event_type,
        module=None,
        message=None,
        track_id=None,
    ):
        if self.event_bus is None or TrackedData is None:
            return False

        try:
            now = time.monotonic()
            last = self._last_event_time.get(event_type, 0.0)

            if (
                event_type == "LIMP_RESOURCE_STATE"
                and now - last < self._event_throttle
            ):
                return False

            self._last_event_time[event_type] = now

            payload = TrackedData(
                track_id=(
                    track_id
                    or self._generate_track_id("LIMP_EVT")
                ),
                parent_id=TrackContext.get(),
                channel=module or "LIMP_TELEMETRY",
                payload={
                    "message": message,
                    "speed": self.speed,
                    "active": self.active,
                    "resource_state": self._resource_state,
                    "cpu": self._last_cpu,
                    "memory": self._last_memory,
                    "timestamp": time.time(),
                    "telemetry_only": True,
                    "authority": "QBIT",
                },
                priority="NORMAL",
            )

            publish = getattr(self.event_bus, "publish", None)
            if callable(publish):
                publish(event_type, payload)
                return True

            emit = getattr(self.event_bus, "emit", None)
            if callable(emit):
                emit(event_type, payload)
                return True

        except Exception as exc:
            self._log_trace(
                f"Failed to publish event '{event_type}': {exc}"
            )

        return False

    # ======================================================
    # STATUS
    # ======================================================

    def status(self):
        with self._lock:
            return {
                "version": self.VERSION,
                "running": self._running,
                "activation_requested": self._activation_requested,
                "shutdown_requested": self._shutdown_requested,
                "active": self.active,
                "reason": self.reason,
                "timestamp": self.timestamp,
                "speed": self.speed,
                "cpu": self._last_cpu,
                "memory": self._last_memory,
                "resource_state": self._resource_state,
                "monitor_started": self._monitor_started,

                # Explicit authority declaration.
                "authority": "QBIT",
                "control_layer": False,
                "telemetry_only": True,
                "boot_interference": False,
                "automatic_recovery": False,
                "automatic_module_reload": False,
                "automatic_maintenance": False,
                "constraint_guardian_authority": False,

                # Compatibility fields.
                "recovery_started": False,
                "idle_read_started": False,
                "overrides": list(self._overrides.keys()),
                "last_errors": list(self._error_log),
            }

    # ======================================================
    # LOGGING
    # ======================================================

    def _log_trace(self, message: str):
        ts = time.strftime(
            "%Y-%m-%d %H:%M:%S",
            time.localtime(),
        )
        full_message = f"[{ts}] {message}"

        try:
            logger.info(full_message)
        except Exception:
            pass

        try:
            print(full_message)
        except Exception:
            pass

        try:
            tb = traceback.format_exc()
            if tb and "NoneType: None" not in tb:
                with self._lock:
                    self._error_log.append(tb)
                    if len(self._error_log) > self._max_error_log:
                        del self._error_log[:-self._max_error_log]
        except Exception:
            pass


def get_limp_controller():
    return limp_controller


# ==========================================================
# END OF FILE
# VERSION: 8.0.0
# BUILD: PASSIVE-RESOURCE-TELEMETRY / QBIT-CONTROLLED
# ==========================================================
