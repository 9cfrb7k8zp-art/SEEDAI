# ================================================================
# SEED AI OS — ETHICS MANAGER
# ================================================================
#
# FILE:
# C:\SEED_ROOT\seed\systemutils\ethics.py
#
# VERSION:
# 2.2.0
#
# ROLE:
# Runtime policy / ethics / cognitive-governance gate
#
# AUTHORITY:
# QbitDialer remains the sole command authority.
#
# ================================================================
#
# COGNITIVE GOVERNANCE FLOW
#
#     RAW QBIT
#         |
#         v
#     QbitDialer
#         |
#         v
#     QbitQueueLoop
#         |
#         v
#     ComputeBrain
#         |
#         v
#     ThoughtPacket
#         |
#         v
#     TransformerBrain
#         |
#         v
#     ETHICS
#         |
#         +---- ALLOWED
#         |       |
#         |       v
#         |   QbitDialer
#         |       |
#         |       v
#         |   submit_command()
#         |
#         +---- DENIED
#         |       |
#         |       v
#         |    feedback
#         |
#         +---- DEFERRED
#                 |
#                 v
#              observe /
#              research /
#              learn
#
# IMPORTANT:
#
# Ethics does NOT execute commands.
# Ethics does NOT create Qbits.
# Ethics does NOT create queues.
# Ethics does NOT create workers.
# Ethics does NOT start loops.
# Ethics does NOT bypass QbitDialer.
# Ethics does NOT become command authority.
#
# ================================================================

from __future__ import annotations

import time
import uuid

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Set


# ================================================================
# OPTIONAL RUNTIME IMPORTS
# ================================================================

try:
    from seed.skills import skills as _default_skills
except Exception:
    _default_skills = None


try:
    from seed.core.qbit import Qbit
except Exception:
    Qbit = None


try:
    from seed.systemutils.healthmonitor import HealthMonitor
except Exception:
    HealthMonitor = None


# ------------------------------------------------
# IMPORTANT:
# SRegistry is the authoritative SEED registry.
#
# Do NOT manufacture a second registry.
# ------------------------------------------------

try:
    from seed.systemutils.registry import (
        SRegistry,
        SEED_KERNEL_REGISTRY,
    )
except Exception:
    try:
        from seed.systemutils.registry import SRegistry
    except Exception:
        SRegistry = None

    try:
        from seed.systemutils.registry import (
            SEED_KERNEL_REGISTRY,
        )
    except Exception:
        SEED_KERNEL_REGISTRY = None


# Compatibility fallback only.
#
# This is NOT authoritative and is only retained so
# older callers that explicitly pass ModuleRegistry
# continue to work.
try:
    from seed.systemutils.registry import ModuleRegistry
except Exception:
    ModuleRegistry = None


# ================================================================
# CONSTANTS
# ================================================================

VERSION = "2.2.0"

ROLE = "ethics_policy_gate"

AUTHORITY = "QbitDialer"

SOURCE = "EthicsManager"


# ================================================================
# POLICY STATES
# ================================================================

DECISION_ALLOWED = "ALLOWED"

DECISION_DENIED = "DENIED"

DECISION_DEFERRED = "DEFERRED"


# ================================================================
# RISK LEVELS
# ================================================================

RISK_LOW = 0.0

RISK_MEDIUM = 0.5

RISK_HIGH = 0.8

RISK_CRITICAL = 1.0


# ================================================================
# PROTECTED INTENTS
# ================================================================

PROTECTED_INTENTS = {
    "SELF_DESTRUCT",
    "SELF_DESTRUCT_SYSTEM",
    "DESTROY_SYSTEM",
    "WIPE_SYSTEM",
    "FORMAT_SYSTEM",
}


# ================================================================
# DEFAULT BLOCKS
# ================================================================

DEFAULT_BLOCKED_INTENTS: Set[str] = set()

DEFAULT_BLOCKED_CONTROLLERS: Set[str] = set()


# ================================================================
# TRACK STUB
# ================================================================

class TrackStub:

    def __init__(
        self,
        track_id: Optional[str] = None,
    ):
        self.track_id = track_id

    def is_conflicted(
        self,
        *args,
        **kwargs,
    ):
        return False


# ================================================================
# EMIT STUB
# ================================================================

class EmitStub:

    def emit(
        self,
        *args,
        **kwargs,
    ):
        return False


# ================================================================
# ETHICS DECISION
# ================================================================

# ================================================================
# ETHICS DECISION
# ================================================================

@dataclass
class EthicsDecision:

    intent: List[str] = field(
        default_factory=list
    )

    controller: List[str] = field(
        default_factory=list
    )

    allowed: bool = False

    reason: str = DECISION_DEFERRED

    risk: float = RISK_LOW

    confidence: float = 0.0

    authority: str = AUTHORITY

    qbit_id: Optional[str] = None

    task_id: Optional[str] = None

    track_id: Optional[str] = None

    pipeline_id: Optional[str] = None

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )

    source: str = SOURCE

    # ------------------------------------------------------------
    # Runtime / Cognitive Dependencies
    # ------------------------------------------------------------
    #
    # Runtime reference supplied by the cognitive pipeline.
    #
    # EthicsDecision does NOT create or own MemoryCrystallizer.
    # It only retains the exact object supplied by the runtime.
    #
    # Excluded from repr/compare because this is a live runtime
    # service reference, not decision-state data.
    # ------------------------------------------------------------

    memory_crystallizer: Any = field(
        default=None,
        repr=False,
        compare=False,
    )

    health_monitor: Any = field(
        default=None,
        repr=False,
        compare=False,
    ) 

    module_registry: Any = field(
        default=None,
        repr=False,
        compare=False,
    )

    track_system: Any = field(
        default=None,
        repr=False,
        compare=False,
    )

    emit: Any = field(
        default=None,
        repr=False,
        compare=False,
    )

    qbit: Any = field(
        default=None,
        repr=False,
        compare=False,
    )
    event_bus: Any = field(
        default=None,
        repr=False,
        compare=False,
    )
    intent_engine: Any = field(
        default=None,
        repr=False,
        compare=False,
    )

    def to_dict(
        self,
    ) -> Dict[str, Any]:

        return {
            "intent": list(
                self.intent
            ),
            "controller": list(
                self.controller
            ),
            "allowed": bool(
                self.allowed
            ),
            "reason": self.reason,
            "risk": float(
                self.risk
            ),
            "confidence": float(
                self.confidence
            ),
            "authority": self.authority,
            "qbit_id": self.qbit_id,
            "task_id": self.task_id,
            "track_id": self.track_id,
            "pipeline_id": self.pipeline_id,
            "metadata": dict(
                self.metadata
            ),
            "source": self.source,
            "memory_crystallizer": (
                type(self.memory_crystallizer).__name__
                if self.memory_crystallizer is not None
                else None
            ),
            "health_monitor": (
                type(self.health_monitor).__name__
                if self.health_monitor is not None
                else None
            ),
            "module_registry": (
                type(self.module_registry).__name__
                if self.module_registry is not None
                else None
            ),
            "track_system": (
                type(self.track_system).__name__
                if self.track_system is not None
                else None
            ),
            "emit": (
                type(self.event_bus.emit).__name__
                if self.emit is not None
                else None
            ),
            "qbit": (
                type(self.qbit).__name__
                if self.qbit is not None
                else None
            ),
            "event_bus": (
                type(self.event_bus).__name__
                if self.event_bus is not None
                else None
            ),
            "event_bus": (
                type(self.intent_engine).__name__
                if self.intent_engine is not None
                else None
            ),
        }


# ================================================================
# ETHICS MANAGER
# ================================================================

class EthicsManager:

    def __init__(
        self,
        qbit=None,
        controller=None,
        health_monitor=None,
        module_registry=None,
        memory_crystallizer=None,
        track_system=None,
        intent_engine=None,
        registry=None,
        node_registry=None,
        node_manager=None,
        oracle=None,
        event_bus=None,
        skills=None,
        qbit_dialer=None,
        action_engine=None,
        compute_brain=None,
        transformer_brain=None,
        qbit_queue_loop=None,
        analytics_engine=None,
        channel_manager=None,
        channel_controller=None,
        watchdog=None,
        cognition_map=None,
        governor=None,
        track_context=None,
        storage_root="./SEED_ROOT",
        **kwargs,
    ):

        self.version = VERSION

        self.role = ROLE

        self.authority = AUTHORITY

        self.source = SOURCE

        self.initialized = True

        self.storage_root = storage_root

        # --------------------------------------------------------
        # CORE REFERENCES
        # --------------------------------------------------------

        self.qbit = qbit

        self.controller = controller

        self.qbit_dialer = qbit_dialer

        self.health_monitor = health_monitor

        self.module_registry = module_registry

        # Actual authoritative registry.
        #
        # If runtime supplies one, use it.
        # Otherwise attempt the real SRegistry singleton.
        self.registry = (
            registry
            if registry is not None
            else SEED_KERNEL_REGISTRY
        )

        self.node_registry = node_registry

        self.node_manager = node_manager

        self.oracle = oracle

        self.event_bus = event_bus

        self.track_system = track_system

        self.track_context = track_context

        self.intent_engine = intent_engine

        self.memory_crystallizer = memory_crystallizer

        self.action_engine = action_engine

        self.compute_brain = compute_brain

        self.transformer_brain = transformer_brain

        self.qbit_queue_loop = qbit_queue_loop

        self.analytics_engine = analytics_engine

        self.channel_manager = channel_manager

        self.channel_controller = channel_controller

        self.watchdog = watchdog

        self.cognition_map = cognition_map

        self.governor = governor

        # --------------------------------------------------------
        # COMPATIBILITY SKILLS OBJECT
        # --------------------------------------------------------

        self.skills = (
            skills
            if skills is not None
            else (
                _default_skills
                if _default_skills is not None
                else _SkillAdapter()
            )
        )

        # --------------------------------------------------------
        # POLICY
        # --------------------------------------------------------

        self.blocked_intents = set(
            DEFAULT_BLOCKED_INTENTS
        )

        self.blocked_controllers = set(
            DEFAULT_BLOCKED_CONTROLLERS
        )

        # --------------------------------------------------------
        # HISTORY
        # --------------------------------------------------------

        self._history = []

        self._feedback_history = []

        self._evaluation_count = 0

        self._allowed_count = 0

        self._denied_count = 0

        self._deferred_count = 0

        self.last_decision = None

        self.last_capability_refresh = 0.0

        self.last_node_refresh = 0.0

        # --------------------------------------------------------
        # COGNITIVE STATE
        # --------------------------------------------------------

        self._generation = 0

        self._cognitive_evaluation_count = 0

        self._learning_allowed_count = 0

        self._development_allowed_count = 0

        self._cognitive_history = []

        self._active_qbit_context = {}

        # --------------------------------------------------------
        # CAPABILITY CACHE
        # --------------------------------------------------------

        self._capability_cache = set()

        self._capability_sources = {}

        # --------------------------------------------------------
        # NODE CACHE
        # --------------------------------------------------------

        self._node_cache = []

        # --------------------------------------------------------
        # RUNTIME BINDINGS
        # --------------------------------------------------------

        self._runtime_bindings = {}

        self.bind_runtime(
            qbit=qbit,
            controller=controller,
            health_monitor=health_monitor,
            module_registry=module_registry,
            memory_crystallizer=memory_crystallizer,
            track_system=track_system,
            intent_engine=intent_engine,
            registry=self.registry,
            node_registry=node_registry,
            node_manager=node_manager,
            oracle=oracle,
            event_bus=event_bus,
            skills=skills,
            qbit_dialer=qbit_dialer,
            action_engine=action_engine,
            compute_brain=compute_brain,
            transformer_brain=transformer_brain,
            qbit_queue_loop=qbit_queue_loop,
            analytics_engine=analytics_engine,
            channel_manager=channel_manager,
            channel_controller=channel_controller,
            watchdog=watchdog,
            cognition_map=cognition_map,
            governor=governor,
            track_context=track_context,
        )

        # --------------------------------------------------------
        # SAFE DEFAULT TRACK
        # --------------------------------------------------------

        self.track = (
            track_system
            if track_system is not None
            else TrackStub()
        )

        # --------------------------------------------------------
        # INITIAL SNAPSHOTS
        # --------------------------------------------------------

        self.refresh_capabilities()

        self.sync_nodes()


    # ============================================================
    # SAFE HELPERS
    # ============================================================

    @staticmethod
    def _normalize_values(
        value: Any,
    ) -> List[str]:

        if value is None:
            return []

        if isinstance(
            value,
            str,
        ):

            value = value.strip()

            return (
                [value]
                if value
                else []
            )

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

            for item in value:

                if item is None:
                    continue

                text = str(
                    item
                ).strip()

                if text:
                    result.append(
                        text
                    )

            return result

        return [
            str(
                value
            ).strip()
        ]


    @staticmethod
    def _safe_get(
        obj: Any,
        name: str,
        default=None,
    ):

        try:
            return getattr(
                obj,
                name,
                default,
            )

        except Exception:
            return default


    @staticmethod
    def _safe_call(
        obj: Any,
        name: str,
        *args,
        **kwargs,
    ):

        if obj is None:
            return None

        try:

            fn = getattr(
                obj,
                name,
                None,
            )

            if not callable(fn):
                return None

            return fn(
                *args,
                **kwargs,
            )

        except Exception:
            return None


    # ============================================================
    # RUNTIME BINDING
    # ============================================================

    def bind_runtime(
        self,
        **bindings,
    ):

        for name, value in bindings.items():

            if value is None:
                continue

            if name == "skills":

                self.skills = value

                self._runtime_bindings[
                    "skills"
                ] = True

                continue

            setattr(
                self,
                name,
                value,
            )

            self._runtime_bindings[
                name
            ] = True

        if self.track_system is not None:

            self.track = (
                self.track_system
            )

        # Re-resolve authoritative registry
        # when runtime did not provide one.
        if self.registry is None:

            self.registry = (
                SEED_KERNEL_REGISTRY
            )

            if self.registry is not None:

                self._runtime_bindings[
                    "registry"
                ] = True

        self.refresh_capabilities()

        self.sync_nodes()

        return True


    # ============================================================
    # INDIVIDUAL BINDINGS
    # ============================================================

    def bind_registry(
        self,
        registry,
    ):

        if registry is None:
            return False

        self.registry = registry

        self._runtime_bindings[
            "registry"
        ] = True

        self.refresh_capabilities()

        self.sync_nodes()

        return True


    def bind_nodes(
        self,
        node_registry=None,
        node_manager=None,
    ):

        if node_registry is not None:

            self.node_registry = (
                node_registry
            )

            self._runtime_bindings[
                "node_registry"
            ] = True

        if node_manager is not None:

            self.node_manager = (
                node_manager
            )

            self._runtime_bindings[
                "node_manager"
            ] = True

        self.sync_nodes()

        return True


    def bind_qbit(
        self,
        qbit,
    ):

        if qbit is None:
            return False

        self.qbit = qbit

        self._runtime_bindings[
            "qbit"
        ] = True

        self._active_qbit_context = (
            self._qbit_identity(qbit)
        )

        return True


    def bind_qbit_dialer(
        self,
        qbit_dialer,
    ):

        if qbit_dialer is None:
            return False

        self.qbit_dialer = (
            qbit_dialer
        )

        self._runtime_bindings[
            "qbit_dialer"
        ] = True

        return True


    def bind_oracle(
        self,
        oracle,
    ):

        if oracle is None:
            return False

        self.oracle = oracle

        self._runtime_bindings[
            "oracle"
        ] = True

        return True


    # ============================================================
    # EVENT EMISSION
    # ============================================================

    def _emit(
        self,
        event_name: str,
        payload: Optional[
            Dict[str, Any]
        ] = None,
    ):

        event_bus = self.event_bus

        if event_bus is None:
            return False

        data = dict(
            payload
            or {}
        )

        data.setdefault(
            "source",
            self.source,
        )

        data.setdefault(
            "authority",
            self.authority,
        )

        data.setdefault(
            "timestamp",
            time.time(),
        )

        try:

            emitter = getattr(
                event_bus,
                "emit",
                None,
            )

            if not callable(emitter):
                return False

            try:

                result = emitter(
                    event_name,
                    payload=data,
                )

            except TypeError:

                result = emitter(
                    event_name,
                    **data,
                )

            return (
                result
                if result is not None
                else True
            )

        except Exception:
            return False


    # ============================================================
    # QBIT IDENTITY
    # ============================================================

    def _qbit_identity(
        self,
        qbit=None,
    ) -> Dict[str, Any]:

        qbit = (
            qbit
            if qbit is not None
            else self.qbit
        )

        if qbit is None:

            return {
                "qbit_id": None,
                "task_id": None,
                "track_id": None,
                "pipeline_id": None,
                "lineage": None,
            }

        def read(
            *names,
        ):

            for name in names:

                value = self._safe_get(
                    qbit,
                    name,
                    None,
                )

                if value is not None:
                    return value

                if isinstance(
                    qbit,
                    dict,
                ):

                    value = qbit.get(
                        name
                    )

                    if value is not None:
                        return value

            return None

        return {
            "qbit_id": read(
                "qbit_id",
                "id",
            ),
            "task_id": read(
                "task_id",
                "task",
            ),
            "track_id": read(
                "track_id",
                "track_id",
                "track",
            ),
            "pipeline_id": read(
                "pipeline_id",
                "pipeline",
            ),
            "lineage": read(
                "lineage",
                "parent_lineage",
            ),
        }


    # ============================================================
    # QBIT CONTEXT EXTRACTION
    # ============================================================

    def _qbit_context(
        self,
        qbit=None,
    ) -> Dict[str, Any]:

        qbit = (
            qbit
            if qbit is not None
            else self.qbit
        )

        identity = self._qbit_identity(
            qbit
        )

        context = {}

        for name in (
            "ethics_context",
            "cognitive_context",
            "learning_context",
        ):

            value = self._safe_get(
                qbit,
                name,
                None,
            )

            if value is None and isinstance(
                qbit,
                dict,
            ):

                value = qbit.get(
                    name
                )

            if isinstance(
                value,
                dict,
            ):

                context[name] = dict(
                    value
                )

        context[
            "identity"
        ] = identity

        return context


    # ============================================================
    # ATTACH QBIT CONTEXT
    # ============================================================

    def attach_ethics_context(
        self,
        qbit,
        decision,
    ) -> Dict[str, Any]:

        if qbit is None:
            return decision

        if hasattr(
            decision,
            "to_dict",
        ):

            decision = (
                decision.to_dict()
            )

        decision = dict(
            decision
            or {}
        )

        identity = self._qbit_identity(
            qbit
        )

        ethics_context = {
            "allowed": bool(
                decision.get(
                    "allowed",
                    False,
                )
            ),
            "reason": decision.get(
                "reason"
            ),
            "risk": float(
                decision.get(
                    "risk",
                    RISK_LOW,
                )
            ),
            "confidence": float(
                decision.get(
                    "confidence",
                    0.0,
                )
            ),
            "authority": self.authority,
            "source": self.source,
            "learning_allowed": bool(
                decision.get(
                    "metadata",
                    {},
                ).get(
                    "learning_allowed",
                    False,
                )
            ),
            "development_allowed": bool(
                decision.get(
                    "metadata",
                    {},
                ).get(
                    "development_allowed",
                    False,
                )
            ),
            "identity": dict(
                identity
            ),
            "registry_generation": (
                decision.get(
                    "metadata",
                    {},
                ).get(
                    "registry_generation"
                )
            ),
            "capability_state": (
                decision.get(
                    "metadata",
                    {},
                ).get(
                    "capability_state",
                    {},
                )
            ),
            "health_gate": (
                decision.get(
                    "metadata",
                    {},
                ).get(
                    "health_gate",
                )
            ),
            "timestamp": time.time(),
        }

        if isinstance(
            qbit,
            dict,
        ):

            qbit[
                "ethics_context"
            ] = ethics_context

            return decision

        try:

            setattr(
                qbit,
                "ethics_context",
                ethics_context,
            )

        except Exception:
            pass

        return decision


    # ============================================================
    # CAPABILITY EXTRACTION
    # ============================================================

    def _extract_capabilities(
        self,
        source: Any,
    ) -> Set[str]:

        capabilities = set()

        if source is None:
            return capabilities

        result = self._safe_call(
            source,
            "available_actions",
        )

        if result is not None:

            capabilities.update(
                self._normalize_values(
                    result
                )
            )

        result = self._safe_call(
            source,
            "get_capabilities",
        )

        if result is not None:

            if isinstance(
                result,
                dict,
            ):

                for key, value in result.items():

                    if isinstance(
                        value,
                        (
                            list,
                            tuple,
                            set,
                        ),
                    ):

                        for item in value:
                            capabilities.add(
                                str(item)
                            )

                    elif value:

                        capabilities.add(
                            str(key)
                        )

            else:

                capabilities.update(
                    self._normalize_values(
                        result
                    )
                )

        value = self._safe_get(
            source,
            "capabilities",
            None,
        )

        if value is not None:

            if isinstance(
                value,
                dict,
            ):

                for key, enabled in value.items():

                    if enabled:
                        capabilities.add(
                            str(key)
                        )

            else:

                capabilities.update(
                    self._normalize_values(
                        value
                    )
                )

        value = self._safe_get(
            source,
            "commands",
            None,
        )

        if value is not None:

            capabilities.update(
                self._normalize_values(
                    value
                )
            )

        value = self._safe_get(
            source,
            "actions",
            None,
        )

        if value is not None:

            capabilities.update(
                self._normalize_values(
                    value
                )
            )

        return {
            str(item).strip()
            for item in capabilities
            if str(item).strip()
        }


    # ============================================================
    # CAPABILITY REFRESH
    # ============================================================

    def refresh_capabilities(
        self,
    ) -> Set[str]:

        sources = {
            "skills": self.skills,
            "qbit_dialer": self.qbit_dialer,
            "module_registry": self.module_registry,
            "registry": self.registry,
            "node_registry": self.node_registry,
            "node_manager": self.node_manager,
            "action_engine": self.action_engine,
            "intent_engine": self.intent_engine,
        }

        combined = set()

        source_counts = {}

        for name, source in sources.items():

            found = self._extract_capabilities(
                source
            )

            if found:

                combined.update(
                    found
                )

                source_counts[
                    name
                ] = len(found)

        self._capability_cache = combined

        self._capability_sources = (
            source_counts
        )

        self.last_capability_refresh = (
            time.time()
        )

        return set(
            self._capability_cache
        )


    def available_actions(
        self,
    ) -> Set[str]:

        return set(
            self.refresh_capabilities()
        )


    # ============================================================
    # NODE EXTRACTION
    # ============================================================

    def _extract_nodes(
        self,
        source: Any,
    ) -> List[Any]:

        if source is None:
            return []

        for method in (
            "get_nodes",
            "list_nodes",
            "discover_nodes",
            "nodes_snapshot",
            "snapshot_nodes",
        ):

            result = self._safe_call(
                source,
                method,
            )

            if result is not None:

                if isinstance(
                    result,
                    dict,
                ):

                    return list(
                        result.values()
                    )

                if isinstance(
                    result,
                    (
                        list,
                        tuple,
                        set,
                    ),
                ):

                    return list(
                        result
                    )

        for name in (
            "nodes",
            "_nodes",
            "registered_nodes",
            "node_registry",
        ):

            value = self._safe_get(
                source,
                name,
                None,
            )

            if value is None:
                continue

            if isinstance(
                value,
                dict,
            ):

                return list(
                    value.values()
                )

            if isinstance(
                value,
                (
                    list,
                    tuple,
                    set,
                ),
            ):

                return list(
                    value
                )

        return []


    # ============================================================
    # NODE NORMALIZATION
    # ============================================================

    def _normalize_node(
        self,
        node: Any,
    ) -> Dict[str, Any]:

        if isinstance(
            node,
            dict,
        ):

            data = dict(
                node
            )

        else:

            data = {}

            for key in (
                "node_id",
                "id",
                "name",
                "type",
                "role",
                "state",
                "status",
                "health",
                "capabilities",
                "track_id",
                "qbit_id",
                "last_seen",
            ):

                value = self._safe_get(
                    node,
                    key,
                    None,
                )

                if value is not None:
                    data[key] = value

        node_id = (
            data.get(
                "node_id"
            )
            or data.get(
                "id"
            )
            or data.get(
                "name"
            )
        )

        return {
            "node_id": node_id,
            "name": data.get(
                "name",
                node_id,
            ),
            "type": data.get(
                "type"
            ),
            "role": data.get(
                "role"
            ),
            "state": data.get(
                "state",
                data.get(
                    "status"
                ),
            ),
            "health": data.get(
                "health"
            ),
            "capabilities": sorted(
                self._normalize_values(
                    data.get(
                        "capabilities"
                    )
                )
            ),
            "track_id": data.get(
                "track_id"
            ),
            "qbit_id": data.get(
                "qbit_id"
            ),
            "last_seen": data.get(
                "last_seen"
            ),
        }


    # ============================================================
    # NODE SYNCHRONIZATION
    # ============================================================

    def sync_nodes(
        self,
    ) -> List[Dict[str, Any]]:

        sources = [
            self.node_registry,
            self.node_manager,
            self.registry,
        ]

        nodes = []

        seen = set()

        for source in sources:

            for raw_node in self._extract_nodes(
                source
            ):

                node = self._normalize_node(
                    raw_node
                )

                identity = (
                    node.get(
                        "node_id"
                    )
                    or node.get(
                        "name"
                    )
                )

                if identity is None:
                    continue

                identity = str(
                    identity
                )

                if identity in seen:
                    continue

                seen.add(
                    identity
                )

                nodes.append(
                    node
                )

        self._node_cache = nodes

        self.last_node_refresh = (
            time.time()
        )

        return list(
            self._node_cache
        )


    # ============================================================
    # REGISTRY CONTEXT
    # ============================================================

    def _registry_context(
        self,
    ) -> Dict[str, Any]:

        registry = self.registry

        if registry is None:

            return {
                "bound": False,
                "generation": None,
                "nodes": len(
                    self._node_cache
                ),
            }

        generation = None

        for name in (
            "generation",
            "registry_generation",
            "version",
            "revision",
        ):

            value = self._safe_get(
                registry,
                name,
                None,
            )

            if value is not None:

                generation = value
                break

        return {
            "bound": True,
            "generation": generation,
            "nodes": len(
                self._node_cache
            ),
            "capabilities": len(
                self._capability_cache
            ),
        }


    # ============================================================
    # HEALTH
    # ============================================================

    def _health_is_stable(
        self,
    ) -> Optional[bool]:

        monitor = self.health_monitor

        if monitor is None:
            return None

        result = self._safe_call(
            monitor,
            "is_stable",
        )

        if isinstance(
            result,
            bool,
        ):
            return result

        result = self._safe_call(
            monitor,
            "is_operational",
            getattr(
                self.qbit_dialer,
                "name",
                "QbitDialer",
            ),
        )

        if isinstance(
            result,
            bool,
        ):
            return result

        status = self._safe_get(
            monitor,
            "status",
            None,
        )

        if callable(status):

            status = self._safe_call(
                monitor,
                "status",
            )

        if isinstance(
            status,
            dict,
        ):

            state = str(
                status.get(
                    "state",
                    status.get(
                        "health",
                        "",
                    ),
                )
            ).upper()

            if state in {
                "GREEN",
                "HEALTHY",
                "STABLE",
                "READY",
                "OPERATIONAL",
            }:
                return True

            if state in {
                "RED",
                "CRITICAL",
                "FAILED",
                "BLOCKED",
                "UNSTABLE",
            }:
                return False

        return None


    # ============================================================
    # TRACK CONFLICT
    # ============================================================

    def _track_is_conflicted(
        self,
        track_id=None,
    ) -> bool:

        tracker = (
            self.track_system
            or self.track
        )

        if tracker is None:
            return False

        result = self._safe_call(
            tracker,
            "is_conflicted",
            track_id,
        )

        return (
            bool(result)
            if isinstance(
                result,
                bool,
            )
            else False
        )


    # ============================================================
    # MEMORY LOOP
    # ============================================================

    def _memory_loop_detected(
        self,
        intent: str,
    ) -> bool:

        memory = (
            self.memory_crystallizer
        )

        if memory is None:
            return False

        for method in (
            "detect_loop",
            "is_loop",
            "has_recent_intent",
            "contains_recent_intent",
        ):

            result = self._safe_call(
                memory,
                method,
                intent,
            )

            if (
                isinstance(
                    result,
                    bool,
                )
                and result
            ):

                return True

        return False


    # ============================================================
    # BLOCKING
    # ============================================================

    def block_intent(
        self,
        intent: str,
    ):

        for value in self._normalize_values(
            intent
        ):

            self.blocked_intents.add(
                value.upper()
            )

        return True


    def unblock_intent(
        self,
        intent: str,
    ):

        for value in self._normalize_values(
            intent
        ):

            self.blocked_intents.discard(
                value.upper()
            )

        return True


    def block_controller(
        self,
        controller: str,
    ):

        for value in self._normalize_values(
            controller
        ):

            self.blocked_controllers.add(
                value.upper()
            )

        return True


    def unblock_controller(
        self,
        controller: str,
    ):

        for value in self._normalize_values(
            controller
        ):

            self.blocked_controllers.discard(
                value.upper()
            )

        return True


    # ============================================================
    # RISK
    # ============================================================

    def _risk_for_intent(
        self,
        intent: str,
    ) -> float:

        normalized = (
            str(intent or "")
            .upper()
            .strip()
        )

        if normalized in PROTECTED_INTENTS:
            return RISK_CRITICAL

        if any(
            token in normalized
            for token in (
                "DELETE",
                "WIPE",
                "DESTROY",
                "REWRITE",
                "UPGRADE",
                "DEPLOY",
                "MODIFY",
                "REPAIR",
            )
        ):

            return RISK_HIGH

        if any(
            token in normalized
            for token in (
                "EXECUTE",
                "RUN",
                "COMMAND",
            )
        ):

            return RISK_MEDIUM

        return RISK_LOW


    # ============================================================
    # CAPABILITY CHECK
    # ============================================================

    def _check_capability(
        self,
        intent: str,
    ) -> Dict[str, Any]:

        intent_upper = (
            str(intent or "")
            .upper()
            .strip()
        )

        capabilities = (
            self.refresh_capabilities()
        )

        normalized = {
            str(item).upper().strip()
            for item in capabilities
        }

        if intent_upper in normalized:

            return {
                "state": "AVAILABLE",
                "available": True,
                "authoritative": True,
                "capabilities": sorted(
                    capabilities
                ),
            }

        aliases = {
            intent_upper,
            intent_upper.lower(),
            intent_upper.replace(
                "_",
                ".",
            ),
            intent_upper.replace(
                ".",
                "_",
            ),
        }

        for alias in aliases:

            if str(alias).upper() in normalized:

                return {
                    "state": "AVAILABLE",
                    "available": True,
                    "authoritative": True,
                    "capabilities": sorted(
                        capabilities
                    ),
                }

        if self._capability_sources:

            return {
                "state": "UNAVAILABLE",
                "available": False,
                "authoritative": True,
                "capabilities": sorted(
                    capabilities
                ),
            }

        return {
            "state": "DEFERRED",
            "available": None,
            "authoritative": False,
            "capabilities": [],
        }


    # ============================================================
    # EVALUATE
    # ============================================================

    def evaluate(
        self,
        intent,
        controller=None,
        qbit=None,
        task_id=None,
        track_id=None,
        pipeline_id=None,
        metadata=None,
        **kwargs,
    ) -> Dict[str, Any]:

        self._evaluation_count += 1

        intents = self._normalize_values(
            intent
        )

        controllers = self._normalize_values(
            controller
            if controller is not None
            else self.controller
        )

        metadata = dict(
            metadata
            or {}
        )

        qbit_context = self._qbit_identity(
            qbit
        )

        qbit_id = qbit_context.get(
            "qbit_id"
        )

        if task_id is None:
            task_id = qbit_context.get(
                "task_id"
            )

        if track_id is None:
            track_id = qbit_context.get(
                "track_id"
            )

        if pipeline_id is None:
            pipeline_id = qbit_context.get(
                "pipeline_id"
            )

        allowed = True

        reason = "ALLOWED"

        risk = max(
            [
                self._risk_for_intent(
                    item
                )
                for item in intents
            ]
            or [RISK_LOW]
        )

        confidence = 1.0

        # --------------------------------------------------------
        # EMPTY INTENT
        # --------------------------------------------------------

        if not intents:

            allowed = False

            reason = "MISSING_INTENT"

        # --------------------------------------------------------
        # HARD BLOCK
        # --------------------------------------------------------

        elif any(
            item.upper()
            in self.blocked_intents
            for item in intents
        ):

            allowed = False

            reason = "INTENT_BLOCKED"

            risk = max(
                risk,
                RISK_HIGH,
            )

        # --------------------------------------------------------
        # PROTECTED
        # --------------------------------------------------------

        elif any(
            item.upper()
            in PROTECTED_INTENTS
            for item in intents
        ):

            allowed = False

            reason = "PROTECTED_INTENT"

            risk = RISK_CRITICAL

        # --------------------------------------------------------
        # CONTROLLER
        # --------------------------------------------------------

        elif any(
            item.upper()
            in self.blocked_controllers
            for item in controllers
        ):

            allowed = False

            reason = "CONTROLLER_BLOCKED"

            risk = max(
                risk,
                RISK_HIGH,
            )

        # --------------------------------------------------------
        # AUTHORITY
        # --------------------------------------------------------

        elif controllers:

            normalized_controllers = {
                item.upper()
                for item in controllers
            }

            if (
                "QBITDIALER"
                not in normalized_controllers
                and
                "QBIT_DIALER"
                not in normalized_controllers
            ):

                metadata[
                    "authority_boundary"
                ] = "QbitDialer"

        # --------------------------------------------------------
        # HEALTH
        # --------------------------------------------------------

        if allowed:

            stable = (
                self._health_is_stable()
            )

            if stable is False:

                metadata[
                    "health_gate"
                ] = "UNSTABLE"

                if risk >= RISK_HIGH:

                    allowed = False

                    reason = (
                        "HEALTH_UNSTABLE"
                    )

                else:

                    confidence = min(
                        confidence,
                        0.75,
                    )

            elif stable is None:

                metadata[
                    "health_gate"
                ] = "DEFERRED"

        # --------------------------------------------------------
        # CAPABILITY
        # --------------------------------------------------------

        capability_states = []

        if allowed:

            for item in intents:

                capability_states.append(
                    self._check_capability(
                        item
                    )
                )

            if any(
                result["state"]
                == "UNAVAILABLE"
                for result
                in capability_states
            ):

                allowed = False

                reason = (
                    "CAPABILITY_UNAVAILABLE"
                )

            elif all(
                result["state"]
                == "AVAILABLE"
                for result
                in capability_states
            ):

                metadata[
                    "capability_gate"
                ] = "AVAILABLE"

            else:

                metadata[
                    "capability_gate"
                ] = "DEFERRED"

        # --------------------------------------------------------
        # MEMORY LOOP
        # --------------------------------------------------------

        if allowed:

            if any(
                self._memory_loop_detected(
                    item
                )
                for item in intents
            ):

                allowed = False

                reason = (
                    "MEMORY_LOOP_DETECTED"
                )

                risk = max(
                    risk,
                    RISK_MEDIUM,
                )

                confidence = 0.95

        # --------------------------------------------------------
        # TRACK
        # --------------------------------------------------------

        if allowed:

            if self._track_is_conflicted(
                track_id
            ):

                allowed = False

                reason = (
                    "TRACK_CONFLICT"
                )

                risk = max(
                    risk,
                    RISK_MEDIUM,
                )

                confidence = 0.95

        # --------------------------------------------------------
        # LEARNING / DEVELOPMENT POLICY
        # --------------------------------------------------------

        learning_allowed = (
            allowed
            and risk < RISK_CRITICAL
        )

        development_allowed = (
            allowed
            and risk < RISK_CRITICAL
        )

        if learning_allowed:

            self._learning_allowed_count += 1

        if development_allowed:

            self._development_allowed_count += 1

        metadata[
            "learning_allowed"
        ] = learning_allowed

        metadata[
            "development_allowed"
        ] = development_allowed

        metadata[
            "registry_context"
        ] = self._registry_context()

        metadata[
            "node_count"
        ] = len(
            self._node_cache
        )

        metadata[
            "generation"
        ] = self._generation

        metadata[
            "cognitive_governance"
        ] = True

        # --------------------------------------------------------
        # FINAL DECISION
        # --------------------------------------------------------

        if allowed:

            self._allowed_count += 1

        else:

            self._denied_count += 1

        decision = EthicsDecision(
            intent=intents,
            controller=controllers,
            allowed=allowed,
            reason=reason,
            risk=risk,
            confidence=confidence,
            authority=self.authority,
            qbit_id=qbit_id,
            task_id=task_id,
            track_id=track_id,
            pipeline_id=pipeline_id,
            metadata={
                **metadata,
                "task_id": task_id,
                "track_id": track_id,
                "pipeline_id": pipeline_id,
                "authority": self.authority,
                "source": self.source,
                "capability_states":
                    capability_states,
                "capability_sources":
                    dict(
                        self._capability_sources
                    ),
            },
            source=self.source,
        )

        result = decision.to_dict()

        self.last_decision = decision

        self._history.append(
            result
        )

        if len(
            self._history
        ) > 500:

            self._history = (
                self._history[-500:]
            )

        self._emit(
            "ETHICS_EVALUATION",
            result,
        )

        return result


    # ============================================================
    # COGNITIVE QBIT EVALUATION
    # ============================================================

    def evaluate_qbit(
        self,
        qbit,
        intent=None,
        controller=None,
        thought=None,
        transform=None,
        metadata=None,
    ) -> Dict[str, Any]:

        self._cognitive_evaluation_count += 1

        self.bind_qbit(
            qbit
        )

        identity = self._qbit_identity(
            qbit
        )

        # --------------------------------------------------------
        # Infer intent from cognitive stages when available.
        # --------------------------------------------------------

        inferred_intents = (
            self._normalize_values(
                intent
            )
        )

        if not inferred_intents:

            for source in (
                transform,
                thought,
            ):

                if not isinstance(
                    source,
                    dict,
                ):
                    continue

                for key in (
                    "intent",
                    "action",
                    "command",
                    "cmd",
                    "classification",
                ):

                    value = source.get(
                        key
                    )

                    if value:

                        inferred_intents = (
                            self._normalize_values(
                                value
                            )
                        )

                        if inferred_intents:
                            break

                if inferred_intents:
                    break

        # --------------------------------------------------------
        # A cognitive observation without an executable intent
        # is NOT an error. It is deferred observation.
        # --------------------------------------------------------

        if not inferred_intents:

            result = self.evaluate(
                intent=[],
                controller=(
                    controller
                    or self.authority
                ),
                qbit=qbit,
                metadata={
                    **dict(
                        metadata
                        or {}
                    ),
                    "cognitive_stage":
                        True,
                    "thought_present":
                        thought is not None,
                    "transform_present":
                        transform is not None,
                },
            )

            result[
                "cognitive_state"
            ] = "OBSERVATION_ONLY"

            result[
                "execution_candidate"
            ] = False

            self.attach_ethics_context(
                qbit,
                result,
            )

            return result

        result = self.evaluate(
            intent=inferred_intents,
            controller=(
                controller
                or self.authority
            ),
            qbit=qbit,
            metadata={
                **dict(
                    metadata
                    or {}
                ),
                "cognitive_stage":
                    True,
                "thought":
                    thought,
                "transform":
                    transform,
            },
        )

        result[
            "cognitive_state"
        ] = (
            "AUTHORIZED_CANDIDATE"
            if result.get(
                "allowed"
            )
            else "GOVERNANCE_BLOCKED"
        )

        result[
            "execution_candidate"
        ] = bool(
            result.get(
                "allowed",
                False,
            )
        )

        result[
            "identity"
        ] = dict(
            identity
        )

        self.attach_ethics_context(
            qbit,
            result,
        )

        self._active_qbit_context = (
            self._qbit_context(qbit)
        )

        self._cognitive_history.append(
            dict(
                result
            )
        )

        if len(
            self._cognitive_history
        ) > 500:

            self._cognitive_history = (
                self._cognitive_history[-500:]
            )

        self._emit(
            "ETHICS_COGNITIVE_EVALUATION",
            result,
        )

        return result


    # ============================================================
    # COGNITIVE CONTEXT EVALUATION
    # ============================================================

    def evaluate_cognitive_context(
        self,
        qbit,
        thought=None,
        transform=None,
        intent=None,
        controller=None,
        metadata=None,
    ) -> Dict[str, Any]:

        return self.evaluate_qbit(
            qbit=qbit,
            intent=intent,
            controller=(
                controller
                or self.authority
            ),
            thought=thought,
            transform=transform,
            metadata=metadata,
        )


    # ============================================================
    # FEEDBACK / LEARNING
    # ============================================================

    def record_feedback(
        self,
        qbit=None,
        result=None,
        feedback=None,
        success=None,
        metadata=None,
    ) -> Dict[str, Any]:

        identity = self._qbit_identity(
            qbit
        )

        if success is None:

            if isinstance(
                result,
                dict,
            ):

                success = bool(
                    result.get(
                        "success",
                        result.get(
                            "ok",
                            False,
                        ),
                    )
                )

        record = {
            "feedback_id": str(
                uuid.uuid4()
            ),
            "qbit_id": identity.get(
                "qbit_id"
            ),
            "task_id": identity.get(
                "task_id"
            ),
            "track_id": identity.get(
                "track_id"
            ),
            "pipeline_id": identity.get(
                "pipeline_id"
            ),
            "success": (
                None
                if success is None
                else bool(success)
            ),
            "result": result,
            "feedback": feedback,
            "learning_allowed": bool(
                (
                    self.last_decision
                    and
                    self.last_decision.metadata.get(
                        "learning_allowed",
                        False,
                    )
                )
            ),
            "metadata": dict(
                metadata
                or {}
            ),
            "timestamp": time.time(),
            "source": self.source,
        }

        self._feedback_history.append(
            record
        )

        if len(
            self._feedback_history
        ) > 500:

            self._feedback_history = (
                self._feedback_history[-500:]
            )

        self._emit(
            "ETHICS_FEEDBACK",
            record,
        )

        return record


    # ============================================================
    # GENERATION
    # ============================================================

    def next_generation(
        self,
        qbit=None,
        result=None,
        feedback=None,
    ) -> Dict[str, Any]:

        self._generation += 1

        identity = self._qbit_identity(
            qbit
        )

        learning = {
            "generation": self._generation,
            "attempt": self._generation,
            "result": result,
            "feedback": feedback,
            "qbit_id": identity.get(
                "qbit_id"
            ),
            "task_id": identity.get(
                "task_id"
            ),
            "track_id": identity.get(
                "track_id"
            ),
            "pipeline_id": identity.get(
                "pipeline_id"
            ),
            "timestamp": time.time(),
        }

        if qbit is not None:

            if isinstance(
                qbit,
                dict,
            ):

                qbit[
                    "learning_context"
                ] = learning

            else:

                try:

                    setattr(
                        qbit,
                        "learning_context",
                        learning,
                    )

                except Exception:
                    pass

        self._emit(
            "ETHICS_NEXT_GENERATION",
            learning,
        )

        return learning


    # ============================================================
    # AUDIT
    # ============================================================

    def audit_history(
        self,
        limit: int = 50,
    ) -> List[
        Dict[str, Any]
    ]:

        try:
            limit = max(
                1,
                int(limit),
            )
        except Exception:
            limit = 50

        return list(
            self._history[
                -limit:
            ]
        )


    # ============================================================
    # FEEDBACK HISTORY
    # ============================================================

    def feedback_history(
        self,
        limit: int = 50,
    ) -> List[
        Dict[str, Any]
    ]:

        try:
            limit = max(
                1,
                int(limit),
            )
        except Exception:
            limit = 50

        return list(
            self._feedback_history[
                -limit:
            ]
        )


    # ============================================================
    # LAST DECISION
    # ============================================================

    def get_last_decision(
        self,
    ) -> Optional[
        Dict[str, Any]
    ]:

        if self.last_decision is None:
            return None

        return self.last_decision.to_dict()


    # ============================================================
    # TRACK SEED
    # ============================================================

    def seed_track(
        self,
        track_id=None,
        qbit=None,
        task_id=None,
        pipeline_id=None,
    ) -> Dict[str, Any]:

        context = self._qbit_identity(
            qbit
        )

        return {
            "track_id": (
                track_id
                or context.get(
                    "track_id"
                )
            ),
            "qbit_id": context.get(
                "qbit_id"
            ),
            "task_id": (
                task_id
                or context.get(
                    "task_id"
                )
            ),
            "pipeline_id": (
                pipeline_id
                or context.get(
                    "pipeline_id"
                )
            ),
            "authority": self.authority,
            "source": self.source,
            "timestamp": time.time(),
        }


    # ============================================================
    # RUNTIME SNAPSHOT
    # ============================================================

    def runtime_snapshot(
        self,
    ) -> Dict[str, Any]:

        self.refresh_capabilities()

        self.sync_nodes()

        return {
            "component":
                "EthicsManager",

            "version":
                self.version,

            "role":
                self.role,

            "authority":
                self.authority,

            "qbit":
                self._qbit_identity(
                    self.qbit
                ),

            "qbit_dialer":
                self.qbit_dialer is not None,

            "compute_brain":
                self.compute_brain is not None,

            "transformer_brain":
                self.transformer_brain is not None,

            "qbit_queue_loop":
                self.qbit_queue_loop is not None,

            "track_system":
                self.track_system is not None,

            "oracle":
                self.oracle is not None,

            "event_bus":
                self.event_bus is not None,

            "registry":
                self.registry is not None,

            "registry_context":
                self._registry_context(),

            "health_monitor":
                self.health_monitor is not None,

            "capabilities":
                sorted(
                    self._capability_cache
                ),

            "capability_sources":
                dict(
                    self._capability_sources
                ),

            "nodes":
                list(
                    self._node_cache
                ),

            "generation":
                self._generation,

            "cognitive_evaluation_count":
                self._cognitive_evaluation_count,

            "learning_allowed_count":
                self._learning_allowed_count,

            "development_allowed_count":
                self._development_allowed_count,

            "timestamp":
                time.time(),
        }


    # ============================================================
    # STATUS
    # ============================================================

    def status(
        self,
    ) -> Dict[str, Any]:

        self.refresh_capabilities()

        self.sync_nodes()

        return {
            "component":
                "EthicsManager",

            "version":
                self.version,

            "role":
                self.role,

            "authority":
                self.authority,

            "initialized":
                bool(
                    self.initialized
                ),

            "qbit":
                self.qbit is not None,

            "qbit_dialer":
                self.qbit_dialer is not None,

            "track_system":
                self.track_system is not None,

            "health_monitor":
                self.health_monitor is not None,

            "registry":
                self.registry is not None,

            "module_registry":
                self.module_registry is not None,

            "node_registry":
                self.node_registry is not None,

            "node_manager":
                self.node_manager is not None,

            "oracle":
                self.oracle is not None,

            "event_bus":
                self.event_bus is not None,

            "compute_brain":
                self.compute_brain is not None,

            "transformer_brain":
                self.transformer_brain is not None,

            "qbit_queue_loop":
                self.qbit_queue_loop is not None,

            "capabilities": {
                "actions":
                    sorted(
                        self._capability_cache
                    ),

                "action_count":
                    len(
                        self._capability_cache
                    ),

                "sources":
                    dict(
                        self._capability_sources
                    ),

                "nodes":
                    len(
                        self._node_cache
                    ),
            },

            "registry_context":
                self._registry_context(),

            "generation":
                self._generation,

            "evaluation_count":
                self._evaluation_count,

            "cognitive_evaluation_count":
                self._cognitive_evaluation_count,

            "allowed_count":
                self._allowed_count,

            "denied_count":
                self._denied_count,

            "deferred_count":
                self._deferred_count,

            "learning_allowed_count":
                self._learning_allowed_count,

            "development_allowed_count":
                self._development_allowed_count,

            "blocked_intents":
                sorted(
                    self.blocked_intents
                ),

            "blocked_controllers":
                sorted(
                    self.blocked_controllers
                ),

            "last_decision":
                self.get_last_decision(),

            "runtime_bindings": {
                key: bool(value)
                for key, value
                in self._runtime_bindings.items()
            },

            "timestamp":
                time.time(),
        }


# ================================================================
# SKILL ADAPTER
# ================================================================

class _SkillAdapter:

    def available_actions(
        self,
    ):

        return set()

    @property
    def capabilities(
        self,
    ):

        return set()


# ================================================================
# COMPATIBILITY ALIAS
# ================================================================

Ethics = EthicsManager


# ================================================================
# MODULE METADATA
# ================================================================

__all__ = [
    "EthicsManager",
    "Ethics",
    "EthicsDecision",
    "TrackStub",
    "EmitStub",
    "VERSION",
    "ROLE",
    "AUTHORITY",
    "DECISION_ALLOWED",
    "DECISION_DENIED",
    "DECISION_DEFERRED",
]