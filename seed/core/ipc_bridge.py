# ==========================================================
# FILE: ipc_bridge.py
# PATH: SEED_ROOT/seed/core/ipc_bridge.py
# VERSION: 3.2
#
# PERMISSION-ENFORCED | RUNTIME-BOUND | FATHUD-AWARE
# SINGLE-AUTHORITY IPC BRIDGE
# ==========================================================

import inspect
import logging
from collections import defaultdict
from typing import Callable, Dict, List

from seed.core.ipc_permissions import (
    IPCPermissionMatrix,
    IPCDomain,
)

logger = logging.getLogger("IPCBridge")
logger.setLevel(logging.INFO)


class IPCBridge:

    VERSION = "3.2"
    COMPONENT = "IPCBridge"

    def __init__(
        self,
        *,
        channel_manager=None,
        event_bus=None,
        qbit=None,
        queue_loop=None,
        qbit_dialer=None,
        track_system=None,
        registry=None,
        registry_runtime=None,
        nodes=None,
        node_registry=None,
        seedcore=None,
        seed_core=None,
        fathud=None,
        fat_hud=None,
        fat_hud_adapter=None,
        kernel_bus=None,
    ):
        # ======================================================
        # Authoritative Runtime References
        # ======================================================

        self.channel_manager = channel_manager

        self.event_bus = event_bus
        self.qbit = qbit
        self.queue_loop = queue_loop
        self.qbit_dialer = qbit_dialer

        self.track_system = track_system

        self.registry = registry
        self.registry_runtime = registry_runtime

        self.nodes = nodes
        self.node_registry = node_registry

        self.seedcore = (
            seedcore
            if seedcore is not None
            else seed_core
        )

        self.kernel_bus = kernel_bus

        self.fathud = (
            fathud
            if fathud is not None
            else fat_hud
        )

        self.fat_hud_adapter = fat_hud_adapter

        # ======================================================
        # IPC State
        # ======================================================

        self.subscribers: Dict[str, List[Callable]] = defaultdict(list)

        self.permissions = IPCPermissionMatrix()

        self._init_default_permissions()

        self._fathud_bound = False
        self._runtime_bound = False
        self._shutdown = False

        logger.info(
            "[IPCBridge] Initialized | "
            "permissions=ONLINE | "
            "event_bus=%s | "
            "qbit=%s | "
            "queue_loop=%s | "
            "qbit_dialer=%s | "
            "track_system=%s | "
            "registry=%s | "
            "registry_runtime=%s | "
            "nodes=%s | "
            "seed_core=%s | "
            "fathud=%s",
            self._type_name(self.event_bus),
            self._type_name(self.qbit),
            self._type_name(self.queue_loop),
            self._type_name(self.qbit_dialer),
            self._type_name(self.track_system),
            self._type_name(self.registry),
            self._type_name(self.registry_runtime),
            self._type_name(self.nodes),
            self._type_name(self.seedcore),
            self._type_name(self.fathud),
        )

        # Bind immediately only when supplied by the authoritative
        # runtime. No object is created here.
        if any(
            value is not None
            for value in (
                event_bus,
                qbit,
                queue_loop,
                qbit_dialer,
                track_system,
                registry,
                registry_runtime,
                nodes,
                node_registry,
                seedcore,
                seed_core,
                fathud,
                fat_hud,
                fat_hud_adapter,
                kernel_bus,
                channel_manager,
            )
        ):
            self.bind_runtime(
                channel_manager=channel_manager,
                event_bus=event_bus,
                qbit=qbit,
                queue_loop=queue_loop,
                qbit_dialer=qbit_dialer,
                track_system=track_system,
                registry=registry,
                registry_runtime=registry_runtime,
                nodes=nodes,
                node_registry=node_registry,
                seedcore=seedcore,
                seed_core=seed_core,
                fathud=fathud,
                fat_hud=fat_hud,
                fat_hud_adapter=fat_hud_adapter,
                kernel_bus=kernel_bus,
            )

    # ==========================================================
    # Helpers
    # ==========================================================

    @staticmethod
    def _type_name(value):
        if value is None:
            return "NONE"

        return type(value).__name__

    @staticmethod
    def _instance_id(value):
        if value is None:
            return None

        explicit = getattr(value, "instance_id", None)

        if explicit is not None:
            return str(explicit)

        return (
            f"{type(value).__module__}."
            f"{type(value).__name__}:"
            f"{id(value)}"
        )

    @staticmethod
    def _same_or_unbound(
        current,
        incoming,
    ):
        if incoming is None:
            return True

        if current is None:
            return True

        return current is incoming

    # ==========================================================
    # Runtime Binding
    # ==========================================================

    def bind_runtime(
        self,
        *,
        channel_manager=None,
        event_bus=None,
        qbit=None,
        queue_loop=None,
        qbit_dialer=None,
        track_system=None,
        registry=None,
        registry_runtime=None,
        nodes=None,
        node_registry=None,
        seedcore=None,
        seed_core=None,
        fathud=None,
        fat_hud=None,
        fat_hud_adapter=None,
        kernel_bus=None,
    ):

        resolved_seed_core = (
            seedcore
            if seedcore is not None
            else seed_core
        )

        resolved_fathud = (
            fathud
            if fathud is not None
            else fat_hud
        )

        # ======================================================
        # Identity Enforcement
        # ======================================================

        checks = (
            ("channel_manager", self.channel_manager, channel_manager),
            ("event_bus", self.event_bus, event_bus),
            ("qbit", self.qbit, qbit),
            ("queue_loop", self.queue_loop, queue_loop),
            ("qbit_dialer", self.qbit_dialer, qbit_dialer),
            ("track_system", self.track_system, track_system),
            ("registry", self.registry, registry),
            (
                "registry_runtime",
                self.registry_runtime,
                registry_runtime,
            ),
            ("nodes", self.nodes, nodes),
            (
                "node_registry",
                self.node_registry,
                node_registry,
            ),
            ("seedcore", self.seedcore, resolved_seed_core),
            ("kernel_bus", self.kernel_bus, kernel_bus),
        )

        for name, current, incoming in checks:
            if (
                current is not None
                and incoming is not None
                and current is not incoming
            ):
                raise RuntimeError(
                    f"[IPCBridge] {name} identity mismatch"
                )

        # ======================================================
        # Bind Runtime References
        # ======================================================

        if channel_manager is not None:
            self.channel_manager = channel_manager

        if event_bus is not None:
            self.event_bus = event_bus

        if qbit is not None:
            self.qbit = qbit

        if queue_loop is not None:
            self.queue_loop = queue_loop

        if qbit_dialer is not None:
            self.qbit_dialer = qbit_dialer

        if track_system is not None:
            self.track_system = track_system

        if registry is not None:
            self.registry = registry

        if registry_runtime is not None:
            self.registry_runtime = registry_runtime

        if nodes is not None:
            self.nodes = nodes

        if node_registry is not None:
            self.node_registry = node_registry

        if resolved_seed_core is not None:
            self.seedcore = resolved_seed_core

        if kernel_bus is not None:
            self.kernel_bus = kernel_bus

        if resolved_fathud is not None:
            self.bind_fathud(resolved_fathud)

        if fat_hud_adapter is not None:
            self.bind_fathud_adapter(fat_hud_adapter)

        self._runtime_bound = True

        logger.info(
            "[IPCBridge] Runtime bound | "
            "event_bus=%s | "
            "qbit=%s | "
            "queue_loop=%s | "
            "qbit_dialer=%s | "
            "track_system=%s | "
            "registry=%s | "
            "registry_runtime=%s | "
            "nodes=%s | "
            "seed_core=%s | "
            "fathud=%s",
            self._type_name(self.event_bus),
            self._type_name(self.qbit),
            self._type_name(self.queue_loop),
            self._type_name(self.qbit_dialer),
            self._type_name(self.track_system),
            self._type_name(self.registry),
            self._type_name(self.registry_runtime),
            self._type_name(self.nodes),
            self._type_name(self.seedcore),
            self._type_name(self.fathud),
        )

        return True

    # ==========================================================
    # FATHUD Binding
    # ==========================================================

    def bind_fathud(self, fathud):

        if fathud is None:
            return False

        if (
            self.fathud is not None
            and self.fathud is not fathud
        ):
            raise RuntimeError(
                "[IPCBridge] FATHUD identity mismatch"
            )

        self.fathud = fathud
        self._fathud_bound = True

        logger.info(
            "[IPCBridge] FATHUD observer bound | "
            "instance=%s",
            self._instance_id(fathud),
        )

        self._publish_fathud_status()

        return True

    def bind_fathud_adapter(self, adapter):

        if adapter is None:
            return False

        if (
            self.fat_hud_adapter is not None
            and self.fat_hud_adapter is not adapter
        ):
            raise RuntimeError(
                "[IPCBridge] FATHUD adapter identity mismatch"
            )

        self.fat_hud_adapter = adapter
        self._fathud_bound = True

        logger.info(
            "[IPCBridge] FATHUD adapter bound | "
            "instance=%s",
            self._instance_id(adapter),
        )

        self._publish_fathud_status()

        return True

    def _publish_fathud_status(self):
        payload = self.status()

        targets = (
            self.fathud,
            self.fat_hud_adapter,
        )

        for target in targets:
            if target is None:
                continue

            try:
                # Existing observer APIs are used when present.
                for method_name in (
                    "update_ipc_status",
                    "update_runtime_status",
                    "publish_status",
                    "receive_runtime_status",
                ):
                    method = getattr(
                        target,
                        method_name,
                        None,
                    )

                    if callable(method):
                        result = method(payload)

                        if inspect.isawaitable(result):
                            self._schedule_awaitable(
                                result
                            )

                        break

            except Exception:
                logger.exception(
                    "[IPCBridge] FATHUD status update failed"
                )

    def _schedule_awaitable(self, awaitable):

        try:
            import asyncio

            try:
                running_loop = asyncio.get_running_loop()
            except RuntimeError:
                running_loop = None

            if running_loop is not None:
                running_loop.create_task(awaitable)
                return True

        except Exception:
            logger.exception(
                "[IPCBridge] Failed to schedule awaitable"
            )

        return False

    # ==========================================================
    # Default Security Policy
    # ==========================================================

    def _init_default_permissions(self):

        # ------------------------------------------------------
        # UI
        # ------------------------------------------------------

        self.permissions.allow_publish(
            "seed.ui.launch",
            IPCDomain.SYSTEM,
            IPCDomain.DEV,
        )

        self.permissions.allow_subscribe(
            "seed.ui.launch",
            IPCDomain.SYSTEM,
            IPCDomain.DEV,
        )

        # ------------------------------------------------------
        # Events
        # ------------------------------------------------------

        self.permissions.allow_publish(
            "channel.event",
            IPCDomain.SYSTEM,
            IPCDomain.DEV,
            IPCDomain.USER,
        )

        self.permissions.allow_subscribe(
            "channel.event",
            IPCDomain.SYSTEM,
            IPCDomain.DEV,
        )

        # ------------------------------------------------------
        # Devices
        # ------------------------------------------------------

        self.permissions.allow_publish(
            "device.write",
            IPCDomain.SYSTEM,
        )

        self.permissions.allow_subscribe(
            "device.read",
            IPCDomain.SYSTEM,
            IPCDomain.DEV,
        )

        # ------------------------------------------------------
        # Runtime telemetry
        # ------------------------------------------------------

        self.permissions.allow_publish(
            "runtime.status",
            IPCDomain.SYSTEM,
            IPCDomain.DEV,
        )

        self.permissions.allow_subscribe(
            "runtime.status",
            IPCDomain.SYSTEM,
            IPCDomain.DEV,
        )

        self.permissions.allow_publish(
            "fathud.status",
            IPCDomain.SYSTEM,
            IPCDomain.DEV,
        )

        self.permissions.allow_subscribe(
            "fathud.status",
            IPCDomain.SYSTEM,
            IPCDomain.DEV,
        )

    # ==========================================================
    # Subscribe
    # ==========================================================

    def subscribe(
        self,
        topic: str,
        handler: Callable,
        domain: IPCDomain = IPCDomain.SYSTEM,
    ):
        if not callable(handler):
            raise TypeError(
                "[IPC] handler must be callable"
            )

        if not self.permissions.can_subscribe(
            topic,
            domain,
        ):
            raise PermissionError(
                f"[IPC] {domain} may NOT subscribe "
                f"to '{topic}'"
            )

        if handler not in self.subscribers[topic]:
            self.subscribers[topic].append(handler)

        logger.info(
            "[IPC] %s subscribed → %s",
            domain,
            topic,
        )

        return True

    # ==========================================================
    # Publish
    # ==========================================================

    def publish(
        self,
        topic: str,
        payload,
        domain: IPCDomain = IPCDomain.SYSTEM,
    ):
        if self._shutdown:
            return False

        if not self.permissions.can_publish(
            topic,
            domain,
        ):
            raise PermissionError(
                f"[IPC] {domain} may NOT publish "
                f"to '{topic}'"
            )

        callbacks = list(
            self.subscribers.get(topic, [])
        )

        for handler in callbacks:
            try:
                result = handler(payload)

                if inspect.isawaitable(result):
                    self._schedule_awaitable(result)

            except Exception as exc:
                logger.exception(
                    "[IPC] Handler error on '%s': %s",
                    topic,
                    exc,
                )

        # ======================================================
        # EventBus observation
        # ======================================================

        self._publish_event_bus(
            topic,
            payload,
        )

        # ======================================================
        # FATHUD observation
        # ======================================================

        if topic in (
            "runtime.status",
            "fathud.status",
            "channel.event",
        ):
            self._publish_fathud_status()

        return True

    # ==========================================================
    # EventBus Forwarding
    # ==========================================================

    def _publish_event_bus(
        self,
        topic,
        payload,
    ):
        if self.event_bus is None:
            return False

        event_payload = {
            "source": "IPCBridge",
            "topic": topic,
            "payload": payload,
            "ipc_bridge": self.status(),
        }

        try:
            for method_name in (
                "publish",
                "emit",
                "post",
                "send",
            ):
                method = getattr(
                    self.event_bus,
                    method_name,
                    None,
                )

                if not callable(method):
                    continue

                try:
                    result = method(
                        topic,
                        event_payload,
                    )
                except TypeError:
                    result = method(
                        event_payload
                    )

                if inspect.isawaitable(result):
                    self._schedule_awaitable(result)

                return True

        except Exception:
            logger.exception(
                "[IPCBridge] EventBus publish failed"
            )

        return False

    # ==========================================================
    # Runtime Status
    # ==========================================================

    def status(self):
        return {
            "component": self.COMPONENT,
            "version": self.VERSION,
            "permissions": "ONLINE",
            "runtime_bound": self._runtime_bound,
            "fathud_bound": self._fathud_bound,
            "shutdown": self._shutdown,

            "subscribers": {
                topic: len(handlers)
                for topic, handlers
                in self.subscribers.items()
            },

            "channel_manager": self._type_name(
                self.channel_manager
            ),

            "event_bus": self._type_name(
                self.event_bus
            ),

            "qbit": self._type_name(
                self.qbit
            ),

            "queue_loop": self._type_name(
                self.queue_loop
            ),

            "qbit_dialer": self._type_name(
                self.qbit_dialer
            ),

            "track_system": self._type_name(
                self.track_system
            ),

            "registry": self._type_name(
                self.registry
            ),

            "registry_runtime": self._type_name(
                self.registry_runtime
            ),

            "nodes": self._type_name(
                self.nodes
            ),

            "node_registry": self._type_name(
                self.node_registry
            ),

            "seed_core": self._type_name(
                self.seedcore
            ),

            "kernel_bus": self._type_name(
                self.kernel_bus
            ),

            "fathud": self._type_name(
                self.fathud
            ),

            "fat_hud_adapter": self._type_name(
                self.fat_hud_adapter
            ),
        }

    # ==========================================================
    # Shutdown
    # ==========================================================

    def shutdown(self):

        self.subscribers.clear()
        self._shutdown = True

        logger.info(
            "[IPC] Shutdown complete"
        )

        return True