# ==========================================================
# FILE: actions.py
# PATH: seed/core/actions.py
# VERSION: 3.1.0 — DYNAMIC ACTION / QBIT / DEVICE CONTROL
# UPDATED: 2026-09-01
#
# PURPOSE:
#   Autonomous ActionEngine observation / discovery / proposal
#   capability layer.
#
# AUTHORITY:
#   QbitDialer is the sole command authority.
#
# EXECUTION:
#   ActionEngine NEVER executes commands.
#   ActionEngine NEVER submits commands.
#   ActionEngine NEVER creates Qbits.
#   ActionEngine NEVER creates queues.
#   ActionEngine NEVER creates workers.
#   ActionEngine NEVER creates a private EventBus.
#
# PIPELINE:
#
#   RAW QBIT
#       |
#       v
#   EXISTING QbitQueueLoop
#       |
#       v
#   QbitDialer
#       |
#       v
#   ComputeBrain
#       |
#       v
#   ThoughtPacket
#       |
#       v
#   TransformerBrain
#       |
#       v
#   Ethics
#       |
#       v
#   QbitDialer
#       |
#       +--> submit_command()
#       |
#       v
#   EXISTING COMMAND PLANE
#       |
#       v
#   REGISTERED HANDLER
#       |
#       v
#   DeviceManager / Device / System
#
# DEVICE CONTROL VOCABULARY:
#
#   RUN
#   STOP
#   PAUSE
#   RESUME
#   ACTIVATE
#   DEACTIVATE
#   REFRESH
#
# These are capability definitions here.
# Their handlers belong to QbitDialer's command plane.
#
# ==========================================================

from __future__ import annotations

import ast
import datetime
import hashlib
import inspect
import json
import logging
import os
import sys
import time

from dataclasses import dataclass, field
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Optional,
    Set,
)


# ==========================================================
# MODULE METADATA
# ==========================================================

MODULE_NAME = "CORE_ACTIONS"
MODULE_VERSION = "3.1.0"
MODULE_ROLE = "ACTION_ENGINE"
MODULE_CHANNEL = "ACTIONS"

ACTION_EVENT_TYPE = "ACTION"
ACTION_SOURCE = "ActionEngine"
ACTION_KIND = "ACTION_TELEMETRY"

COMMAND_AUTHORITY = "QbitDialer"
COMMAND_ADMISSION = "submit_command"

ARCHITECTURE_VERSION = "3.1.0"


# ==========================================================
# LOGGING
# ==========================================================

logger = logging.getLogger("ActionEngine")


def _log_debug(message: str, *args: Any) -> None:
    try:
        logger.debug(message, *args)
    except Exception:
        pass


def _log_info(message: str, *args: Any) -> None:
    try:
        logger.info(message, *args)
    except Exception:
        pass


def _log_warning(message: str, *args: Any) -> None:
    try:
        logger.warning(message, *args)
    except Exception:
        pass


def _log_error(message: str, *args: Any) -> None:
    try:
        logger.error(message, *args)
    except Exception:
        pass


# ==========================================================
# OPTIONAL CORE IMPORTS
# ==========================================================

try:
    from seed.core.tracked_data import TrackedData
except Exception:
    TrackedData = None


try:
    from seed.core.channel_id import ChannelID
except Exception:
    ChannelID = None


# ==========================================================
# IMPORTANT:
#
# Do NOT instantiate ChannelManager here.
#
# ActionEngine is a capability/proposal layer and must not
# create runtime infrastructure during module import.
#
# A shared ChannelManager may be attached by the boot system.
# ==========================================================

root_node = None
cm = None


# ==========================================================
# BASE ACTION
# ==========================================================

class Action:

    name = "ACTION"
    category = "SYSTEM"
    description = ""
    risk = 0.0
    requires_authorization = True

    def __init__(
        self,
        target: Optional[str] = None,
    ):
        self.target = target

    def execute(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        raise NotImplementedError(
            "ActionEngine actions are proposal definitions. "
            "Execution belongs to QbitDialer."
        )


# ==========================================================
# ACTION DEFINITION
# ==========================================================

@dataclass
class ActionDefinition:

    name: str
    source: str
    module: str

    category: str = "SYSTEM"
    description: str = ""

    callable_name: Optional[str] = None
    callable_ref: Optional[Callable] = None

    risk: float = 0.0
    requires_authorization: bool = True

    proposal_only: bool = True
    execution_required: bool = False

    discovered: bool = False
    builtin: bool = False

    handler_key: Optional[str] = None
    execution_owner: str = COMMAND_AUTHORITY

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )

    def snapshot(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "source": self.source,
            "module": self.module,
            "category": self.category,
            "description": self.description,
            "callable_name": self.callable_name,
            "risk": self.risk,
            "requires_authorization": (
                self.requires_authorization
            ),
            "proposal_only": self.proposal_only,
            "execution_required": (
                self.execution_required
            ),
            "discovered": self.discovered,
            "builtin": self.builtin,
            "handler_key": self.handler_key,
            "execution_owner": self.execution_owner,
            "metadata": dict(self.metadata),
        }


# ==========================================================
# ACTION PROPOSAL
# ==========================================================

@dataclass
class ActionProposal:

    action: str
    reason: str

    qbit_id: Optional[str] = None
    task_id: Optional[str] = None
    track_id: Optional[str] = None
    channel_id: Optional[str] = None
    pipeline_id: Optional[str] = None

    source: str = ACTION_SOURCE
    authority: str = COMMAND_AUTHORITY

    category: str = "SYSTEM"
    risk: float = 0.0

    parameters: Dict[str, Any] = field(
        default_factory=dict
    )

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )

    proposal_only: bool = True
    execution_required: bool = False

    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "reason": self.reason,

            "qbit_id": self.qbit_id,
            "task_id": self.task_id,
            "track_id": self.track_id,
            "channel_id": self.channel_id,
            "pipeline_id": self.pipeline_id,

            "source": self.source,
            "authority": self.authority,

            "category": self.category,
            "risk": self.risk,

            "parameters": dict(
                self.parameters
            ),

            "metadata": dict(
                self.metadata
            ),

            "proposal_only": True,
            "execution_required": False,

            "timestamp": self.timestamp,
        }


# ==========================================================
# BUILT-IN AI ACTIONS
# ==========================================================

class ObserveSystem(Action):
    name = "OBSERVE_SYSTEM"
    category = "AI"
    description = "Collect current system observations."
    risk = 0.0
    requires_authorization = False


class AnalyzeSystem(Action):
    name = "ANALYZE_SYSTEM"
    category = "AI"
    description = "Request cognitive analysis of observed system state."
    risk = 0.05
    requires_authorization = True


class ResearchSystem(Action):
    name = "RESEARCH_SYSTEM"
    category = "AI"
    description = "Propose research for an identified system question."
    risk = 0.05
    requires_authorization = True


class LearnFromResult(Action):
    name = "LEARN_FROM_RESULT"
    category = "AI"
    description = "Record result-derived learning context."
    risk = 0.0
    requires_authorization = False


class GenerateImprovement(Action):
    name = "GENERATE_IMPROVEMENT"
    category = "AI"
    description = "Generate an improvement proposal from observed evidence."
    risk = 0.2
    requires_authorization = True


class EvaluateProposal(Action):
    name = "EVALUATE_PROPOSAL"
    category = "AI"
    description = "Evaluate a proposed system change."
    risk = 0.1
    requires_authorization = True


# ==========================================================
# BUILT-IN SYSTEM CONTROL ACTIONS
# ==========================================================

class RepairSystem(Action):
    name = "REPAIR_SYSTEM"
    category = "CONTROL"
    description = "Propose governed system repair."
    risk = 0.7
    requires_authorization = True


class OptimizeSystem(Action):
    name = "OPTIMIZE_SYSTEM"
    category = "CONTROL"
    description = "Propose system-flow optimization."
    risk = 0.4
    requires_authorization = True


class ResetSystem(Action):
    name = "RESET_SYSTEM"
    category = "CONTROL"
    description = "Propose governed system reset."
    risk = 0.7
    requires_authorization = True


class EnableChannel(Action):
    name = "ENABLE_CHANNEL"
    category = "CONTROL"
    description = "Propose enabling an existing SEED channel."
    risk = 0.25
    requires_authorization = True
    handler_key = "ENABLE_CHANNEL"


class DisableChannel(Action):
    name = "DISABLE_CHANNEL"
    category = "CONTROL"
    description = "Propose disabling an existing SEED channel."
    risk = 0.4
    requires_authorization = True
    handler_key = "DISABLE_CHANNEL"


# ==========================================================
# BUILT-IN QBIT ACTIONS
# ==========================================================

class StabilizeQbit(Action):
    name = "STABILIZE_QBIT"
    category = "QBIT"
    description = "Propose bounded Qbit stabilization."
    risk = 0.4
    requires_authorization = True


class SyncQbit(Action):
    name = "SYNC_QBIT"
    category = "QBIT"
    description = "Propose synchronization of the existing Qbit lineage."
    risk = 0.2
    requires_authorization = True


class InspectQueue(Action):
    name = "INSPECT_QBIT_QUEUE"
    category = "QBIT"
    description = "Observe the existing QbitQueueLoop."
    risk = 0.0
    requires_authorization = False


class InspectDialer(Action):
    name = "INSPECT_QBIT_DIALER"
    category = "QBIT"
    description = "Observe QbitDialer state and command authority."
    risk = 0.0
    requires_authorization = False


# ==========================================================
# BUILT-IN DEVICE CONTROL ACTIONS
#
# These definitions intentionally do not execute anything.
#
# Actual handlers belong in QbitDialer's existing
# command_registry and execute through submit_command().
# ==========================================================

class RunDevice(Action):
    name = "RUN"
    category = "DEVICE"
    description = "Request execution/start of an existing device."
    risk = 0.4
    requires_authorization = True
    handler_key = "RUN"


class StopDevice(Action):
    name = "STOP"
    category = "DEVICE"
    description = "Request operational stop of an existing device."
    risk = 0.5
    requires_authorization = True
    handler_key = "STOP"


class PauseDevice(Action):
    name = "PAUSE"
    category = "DEVICE"
    description = "Request pause of an existing device."
    risk = 0.3
    requires_authorization = True
    handler_key = "PAUSE"


class ResumeDevice(Action):
    name = "RESUME"
    category = "DEVICE"
    description = "Request resume of an existing paused device."
    risk = 0.3
    requires_authorization = True
    handler_key = "RESUME"


class ActivateDevice(Action):
    name = "ACTIVATE"
    category = "DEVICE"
    description = "Request activation of an existing device."
    risk = 0.5
    requires_authorization = True
    handler_key = "ACTIVATE"


class DeactivateDevice(Action):
    name = "DEACTIVATE"
    category = "DEVICE"
    description = "Request deactivation of an existing device."
    risk = 0.5
    requires_authorization = True
    handler_key = "DEACTIVATE"


class RefreshDevice(Action):
    name = "REFRESH"
    category = "DEVICE"
    description = "Request refresh/health synchronization of an existing device."
    risk = 0.1
    requires_authorization = False
    handler_key = "REFRESH"


# ==========================================================
# GENERAL DEVICE-MANAGER CAPABILITY
# ==========================================================

class DeviceManagerControl(Action):
    name = "DEVICE_MANAGER"
    category = "DEVICE"
    description = (
        "Address the existing DeviceManager through "
        "the authoritative QbitDialer command plane."
    )
    risk = 0.5
    requires_authorization = True
    handler_key = "DEVICE_MANAGER"


# ==========================================================
# BUILT-IN ACTION LIBRARY
# ==========================================================

BUILTIN_ACTIONS = (
    # AI
    ObserveSystem,
    AnalyzeSystem,
    ResearchSystem,
    LearnFromResult,
    GenerateImprovement,
    EvaluateProposal,

    # System
    RepairSystem,
    OptimizeSystem,
    ResetSystem,
    EnableChannel,
    DisableChannel,

    # Qbit
    StabilizeQbit,
    SyncQbit,
    InspectQueue,
    InspectDialer,

    # Device
    RunDevice,
    StopDevice,
    PauseDevice,
    ResumeDevice,
    ActivateDevice,
    DeactivateDevice,
    RefreshDevice,
    DeviceManagerControl,
)


# ==========================================================
# ACTION ENGINE
# ==========================================================

class ActionEngine:

    def __init__(
        self,
        emit: Optional[Callable] = None,
        track: Optional[Callable] = None,
        task: Optional[Callable] = None,

        storage_root: str = "./SEED_ROOT",

        # Shared transport only.
        event_bus: Any = None,

        device_id: str = "SEED_CORE",

        # Governance.
        ethics: Any = None,

        # Authoritative cognitive objects.
        qbit: Any = None,
        qbit_dialer: Any = None,
        qbit_queue_loop: Any = None,

        # Tracking.
        track_system: Any = None,

        # Cognitive stages.
        compute_brain: Any = None,
        transformer_brain: Any = None,

        # Authoritative registry references.
        registry: Any = None,
        node_registry: Any = None,
        node_manager: Any = None,

        # Device control surface.
        device_manager: Any = None,
        device_registry: Any = None,

        # Heartbeat observation only.
        heartbeat: Any = None,

        # Oracle observation only.
        oracle: Any = None,

        # Encoder / decoder observation.
        encoder: Any = None,
        decoder: Any = None,

        # Existing command sources.
        command_sources: Optional[
            Dict[str, Any]
        ] = None,

        **kwargs: Any,
    ):

        self.module_name = MODULE_NAME
        self.module_version = MODULE_VERSION
        self.module_role = MODULE_ROLE

        # ------------------------------------------------------
        # Shared EventBus.
        #
        # NEVER create a fallback EventBus.
        # ------------------------------------------------------

        self.event_bus = event_bus

        if self.event_bus is None:
            _log_debug(
                "[ActionEngine] Shared EventBus not supplied; "
                "telemetry transport deferred"
            )

        # ------------------------------------------------------
        # External callbacks.
        # ------------------------------------------------------

        self.emit = emit
        self.track = track
        self.task = task

        # ------------------------------------------------------
        # Governance.
        # ------------------------------------------------------

        self.ethics = ethics
        self.oracle = oracle

        # ------------------------------------------------------
        # Authoritative cognitive connections.
        # ------------------------------------------------------

        self.qbit = qbit
        self.qbit_dialer = qbit_dialer
        self.qbit_queue_loop = qbit_queue_loop

        self.compute_brain = compute_brain
        self.transformer_brain = transformer_brain

        # ------------------------------------------------------
        # Tracking.
        # ------------------------------------------------------

        self.track_system = track_system

        # ------------------------------------------------------
        # Registry/discovery.
        # ------------------------------------------------------

        self.registry = registry
        self.node_registry = node_registry
        self.node_manager = node_manager

        # ------------------------------------------------------
        # Device control observation.
        #
        # ActionEngine observes these objects.
        # QbitDialer owns execution.
        # ------------------------------------------------------

        self.device_manager = device_manager
        self.device_registry = device_registry

        # ------------------------------------------------------
        # Heartbeat / codec observation.
        # ------------------------------------------------------

        self.heartbeat = heartbeat
        self.encoder = encoder
        self.decoder = decoder

        # ------------------------------------------------------
        # Existing command sources.
        # ------------------------------------------------------

        self.command_sources = (
            dict(command_sources or {})
        )

        # ------------------------------------------------------
        # Storage.
        # ------------------------------------------------------

        self.storage_root = (
            os.path.abspath(storage_root)
            if storage_root
            else os.path.abspath("./SEED_ROOT")
        )

        self.device_id = device_id

        # ------------------------------------------------------
        # Runtime state.
        # ------------------------------------------------------

        self.running = False

        self.last_action = None
        self.last_proposal = None

        self.reward_points = 0
        self.success_rate = 0.0

        self.action_history: List[
            Dict[str, Any]
        ] = []

        self.proposal_history: List[
            Dict[str, Any]
        ] = []

        self.subscribers: List[
            Callable
        ] = []

        # ------------------------------------------------------
        # Current Qbit lineage.
        # ------------------------------------------------------

        self.current_qbit_id: Optional[str] = None
        self.current_task_id: Optional[str] = None
        self.current_track_id: Optional[str] = None
        self.current_channel_id: Optional[str] = None
        self.current_pipeline_id: Optional[str] = None

        # ------------------------------------------------------
        # Action catalog.
        # ------------------------------------------------------

        self.action_catalog: Dict[
            str,
            ActionDefinition,
        ] = {}

        self.discovered_actions: Dict[
            str,
            ActionDefinition,
        ] = {}

        self.builtin_actions: Dict[
            str,
            ActionDefinition,
        ] = {}

        self.discovery_errors: List[
            Dict[str, Any]
        ] = []

        # ------------------------------------------------------
        # Directories.
        # ------------------------------------------------------

        self.actions_dir = os.path.join(
            self.storage_root,
            "storage",
            "actions",
        )

        self.state_dir = os.path.join(
            self.storage_root,
            "storage",
            "state",
        )

        self.devices_dir = os.path.join(
            self.storage_root,
            "seed",
            "core",
            "devices",
        )

        self._ensure_directories()

        # ------------------------------------------------------
        # Load bounded built-in capabilities.
        # ------------------------------------------------------

        self.load_basic_action_library()

        # ------------------------------------------------------
        # Initial discovery.
        # ------------------------------------------------------

        try:
            self.discover_actions()
        except Exception as exc:
            _log_warning(
                "[ActionEngine] Initial discovery deferred | %s",
                exc,
            )

        _log_info(
            "[ActionEngine] Initialized | "
            "version=%s | "
            "qbit=%s | dialer=%s | queue_loop=%s | "
            "compute=%s | transformer=%s | ethics=%s | "
            "track=%s | registry=%s | device_manager=%s | "
            "actions=%s",
            self.module_version,
            self.qbit is not None,
            self.qbit_dialer is not None,
            self.qbit_queue_loop is not None,
            self.compute_brain is not None,
            self.transformer_brain is not None,
            self.ethics is not None,
            self.track_system is not None,
            self.registry is not None,
            self.device_manager is not None,
            len(self.action_catalog),
        )

    # ======================================================
    # DIRECTORY SAFETY
    # ======================================================

    def _ensure_directories(self) -> None:

        for path in (
            self.actions_dir,
            self.state_dir,
            self.devices_dir,
        ):

            try:
                os.makedirs(
                    path,
                    exist_ok=True,
                )

            except Exception as exc:

                _log_error(
                    "[ActionEngine] Directory creation failed | "
                    "path=%s | error=%s",
                    path,
                    exc,
                )

    # ======================================================
    # LIFECYCLE
    # ======================================================

    def start(self) -> bool:

        self.running = True

        self._emit_event(
            "ACTION_ENGINE_STARTED",
            self.get_state(),
        )

        return True

    def stop(self) -> bool:

        self.running = False

        self._emit_event(
            "ACTION_ENGINE_STOPPED",
            self.get_state(),
        )

        return True

    # ======================================================
    # ATTACHMENTS
    # ======================================================

    def attach_qbit(
        self,
        qbit: Any,
    ) -> bool:

        if qbit is None:
            return False

        self.qbit = qbit

        self._capture_lineage(
            self._qbit_snapshot()
        )

        return True

    def attach_qbit_dialer(
        self,
        qbit_dialer: Any,
    ) -> bool:

        if qbit_dialer is None:
            return False

        self.qbit_dialer = qbit_dialer

        _log_info(
            "[ActionEngine] QbitDialer attached | "
            "authority=%s | admission=%s",
            COMMAND_AUTHORITY,
            COMMAND_ADMISSION,
        )

        return True

    def attach_qbit_queue_loop(
        self,
        qbit_queue_loop: Any,
    ) -> bool:

        if qbit_queue_loop is None:
            return False

        self.qbit_queue_loop = qbit_queue_loop

        _log_info(
            "[ActionEngine] Existing QbitQueueLoop attached"
        )

        return True

    def attach_track_system(
        self,
        track_system: Any,
    ) -> bool:

        if track_system is None:
            return False

        self.track_system = track_system

        return True

    def attach_cognitive_systems(
        self,
        compute_brain: Any = None,
        transformer_brain: Any = None,
        ethics: Any = None,
    ) -> bool:

        if compute_brain is not None:
            self.compute_brain = compute_brain

        if transformer_brain is not None:
            self.transformer_brain = transformer_brain

        if ethics is not None:
            self.ethics = ethics

        return True

    def attach_registry(
        self,
        registry: Any = None,
        node_registry: Any = None,
        node_manager: Any = None,
    ) -> bool:

        if registry is not None:
            self.registry = registry

        if node_registry is not None:
            self.node_registry = node_registry

        if node_manager is not None:
            self.node_manager = node_manager

        return True

    def attach_device_manager(
        self,
        device_manager: Any = None,
        device_registry: Any = None,
    ) -> bool:

        if device_manager is not None:
            self.device_manager = device_manager

        if device_registry is not None:
            self.device_registry = device_registry

        _log_info(
            "[ActionEngine] Device control surface attached | "
            "manager=%s | registry=%s",
            self.device_manager is not None,
            self.device_registry is not None,
        )

        return True

    def attach_observers(
        self,
        heartbeat: Any = None,
        oracle: Any = None,
        encoder: Any = None,
        decoder: Any = None,
    ) -> bool:

        if heartbeat is not None:
            self.heartbeat = heartbeat

        if oracle is not None:
            self.oracle = oracle

        if encoder is not None:
            self.encoder = encoder

        if decoder is not None:
            self.decoder = decoder

        return True

    # ======================================================
    # RUNTIME BINDING
    #
    # Binds already-created systems.
    #
    # Does NOT create anything.
    # ======================================================

    def bind_runtime(
        self,
        *,
        qbit: Any = None,
        qbit_dialer: Any = None,
        qbit_queue_loop: Any = None,
        compute_brain: Any = None,
        transformer_brain: Any = None,
        ethics: Any = None,
        track_system: Any = None,
        registry: Any = None,
        node_registry: Any = None,
        node_manager: Any = None,
        device_manager: Any = None,
        device_registry: Any = None,
        heartbeat: Any = None,
        oracle: Any = None,
        encoder: Any = None,
        decoder: Any = None,
    ) -> Dict[str, bool]:

        bindings = {
            "qbit": qbit,
            "qbit_dialer": qbit_dialer,
            "qbit_queue_loop": qbit_queue_loop,
            "compute_brain": compute_brain,
            "transformer_brain": transformer_brain,
            "ethics": ethics,
            "track_system": track_system,
            "registry": registry,
            "node_registry": node_registry,
            "node_manager": node_manager,
            "device_manager": device_manager,
            "device_registry": device_registry,
            "heartbeat": heartbeat,
            "oracle": oracle,
            "encoder": encoder,
            "decoder": decoder,
        }

        for name, value in bindings.items():

            if value is None:
                continue

            setattr(
                self,
                name,
                value,
            )

        if qbit is not None:
            self._capture_lineage(
                self._qbit_snapshot()
            )

        return {
            name: getattr(
                self,
                name,
                None,
            ) is not None
            for name in bindings
        }

    # ======================================================
    # SUBSCRIBERS
    # ======================================================

    def subscribe(
        self,
        callback: Callable,
    ) -> bool:

        if not callable(callback):
            return False

        if callback not in self.subscribers:
            self.subscribers.append(callback)

        return True

    def unsubscribe(
        self,
        callback: Callable,
    ) -> bool:

        try:
            self.subscribers.remove(
                callback
            )
            return True

        except ValueError:
            return False

    def _notify(
        self,
        metadata: Dict[str, Any],
    ) -> None:

        for callback in list(
            self.subscribers
        ):

            try:
                callback(
                    metadata
                )

            except Exception as exc:

                _log_warning(
                    "[ActionEngine] Subscriber failed | %s",
                    exc,
                )

    # ======================================================
    # BASIC ACTION LIBRARY
    # ======================================================

    def load_basic_action_library(
        self,
    ) -> int:

        loaded = 0

        for action_cls in BUILTIN_ACTIONS:

            try:

                name = str(
                    getattr(
                        action_cls,
                        "name",
                        action_cls.__name__,
                    )
                ).strip().upper()

                definition = ActionDefinition(
                    name=name,
                    source="builtin",
                    module=action_cls.__module__,

                    category=str(
                        getattr(
                            action_cls,
                            "category",
                            "SYSTEM",
                        )
                    ),

                    description=str(
                        getattr(
                            action_cls,
                            "description",
                            "",
                        )
                    ),

                    callable_name=(
                        action_cls.__name__
                    ),

                    callable_ref=action_cls,

                    risk=self._safe_float(
                        getattr(
                            action_cls,
                            "risk",
                            0.0,
                        )
                    ),

                    requires_authorization=bool(
                        getattr(
                            action_cls,
                            "requires_authorization",
                            True,
                        )
                    ),

                    proposal_only=True,

                    execution_required=(
                        getattr(
                            action_cls,
                            "handler_key",
                            None,
                        )
                        is not None
                    ),

                    discovered=False,
                    builtin=True,

                    handler_key=getattr(
                        action_cls,
                        "handler_key",
                        None,
                    ),

                    execution_owner=COMMAND_AUTHORITY,

                    metadata={
                        "class": action_cls.__name__,
                        "authority": COMMAND_AUTHORITY,
                        "execution_owner": COMMAND_AUTHORITY,
                        "execution_via": COMMAND_ADMISSION,
                    },
                )

                self.builtin_actions[
                    name
                ] = definition

                self.action_catalog[
                    name
                ] = definition

                loaded += 1

            except Exception as exc:

                _log_warning(
                    "[ActionEngine] Built-in action load failed | %s",
                    exc,
                )

        self._emit_event(
            "ACTION_LIBRARY_LOADED",
            {
                "module": self.module_name,
                "version": self.module_version,
                "loaded": loaded,
                "total": len(
                    self.action_catalog
                ),
                "authority": COMMAND_AUTHORITY,
            },
        )

        return loaded

    # ======================================================
    # REGISTER EXPLICIT MODULE
    # ======================================================

    def register_module(
        self,
        module: Any,
    ) -> int:

        if module is None:
            return 0

        definitions = self._discover_module_actions(
            module
        )

        loaded = 0

        for definition in definitions:

            self.discovered_actions[
                definition.name
            ] = definition

            self.action_catalog[
                definition.name
            ] = definition

            loaded += 1

        return loaded

    # ======================================================
    # DYNAMIC ACTION DISCOVERY
    # ======================================================

    def discover_actions(
        self,
        modules: Optional[
            Iterable[Any]
        ] = None,
    ) -> Dict[str, ActionDefinition]:

        candidates = list(
            modules
            if modules is not None
            else self._collect_registered_modules()
        )

        discovered: Dict[
            str,
            ActionDefinition,
        ] = {}

        for module in candidates:

            try:

                definitions = (
                    self._discover_module_actions(
                        module
                    )
                )

                for definition in definitions:

                    discovered[
                        definition.name
                    ] = definition

            except Exception as exc:

                self.discovery_errors.append(
                    {
                        "module": self._module_name(
                            module
                        ),
                        "error": str(exc),
                    }
                )

                _log_warning(
                    "[ActionEngine] Module discovery failed | "
                    "module=%s | error=%s",
                    self._module_name(module),
                    exc,
                )

        self.discovered_actions.update(
            discovered
        )

        self.action_catalog.update(
            discovered
        )

        self._emit_event(
            "ACTION_DISCOVERY_COMPLETE",
            {
                "discovered": len(
                    discovered
                ),
                "total": len(
                    self.action_catalog
                ),
                "errors": len(
                    self.discovery_errors
                ),
                "authority": COMMAND_AUTHORITY,
            },
        )

        return dict(
            discovered
        )

    # ======================================================
    # REGISTERED MODULE COLLECTION
    #
    # This observes existing registry structures.
    # It does not instantiate registry infrastructure.
    # ======================================================

    def _collect_registered_modules(
        self,
    ) -> List[Any]:

        result: List[Any] = []
        seen: Set[int] = set()

        sources = (
            self.registry,
            self.node_registry,
            self.node_manager,
        )

        for source in sources:

            if source is None:
                continue

            values: List[Any] = []

            if isinstance(
                source,
                dict,
            ):

                values.extend(
                    source.values()
                )

            for method_name in (
                "get_modules",
                "list_modules",
                "get_nodes",
                "list_nodes",
                "discover_nodes",
                "snapshot_nodes",
            ):

                method = getattr(
                    source,
                    method_name,
                    None,
                )

                if not callable(method):
                    continue

                try:

                    value = method()

                    if isinstance(
                        value,
                        dict,
                    ):

                        values.extend(
                            value.values()
                        )

                    elif isinstance(
                        value,
                        (
                            list,
                            tuple,
                            set,
                        ),
                    ):

                        values.extend(
                            value
                        )

                except Exception:
                    continue

            for attr_name in (
                "modules",
                "_modules",
                "nodes",
                "_nodes",
                "registered_nodes",
                "registered_modules",
            ):

                value = getattr(
                    source,
                    attr_name,
                    None,
                )

                if isinstance(
                    value,
                    dict,
                ):

                    values.extend(
                        value.values()
                    )

                elif isinstance(
                    value,
                    (
                        list,
                        tuple,
                        set,
                    ),
                ):

                    values.extend(
                        value
                    )

            for value in values:

                if value is None:
                    continue

                marker = id(value)

                if marker in seen:
                    continue

                seen.add(marker)

                result.append(
                    value
                )

        return result

    # ======================================================
    # MODULE ACTION DISCOVERY
    # ======================================================

    def _discover_module_actions(
        self,
        module: Any,
    ) -> List[ActionDefinition]:

        results: List[
            ActionDefinition
        ] = []

        if module is None:
            return results

        module_name = self._module_name(
            module
        )

        try:

            if inspect.isclass(
                module
            ):

                members = inspect.getmembers(
                    module
                )

            else:

                members = inspect.getmembers(
                    module
                )

        except Exception:

            return results

        for name, value in members:

            try:

                if name.startswith(
                    "__"
                ):
                    continue

                # ----------------------------------------------
                # Explicit Action subclasses.
                # ----------------------------------------------

                if inspect.isclass(
                    value
                ):

                    try:
                        is_action = issubclass(
                            value,
                            Action,
                        )
                    except Exception:
                        is_action = False

                    if is_action and value is not Action:

                        definition = (
                            self._definition_from_callable(
                                name=name,
                                value=value,
                                module_name=module_name,
                                explicit=True,
                            )
                        )

                        if definition:
                            results.append(
                                definition
                            )

                        continue

                # ----------------------------------------------
                # Functions / coroutine functions.
                # ----------------------------------------------

                if not callable(
                    value
                ):
                    continue

                if not (
                    inspect.isfunction(value)
                    or inspect.iscoroutinefunction(value)
                    or inspect.ismethod(value)
                ):
                    continue

                if not self._looks_action_capable(
                    name
                ):
                    continue

                definition = (
                    self._definition_from_callable(
                        name=name,
                        value=value,
                        module_name=module_name,
                        explicit=False,
                    )
                )

                if definition:
                    results.append(
                        definition
                    )

            except Exception as exc:

                self.discovery_errors.append(
                    {
                        "module": module_name,
                        "member": name,
                        "error": str(exc),
                    }
                )

        return results

    # ======================================================
    # ACTION-CAPABLE DEF DETECTION
    #
    # Covers the user's "def in modules" requirement.
    # ======================================================

    @staticmethod
    def _looks_action_capable(
        name: str,
    ) -> bool:

        normalized = str(
            name
        ).strip().lower()

        if not normalized:
            return False

        prefixes = (
            "action_",
            "command_",
            "execute_",
            "control_",

            "ai_",
            "repair_",
            "optimize_",
            "research_",
            "learn_",
            "analyze_",
            "improve_",
            "act_",

            "enable_",
            "disable_",
            "activate_",
            "deactivate_",

            "start_",
            "stop_",
            "run_",
            "pause_",
            "resume_",

            "reset_",
            "refresh_",
            "sync_",
            "stabilize_",

            "update_",
            "upgrade_",
            "rewind_",
        )

        exact_names = {
            "run",
            "stop",
            "pause",
            "resume",
            "activate",
            "deactivate",
            "refresh",
            "reset",
            "start",
            "shutdown",
            "halt",
        }

        if normalized in exact_names:
            return True

        return normalized.startswith(
            prefixes
        )

    # ======================================================
    # ACTION DEFINITION NORMALIZATION
    # ======================================================

    def _definition_from_callable(
        self,
        name: str,
        value: Callable,
        module_name: str,
        explicit: bool,
    ) -> Optional[ActionDefinition]:

        try:

            normalized = (
                self._normalize_action_name(
                    name
                )
            )

            if not normalized:
                return None

            doc = (
                inspect.getdoc(
                    value
                )
                or ""
            )

            handler_key = (
                self._infer_handler_key(
                    normalized
                )
            )

            category = (
                self._infer_category(
                    normalized
                )
            )

            definition = ActionDefinition(
                name=normalized,

                source="registry_discovery",

                module=module_name,

                category=category,

                description=doc[:1000],

                callable_name=name,

                callable_ref=value,

                risk=self._infer_risk(
                    normalized
                ),

                requires_authorization=(
                    normalized
                    not in {
                        "OBSERVE",
                        "REFRESH",
                        "STATUS",
                        "INSPECT",
                    }
                ),

                proposal_only=True,

                execution_required=(
                    handler_key is not None
                ),

                discovered=True,

                builtin=False,

                handler_key=handler_key,

                execution_owner=COMMAND_AUTHORITY,

                metadata={
                    "explicit_action_class": explicit,
                    "signature": self._safe_signature(
                        value
                    ),
                    "authority": COMMAND_AUTHORITY,
                    "execution_owner": COMMAND_AUTHORITY,
                    "execution_via": COMMAND_ADMISSION,
                },
            )

            return definition

        except Exception as exc:

            _log_warning(
                "[ActionEngine] Definition normalization failed | "
                "name=%s | error=%s",
                name,
                exc,
            )

            return None

    # ======================================================
    # COMMAND HANDLER NORMALIZATION
    # ======================================================

    @staticmethod
    def _infer_handler_key(
        name: str,
    ) -> Optional[str]:

        value = str(
            name
        ).strip().upper()

        aliases = {
            "START": "RUN",
            "RUN": "RUN",

            "HALT": "STOP",
            "SHUTDOWN": "STOP",
            "STOP": "STOP",

            "PAUSE": "PAUSE",
            "RESUME": "RESUME",

            "ACTIVATE": "ACTIVATE",
            "ENABLE": "ACTIVATE",

            "DEACTIVATE": "DEACTIVATE",
            "DISABLE": "DEACTIVATE",

            "REFRESH": "REFRESH",
            "RESET": "RESET",

            "DEVICE_MANAGER": "DEVICE_MANAGER",
        }

        return aliases.get(
            value
        )

    # ======================================================
    # CATEGORY
    # ======================================================

    @staticmethod
    def _infer_category(
        name: str,
    ) -> str:

        value = str(
            name
        ).upper()

        if any(
            token in value
            for token in (
                "QBIT",
                "QUEUE",
                "DIALER",
            )
        ):
            return "QBIT"

        if any(
            token in value
            for token in (
                "AI",
                "THINK",
                "ANALYZE",
                "RESEARCH",
                "LEARN",
                "COGNITIVE",
                "TRANSFORM",
            )
        ):
            return "AI"

        if any(
            token in value
            for token in (
                "DEVICE",
                "RUN",
                "STOP",
                "PAUSE",
                "RESUME",
                "ACTIVATE",
                "DEACTIVATE",
                "REFRESH",
            )
        ):
            return "DEVICE"

        if any(
            token in value
            for token in (
                "REPAIR",
                "OPTIMIZE",
                "CONTROL",
                "RESET",
                "ENABLE",
                "DISABLE",
                "START",
                "UPGRADE",
            )
        ):
            return "CONTROL"

        return "SYSTEM"

    # ======================================================
    # RISK
    # ======================================================

    @staticmethod
    def _infer_risk(
        name: str,
    ) -> float:

        value = str(
            name
        ).upper()

        if any(
            token in value
            for token in (
                "DELETE",
                "DESTROY",
                "SELF_DESTRUCT",
                "WIPE",
                "FORMAT",
            )
        ):
            return 1.0

        if any(
            token in value
            for token in (
                "REPAIR",
                "UPGRADE",
                "RESET",
                "REWRITE",
                "REPLACE",
                "EXECUTE",
                "DEACTIVATE",
            )
        ):
            return 0.7

        if any(
            token in value
            for token in (
                "CONTROL",
                "ENABLE",
                "DISABLE",
                "ACTIVATE",
                "START",
                "STOP",
                "RUN",
            )
        ):
            return 0.4

        if any(
            token in value
            for token in (
                "PAUSE",
                "RESUME",
            )
        ):
            return 0.3

        if any(
            token in value
            for token in (
                "ANALYZE",
                "RESEARCH",
                "LEARN",
                "OBSERVE",
                "INSPECT",
                "STATUS",
                "REFRESH",
            )
        ):
            return 0.05

        return 0.2

    # ======================================================
    # QBIT LINEAGE
    # ======================================================

    def _capture_lineage(
        self,
        qbit_state: Dict[str, Any],
    ) -> None:

        if not isinstance(
            qbit_state,
            dict,
        ):
            qbit_state = {}

        self.current_qbit_id = (
            self._first_value(
                qbit_state,
                (
                    "qbit_id",
                    "id",
                ),
            )
        )

        self.current_task_id = (
            self._first_value(
                qbit_state,
                (
                    "task_id",
                ),
            )
        )

        self.current_track_id = (
            self._first_value(
                qbit_state,
                (
                    "track_id",
                ),
            )
        )

        self.current_channel_id = (
            self._first_value(
                qbit_state,
                (
                    "channel_id",
                    "channel",
                ),
            )
        )

        self.current_pipeline_id = (
            self._first_value(
                qbit_state,
                (
                    "pipeline_id",
                ),
            )
        )

    # ======================================================
    # QBIT SNAPSHOT
    # ======================================================

    def _qbit_snapshot(
        self,
    ) -> Dict[str, Any]:

        qbit = self.qbit

        if qbit is None:
            return {}

        if isinstance(
            qbit,
            dict,
        ):
            return dict(
                qbit
            )

        for method_name in (
            "snapshot",
            "to_dict",
            "get_state",
            "state",
        ):

            value = getattr(
                qbit,
                method_name,
                None,
            )

            try:

                if callable(value):

                    result = value()

                    if isinstance(
                        result,
                        dict,
                    ):
                        return dict(
                            result
                        )

                elif isinstance(
                    value,
                    dict,
                ):

                    return dict(
                        value
                    )

            except Exception:
                pass

        result = {}

        for key in (
            "qbit_id",
            "id",
            "task_id",
            "track_id",
            "channel_id",
            "pipeline_id",
            "status",
            "state",
            "intent",
            "action",
            "command",
        ):

            try:

                value = getattr(
                    qbit,
                    key,
                    None,
                )

                if value is not None:
                    result[key] = value

            except Exception:
                pass

        return result


    # ======================================================
    # PROPOSAL GENERATION
    # ======================================================

    def propose(
        self,
        action: str,
        reason: str,
        *,
        parameters: Optional[
            Dict[str, Any]
        ] = None,
        qbit_state: Optional[
            Dict[str, Any]
        ] = None,
        category: Optional[str] = None,
        risk: Optional[float] = None,
        metadata: Optional[
            Dict[str, Any]
        ] = None,
    ) -> Dict[str, Any]:

        if qbit_state is None:
            qbit_state = self._qbit_snapshot()

        self._capture_lineage(
            qbit_state
        )

        action_name = (
            self._normalize_action_name(
                action
            )
        )

        definition = (
            self.action_catalog.get(
                action_name
            )
        )

        if definition is not None:

            if category is None:
                category = definition.category

            if risk is None:
                risk = definition.risk

        if category is None:
            category = self._infer_category(
                action_name
            )

        if risk is None:
            risk = self._infer_risk(
                action_name
            )

        # --------------------------------------------------
        # Resolve execution metadata once.
        # --------------------------------------------------

        handler_key = (
            definition.handler_key
            if definition is not None
            else self._infer_handler_key(
                action_name
            )
        )

        execution_required = bool(
            definition is not None
            and (
                definition.handler_key
                is not None
            )
        )

        proposal_metadata = dict(
            metadata or {}
        )

        proposal_metadata.update({
            "action_known": (
                definition is not None
            ),

            "action_source": (
                definition.source
                if definition is not None
                else None
            ),

            "handler_key": handler_key,

            "execution_required": (
                execution_required
            ),

            "execution_requested": (
                execution_required
            ),

            "actionable": (
                execution_required
            ),

            "has_actionable_command": (
                execution_required
            ),

            "proposal_only": True,

            "authorized": False,

            "authority": COMMAND_AUTHORITY,

            "admission": COMMAND_ADMISSION,

            "command_authority": (
                COMMAND_AUTHORITY
            ),

            "command_admission": (
                COMMAND_ADMISSION
            ),

            "execution_owner": (
                COMMAND_AUTHORITY
            ),

            "action_engine_executes": False,

            "action_engine_submits": False,

            "executes_commands": False,

            "submits_commands": False,
        })

        proposal = ActionProposal(
            action=action_name,

            reason=str(
                reason
            ),

            qbit_id=self.current_qbit_id,
            task_id=self.current_task_id,
            track_id=self.current_track_id,
            channel_id=self.current_channel_id,
            pipeline_id=self.current_pipeline_id,

            category=category,

            risk=self._safe_float(
                risk
            ),

            parameters=dict(
                parameters or {}
            ),

            metadata=proposal_metadata,
        )

        result = proposal.to_dict()

        # --------------------------------------------------
        # Preserve execution metadata at the proposal
        # root as well. This gives QbitDialer a stable
        # handoff contract without requiring it to know
        # ActionProposal internals.
        # --------------------------------------------------

        result.update({
            "execution_required": (
                execution_required
            ),

            "execution_requested": (
                execution_required
            ),

            "actionable": (
                execution_required
            ),

            "has_actionable_command": (
                execution_required
            ),

            "handler_key": handler_key,

            "proposal_only": True,

            "authorized": False,

            "command_authority": (
                COMMAND_AUTHORITY
            ),

            "command_admission": (
                COMMAND_ADMISSION
            ),

            "execution_owner": (
                COMMAND_AUTHORITY
            ),

            "executes_commands": False,

            "submits_commands": False,
        })

        self.last_proposal = result

        self.proposal_history.append(
            result
        )

        self._emit_event(
            "ACTION_PROPOSAL",
            result,
            track_id=self.current_track_id,
            channel=MODULE_CHANNEL,
        )

        return result

    # ======================================================
    # THINK / PROPOSE
    # ======================================================

    def think_and_act(
        self,
        qbit_state: Optional[
            Dict[str, Any]
        ],
    ) -> Dict[str, Any]:

        if not isinstance(
            qbit_state,
            dict,
        ):
            qbit_state = {}

        self._capture_lineage(
            qbit_state
        )

        try:

            intent = str(
                qbit_state.get(
                    "intent",
                    "UNKNOWN",
                )
            )

            motivation = self._safe_float(
                qbit_state.get(
                    "brain_motivation",
                    qbit_state.get(
                        "motivation",
                        0.0,
                    ),
                )
            )

            drive = self._safe_float(
                qbit_state.get(
                    "brain_drive",
                    qbit_state.get(
                        "drive",
                        0.0,
                    ),
                )
            )

            limp = bool(
                qbit_state.get(
                    "limp",
                    False,
                )
            )

            # --------------------------------------------------
            # Explicit action/command already supplied.
            #
            # Preserve it rather than replacing it with an
            # unrelated heuristic.
            # --------------------------------------------------

            requested_action = (
                qbit_state.get(
                    "action"
                )
                or qbit_state.get(
                    "command"
                )
                or qbit_state.get(
                    "cmd"
                )
            )

            if requested_action:

                requested_name = (
                    self._normalize_action_name(
                        requested_action
                    )
                )

                if (
                    requested_name
                    in self.action_catalog
                ):

                    return self.propose(
                        requested_name,
                        "EXPLICIT_QBIT_ACTION",
                        qbit_state=qbit_state,
                    )

            # --------------------------------------------------
            # Intent -> Action contract.
            # IntentEngine decides WHAT the system is trying to
            # accomplish; ActionEngine converts that intent into
            # a governed proposal. It still never executes.
            # --------------------------------------------------

            intent_action_map = {
                "IDLE": "OBSERVE_SYSTEM",
                "OBSERVE": "OBSERVE_SYSTEM",
                "PROCESS": "ANALYZE_SYSTEM",
                "ANALYZE": "EVALUATE_PROPOSAL",
                "RECOVER": "REPAIR_SYSTEM",
                "HANDLE_ERROR": "REPAIR_SYSTEM",
            }
            mapped_action = intent_action_map.get(intent.upper())
            if mapped_action and mapped_action in self.action_catalog:
                return self.propose(
                    mapped_action,
                    "INTENT_ENGINE_ACTION_MAPPING",
                    qbit_state=qbit_state,
                    category=self.action_catalog[mapped_action].category,
                    risk=self.action_catalog[mapped_action].risk,
                    metadata={
                        "intent_source": intent,
                        "intent_to_action": True,
                    },
                )

            # --------------------------------------------------
            # Observation intents.
            # --------------------------------------------------

            if intent.upper() in {
                "STATUS",
                "OBSERVE",
                "HEALTH",
                "INSPECT",
            }:

                return self.propose(
                    "OBSERVE_SYSTEM",
                    "SYSTEM_OBSERVATION_REQUEST",
                    qbit_state=qbit_state,
                    category="AI",
                    risk=0.0,
                )

            # --------------------------------------------------
            # Limp mode.
            # --------------------------------------------------

            if limp:

                return self.propose(
                    "REPAIR_SYSTEM",
                    "LIMP_MODE_REQUIRES_GOVERNED_REPAIR",
                    qbit_state=qbit_state,
                    category="CONTROL",
                    risk=0.7,
                )

            # --------------------------------------------------
            # High drive.
            # --------------------------------------------------

            if drive > 0.9:

                return self.propose(
                    "OPTIMIZE_SYSTEM",
                    "HIGH_SYSTEM_DRIVE",
                    qbit_state=qbit_state,
                    category="CONTROL",
                    risk=0.4,
                )

            # --------------------------------------------------
            # High motivation.
            # --------------------------------------------------

            if motivation > 0.85:

                return self.propose(
                    "RESEARCH_SYSTEM",
                    "HIGH_COGNITIVE_MOTIVATION",
                    qbit_state=qbit_state,
                    category="AI",
                    risk=0.05,
                )

            # --------------------------------------------------
            # Moderate motivation.
            # --------------------------------------------------

            if motivation > 0.6:

                return self.propose(
                    "STABILIZE_QBIT",
                    "QBIT_CONTROL_THRESHOLD_REACHED",
                    qbit_state=qbit_state,
                    category="QBIT",
                    risk=0.4,
                )

            # --------------------------------------------------
            # Safe observation fallback.
            # --------------------------------------------------

            return self.propose(
                "OBSERVE_SYSTEM",
                "NO_HIGHER_PRIORITY_ACTION_REQUIRED",
                qbit_state=qbit_state,
                category="AI",
                risk=0.0,
            )

        except Exception as exc:

            _log_error(
                "[ActionEngine] think_and_act failed | %s",
                exc,
            )

            return self.propose(
                "OBSERVE_SYSTEM",
                "ACTION_ENGINE_FAILURE",
                qbit_state=qbit_state,
                category="AI",
                risk=0.0,
                metadata={
                    "error": str(exc),
                },
            )

    # ======================================================
    # COGNITIVE CONTEXT
    # ======================================================

    def get_cognitive_context(
        self,
        qbit_state: Optional[
            Dict[str, Any]
        ] = None,
    ) -> Dict[str, Any]:

        if qbit_state is None:
            qbit_state = self._qbit_snapshot()

        self._capture_lineage(
            qbit_state
        )

        return {

            "action_engine": {
                "module": self.module_name,
                "version": self.module_version,

                "catalog_size": len(
                    self.action_catalog
                ),

                "discovered_actions": len(
                    self.discovered_actions
                ),

                "builtin_actions": len(
                    self.builtin_actions
                ),

                "discovery_errors": len(
                    self.discovery_errors
                ),
            },

            "lineage": {
                "qbit_id": self.current_qbit_id,
                "task_id": self.current_task_id,
                "track_id": self.current_track_id,
                "channel_id": self.current_channel_id,
                "pipeline_id": self.current_pipeline_id,
            },

            "cognitive_connections": {
                "qbit": (
                    self.qbit is not None
                ),

                "qbit_dialer": (
                    self.qbit_dialer is not None
                ),

                "qbit_queue_loop": (
                    self.qbit_queue_loop is not None
                ),

                "compute_brain": (
                    self.compute_brain is not None
                ),

                "transformer_brain": (
                    self.transformer_brain is not None
                ),

                "ethics": (
                    self.ethics is not None
                ),

                "track_system": (
                    self.track_system is not None
                ),

                "oracle": (
                    self.oracle is not None
                ),

                "heartbeat": (
                    self.heartbeat is not None
                ),
            },

            "device_connections": {
                "device_manager": (
                    self.device_manager is not None
                ),

                "device_registry": (
                    self.device_registry is not None
                ),

                "controls": [
                    "RUN",
                    "STOP",
                    "PAUSE",
                    "RESUME",
                    "ACTIVATE",
                    "DEACTIVATE",
                    "REFRESH",
                ],
            },

            "command_plane": {
                "authority": COMMAND_AUTHORITY,
                "admission": COMMAND_ADMISSION,

                "dialer_attached": (
                    self.qbit_dialer is not None
                ),

                "action_engine_executes": False,
                "action_engine_submits": False,

                "device_execution_owner": (
                    COMMAND_AUTHORITY
                ),
            },

            "available_actions": (
                self.get_capabilities()
            ),
        }

    # ======================================================
    # CAPABILITIES
    # ======================================================

    def get_capabilities(
        self,
    ) -> List[Dict[str, Any]]:

        return [
            definition.snapshot()
            for definition
            in self.action_catalog.values()
        ]

    def available_actions(
        self,
    ) -> Set[str]:

        return set(
            self.action_catalog.keys()
        )

    def get_action(
        self,
        action: str,
    ) -> Optional[
        ActionDefinition
    ]:

        return self.action_catalog.get(
            self._normalize_action_name(
                action
            )
        )

    def get_device_controls(
        self,
    ) -> List[
        Dict[str, Any]
    ]:

        controls = (
            "RUN",
            "STOP",
            "PAUSE",
            "RESUME",
            "ACTIVATE",
            "DEACTIVATE",
            "REFRESH",
        )

        return [
            self.action_catalog[name].snapshot()
            for name in controls
            if name in self.action_catalog
        ]

    # ======================================================
    # COMMAND-PLANE CAPABILITY SNAPSHOT
    #
    # This observes the actual Dialer command catalog and
    # registry without modifying either.
    # ======================================================

    def get_command_plane_context(
        self,
    ) -> Dict[str, Any]:

        dialer = self.qbit_dialer

        if dialer is None:

            return {
                "attached": False,
                "authority": COMMAND_AUTHORITY,
                "cataloged": [],
                "executable": [],
                "device_controls": {},
            }

        catalog = getattr(
            dialer,
            "command_catalog",
            {},
        )

        registry = getattr(
            dialer,
            "command_registry",
            {},
        )

        if not isinstance(
            catalog,
            dict,
        ):
            catalog = {}

        if not isinstance(
            registry,
            dict,
        ):
            registry = {}

        cataloged = sorted(
            str(name).strip().upper()
            for name in catalog
            if str(name).strip()
        )

        executable = sorted(
            str(name).strip().upper()
            for name, handler in registry.items()
            if callable(handler)
            and str(name).strip()
        )

        controls = {}

        for name in (
            "RUN",
            "STOP",
            "PAUSE",
            "RESUME",
            "ACTIVATE",
            "DEACTIVATE",
            "REFRESH",
        ):

            controls[name] = {
                "cataloged": (
                    name in cataloged
                ),

                "executable": (
                    name in executable
                ),

                "authority": COMMAND_AUTHORITY,

                "admission": COMMAND_ADMISSION,
            }

        return {
            "attached": True,
            "authority": COMMAND_AUTHORITY,
            "admission": COMMAND_ADMISSION,
            "cataloged": cataloged,
            "executable": executable,
            "device_controls": controls,
        }

    # ======================================================
    # DEVICE OBSERVATION
    #
    # No execution.
    # ======================================================

    def get_device_context(
        self,
    ) -> Dict[str, Any]:

        manager = self.device_manager
        registry = self.device_registry

        devices = []

        for source in (
            manager,
            registry,
        ):

            if source is None:
                continue

            try:

                method = getattr(
                    source,
                    "list_devices",
                    None,
                )

                if callable(method):

                    result = method()

                    if inspect.isawaitable(
                        result
                    ):
                        result = None

                    if isinstance(
                        result,
                        dict,
                    ):
                        devices.extend(
                            result.values()
                        )

                    elif isinstance(
                        result,
                        (
                            list,
                            tuple,
                            set,
                        ),
                    ):
                        devices.extend(
                            result
                        )

            except Exception:
                pass

        normalized = []

        seen = set()

        for device in devices:

            marker = id(device)

            if marker in seen:
                continue

            seen.add(marker)

            if isinstance(
                device,
                dict,
            ):
                normalized.append(
                    dict(device)
                )
                continue

            snapshot = None

            for method_name in (
                "to_dict",
                "snapshot",
                "get_state",
            ):

                method = getattr(
                    device,
                    method_name,
                    None,
                )

                if callable(method):

                    try:

                        value = method()

                        if isinstance(
                            value,
                            dict,
                        ):

                            snapshot = dict(
                                value
                            )
                            break

                    except Exception:
                        pass

            if snapshot is None:

                snapshot = {
                    "id": getattr(
                        device,
                        "id",
                        None,
                    ),

                    "name": getattr(
                        device,
                        "name",
                        None,
                    ),

                    "status": getattr(
                        device,
                        "status",
                        None,
                    ),

                    "active": getattr(
                        device,
                        "active",
                        None,
                    ),

                    "online": getattr(
                        device,
                        "online",
                        None,
                    ),
                }

            normalized.append(
                snapshot
            )

        return {
            "device_manager_attached": (
                manager is not None
            ),

            "device_registry_attached": (
                registry is not None
            ),

            "count": len(
                normalized
            ),

            "devices": normalized,

            "controls": [
                "RUN",
                "STOP",
                "PAUSE",
                "RESUME",
                "ACTIVATE",
                "DEACTIVATE",
                "REFRESH",
            ],

            "execution_owner": (
                COMMAND_AUTHORITY
            ),
        }

    # ======================================================
    # ACTION RECORD
    # ======================================================

    def _record_action(
        self,
        action_type: str,
        reason: str,
        success: bool,
        details: Optional[
            Dict[str, Any]
        ] = None,
        reward: int = 0,
        error: Optional[str] = None,
    ) -> Dict[str, Any]:

        timestamp = (
            datetime.datetime.now(
                datetime.timezone.utc
            ).isoformat()
        )

        action_id = hashlib.sha256(
            (
                f"{time.time_ns()}|"
                f"{action_type}|"
                f"{reason}|"
                f"{self.device_id}|"
                f"{self.current_track_id}"
            ).encode(
                "utf-8"
            )
        ).hexdigest()[:16]

        metadata = {

            "id": action_id,
            "timestamp": timestamp,

            "module": self.module_name,
            "version": self.module_version,

            "device_id": self.device_id,

            "channel": MODULE_CHANNEL,

            "source": ACTION_SOURCE,
            "event_kind": ACTION_KIND,

            "qbit_id": self.current_qbit_id,
            "task_id": self.current_task_id,
            "track_id": self.current_track_id,
            "channel_id": self.current_channel_id,
            "pipeline_id": self.current_pipeline_id,

            "action_type": action_type,

            "command": None,

            "command_authority": COMMAND_AUTHORITY,
            "command_admission": COMMAND_ADMISSION,

            "reason": reason,

            "success": bool(
                success
            ),

            "reward": reward,

            "error": error,

            "details": {
                **dict(
                    details or {}
                ),

                "proposal_only": True,
                "execution_required": False,

                "executes_commands": False,
                "submits_commands": False,
            },
        }

        if success:
            self.reward_points += reward

        self.action_history.append(
            metadata
        )

        successful = sum(
            1
            for item
            in self.action_history
            if item.get(
                "success"
            )
        )

        self.success_rate = (
            successful
            / max(
                1,
                len(
                    self.action_history
                ),
            )
        )

        self.last_action = metadata

        self._log_action(
            metadata
        )

        self._emit_action(
            metadata
        )

        self._notify(
            metadata
        )

        return metadata

    # ======================================================
    # FILE LOGGING
    #
    # Logging is telemetry.
    # It is not command execution.
    # ======================================================

    def _log_action(
        self,
        metadata: Dict[str, Any],
    ) -> bool:

        try:

            path = os.path.join(
                self.actions_dir,
                f"{metadata['id']}.json",
            )

            with open(
                path,
                "w",
                encoding="utf-8",
            ) as handle:

                json.dump(
                    metadata,
                    handle,
                    indent=2,
                    ensure_ascii=False,
                )

            return True

        except Exception as exc:

            _log_error(
                "[ActionEngine] Action log failed | %s",
                exc,
            )

            return False

    # ======================================================
    # EVENT / TRACK TELEMETRY
    # ======================================================

    def _emit_action(
        self,
        metadata: Dict[str, Any],
    ) -> bool:

        return self._emit_event(
            ACTION_EVENT_TYPE,
            metadata,

            track_id=metadata.get(
                "track_id"
            ),

            channel=MODULE_CHANNEL,

            source=ACTION_SOURCE,
        )

    def _emit_event(
        self,
        event_type: str,
        payload: Any = None,
        *,
        track_id: Optional[str] = None,
        channel: Optional[str] = None,
        source: str = ACTION_SOURCE,
        priority: int = 0,
    ) -> bool:

        emitted = False

        # --------------------------------------------------
        # Shared EventBus only.
        # --------------------------------------------------

        if self.event_bus is not None:

            try:

                emit_method = getattr(
                    self.event_bus,
                    "emit",
                    None,
                )

                if callable(
                    emit_method
                ):

                    try:

                        result = emit_method(
                            event_type,
                            payload,
                            source=source,
                            channel=channel,
                            track_id=track_id,
                            device_id=self.device_id,
                            priority=priority,
                        )

                    except TypeError:

                        result = emit_method(
                            event_type,
                            payload,
                        )

                    emitted = (
                        True
                        if result is None
                        else bool(result)
                    )

            except Exception as exc:

                _log_warning(
                    "[ActionEngine] EventBus emit failed | "
                    "event=%s | error=%s",
                    event_type,
                    exc,
                )

        # --------------------------------------------------
        # Optional external emitter.
        # --------------------------------------------------

        if callable(
            self.emit
        ):

            try:

                result = self.emit(
                    event_type,
                    payload,
                )

                emitted = (
                    emitted
                    or result is None
                    or bool(result)
                )

            except TypeError:

                try:

                    result = self.emit(
                        payload
                    )

                    emitted = (
                        emitted
                        or result is None
                        or bool(result)
                    )

                except Exception:
                    pass

            except Exception:
                pass

        # --------------------------------------------------
        # Existing track callback.
        # --------------------------------------------------

        if callable(
            self.track
        ):

            try:

                self.track(
                    stage=MODULE_CHANNEL,
                    payload=payload,
                    priority=priority,
                    track_id=track_id,
                )

            except TypeError:

                try:
                    self.track(
                        payload
                    )
                except Exception:
                    pass

            except Exception:
                pass

        # --------------------------------------------------
        # Existing TrackSystem.
        # --------------------------------------------------

        if self.track_system is not None:

            try:

                method = getattr(
                    self.track_system,
                    "track",
                    None,
                )

                if callable(
                    method
                ):

                    try:

                        method(
                            stage=MODULE_CHANNEL,
                            payload=payload,
                            priority=priority,
                            track_id=track_id,
                        )

                    except TypeError:

                        method(
                            payload
                        )

            except Exception as exc:

                _log_debug(
                    "[ActionEngine] TrackSystem telemetry failed | %s",
                    exc,
                )

        return emitted

    # ======================================================
    # SYSTEM SNAPSHOT
    # ======================================================

    def seed_track(
        self,
    ) -> Dict[str, Any]:

        try:
            import psutil
        except ImportError:
            psutil = None

        cpu = None
        memory_used_mb = None
        memory_percent = None
        disk_percent = None

        if psutil is not None:

            try:
                cpu = psutil.cpu_percent(
                    interval=None
                )
            except Exception:
                pass

            try:

                memory = psutil.virtual_memory()

                memory_used_mb = round(
                    memory.used
                    / (
                        1024 * 1024
                    ),
                    2,
                )

                memory_percent = (
                    memory.percent
                )

            except Exception:
                pass

            try:

                disk_percent = (
                    psutil.disk_usage(
                        self.storage_root
                    ).percent
                )

            except Exception:
                pass

        return {

            "module": self.module_name,
            "version": self.module_version,

            "device_id": self.device_id,

            "cpu_percent": cpu,
            "memory_used_mb": memory_used_mb,
            "memory_percent": memory_percent,
            "disk_percent": disk_percent,

            "qbit_status": (
                self._get_qbit_status()
            ),

            "qbit_id": self.current_qbit_id,
            "task_id": self.current_task_id,
            "track_id": self.current_track_id,
            "channel_id": self.current_channel_id,
            "pipeline_id": self.current_pipeline_id,

            "action_count": len(
                self.action_history
            ),

            "proposal_count": len(
                self.proposal_history
            ),

            "action_catalog_size": len(
                self.action_catalog
            ),

            "discovered_action_count": len(
                self.discovered_actions
            ),

            "reward_points": self.reward_points,
            "success_rate": self.success_rate,

            "running": self.running,

            "qbit_attached": (
                self.qbit is not None
            ),

            "qbit_dialer_attached": (
                self.qbit_dialer is not None
            ),

            "qbit_queue_loop_attached": (
                self.qbit_queue_loop is not None
            ),

            "compute_brain_attached": (
                self.compute_brain is not None
            ),

            "transformer_brain_attached": (
                self.transformer_brain is not None
            ),

            "ethics_attached": (
                self.ethics is not None
            ),

            "track_system_attached": (
                self.track_system is not None
            ),

            "registry_attached": (
                self.registry is not None
            ),

            "oracle_attached": (
                self.oracle is not None
            ),

            "heartbeat_attached": (
                self.heartbeat is not None
            ),

            "encoder_attached": (
                self.encoder is not None
            ),

            "decoder_attached": (
                self.decoder is not None
            ),

            "device_manager_attached": (
                self.device_manager is not None
            ),

            "device_registry_attached": (
                self.device_registry is not None
            ),

            "command_authority": (
                COMMAND_AUTHORITY
            ),

            "command_admission": (
                COMMAND_ADMISSION
            ),

            "executes_commands": False,
            "submits_commands": False,

            "creates_qbits": False,
            "creates_queues": False,
            "creates_workers": False,
            "creates_event_bus": False,
        }

    def get_state(
        self,
    ) -> Dict[str, Any]:

        return self.seed_track()

    # ======================================================
    # QBIT STATUS
    # ======================================================

    def _get_qbit_status(
        self,
    ) -> Any:

        try:

            qbit = self.qbit

            if qbit is None:
                return "NOT_ATTACHED"

            status = getattr(
                qbit,
                "status",
                None,
            )

            if callable(
                status
            ):

                return status()

            if status is not None:
                return status

            return "AVAILABLE"

        except Exception as exc:

            return {
                "state": "ERROR",
                "error": str(exc),
            }

    # ======================================================
    # SOURCE FILE DISCOVERY
    #
    # AST only.
    #
    # The source is inspected without importing/executing it.
    # ======================================================

    def discover_actions_from_source(
        self,
        path: str,
    ) -> List[
        ActionDefinition
    ]:

        results: List[
            ActionDefinition
        ] = []

        if not path:
            return results

        try:

            if not os.path.isfile(
                path
            ):
                return results

            with open(
                path,
                "r",
                encoding="utf-8",
            ) as handle:

                source = handle.read()

            tree = ast.parse(
                source,
                filename=path,
            )

            module_name = os.path.splitext(
                os.path.basename(path)
            )[0]

            for node in ast.walk(
                tree
            ):

                if not isinstance(
                    node,
                    (
                        ast.FunctionDef,
                        ast.AsyncFunctionDef,
                    ),
                ):
                    continue

                name = node.name

                if not self._looks_action_capable(
                    name
                ):
                    continue

                action_name = (
                    self._normalize_action_name(
                        name
                    )
                )

                handler_key = (
                    self._infer_handler_key(
                        action_name
                    )
                )

                definition = ActionDefinition(

                    name=action_name,

                    source="source_discovery",

                    module=module_name,

                    category=self._infer_category(
                        action_name
                    ),

                    description=(
                        ast.get_docstring(
                            node
                        )
                        or ""
                    )[:1000],

                    callable_name=name,

                    callable_ref=None,

                    risk=self._infer_risk(
                        action_name
                    ),

                    requires_authorization=(
                        action_name
                        not in {
                            "OBSERVE",
                            "REFRESH",
                            "STATUS",
                            "INSPECT",
                        }
                    ),

                    proposal_only=True,

                    execution_required=(
                        handler_key is not None
                    ),

                    discovered=True,

                    builtin=False,

                    handler_key=handler_key,

                    execution_owner=COMMAND_AUTHORITY,

                    metadata={

                        "path": os.path.abspath(
                            path
                        ),

                        "line": getattr(
                            node,
                            "lineno",
                            None,
                        ),

                        "async": isinstance(
                            node,
                            ast.AsyncFunctionDef,
                        ),

                        "source_only": True,

                        "authority": COMMAND_AUTHORITY,

                        "execution_via": (
                            COMMAND_ADMISSION
                        ),
                    },
                )

                results.append(
                    definition
                )

                self.action_catalog[
                    action_name
                ] = definition

                self.discovered_actions[
                    action_name
                ] = definition

            self._emit_event(
                "ACTION_SOURCE_DISCOVERY",
                {
                    "path": os.path.abspath(
                        path
                    ),

                    "module": module_name,

                    "actions": len(
                        results
                    ),
                },
            )

        except Exception as exc:

            self.discovery_errors.append(
                {
                    "path": path,
                    "error": str(exc),
                }
            )

            _log_warning(
                "[ActionEngine] Source discovery failed | "
                "path=%s | error=%s",
                path,
                exc,
            )

        return results

    # ======================================================
    # UTILITY
    # ======================================================

    @staticmethod
    def _first_value(
        data: Dict[str, Any],
        keys: Iterable[str],
    ) -> Optional[str]:

        for key in keys:

            try:
                value = data.get(
                    key
                )
            except Exception:
                value = None

            if value is None:
                continue

            try:
                return str(
                    value
                )
            except Exception:
                continue

        return None

    @staticmethod
    def _module_name(
        value: Any,
    ) -> str:

        try:

            if isinstance(
                value,
                str,
            ):
                return value

            return str(
                getattr(
                    value,
                    "__name__",
                    value.__class__.__name__,
                )
            )

        except Exception:

            return "UNKNOWN"

    @staticmethod
    def _safe_signature(
        value: Callable,
    ) -> Optional[str]:

        try:

            return str(
                inspect.signature(
                    value
                )
            )

        except Exception:

            return None

    @staticmethod
    def _safe_float(
        value: Any,
    ) -> float:

        try:
            return float(
                value
            )

        except (
            TypeError,
            ValueError,
        ):

            return 0.0

    @staticmethod
    def _normalize_action_name(
        name: str,
    ) -> str:

        value = str(
            name
        ).strip()

        if not value:
            return ""

        if value.startswith(
            "_"
        ):

            value = value.lstrip(
                "_"
            )

        return value.upper()

    @staticmethod
    def _safe_identifier(
        value: Any,
    ) -> str:

        if value is None:
            return ""

        value = str(
            value
        ).strip()

        allowed = (
            "abcdefghijklmnopqrstuvwxyz"
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            "0123456789_"
        )

        cleaned = "".join(
            char
            if char in allowed
            else "_"
            for char in value
        )

        return cleaned.strip(
            "_"
        )


# ==========================================================
# MODULE EXPORTS
# ==========================================================

__all__ = [

    "Action",

    "ActionDefinition",
    "ActionProposal",

    "ActionEngine",

    # AI
    "ObserveSystem",
    "AnalyzeSystem",
    "ResearchSystem",
    "LearnFromResult",
    "GenerateImprovement",
    "EvaluateProposal",

    # System control
    "RepairSystem",
    "OptimizeSystem",
    "ResetSystem",
    "EnableChannel",
    "DisableChannel",

    # Qbit
    "StabilizeQbit",
    "SyncQbit",
    "InspectQueue",
    "InspectDialer",

    # Device
    "RunDevice",
    "StopDevice",
    "PauseDevice",
    "ResumeDevice",
    "ActivateDevice",
    "DeactivateDevice",
    "RefreshDevice",
    "DeviceManagerControl",

    "BUILTIN_ACTIONS",

    "MODULE_NAME",
    "MODULE_VERSION",
    "MODULE_ROLE",
    "MODULE_CHANNEL",

    "COMMAND_AUTHORITY",
    "COMMAND_ADMISSION",
]