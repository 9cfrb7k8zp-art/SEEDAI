# ==========================================================
# FILE: module_registry.py
# PATH: SEED_ROOT/seed/core/module_registry.py
#
# MODULE: SEED Module Registry v7.0
# BUILD: PASSIVE | TRACK-AWARE | QBIT-AWARE | DIALER-AUTHORITY
#        | SREGISTRY-NODE-AWARE | RUNTIME-REGISTRY-AWARE
# VERSION: 7.0.0
#
# PURPOSE:
# - Maintain SEED module inventory and lifecycle metadata
# - Track module heartbeats
# - Produce health/status telemetry
# - Feed Qbit telemetry toward the existing QbitDialer
# - Preserve TrackID / parent-track relationships
# - Maintain build and distribution requests
# - Provide explicit restart support when commanded externally
# - Register every known module as an SRegistry node
# - Publish live module instances to registry_runtime
# - Preserve authoritative runtime identity
# - Expose module/node/runtime state to NeuralBridge and FATHUD
#
# AUTHORITY MODEL:
# ModuleRegistry -> observes / records / signals / registers
# SRegistry      -> authoritative structural registry
# registry_runtime -> authoritative live-provider/binding state
# Qbit           -> carries system data
# QbitQueueLoop  -> authoritative Qbit transport/execution loop
# QbitDialer     -> processing / command authority
#
# IMPORTANT:
# - ModuleRegistry NEVER creates its own QbitDialer.
# - ModuleRegistry NEVER creates its own Qbit.
# - ModuleRegistry NEVER creates its own QbitQueueLoop.
# - ModuleRegistry NEVER starts a worker thread.
# - ModuleRegistry NEVER autonomously restarts modules.
# - ModuleRegistry NEVER owns boot sequencing.
# - ModuleRegistry NEVER becomes a command authority.
# - ModuleRegistry NEVER replaces an authoritative runtime object.
# - SRegistry registration is structural/discovery state.
# - registry_runtime registration is live-provider state.
# ==========================================================

from __future__ import annotations

import logging
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from seed.core.track_context import (
    TrackContext,
    PermissionRegistry,
)

logger = logging.getLogger("ModuleRegistry")
logger.setLevel(logging.INFO)


# ==========================================================
# OPTIONAL AUTHORITATIVE REGISTRY CONNECTIONS
#
# These imports are intentionally soft.
#
# ModuleRegistry remains usable if SRegistry or
# registry_runtime is temporarily unavailable during early boot.
#
# Once the authoritative runtime exists, bind_runtime()
# reconnects the registry without creating replacements.
# ==========================================================

try:
    from SRegistry import (
        register_node,
    )
except Exception:
    register_node = None


try:
    from SRegistry.registry_runtime import (
        register_dependency_provider,
        update_dependency_provider_state,
        get_dependency_provider,
    )
except Exception:
    register_dependency_provider = None
    update_dependency_provider_state = None
    get_dependency_provider = None


# ==========================================================
# MODULE REGISTRY
# ==========================================================

class ModuleRegistry:

    VERSION = "7.0.0"

    DEFAULT_HEARTBEAT_TIMEOUT = 10
    DEFAULT_DEVICE_FEEDBACK_TIMEOUT = 5
    DEFAULT_PREDICTIVE_THRESHOLD = 0.8

    # ------------------------------------------------------
    # Constructor
    # ------------------------------------------------------

    def __init__(
        self,
        device_manager=None,
        qbit=None,
        dialer=None,
        event_bus=None,
        track=None,
        seedcore=None,
        passive=True,
        predictive_enabled=False,
        predictive_threshold=None,

        # --------------------------------------------------
        # Runtime authorities.
        #
        # These are late-bound because ModuleRegistry can
        # exist before the authoritative runtime is complete.
        # --------------------------------------------------

        queue_loop=None,
        track_system=None,
        track_context=None,
        registry=None,
        registry_runtime=None,
        node_registry=None,
        nodes=None,
        kernel_bus=None,
        neural_bridge=None,
        fathud=None,
    ):

        # --------------------------------------------------
        # Core state
        # --------------------------------------------------

        self._modules: Dict[str, Dict[str, Any]] = {}

        # RLock allows explicit operations to safely inspect
        # registry state without creating lock recursion hazards.
        self._lock = threading.RLock()

        # --------------------------------------------------
        # Existing runtime dependencies
        # --------------------------------------------------

        self.device_manager = device_manager

        self.qbit = qbit
        self.dialer = dialer
        self.event_bus = event_bus

        self.track = track
        self.seedcore = seedcore

        # --------------------------------------------------
        # Authoritative runtime connections
        # --------------------------------------------------

        self.queue_loop = queue_loop
        self.track_system = track_system
        self.track_context = track_context

        self.registry = registry
        self.registry_runtime = registry_runtime
        self.node_registry = node_registry
        self.nodes = nodes

        self.kernel_bus = kernel_bus
        self.neural_bridge = neural_bridge
        self.fathud = fathud

        # --------------------------------------------------
        # Database connectivity remains observational/storage-only.
        # --------------------------------------------------
        try:
            from seed.core.database_connector import SEEDDatabaseConnector
            self.database = SEEDDatabaseConnector()
        except Exception:
            self.database = None

        # --------------------------------------------------
        # Registry identity
        # --------------------------------------------------

        self.registry_name = "ModuleRegistry"
        self.registry_role = "module-registry"
        self.registry_group = "kernel"
        self.registry_update_domain = "seed-runtime"

        self._registry_node_registered = False
        self._runtime_provider_registered = False
        self._runtime_binding_generation = 0

        self.passive = bool(passive)

        self._device_feedback_timeout = (
            self.DEFAULT_DEVICE_FEEDBACK_TIMEOUT
        )

        self._build_queue: List[Dict[str, Any]] = []
        self._distribution_log: List[Dict[str, Any]] = []

        # Passive skill/integration catalog. Entries are paths and
        # capability metadata only; modules are loaded lazily by the
        # authoritative command/skill plane when explicitly bound.
        self.skill_catalog: Dict[str, Dict[str, Any]] = {}

        self._predictive_threshold = (
            self.DEFAULT_PREDICTIVE_THRESHOLD
            if predictive_threshold is None
            else float(predictive_threshold)
        )

        self.predictive_enabled = bool(
            predictive_enabled
        )

        # Lifecycle state is observational.
        self._started = False
        self._shutdown = False

        # --------------------------------------------------
        # Register the registry itself as a structural node.
        #
        # This does NOT require a runtime worker and does not
        # create a second authority.
        # --------------------------------------------------

        self._register_registry_node()

        # --------------------------------------------------
        # Register the registry itself as a live provider
        # when registry_runtime is available.
        # --------------------------------------------------

        self._register_runtime_provider()

        # --------------------------------------------------
        # Resolve NodeRegistry if the authoritative registry
        # already exists during construction.
        #
        # Late binding remains supported through bind_runtime().
        # --------------------------------------------------

        self._resolve_authoritative_node_registry()

        logger.info(
            "[ModuleRegistry] Initialized | version=%s | "
            "passive=%s | qbit=%s | dialer=%s | "
            "queue_loop=%s | track_system=%s | "
            "registry=%s | registry_runtime=%s",
            self.VERSION,
            self.passive,
            type(self.qbit).__name__
            if self.qbit
            else None,
            type(self.dialer).__name__
            if self.dialer
            else None,
            type(self.queue_loop).__name__
            if self.queue_loop
            else None,
            type(self.track_system).__name__
            if self.track_system
            else None,
            type(self.registry).__name__
            if self.registry
            else None,
            type(self.registry_runtime).__name__
            if self.registry_runtime
            else None,
        )

    # ======================================================
    # LIFECYCLE
    # ======================================================

    def start(self):

        with self._lock:
            if self._shutdown:
                logger.warning(
                    "[ModuleRegistry] Start rejected after shutdown"
                )
                return False

            self._started = True

        self._publish_runtime_state(
            state="ONLINE"
        )

        # --------------------------------------------------
        # Persistent SEED network presence.
        # Database records state only; QbitDialer remains
        # command authority and QueueLoop remains execution
        # authority.
        # --------------------------------------------------
        if self.database is not None and self.database.enabled:
            try:
                self.database.start_network_session(
                    metadata={
                        "registry": self.registry_name,
                        "registry_version": self.VERSION,
                    }
                )
            except Exception as exc:
                logger.warning(
                    "[ModuleRegistry] Network session start failed: %s",
                    exc,
                )

        logger.info("[ModuleRegistry] ONLINE")
        return True

    def stop(self):

        with self._lock:
            self._started = False

        self._publish_runtime_state(
            state="OFFLINE"
        )

        if self.database is not None and self.database.enabled:
            try:
                self.database.stop_network_session()
            except Exception as exc:
                logger.warning(
                    "[ModuleRegistry] Network session stop failed: %s",
                    exc,
                )

        logger.info("[ModuleRegistry] OFFLINE")
        return True

    def shutdown(self):

        with self._lock:
            self._shutdown = True
            self._started = False

        self._publish_runtime_state(
            state="SHUTDOWN"
        )

        if self.database is not None and self.database.enabled:
            try:
                self.database.stop_network_session()
            except Exception as exc:
                logger.warning(
                    "[ModuleRegistry] Network session shutdown failed: %s",
                    exc,
                )

        logger.info(
            "[ModuleRegistry] Shutdown complete"
        )

        return True

    @property
    def started(self) -> bool:
        with self._lock:
            return (
                self._started
                and not self._shutdown
            )

    # ======================================================
    # AUTHORITATIVE RUNTIME BINDING
    # ======================================================

    def bind_runtime(
        self,
        *,
        qbit=None,
        dialer=None,
        queue_loop=None,
        event_bus=None,
        track_system=None,
        track=None,
        track_context=None,
        seedcore=None,
        registry=None,
        registry_runtime=None,
        node_registry=None,
        nodes=None,
        kernel_bus=None,
        neural_bridge=None,
        fathud=None,
    ):

        changed = []

        def preserve(
            attribute,
            incoming,
        ):
            if incoming is None:
                return

            existing = getattr(
                self,
                attribute,
                None,
            )

            if (
                existing is not None
                and existing is not incoming
            ):
                logger.warning(
                    "[ModuleRegistry] Authority replacement "
                    "rejected | attr=%s | existing_id=%s | "
                    "incoming_id=%s",
                    attribute,
                    id(existing),
                    id(incoming),
                )
                return

            if existing is None:
                setattr(
                    self,
                    attribute,
                    incoming,
                )
                changed.append(attribute)

        # --------------------------------------------------
        # Resolve the authoritative structural NodeRegistry.
        #
        # This does not create a registry.
        # It binds the existing SRegistry/runtime authority.
        # --------------------------------------------------

        self._resolve_authoritative_node_registry()

        # --------------------------------------------------
        # Re-attempt authoritative registry registration
        # after late binding.
        # --------------------------------------------------

        self._register_registry_node()
        self._register_runtime_provider()

        with self._lock:
            preserve("qbit", qbit)
            preserve("dialer", dialer)
            preserve("queue_loop", queue_loop)
            preserve("event_bus", event_bus)

            preserve(
                "track_system",
                track_system,
            )

            preserve(
                "track",
                track,
            )

            preserve(
                "track_context",
                track_context,
            )

            preserve(
                "seedcore",
                seedcore,
            )

            preserve(
                "registry",
                registry,
            )

            preserve(
                "registry_runtime",
                registry_runtime,
            )

            preserve(
                "node_registry",
                node_registry,
            )

            preserve(
                "nodes",
                nodes,
            )

            preserve(
                "kernel_bus",
                kernel_bus,
            )

            preserve(
                "neural_bridge",
                neural_bridge,
            )

            preserve(
                "fathud",
                fathud,
            )

            if changed:
                self._runtime_binding_generation += 1

        # --------------------------------------------------
        # Re-attempt authoritative registry registration
        # after late binding.
        # --------------------------------------------------

        self._register_registry_node()
        self._register_runtime_provider()

        # --------------------------------------------------
        # Synchronize all existing module nodes/providers.
        # --------------------------------------------------

        self._synchronize_registered_modules()

        logger.info(
            "[ModuleRegistry] Runtime bound | "
            "changed=%s | qbit=%s | dialer=%s | "
            "queue_loop=%s | event_bus=%s | "
            "track_system=%s | registry=%s | "
            "registry_runtime=%s | node_registry=%s | "
            "neural_bridge=%s",
            changed,
            type(self.qbit).__name__
            if self.qbit
            else None,
            type(self.dialer).__name__
            if self.dialer
            else None,
            type(self.queue_loop).__name__
            if self.queue_loop
            else None,
            type(self.event_bus).__name__
            if self.event_bus
            else None,
            type(self.track_system).__name__
            if self.track_system
            else None,
            type(self.registry).__name__
            if self.registry
            else None,
            type(self.registry_runtime).__name__
            if self.registry_runtime
            else None,
            type(self.node_registry).__name__
            if self.node_registry
            else None,
            type(self.neural_bridge).__name__
            if self.neural_bridge
            else None,
        )

        return self.runtime_status()

    # ======================================================
    # AUTHORITATIVE NODE REGISTRY RESOLUTION
    #
    # SRegistry is the authoritative structural registry.
    #
    # A separate NodeRegistry object is used only when the
    # authoritative runtime has explicitly registered one.
    #
    # NEVER CREATE A SECOND REGISTRY.
    # ======================================================

    def _resolve_authoritative_node_registry(self):

        # --------------------------------------------------
        # Already bound.
        # --------------------------------------------------

        if self.node_registry is not None:

            if (
                self.nodes is None
            ):

                self.nodes = (
                    self.node_registry
                )

            return self.node_registry

        # --------------------------------------------------
        # Explicit nodes alias.
        # --------------------------------------------------

        if self.nodes is not None:

            self.node_registry = (
                self.nodes
            )

            return self.node_registry

        # --------------------------------------------------
        # First: registry_runtime.
        #
        # If a dedicated NodeRegistry provider exists,
        # use its LIVE reference.
        #
        # Never use a copied snapshot.
        # --------------------------------------------------

        runtime = (
            self.registry_runtime
        )

        if runtime is not None:

            try:

                getter = getattr(
                    runtime,
                    "get_dependency_provider",
                    None,
                )

                if callable(
                    getter
                ):

                    provider = getter(
                        "NodeRegistry",
                        include_reference=True,
                    )

                    if (
                        isinstance(
                            provider,
                            dict,
                        )
                    ):

                        reference = (
                            provider.get(
                                "_ref"
                            )
                        )

                        if reference is None:

                            reference = (
                                provider.get(
                                    "reference"
                                )
                            )

                        if reference is not None:

                            self.node_registry = (
                                reference
                            )

                            self.nodes = (
                                reference
                            )

                            logger.info(
                                "[ModuleRegistry] "
                                "Authoritative NodeRegistry "
                                "resolved from registry_runtime | "
                                "type=%s | identity=%s",
                                type(
                                    reference
                                ).__name__,
                                id(reference),
                            )

                            return reference

            except Exception as exc:

                logger.debug(
                    "[ModuleRegistry] NodeRegistry "
                    "runtime-provider resolution deferred | "
                    "error=%s",
                    exc,
                )

        # --------------------------------------------------
        # Second: SRegistry itself.
        #
        # The supplied SRegistry implementation is the
        # authoritative structural node registry when no
        # separate NodeRegistry provider exists.
        #
        # It exposes register_node/get_node/etc.
        # --------------------------------------------------

        registry = (
            self.registry
        )

        if registry is not None:

            structural_methods = (
                "register_node",
                "get_node",
                "get_node_by_name",
                "get_registry_view",
                "snapshot_registry",
            )

            if any(
                callable(
                    getattr(
                        registry,
                        method_name,
                        None,
                    )
                )
                for method_name
                in structural_methods
            ):

                self.node_registry = (
                    registry
                )

                self.nodes = (
                    registry
                )

                logger.info(
                    "[ModuleRegistry] "
                    "SRegistry bound as authoritative "
                    "structural NodeRegistry | "
                    "type=%s | identity=%s",
                    type(
                        registry
                    ).__name__,
                    id(registry),
                )

                return registry

        # --------------------------------------------------
        # Third: imported SRegistry register_node API.
        #
        # If SRegistry is available through the module-level
        # registration API but the registry object was not
        # injected yet, remain deferred rather than creating
        # a replacement object.
        # --------------------------------------------------

        if callable(
            register_node
        ):

            logger.debug(
                "[ModuleRegistry] SRegistry node API "
                "available but authoritative registry "
                "object is not yet bound"
            )

        return None

    # ======================================================
    # REGISTRY NODE REGISTRATION
    # ======================================================

    def _register_registry_node(self):

        if not callable(register_node):
            logger.debug(
                "[ModuleRegistry] SRegistry register_node "
                "not available yet"
            )
            return False

        try:
            module_path = (
                Path(__file__).resolve()
            )

            result = register_node(
                name="ModuleRegistry",
                path=module_path,
                parent=(
                    Path(
                        module_path.parent
                    ).parent
                ),
                group=self.registry_group,
                role=self.registry_role,
                update_domain=self.registry_update_domain,
                state=(
                    "ONLINE"
                    if self.started
                    else "DISCOVERED"
                ),
                capabilities=[
                    "module_inventory",
                    "module_health",
                    "module_heartbeat",
                    "module_telemetry",
                    "module_build_requests",
                    "module_distribution",
                    "module_restart_request",
                    "runtime_node_registration",
                ],
                metadata={
                    "version": self.VERSION,
                    "passive": self.passive,
                    "authority": "ModuleRegistry",
                    "command_authority": "QbitDialer",
                },
            )

            self._registry_node_registered = True

            logger.info(
                "[ModuleRegistry] SRegistry node registered | "
                "result=%s",
                result,
            )

            return True

        except Exception as exc:
            logger.warning(
                "[ModuleRegistry] SRegistry node registration "
                "deferred: %s",
                exc,
            )

            return False

    # ======================================================
    # LIVE REGISTRY-RUNTIME PROVIDER
    # ======================================================

    def _register_runtime_provider(self):

        if not callable(
            register_dependency_provider
        ):
            logger.debug(
                "[ModuleRegistry] registry_runtime provider "
                "API not available yet"
            )
            return False

        try:
            register_dependency_provider(
                name="ModuleRegistry",
                ref=self,
                state=(
                    "ONLINE"
                    if self.started
                    else "REGISTERED"
                ),
                capabilities=[
                    "module_inventory",
                    "module_health",
                    "module_heartbeat",
                    "module_telemetry",
                    "module_build_requests",
                    "module_distribution",
                    "module_restart_request",
                    "runtime_node_registration",
                ],
                metadata={
                    "version": self.VERSION,
                    "authority": "ModuleRegistry",
                    "passive": self.passive,
                    "provider_type": "module_registry",
                    "structural_registry": "SRegistry",
                    "live_registry": "registry_runtime",
                },
                instance_id=self._instance_id(),
                authoritative=True,
                source="ModuleRegistry",
            )

            self._runtime_provider_registered = True

            logger.info(
                "[ModuleRegistry] registry_runtime provider "
                "registered | instance=%s",
                self._instance_id(),
            )

            return True

        except Exception as exc:
            logger.warning(
                "[ModuleRegistry] registry_runtime provider "
                "registration deferred: %s",
                exc,
            )

            return False

    # ======================================================
    # RUNTIME PROVIDER STATE
    # ======================================================

    def _publish_runtime_state(
        self,
        state: str,
    ):
        if not callable(
            update_dependency_provider_state
        ):
            return False

        try:
            update_dependency_provider_state(
                "ModuleRegistry",
                state,
                metadata={
                    "version": self.VERSION,
                    "started": self.started,
                    "module_count": len(
                        self._modules
                    ),
                    "binding_generation": (
                        self._runtime_binding_generation
                    ),
                },
                ref=self,
                instance_id=self._instance_id(),
            )

            return True

        except Exception as exc:
            logger.debug(
                "[ModuleRegistry] Runtime provider state "
                "update deferred: %s",
                exc,
            )

            return False

    # ======================================================
    # MODULE NODE REGISTRATION
    # ======================================================

    def _register_module_node(
        self,
        name: str,
        data: Dict[str, Any],
    ):

        if not callable(register_node):
            return False

        module_path = self._resolve_module_path(
            name,
            data,
        )

        parent_path = (
            self._resolve_parent_path(
                data
            )
        )

        inventory = data.get(
            "inventory",
            {},
        )

        if not isinstance(
            inventory,
            dict,
        ):
            inventory = {}

        capabilities = [
            "module_health",
            "module_heartbeat",
            "module_telemetry",
        ]

        if data.get(
            "restartable",
            False,
        ):
            capabilities.append(
                "restart_request"
            )

        try:
            result = register_node(
                name=name,
                path=module_path,
                parent=parent_path,
                group=(
                    inventory.get(
                        "group",
                        "modules",
                    )
                ),
                role=(
                    inventory.get(
                        "role",
                        "module",
                    )
                ),
                update_domain=(
                    inventory.get(
                        "update_domain",
                        "module-domain",
                    )
                ),
                state=self._node_state(
                    data
                ),
                capabilities=capabilities,
                metadata={
                    "module_registry": (
                        self.registry_name
                    ),
                    "module": name,
                    "track_id": data.get(
                        "track_id"
                    ),
                    "parent_track": data.get(
                        "parent_track"
                    ),
                    "priority": data.get(
                        "priority"
                    ),
                    "critical": data.get(
                        "critical",
                        False,
                    ),
                    "restartable": data.get(
                        "restartable",
                        False,
                    ),
                    "heartbeat_timeout": data.get(
                        "timeout"
                    ),
                    "inventory": dict(
                        inventory
                    ),
                },
            )

            logger.info(
                "[ModuleRegistry][NODE] %s registered | "
                "path=%s | state=%s",
                name,
                module_path,
                self._node_state(data),
            )

            return result

        except Exception as exc:
            logger.warning(
                "[ModuleRegistry][NODE] %s registration "
                "deferred: %s",
                name,
                exc,
            )

            return False

    # ======================================================
    # MODULE LIVE PROVIDER REGISTRATION
    # ======================================================

    def _register_module_runtime_provider(
        self,
        name: str,
        data: Dict[str, Any],
    ):

        if not callable(
            register_dependency_provider
        ):
            return False

        try:
            provider_name = (
                f"module:{name}"
            )

            register_dependency_provider(
                name=provider_name,
                ref=self,
                state=self._runtime_provider_state(
                    data
                ),
                capabilities=[
                    "module_health",
                    "module_heartbeat",
                    "module_telemetry",
                ],
                metadata={
                    "module": name,
                    "track_id": data.get(
                        "track_id"
                    ),
                    "parent_track": data.get(
                        "parent_track"
                    ),
                    "priority": data.get(
                        "priority"
                    ),
                    "critical": data.get(
                        "critical",
                        False,
                    ),
                    "restartable": data.get(
                        "restartable",
                        False,
                    ),
                    "status": data.get(
                        "status"
                    ),
                    "last_heartbeat": data.get(
                        "last_heartbeat"
                    ),
                    "inventory": dict(
                        data.get(
                            "inventory",
                            {},
                        )
                    ),
                    "provider_type": "module",
                    "registry": "ModuleRegistry",
                },
                instance_id=self._module_instance_id(
                    name,
                    data,
                ),
                authoritative=True,
                source="ModuleRegistry",
            )

            return True

        except Exception as exc:
            logger.debug(
                "[ModuleRegistry][RUNTIME NODE] "
                "%s provider registration deferred: %s",
                name,
                exc,
            )

            return False

    # ======================================================
    # MODULE NODE SYNCHRONIZATION
    # ======================================================

    def _synchronize_module_node(
        self,
        name: str,
        data: Dict[str, Any],
    ):
        node_registered = (
            self._register_module_node(
                name,
                data,
            )
        )

        provider_registered = (
            self._register_module_runtime_provider(
                name,
                data,
            )
        )

        return (
            node_registered
            or provider_registered
        )

    def _synchronize_registered_modules(self):
        with self._lock:
            modules = [
                (
                    name,
                    self._copy_module(data),
                )
                for name, data
                in self._modules.items()
            ]

        for name, data in modules:
            try:
                self._synchronize_module_node(
                    name,
                    data,
                )
            except Exception:
                logger.exception(
                    "[ModuleRegistry] Module runtime "
                    "synchronization failed | module=%s",
                    name,
                )

    # ======================================================
    # PASSIVE SKILL / INTEGRATION DISCOVERY
    # ======================================================

    def refresh_skill_catalog(self, roots=None, max_files=500):
        """Catalog skill/integration files as runtime nodes without importing them."""
        default_roots = [
            Path(__file__).resolve().parents[1] / "skills",
            Path(__file__).resolve().parent / "integration",
        ]
        roots = list(roots or default_roots)
        discovered = 0
        skipped = {"__pycache__", "inbox", "outbox", "_archive", "test_skills"}

        for root in roots:
            root = Path(root)
            if not root.exists():
                continue
            for path in root.rglob("*.py"):
                if discovered >= max(1, int(max_files)):
                    break
                if any(part in skipped for part in path.parts):
                    continue
                if path.name.startswith("_"):
                    continue
                key = f"skill:{path.relative_to(root).with_suffix('')}"
                data = {
                    "name": key,
                    "status": "discovered",
                    "track_id": None,
                    "parent_track": None,
                    "priority": "BACKGROUND",
                    "restartable": False,
                    "critical": False,
                    "inventory": {
                        "type": "skill" if "skills" in root.parts else "integration",
                        "path": str(path),
                        "lazy": True,
                    },
                }
                with self._lock:
                    self.skill_catalog[key] = dict(data)
                    self._modules[key] = dict(data)
                self._synchronize_module_node(key, data)
                discovered += 1

        logger.info(
            "[ModuleRegistry] Skill/integration catalog refreshed | discovered=%d",
            discovered,
        )
        return dict(self.skill_catalog)

    # ======================================================
    # QBIT / DIALER BINDING
    # ======================================================

    def bind_qbit(
        self,
        qbit,
        dialer=None,
    ):

        with self._lock:
            if (
                self.qbit is not None
                and self.qbit is not qbit
            ):
                logger.warning(
                    "[ModuleRegistry] Qbit replacement "
                    "rejected | existing_id=%s | "
                    "incoming_id=%s",
                    id(self.qbit),
                    id(qbit),
                )
            else:
                self.qbit = qbit

            if dialer is not None:
                if (
                    self.dialer is not None
                    and self.dialer is not dialer
                ):
                    logger.warning(
                        "[ModuleRegistry] Dialer replacement "
                        "rejected | existing_id=%s | "
                        "incoming_id=%s",
                        id(self.dialer),
                        id(dialer),
                    )
                else:
                    self.dialer = dialer

        logger.info(
            "[ModuleRegistry] Qbit bound | qbit=%s | dialer=%s",
            type(self.qbit).__name__
            if self.qbit
            else None,
            type(self.dialer).__name__
            if self.dialer
            else None,
        )

        return True

    def bind_dialer(
        self,
        dialer,
    ):

        with self._lock:
            if (
                self.dialer is not None
                and self.dialer is not dialer
            ):
                logger.warning(
                    "[ModuleRegistry] QbitDialer replacement "
                    "rejected | existing_id=%s | "
                    "incoming_id=%s",
                    id(self.dialer),
                    id(dialer),
                )
                return False

            self.dialer = dialer

        logger.info(
            "[ModuleRegistry] QbitDialer bound | dialer=%s",
            type(dialer).__name__
            if dialer
            else None,
        )

        return True

    def bind_queue_loop(
        self,
        queue_loop,
    ):
        if queue_loop is None:
            return False

        with self._lock:
            if (
                self.queue_loop is not None
                and self.queue_loop is not queue_loop
            ):
                logger.warning(
                    "[ModuleRegistry] QueueLoop replacement "
                    "rejected | existing_id=%s | "
                    "incoming_id=%s",
                    id(self.queue_loop),
                    id(queue_loop),
                )
                return False

            self.queue_loop = queue_loop

        logger.info(
            "[ModuleRegistry] QbitQueueLoop bound | "
            "queue_loop=%s | identity=%s",
            type(queue_loop).__name__,
            id(queue_loop),
        )

        return True

    def bind_event_bus(
        self,
        event_bus,
    ):
        if event_bus is None:
            return False

        with self._lock:
            if (
                self.event_bus is not None
                and self.event_bus is not event_bus
            ):
                logger.warning(
                    "[ModuleRegistry] EventBus replacement "
                    "rejected | existing_id=%s | "
                    "incoming_id=%s",
                    id(self.event_bus),
                    id(event_bus),
                )
                return False

            self.event_bus = event_bus

        logger.info(
            "[ModuleRegistry] EventBus bound | event_bus=%s",
            type(event_bus).__name__,
        )

        return True

    def bind_track_system(
        self,
        track_system,
    ):
        if track_system is None:
            return False

        with self._lock:
            if (
                self.track_system is not None
                and self.track_system is not track_system
            ):
                logger.warning(
                    "[ModuleRegistry] TrackSystem replacement "
                    "rejected"
                )
                return False

            self.track_system = track_system

        logger.info(
            "[ModuleRegistry] TrackSystem bound | "
            "track_system=%s",
            type(track_system).__name__,
        )

        return True

    # ======================================================
    # QBIT TELEMETRY HANDOFF
    # ======================================================

    def _send_qbit(
        self,
        event: Dict[str, Any],
        track_id: Optional[str] = None,
    ) -> bool:

        packet = dict(event)

        if track_id is not None:
            packet["track_id"] = track_id

        packet.setdefault(
            "source",
            "module_registry",
        )

        packet.setdefault(
            "timestamp",
            time.time(),
        )

        packet.setdefault(
            "registry",
            "ModuleRegistry",
        )

        packet.setdefault(
            "authority",
            "QbitDialer",
        )

        # --------------------------------------------------
        # Existing Qbit path
        #
        # Preserve the existing behavior.
        # --------------------------------------------------

        qbit = self.qbit

        if qbit is not None:
            emitter = getattr(
                qbit,
                "emit",
                None,
            )

            if callable(emitter):
                try:
                    emitter(
                        packet,
                        track_id=track_id,
                    )

                    return True

                except TypeError:
                    # Compatibility with emit(packet)
                    # implementations.
                    try:
                        emitter(packet)
                        return True

                    except Exception:
                        logger.exception(
                            "[ModuleRegistry] Qbit emit failed"
                        )

                except Exception:
                    logger.exception(
                        "[ModuleRegistry] Qbit emit failed"
                    )

        # --------------------------------------------------
        # Existing Dialer handoff
        #
        # Only use the explicitly supplied authoritative Dialer.
        # Never instantiate one here.
        # --------------------------------------------------

        dialer = self.dialer

        if dialer is not None:
            receive = getattr(
                dialer,
                "receive_qbit",
                None,
            )

            if callable(receive):
                try:
                    receive(packet)
                    return True

                except Exception:
                    logger.exception(
                        "[ModuleRegistry] "
                        "QbitDialer receive_qbit failed"
                    )

        logger.debug(
            "[ModuleRegistry] Telemetry retained without "
            "Qbit handoff | event=%s",
            packet.get("event"),
        )

        return False

    # ======================================================
    # TRACK HELPERS
    # ======================================================

    def _create_track(
        self,
        priority: str,
    ):

        try:
            result = TrackContext.push(
                channel="MOD",
                skill="ModuleRegistry",
                priority=priority,
            )

            if isinstance(
                result,
                tuple,
            ):
                if len(result) >= 2:
                    return (
                        result[0],
                        result[1],
                    )

                if len(result) == 1:
                    return (
                        result[0],
                        None,
                    )

            if isinstance(
                result,
                dict,
            ):
                return (
                    result.get(
                        "track_id"
                    ),
                    result.get(
                        "parent_id"
                    ),
                )

            if result is not None:
                return (
                    str(result),
                    None,
                )

        except Exception as exc:
            logger.warning(
                "[ModuleRegistry] TrackContext creation "
                "failed: %s",
                exc,
            )

        return (
            str(uuid.uuid4()),
            None,
        )

    # ======================================================
    # REGISTER MODULE
    # ======================================================

    def register(
        self,
        name: str,
        *,
        dependencies: Optional[List[str]] = None,
        heartbeat_timeout: int = DEFAULT_HEARTBEAT_TIMEOUT,
        restartable: bool = True,
        critical: bool = False,
        priority: str = "MED",
        permissions: Optional[List[str]] = None,
        inventory: Optional[Dict[str, Any]] = None,
    ):

        if not name:
            raise ValueError(
                "[ModuleRegistry] Module name is required"
            )

        track_id, parent_id = (
            self._create_track(
                priority
            )
        )

        try:
            if permissions:
                for permission in permissions:
                    try:
                        PermissionRegistry.assign_to_track(
                            track_id,
                            permission,
                        )

                    except Exception as exc:
                        logger.warning(
                            "[ModuleRegistry] Permission "
                            "assignment failed | module=%s | "
                            "permission=%s | %s",
                            name,
                            permission,
                            exc,
                        )

            with self._lock:
                now = time.time()

                existing = self._modules.get(
                    name
                )

                # --------------------------------------------------
                # Preserve an existing registration when possible.
                #
                # Re-registering a module should refresh metadata
                # rather than destroy its accumulated health state.
                # --------------------------------------------------

                if existing is not None:
                    existing_inventory = dict(
                        existing.get(
                            "inventory",
                            {},
                        )
                    )

                    if inventory:
                        existing_inventory.update(
                            dict(inventory)
                        )

                    existing.update(
                        {
                            "name": name,
                            "timeout": max(
                                0.1,
                                float(
                                    heartbeat_timeout
                                ),
                            ),
                            "dependencies": list(
                                dependencies or existing.get(
                                    "dependencies",
                                    [],
                                )
                            ),
                            "restartable": bool(
                                restartable
                            ),
                            "critical": bool(
                                critical
                            ),
                            "priority": priority,
                            "permissions": list(
                                permissions
                                or existing.get(
                                    "permissions",
                                    [],
                                )
                            ),
                            "inventory": (
                                existing_inventory
                            ),
                            "last_status_change": now,
                        }
                    )

                    module_data = (
                        self._copy_module(
                            existing
                        )
                    )

                else:
                    self._modules[name] = {
                        "name": name,
                        "last_heartbeat": now,
                        "timeout": max(
                            0.1,
                            float(
                                heartbeat_timeout
                            ),
                        ),
                        "dependencies": list(
                            dependencies or []
                        ),
                        "restartable": bool(
                            restartable
                        ),
                        "critical": bool(
                            critical
                        ),
                        "status": "healthy",
                        "priority": priority,
                        "permissions": list(
                            permissions or []
                        ),
                        "inventory": dict(
                            inventory or {}
                        ),
                        "track_id": track_id,
                        "parent_track": parent_id,
                        "predictive_score": 0.0,
                        "fault_count": 0,
                        "last_status_change": now,
                    }

                    module_data = (
                        self._copy_module(
                            self._modules[name]
                        )
                    )

            # --------------------------------------------------
            # Structural node registration.
            # --------------------------------------------------

            self._synchronize_module_node(
                name,
                module_data,
            )

            # --------------------------------------------------
            # Existing Qbit telemetry.
            # --------------------------------------------------

            self._send_qbit(
                {
                    "event": "MODULE_REGISTERED",
                    "module": name,
                    "priority": priority,
                    "status": "healthy",
                    "node_registered": True,
                    "runtime_registry": (
                        self._runtime_provider_registered
                    ),
                },
                track_id=module_data.get(
                    "track_id"
                ),
            )

            if self.database is not None and self.database.enabled:
                track_value = module_data.get("track_id")
                if track_value:
                    self.database.upsert("runtime_tracks", {
                        "track_id": str(track_value),
                        "parent_track_id": module_data.get("parent_track"),
                        "source": "ModuleRegistry",
                        "status": "active",
                        "metadata": {"module": name},
                    }, conflict="track_id")
                self.database.sync_module(module_data)
                self.database.sync_node({
                    "node_id": name,
                    "module_name": name,
                    "track_id": module_data.get("track_id"),
                    "status": "healthy",
                    "capabilities": module_data.get("inventory", {}),
                    "metadata": {"priority": priority},
                })

            logger.info(
                "[ModuleRegistry][REGISTER] %s | "
                "track_id=%s | priority=%s | "
                "node_registered=%s",
                name,
                module_data.get(
                    "track_id"
                ),
                priority,
                True,
            )

            return self.get(name)

        finally:
            try:
                TrackContext.pop()

            except Exception:
                pass

    # ======================================================
    # GET MODULE
    # ======================================================

    def get(
        self,
        name: str,
    ) -> Optional[Dict[str, Any]]:

        with self._lock:
            module = self._modules.get(
                name
            )

            if module is None:
                return None

            result = dict(module)

            result["dependencies"] = list(
                module.get(
                    "dependencies",
                    [],
                )
            )

            result["permissions"] = list(
                module.get(
                    "permissions",
                    [],
                )
            )

            result["inventory"] = dict(
                module.get(
                    "inventory",
                    {},
                )
            )

            return result

    # ======================================================
    # LIST MODULES
    # ======================================================

    def all(self) -> List[Dict[str, Any]]:
        with self._lock:
            names = list(
                self._modules.keys()
            )

        return [
            self.get(name)
            for name in names
        ]

    # ======================================================
    # HEARTBEAT
    # ======================================================

    def update_heartbeat(
        self,
        name: str,
    ):

        with self._lock:
            module = self._modules.get(
                name
            )

            if module is None:
                logger.debug(
                    "[ModuleRegistry][HEARTBEAT] "
                    "Unknown module: %s",
                    name,
                )
                return False

            module["last_heartbeat"] = (
                time.time()
            )

            previous_status = module.get(
                "status",
                "unknown",
            )

            module["status"] = "healthy"

            track_id = module.get(
                "track_id"
            )

            snapshot = self._copy_module(
                module
            )

        # --------------------------------------------------
        # Keep SRegistry + registry_runtime synchronized.
        # --------------------------------------------------

        self._synchronize_module_node(
            name,
            snapshot,
        )

        self._send_qbit(
            {
                "event": "HEARTBEAT",
                "module": name,
                "status": "healthy",
            },
            track_id=track_id,
        )

        if previous_status != "healthy":
            self._send_qbit(
                {
                    "event": "STATUS_CHANGE",
                    "module": name,
                    "previous_status": (
                        previous_status
                    ),
                    "status": "healthy",
                },
                track_id=track_id,
            )

        if self.database is not None and self.database.enabled:
            try:
                dialer_state = self._object_status(self.dialer)
                queue_state = self._object_status(self.queue_loop)
                qbit_state = self._object_status(self.qbit)
                self.database.network_heartbeat(
                    status="ONLINE" if self.started else "OFFLINE",
                    dialer_state=str(dialer_state),
                    queue_state=str(queue_state),
                    qbit_state=str(qbit_state),
                    telemetry={"module": name},
                )
            except Exception as exc:
                logger.debug(
                    "[ModuleRegistry] Network heartbeat unavailable: %s",
                    exc,
                )

        logger.debug(
            "[ModuleRegistry][HEARTBEAT] %s refreshed",
            name,
        )

        return True

    # ======================================================
    # HEALTH CHECK
    # ======================================================

    def check_health(
        self,
    ) -> List[Dict[str, Any]]:

        now = time.time()

        unhealthy: List[
            Dict[str, Any]
        ] = []

        status_events: List[
            Dict[str, Any]
        ] = []

        node_sync: List[
            tuple[str, Dict[str, Any]]
        ] = []

        with self._lock:
            module_names = list(
                self._modules.keys()
            )

            for name in module_names:
                data = self._modules[name]

                previous_status = data.get(
                    "status",
                    "unknown",
                )

                last_heartbeat = float(
                    data.get(
                        "last_heartbeat",
                        now,
                    )
                )

                timeout = float(
                    data.get(
                        "timeout",
                        self.DEFAULT_HEARTBEAT_TIMEOUT,
                    )
                )

                # ------------------------------------------
                # Heartbeat status
                # ------------------------------------------

                if (
                    now - last_heartbeat
                    > timeout
                ):
                    new_status = (
                        "unresponsive"
                    )

                # ------------------------------------------
                # Device feedback
                # ------------------------------------------

                elif (
                    self.device_manager
                    is not None
                ):
                    try:
                        active_sessions = getattr(
                            self.device_manager,
                            "active_sessions",
                            None,
                        )

                        if (
                            active_sessions
                            is not None
                            and not active_sessions
                            and (
                                now - last_heartbeat
                                > self._device_feedback_timeout
                            )
                        ):
                            new_status = (
                                "device_inactive"
                            )

                        else:
                            new_status = (
                                "healthy"
                            )

                    except Exception:
                        # DeviceManager failure must not
                        # turn the registry into a fault
                        # generator.
                        new_status = (
                            "healthy"
                        )

                else:
                    new_status = "healthy"

                data["status"] = (
                    new_status
                )

                # ------------------------------------------
                # Predictive score
                # ------------------------------------------

                if self.predictive_enabled:
                    if (
                        new_status
                        == "healthy"
                    ):
                        data[
                            "predictive_score"
                        ] = max(
                            0.0,
                            data.get(
                                "predictive_score",
                                0.0,
                            ) * 0.95,
                        )

                    else:
                        data[
                            "predictive_score"
                        ] = min(
                            1.0,
                            data.get(
                                "predictive_score",
                                0.0,
                            ) + 0.1,
                        )

                    if (
                        data[
                            "predictive_score"
                        ]
                        >= self._predictive_threshold
                    ):
                        status_events.append(
                            {
                                "event": (
                                    "PREDICTIVE_ALERT"
                                ),
                                "module": name,
                                "predictive_score": (
                                    data[
                                        "predictive_score"
                                    ]
                                ),
                                "track_id": data.get(
                                    "track_id"
                                ),
                            }
                        )

                # ------------------------------------------
                # Status transition
                # ------------------------------------------

                if (
                    new_status
                    != previous_status
                ):
                    data[
                        "last_status_change"
                    ] = now

                    status_events.append(
                        {
                            "event": (
                                "STATUS_CHANGE"
                            ),
                            "module": name,
                            "previous_status": (
                                previous_status
                            ),
                            "status": (
                                new_status
                            ),
                            "track_id": data.get(
                                "track_id"
                            ),
                        }
                    )

                    logger.info(
                        "[ModuleRegistry][STATUS] %s "
                        "changed %s -> %s",
                        name,
                        previous_status,
                        new_status,
                    )

                # ------------------------------------------
                # Health result
                # ------------------------------------------

                if (
                    new_status
                    != "healthy"
                ):
                    unhealthy.append(
                        self._copy_module(
                            data
                        )
                    )

                node_sync.append(
                    (
                        name,
                        self._copy_module(
                            data
                        ),
                    )
                )

        # --------------------------------------------------
        # Synchronize registry nodes outside the lock.
        # --------------------------------------------------

        for name, data in node_sync:
            self._synchronize_module_node(
                name,
                data,
            )

        # --------------------------------------------------
        # Send telemetry outside the registry lock.
        # --------------------------------------------------

        for event in status_events:
            track_id = event.pop(
                "track_id",
                None,
            )

            self._send_qbit(
                event,
                track_id=track_id,
            )

        return unhealthy

    # ======================================================
    # PREDICTIVE ALERT
    # ======================================================

    def _emit_predictive_alert(
        self,
        name: str,
        data: Dict[str, Any],
    ):

        track_id = data.get(
            "track_id"
        )

        self._send_qbit(
            {
                "event": "PREDICTIVE_ALERT",
                "module": name,
                "predictive_score": data.get(
                    "predictive_score",
                    0.0,
                ),
            },
            track_id=track_id,
        )

        logger.warning(
            "[ModuleRegistry][PREDICTIVE] %s "
            "predictive_score=%.2f",
            name,
            data.get(
                "predictive_score",
                0.0,
            ),
        )

    # ======================================================
    # EXPLICIT RESTART
    # ======================================================

    def restart_module(
        self,
        name: str,
    ):

        with self._lock:
            module = self._modules.get(
                name
            )

            if module is None:
                logger.warning(
                    "[ModuleRegistry][RESTART] "
                    "Unknown module %s",
                    name,
                )
                return False

            if not module.get(
                "restartable",
                False,
            ):
                logger.info(
                    "[ModuleRegistry][RESTART] "
                    "%s is not restartable",
                    name,
                )
                return False

            track_id = module.get(
                "track_id"
            )

            module["status"] = (
                "restart_requested"
            )

            snapshot = self._copy_module(
                module
            )

        # --------------------------------------------------
        # Update node state.
        # --------------------------------------------------

        self._synchronize_module_node(
            name,
            snapshot,
        )

        self._send_qbit(
            {
                "event": (
                    "MODULE_RESTART_REQUEST"
                ),
                "module": name,
                "reason": (
                    "explicit_external_request"
                ),
            },
            track_id=track_id,
        )

        logger.info(
            "[ModuleRegistry][RESTART] "
            "Restart request emitted for %s | "
            "track_id=%s",
            name,
            track_id,
        )

        # --------------------------------------------------
        # IMPORTANT:
        #
        # The Registry does not simulate a restart anymore.
        # It does not sleep.
        # It does not claim the module restarted.
        #
        # The command authority must perform the operation
        # and the module must subsequently heartbeat.
        # --------------------------------------------------

        return True

    # ======================================================
    # BUILD REQUEST
    # ======================================================

    def request_build(
        self,
        module_name: str,
        build_spec: Dict[str, Any],
    ):

        if not module_name:
            raise ValueError(
                "[ModuleRegistry] module_name required"
            )

        if not isinstance(
            build_spec,
            dict,
        ):
            raise TypeError(
                "[ModuleRegistry] build_spec must be dict"
            )

        request = {
            "module": module_name,
            "build_spec": dict(
                build_spec
            ),
            "timestamp": time.time(),
            "track_id": str(
                uuid.uuid4()
            ),
        }

        with self._lock:
            self._build_queue.append(
                request
            )

        self._send_qbit(
            {
                "event": "BUILD_REQUEST",
                "module": module_name,
                "build_spec": dict(
                    build_spec
                ),
            },
            track_id=request[
                "track_id"
            ],
        )

        logger.info(
            "[ModuleRegistry][BUILD REQUEST] "
            "%s | track_id=%s",
            module_name,
            request[
                "track_id"
            ],
        )

        return dict(request)

    # ======================================================
    # DISTRIBUTION / ROUTING
    # ======================================================

    def distribute(
        self,
        module_name: str,
        destination: str,
    ):

        with self._lock:
            module = self._modules.get(
                module_name
            )

            if module is None:
                logger.warning(
                    "[ModuleRegistry][DISTRIBUTE] "
                    "Unknown module %s",
                    module_name,
                )
                return False

            track_id = module.get(
                "track_id"
            )

            event = {
                "module": module_name,
                "destination": destination,
                "timestamp": time.time(),
                "track_id": track_id,
            }

            self._distribution_log.append(
                dict(event)
            )

        self._send_qbit(
            {
                "event": (
                    "MODULE_DISTRIBUTED"
                ),
                "module": module_name,
                "destination": destination,
            },
            track_id=track_id,
        )

        logger.info(
            "[ModuleRegistry][DISTRIBUTION] "
            "%s -> %s",
            module_name,
            destination,
        )

        return dict(event)

    # ======================================================
    # SNAPSHOT
    # ======================================================

    def snapshot(
        self,
    ) -> Dict[str, Any]:

        with self._lock:
            return {
                "version": self.VERSION,
                "passive": self.passive,
                "started": self._started,
                "shutdown": self._shutdown,

                "runtime": {
                    "qbit": self._object_status(
                        self.qbit
                    ),
                    "dialer": self._object_status(
                        self.dialer
                    ),
                    "queue_loop": self._object_status(
                        self.queue_loop
                    ),
                    "event_bus": self._object_status(
                        self.event_bus
                    ),
                    "track_system": self._object_status(
                        self.track_system
                    ),
                    "registry": self._object_status(
                        self.registry
                    ),
                    "registry_runtime": self._object_status(
                        self.registry_runtime
                    ),
                    "node_registry": self._object_status(
                        self.node_registry
                    ),
                    "kernel_bus": self._object_status(
                        self.kernel_bus
                    ),
                    "neural_bridge": self._object_status(
                        self.neural_bridge
                    ),
                    "fathud": self._object_status(
                        self.fathud
                    ),
                    "binding_generation": (
                        self._runtime_binding_generation
                    ),
                },

                "modules": {
                    name: self._copy_module(
                        data
                    )
                    for name, data
                    in self._modules.items()
                },

                "build_queue": [
                    dict(item)
                    for item in self._build_queue
                ],

                "distribution_log": [
                    dict(item)
                    for item
                    in self._distribution_log
                ],
            }

    # ======================================================
    # RUNTIME STATUS
    # ======================================================

    def runtime_status(
        self,
    ) -> Dict[str, Any]:

        with self._lock:
            module_count = len(
                self._modules
            )

            healthy = sum(
                1
                for data
                in self._modules.values()
                if data.get(
                    "status"
                ) == "healthy"
            )

            unhealthy = module_count - healthy

            return {
                "name": self.registry_name,
                "version": self.VERSION,
                "state": (
                    "ONLINE"
                    if self.started
                    else (
                        "SHUTDOWN"
                        if self._shutdown
                        else "WAITING"
                    )
                ),
                "passive": self.passive,
                "authorities": {
                    "qbit": self._object_status(
                        self.qbit
                    ),
                    "qbit_dialer": self._object_status(
                        self.dialer
                    ),
                    "qbit_queue_loop": self._object_status(
                        self.queue_loop
                    ),
                    "event_bus": self._object_status(
                        self.event_bus
                    ),
                    "track_system": self._object_status(
                        self.track_system
                    ),
                    "sregistry": self._object_status(
                        self.registry
                    ),
                    "registry_runtime": self._object_status(
                        self.registry_runtime
                    ),
                    "node_registry": self._object_status(
                        self.node_registry
                    ),
                    "kernel_bus": self._object_status(
                        self.kernel_bus
                    ),
                    "neural_bridge": self._object_status(
                        self.neural_bridge
                    ),
                    "fathud": self._object_status(
                        self.fathud
                    ),
                },
                "modules": {
                    "total": module_count,
                    "healthy": healthy,
                    "unhealthy": unhealthy,
                },
                "registry_node_registered": (
                    self._registry_node_registered
                ),
                "runtime_provider_registered": (
                    self._runtime_provider_registered
                ),
                "binding_generation": (
                    self._runtime_binding_generation
                ),
            }

    # ======================================================
    # CLEAR
    # ======================================================

    def clear(
        self,
    ):

        with self._lock:
            self._modules.clear()
            self._build_queue.clear()
            self._distribution_log.clear()

        self._publish_runtime_state(
            state=(
                "ONLINE"
                if self.started
                else "REGISTERED"
            )
        )

        logger.info(
            "[ModuleRegistry] Cleared registry"
        )

        return True

    # ======================================================
    # INTERNAL PATH HELPERS
    # ======================================================

    @staticmethod
    def _resolve_module_path(
        name: str,
        data: Dict[str, Any],
    ) -> Path:

        inventory = data.get(
            "inventory",
            {},
        )

        if not isinstance(
            inventory,
            dict,
        ):
            inventory = {}

        candidates = (
            inventory.get("path"),
            inventory.get("file"),
            inventory.get("module_path"),
            inventory.get("source_path"),
        )

        for candidate in candidates:
            if candidate:
                try:
                    return Path(
                        candidate
                    ).resolve()
                except Exception:
                    pass

        # --------------------------------------------------
        # Preserve dotted module identity when an explicit
        # filesystem path is unavailable.
        #
        # This creates a stable registry identity without
        # pretending that a physical file exists.
        # --------------------------------------------------

        parts = [
            part
            for part in str(name).split(".")
            if part
        ]

        if parts:
            try:
                return (
                    Path(
                        __file__
                    ).resolve().parent
                    / "registered"
                    / Path(*parts)
                )
            except Exception:
                pass

        return (
            Path(
                __file__
            ).resolve()
        )

    @staticmethod
    def _resolve_parent_path(
        data: Dict[str, Any],
    ):

        inventory = data.get(
            "inventory",
            {},
        )

        if not isinstance(
            inventory,
            dict,
        ):
            inventory = {}

        parent = inventory.get(
            "parent"
        )

        if parent:
            try:
                return Path(
                    parent
                ).resolve()
            except Exception:
                return parent

        return (
            Path(
                __file__
            ).resolve().parent
        )

    # ======================================================
    # INTERNAL STATE HELPERS
    # ======================================================

    @staticmethod
    def _node_state(
        data: Dict[str, Any],
    ) -> str:

        status = str(
            data.get(
                "status",
                "unknown",
            )
        ).lower()

        mapping = {
            "healthy": "ONLINE",
            "online": "ONLINE",
            "running": "ONLINE",
            "restart_requested": (
                "DEGRADED"
            ),
            "device_inactive": (
                "DEGRADED"
            ),
            "unresponsive": (
                "DEGRADED"
            ),
            "error": "FAILED",
            "failed": "FAILED",
            "offline": "OFFLINE",
        }

        return mapping.get(
            status,
            "REGISTERED",
        )

    @staticmethod
    def _runtime_provider_state(
        data: Dict[str, Any],
    ) -> str:

        status = str(
            data.get(
                "status",
                "unknown",
            )
        ).lower()

        if status in (
            "healthy",
            "online",
            "running",
        ):
            return "ONLINE"

        if status in (
            "failed",
            "error",
        ):
            return "FAILED"

        if status in (
            "unresponsive",
            "device_inactive",
            "restart_requested",
        ):
            return "DEGRADED"

        return "REGISTERED"

    @staticmethod
    def _object_status(
        obj,
    ) -> Dict[str, Any]:

        if obj is None:
            return {
                "online": False,
                "type": None,
                "identity": None,
            }

        return {
            "online": True,
            "type": type(
                obj
            ).__name__,
            "identity": id(obj),
        }

    def _instance_id(
        self,
    ) -> str:

        explicit = getattr(
            self,
            "instance_id",
            None,
        )

        if explicit:
            return str(
                explicit
            )

        return (
            f"{type(self).__module__}."
            f"{type(self).__qualname__}."
            f"{id(self)}"
        )

    @staticmethod
    def _module_instance_id(
        name: str,
        data: Dict[str, Any],
    ) -> str:

        track_id = data.get(
            "track_id"
        )

        if track_id:
            return (
                f"module:{name}:"
                f"{track_id}"
            )

        return (
            f"module:{name}"
        )

    # ======================================================
    # INTERNAL COPY HELPER
    # ======================================================

    @staticmethod
    def _copy_module(
        data: Dict[str, Any],
    ) -> Dict[str, Any]:

        result = dict(
            data
        )

        result["dependencies"] = list(
            data.get(
                "dependencies",
                [],
            )
        )

        result["permissions"] = list(
            data.get(
                "permissions",
                [],
            )
        )

        result["inventory"] = dict(
            data.get(
                "inventory",
                {},
            )
        )

        return result


# ==========================================================
# END OF FILE
# ==========================================================