# ==========================================================
# FILE: channel_manager.py
# PATH: SEED_ROOT/seed/core/channel_manager.py
# VERSION: 3.0 — FULL SYSTEM / QBIT / ORACLE INTEGRATION
# UPDATED: 2026-08-30
# ==========================================================
#
# PURPOSE:
#
#   ChannelManager is the authoritative channel topology,
#   sequencing, track-membership, flow-control, and routing
#   metadata manager.
#
# ARCHITECTURE:
#
#   EventBus
#       │
#       ▼
#   ChannelManager
#       │
#       ├── ChannelNode
#       │      ├── ChannelID metadata
#       │      ├── Track membership
#       │      ├── sequence / timestamp
#       │      ├── flow permissions
#       │      └── HUD visibility
#       │
#       ├──────────────► Oracle
#       │                 observation / metadata
#       │
#       ├──────────────► QbitDialer
#       │                 channel context / routing metadata
#       │
#       └──────────────► Registry
#                         discovery / integration
#
# IMPORTANT AUTHORITY RULES:
#
#   ChannelManager
#       = channel topology + sequencing + flow context
#
#   TrackSystem
#       = track ownership / track context
#
#   Qbit
#       = data transport / identity / lineage
#
#   ComputeBrain
#       = Qbit processing / ThoughtPacket generation
#
#   TransformerBrain
#       = actionable command proposal
#
#   QbitDialer
#       = SOLE COMMAND AUTHORITY
#
#   submit_command()
#       = SOLE COMMAND ADMISSION PATH
#
#   Oracle
#       = observation / metadata / intelligence
#       NEVER command authority
#
# RAW QBITS ARE NEVER EXECUTED BY ChannelManager.
#
# ==========================================================

import asyncio
import inspect
import logging
import threading
import time
import uuid
from typing import Dict, List, Set, Optional, Any


logger = logging.getLogger("ChannelManager")

MODULE_ID = "CM-1"
MODULE_NAME = "ChannelManager"
MODULE_VERSION = "3.0"


# ==========================================================
# OPTIONAL SYSTEM IMPORTS
# ==========================================================

try:
    from seed.core.channel_id import ChannelID
except Exception:
    ChannelID = None


try:
    from seed.core.track_id_manager import TrackIDManager
except Exception:
    TrackIDManager = None


# ==========================================================
# CHANNEL NODE
# ==========================================================

class ChannelNode:

    _registry: Dict[str, "ChannelNode"] = {}
    _counters: Dict[str, int] = {}

    def __init__(
        self,
        root=None,
        name=None,
        track=None,
        path=None,
        mode=None,
        value=None,
        children=None,
        flags=None,
        metadata=None,
        parent=None,
        storage_root="./SEED_ROOT",
        **kwargs,
    ):

        self.root = root
        self.name = name or ""
        self.parent = parent

        self.path = (
            path
            if path is not None
            else self.name
        )

        self.storage_root = storage_root

        # ------------------------------------------------------
        # Child topology
        # ------------------------------------------------------

        self.children: Dict[str, "ChannelNode"] = (
            dict(children)
            if isinstance(children, dict)
            else {}
        )

        # ------------------------------------------------------
        # Track membership
        # ------------------------------------------------------

        if track is None:
            self.tracks: Set[str] = set()

        elif isinstance(track, str):
            self.tracks = {track}

        else:
            try:
                self.tracks = set(track)
            except Exception:
                self.tracks = set()

        # Backward-compatible alias.
        self.track = self.tracks

        # ------------------------------------------------------
        # Runtime state
        # ------------------------------------------------------

        self.handlers: List[Any] = []
        self.events: List[Any] = []
        self.mode = mode
        self.permissions: List[Any] = []

        self.flags = {
            "enabled": True,
            "flow_enabled": True,
            "qbit_allowed": True,
            "hud_visible": True,
        }

        if isinstance(flags, dict):
            self.flags.update(flags)

        self.enabled = bool(
            self.flags.get("enabled", True)
        )

        self.flow_enabled = bool(
            self.flags.get("flow_enabled", True)
        )

        self.qbit_allowed = bool(
            self.flags.get("qbit_allowed", True)
        )

        self.hud_visible = bool(
            self.flags.get("hud_visible", True)
        )

        # ------------------------------------------------------
        # Sequencing
        # ------------------------------------------------------

        self.sequence = 0
        self.last_timestamp = 0.0

        # ------------------------------------------------------
        # Metadata
        # ------------------------------------------------------

        self.metadata: Dict[str, Any] = {}

        if isinstance(metadata, dict):
            self.metadata.update(metadata)

        self.value = value

        # ------------------------------------------------------
        # Arbitrary extension attributes
        # ------------------------------------------------------

        for key, val in kwargs.items():
            setattr(self, key, val)

        self._lock = threading.RLock()

        # ------------------------------------------------------
        # Local registry
        # ------------------------------------------------------

        if self.name:
            ChannelNode._registry[self.name] = self

    # ======================================================
    # REGISTRY
    # ======================================================

    @classmethod
    def get(cls, name: str):

        if name in cls._registry:
            return cls._registry[name]

        return cls(
            root=None,
            name=name,
            path=name,
        )

    @classmethod
    def next(cls, prefix: str):

        prefix = str(prefix or "CHANNEL")

        cls._counters.setdefault(
            prefix,
            0,
        )

        cls._counters[prefix] += 1

        return (
            f"{prefix}."
            f"{cls._counters[prefix]}"
        )

    # ======================================================
    # SEQUENCING
    # ======================================================

    def next_sequence(self) -> int:

        with self._lock:

            self.sequence += 1

            return self.sequence

    def next_timestamp(self) -> float:

        with self._lock:

            now = time.monotonic()

            if now <= self.last_timestamp:
                now = (
                    self.last_timestamp
                    + 1e-9
                )

            self.last_timestamp = now

            return now

    # ======================================================
    # EVENT / DATA
    # ======================================================

    def emit(self, event):

        with self._lock:
            self.events.append(event)

            if len(self.events) > 500:
                del self.events[:-500]

        return event

    def send(self, data: Any):

        event = {
            "type": "CHANNEL_DATA",
            "channel": self.path,
            "data": data,
            "timestamp": time.time(),
        }

        self.emit(event)

        return event

    # ======================================================
    # SERIALIZATION
    # ======================================================

    def to_dict(
        self,
        recursive: bool = True,
    ) -> Dict[str, Any]:

        with self._lock:

            data = {
                "name": self.name,
                "path": self.path,
                "tracks": sorted(
                    str(track)
                    for track in self.tracks
                ),
                "sequence": self.sequence,
                "last_timestamp": self.last_timestamp,
                "enabled": self.enabled,
                "flow_enabled": self.flow_enabled,
                "qbit_allowed": self.qbit_allowed,
                "hud_visible": self.hud_visible,
                "mode": self.mode,
                "value": self.value,
                "metadata": dict(self.metadata),
            }

            if recursive:

                data["children"] = {
                    name: child.to_dict(
                        recursive=True
                    )
                    for name, child in self.children.items()
                    if child.hud_visible
                }

            return data

    def __str__(self):

        return self.path or "ROOT"


# ==========================================================
# CHANNEL MANAGER
# ==========================================================

class ChannelManager:

    def __init__(
        self,
        root=None,
        event_bus=None,
        qbit_dialer=None,
        oracle=None,
        track_system=None,
        module_registry=None,
        channel_id=None,
        hud=None,
        emit=None,
        storage_root="./SEED_ROOT",
        **kwargs,
    ):

        self.module_id = MODULE_ID
        self.module_name = MODULE_NAME
        self.version = MODULE_VERSION

        self._lock = threading.RLock()

        # ------------------------------------------------------
        # System dependencies
        # ------------------------------------------------------

        self.event_bus = event_bus
        self.qbit_dialer = qbit_dialer
        self.oracle = oracle
        self.track_system = track_system
        self.module_registry = module_registry
        self.channel_id = channel_id or ChannelID
        self.hud = hud
        self.emit = emit
        self.storage_root = storage_root

        # Compatibility aliases.
        self.dialer = qbit_dialer
        self.registry = module_registry

        # ------------------------------------------------------
        # Runtime indexes
        # ------------------------------------------------------

        self._channels: Dict[str, ChannelNode] = {}
        self._tracks: Dict[str, Set[str]] = {}

        self.last_event = None
        self.last_qbit_context = None
        self.last_track_id = None

        self.running = False

        # ------------------------------------------------------
        # Root
        # ------------------------------------------------------

        self.root = ChannelNode(
            root=root,
            name="ROOT",
            path="ROOT",
            parent=None,
            storage_root=storage_root,
        )

        self._channels["ROOT"] = self.root

        # ------------------------------------------------------
        # Registry integration
        # ------------------------------------------------------

        self._register_with_registry()

        logger.info(
            "[ChannelManager] initialized | "
            "module=%s | version=%s",
            self.module_id,
            self.version,
        )

    # ======================================================
    # REGISTRY INTEGRATION
    # ======================================================

    def _register_with_registry(self):

        registry = self.module_registry

        if registry is None:
            return

        try:

            register = getattr(
                registry,
                "register",
                None,
            )

            if callable(register):

                try:
                    register(
                        MODULE_NAME,
                        self,
                    )

                except TypeError:

                    register(
                        self,
                    )

                return

            register_module = getattr(
                registry,
                "register_module",
                None,
            )

            if callable(register_module):

                try:
                    register_module(
                        MODULE_NAME,
                        self,
                    )

                except TypeError:

                    register_module(
                        self,
                    )

        except Exception:

            logger.debug(
                "[ChannelManager] registry registration skipped",
                exc_info=True,
            )

    # ======================================================
    # DEPENDENCY ATTACHMENT
    # ======================================================

    def attach_qbit_dialer(
        self,
        dialer,
    ):

        if dialer is None:
            return False

        self.qbit_dialer = dialer
        self.dialer = dialer

        logger.info(
            "[ChannelManager] QbitDialer attached"
        )

        return True

    def attach_oracle(
        self,
        oracle,
    ):

        if oracle is None:
            return False

        self.oracle = oracle

        logger.info(
            "[ChannelManager] Oracle attached"
        )

        return True

    def attach_event_bus(
        self,
        event_bus,
    ):

        if event_bus is None:
            return False

        self.event_bus = event_bus

        logger.info(
            "[ChannelManager] EventBus attached"
        )

        return True

    def attach_track_system(
        self,
        track_system,
    ):

        if track_system is None:
            return False

        self.track_system = track_system

        return True

    # ======================================================
    # EVENT EMISSION
    # ======================================================

    def _emit_event(
        self,
        event_name,
        data=None,
    ):

        payload = {
            "module": MODULE_NAME,
            "module_id": MODULE_ID,
            "event": event_name,
            "timestamp": time.time(),
            "data": data or {},
        }

        self.last_event = payload

        # --------------------------------------------------
        # Local emitter
        # --------------------------------------------------

        if callable(self.emit):

            try:

                result = self.emit(
                    event_name,
                    payload["data"],
                )

                if inspect.isawaitable(result):

                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(result)
                    except RuntimeError:
                        pass

            except Exception:

                logger.debug(
                    "[ChannelManager] local emit failed",
                    exc_info=True,
                )

        # --------------------------------------------------
        # EventBus
        # --------------------------------------------------

        event_bus = self.event_bus

        if event_bus is not None:

            emit_method = getattr(
                event_bus,
                "emit",
                None,
            )

            if callable(emit_method):

                try:

                    result = emit_method(
                        event_name,
                        data=payload["data"],
                    )

                    if inspect.isawaitable(result):

                        try:
                            loop = asyncio.get_running_loop()
                            loop.create_task(result)
                        except RuntimeError:
                            pass

                except Exception:

                    logger.debug(
                        "[ChannelManager] EventBus emission failed",
                        exc_info=True,
                    )

        return payload

    # ======================================================
    # ORACLE OBSERVATION
    # ======================================================

    def _send_to_oracle(
        self,
        event_name,
        metadata,
    ):

        oracle = self.oracle

        if oracle is None:
            return None

        observation = {
            "source": MODULE_NAME,
            "module_id": MODULE_ID,
            "event": event_name,
            "timestamp": time.time(),
            "channel_metadata": metadata,
        }

        try:

            for method_name in (
                "observe",
                "record",
                "receive_metadata",
                "receive_event",
                "ingest",
            ):

                method = getattr(
                    oracle,
                    method_name,
                    None,
                )

                if not callable(method):
                    continue

                try:

                    result = method(
                        observation
                    )

                except TypeError:

                    result = method(
                        event_name,
                        observation,
                    )

                if inspect.isawaitable(result):

                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(result)
                    except RuntimeError:
                        pass

                return result

        except Exception:

            logger.debug(
                "[ChannelManager] Oracle observation failed",
                exc_info=True,
            )

        return None

    # ======================================================
    # QBITDIALER CONTEXT
    # ======================================================

    def _publish_qbit_context(
        self,
        node,
        track_id=None,
    ):

        dialer = self.qbit_dialer

        context = {
            "channel": node.path,
            "channel_name": node.name,
            "channel_id": node.metadata.get(
                "channel_id",
                node.name,
            ),
            "track_id": track_id,
            "sequence": node.sequence,
            "timestamp": node.last_timestamp,
            "enabled": node.enabled,
            "flow_enabled": node.flow_enabled,
            "qbit_allowed": node.qbit_allowed,
            "metadata": dict(
                node.metadata
            ),
        }

        self.last_qbit_context = context

        if dialer is None:
            return context

        # --------------------------------------------------
        # Prefer explicit context APIs.
        # --------------------------------------------------

        for method_name in (
            "update_channel_context",
            "register_channel_context",
            "set_channel_context",
            "attach_channel_context",
        ):

            method = getattr(
                dialer,
                method_name,
                None,
            )

            if not callable(method):
                continue

            try:

                result = method(
                    context
                )

                if inspect.isawaitable(result):

                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(result)
                    except RuntimeError:
                        pass

                break

            except Exception:

                logger.debug(
                    "[ChannelManager] "
                    "QbitDialer context update failed",
                    exc_info=True,
                )

        return context

    # ======================================================
    # CHANNEL REGISTRATION
    # ======================================================

    def register_channel(
        self,
        path="",
        tracks=None,
        metadata=None,
        mode=None,
        flags=None,
        value=None,
    ) -> ChannelNode:

        # --------------------------------------------------
        # Normalize path.
        # --------------------------------------------------

        if path is None:
            path = ""

        if not isinstance(path, str):

            path = str(path)

        path = path.strip()

        path = path.replace(
            "\\",
            "/",
        )

        parts = [
            part.strip()
            for part in path.split("/")
            if part.strip()
        ]

        with self._lock:

            # --------------------------------------------------
            # Root request.
            # --------------------------------------------------

            if not parts:

                node = self.root

                if metadata:
                    node.metadata.update(metadata)

                if flags:
                    self.set_flags(
                        "ROOT",
                        **flags,
                    )

                if mode is not None:
                    node.mode = mode

                if value is not None:
                    node.value = value

                return node

            # --------------------------------------------------
            # Build missing tree nodes.
            # --------------------------------------------------

            current = self.root
            current_path = ""

            for part in parts:

                current_path = (
                    f"{current_path}/{part}"
                    if current_path
                    else part
                )

                node = self._channels.get(
                    current_path
                )

                if node is None:

                    node = ChannelNode(
                        root=self.root,
                        name=part,
                        path=current_path,
                        parent=current,
                        mode=mode,
                        value=value,
                        flags=flags,
                        storage_root=self.storage_root,
                    )

                    current.children[
                        part
                    ] = node

                    self._channels[
                        current_path
                    ] = node

                current = node

            # --------------------------------------------------
            # Apply metadata.
            # --------------------------------------------------

            if metadata:

                current.metadata.update(
                    metadata
                )

            if mode is not None:
                current.mode = mode

            if value is not None:
                current.value = value

            if flags:
                self.set_flags(
                    current.path,
                    **flags,
                )

            # --------------------------------------------------
            # Attach tracks.
            # --------------------------------------------------

            if tracks:

                if isinstance(
                    tracks,
                    str,
                ):

                    tracks = [tracks]

                for track in tracks:

                    self.attach_track(
                        current.path,
                        track,
                    )

            self._publish_qbit_context(
                current
            )

            self._emit_event(
                "CHANNEL_REGISTERED",
                current.to_dict(
                    recursive=False
                ),
            )

            self._send_to_oracle(
                "CHANNEL_REGISTERED",
                current.to_dict(
                    recursive=False
                ),
            )

            return current

    # ======================================================
    # CHANNEL ALIASES
    # ======================================================

    register = register_channel

    # ======================================================
    # CHANNEL LOOKUP
    # ======================================================

    def get_channel(
        self,
        channel_path: str,
    ) -> ChannelNode:

        if channel_path is None:
            channel_path = "ROOT"

        channel_path = str(
            channel_path
        ).strip("/")

        if not channel_path:
            channel_path = "ROOT"

        with self._lock:

            node = self._channels.get(
                channel_path
            )

            if node is None:

                raise KeyError(
                    "Channel not found: "
                    f"{channel_path}"
                )

            return node

    def get_or_create_channel(
        self,
        channel_path: str,
        **kwargs,
    ) -> ChannelNode:

        try:

            return self.get_channel(
                channel_path
            )

        except KeyError:

            return self.register_channel(
                channel_path,
                **kwargs,
            )

    # ======================================================
    # TRACK MANAGEMENT
    # ======================================================

    def attach_track(
        self,
        channel_path: str,
        track: str,
    ):

        if track is None:
            return False

        track = str(track)

        node = self.get_channel(
            channel_path
        )

        with self._lock:

            node.tracks.add(track)

            self._tracks.setdefault(
                track,
                set(),
            ).add(
                node.path
            )

            node.metadata[
                "last_track_id"
            ] = track

            self.last_track_id = track

        self._emit_event(
            "CHANNEL_TRACK_ATTACHED",
            {
                "channel": node.path,
                "track_id": track,
            },
        )

        self._send_to_oracle(
            "CHANNEL_TRACK_ATTACHED",
            {
                "channel": node.path,
                "track_id": track,
            },
        )

        self._publish_qbit_context(
            node,
            track,
        )

        return True

    def detach_track(
        self,
        channel_path: str,
        track: str,
    ):

        node = self.get_channel(
            channel_path
        )

        track = str(track)

        with self._lock:

            node.tracks.discard(
                track
            )

            if track in self._tracks:

                self._tracks[
                    track
                ].discard(
                    node.path
                )

                if not self._tracks[
                    track
                ]:

                    del self._tracks[
                        track
                    ]

        self._emit_event(
            "CHANNEL_TRACK_DETACHED",
            {
                "channel": node.path,
                "track_id": track,
            },
        )

        return True

    # ======================================================
    # SEQUENCING AUTHORITY
    # ======================================================

    def next_sequence(
        self,
        channel_path: str,
    ) -> int:

        node = self.get_channel(
            channel_path
        )

        sequence = node.next_sequence()

        node.metadata[
            "last_sequence"
        ] = sequence

        return sequence

    def next_timestamp(
        self,
        channel_path: str,
    ) -> float:

        node = self.get_channel(
            channel_path
        )

        timestamp = node.next_timestamp()

        node.metadata[
            "last_monotonic_timestamp"
        ] = timestamp

        return timestamp

    def next_channel_context(
        self,
        channel_path: str,
        track_id=None,
        qbit_id=None,
        task_id=None,
        pipeline_id=None,
    ):

        node = self.get_channel(
            channel_path
        )

        sequence = node.next_sequence()
        timestamp = node.next_timestamp()

        context = {
            "channel": node.path,
            "channel_id": node.metadata.get(
                "channel_id",
                node.name,
            ),
            "track_id": track_id,
            "qbit_id": qbit_id,
            "task_id": task_id,
            "pipeline_id": pipeline_id,
            "sequence": sequence,
            "timestamp": timestamp,
            "enabled": node.enabled,
            "flow_enabled": node.flow_enabled,
            "qbit_allowed": node.qbit_allowed,
            "metadata": dict(
                node.metadata
            ),
        }

        self.last_qbit_context = context

        self._publish_qbit_context(
            node,
            track_id,
        )

        self._send_to_oracle(
            "CHANNEL_CONTEXT",
            context,
        )

        return context

    # ======================================================
    # QBIT FLOW CONTROL
    # ======================================================

    def qbit_allowed(
        self,
        channel_path: str,
    ) -> bool:

        node = self.get_channel(
            channel_path
        )

        return bool(
            node.enabled
            and node.flow_enabled
            and node.qbit_allowed
        )

    def validate_qbit_flow(
        self,
        channel_path: str,
        qbit=None,
    ) -> bool:

        allowed = self.qbit_allowed(
            channel_path
        )

        if not allowed:

            self._emit_event(
                "QBIT_FLOW_BLOCKED",
                {
                    "channel": channel_path,
                    "qbit": qbit,
                },
            )

            self._send_to_oracle(
                "QBIT_FLOW_BLOCKED",
                {
                    "channel": channel_path,
                    "qbit": qbit,
                },
            )

        return allowed

    # ======================================================
    # DEVHUD DISCOVERY
    # ======================================================

    def get_tree(self) -> ChannelNode:

        return self.root

    def get_tree_dict(
        self,
    ) -> Dict[str, Any]:

        return self.root.to_dict(
            recursive=True
        )

    def list_channels(self) -> List[str]:

        with self._lock:

            return sorted(
                self._channels.keys()
            )

    # ======================================================
    # TRACK DISCOVERY
    # ======================================================

    def get_tracks(self) -> List[str]:

        with self._lock:

            return sorted(
                self._tracks.keys()
            )

    def channels_for_track(
        self,
        track: str,
    ) -> List[str]:

        with self._lock:

            return sorted(
                self._tracks.get(
                    str(track),
                    set(),
                )
            )

    # ======================================================
    # FLAGS / FLOW CONTROL
    # ======================================================

    def set_flags(
        self,
        channel_path: str,
        **flags,
    ):

        node = self.get_channel(
            channel_path
        )

        with node._lock:

            for key, value in flags.items():

                if key not in (
                    "enabled",
                    "flow_enabled",
                    "qbit_allowed",
                    "hud_visible",
                ):

                    continue

                bool_value = bool(value)

                setattr(
                    node,
                    key,
                    bool_value,
                )

                node.flags[
                    key
                ] = bool_value

        self._publish_qbit_context(
            node
        )

        self._emit_event(
            "CHANNEL_FLAGS_UPDATED",
            {
                "channel": node.path,
                "flags": self.get_flags(
                    node.path
                ),
            },
        )

        return self.get_flags(
            node.path
        )

    def get_flags(
        self,
        channel_path: str,
    ) -> Dict[str, bool]:

        node = self.get_channel(
            channel_path
        )

        return {
            "enabled": node.enabled,
            "flow_enabled": node.flow_enabled,
            "qbit_allowed": node.qbit_allowed,
            "hud_visible": node.hud_visible,
        }

    # ======================================================
    # METADATA
    # ======================================================

    def update_metadata(
        self,
        channel_path: str,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):

        node = self.get_channel(
            channel_path
        )

        updates = {}

        if isinstance(
            metadata,
            dict,
        ):

            updates.update(
                metadata
            )

        updates.update(
            kwargs
        )

        with node._lock:

            node.metadata.update(
                updates
            )

        self._publish_qbit_context(
            node
        )

        self._send_to_oracle(
            "CHANNEL_METADATA_UPDATED",
            {
                "channel": node.path,
                "metadata": updates,
            },
        )

        self._emit_event(
            "CHANNEL_METADATA_UPDATED",
            {
                "channel": node.path,
                "metadata": updates,
            },
        )

        return dict(
            node.metadata
        )

    def get_metadata(
        self,
        channel_path: str,
    ) -> Dict[str, Any]:

        node = self.get_channel(
            channel_path
        )

        with node._lock:

            return dict(
                node.metadata
            )

    # ======================================================
    # CHANNEL EVENT RECORDING
    # ======================================================

    def record_event(
        self,
        channel_path: str,
        event_type: str,
        data=None,
    ):

        node = self.get_channel(
            channel_path
        )

        event = {
            "event": event_type,
            "channel": node.path,
            "sequence": node.next_sequence(),
            "timestamp": time.time(),
            "monotonic_timestamp": node.next_timestamp(),
            "data": data,
        }

        node.emit(
            event
        )

        self._emit_event(
            event_type,
            event,
        )

        self._send_to_oracle(
            event_type,
            event,
        )

        return event

    # ======================================================
    # QBIT DIALER EXPORT
    # ======================================================

    def export_for_qbit(
        self,
    ) -> Dict[str, Dict[str, Any]]:

        export = {}

        with self._lock:

            for path, node in self._channels.items():

                export[path] = {
                    "name": node.name,
                    "channel_id": node.metadata.get(
                        "channel_id",
                        node.name,
                    ),
                    "tracks": sorted(
                        str(track)
                        for track in node.tracks
                    ),
                    "enabled": node.enabled,
                    "flow_enabled": node.flow_enabled,
                    "qbit_allowed": node.qbit_allowed,
                    "hud_visible": node.hud_visible,
                    "sequence": node.sequence,
                    "last_timestamp": node.last_timestamp,
                    "mode": node.mode,
                    "value": node.value,
                    "metadata": dict(
                        node.metadata
                    ),
                }

        return export

    # ======================================================
    # QBIT CONTEXT EXPORT
    # ======================================================

    def get_qbit_context(
        self,
        channel_path: str,
        qbit_id=None,
        track_id=None,
        task_id=None,
        pipeline_id=None,
    ):

        return self.next_channel_context(
            channel_path=channel_path,
            track_id=track_id,
            qbit_id=qbit_id,
            task_id=task_id,
            pipeline_id=pipeline_id,
        )

    # ======================================================
    # HUD EXPORT
    # ======================================================

    def export_for_hud(self):

        tree = self.get_tree_dict()

        payload = {
            "module": MODULE_NAME,
            "module_id": MODULE_ID,
            "version": MODULE_VERSION,
            "timestamp": time.time(),
            "channels": tree,
        }

        if self.hud is not None:

            try:

                update = getattr(
                    self.hud,
                    "update_channels",
                    None,
                )

                if callable(update):

                    result = update(
                        payload
                    )

                    if inspect.isawaitable(result):

                        try:
                            loop = asyncio.get_running_loop()
                            loop.create_task(result)
                        except RuntimeError:
                            pass

            except Exception:

                logger.debug(
                    "[ChannelManager] HUD update failed",
                    exc_info=True,
                )

        return payload

    # ======================================================
    # SYSTEM STATUS
    # ======================================================

    def status(self):

        return {
            "module": MODULE_NAME,
            "module_id": MODULE_ID,
            "version": MODULE_VERSION,
            "running": self.running,
            "channel_count": len(
                self._channels
            ),
            "track_count": len(
                self._tracks
            ),
            "qbit_dialer_connected": (
                self.qbit_dialer is not None
            ),
            "oracle_connected": (
                self.oracle is not None
            ),
            "event_bus_connected": (
                self.event_bus is not None
            ),
            "track_system_connected": (
                self.track_system is not None
            ),
            "registry_connected": (
                self.module_registry is not None
            ),
        }

    # ======================================================
    # START / STOP
    # ======================================================

    def start(self):

        self.running = True

        self._emit_event(
            "CHANNEL_MANAGER_ONLINE",
            self.status(),
        )

        self._send_to_oracle(
            "CHANNEL_MANAGER_ONLINE",
            self.status(),
        )

        logger.info(
            "[ChannelManager] ONLINE"
        )

        return True

    def stop(self):

        self.running = False

        self._emit_event(
            "CHANNEL_MANAGER_OFFLINE",
            self.status(),
        )

        logger.info(
            "[ChannelManager] OFFLINE"
        )

        return True


# ==========================================================
# END OF FILE
# ==========================================================