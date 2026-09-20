# ==========================================================
# FILE: node_registry.py
# PATH: C:\SEED_ROOT\seed\core\neural\node_registry.py
#
# SEED AI OS :: NODE REGISTRY BRIDGE
# "NEURAL network + NODE network = BRIDGE"
#
# VERSION: 1.0.0
# BUILD: SYSTEM-INTEGRATED / DEPENDENCY-AWARE / QBIT-SAFE
#
# ROLE
# ----------------------------------------------------------
# Node Registry Bridge
#
# The Node Registry Bridge is the discovery, inspection,
# registration, dependency-coordination, and neural
# representation layer between SRegistry and the neural
# runtime.
#
# Node Registry Bridge DOES:
#
# - Register modules as Nodes
# - Discover system dependencies
# - Discover modules/packages/nodes
# - Search registered modules and nodes
# - Inspect module/node metadata
# - Read available registry information
# - Publish registry/node information
# - Register unknown/unlisted runtime modules
# - Track dependency lifecycle
# - Request dependency delivery
# - Wait for unavailable dependencies
# - Validate delivered dependencies
# - Build up from available runtime information
# - Preserve Qbit identity + lineage
# - Convert Qbits <-> neural vectors
# - Publish registry/neural telemetry
#
# Node Registry Bridge DOES NOT:
#
# - create SRegistry
# - replace SRegistry
# - create QbitQueueLoop
# - create another runtime loop
# - create another EventBus
# - create another TrackSystem
# - create another Qbit
# - create another QbitDialer
# - execute commands
# - bypass QbitDialer.submit_command()
# - become command authority
#
# AUTHORITY
# ----------------------------------------------------------
# SRegistry        -> authoritative discovery / identity
# registry_runtime -> lifecycle / runtime binding state
# Node_Registry    -> node registry bridge / coordination
# QbitQueueLoop    -> authoritative Qbit transport
# QbitDialer       -> authoritative command plane
# EventBus         -> event transport
# TrackSystem      -> tracking / lineage
# NeuralBridge     -> neural cognition
#
# ==========================================================

import hashlib
import logging
import math
import time
import uuid
from copy import deepcopy
from uuid import uuid4


log = logging.getLogger("NodeRegistry")


# ==========================================================
# LIFECYCLE STATES
# ==========================================================

STATE_INITIALIZING = "INITIALIZING"
STATE_DISCOVERING = "DISCOVERING"
STATE_WAITING = "WAITING"
STATE_LOADING = "LOADING"
STATE_VALIDATING = "VALIDATING"
STATE_AVAILABLE = "AVAILABLE"
STATE_DELIVERED = "DELIVERED"
STATE_BOUND = "BOUND"
STATE_READY = "READY"
STATE_RUNNING = "RUNNING"
STATE_FAILED = "FAILED"
STATE_DISABLED = "DISABLED"


# ==========================================================
# DEPENDENCY STATES
# ==========================================================

DEPENDENCY_REQUIRED = "REQUIRED"
DEPENDENCY_OPTIONAL = "OPTIONAL"


REQUIRED_DEPENDENCIES = (
    "SRegistry",
    "registry_runtime",
)


OPTIONAL_DEPENDENCIES = (
    "QbitQueueLoop",
    "EventBus",
    "TrackSystem",
    "NeuralBridge",
    "ComputeBrain",
    "TransformerBrain",
    "QbitDialer",
    "FATHUDAdapter",
)


# ==========================================================
# HELPERS
# ==========================================================

def gen_track_id(prefix="NODE_REG"):
    return f"{prefix}-{uuid4().hex[:8]}"


# ==========================================================
# INTERNAL SENTINEL
# ==========================================================

_UNSET = object()


# ==========================================================
# NODE REGISTRY BRIDGE
# ==========================================================

class Node_Registry:

    # ======================================================
    # INIT
    # ======================================================

    def __init__(
        self,
        registry=None,
        registry_runtime=None,
        qbit_queue_loop=None,
        event_bus=None,
        track_system=None,
        neural_bridge=None,
        compute_brain=None,
        transformer_brain=None,
        qbit_dialer=None,
        fathud=None,
    ):
        self.bridge_id = (
            f"NODE_REG.{uuid.uuid4()}"
        )

        self.track_id = gen_track_id()

        self.state = STATE_INITIALIZING

        self.created_at = time.time()
        self.started_at = None
        self.last_update = None
        self.last_error = None

        self.discovery_count = 0
        self.registration_count = 0
        self.search_count = 0
        self.publish_count = 0

        # --------------------------------------------------
        # Authoritative runtime references.
        #
        # These are REFERENCES ONLY.
        # --------------------------------------------------

        self.registry = registry
        self.registry_runtime = registry_runtime

        self.qbit_queue_loop = qbit_queue_loop
        self.event_bus = event_bus
        self.track_system = track_system

        self.neural_bridge = neural_bridge
        self.compute_brain = compute_brain
        self.transformer_brain = transformer_brain
        self.qbit_dialer = qbit_dialer
        self.fathud = fathud

        # --------------------------------------------------
        # Node cache.
        #
        # This is a bridge cache, NOT an authoritative
        # replacement for SRegistry.
        # --------------------------------------------------

        self.nodes = {}
        self.modules = {}
        self.services = {}
        self.dependencies = {}

        # --------------------------------------------------
        # Qbit lineage state.
        # --------------------------------------------------

        self.last_qbit_id = None
        self.last_parent_qbit_id = None
        self.last_generation = None

        self._initialize_dependency_records()

        self.state = STATE_DISCOVERING

        log.info(
            "[NodeRegistry] initialized | "
            "bridge_id=%s | track_id=%s",
            self.bridge_id,
            self.track_id,
        )

    # ======================================================
    # DEPENDENCY RECORDS
    # ======================================================

    def _initialize_dependency_records(self):

        for name in REQUIRED_DEPENDENCIES:

            self.dependencies[name] = {
                "name": name,
                "required": True,
                "state": STATE_WAITING,
                "available": False,
                "delivered": False,
                "bound": False,
                "same_instance": None,
                "instance_id": None,
                "type": None,
                "error": None,
                "updated_at": time.time(),
            }

        for name in OPTIONAL_DEPENDENCIES:

            self.dependencies[name] = {
                "name": name,
                "required": False,
                "state": STATE_WAITING,
                "available": False,
                "delivered": False,
                "bound": False,
                "same_instance": None,
                "instance_id": None,
                "type": None,
                "error": None,
                "updated_at": time.time(),
            }

        supplied = {
            "SRegistry": self.registry,
            "registry_runtime": self.registry_runtime,
            "QbitQueueLoop": self.qbit_queue_loop,
            "EventBus": self.event_bus,
            "TrackSystem": self.track_system,
            "NeuralBridge": self.neural_bridge,
            "ComputeBrain": self.compute_brain,
            "TransformerBrain": self.transformer_brain,
            "QbitDialer": self.qbit_dialer,
            "FATHUDAdapter": self.fathud,
        }

        for name, dependency in supplied.items():

            if dependency is not None:

                self._mark_dependency_delivered(
                    name,
                    dependency,
                )

                self._bind_dependency(
                    name,
                    dependency,
                )

    # ======================================================
    # INSTANCE ID
    # ======================================================

    def _instance_id(self, obj):

        if obj is None:
            return None

        explicit = getattr(
            obj,
            "instance_id",
            None,
        )

        if explicit:
            return str(explicit)

        explicit = getattr(
            obj,
            "id",
            None,
        )

        if explicit and isinstance(
            explicit,
            (str, int),
        ):
            return str(explicit)

        return (
            f"{type(obj).__module__}."
            f"{type(obj).__name__}:"
            f"{id(obj)}"
        )

    # ======================================================
    # DEPENDENCY DELIVERY
    # ======================================================

    def deliver_dependency(
        self,
        name,
        dependency,
    ):

        if dependency is None:

            self._dependency_failure(
                name,
                "received_none",
            )

            return False

        if name not in self.dependencies:

            self.dependencies[name] = {
                "name": name,
                "required": False,
                "state": STATE_WAITING,
                "available": False,
                "delivered": False,
                "bound": False,
                "same_instance": None,
                "instance_id": None,
                "type": None,
                "error": None,
                "updated_at": time.time(),
            }

        if not self._validate_dependency(
            name,
            dependency,
        ):
            return False

        self._assign_dependency(
            name,
            dependency,
        )

        self._mark_dependency_delivered(
            name,
            dependency,
        )

        return self._bind_dependency(
            name,
            dependency,
        )

    # ======================================================
    # MARK DELIVERED
    # ======================================================

    def _mark_dependency_delivered(
        self,
        name,
        dependency,
    ):

        record = self.dependencies.get(name)

        if record is None:
            return False

        record.update(
            {
                "state": STATE_DELIVERED,
                "available": True,
                "delivered": True,
                "instance_id": self._instance_id(
                    dependency
                ),
                "type": type(
                    dependency
                ).__name__,
                "updated_at": time.time(),
                "error": None,
            }
        )

        return True

    # ======================================================
    # ASSIGN DEPENDENCY
    # ======================================================

    def _assign_dependency(
        self,
        name,
        dependency,
    ):

        assignments = {
            "SRegistry": "registry",
            "registry_runtime": "registry_runtime",
            "QbitQueueLoop": "qbit_queue_loop",
            "EventBus": "event_bus",
            "TrackSystem": "track_system",
            "NeuralBridge": "neural_bridge",
            "ComputeBrain": "compute_brain",
            "TransformerBrain": "transformer_brain",
            "QbitDialer": "qbit_dialer",
            "FATHUDAdapter": "fathud",
        }

        attribute = assignments.get(name)

        if attribute:
            setattr(
                self,
                attribute,
                dependency,
            )

    # ======================================================
    # DEPENDENCY VALIDATION
    # ======================================================

    def _validate_dependency(
        self,
        name,
        dependency,
    ):

        if dependency is None:

            self._dependency_failure(
                name,
                "dependency_is_none",
            )

            return False

        expected = {
            "SRegistry": (
                "get_node",
                "get_node_by_name",
                "register_node",
                "register_module",
                "get_registry_view",
            ),
            "registry_runtime": (
                "get_registry_view",
                "snapshot_registry",
                "get_status",
                "status",
            ),
            "QbitQueueLoop": (
                "put",
                "enqueue",
                "submit",
                "start",
            ),
            "EventBus": (
                "emit",
                "publish",
                "send",
            ),
            "TrackSystem": (
                "track",
                "record",
                "register",
            ),
            "NeuralBridge": (
                "process_qbit",
                "qbit_to_vector",
                "vector_to_qbit",
            ),
            "ComputeBrain": (
                "process",
                "process_qbit",
                "compute",
            ),
            "TransformerBrain": (
                "process",
                "transform",
                "transform_qbit",
            ),
            "QbitDialer": (
                "submit_command",
                "receive",
                "process",
            ),
            "FATHUDAdapter": (
                "publish",
                "send",
                "emit",
            ),
        }

        methods = expected.get(name)

        if not methods:
            return True

        if any(
            callable(
                getattr(
                    dependency,
                    method,
                    None,
                )
            )
            for method in methods
        ):
            return True

        # SRegistry and registry_runtime are allowed to
        # expose dictionary-backed authoritative state.
        if name in (
            "SRegistry",
            "registry_runtime",
        ):
            if isinstance(
                dependency,
                dict,
            ):
                return True

        self._dependency_failure(
            name,
            "required_interface_missing",
        )

        return False

    # ======================================================
    # BIND DEPENDENCY
    # ======================================================

    def _bind_dependency(
        self,
        name,
        dependency,
    ):

        record = self.dependencies.get(name)

        if record is None:
            return False

        if not self._validate_dependency(
            name,
            dependency,
        ):
            return False

        self.state = STATE_VALIDATING

        # --------------------------------------------------
        # Runtime authorities require exact identity when
        # the registry/runtime exposes an authoritative
        # object reference.
        #
        # Registry records themselves are NOT treated as
        # Python object authorities.
        # --------------------------------------------------

        registered_ref = None

        if name not in (
            "SRegistry",
            "registry_runtime",
        ):
            registered_ref = self._get_runtime_reference(
                name
            )

        if registered_ref is not None:

            same_instance = (
                registered_ref is dependency
            )

            record["same_instance"] = (
                same_instance
            )

            if not same_instance:

                self._dependency_failure(
                    name,
                    "authoritative_instance_mismatch",
                )

                log.error(
                    "[NodeRegistry] dependency "
                    "identity mismatch | dependency=%s",
                    name,
                )

                return False

        else:

            record["same_instance"] = True

        record.update(
            {
                "state": STATE_BOUND,
                "bound": True,
                "available": True,
                "instance_id": self._instance_id(
                    dependency
                ),
                "updated_at": time.time(),
                "error": None,
            }
        )

        return True

    # ======================================================
    # RUNTIME REFERENCE
    # ======================================================

    def _get_runtime_reference(
        self,
        name,
    ):

        runtime = self.registry_runtime

        if runtime is None:
            return None

        mapping = {
            "QbitQueueLoop": (
                "qbit_queue_loop",
                "queue_loop",
            ),
            "EventBus": (
                "event_bus",
            ),
            "TrackSystem": (
                "track_system",
            ),
            "NeuralBridge": (
                "neural_bridge",
            ),
            "ComputeBrain": (
                "compute_brain",
            ),
            "TransformerBrain": (
                "transformer_brain",
            ),
            "QbitDialer": (
                "qbit_dialer",
            ),
            "FATHUDAdapter": (
                "fathud",
                "fathud_adapter",
            ),
        }

        getter = getattr(
            runtime,
            "get_dependency_provider",
            None,
        )

        if callable(getter):
            try:
                provider = getter(
                    name,
                    include_reference=True,
                )
                if isinstance(provider, dict):
                    reference = provider.get("_ref")
                    if reference is None:
                        reference = provider.get("reference")
                    if reference is not None:
                        return reference
            except Exception:
                pass

        for attribute in mapping.get(
            name,
            (),
        ):

            reference = getattr(
                runtime,
                attribute,
                None,
            )

            if reference is not None:
                return reference

        if isinstance(
            runtime,
            dict,
        ):

            for attribute in mapping.get(
                name,
                (),
            ):

                reference = runtime.get(
                    attribute
                )

                if reference is not None:
                    return reference

        return None

    # ======================================================
    # DISCOVER DEPENDENCIES
    # ======================================================

    def discover_dependencies(self):

        self.state = STATE_DISCOVERING

        discovered = 0

        for name in self.dependencies:

            current = (
                self._get_current_dependency(
                    name
                )
            )

            if current is None:
                continue

            if not self._validate_dependency(
                name,
                current,
            ):
                continue

            self._assign_dependency(
                name,
                current,
            )

            self._mark_dependency_delivered(
                name,
                current,
            )

            if self._bind_dependency(
                name,
                current,
            ):
                discovered += 1

        self.discovery_count += 1
        self.last_update = time.time()

        log.info(
            "[NodeRegistry] dependency discovery "
            "complete | discovered=%d | total=%d",
            discovered,
            len(self.dependencies),
        )

        return self.get_dependency_status()

    # ======================================================
    # CURRENT DEPENDENCY
    # ======================================================

    def _get_current_dependency(
        self,
        name,
    ):

        mapping = {
            "SRegistry": self.registry,
            "registry_runtime": self.registry_runtime,
            "QbitQueueLoop": self.qbit_queue_loop,
            "EventBus": self.event_bus,
            "TrackSystem": self.track_system,
            "NeuralBridge": self.neural_bridge,
            "ComputeBrain": self.compute_brain,
            "TransformerBrain": self.transformer_brain,
            "QbitDialer": self.qbit_dialer,
            "FATHUDAdapter": self.fathud,
        }

        current = mapping.get(name)

        if current is not None:
            return current

        return self._get_runtime_reference(
            name
        )

    # ======================================================
    # DEPENDENCY READINESS
    # ======================================================

    def dependencies_ready(self):

        missing = []
        waiting = []
        failed = []

        for name, record in (
            self.dependencies.items()
        ):

            if not record.get(
                "required",
                False,
            ):
                continue

            if record.get(
                "state"
            ) == STATE_FAILED:

                failed.append(name)

            elif not record.get(
                "bound",
                False,
            ):

                waiting.append(name)

            elif not record.get(
                "available",
                False,
            ):

                missing.append(name)

        ready = not (
            missing
            or waiting
            or failed
        )

        if ready:
            self.state = STATE_READY
        else:
            self.state = STATE_WAITING

        return {
            "ready": ready,
            "missing": missing,
            "waiting": waiting,
            "failed": failed,
        }

    # ======================================================
    # WAIT
    # ======================================================

    def wait_for_dependencies(self):

        status = self.dependencies_ready()

        if status["ready"]:
            return status

        self.state = STATE_WAITING

        log.info(
            "[NodeRegistry] waiting for dependencies "
            "| waiting=%s | missing=%s | failed=%s",
            status["waiting"],
            status["missing"],
            status["failed"],
        )

        return status

    # ======================================================
    # REFRESH
    # ======================================================

    def refresh(self):

        self.discover_dependencies()

        self.refresh_nodes()

        return self.get_status()

    # ======================================================
    # REGISTRY VIEW
    # ======================================================

    def _get_registry_view(self):

        registry = self.registry

        if registry is None:
            return None

        method = getattr(
            registry,
            "get_registry_view",
            None,
        )

        if callable(method):

            try:
                return method()

            except Exception:
                log.exception(
                    "[NodeRegistry] registry view failed"
                )

        if isinstance(
            registry,
            dict,
        ):
            return registry

        return None

    # ======================================================
    # NODE DISCOVERY
    # ======================================================

    def refresh_nodes(self):

        self.state = STATE_DISCOVERING

        view = self._get_registry_view()

        if not isinstance(
            view,
            dict,
        ):
            return self.nodes

        kernel = view.get(
            "kernel",
            {},
        )

        if not isinstance(
            kernel,
            dict,
        ):
            kernel = {}

        tree = kernel.get(
            "tree",
            view.get(
                "tree",
                {},
            ),
        )

        if isinstance(
            tree,
            dict,
        ):

            self.nodes = dict(tree)

        modules = kernel.get(
            "modules",
            view.get(
                "modules",
                {},
            ),
        )

        if isinstance(
            modules,
            dict,
        ):

            self.modules = dict(modules)

        services = kernel.get(
            "services",
            view.get(
                "services",
                {},
            ),
        )

        if isinstance(
            services,
            dict,
        ):

            self.services = dict(services)

        self.last_update = time.time()

        return self.nodes

    # ======================================================
    # FIND NODE
    # ======================================================

    def find_node(
        self,
        name_or_path,
    ):

        self.search_count += 1

        registry = self.registry

        if registry is None:
            return None

        method = getattr(
            registry,
            "get_node",
            None,
        )

        if callable(method):

            try:
                result = method(
                    name_or_path
                )

                if result is not None:
                    return deepcopy(
                        result
                    )

            except Exception:
                pass

        method = getattr(
            registry,
            "get_node_by_name",
            None,
        )

        if callable(method):

            try:
                result = method(
                    name_or_path
                )

                if result is not None:
                    return deepcopy(
                        result
                    )

            except Exception:
                pass

        if isinstance(
            self.nodes,
            dict,
        ):

            if name_or_path in self.nodes:
                return deepcopy(
                    self.nodes[
                        name_or_path
                    ]
                )

            for node in self.nodes.values():

                if not isinstance(
                    node,
                    dict,
                ):
                    continue

                if node.get(
                    "name"
                ) == name_or_path:

                    return deepcopy(
                        node
                    )

        return None

    # ======================================================
    # SEARCH
    # ======================================================

    def search(
        self,
        query,
    ):

        self.search_count += 1

        if query is None:
            return []

        query = str(
            query
        ).strip().lower()

        if not query:
            return []

        results = []

        containers = (
            ("nodes", self.nodes),
            ("modules", self.modules),
            ("services", self.services),
        )

        for object_type, container in containers:

            if not isinstance(
                container,
                dict,
            ):
                continue

            for key, value in container.items():

                searchable = [
                    str(key)
                ]

                if isinstance(
                    value,
                    dict,
                ):

                    for field in (
                        "name",
                        "path",
                        "role",
                        "group",
                        "module_type",
                        "service_type",
                    ):

                        if value.get(field) is not None:

                            searchable.append(
                                str(
                                    value[field]
                                )
                            )

                text = " ".join(
                    searchable
                ).lower()

                if query in text:

                    results.append(
                        {
                            "type": object_type,
                            "key": key,
                            "record": deepcopy(
                                value
                            ),
                        }
                    )

        return results

    # ======================================================
    # REGISTER MODULE AS NODE
    # ======================================================

    def register_module_as_node(
        self,
        name,
        path=None,
        parent=None,
        group=None,
        role="module",
        update_domain=None,
        capabilities=None,
        metadata=None,
    ):

        registry = self.registry

        if registry is None:
            return None

        register_node = getattr(
            registry,
            "register_node",
            None,
        )

        if not callable(
            register_node
        ):
            return None

        if path is None:
            path = name

        try:

            result = register_node(
                name=name,
                path=path,
                parent=parent,
                group=group,
                role=role,
                update_domain=update_domain,
                state="ONLINE",
                capabilities=capabilities,
                metadata=metadata,
            )

            self.registration_count += 1

            self.refresh_nodes()

            self._publish_registry_event(
                "NODE_REGISTERED",
                {
                    "name": name,
                    "path": path,
                    "role": role,
                    "capabilities": capabilities,
                },
            )

            return deepcopy(
                result
            )

        except TypeError:

            # Compatibility path for older registry
            # signatures.

            try:

                result = register_node(
                    name,
                    path,
                )

                self.registration_count += 1
                self.refresh_nodes()

                return deepcopy(
                    result
                )

            except Exception as exc:

                self.last_error = str(
                    exc
                )

                log.exception(
                    "[NodeRegistry] node registration failed"
                )

                return None

        except Exception as exc:

            self.last_error = str(
                exc
            )

            log.exception(
                "[NodeRegistry] node registration failed"
            )

            return None

    # ======================================================
    # REGISTER MODULE
    # ======================================================

    def register_module(
        self,
        name,
        module_type="generic",
        ref=None,
        capabilities=None,
        autostart=False,
        path=None,
        state="REGISTERED",
        metadata=None,
    ):

        registry = self.registry

        if registry is None:
            return None

        register_module = getattr(
            registry,
            "register_module",
            None,
        )

        if not callable(
            register_module
        ):
            return None

        try:

            result = register_module(
                name=name,
                module_type=module_type,
                ref=ref,
                capabilities=capabilities,
                autostart=autostart,
                path=path,
                state=state,
                metadata=metadata,
            )

            self.registration_count += 1

            self.refresh_nodes()

            self._publish_registry_event(
                "MODULE_REGISTERED",
                {
                    "name": name,
                    "module_type": module_type,
                    "path": path,
                },
            )

            return deepcopy(
                result
            )

        except Exception as exc:

            self.last_error = str(
                exc
            )

            log.exception(
                "[NodeRegistry] module registration failed"
            )

            return None

    # ======================================================
    # UNKNOWN MODULE REGISTRATION
    # ======================================================

    def register_unknown_module(
        self,
        module_name,
        path=None,
        metadata=None,
        capabilities=None,
    ):

        existing = self.search(
            module_name
        )

        if existing:
            return {
                "status": "already_registered",
                "matches": existing,
            }

        node = self.register_module_as_node(
            name=module_name,
            path=path or module_name,
            role="unknown_module",
            capabilities=capabilities,
            metadata=metadata,
        )

        module = self.register_module(
            name=module_name,
            module_type="discovered",
            path=path,
            state="DISCOVERED",
            capabilities=capabilities,
            metadata=metadata,
        )

        return {
            "status": "registered",
            "node": node,
            "module": module,
        }

    # ======================================================
    # MODULE INFO
    # ======================================================

    def inspect_module(
        self,
        name,
    ):

        registry = self.registry

        if registry is not None:

            method = getattr(
                registry,
                "get_package",
                None,
            )

            if callable(method):

                try:

                    result = method(
                        name
                    )

                    if result is not None:
                        return deepcopy(
                            result
                        )

                except Exception:
                    pass

        matches = self.search(
            name
        )

        if matches:
            return matches[0]

        return None

    # ======================================================
    # CAPABILITY SEARCH
    # ======================================================

    def find_by_capability(
        self,
        capability,
    ):

        registry = self.registry

        if registry is None:
            return []

        method = getattr(
            registry,
            "get_capability_members",
            None,
        )

        if callable(method):

            try:

                result = method(
                    capability
                )

                if result is not None:
                    return deepcopy(
                        result
                    )

            except Exception:
                pass

        method = getattr(
            registry,
            "get_nodes_by_capability",
            None,
        )

        if callable(method):

            try:

                result = method(
                    capability
                )

                if result is not None:
                    return deepcopy(
                        result
                    )

            except Exception:
                pass

        return []

    # ======================================================
    # PUBLISH REGISTRY EVENT
    # ======================================================

    def _publish_registry_event(
        self,
        event_name,
        data=None,
    ):

        event_bus = self.event_bus

        if event_bus is None:
            return False

        event = {
            "event": event_name,
            "source": "NodeRegistry",
            "bridge_id": self.bridge_id,
            "track_id": self.track_id,
            "timestamp": time.time(),
            "data": deepcopy(
                data or {}
            ),
        }

        for method_name in (
            "emit",
            "publish",
            "send",
        ):

            method = getattr(
                event_bus,
                method_name,
                None,
            )

            if not callable(method):
                continue

            try:

                method(event)

                self.publish_count += 1

                return True

            except TypeError:
                continue

            except Exception:

                log.exception(
                    "[NodeRegistry] registry "
                    "event publication failed"
                )

                return False

        return False

    # ======================================================
    # QBIT EXTRACTION
    # ======================================================

    def _qbit_get(
        self,
        qbit,
        key,
        default=None,
    ):

        if qbit is None:
            return default

        if isinstance(
            qbit,
            dict,
        ):

            return qbit.get(
                key,
                default,
            )

        return getattr(
            qbit,
            key,
            default,
        )

    # ======================================================
    # QBIT VECTOR HASH
    # ======================================================

    def _stable_numeric_hash(
        self,
        value,
    ):

        raw = str(
            value
            if value is not None
            else ""
        ).encode(
            "utf-8",
            errors="replace",
        )

        digest = hashlib.sha256(
            raw
        ).hexdigest()

        return int(
            digest[:12],
            16,
        ) % 1000000

    # ======================================================
    # QBIT -> NEURAL VECTOR
    # ======================================================

    def qbit_to_vector(
        self,
        qbit,
    ):

        qbit_id = self._qbit_get(
            qbit,
            "qbit_id",
            self._qbit_get(
                qbit,
                "id",
                "",
            ),
        )

        generation = self._qbit_get(
            qbit,
            "generation",
            0,
        )

        intent = self._qbit_get(
            qbit,
            "intent",
            "",
        )

        metadata = self._qbit_get(
            qbit,
            "metadata",
            {},
        )

        payload = self._qbit_get(
            qbit,
            "payload",
            self._qbit_get(
                qbit,
                "data",
                "",
            ),
        )

        if not isinstance(
            metadata,
            dict,
        ):
            metadata = {}

        return [
            float(
                self._stable_numeric_hash(
                    qbit_id
                )
            ),
            float(
                self._stable_numeric_hash(
                    generation
                )
            ),
            float(
                self._stable_numeric_hash(
                    intent
                )
            ),
            float(
                len(metadata)
            ),
            float(
                self._stable_numeric_hash(
                    payload
                )
            ),
            float(
                len(self.nodes)
            ),
            float(
                len(self.modules)
            ),
            float(
                len(self.services)
            ),
        ]

    # ======================================================
    # VECTOR NORMALIZATION
    # ======================================================

    def _normalize_vector(
        self,
        vector,
    ):

        if not vector:
            return []

        normalized = []

        for value in vector:

            try:
                number = float(
                    value
                )

            except Exception:
                number = 0.0

            if not math.isfinite(
                number
            ):
                number = 0.0

            normalized.append(
                number
            )

        maximum = max(
            (
                abs(x)
                for x in normalized
            ),
            default=1.0,
        )

        if maximum == 0.0:
            maximum = 1.0

        return [
            x / maximum
            for x in normalized
        ]

    # ======================================================
    # VECTOR -> QBIT REPRESENTATION
    # ======================================================

    def vector_to_qbit(
        self,
        vector,
        source_qbit=None,
    ):

        normalized = (
            self._normalize_vector(
                vector
            )
        )

        # --------------------------------------------------
        # Preserve the source Qbit representation when
        # possible. This bridge does NOT manufacture a
        # competing authoritative Qbit object.
        # --------------------------------------------------

        if isinstance(
            source_qbit,
            dict,
        ):

            result = deepcopy(
                source_qbit
            )

        else:

            try:
                result = deepcopy(
                    vars(source_qbit)
                )

            except Exception:

                result = {
                    "value": source_qbit
                }

        source_qbit_id = (
            self._qbit_get(
                source_qbit,
                "qbit_id",
                self._qbit_get(
                    source_qbit,
                    "id",
                    None,
                ),
            )
        )

        source_generation = (
            self._qbit_get(
                source_qbit,
                "generation",
                0,
            )
        )

        try:
            generation = (
                int(
                    source_generation
                )
                + 1
            )

        except Exception:
            generation = 1

        result.setdefault(
            "qbit_id",
            source_qbit_id,
        )

        result[
            "parent_qbit_id"
        ] = source_qbit_id

        result[
            "generation"
        ] = generation

        metadata = result.setdefault(
            "metadata",
            {},
        )

        if not isinstance(
            metadata,
            dict,
        ):

            metadata = {}

            result[
                "metadata"
            ] = metadata

        metadata.update(
            {
                "node_registry_bridge":
                    self.bridge_id,
                "node_registry_track_id":
                    self.track_id,
                "neural_origin":
                    "NODE_REGISTRY",
                "registry_node_count":
                    len(self.nodes),
                "registry_module_count":
                    len(self.modules),
                "registry_service_count":
                    len(self.services),
                "vector_dimension":
                    len(normalized),
                "processed_at":
                    time.time(),
            }
        )

        return result

    # ======================================================
    # PROCESS QBIT THROUGH NEURAL BRIDGE
    # ======================================================

    def process_qbit(
        self,
        qbit,
    ):

        if qbit is None:
            return None

        qbit_id = self._qbit_get(
            qbit,
            "qbit_id",
            self._qbit_get(
                qbit,
                "id",
                None,
            ),
        )

        generation = self._qbit_get(
            qbit,
            "generation",
            0,
        )

        self.last_qbit_id = qbit_id
        self.last_generation = generation

        vector = self.qbit_to_vector(
            qbit
        )

        neural_bridge = (
            self.neural_bridge
        )

        # --------------------------------------------------
        # NeuralBridge is the neural cognition layer.
        # Node Registry does not replace it.
        # --------------------------------------------------

        if neural_bridge is not None:

            method = getattr(
                neural_bridge,
                "process_qbit",
                None,
            )

            if callable(method):

                try:

                    result = method(
                        qbit
                    )

                    if result is not None:

                        self.last_parent_qbit_id = (
                            qbit_id
                        )

                        return result

                except Exception:

                    log.exception(
                        "[NodeRegistry] NeuralBridge "
                        "Qbit processing failed"
                    )

        # --------------------------------------------------
        # No neural processor available.
        #
        # Return a registry-enriched representation
        # without creating a new authoritative Qbit.
        # --------------------------------------------------

        return self.vector_to_qbit(
            vector,
            source_qbit=qbit,
        )

    # ======================================================
    # TRACK NODE
    # ======================================================

    def track_node(
        self,
        node,
    ):

        track_system = (
            self.track_system
        )

        if track_system is None:
            return False

        for method_name in (
            "track",
            "record",
            "register",
        ):

            method = getattr(
                track_system,
                method_name,
                None,
            )

            if not callable(method):
                continue

            try:

                method(
                    node
                )

                return True

            except TypeError:

                try:

                    method(
                        data=node
                    )

                    return True

                except Exception:
                    continue

            except Exception:
                continue

        return False

    # ======================================================
    # HEALTH
    # ======================================================

    def get_health(self):

        dependency_status = (
            self.dependencies_ready()
        )

        return {
            "healthy":
                dependency_status[
                    "ready"
                ],
            "state":
                self.state,
            "dependencies_ready":
                dependency_status[
                    "ready"
                ],
            "node_count":
                len(self.nodes),
            "module_count":
                len(self.modules),
            "service_count":
                len(self.services),
            "discovery_count":
                self.discovery_count,
            "registration_count":
                self.registration_count,
            "search_count":
                self.search_count,
            "publish_count":
                self.publish_count,
            "last_error":
                self.last_error,
        }

    # ======================================================
    # DEPENDENCY STATUS
    # ======================================================

    def get_dependency_status(self):

        return {
            name: deepcopy(
                record
            )
            for name, record
            in self.dependencies.items()
        }

    # ======================================================
    # SINGLE DEPENDENCY
    # ======================================================

    def get_dependency(
        self,
        name,
    ):

        record = self.dependencies.get(
            name
        )

        if record is None:
            return None

        return deepcopy(
            record
        )

    # ======================================================
    # DEPENDENCY FAILURE
    # ======================================================

    def _dependency_failure(
        self,
        name,
        error,
    ):

        record = self.dependencies.setdefault(
            name,
            {
                "name": name,
                "required": False,
                "state": STATE_WAITING,
                "available": False,
                "delivered": False,
                "bound": False,
                "same_instance": None,
                "instance_id": None,
                "type": None,
                "error": None,
                "updated_at": time.time(),
            },
        )

        record.update(
            {
                "state": STATE_FAILED,
                "available": False,
                "bound": False,
                "error": error,
                "updated_at": time.time(),
            }
        )

    # ======================================================
    # FULL STATUS
    # ======================================================

    def get_status(self):

        readiness = (
            self.dependencies_ready()
        )

        return {
            "bridge_id":
                self.bridge_id,
            "track_id":
                self.track_id,
            "state":
                self.state,
            "dependencies":
                {
                    "ready":
                        readiness[
                            "ready"
                        ],
                    "missing":
                        readiness[
                            "missing"
                        ],
                    "waiting":
                        readiness[
                            "waiting"
                        ],
                    "failed":
                        readiness[
                            "failed"
                        ],
                    "records":
                        self.get_dependency_status(),
                },
            "registry":
                {
                    "nodes":
                        len(self.nodes),
                    "modules":
                        len(self.modules),
                    "services":
                        len(self.services),
                },
            "activity":
                {
                    "discoveries":
                        self.discovery_count,
                    "registrations":
                        self.registration_count,
                    "searches":
                        self.search_count,
                    "publications":
                        self.publish_count,
                },
            "qbit":
                {
                    "last_qbit_id":
                        self.last_qbit_id,
                    "last_parent_qbit_id":
                        self.last_parent_qbit_id,
                    "last_generation":
                        self.last_generation,
                },
            "last_error":
                self.last_error,
            "created_at":
                self.created_at,
            "started_at":
                self.started_at,
            "last_update":
                self.last_update,
        }

    # ======================================================
    # START
    # ======================================================

    def start(self):

        if self.state == STATE_RUNNING:
            return self.get_status()

        self.started_at = time.time()

        self.refresh()

        readiness = (
            self.dependencies_ready()
        )

        if not readiness["ready"]:

            self.state = STATE_WAITING

            log.warning(
                "[NodeRegistry] START WAITING "
                "| dependencies=%s",
                readiness,
            )

            return self.get_status()

        self.state = STATE_READY

        log.info(
            "[NodeRegistry] READY "
            "| bridge_id=%s "
            "| nodes=%d "
            "| modules=%d",
            self.bridge_id,
            len(self.nodes),
            len(self.modules),
        )

        return self.get_status()

    # ======================================================
    # STOP
    # ======================================================

    def stop(self):

        self.state = STATE_DISABLED

        log.info(
            "[NodeRegistry] disabled "
            "| bridge_id=%s",
            self.bridge_id,
        )

        return self.get_status()


# ==========================================================
# EXPORTS
# ==========================================================

__all__ = [
    "Node_Registry",
    "STATE_INITIALIZING",
    "STATE_DISCOVERING",
    "STATE_WAITING",
    "STATE_LOADING",
    "STATE_VALIDATING",
    "STATE_AVAILABLE",
    "STATE_DELIVERED",
    "STATE_BOUND",
    "STATE_READY",
    "STATE_RUNNING",
    "STATE_FAILED",
    "STATE_DISABLED",
    "DEPENDENCY_REQUIRED",
    "DEPENDENCY_OPTIONAL",
]