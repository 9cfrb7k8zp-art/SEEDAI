# ==========================================================
# FILE: neural_bridge.py
# PATH: C:\SEED_ROOT\seed\core\neural\neural_bridge.py
#
# SEED AI OS :: NEURAL BRIDGE
# VERSION: 2.2.0
# BUILD: SYSTEM-INTEGRATED / REGISTRY-RUNTIME-AWARE /
#        QBIT-SAFE / FATHUD-AWARE / NODE-REGISTERED
#
# ROLE:
# Neural representation + dependency coordination bridge.
#
# ARCHITECTURE:
#
# SRegistry
# |
# v
# registry_runtime
# |
# v
# Node_Registry
# |
# v
# NeuralBridge
# |
# +----> ComputeBrain
# |
# +----> TransformerBrain
# |
# +----> Analytics / observation
# |
# v
# QbitDialer
# |
# v
# submit_command()
#
# IMPORTANT:
#
# NeuralBridge DOES NOT:
# - create QbitQueueLoop
# - create EventBus
# - create QbitDialer
# - create a second registry
# - create a second runtime
# - create a second Qbit
# - execute commands directly
# - bypass QbitDialer.submit_command()
# - replace the authoritative Qbit
# - become FATHUD command authority
# - become HUD command authority
#
# NeuralBridge DOES:
# - discover registered nodes/modules
# - resolve live runtime authorities
# - inspect dependencies
# - convert Qbit information into neural representation
# - preserve Qbit identity and lineage
# - ask cognitive questions
# - produce observations/proposals
# - route proposed work toward QbitDialer
# - observe execution results
# - support adaptive recovery planning
# - publish safe telemetry
# - register itself as a runtime node/provider
# - expose live status to FATHUD
#
# REGISTRY-RUNTIME CONTRACT:
#
# SRegistry:
# WHAT EXISTS?
#
# registry_runtime:
# WHAT STATE IS IT IN?
# WHICH LIVE AUTHORITATIVE INSTANCE PROVIDES IT?
#
# NeuralBridge:
# WHAT DOES THE CONSUMER NEED?
# WHEN CAN IT RECEIVE IT?
#
# registry_runtime stores live provider references privately
# under provider["_ref"]. NeuralBridge consumes those live
# references and never manufactures replacements.
#
# QBIT SAFETY CONTRACT:
#
# self.qbit:
#     authoritative runtime Qbit anchor.
#
# self.last_qbit:
#     most recently processed/evolving Qbit.
#
# These may legitimately differ when an evolved Qbit enters
# the cognitive pipeline. Difference does NOT mean that the
# authoritative runtime Qbit was replaced.
#
# SERIALIZATION SAFETY:
#
# Live runtime authorities are NEVER deep-copied into:
# - cognitive context
# - status payloads
# - health payloads
# - TrackSystem telemetry
# - EventBus telemetry
# - FATHUD telemetry
#
# This prevents failures such as:
#
# TypeError:
# cannot pickle '_contextvars.Context' object
#
# ==========================================================

from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import logging
import math
import time
from typing import Any, Dict, Iterable, List, Optional


# ==========================================================
# LOGGING
# ==========================================================

logger = logging.getLogger("NeuralBridge")


# ==========================================================
# STATES
# ==========================================================

STATE_OFFLINE = "OFFLINE"
STATE_WAITING = "WAITING"
STATE_READY = "READY"
STATE_ACTIVE = "ACTIVE"
STATE_DEGRADED = "DEGRADED"
STATE_FAILED = "FAILED"
STATE_STOPPED = "STOPPED"


# ==========================================================
# DEPENDENCY STATES
# ==========================================================

DEP_PENDING = "PENDING"
DEP_READY = "READY"
DEP_MISSING = "MISSING"
DEP_INVALID = "INVALID"
DEP_BOUND = "BOUND"


# ==========================================================
# HELPERS
# ==========================================================

def _safe_bool(value: Any) -> bool:
    return bool(value)


def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:

    try:
        value = float(value)

        if math.isfinite(value):
            return value

    except Exception:
        pass

    return default


def _stable_json(value: Any) -> str:

    try:
        return json.dumps(
            value,
            sort_keys=True,
            default=str,
            separators=(",", ":"),
        )

    except Exception:
        return repr(value)


def _safe_snapshot(
    value: Any,
    *,
    depth: int = 0,
    max_depth: int = 8,
    max_items: int = 256,
) -> Any:

    if depth > max_depth:
        return "<MAX_DEPTH>"

    if value is None:
        return None

    if isinstance(
        value,
        (
            str,
            int,
            float,
            bool,
        ),
    ):
        if isinstance(value, float):
            if not math.isfinite(value):
                return str(value)

        return value

    if isinstance(value, bytes):
        try:
            return value.decode(
                "utf-8",
                errors="replace",
            )
        except Exception:
            return f"<bytes:{len(value)}>"

    if isinstance(value, dict):

        result = {}

        try:
            items = list(
                value.items()
            )[:max_items]

        except Exception:
            return {
                "type": type(value).__name__,
                "repr": repr(value),
            }

        for key, item in items:

            try:
                safe_key = (
                    key
                    if isinstance(
                        key,
                        (
                            str,
                            int,
                            float,
                            bool,
                        ),
                    )
                    else str(key)
                )

                result[str(safe_key)] = _safe_snapshot(
                    item,
                    depth=depth + 1,
                    max_depth=max_depth,
                    max_items=max_items,
                )

            except Exception:
                result[str(key)] = (
                    "<UNSERIALIZABLE>"
                )

        return result

    if isinstance(
        value,
        (
            list,
            tuple,
            set,
            frozenset,
        ),
    ):

        result = []

        try:
            iterable = list(value)[
                :max_items
            ]

        except Exception:
            return {
                "type": type(value).__name__,
                "repr": repr(value),
            }

        for item in iterable:

            result.append(
                _safe_snapshot(
                    item,
                    depth=depth + 1,
                    max_depth=max_depth,
                    max_items=max_items,
                )
            )

        return result

    # ------------------------------------------------------
    # Dataclass / object-style values.
    #
    # Only inspect simple public attributes.
    # Never deepcopy the object.
    # ------------------------------------------------------

    if hasattr(
        value,
        "__dict__",
    ):

        try:

            public = {}

            for key, item in list(
                vars(value).items()
            )[:max_items]:

                if str(key).startswith("_"):
                    continue

                # Avoid recursively walking obvious
                # runtime machinery.
                if key in {
                    "loop",
                    "_loop",
                    "event_loop",
                    "_event_loop",
                    "queue",
                    "_queue",
                    "lock",
                    "_lock",
                    "task",
                    "_task",
                    "thread",
                    "_thread",
                    "executor",
                    "socket",
                    "_socket",
                    "callbacks",
                    "_callbacks",
                }:
                    continue

                try:
                    public[str(key)] = (
                        _safe_snapshot(
                            item,
                            depth=depth + 1,
                            max_depth=max_depth,
                            max_items=max_items,
                        )
                    )

                except Exception:
                    public[str(key)] = (
                        "<UNSERIALIZABLE>"
                    )

            return {
                "type": type(value).__name__,
                "attributes": public,
            }

        except Exception:
            pass

    # ------------------------------------------------------
    # Final safe representation.
    # ------------------------------------------------------

    try:
        return {
            "type": type(value).__name__,
            "repr": repr(value),
        }

    except Exception:
        return {
            "type": type(value).__name__,
        }


def _get_field(
    obj: Any,
    name: str,
    default: Any = None,
) -> Any:

    if obj is None:
        return default

    if isinstance(obj, dict):
        return obj.get(
            name,
            default,
        )

    try:
        return getattr(
            obj,
            name,
        )

    except Exception:
        return default


def _set_if_supported(
    obj: Any,
    name: str,
    value: Any,
) -> bool:

    if obj is None:
        return False

    if isinstance(obj, dict):
        obj[name] = value
        return True

    try:
        setattr(
            obj,
            name,
            value,
        )

        return True

    except Exception:
        return False


# ==========================================================
# NEURAL BRIDGE
# ==========================================================

class NeuralBridge:

    VERSION = "2.2.0"

    NODE_NAME = "NeuralBridge"

    NODE_ROLE = "neural_bridge"

    PROVIDER_NAME = "neural_bridge"

    # ------------------------------------------------------
    # CAPABILITIES
    # ------------------------------------------------------

    CAPABILITIES = (
        "neural_representation",
        "qbit_processing",
        "cognitive_context",
        "observation",
        "proposal",
        "adaptive_recovery",
        "lineage_tracking",
        "runtime_dependency_resolution",
        "fathud_telemetry",
    )

    # ------------------------------------------------------
    # CONSTRUCTOR
    # ------------------------------------------------------

    def __init__(
        self,
        *,
        registry=None,
        registry_runtime=None,
        qbit_queue_loop=None,
        event_bus=None,
        track_system=None,
        runtime_context=None,
        compute_brain=None,
        transformer_brain=None,
        qbit_dialer=None,
        fathud=None,
        encoder=None,
        kernel_bus=None,
        node_registry=None,
        seed_core=None,
        qbit=None,
        intent_engine=None,
        action_engine=None,
        analytics_engine=None,
        adaptive_engine=None,
        adaptive_priority_engine=None,
        track_context=None,
        growth_tree=None,
        cognition_map=None,
        cognitive_clock=None,
        cognitive_scheduler=None,
        goal_engine=None,
        cognition_node=None,
        cognition_binary_encoder=None,
        cognition_load_balancer=None,
        logger_instance=None,
    ):

        self.logger = (
            logger_instance
            if logger_instance is not None
            else logger
        )

        # --------------------------------------------------
        # AUTHORITATIVE RUNTIME REFERENCES
        # --------------------------------------------------

        self.registry = registry
        self.registry_runtime = registry_runtime

        self.qbit = qbit

        self.qbit_queue_loop = qbit_queue_loop
        self.event_bus = event_bus
        self.track_system = track_system
        self.runtime_context = runtime_context

        self.compute_brain = compute_brain
        self.transformer_brain = transformer_brain
        self.qbit_dialer = qbit_dialer

        # FATHUD is observer/telemetry only.
        self.fathud = fathud

        self.encoder = encoder
        self.kernel_bus = kernel_bus
        self.node_registry = node_registry
        self.seed_core = seed_core

        # --------------------------------------------------
        # COGNITION RUNTIME REFERENCES
        # --------------------------------------------------

        self.intent_engine = intent_engine
        self.action_engine = action_engine
        self.analytics_engine = analytics_engine
        self.adaptive_engine = adaptive_engine
        self.adaptive_priority_engine = adaptive_priority_engine
        self.track_context = track_context
        self.growth_tree = growth_tree
        self.cognition_map = cognition_map
        self.cognitive_clock = cognitive_clock
        self.cognitive_scheduler = cognitive_scheduler
        self.goal_engine = goal_engine
        self.cognition_node = cognition_node
        self.cognition_binary_encoder = cognition_binary_encoder
        self.cognition_load_balancer = cognition_load_balancer

        # --------------------------------------------------
        # LIFECYCLE
        # --------------------------------------------------

        self.state = STATE_OFFLINE
        self.running = False
        self.active = False

        # --------------------------------------------------
        # DEPENDENCY STATE
        # --------------------------------------------------

        self.dependencies: Dict[
            str,
            Dict[str, Any],
        ] = {}

        # --------------------------------------------------
        # REGISTRY/NODE STATE
        # --------------------------------------------------

        self.node_registered = False
        self.runtime_provider_registered = False

        self.node_path = None

        # --------------------------------------------------
        # FATHUD STATE
        # --------------------------------------------------

        self.fathud_bound = False
        self.last_fathud_status = None

        # --------------------------------------------------
        # NEURAL MODEL STATE
        # --------------------------------------------------

        self.model_loaded = False
        self.model_name = None
        self.model_version = None

        # --------------------------------------------------
        # QBIT / LINEAGE STATE
        #
        # self.qbit:
        #     authoritative runtime Qbit reference.
        #
        # self.last_qbit:
        #     most recently processed/evolving Qbit.
        # --------------------------------------------------

        self.last_qbit = None
        self.last_qbit_id = None
        self.last_track_id = None
        self.last_parent_qbit_id = None
        self.last_vector = None

        # --------------------------------------------------
        # COGNITIVE STATE
        # --------------------------------------------------

        self.last_thought = None
        self.last_question = None
        self.last_proposal = None
        self.last_execution_result = None
        self.last_recovery_proposal = None

        self.cycle_count = 0
        self.question_count = 0
        self.proposal_count = 0
        self.execution_observation_count = 0

        # --------------------------------------------------
        # HEALTH
        # --------------------------------------------------

        self.errors: List[
            Dict[str, Any]
        ] = []

        self.warnings: List[
            Dict[str, Any]
        ] = []

        # --------------------------------------------------
        # REQUIRED DEPENDENCY DECLARATION
        # --------------------------------------------------

        self._declare_dependencies()

        # --------------------------------------------------
        # INITIAL RESOLUTION
        # --------------------------------------------------

        self._resolve_runtime_context()

        self._resolve_registry_runtime_dependencies()

        self.discover_dependencies()

        # --------------------------------------------------
        # REGISTRY / NODE INTEGRATION
        # --------------------------------------------------

        self._register_sregistry_node()

        self._register_registry_runtime_provider()

        # --------------------------------------------------
        # FATHUD INTEGRATION
        # --------------------------------------------------

        self._bind_fathud()

        # --------------------------------------------------
        # LIFECYCLE STATE
        # --------------------------------------------------

        if self.dependencies_ready():
            self.state = STATE_READY
        else:
            self.state = STATE_WAITING

        # --------------------------------------------------
        # MODEL
        # --------------------------------------------------

        self._load_neural_model()

        # --------------------------------------------------
        # STATUS PUBLICATION
        # --------------------------------------------------

        self._update_registry_runtime_state(
            self.state
        )

        self._publish_fathud_status()

        self.logger.info(
            "[NeuralBridge] initialized | "
            "state=%s | "
            "qbit=%s | "
            "queue_loop=%s | "
            "event_bus=%s | "
            "track_system=%s | "
            "dialer=%s | "
            "registry=%s | "
            "registry_runtime=%s | "
            "node_registry=%s | "
            "fathud=%s",
            self.state,
            type(self.qbit).__name__
            if self.qbit is not None
            else "NONE",
            type(self.qbit_queue_loop).__name__
            if self.qbit_queue_loop is not None
            else "NONE",
            type(self.event_bus).__name__
            if self.event_bus is not None
            else "NONE",
            type(self.track_system).__name__
            if self.track_system is not None
            else "NONE",
            type(self.qbit_dialer).__name__
            if self.qbit_dialer is not None
            else "NONE",
            type(self.registry).__name__
            if self.registry is not None
            else "NONE",
            type(self.registry_runtime).__name__
            if self.registry_runtime is not None
            else "NONE",
            type(self.node_registry).__name__
            if self.node_registry is not None
            else "NONE",
            type(self.fathud).__name__
            if self.fathud is not None
            else "NONE",
        )

    # ======================================================
    # DEPENDENCY DECLARATION
    # ======================================================

    def _declare_dependencies(self):

        self.dependencies = {
            "registry": {
                "required": True,
                "state": DEP_PENDING,
                "reference": None,
            },

            "registry_runtime": {
                "required": False,
                "state": DEP_PENDING,
                "reference": None,
            },

            "qbit": {
                "required": False,
                "state": DEP_PENDING,
                "reference": None,
            },

            "qbit_queue_loop": {
                "required": True,
                "state": DEP_PENDING,
                "reference": None,
            },

            "event_bus": {
                "required": True,
                "state": DEP_PENDING,
                "reference": None,
            },

            "track_system": {
                "required": True,
                "state": DEP_PENDING,
                "reference": None,
            },

            "qbit_dialer": {
                "required": True,
                "state": DEP_PENDING,
                "reference": None,
            },

            "compute_brain": {
                "required": False,
                "state": DEP_PENDING,
                "reference": None,
            },

            "transformer_brain": {
                "required": False,
                "state": DEP_PENDING,
                "reference": None,
            },

            "node_registry": {
                "required": False,
                "state": DEP_PENDING,
                "reference": None,
            },
        }

    # ======================================================
    # RUNTIME CONTEXT
    # ======================================================

    def _resolve_runtime_context(self):

        context = self.runtime_context

        if context is None:
            return

        names = {
            "registry": (
                "registry",
                "system_registry",
                "seed_registry",
            ),

            "registry_runtime": (
                "registry_runtime",
            ),

            "node_registry": (
                "node_registry",
                "nodes",
                "runtime_nodes",
            ),

            "qbit": (
                "qbit",
            ),

            "event_bus": (
                "event_bus",
            ),

            "qbit_queue_loop": (
                "qbit_queue_loop",
                "queue_loop",
                "qbit_loop",
            ),

            "qbit_dialer": (
                "qbit_dialer",
            ),

            "track_system": (
                "track_system",
            ),

            "compute_brain": (
                "compute_brain",
            ),

            "transformer_brain": (
                "transformer_brain",
            ),

            "seed_core": (
                "seed_core",
                "seedcore",
            ),

            "fathud": (
                "fathud",
                "fat_hud_adapter",
            ),
        }

        for target, candidates in names.items():

            current = getattr(
                self,
                target,
                None,
            )

            if current is not None:
                continue

            for name in candidates:

                candidate = _get_field(
                    context,
                    name,
                    None,
                )

                if candidate is not None:

                    setattr(
                        self,
                        target,
                        candidate,
                    )

                    break

        self._capture_qbit_from_runtime()

    def _capture_qbit_from_runtime(self):

        qbit = self.qbit

        if qbit is None:

            qbit = _get_field(
                self.runtime_context,
                "qbit",
                None,
            )

        if qbit is None:
            return

        if (
            self.qbit is not None
            and self.qbit is not qbit
        ):

            raise RuntimeError(
                "[NeuralBridge] authoritative "
                "Qbit identity mismatch"
            )

        self.qbit = qbit

        if self.last_qbit is None:
            self.last_qbit = qbit

    # ======================================================
    # REGISTRY-RUNTIME LIVE PROVIDER RESOLUTION
    # ======================================================

    def _registry_runtime_api(
        self,
        name: str,
    ):

        runtime = self.registry_runtime

        if runtime is None:
            return None

        method = getattr(
            runtime,
            name,
            None,
        )

        if callable(method):
            return method

        return None

    def _get_live_runtime_provider(
        self,
        *names: str,
    ):

        runtime = self.registry_runtime

        if runtime is None:
            return None

        getter = self._registry_runtime_api(
            "get_dependency_provider"
        )

        if getter is None:
            return None

        for name in names:

            try:

                provider = getter(
                    name,
                    include_reference=True,
                )

            except TypeError:

                try:

                    provider = getter(
                        name,
                    )

                except Exception as exc:

                    self._record_error(
                        "registry_runtime_provider",
                        exc,
                    )

                    continue

            except Exception as exc:

                self._record_error(
                    "registry_runtime_provider",
                    exc,
                )

                continue

            if provider is None:
                continue

            # registry_runtime stores the actual live
            # object privately under "_ref".
            if isinstance(
                provider,
                dict,
            ):

                reference = provider.get(
                    "_ref"
                )

                if reference is not None:
                    return reference

                reference = provider.get(
                    "reference"
                )

                if reference is not None:
                    return reference

                continue

            return provider

        return None

    def _bind_registry_runtime_reference(
        self,
        attribute_name: str,
        reference: Any,
        *,
        authoritative: bool = True,
    ) -> bool:

        if reference is None:
            return False

        current = getattr(
            self,
            attribute_name,
            None,
        )

        if current is None:

            setattr(
                self,
                attribute_name,
                reference,
            )

            return True

        if current is reference:
            return True

        if authoritative:

            raise RuntimeError(
                "[NeuralBridge] registry_runtime "
                f"identity mismatch for {attribute_name}"
            )

        return False

    def _resolve_registry_runtime_dependencies(
        self,
    ):

        runtime = self.registry_runtime

        if runtime is None:
            return False

        resolved = False

        provider_map = {
            "registry": (
                "registry",
                "system_registry",
                "seed_registry",
            ),

            "qbit": (
                "qbit",
                "authoritative_qbit",
            ),

            "qbit_queue_loop": (
                "qbit_queue_loop",
                "queue_loop",
                "qbit_loop",
            ),

            "event_bus": (
                "event_bus",
                "authoritative_event_bus",
            ),

            "track_system": (
                "track_system",
                "authoritative_track_system",
            ),

            "qbit_dialer": (
                "qbit_dialer",
                "dialer",
                "authoritative_qbit_dialer",
            ),

            "compute_brain": (
                "compute_brain",
                "compute",
            ),

            "transformer_brain": (
                "transformer_brain",
                "transformer",
            ),

            "node_registry": (
                "node_registry",
                "nodes",
                "runtime_nodes",
            ),
        }

        authoritative_names = {
            "qbit",
            "qbit_queue_loop",
            "event_bus",
            "track_system",
            "qbit_dialer",
            "compute_brain",
            "transformer_brain",
        }

        for attribute_name, provider_names in provider_map.items():

            current = getattr(
                self,
                attribute_name,
                None,
            )

            reference = self._get_live_runtime_provider(
                *provider_names
            )

            if reference is None:
                continue

            if current is None:

                self._bind_registry_runtime_reference(
                    attribute_name,
                    reference,
                    authoritative=(
                        attribute_name
                        in authoritative_names
                    ),
                )

                resolved = True
                continue

            if current is reference:
                resolved = True
                continue

            if attribute_name in authoritative_names:

                raise RuntimeError(
                    "[NeuralBridge] registry_runtime "
                    f"authoritative identity mismatch "
                    f"for {attribute_name}"
                )

            setattr(
                self,
                attribute_name,
                reference,
            )

            resolved = True

        self._capture_qbit_from_runtime()

        return resolved

    # ======================================================
    # RUNTIME BINDING
    # ======================================================

    def bind_runtime(
        self,
        *,
        registry=None,
        registry_runtime=None,
        qbit_queue_loop=None,
        event_bus=None,
        track_system=None,
        runtime_context=None,
        compute_brain=None,
        transformer_brain=None,
        qbit_dialer=None,
        fathud=None,
        node_registry=None,
        seed_core=None,
        qbit=None,
        intent_engine=None,
        action_engine=None,
        analytics_engine=None,
        adaptive_engine=None,
        adaptive_priority_engine=None,
        track_context=None,
        growth_tree=None,
        cognition_map=None,
        cognitive_clock=None,
        cognitive_scheduler=None,
        goal_engine=None,
        cognition_node=None,
        cognition_binary_encoder=None,
        cognition_load_balancer=None,
    ):

        if runtime_context is not None:
            self.runtime_context = runtime_context

        incoming = {
            "registry": registry,
            "registry_runtime": registry_runtime,
            "qbit_queue_loop": qbit_queue_loop,
            "event_bus": event_bus,
            "track_system": track_system,
            "compute_brain": compute_brain,
            "transformer_brain": transformer_brain,
            "qbit_dialer": qbit_dialer,
            "fathud": fathud,
            "node_registry": node_registry,
            "seed_core": seed_core,
            "intent_engine": intent_engine,
            "action_engine": action_engine,
            "analytics_engine": analytics_engine,
            "adaptive_engine": adaptive_engine,
            "adaptive_priority_engine": adaptive_priority_engine,
            "track_context": track_context,
            "growth_tree": growth_tree,
            "cognition_map": cognition_map,
            "cognitive_clock": cognitive_clock,
            "cognitive_scheduler": cognitive_scheduler,
            "goal_engine": goal_engine,
            "cognition_node": cognition_node,
            "cognition_binary_encoder": cognition_binary_encoder,
            "cognition_load_balancer": cognition_load_balancer,
        }

        for name, candidate in incoming.items():

            if candidate is None:
                continue

            current = getattr(
                self,
                name,
                None,
            )

            if current is None:

                setattr(
                    self,
                    name,
                    candidate,
                )

                continue

            if current is candidate:
                continue

            # --------------------------------------------------
            # Runtime authorities cannot be silently replaced.
            # --------------------------------------------------

            if name in {
                "qbit_queue_loop",
                "event_bus",
                "track_system",
                "qbit_dialer",
                "compute_brain",
                "transformer_brain",
            }:

                raise RuntimeError(
                    "[NeuralBridge] authoritative identity "
                    f"mismatch for {name}"
                )

            # --------------------------------------------------
            # Registry metadata / observer refs may refresh.
            # --------------------------------------------------

            if name in {
                "registry",
                "registry_runtime",
                "node_registry",
                "fathud",
                "seed_core",
            }:

                setattr(
                    self,
                    name,
                    candidate,
                )

        # ------------------------------------------------------
        # Authoritative Qbit binding.
        # ------------------------------------------------------

        if qbit is not None:

            if (
                self.qbit is not None
                and self.qbit is not qbit
            ):

                raise RuntimeError(
                    "[NeuralBridge] authoritative Qbit "
                    "identity mismatch"
                )

            self.qbit = qbit

            if self.last_qbit is None:
                self.last_qbit = qbit

        # ------------------------------------------------------
        # Runtime context can supply late dependencies.
        # ------------------------------------------------------

        self._resolve_runtime_context()

        # ------------------------------------------------------
        # registry_runtime supplies live authorities.
        # ------------------------------------------------------

        self._resolve_registry_runtime_dependencies()

        self.discover_dependencies()

        # ------------------------------------------------------
        # Register after late binding.
        # ------------------------------------------------------

        self._register_sregistry_node()

        self._register_registry_runtime_provider()

        self._bind_fathud()

        if self.dependencies_ready():
            self.state = STATE_READY
        else:
            self.state = STATE_WAITING

        self._update_registry_runtime_state(
            self.state
        )

        self._publish_fathud_status()

        self.logger.info(
            "[NeuralBridge] runtime bound | "
            "state=%s | "
            "qbit=%s | "
            "queue_loop=%s | "
            "dialer=%s | "
            "registry_runtime=%s | "
            "fathud=%s",
            self.state,
            type(self.qbit).__name__
            if self.qbit is not None
            else "NONE",
            type(self.qbit_queue_loop).__name__
            if self.qbit_queue_loop is not None
            else "NONE",
            type(self.qbit_dialer).__name__
            if self.qbit_dialer is not None
            else "NONE",
            type(self.registry_runtime).__name__
            if self.registry_runtime is not None
            else "NONE",
            type(self.fathud).__name__
            if self.fathud is not None
            else "NONE",
        )

        return self.status()

    # ======================================================
    # DEPENDENCY DISCOVERY
    # ======================================================

    def discover_dependencies(self):

        try:

            self._resolve_registry_runtime_dependencies()

        except RuntimeError as exc:

            self._record_error(
                "registry_runtime_identity",
                exc,
            )

            raise

        for name, record in self.dependencies.items():

            reference = getattr(
                self,
                name,
                None,
            )

            if reference is None:

                record["reference"] = None

                if record["required"]:
                    record["state"] = DEP_MISSING
                else:
                    record["state"] = DEP_PENDING

                continue

            # --------------------------------------------------
            # IMPORTANT:
            #
            # Keep live reference internally.
            # Never deepcopy it.
            # --------------------------------------------------

            record["reference"] = reference
            record["state"] = DEP_BOUND

        return self.dependencies

    def dependencies_ready(self) -> bool:

        for record in self.dependencies.values():

            if not record["required"]:
                continue

            if record["reference"] is None:
                return False

        return True

    async def wait_for_dependencies(
        self,
        timeout: float = 10.0,
        interval: float = 0.25,
    ) -> bool:

        started = time.monotonic()

        while True:

            self._resolve_runtime_context()

            self._resolve_registry_runtime_dependencies()

            self.discover_dependencies()

            self._register_sregistry_node()

            self._register_registry_runtime_provider()

            self._bind_fathud()

            if self.dependencies_ready():

                self.state = STATE_READY

                self._update_registry_runtime_state(
                    self.state
                )

                self._publish_fathud_status()

                return True

            if (
                time.monotonic() - started
                >= timeout
            ):

                self.state = STATE_DEGRADED

                self._update_registry_runtime_state(
                    self.state
                )

                self._publish_fathud_status()

                return False

            await asyncio.sleep(
                interval
            )

    # ======================================================
    # SREGISTRY INTEGRATION
    # ======================================================

    def _registry_api(
        self,
        name: str,
    ):

        registry = self.registry

        if registry is None:
            return None

        method = getattr(
            registry,
            name,
            None,
        )

        if callable(method):
            return method

        return None

    def _get_registry_reference(
        self,
        identifier=None,
        *,
        capability=None,
    ):

        registry = self.registry

        if registry is None:
            return None

        # --------------------------------------------------
        # Capability lookup
        # --------------------------------------------------

        if capability is not None:

            method = getattr(
                registry,
                "get_capability_members",
                None,
            )

            if callable(method):

                try:

                    return method(
                        capability
                    )

                except Exception as exc:

                    self._record_error(
                        "registry_capability_lookup",
                        exc,
                    )

            method = getattr(
                registry,
                "get_nodes_by_capability",
                None,
            )

            if callable(method):

                try:

                    return method(
                        capability
                    )

                except Exception as exc:

                    self._record_error(
                        "registry_node_capability_lookup",
                        exc,
                    )

        if identifier is None:
            return None

        # --------------------------------------------------
        # Node lookup by path
        # --------------------------------------------------

        method = getattr(
            registry,
            "get_node",
            None,
        )

        if callable(method):

            try:

                result = method(
                    identifier
                )

                if result is not None:
                    return result

            except Exception as exc:

                self._record_error(
                    "registry_get_node",
                    exc,
                )

        # --------------------------------------------------
        # Node lookup by name
        # --------------------------------------------------

        method = getattr(
            registry,
            "get_node_by_name",
            None,
        )

        if callable(method):

            try:

                result = method(
                    identifier
                )

                if result is not None:
                    return result

            except Exception as exc:

                self._record_error(
                    "registry_get_node_by_name",
                    exc,
                )

        # --------------------------------------------------
        # Package lookup
        # --------------------------------------------------

        method = getattr(
            registry,
            "get_package",
            None,
        )

        if callable(method):

            try:

                result = method(
                    identifier
                )

                if result is not None:
                    return result

            except Exception as exc:

                self._record_error(
                    "registry_get_package",
                    exc,
                )

        return None

    def inspect_registry(self):

        registry = self.registry

        if registry is None:

            return {
                "status": "OFFLINE",
            }

        method = getattr(
            registry,
            "get_registry_view",
            None,
        )

        if callable(method):

            try:

                return _safe_snapshot(
                    method()
                )

            except Exception as exc:

                self._record_error(
                    "registry_view",
                    exc,
                )

        return {
            "status": "ONLINE",
            "type": type(registry).__name__,
        }

    def _register_sregistry_node(self) -> bool:

        registry = self.registry

        if registry is None:
            return False

        register = getattr(
            registry,
            "register_node",
            None,
        )

        if not callable(register):
            return False

        try:

            try:

                from pathlib import Path

                self.node_path = str(
                    Path(__file__).resolve()
                )

            except Exception:

                self.node_path = (
                    "seed.core.neural.neural_bridge"
                )

            result = register(
                self.NODE_NAME,
                self.node_path,
                parent="seed.core.neural",
                group="neural",
                role=self.NODE_ROLE,
                update_domain="neural",
                state=(
                    STATE_READY
                    if self.dependencies_ready()
                    else STATE_WAITING
                ),
                capabilities=list(
                    self.CAPABILITIES
                ),
                metadata={
                    "module": self.NODE_NAME,
                    "version": self.VERSION,
                    "source": "NeuralBridge",
                    "authoritative": False,
                    "command_authority": "QbitDialer",
                    "observer": True,
                },
            )

            self.node_registered = True

            self._safe_publish_event(
                "NEURAL_BRIDGE_NODE_REGISTERED",
                {
                    "node": self.NODE_NAME,
                    "path": self.node_path,
                    "state": self.state,
                },
            )

            return True

        except TypeError:
            # Compatibility with older register_node surfaces.
            try:

                result = register(
                    self.NODE_NAME,
                    self.node_path,
                )

                self.node_registered = True

                return True

            except Exception as exc:

                self._record_error(
                    "sregistry_register_node",
                    exc,
                )

        except Exception as exc:

            self._record_error(
                "sregistry_register_node",
                exc,
            )

        return False

    # ======================================================
    # REGISTRY-RUNTIME PROVIDER REGISTRATION
    # ======================================================

    def _register_registry_runtime_provider(
        self,
    ) -> bool:

        runtime = self.registry_runtime

        if runtime is None:
            return False

        register = getattr(
            runtime,
            "register_dependency_provider",
            None,
        )

        if not callable(register):
            return False

        try:

            register(
                self.PROVIDER_NAME,
                ref=self,
                state=self.state,
                capabilities=list(
                    self.CAPABILITIES
                ),
                metadata={
                    "module": self.NODE_NAME,
                    "version": self.VERSION,
                    "source": "NeuralBridge",
                    "command_authority": "QbitDialer",
                    "authoritative": False,
                },
                instance_id=str(
                    id(self)
                ),
                authoritative=False,
                source="NeuralBridge",
            )

            self.runtime_provider_registered = True

            return True

        except TypeError:

            # Compatibility fallback for older runtime APIs.
            try:

                register(
                    self.PROVIDER_NAME,
                    ref=self,
                    state=self.state,
                )

                self.runtime_provider_registered = True

                return True

            except Exception as exc:

                self._record_error(
                    "registry_runtime_register_provider",
                    exc,
                )

        except Exception as exc:

            self._record_error(
                "registry_runtime_register_provider",
                exc,
            )

        return False

    def _update_registry_runtime_state(
        self,
        state: str,
    ) -> bool:

        runtime = self.registry_runtime

        if runtime is None:
            return False

        updater = getattr(
            runtime,
            "update_dependency_provider_state",
            None,
        )

        if not callable(updater):
            return False

        try:

            updater(
                self.PROVIDER_NAME,
                state,
            )

            return True

        except TypeError:

            try:

                updater(
                    self.PROVIDER_NAME,
                    state=state,
                )

                return True

            except Exception as exc:

                self._record_error(
                    "registry_runtime_state",
                    exc,
                )

        except Exception as exc:

            self._record_error(
                "registry_runtime_state",
                exc,
            )

        return False

    # ======================================================
    # NODE REGISTRY INTEGRATION
    # ======================================================

    def discover_node(
        self,
        identifier=None,
        *,
        capability=None,
    ):

        if self.node_registry is not None:

            method = getattr(
                self.node_registry,
                "find_node",
                None,
            )

            if callable(method):

                try:

                    if identifier is not None:

                        return method(
                            identifier
                        )

                except Exception as exc:

                    self._record_error(
                        "node_registry_find",
                        exc,
                    )

            method = getattr(
                self.node_registry,
                "find_by_capability",
                None,
            )

            if (
                callable(method)
                and capability is not None
            ):

                try:

                    return method(
                        capability
                    )

                except Exception as exc:

                    self._record_error(
                        "node_registry_capability",
                        exc,
                    )

        return self._get_registry_reference(
            identifier,
            capability=capability,
        )

    # ======================================================
    # QBIT EXTRACTION
    # ======================================================

    def _qbit_id(
        self,
        qbit,
    ) -> Optional[str]:

        return (
            _get_field(
                qbit,
                "qbit_id",
                None,
            )
            or _get_field(
                qbit,
                "id",
                None,
            )
        )

    def _track_id(
        self,
        qbit,
    ) -> Optional[str]:

        return _get_field(
            qbit,
            "track_id",
            None,
        )

    def _channel_id(
        self,
        qbit,
    ) -> Optional[str]:

        return (
            _get_field(
                qbit,
                "channel_id",
                None,
            )
            or _get_field(
                qbit,
                "channel",
                None,
            )
            or _get_field(
                qbit,
                "channel_marker",
                None,
            )
        )

    def _parent_qbit_id(
        self,
        qbit,
    ) -> Optional[str]:

        return _get_field(
            qbit,
            "parent_qbit_id",
            None,
        )

    def _generation(
        self,
        qbit,
    ):

        return _get_field(
            qbit,
            "generation",
            0,
        )

    def _metadata(
        self,
        qbit,
    ):

        metadata = _get_field(
            qbit,
            "metadata",
            {},
        )

        if isinstance(
            metadata,
            dict,
        ):

            return _safe_snapshot(
                metadata
            )

        return {
            "value": _safe_snapshot(
                metadata
            ),
        }

    def _payload(
        self,
        qbit,
    ):

        payload = _get_field(
            qbit,
            "payload",
            None,
        )

        if payload is not None:
            return payload

        return _get_field(
            qbit,
            "data",
            None,
        )

    def _qbit_snapshot(
        self,
        qbit,
    ) -> Dict[str, Any]:

        if qbit is None:
            return {
                "qbit_id": None,
                "track_id": None,
                "parent_qbit_id": None,
                "generation": 0,
            }

        return {
            "qbit_id": self._qbit_id(qbit),
            "track_id": self._track_id(qbit),
            "channel_id": self._channel_id(qbit),
            "parent_qbit_id": (
                self._parent_qbit_id(qbit)
            ),
            "generation": self._generation(qbit),
            "payload": _safe_snapshot(
                self._payload(qbit)
            ),
            "metadata": self._metadata(qbit),
            "type": type(qbit).__name__,
        }

    # ======================================================
    # QBIT -> NEURAL VECTOR
    # ======================================================

    def qbit_to_vector(
        self,
        qbit,
        *,
        dimensions: int = 16,
    ) -> List[float]:

        if qbit is None:

            raise ValueError(
                "[NeuralBridge] qbit_to_vector "
                "requires a Qbit"
            )

        identity = {
            "qbit_id": self._qbit_id(qbit),
            "track_id": self._track_id(qbit),
            "channel_id": self._channel_id(qbit),
            "parent_qbit_id": (
                self._parent_qbit_id(qbit)
            ),
            "generation": self._generation(qbit),
            "payload": _safe_snapshot(
                self._payload(qbit)
            ),
            "metadata": self._metadata(qbit),
        }

        raw = _stable_json(
            identity
        )

        digest = hashlib.sha512(
            raw.encode(
                "utf-8",
                errors="replace",
            )
        ).digest()

        vector = []

        for index in range(
            dimensions
        ):

            offset = (
                index * 2
            ) % len(digest)

            value = int.from_bytes(
                digest[
                    offset:
                    offset + 2
                ],
                "big",
                signed=False,
            )

            normalized = (
                value / 65535.0
            )

            vector.append(
                normalized * 2.0 - 1.0
            )

        vector = self.normalize_vector(
            vector
        )

        self.last_qbit = qbit
        self.last_qbit_id = (
            self._qbit_id(qbit)
        )
        self.last_track_id = (
            self._track_id(qbit)
        )
        self.last_parent_qbit_id = (
            self._parent_qbit_id(qbit)
        )
        self.last_vector = vector

        return vector

    # ======================================================
    # VECTOR NORMALIZATION
    # ======================================================

    @staticmethod
    def normalize_vector(
        vector: Iterable[Any],
    ) -> List[float]:

        values = [
            _safe_float(value)
            for value in vector
        ]

        magnitude = math.sqrt(
            sum(
                value * value
                for value in values
            )
        )

        if magnitude <= 1e-12:

            return [
                0.0
                for _ in values
            ]

        return [
            value / magnitude
            for value in values
        ]

    # ======================================================
    # NEURAL REPRESENTATION
    # ======================================================

    def represent_qbit(
        self,
        qbit,
    ) -> Dict[str, Any]:

        vector = self.qbit_to_vector(
            qbit
        )

        representation = {
            "type": "NEURAL_QBIT",

            # --------------------------------------------------
            # IMPORTANT:
            #
            # Do not put the live qbit object into the
            # serializable representation.
            #
            # The actual qbit is still available to the caller
            # and to NeuralBridge processing.
            # --------------------------------------------------

            "qbit": self._qbit_snapshot(
                qbit
            ),

            "qbit_id": self._qbit_id(qbit),

            "track_id": self._track_id(qbit),

            "channel_id": self._channel_id(qbit),

            "parent_qbit_id": (
                self._parent_qbit_id(qbit)
            ),

            "generation": self._generation(qbit),

            "vector": vector,

            "metadata": self._metadata(qbit),

            "timestamp": time.time(),
        }

        return representation

    # ======================================================
    # VECTOR -> QBIT METADATA
    #
    # IMPORTANT:
    #
    # This method does NOT manufacture a replacement Qbit.
    #
    # It returns an evolution envelope preserving the
    # canonical Qbit identity/lineage information.
    # ======================================================

    def vector_to_qbit_envelope(
        self,
        vector,
        *,
        source_qbit=None,
        metadata=None,
    ) -> Dict[str, Any]:

        if source_qbit is None:
            source_qbit = self.last_qbit

        source_metadata = (
            self._metadata(
                source_qbit
            )
            if source_qbit is not None
            else {}
        )

        if metadata:

            safe_metadata = _safe_snapshot(
                metadata
            )

            if isinstance(
                safe_metadata,
                dict,
            ):

                source_metadata.update(
                    safe_metadata
                )

        source_qbit_id = (
            self._qbit_id(
                source_qbit
            )
            if source_qbit is not None
            else self.last_qbit_id
        )

        source_track_id = (
            self._track_id(
                source_qbit
            )
            if source_qbit is not None
            else self.last_track_id
        )

        parent_qbit_id = (
            self._parent_qbit_id(
                source_qbit
            )
            if source_qbit is not None
            else self.last_parent_qbit_id
        )

        generation = (
            self._generation(
                source_qbit
            )
            if source_qbit is not None
            else 0
        )

        return {
            "type": "NEURAL_QBIT_EVOLUTION",
            "source_qbit_id": source_qbit_id,
            "parent_qbit_id": parent_qbit_id,
            "track_id": source_track_id,
            "channel_id": (
                self._channel_id(
                    source_qbit
                )
                if source_qbit is not None
                else None
            ),
            "generation": generation,
            "next_generation": (
                _safe_float(
                    generation,
                    0.0,
                ) + 1
            ),
            "vector": self.normalize_vector(
                vector
            ),
            "metadata": source_metadata,
            "timestamp": time.time(),
        }

    # ======================================================
    # TRACK SYSTEM
    # ======================================================

    def _publish_track(
        self,
        packet,
    ):

        track_system = self.track_system

        if track_system is None:
            return False

        for method_name in (
            "publish",
            "ingest",
            "update",
            "record",
            "track",
        ):

            method = getattr(
                track_system,
                method_name,
                None,
            )

            if not callable(method):
                continue

            try:

                result = method(
                    packet
                )

                self._schedule_awaitable(
                    result
                )

                return True

            except TypeError:

                try:

                    result = method(
                        **packet
                    )

                    self._schedule_awaitable(
                        result
                    )

                    return True

                except Exception:
                    continue

            except Exception as exc:

                self._record_error(
                    "track_publish",
                    exc,
                )

        return False

    def publish_neural_track(
        self,
        *,
        qbit,
        event,
        payload=None,
    ):

        # --------------------------------------------------
        # NEVER put the live qbit into telemetry.
        # --------------------------------------------------

        packet = {
            "type": "NEURAL_BRIDGE",
            "event": event,

            "qbit": self._qbit_snapshot(
                qbit
            ),

            "qbit_id": self._qbit_id(qbit),

            "track_id": self._track_id(qbit),

            "channel_id": self._channel_id(qbit),

            "parent_qbit_id": (
                self._parent_qbit_id(qbit)
            ),

            "generation": self._generation(qbit),

            "payload": _safe_snapshot(
                payload
            ),

            "timestamp": time.time(),

            "source": "NeuralBridge",

            "command_authority": "QbitDialer",
        }

        return self._publish_track(
            packet
        )

    # ======================================================
    # EVENT BUS TELEMETRY
    # ======================================================

    def _emit(
        self,
        event_name,
        payload=None,
    ):

        return self._safe_publish_event(
            event_name,
            payload,
        )

    def _safe_publish_event(
        self,
        event_name,
        payload=None,
    ):

        event_bus = self.event_bus

        if event_bus is None:
            return False

        safe_payload = _safe_snapshot(
            payload or {}
        )

        # --------------------------------------------------
        # Primary verified EventBus surface.
        # --------------------------------------------------

        emit = getattr(
            event_bus,
            "emit",
            None,
        )

        if callable(emit):

            try:

                result = emit(
                    event_name,
                    safe_payload,
                )

                self._schedule_awaitable(
                    result
                )

                return True

            except Exception as exc:

                self._record_error(
                    f"event:{event_name}",
                    exc,
                )

        # --------------------------------------------------
        # Compatibility fallback.
        #
        # Only use if emit() is unavailable.
        # --------------------------------------------------

        publish = getattr(
            event_bus,
            "publish",
            None,
        )

        if callable(publish):

            try:

                result = publish(
                    event_name,
                    safe_payload,
                )

                self._schedule_awaitable(
                    result
                )

                return True

            except Exception as exc:

                self._record_error(
                    f"event_publish:{event_name}",
                    exc,
                )

        return False

    # ======================================================
    # ASYNC SAFETY
    # ======================================================

    def _schedule_awaitable(
        self,
        result,
    ) -> bool:

        if not inspect.isawaitable(
            result
        ):
            return False

        # --------------------------------------------------
        # Use the already-running authoritative runtime loop.
        #
        # NEVER create another loop.
        # --------------------------------------------------

        try:

            loop = asyncio.get_running_loop()

        except RuntimeError:

            loop = None

        if loop is not None:

            try:

                loop.create_task(
                    result
                )

                return True

            except Exception as exc:

                self._record_error(
                    "schedule_awaitable",
                    exc,
                )

                return False

        # --------------------------------------------------
        # If there is no running loop, do not manufacture one.
        #
        # Close coroutine-like objects where supported so
        # Python does not produce "coroutine was never awaited".
        # --------------------------------------------------

        close = getattr(
            result,
            "close",
            None,
        )

        if callable(close):

            try:
                close()
            except Exception:
                pass

        return False

    # ======================================================
    # COGNITIVE INPUT
    # ======================================================

    def _build_cognitive_context(
        self,
        qbit,
        representation,
    ):

        registry_view = None

        try:

            registry_view = (
                self.inspect_registry()
            )

        except Exception as exc:

            self._record_error(
                "registry_context",
                exc,
            )

        # --------------------------------------------------
        # SAFE DEPENDENCY DESCRIPTORS.
        #
        # The actual references remain in
        # self.dependencies.
        #
        # Cognitive context receives metadata only.
        # --------------------------------------------------

        dependency_snapshot = {}

        for name, record in (
            self.dependencies.items()
        ):

            reference = record.get(
                "reference"
            )

            dependency_snapshot[name] = {
                "required": bool(
                    record.get(
                        "required",
                        False,
                    )
                ),
                "state": record.get(
                    "state",
                    DEP_PENDING,
                ),
                "bound": reference is not None,
                "type": (
                    type(reference).__name__
                    if reference is not None
                    else None
                ),
            }

        return {
            "source": "NeuralBridge",

            "qbit_id": self._qbit_id(qbit),

            "track_id": self._track_id(qbit),

            "channel_id": self._channel_id(qbit),

            "parent_qbit_id": (
                self._parent_qbit_id(qbit)
            ),

            "generation": self._generation(qbit),

            # representation is already safe.
            "representation": _safe_snapshot(
                representation
            ),

            "registry": _safe_snapshot(
                registry_view
            ),

            "dependencies": dependency_snapshot,

            "runtime": {
                "state": self.state,
                "running": self.running,
                "active": self.active,
                "qbit_bound": self.qbit is not None,
                "queue_loop_bound": (
                    self.qbit_queue_loop is not None
                ),
                "dialer_bound": (
                    self.qbit_dialer is not None
                ),
            },

            "timestamp": time.time(),
        }

    # ======================================================
    # THINK
    # ======================================================

    async def think(
        self,
        qbit,
        *,
        context=None,
    ):

        if qbit is None:

            return {
                "status": "no_qbit",
            }

        self.cycle_count += 1

        representation = (
            self.represent_qbit(
                qbit
            )
        )

        cognitive_context = (
            self._build_cognitive_context(
                qbit,
                representation,
            )
        )

        if context:

            cognitive_context[
                "external_context"
            ] = _safe_snapshot(
                context
            )

        compute = self.compute_brain

        result = None

        if compute is not None:

            for method_name in (
                "process",
                "compute",
                "think",
                "process_qbit",
            ):

                method = getattr(
                    compute,
                    method_name,
                    None,
                )

                if not callable(method):
                    continue

                try:

                    result = method(
                        qbit=qbit,
                        context=cognitive_context,
                    )

                    if inspect.isawaitable(
                        result
                    ):

                        result = await result

                    break

                except TypeError:

                    try:

                        result = method(
                            qbit
                        )

                        if inspect.isawaitable(
                            result
                        ):

                            result = await result

                        break

                    except Exception as exc:

                        self._record_error(
                            f"compute:{method_name}",
                            exc,
                        )

                except Exception as exc:

                    self._record_error(
                        f"compute:{method_name}",
                        exc,
                    )

        self.last_thought = result

        self.publish_neural_track(
            qbit=qbit,
            event="THOUGHT",
            payload=result,
        )

        self._emit(
            "NEURAL_THOUGHT",
            {
                "qbit_id": self._qbit_id(qbit),
                "track_id": self._track_id(qbit),
                "channel_id": self._channel_id(qbit),
                "thought": result,
            },
        )

        return {
            "status": "thought",

            # Keep live qbit only in the direct return used by
            # the active processing path.
            "qbit": qbit,

            "qbit_id": self._qbit_id(qbit),

            "context": cognitive_context,

            "representation": representation,

            "thought": result,
        }

    # ======================================================
    # TRANSFORM
    # ======================================================

    async def transform(
        self,
        thought_result,
        *,
        qbit=None,
    ):

        qbit = (
            qbit
            if qbit is not None
            else self.last_qbit
        )

        transformer = (
            self.transformer_brain
        )

        if transformer is None:

            return {
                "status": "no_transformer",
                "thought": _safe_snapshot(
                    thought_result
                ),
            }

        context = {
            "qbit_id": self._qbit_id(qbit),

            "track_id": self._track_id(qbit),

            "channel_id": self._channel_id(qbit),

            "parent_qbit_id": (
                self._parent_qbit_id(qbit)
            ),

            "thought": _safe_snapshot(
                thought_result
            ),

            "source": "NeuralBridge",
        }

        result = None

        for method_name in (
            "transform",
            "process",
            "compute",
            "think",
        ):

            method = getattr(
                transformer,
                method_name,
                None,
            )

            if not callable(method):
                continue

            try:

                result = method(
                    thought_result,
                    context=context,
                )

                if inspect.isawaitable(
                    result
                ):

                    result = await result

                break

            except TypeError:

                try:

                    result = method(
                        thought_result
                    )

                    if inspect.isawaitable(
                        result
                    ):

                        result = await result

                    break

                except Exception as exc:

                    self._record_error(
                        f"transform:{method_name}",
                        exc,
                    )

            except Exception as exc:

                self._record_error(
                    f"transform:{method_name}",
                    exc,
                )

        self.last_proposal = result
        self.proposal_count += 1

        self.publish_neural_track(
            qbit=qbit,
            event="TRANSFORM",
            payload=result,
        )

        self._emit(
            "NEURAL_PROPOSAL",
            {
                "qbit_id": self._qbit_id(qbit),
                "track_id": self._track_id(qbit),
                "channel_id": self._channel_id(qbit),
                "proposal": result,
            },
        )

        return {
            "status": "transformed",
            "proposal": result,
            "qbit": qbit,
            "qbit_id": self._qbit_id(qbit),
        }

    # ======================================================
    # QUESTION
    # ======================================================

    def ask_question(
        self,
        *,
        qbit=None,
        question=None,
        reason=None,
        context=None,
    ):

        qbit = (
            qbit
            if qbit is not None
            else self.last_qbit
        )

        if not question:

            question = (
                "What is the next safe, "
                "authorized step required "
                "to improve the current state?"
            )

        self.question_count += 1

        record = {
            "type": "NEURAL_QUESTION",

            "question": question,

            "reason": _safe_snapshot(
                reason
            ),

            "qbit_id": self._qbit_id(qbit),

            "track_id": self._track_id(qbit),

            "channel_id": self._channel_id(qbit),

            "parent_qbit_id": (
                self._parent_qbit_id(qbit)
            ),

            "context": _safe_snapshot(
                context or {}
            ),

            "timestamp": time.time(),

            "requires_command_authority": True,

            "command_authority": "QbitDialer",

            "admission_path": "submit_command",
        }

        self.last_question = record

        self.publish_neural_track(
            qbit=qbit,
            event="QUESTION",
            payload=record,
        )

        self._emit(
            "NEURAL_QUESTION",
            record,
        )

        return record

    # ======================================================
    # PROPOSE FIX
    # ======================================================

    def propose_fix(
        self,
        *,
        qbit=None,
        problem=None,
        evidence=None,
        proposed_action=None,
        confidence=0.0,
        reason=None,
    ):

        qbit = (
            qbit
            if qbit is not None
            else self.last_qbit
        )

        proposal = {
            "type": "FIX_PROPOSAL",

            "status": "PROPOSED",

            "problem": _safe_snapshot(
                problem
            ),

            "evidence": _safe_snapshot(
                evidence or {}
            ),

            "proposed_action": _safe_snapshot(
                proposed_action
            ),

            "confidence": max(
                0.0,
                min(
                    1.0,
                    _safe_float(
                        confidence
                    ),
                ),
            ),

            "reason": _safe_snapshot(
                reason
            ),

            "qbit_id": self._qbit_id(qbit),

            "track_id": self._track_id(qbit),

            "channel_id": self._channel_id(qbit),

            "parent_qbit_id": (
                self._parent_qbit_id(qbit)
            ),

            "source": "NeuralBridge",

            "timestamp": time.time(),

            "command_authority": "QbitDialer",

            "admission_path": "submit_command",
        }

        self.last_recovery_proposal = proposal

        self.publish_neural_track(
            qbit=qbit,
            event="FIX_PROPOSAL",
            payload=proposal,
        )

        self._emit(
            "NEURAL_FIX_PROPOSAL",
            proposal,
        )

        return proposal

    # ======================================================
    # ATTEMPT FIX
    # ======================================================

    async def attempt_fix(
        self,
        command,
        *,
        qbit=None,
        reason=None,
        metadata=None,
    ):

        qbit = (
            qbit
            if qbit is not None
            else self.last_qbit
        )

        dialer = self.qbit_dialer

        if dialer is None:

            return {
                "status": "no_command_authority",
                "command": command,
            }

        submit = getattr(
            dialer,
            "submit_command",
            None,
        )

        if not callable(submit):

            return {
                "status": "submit_command_unavailable",
                "command": command,
            }

        # --------------------------------------------------
        # IMPORTANT:
        #
        # NeuralBridge remains proposal/coordination layer.
        #
        # QbitDialer remains the command authority.
        #
        # The live qbit is supplied to the authoritative
        # submit surface when needed, but is never copied.
        # --------------------------------------------------

        envelope = {
            "command": command,

            "qbit": qbit,

            "qbit_id": self._qbit_id(qbit),

            "track_id": self._track_id(qbit),

            "channel_id": self._channel_id(qbit),

            "parent_qbit_id": (
                self._parent_qbit_id(qbit)
            ),

            "generation": self._generation(qbit),

            "reason": _safe_snapshot(
                reason
            ),

            "metadata": _safe_snapshot(
                metadata or {}
            ),

            "source": "NeuralBridge",

            "authority": "QbitDialer",

            "admission_path": "submit_command",
        }

        try:

            result = submit(
                envelope
            )

            if inspect.isawaitable(
                result
            ):

                result = await result

            self.last_execution_result = result
            self.execution_observation_count += 1

            self.publish_neural_track(
                qbit=qbit,
                event="FIX_ATTEMPT",
                payload={
                    "command": command,
                    "result": result,
                },
            )

            self._emit(
                "NEURAL_FIX_ATTEMPT",
                {
                    "qbit_id": self._qbit_id(qbit),
                    "track_id": self._track_id(qbit),
                    "channel_id": self._channel_id(qbit),
                    "command": command,
                    "result": result,
                    "authority": "QbitDialer",
                },
            )

            return {
                "status": "submitted",
                "command": command,
                "result": result,
                "authority": "QbitDialer",
            }

        except Exception as exc:

            self._record_error(
                "attempt_fix",
                exc,
            )

            result = {
                "status": "submission_failed",

                "command": command,

                "error": str(exc),

                "error_type": type(
                    exc
                ).__name__,

                "authority": "QbitDialer",
            }

            self.last_execution_result = result

            return result

    # ======================================================
    # OBSERVE RESULT
    # ======================================================

    def observe_result(
        self,
        result,
        *,
        qbit=None,
    ):

        qbit = (
            qbit
            if qbit is not None
            else self.last_qbit
        )

        safe_result = _safe_snapshot(
            result
        )

        observation = {
            "type": "EXECUTION_OBSERVATION",

            "qbit_id": self._qbit_id(qbit),

            "track_id": self._track_id(qbit),

            "channel_id": self._channel_id(qbit),

            "parent_qbit_id": (
                self._parent_qbit_id(qbit)
            ),

            "result": safe_result,

            "timestamp": time.time(),

            "source": "NeuralBridge",

            "authority": "QbitDialer",
        }

        self.last_execution_result = result
        self.execution_observation_count += 1

        self.publish_neural_track(
            qbit=qbit,
            event="EXECUTION_RESULT",
            payload=observation,
        )

        self._emit(
            "NEURAL_EXECUTION_OBSERVATION",
            observation,
        )

        return observation

    # ======================================================
    # ADAPTIVE RECOVERY
    # ======================================================

    async def adaptive_recovery(
        self,
        *,
        qbit=None,
        problem=None,
        evidence=None,
    ):

        qbit = (
            qbit
            if qbit is not None
            else self.last_qbit
        )

        safe_evidence = _safe_snapshot(
            evidence or {}
        )

        question = self.ask_question(
            qbit=qbit,
            question=(
                "What failed, why did it fail, "
                "and what is the safest authorized "
                "recovery step?"
            ),
            reason=problem,
            context={
                "evidence": safe_evidence,
            },
        )

        proposal = self.propose_fix(
            qbit=qbit,
            problem=problem,
            evidence=safe_evidence,
            proposed_action=None,
            confidence=0.0,
            reason=question["question"],
        )

        return {
            "status": "recovery_analysis",

            "question": question,

            "proposal": proposal,

            "qbit": qbit,

            "qbit_id": self._qbit_id(qbit),

            "track_id": self._track_id(qbit),
        }

    # ======================================================
    # COMPLETE QBIT PROCESSING
    # ======================================================

    async def process_qbit(
        self,
        qbit,
        *,
        context=None,
    ):

        if qbit is None:

            return {
                "status": "no_qbit",
            }

        # --------------------------------------------------
        # Preserve exact incoming Qbit reference.
        #
        # Evolved Qbits are valid.
        # --------------------------------------------------

        self.last_qbit = qbit

        # --------------------------------------------------
        # Do not replace authoritative runtime Qbit.
        #
        # If no authoritative runtime anchor exists yet,
        # this first Qbit can establish the anchor.
        # --------------------------------------------------

        if self.qbit is None:
            self.qbit = qbit

        # --------------------------------------------------
        # Resolve late dependencies.
        # --------------------------------------------------

        if not self.dependencies_ready():

            self._resolve_runtime_context()

            self._resolve_registry_runtime_dependencies()

            self.discover_dependencies()

        # --------------------------------------------------
        # Register/update runtime visibility.
        # --------------------------------------------------

        self._register_sregistry_node()

        self._register_registry_runtime_provider()

        self._bind_fathud()

        # --------------------------------------------------
        # Process thought.
        # --------------------------------------------------

        thought = await self.think(
            qbit,
            context=context,
        )

        # --------------------------------------------------
        # Transform thought.
        # --------------------------------------------------

        transformed = await self.transform(
            thought.get("thought"),
            qbit=qbit,
        )

        # --------------------------------------------------
        # Active status.
        # --------------------------------------------------

        if self.dependencies_ready():

            self.state = (
                STATE_ACTIVE
                if self.running
                else STATE_READY
            )

        else:

            self.state = STATE_DEGRADED

        self._update_registry_runtime_state(
            self.state
        )

        self._publish_fathud_status()

        return {
            "status": "processed",

            "qbit": qbit,

            "qbit_id": self._qbit_id(qbit),

            "track_id": self._track_id(qbit),

            "thought": thought,

            "transform": transformed,

            "neural_vector": self.last_vector,

            "state": self.state,
        }

    # ======================================================
    # FATHUD INTEGRATION
    # ======================================================

    def _bind_fathud(
        self,
    ) -> bool:

        fathud = self.fathud

        if fathud is None:
            self.fathud_bound = False
            return False

        self.fathud_bound = True

        # --------------------------------------------------
        # Prefer explicit attach/bind methods if supplied.
        # --------------------------------------------------

        for method_name in (
            "attach_neural_bridge",
            "bind_neural_bridge",
            "attach_neural",
        ):

            method = getattr(
                fathud,
                method_name,
                None,
            )

            if not callable(method):
                continue

            try:

                result = method(
                    self
                )

                self._schedule_awaitable(
                    result
                )

                break

            except TypeError:

                try:

                    result = method(
                        neural_bridge=self
                    )

                    self._schedule_awaitable(
                        result
                    )

                    break

                except Exception as exc:

                    self._record_error(
                        f"fathud:{method_name}",
                        exc,
                    )

            except Exception as exc:

                self._record_error(
                    f"fathud:{method_name}",
                    exc,
                )

        # --------------------------------------------------
        # Some FATHUD implementations expose an attach()
        # surface for dynamic system registration.
        #
        # Use only if present.
        # --------------------------------------------------

        attach = getattr(
            fathud,
            "attach",
            None,
        )

        if callable(attach):

            try:

                result = attach(
                    "neural_bridge",
                    self,
                )

                self._schedule_awaitable(
                    result
                )

            except TypeError:

                try:

                    result = attach(
                        neural_bridge=self
                    )

                    self._schedule_awaitable(
                        result
                    )

                except Exception:
                    pass

            except Exception:
                pass

        return self.fathud_bound

    def _fathud_status_payload(
        self,
    ) -> Dict[str, Any]:

        return {
            "module": "NeuralBridge",

            "version": self.VERSION,

            "state": self.state,

            "online": self.state in {
                STATE_READY,
                STATE_ACTIVE,
            },

            "running": self.running,

            "active": self.active,

            "dependencies_ready": (
                self.dependencies_ready()
            ),

            "node_registered": (
                self.node_registered
            ),

            "registry_runtime_registered": (
                self.runtime_provider_registered
            ),

            "fathud_bound": (
                self.fathud_bound
            ),

            "qbit": {
                "bound": self.qbit is not None,
                "authoritative_qbit_id": (
                    self._qbit_id(
                        self.qbit
                    )
                    if self.qbit is not None
                    else None
                ),
                "processed_qbit_id": (
                    self.last_qbit_id
                ),
                "track_id": (
                    self.last_track_id
                ),
                "parent_qbit_id": (
                    self.last_parent_qbit_id
                ),
            },

            "authorities": {
                "registry": (
                    self.registry is not None
                ),
                "registry_runtime": (
                    self.registry_runtime is not None
                ),
                "qbit_queue_loop": (
                    self.qbit_queue_loop is not None
                ),
                "event_bus": (
                    self.event_bus is not None
                ),
                "track_system": (
                    self.track_system is not None
                ),
                "qbit_dialer": (
                    self.qbit_dialer is not None
                ),
                "compute_brain": (
                    self.compute_brain is not None
                ),
                "transformer_brain": (
                    self.transformer_brain is not None
                ),
                "node_registry": (
                    self.node_registry is not None
                ),
            },

            "command_authority": (
                "QbitDialer"
            ),

            "command_path": (
                "NeuralBridge"
                " -> QbitDialer"
                " -> submit_command"
            ),

            "cycles": self.cycle_count,

            "questions": self.question_count,

            "proposals": self.proposal_count,

            "execution_observations": (
                self.execution_observation_count
            ),

            "errors": len(
                self.errors
            ),

            "timestamp": time.time(),
        }

    def _publish_fathud_status(
        self,
    ) -> bool:

        fathud = self.fathud

        if fathud is None:
            return False

        payload = self._fathud_status_payload()

        self.last_fathud_status = payload

        # --------------------------------------------------
        # Preferred direct push surface.
        # --------------------------------------------------

        push = getattr(
            fathud,
            "push",
            None,
        )

        if callable(push):

            try:

                result = push(
                    {
                        "type": "NEURAL_BRIDGE_STATUS",
                        "source": "NeuralBridge",
                        "data": payload,
                    }
                )

                self._schedule_awaitable(
                    result
                )

                return True

            except TypeError:

                try:

                    result = push(
                        payload
                    )

                    self._schedule_awaitable(
                        result
                    )

                    return True

                except Exception:
                    pass

            except Exception:
                pass

        # --------------------------------------------------
        # Event-based FATHUD surfaces.
        # --------------------------------------------------

        for method_name in (
            "publish",
            "emit",
            "send",
        ):

            method = getattr(
                fathud,
                method_name,
                None,
            )

            if not callable(method):
                continue

            try:

                result = method(
                    "NEURAL_BRIDGE_STATUS",
                    payload,
                )

                self._schedule_awaitable(
                    result
                )

                return True

            except TypeError:

                try:

                    result = method(
                        payload
                    )

                    self._schedule_awaitable(
                        result
                    )

                    return True

                except Exception:
                    continue

            except Exception:
                continue

        return False

    # ======================================================
    # MODEL
    # ======================================================

    def _load_neural_model(self):

        self.model_name = (
            "SEED-NEURAL-REPRESENTATION"
        )

        self.model_version = (
            self.VERSION
        )

        self.model_loaded = True

    # ======================================================
    # ERROR TRACKING
    # ======================================================

    def _record_error(
        self,
        stage,
        exc,
    ):

        record = {
            "stage": stage,

            "error": str(exc),

            "error_type": type(
                exc
            ).__name__,

            "timestamp": time.time(),
        }

        self.errors.append(
            record
        )

        if len(self.errors) > 128:

            self.errors = (
                self.errors[-128:]
            )

        self.logger.warning(
            "[NeuralBridge] %s | %s",
            stage,
            exc,
        )

    # ======================================================
    # WARNING TRACKING
    # ======================================================

    def _record_warning(
        self,
        stage,
        message,
    ):

        record = {
            "stage": stage,

            "warning": str(
                message
            ),

            "timestamp": time.time(),
        }

        self.warnings.append(
            record
        )

        if len(self.warnings) > 128:

            self.warnings = (
                self.warnings[-128:]
            )

        self.logger.warning(
            "[NeuralBridge] WARNING %s | %s",
            stage,
            message,
        )

    # ======================================================
    # SAFE DEPENDENCY STATUS
    # ======================================================

    def _dependency_status_snapshot(
        self,
    ) -> Dict[str, Any]:

        result = {}

        for name, record in (
            self.dependencies.items()
        ):

            reference = record.get(
                "reference"
            )

            result[name] = {
                "required": bool(
                    record.get(
                        "required",
                        False,
                    )
                ),

                "state": record.get(
                    "state",
                    DEP_PENDING,
                ),

                "bound": reference is not None,

                "type": (
                    type(reference).__name__
                    if reference is not None
                    else None
                ),
            }

        return result

    # ======================================================
    # HEALTH
    # ======================================================

    def health(self):

        required_ready = {
            name: (
                record["reference"]
                is not None
            )
            for name, record
            in self.dependencies.items()
            if record["required"]
        }

        return {
            "module": "NeuralBridge",

            "version": self.VERSION,

            "state": self.state,

            "running": self.running,

            "active": self.active,

            "online": self.state in {
                STATE_READY,
                STATE_ACTIVE,
            },

            "model_loaded": self.model_loaded,

            "dependencies_ready": (
                self.dependencies_ready()
            ),

            "required_dependencies": (
                required_ready
            ),

            "dependencies": (
                self._dependency_status_snapshot()
            ),

            "qbit_bound": (
                self.qbit is not None
            ),

            "qbit_id": self.last_qbit_id,

            "track_id": self.last_track_id,

            "parent_qbit_id": (
                self.last_parent_qbit_id
            ),

            "authoritative_qbit_id": (
                self._qbit_id(
                    self.qbit
                )
                if self.qbit is not None
                else None
            ),

            "processed_qbit_id": (
                self.last_qbit_id
            ),

            "node_registered": (
                self.node_registered
            ),

            "registry_runtime_bound": (
                self.registry_runtime is not None
            ),

            "registry_runtime_registered": (
                self.runtime_provider_registered
            ),

            "fathud_bound": (
                self.fathud_bound
            ),

            "cycles": self.cycle_count,

            "questions": self.question_count,

            "proposals": self.proposal_count,

            "execution_observations": (
                self.execution_observation_count
            ),

            "errors": len(
                self.errors
            ),

            "warnings": len(
                self.warnings
            ),
        }

    # ======================================================
    # STATUS
    # ======================================================

    def status(self):

        authoritative_qbit_id = (
            self._qbit_id(
                self.qbit
            )
            if self.qbit is not None
            else None
        )

        processed_qbit_id = (
            self.last_qbit_id
        )

        # --------------------------------------------------
        # IMPORTANT:
        #
        # Different authoritative and processed Qbit IDs are
        # allowed when the pipeline has evolved a Qbit.
        #
        # This replaces the old misleading
        # "same_authoritative_reference" interpretation.
        # --------------------------------------------------

        return {
            "module": "NeuralBridge",

            "version": self.VERSION,

            "state": self.state,

            "online": self.state in {
                STATE_READY,
                STATE_ACTIVE,
            },

            "running": self.running,

            "active": self.active,

            "authorities": {
                "registry": (
                    type(
                        self.registry
                    ).__name__
                    if self.registry is not None
                    else None
                ),

                "registry_runtime": (
                    type(
                        self.registry_runtime
                    ).__name__
                    if self.registry_runtime is not None
                    else None
                ),

                "event_bus": (
                    type(
                        self.event_bus
                    ).__name__
                    if self.event_bus is not None
                    else None
                ),

                "qbit": (
                    type(
                        self.qbit
                    ).__name__
                    if self.qbit is not None
                    else None
                ),

                "qbit_queue_loop": (
                    type(
                        self.qbit_queue_loop
                    ).__name__
                    if self.qbit_queue_loop is not None
                    else None
                ),

                "qbit_dialer": (
                    type(
                        self.qbit_dialer
                    ).__name__
                    if self.qbit_dialer is not None
                    else None
                ),

                "track_system": (
                    type(
                        self.track_system
                    ).__name__
                    if self.track_system is not None
                    else None
                ),

                "compute_brain": (
                    type(
                        self.compute_brain
                    ).__name__
                    if self.compute_brain is not None
                    else None
                ),

                "transformer_brain": (
                    type(
                        self.transformer_brain
                    ).__name__
                    if self.transformer_brain is not None
                    else None
                ),

                "node_registry": (
                    type(
                        self.node_registry
                    ).__name__
                    if self.node_registry is not None
                    else None
                ),
            },

            "registrations": {
                "sregistry_node": (
                    self.node_registered
                ),

                "registry_runtime_provider": (
                    self.runtime_provider_registered
                ),

                "fathud": (
                    self.fathud_bound
                ),
            },

            "qbit": {
                "authoritative_bound": (
                    self.qbit is not None
                ),

                "processed_bound": (
                    self.last_qbit is not None
                ),

                "authoritative_qbit_id": (
                    authoritative_qbit_id
                ),

                "processed_qbit_id": (
                    processed_qbit_id
                ),

                "processed_is_authoritative": (
                    self.last_qbit is self.qbit
                    if (
                        self.last_qbit is not None
                        and self.qbit is not None
                    )
                    else None
                ),

                "lineage_preserved": (
                    self.last_qbit is not None
                ),

                "qbit_id": self.last_qbit_id,

                "track_id": self.last_track_id,

                "channel_id": (
                    self._channel_id(
                        self.last_qbit
                    )
                    if self.last_qbit is not None
                    else None
                ),

                "parent_qbit_id": (
                    self.last_parent_qbit_id
                ),

                "generation": (
                    self._generation(
                        self.last_qbit
                    )
                    if self.last_qbit is not None
                    else None
                ),
            },

            "neural": {
                "model_loaded": (
                    self.model_loaded
                ),

                "model": (
                    self.model_name
                ),

                "model_version": (
                    self.model_version
                ),

                "vector_dimensions": (
                    len(self.last_vector)
                    if self.last_vector is not None
                    else 0
                ),
            },

            "cognition": {
                "cycles": self.cycle_count,

                "questions": (
                    self.question_count
                ),

                "proposals": (
                    self.proposal_count
                ),

                "last_question": (
                    _safe_snapshot(
                        self.last_question
                    )
                ),

                "last_proposal": (
                    _safe_snapshot(
                        self.last_proposal
                    )
                ),

                "last_execution_result": (
                    _safe_snapshot(
                        self.last_execution_result
                    )
                ),
            },

            "registry_runtime": {
                "bound": (
                    self.registry_runtime is not None
                ),

                "provider_api": (
                    self._registry_runtime_api(
                        "get_dependency_provider"
                    )
                    is not None
                ),

                "provider_registered": (
                    self.runtime_provider_registered
                ),
            },

            "fathud": {
                "bound": self.fathud_bound,

                "online": (
                    self.fathud is not None
                ),

                "last_status": (
                    _safe_snapshot(
                        self.last_fathud_status
                    )
                ),
            },

            # --------------------------------------------------
            # IMPORTANT:
            #
            # Safe dependency metadata only.
            # No live runtime object is returned here.
            # --------------------------------------------------

            "dependencies": (
                self._dependency_status_snapshot()
            ),

            "node": {
                "registered": (
                    self.node_registered
                ),

                "name": self.NODE_NAME,

                "path": self.node_path,

                "role": self.NODE_ROLE,

                "capabilities": list(
                    self.CAPABILITIES
                ),
            },

            "command_authority": {
                "authority": "QbitDialer",

                "admission_path": (
                    "QbitDialer.submit_command"
                ),

                "neural_bridge_executes_commands": (
                    False
                ),

                "bypasses_qbit_dialer": (
                    False
                ),
            },

            "health": self.health(),
        }

    # ======================================================
    # START
    # ======================================================

    async def start(self):

        self._resolve_runtime_context()

        self._resolve_registry_runtime_dependencies()

        self.discover_dependencies()

        self._register_sregistry_node()

        self._register_registry_runtime_provider()

        self._bind_fathud()

        if not self.dependencies_ready():

            self.state = STATE_WAITING
            self.running = False
            self.active = False

            self._update_registry_runtime_state(
                self.state
            )

            self._publish_fathud_status()

            self.logger.warning(
                "[NeuralBridge] start waiting "
                "for dependencies"
            )

            return self.status()

        self.running = True
        self.active = True
        self.state = STATE_ACTIVE

        self._update_registry_runtime_state(
            self.state
        )

        self._safe_publish_event(
            "NEURAL_BRIDGE_ONLINE",
            self.status(),
        )

        self._publish_fathud_status()

        self.logger.info(
            "[NeuralBridge] ONLINE"
        )

        return self.status()

    # ======================================================
    # STOP
    # ======================================================

    async def stop(self):

        self.running = False
        self.active = False
        self.state = STATE_STOPPED

        self._update_registry_runtime_state(
            self.state
        )

        self._safe_publish_event(
            "NEURAL_BRIDGE_STOPPED",
            self.status(),
        )

        self._publish_fathud_status()

        self.logger.info(
            "[NeuralBridge] STOPPED"
        )

        return self.status()


# ==========================================================
# FACTORY
# ==========================================================

def create_neural_bridge(
    **kwargs,
):

    return NeuralBridge(
        **kwargs
    )


# ==========================================================
# EXPORTS
# ==========================================================

__all__ = [
    "NeuralBridge",
    "create_neural_bridge",

    "STATE_OFFLINE",
    "STATE_WAITING",
    "STATE_READY",
    "STATE_ACTIVE",
    "STATE_DEGRADED",
    "STATE_FAILED",
    "STATE_STOPPED",

    "DEP_PENDING",
    "DEP_READY",
    "DEP_MISSING",
    "DEP_INVALID",
    "DEP_BOUND",
]