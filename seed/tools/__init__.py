
# =============================================================
# SEED-AI Tools Subsystem - Autonomous Nervous System
#
# File:
# SEED_ROOT/seed/tools/__init__.py
#
# VERSION:
# 4.0.0
#
# ROLE:
#   Dynamic tool discovery
#   Tool-node registration
#   Dependency discovery / binding
#   Capability awareness
#   Tool lifecycle
#   Tool execution muscles
#   Neural-node topology
#   Telemetry / learning
#   Reports / recommendations
#
# AUTHORITY:
#
#   SRegistry
#       authoritative node identity / registration
#
#   registry_runtime
#       runtime dependency / state visibility
#
#   EventBus
#       event transport
#
#   TrackSystem
#       tracking / lineage / observation
#
#   NeuralBridge
#       neural-node dependency / translation bridge
#
#   QbitDialer
#       authoritative command admission / execution
#
#   ToolOrgan
#       local tool-node execution wrapper
#
# IMPORTANT:
#
# This subsystem NEVER creates:
#
#   QbitQueueLoop
#   QbitDialer
#   EventBus
#   NeuralBridge
#   TrackSystem
#
# This subsystem NEVER becomes a command authority.
#
# Recommendations are DATA.
#
# QbitDialer decides whether a recommendation becomes an
# executable command through its authoritative command path.
#
# =============================================================

import asyncio
import importlib
import inspect
import json
import logging
import pkgutil
import threading
import time
import uuid
from collections import deque
from pathlib import Path


# =============================================================
# OPTIONAL AUTHORITATIVE REGISTRY IMPORT
#
# SRegistry remains authoritative.
# We do not replace it with a local registry.
# =============================================================

try:
    from SRegistry import register_node
except Exception:
    register_node = None


# =============================================================
# LOGGER
# =============================================================

logger = logging.getLogger("SEED-TOOLS")
logger.setLevel(logging.INFO)


# =============================================================
# PATHS
# =============================================================

THIS_PATH = Path(__file__).resolve().parent
STATUS_FILE = THIS_PATH / "tools_status.json"


# =============================================================
# SHARED TRACK ID
# =============================================================

def gen_track_id(prefix="SEEDTools_init"):

    return f"{prefix}-{uuid.uuid4().hex[:8]}"


# =============================================================
# TOOL NODE LIFECYCLE
# =============================================================

NODE_DISCOVERED = "DISCOVERED"
NODE_REGISTERED = "REGISTERED"
NODE_LOADING = "LOADING"
NODE_AVAILABLE = "AVAILABLE"
NODE_ACTIVE = "ACTIVE"
NODE_READY = "READY"
NODE_DEGRADED = "DEGRADED"
NODE_FAILED = "FAILED"
NODE_DISABLED = "DISABLED"
NODE_WAITING = "WAITING"


# =============================================================
# RECOMMENDATION ACTIONS
# =============================================================

ACTION_ACTIVATE = "ACTIVATE"
ACTION_DEACTIVATE = "DEACTIVATE"
ACTION_RESTART = "RESTART"
ACTION_REBIND = "REBIND"
ACTION_REPAIR = "REPAIR"
ACTION_UPDATE = "UPDATE"
ACTION_REBUILD = "REBUILD"
ACTION_RETRY = "RETRY"
ACTION_QUARANTINE = "QUARANTINE"
ACTION_INVESTIGATE = "INVESTIGATE"
ACTION_MONITOR = "MONITOR"


# =============================================================
# METADATA HELPERS
#
# These allow future tools to expose explicit metadata without
# requiring this package to know the tool's filename or class.
#
# Supported module metadata:
#
#   TOOL_NAME
#   TOOL_ROLE
#   TOOL_VERSION
#   TOOL_CAPABILITIES
#   TOOL_DEPENDENCIES
#   TOOL_ENTRYPOINT
#   TOOL_CLASS
#   TOOL_ALWAYS_ON
#
# Legacy metadata remains supported.
# =============================================================

_METADATA_CAPABILITY_NAMES = (
    "TOOL_CAPABILITIES",
    "CAPABILITIES",
    "capabilities",
    "TOOLS",
    "SUPPORTED_OPERATIONS",
)

_METADATA_DEPENDENCY_NAMES = (
    "TOOL_DEPENDENCIES",
    "DEPENDENCIES",
    "dependencies",
    "REQUIRES",
    "requires",
)

_METADATA_CLASS_NAMES = (
    "TOOL_CLASS",
    "tool_class",
)

_METADATA_ENTRYPOINT_NAMES = (
    "TOOL_ENTRYPOINT",
    "tool_entrypoint",
)

_METADATA_NAME_NAMES = (
    "TOOL_NAME",
    "tool_name",
)

_METADATA_ROLE_NAMES = (
    "TOOL_ROLE",
    "tool_role",
)

_METADATA_VERSION_NAMES = (
    "TOOL_VERSION",
    "tool_version",
    "VERSION",
    "version",
)

_METADATA_ALWAYS_ON_NAMES = (
    "TOOL_ALWAYS_ON",
    "always_on",
)


# =============================================================
# SAFE COPY
# =============================================================

def deepcopy_safe(value):

    try:
        return json.loads(
            json.dumps(
                value,
                default=str,
            )
        )

    except Exception:

        try:
            return dict(value)

        except Exception:

            return str(value)


# =============================================================
# TOOL NETWORK
#
# Dynamic topology / awareness layer.
#
# It is NOT:
#
#   command authority
#   execution queue
#   QbitQueueLoop
#   EventBus replacement
#   registry replacement
#
# =============================================================

class ToolNodeNetwork:

    name = "tool_node_network"
    version = "4.0.0"
    role = "dynamic-tool-neural-network"

    authority = (
        "observation-capability-recommendation"
    )

    def __init__(self):

        self._lock = threading.RLock()

        self.nodes = {}
        self.connections = {}
        self.capabilities = {}
        self.dependencies = {}
        self.providers = {}
        self.lifecycle = {}

        self.recommendations = deque(
            maxlen=512
        )

        self.reports = deque(
            maxlen=256
        )

        self.errors = deque(
            maxlen=128
        )

        self.sequence = 0
        self.last_update = None

        # -----------------------------------------------------
        # Existing authoritative runtime references.
        #
        # These are injected dynamically.
        # -----------------------------------------------------

        self.event_bus = None
        self.track_system = None
        self.neural_bridge = None
        self.qbit_dialer = None
        self.registry = None
        self.registry_runtime = None
        self.runtime_context = None

        # -----------------------------------------------------
        # Statistics
        # -----------------------------------------------------

        self.stats = {
            "modules_discovered": 0,
            "nodes_discovered": 0,
            "nodes_registered": 0,
            "nodes_available": 0,
            "nodes_active": 0,
            "nodes_ready": 0,
            "nodes_failed": 0,
            "nodes_waiting": 0,
            "dependencies_discovered": 0,
            "dependencies_bound": 0,
            "capabilities_discovered": 0,
            "recommendations": 0,
            "reports": 0,
            "errors": 0,
        }

    # =========================================================
    # SEQUENCE
    # =========================================================

    def _next_sequence(self):

        with self._lock:

            self.sequence += 1
            self.last_update = time.time()

            return self.sequence

    # =========================================================
    # RUNTIME ATTACHMENT
    # =========================================================

    def attach_runtime(
        self,
        *,
        event_bus=None,
        track_system=None,
        neural_bridge=None,
        qbit_dialer=None,
        registry=None,
        registry_runtime=None,
        runtime_context=None,
    ):

        with self._lock:

            if event_bus is not None:
                self.event_bus = event_bus

            if track_system is not None:
                self.track_system = track_system

            if neural_bridge is not None:
                self.neural_bridge = neural_bridge

            if qbit_dialer is not None:
                self.qbit_dialer = qbit_dialer

            if registry is not None:
                self.registry = registry

            if registry_runtime is not None:
                self.registry_runtime = (
                    registry_runtime
                )

            if runtime_context is not None:
                self.runtime_context = (
                    runtime_context
                )

        self._discover_runtime_providers()
        self._connect_authoritative_nodes()

        return self.snapshot()

    # =========================================================
    # DYNAMIC PROVIDER DISCOVERY
    # =========================================================

    def _discover_runtime_providers(self):

        providers = {}

        with self._lock:

            runtime_objects = {
                "EventBus": self.event_bus,
                "TrackSystem": self.track_system,
                "NeuralBridge": self.neural_bridge,
                "QbitDialer": self.qbit_dialer,
                "SRegistry": self.registry,
                "registry_runtime": self.registry_runtime,
                "RuntimeContext": self.runtime_context,
            }

            for name, instance in (
                runtime_objects.items()
            ):

                if instance is None:
                    continue

                providers[name] = instance

                class_name = type(
                    instance
                ).__name__

                providers[class_name] = instance

                object_name = getattr(
                    instance,
                    "name",
                    None,
                )

                if object_name:
                    providers[str(
                        object_name
                    )] = instance

                object_node_id = getattr(
                    instance,
                    "node_id",
                    None,
                )

                if object_node_id:
                    providers[str(
                        object_node_id
                    )] = instance

            self.providers = providers

        return providers

    # =========================================================
    # AUTHORITATIVE TOPOLOGY
    # =========================================================

    def _connect_authoritative_nodes(self):

        bindings = (
            (
                "TOOLS",
                self.event_bus,
                "EventBus",
                "EVENT_TRANSPORT",
            ),
            (
                "TOOLS",
                self.track_system,
                "TrackSystem",
                "TRACK_OBSERVATION",
            ),
            (
                "TOOLS",
                self.neural_bridge,
                "NeuralBridge",
                "NEURAL_BRIDGE",
            ),
            (
                "TOOLS",
                self.qbit_dialer,
                "QbitDialer",
                "COMMAND_AUTHORITY",
            ),
            (
                "TOOLS",
                self.registry,
                "SRegistry",
                "IDENTITY_AUTHORITY",
            ),
            (
                "TOOLS",
                self.registry_runtime,
                "registry_runtime",
                "RUNTIME_STATE",
            ),
            (
                "TOOLS",
                self.runtime_context,
                "RuntimeContext",
                "RUNTIME_CONTEXT",
            ),
        )

        for source, provider, target, relation in bindings:

            if provider is None:
                continue

            self.connect(
                source,
                target,
                relation=relation,
            )

    # =========================================================
    # DEPENDENCY RESOLUTION
    # =========================================================

    def resolve_dependency(
        self,
        dependency,
    ):

        dependency = str(
            dependency
        )

        normalized = {
            dependency,
            dependency.lower(),
            dependency.replace(
                "_",
                "",
            ).lower(),
        }

        with self._lock:

            for provider_name, provider in (
                self.providers.items()
            ):

                candidate_names = {
                    str(provider_name),
                    str(provider_name).lower(),
                    str(provider_name).replace(
                        "_",
                        "",
                    ).lower(),
                }

                if normalized & candidate_names:
                    return provider

            registry = self.registry
            runtime = self.registry_runtime

        # -----------------------------------------------------
        # SRegistry remains authoritative.
        #
        # Only use interfaces that actually exist.
        # -----------------------------------------------------

        if registry is not None:

            for method_name in (
                "get",
                "lookup",
                "resolve",
                "find",
            ):

                method = getattr(
                    registry,
                    method_name,
                    None,
                )

                if not callable(method):
                    continue

                try:

                    result = method(
                        dependency
                    )

                except Exception:
                    continue

                if result is not None:

                    with self._lock:
                        self.providers[
                            dependency
                        ] = result

                    return result

        # -----------------------------------------------------
        # Runtime registry.
        # -----------------------------------------------------

        if runtime is not None:

            for method_name in (
                "get",
                "lookup",
                "resolve",
                "find",
                "get_provider",
                "resolve_dependency",
            ):

                method = getattr(
                    runtime,
                    method_name,
                    None,
                )

                if not callable(method):
                    continue

                try:

                    result = method(
                        dependency
                    )

                except Exception:
                    continue

                if result is not None:

                    with self._lock:
                        self.providers[
                            dependency
                        ] = result

                    return result

        return None

    # =========================================================
    # DECLARE DEPENDENCY
    # =========================================================

    def declare_dependency(
        self,
        node_name,
        dependency,
    ):

        dependency = str(
            dependency
        )

        with self._lock:

            bucket = self.dependencies.setdefault(
                node_name,
                {},
            )

            if dependency not in bucket:

                bucket[dependency] = {
                    "name": dependency,
                    "state": NODE_WAITING,
                    "provider": None,
                    "provider_type": None,
                    "same_instance": False,
                    "timestamp": time.time(),
                }

                self.stats[
                    "dependencies_discovered"
                ] += 1

        return self.bind_dependency(
            node_name,
            dependency,
        )

    # =========================================================
    # BIND DEPENDENCY
    # =========================================================

    def bind_dependency(
        self,
        node_name,
        dependency,
    ):

        dependency = str(
            dependency
        )

        provider = self.resolve_dependency(
            dependency
        )

        with self._lock:

            bucket = self.dependencies.setdefault(
                node_name,
                {},
            )

            record = bucket.setdefault(
                dependency,
                {
                    "name": dependency,
                    "state": NODE_WAITING,
                    "provider": None,
                    "provider_type": None,
                    "same_instance": False,
                    "timestamp": time.time(),
                },
            )

            if provider is None:

                record["state"] = NODE_WAITING
                record["provider"] = None
                record["provider_type"] = None
                record["same_instance"] = False
                record["timestamp"] = time.time()

                return None

            record["provider"] = provider
            record["provider_type"] = type(
                provider
            ).__name__

            record["state"] = NODE_READY
            record["same_instance"] = True
            record["timestamp"] = time.time()

            self.stats[
                "dependencies_bound"
            ] += 1

        self.connect(
            node_name,
            dependency,
            relation="DEPENDS_ON",
        )

        self.connect(
            node_name,
            type(provider).__name__,
            relation="BOUND_TO",
        )

        return provider

    # =========================================================
    # RESOLVE ALL NODE DEPENDENCIES
    # =========================================================

    def resolve_node_dependencies(
        self,
        node_name,
    ):

        with self._lock:

            dependencies = list(
                self.dependencies.get(
                    node_name,
                    {},
                ).keys()
            )

        resolved = {}

        for dependency in dependencies:

            provider = self.bind_dependency(
                node_name,
                dependency,
            )

            resolved[dependency] = (
                provider is not None
            )

        return resolved

    # =========================================================
    # REGISTER NODE
    # =========================================================

    def register_tool_node(
        self,
        *,
        name,
        module_name,
        path,
        parent,
        capabilities=None,
        dependencies=None,
        role="tool-node",
        version="1.0.0",
        always_on=False,
    ):

        capabilities = sorted(
            set(
                str(value)
                for value in (
                    capabilities or []
                )
            )
        )

        dependencies = sorted(
            set(
                str(value)
                for value in (
                    dependencies or []
                )
            )
        )

        now = time.time()

        with self._lock:

            existing = self.nodes.get(
                name
            )

            node = {
                "name": name,
                "module_name": module_name,
                "path": str(path),
                "parent": str(parent),
                "group": "tools",
                "role": role,
                "version": version,
                "always_on": bool(always_on),
                "update_domain": "tool-runtime",
                "state": (
                    existing.get(
                        "state",
                        NODE_DISCOVERED,
                    )
                    if existing
                    else NODE_DISCOVERED
                ),
                "capabilities": capabilities,
                "dependencies": dependencies,
                "usage_count": (
                    existing.get(
                        "usage_count",
                        0,
                    )
                    if existing
                    else 0
                ),
                "success_count": (
                    existing.get(
                        "success_count",
                        0,
                    )
                    if existing
                    else 0
                ),
                "fail_count": (
                    existing.get(
                        "fail_count",
                        0,
                    )
                    if existing
                    else 0
                ),
                "muscle_score": (
                    existing.get(
                        "muscle_score",
                        1.0,
                    )
                    if existing
                    else 1.0
                ),
                "last_update": now,
            }

            self.nodes[name] = node

            self.lifecycle[name] = node[
                "state"
            ]

            for capability in capabilities:

                bucket = (
                    self.capabilities.setdefault(
                        capability,
                        [],
                    )
                )

                if name not in bucket:
                    bucket.append(name)

            for dependency in dependencies:

                self.dependencies.setdefault(
                    name,
                    {},
                ).setdefault(
                    dependency,
                    {
                        "name": dependency,
                        "state": NODE_WAITING,
                        "provider": None,
                        "provider_type": None,
                        "same_instance": False,
                        "timestamp": now,
                    },
                )

            self._next_sequence()

        # -----------------------------------------------------
        # SRegistry is authoritative for identity.
        # -----------------------------------------------------

        if register_node is not None:

            try:

                register_node(
                    name=name,
                    path=Path(path),
                    parent=Path(parent),
                    group="tools",
                    role=role,
                    update_domain="tool-runtime",
                )

                self.set_state(
                    name,
                    NODE_REGISTERED,
                )

            except Exception as exc:

                logger.debug(
                    "[TOOLS][REGISTRY] "
                    "Registration deferred | %s | %s",
                    name,
                    exc,
                )

        else:

            logger.debug(
                "[TOOLS][REGISTRY] "
                "SRegistry unavailable | %s",
                name,
            )

        self.stats[
            "nodes_registered"
        ] += 1

        return node

    # =========================================================
    # LIFECYCLE
    # =========================================================

    def set_state(
        self,
        name,
        state,
        *,
        error=None,
    ):

        with self._lock:

            node = self.nodes.get(
                name
            )

            if node is None:
                return False

            previous = node.get(
                "state"
            )

            node["state"] = state

            if error is not None:
                node["last_error"] = str(
                    error
                )

            node["last_update"] = time.time()

            self.lifecycle[name] = state

            self._next_sequence()

            if (
                previous != state
                and state == NODE_AVAILABLE
            ):
                self.stats[
                    "nodes_available"
                ] += 1

            elif (
                previous != state
                and state == NODE_ACTIVE
            ):
                self.stats[
                    "nodes_active"
                ] += 1

            elif (
                previous != state
                and state == NODE_READY
            ):
                self.stats[
                    "nodes_ready"
                ] += 1

            elif (
                previous != state
                and state == NODE_FAILED
            ):
                self.stats[
                    "nodes_failed"
                ] += 1

            elif (
                previous != state
                and state == NODE_WAITING
            ):
                self.stats[
                    "nodes_waiting"
                ] += 1

        self._publish(
            {
                "type": "TOOL_NODE_LIFECYCLE",
                "track_id": gen_track_id(),
                "node": name,
                "previous_state": previous,
                "state": state,
                "error": (
                    str(error)
                    if error is not None
                    else None
                ),
                "timestamp": time.time(),
            }
        )

        return True

    # =========================================================
    # CAPABILITY INDEX
    # =========================================================

    def update_capabilities(
        self,
        name,
        capabilities,
    ):

        capabilities = sorted(
            set(
                str(value)
                for value in (
                    capabilities or []
                )
            )
        )

        with self._lock:

            node = self.nodes.get(
                name
            )

            if node is None:
                return False

            old = set(
                node.get(
                    "capabilities",
                    [],
                )
            )

            node["capabilities"] = capabilities

            for capability in old:

                bucket = self.capabilities.get(
                    capability,
                    [],
                )

                if name in bucket:
                    bucket.remove(name)

            for capability in capabilities:

                bucket = (
                    self.capabilities.setdefault(
                        capability,
                        [],
                    )
                )

                if name not in bucket:
                    bucket.append(name)

            added = len(
                set(capabilities) - old
            )

            self.stats[
                "capabilities_discovered"
            ] += added

            node["last_update"] = time.time()

            self._next_sequence()

        return True

    # =========================================================
    # TOPOLOGY
    # =========================================================

    def connect(
        self,
        source,
        target,
        *,
        relation="CONNECTED",
    ):

        source = str(source)
        target = str(target)
        relation = str(relation)

        with self._lock:

            bucket = self.connections.setdefault(
                source,
                [],
            )

            if any(
                item.get("target") == target
                and item.get("relation") == relation
                for item in bucket
            ):
                return False

            bucket.append(
                {
                    "target": target,
                    "relation": relation,
                    "timestamp": time.time(),
                }
            )

            self._next_sequence()

        return True

    # =========================================================
    # CAPABILITY LOOKUP
    # =========================================================

    def find_capable_nodes(
        self,
        capability,
    ):

        with self._lock:

            return list(
                self.capabilities.get(
                    str(capability),
                    [],
                )
            )

    # =========================================================
    # RESULT / LEARNING
    # =========================================================

    def record_result(
        self,
        name,
        *,
        success,
        error=None,
    ):

        with self._lock:

            node = self.nodes.get(
                name
            )

            if node is None:
                return False

            node["usage_count"] = (
                node.get(
                    "usage_count",
                    0,
                )
                + 1
            )

            if success:

                node["success_count"] = (
                    node.get(
                        "success_count",
                        0,
                    )
                    + 1
                )

                node["muscle_score"] = min(
                    1.0,
                    node.get(
                        "muscle_score",
                        1.0,
                    )
                    + 0.05,
                )

            else:

                node["fail_count"] = (
                    node.get(
                        "fail_count",
                        0,
                    )
                    + 1
                )

                node["muscle_score"] = max(
                    0.0,
                    node.get(
                        "muscle_score",
                        1.0,
                    )
                    - 0.10,
                )

                if error is not None:
                    node["last_error"] = str(
                        error
                    )

            node["last_update"] = time.time()

            self._next_sequence()

        return True

    # =========================================================
    # RECOMMENDATION
    # =========================================================

    def recommend(
        self,
        *,
        source,
        action,
        target=None,
        reason=None,
        confidence=0.5,
        priority="normal",
        evidence=None,
        required_capability=None,
    ):

        recommendation = {
            "recommendation_id": (
                f"TREC-{uuid.uuid4().hex[:12]}"
            ),
            "track_id": gen_track_id(),
            "timestamp": time.time(),
            "type": "TOOL_RECOMMENDATION",
            "source": source,
            "action": str(action).upper(),
            "target": target,
            "reason": reason,
            "confidence": float(
                max(
                    0.0,
                    min(
                        1.0,
                        confidence,
                    ),
                )
            ),
            "priority": priority,
            "required_capability": (
                required_capability
            ),
            "evidence": (
                evidence
                if isinstance(
                    evidence,
                    dict,
                )
                else {}
            ),
            "authority": {
                "owner": "QbitDialer",
                "execution": False,
            },
            "execution": {
                "executed": False,
                "allowed_here": False,
                "requires_command_admission": True,
            },
        }

        if required_capability:

            recommendation[
                "candidate_nodes"
            ] = self.find_capable_nodes(
                required_capability
            )

        with self._lock:

            self.recommendations.append(
                recommendation
            )

            self.stats[
                "recommendations"
            ] += 1

            self._next_sequence()

        self._publish(
            recommendation
        )

        return deepcopy_safe(
            recommendation
        )

    # =========================================================
    # REPORT
    # =========================================================

    def report(
        self,
        *,
        source,
        report_type,
        data,
    ):

        report = {
            "report_id": (
                f"TREPORT-{uuid.uuid4().hex[:12]}"
            ),
            "track_id": gen_track_id(),
            "timestamp": time.time(),
            "source": source,
            "type": report_type,
            "data": (
                data
                if isinstance(data, dict)
                else {
                    "value": str(data)
                }
            ),
            "authority": {
                "execution": "QbitDialer",
                "tool_network_executes_commands": False,
            },
        }

        with self._lock:

            self.reports.append(
                report
            )

            self.stats[
                "reports"
            ] += 1

            self._next_sequence()

        self._publish(
            report
        )

        return deepcopy_safe(
            report
        )

    # =========================================================
    # EVENT TRANSPORT
    # =========================================================

    def _publish(
        self,
        packet,
    ):

        bus = self.event_bus

        if bus is None:
            return False

        publish = getattr(
            bus,
            "publish",
            None,
        )

        if not callable(publish):
            return False

        try:

            result = publish(
                "TOOL_NODE",
                payload=packet,
            )

            # -------------------------------------------------
            # Do not create another event loop here.
            # Async EventBus publication belongs to the
            # authoritative runtime.
            # -------------------------------------------------

            if inspect.isawaitable(result):
                return False

            return True

        except TypeError:

            try:

                result = publish(
                    "TOOL_NODE",
                    packet,
                )

                if inspect.isawaitable(result):
                    return False

                return True

            except Exception as exc:

                logger.debug(
                    "[TOOLS][EVENTBUS] "
                    "Publish failed: %s",
                    exc,
                )

        except Exception as exc:

            logger.debug(
                "[TOOLS][EVENTBUS] "
                "Publish failed: %s",
                exc,
            )

        return False

    # =========================================================
    # SNAPSHOT
    # =========================================================

    def snapshot(self):

        with self._lock:

            return {
                "name": self.name,
                "version": self.version,
                "role": self.role,
                "authority": self.authority,
                "track_id": gen_track_id(),
                "sequence": self.sequence,
                "last_update": self.last_update,
                "nodes": deepcopy_safe(
                    self.nodes
                ),
                "connections": deepcopy_safe(
                    self.connections
                ),
                "capabilities": deepcopy_safe(
                    self.capabilities
                ),
                "dependencies": (
                    self._dependency_snapshot()
                ),
                "lifecycle": dict(
                    self.lifecycle
                ),
                "providers": {
                    name: type(value).__name__
                    for name, value
                    in self.providers.items()
                    if value is not None
                },
                "authoritative_bindings": {
                    "EventBus": (
                        self.event_bus is not None
                    ),
                    "TrackSystem": (
                        self.track_system is not None
                    ),
                    "NeuralBridge": (
                        self.neural_bridge is not None
                    ),
                    "QbitDialer": (
                        self.qbit_dialer is not None
                    ),
                    "SRegistry": (
                        self.registry is not None
                    ),
                    "registry_runtime": (
                        self.registry_runtime is not None
                    ),
                    "RuntimeContext": (
                        self.runtime_context is not None
                    ),
                },
                "stats": deepcopy_safe(
                    self.stats
                ),
            }

    # =========================================================
    # DEPENDENCY SNAPSHOT
    # =========================================================

    def _dependency_snapshot(self):

        result = {}

        for node_name, dependencies in (
            self.dependencies.items()
        ):

            result[node_name] = {}

            for dependency, record in (
                dependencies.items()
            ):

                result[node_name][
                    dependency
                ] = {
                    "name": record.get(
                        "name"
                    ),
                    "state": record.get(
                        "state"
                    ),
                    "provider_type": record.get(
                        "provider_type"
                    ),
                    "same_instance": record.get(
                        "same_instance",
                        False,
                    ),
                    "timestamp": record.get(
                        "timestamp"
                    ),
                }

        return result

    # =========================================================
    # ERROR
    # =========================================================

    def record_error(
        self,
        message,
    ):

        with self._lock:

            self.errors.append(
                {
                    "track_id": gen_track_id(),
                    "timestamp": time.time(),
                    "message": str(message),
                }
            )

            self.stats[
                "errors"
            ] += 1

        logger.warning(
            "[TOOLS] %s",
            message,
        )


# =============================================================
# AUTHORITATIVE TOOL NETWORK
# =============================================================

TOOL_NETWORK = ToolNodeNetwork()


# =============================================================
# TOOL ORGAN
#
# Local tool execution wrapper.
#
# It does not own system command authority.
# =============================================================

class ToolOrgan:

    name = "tool_organ"

    def __init__(
        self,
        module_name,
    ):

        self.module_name = str(
            module_name
        )

        self.node_name = (
            f"seed.tools.{self.module_name}"
        )

        self._module = None
        self.instance = None

        self.running = False

        self.failures = 0
        self.usage_count = 0
        self.success_count = 0
        self.fail_count = 0

        self.muscle_score = 1.0

        self.capabilities = []
        self.dependencies = []

        self.tool_name = self.module_name
        self.tool_role = "tool-node"
        self.tool_version = "1.0.0"
        self.always_on = False

        self.entrypoint_name = None
        self.tool_class_name = None

        self.state = NODE_DISCOVERED

        self.last_error = None
        self.last_result = None

        TOOL_NETWORK.register_tool_node(
            name=self.node_name,
            module_name=self.module_name,
            path=THIS_PATH / (
                f"{self.module_name}.py"
            ),
            parent=THIS_PATH,
            capabilities=[],
            dependencies=[],
            role=self.tool_role,
            version=self.tool_version,
            always_on=self.always_on,
        )

    # =========================================================
    # MODULE LOAD
    # =========================================================

    def load(self):

        if self._module is not None:
            return self._module

        self.state = NODE_LOADING

        TOOL_NETWORK.set_state(
            self.node_name,
            NODE_LOADING,
        )

        try:

            self._module = importlib.import_module(
                f"seed.tools.{self.module_name}"
            )

            self.state = NODE_AVAILABLE

            TOOL_NETWORK.set_state(
                self.node_name,
                NODE_AVAILABLE,
            )

            return self._module

        except Exception as exc:

            self.failures += 1
            self.last_error = str(exc)

            self.state = NODE_FAILED

            TOOL_NETWORK.set_state(
                self.node_name,
                NODE_FAILED,
                error=exc,
            )

            TOOL_NETWORK.record_error(
                f"{self.module_name} "
                f"load failed: {exc}"
            )

            return None

    # =========================================================
    # METADATA VALUE
    # =========================================================

    @staticmethod
    def _metadata_value(
        module,
        names,
        default=None,
    ):

        for name in names:

            value = getattr(
                module,
                name,
                None,
            )

            if value is not None:
                return value

        return default

    # =========================================================
    # NORMALIZE COLLECTION
    # =========================================================

    @staticmethod
    def _normalize_collection(value):

        if value is None:
            return []

        if isinstance(
            value,
            str,
        ):
            return [value]

        if isinstance(
            value,
            (list, tuple, set, frozenset),
        ):

            return [
                str(item)
                for item in value
            ]

        return [str(value)]

    # =========================================================
    # CLASS DISCOVERY
    #
    # Important:
    #
    # Only classes DEFINED by this tool module are eligible.
    #
    # Imported BaseTool/EventBus/etc. classes are not
    # accidentally selected as the tool.
    # =========================================================

    def _defined_classes(self):

        module = self._module

        if module is None:
            return []

        classes = []

        for _, attr in inspect.getmembers(
            module,
            inspect.isclass,
        ):

            if getattr(
                attr,
                "__module__",
                None,
            ) != module.__name__:
                continue

            classes.append(attr)

        return classes

    # =========================================================
    # EXPLICIT TOOL CLASS
    # =========================================================

    def _find_explicit_tool_class(self):

        module = self._module

        if module is None:
            return None

        explicit = self._metadata_value(
            module,
            _METADATA_CLASS_NAMES,
        )

        if inspect.isclass(explicit):

            if getattr(
                explicit,
                "__module__",
                None,
            ) == module.__name__:

                return explicit

        if isinstance(
            explicit,
            str,
        ):

            candidate = getattr(
                module,
                explicit,
                None,
            )

            if inspect.isclass(candidate):

                if getattr(
                    candidate,
                    "__module__",
                    None,
                ) == module.__name__:

                    return candidate

        return None

    # =========================================================
    # ENTRYPOINT DISCOVERY
    # =========================================================

    def _find_entrypoint(self):

        module = self._module

        if module is None:
            return None

        explicit = self._metadata_value(
            module,
            _METADATA_ENTRYPOINT_NAMES,
        )

        if callable(explicit):
            return explicit

        if isinstance(
            explicit,
            str,
        ):

            candidate = getattr(
                module,
                explicit,
                None,
            )

            if callable(candidate):
                return candidate

        return None

    # =========================================================
    # TOOL CLASS DISCOVERY
    # =========================================================

    def _find_tool_class(self):

        explicit = (
            self._find_explicit_tool_class()
        )

        if explicit is not None:
            return explicit

        classes = self._defined_classes()

        # -----------------------------------------------------
        # Prefer BaseTool-derived classes.
        # -----------------------------------------------------

        for attr in classes:

            try:

                from .base_tool import BaseTool

                if (
                    attr is not BaseTool
                    and issubclass(
                        attr,
                        BaseTool,
                    )
                ):
                    return attr

            except Exception:
                break

        # -----------------------------------------------------
        # Compatibility fallback:
        # a class defined in the module that exposes the
        # normal tool lifecycle contract.
        # -----------------------------------------------------

        candidates = []

        for attr in classes:

            if attr.__name__.lower() in {
                "tool",
                "toolorgan",
                "toolsorchestrator",
                "toolnodenetwork",
            }:
                continue

            if (
                hasattr(attr, "start")
                or hasattr(attr, "status")
            ):
                candidates.append(attr)

        if len(candidates) == 1:
            return candidates[0]

        # -----------------------------------------------------
        # If several candidates exist, explicit metadata is
        # required rather than guessing.
        # -----------------------------------------------------

        if candidates:

            logger.warning(
                "[TOOLS][ENTRYPOINT] "
                "Multiple tool classes found | node=%s",
                self.node_name,
            )

        return None

    # =========================================================
    # METADATA DISCOVERY
    # =========================================================

    def discover_metadata(self):

        module = self._module

        if module is None:
            return False

        capabilities = set()
        dependencies = set()

        # -----------------------------------------------------
        # Explicit module metadata.
        # -----------------------------------------------------

        for attr_name in (
            *_METADATA_CAPABILITY_NAMES,
        ):

            value = getattr(
                module,
                attr_name,
                None,
            )

            capabilities.update(
                self._normalize_collection(
                    value
                )
            )

        for attr_name in (
            *_METADATA_DEPENDENCY_NAMES,
        ):

            value = getattr(
                module,
                attr_name,
                None,
            )

            dependencies.update(
                self._normalize_collection(
                    value
                )
            )

        tool_name = self._metadata_value(
            module,
            _METADATA_NAME_NAMES,
            self.module_name,
        )

        tool_role = self._metadata_value(
            module,
            _METADATA_ROLE_NAMES,
            "tool-node",
        )

        tool_version = self._metadata_value(
            module,
            _METADATA_VERSION_NAMES,
            "1.0.0",
        )

        always_on = self._metadata_value(
            module,
            _METADATA_ALWAYS_ON_NAMES,
            False,
        )

        self.tool_name = str(
            tool_name
        )

        self.tool_role = str(
            tool_role
        )

        self.tool_version = str(
            tool_version
        )

        self.always_on = bool(
            always_on
        )

        # -----------------------------------------------------
        # Discover actual tool class.
        # -----------------------------------------------------

        tool_class = (
            self._find_tool_class()
        )

        if tool_class is not None:

            self.tool_class_name = (
                tool_class.__name__
            )

            for metadata_name in (
                *_METADATA_CAPABILITY_NAMES,
            ):

                value = getattr(
                    tool_class,
                    metadata_name,
                    None,
                )

                capabilities.update(
                    self._normalize_collection(
                        value
                    )
                )

            for metadata_name in (
                *_METADATA_DEPENDENCY_NAMES,
            ):

                value = getattr(
                    tool_class,
                    metadata_name,
                    None,
                )

                dependencies.update(
                    self._normalize_collection(
                        value
                    )
                )

            # -------------------------------------------------
            # Public class methods become discoverable
            # capabilities, excluding lifecycle/control
            # internals.
            # -------------------------------------------------

            excluded = {
                "start",
                "stop",
                "status",
                "health",
                "run",
                "execute",
                "report",
                "snapshot",
            }

            for method_name, method in inspect.getmembers(
                tool_class,
                predicate=callable,
            ):

                if method_name.startswith("_"):
                    continue

                if method_name in excluded:
                    continue

                capabilities.add(
                    method_name
                )

        # -----------------------------------------------------
        # Module-level entrypoint.
        # -----------------------------------------------------

        entrypoint = (
            self._find_entrypoint()
        )

        if entrypoint is not None:

            self.entrypoint_name = getattr(
                entrypoint,
                "__name__",
                str(entrypoint),
            )

        self.capabilities = sorted(
            capabilities
        )

        self.dependencies = sorted(
            dependencies
        )

        # -----------------------------------------------------
        # Update node metadata.
        # -----------------------------------------------------

        with TOOL_NETWORK._lock:

            node = TOOL_NETWORK.nodes.get(
                self.node_name
            )

            if node is not None:

                node["name"] = self.tool_name
                node["role"] = self.tool_role
                node["version"] = self.tool_version
                node["always_on"] = self.always_on
                node["tool_class"] = (
                    self.tool_class_name
                )
                node["entrypoint"] = (
                    self.entrypoint_name
                )
                node["dependencies"] = list(
                    self.dependencies
                )

        TOOL_NETWORK.update_capabilities(
            self.node_name,
            self.capabilities,
        )

        # -----------------------------------------------------
        # Register dependencies dynamically.
        # -----------------------------------------------------

        for dependency in self.dependencies:

            TOOL_NETWORK.declare_dependency(
                self.node_name,
                dependency,
            )

        return True

    # =========================================================
    # ACTIVATE
    # =========================================================

    def activate(self):

        module = self.load()

        if module is None:
            return None

        if not self.discover_metadata():
            return None

        if self.instance is not None:
            return self.instance

        # -----------------------------------------------------
        # Required dependencies must be available before
        # construction.
        # -----------------------------------------------------

        dependency_state = (
            TOOL_NETWORK.resolve_node_dependencies(
                self.node_name
            )
        )

        unresolved = [
            name
            for name, resolved
            in dependency_state.items()
            if not resolved
        ]

        if unresolved:

            self.state = NODE_WAITING

            TOOL_NETWORK.set_state(
                self.node_name,
                NODE_WAITING,
            )

            logger.info(
                "[TOOLS][DEPENDENCY] "
                "Waiting | node=%s | unresolved=%s",
                self.node_name,
                unresolved,
            )

            return None

        # -----------------------------------------------------
        # Module-level factory takes precedence when explicitly
        # declared.
        # -----------------------------------------------------

        entrypoint = (
            self._find_entrypoint()
        )

        try:

            if entrypoint is not None:

                self.instance = (
                    self._call_entrypoint(
                        entrypoint
                    )
                )

            else:

                tool_class = (
                    self._find_tool_class()
                )

                if tool_class is None:

                    self.state = NODE_DEGRADED

                    TOOL_NETWORK.set_state(
                        self.node_name,
                        NODE_DEGRADED,
                    )

                    return None

                self.instance = (
                    self._construct_with_dynamic_dependencies(
                        tool_class
                    )
                )

            if self.instance is None:

                if self.state != NODE_WAITING:

                    self.state = NODE_DEGRADED

                    TOOL_NETWORK.set_state(
                        self.node_name,
                        NODE_DEGRADED,
                    )

                return None

            if not hasattr(
                self.instance,
                "name",
            ):

                try:
                    self.instance.name = (
                        self.tool_name
                    )
                except Exception:
                    pass

            self.start()

            if not self.running:

                return None

            self.state = NODE_ACTIVE

            TOOL_NETWORK.set_state(
                self.node_name,
                NODE_ACTIVE,
            )

            self._validate_ready()

            logger.info(
                "[TOOLS] Activated node | %s",
                self.node_name,
            )

            return self.instance

        except Exception as exc:

            self.failures += 1
            self.last_error = str(exc)

            self.state = NODE_DEGRADED

            TOOL_NETWORK.set_state(
                self.node_name,
                NODE_DEGRADED,
                error=exc,
            )

            TOOL_NETWORK.record_error(
                f"{self.node_name} "
                f"activation failed: {exc}"
            )

            return None

    # =========================================================
    # ENTRYPOINT CALL
    # =========================================================

    def _call_entrypoint(
        self,
        entrypoint,
    ):

        try:

            signature = inspect.signature(
                entrypoint
            )

        except Exception:

            return entrypoint()

        kwargs = {}

        for parameter in (
            signature.parameters.values()
        ):

            if parameter.kind in (
                parameter.VAR_POSITIONAL,
                parameter.VAR_KEYWORD,
            ):
                continue

            provider = (
                TOOL_NETWORK.resolve_dependency(
                    parameter.name
                )
            )

            if provider is not None:

                kwargs[
                    parameter.name
                ] = provider

                continue

            if (
                parameter.default
                is not inspect.Parameter.empty
            ):
                continue

            TOOL_NETWORK.declare_dependency(
                self.node_name,
                parameter.name,
            )

            self.state = NODE_WAITING

            TOOL_NETWORK.set_state(
                self.node_name,
                NODE_WAITING,
            )

            return None

        result = entrypoint(
            **kwargs
        )

        # -----------------------------------------------------
        # An async factory must be owned by the authoritative
        # runtime. We do not create a second SEED loop.
        # -----------------------------------------------------

        if inspect.isawaitable(result):

            logger.warning(
                "[TOOLS][ENTRYPOINT] "
                "Async factory requires authoritative runtime | %s",
                self.node_name,
            )

            return None

        return result

    # =========================================================
    # DYNAMIC CONSTRUCTOR
    #
    # ToolOrgan does not know which SEED systems a tool needs.
    #
    # It reads the constructor signature and resolves each
    # required dependency against existing providers.
    #
    # It never creates missing providers.
    # =========================================================

    def _construct_with_dynamic_dependencies(
        self,
        tool_class,
    ):

        try:

            signature = inspect.signature(
                tool_class
            )

        except Exception as exc:

            logger.debug(
                "[TOOLS][DEPENDENCY] "
                "Signature unavailable | %s | %s",
                self.node_name,
                exc,
            )

            return None

        kwargs = {}

        for parameter in (
            signature.parameters.values()
        ):

            if parameter.name == "self":
                continue

            if parameter.kind in (
                parameter.VAR_POSITIONAL,
                parameter.VAR_KEYWORD,
            ):
                continue

            provider = (
                TOOL_NETWORK.resolve_dependency(
                    parameter.name
                )
            )

            if provider is not None:

                kwargs[
                    parameter.name
                ] = provider

                continue

            if (
                parameter.default
                is not inspect.Parameter.empty
            ):
                continue

            # -------------------------------------------------
            # Required provider is missing.
            #
            # Do not fabricate it.
            # -------------------------------------------------

            logger.info(
                "[TOOLS][DEPENDENCY] "
                "Waiting | node=%s | dependency=%s",
                self.node_name,
                parameter.name,
            )

            TOOL_NETWORK.declare_dependency(
                self.node_name,
                parameter.name,
            )

            self.state = NODE_WAITING

            TOOL_NETWORK.set_state(
                self.node_name,
                NODE_WAITING,
            )

            return None

        try:

            return tool_class(
                **kwargs
            )

        except Exception as exc:

            logger.debug(
                "[TOOLS][DEPENDENCY] "
                "Construction failed | %s | %s",
                self.node_name,
                exc,
            )

            self.last_error = str(exc)

            return None

    # =========================================================
    # START
    # =========================================================

    def start(self):

        if self.instance is None:
            return False

        if self.running:
            return True

        start_method = getattr(
            self.instance,
            "start",
            None,
        )

        if not callable(
            start_method
        ):
            self.running = True
            return True

        try:

            result = start_method()

            # -------------------------------------------------
            # Do not call asyncio.run().
            #
            # If the tool's start() is async, the authoritative
            # SEED runtime must own its scheduling.
            # -------------------------------------------------

            if inspect.isawaitable(result):

                logger.warning(
                    "[TOOLS][ASYNC] "
                    "Async start requires authoritative runtime | %s",
                    self.node_name,
                )

                return False

            self.running = True

            self.state = NODE_ACTIVE

            TOOL_NETWORK.set_state(
                self.node_name,
                NODE_ACTIVE,
            )

            return True

        except Exception as exc:

            self.failures += 1
            self.last_error = str(exc)

            self.state = NODE_FAILED

            TOOL_NETWORK.set_state(
                self.node_name,
                NODE_FAILED,
                error=exc,
            )

            return False

    # =========================================================
    # READY VALIDATION
    # =========================================================

    def _validate_ready(self):

        with TOOL_NETWORK._lock:

            dependencies = (
                TOOL_NETWORK.dependencies.get(
                    self.node_name,
                    {},
                )
            )

        waiting = [
            name
            for name, record
            in dependencies.items()
            if record.get("state")
            != NODE_READY
        ]

        if waiting:

            self.state = NODE_WAITING

            TOOL_NETWORK.set_state(
                self.node_name,
                NODE_WAITING,
            )

            return False

        self.state = NODE_READY

        TOOL_NETWORK.set_state(
            self.node_name,
            NODE_READY,
        )

        return True

    # =========================================================
    # ADAPTIVE ACTIVATION
    # =========================================================

    def adaptive_activate(
        self,
        urgency=1.0,
    ):

        if (
            self.instance is not None
            and self.running
        ):
            return self.instance

        if (
            self.usage_count > 0
            or urgency > 0.5
            or self.always_on
        ):

            return self.activate()

        return None

    # =========================================================
    # TASK
    #
    # Local tool execution only.
    #
    # This does not submit commands to QbitDialer.
    # =========================================================

    def schedule_task(
        self,
        func_name,
        *args,
        **kwargs,
    ):

        tool = self.activate()

        if tool is None:
            return False

        func = getattr(
            tool,
            func_name,
            None,
        )

        if not callable(func):
            return False

        thread = threading.Thread(
            target=self._run_task,
            args=(
                func,
                args,
                kwargs,
            ),
            daemon=True,
            name=(
                f"Tool-{self.module_name}"
            ),
        )

        thread.start()

        return True

    # =========================================================
    # EXECUTION
    # =========================================================

    def _run_task(
        self,
        func,
        args,
        kwargs,
    ):

        self.usage_count += 1

        try:

            result = func(
                *args,
                **kwargs,
            )

            # -------------------------------------------------
            # Async tool execution is intentionally not
            # converted into a new asyncio.run() loop.
            #
            # The caller must use the authoritative runtime
            # when invoking async tool methods.
            # -------------------------------------------------

            if inspect.isawaitable(result):

                self.report_failure(
                    error=(
                        "Async tool result requires "
                        "authoritative runtime scheduling"
                    )
                )

                return

            self.last_result = (
                deepcopy_safe(result)
            )

            self.report_success()

        except Exception as exc:

            self.report_failure(
                error=exc
            )

    # =========================================================
    # LEARNING
    # =========================================================

    def report_success(self):

        self.success_count += 1

        self.muscle_score = min(
            1.0,
            self.muscle_score + 0.05,
        )

        TOOL_NETWORK.record_result(
            self.node_name,
            success=True,
        )

    # =========================================================
    # FAILURE
    # =========================================================

    def report_failure(
        self,
        error=None,
    ):

        self.fail_count += 1

        self.muscle_score = max(
            0.0,
            self.muscle_score - 0.10,
        )

        self.last_error = (
            str(error)
            if error is not None
            else self.last_error
        )

        TOOL_NETWORK.record_result(
            self.node_name,
            success=False,
            error=error,
        )

    # =========================================================
    # STATUS
    # =========================================================

    def status(self):

        result = {
            "node": self.node_name,
            "name": self.tool_name,
            "module": self.module_name,
            "role": self.tool_role,
            "version": self.tool_version,
            "state": self.state,
            "running": self.running,
            "always_on": self.always_on,
            "failures": self.failures,
            "usage_count": self.usage_count,
            "success_count": self.success_count,
            "fail_count": self.fail_count,
            "muscle_score": self.muscle_score,
            "capabilities": list(
                self.capabilities
            ),
            "dependencies": list(
                self.dependencies
            ),
            "tool_class": self.tool_class_name,
            "entrypoint": self.entrypoint_name,
            "last_error": self.last_error,
        }

        if self.instance is not None:

            status_method = getattr(
                self.instance,
                "status",
                None,
            )

            if callable(status_method):

                try:

                    instance_status = (
                        status_method()
                    )

                    if isinstance(
                        instance_status,
                        dict,
                    ):

                        result[
                            "instance"
                        ] = deepcopy_safe(
                            instance_status
                        )

                except Exception as exc:

                    result[
                        "status_error"
                    ] = str(exc)

        return result


# =============================================================
# TOOLS ORCHESTRATOR
#
# Dynamic discovery + lifecycle coordination.
#
# It does NOT own command authority.
# =============================================================

class ToolsOrchestrator:

    name = "tools_orchestrator"
    version = "4.0.0"
    role = "dynamic-tools-orchestrator"

    def __init__(
        self,
        *,
        auto_monitor=True,
    ):

        self.tools = {}

        self._lock = threading.RLock()

        self.monitor_active = False
        self._monitor_thread = None

        self.auto_monitor = bool(
            auto_monitor
        )

        # -----------------------------------------------------
        # Do initial discovery immediately.
        #
        # This registers the contents of seed/tools without
        # activating every tool.
        # -----------------------------------------------------

        self.discover_tools()

        if self.auto_monitor:
            self.start_monitor()

    # =========================================================
    # RUNTIME FABRIC
    # =========================================================

    def attach_runtime(
        self,
        *,
        event_bus=None,
        track_system=None,
        neural_bridge=None,
        qbit_dialer=None,
        registry=None,
        registry_runtime=None,
        runtime_context=None,
    ):

        TOOL_NETWORK.attach_runtime(
            event_bus=event_bus,
            track_system=track_system,
            neural_bridge=neural_bridge,
            qbit_dialer=qbit_dialer,
            registry=registry,
            registry_runtime=registry_runtime,
            runtime_context=runtime_context,
        )

        # -----------------------------------------------------
        # Re-resolve already discovered nodes.
        # -----------------------------------------------------

        self.refresh_dependencies()

        return self.network_status()

    # =========================================================
    # DYNAMIC DISCOVERY
    #
    # Reads the actual seed/tools directory.
    #
    # No individual tool module names are hardwired.
    # =========================================================

    def discover_tools(self):

        discovered = []

        try:

            modules = pkgutil.iter_modules(
                [str(THIS_PATH)]
            )

        except Exception as exc:

            TOOL_NETWORK.record_error(
                f"Tool discovery failed: {exc}"
            )

            return discovered

        for _, mod_name, is_pkg in modules:

            # -------------------------------------------------
            # Skip private modules/packages.
            # -------------------------------------------------

            if mod_name.startswith("_"):
                continue

            if mod_name == "__init__":
                continue

            # -------------------------------------------------
            # Only Python tool modules are discovered here.
            #
            # Subpackages can be added later through their own
            # package registration path.
            # -------------------------------------------------

            if is_pkg:
                continue

            with self._lock:

                if mod_name in self.tools:
                    continue

                organ = ToolOrgan(
                    mod_name
                )

                self.tools[
                    mod_name
                ] = organ

                discovered.append(
                    mod_name
                )

            TOOL_NETWORK.stats[
                "modules_discovered"
            ] += 1

            TOOL_NETWORK.stats[
                "nodes_discovered"
            ] += 1

            logger.info(
                "[TOOLS][NODE] "
                "Discovered | %s",
                organ.node_name,
            )

        return discovered

    # =========================================================
    # REFRESH DISCOVERY
    #
    # Detect tools added after boot.
    # =========================================================

    def refresh_discovery(self):

        return self.discover_tools()

    # =========================================================
    # ACTIVATE
    # =========================================================

    def activate_tool(
        self,
        name,
        urgency=1.0,
    ):

        with self._lock:

            organ = self.tools.get(
                name
            )

        if organ is None:

            # -------------------------------------------------
            # Allow callers to use a fully qualified node name.
            # -------------------------------------------------

            prefix = "seed.tools."

            if str(name).startswith(prefix):

                short_name = str(
                    name
                )[len(prefix):]

                with self._lock:

                    organ = self.tools.get(
                        short_name
                    )

        if organ is None:
            return None

        return organ.adaptive_activate(
            urgency
        )

    # =========================================================
    # CAPABILITY ROUTING
    # =========================================================

    def find_tools_for_capability(
        self,
        capability,
    ):

        return (
            TOOL_NETWORK.find_capable_nodes(
                capability
            )
        )

    # =========================================================
    # SCHEDULE
    # =========================================================

    def schedule_task(
        self,
        tool_name,
        func_name,
        *args,
        **kwargs,
    ):

        with self._lock:

            organ = self.tools.get(
                tool_name
            )

        if organ is None:
            return False

        return organ.schedule_task(
            func_name,
            *args,
            **kwargs,
        )

    # =========================================================
    # REPORT
    # =========================================================

    def report(
        self,
        report_type,
        data,
    ):

        return TOOL_NETWORK.report(
            source=self.name,
            report_type=report_type,
            data=data,
        )

    # =========================================================
    # RECOMMEND
    # =========================================================

    def recommend(
        self,
        action,
        target=None,
        *,
        reason=None,
        confidence=0.5,
        priority="normal",
        evidence=None,
        required_capability=None,
    ):

        return TOOL_NETWORK.recommend(
            source=self.name,
            action=action,
            target=target,
            reason=reason,
            confidence=confidence,
            priority=priority,
            evidence=evidence,
            required_capability=(
                required_capability
            ),
        )

    # =========================================================
    # DEPENDENCY REFRESH
    # =========================================================

    def refresh_dependencies(self):

        with self._lock:

            organs = list(
                self.tools.values()
            )

        results = {}

        for organ in organs:

            try:

                if organ._module is None:

                    continue

                organ.discover_metadata()

                results[
                    organ.node_name
                ] = (
                    TOOL_NETWORK.resolve_node_dependencies(
                        organ.node_name
                    )
                )

                # -------------------------------------------------
                # A previously WAITING tool can become READY
                # after its providers arrive.
                # -------------------------------------------------

                if (
                    organ.instance is not None
                    and organ.running
                ):

                    organ._validate_ready()

            except Exception as exc:

                TOOL_NETWORK.record_error(
                    f"Dependency refresh failed "
                    f"for {organ.node_name}: {exc}"
                )

        return results

    # =========================================================
    # STATUS
    # =========================================================

    def status_all(self):

        with self._lock:

            return {
                name: organ.status()
                for name, organ
                in self.tools.items()
            }

    # =========================================================
    # NETWORK
    # =========================================================

    def network_status(self):

        return TOOL_NETWORK.snapshot()

    # =========================================================
    # MONITOR START
    # =========================================================

    def start_monitor(self):

        if self.monitor_active:
            return False

        self.monitor_active = True

        self._monitor_thread = (
            threading.Thread(
                target=self._monitor_loop,
                daemon=True,
                name="SEED-Tools-Monitor",
            )
        )

        self._monitor_thread.start()

        return True

    # =========================================================
    # MONITOR LOOP
    #
    # This is ONLY the tools observer.
    #
    # It is NOT the SEED runtime loop.
    # It does NOT own:
    #
    #   QbitQueueLoop
    #   EventBus
    #   command execution
    # =========================================================

    def _monitor_loop(self):

        while self.monitor_active:

            try:

                # -------------------------------------------------
                # Detect modules added to the folder.
                # -------------------------------------------------

                self.refresh_discovery()

                # -------------------------------------------------
                # Refresh existing authoritative providers.
                # -------------------------------------------------

                TOOL_NETWORK._discover_runtime_providers()

                TOOL_NETWORK._connect_authoritative_nodes()

                # -------------------------------------------------
                # Re-read metadata and dependencies.
                # -------------------------------------------------

                self.refresh_dependencies()

                # -------------------------------------------------
                # Explicit ALWAYS_ON tools only.
                #
                # We do NOT activate every discovered tool.
                # -------------------------------------------------

                with self._lock:

                    organs = list(
                        self.tools.values()
                    )

                for organ in organs:

                    if not organ.always_on:
                        continue

                    if organ.running:
                        continue

                    organ.adaptive_activate(
                        urgency=1.0
                    )

                # -------------------------------------------------
                # Persist awareness only.
                #
                # This file is not authoritative state.
                # -------------------------------------------------

                payload = {
                    "timestamp": time.time(),
                    "track_id": gen_track_id(),
                    "tools": self.status_all(),
                    "network": self.network_status(),
                    "authority": {
                        "identity": "SRegistry",
                        "runtime_state": "registry_runtime",
                        "transport": "EventBus",
                        "tracking": "TrackSystem",
                        "neural_bridge": "NeuralBridge",
                        "command_execution": "QbitDialer",
                    },
                }

                try:

                    with STATUS_FILE.open(
                        "w",
                        encoding="utf-8",
                    ) as handle:

                        json.dump(
                            payload,
                            handle,
                            indent=2,
                            default=str,
                        )

                except Exception as exc:

                    TOOL_NETWORK.record_error(
                        "tools_status.json "
                        f"write failed: {exc}"
                    )

            except Exception as exc:

                TOOL_NETWORK.record_error(
                    f"Tool monitor failed: {exc}"
                )

            # -----------------------------------------------------
            # Stop-aware wait.
            #
            # Avoid raw sleep so shutdown is responsive.
            # -----------------------------------------------------

            for _ in range(20):

                if not self.monitor_active:
                    break

                time.sleep(
                    0.1
                )

    # =========================================================
    # STOP
    # =========================================================

    def stop(self):

        self.monitor_active = False

        with self._lock:

            organs = list(
                self.tools.values()
            )

        for organ in organs:

            instance = organ.instance

            if instance is None:
                continue

            stop_method = getattr(
                instance,
                "stop",
                None,
            )

            if not callable(
                stop_method
            ):
                organ.running = False
                continue

            try:

                result = stop_method()

                # -------------------------------------------------
                # Async shutdown must be handled by authoritative
                # runtime. We do not create another loop here.
                # -------------------------------------------------

                if inspect.isawaitable(result):

                    logger.warning(
                        "[TOOLS][ASYNC] "
                        "Async stop requires authoritative runtime | %s",
                        organ.node_name,
                    )

                else:

                    organ.running = False
                    organ.state = NODE_DISABLED

                    TOOL_NETWORK.set_state(
                        organ.node_name,
                        NODE_DISABLED,
                    )

            except Exception as exc:

                TOOL_NETWORK.record_error(
                    f"{organ.node_name} "
                    f"stop failed: {exc}"
                )

        return True


# =============================================================
# AUTHORITATIVE ORCHESTRATOR
# =============================================================

orchestrator = ToolsOrchestrator(
    auto_monitor=True
)


# =============================================================
# PUBLIC API
# =============================================================

__all__ = [
    "orchestrator",
    "ToolOrgan",
    "ToolsOrchestrator",
    "ToolNodeNetwork",
    "TOOL_NETWORK",
    "gen_track_id",
    "deepcopy_safe",

    "NODE_DISCOVERED",
    "NODE_REGISTERED",
    "NODE_LOADING",
    "NODE_AVAILABLE",
    "NODE_ACTIVE",
    "NODE_READY",
    "NODE_DEGRADED",
    "NODE_FAILED",
    "NODE_DISABLED",
    "NODE_WAITING",

    "ACTION_ACTIVATE",
    "ACTION_DEACTIVATE",
    "ACTION_RESTART",
    "ACTION_REBIND",
    "ACTION_REPAIR",
    "ACTION_UPDATE",
    "ACTION_REBUILD",
    "ACTION_RETRY",
    "ACTION_QUARANTINE",
    "ACTION_INVESTIGATE",
    "ACTION_MONITOR",
]
