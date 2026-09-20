
# ==========================================================
# FILE: build_manager.py
# PATH: SEED_ROOT/seed/core/build_manager.py
# VERSION: 4.0 (SYSTEM-INTEGRATED | TRACK + QBIT + EVENT + HUD)
# UPDATED: 2026-08-31
# ==========================================================
# PURPOSE:
#   Build orchestration / execution subsystem.
#
# SYSTEM BOUNDARY:
#   BuildManager is NOT command authority.
#
#   Qbit
#      │
#      ├── carries identity / lineage / telemetry
#      │
#      ▼
#   BuildManager
#      │
#      ├── observes build requests
#      ├── manages build queue
#      ├── performs build work
#      ├── emits telemetry
#      └── reports state
#      │
#      ├──────────────► EventBus
#      ├──────────────► TrackSystem / ChannelID
#      ├──────────────► TrackedData
#      ├──────────────► HUD
#      ├──────────────► Watchdog
#      └──────────────► QbitDialer telemetry interface
#
# COMMAND AUTHORITY:
#   QbitDialer remains the sole command authority.
#   submit_command() remains the sole command admission path.
#   BuildManager never executes commands through a fallback queue.
#
# REGISTRY:
#   Registry / package __init__ discovery is used when available.
#   Dependencies are late-bound to reduce circular-import risk.
#
# ==========================================================

import asyncio
import inspect
import logging
import os
import threading
import time
import uuid
from collections import deque
from copy import deepcopy
from typing import Any, Dict, Optional

logger = logging.getLogger("BuildManager")
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            "[%(name)s] %(levelname)s: %(message)s"
        )
    )
    logger.addHandler(handler)


MODULE_ID = "BUILD-MANAGER"
MODULE_VERSION = "4.0"

# ==========================================================
# Event / Channel Constants
# ==========================================================

BUILD_QUEUED = "BUILD_QUEUED"
BUILD_STARTED = "BUILD_STARTED"
BUILD_COMPLETED = "BUILD_COMPLETED"
BUILD_FAILED = "BUILD_FAILED"
BUILD_CANCELLED = "BUILD_CANCELLED"
BUILD_STATUS = "BUILD_STATUS"

CHANNEL_BUILD = "SEED:BUILD:MANAGER"


# ==========================================================
# TrackID Generator
# ==========================================================

def gen_track_id(
    prefix: str = "BUILD",
    device: Any = None,
    channel: Optional[str] = None,
) -> str:
  
    try:
        device_id = getattr(device, "device_id", None)
    except Exception:
        device_id = None

    tag = device_id or channel or "GEN"

    return (
        f"{prefix}-"
        f"{str(tag).upper()}-"
        f"{uuid.uuid4().hex[:8]}"
    )


# ==========================================================
# BuildManager
# ==========================================================

class BuildManager:


    PRIORITY_MAP = {
        "high": 3,
        "medium": 2,
        "low": 1,
    }

    def __init__(
        self,
        storage_root: str = "./SEED_ROOT",
        hud_interface: Any = None,
        watchdog: Any = None,
        event_bus: Any = None,
        device_manager: Any = None,
        py_seed: Any = None,
        max_cpu: float = 70.0,
        max_mem: float = 75.0,
        memory_recovery: Any = None,
        qbit_dialer: Any = None,
        limp_mode: bool = False,
        track_system: Any = None,
        channel_manager: Any = None,
        channel_id: Any = None,
        registry: Any = None,
    ):
        self.storage_root = storage_root
        self.hud = hud_interface

        self.watchdog = watchdog
        self.event_bus = event_bus
        self.device_manager = device_manager

        self.max_cpu = float(max_cpu)
        self.max_mem = float(max_mem)

        self.memory_recovery = memory_recovery

        # IMPORTANT:
        # QbitDialer is injected only for telemetry/data integration.
        # BuildManager never becomes command authority.
        self.qbit_dialer = qbit_dialer

        self.limp_mode = bool(limp_mode)

        # Authoritative system dependencies when supplied by boot.
        self.track_system = track_system
        self.channel_manager = channel_manager
        self.channel_id = channel_id
        self.registry = registry

        # Build queue / lifecycle.
        self.queue = deque()
        self._queue_task = None
        self._queue_loop = None
        self._shutdown = False
        self._active_build = None

        self._queue_lock = threading.RLock()
        self._build_lock = threading.RLock()

        self._build_history = []
        self._build_counter = 0

        # py_seed is an optional execution backend.
        self.py_seed = py_seed
        self.py_seed_available = False

        # System registration.
        self.module_id = MODULE_ID
        self.module_version = MODULE_VERSION

        # Resolve optional dependencies without forcing circular imports.
        self._resolve_system_dependencies()

        # Initialize optional native/backend support.
        self._initialize_py_seed()

        # Register the module with available registry infrastructure.
        self._register_module()

        logger.info(
            "[BuildManager] initialized | "
            "module=%s | version=%s | "
            "track=%s | channel=%s | qbit=%s | event=%s",
            self.module_id,
            self.module_version,
            bool(self.track_system),
            bool(self.channel_manager or self.channel_id),
            bool(self.qbit_dialer),
            bool(self.event_bus),
        )

    # ======================================================
    # SYSTEM DISCOVERY
    # ======================================================

    def _resolve_system_dependencies(self):
        """
        Discover already-created system objects.

        This function does NOT construct competing system
        authorities. It only discovers objects supplied by
        the boot layer / registry / package.
        """

        # --------------------------------------------------
        # Registry discovery
        # --------------------------------------------------
        if self.registry is None:
            try:
                from seed.core import registry as core_registry

                self.registry = core_registry

            except Exception:
                self.registry = None

        # --------------------------------------------------
        # TrackSystem discovery
        # --------------------------------------------------
        if self.track_system is None:
            self.track_system = self._registry_get(
                "track_system",
                "TrackSystem",
                "tracksystem",
            )

        # --------------------------------------------------
        # ChannelManager discovery
        # --------------------------------------------------
        if self.channel_manager is None:
            self.channel_manager = self._registry_get(
                "channel_manager",
                "ChannelManager",
                "channels",
            )

        # --------------------------------------------------
        # ChannelID discovery
        # --------------------------------------------------
        if self.channel_id is None:
            try:
                from seed.core.channel_id import ChannelID

                self.channel_id = ChannelID

            except Exception:
                self.channel_id = None

    def _registry_get(self, *names):
      
        registry = self.registry

        if registry is None:
            return None

        for name in names:
            try:
                if isinstance(registry, dict):
                    value = registry.get(name)
                    if value is not None:
                        return value

                getter = getattr(registry, "get", None)

                if callable(getter):
                    value = getter(name)

                    if value is not None:
                        return value

                getter = getattr(
                    registry,
                    "get_component",
                    None,
                )

                if callable(getter):
                    value = getter(name)

                    if value is not None:
                        return value

                if hasattr(registry, name):
                    value = getattr(registry, name)

                    if value is not None:
                        return value

            except Exception:
                continue

        return None

    # ======================================================
    # REGISTRY REGISTRATION
    # ======================================================

    def _register_module(self):
   
        registry = self.registry

        if registry is None:
            return

        payload = {
            "module_id": self.module_id,
            "version": self.module_version,
            "instance": self,
            "type": "BUILD_MANAGER",
            "command_authority": False,
            "telemetry": True,
            "track_aware": bool(self.track_system),
            "qbit_aware": bool(self.qbit_dialer),
            "event_bus_aware": bool(self.event_bus),
        }

        methods = (
            "register",
            "register_module",
            "register_component",
            "register_node",
        )

        for method_name in methods:
            try:
                method = getattr(registry, method_name, None)

                if not callable(method):
                    continue

                try:
                    method(
                        self.module_id,
                        self,
                        metadata=payload,
                    )
                except TypeError:
                    try:
                        method(self.module_id, self)
                    except TypeError:
                        method(payload)

                logger.debug(
                    "[BuildManager] registry registration complete"
                )
                return

            except Exception as exc:
                logger.debug(
                    "[BuildManager] registry registration "
                    "via %s failed: %s",
                    method_name,
                    exc,
                )

    # ======================================================
    # PY_SEED INITIALIZATION
    # ======================================================

    def _initialize_py_seed(self):
    
        if self.py_seed is None:
            try:
                from seed.core.py_seed import PySeedContext

                self.py_seed = PySeedContext

            except Exception as exc:
                logger.debug(
                    "[BuildManager] py_seed unavailable: %s",
                    exc,
                )
                return

        context = self.py_seed

        try:
            if hasattr(context, "boot_sequence"):
                context.boot_sequence()

            if hasattr(context, "sandbox_monitor"):
                context.sandbox_monitor()

            if hasattr(context, "load_dictionary"):
                context.load_dictionary()

            self.py_seed_available = True

            logger.info(
                "[BuildManager] py_seed backend available"
            )

        except Exception as exc:
            self.py_seed_available = False

            logger.warning(
                "[BuildManager] py_seed initialization failed: %s",
                exc,
            )

    # ======================================================
    # QUEUE LIFECYCLE
    # ======================================================

    async def start(self):
    
        if self._shutdown:
            logger.warning(
                "[BuildManager] start ignored after shutdown"
            )
            return

        if self._queue_task and not self._queue_task.done():
            return

        try:
            self._queue_loop = asyncio.get_running_loop()

        except RuntimeError:
            logger.warning(
                "[BuildManager] start() requires a running "
                "asyncio event loop"
            )
            return

        self._queue_task = self._queue_loop.create_task(
            self._process_queue()
        )

        self._publish_status("STARTED")

        logger.info("[BuildManager] queue worker started")

    def start_background(self):
  
        try:
            loop = asyncio.get_running_loop()

            if loop.is_running():
                self._queue_task = loop.create_task(
                    self._process_queue()
                )
                return self._queue_task

        except RuntimeError:
            pass

        logger.warning(
            "[BuildManager] start_background() requires "
            "an existing runtime loop"
        )

        return None

    # ======================================================
    # QUEUE BUILD REQUEST
    # ======================================================

    async def request_build(
        self,
        file_path,
        priority="medium",
        behavior="default",
        device_name=None,
        channel=None,
        track_id=None,
    ):

        if self._shutdown:
            raise RuntimeError(
                "BuildManager is shut down"
            )

        if not file_path:
            raise ValueError(
                "file_path is required"
            )

        priority_key = str(priority).lower()

        level = self.PRIORITY_MAP.get(
            priority_key,
            self.PRIORITY_MAP["medium"],
        )

        device = None

        if (
            device_name
            and self.device_manager
            and hasattr(
                self.device_manager,
                "get_device_by_name",
            )
        ):
            try:
                device = (
                    self.device_manager
                    .get_device_by_name(device_name)
                )
            except Exception as exc:
                logger.debug(
                    "[BuildManager] device lookup failed: %s",
                    exc,
                )

        channel = channel or CHANNEL_BUILD

        track_id = (
            track_id
            or self._create_track(
                channel=channel,
                device=device,
            )
        )

        # --------------------------------------------------
        # Memory-aware priority adjustment.
        # --------------------------------------------------
        if self.memory_recovery and self.qbit_dialer:
            try:
                memory_importance = getattr(
                    self.qbit_dialer,
                    "memory_importance",
                    None,
                )

                if callable(memory_importance):
                    result = memory_importance(file_path)

                    if inspect.isawaitable(result):
                        mem_score = await result
                    else:
                        mem_score = result

                    if (
                        float(mem_score) < 0.3
                        and self.limp_mode
                    ):
                        level = max(1, level - 1)

            except Exception as exc:
                logger.debug(
                    "[BuildManager] memory scoring failed: %s",
                    exc,
                )

        item = (
            level,
            time.time(),
            file_path,
            track_id,
            behavior,
            device,
            channel,
        )

        with self._queue_lock:
            self.queue.append(item)
            self.queue = deque(
                sorted(
                    self.queue,
                    key=lambda x: (-x[0], x[1]),
                )
            )

            self._build_counter += 1

        logger.info(
            "[%s] Build queued: %s | priority=%s",
            track_id,
            file_path,
            priority_key,
        )

        self._notify_hud(
            f"[{track_id}] Build queued: "
            f"{file_path} "
            f"(priority={priority_key})"
        )

        self._publish_event(
            BUILD_QUEUED,
            track_id,
            file_path,
            priority_key,
            device=device,
            channel=channel,
        )

        self._emit_tracked_event(
            BUILD_QUEUED,
            channel,
            {
                "file_path": file_path,
                "priority": priority_key,
                "behavior": behavior,
            },
            track_id=track_id,
        )

        return track_id

    # ======================================================
    # TRACK SYSTEM CONNECTION
    # ======================================================

    def _create_track(self, channel, device=None):
   
        track_system = self.track_system

        if track_system is not None:
            for method_name in (
                "create_track",
                "generate_track",
                "new_track",
                "register_track",
            ):
                try:
                    method = getattr(
                        track_system,
                        method_name,
                        None,
                    )

                    if not callable(method):
                        continue

                    try:
                        result = method(
                            channel=channel,
                            module=self.module_id,
                        )
                    except TypeError:
                        try:
                            result = method(channel)
                        except TypeError:
                            result = method()

                    if result:
                        return str(result)

                except Exception as exc:
                    logger.debug(
                        "[BuildManager] TrackSystem %s failed: %s",
                        method_name,
                        exc,
                    )

        return gen_track_id(
            prefix="BUILD",
            device=device,
            channel=channel,
        )

    # ======================================================
    # PROCESS QUEUE
    # ======================================================

    async def _process_queue(self):
 
        while not self._shutdown:
            try:
                if self.queue and self._active_build is None:

                    if self._system_overloaded():
                        await asyncio.sleep(1.0)
                        continue

                    with self._queue_lock:
                        if not self.queue:
                            continue

                        (
                            level,
                            ts,
                            file_path,
                            track_id,
                            behavior,
                            device,
                            channel,
                        ) = self.queue.popleft()

                    await self._execute_build(
                        file_path=file_path,
                        priority_level=level,
                        track_id=track_id,
                        behavior=behavior,
                        device=device,
                        channel=channel,
                    )

                await asyncio.sleep(0.05)

            except asyncio.CancelledError:
                logger.info(
                    "[BuildManager] queue worker cancelled"
                )
                raise

            except Exception as exc:
                logger.exception(
                    "[BuildManager] queue error: %s",
                    exc,
                )

                await asyncio.sleep(0.25)

    # ======================================================
    # EXECUTE BUILD
    # ======================================================

    async def _execute_build(
        self,
        file_path,
        priority_level,
        track_id,
        behavior,
        device=None,
        channel=None,
    ):
        self._active_build = file_path
        start_time = time.time()

        logger.info(
            "[%s] Starting build: %s | priority=%s",
            track_id,
            file_path,
            priority_level,
        )

        self._notify_hud(
            f"[{track_id}] Build started: "
            f"{file_path} "
            f"(priority={priority_level})"
        )

        self._publish_event(
            BUILD_STARTED,
            track_id,
            file_path,
            priority_level,
            device=device,
            channel=channel,
        )

        self._emit_tracked_event(
            BUILD_STARTED,
            channel,
            {"file_path": file_path},
            track_id=track_id,
        )

        try:
            # --------------------------------------------------
            # Optional py_seed backend.
            # --------------------------------------------------
            if self.py_seed_available and self.py_seed:
                try:
                    buffer = bytearray(2048)

                    generator = getattr(
                        self.py_seed,
                        "generate_binary",
                        None,
                    )

                    if callable(generator):
                        generator(
                            behavior,
                            buffer,
                            len(buffer),
                        )

                    monitor = getattr(
                        self.py_seed,
                        "sandbox_monitor",
                        None,
                    )

                    if callable(monitor):
                        monitor()

                except Exception as exc:
                    logger.warning(
                        "[%s] py_seed execution failed: %s",
                        track_id,
                        exc,
                    )

            # --------------------------------------------------
            # Memory recovery.
            # --------------------------------------------------
            if self.memory_recovery:
                try:
                    recover = getattr(
                        self.memory_recovery,
                        "scan_and_recover",
                        None,
                    )

                    if callable(recover):
                        recovered = recover(
                            max_events=5,
                            limp_mode=self.limp_mode,
                        )

                        if inspect.isawaitable(recovered):
                            recovered = await recovered

                        logger.info(
                            "[%s] Memory recovery applied: %s",
                            track_id,
                            recovered,
                        )

                except Exception as exc:
                    logger.warning(
                        "[%s] Memory recovery failed: %s",
                        track_id,
                        exc,
                    )

            # --------------------------------------------------
            # Build execution window.
            #
            # Actual build backends may be connected here.
            # This manager does not invent a command backend.
            # --------------------------------------------------
            await asyncio.sleep(
                0.5 if self.limp_mode else 2.0
            )

            duration = time.time() - start_time

            record = {
                "file_path": file_path,
                "priority": priority_level,
                "timestamp": time.time(),
                "duration": duration,
                "track_id": track_id,
                "behavior": behavior,
                "device": (
                    getattr(device, "device_id", None)
                    if device
                    else None
                ),
                "channel": channel,
                "status": "COMPLETED",
            }

            self._build_history.append(record)

            logger.info(
                "[%s] Build completed: %s (%.2fs)",
                track_id,
                file_path,
                duration,
            )

            self._notify_hud(
                f"[{track_id}] Build completed: "
                f"{file_path} ({duration:.2f}s)"
            )

            self._publish_event(
                BUILD_COMPLETED,
                track_id,
                file_path,
                priority_level,
                device=device,
                channel=channel,
            )

            self._emit_tracked_event(
                BUILD_COMPLETED,
                channel,
                {
                    "file_path": file_path,
                    "duration": duration,
                },
                track_id=track_id,
            )

        except asyncio.CancelledError:
            logger.warning(
                "[%s] Build cancelled: %s",
                track_id,
                file_path,
            )

            self._publish_event(
                BUILD_CANCELLED,
                track_id,
                file_path,
                priority_level,
                device=device,
                channel=channel,
            )

            self._emit_tracked_event(
                BUILD_CANCELLED,
                channel,
                {"file_path": file_path},
                track_id=track_id,
            )

            raise

        except Exception as exc:
            logger.exception(
                "[%s] Build failed: %s -> %s",
                track_id,
                file_path,
                exc,
            )

            self._notify_hud(
                f"[{track_id}] Build failed: "
                f"{file_path} -> {exc}"
            )

            self._publish_event(
                BUILD_FAILED,
                track_id,
                file_path,
                priority_level,
                device=device,
                channel=channel,
                error=str(exc),
            )

            self._emit_tracked_event(
                BUILD_FAILED,
                channel,
                {
                    "file_path": file_path,
                    "error": str(exc),
                },
                track_id=track_id,
            )

        finally:
            self._active_build = None

    # ======================================================
    # HUD
    # ======================================================

    def _notify_hud(self, message):
        if self.hud is None:
            return

        try:
            method = getattr(
                self.hud,
                "hud_system_message",
                None,
            )

            if callable(method):
                method(message)
                return

            method = getattr(
                self.hud,
                "system_message",
                None,
            )

            if callable(method):
                method(message)

        except Exception as exc:
            logger.debug(
                "[BuildManager] HUD notification failed: %s",
                exc,
            )

    # ======================================================
    # EVENT BUS
    # ======================================================

    def _publish_event(
        self,
        event_type,
        track_id,
        file_path,
        priority,
        device=None,
        channel=None,
        error=None,
    ):
        payload = {
            "module_id": self.module_id,
            "event": event_type,
            "track_id": track_id,
            "file_path": file_path,
            "priority": priority,
            "timestamp": time.time(),
            "device": (
                getattr(device, "device_id", None)
                if device
                else None
            ),
            "channel": channel,
        }

        if error:
            payload["error"] = error

        self._event_emit(
            event_type,
            payload,
        )

    def _event_emit(self, event_type, payload):
 
        bus = self.event_bus

        if bus is None:
            return

        try:
            publish = getattr(
                bus,
                "publish",
                None,
            )

            if callable(publish):
                try:
                    publish(
                        event_type,
                        payload=payload,
                    )
                except TypeError:
                    publish(
                        event_type,
                        payload,
                    )
                return

            emit = getattr(
                bus,
                "emit",
                None,
            )

            if callable(emit):
                try:
                    emit(
                        event_type,
                        payload=payload,
                    )
                except TypeError:
                    emit(
                        event_type,
                        payload,
                    )

        except Exception as exc:
            logger.debug(
                "[BuildManager] EventBus emission failed: %s",
                exc,
            )

    # ======================================================
    # TRACKED DATA / QBIT TELEMETRY
    # ======================================================

    def _emit_tracked_event(
        self,
        event,
        channel,
        payload,
        track_id=None,
    ):
    
        try:
            from seed.core.tracked_data import TrackedData

        except Exception as exc:
            logger.debug(
                "[BuildManager] TrackedData unavailable: %s",
                exc,
            )
            return

        telemetry = dict(payload)

        telemetry.update(
            {
                "module_id": self.module_id,
                "track_id": track_id,
                "timestamp": time.time(),
            }
        )

        try:
            emitter = getattr(
                TrackedData,
                "emit_event",
                None,
            )

            if not callable(emitter):
                return

            kwargs = {
                "event": event,
                "channel": channel,
                "payload": telemetry,
            }

            # QbitDialer is an injected telemetry/data sink only.
            if self.qbit_dialer is not None:
                kwargs["qbit_callback"] = (
                    self.qbit_dialer
                )

            try:
                emitter(**kwargs)

            except TypeError:
                kwargs.pop(
                    "qbit_callback",
                    None,
                )
                emitter(**kwargs)

        except Exception as exc:
            logger.debug(
                "[BuildManager] TrackedData emission failed: %s",
                exc,
            )

    # ======================================================
    # CHANNEL / TRACK SYNCHRONIZATION
    # ======================================================

    def _sync_channel(self, channel, track_id):
     
        if not channel:
            return

        # --------------------------------------------------
        # ChannelManager
        # --------------------------------------------------
        manager = self.channel_manager

        if manager is not None:
            try:
                register = getattr(
                    manager,
                    "register_channel",
                    None,
                )

                if callable(register):
                    try:
                        register(
                            path=channel,
                            tracks=[track_id],
                            metadata={
                                "module": self.module_id,
                            },
                        )
                    except TypeError:
                        try:
                            register(
                                channel,
                                tracks=[track_id],
                            )
                        except Exception:
                            pass

            except Exception as exc:
                logger.debug(
                    "[BuildManager] channel sync failed: %s",
                    exc,
                )

        # --------------------------------------------------
        # ChannelID
        # --------------------------------------------------
        cid = self.channel_id

        if cid is not None:
            try:
                ensure = getattr(
                    cid,
                    "_ensure_registered",
                    None,
                )

                if callable(ensure):
                    ensure(channel)

                next_method = getattr(
                    cid,
                    "next",
                    None,
                )

                if callable(next_method):
                    try:
                        next_method(
                            channel,
                            track_id=track_id,
                        )
                    except TypeError:
                        try:
                            next_method(channel)
                        except Exception:
                            pass

            except Exception as exc:
                logger.debug(
                    "[BuildManager] ChannelID sync failed: %s",
                    exc,
                )

    # ======================================================
    # SYSTEM OVERLOAD
    # ======================================================

    def _system_overloaded(self):
        try:
            import psutil

            cpu = psutil.cpu_percent(
                interval=0.1
            )

            mem = psutil.virtual_memory().percent

            self._record_watchdog(
                cpu=cpu,
                mem=mem,
            )

            if (
                cpu > self.max_cpu
                or mem > self.max_mem
            ):
                logger.warning(
                    "[BuildManager] Overload: "
                    "CPU=%.1f%% MEM=%.1f%%",
                    cpu,
                    mem,
                )

                self._publish_status(
                    "OVERLOADED",
                    cpu=cpu,
                    mem=mem,
                )

                return True

            return False

        except Exception as exc:
            logger.warning(
                "[BuildManager] Load check failed: %s",
                exc,
            )
            return False

    def _record_watchdog(self, cpu, mem):
        watchdog = self.watchdog

        if watchdog is None:
            return

        payload = {
            "cpu": cpu,
            "mem": mem,
            "timestamp": time.time(),
            "module": self.module_id,
        }

        try:
            heartbeats = getattr(
                watchdog,
                "_heartbeats",
                None,
            )

            if isinstance(heartbeats, dict):
                heartbeats[self.module_id] = payload
                return

            record = getattr(
                watchdog,
                "record_heartbeat",
                None,
            )

            if callable(record):
                record(
                    self.module_id,
                    payload,
                )

        except Exception as exc:
            logger.debug(
                "[BuildManager] Watchdog update failed: %s",
                exc,
            )

    # ======================================================
    # STATUS
    # ======================================================

    def _publish_status(self, state, **extra):
        payload = {
            "module_id": self.module_id,
            "state": state,
            "active_build": self._active_build,
            "queue_depth": len(self.queue),
            "timestamp": time.time(),
        }

        payload.update(extra)

        self._event_emit(
            BUILD_STATUS,
            payload,
        )

        self._notify_hud(
            f"[{self.module_id}] STATUS={state} "
            f"QUEUE={len(self.queue)}"
        )

    # ======================================================
    # BUILD HISTORY
    # ======================================================

    def get_build_history(self):
        with self._build_lock:
            return deepcopy(
                self._build_history
            )

    def get_status(self) -> Dict[str, Any]:
        return {
            "module_id": self.module_id,
            "version": self.module_version,
            "active_build": self._active_build,
            "queue_depth": len(self.queue),
            "history_count": len(self._build_history),
            "limp_mode": self.limp_mode,
            "py_seed_available": self.py_seed_available,
            "track_system": bool(self.track_system),
            "channel_manager": bool(self.channel_manager),
            "channel_id": bool(self.channel_id),
            "event_bus": bool(self.event_bus),
            "qbit_dialer": bool(self.qbit_dialer),
            "command_authority": False,
        }

    # ======================================================
    # SHUTDOWN
    # ======================================================

    async def shutdown(self):
        if self._shutdown:
            return

        self._shutdown = True

        if self._queue_task:
            self._queue_task.cancel()

            try:
                await asyncio.gather(
                    self._queue_task,
                    return_exceptions=True,
                )
            except Exception:
                pass

        self._queue_task = None

        self._publish_status(
            "SHUTDOWN",
        )

        logger.info(
            "[BuildManager] Shutdown complete"
        )


# ==========================================================
# MODULE EXPORTS
# ==========================================================

__all__ = [
    "BuildManager",
    "gen_track_id",
    "BUILD_QUEUED",
    "BUILD_STARTED",
    "BUILD_COMPLETED",
    "BUILD_FAILED",
    "BUILD_CANCELLED",
    "BUILD_STATUS",
]
# ==========================================================
# END FILE
# ==========================================================

