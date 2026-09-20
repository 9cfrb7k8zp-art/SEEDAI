# ==========================================================
# FILE: qbit.py
# PATH: SEED_ROOT/seed/core/qbit/qbit.py
# VERSION: 0.7.0
# BUILD: MULTI-QBIT / THREAD-SAFE-CARRIER / QUEUE-LINKED
#
# PURPOSE:
#   Qbit is the canonical SEED cognitive data carrier.
#
# SYSTEM MODEL:
#
#       HEARTBEAT
#           |
#           v
#     HeartbeatEmitter
#           |
#           v
#        QBIT CELL
#           |
#           v
#     QbitQueueLoop
#           |
#           v
#       QbitDialer
#           |
#           v
#       processing
#           |
#           v
#       QBIT_RESULT
#           |
#           v
#       EventBus
#
# METAPHOR:
#
#   Qbit            = blood cell / cognitive carrier
#   QbitQueueLoop   = bloodstream / transport layer
#   QbitDialer      = brain / processing authority
#   Heartbeat       = pulse / cycle origin
#   EventBus        = circulation / event distribution
#   TrackSystem     = lineage / identity tracking
#
# IMPORTANT AUTHORITY RULES:
#
#   Qbit:
#       - carries data
#       - owns identity
#       - owns state
#       - owns lineage
#       - reports lifecycle
#       - may be spawned/cloned
#
#   QbitQueueLoop:
#       - transports Qbits
#       - may process multiple Qbits
#       - controls queue scheduling
#       - may operate across worker threads/tasks
#
#   QbitDialer:
#       - processing authority
#       - command authority
#       - measurement authority
#
#   HeartbeatEmitter:
#       - heartbeat authority
#       - creates/pulses work origin
#       - does NOT become a command
#
#   EventBus:
#       - event circulation authority
#
# HARD RULES:
#
#   1. Qbit MUST NOT recursively invoke QbitDialer.
#   2. Qbit MUST NOT create its own heartbeat clock.
#   3. Qbit MUST NOT replace an existing TrackID.
#   4. Qbit MUST NOT manufacture command work merely by existing.
#   5. Multiple Qbits are valid.
#   6. Every Qbit retains independent identity.
#   7. Spawned Qbits retain explicit parent lineage.
#   8. Queue transport must be safe across threads.
#   9. Queue transport must be safe across async tasks.
#  10. Startup multiplication creates carriers, not commands.
# ==========================================================

from __future__ import annotations

import asyncio
import inspect
import logging
import random
import threading
import time
import uuid

from enum import Enum
from queue import Empty, Queue
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Optional,
    Tuple,
)

from seed.kernel_paths import RUNTIME_STATE_FILE
# ==========================================================
# SEED CORE REGISTRY / NODE ADAPTERS
# ==========================================================
#
# Qbit may observe the SEED node registry and carry node
# information through the cognitive pipeline.
#
# Qbit does NOT own the registry.
# Qbit does NOT register itself as a system controller.
# Qbit does NOT directly control nodes.
#
# Authority remains:
#
#   SEED Core Registry -> discovery / registration
#   Qbit              -> carrier
#   QbitQueueLoop     -> transport
#   QbitDialer        -> decision / command authority
#   Node              -> execution authority
#
# Imports are intentionally lazy so qbit.py remains import-safe.
# ==========================================================

def _get_seed_registry():

    try:
        from SRegistry import (
            get_registry,
            get_node,
            list_nodes,
        )

        return {
            "registry": get_registry,
            "get_node": get_node,
            "list_nodes": list_nodes,
        }

    except Exception:

        return {}

logger = logging.getLogger("Qbit")


# ==========================================================
# PUBLIC API
# ==========================================================

__all__ = [
    "Qbit",
    "QbitMode",
    "QbitLifecycle",
    "QbitConvector",
    "QBIT_OUTBOX_PROPOSAL",
    "QBIT_TICK",
    "QBIT_RESULT",
]


# ==========================================================
# EVENT CONTRACT
# ==========================================================

QBIT_OUTBOX_PROPOSAL = "OUTBOX_PROPOSAL"
QBIT_TICK = "QBIT_TICK"
QBIT_RESULT = "QBIT_RESULT"


# ==========================================================
# QBIT LIFECYCLE
# ==========================================================

class QbitLifecycle(Enum):

    CREATED = "CREATED"
    READY = "READY"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    HELD = "HELD"
    FAILED = "FAILED"
    STOPPED = "STOPPED"


# ==========================================================
# RUNTIME MODE
# ==========================================================

class QbitMode(Enum):

    PROBABILISTIC = "probabilistic"
    DETERMINISTIC = "deterministic"

class QbitSourceMode(Enum):
    UNKNOWN = "UNKNOWN"

    SYSTEM = "SYSTEM"
    STARTUP = "STARTUP"

    HEARTBEAT = "HEARTBEAT"
    ORACLE = "ORACLE"

    INTENT_ENGINE = "INTENT_ENGINE"
    COMPUTE_BRAIN = "COMPUTE_BRAIN"
    TRANSFORMER_BRAIN = "TRANSFORMER_BRAIN"
    ANALYTICS_ENGINE = "ANALYTICS_ENGINE"

    QBIT_DIALER = "QBIT_DIALER"
    QBIT_QUEUE_LOOP = "QBIT_QUEUE_LOOP"

    TRACK_SYSTEM = "TRACK_SYSTEM"
    EVENT_BUS = "EVENT_BUS"

    TIME_TRAVEL = "TIME_TRAVEL"
    RECOVERY = "RECOVERY"

    SPAWN = "SPAWN"
    CLONE = "CLONE"
    REPLAY = "REPLAY"

    EXTERNAL = "EXTERNAL"
    NODE = "NODE"

# ==========================================================
# TRACKING HELPERS
# ==========================================================

def _safe_parent_track():

    try:

        from seed.core.track_context import TrackContext  # type: ignore

        if hasattr(TrackContext, "get"):
            return TrackContext.get()

        if hasattr(TrackContext, "get_current"):
            return TrackContext.get_current()

    except Exception:
        pass

    return None


def gen_track_id(
    prefix: str = "QBIT",
    parent_id: Optional[str] = None,
    origin: str = "SYSTEM",
) -> Dict[str, Optional[str]]:

    return {
        "track_id": (
            f"{prefix}-{uuid.uuid4().hex[:12]}"
        ),
        "parent_id": parent_id,
        "origin": origin,
    }


# ==========================================================
# QBIT CORE
# ==========================================================

class Qbit:

    # ======================================================
    # CONSTRUCTION
    # ======================================================

    def __init__(
        self,
        *,
        emit=None,
        event_bus=None,
        qbit_id=None,
        payload=None,
        alpha=1 + 0j,
        beta=0 + 0j,
        mode=QbitMode.PROBABILISTIC,
        upstream_track=None,
        parent_qbit_id=None,
        generation: int = 0,
        source_mode=QbitSourceMode.UNKNOWN,
        source=None,
        producer=None,
        producer_id=None,
        creation_reason=None,
        upstream_source=None,
    ):

        if callable(payload):

            raise TypeError(
                "[QBIT ERROR] payload cannot be callable"
            )

        payload = payload or {}

        # --------------------------------------------------
        # Payload schema
        # --------------------------------------------------

        self.payload = _validate_schema(payload)

        # --------------------------------------------------
        # Payload shortcuts
        # --------------------------------------------------

        self.intent = self.payload["intent"]
        self.action = self.payload["action"]
        self.data = self.payload["data"]
        self.meta = self.payload["meta"]

        # --------------------------------------------------
        # Runtime bindings
        # --------------------------------------------------

        self.event_bus = event_bus
        self._emit_callback = (
            emit
            if callable(emit)
            else None
        )

        self.device_manager = None
        self.qbit_dialer = None
        self.qbit_queue_loop = None
        self.track_system = None

        # --------------------------------------------------
        # SEED NODE OBSERVATION
        # --------------------------------------------------
        #
        # Qbit can carry a snapshot of system/node knowledge.
        #
        # This is observation only.
        #
        # Commands are still decided by QbitDialer.
        # --------------------------------------------------

        self.node_registry = None

        self.node_observations: Dict[str, Dict[str, Any]] = {}

        self.node_control_context: Dict[str, Any] = {
            "last_node": None,
            "last_command": None,
            "last_result": None,
            "last_health": None,
            "last_event": None,
            "last_read": None,
            "last_write": None,
        }

        # --------------------------------------------------
        # Thread / async safety
        # --------------------------------------------------

        self._lock = threading.RLock()

        self._listeners: List[Callable] = []
        self._output = None

        # --------------------------------------------------
        # Stable identity
        # --------------------------------------------------

        self.qbit_id = (
            qbit_id
            or f"QBIT.{uuid.uuid4().hex[:12]}"
        )

        self.id = (
            f"TASK.{uuid.uuid4().hex[:8]}"
        )

        # --------------------------------------------------
        # Lineage
        # --------------------------------------------------

        self.upstream_track = (
            dict(upstream_track)
            if isinstance(upstream_track, dict)
            else {}
        )

        self.parent_qbit_id = parent_qbit_id

        self.generation = max(
            0,
            int(generation),
        )

        # --------------------------------------------------
        # PROVENANCE / SOURCE IDENTITY
        # --------------------------------------------------
        #
        # Qbit identity answers:
        #     "Which carrier is this?"
        #
        # Provenance answers:
        #     "Where did this carrier come from?"
        #
        # This does NOT replace TrackID.
        # It complements TrackSystem lineage.
        # --------------------------------------------------

        if isinstance(source_mode, QbitSourceMode):
            resolved_source_mode = source_mode

        elif isinstance(source_mode, str):

            try: 
                resolved_source_mode = QbitSourceMode(
                    source_mode.upper()
                )

            except ValueError:
                resolved_source_mode = QbitSourceMode.UNKNOWN

        else:
            resolved_source_mode = QbitSourceMode.UNKNOWN

        self.source_mode = resolved_source_mode

        self.provenance = {
            "source_mode": self.source_mode.value,
            "source": (
                str(source)
                if source is not None
                else self.source_mode.value
            ),
            "producer": (
                str(producer)
                if producer is not None
                else None
            ),
            "producer_id": (
                str(producer_id)
                if producer_id is not None
                else None
            ),
            "creation_reason": creation_reason,
            "upstream_source": (
                str(upstream_source)
                if upstream_source is not None
                else None
            ),
            "created_at": time.time(),
            "created_qbit_id": self.qbit_id,
            "parent_qbit_id": self.parent_qbit_id,
            "generation": self.generation,
            "route": [],
        }

        # --------------------------------------------------
        # Track identity
        # --------------------------------------------------

        parent_track_id = None

        if isinstance(upstream_track, dict):

            parent_track_id = (
                upstream_track.get("track_id")
            )

        if parent_track_id is None:

            parent_context = _safe_parent_track()

            if isinstance(parent_context, dict):

                parent_track_id = (
                    parent_context.get("track_id")
                )

            elif parent_context is not None:

                parent_track_id = str(
                    parent_context
                )

        self.track = gen_track_id(
            parent_id=parent_track_id,
            origin="QBIT_CORE",
        )

        # --------------------------------------------------
        # PROVENANCE / SOURCE IDENTITY
        # --------------------------------------------------
        #
        # Qbit identity answers:
        #     "Which carrier is this?"
        #
        # Provenance answers:
        #     "Where did this carrier come from?"
        #
        # This does NOT replace TrackID.
        # It complements TrackSystem lineage.
        # --------------------------------------------------

        if isinstance(source_mode, QbitSourceMode):
            resolved_source_mode = source_mode
        elif isinstance(source_mode, str):
            try:
                resolved_source_mode = QbitSourceMode(
                    source_mode.upper()
                )
            except ValueError:
                resolved_source_mode = QbitSourceMode.UNKNOWN
        else:
            resolved_source_mode = QbitSourceMode.UNKNOWN

        self.source_mode = resolved_source_mode

        self.provenance = {
            "source_mode": self.source_mode.value,
            "source": (
                str(source)
                if source is not None
                else self.source_mode.value
            ),
            "producer": (
                str(producer)
                if producer is not None
                else None
            ),
            "producer_id": (
                str(producer_id)
                if producer_id is not None
                else None
            ),
            "creation_reason": creation_reason,
            "upstream_source": (
                str(upstream_source)
                if upstream_source is not None
                else None
            ),
            "created_at": time.time(),
            "created_qbit_id": self.qbit_id,
            "parent_qbit_id": self.parent_qbit_id,
            "generation": self.generation,
            "route": [],
        }
        # --------------------------------------------------
        # Track identity
        # --------------------------------------------------

        parent_track_id = None

        if isinstance(upstream_track, dict):

            parent_track_id = (
                upstream_track.get("track_id")
            )

        if parent_track_id is None:

            parent_context = _safe_parent_track()

            if isinstance(parent_context, dict):

                parent_track_id = (
                    parent_context.get("track_id")
                )

            elif parent_context is not None:

                parent_track_id = str(
                    parent_context
                )

        self.track = gen_track_id(
            parent_id=parent_track_id,
            origin="QBIT_CORE",
        )

        # --------------------------------------------------
        # Lineage
        # --------------------------------------------------

        self.upstream_track = (
            dict(upstream_track)
            if isinstance(upstream_track, dict)
            else {}
        )

        self.parent_qbit_id = parent_qbit_id
        self.generation = max(
            0,
            int(generation),
        )

        # --------------------------------------------------
        # Cognitive state
        # --------------------------------------------------

        self.state: Tuple[complex, complex] = (
            complex(alpha),
            complex(beta),
        )

        self._normalize()

        # --------------------------------------------------
        # Internal task/data queue
        #
        # This is NOT the global QbitQueueLoop.
        #
        # It is local carrier storage.
        # --------------------------------------------------

        self.task_queue: List[Any] = []

        # --------------------------------------------------
        # Runtime mode
        # --------------------------------------------------

        if isinstance(mode, QbitMode):

            self.mode = mode

        elif isinstance(mode, str):

            self.mode = QbitMode(
                mode.lower()
            )

        else:

            self.mode = QbitMode.PROBABILISTIC

        # --------------------------------------------------
        # Lifecycle
        # --------------------------------------------------

        self.lifecycle = QbitLifecycle.CREATED

        self.flags: Dict[str, Any] = {}

        # --------------------------------------------------
        # Runtime counters
        # --------------------------------------------------

        self._last_tick = None
        self._last_result = None
        self._processed_ticks = 0
        self._result_sequence = 0
        self._queue_sequence = 0
        self._measurement_sequence = 0

        # --------------------------------------------------
        # Runtime context
        # --------------------------------------------------

        self.runtime_context: Dict[str, Any] = {

            "created_at": time.time(),

            "last_heartbeat": None,

            "last_processed": None,

            "last_result": None,

            "last_queued": None,

            "last_measurement": None,

            "queue_count": 0,

            "processing_count": 0,

            "generation": self.generation,

            "parent_qbit_id": self.parent_qbit_id,

        }

        # --------------------------------------------------
        # Kernel state check
        # --------------------------------------------------

        if not RUNTIME_STATE_FILE.exists():

            logger.warning(
                "[Qbit] Kernel context file missing: %s",
                RUNTIME_STATE_FILE,
            )

        self.lifecycle = QbitLifecycle.READY

        logger.info(
            "[Qbit] Initialized | "
            "qbit_id=%s | "
            "track=%s | "
            "generation=%d",
            self.qbit_id,
            self.track_id,
            self.generation,
        )

    # ======================================================
    # BASIC IDENTITY
    # ======================================================

    @property
    def track_id(self) -> Optional[str]:

        return self.track.get(
            "track_id"
        )

    @property
    def parent_track_id(self) -> Optional[str]:

        return self.track.get(
            "parent_id"
        )

    @property
    def origin(self) -> Optional[str]:

        return self.track.get(
            "origin"
        )

    @property
    def status(self) -> str:

        return self.lifecycle.value

    # ======================================================
    # ======================================================
    # PROVENANCE / SOURCE IDENTIFICATION
    # ======================================================

    def set_source(
        self,
        source_mode=None,
        *,
        source=None,
        producer=None,
        producer_id=None,
        reason=None,
        upstream_source=None,
    ):

        if source_mode is not None:

            if isinstance(
                source_mode,
                QbitSourceMode,
            ):
                resolved = source_mode

            elif isinstance(
                source_mode,
                str,
            ):

                try:
                    resolved = QbitSourceMode(
                        source_mode.upper()
                    )

                except ValueError:

                    resolved = (
                        QbitSourceMode.UNKNOWN
                    )

            else:

                resolved = (
                    QbitSourceMode.UNKNOWN
                )
 
            self.source_mode = resolved

            self.provenance[
                "source_mode"
            ] = resolved.value

        if source is not None:
            self.provenance["source"] = str(source)

        if producer is not None:
            self.provenance["producer"] = str(
                producer
            )

        if producer_id is not None:
            self.provenance["producer_id"] = str(
                producer_id
            )

        if reason is not None:
            self.provenance[
                "creation_reason"
            ] = reason

        if upstream_source is not None:
            self.provenance[
                "upstream_source"
            ] = str(upstream_source)

        return dict(self.provenance)


    def record_route(
        self,
        component,
        *,
        component_id=None,
        event=None,
        role=None,
    ):

        entry = {
            "component": str(component),
            "component_id": (
                str(component_id)
                if component_id is not None
                else None
            ),
            "event": event,
            "role": role,
            "timestamp": time.time(),
        }

        with self._lock:
            self.provenance.setdefault(
                "route",
                [],
            ).append(entry)

        return dict(entry)


    def identify_source(self) -> Dict[str, Any]:
        with self._lock:

            return {
                "qbit_id": self.qbit_id,
                "task_id": self.id,
                "track_id": self.track_id,
                "parent_track_id": (
                    self.parent_track_id
                ),
                "parent_qbit_id": (
                    self.parent_qbit_id
                ),
                "generation": self.generation,
                "source_mode": (
                    self.source_mode.value
                    if isinstance(
                        self.source_mode,
                        QbitSourceMode,
                    )
                    else str(
                        self.source_mode
                    )
                ),
                "provenance": {
                    key: (
                        list(value)
                        if key == "route"
                        and isinstance(value, list)
                        else value
                    )
                    for key, value
                    in self.provenance.items()
                },
            }


    @property
    def source(self) -> str:

        return self.provenance.get(
            "source",
            "UNKNOWN",
        )


    @property
    def producer(self) -> Optional[str]:

        return self.provenance.get(
            "producer"
        )

    # ======================================================
    # BINDINGS
    # ======================================================

    def attach_event_bus(
        self,
        event_bus,
    ):

        if event_bus is None:
            return self

        self.event_bus = event_bus

        logger.debug(
            "[Qbit] EventBus attached | qbit=%s",
            self.qbit_id,
        )

        return self

    bind_event_bus = attach_event_bus

    def attach_qbit_dialer(
        self,
        qbit_dialer,
    ):

        self.qbit_dialer = qbit_dialer

        logger.debug(
            "[Qbit] QbitDialer reference attached | "
            "qbit=%s",
            self.qbit_id,
        )

        return self

    def attach_queue_loop(
        self,
        queue_loop,
    ):

        self.qbit_queue_loop = queue_loop

        logger.debug(
            "[Qbit] QbitQueueLoop attached | "
            "qbit=%s | queue=%s",
            self.qbit_id,
            type(queue_loop).__name__
            if queue_loop is not None
            else "NONE",
        )

        return self

    def attach_track_system(
        self,
        track_system,
    ):

        self.track_system = track_system

        return self

    # ======================================================
    # SEED REGISTRY
    # ======================================================
    #
    # The registry belongs to SEED Core.
    #
    # Qbit only receives a reference to the existing registry.
    # It never creates or replaces one.
    # ======================================================

    def identify_transport(self) -> Dict[str, Any]:

        queue_loop = self.qbit_queue_loop

        return {
            "qbit_id": self.qbit_id,
            "queue_bound": queue_loop is not None,
            "queue_type": (
                type(queue_loop).__name__
                if queue_loop is not None
                else None
            ),
            "queue_loop_id": (
                id(queue_loop)
                if queue_loop is not None
                else None
            ),
            "has_put": (
                callable(
                    getattr(
                        queue_loop,
                        "put",
                        None,
                    )
                )
                if queue_loop is not None
                else False
            ),
            "is_physical_queue": (
                isinstance(queue_loop, Queue)
                if queue_loop is not None
                else False
            ),
        }

    def attach_node_registry(
        self,
        registry,
    ):

        self.node_registry = registry

        logger.debug(
            "[Qbit] Node registry attached | qbit=%s | registry=%s",
            self.qbit_id,
            type(registry).__name__
            if registry is not None
            else "NONE",
        )

        return self

    def bind_runtime(
        self,
        *,
        event_bus=None,
        emit=None,
        qbit_dialer=None,
        queue_loop=None,
        track_system=None,
        node_registry=None,
    ):

        if event_bus is not None:
            self.attach_event_bus(event_bus)

        if node_registry is not None:
            self.attach_node_registry(node_registry)

        if emit is not None:
            self.attach_emit(emit)

        if qbit_dialer is not None:
            self.attach_qbit_dialer(qbit_dialer)

        if queue_loop is not None:
            self.attach_queue_loop(queue_loop)

        if track_system is not None:
            self.attach_track_system(track_system)

        return self

    # ======================================================
    # NODE OBSERVATION
    # ======================================================

    def observe_node(
        self,
        node_name: str,
        node=None,
        *,
        health=None,
        state=None,
        metadata=None,
    ) -> Dict[str, Any]:

        if not node_name:
            raise ValueError(
                "[Qbit] node_name is required"
            )

        observation = {
            "node": str(node_name),
            "timestamp": time.time(),
            "health": health,
            "state": state,
            "metadata": dict(metadata or {}),
        }

        if node is not None:

            observation["node_type"] = (
                type(node).__name__
            )

            observation["available"] = True

        else:

            observation["node_type"] = None
            observation["available"] = False

        with self._lock:

            self.node_observations[
                str(node_name)
            ] = observation

            self.node_control_context[
                "last_node"
            ] = str(node_name)

            self.node_control_context[
                "last_health"
            ] = health

        self.flags[
            "node_observation_count"
        ] = len(self.node_observations)

        return dict(observation)

    def observe_registry(
        self,
    ) -> Dict[str, Dict[str, Any]]:

        registry = self.node_registry

        if registry is None:

            helpers = _get_seed_registry()

            get_registry = helpers.get(
                "registry"
            )

            if callable(get_registry):

                try:
                    registry = get_registry()

                except Exception as exc:

                    self.flags[
                        "registry_error"
                    ] = str(exc)

                    return {}

        if registry is None:

            self.flags[
                "registry_unavailable"
            ] = True

            return {}

        try:

            list_nodes = getattr(
                registry,
                "list_nodes",
                None,
            )

            if not callable(list_nodes):

                list_nodes = getattr(
                    registry,
                    "get_nodes",
                    None,
                )

            if not callable(list_nodes):

                self.flags[
                    "registry_node_api_missing"
                ] = True

                return {}

            nodes = list_nodes()

            if inspect.isawaitable(nodes):

                self.flags[
                    "registry_async_observer"
                ] = True

                return {}

            observed = {}

            if isinstance(nodes, dict):

                iterator = nodes.items()

            else:

                iterator = (
                    (str(node), node)
                    for node in nodes
                )

            for name, node in iterator:

                observation = self.observe_node(
                    name,
                    node,
                )

                observed[
                    str(name)
                ] = observation

            self.node_registry = registry

            self.flags[
                "registry_observed"
            ] = True

            self.flags[
                "registry_node_count"
            ] = len(observed)

            return observed

        except Exception as exc:

            self.flags[
                "registry_observation_error"
            ] = str(exc)

            logger.exception(
                "[Qbit] Registry observation failed"
            )

            return {}

    # ======================================================
    # NODE CONTROL PROPOSAL
    # ======================================================
    #
    # Qbit may carry a proposed node action.
    #
    # Qbit does NOT execute it.
    # QbitDialer remains command authority.
    # ======================================================

    def propose_node_command(
        self,
        node_name: str,
        command: str,
        *,
        data=None,
        reason=None,
        priority=None,
    ) -> Dict[str, Any]:

        if not node_name:
            raise ValueError(
                "[Qbit] node_name is required"
            )

        if not command:
            raise ValueError(
                "[Qbit] command is required"
            )

        proposal = {
            "type": "NODE_COMMAND_PROPOSAL",
            "node": str(node_name),
            "command": str(command),
            "data": dict(data or {}),
            "reason": reason,
            "priority": priority,
            "qbit_id": self.qbit_id,
            "track_id": self.track_id,
            "parent_id": self.parent_track_id,
            "timestamp": time.time(),
        }

        with self._lock:

            self.node_control_context[
                "last_node"
            ] = str(node_name)

            self.node_control_context[
                "last_command"
            ] = dict(proposal)

        self.put(proposal)

        self.emit(
            "NODE_COMMAND_PROPOSAL",
            payload=proposal,
        )

        return proposal

    def accept_node_result(
        self,
        result,
    ):

        with self._lock:

            self.node_control_context[
                "last_result"
            ] = result

        if isinstance(result, dict):

            node_name = result.get(
                "node"
            )

            if node_name:

                observation = self.node_observations.get(
                    str(node_name),
                    {},
                )

                observation.update({
                    "timestamp": time.time(),
                    "last_result": result,
                    "health": result.get(
                        "health",
                        observation.get("health"),
                    ),
                    "state": result.get(
                        "state",
                        observation.get("state"),
                    ),
                })

                self.node_observations[
                    str(node_name)
                ] = observation

        self.emit(
            "NODE_RESULT",
            payload={
                "qbit_id": self.qbit_id,
                "track_id": self.track_id,
                "result": result,
            },
        )

        return result


    def attach_emit(
        self,
        emit=None,
    ):

        if (
            emit is not None
            and not callable(emit)
        ):
            raise TypeError(
                "[Qbit] emit must be callable or None"
            )

        self._emit_callback = emit

        return self

    bind_emit = attach_emit

    # ======================================================
    # EVENT / OUTPUT
    #
    # Qbit is a carrier.
    #
    # EventBus remains the canonical circulation layer.
    # Explicit output callbacks are optional adapters.
    # Qbit never becomes the EventBus.
    # ======================================================

    def emit(
        self,
        event: str,
        payload: Optional[dict] = None,
    ):
        payload = payload or {}

        # --------------------------------------------------
        # Explicit output callback
        # --------------------------------------------------

        output = self._output

        if callable(output):

            try:
                return output(
                    event,
                    payload,
                )

            except Exception as exc:

                self.flags[
                    "emit_error"
                ] = str(exc)

                logger.exception(
                    "[Qbit] Output callback failed"
                )

        # --------------------------------------------------
        # Constructor/runtime callback
        # --------------------------------------------------

        callback = self._emit_callback

        if callable(callback):

            try:
                return callback(
                    event,
                    payload,
                )

            except Exception as exc:

                self.flags[
                    "emit_callback_error"
                ] = str(exc)

                logger.exception(
                    "[Qbit] Emit callback failed"
                )

        # --------------------------------------------------
        # EventBus is canonical circulation.
        # --------------------------------------------------

        event_bus = self.event_bus

        if event_bus is not None:

            try:

                publish = getattr(
                    event_bus,
                    "publish",
                    None,
                )

                if callable(publish):

                    return publish(
                        event,
                        payload=payload,
                    )

                emit = getattr(
                    event_bus,
                    "emit",
                    None,
                )

                if callable(emit):

                    return emit(
                        event,
                        payload,
                    )

            except Exception as exc:

                self.flags[
                    "event_bus_emit_error"
                ] = str(exc)

                logger.exception(
                    "[Qbit] EventBus emission failed"
                )

        return None

    # ======================================================
    # DEVICE COMPATIBILITY
    # ======================================================

    def link_device_manager(
        self,
        device_manager,
    ):

        self.device_manager = device_manager

        return self

    # ======================================================
    # TRACKING
    # ======================================================

    def set_track(
        self,
        track_id: Optional[str] = None,
        parent_id: Optional[str] = None,
        origin: Optional[str] = None,
    ):

        with self._lock:

            if track_id is not None:

                current_track_id = self.track.get(
                    "track_id"
                )

                if (
                    current_track_id is not None
                    and current_track_id != track_id
                ):

                    raise RuntimeError(
                        "[QBIT TRACK ERROR] "
                        "Existing TrackID cannot be replaced"
                    )

                self.track["track_id"] = track_id

            if parent_id is not None:

                self.track["parent_id"] = parent_id

            if origin is not None:

                self.track["origin"] = origin

        return dict(self.track)

    # ======================================================
    # LIFECYCLE
    # ======================================================

    def set_lifecycle(
        self,
        lifecycle,
        *,
        reason=None,
    ):

        if isinstance(
            lifecycle,
            QbitLifecycle,
        ):

            new_state = lifecycle

        else:

            new_state = QbitLifecycle(
                str(lifecycle).upper()
            )

        with self._lock:

            previous = self.lifecycle

            self.lifecycle = new_state

            if reason is not None:

                self.flags[
                    "lifecycle_reason"
                ] = reason

        logger.debug(
            "[Qbit] Lifecycle | "
            "qbit=%s | %s -> %s | reason=%s",
            self.qbit_id,
            previous.value,
            new_state.value,
            reason,
        )

        return new_state

    # ======================================================
    # QUEUE / CARRIER API
    # ======================================================

    def mark_queued(
        self,
        *,
        queue_name=None,
    ):

        with self._lock:

            self._queue_sequence += 1

            self.runtime_context[
                "last_queued"
            ] = time.time()

            self.runtime_context[
                "queue_count"
            ] += 1

            self.flags[
                "queue_sequence"
            ] = self._queue_sequence

            if queue_name is not None:

                self.flags[
                    "queue_name"
                ] = queue_name

        self.set_lifecycle(
            QbitLifecycle.QUEUED
        )

        return self

    def mark_processing(self):

        with self._lock:

            self.runtime_context[
                "processing_count"
            ] += 1

        self.set_lifecycle(
            QbitLifecycle.PROCESSING
        )

        return self

    def mark_processed(
        self,
        *,
        result=None,
    ):

        if result is not None:
            self.accept_result(result)

        self.set_lifecycle(
            QbitLifecycle.PROCESSED
        )

        return self

    def hold(
        self,
        reason=None,
    ):

        self.set_lifecycle(
            QbitLifecycle.HELD,
            reason=reason,
        )

        return self

    def fail(
        self,
        reason=None,
    ):

        if reason is not None:

            self.flags[
                "failure_reason"
            ] = str(reason)

        self.set_lifecycle(
            QbitLifecycle.FAILED,
            reason=reason,
        )

        return self

    def stop(self):

        self.set_lifecycle(
            QbitLifecycle.STOPPED
        )

        return self

    # ======================================================
    # QUEUE HANDOFF
    # ======================================================

    def enqueue(
        self,
        queue_loop=None,
    ):
        self.record_route(
            type(queue_loop).__name__,
            component_id=id(queue_loop),
            event="ENQUEUE",
            role="TRANSPORT",
        )

        queue_loop = (
            queue_loop
            or self.qbit_queue_loop
        )

        if queue_loop is None:

            self.flags[
                "queue_error"
            ] = "queue_loop_unavailable"

            return False

        self.mark_queued(
            queue_name=type(
                queue_loop
            ).__name__,
        )

        # --------------------------------------------------
        # Prefer canonical QbitQueueLoop APIs.
        # --------------------------------------------------

        for method_name in (
            "enqueue_qbit",
            "submit_qbit",
            "put_qbit",
            "enqueue",
            "submit",
            "put",
        ):

            method = getattr(
                queue_loop,
                method_name,
                None,
            )

            if not callable(method):
                continue

            try:

                result = method(self)

                if inspect.isawaitable(result):

                    # Do not create a new event loop here.
                    # Caller may await the returned coroutine.
                    return result

                return (
                    True
                    if result is None
                    else result
                )

            except TypeError:

                # Compatibility fallback:
                # some queue implementations expect
                # a processing frame rather than a Qbit.
                continue

            except Exception:

                logger.exception(
                    "[Qbit] Queue handoff failed | "
                    "qbit=%s | queue=%s",
                    self.qbit_id,
                    type(queue_loop).__name__,
                )

                self.fail(
                    "queue_handoff_failed"
                )

                return False

        self.flags[
            "queue_error"
        ] = "no_supported_enqueue_method"

        self.set_lifecycle(
            QbitLifecycle.READY
        )

        return False

    # ======================================================
    # HEARTBEAT / THOUGHT LOOP ENTRY
    # ======================================================

    def process_tick(
        self,
        tick,
    ):
        self.record_route(
            "HeartbeatEmitter",
            event="PROCESS_TICK",
            role="PULSE_INPUT",
        )
        with self._lock:

            self._last_tick = tick

            self._processed_ticks += 1

            self.runtime_context[
                "last_heartbeat"
            ] = time.time()

        # --------------------------------------------------
        # Qbit does not own the heartbeat.
        #
        # It merely receives the pulse.
        # --------------------------------------------------

        self._normalize()

        with self._lock:

            self.runtime_context[
                "last_processed"
            ] = time.time()

        return self.state

    # ======================================================
    # BUILD PROCESSING FRAME
    # ======================================================

    def build_processing_frame(
        self,
        *,
        tick=None,
        source="HeartbeatEmitter",
        event="HEARTBEAT",
        channel=None,
        track_id=None,
        parent_id=None,
        **metadata,
    ) -> Dict[str, Any]:

        if tick is None:
            tick = self._last_tick

        # --------------------------------------------------
        # NEVER manufacture a replacement TrackID.
        # --------------------------------------------------

        if track_id is None:
            track_id = self.track_id

        if parent_id is None:
            parent_id = self.parent_track_id

        return {

            "event": event,

            "type": "QBIT",

            "source": source,

            "qbit_id": self.qbit_id,

            "task_id": self.id,

            "track_id": track_id,

            "parent_id": parent_id,

            "parent_qbit_id": self.parent_qbit_id,

            "generation": self.generation,

            "lifecycle": self.status,

            "tick": tick,

            "timestamp": time.time(),

            "payload": self.payload,

            "state": {
                "alpha": self.state[0],
                "beta": self.state[1],
            },

            "mode": (
                self.mode.value
                if isinstance(
                    self.mode,
                    QbitMode,
                )
                else str(self.mode)
            ),

            "flags": dict(
                self.flags
            ),

            "runtime": dict(
                self.runtime_context
            ),

            "source_mode": (
                self.source_mode.value
                if isinstance(
                    self.source_mode,
                    QbitSourceMode,
                )
                else str(self.source_mode)
            ),

            "provenance": dict(
                self.provenance
            ),

            # Canonical carrier object.
            "qbit": self,
        }

    # ======================================================
    # RESULT
    # ======================================================

    def build_result(
        self,
        *,
        tick=None,
        source="QbitDialer",
        processing_stage="PROCESSED",
        channel=None,
        track_id=None,
        parent_id=None,
        result=None,
        **metadata,
    ) -> Dict[str, Any]:

        if tick is None:
            tick = self._last_tick

        if track_id is None:
            track_id = self.track_id

        if parent_id is None:
            parent_id = self.parent_track_id

        with self._lock:

            self._result_sequence += 1

            sequence = self._result_sequence

        result_payload = {

            "event": QBIT_RESULT,

            "type": "QBIT_RESULT",

            "source": source,

            "processing_stage": processing_stage,

            "qbit_id": self.qbit_id,

            "task_id": self.id,

            "track_id": track_id,

            "parent_id": parent_id,

            "parent_qbit_id": self.parent_qbit_id,

            "generation": self.generation,

            "tick": tick,

            "sequence": sequence,

            "timestamp": time.time(),

            "state": {
                "alpha": self.state[0],
                "beta": self.state[1],
            },

            "energy": self.data_weight,

            "payload": self.payload,

            "result": result,

            "flags": dict(
                self.flags
            ),

            "source_mode": (
                self.source_mode.value
                if isinstance(
                    self.source_mode,
                    QbitSourceMode,
                )
                else str(self.source_mode)
            ),

            "provenance": dict(
                self.provenance
            ),
        }

        if channel is not None:
            result_payload[
                "channel"
            ] = channel

        if metadata:
            result_payload[
                "metadata"
            ] = dict(metadata)

        self._last_result = result_payload

        self.runtime_context[
            "last_result"
        ] = result_payload

        return result_payload

    # ======================================================
    # RESULT FEEDBACK
    # ======================================================

    def accept_result(
        self,
        result,
    ):

        with self._lock:

            self._last_result = result

            self.runtime_context[
                "last_result"
            ] = result

            if isinstance(
                result,
                dict,
            ):

                metadata = result.get(
                    "metadata"
                )

                if isinstance(
                    metadata,
                    dict,
                ):

                    for key, value in metadata.items():

                        if key.startswith(
                            "qbit_"
                        ):

                            self.flags[
                                key
                            ] = value

                result_tick = result.get(
                    "tick"
                )

                if result_tick is not None:

                    self._last_tick = (
                        result_tick
                    )

        return result


    # ======================================================
    # QBIT MULTIPLICATION
    # ======================================================

    def spawn(
        self,
        *,
        payload=None,
        parent_track=True,
        origin="QBIT_SPAWN",
        generation=None,
        copy_state=True,
        metadata=None,
    ) -> "Qbit":

        # --------------------------------------------------
        # Spawn means create another carrier.
        #
        # It does NOT create a command.
        # It does NOT start a loop.
        # It does NOT create a queue.
        #
        # The child inherits the authoritative runtime
        # bindings of the parent.
        # --------------------------------------------------

        if payload is None:

            payload = dict(self.payload)

            if isinstance(self.data, dict):
                payload["data"] = dict(self.data)

        else:

            payload = _validate_schema(payload)

        if generation is None:
            generation = self.generation + 1

        # --------------------------------------------------
        # Preserve quantum/runtime state when requested.
        # --------------------------------------------------

        if copy_state:
            alpha, beta = self.state
        else:
            alpha = 1 + 0j
            beta = 0 + 0j

        # --------------------------------------------------
        # Create carrier only.
        #
        # Qbit itself does NOT create runtime infrastructure.
        # --------------------------------------------------

        child = Qbit(
            event_bus=self.event_bus,
            payload=payload,
            alpha=alpha,
            beta=beta,
            mode=self.mode,

            source_mode=QbitSourceMode.SPAWN,
            source="QBIT_SPAWN",
            producer="Qbit",
            producer_id=self.qbit_id,
            creation_reason="spawn",
            upstream_source=self.source,

            upstream_track=(
                dict(self.track)
                if parent_track
                else {}
            ),
            parent_qbit_id=self.qbit_id,
            generation=generation,
        )

        # --------------------------------------------------
        # Preserve the authoritative runtime bindings.
        # --------------------------------------------------

        child.bind_runtime(
            event_bus=self.event_bus,
            emit=self._emit_callback,
            qbit_dialer=self.qbit_dialer,
            queue_loop=self.qbit_queue_loop,
            track_system=self.track_system,
            node_registry=self.node_registry,
        )

        # --------------------------------------------------
        # Preserve observations.
        # --------------------------------------------------

        child.node_observations = {
            name: dict(observation)
            for name, observation
            in self.node_observations.items()
        }

        # --------------------------------------------------
        # Preserve control context.
        # --------------------------------------------------

        child.node_control_context = {
            key: (
                dict(value)
                if isinstance(value, dict)
                else value
            )
            for key, value
            in self.node_control_context.items()
        }


        child.provenance[
            "parent_qbit_id"
        ] = self.qbit_id

        child.provenance[
            "parent_track_id"
        ] = self.track_id

        child.provenance[
            "upstream_source"
        ] = self.source

        child.record_route(
            "Qbit.spawn",
            component_id=self.qbit_id,
            event="SPAWN",
            role="DERIVATION",
        )

        # --------------------------------------------------
        # Preserve device binding.
        # --------------------------------------------------

        if self.device_manager is not None:
            child.device_manager = self.device_manager

        # --------------------------------------------------
        # Apply caller metadata.
        # --------------------------------------------------

        if metadata:
            child.flags.update(metadata)

        child.flags["spawned_from"] = self.qbit_id
        child.track["origin"] = origin

        logger.debug(
            "[Qbit] Spawned child | "
            "parent=%s | child=%s | generation=%d | "
            "queue_bound=%s",
            self.qbit_id,
            child.qbit_id,
            child.generation,
            child.qbit_queue_loop is not None,
        )

        return child


    # ======================================================
    # STARTUP POPULATION
    #
    # AUTHORITATIVE POPULATION CONSTRUCTION
    #
    # Qbits are created here.
    #
    # Runtime ownership remains external:
    #
    #   EventBus
    #   QbitDialer
    #   QbitQueueLoop
    #   TrackSystem
    #   SRegistry / node registry
    #
    # This method MUST NOT:
    #
    #   - create a queue
    #   - create a processing loop
    #   - create a QbitDialer
    #   - create another runtime
    #
    # Population creation and queue submission remain
    # separate operations.
    # ======================================================

    @classmethod
    def spawn_population(
        cls,
        count: int = 1,
        *,
        event_bus=None,
        queue_loop=None,
        qbit_dialer=None,
        track_system=None,
        node_registry=None,
        payload=None,
        mode=QbitMode.PROBABILISTIC,
        origin="SYSTEM_STARTUP",
    ):

        # --------------------------------------------------
        # NORMALIZE COUNT
        # --------------------------------------------------

        try:
            count = max(
                0,
                int(count),
            )

        except (TypeError, ValueError):
            count = 0

        population = []

        # --------------------------------------------------
        # CREATE / BIND POPULATION
        # --------------------------------------------------

        for index in range(count):

            qbit = cls(
                event_bus=event_bus,
                payload=(
                    dict(payload)
                    if isinstance(payload, dict)
                    else payload
                ),
                mode=mode,

                source_mode=QbitSourceMode.STARTUP,
                source=origin,
                producer="Qbit.spawn_population",
                creation_reason="startup_population",
            )

            qbit.record_route(
                "Qbit.spawn_population",
                event="POPULATION_CREATE",
                role="CARRIER_CREATION",
            )

            # --------------------------------------------------
            # Bind to the EXISTING authoritative runtime.
            #
            # Nothing is created here.
            # --------------------------------------------------

            qbit.bind_runtime(
                event_bus=event_bus,
                qbit_dialer=qbit_dialer,
                queue_loop=queue_loop,
                track_system=track_system,
                node_registry=node_registry,
            )

            # --------------------------------------------------
            # Population metadata.
            # --------------------------------------------------

            qbit.flags["population_index"] = index
            qbit.flags["population_origin"] = origin

            population.append(qbit)

        logger.info(
            "[Qbit] Population created | "
            "count=%d | origin=%s | "
            "queue_bound=%s | dialer_bound=%s",
            len(population),
            origin,
            queue_loop is not None,
            qbit_dialer is not None,
        )

        return population



    # ======================================================
    # PUT / SUBMIT DATA
    #
    # AUTHORITATIVE QBIT TRANSPORT PATH
    #
    # Qbit is the carrier.
    # QbitQueueLoop owns transport + processing.
    #
    # AUTHORITATIVE FLOW:
    #
    #     Qbit
    #       |
    #       v
    #     Qbit.put()
    #       |
    #       v
    #     QbitQueueLoop.put()
    #       |
    #       v
    #     QbitQueueLoop processing
    #       |
    #       v
    #     QbitDialer
    #       |
    #       v
    #     ComputeBrain
    #       |
    #       v
    #     ThoughtPacket
    #       |
    #       v
    #     TransformerBrain
    #       |
    #       v
    #     Command proposal
    #       |
    #       v
    #     QbitDialer.submit_command()
    #
    # Qbit MUST NOT:
    #
    #     - create a queue
    #     - maintain a processing queue
    #     - consume a queue
    #     - create a processing loop
    #     - bypass QbitQueueLoop
    #
    # ======================================================

    def put(
        self,
        item: Any,
        *,
        priority=None,
    ):


        # --------------------------------------------------
        # Carrier validation
        # --------------------------------------------------

        if callable(item):
            raise TypeError(
                "[Qbit] Callable items are not valid "
                "carrier data"
            )

        # --------------------------------------------------
        # Resolve authoritative QueueLoop.
        #
        # qbit_queue_loop is the canonical binding.
        #
        # queue_loop is retained only as compatibility
        # with older Qbit revisions.
        # --------------------------------------------------

        queue_loop = getattr(
            self,
            "qbit_queue_loop",
            None,
        )

        if queue_loop is None:
            queue_loop = getattr(
                self,
                "queue_loop",
                None,
            )

        # --------------------------------------------------
        # No QueueLoop means no transport.
        #
        # NEVER silently fall back to task_queue.
        # --------------------------------------------------

        if queue_loop is None:
            if hasattr(self, "stats"):
                self.stats[
                    "queue_submission_failures"
                ] = (
                    self.stats.get(
                        "queue_submission_failures",
                        0,
                    )
                    + 1
                )

            logger.warning(
                "[Qbit] Carrier submission rejected | "
                "qbit=%s | "
                "reason=QbitQueueLoop not bound",
                getattr(
                    self,
                    "qbit_id",
                    "UNKNOWN",
                ),
            )

            raise RuntimeError(
                "[Qbit] QbitQueueLoop is not bound; "
                "carrier cannot enter the processing system"
            )

        # --------------------------------------------------
        # Validate authoritative transport interface.
        # --------------------------------------------------

        put = getattr(
            queue_loop,
            "put",
            None,
        )

        if not callable(put):

            if hasattr(self, "stats"):
                self.stats[
                    "queue_submission_failures"
                ] = (
                    self.stats.get(
                        "queue_submission_failures",
                        0,
                    )
                    + 1
                )

            raise TypeError(
                "[Qbit] Bound QbitQueueLoop does not "
                "expose authoritative put()"
            )

        # --------------------------------------------------
        # Submit to QueueLoop.
        #
        # QueueLoop, not Qbit, decides how the item is
        # queued, prioritized, tracked, and processed.
        # --------------------------------------------------

        try:

            if priority is None:

                result = put(
                    item
                )

            else:

                try:
                    result = put(
                        item,
                        priority=priority,
                    )

                except TypeError:
                    # Compatibility with older QueueLoop
                    # implementations that accept only
                    # put(item).
                    result = put(
                        item
                    )

            # --------------------------------------------------
            # Transport diagnostics
            # --------------------------------------------------

            if hasattr(self, "stats"):

                self.stats[
                    "queue_submissions"
                ] = (
                    self.stats.get(
                        "queue_submissions",
                        0,
                    )
                    + 1
                )

            logger.debug(
                "[Qbit] Carrier submitted → "
                "QbitQueueLoop | "
                "qbit=%s | priority=%s | "
                "queue=%s",
                getattr(
                    self,
                    "qbit_id",
                    "UNKNOWN",
                ),
                priority,
                type(queue_loop).__name__,
            )

            return (
                item
                if result is None
                else result
            )

        except Exception as exc:

            if hasattr(self, "stats"):

                self.stats[
                    "queue_submission_failures"
                ] = (
                    self.stats.get(
                        "queue_submission_failures",
                        0,
                    )
                    + 1
                )

            logger.error(
                "[Qbit] Carrier submission failed → "
                "QbitQueueLoop | "
                "qbit=%s | error=%s",
                getattr(
                    self,
                    "qbit_id",
                    "UNKNOWN",
                ),
                exc,
            )

            raise


    # ======================================================
    # QUEUE BINDING DIAGNOSTIC
    # ======================================================

    def queue_ready(
        self,
    ) -> bool:

        queue_loop = getattr(
            self,
            "qbit_queue_loop",
            None,
        )

        if queue_loop is None:
            queue_loop = getattr(
                self,
                "queue_loop",
                None,
            )

        return (
            queue_loop is not None
            and callable(
                getattr(
                    queue_loop,
                    "put",
                    None,
                )
            )
        )


    # ======================================================
    # OUTBOX
    # ======================================================

    def push_outbox_proposal(
        self,
        path: str,
        content: str,
        meta: dict,
    ):

        return self.put({

            "type": QBIT_OUTBOX_PROPOSAL,

            "source": "observer_outbox",

            "path": path,

            "content": content,

            "meta": meta,

            "ts": time.time(),

        })

    # ======================================================
    # UPSTREAM TRACK
    # ======================================================

    def set_upstream_track(
        self,
        track=None,
        **kwargs,
    ):

        if track is None:
            track = {}

        if isinstance(
            track,
            dict,
        ):

            self.upstream_track = dict(
                track
            )

        else:

            self.upstream_track = {
                "track_id": str(track)
            }

        if kwargs:

            self.upstream_track.update(
                kwargs
            )

        return self.upstream_track

    def upstream_track_update(
        self,
        command,
        meta,
        **kwargs,
    ):

        self.set_upstream_track({

            "command": command,

            "meta": meta,

            **kwargs,

        })

        return self.upstream_track

    # ======================================================
    # STATE MATH
    # ======================================================

    def set_state(
        self,
        state: Tuple[complex, complex],
    ) -> None:

        if (
            not isinstance(
                state,
                tuple,
            )
            or len(state) != 2
        ):

            raise ValueError(
                "Qbit state must be a 2-tuple"
            )

        with self._lock:

            self.state = (
                complex(state[0]),
                complex(state[1]),
            )

            self._normalize()

    def _normalize(self) -> None:

        a, b = self.state

        norm = (
            abs(a) ** 2
            + abs(b) ** 2
        )

        if norm == 0:

            self.flags[
                "state_error"
            ] = "zero_vector"

            raise ValueError(
                "Invalid Qbit state "
                "(zero vector)"
            )

        factor = norm ** 0.5

        self.state = (
            a / factor,
            b / factor,
        )

    # ======================================================
    # MODE CONTROL
    # ======================================================

    def set_mode(
        self,
        mode: QbitMode,
    ) -> None:

        if not isinstance(
            mode,
            QbitMode,
        ):

            if isinstance(
                mode,
                str,
            ):

                try:

                    mode = QbitMode(
                        mode.lower()
                    )

                except ValueError:

                    raise ValueError(
                        f"Unknown Qbit mode: {mode}"
                    )

            else:

                raise TypeError(
                    "Qbit mode must be QbitMode "
                    "or valid mode string"
                )

        self.mode = mode

    # ======================================================
    # MEASUREMENT
    # ======================================================

    def measure(self) -> int:

        alpha, beta = self.state

        with self._lock:

            self._measurement_sequence += 1

            self.runtime_context[
                "last_measurement"
            ] = time.time()

            self.flags[
                "measurement_sequence"
            ] = self._measurement_sequence

        if (
            self.mode
            == QbitMode.DETERMINISTIC
        ):

            return (
                0
                if abs(alpha)
                >= abs(beta)
                else 1
            )

        return (
            0
            if random.random()
            < abs(alpha) ** 2
            else 1
        )

    @property
    def data_weight(self) -> float:

        a, b = self.state

        return (
            abs(a) ** 2
            + abs(b) ** 2
        )

    def get(
        self,
        key,
        default=None,
    ):

        if isinstance(
            self.payload,
            dict,
        ):

            return self.payload.get(
                key,
                default,
            )

        return default

    # ======================================================
    # LISTENER API
    # ======================================================

    def subscribe(
        self,
        callback,
    ):

        if not callable(callback):

            raise ValueError(
                "Qbit.subscribe requires "
                "a callable"
            )

        with self._lock:

            if callback not in self._listeners:

                self._listeners.append(
                    callback
                )

        return callback

    on = subscribe

    def add_listener(
        self,
        listener,
    ):

        return self.subscribe(
            listener
        )

    def _notify_listeners(
        self,
        data,
    ):

        with self._lock:

            listeners = list(
                self._listeners
            )

        for listener in listeners:

            try:

                result = listener(
                    data
                )

                # Listener may optionally be async.
                if inspect.isawaitable(
                    result
                ):

                    try:

                        loop = (
                            asyncio.get_running_loop()
                        )

                        loop.create_task(
                            result
                        )

                    except RuntimeError:

                        pass

            except Exception:

                logger.exception(
                    "[Qbit] Listener error"
                )

    # ======================================================
    # OUTPUT
    # ======================================================

    def set_output(
        self,
        fn,
    ):

        if (
            fn is not None
            and not callable(fn)
        ):

            raise TypeError(
                "Qbit output must be "
                "callable or None"
            )

        self._output = fn

        return fn


    # ======================================================
    # RESULT NOTIFICATION
    # ======================================================

    def notify_result(
        self,
        result,
    ):

        self.accept_result(
            result
        )

        self._notify_listeners(
            result
        )

        return result

    # ======================================================
    # COMMAND EXECUTION
    #
    # Qbit may carry a command.
    # Qbit does NOT become the command authority.
    # ======================================================

    async def execute_command(
        self,
        command: Any,
    ) -> None:

        await asyncio.sleep(0)

        self.emit(
            "QBIT_COMMAND_EXECUTED",
            payload={

                "command": command,

                "qbit_id": self.qbit_id,

                "state": self.state,

                "payload": self.payload,

                "track": dict(
                    self.track,
                ),

                "upstream_track": dict(
                    self.upstream_track,
                ),

                "mode": (
                    self.mode.value
                    if isinstance(
                        self.mode,
                        QbitMode,
                    )
                    else str(
                        self.mode,
                    )
                ),

                "flags": dict(
                    self.flags,
                ),

            },
        )

    # ======================================================
    # COMMAND CREATION
    # ======================================================

    @classmethod
    def create_task(
        cls,
        command,
        action,
        task_id=None,
        meta=None,
        name=None,
        **kwargs,
    ):

        qbit = cls(

            payload={

                "intent": kwargs.get(
                    "intent",
                    "unknown",
                ),

                "action": action,

                "data": {

                    "command": command,

                    **kwargs,

                },

                "meta": meta or {},

            },

            source_mode=QbitSourceMode.EXTERNAL,

            source="QBIT_CREATE_TASK",

            producer="Qbit.create_task",

            creation_reason="task_creation",

        )

        qbit.task_queue.append({

            "id": task_id,

            "action": action,

            "meta": meta,

            "name": name,

        })

        return qbit

    @classmethod
    def create_command(
        cls,
        intent,
        action,
        data=None,
        meta=None,
    ):

        return cls(

            payload={

                "intent": intent,

                "action": action,

                "data": data or {},

                "meta": meta or {},

            },

            source_mode=QbitSourceMode.EXTERNAL,

            source="QBIT_CREATE_COMMAND",

            producer="Qbit.create_command",

            creation_reason="command_creation",

        )

    # ======================================================
    # NORMALIZATION / ENSURE
    # ======================================================

    @classmethod
    def ensure(
        cls,
        obj: Any,
    ) -> "Qbit":

        if isinstance(
            obj,
            cls,
        ):

            return obj

        if callable(obj):

            sig = inspect.signature(
                obj
            )

            required_parameters = [

                parameter

                for parameter
                in sig.parameters.values()

                if (

                    parameter.default
                    is inspect.Parameter.empty

                    and parameter.kind
                    in (

                        inspect.Parameter.POSITIONAL_ONLY,

                        inspect.Parameter.POSITIONAL_OR_KEYWORD,

                    )

                )

            ]

            if not required_parameters:

                obj = obj()

            else:

                raise TypeError(
                    "[QBIT ERROR] Callable "
                    "requires parameters: "
                    f"{obj}"
                )

        if isinstance(
            obj,
            dict,
        ):

            return cls(
                payload=obj
            )

        raise TypeError(
            f"[QBIT ERROR] Cannot convert "
            f"{type(obj)} into Qbit"
        )

    # ======================================================
    # SNAPSHOT
    # ======================================================

    def snapshot(
        self,
    ) -> Dict[str, Any]:

        with self._lock:

            return {

                "id": self.id,

                "qbit_id": self.qbit_id,

                "track": dict(
                    self.track
                ),

                "upstream_track": dict(
                    self.upstream_track
                ),

                "parent_qbit_id": (
                    self.parent_qbit_id
                ),

                "generation": self.generation,

                "lifecycle": self.status,

                "payload": self.payload,

                "state": {

                    "alpha": self.state[0],

                    "beta": self.state[1],

                },

                "mode": (

                    self.mode.value

                    if isinstance(
                        self.mode,
                        QbitMode,
                    )

                    else str(
                        self.mode
                    )

                ),

                "flags": dict(
                    self.flags
                ),

                "last_tick": (
                    self._last_tick
                ),

                "processed_ticks": (
                    self._processed_ticks
                ),

                "result_sequence": (
                    self._result_sequence
                ),

                "last_result": (
                    self._last_result
                ),

                "runtime_context": dict(
                    self.runtime_context
                ),

                "node_observations": {
                    name: dict(observation)
                    for name, observation
                    in self.node_observations.items()
                },

                "node_control_context": {
                    key: (
                        dict(value)
                        if isinstance(value, dict)
                        else value
                    )
                    for key, value
                    in self.node_control_context.items()
                },
                "source_mode": (
                     self.source_mode.value
                     if isinstance(
                        self.source_mode,
                        QbitSourceMode,
                    )
                    else str(self.source_mode)
                ),

                "provenance": {
                    key: (
                        list(value)
                        if key == "route"
                        and isinstance(value, list)
                        else value
                    )
                    for key, value in self.provenance.items()
                },
            }

    # ======================================================
    # REPRESENTATION
    # ======================================================

    def __repr__(
        self,
    ) -> str:

        return (

            "Qbit("

            f"id={self.qbit_id}, "

            f"track={self.track_id}, "

            f"state={self.state}, "

            f"mode={self.mode.value}, "

            f"status={self.status}, "

            f"generation={self.generation}"

            ")"

        )


# ==========================================================
# CONVERSION UTILITIES
# ==========================================================

class QbitConvector:

    @staticmethod
    def to_tuple(
        data: Any,
    ) -> Tuple[complex, complex]:

        if isinstance(
            data,
            tuple,
        ):

            return (
                QbitConvector
                ._validate_tuple(data)
            )

        if isinstance(
            data,
            list,
        ):

            return (
                QbitConvector
                ._validate_tuple(
                    tuple(data)
                )
            )

        if isinstance(
            data,
            dict,
        ):

            return (
                QbitConvector
                ._from_dict(data)
            )

        raise ValueError(
            f"Cannot convert "
            f"{type(data)} to Qbit state"
        )

    @staticmethod
    def _validate_tuple(
        state: Tuple[Any, Any],
    ) -> Tuple[complex, complex]:

        if len(state) != 2:

            raise ValueError(
                "Qbit tuple must have "
                "exactly 2 elements"
            )

        return (

            complex(state[0]),

            complex(state[1]),

        )

    @staticmethod
    def _from_dict(
        data: dict,
    ) -> Tuple[complex, complex]:

        if "state" in data:

            return (
                QbitConvector
                ._validate_tuple(
                    tuple(
                        data["state"]
                    )
                )
            )

        if (
            "alpha" in data
            and "beta" in data
        ):

            return (

                complex(
                    data["alpha"]
                ),

                complex(
                    data["beta"]
                ),

            )

        raise ValueError(
            "Dict does not contain "
            "Qbit state"
        )


# ==========================================================
# QBIT SCHEMA
# ==========================================================

REQUIRED_KEYS = {

    "intent",

    "action",

    "data",

    "meta",

}


def _validate_schema(
    payload: dict,
) -> dict:

    if not isinstance(
        payload,
        dict,
    ):

        payload = {
            "data": payload
        }

    payload.setdefault(
        "intent",
        "unknown",
    )

    payload.setdefault(
        "action",
        "noop",
    )

    payload.setdefault(
        "data",
        {},
    )

    payload.setdefault(
        "meta",
        {},
    )

    return payload