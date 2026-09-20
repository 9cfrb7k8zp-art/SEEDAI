# ==========================================================
# FILE: DEVHUD_channels.py
# PATH: SEED_ROOT/seed/systemutils/DEVHUD_channels.py
# VERSION: 0.1
# UPDATED: 2026-01-03
# ==========================================================
# PURPOSE:
#   DEVHUD adapter for ChannelManager
#
#   - Builds left-side channel tree     - Expose HUD-safe channel tree
#   - Handles channel selection     - Provide channel data view window
#   - Provides right-panel channel details
#   - Exposes track-based views     - Maintain selected channel state
#   - Allows safe flag toggling     - Allow controlled flag toggling
#         Valid flags:
#        - enabled
#        - flow_enabled
#        - qbit_allowed
#        - hud_visible
#   NOTE:
#   This module DOES NOT modify ChannelManager.
#   It is a pure consumer / adapter layer.
# ==========================================================

from typing import Dict, Any, Optional, List
from pathlib import Path
import json
import threading
import time

from seed.core.channel_manager import ChannelManager, ChannelNode
from seed.core.channel_id import ChannelID


# ==========================================================
# DEVHUD Channel Controller
# ==========================================================

class DEVHUDChannelController:

    def __init__(
        self,
        channel_manager: ChannelManager,
        *,
        channel_id=ChannelID,
        track_system=None,
        storage_root=None,
        engines=None,
    ):
        self.cm = channel_manager
        self.channel_id = channel_id or ChannelID
        self.track_system = track_system
        self.selected_channel_path = []
        self.selected_channel_path = None

        self.storage_root = Path(
            storage_root or getattr(
                channel_manager,
                "storage_root",
                "./SEED_ROOT",
            )
        )
        self.settings_path = (
            self.storage_root
            / "config"
            / "devhud_engine_settings.json"
        )
        self._settings_lock = threading.RLock()

        self.engines = dict(engines or {})
        self.engine_settings = self._load_engine_settings()

    # ======================================================
    # AUTHORITATIVE RUNTIME BINDING
    # ======================================================

    def bind_runtime(
        self,
        *,
        channel_manager=None,
        channel_id=None,
        track_system=None,
        engines=None,
    ):
        """Bind existing system authorities; never creates replacements."""
        if channel_manager is not None:
            self.cm = channel_manager

        if channel_id is not None:
            self.channel_id = channel_id
        elif self.channel_id is None:
            self.channel_id = ChannelID

        if track_system is not None:
            self.track_system = track_system

        if engines:
            self.engines.update(
                {
                    str(name): engine
                    for name, engine in engines.items()
                    if engine is not None
                }
            )

        return self.runtime_status()

    def runtime_status(self) -> Dict[str, Any]:
        return {
            "channel_manager": self.cm is not None,
            "channel_id": self.channel_id is not None,
            "channel_nodes": self.cm is not None,
            "track_system": self.track_system is not None,
            "engines": sorted(self.engines.keys()),
        }

    # ======================================================
    # CHANNEL ID / TRACK BRIDGE
    # ======================================================

    def channel_identity(self, channel_path: str) -> Dict[str, Any]:
        node = self.cm.get_channel(channel_path)
        channel_id = self.channel_id

        result = {
            "path": channel_path,
            "name": getattr(node, "name", channel_path),
            "tracks": sorted(
                str(track)
                for track in getattr(node, "tracks", set())
            ),
        }

        for method_name in (
            "get",
            "inspect",
            "status",
            "snapshot",
            "telemetry",
        ):
            method = getattr(channel_id, method_name, None)
            if not callable(method):
                continue
            try:
                value = method(channel_path)
                result["channel_id"] = value
                break
            except TypeError:
                continue
            except Exception:
                break

        if "channel_id" not in result:
            result["channel_id"] = channel_path

        return result

    def get_track_context(self, track_id: str = None) -> Dict[str, Any]:
        ts = self.track_system
        if ts is None:
            return {
                "track_id": track_id,
                "available": False,
            }

        result = {
            "track_id": track_id,
            "available": True,
        }

        for method_name in (
            "get_track",
            "get_context",
            "get_track_context",
            "snapshot",
            "status",
        ):
            method = getattr(ts, method_name, None)
            if not callable(method):
                continue
            try:
                value = (
                    method(track_id)
                    if track_id is not None
                    else method()
                )
                result["context"] = value
                break
            except TypeError:
                continue
            except Exception:
                break

        return result

    def get_channels_for_track(self, track: str) -> List[str]:
        channels = self.cm.channels_for_track(track)
        return sorted(str(path) for path in channels)

    # ======================================================
    # ENGINE SETTINGS — PERSISTED / ALLOWLISTED
    # ======================================================

    DEFAULT_ENGINE_SETTINGS = {
        "qbit_dialer": {
            "qbit_rate_hz": 10.0,
            "telemetry_rate_hz": 2.0,
            "single_task": True,
            "heartbeat_supervised": True,
        },
        "compute_brain": {
            "enabled": True,
        },
        "transformer_brain": {
            "enabled": True,
        },
        "intent_engine": {
            "enabled": True,
        },
        "analytics_engine": {
            "enabled": True,
        },
        "action_engine": {
            "proposal_only": True,
        },
        "adaptive_engine": {
            "enabled": True,
        },
        "oracle": {
            "passive": True,
        },
    }

    SETTING_ALIASES = {
        "qbit_rate_hz": ("qbit_rate_hz", "qbit_rate", "rate_hz"),
        "telemetry_rate_hz": (
            "telemetry_rate_hz",
            "telemetry_rate",
        ),
        "single_task": ("single_task",),
        "heartbeat_supervised": ("heartbeat_supervised",),
        "enabled": ("enabled", "active"),
        "proposal_only": ("proposal_only", "execution_required"),
        "passive": ("passive", "lifecycle_gated"),
    }

    def _load_engine_settings(self):
        defaults = json.loads(
            json.dumps(self.DEFAULT_ENGINE_SETTINGS)
        )

        try:
            if self.settings_path.exists():
                saved = json.loads(
                    self.settings_path.read_text(
                        encoding="utf-8"
                    )
                )
                for engine, values in saved.items():
                    if (
                        engine in defaults
                        and isinstance(values, dict)
                    ):
                        defaults[engine].update(values)
        except Exception:
            pass

        return defaults

    def save_engine_settings(self):
        with self._settings_lock:
            self.settings_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )
            self.settings_path.write_text(
                json.dumps(
                    self.engine_settings,
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
        return True

    def get_engine_settings(self):
        with self._settings_lock:
            return json.loads(
                json.dumps(self.engine_settings)
            )

    def set_engine_setting(
        self,
        engine_name: str,
        setting: str,
        value,
    ) -> Dict[str, Any]:
        engine_name = str(engine_name).strip().lower()
        setting = str(setting).strip().lower()

        if engine_name not in self.DEFAULT_ENGINE_SETTINGS:
            raise KeyError(
                f"Unsupported engine: {engine_name}"
            )

        if setting not in self.DEFAULT_ENGINE_SETTINGS[engine_name]:
            raise KeyError(
                f"Unsupported setting: {engine_name}.{setting}"
            )

        if setting in {
            "qbit_rate_hz",
            "telemetry_rate_hz",
        }:
            value = max(0.0, float(value))

        elif setting in {
            "single_task",
            "heartbeat_supervised",
            "enabled",
            "proposal_only",
            "passive",
        }:
            if isinstance(value, str):
                value = value.strip().lower() in {
                    "1",
                    "true",
                    "yes",
                    "on",
                }
            value = bool(value)

        self.engine_settings[engine_name][setting] = value

        engine = self.engines.get(engine_name)
        aliases = self.SETTING_ALIASES.get(
            setting,
            (setting,),
        )

        applied = False

        if engine is not None:
            for attr_name in aliases:
                if hasattr(engine, attr_name):
                    try:
                        setattr(
                            engine,
                            attr_name,
                            value,
                        )
                        applied = True
                        break
                    except Exception:
                        pass

            # ActionEngine safety contract:
            # proposal_only=True must imply execution_required=False.
            if (
                engine_name == "action_engine"
                and setting == "proposal_only"
                and hasattr(engine, "execution_required")
            ):
                try:
                    engine.execution_required = not value
                    applied = True
                except Exception:
                    pass

        self.save_engine_settings()

        return {
            "ok": True,
            "engine": engine_name,
            "setting": setting,
            "value": value,
            "applied_live": applied,
            "persisted": True,
            "timestamp": time.time(),
        }

    def apply_all_engine_settings(self):
        results = []
        for engine_name, values in self.engine_settings.items():
            for setting, value in values.items():
                try:
                    results.append(
                        self.set_engine_setting(
                            engine_name,
                            setting,
                            value,
                        )
                    )
                except Exception as exc:
                    results.append(
                        {
                            "ok": False,
                            "engine": engine_name,
                            "setting": setting,
                            "error": str(exc),
                        }
                    )
        return results

    # ======================================================
    # Channel Tree (Left Panel)
    # ======================================================

    def get_channel_tree(self) -> Dict[str, Any]:
        return self.cm.get_tree_dict()

    # ======================================================
    # Channel Selection
    # ======================================================

    def select_channel(self, channel_path: str) -> bool:
        try:
            node: ChannelNode = self.cm.get_channel(channel_path)
        except KeyError:
            return False

        if not node.hud_visible:
            return False

        self.selected_channel_path = channel_path
        return True

    def clear_selection(self):
        self.selected_channel_path = None

    # ======================================================
    # Channel Detail Panel (Main / Right Pane)
    # ======================================================

    def get_selected_channel_info(self) -> Optional[Dict[str, Any]]:
        if not self.selected_channel_path:
            return None

        node: ChannelNode = self.cm.get_channel(self.selected_channel_path)

        return {
            "path": node.path,
            "name": node.name,
            "tracks": sorted(node.tracks),
            "flags": {
                "enabled": node.enabled,
                "flow_enabled": node.flow_enabled,
                "qbit_allowed": node.qbit_allowed,
                "hud_visible": node.hud_visible,
            },
            "sequence": node.sequence,
            "last_timestamp": node.last_timestamp,
            "metadata": dict(node.metadata),
            "children": sorted(node.children.keys()),
        }

    # ======================================================
    # Track Views (Optional DEVHUD Tabs)
    # ======================================================

    def get_tracks(self) -> List[str]:
        return self.cm.get_tracks()

    def get_channels_for_track(self, track: str) -> List[str]:
        return self.cm.channels_for_track(track)

    # ======================================================
    # HUD Actions (Controlled Mutations)
    # ======================================================

    def toggle_channel_flag(self, flag_name: str, value: bool) -> bool:
        if not self.selected_channel_path:
            return False

        self.cm.set_flags(self.selected_channel_path, **{flag_name: value})
        return True
