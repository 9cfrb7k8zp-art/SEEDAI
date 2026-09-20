# ==========================================================
# FILE: track_system.py
# PATH: C:\SEED_ROOT\seed\core\track_system.py
# VERSION: 10.0.0
# NAME: Track Station / Identity / Registry / Data Flow Authority
# UPDATED: 2026-08-29
#
# ==========================================================
# TRACKSYSTEM v10 — AUTHORITATIVE ARCHITECTURE
# ==========================================================
#
# TrackSystem is the station responsible for:
#
#   IDENTITY
#   TRACK CONTEXT
#   CHANNEL CONTEXT
#   MODULE REGISTRY
#   NODE REGISTRY
#   SYSTEM STATE
#   PACKET NORMALIZATION
#   DATA-FLOW OBSERVATION
#   QBIT REQUEST/FEEDBACK ROUTING THROUGH EVENTBUS
#
# TrackSystem is NOT the command executor.
#
# ==========================================================
# CORE SEED DATA / COGNITION / COMMAND PIPELINE
# ==========================================================
#
# HEARTBEAT
#     |
#     | system clock / control input
#     v
# SYSTEM STATE
#     |
#     v
# TRACKSYSTEM
#     |
#     | authoritative state / context
#     v
# EVENTBUS
#     |
#     v
# QBIT
#     |
#     | data + identity + lineage
#     v
# QbitQueueLoop
#     |
#     | sole Qbit processing queue
#     v
# ComputeBrain
#     |
#     | decode/process
#     v
# ThoughtPacket
#     |
#     | cognition result
#     v
# TransformerBrain
#     |
#     | actionable proposal
#     v
# QbitDialer
#     |
#     | SOLE COMMAND AUTHORITY
#     v
# submit_command()
#     |
#     | SOLE COMMAND ADMISSION
#     v
# QbitQueueLoop
#     |
#     | execution/runtime
#     v
# FEEDBACK
#     |
#     v
# EVENTBUS
#     |
#     v
# TrackSystem
#
# ==========================================================
# QBIT = DATA / BLOOD-CELL TRANSPORT
# ==========================================================
#
# A Qbit is a transport object.
#
# Qbit carries:
#
#   - payload
#   - identity
#   - lineage
#   - track identity
#   - channel identity
#   - source
#   - destination
#   - priority
#   - timestamps
#   - metadata
#
# Qbit is NOT:
#
#   - the command authority
#   - the execution authority
#   - a replacement for QbitQueueLoop
#   - a second task queue
#
# IMPORTANT:
#
# Qbit does not create an independent fallback execution queue.
#
# Qbit.put() / Qbit submission must ultimately feed the
# authoritative QbitQueueLoop.
#
# ==========================================================
# COGNITION OWNERSHIP
# ==========================================================
#
# ComputeBrain
#   = receives Qbit data
#   = decodes/processes Qbit payload
#   = produces ThoughtPacket
#
# ThoughtPacket
#   = structured cognition result
#   = carries interpreted meaning/context
#
# TransformerBrain
#   = receives ThoughtPacket
#   = transforms cognition into actionable proposal
#   = does NOT independently execute commands
#
# ==========================================================
# COMMAND OWNERSHIP
# ==========================================================
#
# QbitDialer
#   = SOLE COMMAND AUTHORITY
#
# QbitDialer:
#
#   - receives actionable command proposals
#   - validates command intent
#   - applies command policy
#   - controls command admission
#   - creates/uses the authoritative task contract
#   - submits commands through submit_command()
#
# submit_command()
#   = SOLE COMMAND ADMISSION PATH
#
# No other module may create a competing command-execution
# authority.
#
# TrackSystem MUST NOT execute commands.
# TrackSystem MUST NOT bypass QbitDialer.
# TrackSystem MUST NOT call QbitQueueLoop as a command shortcut.
#
# ==========================================================
# EXECUTION OWNERSHIP
# ==========================================================
#
# QbitQueueLoop
#   = SOLE Qbit processing/execution runtime
#
# QbitQueueLoop owns:
#
#   - authoritative Qbit processing queue
#   - execution scheduling
#   - Qbit dequeue/processing lifecycle
#   - runtime execution handoff
#
# TrackSystem may observe queue depth/state through an
# integration interface, but does NOT own or replace the
# QbitQueueLoop.
#
# ==========================================================
# TRACK / IDENTITY OWNERSHIP
# ==========================================================
#
# TrackContext
#   = active identity / context / metadata state
#
# TrackIDManager
#   = canonical track identity generation
#
# ChannelID
#   = canonical channel identity
#
# TrackSystem
#   = tracking station / context / registry authority
#
# TrackSystem associates Qbits, packets, modules and nodes
# with track/channel context.
#
# TrackSystem does NOT become the Qbit execution authority
# merely because it tracks a Qbit.
#
# ==========================================================
# REGISTRY OWNERSHIP
# ==========================================================
#
# TrackSystem maintains the authoritative descriptive view of:
#
#   MODULE REGISTRY
#   NODE REGISTRY
#   MODULE STATE
#   NODE STATE
#   SYSTEM STATE
#   REGISTRY GENERATION
#
# Package __init__.py metadata may register through TrackSystem.
#
# Registration is descriptive.
#
# Registration does NOT mean:
#
#   - module execution
#   - command execution
#   - boot ownership
#   - shutdown ownership
#
# ==========================================================
# SYSTEM READINESS / CONNECTION MODEL
# ==========================================================
#
# TrackSystem publishes authoritative system state.
#
# QbitDialer uses that state to determine whether the system
# has reached the required connected/ready condition.
#
# TrackSystem does NOT "wake" QbitDialer by directly invoking it.
#
# Correct relationship:
#
#   TrackSystem
#       |
#       | TRACK_SYSTEM_STATE
#       | TRACK_REGISTRY_SYNC
#       v
#   EventBus
#       |
#       v
#   QbitDialer
#
# This keeps construction, registration, synchronization and
# runtime execution separate.
#
# ==========================================================
# HEARTBEAT OWNERSHIP
# ==========================================================
#
# Heartbeat
#   = system clock / liveness / control-input source
#
# Heartbeat:
#
#   - reports liveness
#   - provides timing/state signals
#   - supplies control input into the system
#
# Heartbeat does NOT:
#
#   - execute commands
#   - own QbitQueueLoop
#   - bypass QbitDialer
#   - become a second command authority
#
# ==========================================================
# EVENTBUS OWNERSHIP
# ==========================================================
#
# EventBus
#   = communication / transport backbone
#
# EventBus connects authorities without transferring ownership.
#
# TrackSystem publishes state and tracking events.
# QbitDialer consumes relevant system/Qbit state.
# QbitQueueLoop processes Qbits.
# ComputeBrain and TransformerBrain process cognition.
# Feedback returns through EventBus and is recorded by
# TrackSystem.
#
# ==========================================================
# AUTHORITY MODEL
# ==========================================================
#
# TrackContext
#   = active identity / context / metadata
#
# TrackIDManager
#   = canonical track identity
#
# ChannelID
#   = canonical channel identity
#
# TrackSystem
#   = tracking + station + packet normalization +
#     module registry + node registry +
#     state aggregation + data-flow authority
#
# EventBus
#   = communication / transport backbone
#
# Qbit
#   = data / identity / lineage transporter
#
# QbitQueueLoop
#   = sole Qbit processing/execution runtime
#
# ComputeBrain
#   = Qbit cognition / ThoughtPacket production
#
# TransformerBrain
#   = ThoughtPacket transformation / command proposal
#
# QbitDialer
#   = SOLE COMMAND AUTHORITY
#
# submit_command()
#   = SOLE COMMAND ADMISSION PATH
#
# Heartbeat
#   = heartbeat / liveness / control-input authority
#
# AgentManager
#   = orchestration authority
#
# HUD
#   = observer only
#
# ==========================================================
# CORE RULE — TRACKSYSTEM NEVER
# ==========================================================
#
# TrackSystem NEVER:
#
#   - instantiates QbitDialer
#   - instantiates QbitQueueLoop
#   - executes Qbit commands
#   - owns the Qbit execution queue
#   - creates a Qbit fallback task queue
#   - calls submit_command() as an execution shortcut
#   - bypasses QbitDialer
#   - controls Heartbeat
#   - controls boot
#   - controls shutdown
#   - becomes a competing command authority
#
# ==========================================================
# CORE RULE — TRACKSYSTEM MAY
# ==========================================================
#
# TrackSystem MAY:
#
#   - register module metadata
#   - register package __init__.py metadata
#   - register nodes
#   - record module state
#   - record node state
#   - aggregate system state
#   - publish system state
#   - publish registry synchronization
#   - create tracks
#   - create packets
#   - normalize payloads
#   - associate Qbits with track/channel context
#   - request Qbit processing through EventBus
#   - receive Qbit feedback
#   - maintain learning/observation state
#   - notify observers
#
# ==========================================================
# DATA FLOW
# ==========================================================
#
# package/__init__.py
#       |
#       v
# MODULE METADATA
#       |
#       v
# NODE STATE
#       |
#       v
# TrackSystem
#       |
#       +-------------------+
#       |                   |
#       v                   v
# TRACK_PACKET       SYSTEM_STATE
#       |                   |
#       v                   v
# EventBus ------------ QbitDialer
#       |                   ^
#       |                   |
#       v              command proposal
#     Qbit                  |
#       |                   |
#       v                   |
# QbitQueueLoop             |
#       |                   |
#       v                   |
# ComputeBrain              |
#       |                   |
#       v                   |
# ThoughtPacket             |
#       |                   |
#       v                   |
# TransformerBrain --------+
#       |
#       v
# QbitDialer
#       |
#       v
# submit_command()
#       |
#       v
# QbitQueueLoop
#       |
#       v
# feedback
#       |
#       v
# EventBus
#       |
#       v
# TrackSystem
#
# ==========================================================
# IMPORTANT ARCHITECTURAL INVARIANTS
# ==========================================================
#
# 1. Qbit is transport.
# 2. TrackSystem owns track/channel context and registry/state.
# 3. EventBus is transport between authorities.
# 4. QbitQueueLoop is the single authoritative Qbit queue.
# 5. There is NO Qbit-owned fallback execution queue.
# 6. ComputeBrain produces ThoughtPacket from Qbit data.
# 7. TransformerBrain produces actionable proposals from
#    ThoughtPacket.
# 8. QbitDialer is the ONLY command authority.
# 9. submit_command() is the ONLY command admission path.
# 10. QbitQueueLoop is the ONLY execution/runtime authority.
# 11. Heartbeat provides liveness/control input but executes
#     no commands.
# 12. TrackSystem publishes state; it does not directly wake,
#     execute or control QbitDialer.
# 13. HUD remains observer-only.
# 14. Construction does not equal runtime start.
# 15. Registration does not equal execution.
# 16. System readiness is established through authoritative
#     state/registry synchronization.
#
# ==========================================================
# IMPORTANT
# ==========================================================
#
# The EventBus remains the transport.
#
# TrackSystem publishes authoritative state so QbitDialer can
# determine that the system is connected and ready.
#
# TrackSystem does not directly instantiate or invoke the
# command/execution authorities.
#
# ==========================================================

from __future__ import annotations

import inspect
import logging
import os
import pkgutil
import threading
import time
import uuid

from collections import defaultdict, deque
from typing import Any, Callable, Dict, Optional


# ==========================================================
# CORE IMPORTS
# ==========================================================

from seed.core.track_base import (
    TrackBase,
    TrackIDBase,
    TrackContextBase,
)

from seed.core.track_context import TrackContext
from seed.core.track_id_manager import TrackIDManager
from seed.core.channel_id import ChannelID


# ==========================================================
# LOGGER
# ==========================================================

logger = logging.getLogger("TrackSystem")

if not logger.handlers:
    logging.basicConfig(level=logging.INFO)

logger.setLevel(logging.INFO)


# ==========================================================
# MODULE METADATA
# ==========================================================

MODULE_NAME = "TrackSystem"
MODULE_ID = "TRACK-STATION"
MODULE_VERSION = "10.0.0"

CABI_ID = "CABI-TRACK-2"

MODULE_TYPE = "CORE"
MODULE_ROLE = "DATA_FLOW_AUTHORITY"


# ==========================================================
# AUTHORITY IDENTIFIERS
# ==========================================================
#
# These identifiers are descriptive contracts.
#
# TrackSystem does NOT import or instantiate these runtime
# authorities merely by naming them here.
#
# Keeping the authority names explicit prevents accidental
# architectural drift and makes emitted state understandable
# to QbitDialer, QbitQueueLoop and diagnostic observers.
#
# ==========================================================

QBIT_TRANSPORT_AUTHORITY = "Qbit"
QBIT_QUEUE_AUTHORITY = "QbitQueueLoop"

COMPUTE_AUTHORITY = "ComputeBrain"
THOUGHT_PACKET_TYPE = "ThoughtPacket"

TRANSFORMER_AUTHORITY = "TransformerBrain"

COMMAND_AUTHORITY = "QbitDialer"
COMMAND_ADMISSION = "submit_command"

HEARTBEAT_AUTHORITY = "Heartbeat"
EVENT_TRANSPORT = "EventBus"

TRACK_AUTHORITY = "TrackSystem"
HUD_AUTHORITY = "HUD_OBSERVER_ONLY"


# ==========================================================
# EVENT TYPES
# ==========================================================

TRACK_BEGIN = "TRACK_BEGIN"
TRACK_END = "TRACK_END"
TRACK_EMIT = "TRACK_EMIT"
TRACK_PACKET = "TRACK_PACKET"

TRACK_QBIT_REQUEST = "TRACK_QBIT_REQUEST"
TRACK_QBIT_RESULT = "TRACK_QBIT_RESULT"
TRACK_QBIT_FEEDBACK = "TRACK_QBIT_FEEDBACK"

TRACK_FEEDBACK = "TRACK_FEEDBACK"
TRACK_ERROR = "TRACK_ERROR"
TRACK_HEALTH = "TRACK_HEALTH"
TRACK_RECOVERY = "TRACK_RECOVERY"


# ==========================================================
# REGISTRY / STATE EVENTS
# ==========================================================

TRACK_MODULE_REGISTER = "TRACK_MODULE_REGISTER"
TRACK_MODULE_STATE = "TRACK_MODULE_STATE"

TRACK_NODE_REGISTER = "TRACK_NODE_REGISTER"
TRACK_NODE_STATE = "TRACK_NODE_STATE"

TRACK_SYSTEM_STATE = "TRACK_SYSTEM_STATE"
TRACK_REGISTRY_SYNC = "TRACK_REGISTRY_SYNC"


# ==========================================================
# PIPELINE OBSERVATION EVENTS
# ==========================================================

TRACK_QBIT_RECEIVED = "TRACK_QBIT_RECEIVED"
TRACK_QBIT_QUEUED = "TRACK_QBIT_QUEUED"

TRACK_THOUGHT_PACKET = "TRACK_THOUGHT_PACKET"
TRACK_COMMAND_PROPOSAL = "TRACK_COMMAND_PROPOSAL"

TRACK_COMMAND_ADMITTED = "TRACK_COMMAND_ADMITTED"
TRACK_COMMAND_FEEDBACK = "TRACK_COMMAND_FEEDBACK"

TRACK_HEARTBEAT_STATE = "TRACK_HEARTBEAT_STATE"
TRACK_RUNTIME_STATE = "TRACK_RUNTIME_STATE"


# ==========================================================
# COMPATIBILITY ALIASES
# ==========================================================

QBIT_RESULT = TRACK_QBIT_RESULT
QBIT_FEEDBACK = TRACK_QBIT_FEEDBACK
TRACK_RESULT = TRACK_FEEDBACK


# ==========================================================
# PRIORITY
# ==========================================================

PRIORITY_LEVELS = {
    "LOW": 10,
    "MED": 50,
    "HIGH": 80,
    "CRITICAL": 100,
}


CHANNEL_COOLDOWN = {
    "LOW": 0.05,
    "MED": 0.02,
    "HIGH": 0.005,
    "CRITICAL": 0.0,
}


ESCALATION_PLAN = {
    "LOW": [
        "log",
    ],
    "MED": [
        "log",
        "notify",
    ],
    "HIGH": [
        "log",
        "notify",
        "attempt_fix",
    ],
    "CRITICAL": [
        "log",
        "notify",
        "attempt_fix",
        "escalate",
    ],
}


# ==========================================================
# TRACK SYSTEM ERROR
# ==========================================================

class TrackSystemError(Exception):

    def __init__(
        self,
        message=None,
        *args,
        event_bus=None,
        storage_root="./SEED_ROOT",
        priority="MED",
        track_id=None,
        hud_id=None,
    ):
        if not message and args:
            for candidate in args:
                if (
                    isinstance(candidate, str)
                    and candidate.strip()
                ):
                    message = candidate
                    break

        message = message or "TrackSystem error"

        super().__init__(message)

        self.event_bus = event_bus
        self.storage_root = storage_root
        self.message = message

        self.priority = str(
            priority or "MED"
        ).upper()

        if self.priority not in ESCALATION_PLAN:
            self.priority = "MED"

        self.track_id = track_id
        self.hud_id = hud_id

        self.plan = ESCALATION_PLAN.get(
            self.priority,
            ESCALATION_PLAN["MED"],
        )


# =======================================================================

    def execute(self):

        for step in self.plan:

            if step == "log":

                logger.warning(
                    "[TrackSystem] %s | track=%s | hud=%s",
                    self.message,
                    self.track_id,
                    self.hud_id,
                )

            elif step == "notify":

                self._emit_error_event()

            elif step == "attempt_fix":

                try:
                    TrackContext.clear()
                except Exception:
                    pass

            elif step == "escalate":

                logger.critical(
                    "[TrackSystem] ESCALATION REQUIRED | track=%s",
                    self.track_id,
                )

        return False

    def _emit_error_event(self):

        if self.event_bus is None:
            return False

        payload = {
            "error": self.message,
            "priority": self.priority,
            "track_id": self.track_id,
            "hud_id": self.hud_id,
            "source": MODULE_NAME,
            "module": MODULE_ID,
            "timestamp": time.time(),
        }

        return TrackSystem._safe_bus_emit(
            self.event_bus,
            TRACK_ERROR,
            payload,
        )


# ==========================================================
# TRACK SYSTEM
# ==========================================================

class TrackSystem:

    # ======================================================
    # SHARED STATION STATE
    # ======================================================

    _skill_matrix = defaultdict(
        lambda: {
            "tracks": 1,
            "channels": 3,
            "success": 0,
            "failures": 0,
            "last_success": None,
            "last_failure": None,
        }
    )

    _channel_last_emit = defaultdict(float)

    # ------------------------------------------------------
    # IMPORTANT:
    #
    # This is ONLY the TrackSystem station buffer.
    #
    # It is NOT:
    #   - the Qbit queue
    #   - the task queue
    #   - the command queue
    #   - the execution queue
    #
    # QbitQueueLoop remains the sole authoritative Qbit
    # processing/execution queue.
    # ------------------------------------------------------

    _station_queue = deque()

    _lock = threading.RLock()

    _qbit_enabled = True
    _qbit_override_enabled = False

    _hud_sync_callbacks = []
    _feedback_callbacks = []

    _event_bus = None
    _event_bus_subscription_handles = []

    _instance = None

    # ======================================================
    # REGISTRY STATE
    # ======================================================

    _module_registry = {}
    _node_registry = {}

    _registry_generation = 0

    # ======================================================
    # SEQUENCE
    # ======================================================

    _packet_sequence = 0
    _feedback_sequence = 0
    _state_sequence = 0

    # ======================================================
    # METRICS
    # ======================================================

    _metrics = {
        "tracks_started": 0,
        "tracks_completed": 0,
        "packets_emitted": 0,
        "qbit_requests": 0,
        "qbit_received": 0,
        "qbit_queued": 0,
        "qbit_results": 0,
        "feedback_received": 0,
        "thought_packets": 0,
        "command_proposals": 0,
        "commands_admitted": 0,
        "command_feedback": 0,
        "heartbeat_states": 0,
        "runtime_states": 0,
        "errors": 0,
        "recovery_events": 0,
        "modules_registered": 0,
        "nodes_registered": 0,
        "states_updated": 0,
        "state_snapshots": 0,
    }

    # ======================================================
    # INIT
    # ======================================================

    def __init__(
        self,
        storage_root="./SEED_ROOT",
        event_bus=None,
        qbit=None,
        qbit_dialer=None,
        kernel=None,
        seedcore=None,
        fathud=None,
        computebrain=None,
        transformerbrain=None,
        fat_layer=None,
        track_id="TS",
        registry=None,
        node_registry=None,
        encoder=None,
    ):

        self.storage_root = storage_root
        self.track_id = track_id

        self.channels: Dict[
            str,
            Dict[str, Any],
        ] = {}

        self._overlays: Dict[
            str,
            Any,
        ] = {}

    # ======================================================
    # AUTHORITATIVE RUNTIME REFERENCES
    # ======================================================
    #
    # TrackSystem receives these objects by injection.
    #
    # It does NOT construct:
    #   - EventBus
    #   - Qbit
    #   - QbitQueueLoop
    #   - QbitDialer
    #   - ComputeBrain
    #   - TransformerBrain
    #   - FATHUDAdapter
    #
    # ======================================================

        self.qbit = qbit
        self.qbit_dialer = qbit_dialer

        self.kernel = kernel
        self.seedcore = seedcore

        self.computebrain = computebrain
        self.transformerbrain = transformerbrain

        self.registry = registry
        self.node_registry = node_registry
        self.encoder = encoder

    # ======================================================
    # FATHUD — AUTHORITATIVE INSTANCE ONLY
    # ======================================================
    #
    # FATHUD is injected by the boot/runtime layer.
    #
    # TrackSystem must never instantiate another
    # FATHUDAdapter or start another HUD server.
    #
    # ======================================================

        self.fathud = fathud

        if self.fathud is None:

            self.fathud = getattr(
                self.seedcore,
                "fathud",
                None,
            )

        if self.fathud is None:

            self.fathud = getattr(
                self.qbit_dialer,
                "fathud",
                None,
            )

    # Preserve compatibility with systems still using
    # the older fat_layer name.

        self.fat_layer = (
            fat_layer
            if fat_layer is not None
            else self.fathud
        )

    # ======================================================
    # INTERNAL RUNTIME STATE
    # ======================================================

        self._event_bus_attached = False
 
        self._started = False
        self._start_requested = False
        self._boot_complete = False
        self._shutdown_requested = False

        self._lock_instance = threading.RLock()

        self._last_feedback = None
        self._last_qbit_result = None

        self._active_packets = {}

        TrackSystem._instance = self

    # --------------------------------------------------
    # EventBus is injected.
    #
    # TrackSystem does not construct the EventBus and
    # does not construct QbitDialer or QbitQueueLoop.
    # --------------------------------------------------

        if event_bus is not None:

            self.set_event_bus(
                event_bus
            )

    # --------------------------------------------------
    # Register TrackSystem itself immediately.
    #
    # Registration is descriptive metadata.
    # Registration is NOT execution.
    # --------------------------------------------------

        self.register_module(
            module_name=MODULE_NAME,
            module_id=MODULE_ID,
            version=MODULE_VERSION,
            path=__file__,
            module_type=MODULE_TYPE,
            role=MODULE_ROLE,
            state="INITIALIZED",
            metadata={
                "cabi_id": CABI_ID,
                "track_system": True,
                "authority": TRACK_AUTHORITY,
                "data_flow_authority": True,
                "qbit_transport": QBIT_TRANSPORT_AUTHORITY,
                "qbit_queue_authority": QBIT_QUEUE_AUTHORITY,
                "compute_authority": COMPUTE_AUTHORITY,
                "thought_packet": THOUGHT_PACKET_TYPE,
                "transformer_authority": TRANSFORMER_AUTHORITY,
                "command_authority": COMMAND_AUTHORITY,
                "command_admission": COMMAND_ADMISSION,
                "heartbeat_authority": HEARTBEAT_AUTHORITY,
                "event_transport": EVENT_TRANSPORT,
                "hud_authority": HUD_AUTHORITY,
            },
        )

        logger.info(
            "[TrackSystem] Initialized | "
            "version=%s | "
            "event_bus=%s | "
            "qbit=%s | "
            "dialer=%s | "
            "compute=%s | "
            "transformer=%s | "
            "fathud=%s",
            MODULE_VERSION,
            (
                type(self.event_bus).__name__
                if self.event_bus is not None
                else "NONE"
            ),
            (
                type(self.qbit).__name__
                if self.qbit is not None
                else "NONE"
            ),
            (
                type(self.qbit_dialer).__name__
                if self.qbit_dialer is not None
                else "NONE"
            ),
            (
                type(self.computebrain).__name__
                if self.computebrain is not None
                else "NONE"
            ),
            (
                type(self.transformerbrain).__name__
                if self.transformerbrain is not None
                else "NONE"
            ),
            (
                type(self.fathud).__name__
                if self.fathud is not None
                else "NONE"
            ),
        )

    # ======================================================
    # BASIC STATE
    # ======================================================

    @property
    def event_bus(self):
        return TrackSystem._event_bus

    @property
    def is_event_bus_connected(self):
        return bool(
            self._event_bus_attached
            and TrackSystem._event_bus is not None
        )

    @property
    def started(self):
        return self._started

    # ======================================================
    # MODULE REGISTRATION
    # ======================================================

    def register_module(
        self,
        module_name,
        module_id=None,
        version=None,
        path=None,
        module_type="MODULE",
        role=None,
        state="REGISTERED",
        metadata=None,
        package=None,
        init_file=None,
    ):

        name = str(
            module_name or "UNKNOWN"
        )

        now = time.time()

        normalized_state = str(
            state or "REGISTERED"
        ).upper()

        entry = {
            "module_name": name,
            "module_id": str(
                module_id or name
            ),
            "version": str(
                version or "UNKNOWN"
            ),
            "path": path,
            "package": package,
            "init_file": init_file,
            "module_type": str(
                module_type or "MODULE"
            ),
            "role": role,
            "state": normalized_state,
            "active": normalized_state in {
                "ONLINE",
                "ACTIVE",
                "READY",
                "RUNNING",
            },
            "healthy": True,
            "ready": normalized_state in {
                "READY",
                "ONLINE",
                "ACTIVE",
                "RUNNING",
            },
            "registered_at": now,
            "updated_at": now,
            "metadata": dict(
                metadata or {}
            ),
        }

        with TrackSystem._lock:

            TrackSystem._module_registry[
                name
            ] = entry

            TrackSystem._registry_generation += 1

            TrackSystem._metrics[
                "modules_registered"
            ] += 1

        self._mirror_module_registry(
            entry
        )

        self._emit(
            TRACK_MODULE_REGISTER,
            dict(entry),
        )

        self._publish_system_state()

        return dict(entry)

    # ======================================================
    # INIT.PY / PACKAGE REGISTRATION
    # ======================================================

    def register_package(
        self,
        package,
        *,
        path=None,
        metadata=None,
        state="REGISTERED",
        module_type="PACKAGE",
        role="PACKAGE_ROOT",
    ):

        package_name = str(
            package or "UNKNOWN"
        )

        if path is None:

            try:

                imported = __import__(
                    package_name,
                    fromlist=["__name__"],
                )

                path = getattr(
                    imported,
                    "__path__",
                    None,
                )

                if path:
                    path = list(path)[0]

                if path is None:
                    path = getattr(
                        imported,
                        "__file__",
                        None,
                    )

            except Exception:

                path = None

        init_file = None

        if path:

            if os.path.isdir(path):

                candidate = os.path.join(
                    path,
                    "__init__.py",
                )

                if os.path.isfile(candidate):
                    init_file = candidate

            elif str(path).endswith(
                "__init__.py"
            ):

                init_file = path

        entry_metadata = dict(
            metadata or {}
        )

        entry_metadata.setdefault(
            "has_init",
            bool(init_file),
        )

        entry_metadata.setdefault(
            "package",
            package_name,
        )

        return self.register_module(
            module_name=package_name,
            module_id=f"PKG:{package_name}",
            version=entry_metadata.get(
                "version",
                "UNKNOWN",
            ),
            path=path,
            module_type=module_type,
            role=role,
            state=state,
            metadata=entry_metadata,
            package=package_name,
            init_file=init_file,
        )

    # ======================================================
    # REGISTER INIT FOLDER
    # ======================================================

    def register_init_folder(
        self,
        path,
        *,
        package=None,
        metadata=None,
        state="REGISTERED",
    ):

        if not path:
            return False

        path = os.path.abspath(
            os.path.expanduser(
                str(path)
            )
        )

        if not os.path.isdir(path):
            return False

        init_file = os.path.join(
            path,
            "__init__.py",
        )

        if not os.path.isfile(init_file):
            return False

        if package is None:
            package = os.path.basename(
                path
            )

        data = dict(
            metadata or {}
        )

        data.setdefault(
            "filesystem_path",
            path,
        )

        data.setdefault(
            "init_file",
            init_file,
        )

        return self.register_module(
            module_name=package,
            module_id=f"PKG:{package}",
            version=data.get(
                "version",
                "UNKNOWN",
            ),
            path=path,
            module_type="PACKAGE",
            role=data.get(
                "role",
                "PACKAGE_ROOT",
            ),
            state=state,
            metadata=data,
            package=package,
            init_file=init_file,
        )

    # ======================================================
    # DISCOVER INIT.PY PACKAGES
    # ======================================================

    def discover_init_packages(
        self,
        root=None,
        *,
        package_prefix=None,
        recursive=True,
        state="DISCOVERED",
    ):

        root = root or self.storage_root

        root = os.path.abspath(
            os.path.expanduser(
                str(root)
            )
        )

        discovered = []

        if not os.path.isdir(root):
            return discovered

        for current_root, dirs, files in os.walk(root):

            if "__init__.py" not in files:
                continue

            # --------------------------------------------------
            # Avoid common runtime/cache directories.
            # --------------------------------------------------

            dirs[:] = [
                directory
                for directory in dirs
                if directory not in {
                    "__pycache__",
                    ".git",
                    ".venv",
                    "venv",
                    "node_modules",
                }
            ]

            relative = os.path.relpath(
                current_root,
                root,
            )

            parts = []

            if relative != ".":

                parts = [
                    part
                    for part in relative.split(
                        os.sep
                    )
                    if part
                ]

            if package_prefix:

                package_name = (
                    str(package_prefix)
                    + "."
                    + ".".join(parts)
                    if parts
                    else str(package_prefix)
                )

            else:

                package_name = ".".join(
                    parts
                )

            if not package_name:

                package_name = os.path.basename(
                    root
                )

            entry = self.register_init_folder(
                current_root,
                package=package_name,
                metadata={
                    "discovered": True,
                    "recursive": recursive,
                    "root": root,
                },
                state=state,
            )

            if entry:
                discovered.append(entry)

            if not recursive:
                dirs[:] = []

        return discovered

    # ======================================================
    # NODE REGISTRATION
    # ======================================================

    def register_node(
        self,
        node_id,
        *,
        module_name=None,
        node_type="MODULE",
        controller=None,
        state="REGISTERED",
        metadata=None,
    ):

        node_id = str(
            node_id or "NODE-UNKNOWN"
        )

        now = time.time()

        normalized_state = str(
            state or "REGISTERED"
        ).upper()

        entry = {
            "node_id": node_id,
            "module_name": module_name,
            "node_type": str(
                node_type or "MODULE"
            ),
            "controller": controller,
            "state": normalized_state,
            "active": normalized_state in {
                "ONLINE",
                "ACTIVE",
                "READY",
                "RUNNING",
            },
            "healthy": True,
            "ready": normalized_state in {
                "READY",
                "ONLINE",
                "ACTIVE",
                "RUNNING",
            },
            "registered_at": now,
            "updated_at": now,
            "metadata": dict(
                metadata or {}
            ),
        }

        with TrackSystem._lock:

            TrackSystem._node_registry[
                node_id
            ] = entry

            TrackSystem._registry_generation += 1

            TrackSystem._metrics[
                "nodes_registered"
            ] += 1

        self._mirror_node_registry(
            entry
        )

        self._emit(
            TRACK_NODE_REGISTER,
            dict(entry),
        )

        self._publish_system_state()

        return dict(entry)

    # ======================================================
    # MODULE STATE
    # ======================================================

    def update_module_state(
        self,
        module_name,
        state=None,
        *,
        module_id=None,
        healthy=None,
        active=None,
        ready=None,
        error=None,
        metadata=None,
    ):

        name = str(
            module_name or "UNKNOWN"
        )

        with TrackSystem._lock:

            current = TrackSystem._module_registry.get(
                name
            )

            if current is None:

                current = self.register_module(
                    module_name=name,
                    module_id=module_id,
                    state=state or "UNKNOWN",
                    metadata=metadata,
                )

            current = dict(current)

            if state is not None:
                current["state"] = str(
                    state
                ).upper()

            if module_id is not None:
                current["module_id"] = str(
                    module_id
                )

            if healthy is not None:
                current["healthy"] = bool(
                    healthy
                )

            if active is not None:
                current["active"] = bool(
                    active
                )

            if ready is not None:
                current["ready"] = bool(
                    ready
                )

            if error is not None:
                current["error"] = str(
                    error
                )

            if metadata:

                current.setdefault(
                    "metadata",
                    {},
                ).update(
                    dict(metadata)
                )

            current["updated_at"] = time.time()

            TrackSystem._module_registry[
                name
            ] = current

            TrackSystem._state_sequence += 1

            current[
                "state_sequence"
            ] = TrackSystem._state_sequence

            TrackSystem._metrics[
                "states_updated"
            ] += 1

            TrackSystem._registry_generation += 1

        self._mirror_module_registry(
            current
        )

        self._emit(
            TRACK_MODULE_STATE,
            dict(current),
        )

        self._publish_system_state()

        return dict(current)

    # ======================================================
    # NODE STATE
    # ======================================================

    def update_node_state(
        self,
        node_id,
        state=None,
        *,
        healthy=None,
        active=None,
        ready=None,
        error=None,
        metadata=None,
    ):

        node_id = str(
            node_id or "NODE-UNKNOWN"
        )

        with TrackSystem._lock:

            current = TrackSystem._node_registry.get(
                node_id
            )

            if current is None:

                current = self.register_node(
                    node_id,
                    state=state or "UNKNOWN",
                    metadata=metadata,
                )

            current = dict(current)

            if state is not None:
                current["state"] = str(
                    state
                ).upper()

            if healthy is not None:
                current["healthy"] = bool(
                    healthy
                )

            if active is not None:
                current["active"] = bool(
                    active
                )

            if ready is not None:
                current["ready"] = bool(
                    ready
                )

            if error is not None:
                current["error"] = str(
                    error
                )

            if metadata:

                current.setdefault(
                    "metadata",
                    {},
                ).update(
                    dict(metadata)
                )

            current["updated_at"] = time.time()

            TrackSystem._node_registry[
                node_id
            ] = current

            TrackSystem._state_sequence += 1

            current[
                "state_sequence"
            ] = TrackSystem._state_sequence

            TrackSystem._metrics[
                "states_updated"
            ] += 1

            TrackSystem._registry_generation += 1

        self._mirror_node_registry(
            current
        )

        self._emit(
            TRACK_NODE_STATE,
            dict(current),
        )

        self._publish_system_state()

        return dict(current)

    # ======================================================
    # REGISTER + STATE COMBINED
    # ======================================================

    def register_module_state(
        self,
        module_name,
        *,
        module_id=None,
        version=None,
        path=None,
        state="ONLINE",
        healthy=True,
        active=True,
        ready=True,
        role=None,
        metadata=None,
    ):

        self.register_module(
            module_name=module_name,
            module_id=module_id,
            version=version,
            path=path,
            role=role,
            state=state,
            metadata=metadata,
        )

        return self.update_module_state(
            module_name,
            state,
            module_id=module_id,
            healthy=healthy,
            active=active,
            ready=ready,
            metadata=metadata,
        )

    # ======================================================
    # SNAPSHOT
    # ======================================================

    def get_module_states(self):

        with TrackSystem._lock:

            return {
                key: dict(value)
                for key, value
                in TrackSystem._module_registry.items()
            }

    def get_node_states(self):

        with TrackSystem._lock:

            return {
                key: dict(value)
                for key, value
                in TrackSystem._node_registry.items()
            }

    # ======================================================
    # QBIT SYSTEM STATE
    # ======================================================

    def build_qbit_system_state(self):

        modules = self.get_module_states()
        nodes = self.get_node_states()

        online_modules = 0
        healthy_modules = 0
        ready_modules = 0

        for item in modules.values():

            if item.get("active"):
                online_modules += 1

            if item.get("healthy", False):
                healthy_modules += 1

            if item.get("ready", False):
                ready_modules += 1

        online_nodes = 0
        healthy_nodes = 0
        ready_nodes = 0

        for item in nodes.values():

            if item.get("active"):
                online_nodes += 1

            if item.get("healthy", False):
                healthy_nodes += 1

            if item.get("ready", False):
                ready_nodes += 1

        context_id = None

        try:
            context_id = TrackContext.current()
        except Exception:
            pass

        event_bus_connected = bool(
            self.is_event_bus_connected
        )

        return {
            "state_id": (
                f"SYS-{uuid.uuid4().hex[:12]}"
            ),

            "state_sequence": (
                TrackSystem._state_sequence
            ),

            # --------------------------------------------------
            # SYSTEM
            # --------------------------------------------------

            "system": {
                "name": "SEED AI OS",
                "module": MODULE_NAME,
                "module_id": MODULE_ID,
                "track_system_version": MODULE_VERSION,
                "boot_complete": bool(
                    self._boot_complete
                ),
                "started": bool(
                    self._started
                ),
                "shutdown_requested": bool(
                    self._shutdown_requested
                ),
            },

            # --------------------------------------------------
            # EVENTBUS
            # --------------------------------------------------

            "event_bus": {
                "connected": event_bus_connected,
                "type": (
                    type(
                        self.event_bus
                    ).__name__
                    if self.event_bus is not None
                    else None
                ),
                "transport_authority": EVENT_TRANSPORT,
            },

            # --------------------------------------------------
            # TRACK
            # --------------------------------------------------

            "track": {
                "active_track_id": context_id,
                "queue_depth": self.queue_depth(),
                "active_packets": self.active_packet_count(),
                "channels": self.all_channels(),
            },

            # --------------------------------------------------
            # QBIT
            #
            # Qbit is explicitly transport.
            # It does NOT own execution.
            # --------------------------------------------------

            "qbit": {
                "enabled": bool(
                    TrackSystem._qbit_enabled
                ),
                "override": bool(
                    TrackSystem._qbit_override_enabled
                ),
                "transport_authority": (
                    QBIT_TRANSPORT_AUTHORITY
                ),
                "authority": (
                    COMMAND_AUTHORITY
                ),
                "execution_authority": (
                    QBIT_QUEUE_AUTHORITY
                ),
                "fallback_execution_queue": False,
                "independent_execution_authority": False,
            },

            # --------------------------------------------------
            # COGNITION
            # --------------------------------------------------

            "cognition": {
                "compute_authority": COMPUTE_AUTHORITY,
                "thought_packet_type": THOUGHT_PACKET_TYPE,
                "transformer_authority": (
                    TRANSFORMER_AUTHORITY
                ),
                "pipeline": [
                    QBIT_TRANSPORT_AUTHORITY,
                    QBIT_QUEUE_AUTHORITY,
                    COMPUTE_AUTHORITY,
                    THOUGHT_PACKET_TYPE,
                    TRANSFORMER_AUTHORITY,
                ],
            },

            # --------------------------------------------------
            # COMMAND
            # --------------------------------------------------

            "command": {
                "authority": COMMAND_AUTHORITY,
                "admission": COMMAND_ADMISSION,
                "sole_authority": True,
                "sole_admission_path": True,
                "track_system_execution": False,
            },

            # --------------------------------------------------
            # HEARTBEAT
            # --------------------------------------------------

            "heartbeat": {
                "authority": HEARTBEAT_AUTHORITY,
                "role": "LIVENESS_CONTROL_INPUT",
                "executes_commands": False,
                "owns_qbit_queue": False,
                "bypasses_command_authority": False,
            },

            # --------------------------------------------------
            # REGISTRY
            # --------------------------------------------------

            "registry": {
                "generation": (
                    TrackSystem._registry_generation
                ),
                "module_count": len(modules),
                "node_count": len(nodes),
            },

            # --------------------------------------------------
            # MODULE / NODE STATE
            # --------------------------------------------------

            "modules": modules,
            "nodes": nodes,

            # --------------------------------------------------
            # SUMMARY
            # --------------------------------------------------

            "summary": {
                "module_count": len(modules),
                "online_modules": online_modules,
                "healthy_modules": healthy_modules,
                "ready_modules": ready_modules,

                "node_count": len(nodes),
                "online_nodes": online_nodes,
                "healthy_nodes": healthy_nodes,
                "ready_nodes": ready_nodes,

                "channel_count": len(
                    self.channels
                ),
            },

            # --------------------------------------------------
            # ARCHITECTURAL CONTRACT
            # --------------------------------------------------

            "authority_model": {
                "track": TRACK_AUTHORITY,
                "event_transport": EVENT_TRANSPORT,
                "qbit_transport": QBIT_TRANSPORT_AUTHORITY,
                "qbit_runtime": QBIT_QUEUE_AUTHORITY,
                "compute": COMPUTE_AUTHORITY,
                "thought_packet": THOUGHT_PACKET_TYPE,
                "transformer": TRANSFORMER_AUTHORITY,
                "command": COMMAND_AUTHORITY,
                "command_admission": COMMAND_ADMISSION,
                "heartbeat": HEARTBEAT_AUTHORITY,
                "hud": HUD_AUTHORITY,
            },

            # --------------------------------------------------
            # METADATA
            # --------------------------------------------------

            "metadata": {
                "source": MODULE_NAME,
                "module_id": MODULE_ID,
                "version": MODULE_VERSION,
                "cabi_id": CABI_ID,
                "timestamp": time.time(),
            },
        }

    # ======================================================
    # PUBLISH SYSTEM STATE
    # ======================================================

    def _publish_system_state(self):

        if not self.is_event_bus_connected:
            return False

        payload = self.build_qbit_system_state()

        TrackSystem._metrics[
            "state_snapshots"
        ] += 1

        # --------------------------------------------------
        # Primary authoritative state event.
        # --------------------------------------------------

        self._emit(
            TRACK_SYSTEM_STATE,
            payload,
        )

        # --------------------------------------------------
        # Explicit registry synchronization event.
        # --------------------------------------------------

        self._emit(
            TRACK_REGISTRY_SYNC,
            payload,
        )

        return payload

    # ======================================================
    # QBIT STATE REQUEST
    # ======================================================

    def emit_qbit_state(self):

        payload = self.build_qbit_system_state()

        return self._emit(
            TRACK_SYSTEM_STATE,
            payload,
        )


    # ======================================================
    # EXTERNAL REGISTRY MIRROR
    # ======================================================

    def _mirror_module_registry(
        self,
        entry,
    ):

        registry = self.registry

        if registry is None:
            return False

        methods = (
            "register_module",
            "register",
            "add_module",
            "register_node",
        )

        for method_name in methods:

            method = getattr(
                registry,
                method_name,
                None,
            )

            if not callable(method):
                continue

            # --------------------------------------------------
            # Full dictionary form.
            # --------------------------------------------------

            try:

                result = method(
                    dict(entry)
                )

                return result

            except TypeError:
                pass

            except Exception as exc:

                logger.debug(
                    "[TrackSystem] Registry mirror failed: %s",
                    exc,
                )

            # --------------------------------------------------
            # Keyword form.
            # --------------------------------------------------

            try:

                result = method(
                    module_name=entry[
                        "module_name"
                    ],
                    module_id=entry[
                        "module_id"
                    ],
                    state=entry[
                        "state"
                    ],
                    metadata=entry.get(
                        "metadata",
                        {},
                    ),
                )

                return result

            except Exception:
                pass

        return False

    def _mirror_node_registry(
        self,
        entry,
    ):

        registry = self.node_registry or self.registry

        if registry is None:
            return False

        methods = (
            "register_node",
            "register",
            "add_node",
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

                return method(
                    dict(entry)
                )

            except TypeError:
                pass

            except Exception:
                pass

            try:

                return method(
                    node_id=entry[
                        "node_id"
                    ],
                    state=entry[
                        "state"
                    ],
                    metadata=entry.get(
                        "metadata",
                        {},
                    ),
                )

            except Exception:
                pass

        return False

    # ======================================================
    # EVENTBUS
    # ======================================================

    def set_event_bus(
        self,
        event_bus,
    ):

        if event_bus is None:
            self.detach_event_bus()
            return False

        if isinstance(event_bus, type):

            try:
                event_bus = event_bus()
            except Exception as exc:

                logger.error(
                    "[TrackSystem] Unable to instantiate EventBus: %s",
                    exc,
                )

                return False

        emit_method = getattr(
            event_bus,
            "emit",
            None,
        )

        if not callable(emit_method):

            emit_method = getattr(
                event_bus,
                "_emit",
                None,
            )

        if not callable(emit_method):

            logger.error(
                "[TrackSystem] EventBus has no usable emit method"
            )

            self._event_bus_attached = False
            TrackSystem._event_bus = None

            return False

        if (
            TrackSystem._event_bus is not None
            and TrackSystem._event_bus is not event_bus
        ):

            self._detach_event_subscriptions(
                TrackSystem._event_bus
            )

        TrackSystem._event_bus = event_bus
        self._event_bus_attached = True

        self._attach_feedback_subscriptions(
            event_bus
        )

        logger.info(
            "[TrackSystem] EventBus attached | %s",
            type(event_bus).__name__,
        )

        # --------------------------------------------------
        # CRITICAL:
        #
        # As soon as EventBus becomes available, publish
        # everything TrackSystem already knows.
        #
        # This is the missing state handoff that QbitDialer
        # needs.
        # --------------------------------------------------

        self._publish_registry_snapshot()

        return True

    # ======================================================

    def detach_event_bus(self):

        old_bus = TrackSystem._event_bus

        if old_bus is not None:
            self._detach_event_subscriptions(
                old_bus
            )

        self._event_bus_attached = False
        TrackSystem._event_bus = None

        logger.info(
            "[TrackSystem] EventBus detached"
        )

        return True

    # ======================================================
    # REGISTRY SNAPSHOT
    # ======================================================

    def _publish_registry_snapshot(self):

        payload = self.build_qbit_system_state()

        self._emit(
            TRACK_REGISTRY_SYNC,
            payload,
        )

        self._emit(
            TRACK_SYSTEM_STATE,
            payload,
        )

        return payload

    # ======================================================
    # SUBSCRIPTIONS
    # ======================================================

    def _attach_feedback_subscriptions(
        self,
        event_bus,
    ):

        TrackSystem._event_bus_subscription_handles = []

        candidates = (
            "subscribe",
            "on",
            "register",
            "add_listener",
            "add_subscriber",
        )

        subscribe_method = None

        for name in candidates:

            method = getattr(
                event_bus,
                name,
                None,
            )

            if callable(method):

                subscribe_method = method
                break

        if subscribe_method is None:
            return False

        registrations = (
            (
                TRACK_QBIT_RESULT,
                self.receive_qbit_feedback,
            ),
            (
                TRACK_QBIT_FEEDBACK,
                self.receive_qbit_feedback,
            ),
            (
                TRACK_FEEDBACK,
                self.receive_feedback,
            ),
        )

        attached = 0

        for event_name, callback in registrations:

            handle = self._safe_bus_subscribe(
                subscribe_method,
                event_name,
                callback,
            )

            if handle is not None:

                TrackSystem._event_bus_subscription_handles.append(
                    handle
                )

                attached += 1

        return attached > 0

    # ======================================================

    @staticmethod
    def _safe_bus_subscribe(
        subscribe_method,
        event_name,
        callback,
    ):

        if not callable(subscribe_method):
            return None

        try:

            result = subscribe_method(
                event_name,
                callback,
            )

            return (
                result
                if result is not None
                else True
            )

        except TypeError:
            pass

        except Exception:
            return None

        try:

            result = subscribe_method(
                event=event_name,
                callback=callback,
            )

            return (
                result
                if result is not None
                else True
            )

        except Exception:
            pass

        try:

            result = subscribe_method(
                event_name,
                handler=callback,
            )

            return (
                result
                if result is not None
                else True
            )

        except Exception:
            return None

    # ======================================================

    def _detach_event_subscriptions(
        self,
        event_bus,
    ):

        if event_bus is None:
            return

        for handle in list(
            TrackSystem._event_bus_subscription_handles
        ):

            try:

                unsubscribe = getattr(
                    handle,
                    "unsubscribe",
                    None,
                )

                if callable(unsubscribe):
                    unsubscribe()

            except Exception:
                pass

        TrackSystem._event_bus_subscription_handles = []

        unsubscribe = getattr(
            event_bus,
            "unsubscribe",
            None,
        )

        if callable(unsubscribe):

            for event_name, callback in (
                (
                    TRACK_QBIT_RESULT,
                    self.receive_qbit_feedback,
                ),
                (
                    TRACK_QBIT_FEEDBACK,
                    self.receive_qbit_feedback,
                ),
                (
                    TRACK_FEEDBACK,
                    self.receive_feedback,
                ),
            ):

                try:

                    unsubscribe(
                        event_name,
                        callback,
                    )

                except Exception:
                    pass

    # ======================================================
    # SAFE EMIT
    # ======================================================

    @staticmethod
    def _safe_bus_emit(
        event_bus,
        event_type,
        payload,
    ):

        if event_bus is None:
            return False

        emit = getattr(
            event_bus,
            "emit",
            None,
        )

        if not callable(emit):

            emit = getattr(
                event_bus,
                "_emit",
                None,
            )

        if not callable(emit):
            return False

        try:

            return emit(
                event_type,
                payload,
            )

        except TypeError:
            pass

        except Exception as exc:

            logger.debug(
                "[TrackSystem] EventBus emit failed: %s",
                exc,
            )

        try:

            return emit(
                event=event_type,
                payload=payload,
            )

        except TypeError:
            pass

        except Exception:
            pass

        try:

            return emit(
                {
                    "type": event_type,
                    "event_type": event_type,
                    "payload": payload,
                }
            )

        except Exception:
            return False

    # ======================================================
    # CHANNEL MANAGEMENT
    # ======================================================

    def register_channel(
        self,
        name,
        *,
        controller="SYSTEM",
        metadata=None,
    ):

        name = str(
            name or "GEN"
        ).upper()

        metadata = dict(
            metadata or {}
        )

        try:

            ChannelID.register(
                name,
                controller=controller,
                metadata=metadata,
            )

        except Exception as exc:

            logger.debug(
                "[TrackSystem] ChannelID registration warning: %s",
                exc,
            )

        self.channels[name] = {
            "controller": controller,
            "metadata": metadata,
            "registered_at": time.time(),
        }

        self._publish_system_state()

        return name

    def all_channels(self):
        return dict(self.channels)

    def all_overlays(self):
        return dict(self._overlays)

    # ======================================================
    # LIFECYCLE
    # ======================================================

    def _system_boot_complete(self):

        try:

            getter = getattr(
                TrackContext,
                "system_state",
                None,
            )

            if callable(getter):

                state = getter() or {}

                if isinstance(state, dict):

                    if state.get(
                        "shutdown_requested",
                        False,
                    ):
                        return False

                    return bool(
                        state.get(
                            "boot_complete",
                            False,
                        )
                    )

        except Exception:
            pass

        return (
            bool(self._boot_complete)
            and not bool(
                self._shutdown_requested
            )
        )

    def set_boot_complete(
        self,
        value=True,
    ):

        self._boot_complete = bool(
            value
        )

        if self._boot_complete:
            self._shutdown_requested = False

        if not self._boot_complete:

            self._started = False

            self.update_module_state(
                MODULE_NAME,
                "WAITING",
                active=False,
                ready=False,
            )

            return False

        if self._shutdown_requested:
            return False

        self.update_module_state(
            MODULE_NAME,
            "READY",
            active=True,
            ready=True,
        )

        if (
            self._start_requested
            and not self._started
        ):
            self._activate_runtime()

        return self._started

    def _activate_runtime(self):

        if (
            self._shutdown_requested
            or not self._system_boot_complete()
        ):
            return False

        if self._started:
            return True

        self._started = True

        self.update_module_state(
            MODULE_NAME,
            "ONLINE",
            active=True,
            ready=True,
            healthy=True,
        )

        logger.info(
            "[TrackSystem] ONLINE | event_bus=%s",
            self.is_event_bus_connected,
        )

        self._publish_system_state()

        return True

    def _runtime_ready(self):

        if (
            self._shutdown_requested
            or not self._start_requested
        ):
            return False

        if not self._system_boot_complete():
            return False

        return self._activate_runtime()

    def start(self):

        if self._shutdown_requested:
            return False

        self._start_requested = True

        if not self._system_boot_complete():

            logger.info(
                "[TrackSystem] START DEFERRED | waiting for SEED BOOT COMPLETE"
            )

            return False

        return self._activate_runtime()

    def stop(
        self,
        *,
        clear_context=False,
    ):

        self._started = False
        self._start_requested = False
        self._shutdown_requested = True

        with self._lock:
            self._station_queue.clear()

        self.update_module_state(
            MODULE_NAME,
            "OFFLINE",
            active=False,
            ready=False,
        )

        if clear_context:

            try:
                TrackContext.clear()
            except Exception:
                pass

        logger.info(
            "[TrackSystem] OFFLINE"
        )

        return True

    # ======================================================
    # CALL COMPATIBILITY
    # ======================================================

    def __call__(
        self,
        *args,
        **kwargs,
    ):

        if len(args) >= 2:

            return self.track(
                args[0],
                args[1],
                **kwargs,
            )

        if (
            "channel" in kwargs
            and "state" in kwargs
        ):

            channel = kwargs.pop(
                "channel"
            )

            state = kwargs.pop(
                "state"
            )

            return self.track(
                channel,
                state,
                **kwargs,
            )

        return None

    # ======================================================
    # TRACK
    # ======================================================

    def track(
        self,
        channel,
        state="ENTER",
        *,
        priority="MED",
        skill=None,
        parent_id=None,
        metadata=None,
        hud_id=None,
        dev_line=None,
        **kwargs,
    ):

        if not self._runtime_ready():
            return False

        state_upper = str(
            state or "PROCESS"
        ).upper()

        if state_upper in {
            "ENTER",
            "BEGIN",
            "START",
        }:

            return self.begin(
                channel=channel,
                skill=skill,
                priority=priority,
                parent_id=parent_id,
                metadata={
                    **dict(
                        metadata or {}
                    ),
                    "state": state_upper,
                    **kwargs,
                },
                hud_id=hud_id,
                dev_line=dev_line,
            )

        if state_upper in {
            "EXIT",
            "END",
            "COMPLETE",
        }:

            self.emit_lifecycle_event(
                channel=channel,
                state="COMPLETE",
                priority=priority,
                metadata=metadata,
                dev_line=dev_line,
            )

            return self.end()

        self.emit_lifecycle_event(
            channel=channel,
            state=state_upper,
            priority=priority,
            metadata=metadata,
            dev_line=dev_line,
        )

        return TrackContext.current()

    # ======================================================
    # BEGIN
    # ======================================================

    def begin(
        self,
        *,
        channel,
        skill=None,
        priority="MED",
        parent_id=None,
        metadata=None,
        hud_id=None,
        dev_line=None,
    ):

        if not self._runtime_ready():
            return False

        try:

            channel = self._validate_channel(
                channel
            )

            norm_priority = self._normalize_priority(
                priority
            )

            ctx_parent = TrackContext.current()

            parent_id = (
                parent_id
                or ctx_parent
            )

            hud_id = (
                hud_id
                or
                f"SS-HUD-{uuid.uuid4().hex[:8]}"
            )

            metadata = dict(
                metadata or {}
            )

            metadata.setdefault(
                "channel",
                channel,
            )

            metadata.setdefault(
                "state",
                "ENTER",
            )

            metadata.setdefault(
                "source",
                MODULE_NAME,
            )

            metadata.setdefault(
                "module",
                MODULE_ID,
            )

            track_id = TrackIDManager().new(
                channel=channel,
                skill=skill,
                parent_id=parent_id,
                priority=norm_priority,
                actuator_bridge=False,
                metadata=metadata,
                domain_override=None,
                reasoning_input=None,
                qbit_callback=None,
            )

            TrackContext.set(
                track_id,
                hud_id=hud_id,
            )

            with TrackSystem._lock:

                TrackSystem._metrics[
                    "tracks_started"
                ] += 1

            payload = {
                "track_id": track_id,
                "parent_id": parent_id,
                "channel": channel,
                "skill": skill,
                "state": "ENTER",
                "priority": norm_priority,
                "hud_id": hud_id,
                "metadata": metadata,
                "dev_line": dev_line,
                "source": MODULE_NAME,
                "module": MODULE_ID,
                "timestamp": time.time(),
            }

            self._emit(
                TRACK_BEGIN,
                payload,
            )

            return track_id

        except Exception as exc:

            with TrackSystem._lock:
                TrackSystem._metrics[
                    "errors"
                ] += 1

            err = TrackSystemError(
                f"BEGIN failed: {exc}",
                event_bus=self.event_bus,
                storage_root=self.storage_root,
                priority="HIGH",
                track_id=parent_id,
                hud_id=hud_id,
            )

            err.execute()

            raise

    # ======================================================
    # END
    # ======================================================

    def end(self):

        track_id = TrackContext.current()

        if track_id is None:
            return False

        try:

            self._emit(
                TRACK_END,
                {
                    "track_id": track_id,
                    "source": MODULE_NAME,
                    "module": MODULE_ID,
                    "timestamp": time.time(),
                },
            )

            with TrackSystem._lock:

                TrackSystem._metrics[
                    "tracks_completed"
                ] += 1

        finally:

            TrackContext.clear()

        return True

    # ======================================================
    # LIFECYCLE EVENT
    # ======================================================

    def emit_lifecycle_event(
        self,
        *,
        channel,
        state,
        priority="MED",
        metadata=None,
        dev_line=None,
    ):

        channel = self._validate_channel(
            channel
        )

        payload = {
            "track_id": TrackContext.current(),
            "channel": channel,
            "state": state,
            "priority": self._normalize_priority(
                priority
            ),
            "metadata": dict(
                metadata or {}
            ),
            "dev_line": dev_line,
            "source": MODULE_NAME,
            "module": MODULE_ID,
            "timestamp": time.time(),
        }

        self._emit(
            TRACK_EMIT,
            payload,
        )

        return payload["track_id"]

    # ======================================================
    # DATA FLOW
    # ======================================================

    def emit(
        self,
        *,
        channel,
        state,
        stage,
        payload,
        input_type,
        output_type,
        priority="MED",
        metadata=None,
        dev_line=None,
    ):

        if not self._runtime_ready():
            return False

        channel = self._validate_channel(
            channel
        )

        track_id = TrackContext.current()

        if not track_id:

            err = TrackSystemError(
                "Emit without active track",
                event_bus=self.event_bus,
                storage_root=self.storage_root,
                priority="CRITICAL",
            )

            with TrackSystem._lock:
                TrackSystem._metrics[
                    "errors"
                ] += 1

            err.execute()

            raise err

        self._throttle(
            channel,
            priority,
        )

        numeric_payload = (
            self._convert_payload_to_number(
                payload
            )
        )

        packet = {
            "packet_id": self._next_packet_id(),
            "sequence": self._next_packet_sequence(),
            "track_id": track_id,
            "parent_id": (
                dict(metadata or {})
            ).get("parent_id"),
            "hud_id": (
                self._get_hud_id()
                or f"HUD-{uuid.uuid4().hex[:6]}"
            ),
            "channel": channel,
            "state": state,
            "stage": stage,
            "input_type": input_type,
            "output_type": output_type,
            "skill": (dict(metadata or {})).get("skill"),
            "command": (dict(metadata or {})).get("command"),
            "command_type": (dict(metadata or {})).get("command_type"),
            "payload": payload,
            "numeric_payload": numeric_payload,
            "priority": self._normalize_priority(
                priority
            ),
            "metadata": {
                **dict(metadata or {}),
                "track_system_version": MODULE_VERSION,
                "flow_direction": "TRACK_TO_QBIT",
                "qbit_authority": "QbitDialer",
            },
            "dev_line": (
                dev_line
                or f"DEV-{uuid.uuid4().hex[:6]}"
            ),
            "channel_labels": self._generate_channel_labels(
                channel,
                state,
                stage,
            ),
            "timestamp": time.time(),
            "source": MODULE_NAME,
            "module": MODULE_ID,
            "flow": {
                "source": "TrackSystem",
                "destination": "QbitDialer",
                "execution_authority": "QbitQueueLoop",
                "feedback_destination": "TrackSystem",
            },

            # ------------------------------------------------
            # THIS IS THE NEW STATE FEED.
            # ------------------------------------------------
            "system_state": self.build_qbit_system_state(),
        }

        with self._lock:

            self._station_queue.append(
                packet
            )

            self._active_packets[
                packet["packet_id"]
            ] = packet

            TrackSystem._metrics[
                "packets_emitted"
            ] += 1

        self._emit(
            TRACK_PACKET,
            packet,
        )

        self._notify_hud(
            packet
        )

        if self._qbit_enabled:
            self.request_qbit_processing(
                packet
            )

        return packet

    # ======================================================
    # QBIT REQUEST
    # ======================================================

    def request_qbit_processing(
        self,
        packet,
    ):

        if not self._runtime_ready():
            return False

        if not TrackSystem._qbit_enabled:
            return False

        if not isinstance(
            packet,
            dict,
        ):
            return False

        request = self._build_qbit_request(
            packet
        )

        result = self._emit(
            TRACK_QBIT_REQUEST,
            request,
        )

        with TrackSystem._lock:
            TrackSystem._metrics[
                "qbit_requests"
            ] += 1

        return result

    # ======================================================
    # QBIT REQUEST BUILDER
    # ======================================================

    @staticmethod
    def _build_qbit_request(
        packet,
    ):

        return {
            "request_id": (
                f"QREQ-{uuid.uuid4().hex[:12]}"
            ),
            "packet_id": packet.get(
                "packet_id"
            ),
            "sequence": packet.get(
                "sequence"
            ),
            "track_id": packet.get(
                "track_id"
            ),
            "parent_id": packet.get(
                "parent_id"
            ),
            "channel": packet.get(
                "channel"
            ),
            "state": packet.get(
                "state"
            ),
            "stage": packet.get(
                "stage"
            ),
            "payload": packet.get(
                "payload"
            ),
            "numeric_payload": packet.get(
                "numeric_payload"
            ),
            "input_type": packet.get(
                "input_type"
            ),
            "output_type": packet.get(
                "output_type"
            ),
            "skill": packet.get("skill"),
            "command": packet.get("command"),
            "command_type": packet.get("command_type"),
            "priority": packet.get(
                "priority",
                PRIORITY_LEVELS["MED"],
            ),
            "metadata": dict(
                packet.get(
                    "metadata",
                    {},
                )
            ),
            "system_state": packet.get(
                "system_state",
                {},
            ),
            "source": MODULE_NAME,
            "destination": "QbitDialer",
            "execution_authority": "QbitQueueLoop",
            "timestamp": time.time(),
        }

    # ======================================================
    # EVENT OUTPUT
    # ======================================================

    def _emit(
        self,
        event_type,
        payload,
    ):

        if not self.is_event_bus_connected:
            return False

        try:

            return self._safe_bus_emit(
                self.event_bus,
                event_type,
                payload,
            )

        except Exception as exc:

            logger.warning(
                "[TrackSystem] EventBus emission failed | event=%s | error=%s",
                event_type,
                exc,
            )

            return False

    # ======================================================
    # QBIT AUTHORITY BRIDGE
    # ======================================================

    @classmethod
    def enable_qbit_override(
        cls,
        value: bool,
    ):

        cls._qbit_override_enabled = bool(
            value
        )

        return cls._qbit_override_enabled

    @classmethod
    def is_qbit_override(cls):
        return cls._qbit_override_enabled

    def set_qbit_enabled(
        self,
        enabled=True,
    ):

        TrackSystem._qbit_enabled = bool(
            enabled
        )

        return TrackSystem._qbit_enabled

    # ======================================================
    # QBIT FEEDBACK
    # ======================================================

    def receive_qbit_feedback(
        self,
        feedback=None,
        *args,
        **kwargs,
    ):

        feedback = self._normalize_feedback(
            feedback,
            *args,
            **kwargs,
        )

        if not feedback:
            return False

        packet_id = feedback.get(
            "packet_id"
        )

        success = feedback.get(
            "success"
        )

        if success is None:

            status = str(
                feedback.get(
                    "status",
                    "",
                )
            ).upper()

            success = status in {
                "OK",
                "SUCCESS",
                "COMPLETE",
                "COMPLETED",
                "DONE",
            }

        success = bool(
            success
        )

        self._last_qbit_result = dict(
            feedback
        )

        with TrackSystem._lock:

            TrackSystem._metrics[
                "qbit_results"
            ] += 1

            TrackSystem._metrics[
                "feedback_received"
            ] += 1

        original_packet = None

        if packet_id:

            with self._lock:

                original_packet = (
                    self._active_packets.get(
                        packet_id
                    )
                )

        if original_packet:

            for key in (
                "channel",
                "stage",
                "input_type",
                "output_type",
                "priority",
            ):

                feedback.setdefault(
                    key,
                    original_packet.get(
                        key
                    ),
                )

        skill = (
            feedback.get("skill")
            or feedback.get("stage")
            or (
                original_packet.get(
                    "metadata",
                    {},
                ).get("skill")
                if original_packet
                else None
            )
        )

        if success:

            self.record_success(
                skill or "default",
                int(
                    feedback.get(
                        "success_percent",
                        100,
                    )
                ),
            )

        else:

            self.record_failure(
                skill or "default"
            )

        normalized = self._build_normalized_feedback(
            feedback=feedback,
            success=success,
            original_packet=original_packet,
        )

        self._last_feedback = normalized

        self._emit(
            TRACK_FEEDBACK,
            normalized,
        )

        self._notify_feedback(
            normalized
        )

        if packet_id:

            with self._lock:

                self._active_packets.pop(
                    packet_id,
                    None,
                )

        return normalized

    # ======================================================
    # FEEDBACK
    # ======================================================

    def receive_feedback(
        self,
        feedback=None,
        *args,
        **kwargs,
    ):

        return self.receive_qbit_feedback(
            feedback,
            *args,
            **kwargs,
        )

    @staticmethod
    def _normalize_feedback(
        feedback=None,
        *args,
        **kwargs,
    ):

        if feedback is None and args:
            feedback = args[0]

        if isinstance(
            feedback,
            dict,
        ):

            if (
                "payload" in feedback
                and isinstance(
                    feedback.get(
                        "payload"
                    ),
                    dict,
                )
                and not (
                    "track_id" in feedback
                    or "packet_id" in feedback
                )
            ):

                feedback = dict(
                    feedback["payload"]
                )

            else:

                feedback = dict(
                    feedback
                )

        elif feedback is None:

            feedback = {}

        else:

            feedback = {
                "result": feedback
            }

        if kwargs:
            feedback.update(kwargs)

        return feedback

    # ======================================================
    # NORMALIZED FEEDBACK
    # ======================================================

    def _build_normalized_feedback(
        self,
        *,
        feedback,
        success,
        original_packet,
    ):

        packet_id = (
            feedback.get("packet_id")
            or (
                original_packet.get(
                    "packet_id"
                )
                if original_packet
                else None
            )
        )

        track_id = (
            feedback.get("track_id")
            or (
                original_packet.get(
                    "track_id"
                )
                if original_packet
                else None
            )
        )

        return {
            "feedback_id": (
                f"FB-{uuid.uuid4().hex[:12]}"
            ),
            "sequence": self._next_feedback_sequence(),
            "packet_id": packet_id,
            "track_id": track_id,
            "parent_id": feedback.get(
                "parent_id"
            ),
            "channel": feedback.get(
                "channel"
            ),
            "stage": feedback.get(
                "stage"
            ),
            "success": bool(
                success
            ),
            "success_percent": int(
                feedback.get(
                    "success_percent",
                    100 if success else 0,
                )
            ),
            "status": feedback.get(
                "status",
                "SUCCESS"
                if success
                else "FAILED",
            ),
            "result": feedback.get(
                "result"
            ),
            "output": feedback.get(
                "output"
            ),
            "numeric_result": (
                self._convert_payload_to_number(
                    feedback.get(
                        "result"
                    )
                )
                if feedback.get(
                    "result"
                ) is not None
                else None
            ),
            "metadata": dict(
                feedback.get(
                    "metadata",
                    {},
                )
            ),
            "source": feedback.get(
                "source",
                "QbitDialer",
            ),
            "destination": MODULE_NAME,
            "timestamp": time.time(),
        }

    # ======================================================
    # FEEDBACK CALLBACKS
    # ======================================================

    @classmethod
    def register_feedback_callback(
        cls,
        callback: Callable,
    ):

        if not callable(callback):
            return False

        if callback not in cls._feedback_callbacks:
            cls._feedback_callbacks.append(
                callback
            )

        return True

    @classmethod
    def unregister_feedback_callback(
        cls,
        callback: Callable,
    ):

        try:

            cls._feedback_callbacks.remove(
                callback
            )

            return True

        except ValueError:
            return False

    @classmethod
    def _notify_feedback(
        cls,
        feedback,
    ):

        for callback in list(
            cls._feedback_callbacks
        ):

            try:
                callback(feedback)
            except Exception as exc:

                logger.warning(
                    "[TrackSystem] Feedback callback failed: %s",
                    exc,
                )

    # ======================================================
    # HUD
    # ======================================================

    @staticmethod
    def register_hud_sync(
        callback: Callable,
    ):

        if not callable(callback):
            return False

        if callback not in TrackSystem._hud_sync_callbacks:
            TrackSystem._hud_sync_callbacks.append(
                callback
            )

        return True

    @staticmethod
    def unregister_hud_sync(
        callback: Callable,
    ):

        try:

            TrackSystem._hud_sync_callbacks.remove(
                callback
            )

            return True

        except ValueError:
            return False

    @staticmethod
    def _notify_hud(
        packet,
    ):

        for callback in list(
            TrackSystem._hud_sync_callbacks
        ):

            try:
                callback(packet)
            except Exception as exc:

                logger.warning(
                    "[HUD SYNC] Callback failed: %s",
                    exc,
                )

    # ======================================================
    # HUD ID
    # ======================================================

    @staticmethod
    def _get_hud_id():

        try:

            value = getattr(
                TrackContext,
                "hud_id",
                None,
            )

            if callable(value):
                value = value()

            if value is not None:
                return value

        except Exception:
            pass

        for name in (
            "get_hud_id",
            "current_hud_id",
        ):

            try:

                method = getattr(
                    TrackContext,
                    name,
                    None,
                )

                if callable(method):

                    value = method()

                    if value:
                        return value

            except Exception:
                pass

        return None

    # ======================================================
    # PAYLOAD NUMBER
    # ======================================================

    @staticmethod
    def _convert_payload_to_number(
        payload: Any,
    ) -> int:

        if payload is None:
            return 0

        if isinstance(payload, bool):
            return int(payload)

        if isinstance(
            payload,
            (int, float),
        ):

            try:
                return int(payload)
            except Exception:
                return 0

        if isinstance(
            payload,
            complex,
        ):

            return int(abs(payload))

        if isinstance(
            payload,
            str,
        ):

            return sum(
                ord(c)
                for c in payload
            )

        if isinstance(
            payload,
            dict,
        ):

            return sum(
                TrackSystem._convert_payload_to_number(
                    value
                )
                for value in payload.values()
            )

        if isinstance(
            payload,
            (
                list,
                tuple,
                set,
            ),
        ):

            return sum(
                TrackSystem._convert_payload_to_number(
                    value
                )
                for value in payload
            )

        return 0

    # ======================================================
    # CHANNEL LABELS
    # ======================================================

    @staticmethod
    def _generate_channel_labels(
        channel,
        state,
        stage,
    ):

        return {
            "channel": str(channel),
            "state": str(state),
            "stage": str(stage),
            "dev_label": (
                f"{channel}-"
                f"{stage}-"
                f"{uuid.uuid4().hex[:4]}"
            ),
        }

    # ======================================================
    # INITIAL QBIT STATE
    # ======================================================

    def get_initial_qbit_state(self):

        default_state = (
            1 + 0j,
            0 + 0j,
        )

        norm = sum(
            abs(x) ** 2
            for x in default_state
        ) ** 0.5

        if norm == 0:
            raise ValueError(
                "TrackSystem returned zero vector for initial Qbit state"
            )

        return tuple(
            x / norm
            for x in default_state
        )

    # ======================================================
    # LEARNING
    # ======================================================

    @classmethod
    def record_success(
        cls,
        skill,
        success=100,
    ):

        key = skill or "default"

        matrix = cls._skill_matrix[key]

        matrix["success"] = max(
            0,
            min(
                100,
                int(success),
            ),
        )

        matrix["tracks"] += 1
        matrix["last_success"] = time.time()

        return dict(matrix)

    @classmethod
    def record_failure(
        cls,
        skill,
    ):

        key = skill or "default"

        matrix = cls._skill_matrix[key]

        matrix["failures"] += 1
        matrix["last_failure"] = time.time()

        return dict(matrix)

    @classmethod
    def get_skill_matrix(cls):

        return {
            key: dict(value)
            for key, value
            in cls._skill_matrix.items()
        }

    # ======================================================
    # QUEUE
    # ======================================================

    @classmethod
    def queue_depth(cls):

        with cls._lock:
            return len(
                cls._station_queue
            )

    @classmethod
    def drain_queue(cls):

        packets = []

        with cls._lock:

            while cls._station_queue:
                packets.append(
                    cls._station_queue.popleft()
                )

        return packets

    @classmethod
    def peek_queue(
        cls,
        limit=10,
    ):

        try:
            limit = max(
                0,
                int(limit),
            )
        except Exception:
            limit = 10

        with cls._lock:

            return list(
                cls._station_queue
            )[:limit]

    # ======================================================
    # ACTIVE PACKETS
    # ======================================================

    def get_active_packet(
        self,
        packet_id,
    ):

        if not packet_id:
            return None

        with self._lock:

            packet = self._active_packets.get(
                packet_id
            )

        return (
            dict(packet)
            if packet
            else None
        )

    def active_packet_count(self):

        with self._lock:
            return len(
                self._active_packets
            )

    # ======================================================
    # STATION HANDOFF
    # ======================================================

    @staticmethod
    def _dispatch_qbit():

        with TrackSystem._lock:

            if not TrackSystem._station_queue:
                return False

            packet = (
                TrackSystem._station_queue.popleft()
            )

            instance = TrackSystem._instance

        if instance is None:
            return False

        try:

            return instance.request_qbit_processing(
                packet
            )

        except Exception as exc:

            logger.exception(
                "[STATION → QBIT] Handoff failed"
            )

            with TrackSystem._lock:
                TrackSystem._metrics[
                    "errors"
                ] += 1

            err = TrackSystemError(
                f"Qbit handoff failed: {exc}",
                event_bus=instance.event_bus,
                storage_root=instance.storage_root,
                priority="HIGH",
                track_id=packet.get(
                    "track_id"
                ),
                hud_id=packet.get(
                    "hud_id"
                ),
            )

            err.execute()

            return False

    def dispatch_next(self):

        if not self._runtime_ready():
            return False

        return self._dispatch_qbit()

    # ======================================================
    # METRICS
    # ======================================================

    @classmethod
    def metrics(cls):

        with cls._lock:
            return dict(
                cls._metrics
            )

    # ======================================================
    # HEALTH
    # ======================================================

    def health(self):

        metrics = self.metrics()

        return {
            "status": (
                "ONLINE"
                if self._started
                else "OFFLINE"
            ),
            "module": MODULE_ID,
            "version": MODULE_VERSION,
            "event_bus_connected": (
                self.is_event_bus_connected
            ),
            "qbit_enabled": (
                TrackSystem._qbit_enabled
            ),
            "qbit_override": (
                TrackSystem._qbit_override_enabled
            ),
            "queue_depth": self.queue_depth(),
            "active_packets": self.active_packet_count(),
            "channels": len(
                self.channels
            ),
            "modules": len(
                TrackSystem._module_registry
            ),
            "nodes": len(
                TrackSystem._node_registry
            ),
            "feedback_listeners": len(
                TrackSystem._feedback_callbacks
            ),
            "hud_listeners": len(
                TrackSystem._hud_sync_callbacks
            ),
            "metrics": metrics,
            "timestamp": time.time(),
        }

    # ======================================================
    # RECOVERY
    # ======================================================

    def recovery_event(
        self,
        *,
        reason,
        track_id=None,
        priority="HIGH",
        metadata=None,
    ):

        if not self._runtime_ready():
            return False

        payload = {
            "recovery_id": (
                f"REC-{uuid.uuid4().hex[:12]}"
            ),
            "track_id": (
                track_id
                or TrackContext.current()
            ),
            "reason": str(reason),
            "priority": self._normalize_priority(
                priority
            ),
            "metadata": dict(
                metadata or {}
            ),
            "source": MODULE_NAME,
            "timestamp": time.time(),
        }

        with TrackSystem._lock:
            TrackSystem._metrics[
                "recovery_events"
            ] += 1

        self._emit(
            TRACK_RECOVERY,
            payload,
        )

        return payload

    # ======================================================
    # INTERNAL
    # ======================================================

    @staticmethod
    def _normalize_priority(
        priority,
    ):

        if isinstance(priority, int):

            return max(
                0,
                min(
                    100,
                    priority,
                ),
            )

        return PRIORITY_LEVELS.get(
            str(
                priority or "MED"
            ).upper(),
            PRIORITY_LEVELS["MED"],
        )

    @staticmethod
    def _validate_channel(
        channel,
    ):

        channel = str(
            channel or "GEN"
        ).upper()

        try:
            ChannelID.next(channel)
        except Exception:
            pass

        return channel

    @staticmethod
    def _throttle(
        channel,
        priority,
    ):

        priority_name = str(
            priority or "MED"
        ).upper()

        cooldown = CHANNEL_COOLDOWN.get(
            priority_name,
            0.02,
        )

        if cooldown <= 0:
            return

        last = TrackSystem._channel_last_emit[
            channel
        ]

        now = time.time()

        delta = now - last

        if delta < cooldown:

            time.sleep(
                cooldown - delta
            )

        TrackSystem._channel_last_emit[
            channel
        ] = time.time()

    # ======================================================
    # IDS
    # ======================================================

    @classmethod
    def _next_packet_sequence(cls):

        with cls._lock:

            cls._packet_sequence += 1

            return cls._packet_sequence

    @classmethod
    def _next_feedback_sequence(cls):

        with cls._lock:

            cls._feedback_sequence += 1

            return cls._feedback_sequence

    @staticmethod
    def _next_packet_id():

        return (
            f"TP-{uuid.uuid4().hex[:12]}"
        )


# ==========================================================
# COMPATIBILITY EXPORTS
# ==========================================================

track_base = (
    "TrackBase",
    "TrackIDBase",
    "TrackContextBase",
)

track_context = TrackContext

track_id_manager = TrackIDManager


# ==========================================================
# SINGLETON ACCESS
# ==========================================================

def get_track_system(
    event_bus=None,
    registry=None,
    node_registry=None,
):

    instance = TrackSystem._instance

    if instance is None:

        instance = TrackSystem(
            event_bus=event_bus,
            registry=registry,
            node_registry=node_registry,
        )

    else:

        if event_bus is not None:

            if not instance.is_event_bus_connected:

                instance.set_event_bus(
                    event_bus
                )

        if registry is not None:
            instance.registry = registry

        if node_registry is not None:
            instance.node_registry = node_registry

    return instance


# ==========================================================
# MODULE HEALTH
# ==========================================================

def track_system_health():

    instance = TrackSystem._instance

    if instance is None:

        return {
            "status": "OFFLINE",
            "module": MODULE_ID,
            "version": MODULE_VERSION,
            "instance": False,
            "timestamp": time.time(),
        }

    return instance.health()


# ==========================================================
# MODULE STATE ACCESS
# ==========================================================

def track_system_state():

    instance = TrackSystem._instance

    if instance is None:
        return {
            "status": "OFFLINE",
            "module": MODULE_ID,
            "version": MODULE_VERSION,
            "modules": {},
            "nodes": {},
            "timestamp": time.time(),
        }

    return instance.build_qbit_system_state()


# ==========================================================
# END FILE
# TRACK SYSTEM STATION v9.0.0
# ==========================================================