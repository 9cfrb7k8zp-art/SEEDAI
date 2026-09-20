# ========================================================================
# FILE: device.py
# PATH: SEED_ROOT/seed/core/device.py
# VERSION: 5.2
# UPDATED: 2026-09-01
#
# PHASE:
# DEVICE FOUNDATION / FULL BOOT STABILIZATION
#
# CONTRACT:
# - Core device abstraction for SEED AI OS
# - Sync + async device I/O safe
# - Lifecycle-aware
# - TrackContext-bound
# - TrackID-aware
# - Qbit-compatible
# - EventBus-compatible through DeviceManager
# - Registry-safe
# - Shutdown-safe
# - QbitDialer command-plane compatible
# - Device lifecycle control compatible
#
# AUTHORITY:
# CORE DEVICE FOUNDATION
#
# PURPOSE:
# Provide one stable device contract for:
# LocalDevice
# hardware devices
# serial devices
# Bluetooth devices
# IoT devices
# smart devices
# SEEDCore devices
# simulated/test devices
#
# BOOT ORDER:
# Device
# ↓
# DeviceRegistry
# ↓
# DeviceManager
# ↓
# TrackSystem / EventBus
# ↓
# Qbit / Heartbeat / higher layers
#
# IMPORTANT:
# Device is intentionally NOT responsible for commanding:
# Qbit
# EventBus
# HeartbeatEmitter
# HUD
#
# QbitDialer remains command authority.
# Device only implements the actuator contract.
#
# CONTROL PATH:
# QbitDialer
# ↓
# submit_command()
# ↓
# command plane
# ↓
# DeviceManager
# ↓
# DeviceRegistry
# ↓
# Device.control()
# ↓
# run / stop / pause / resume /
# activate / deactivate / refresh / shutdown
#
# ========================================================================

from __future__ import annotations

import asyncio
import datetime
import inspect
import logging
import uuid
from typing import Any, Optional, Dict, List, Iterable

from seed.core.track_context import TrackContext
from seed.core.tracked_data import TrackedData


# ========================================================================
# LOGGING
# ========================================================================

logger = logging.getLogger("Device")
logger.setLevel(logging.INFO)


# ========================================================================
# CONSTANTS
# ========================================================================

DEVICE_VERSION = "5.2"

DEFAULT_DEVICE_DOMAIN = "User"
DEFAULT_DEVICE_TYPE = "generic"
DEFAULT_DEVICE_STATUS = "ON"

DEFAULT_READ_INTERVAL = 0.25
MIN_READ_INTERVAL = 0.02
MAX_READ_INTERVAL = 10.0

# ------------------------------------------------------------------------
# Lifecycle states
# ------------------------------------------------------------------------

DEVICE_RUNNING = "RUNNING"
DEVICE_STOPPED = "STOPPED"
DEVICE_PAUSED = "PAUSED"
DEVICE_ON = "ON"
DEVICE_OFF = "OFF"
DEVICE_ERROR = "ERROR"
DEVICE_DISCONNECTED = "DISCONNECTED"

DEVICE_TERMINAL_STATES = {
    DEVICE_OFF,
}

DEVICE_UNAVAILABLE_STATES = {
    DEVICE_OFF,
    DEVICE_ERROR,
    DEVICE_DISCONNECTED,
    DEVICE_STOPPED,
}

DEVICE_ONLINE_STATES = {
    DEVICE_RUNNING,
    DEVICE_ON,
    DEVICE_PAUSED,
}


DOMAIN_MAP = {
    "User": "U",
    "System": "S",
    "SEEDCore AI": "SC",
}


# ========================================================================
# HELPERS
# ========================================================================

def gen_track_id(prefix: str = "D") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


async def maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _safe_float(
    value: Any,
    default: float,
) -> float:
    try:
        result = float(value)

        if result != result:  # NaN
            return default

        return result

    except (TypeError, ValueError):
        return default


# ========================================================================
# CORE DEVICE
# ========================================================================

class Device:

    DOMAIN_MAP = DOMAIN_MAP.copy()

    # ====================================================================
    # CONTROL VOCABULARY
    # ====================================================================

    CONTROL_ALIASES = {
        "run": "run",
        "start": "run",

        "stop": "stop",

        "pause": "pause",

        "resume": "resume",
        "continue": "resume",

        "activate": "activate",
        "enable": "activate",

        "deactivate": "deactivate",
        "disable": "deactivate",

        "refresh": "refresh",
        "status": "refresh",

        "shutdown": "shutdown",
    }

    # ====================================================================
    # INIT
    # ====================================================================

    def __init__(
        self,
        name: Optional[str] = None,
        storage_root: str = "./SEED_ROOT",
        device_id: Optional[str] = None,
        domain: str = DEFAULT_DEVICE_DOMAIN,
        type: str = DEFAULT_DEVICE_TYPE,
        status: str = DEFAULT_DEVICE_STATUS,
        port: Any = None,
        channels: Optional[Iterable[str]] = None,
        bluetooth_id: Optional[str] = None,
        iot_capable: bool = True,
        smart_device: bool = True,
        capabilities: Optional[Iterable[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ):
        # ---------------------------------------------------------------
        # Identity
        # ---------------------------------------------------------------

        self.name = name or "local_device"

        self.storage_root = storage_root

        self.domain = (
            domain
            if domain in self.DOMAIN_MAP
            else "User"
        )

        self.type = type or DEFAULT_DEVICE_TYPE

        self.device_id = (
            device_id
            or f"{self.name}:{uuid.uuid4().hex[:8]}"
        )

        self.bluetooth_id = bluetooth_id

        self.label = self._smart_label(
            self.name,
            self.domain,
            self.bluetooth_id,
        )

        # ---------------------------------------------------------------
        # Status
        # ---------------------------------------------------------------

        self.status = (
            status
            or DEFAULT_DEVICE_STATUS
        )

        self._active = True

        # ---------------------------------------------------------------
        # Connectivity
        # ---------------------------------------------------------------

        self.port = port

        self.connection: Optional[Any] = None

        self.iot_capable = bool(iot_capable)

        self.smart_device = bool(smart_device)

        # ---------------------------------------------------------------
        # Health / State
        # ---------------------------------------------------------------

        self.created_ts = datetime.datetime.now(
            datetime.timezone.utc
        )

        self.last_seen = self.created_ts

        self.heartbeat_ts: Optional[
            datetime.datetime
        ] = None

        self.alerted = False

        self.error_state: Optional[str] = None

        self.last_error_ts: Optional[
            datetime.datetime
        ] = None

        self.read_count = 0

        self.write_count = 0

        self.error_count = 0

        # ---------------------------------------------------------------
        # Capabilities
        # ---------------------------------------------------------------

        self.capabilities: List[str] = []

        if capabilities:
            for capability in capabilities:
                self.add_capability(
                    capability
                )

        # ---------------------------------------------------------------
        # Channels
        # ---------------------------------------------------------------

        self.channels: List[str] = []

        if channels:
            for channel in channels:
                self.add_channel(channel)

        if not self.channels:
            self.channels.append(
                self._default_channel()
            )

        # ---------------------------------------------------------------
        # Metadata
        # ---------------------------------------------------------------

        self.meta: Dict[str, Any] = dict(
            metadata or {}
        )

        # Preserve extension kwargs without
        # overwriting core fields.
        for key, value in kwargs.items():
            if key not in self.__dict__:
                self.meta[key] = value

        self.meta.setdefault(
            "device_version",
            DEVICE_VERSION,
        )

        self.meta.setdefault(
            "created_by",
            "Device",
        )

        self.meta.setdefault(
            "domain_code",
            self.DOMAIN_MAP.get(
                self.domain,
                "U",
            ),
        )

        # ---------------------------------------------------------------
        # Polling / monitoring configuration
        # ---------------------------------------------------------------

        self.read_interval = (
            DEFAULT_READ_INTERVAL
        )

        self.min_read_interval = (
            MIN_READ_INTERVAL
        )

        self.max_read_interval = (
            MAX_READ_INTERVAL
        )

        self._last_read_ts = 0.0

        self._last_send_ts = 0.0

        # ---------------------------------------------------------------
        # Async synchronization
        # ---------------------------------------------------------------

        self._read_lock = asyncio.Lock()

        self._send_lock = asyncio.Lock()

        self._lifecycle_lock = asyncio.Lock()

        # ---------------------------------------------------------------
        # Internal lifecycle task
        # ---------------------------------------------------------------

        self._monitor_task: Optional[
            asyncio.Task
        ] = None

        # ---------------------------------------------------------------
        # Lifecycle metadata
        # ---------------------------------------------------------------

        self.meta.setdefault(
            "lifecycle_state",
            self.status,
        )

        self.meta.setdefault(
            "previous_lifecycle_state",
            None,
        )

        self.meta.setdefault(
            "running",
            self.status == DEVICE_RUNNING,
        )

        self.meta.setdefault(
            "paused",
            self.status == DEVICE_PAUSED,
        )

        self.meta.setdefault(
            "stopped",
            self.status == DEVICE_STOPPED,
        )

        self.meta.setdefault(
            "active",
            self._active,
        )

        self.meta.setdefault(
            "deactivated",
            not self._active,
        )

        self.meta.setdefault(
            "control_authority",
            "QbitDialer",
        )

        self.meta.setdefault(
            "execution_owner",
            "Device",
        )

    # ====================================================================
    # SMART LABELING
    # ====================================================================

    def _smart_label(
        self,
        name: Optional[str],
        domain: str,
        bluetooth_id: Optional[str],
    ) -> str:

        prefix = self.DOMAIN_MAP.get(
            domain,
            "U",
        )

        safe_name = (
            name
            or "local_device"
        )

        suffix = (
            "-BT"
            if bluetooth_id
            else ""
        )

        return f"{prefix}-{safe_name}{suffix}"

    def _default_channel(self) -> str:
        return (
            f"{self.DOMAIN_MAP.get(self.domain, 'U')}"
            f"-device"
        )

    # ====================================================================
    # PROPERTIES
    # ====================================================================

    @property
    def id(self) -> str:
        return self.device_id

    @property
    def active(self) -> bool:
        return self._active

    @property
    def online(self) -> bool:

        if not self._active:
            return False

        if self.error_state is not None:
            return False

        if self.status in {
            DEVICE_ERROR,
            DEVICE_OFF,
            DEVICE_DISCONNECTED,
            DEVICE_STOPPED,
        }:
            return False

        if self.status in DEVICE_ONLINE_STATES:
            return True

        return bool(
            self.connection is not None
        )

    @property
    def priority(self) -> int:
        return self.priority_hint()

    # ====================================================================
    # DICT COMPATIBILITY
    # ====================================================================

    def get(
        self,
        key: str,
        default: Any = None,
    ) -> Any:

        if hasattr(self, key):
            return getattr(
                self,
                key,
            )

        return self.meta.get(
            key,
            default,
        )

    def to_dict(
        self,
    ) -> Dict[str, Any]:

        return {
            "device_id": self.device_id,
            "name": self.name,
            "label": self.label,
            "type": self.type,
            "status": self.status,
            "domain": self.domain,
            "domain_code": self.DOMAIN_MAP.get(
                self.domain,
                "U",
            ),
            "port": self.port,
            "bluetooth_id": self.bluetooth_id,
            "iot_capable": self.iot_capable,
            "smart_device": self.smart_device,
            "active": self._active,
            "online": self.online,
            "created": self.created_ts.isoformat(),
            "last_seen": self.last_seen.isoformat(),
            "heartbeat": (
                self.heartbeat_ts.isoformat()
                if self.heartbeat_ts
                else None
            ),
            "alerted": self.alerted,
            "error_state": self.error_state,
            "error_count": self.error_count,
            "read_count": self.read_count,
            "write_count": self.write_count,
            "read_interval": self.read_interval,
            "capabilities": list(
                self.capabilities
            ),
            "channels": list(
                self.channels
            ),
            "controls": self.available_controls(),
            "lifecycle": self.lifecycle_snapshot(),
            "meta": dict(
                self.meta
            ),
        }

    # ====================================================================
    # HEALTH
    # ====================================================================

    def touch(self) -> None:
        self.last_seen = (
            datetime.datetime.now(
                datetime.timezone.utc
            )
        )

    def heartbeat(self) -> None:

        if not self._active:
            return

        if self.status in {
            DEVICE_PAUSED,
            DEVICE_STOPPED,
            DEVICE_OFF,
            DEVICE_ERROR,
        }:
            return

        self.heartbeat_ts = (
            datetime.datetime.now(
                datetime.timezone.utc
            )
        )

        self.touch()

    def set_error(
        self,
        error: str,
    ) -> None:

        previous = self.status

        self.status = DEVICE_ERROR

        self.error_state = str(error)

        self.alerted = True

        self.error_count += 1

        self.last_error_ts = (
            datetime.datetime.now(
                datetime.timezone.utc
            )
        )

        self.meta[
            "previous_lifecycle_state"
        ] = previous

        self.meta[
            "lifecycle_state"
        ] = DEVICE_ERROR

        self.meta[
            "running"
        ] = False

        self.touch()

    def clear_error(self) -> None:

        self.error_state = None

        self.alerted = False

        self.last_error_ts = None

        if self.status == DEVICE_ERROR:

            if self._active:
                self.status = DEVICE_ON
            else:
                self.status = DEVICE_OFF

        self.meta[
            "lifecycle_state"
        ] = self.status

        self.touch()

    # ====================================================================
    # CAPABILITIES
    # ====================================================================

    def add_capability(
        self,
        cap: str,
    ) -> None:

        if not cap:
            return

        cap = str(cap)

        if cap not in self.capabilities:
            self.capabilities.append(
                cap
            )

    def remove_capability(
        self,
        cap: str,
    ) -> None:

        if cap in self.capabilities:
            self.capabilities.remove(
                cap
            )

    def has_capability(
        self,
        cap: str,
    ) -> bool:

        return cap in self.capabilities

    # ====================================================================
    # CHANNELS
    # ====================================================================

    def add_channel(
        self,
        channel: str,
    ) -> None:

        if not channel:
            return

        channel = str(channel)

        if channel not in self.channels:
            self.channels.append(
                channel
            )

    def remove_channel(
        self,
        channel: str,
    ) -> None:

        if channel in self.channels:
            self.channels.remove(
                channel
            )

    # ====================================================================
    # CONNECTION MANAGEMENT
    # ====================================================================

    def attach_connection(
        self,
        connection: Any,
    ) -> None:

        self.connection = connection

        self.clear_error()

        if self.status in {
            DEVICE_OFF,
            DEVICE_DISCONNECTED,
            DEVICE_STOPPED,
        }:
            self.status = DEVICE_ON

        self.meta[
            "connection_attached"
        ] = True

        self.meta[
            "lifecycle_state"
        ] = self.status

        self.touch()

    async def detach_connection(
        self,
    ) -> None:

        connection = self.connection

        self.connection = None

        self.meta[
            "connection_attached"
        ] = False

        if connection is not None:

            close_method = getattr(
                connection,
                "close",
                None,
            )

            if callable(close_method):

                try:
                    await maybe_await(
                        close_method()
                    )

                except Exception as exc:

                    logger.debug(
                        "[Device] Connection close error "
                        "(%s): %s",
                        self.name,
                        exc,
                    )

        if self._active:
            self.status = DEVICE_DISCONNECTED

        self.meta[
            "lifecycle_state"
        ] = self.status

    # ====================================================================
    # ASYNC DEVICE I/O
    # ====================================================================

    async def read(
        self,
    ) -> Any:

        async with self._read_lock:

            if not self._active:
                return None

            if self.status in {
                DEVICE_PAUSED,
                DEVICE_STOPPED,
                DEVICE_OFF,
            }:
                return None

            self.touch()

            connection = self.connection

            if connection is None:

                # A disconnected/local core device
                # is valid.
                self.status = (
                    DEVICE_ON
                    if self.type == "core"
                    else DEVICE_DISCONNECTED
                )

                self.meta[
                    "lifecycle_state"
                ] = self.status

                return None

            read_method = getattr(
                connection,
                "read",
                None,
            )

            if not callable(read_method):

                self.meta[
                    "read_supported"
                ] = False

                return None

            try:

                result = await maybe_await(
                    read_method()
                )

                self.read_count += 1

                self._last_read_ts = (
                    asyncio
                    .get_running_loop()
                    .time()
                )

                self.touch()

                if self.status == DEVICE_ERROR:
                    self.clear_error()

                return result

            except asyncio.CancelledError:
                raise

            except Exception as exc:

                self.set_error(
                    f"Read error: {exc}"
                )

                logger.warning(
                    "[Device] Read error (%s): %s",
                    self.name,
                    exc,
                )

                return None

    async def send(
        self,
        data: Any,
    ) -> Any:

        async with self._send_lock:

            if not self._active:
                return False

            if self.status in {
                DEVICE_PAUSED,
                DEVICE_STOPPED,
                DEVICE_OFF,
            }:
                return False

            self.touch()

            connection = self.connection

            if connection is None:

                # A core/local device may legitimately
                # have no physical output connection.
                return False

            send_method = getattr(
                connection,
                "send",
                None,
            )

            if not callable(send_method):

                self.meta[
                    "send_supported"
                ] = False

                return False

            try:

                result = await maybe_await(
                    send_method(data)
                )

                self.write_count += 1

                self._last_send_ts = (
                    asyncio
                    .get_running_loop()
                    .time()
                )

                self.touch()

                if self.status == DEVICE_ERROR:
                    self.clear_error()

                return (
                    True
                    if result is None
                    else result
                )

            except asyncio.CancelledError:
                raise

            except Exception as exc:

                self.set_error(
                    f"Send error: {exc}"
                )

                logger.warning(
                    "[Device] Send error (%s): %s",
                    self.name,
                    exc,
                )

                return False

    # ====================================================================
    # TRACK ID GENERATION
    # ====================================================================

    def generate_track_id(
        self,
        category: str = "DeviceUpdate",
        stream_type: str = "IN",
        actuator_bridge: bool = False,
        multi_channel: bool = True,
    ) -> str:

        domain_code = self.DOMAIN_MAP.get(
            self.domain,
            "U",
        )

        channel_str = (
            ",".join(self.channels)
            if (
                multi_channel
                and self.channels
            )
            else (
                self.channels[0]
                if self.channels
                else "GEN"
            )
        )

        try:

            with TrackContext.bind(
                domain=domain_code
            ):

                return (
                    TrackedData.generate_track_id(
                        category=category,
                        domain=domain_code,
                        stream_type=stream_type,
                        parent_id=TrackContext.current(),
                        actuator_bridge=actuator_bridge,
                        channels=channel_str,
                        emit_hud=True,
                    )
                )

        except Exception as exc:

            # Track generation must never prevent
            # a device from operating.
            logger.debug(
                "[Device] TrackID generation fallback "
                "(%s): %s",
                self.name,
                exc,
            )

            return gen_track_id("D")

    # ====================================================================
    # METADATA
    # ====================================================================

    def set_metadata(
        self,
        key: str,
        value: Any,
    ) -> None:

        if key:
            self.meta[
                str(key)
            ] = value

    def get_metadata(
        self,
        key: str,
        default: Any = None,
    ) -> Any:

        return self.meta.get(
            key,
            default,
        )

    def update_metadata(
        self,
        values: Optional[
            Dict[str, Any]
        ],
    ) -> None:

        if values:
            self.meta.update(
                values
            )

    # ====================================================================
    # PRIORITY / SORTING
    # ====================================================================

    def priority_hint(
        self,
    ) -> int:

        if "em_sensor" in self.capabilities:
            return 90

        if "qbit_input" in self.capabilities:
            return 80

        if "heartbeat" in self.capabilities:
            return 75

        if "hud_output" in self.capabilities:
            return 60

        if (
            self.iot_capable
            or self.smart_device
        ):
            return 70

        if self.type == "core":
            return 50

        return 40

    def sort_key(
        self,
    ):

        domain_priority = {
            "U": 1,
            "S": 2,
            "SC": 3,
        }.get(
            self.DOMAIN_MAP.get(
                self.domain,
                "U",
            ),
            99,
        )

        return (
            domain_priority,
            self.name,
            self.device_id,
        )

    # ====================================================================
    # POLLING CONTROL
    # ====================================================================

    def set_read_interval(
        self,
        interval: float,
    ) -> float:

        interval = _safe_float(
            interval,
            DEFAULT_READ_INTERVAL,
        )

        interval = max(
            self.min_read_interval,
            min(
                interval,
                self.max_read_interval,
            ),
        )

        self.read_interval = interval

        return interval

    # ====================================================================
    # DEVICE LIFECYCLE
    # ====================================================================

    def lifecycle_snapshot(
        self,
    ) -> Dict[str, Any]:

        return {
            "device_id": self.device_id,
            "state": self.status,
            "active": self._active,
            "online": self.online,
            "running": bool(
                self.status
                == DEVICE_RUNNING
            ),
            "paused": bool(
                self.status
                == DEVICE_PAUSED
            ),
            "stopped": bool(
                self.status
                == DEVICE_STOPPED
            ),
            "error": bool(
                self.status
                == DEVICE_ERROR
            ),
            "connected": bool(
                self.connection is not None
            ),
        }

    def available_controls(
        self,
    ) -> List[str]:

        return [
            "run",
            "stop",
            "pause",
            "resume",
            "activate",
            "deactivate",
            "refresh",
            "shutdown",
        ]

    def control_capabilities(
        self,
    ) -> Dict[str, Any]:

        return {
            "device_id": self.device_id,
            "name": self.name,
            "type": self.type,
            "domain": self.domain,
            "controls": self.available_controls(),
            "lifecycle": True,
            "read": callable(
                getattr(
                    self,
                    "read",
                    None,
                )
            ),
            "write": callable(
                getattr(
                    self,
                    "send",
                    None,
                )
            ),
            "command_authority": "QbitDialer",
            "execution_owner": "Device",
        }

    def _set_lifecycle_state(
        self,
        state: str,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:

        previous = self.status

        self.status = state

        self.meta[
            "previous_lifecycle_state"
        ] = previous

        self.meta[
            "lifecycle_state"
        ] = state

        self.meta[
            "lifecycle_updated_at"
        ] = datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat()

        if reason is not None:
            self.meta[
                "lifecycle_reason"
            ] = str(reason)

        self.meta[
            "active"
        ] = self._active

        self.meta[
            "running"
        ] = state == DEVICE_RUNNING

        self.meta[
            "paused"
        ] = state == DEVICE_PAUSED

        self.meta[
            "stopped"
        ] = state == DEVICE_STOPPED

        self.meta[
            "deactivated"
        ] = not self._active

        self.touch()

        return {
            "status": "success",
            "device_id": self.device_id,
            "previous_state": previous,
            "state": state,
            "active": self._active,
            "online": self.online,
            "reason": reason,
        }

    # ====================================================================
    # RUN
    # ====================================================================

    async def run(
        self,
        **kwargs: Any,
    ) -> Dict[str, Any]:

        async with self._lifecycle_lock:

            if not self._active:

                return {
                    "status": "error",
                    "device_id": self.device_id,
                    "action": "run",
                    "reason": "DEVICE_INACTIVE",
                }

            if self.error_state is not None:

                return {
                    "status": "error",
                    "device_id": self.device_id,
                    "action": "run",
                    "reason": "DEVICE_ERROR",
                    "error": self.error_state,
                }

            result = self._set_lifecycle_state(
                DEVICE_RUNNING,
                reason="run",
            )

            try:
                await self.start_monitor()

            except Exception as exc:

                logger.debug(
                    "[Device] Monitor start failed "
                    "(%s): %s",
                    self.name,
                    exc,
                )

            return {
                **result,
                "action": "run",
            }

    # ====================================================================
    # STOP
    # ====================================================================

    async def stop(
        self,
        **kwargs: Any,
    ) -> Dict[str, Any]:

        async with self._lifecycle_lock:

            try:
                await self.stop_monitor()

            except Exception as exc:

                logger.debug(
                    "[Device] Monitor stop failed "
                    "(%s): %s",
                    self.name,
                    exc,
                )

            self._set_lifecycle_state(
                DEVICE_STOPPED,
                reason="stop",
            )

            return {
                "status": "success",
                "device_id": self.device_id,
                "action": "stop",
                "state": self.status,
                "active": self._active,
                "online": self.online,
            }

    # ====================================================================
    # PAUSE
    # ====================================================================

    async def pause(
        self,
        **kwargs: Any,
    ) -> Dict[str, Any]:

        async with self._lifecycle_lock:

            if not self._active:

                return {
                    "status": "error",
                    "device_id": self.device_id,
                    "action": "pause",
                    "reason": "DEVICE_INACTIVE",
                }

            try:
                await self.stop_monitor()

            except Exception as exc:

                logger.debug(
                    "[Device] Monitor pause failed "
                    "(%s): %s",
                    self.name,
                    exc,
                )

            self._set_lifecycle_state(
                DEVICE_PAUSED,
                reason="pause",
            )

            return {
                "status": "success",
                "device_id": self.device_id,
                "action": "pause",
                "state": self.status,
                "active": self._active,
                "online": self.online,
            }

    # ====================================================================
    # RESUME
    # ====================================================================

    async def resume(
        self,
        **kwargs: Any,
    ) -> Dict[str, Any]:

        async with self._lifecycle_lock:

            if not self._active:

                return {
                    "status": "error",
                    "device_id": self.device_id,
                    "action": "resume",
                    "reason": "DEVICE_INACTIVE",
                }

            if self.error_state is not None:

                return {
                    "status": "error",
                    "device_id": self.device_id,
                    "action": "resume",
                    "reason": "DEVICE_ERROR",
                    "error": self.error_state,
                }

            self._set_lifecycle_state(
                DEVICE_RUNNING,
                reason="resume",
            )

            try:
                await self.start_monitor()

            except Exception as exc:

                logger.debug(
                    "[Device] Monitor resume failed "
                    "(%s): %s",
                    self.name,
                    exc,
                )

            return {
                "status": "success",
                "device_id": self.device_id,
                "action": "resume",
                "state": self.status,
                "active": self._active,
                "online": self.online,
            }

    # ====================================================================
    # ACTIVATE
    # ====================================================================

    async def activate(
        self,
        **kwargs: Any,
    ) -> Dict[str, Any]:

        async with self._lifecycle_lock:

            if (
                self.status == DEVICE_OFF
                and self.connection is None
                and self.type != "core"
            ):
                # Activation is allowed without a physical
                # connection. The resulting state is ON,
                # not falsely reported as connected.
                pass

            self._active = True

            if self.error_state is not None:
                state = DEVICE_ERROR
            elif self.connection is not None:
                state = DEVICE_ON
            elif self.type == "core":
                state = DEVICE_ON
            else:
                state = DEVICE_ON

            result = self._set_lifecycle_state(
                state,
                reason="activate",
            )

            return {
                **result,
                "action": "activate",
            }

    # ====================================================================
    # DEACTIVATE
    # ====================================================================

    async def deactivate(
        self,
        **kwargs: Any,
    ) -> Dict[str, Any]:

        async with self._lifecycle_lock:

            try:
                await self.stop_monitor()

            except Exception as exc:

                logger.debug(
                    "[Device] Monitor deactivate failed "
                    "(%s): %s",
                    self.name,
                    exc,
                )

            self._active = False

            result = self._set_lifecycle_state(
                DEVICE_OFF,
                reason="deactivate",
            )

            return {
                **result,
                "action": "deactivate",
                "active": False,
                "online": False,
            }

    # ====================================================================
    # REFRESH
    # ====================================================================

    async def refresh(
        self,
        perform_read: bool = False,
        **kwargs: Any,
    ) -> Dict[str, Any]:

        self.touch()

        result = {
            "status": "success",
            "device_id": self.device_id,
            "action": "refresh",
            "state": self.status,
            "active": self._active,
            "online": self.online,
            "connected": (
                self.connection is not None
            ),
            "error": self.error_state,
            "read_count": self.read_count,
            "write_count": self.write_count,
            "error_count": self.error_count,
            "timestamp": (
                datetime.datetime.now(
                    datetime.timezone.utc
                ).isoformat()
            ),
            "lifecycle": (
                self.lifecycle_snapshot()
            ),
        }

        # Explicitly opt-in physical/device I/O.
        # A normal refresh is state-only.
        if perform_read:

            if not self._active:

                result[
                    "read_skipped"
                ] = "DEVICE_INACTIVE"

            elif self.status in {
                DEVICE_PAUSED,
                DEVICE_STOPPED,
                DEVICE_OFF,
            }:

                result[
                    "read_skipped"
                ] = self.status

            else:

                try:

                    result[
                        "read"
                    ] = await self.read()

                except Exception as exc:

                    result[
                        "read_error"
                    ] = {
                        "type": type(exc).__name__,
                        "message": str(exc),
                    }

        return result

    # ====================================================================
    # UNIFIED CONTROL DISPATCHER
    #
    # IMPORTANT:
    #
    # This does NOT make Device the command authority.
    #
    # QbitDialer is still responsible for:
    #
    #     admission
    #     authorization
    #     command routing
    #     execution-plane ownership
    #
    # Device.control() only resolves the already-authorized
    # device action into the concrete Device actuator method.
    # ====================================================================

    async def control(
        self,
        action: Any,
        **kwargs: Any,
    ) -> Dict[str, Any]:

        if action is None:

            return {
                "status": "error",
                "device_id": self.device_id,
                "reason": "MISSING_ACTION",
                "available_controls": (
                    self.available_controls()
                ),
            }

        normalized = self.CONTROL_ALIASES.get(
            str(action).strip().lower()
        )

        if normalized is None:

            return {
                "status": "error",
                "device_id": self.device_id,
                "action": action,
                "reason": "UNSUPPORTED_DEVICE_ACTION",
                "available_controls": (
                    self.available_controls()
                ),
            }

        handler = getattr(
            self,
            normalized,
            None,
        )

        if not callable(handler):

            return {
                "status": "error",
                "device_id": self.device_id,
                "action": normalized,
                "reason": "CONTROL_HANDLER_UNAVAILABLE",
            }

        try:

            result = await maybe_await(
                handler(**kwargs)
            )

            if isinstance(result, dict):

                result.setdefault(
                    "device_id",
                    self.device_id,
                )

                result.setdefault(
                    "action",
                    normalized,
                )

            return result

        except asyncio.CancelledError:
            raise

        except Exception as exc:

            logger.exception(
                "[Device] Control failed | "
                "device=%s | action=%s",
                self.device_id,
                normalized,
            )

            return {
                "status": "error",
                "device_id": self.device_id,
                "action": normalized,
                "reason": "CONTROL_EXECUTION_ERROR",
                "error": str(exc),
                "error_type": type(exc).__name__,
            }

    # ====================================================================
    # MONITOR
    # ====================================================================

    async def monitor(
        self,
        interval: float = DEFAULT_READ_INTERVAL,
    ) -> None:

        interval = self.set_read_interval(
            interval
        )

        try:

            while self._active:

                # STOPPED and PAUSED are intentionally
                # quiet states. The monitor task normally
                # gets cancelled when entering them, but
                # this guard prevents stale iterations
                # from generating heartbeat activity.
                if self.status not in {
                    DEVICE_PAUSED,
                    DEVICE_STOPPED,
                    DEVICE_OFF,
                    DEVICE_ERROR,
                }:

                    self.heartbeat()

                await asyncio.sleep(
                    interval
                )

        except asyncio.CancelledError:

            logger.debug(
                "[Device] Monitor cancelled: %s",
                self.name,
            )

            raise

        except Exception as exc:

            self.set_error(
                f"Monitor error: {exc}"
            )

            logger.warning(
                "[Device] Monitor error (%s): %s",
                self.name,
                exc,
            )

    async def start_monitor(
        self,
        interval: float = DEFAULT_READ_INTERVAL,
    ) -> bool:

        if not self._active:
            return False

        if self.status in {
            DEVICE_PAUSED,
            DEVICE_STOPPED,
            DEVICE_OFF,
            DEVICE_ERROR,
        }:
            return False

        if (
            self._monitor_task
            and not self._monitor_task.done()
        ):
            return True

        self._monitor_task = (
            asyncio.create_task(
                self.monitor(interval)
            )
        )

        return True

    async def stop_monitor(
        self,
    ) -> None:

        task = self._monitor_task

        self._monitor_task = None

        if task is None:
            return

        if task.done():
            return

        current_task = None

        try:
            current_task = (
                asyncio.current_task()
            )
        except RuntimeError:
            current_task = None

        # Never cancel/await ourselves.
        if task is current_task:
            return

        task.cancel()

        try:
            await task

        except asyncio.CancelledError:
            pass

        except Exception as exc:

            logger.debug(
                "[Device] Monitor task shutdown "
                "error (%s): %s",
                self.name,
                exc,
            )

    # ====================================================================
    # LIFECYCLE / TERMINAL SHUTDOWN
    # ====================================================================

    async def async_shutdown(
        self,
    ) -> None:

        async with self._lifecycle_lock:

            if (
                not self._active
                and self.status == DEVICE_OFF
                and self.connection is None
            ):
                return

            self._active = False

            try:
                await self.stop_monitor()

            except Exception as exc:

                logger.debug(
                    "[Device] Monitor shutdown error "
                    "(%s): %s",
                    self.name,
                    exc,
                )

            try:
                await self.detach_connection()

            except Exception as exc:

                logger.debug(
                    "[Device] Connection shutdown error "
                    "(%s): %s",
                    self.name,
                    exc,
                )

            self._active = False

            self.status = DEVICE_OFF

            self.meta[
                "active"
            ] = False

            self.meta[
                "running"
            ] = False

            self.meta[
                "paused"
            ] = False

            self.meta[
                "stopped"
            ] = False

            self.meta[
                "deactivated"
            ] = True

            self.meta[
                "lifecycle_state"
            ] = DEVICE_OFF

            self.meta[
                "lifecycle_reason"
            ] = "shutdown"

            self.touch()

    async def shutdown(
        self,
    ) -> None:

        await self.async_shutdown()

    # ====================================================================
    # DEBUG / REPRESENTATION
    # ====================================================================

    def __repr__(
        self,
    ):

        return (
            f"<Device "
            f"id={self.device_id} "
            f"name={self.name} "
            f"label={self.label} "
            f"type={self.type} "
            f"status={self.status} "
            f"port={self.port} "
            f"domain={self.domain} "
            f"active={self._active} "
            f"channels={self.channels}>"
        )


# ========================================================================
# DEVICE REGISTRY
# ========================================================================

class DeviceRegistry:

    def __init__(
        self,
    ):

        self._devices: Dict[
            str,
            Device,
        ] = {}

        self._lock = asyncio.Lock()

    # ====================================================================
    # REGISTER
    # ====================================================================

    async def register(
        self,
        device: Device,
    ) -> Device:

        if not isinstance(
            device,
            Device,
        ):
            raise TypeError(
                "DeviceRegistry.register() "
                "requires a Device instance"
            )

        async with self._lock:

            self._devices[
                device.device_id
            ] = device

        return device

    # ====================================================================
    # UNREGISTER
    # ====================================================================

    async def unregister(
        self,
        device_id: str,
    ) -> Optional[Device]:

        async with self._lock:

            device = self._devices.pop(
                device_id,
                None,
            )

        if device is not None:

            try:

                await device.async_shutdown()

            except Exception as exc:

                logger.debug(
                    "[DeviceRegistry] Device shutdown "
                    "error (%s): %s",
                    device_id,
                    exc,
                )

        return device

    # ====================================================================
    # LOOKUP
    # ====================================================================

    async def get(
        self,
        device_id: str,
    ) -> Optional[Device]:

        async with self._lock:

            return self._devices.get(
                device_id
            )

    async def list_devices(
        self,
    ) -> List[Device]:

        async with self._lock:

            return list(
                self._devices.values()
            )

    async def find_by_name(
        self,
        name: str,
    ) -> List[Device]:

        async with self._lock:

            return [
                device
                for device
                in self._devices.values()
                if device.name == name
            ]

    async def find_by_capability(
        self,
        capability: str,
    ) -> List[Device]:

        async with self._lock:

            return [
                device
                for device
                in self._devices.values()
                if device.has_capability(
                    capability
                )
            ]

    async def find_by_type(
        self,
        device_type: str,
    ) -> List[Device]:

        async with self._lock:

            return [
                device
                for device
                in self._devices.values()
                if device.type == device_type
            ]

    # ====================================================================
    # DEVICE CONTROL
    #
    # Registry delegates only.
    #
    # It does not become command authority.
    # ====================================================================

    async def control(
        self,
        device_id: str,
        action: Any,
        **kwargs: Any,
    ) -> Dict[str, Any]:

        device = await self.get(
            device_id
        )

        if device is None:

            return {
                "status": "error",
                "device_id": device_id,
                "action": action,
                "reason": "DEVICE_NOT_FOUND",
            }

        controller = getattr(
            device,
            "control",
            None,
        )

        if not callable(controller):

            return {
                "status": "error",
                "device_id": device_id,
                "action": action,
                "reason": "DEVICE_CONTROL_UNAVAILABLE",
            }

        return await maybe_await(
            controller(
                action,
                **kwargs,
            )
        )

    async def control_by_name(
        self,
        name: str,
        action: Any,
        **kwargs: Any,
    ) -> List[Dict[str, Any]]:

        devices = await self.find_by_name(
            name
        )

        if not devices:

            return [
                {
                    "status": "error",
                    "name": name,
                    "action": action,
                    "reason": "DEVICE_NOT_FOUND",
                }
            ]

        results = []

        for device in devices:

            try:

                results.append(
                    await device.control(
                        action,
                        **kwargs,
                    )
                )

            except Exception as exc:

                results.append(
                    {
                        "status": "error",
                        "device_id": device.device_id,
                        "action": action,
                        "reason": "CONTROL_EXECUTION_ERROR",
                        "error": str(exc),
                        "error_type": type(exc).__name__,
                    }
                )

        return results

    # ====================================================================
    # CONTROL CAPABILITIES
    # ====================================================================

    async def control_capabilities(
        self,
    ) -> Dict[str, Any]:

        async with self._lock:

            devices = list(
                self._devices.values()
            )

        result = {}

        for device in devices:

            provider = getattr(
                device,
                "control_capabilities",
                None,
            )

            if callable(provider):

                try:

                    result[
                        device.device_id
                    ] = provider()

                except Exception as exc:

                    result[
                        device.device_id
                    ] = {
                        "device_id": device.device_id,
                        "error": str(exc),
                    }

        return result

    async def available_controls(
        self,
    ) -> Dict[str, List[str]]:

        async with self._lock:

            devices = list(
                self._devices.values()
            )

        result = {}

        for device in devices:

            provider = getattr(
                device,
                "available_controls",
                None,
            )

            if callable(provider):

                try:

                    result[
                        device.device_id
                    ] = list(
                        provider()
                    )

                except Exception:

                    result[
                        device.device_id
                    ] = []

        return result

    # ====================================================================
    # HEALTH / STATE
    # ====================================================================

    async def heartbeat_all(
        self,
    ):

        async with self._lock:

            devices = list(
                self._devices.values()
            )

        for device in devices:

            try:

                device.heartbeat()

            except Exception as exc:

                logger.debug(
                    "[DeviceRegistry] Heartbeat error "
                    "(%s): %s",
                    device.name,
                    exc,
                )

    async def refresh_all(
        self,
        perform_read: bool = False,
    ) -> List[Dict[str, Any]]:

        async with self._lock:

            devices = list(
                self._devices.values()
            )

        results = []

        for device in devices:

            try:

                results.append(
                    await device.refresh(
                        perform_read=perform_read
                    )
                )

            except Exception as exc:

                results.append(
                    {
                        "status": "error",
                        "device_id": device.device_id,
                        "action": "refresh",
                        "reason": (
                            "REFRESH_EXECUTION_ERROR"
                        ),
                        "error": str(exc),
                        "error_type": (
                            type(exc).__name__
                        ),
                    }
                )

        return results

    async def shutdown_all(
        self,
    ):

        async with self._lock:

            devices = list(
                self._devices.values()
            )

        for device in devices:

            try:

                await device.async_shutdown()

            except Exception as exc:

                logger.warning(
                    "[DeviceRegistry] Shutdown error "
                    "(%s): %s",
                    device.name,
                    exc,
                )

    # ====================================================================
    # REPORTING
    # ====================================================================

    async def to_dict(
        self,
    ) -> List[Dict[str, Any]]:

        async with self._lock:

            return [
                device.to_dict()
                for device
                in self._devices.values()
            ]

    async def count(
        self,
    ) -> int:

        async with self._lock:

            return len(
                self._devices
            )

    # ====================================================================
    # DEBUG
    # ====================================================================

    def __repr__(
        self,
    ):

        return (
            f"<DeviceRegistry "
            f"devices={len(self._devices)}>"
        )