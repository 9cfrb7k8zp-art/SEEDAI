# ==========================================================
# FILE: orchestrator.py
# PATH: SEED_ROOT/seed/core/orchestrator.py
# VERSION: 5.0-T
# ROLE: SYSTEM ORCHESTRATOR / RUNTIME COORDINATOR
# UPDATED: 2026-09-05
# ==========================================================

from __future__ import annotations

import asyncio
import logging
import time
import tracemalloc
from typing import Optional, Dict, Any

tracemalloc.start()

from seed.skills.action_registry import (
    set_qbit_control,
    set_admin_manager,
    set_module_registry,
)

from seed.core.intent_memory import IntentMemory
from seed.core.fat_layer import FATLayer
from seed.core.fat_persistence import FATPersistence
from seed.core.hud_master_overlay import HUDMasterOverlay
from seed.analytics.analytics_engine import SEEDAnalyticsEngine
from seed.core.actuator_engine import ActuatorEngine
from seed.skills.sparkplug import SparkPlug
from seed.core.device_modem_integration import DeviceModemManager
from seed.core.track_system import TrackSystem

logger = logging.getLogger("SEEDOrchestrator")
logger.setLevel(logging.INFO)

MODULE_ID = "O-1"


# ==========================================================
# TRACK TELEMETRY
# ==========================================================

def track(
    channel,
    state,
    *args,
    priority="MED",
    loop_id=None,
    input_from=None,
    output_to=None,
    note=None,
):
    try:
        parts = [
            "[TRACK]",
            f"{MODULE_ID}:{channel}",
            f"| {state}",
            f"| PRIORITY={priority}",
        ]

        if loop_id:
            parts.append(f"| {loop_id}")

        if input_from:
            parts.append(f"| IN={input_from}")

        if output_to:
            parts.append(f"| OUT={output_to}")

        if note:
            parts.append(f"| NOTE={note}")

        print(" ".join(parts), flush=True)

    except Exception:
        pass


track("CH-0", "B-IMPORT", priority="HIGH")


# ==========================================================
# SEED ORCHESTRATOR
# ==========================================================

class SEEDOrchestrator:

    _instance = None
    _lock = None
    _module_flags: Dict[str, str] = {}

    ACTIVE = False

    # ------------------------------------------------------
    # SINGLETON
    # ------------------------------------------------------

    def __new__(cls, *args, **kwargs):

        if cls._instance is None:
            cls._instance = super().__new__(cls)

        return cls._instance

    # ------------------------------------------------------
    # INITIALIZATION
    # ------------------------------------------------------

    def __init__(
        self,
        emit=None,
        callable=None,
        track=None,
        device_manager=None,
        event_bus=None,
        storage_root="./SEED_ROOT",
        loop=None,

        # --------------------------------------------------
        # AUTHORITATIVE RUNTIME REFERENCES
        # --------------------------------------------------

        qbit=None,
        queue_loop=None,
        qbit_dialer=None,
        kernel_bus=None,
        track_system=None,
        registry=None,
        node_registry=None,
        seedcore=None,
        fathud=None,
        intent_engine=None,

        low_power_threshold=15,
    ):

        if getattr(self, "_initialized", False):
            return

        self._initialized = True

        # --------------------------------------------------
        # EVENT LOOP
        # --------------------------------------------------

        try:
            self.loop = (
                loop
                or asyncio.get_running_loop()
            )

        except RuntimeError:

            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

        # --------------------------------------------------
        # EVENT BUS
        #
        # Orchestrator may reuse the authoritative EventBus.
        # It must not replace an existing runtime bus.
        # --------------------------------------------------

        if event_bus is None:

            from seed.core.event_bus import SEEDEventBus

            event_bus = SEEDEventBus()

        self.event_bus = event_bus

        try:
            self.event_bus._orchestrator_ready = False
        except Exception:
            pass

        # --------------------------------------------------
        # CORE REFERENCES
        # --------------------------------------------------

        self.emit = emit
        self._command = None

        self.storage_root = storage_root

        self.qbit = qbit
        self.queue_loop = queue_loop
        self.qbit_dialer = qbit_dialer
        self.kernel_bus = kernel_bus

        self.track_system = track_system
        self.registry = registry
        self.node_registry = node_registry

        self.seedcore = seedcore
        self.fathud = fathud

        # --------------------------------------------------
        # AUTHORITATIVE INTENT ENGINE
        # --------------------------------------------------

        self.intent_engine = intent_engine

        self.low_power_threshold = low_power_threshold

        self.running = False
        self._tasks = []

        # --------------------------------------------------
        # DEVICE MANAGER
        # --------------------------------------------------

        if device_manager is not None:

            self.device_manager = device_manager

        else:

            from seed.core.device_manager import DeviceManager

            self.device_manager = DeviceManager(
                storage_root=storage_root
            )

        # --------------------------------------------------
        # FAT
        # --------------------------------------------------

        self.fat = FATLayer(storage_root)

        self.fat_disk = FATPersistence(
            storage_root
        )

        # --------------------------------------------------
        # HUD OVERLAY
        #
        # Observer/interface only.
        # --------------------------------------------------

        self.hud_overlay = HUDMasterOverlay(
            device_manager=self.device_manager,
            channels=(3, 6, 9),
        )

        # --------------------------------------------------
        # ANALYTICS
        #
        # Reuse authoritative EventBus, Qbit,
        # QbitDialer, and IntentEngine.
        # --------------------------------------------------

        self.analytics = SEEDAnalyticsEngine(
            storage_root=storage_root,
            event_bus=self.event_bus,
            qbit=self.qbit,
            qbit_dialer=self.qbit_dialer,
            intent_engine=self.intent_engine,
            queue_loop=self.queue_loop,
            hud_interface=self.hud_overlay,
            fat_layer=self.fat,
        )

        # --------------------------------------------------
        # INTENT MEMORY
        #
        # Command authority is resolved after Dialer binding.
        # IntentMemory requires the authoritative emit path.
        # --------------------------------------------------

        self.intent_memory = IntentMemory(
            emit=self.emit,
            event_bus=self.event_bus,
            command=self,
            qbit_dialer=self.qbit_dialer,
            memory_window=5.0,
            decay_rate=0.85,
            max_records=64,
            auto_decay_interval=0.5,
            snapshot_interval=10.0,
            snapshot_path=(
                f"{self.storage_root}/"
                "intent_memory_snapshot.json"
            ),
        )

        try:

            self.event_bus.subscribe(
                "CAMERA_INTENT",
                self.intent_memory.ingest,
            )

        except Exception as exc:

            logger.warning(
                "[SEEDOrchestrator] "
                "CAMERA_INTENT subscription failed: %s",
                exc,
            )

        # --------------------------------------------------
        # ACTUATOR ENGINE
        # --------------------------------------------------

        self.actuator_engine = ActuatorEngine(
            fat_layer=self.fat,
            hud_interface=self.hud_overlay,
        )

        # --------------------------------------------------
        # SUBORDINATE MODULES
        # --------------------------------------------------

        self.agent_manager = None
        self.device_modem_manager = None
        self.sparkplug = None

        self._boot_time = time.time()

        track(
            "CH-0",
            "ORCHESTRATOR-INIT",
            priority="HIGH",
            note="system-level runtime references accepted",
        )

    # ======================================================
    # AUTHORITATIVE BINDING
    # ======================================================

    def bind_runtime(
        self,
        *,
        qbit=None,
        queue_loop=None,
        qbit_dialer=None,
        kernel_bus=None,
        track_system=None,
        registry=None,
        node_registry=None,
        seedcore=None,
        fathud=None,
        intent_engine=None,
    ):

        if qbit is not None:
            self.qbit = qbit

        if queue_loop is not None:
            self.queue_loop = queue_loop

        if qbit_dialer is not None:
            self.qbit_dialer = qbit_dialer
            self._command = qbit_dialer

        if kernel_bus is not None:
            self.kernel_bus = kernel_bus

        if track_system is not None:
            self.track_system = track_system

        if registry is not None:
            self.registry = registry

        if node_registry is not None:
            self.node_registry = node_registry

        if seedcore is not None:
            self.seedcore = seedcore

        if fathud is not None:
            self.fathud = fathud

        if intent_engine is not None:
            self.intent_engine = intent_engine

        # --------------------------------------------------
        # Propagate authoritative references to modules.
        # --------------------------------------------------

        if self.analytics is not None:

            try:
                self.analytics.qbit = self.qbit
                self.analytics.qbit_dialer = (
                    self.qbit_dialer
                )
                self.analytics.queue_loop = (
                    self.queue_loop
                )
                self.analytics.event_bus = (
                    self.event_bus
                )
                self.analytics.intent_engine = (
                    self.intent_engine
                )
            except Exception:
                pass

        if self.intent_memory is not None:

            try:
                self.intent_memory.qbit_dialer = (
                    self.qbit_dialer
                )
            except Exception:
                pass

        # --------------------------------------------------
        # TrackSystem receives the same authority.
        # It does not create one.
        # --------------------------------------------------

        if self.track_system is not None:

            for name, value in (
                ("qbit", self.qbit),
                ("qbit_dialer", self.qbit_dialer),
                ("kernel", self.kernel_bus),
                ("seedcore", self.seedcore),
                ("registry", self.registry),
                ("node_registry", self.node_registry),
                ("fathud", self.fathud),
            ):

                if value is not None:

                    try:
                        setattr(
                            self.track_system,
                            name,
                            value,
                        )
                    except Exception:
                        pass

        logger.info(
            "[SEEDOrchestrator] "
            "Authoritative runtime bound | "
            "qbit=%s | queue_loop=%s | "
            "dialer=%s | intent=%s | track=%s",
            type(self.qbit).__name__
            if self.qbit else "NONE",
            type(self.queue_loop).__name__
            if self.queue_loop else "NONE",
            type(self.qbit_dialer).__name__
            if self.qbit_dialer else "NONE",
            type(self.intent_engine).__name__
            if self.intent_engine else "NONE",
            type(self.track_system).__name__
            if self.track_system else "NONE",
        )

        track(
            "CH-RUNTIME",
            "AUTHORITIES-BOUND",
            priority="CRITICAL",
        )

        return True

    # ======================================================
    # ASYNC BOOT
    # ======================================================

    async def _async_boot(self):

        await self.initialize_modules()

    # ======================================================
    # MODULE INITIALIZATION
    # ======================================================

    async def initialize_modules(self):

        logger.info(
            "[SEEDOrchestrator] "
            "Initializing subordinate modules..."
        )

        await asyncio.sleep(0)

        return True

    # ======================================================
    # ASYNC FACTORY
    # ======================================================

    @classmethod
    async def create_async(
        cls,
        event_bus=None,
        storage_root="./SEED_ROOT",

        qbit=None,
        queue_loop=None,
        qbit_dialer=None,
        kernel_bus=None,
        track_system=None,
        registry=None,
        node_registry=None,
        seedcore=None,
        fathud=None,
        device_manager=None,
        intent_engine=None,
        emit=None,
    ):

        if cls._lock is None:
            cls._lock = asyncio.Lock()

        async with cls._lock:

            instance = cls(
                emit=emit,
                event_bus=event_bus,
                storage_root=storage_root,
                qbit=qbit,
                queue_loop=queue_loop,
                qbit_dialer=qbit_dialer,
                kernel_bus=kernel_bus,
                track_system=track_system,
                registry=registry,
                node_registry=node_registry,
                seedcore=seedcore,
                fathud=fathud,
                device_manager=device_manager,
                intent_engine=intent_engine,
            )

            # --------------------------------------------------
            # AUTHORITATIVE RUNTIME BIND
            # --------------------------------------------------

            instance.bind_runtime(
                qbit=qbit,
                queue_loop=queue_loop,
                qbit_dialer=qbit_dialer,
                kernel_bus=kernel_bus,
                track_system=track_system,
                registry=registry,
                node_registry=node_registry,
                seedcore=seedcore,
                fathud=fathud,
                intent_engine=intent_engine,
            )

            # --------------------------------------------------
            # QBIT DIALER
            #
            # CRITICAL:
            # Never construct a second Dialer here.
            # --------------------------------------------------

            if instance.qbit_dialer is not None:

                instance._command = (
                    instance.qbit_dialer
                )

                instance._module_flags[
                    "QbitDialer"
                ] = "GREEN"

                track(
                    "CH-MOD",
                    "QbitDialer-GREEN",
                    priority="HIGH",
                )

            else:

                logger.warning(
                    "[SEEDOrchestrator] "
                    "No authoritative QbitDialer supplied"
                )

            # --------------------------------------------------
            # DEVICE MODEM
            # --------------------------------------------------

            instance.device_modem_manager = (
                DeviceModemManager(
                    storage_root=storage_root,
                    event_bus=instance.event_bus,
                )
            )

            instance._module_flags[
                "DeviceModemManager"
            ] = "GREEN"

            track(
                "CH-MOD",
                "DeviceModemManager-GREEN",
            )

            # --------------------------------------------------
            # SPARKPLUG
            # --------------------------------------------------

            skills_path = (
                f"{storage_root}/seed/skills"
            )

            instance.sparkplug = SparkPlug(
                skills_root=skills_path,
                event_bus=instance.event_bus,
            )

            instance._module_flags[
                "SparkPlug"
            ] = "GREEN"

            track(
                "CH-MOD",
                "SparkPlug-GREEN",
            )

            # --------------------------------------------------
            # ACTION REGISTRY
            # --------------------------------------------------

            if instance.qbit_dialer is not None:

                set_qbit_control(
                    instance.qbit_dialer
                )

            if hasattr(
                instance,
                "admin_manager",
            ):

                if instance.admin_manager is not None:

                    set_admin_manager(
                        instance.admin_manager
                    )

            if (
                instance.sparkplug is not None
                and hasattr(
                    instance.sparkplug,
                    "module_registry",
                )
            ):

                try:

                    set_module_registry(
                        instance.sparkplug.module_registry
                    )

                except Exception as exc:

                    logger.warning(
                        "[SEEDOrchestrator] "
                        "Module registry binding failed: %s",
                        exc,
                    )

            track(
                "CH-MOD",
                "ActionRegistry-WIRED",
                priority="HIGH",
            )

            # --------------------------------------------------
            # AGENT MANAGER
            # --------------------------------------------------

            try:

                from seed.core.agent_manager import (
                    AgentManager,
                )

                instance.agent_manager = AgentManager(
                    actuator=instance.actuator_engine,
                    event_bus=instance.event_bus,
                    orchestrator_command=(
                        instance._command
                    ),
                )

                instance._module_flags[
                    "AgentManager"
                ] = "GREEN"

                track(
                    "CH-MOD",
                    "AgentManager-GREEN",
                )

            except Exception as exc:

                logger.warning(
                    "[SEEDOrchestrator] "
                    "AgentManager initialization failed: %s",
                    exc,
                )

                instance._module_flags[
                    "AgentManager"
                ] = "FAILED"

            # --------------------------------------------------
            # RE-BIND DEPENDENTS AFTER DIALER EXISTS
            # --------------------------------------------------

            instance.bind_runtime(
                qbit=instance.qbit,
                queue_loop=instance.queue_loop,
                qbit_dialer=instance.qbit_dialer,
                kernel_bus=instance.kernel_bus,
                track_system=instance.track_system,
                registry=instance.registry,
                node_registry=instance.node_registry,
                seedcore=instance.seedcore,
                fathud=instance.fathud,
                intent_engine=instance.intent_engine,
            )

            # --------------------------------------------------
            # READY
            # --------------------------------------------------

            try:
                instance.event_bus._orchestrator_ready = True
            except Exception:
                pass

            track(
                "CH-0",
                "ORCHESTRATOR-READY",
                priority="CRITICAL",
            )

            instance.running = True

            track(
                "CH-0",
                "BOOT-ASYNC-COMPLETE",
                priority="CRITICAL",
            )

            logger.info(
                "[SEEDOrchestrator] "
                "System orchestrator ONLINE"
            )

            return instance

    # ======================================================
    # ACTIVATION
    # ======================================================

    @classmethod
    def activate(cls, emit):

        cls.ACTIVE = True

        try:
            emit(
                "orchestrator.active",
                True,
            )
        except Exception:
            pass

        cls.start_thought_loops()

    # ======================================================
    # THOUGHT LOOPS
    # ======================================================

    @classmethod
    def start_thought_loops(cls):

        logger.info(
            "[ORCHESTRATOR] Thought loops started"
        )

    # ======================================================
    # COMMAND PROPERTY
    # ======================================================

    @property
    def command(self):

        return (
            self._command
            or self
        )

    # ======================================================
    # SHUTDOWN
    # ======================================================

    async def shutdown_async(self):

        track(
            "CH-SHUTDOWN",
            "P",
            priority="CRITICAL",
        )

        self.running = False
        self.ACTIVE = False

        # --------------------------------------------------
        # Stop only subordinate resources owned here.
        #
        # Authoritative QueueLoop / Dialer ownership remains
        # with the system boot/runtime authority.
        # --------------------------------------------------

        for name in (
            "device_modem_manager",
        ):

            obj = getattr(
                self,
                name,
                None,
            )

            if obj and hasattr(
                obj,
                "stop",
            ):

                try:
                    result = obj.stop()

                    if asyncio.iscoroutine(result):
                        await result

                except Exception as exc:

                    logger.warning(
                        "[SEEDOrchestrator] "
                        "%s shutdown failed: %s",
                        name,
                        exc,
                    )

        # --------------------------------------------------
        # Cancel tasks owned by Orchestrator.
        # --------------------------------------------------

        for task in list(self._tasks):

            if task and not task.done():

                task.cancel()

                try:
                    await task

                except asyncio.CancelledError:
                    pass

                except Exception:
                    pass

        self._tasks.clear()

        track(
            "CH-SHUTDOWN",
            "S",
            priority="CRITICAL",
        )

        logger.info(
            "[SEEDOrchestrator] Shutdown complete"
        )

    # ======================================================
    # SYNCHRONOUS SHUTDOWN
    # ======================================================

    def shutdown(self):

        try:
            loop = asyncio.get_running_loop()

        except RuntimeError:

            return asyncio.run(
                self.shutdown_async()
            )

        task = loop.create_task(
            self.shutdown_async()
        )

        return task


# ==========================================================
# END FILE
# ==========================================================