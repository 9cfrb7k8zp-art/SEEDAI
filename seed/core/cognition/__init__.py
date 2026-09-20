# ==========================================================
# FILE: __init__.py
# PATH: C:\SEED_ROOT\seed\core\cognition\__init__.py
#
# SYSTEM: SEED AI OS
# COMPONENT: Cognition Node
# VERSION: 5.0.0
#
# BUILD:
#   PASSIVE / BOOT-GATED / LIFECYCLE-SAFE /
#   SINGLE-OWNER / DUPLICATE-START-PROTECTED /
#   CORE-INTEGRATION / QBIT-AWARE /
#   COMMAND-AWARE / RELAY-AWARE /
#   BIOS-AWARE / GROWTH-READY
#
# UPDATED: 2026-08-26
#
# PURPOSE:
# ----------------------------------------------------------
# Public neural-node entry point for the cognition subsystem.
#
# Cognition is the integration point between SEED's cognitive
# governor and the already-authorized core infrastructure.
#
# Cognition MAY KNOW ABOUT:
#
#   - QueueLoop
#   - MemoryGraph
#   - QbitDialer
#   - Command Relay
#   - Relay subsystem
#   - BIOS tools
#   - File/Growth tools
#   - Module loader
#   - Tool registry
#   - Growth/development manager
#
# Cognition DOES NOT OWN THEIR LIFECYCLES.
#
# Those systems are supplied by SEED's authoritative boot/runtime
# layer.
#
# ==========================================================
#
# CORE ARCHITECTURE
#
#                    SEED BOOT
#                        |
#                        v
#                 CORE RUNTIME
#                        |
#          +-------------+-------------+
#          |             |             |
#          v             v             v
#       QbitDialer    Heartbeat      EventBus
#          |
#          v
#      COMMAND PATH
#          |
#          v
#       RELAY LAYER
#          |
#          v
#       BIOS / TOOLS
#          |
#          +----------------------+
#          |                      |
#          v                      v
#    FILE/GROWTH ACCESS       MODULE LOADER
#          |                      |
#          +----------+-----------+
#                     |
#                     v
#               COGNITION NODE
#                     |
#                     v
#                  GOVERNOR
#
# Cognition can therefore operate with awareness of the systems
# that permit SEED to reason, act, inspect, develop, and grow.
#
# ==========================================================
#
# HARD LIFECYCLE RULE
#
# IMPORT COGNITION
#        |
#        v
#   PASSIVE / READY
#        |
#        | explicit SEED lifecycle authorization
#        v
#     STARTING
#        |
#        v
#     RUNNING
#
# Cognition NEVER starts itself merely because this package
# is imported.
#
# ==========================================================
#
# HARD OWNERSHIP RULE
#
# Cognition does NOT own:
#
#   - SEED boot
#   - QbitDialer lifecycle
#   - QueueLoop lifecycle
#   - EventBus lifecycle
#   - Heartbeat lifecycle
#   - KernelBus lifecycle
#   - Relay lifecycle
#   - BIOS lifecycle
#   - filesystem lifecycle
#   - module-loader lifecycle
#   - system shutdown
#
# Cognition only manages:
#
#   - its own lifecycle
#   - its own governor attachment
#   - its dependency references
#   - its readiness state
#   - its cognitive integration contract
#
# ==========================================================
#
# IMPORTANT
#
# This module must NEVER:
#
#   - create a thread at import
#   - create an asyncio task at import
#   - start CognitiveClock
#   - start GoalEngine
#   - start AdaptivePriorityEngine
#   - start QueueLoop
#   - start EventBus
#   - start QbitDialer
#   - start Heartbeat
#   - start KernelBus
#   - start Relay
#   - start BIOS tools
#   - start filesystem workers
#   - start module loaders
#   - start a governor implicitly
#
# ==========================================================

from __future__ import annotations

import logging
import threading
import time

from enum import Enum
from typing import Any, Dict, Optional


# ==========================================================
# LOGGING
# ==========================================================

logger = logging.getLogger("CognitionNode")

if not logger.handlers:
    logger.addHandler(logging.NullHandler())


# ==========================================================
# NODE STATUS
# ==========================================================

class CognitionStatus(str, Enum):

    IMPORTED = "imported"
    READY = "ready"
    STARTING = "starting"
    RUNNING = "running"
    DEGRADED = "degraded"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


# ==========================================================
# NODE MODES
# ==========================================================

class CognitionMode(str, Enum):

    PASSIVE = "passive"
    ACTIVE = "active"
    DEGRADED = "degraded"
    STOPPED = "stopped"
    FAILED = "failed"


# ==========================================================
# LAZY GOVERNOR IMPORT
# ==========================================================

def _load_governor():

    from .governor import start_governor

    return start_governor


# ==========================================================
# COGNITION NODE
# ==========================================================

class CognitionNode:

    VERSION = "5.0.0"
    NAME = "CognitionNode"

    def __init__(
        self,
        queue_loop=None,
        memory_graph=None,
        qbit_dialer=None,
        command_relay=None,
        relay=None,
        bios=None,
        growth_manager=None,
        file_tool=None,
        module_loader=None,
        tool_registry=None,
        permission_manager=None,
    ) -> None:

        # --------------------------------------------------
        # CORE DEPENDENCIES
        # --------------------------------------------------

        self.queue_loop = queue_loop
        self.memory_graph = memory_graph

        # --------------------------------------------------
        # QBIT / COMMAND / RELAY
        #
        # These are references only.
        #
        # Cognition does not construct or start them.
        # --------------------------------------------------

        self.qbit_dialer = qbit_dialer
        self.command_relay = command_relay
        self.relay = relay

        # --------------------------------------------------
        # BIOS / GROWTH INFRASTRUCTURE
        #
        # These references represent capabilities supplied by
        # the authoritative SEED runtime.
        #
        # They may provide controlled read/write access,
        # module loading, tool registration, and development
        # capabilities.
        # --------------------------------------------------

        self.bios = bios
        self.growth_manager = growth_manager
        self.file_tool = file_tool
        self.module_loader = module_loader
        self.tool_registry = tool_registry
        self.permission_manager = permission_manager

        # --------------------------------------------------
        # Local lifecycle synchronization.
        #
        # This protects state only.
        # It does not create execution.
        # --------------------------------------------------

        self._lock = threading.RLock()

        # --------------------------------------------------
        # Lifecycle
        # --------------------------------------------------

        self._status = CognitionStatus.READY
        self._mode = CognitionMode.PASSIVE

        self._governor = None

        # --------------------------------------------------
        # Boot gate.
        #
        # False means cognition exists but cannot activate.
        # --------------------------------------------------

        self._boot_ready = False

        # --------------------------------------------------
        # Explicit lifecycle ownership.
        # --------------------------------------------------

        self._start_requested = False
        self._stop_requested = False

        # --------------------------------------------------
        # Timing
        # --------------------------------------------------

        self._created_at = time.time()
        self._started_at: Optional[float] = None
        self._stopped_at: Optional[float] = None

        # --------------------------------------------------
        # Counters
        # --------------------------------------------------

        self._start_count = 0
        self._stop_count = 0

        # --------------------------------------------------
        # Diagnostics
        # --------------------------------------------------

        self._last_error: Optional[str] = None
        self._last_reason = "initialized"

        logger.info(
            "[CognitionNode] READY | "
            "mode=passive | "
            "boot_ready=False | "
            "governor=not_started | "
            "qbit=not_attached | "
            "relay=not_attached | "
            "bios=not_attached"
        )

    # ======================================================
    # STATUS
    # ======================================================

    @property
    def status(self) -> CognitionStatus:

        with self._lock:
            return self._status

    # ------------------------------------------------------

    @property
    def mode(self) -> CognitionMode:

        with self._lock:
            return self._mode

    # ------------------------------------------------------

    @property
    def running(self) -> bool:

        with self._lock:
            return (
                self._status
                == CognitionStatus.RUNNING
            )

    # ------------------------------------------------------

    @property
    def governor(self):

        with self._lock:
            return self._governor

    # ------------------------------------------------------

    @property
    def boot_ready(self) -> bool:

        with self._lock:
            return self._boot_ready

    # ======================================================
    # CORE ACCESSORS
    # ======================================================

    @property
    def qbit(self):

        with self._lock:
            return self.qbit_dialer

    # ------------------------------------------------------

    @property
    def command_path(self):

        with self._lock:
            return self.command_relay

    # ------------------------------------------------------

    @property
    def relay_layer(self):

        with self._lock:
            return self.relay

    # ------------------------------------------------------

    @property
    def bios_tools(self):

        with self._lock:
            return self.bios

    # ------------------------------------------------------

    @property
    def growth(self):

        with self._lock:
            return self.growth_manager

    # ======================================================
    # DEPENDENCY MANAGEMENT
    # ======================================================

    def attach_dependencies(
        self,
        queue_loop=None,
        memory_graph=None,
        qbit_dialer=None,
        command_relay=None,
        relay=None,
        bios=None,
        growth_manager=None,
        file_tool=None,
        module_loader=None,
        tool_registry=None,
        permission_manager=None,
    ) -> bool:

        with self._lock:

            if self._status in (
                CognitionStatus.RUNNING,
                CognitionStatus.STARTING,
            ):
                logger.warning(
                    "[CognitionNode] "
                    "Dependency attachment rejected while active"
                )
                return False

            # --------------------------------------------------
            # Core
            # --------------------------------------------------

            if queue_loop is not None:
                self.queue_loop = queue_loop

            if memory_graph is not None:
                self.memory_graph = memory_graph

            # --------------------------------------------------
            # Qbit / command / relay
            # --------------------------------------------------

            if qbit_dialer is not None:
                self.qbit_dialer = qbit_dialer

            if command_relay is not None:
                self.command_relay = command_relay

            if relay is not None:
                self.relay = relay

            # --------------------------------------------------
            # BIOS / growth
            # --------------------------------------------------

            if bios is not None:
                self.bios = bios

            if growth_manager is not None:
                self.growth_manager = growth_manager

            if file_tool is not None:
                self.file_tool = file_tool

            if module_loader is not None:
                self.module_loader = module_loader

            if tool_registry is not None:
                self.tool_registry = tool_registry

            if permission_manager is not None:
                self.permission_manager = permission_manager

            # --------------------------------------------------
            # Recover from dependency degradation.
            # --------------------------------------------------

            if self._status == CognitionStatus.DEGRADED:

                self._status = CognitionStatus.READY
                self._mode = CognitionMode.PASSIVE
                self._last_reason = (
                    "dependencies_attached"
                )

            logger.info(
                "[CognitionNode] "
                "DEPENDENCIES ATTACHED | "
                f"queue={self.queue_loop is not None} | "
                f"memory={self.memory_graph is not None} | "
                f"qbit={self.qbit_dialer is not None} | "
                f"command={self.command_relay is not None} | "
                f"relay={self.relay is not None} | "
                f"bios={self.bios is not None} | "
                f"growth={self.growth_manager is not None}"
            )

            return True

    # ======================================================
    # DEPENDENCY READINESS
    # ======================================================

    def dependencies_ready(self) -> bool:

        with self._lock:

            return (
                self.queue_loop is not None
                and not self._stop_requested
            )

    # ------------------------------------------------------

    def core_dependencies_ready(self) -> bool:

        with self._lock:

            return (
                self.queue_loop is not None
                and self.qbit_dialer is not None
                and not self._stop_requested
            )

    # ------------------------------------------------------

    def growth_dependencies_ready(self) -> bool:

        with self._lock:

            return (
                self.bios is not None
                or self.file_tool is not None
                or self.growth_manager is not None
                or self.module_loader is not None
            )

    # ------------------------------------------------------

    def command_dependencies_ready(self) -> bool:

        with self._lock:

            return (
                self.qbit_dialer is not None
                or self.command_relay is not None
                or self.relay is not None
            )

    # ======================================================
    # BOOT GATE
    # ======================================================

    def set_boot_ready(
        self,
        ready: bool = True,
        reason: str = "boot_gate",
    ) -> bool:

        with self._lock:

            if self._status in (
                CognitionStatus.RUNNING,
                CognitionStatus.STARTING,
            ):

                logger.warning(
                    "[CognitionNode] "
                    "boot gate cannot be changed while active"
                )

                return False

            self._boot_ready = bool(ready)

            if ready:

                self._last_reason = (
                    "boot_ready:" + str(reason)
                )

                logger.info(
                    "[CognitionNode] "
                    "BOOT GATE OPEN | "
                    f"reason={reason}"
                )

            else:

                self._last_reason = (
                    "boot_not_ready:" + str(reason)
                )

                logger.info(
                    "[CognitionNode] "
                    "BOOT GATE CLOSED | "
                    f"reason={reason}"
                )

            return True

    # ------------------------------------------------------

    def boot_gate_open(self) -> bool:

        with self._lock:
            return self._boot_ready

    # ======================================================
    # START
    # ======================================================

    def start(
        self,
        *,
        require_boot_ready: bool = True,
    ):

        with self._lock:

            # ------------------------------------------------
            # Already running.
            # ------------------------------------------------

            if (
                self._status
                == CognitionStatus.RUNNING
            ):

                logger.debug(
                    "[CognitionNode] "
                    "start ignored | already running"
                )

                return self._governor

            # ------------------------------------------------
            # Startup already in progress.
            # ------------------------------------------------

            if (
                self._status
                == CognitionStatus.STARTING
            ):

                logger.debug(
                    "[CognitionNode] "
                    "start ignored | already starting"
                )

                return self._governor

            # ------------------------------------------------
            # Hard stop gate.
            # ------------------------------------------------

            if self._stop_requested:

                self._status = CognitionStatus.STOPPED
                self._mode = CognitionMode.STOPPED

                self._last_reason = (
                    "start_rejected_after_stop"
                )

                logger.warning(
                    "[CognitionNode] "
                    "START REJECTED | stop requested"
                )

                return None

            # ------------------------------------------------
            # BOOT GATE
            # ------------------------------------------------

            if (
                require_boot_ready
                and not self._boot_ready
            ):

                self._status = CognitionStatus.READY
                self._mode = CognitionMode.PASSIVE

                self._last_reason = (
                    "boot_gate_closed"
                )

                logger.info(
                    "[CognitionNode] "
                    "START DEFERRED | "
                    "boot gate closed"
                )

                return None

            # ------------------------------------------------
            # Required runtime dependency.
            # ------------------------------------------------

            if self.queue_loop is None:

                self._status = (
                    CognitionStatus.DEGRADED
                )

                self._mode = (
                    CognitionMode.DEGRADED
                )

                self._last_reason = (
                    "queue_loop_unavailable"
                )

                logger.warning(
                    "[CognitionNode] "
                    "DEGRADED | "
                    "queue_loop unavailable"
                )

                return None

            # ------------------------------------------------
            # Mark startup BEFORE governor invocation.
            #
            # This prevents duplicate callers from entering
            # the startup path simultaneously.
            # ------------------------------------------------

            self._status = (
                CognitionStatus.STARTING
            )

            self._mode = CognitionMode.PASSIVE

            self._start_requested = True
            self._last_error = None
            self._last_reason = "explicit_start"

            logger.info(
                "[CognitionNode] "
                "STARTING | "
                "governor initialization | "
                f"qbit={self.qbit_dialer is not None} | "
                f"command={self.command_relay is not None} | "
                f"relay={self.relay is not None} | "
                f"bios={self.bios is not None} | "
                f"growth={self.growth_dependencies_ready()}"
            )

        # ==================================================
        # DO NOT HOLD NODE LOCK WHILE CALLING GOVERNOR.
        # ==================================================

        try:

            start_governor = _load_governor()

            # ------------------------------------------------
            # Preserve the historical governor contract.
            #
            # Existing governor implementations receive the
            # original queue_loop and memory_graph arguments.
            #
            # Additional dependencies remain available through
            # this node and can be attached by the governor or
            # runtime without breaking older constructors.
            # ------------------------------------------------

            governor = start_governor(
                self.queue_loop,
                self.memory_graph,
            )

            with self._lock:

                # ------------------------------------------------
                # Governor returned nothing.
                # ------------------------------------------------

                if governor is None:

                    self._governor = None

                    self._status = (
                        CognitionStatus.DEGRADED
                    )

                    self._mode = (
                        CognitionMode.DEGRADED
                    )

                    self._last_reason = (
                        "governor_returned_none"
                    )

                    self._start_requested = False

                    logger.warning(
                        "[CognitionNode] "
                        "DEGRADED | "
                        "governor returned None"
                    )

                    return None

                # ------------------------------------------------
                # Successful startup.
                # ------------------------------------------------

                self._governor = governor

                # ------------------------------------------------
                # Give the governor access to the authoritative
                # CognitionNode without forcing a constructor
                # signature change.
                #
                # Only attach when the governor explicitly exposes
                # a compatible attribute.
                # ------------------------------------------------

                try:

                    if hasattr(
                        governor,
                        "cognition_node",
                    ):

                        governor.cognition_node = self

                except Exception:

                    logger.debug(
                        "[CognitionNode] "
                        "governor cognition_node attachment skipped",
                        exc_info=True,
                    )

                self._started_at = time.time()
                self._stopped_at = None

                self._start_count += 1

                self._start_requested = False
                self._stop_requested = False

                self._status = (
                    CognitionStatus.RUNNING
                )

                self._mode = (
                    CognitionMode.ACTIVE
                )

                self._last_reason = "started"

                logger.info(
                    "[CognitionNode] RUNNING | "
                    f"starts={self._start_count} | "
                    f"qbit={self.qbit_dialer is not None} | "
                    f"command={self.command_relay is not None} | "
                    f"relay={self.relay is not None} | "
                    f"bios={self.bios is not None} | "
                    f"growth={self.growth_dependencies_ready()}"
                )

                return governor

        except Exception as exc:

            with self._lock:

                self._governor = None

                self._status = (
                    CognitionStatus.FAILED
                )

                self._mode = (
                    CognitionMode.FAILED
                )

                self._start_requested = False

                self._last_error = (
                    f"{type(exc).__name__}: {exc}"
                )

                self._last_reason = (
                    "startup_failed"
                )

            logger.exception(
                "[CognitionNode] "
                "START FAILED | "
                f"{type(exc).__name__}: {exc}"
            )

            return None

    # ======================================================
    # STOP
    # ======================================================

    def stop(
        self,
        reason: str = "shutdown_requested",
    ) -> bool:

        reason = str(reason)

        with self._lock:

            # ------------------------------------------------
            # Already stopped / never started.
            # ------------------------------------------------

            if self._status in (
                CognitionStatus.IMPORTED,
                CognitionStatus.READY,
                CognitionStatus.STOPPED,
            ):

                self._stop_requested = True
                self._start_requested = False

                self._status = (
                    CognitionStatus.STOPPED
                )

                self._mode = (
                    CognitionMode.STOPPED
                )

                self._last_reason = reason
                self._stopped_at = time.time()

                return True

            # ------------------------------------------------
            # Already stopping.
            # ------------------------------------------------

            if (
                self._status
                == CognitionStatus.STOPPING
            ):

                return False

            self._status = (
                CognitionStatus.STOPPING
            )

            self._mode = (
                CognitionMode.PASSIVE
            )

            self._stop_requested = True
            self._start_requested = False

            self._last_reason = reason

            governor = self._governor

        logger.info(
            "[CognitionNode] STOPPING | "
            f"reason={reason}"
        )

        try:

            if governor is not None:

                stopper = getattr(
                    governor,
                    "stop",
                    None,
                )

                if not callable(stopper):

                    stopper = getattr(
                        governor,
                        "shutdown",
                        None,
                    )

                if callable(stopper):

                    try:

                        result = stopper(
                            reason=reason
                        )

                    except TypeError:

                        result = stopper()

                    if result is not None:

                        logger.debug(
                            "[CognitionNode] "
                            "governor stop invoked"
                        )

            with self._lock:

                self._governor = None

                self._status = (
                    CognitionStatus.STOPPED
                )

                self._mode = (
                    CognitionMode.STOPPED
                )

                self._stopped_at = time.time()

                self._stop_count += 1

                self._last_reason = reason

            logger.info(
                "[CognitionNode] STOPPED | "
                f"stops={self._stop_count}"
            )

            return True

        except Exception as exc:

            with self._lock:

                self._status = (
                    CognitionStatus.FAILED
                )

                self._mode = (
                    CognitionMode.FAILED
                )

                self._last_error = (
                    f"{type(exc).__name__}: {exc}"
                )

                self._last_reason = (
                    "stop_failed"
                )

            logger.exception(
                "[CognitionNode] "
                "STOP FAILED | "
                f"{type(exc).__name__}: {exc}"
            )

            return False

    # ======================================================
    # RESET
    # ======================================================

    def reset(
        self,
        *,
        reopen_boot_gate: bool = False,
    ) -> bool:

        with self._lock:

            if self._status in (
                CognitionStatus.RUNNING,
                CognitionStatus.STARTING,
                CognitionStatus.STOPPING,
            ):

                logger.warning(
                    "[CognitionNode] "
                    "RESET rejected | "
                    "node still active"
                )

                return False

            self._governor = None

            self._status = (
                CognitionStatus.READY
            )

            self._mode = (
                CognitionMode.PASSIVE
            )

            self._start_requested = False
            self._stop_requested = False

            self._boot_ready = bool(
                reopen_boot_gate
            )

            self._last_error = None

            self._last_reason = (
                "manual_reset"
            )

            self._started_at = None
            self._stopped_at = None

        logger.info(
            "[CognitionNode] RESET | "
            "status=ready | "
            "mode=passive | "
            f"boot_ready={reopen_boot_gate}"
        )

        return True

    # ======================================================
    # DIAGNOSTICS
    # ======================================================

    def diagnostics(
        self,
    ) -> Dict[str, Any]:

        with self._lock:

            now = time.time()

            uptime = (
                now - self._started_at
                if (
                    self._started_at is not None
                    and self._status
                    == CognitionStatus.RUNNING
                )
                else 0.0
            )

            return {

                "name": self.NAME,
                "version": self.VERSION,

                # ------------------------------------------
                # STATE
                # ------------------------------------------

                "status": (
                    self._status.value
                ),

                "mode": (
                    self._mode.value
                ),

                "running": (
                    self._status
                    == CognitionStatus.RUNNING
                ),

                # ------------------------------------------
                # BOOT
                # ------------------------------------------

                "boot_ready": (
                    self._boot_ready
                ),

                "boot_gate_open": (
                    self._boot_ready
                ),

                # ------------------------------------------
                # CORE DEPENDENCIES
                # ------------------------------------------

                "dependencies_ready": (
                    self.dependencies_ready()
                ),

                "core_dependencies_ready": (
                    self.core_dependencies_ready()
                ),

                "queue_loop_attached": (
                    self.queue_loop is not None
                ),

                "memory_graph_attached": (
                    self.memory_graph is not None
                ),

                # ------------------------------------------
                # QBIT / COMMAND / RELAY
                # ------------------------------------------

                "qbit_dialer_attached": (
                    self.qbit_dialer is not None
                ),

                "command_relay_attached": (
                    self.command_relay is not None
                ),

                "relay_attached": (
                    self.relay is not None
                ),

                "command_dependencies_ready": (
                    self.command_dependencies_ready()
                ),

                # ------------------------------------------
                # BIOS / GROWTH
                # ------------------------------------------

                "bios_attached": (
                    self.bios is not None
                ),

                "growth_manager_attached": (
                    self.growth_manager is not None
                ),

                "file_tool_attached": (
                    self.file_tool is not None
                ),

                "module_loader_attached": (
                    self.module_loader is not None
                ),

                "tool_registry_attached": (
                    self.tool_registry is not None
                ),

                "permission_manager_attached": (
                    self.permission_manager is not None
                ),

                "growth_dependencies_ready": (
                    self.growth_dependencies_ready()
                ),

                # ------------------------------------------
                # GOVERNOR
                # ------------------------------------------

                "governor_attached": (
                    self._governor is not None
                ),

                # ------------------------------------------
                # LIFECYCLE
                # ------------------------------------------

                "start_requested": (
                    self._start_requested
                ),

                "stop_requested": (
                    self._stop_requested
                ),

                "start_count": (
                    self._start_count
                ),

                "stop_count": (
                    self._stop_count
                ),

                "started_at": (
                    self._started_at
                ),

                "stopped_at": (
                    self._stopped_at
                ),

                "uptime": round(
                    uptime,
                    3,
                ),

                # ------------------------------------------
                # ERROR
                # ------------------------------------------

                "last_reason": (
                    self._last_reason
                ),

                "last_error": (
                    self._last_error
                ),

                "created_at": (
                    self._created_at
                ),

                # ------------------------------------------
                # ARCHITECTURE CONTRACT
                # ------------------------------------------

                "architecture": {

                    "cognition_is_lifecycle_owner": True,

                    "cognition_owns_qbit_lifecycle": False,

                    "cognition_owns_queue_lifecycle": False,

                    "cognition_owns_event_bus_lifecycle": False,

                    "cognition_owns_heartbeat_lifecycle": False,

                    "cognition_owns_kernel_bus_lifecycle": False,

                    "cognition_owns_relay_lifecycle": False,

                    "cognition_owns_bios_lifecycle": False,

                    "cognition_owns_filesystem_lifecycle": False,

                    "cognition_owns_module_loader_lifecycle": False,

                    "qbit_is_external_dependency": True,

                    "command_path_is_external_dependency": True,

                    "relay_is_external_dependency": True,

                    "bios_is_external_dependency": True,

                    "growth_is_external_dependency": True,

                    "growth_access_is_runtime_authorized": True,
                },

                # ------------------------------------------
                # LIFECYCLE CONTRACT
                # ------------------------------------------

                "lifecycle": {

                    "passive_import": True,

                    "explicit_start_required": True,

                    "boot_gate_required": True,

                    "duplicate_start_protected": True,

                    "single_governor_owner": True,

                    "background_start_on_import": False,

                    "cognitive_clock_auto_start": False,

                    "goal_engine_auto_start": False,

                    "queue_loop_auto_start": False,

                    "event_bus_auto_start": False,

                    "qbit_dialer_auto_start": False,

                    "heartbeat_auto_start": False,

                    "kernel_bus_auto_start": False,

                    "relay_auto_start": False,

                    "bios_auto_start": False,

                    "growth_auto_start": False,

                    "module_loader_auto_start": False,
                },
            }

    # ======================================================
    # STATUS SNAPSHOT
    # ======================================================

    def get_status(
        self,
    ) -> Dict[str, Any]:

        with self._lock:

            status = self._status

            return {

                "node": self.NAME,

                "status": status.value,

                "mode": (
                    self._mode.value
                ),

                "running": (
                    status
                    == CognitionStatus.RUNNING
                ),

                "boot_ready": (
                    self._boot_ready
                ),

                "dependencies_ready": (
                    self.dependencies_ready()
                ),

                "qbit_ready": (
                    self.qbit_dialer is not None
                ),

                "command_path_ready": (
                    self.command_dependencies_ready()
                ),

                "relay_ready": (
                    self.relay is not None
                    or self.command_relay is not None
                ),

                "growth_ready": (
                    self.growth_dependencies_ready()
                ),

                "bios_ready": (
                    self.bios is not None
                ),

                "healthy": status in (
                    CognitionStatus.READY,
                    CognitionStatus.RUNNING,
                ),
            }

    # ======================================================
    # REPRESENTATION
    # ======================================================

    def __repr__(
        self,
    ) -> str:

        with self._lock:

            status = (
                self._status.value
            )

            mode = (
                self._mode.value
            )

            running = (
                self._status
                == CognitionStatus.RUNNING
            )

            queue_attached = (
                self.queue_loop is not None
            )

            governor_attached = (
                self._governor is not None
            )

            qbit_attached = (
                self.qbit_dialer is not None
            )

            relay_attached = (
                self.relay is not None
                or self.command_relay is not None
            )

            bios_attached = (
                self.bios is not None
            )

            return (
                "CognitionNode("
                f"status={status!r}, "
                f"mode={mode!r}, "
                f"running={running!r}, "
                f"boot_ready="
                f"{self._boot_ready!r}, "
                f"queue_loop="
                f"{queue_attached!r}, "
                f"qbit="
                f"{qbit_attached!r}, "
                f"relay="
                f"{relay_attached!r}, "
                f"bios="
                f"{bios_attached!r}, "
                f"governor="
                f"{governor_attached!r}"
                ")"
            )


# ==========================================================
# MODULE-LEVEL NODE
# ==========================================================
#
# SAFE AT IMPORT.
#
# Creating this state container does NOT:
#
#   - create a thread
#   - create an asyncio task
#   - start a clock
#   - start GoalEngine
#   - start governor
#   - start QueueLoop
#   - start EventBus
#   - start QbitDialer
#   - start Heartbeat
#   - start Relay
#   - start BIOS
#   - start filesystem access
#   - start module loader
#
# ==========================================================

_cognition_node = CognitionNode()


# ==========================================================
# PUBLIC CORE ATTACHMENT API
# ==========================================================

def attach_cognition_dependencies(
    queue_loop=None,
    memory_graph=None,
    qbit_dialer=None,
    command_relay=None,
    relay=None,
    bios=None,
    growth_manager=None,
    file_tool=None,
    module_loader=None,
    tool_registry=None,
    permission_manager=None,
) -> bool:

    return _cognition_node.attach_dependencies(
        queue_loop=queue_loop,
        memory_graph=memory_graph,
        qbit_dialer=qbit_dialer,
        command_relay=command_relay,
        relay=relay,
        bios=bios,
        growth_manager=growth_manager,
        file_tool=file_tool,
        module_loader=module_loader,
        tool_registry=tool_registry,
        permission_manager=permission_manager,
    )


# ==========================================================
# PUBLIC START API
# ==========================================================

def start_cognitive_governor(
    queue_loop,
    memory_graph=None,
    *,
    boot_ready: bool = False,
    qbit_dialer=None,
    command_relay=None,
    relay=None,
    bios=None,
    growth_manager=None,
    file_tool=None,
    module_loader=None,
    tool_registry=None,
    permission_manager=None,
):

    # ------------------------------------------------------
    # Attach whatever runtime dependencies were supplied.
    #
    # This preserves the old two-argument call while allowing
    # the authoritative runtime to wire the complete SEED
    # cognitive environment.
    # ------------------------------------------------------

    _cognition_node.attach_dependencies(
        queue_loop=queue_loop,
        memory_graph=memory_graph,
        qbit_dialer=qbit_dialer,
        command_relay=command_relay,
        relay=relay,
        bios=bios,
        growth_manager=growth_manager,
        file_tool=file_tool,
        module_loader=module_loader,
        tool_registry=tool_registry,
        permission_manager=permission_manager,
    )

    with _cognition_node._lock:

        if queue_loop is None:

            _cognition_node._status = (
                CognitionStatus.DEGRADED
            )

            _cognition_node._mode = (
                CognitionMode.DEGRADED
            )

            _cognition_node._last_reason = (
                "queue_loop_unavailable"
            )

            logger.warning(
                "[CognitionNode] "
                "START REJECTED | "
                "queue_loop unavailable"
            )

            return None

        # --------------------------------------------------
        # Explicit boot authorization.
        # --------------------------------------------------

        if boot_ready:

            _cognition_node._boot_ready = True
            _cognition_node._stop_requested = False

        # --------------------------------------------------
        # If stopped, prepare only for explicit restart.
        # --------------------------------------------------

        if (
            _cognition_node._status
            == CognitionStatus.STOPPED
        ):

            _cognition_node._status = (
                CognitionStatus.READY
            )

            _cognition_node._mode = (
                CognitionMode.PASSIVE
            )

            _cognition_node._last_reason = (
                "restart_requested"
            )

    return _cognition_node.start(
        require_boot_ready=True
    )


# ==========================================================
# PUBLIC BOOT-GATE API
# ==========================================================

def set_cognition_boot_ready(
    ready: bool = True,
    reason: str = "boot_gate",
) -> bool:

    return _cognition_node.set_boot_ready(
        ready=ready,
        reason=reason,
    )


# ==========================================================
# PUBLIC STOP API
# ==========================================================

def stop_cognitive_governor(
    reason: str = "shutdown_requested",
) -> bool:

    return _cognition_node.stop(
        reason=reason
    )


# ==========================================================
# PUBLIC RESET API
# ==========================================================

def reset_cognition(
    *,
    reopen_boot_gate: bool = False,
) -> bool:

    return _cognition_node.reset(
        reopen_boot_gate=reopen_boot_gate
    )


# ==========================================================
# STATUS API
# ==========================================================

def cognition_status() -> Dict[str, Any]:

    return _cognition_node.get_status()


# ==========================================================
# DIAGNOSTICS API
# ==========================================================

def cognition_diagnostics() -> Dict[str, Any]:

    return _cognition_node.diagnostics()


# ==========================================================
# NODE ACCESS
# ==========================================================

def get_cognition_node() -> CognitionNode:

    return _cognition_node


# ==========================================================
# READINESS
# ==========================================================

def cognition_ready() -> bool:

    return (
        _cognition_node.status
        in (
            CognitionStatus.READY,
            CognitionStatus.RUNNING,
        )
    )


# ==========================================================
# BOOT READINESS
# ==========================================================

def cognition_boot_ready() -> bool:

    return _cognition_node.boot_gate_open()


# ==========================================================
# RUNNING
# ==========================================================

def cognition_running() -> bool:

    return _cognition_node.running


# ==========================================================
# ACTIVE CHECK
# ==========================================================

def cognition_active() -> bool:

    with _cognition_node._lock:

        return (
            _cognition_node._status
            == CognitionStatus.RUNNING
            and _cognition_node._governor
            is not None
        )


# ==========================================================
# QBIT CHECK
# ==========================================================

def cognition_qbit_ready() -> bool:

    with _cognition_node._lock:

        return (
            _cognition_node.qbit_dialer
            is not None
        )


# ==========================================================
# COMMAND PATH CHECK
# ==========================================================

def cognition_command_ready() -> bool:

    return _cognition_node.command_dependencies_ready()


# ==========================================================
# RELAY CHECK
# ==========================================================

def cognition_relay_ready() -> bool:

    with _cognition_node._lock:

        return (
            _cognition_node.relay is not None
            or _cognition_node.command_relay is not None
        )


# ==========================================================
# BIOS CHECK
# ==========================================================

def cognition_bios_ready() -> bool:

    with _cognition_node._lock:

        return (
            _cognition_node.bios is not None
        )


# ==========================================================
# GROWTH CHECK
# ==========================================================

def cognition_growth_ready() -> bool:

    return _cognition_node.growth_dependencies_ready()


# ==========================================================
# MODULE EXPORTS
# ==========================================================

__all__ = [

    # ------------------------------------------------------
    # Status
    # ------------------------------------------------------

    "CognitionStatus",
    "CognitionMode",

    # ------------------------------------------------------
    # Node
    # ------------------------------------------------------

    "CognitionNode",

    # ------------------------------------------------------
    # Dependency wiring
    # ------------------------------------------------------

    "attach_cognition_dependencies",

    # ------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------

    "start_cognitive_governor",
    "stop_cognitive_governor",
    "reset_cognition",

    # ------------------------------------------------------
    # Boot gate
    # ------------------------------------------------------

    "set_cognition_boot_ready",
    "cognition_boot_ready",

    # ------------------------------------------------------
    # Status
    # ------------------------------------------------------

    "cognition_status",
    "cognition_diagnostics",
    "get_cognition_node",

    # ------------------------------------------------------
    # Readiness
    # ------------------------------------------------------

    "cognition_ready",
    "cognition_running",
    "cognition_active",

    # ------------------------------------------------------
    # Core integration readiness
    # ------------------------------------------------------

    "cognition_qbit_ready",
    "cognition_command_ready",
    "cognition_relay_ready",
    "cognition_bios_ready",
    "cognition_growth_ready",
]


# ==========================================================
# END COGNITION NEURAL NODE
# ==========================================================
#
# IMPORT:
#     -> READY
#     -> PASSIVE
#     -> NO THREADS
#     -> NO TASKS
#     -> NO SERVICES STARTED
#
# BOOT GATE CLOSED:
#     -> cognition cannot activate
#
# BOOT GATE OPEN:
#     -> permission exists
#     -> cognition still does NOT start automatically
#
# EXPLICIT START:
#     -> STARTING
#     -> governor initialization
#     -> RUNNING
#
# QBIT:
#     -> may be attached
#     -> cognition can know whether Qbit is available
#     -> cognition does NOT start Qbit
#
# COMMAND:
#     -> command path may be attached
#     -> cognition can know whether command infrastructure
#        is available
#
# RELAY:
#     -> relay may be attached
#     -> cognition does NOT own relay lifecycle
#
# BIOS / GROWTH:
#     -> BIOS tools may be attached
#     -> file tools may be attached
#     -> module loader may be attached
#     -> growth manager may be attached
#     -> permission manager may be attached
#
#     These are CAPABILITIES supplied by the authoritative
#     SEED runtime. This node does not silently manufacture
#     filesystem or module authority.
#
# ==========================================================
#
# SEED OWNERSHIP MODEL
#
#     SEED BOOT
#         |
#         +--> QueueLoop
#         |
#         +--> EventBus
#         |
#         +--> Heartbeat
#         |
#         +--> QbitDialer
#         |        |
#         |        v
#         |    COMMAND PATH
#         |        |
#         |        v
#         |      RELAY
#         |        |
#         |        v
#         |      BIOS
#         |        |
#         |        +--> FILE TOOL
#         |        |
#         |        +--> MODULE LOADER
#         |        |
#         |        +--> TOOL REGISTRY
#         |        |
#         |        +--> GROWTH MANAGER
#         |
#         +--> KernelBus
#         |
#         +--> COGNITION BOOT GATE
#                    |
#                    v
#              CognitionNode
#                    |
#                    v
#                 Governor
#
# ==========================================================
#
# DESIGN INTENT
#
# The CognitionNode is now capable of being wired into the
# complete SEED cognitive environment without taking ownership
# of the infrastructure that SEED boot/runtime already owns.
#
# This is the important distinction:
#
#     CAPABILITY != LIFECYCLE OWNERSHIP
#
# SEED may grant Cognition access to the systems required for
# reasoning, command execution, relay communication, inspection,
# development, and growth.
#
# But the authoritative runtime remains responsible for
# starting, stopping, authorizing, and supervising those
# systems.
#
# ==========================================================