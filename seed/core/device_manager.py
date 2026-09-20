# ==========================================================
# FILE: device_manager.py
# PATH: SEED_ROOT/seed/core/device_manager.py
#
# SEED Device Manager v6.0
# STATUS: FULL-BOOT-STABILIZATION / QBIT-SYNC / RUNTIME-SAFE
# UPDATED: 2026-09-02
#
# ==========================================================
# PURPOSE
# ==========================================================
# Central device registration, lifecycle management, polling,
# I/O, event routing, TrackID lineage, Qbit gating, and
# graceful shutdown.
#
# DeviceManager is NOT command authority.
#
# QbitDialer remains the sole command authority.
# submit_command() remains the authoritative command admission
# path.
#
# DeviceManager provides the device-side actuator/service layer
# that QbitDialer may invoke after command admission.
#
# ==========================================================
# AUTHORITY / LAYER
# ==========================================================
# CORE DEVICE MANAGEMENT LAYER
#
# Authority:
#   QbitDialer -> command authority
#
# Execution:
#   QbitQueueLoop -> authoritative execution loop
#
# Device layer:
#   DeviceManager -> device I/O/lifecycle service
#
# Identity:
#   DeviceRegistry / SRegistry where available
#
# Tracking:
#   TrackIDManager / TrackSystem
#
# Transport:
#   SEEDEventBus
#
# Pulse:
#   Heartbeat remains read-only system pulse/output authority
#
# ==========================================================
# BOOT CONTRACT
# ==========================================================
# DeviceManager must:
#
# 1. Never crash because a device has no read/send method.
# 2. Never await a non-awaitable result.
# 3. Support sync and async device implementations.
# 4. Keep LocalDevice alive as a valid core/null device.
# 5. Preserve TrackIDManager authority.
# 6. Preserve ChannelID/EventBus routing.
# 7. Respect Qbit system-go gating.
# 8. Flush gated device data when Qbit allows processing.
# 9. Shut polling down cleanly.
# 10. Never create a fake Qbit object by using the Qbit class
#     itself as an instance.
# 11. Expose device lifecycle controls to the command layer
#     without becoming command authority.
# 12. Preserve Device lifecycle semantics.
# 13. Avoid duplicate device registration where possible.
# 14. Propagate task/track/Qbit lineage into device telemetry.
# 15. Never create a second command queue or execution worker.
# 16. Never directly invoke QbitDialer.submit_command().
# 17. Never directly invoke Heartbeat control.
# 18. Never create a replacement registry when an authoritative
#     registry is available.
#
# ==========================================================

from __future__ import annotations

import asyncio
import inspect
import logging
import socket
import time
import uuid

from collections import deque
from dataclasses import dataclass, field
from typing import (
    Any,
    Callable,
    Deque,
    Dict,
    List,
    Optional,
    Sequence,
)

# ==========================================================
# CORE IMPORTS
# ==========================================================

from seed.core.device import Device, DeviceRegistry
from seed.core.track_id_manager import TrackIDManager
from seed.core.channel_id import ChannelID
from seed.core.event_bus import SEEDEventBus
from seed.core.tracked_data import TrackedData
from seed.core.qbit import Qbit
from seed.core.track_system import TrackSystem

# ==========================================================
# OPTIONAL HARDWARE LAYERS
# ==========================================================

try:
    import serial
    import serial.tools.list_ports
except Exception:
    serial = None

try:
    import bluetooth
except Exception:
    bluetooth = None

# ==========================================================
# OPTIONAL AUTHORITATIVE REGISTRY
# ==========================================================
#
# DeviceManager does not create a second registry.
#
# If the SEED SRegistry implementation is available, it is
# observed/updated through its public API only.
#
# Import failures are intentionally non-fatal because the
# DeviceManager must remain usable during early boot.
# ==========================================================

try:
    from seed.core.registry import (
        SRegistry,
        SEED_KERNEL_REGISTRY,
    )
except Exception:
    SRegistry = None
    SEED_KERNEL_REGISTRY = None

try:
    from seed.systemutils.registry import (
        SRegistry as SystemSRegistry,
        SEED_KERNEL_REGISTRY as SYSTEM_SEED_KERNEL_REGISTRY,
    )
except Exception:
    SystemSRegistry = None
    SYSTEM_SEED_KERNEL_REGISTRY = None


# ==========================================================
# LOGGER
# ==========================================================

logger = logging.getLogger("DeviceManager")
logger.setLevel(logging.INFO)


# ==========================================================
# HELPERS
# ==========================================================

async def _resolve_device_call(
    device: Any,
    method_name: str,
    *args,
    **kwargs,
) -> Any:

    if device is None:
        return None

    method = getattr(device, method_name, None)

    if method is None or not callable(method):
        return None

    result = method(*args, **kwargs)

    if inspect.isawaitable(result):
        return await result

    return result


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value

    return value


def _safe_channel_value() -> str:
    try:
        return str(ChannelID.DEVICE.value)
    except Exception:
        return "DEVICE"


def _safe_track_id(
    skill_name: str,
    priority: int = 50,
) -> str:
    try:
        return TrackIDManager.generate(
            channel_marker="device",
            skill_name=skill_name,
            priority=priority,
        )
    except Exception:
        return (
            f"device_DEVICE_{skill_name.upper()}_"
            f"{uuid.uuid4().hex[:8].upper()}"
        )


# ==========================================================
# LOCAL NULL DEVICE
# ==========================================================

class LocalCoreDevice(Device):

    def __init__(self):
        super().__init__(
            name="LocalDevice",
            type="core",
            status="ONLINE",
        )

        self.device_id = f"LOCAL_{socket.gethostname()}"

        for capability in (
            "compute",
            "hud_output",
            "network",
            "core",
            "device_control",
            "lifecycle",
        ):
            try:
                self.add_capability(capability)
            except Exception:
                pass

    async def read(self):
        return None

    async def send(self, data):
        return False


# ==========================================================
# DUMMY DEVICE
# ==========================================================

class DummyDevice(Device):

    def __init__(self):
        super().__init__(
            name="DUMMY_DEVICE",
            type="dummy",
            status="OFF",
        )

        self.device_id = (
            f"DUMMY_{uuid.uuid4().hex[:12]}"
        )

        for capability in (
            "fallback",
            "device_control",
            "lifecycle",
        ):
            try:
                self.add_capability(capability)
            except Exception:
                pass

    async def read(self):
        return None

    async def send(self, data):
        return False


# ==========================================================
# DEVICE RUNTIME STATE
# ==========================================================

@dataclass
class DeviceRuntimeState:
    reads: int = 0
    sends: int = 0
    errors: int = 0

    last_read: float = 0.0
    last_send: float = 0.0
    last_error: float = 0.0

    last_error_message: Optional[str] = None

    online: bool = True

    lifecycle: str = "ONLINE"
    last_control: Optional[str] = None
    last_control_ts: float = 0.0

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )


# ==========================================================
# MANAGED DEVICE
# ==========================================================

class ManagedDevice:

    def __init__(
        self,
        track_id: Optional[str] = None,
        task_id: Optional[str] = None,
        device: Any = None,
        event_bus: Optional[SEEDEventBus] = None,
        fat_layer: Any = None,
        name: Optional[str] = None,
        track: Any = None,
        device_id: Optional[str] = None,
        qbit: Optional[Qbit] = None,
        device_type: str = "generic",
        min_update_interval: float = 0.05,
        capabilities: Optional[Sequence[str]] = None,
        **kwargs,
    ):
        self.name = (
            name
            or getattr(device, "name", None)
            or "ManagedDevice"
        )

        self.device = device

        self.device_id = (
            device_id
            or getattr(device, "device_id", None)
            or f"DEVICE_{uuid.uuid4().hex[:12]}"
        )

        self.device_type = (
            device_type
            or getattr(device, "type", None)
            or "generic"
        )

        self.event_bus = event_bus
        self.fat_layer = fat_layer

        self.min_update_interval = max(
            0.01,
            float(min_update_interval),
        )

        self.qbit = qbit
        self.track = track
        self.track_id = track_id
        self.task_id = task_id

        self._queue: Deque[TrackedData] = deque()

        self._last_data: Any = None
        self._last_event_ts = 0.0

        self._capabilities: List[str] = list(
            capabilities or []
        )

        self.metadata: Dict[str, Any] = dict(kwargs)

        self.runtime = DeviceRuntimeState()

        self._monitor_task: Optional[
            asyncio.Task
        ] = None

        self._stopping = False
        self._shutdown = False

        self._io_lock = asyncio.Lock()

    # ======================================================
    # IDENTITY
    # ======================================================

    @property
    def id(self) -> str:
        return str(
            getattr(
                self.device,
                "device_id",
                self.device_id,
            )
        )

    # ======================================================
    # CAPABILITIES
    # ======================================================

    def add_capability(
        self,
        capability: str,
    ):
        if not capability:
            return

        capability = str(capability)

        if capability not in self._capabilities:
            self._capabilities.append(capability)

    @property
    def capabilities(self) -> List[str]:
        device_caps = getattr(
            self.device,
            "capabilities",
            None,
        )

        if device_caps:
            try:
                return list(device_caps)
            except Exception:
                pass

        return list(self._capabilities)

    def available_controls(self) -> List[str]:

        controls = []

        for action in (
            "run",
            "stop",
            "pause",
            "resume",
            "activate",
            "deactivate",
            "refresh",
            "status",
            "shutdown",
        ):
            method = getattr(self.device, action, None)

            if callable(method):
                controls.append(action)

        if callable(getattr(self.device, "control", None)):
            for action in (
                "run",
                "stop",
                "pause",
                "resume",
                "activate",
                "deactivate",
                "refresh",
                "status",
                "shutdown",
            ):
                if action not in controls:
                    controls.append(action)

        # ManagedDevice always provides these service actions.
        for action in (
            "read",
            "send",
        ):
            if action not in controls:
                controls.append(action)

        return controls

    def control_capabilities(self) -> Dict[str, Any]:
        return {
            "device_id": self.id,
            "name": self.name,
            "device_type": self.device_type,
            "controls": self.available_controls(),
            "capabilities": self.capabilities,
            "managed": True,
            "authority": "QbitDialer",
        }

    # ======================================================
    # STATUS
    # ======================================================

    @property
    def status(self) -> str:
        status = getattr(
            self.device,
            "status",
            None,
        )

        if status is None:
            return (
                self.runtime.lifecycle
                if self.runtime.lifecycle
                else (
                    "ONLINE"
                    if self.runtime.online
                    else "OFFLINE"
                )
            )

        return str(status)

    # ======================================================
    # METADATA
    # ======================================================

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "name": self.name,
            "device_type": self.device_type,
            "status": self.status,
            "capabilities": self.capabilities,
            "controls": self.available_controls(),
            "min_update_interval": (
                self.min_update_interval
            ),
            "track_id": self.track_id,
            "task_id": self.task_id,
            "runtime": {
                "reads": self.runtime.reads,
                "sends": self.runtime.sends,
                "errors": self.runtime.errors,
                "last_read": self.runtime.last_read,
                "last_send": self.runtime.last_send,
                "last_error": self.runtime.last_error,
                "last_error_message": (
                    self.runtime.last_error_message
                ),
                "online": self.runtime.online,
                "lifecycle": self.runtime.lifecycle,
                "last_control": (
                    self.runtime.last_control
                ),
                "last_control_ts": (
                    self.runtime.last_control_ts
                ),
            },
            "metadata": dict(self.metadata),
        }

    # ======================================================
    # PRIORITY
    # ======================================================

    def _get_priority(self) -> int:
        priority_hint = getattr(
            self.device,
            "priority_hint",
            None,
        )

        if callable(priority_hint):
            try:
                value = priority_hint()
            except Exception:
                value = 50
        else:
            value = getattr(
                self.device,
                "priority",
                50,
            )

        try:
            return int(value)
        except Exception:
            return 50

    # ======================================================
    # QBIT GATE
    # ======================================================

    def _qbit_allows_processing(
        self,
        qbit: Optional[Qbit],
    ) -> bool:

        if qbit is None:
            return True

        # Never instantiate Qbit here.
        #
        # This method only observes the supplied Qbit
        # instance.

        if getattr(
            qbit,
            "_system_go_flag",
            False,
        ):
            return True

        for attr in (
            "system_go",
            "system_go_flag",
            "go",
            "ready",
        ):
            value = getattr(
                qbit,
                attr,
                None,
            )

            if isinstance(value, bool) and value:
                return True

        return False

    # ======================================================
    # DEVICE LIFECYCLE
    # ======================================================

    async def control(
        self,
        action: str,
        **kwargs,
    ) -> Any:

        action = str(
            action or ""
        ).strip().lower()

        aliases = {
            "start": "run",
            "resume_run": "run",
            "enable": "activate",
            "disable": "deactivate",
            "halt": "stop",
            "reload": "refresh",
        }

        action = aliases.get(
            action,
            action,
        )

        method = getattr(
            self.device,
            action,
            None,
        )

        if callable(method):
            result = method(**kwargs)

            if inspect.isawaitable(result):
                result = await result

            self.runtime.last_control = action
            self.runtime.last_control_ts = time.time()

            if action in (
                "run",
                "resume",
                "activate",
            ):
                self.runtime.lifecycle = "RUNNING"
                self.runtime.online = True

            elif action == "pause":
                self.runtime.lifecycle = "PAUSED"
                self.runtime.online = True

            elif action == "stop":
                self.runtime.lifecycle = "STOPPED"
                self.runtime.online = False

            elif action == "deactivate":
                self.runtime.lifecycle = "INACTIVE"
                self.runtime.online = False

            elif action == "shutdown":
                self.runtime.lifecycle = "SHUTDOWN"
                self.runtime.online = False
                self._shutdown = True
                self._stopping = True

            return result

        # Legacy device implementations may only expose a
        # generic control() method.

        generic_control = getattr(
            self.device,
            "control",
            None,
        )

        if callable(generic_control):
            result = generic_control(
                action,
                **kwargs,
            )

            if inspect.isawaitable(result):
                result = await result

            self.runtime.last_control = action
            self.runtime.last_control_ts = time.time()

            return result

        if action == "status":
            return self.to_dict()

        raise AttributeError(
            f"Device '{self.name}' does not support "
            f"control action '{action}'"
        )

    async def run(self, **kwargs):
        return await self.control(
            "run",
            **kwargs,
        )

    async def pause(self, **kwargs):
        return await self.control(
            "pause",
            **kwargs,
        )

    async def resume(self, **kwargs):
        return await self.control(
            "resume",
            **kwargs,
        )

    async def activate(self, **kwargs):
        return await self.control(
            "activate",
            **kwargs,
        )

    async def deactivate(self, **kwargs):
        return await self.control(
            "deactivate",
            **kwargs,
        )

    async def refresh(self, **kwargs):
        return await self.control(
            "refresh",
            **kwargs,
        )

    # ======================================================
    # READ
    # ======================================================

    async def read(
        self,
        qbit: Optional[Qbit] = None,
        parent_track_id: Optional[str] = None,
        task_id: Optional[str] = None,
    ):

        qbit = qbit or self.qbit

        if task_id is not None:
            self.task_id = task_id

        async with self._io_lock:

            if (
                self._stopping
                or self._shutdown
            ):
                return None

            # Respect Device lifecycle if exposed.
            lifecycle = str(
                getattr(
                    self.device,
                    "lifecycle_state",
                    getattr(
                        self.device,
                        "runtime_state",
                        "",
                    ),
                )
                or ""
            ).upper()

            if lifecycle in (
                "STOPPED",
                "INACTIVE",
                "SHUTDOWN",
                "OFF",
            ):
                return None

            if lifecycle == "PAUSED":
                return None

            try:
                data = await _resolve_device_call(
                    self.device,
                    "read",
                )

                self.runtime.reads += 1
                self.runtime.last_read = time.time()
                self.runtime.online = True

                if data is None:
                    return None

                now = time.time()

                # Deduplicate identical data.
                if data == self._last_data:
                    return None

                # Rate limit.
                if (
                    now - self._last_event_ts
                    < self.min_update_interval
                ):
                    return None

                self._last_data = data
                self._last_event_ts = now

                priority = self._get_priority()

                track_id = _safe_track_id(
                    "input",
                    priority,
                )

                payload = {
                    "device_id": self.id,
                    "device_name": self.name,
                    "device_type": self.device_type,
                    "port": getattr(
                        self.device,
                        "port",
                        None,
                    ),
                    "data": data,
                    "capabilities": self.capabilities,
                    "status": self.status,
                    "timestamp": now,
                    "track_id": track_id,
                    "parent_track_id": (
                        parent_track_id
                    ),
                    "task_id": (
                        task_id or self.task_id
                    ),
                    "qbit_id": getattr(
                        qbit,
                        "qbit_id",
                        None,
                    ),
                }

                if self.fat_layer:
                    try:
                        self.fat_layer.append_log(
                            {
                                "action": "read",
                                **payload,
                            },
                            source="DeviceManager",
                        )
                    except Exception as fat_error:
                        logger.debug(
                            "[ManagedDevice] FAT log "
                            "failed (%s): %s",
                            self.name,
                            fat_error,
                        )

                td = TrackedData(
                    payload=payload,
                    track_id=track_id,
                    parent_id=parent_track_id,
                    source_id="device",
                    channel=_safe_channel_value(),
                    priority=priority,
                )

                # ======================================
                # QBIT GATE
                # ======================================

                if not self._qbit_allows_processing(
                    qbit
                ):
                    self._queue.append(td)

                    logger.debug(
                        "[ManagedDevice] Qbit gate "
                        "holding input | device=%s | "
                        "track=%s",
                        self.name,
                        track_id,
                    )

                    return data

                # ======================================
                # FLUSH HELD DATA
                # ======================================

                await self._flush_queue()

                # ======================================
                # CURRENT EVENT
                # ======================================

                self._publish_input(td)

                return data

            except asyncio.CancelledError:
                raise

            except Exception as exc:
                self._record_error(exc)

                logger.warning(
                    "[ManagedDevice] Read error (%s): %s",
                    self.name,
                    exc,
                )

                self._set_device_error(exc)

                return None

    # ======================================================
    # SEND
    # ======================================================

    async def send(
        self,
        data: Any,
        parent_track_id: Optional[str] = None,
        task_id: Optional[str] = None,
    ):

        if task_id is not None:
            self.task_id = task_id

        async with self._io_lock:

            if (
                self._stopping
                or self._shutdown
            ):
                return False

            try:
                result = await _resolve_device_call(
                    self.device,
                    "send",
                    data,
                )

                self.runtime.sends += 1
                self.runtime.last_send = time.time()
                self.runtime.online = True

                priority = self._get_priority()

                track_id = _safe_track_id(
                    "output",
                    priority,
                )

                now = time.time()

                payload = {
                    "device_id": self.id,
                    "device_name": self.name,
                    "device_type": self.device_type,
                    "port": getattr(
                        self.device,
                        "port",
                        None,
                    ),
                    "data": data,
                    "timestamp": now,
                    "track_id": track_id,
                    "parent_track_id": (
                        parent_track_id
                    ),
                    "task_id": (
                        task_id or self.task_id
                    ),
                    "qbit_id": getattr(
                        self.qbit,
                        "qbit_id",
                        None,
                    ),
                }

                if self.fat_layer:
                    try:
                        self.fat_layer.append_log(
                            {
                                "action": "send",
                                **payload,
                            },
                            source="DeviceManager",
                        )
                    except Exception as fat_error:
                        logger.debug(
                            "[ManagedDevice] FAT log "
                            "failed (%s): %s",
                            self.name,
                            fat_error,
                        )

                td = TrackedData(
                    payload=payload,
                    track_id=track_id,
                    parent_id=parent_track_id,
                    source_id="device",
                    channel=_safe_channel_value(),
                    priority=priority,
                )

                self._publish_output(td)

                return result

            except asyncio.CancelledError:
                raise

            except Exception as exc:
                self._record_error(exc)

                logger.warning(
                    "[ManagedDevice] Send error (%s): %s",
                    self.name,
                    exc,
                )

                self._set_device_error(exc)

                return None

    # ======================================================
    # EVENT ROUTING
    # ======================================================

    def _publish_input(
        self,
        td: TrackedData,
    ):

        if self.event_bus:
            try:
                self.event_bus.publish(
                    "device.input",
                    td,
                )
            except Exception as exc:
                logger.warning(
                    "[ManagedDevice] EventBus input "
                    "publish failed (%s): %s",
                    self.name,
                    exc,
                )

        try:
            TrackSystem.feed(td)
        except Exception as exc:
            logger.warning(
                "[ManagedDevice] TrackSystem input "
                "failed (%s): %s",
                self.name,
                exc,
            )

    def _publish_output(
        self,
        td: TrackedData,
    ):

        if self.event_bus:
            try:
                self.event_bus.publish(
                    "device.output",
                    td,
                )
            except Exception as exc:
                logger.warning(
                    "[ManagedDevice] EventBus output "
                    "publish failed (%s): %s",
                    self.name,
                    exc,
                )

        try:
            TrackSystem.feed(td)
        except Exception as exc:
            logger.warning(
                "[ManagedDevice] TrackSystem output "
                "failed (%s): %s",
                self.name,
                exc,
            )

    # ======================================================
    # QUEUE FLUSH
    # ======================================================

    async def _flush_queue(self):

        while self._queue:

            td = self._queue.popleft()

            self._publish_input(td)

            # Prevent a large gated queue from starving
            # Heartbeat/Qbit/EventBus processing.
            await asyncio.sleep(0)

    # ======================================================
    # MONITOR
    # ======================================================

    async def monitor_loop(
        self,
        qbit: Optional[Qbit] = None,
    ):

        qbit = qbit or self.qbit
        self._stopping = False

        try:
            while not self._stopping:

                await self.read(qbit)

                await asyncio.sleep(
                    self.min_update_interval
                )

        except asyncio.CancelledError:
            logger.info(
                "[ManagedDevice] Monitor cancelled: %s",
                self.name,
            )

        finally:
            if not self._shutdown:
                self.runtime.online = False

    def start_monitor(
        self,
        qbit: Optional[Qbit] = None,
    ):

        if (
            self._monitor_task
            and not self._monitor_task.done()
        ):
            return self._monitor_task

        if self._shutdown:
            return None

        self._stopping = False

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                return None

        self._monitor_task = loop.create_task(
            self.monitor_loop(qbit)
        )

        return self._monitor_task

    async def stop_monitor(self):

        self._stopping = True

        task = self._monitor_task

        if task is None:
            return

        current_task = None

        try:
            current_task = asyncio.current_task()
        except Exception:
            pass

        if (
            not task.done()
            and task is not current_task
        ):
            task.cancel()

            try:
                await task
            except asyncio.CancelledError:
                pass

        self._monitor_task = None

        logger.debug(
            "[ManagedDevice] Monitor stopped: %s",
            self.name,
        )

    # ======================================================
    # ERROR STATE
    # ======================================================

    def _record_error(
        self,
        exc: Exception,
    ):

        self.runtime.errors += 1
        self.runtime.last_error = time.time()
        self.runtime.last_error_message = str(exc)
        self.runtime.online = False

    def _set_device_error(
        self,
        exc: Exception,
    ):

        setter = getattr(
            self.device,
            "set_error",
            None,
        )

        if not callable(setter):
            return

        try:
            result = setter(str(exc))

            if inspect.isawaitable(result):
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    return

                loop.create_task(result)

        except Exception:
            pass

    # ======================================================
    # SHUTDOWN
    # ======================================================

    async def stop(self):

        self._stopping = True

        await self.stop_monitor()

        self._queue.clear()

        self.runtime.lifecycle = "STOPPED"
        self.runtime.online = False

        # Preserve the wrapped Device lifecycle when it
        # exposes stop().
        method = getattr(
            self.device,
            "stop",
            None,
        )

        if callable(method):
            try:
                result = method()

                if inspect.isawaitable(result):
                    await result

            except Exception as exc:
                logger.debug(
                    "[ManagedDevice] Wrapped device "
                    "stop failed (%s): %s",
                    self.name,
                    exc,
                )

    async def shutdown(self):

        if self._shutdown:
            return

        self._shutdown = True
        self._stopping = True

        await self.stop_monitor()

        self._queue.clear()

        method = getattr(
            self.device,
            "async_shutdown",
            None,
        )

        if callable(method):
            try:
                result = method()

                if inspect.isawaitable(result):
                    await result

            except Exception as exc:
                logger.debug(
                    "[ManagedDevice] Wrapped device "
                    "async_shutdown failed (%s): %s",
                    self.name,
                    exc,
                )
        else:
            method = getattr(
                self.device,
                "shutdown",
                None,
            )

            if callable(method):
                try:
                    result = method()

                    if inspect.isawaitable(result):
                        await result

                except Exception as exc:
                    logger.debug(
                        "[ManagedDevice] Wrapped device "
                        "shutdown failed (%s): %s",
                        self.name,
                        exc,
                    )

        self.runtime.lifecycle = "SHUTDOWN"
        self.runtime.online = False

    # ======================================================
    # REPRESENTATION
    # ======================================================

    def __repr__(self):

        return (
            f"<ManagedDevice "
            f"name={self.name} "
            f"id={self.device_id} "
            f"type={self.device_type} "
            f"state={self.runtime.lifecycle}>"
        )


# ==========================================================
# DEVICE MANAGER
# ==========================================================

class DeviceManager:

    def __init__(
        self,
        event_bus: Optional[SEEDEventBus] = None,
        name: Optional[str] = None,
        qbit_dialer: Any = None,
        config: Optional[dict] = None,
        fat_layer: Any = None,
        qbit: Optional[Qbit] = None,
        storage_root: str = "./SEED_ROOT",
        track_system: Any = None,
        registry: Any = None,
        node_registry: Any = None,
        oracle: Any = None,
        heartbeat: Any = None,
        **kwargs,
    ):

        self.name = (
            name
            or "DeviceManager"
        )

        self.event_bus = event_bus
        self.fat_layer = fat_layer
        self.qbit = qbit
        self.storage_root = storage_root
        self.qbit_dialer = qbit_dialer

        self.track_system = (
            track_system
            or TrackSystem
        )

        self.registry = registry
        self.node_registry = node_registry
        self.oracle = oracle

        # Heartbeat is observed only.
        self.heartbeat = heartbeat

        self.config = config or {}

        self.metadata = dict(kwargs)

        try:
            self.loop = (
                asyncio.get_running_loop()
            )
        except RuntimeError:
            try:
                self.loop = (
                    asyncio.get_event_loop()
                )
            except RuntimeError:
                self.loop = None

        self.devices: Dict[
            str,
            ManagedDevice,
        ] = {}

        self.callbacks: Dict[
            str,
            List[Callable],
        ] = {}

        self.tasks: Dict[
            str,
            dict,
        ] = {}

        self._polling_task: Optional[
            asyncio.Task
        ] = None

        self._stop_polling = False
        self._shutdown = False

        self._manager_lock = (
            asyncio.Lock()
        )

        self._last_qbit_gate_state = (
            self._qbit_allows_processing()
        )

        # ==============================================
        # LOCAL DEVICE
        # ==============================================

        self.local_id = (
            f"LOCAL_{socket.gethostname()}"
        )

        self.local_name = "LocalDevice"

        self._register_local_device()

        logger.info(
            "[DeviceManager] Initialized | "
            "devices=%d | qbit=%s | dialer=%s",
            len(self.devices),
            type(self.qbit).__name__
            if self.qbit is not None
            else "None",
            type(self.qbit_dialer).__name__
            if self.qbit_dialer is not None
            else "None",
        )

    # ======================================================
    # QBIT
    # ======================================================

    def _qbit_allows_processing(self) -> bool:

        qbit = self.qbit

        if qbit is None:
            return True

        if getattr(
            qbit,
            "_system_go_flag",
            False,
        ):
            return True

        for attr in (
            "system_go",
            "system_go_flag",
            "go",
            "ready",
        ):
            value = getattr(
                qbit,
                attr,
                None,
            )

            if isinstance(value, bool) and value:
                return True

        return False

    def bind_qbit(
        self,
        qbit: Optional[Qbit],
    ) -> bool:

        if qbit is None:
            self.qbit = None

            for device in self.devices.values():
                device.qbit = None

            return True

        # Reject the class itself.
        if inspect.isclass(qbit):
            logger.warning(
                "[DeviceManager] Refusing Qbit class "
                "as runtime instance."
            )
            return False

        self.qbit = qbit

        for device in self.devices.values():
            device.qbit = qbit

        return True

    # ======================================================
    # LOCAL DEVICE
    # ======================================================

    def _register_local_device(self):

        local_core = LocalCoreDevice()

        local = ManagedDevice(
            device=local_core,
            name=self.local_name,
            device_id=self.local_id,
            device_type="core",
            event_bus=self.event_bus,
            fat_layer=self.fat_layer,
            qbit=self.qbit,
            capabilities=[
                "compute",
                "hud_output",
                "network",
                "core",
                "device_control",
                "lifecycle",
            ],
        )

        self.register_device(local)

    # ======================================================
    # REGISTRATION
    # ======================================================

    def register_device(
        self,
        device: Any,
    ) -> ManagedDevice:

        if not isinstance(
            device,
            ManagedDevice,
        ):
            device = ManagedDevice(
                device=device,
                event_bus=self.event_bus,
                fat_layer=self.fat_layer,
                qbit=self.qbit,
            )

        # Ensure manager dependencies are synchronized.
        if device.event_bus is None:
            device.event_bus = self.event_bus

        if device.fat_layer is None:
            device.fat_layer = self.fat_layer

        if device.qbit is None:
            device.qbit = self.qbit

        existing = self.devices.get(
            device.id
        )

        if existing is not None:
            logger.debug(
                "[DeviceManager] Device already "
                "registered: %s",
                device.id,
            )
            return existing

        self.devices[device.id] = device

        logger.info(
            "[DeviceManager] Registered device: "
            "%s | id=%s | type=%s",
            device.name,
            device.id,
            device.device_type,
        )

        self._register_with_authoritative_registry(
            device
        )

        self._publish_registration(
            device
        )

        return device

    def _register_with_authoritative_registry(
        self,
        device: ManagedDevice,
    ):


        registry = (
            self.registry
            or self.node_registry
            or SEED_KERNEL_REGISTRY
            or SYSTEM_SEED_KERNEL_REGISTRY
        )

        if registry is None:
            return

        register = getattr(
            registry,
            "register_node",
            None,
        )

        if not callable(register):
            register = getattr(
                registry,
                "register_module",
                None,
            )

        if not callable(register):
            return

        payload = {
            "name": device.name,
            "device_id": device.id,
            "device_type": device.device_type,
            "status": device.status,
            "capabilities": device.capabilities,
            "controls": device.available_controls(),
            "source": "DeviceManager",
        }

        try:
            result = register(
                device.name,
                payload,
            )

            # Do not block boot for async registry adapters.
            if inspect.isawaitable(result):
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    return

                loop.create_task(result)

        except TypeError:
            try:
                result = register(payload)

                if inspect.isawaitable(result):
                    try:
                        loop = asyncio.get_running_loop()
                    except RuntimeError:
                        return

                    loop.create_task(result)

            except Exception as exc:
                logger.debug(
                    "[DeviceManager] Registry registration "
                    "skipped: %s",
                    exc,
                )

        except Exception as exc:
            logger.debug(
                "[DeviceManager] Registry registration "
                "skipped: %s",
                exc,
            )

    def _publish_registration(
        self,
        device: ManagedDevice,
    ):

        if not self.event_bus:
            return

        track_id = _safe_track_id(
            "registered",
            50,
        )

        td = TrackedData(
            payload=device.to_dict(),
            track_id=track_id,
            source_id="device",
            channel=_safe_channel_value(),
            priority=50,
        )

        try:
            self.event_bus.publish(
                "device.registered",
                td,
            )
        except Exception as exc:
            logger.warning(
                "[DeviceManager] Registration event "
                "failed: %s",
                exc,
            )

    # ======================================================
    # UNREGISTER
    # ======================================================

    async def unregister_device(
        self,
        device_id: str,
    ):

        device = self.devices.pop(
            device_id,
            None,
        )

        if device is None:
            return

        try:
            await device.stop()
        except Exception as exc:
            logger.debug(
                "[DeviceManager] Device stop failed "
                "(%s): %s",
                device_id,
                exc,
            )

        logger.info(
            "[DeviceManager] Unregistered device: %s",
            device_id,
        )

    # ======================================================
    # DEVICE CONTROL SERVICE
    # ======================================================

    async def control_device(
        self,
        device_id: str,
        action: str,
        *,
        task_id: Optional[str] = None,
        track_id: Optional[str] = None,
        qbit_id: Optional[str] = None,
        **kwargs,
    ) -> Any:

        device = self.get_device(
            device_id
        )

        if device is None:
            raise KeyError(
                f"Device not found: {device_id}"
            )

        if task_id is not None:
            device.task_id = task_id

        if track_id is not None:
            device.track_id = track_id

        if qbit_id is not None:
            device.metadata[
                "qbit_id"
            ] = qbit_id

        result = await device.control(
            action,
            **kwargs,
        )

        await self._emit_event(
            "control",
            device,
            action,
            result,
        )

        return result

    async def control_device_by_name(
        self,
        name: str,
        action: str,
        **kwargs,
    ) -> Any:

        device = self.find_by_name(
            name
        )

        if device is None:
            raise KeyError(
                f"Device not found: {name}"
            )

        return await self.control_device(
            device.id,
            action,
            **kwargs,
        )

    def get_control_capabilities(
        self,
    ) -> Dict[str, Any]:

        return {
            device_id: device.control_capabilities()
            for device_id, device
            in self.devices.items()
        }

    def available_controls(
        self,
    ) -> Dict[str, List[str]]:

        return {
            device_id: device.available_controls()
            for device_id, device
            in self.devices.items()
        }

    # ======================================================
    # READ / WRITE SERVICE
    # ======================================================

    async def read_device(
        self,
        device_id: str,
        *,
        task_id: Optional[str] = None,
        track_id: Optional[str] = None,
        qbit: Optional[Qbit] = None,
    ) -> Any:

        device = self.get_device(
            device_id
        )

        if device is None:
            raise KeyError(
                f"Device not found: {device_id}"
            )

        if task_id is not None:
            device.task_id = task_id

        if track_id is not None:
            device.track_id = track_id

        return await device.read(
            qbit=qbit or self.qbit,
            parent_track_id=track_id,
            task_id=task_id,
        )

    async def send_device(
        self,
        device_id: str,
        data: Any,
        *,
        task_id: Optional[str] = None,
        track_id: Optional[str] = None,
    ) -> Any:

        device = self.get_device(
            device_id
        )

        if device is None:
            raise KeyError(
                f"Device not found: {device_id}"
            )

        if task_id is not None:
            device.task_id = task_id

        if track_id is not None:
            device.track_id = track_id

        return await device.send(
            data,
            parent_track_id=track_id,
            task_id=task_id,
        )

    # ======================================================
    # POLLING
    # ======================================================

    async def _poll_loop(
        self,
        qbit: Optional[Qbit] = None,
    ):

        qbit = qbit or self.qbit

        logger.info(
            "[DeviceManager] Poll loop online"
        )

        try:

            while not self._stop_polling:

                devices = list(
                    self.devices.values()
                )

                if devices:

                    results = await asyncio.gather(
                        *(
                            dev.read(qbit)
                            for dev in devices
                        ),
                        return_exceptions=True,
                    )

                    for device, result in zip(
                        devices,
                        results,
                    ):

                        if isinstance(
                            result,
                            asyncio.CancelledError,
                        ):
                            continue

                        if isinstance(
                            result,
                            Exception,
                        ):
                            logger.warning(
                                "[DeviceManager] Poll error "
                                "(%s): %s",
                                device.name,
                                result,
                            )

                await asyncio.sleep(
                    max(
                        0.05,
                        float(
                            self.config.get(
                                "poll_interval",
                                0.05,
                            )
                        ),
                    )
                )

        except asyncio.CancelledError:

            logger.info(
                "[DeviceManager] Poll loop cancelled"
            )

        finally:

            logger.info(
                "[DeviceManager] Poll loop offline"
            )

    # ======================================================
    # START POLLING
    # ======================================================

    def start_polling(
        self,
        qbit: Optional[Qbit] = None,
    ):

        if (
            self._polling_task
            and not self._polling_task.done()
        ):
            return self._polling_task

        if qbit is not None:
            self.bind_qbit(qbit)

        self._stop_polling = False
        self._shutdown = False

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = self.loop

        if loop is None:
            raise RuntimeError(
                "DeviceManager requires an active "
                "asyncio event loop to start polling."
            )

        self._polling_task = loop.create_task(
            self._poll_loop(self.qbit)
        )

        logger.info(
            "[DeviceManager] Polling started"
        )

        return self._polling_task

    # ======================================================
    # STOP POLLING
    # ======================================================

    async def stop_polling(
        self,
        qbit: Optional[Qbit] = None,
    ):

        _ = qbit

        self._stop_polling = True

        task = self._polling_task

        if task is None:
            return

        current_task = None

        try:
            current_task = asyncio.current_task()
        except Exception:
            pass

        if (
            not task.done()
            and task is not current_task
        ):

            task.cancel()

            try:
                await task
            except asyncio.CancelledError:
                pass

        self._polling_task = None

        logger.info(
            "[DeviceManager] Polling stopped"
        )

    # ======================================================
    # DEVICE LOOKUP
    # ======================================================

    def get_device(
        self,
        device_id: str,
    ) -> Optional[ManagedDevice]:

        return self.devices.get(
            device_id
        )

    def list_devices(
        self,
    ) -> List[ManagedDevice]:

        return list(
            self.devices.values()
        )

    def find_by_name(
        self,
        name: str,
    ) -> Optional[ManagedDevice]:

        target = str(name).lower()

        for device in self.devices.values():

            if (
                str(device.name).lower()
                == target
            ):
                return device

        return None

    def find_by_capability(
        self,
        capability: str,
    ) -> List[ManagedDevice]:

        return [
            device
            for device in self.devices.values()
            if capability
            in device.capabilities
        ]

    def find_by_type(
        self,
        device_type: str,
    ) -> List[ManagedDevice]:

        target = str(
            device_type
        ).lower()

        return [
            device
            for device in self.devices.values()
            if str(
                device.device_type
            ).lower()
            == target
        ]

    # ======================================================
    # FETCH BEST DEVICE
    # ======================================================

    def fetch_best_device(
        self,
        required_capabilities: Optional[
            Sequence[str]
        ] = None,
        preferred_types: Optional[
            Sequence[str]
        ] = None,
    ) -> ManagedDevice:

        required_capabilities = list(
            required_capabilities or []
        )

        preferred_types = list(
            preferred_types or []
        )

        candidates = [
            device
            for device in self.devices.values()
            if all(
                capability
                in device.capabilities
                for capability
                in required_capabilities
            )
        ]

        if not candidates:

            logger.warning(
                "[DeviceManager] No matching device "
                "— using DummyDevice"
            )

            dummy = DummyDevice()

            return ManagedDevice(
                device=dummy,
                event_bus=self.event_bus,
                fat_layer=self.fat_layer,
                qbit=self.qbit,
                device_type="dummy",
            )

        if preferred_types:

            for preferred_type in preferred_types:

                for device in candidates:

                    if (
                        device.device_type
                        == preferred_type
                    ):
                        return device

        return candidates[0]

    # ======================================================
    # REGISTRY-STYLE CAPABILITY DISCOVERY
    # ======================================================

    def discover_devices(
        self,
    ) -> List[Dict[str, Any]]:

        return [
            device.to_dict()
            for device in self.devices.values()
        ]

    def capability_snapshot(
        self,
    ) -> Dict[str, Any]:

        return {
            "component": "DeviceManager",
            "role": "device_io_management_layer",
            "authority": "QbitDialer",
            "device_count": len(
                self.devices
            ),
            "devices": (
                self.get_control_capabilities()
            ),
        }

    # ======================================================
    # CALLBACKS
    # ======================================================

    def add_event_callback(
        self,
        callback: Callable,
        event_type: str = "input",
    ):

        if not callable(callback):
            raise TypeError(
                "Device event callback "
                "must be callable."
            )

        self.callbacks.setdefault(
            event_type,
            [],
        ).append(callback)

    def remove_event_callback(
        self,
        callback: Callable,
        event_type: str = "input",
    ):

        callbacks = self.callbacks.get(
            event_type,
            [],
        )

        if callback in callbacks:
            callbacks.remove(callback)

    async def _emit_event(
        self,
        event_type: str,
        *args,
        **kwargs,
    ):

        for callback in list(
            self.callbacks.get(
                event_type,
                [],
            )
        ):

            try:

                result = callback(
                    *args,
                    **kwargs,
                )

                await _maybe_await(
                    result
                )

            except Exception as exc:

                logger.warning(
                    "[DeviceManager] Callback error "
                    "(%s): %s",
                    event_type,
                    exc,
                )

    # ======================================================
    # HEARTBEAT OBSERVATION
    # ======================================================

    def heartbeat_snapshot(
        self,
    ) -> Dict[str, Any]:

        heartbeat = self.heartbeat

        if heartbeat is None:
            return {
                "connected": False,
                "authority": "Heartbeat",
            }

        return {
            "connected": True,
            "authority": "Heartbeat",
            "running": bool(
                getattr(
                    heartbeat,
                    "running",
                    getattr(
                        heartbeat,
                        "_running",
                        False,
                    ),
                )
            ),
        }

    # ======================================================
    # STATUS
    # ======================================================

    def get_status(
        self,
    ) -> Dict[str, Any]:

        return {
            "name": self.name,
            "role": (
                "device_io_management_layer"
            ),
            "authority": "QbitDialer",
            "device_count": len(
                self.devices
            ),
            "polling": bool(
                self._polling_task
                and not self._polling_task.done()
            ),
            "shutdown": self._shutdown,
            "qbit_connected": (
                self.qbit is not None
            ),
            "qbit_go": (
                self._qbit_allows_processing()
            ),
            "qbit_dialer_connected": (
                self.qbit_dialer is not None
            ),
            "heartbeat": (
                self.heartbeat_snapshot()
            ),
            "devices": {
                device_id: device.to_dict()
                for device_id, device
                in self.devices.items()
            },
            "controls": (
                self.available_controls()
            ),
        }

    # ======================================================
    # REFRESH ALL
    # ======================================================

    async def refresh_all(
        self,
    ) -> Dict[str, Any]:

        results = {}

        for device_id, device in list(
            self.devices.items()
        ):

            try:
                results[device_id] = (
                    await device.refresh()
                )

            except Exception as exc:
                results[device_id] = {
                    "ok": False,
                    "error": str(exc),
                }

        return results

    # ======================================================
    # HEARTBEAT / GATE FLUSH
    # ======================================================

    async def flush_gated_data(
        self,
    ) -> int:

        if not self._qbit_allows_processing():
            return 0

        flushed = 0

        for device in self.devices.values():

            before = len(
                device._queue
            )

            if before:
                await device._flush_queue()

            flushed += before

        if flushed:
            logger.debug(
                "[DeviceManager] Flushed gated "
                "device data | count=%d",
                flushed,
            )

        return flushed

    # ======================================================
    # TASK / LINEAGE BINDING
    # ======================================================

    def bind_task_context(
        self,
        task_id: Optional[str] = None,
        track_id: Optional[str] = None,
        qbit: Optional[Qbit] = None,
    ) -> Dict[str, Any]:

        if qbit is not None:
            self.bind_qbit(qbit)

        bound = 0

        for device in self.devices.values():

            if task_id is not None:
                device.task_id = task_id

            if track_id is not None:
                device.track_id = track_id

            bound += 1

        return {
            "task_id": task_id,
            "track_id": track_id,
            "qbit_id": getattr(
                self.qbit,
                "qbit_id",
                None,
            ),
            "devices_bound": bound,
        }

    # ======================================================
    # SHUTDOWN
    # ======================================================

    async def shutdown(
        self,
    ):

        if self._shutdown:
            return

        self._shutdown = True

        logger.info(
            "[DeviceManager] Shutdown initiated"
        )

        try:
            await self.stop_polling()

        except Exception as exc:
            logger.warning(
                "[DeviceManager] Polling shutdown "
                "failed: %s",
                exc,
            )

        devices = list(
            self.devices.values()
        )

        for device in devices:

            try:
                await device.shutdown()

            except Exception as exc:
                logger.debug(
                    "[DeviceManager] Device shutdown "
                    "failed (%s): %s",
                    device.name,
                    exc,
                )

        logger.info(
            "[DeviceManager] Shutdown complete"
        )

    async def stop(self):

        await self.shutdown()

    # ======================================================
    # REPRESENTATION
    # ======================================================

    def __repr__(self):

        return (
            f"<DeviceManager "
            f"name={self.name} "
            f"devices={len(self.devices)} "
            f"polling="
            f"{bool(self._polling_task and not self._polling_task.done())}>"
        )


# ==========================================================
# MODULE METADATA
# ==========================================================

__all__ = [
    "ManagedDevice",
    "DummyDevice",
    "LocalCoreDevice",
    "DeviceRuntimeState",
    "DeviceManager",
]