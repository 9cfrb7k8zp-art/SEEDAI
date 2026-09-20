# ==========================================================
# FILE: devhud_channel_controller.py
# PATH: SEED_ROOT/seed/systemutils/devhud_channel_controller.py
# VERSION: 3.0.0
# BUILD: DEVHUD / CHANNEL MANAGER / TRACKSYSTEM INTEGRATION
#
# ROLE:
#   DEVHUD presentation/navigation adapter for ChannelManager.
#
# AUTHORITY:
#   ChannelManager = channel topology / sequencing / flow context
#   TrackSystem    = track identity / track context / data flow
#   DEVHUD         = presentation / observation
#
# THIS MODULE DOES NOT:
#   - execute commands
#   - create Qbits
#   - submit commands
#   - control QbitQueueLoop
#   - control QbitDialer
#   - create authoritative Track IDs
#   - create channels through get_or_create()
#
# main3.py verified contract:
#
#   controller = DEVHUDChannelController(
#       channel_manager=cm
#   )
#
#   controller.select_channel("root")
#
# ==========================================================

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any, Optional

try:
    import tkinter as tk
    from tkinter import ttk
except Exception:
    tk = None
    ttk = None


logger = logging.getLogger("DEVHUDChannelController")


class DEVHUDChannelController:

    AUTHORITY = "DEVHUD_PRESENTATION"
    CHANNEL_AUTHORITY = "ChannelManager"
    TRACK_AUTHORITY = "TrackSystem"
    COMMAND_AUTHORITY = "QbitDialer"
    QBIT_TRANSPORT = "QbitQueueLoop"

    def __init__(
        self,
        root_frame=None,
        channel_manager=None,
        devhud_instance=None,
        storage_root="./SEED_ROOT",
        track_system=None,
        hud=None,
        event_bus=None,
        registry=None,
        channel_id=None,
        **kwargs,
    ):
        self.root = root_frame

        self.cm = channel_manager
        self.channel_manager = channel_manager

        self.devhud = devhud_instance

        self.storage_root = (
            Path(storage_root)
            if storage_root is not None
            else Path("./SEED_ROOT")
        )

        self.track_system = track_system
        self.hud = hud
        self.event_bus = event_bus
        self.registry = registry
        self.channel_id = channel_id

        # Preserve optional injected references without making them
        # authoritative here.
        self.runtime_context = kwargs.get("runtime_context")
        self.oracle = kwargs.get("oracle")
        self.qbit_dialer = kwargs.get("qbit_dialer")
        self.qbit_queue_loop = kwargs.get("qbit_queue_loop")

        self.tabs: dict[str, Any] = {}
        self.active_channel: Optional[str] = None
        self.selected_channel_path: Optional[str] = None

        self._channel_cache: dict[str, Any] = {}
        self._tree_cache: Any = None

        self._lock = threading.RLock()
        self._started = False
        self._stopped = False

        logger.info(
            "[DEVHUDChannelController] initialized | "
            "channel_manager=%s | "
            "track_system=%s | "
            "devhud=%s",
            type(self.cm).__name__ if self.cm is not None else None,
            type(self.track_system).__name__
            if self.track_system is not None
            else None,
            type(self.devhud).__name__
            if self.devhud is not None
            else None,
        )

    # ==========================================================
    # BINDING / LIFECYCLE
    # ==========================================================

    def bind(
        self,
        root_frame=None,
        channel_manager=None,
        devhud_instance=None,
        track_system=None,
        hud=None,
        event_bus=None,
        registry=None,
        channel_id=None,
        **kwargs,
    ):

        with self._lock:
            if root_frame is not None:
                self.root = root_frame

            if channel_manager is not None:
                self.cm = channel_manager
                self.channel_manager = channel_manager

            if devhud_instance is not None:
                self.devhud = devhud_instance

            if track_system is not None:
                self.track_system = track_system

            if hud is not None:
                self.hud = hud

            if event_bus is not None:
                self.event_bus = event_bus

            if registry is not None:
                self.registry = registry

            if channel_id is not None:
                self.channel_id = channel_id

            for key, value in kwargs.items():
                if value is not None:
                    setattr(self, key, value)

        return self

    # Compatibility alias for runtime wiring.
    attach_runtime = bind

    def start(self):
        with self._lock:
            self._started = True
            self._stopped = False

        self._cache_tree()

        return self.snapshot()

    def stop(self):

        with self._lock:
            self._started = False
            self._stopped = True

            frames = list(self.tabs.values())
            self.tabs.clear()

        for frame in frames:
            try:
                frame.destroy()
            except Exception:
                pass

        return True

    # ==========================================================
    # CHANNEL RESOLUTION
    # ==========================================================

    def _resolve_channel(self, channel_name):

        if channel_name is None:
            return None

        cm = self.cm

        if cm is None:
            return None

        # Verified/current ChannelManager public lookup.
        getter = getattr(cm, "get", None)

        if callable(getter):
            try:
                node = getter(channel_name)

                if node is not None:
                    return node
            except Exception:
                logger.debug(
                    "[DEVHUDChannelController] ChannelManager.get failed",
                    exc_info=True,
                )

        # Compatibility only for an older ChannelManager surface.
        getter = getattr(cm, "get_channel", None)

        if callable(getter):
            try:
                node = getter(channel_name)

                if node is not None:
                    return node
            except Exception:
                logger.debug(
                    "[DEVHUDChannelController] legacy get_channel failed",
                    exc_info=True,
                )

        return None

    # ==========================================================
    # CHANNEL DISCOVERY
    # ==========================================================

    def get_channel_tree(self):

        cm = self.cm

        if cm is None:
            return {}

        getter = getattr(cm, "get_tree", None)

        if callable(getter):
            try:
                tree = getter()
                self._tree_cache = tree
                return tree
            except Exception:
                logger.debug(
                    "[DEVHUDChannelController] get_tree failed",
                    exc_info=True,
                )

        getter = getattr(cm, "get_tree_dict", None)

        if callable(getter):
            try:
                tree = getter()
                self._tree_cache = tree
                return tree
            except Exception:
                logger.debug(
                    "[DEVHUDChannelController] get_tree_dict failed",
                    exc_info=True,
                )

        # Public ChannelManager discovery fallback.
        getter = getattr(cm, "list_channels", None)

        if callable(getter):
            try:
                channels = getter()
                self._tree_cache = channels
                return channels
            except Exception:
                logger.debug(
                    "[DEVHUDChannelController] list_channels failed",
                    exc_info=True,
                )

        return self._tree_cache or {}

    def _cache_tree(self):
        tree = self.get_channel_tree()

        with self._lock:
            self._tree_cache = tree

            if isinstance(tree, dict):
                self._channel_cache = dict(tree)

        return tree

    def list_channels(self):
        cm = self.cm

        if cm is None:
            return []

        getter = getattr(cm, "list_channels", None)

        if callable(getter):
            try:
                result = getter()

                if result is None:
                    return []

                return list(result)
            except Exception:
                logger.debug(
                    "[DEVHUDChannelController] list_channels failed",
                    exc_info=True,
                )

        tree = self.get_channel_tree()

        if isinstance(tree, dict):
            return list(tree.values())

        if isinstance(tree, (list, tuple, set)):
            return list(tree)

        return []

    # ==========================================================
    # CHANNEL SELECTION
    # ==========================================================

    def select_channel(self, channel_name):

        node = self._resolve_channel(channel_name)

        with self._lock:
            self.selected_channel_path = str(channel_name)
            self.active_channel = str(channel_name)

        # DEVHUD is optional because main3.py boots the channel
        # controller before the UI is attached.
        if self.devhud is not None:
            try:
                setattr(
                    self.devhud,
                    "selected_channel_path",
                    str(channel_name),
                )
            except Exception:
                pass

            callback = getattr(
                self.devhud,
                "on_channel_selected",
                None,
            )

            if callable(callback):
                try:
                    callback(
                        channel_name,
                        node,
                    )
                except TypeError:
                    try:
                        callback(channel_name)
                    except Exception:
                        logger.debug(
                            "[DEVHUDChannelController] "
                            "DEVHUD selection callback failed",
                            exc_info=True,
                        )
                except Exception:
                    logger.debug(
                        "[DEVHUDChannelController] "
                        "DEVHUD selection callback failed",
                        exc_info=True,
                    )

        self.switch(channel_name)

        return node

    def switch(self, channel_name):

        node = self._resolve_channel(channel_name)

        with self._lock:
            self.active_channel = str(channel_name)
            self.selected_channel_path = str(channel_name)

        self._show_channel_frame(
            str(channel_name)
        )

        return node

    def get_selected_channel(self):

        path = self.selected_channel_path

        if not path and self.devhud is not None:
            path = getattr(
                self.devhud,
                "selected_channel_path",
                None,
            )

        if not path:
            return None

        return self._resolve_channel(path)

    def get_selected_channel_info(self):
        node = self.get_selected_channel()

        if node is None:
            return None

        return self._channel_to_dict(node)

    def get_channel_info(self, channel_name):
        node = self._resolve_channel(channel_name)

        if node is None:
            return None

        return self._channel_to_dict(node)

    # ==========================================================
    # TK CHANNEL PRESENTATION
    # ==========================================================

    def attach_channel(self, channel_node):

        if channel_node is None:
            return None

        if ttk is None:
            logger.warning(
                "[DEVHUDChannelController] tkinter/ttk unavailable"
            )
            return None

        if self.root is None:
            logger.debug(
                "[DEVHUDChannelController] "
                "root frame not attached; channel frame deferred"
            )
            return None

        name = getattr(
            channel_node,
            "name",
            None,
        )

        if not name:
            name = str(channel_node)

        name = str(name)

        with self._lock:
            existing = self.tabs.get(name)

            if existing is not None:
                return existing

        try:
            frame = ttk.Frame(
                self.root
            )

            frame.grid(
                row=0,
                column=0,
                sticky="nsew",
            )

            try:
                frame.grid_remove()
            except Exception:
                frame.grid_forget()

            with self._lock:
                self.tabs[name] = frame

            return frame

        except Exception:
            logger.exception(
                "[DEVHUDChannelController] "
                "failed to attach channel frame | channel=%s",
                name,
            )

            return None

    def _show_channel_frame(self, channel_name):

        if self.root is None:
            return False

        def _show():
            with self._lock:
                frames = dict(self.tabs)

            selected = frames.get(
                str(channel_name)
            )

            if selected is None:
                node = self._resolve_channel(
                    channel_name
                )

                if node is not None:
                    selected = self.attach_channel(
                        node
                    )

            for name, frame in frames.items():
                try:
                    frame.grid_remove()
                except Exception:
                    try:
                        frame.grid_forget()
                    except Exception:
                        pass

            if selected is not None:
                try:
                    selected.grid(
                        row=0,
                        column=0,
                        sticky="nsew",
                    )
                except Exception:
                    pass

            with self._lock:
                self.tabs[str(channel_name)] = selected

        try:
            after = getattr(
                self.root,
                "after",
                None,
            )

            if callable(after):
                after(
                    0,
                    _show,
                )
            else:
                _show()

            return True

        except Exception:
            logger.debug(
                "[DEVHUDChannelController] "
                "channel frame switch failed",
                exc_info=True,
            )

            return False

    # ==========================================================
    # TRACK DISCOVERY
    # ==========================================================

    @staticmethod
    def _track_identity(track):

        if track is None:
            return None

        if isinstance(track, dict):
            return (
                track.get("track_id")
                or track.get("id")
                or track.get("name")
            )

        return (
            getattr(
                track,
                "track_id",
                None,
            )
            or getattr(
                track,
                "id",
                None,
            )
            or getattr(
                track,
                "name",
                None,
            )
        )

    @staticmethod
    def _node_tracks(node):
        if node is None:
            return []

        tracks = getattr(
            node,
            "tracks",
            None,
        )

        if tracks is None:
            tracks = getattr(
                node,
                "track",
                None,
            )

        if tracks is None:
            return []

        if isinstance(
            tracks,
            dict,
        ):
            return list(
                tracks.values()
            )

        if isinstance(
            tracks,
            (list, tuple, set),
        ):
            return list(tracks)

        return [tracks]

    def get_tracks(self):

        tracks = {}

        for node in self.list_channels():
            for track in self._node_tracks(node):
                identity = self._track_identity(track)

                if identity is None:
                    continue

                tracks[str(identity)] = track

        # Compatibility discovery from TrackSystem only.
        #
        # No new track identity is generated here.
        if not tracks and self.track_system is not None:

            for attribute in (
                "tracks",
                "_tracks",
                "track_registry",
            ):
                registry = getattr(
                    self.track_system,
                    attribute,
                    None,
                )

                if registry is None:
                    continue

                try:
                    values = (
                        registry.values()
                        if isinstance(
                            registry,
                            dict,
                        )
                        else registry
                    )

                    for track in values:
                        identity = self._track_identity(
                            track
                        )

                        if identity is not None:
                            tracks[str(identity)] = track

                    if tracks:
                        break

                except Exception:
                    logger.debug(
                        "[DEVHUDChannelController] "
                        "TrackSystem discovery failed | attribute=%s",
                        attribute,
                        exc_info=True,
                    )

        return list(
            tracks.values()
        )

    def get_channels_for_track(self, track_name):

        if track_name is None:
            return []

        wanted = str(
            track_name
        )

        channels = []

        for node in self.list_channels():
            for track in self._node_tracks(node):
                identity = self._track_identity(
                    track
                )

                if identity is not None and str(
                    identity
                ) == wanted:
                    channels.append(node)
                    break

        return channels

    def get_track(self, track_id):

        if not track_id:
            return None

        ts = self.track_system

        if ts is None:
            return None

        getter = getattr(
            ts,
            "get_track",
            None,
        )

        if callable(getter):
            try:
                result = getter(
                    track_id
                )

                if result is not None:
                    return result

            except Exception:
                logger.debug(
                    "[DEVHUDChannelController] "
                    "TrackSystem.get_track failed",
                    exc_info=True,
                )

        getter = getattr(
            ts,
            "get_track_context",
            None,
        )

        if callable(getter):
            try:
                return getter(
                    track_id
                )
            except Exception:
                logger.debug(
                    "[DEVHUDChannelController] "
                    "TrackSystem.get_track_context failed",
                    exc_info=True,
                )

        return None

    # ==========================================================
    # CHANNEL SERIALIZATION
    # ==========================================================

    @staticmethod
    def _channel_to_dict(node):
        if node is None:
            return None

        serializer = getattr(
            node,
            "to_dict",
            None,
        )

        if callable(serializer):
            try:
                value = serializer()

                if isinstance(
                    value,
                    dict,
                ):
                    return dict(value)

            except Exception:
                logger.debug(
                    "[DEVHUDChannelController] "
                    "ChannelNode.to_dict failed",
                    exc_info=True,
                )

        if isinstance(
            node,
            dict,
        ):
            return dict(node)

        result = {}

        for attribute in (
            "name",
            "path",
            "parent",
            "enabled",
            "flow_enabled",
            "qbit_allowed",
            "hud_visible",
            "sequence",
            "last_timestamp",
            "metadata",
            "tracks",
        ):
            try:
                value = getattr(
                    node,
                    attribute,
                    None,
                )

                if attribute == "parent" and value is not None:
                    value = getattr(
                        value,
                        "path",
                        None,
                    ) or getattr(
                        value,
                        "name",
                        None,
                    )

                if attribute == "tracks":
                    value = [
                        DEVHUDChannelController._track_identity(
                            track
                        )
                        for track in (
                            value or []
                        )
                    ]

                result[attribute] = value

            except Exception:
                pass

        return result

    # ==========================================================
    # PRESENTATION SNAPSHOT
    # ==========================================================

    def snapshot(self):

        with self._lock:
            selected = self.selected_channel_path
            active = self.active_channel
            tab_names = list(
                self.tabs.keys()
            )
            started = self._started
            stopped = self._stopped

        return {
            "controller": "DEVHUDChannelController",
            "authority": self.AUTHORITY,
            "channel_authority": self.CHANNEL_AUTHORITY,
            "track_authority": self.TRACK_AUTHORITY,
            "command_authority": self.COMMAND_AUTHORITY,
            "qbit_transport": self.QBIT_TRANSPORT,
            "started": started,
            "stopped": stopped,
            "selected_channel": selected,
            "active_channel": active,
            "tabs": tab_names,
            "channel_manager": (
                type(self.cm).__name__
                if self.cm is not None
                else None
            ),
            "track_system": (
                type(self.track_system).__name__
                if self.track_system is not None
                else None
            ),
            "devhud": (
                type(self.devhud).__name__
                if self.devhud is not None
                else None
            ),
        }


__all__ = [
    "DEVHUDChannelController",
]