
# =====================================================================
# FILE: SEED_OS_Final.py
# PATH: C:\SEED_ROOT\SEED_OS_Final.py
#
# SEED AI CONTROLLED OPERATING SYSTEM
#
# VERSION: 11.0 FOUNDATION
#
# PURPOSE
# -------
# Foundational SEED AI operating environment.
#
# SEED is the operating intelligence/control layer.
# The underlying Windows/Linux host remains the physical execution
# environment until SEED owns enough of the platform to replace it.
#
# CORE PRINCIPLE
# --------------
#
#                       SEED AI
#                          |
#                +---------+---------+
#                |                   |
#             OBSERVE             THINK
#                |                   |
#                +---------+---------+
#                          |
#                       DECIDE
#                          |
#                     GOVERNANCE
#                          |
#                     QbitDialer
#                          |
#                    SYSTEM CONTROL
#
# USER INPUT IS INPUT.
#
# Users do not become command authority.
# User requests enter the same controlled input pipeline as other
# observations and are evaluated by SEED.
#
# FOUNDATION
# ----------
#
#   SEED OS
#      |
#      +-- Kernel/Runtime Context
#      +-- Stability Gate
#      +-- System State
#      +-- Filesystem
#      +-- Desktop
#      +-- Windows
#      +-- Icons
#      +-- Start Menu
#      +-- Applications / Nodes
#      +-- Tool Fabric
#      +-- Registry
#      +-- TrackSystem
#      +-- NeuralBridge
#      +-- Oracle
#      +-- EventBus
#      +-- QbitQueueLoop
#      +-- QbitDialer
#
# IMPORTANT ARCHITECTURAL RULES
# -----------------------------
#
# This file does NOT create:
#
#   - QbitDialer
#   - QbitQueueLoop
#   - EventBus
#   - SRegistry
#   - NeuralBridge
#   - Oracle
#   - TrackSystem
#
# Those are injected from the authoritative SEED runtime.
#
# This file also does not create a second autonomous command plane.
#
# =====================================================================

from __future__ import annotations

import copy
import json
import logging
import os
import threading
import time
import uuid
from pathlib import Path


# =====================================================================
# LOGGING
# =====================================================================

log = logging.getLogger("SEED_OS")


def telemetry(event, data=None):
    log.info(
        "SEED_OS | %s | %s",
        event,
        data,
    )


# =====================================================================
# TRACK ID
# =====================================================================

def gen_track_id(prefix="SEEDCore_in"):
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


# =====================================================================
# PATH / FILESYSTEM MODEL
# =====================================================================

class SEEDFileSystem:

    name = "seed_filesystem"

    DIRECTORIES = (
        "Desktop",
        "Documents",
        "Downloads",
        "Applications",
        "System",
        "System/Nodes",
        "System/Tools",
        "System/Registry",
        "System/Memory",
        "System/Logs",
        "System/State",
        "Users",
        "Shared",
        "Workspace",
        "Inbox",
        "Quarantine",
    )

    def __init__(
        self,
        root=None,
    ):
        self.root = Path(
            root or
            os.environ.get(
                "SEED_OS_ROOT",
                r"C:\SEED_ROOT",
            )
        ).resolve()

        self._lock = threading.RLock()
        self._initialized = False

    # -----------------------------------------------------------------
    # Initialize filesystem
    # -----------------------------------------------------------------

    def initialize(self):
        with self._lock:

            self.root.mkdir(
                parents=True,
                exist_ok=True,
            )

            for directory in self.DIRECTORIES:

                path = self.root / directory

                path.mkdir(
                    parents=True,
                    exist_ok=True,
                )

            self._initialized = True

        telemetry(
            "SEED filesystem initialized",
            str(self.root),
        )

        return self.status()

    # -----------------------------------------------------------------
    # Resolve logical path
    # -----------------------------------------------------------------

    def resolve(self, path=""):

        relative = Path(path)

        if relative.is_absolute():
            raise ValueError(
                "SEED logical paths must be relative"
            )

        target = (
            self.root / relative
        ).resolve()

        try:
            target.relative_to(
                self.root
            )
        except ValueError:
            raise PermissionError(
                "Filesystem traversal outside SEED root blocked"
            )

        return target

    # -----------------------------------------------------------------
    # Create directory
    # -----------------------------------------------------------------

    def mkdir(self, path):
        target = self.resolve(path)

        target.mkdir(
            parents=True,
            exist_ok=True,
        )

        return str(target)

    # -----------------------------------------------------------------
    # Write JSON state
    # -----------------------------------------------------------------

    def write_json(
        self,
        path,
        data,
    ):

        target = self.resolve(path)

        target.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary = target.with_suffix(
            target.suffix + ".tmp"
        )

        with temporary.open(
            "w",
            encoding="utf-8",
        ) as handle:

            json.dump(
                data,
                handle,
                indent=2,
                ensure_ascii=False,
            )

        temporary.replace(target)

        return str(target)

    # -----------------------------------------------------------------
    # Read JSON state
    # -----------------------------------------------------------------

    def read_json(
        self,
        path,
        default=None,
    ):

        target = self.resolve(path)

        if not target.exists():
            return (
                copy.deepcopy(default)
                if default is not None
                else None
            )

        try:

            with target.open(
                "r",
                encoding="utf-8",
            ) as handle:

                return json.load(handle)

        except Exception as exc:

            telemetry(
                "Filesystem JSON read failed",
                f"{path} | {exc}",
            )

            return (
                copy.deepcopy(default)
                if default is not None
                else None
            )

    # -----------------------------------------------------------------
    # List directory
    # -----------------------------------------------------------------

    def list(self, path=""):
        target = self.resolve(path)

        if not target.exists():
            return []

        return [
            {
                "name": item.name,
                "path": str(
                    item.relative_to(
                        self.root
                    )
                ),
                "directory": item.is_dir(),
                "file": item.is_file(),
            }
            for item in target.iterdir()
        ]

    # -----------------------------------------------------------------
    # Status
    # -----------------------------------------------------------------

    def status(self):

        with self._lock:

            return {
                "name": self.name,
                "root": str(self.root),
                "initialized": self._initialized,
                "directories": list(
                    self.DIRECTORIES
                ),
            }


# =====================================================================
# PERSISTENT SEED STATE
# =====================================================================

class SEEDStateStore:

    name = "seed_state"

    def __init__(
        self,
        filesystem,
    ):

        self.filesystem = filesystem

        self.state_file = (
            "System/State/seed_os_state.json"
        )

        self._lock = threading.RLock()

        self.state = {
            "version": 1,
            "created": time.time(),
            "boot_count": 0,
            "system_state": "INITIALIZING",
            "desktop": {},
            "windows": {},
            "icons": {},
            "applications": {},
            "nodes": {},
            "users": {},
            "telemetry": {},
        }

    def load(self):

        data = self.filesystem.read_json(
            self.state_file,
            default=None,
        )

        if isinstance(data, dict):

            with self._lock:

                loaded = copy.deepcopy(data)

                self.state.update(
                    loaded
                )

        return self.snapshot()

    def save(self):

        with self._lock:

            data = copy.deepcopy(
                self.state
            )

        self.filesystem.write_json(
            self.state_file,
            data,
        )

        return True

    def update(
        self,
        key,
        value,
    ):

        with self._lock:

            self.state[key] = copy.deepcopy(
                value
            )

        return self.save()

    def snapshot(self):

        with self._lock:

            return copy.deepcopy(
                self.state
            )


# =====================================================================
# STABILITY GATE
# =====================================================================

class SystemStabilityGate:


    name = "system_stability_gate"

    REQUIRED_BINDINGS = (
        "event_bus",
        "track_system",
        "registry",
        "neural_bridge",
        "oracle",
        "qbit_queue_loop",
        "qbit_dialer",
    )

    def __init__(
        self,
        *,
        stability_threshold=0.80,
    ):

        self.stability_threshold = (
            float(stability_threshold)
        )

        self._lock = threading.RLock()

        self._signals = {}
        self._stable = False
        self._last_score = 0.0
        self._last_evaluation = None

    def bind_signal(
        self,
        name,
        value,
    ):

        with self._lock:
            self._signals[name] = value

        return self.evaluate()

    def evaluate(self):

        with self._lock:

            if not self._signals:

                self._stable = False
                self._last_score = 0.0

                return self.status()

            positive = 0
            total = len(
                self._signals
            )

            for value in self._signals.values():

                if isinstance(value, bool):

                    positive += int(value)

                elif isinstance(value, (int, float)):

                    positive += int(
                        float(value) >=
                        self.stability_threshold
                    )

                elif isinstance(value, dict):

                    state = str(
                        value.get(
                            "state",
                            value.get(
                                "health",
                                ""
                            ),
                        )
                    ).upper()

                    if state in (
                        "HEALTHY",
                        "STABLE",
                        "READY",
                        "RUNNING",
                        "ONLINE",
                    ):
                        positive += 1

            self._last_score = (
                positive / total
                if total
                else 0.0
            )

            self._stable = (
                self._last_score >=
                self.stability_threshold
            )

            self._last_evaluation = (
                time.time()
            )

            return self.status()

    def is_stable(self):
        with self._lock:
            return self._stable

    def status(self):

        with self._lock:

            return {
                "name": self.name,
                "stable": self._stable,
                "score": self._last_score,
                "threshold": (
                    self.stability_threshold
                ),
                "signals": copy.deepcopy(
                    self._signals
                ),
                "last_evaluation": (
                    self._last_evaluation
                ),
            }


# =====================================================================
# ICON
# =====================================================================

class SEEDIcon:

    def __init__(
        self,
        name,
        target,
        icon_type="application",
        metadata=None,
    ):

        self.id = (
            f"ICON.{uuid.uuid4().hex[:12]}"
        )

        self.name = name
        self.target = target
        self.icon_type = icon_type
        self.metadata = (
            copy.deepcopy(metadata)
            if metadata
            else {}
        )

    def to_dict(self):

        return {
            "id": self.id,
            "name": self.name,
            "target": self.target,
            "type": self.icon_type,
            "metadata": copy.deepcopy(
                self.metadata
            ),
        }


# =====================================================================
# WINDOW
# =====================================================================

class SEEDWindow:

    def __init__(
        self,
        title,
        application=None,
        *,
        x=100,
        y=100,
        width=900,
        height=600,
    ):

        self.id = (
            f"WINDOW.{uuid.uuid4().hex[:12]}"
        )

        self.title = title
        self.application = application

        self.x = x
        self.y = y
        self.width = width
        self.height = height

        self.visible = False
        self.minimized = False
        self.maximized = False
        self.focused = False

        self.created_at = time.time()

    def open(self):

        self.visible = True
        self.minimized = False
        self.focused = True

        return self.to_dict()

    def close(self):

        self.visible = False
        self.focused = False

        return self.to_dict()

    def minimize(self):

        self.minimized = True
        self.focused = False

        return self.to_dict()

    def restore(self):

        self.minimized = False
        self.visible = True
        self.focused = True

        return self.to_dict()

    def maximize(self):

        self.maximized = True
        self.visible = True
        self.focused = True

        return self.to_dict()

    def to_dict(self):

        return {
            "id": self.id,
            "title": self.title,
            "application": self.application,
            "geometry": {
                "x": self.x,
                "y": self.y,
                "width": self.width,
                "height": self.height,
            },
            "visible": self.visible,
            "minimized": self.minimized,
            "maximized": self.maximized,
            "focused": self.focused,
            "created_at": self.created_at,
        }


# =====================================================================
# DESKTOP
# =====================================================================

class SEEDDesktop:

    name = "seed_desktop"

    def __init__(
        self,
        state_store,
    ):

        self.state_store = state_store

        self._lock = threading.RLock()

        self.icons = {}
        self.windows = {}

        self.wallpaper = (
            "SEED://desktop/default"
        )

        self.ready = False

    # -----------------------------------------------------------------
    # Initialize desktop
    # -----------------------------------------------------------------

    def initialize(self):

        with self._lock:

            self._create_default_icons()

            self.ready = True

            self._persist()

        telemetry(
            "SEED desktop initialized"
        )

        return self.status()

    # -----------------------------------------------------------------
    # Default icons
    # -----------------------------------------------------------------

    def _create_default_icons(self):

        defaults = (
            (
                "File System",
                "seed://filesystem",
                "system",
            ),
            (
                "Applications",
                "seed://applications",
                "system",
            ),
            (
                "System",
                "seed://system",
                "system",
            ),
            (
                "Workspace",
                "seed://workspace",
                "folder",
            ),
            (
                "SEED AI",
                "seed://ai",
                "ai",
            ),
        )

        for name, target, icon_type in defaults:

            icon = SEEDIcon(
                name=name,
                target=target,
                icon_type=icon_type,
            )

            self.icons[
                icon.id
            ] = icon

    # -----------------------------------------------------------------
    # Add icon
    # -----------------------------------------------------------------

    def add_icon(
        self,
        name,
        target,
        icon_type="application",
        metadata=None,
    ):

        icon = SEEDIcon(
            name=name,
            target=target,
            icon_type=icon_type,
            metadata=metadata,
        )

        with self._lock:

            self.icons[
                icon.id
            ] = icon

            self._persist()

        return icon.to_dict()

    # -----------------------------------------------------------------
    # Open window
    # -----------------------------------------------------------------

    def open_window(
        self,
        title,
        application=None,
    ):

        window = SEEDWindow(
            title=title,
            application=application,
        )

        with self._lock:

            self.windows[
                window.id
            ] = window

            window.open()

            self._persist()

        return window.to_dict()

    # -----------------------------------------------------------------
    # Close window
    # -----------------------------------------------------------------

    def close_window(
        self,
        window_id,
    ):

        with self._lock:

            window = self.windows.get(
                window_id
            )

            if window is None:
                return False

            window.close()

            self._persist()

            return window.to_dict()

    # -----------------------------------------------------------------
    # Persist desktop
    # -----------------------------------------------------------------

    def _persist(self):

        self.state_store.state[
            "desktop"
        ] = {
            "wallpaper": self.wallpaper,
            "ready": self.ready,
        }

        self.state_store.state[
            "icons"
        ] = {
            key: icon.to_dict()
            for key, icon
            in self.icons.items()
        }

        self.state_store.state[
            "windows"
        ] = {
            key: window.to_dict()
            for key, window
            in self.windows.items()
        }

    # -----------------------------------------------------------------
    # Snapshot
    # -----------------------------------------------------------------

    def snapshot(self):

        with self._lock:

            return {
                "name": self.name,
                "ready": self.ready,
                "wallpaper": self.wallpaper,
                "icons": {
                    key: icon.to_dict()
                    for key, icon
                    in self.icons.items()
                },
                "windows": {
                    key: window.to_dict()
                    for key, window
                    in self.windows.items()
                },
            }

    def status(self):

        return self.snapshot()


# =====================================================================
# START MENU
# =====================================================================

class SEEDStartMenu:

    name = "seed_start_menu"

    def __init__(
        self,
        desktop,
    ):

        self.desktop = desktop

        self._lock = threading.RLock()

        self.entries = {}

        self.opened = False

    def register(
        self,
        name,
        target,
        category="Applications",
        icon_type="application",
    ):

        entry_id = (
            f"START.{uuid.uuid4().hex[:12]}"
        )

        entry = {
            "id": entry_id,
            "name": name,
            "target": target,
            "category": category,
            "icon_type": icon_type,
        }

        with self._lock:

            self.entries[
                entry_id
            ] = entry

        return copy.deepcopy(entry)

    def open(self):

        with self._lock:
            self.opened = True

        return self.status()

    def close(self):

        with self._lock:
            self.opened = False

        return self.status()

    def search(self, query):

        query = str(query).lower()

        with self._lock:

            return [
                copy.deepcopy(entry)
                for entry in self.entries.values()
                if (
                    query in
                    entry["name"].lower()
                    or
                    query in
                    entry["category"].lower()
                )
            ]

    def status(self):

        with self._lock:

            categories = {}

            for entry in self.entries.values():

                category = entry[
                    "category"
                ]

                categories.setdefault(
                    category,
                    [],
                ).append(
                    copy.deepcopy(entry)
                )

            return {
                "name": self.name,
                "opened": self.opened,
                "categories": categories,
            }


# =====================================================================
# USER INPUT
# =====================================================================

class SEEDUserInput:


    name = "seed_user_input"

    def __init__(
        self,
        os_core,
    ):

        self.os_core = os_core

        self._lock = threading.RLock()

        self.history = []

    def submit(
        self,
        content,
        *,
        user_id="local",
        metadata=None,
    ):

        request = {
            "type": "user_input",
            "input_id": (
                f"INPUT.{uuid.uuid4().hex[:12]}"
            ),
            "track_id": gen_track_id(),
            "timestamp": time.time(),
            "user_id": user_id,
            "content": str(content),
            "metadata": (
                copy.deepcopy(metadata)
                if metadata
                else {}
            ),
            "authority": {
                "user_is_input": True,
                "user_is_command_authority": False,
                "execution_owner": "QbitDialer",
            },
        }

        with self._lock:

            self.history.append(
                copy.deepcopy(request)
            )

            if len(self.history) > 256:
                self.history.pop(0)

        self.os_core.observe(
            request
        )

        return request


# =====================================================================
# SEED OS CORE
# =====================================================================

class SEEDOS:

    name = "SEED_LYNX_OS"
    version = "11.1.0"
    role = "cross-platform-ai-desktop-environment"
    shell_name = "Lynx"
    shell_style = "Windows XP inspired"
    supported_platforms = ("Windows", "Darwin", "Linux")

    def __init__(
        self,
        *,
        storage_root=None,
        queue_loop=None,
        event_bus=None,
        track_system=None,
        registry=None,
        registry_runtime=None,
        neural_bridge=None,
        oracle=None,
        qbit_queue_loop=None,
        qbit_dialer=None,
        nodes=None,
        seedcore=None,
        runtime_context=None,
    ):

        # -------------------------------------------------------------
        # Existing authoritative SEED systems
        # -------------------------------------------------------------
        self.queue_loop = queue_loop
        self.event_bus = event_bus
        self.track_system = track_system
        self.registry = registry
        self.registry_runtime = registry_runtime
        self.neural_bridge = neural_bridge
        self.oracle = oracle
        self.qbit_queue_loop = qbit_queue_loop
        self.qbit_dialer = qbit_dialer
        self.runtime_context = runtime_context
        self.nodes = nodes
        self.seedcore = seedcore

        # -------------------------------------------------------------
        # Local foundational OS components
        # -------------------------------------------------------------

        self.filesystem = SEEDFileSystem(
            storage_root
        )

        self.state = SEEDStateStore(
            self.filesystem
        )

        self.stability = (
            SystemStabilityGate()
        )

        self.desktop = SEEDDesktop(
            self.state
        )

        self.start_menu = SEEDStartMenu(
            self.desktop
        )

        self.user_input = SEEDUserInput(
            self
        )

        # -------------------------------------------------------------
        # Runtime state
        # -------------------------------------------------------------

        self._lock = threading.RLock()

        self.running = False
        self.booted = False
        self.desktop_ready = False
        self.control_ready = False

        self.node_id = (
            f"SEED_OS.{uuid.uuid4().hex[:12]}"
        )

        self.boot_time = None
        self.last_observation = None

        self.observation_count = 0

    # =================================================================
    # BIND EXISTING SYSTEM
    # =================================================================

    def bind(
        self,
        name,
        obj,
    ):

        if not name:
            raise ValueError(
                "binding name required"
            )

        with self._lock:

            setattr(
                self,
                name,
                obj,
            )

        self._refresh_control_state()

        return True

    # =================================================================
    # STABILITY
    # =================================================================

    def _refresh_control_state(self):

        signals = {
            "event_bus": (
                self.event_bus is not None
            ),
            "track_system": (
                self.track_system is not None
            ),
            "registry": (
                self.registry is not None
            ),
            "neural_bridge": (
                self.neural_bridge is not None
            ),
            "oracle": (
                self.oracle is not None
            ),
            "qbit_queue_loop": (
                self.qbit_queue_loop is not None
            ),
            "qbit_dialer": (
                self.qbit_dialer is not None
            ),
        }

        for name, value in signals.items():

            self.stability.bind_signal(
                name,
                value,
            )

        self.control_ready = (
            self.qbit_queue_loop is not None
            and
            self.qbit_dialer is not None
        )

        return self.stability.evaluate()

    # =================================================================
    # BOOT
    # =================================================================

    def boot(self):

        telemetry(
            "SEED OS boot sequence started"
        )

        # -------------------------------------------------------------
        # Filesystem first
        # -------------------------------------------------------------

        self.filesystem.initialize()

        # -------------------------------------------------------------
        # Persistent state
        # -------------------------------------------------------------

        self.state.load()

        with self.state._lock:

            self.state.state[
                "boot_count"
            ] += 1

            self.state.state[
                "system_state"
            ] = "INITIALIZING"

        self.state.save()

        # -------------------------------------------------------------
        # Verify injected SEED infrastructure
        # -------------------------------------------------------------

        self._refresh_control_state()

        # -------------------------------------------------------------
        # Desktop is NOT allowed to start until stable.
        # -------------------------------------------------------------

        if not self.stability.is_stable():

            telemetry(
                "SEED OS waiting for system stability",
                self.stability.status(),
            )

            with self.state._lock:

                self.state.state[
                    "system_state"
                ] = "WAITING_FOR_STABILITY"

            self.state.save()

            return self.status()

        # -------------------------------------------------------------
        # Stable -> construct logical desktop
        # -------------------------------------------------------------

        self.desktop.initialize()

        self._initialize_start_menu()

        self.desktop_ready = True
        self.running = True
        self.booted = True
        self.boot_time = time.time()

        with self.state._lock:

            self.state.state[
                "system_state"
            ] = "RUNNING"

        self.state.save()

        telemetry(
            "SEED OS boot complete",
            {
                "node_id": self.node_id,
                "desktop": self.desktop_ready,
                "control": self.control_ready,
            },
        )

        self._publish_status()

        return self.status()

    # =================================================================
    # START MENU DEFAULTS
    # =================================================================

    def _initialize_start_menu(self):

        defaults = (
            (
                "File System",
                "seed://filesystem",
                "System",
                "system",
            ),
            (
                "System Monitor",
                "seed://system/monitor",
                "System",
                "system",
            ),
            (
                "SEED AI",
                "seed://ai",
                "SEED AI",
                "ai",
            ),
            (
                "Applications",
                "seed://applications",
                "Applications",
                "application",
            ),
            (
                "Workspace",
                "seed://workspace",
                "Workspace",
                "folder",
            ),
        )

        for (
            name,
            target,
            category,
            icon_type,
        ) in defaults:

            self.start_menu.register(
                name=name,
                target=target,
                category=category,
                icon_type=icon_type,
            )

    # =================================================================
    # OBSERVE
    # =================================================================

    def observe(
        self,
        observation,
    ):

        if observation is None:
            return None

        if not isinstance(
            observation,
            dict,
        ):

            observation = {
                "type": "observation",
                "value": observation,
            }

        if "track_id" not in observation:

            observation = copy.deepcopy(
                observation
            )

            observation[
                "track_id"
            ] = gen_track_id()

        observation.setdefault(
            "timestamp",
            time.time(),
        )

        observation.setdefault(
            "source_node",
            self.node_id,
        )

        with self._lock:

            self.observation_count += 1

            self.last_observation = (
                copy.deepcopy(
                    observation
                )
            )

        # -------------------------------------------------------------
        # Passive system propagation.
        #
        # Existing components only.
        # -------------------------------------------------------------

        self._publish_track(
            observation
        )

        self._publish_registry(
            observation
        )

        self._publish_neural_bridge(
            observation
        )

        self._publish_event_bus(
            observation
        )

        self._publish_oracle(
            observation
        )

        return observation

    # =================================================================
    # EVENT BUS
    # =================================================================

    def _publish_event_bus(
        self,
        observation,
    ):

        bus = self.event_bus

        if bus is None:
            return False

        emit = getattr(
            bus,
            "emit",
            None,
        )

        if not callable(emit):
            return False

        try:

            emit(observation)

            return True

        except TypeError:

            return False

        except Exception:

            log.debug(
                "EventBus observation failed",
                exc_info=True,
            )

            return False

    # =================================================================
    # TRACK SYSTEM
    # =================================================================

    def _publish_track(
        self,
        observation,
    ):

        tracker = self.track_system

        if tracker is None:
            return False

        for method_name in (
            "record",
            "observe",
            "track",
            "ingest",
        ):

            method = getattr(
                tracker,
                method_name,
                None,
            )

            if not callable(method):
                continue

            try:

                method(
                    observation
                )

                return True

            except TypeError:

                continue

            except Exception:

                log.debug(
                    "TrackSystem observation failed",
                    exc_info=True,
                )

                return False

        return False

    # =================================================================
    # REGISTRY
    # =================================================================

    def _publish_registry(
        self,
        observation,
    ):

        registry = self.registry

        if registry is None:
            return False

        for method_name in (
            "record_observation",
            "observe",
            "record",
        ):

            method = getattr(
                registry,
                method_name,
                None,
            )

            if not callable(method):
                continue

            try:

                method(
                    observation
                )

                return True

            except TypeError:

                continue

            except Exception:

                log.debug(
                    "Registry observation failed",
                    exc_info=True,
                )

                return False

        return False

    # =================================================================
    # NEURAL BRIDGE
    # =================================================================

    def _publish_neural_bridge(
        self,
        observation,
    ):

        bridge = self.neural_bridge

        if bridge is None:
            return False

        for method_name in (
            "observe",
            "ingest",
            "process_observation",
            "receive",
        ):

            method = getattr(
                bridge,
                method_name,
                None,
            )

            if not callable(method):
                continue

            try:

                # IMPORTANT:
                # If this returns an awaitable, the authoritative
                # runtime must await it. This OS layer does not call
                # asyncio.run() and does not create another runtime.
                method(observation)

                return True

            except TypeError:

                continue

            except Exception:

                log.debug(
                    "NeuralBridge observation failed",
                    exc_info=True,
                )

                return False

        return False

    # =================================================================
    # ORACLE
    # =================================================================

    def _publish_oracle(
        self,
        observation,
    ):

        oracle = self.oracle

        if oracle is None:
            return False

        for method_name in (
            "observe",
            "record_observation",
            "record",
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

                method(
                    observation
                )

                return True

            except TypeError:

                continue

            except Exception:

                log.debug(
                    "Oracle observation failed",
                    exc_info=True,
                )

                return False

        return False

    # =================================================================
    # USER INPUT
    # =================================================================

    def input(
        self,
        content,
        *,
        user_id="local",
        metadata=None,
    ):

        return self.user_input.submit(
            content,
            user_id=user_id,
            metadata=metadata,
        )

    # =================================================================
    # CONTROL REQUEST
    # =================================================================

    def build_control_request(
        self,
        *,
        action,
        target=None,
        parameters=None,
        reason=None,
    ):


        return {
            "type": "seed_control_request",

            "request_id": (
                f"CTRL.{uuid.uuid4().hex[:12]}"
            ),

            "track_id": gen_track_id(),

            "timestamp": time.time(),

            "source_node": self.node_id,

            "action": action,

            "target": target,

            "parameters": (
                copy.deepcopy(parameters)
                if parameters
                else {}
            ),

            "reason": reason,

            "authority": {
                "required": True,
                "owner": "QbitDialer",
                "submit_command_required": True,
                "command_submitted": False,
                "executed": False,
            },
        }

    # =================================================================
    # STATUS
    # =================================================================

    def status(self):

        with self._lock:

            return {
                "name": self.name,
                "version": self.version,
                "node_id": self.node_id,
                "role": self.role,

                "running": self.running,
                "booted": self.booted,

                "desktop_ready": (
                    self.desktop_ready
                ),

                "control_ready": (
                    self.control_ready
                ),

                "stability": (
                    self.stability.status()
                ),

                "filesystem": (
                    self.filesystem.status()
                ),

                "desktop": (
                    self.desktop.status()
                ),

                "start_menu": (
                    self.start_menu.status()
                ),

                "bindings": {
                    "event_bus": (
                        self.event_bus is not None
                    ),
                    "track_system": (
                        self.track_system is not None
                    ),
                    "registry": (
                        self.registry is not None
                    ),
                    "registry_runtime": (
                        self.registry_runtime is not None
                    ),
                    "neural_bridge": (
                        self.neural_bridge is not None
                    ),
                    "oracle": (
                        self.oracle is not None
                    ),
                    "qbit_queue_loop": (
                        self.qbit_queue_loop is not None
                    ),
                    "qbit_dialer": (
                        self.qbit_dialer is not None
                    ),
                    "runtime_context": (
                        self.runtime_context is not None
                    ),
                },

                "telemetry": {
                    "observations": (
                        self.observation_count
                    ),
                    "boot_time": (
                        self.boot_time
                    ),
                },

                "authority": {
                    "user_is_input": True,
                    "system_authority": "SEED_AI",
                    "command_authority": "QbitDialer",
                    "transport_authority": (
                        "QbitQueueLoop"
                    ),
                    "registry_authority": "SRegistry",
                    "governance_authority": "Oracle",
                    "execution_allowed_here": False,
                },
            }

    # =================================================================
    # PUBLISH STATUS
    # =================================================================

    def _publish_status(self):

        observation = {
            "type": "seed_os_status",
            "track_id": gen_track_id(),
            "timestamp": time.time(),
            "source_node": self.node_id,
            "status": self.status(),
        }

        self._publish_track(
            observation
        )

        self._publish_registry(
            observation
        )

        self._publish_event_bus(
            observation
        )

        self._publish_oracle(
            observation
        )

        return observation

    # =================================================================
    # STOP
    # =================================================================

    def stop(self):

        with self._lock:

            self.running = False
            self.desktop_ready = False

            self.state.state[
                "system_state"
            ] = "STOPPED"

        self.state.save()

        telemetry(
            "SEED OS stopped"
        )

        return self.status()


# =====================================================================
# RUNTIME ATTACHMENT
# =====================================================================

def attach_runtime(
    seed_os,
    *,
    event_bus=None,
    track_system=None,
    registry=None,
    registry_runtime=None,
    neural_bridge=None,
    oracle=None,
    qbit_queue_loop=None,
    qbit_dialer=None,
    runtime_context=None,
):
 

    bindings = {
        "event_bus": event_bus,
        "track_system": track_system,
        "registry": registry,
        "registry_runtime": registry_runtime,
        "neural_bridge": neural_bridge,
        "oracle": oracle,
        "qbit_queue_loop": qbit_queue_loop,
        "qbit_dialer": qbit_dialer,
        "runtime_context": runtime_context,
    }

    for name, obj in bindings.items():

        if obj is not None:
            seed_os.bind(
                name,
                obj,
            )

    return seed_os.status()


# =====================================================================
# BOOTSTRAP
# =====================================================================
#
# This intentionally does NOT instantiate the authoritative SEED
# runtime components.
#
# In the real SEED boot path, the existing runtime constructs/binds:
#
#   SRegistry
#   EventBus
#   TrackSystem
#   registry_runtime
#   NeuralBridge
#   Oracle
#   QbitQueueLoop
#   QbitDialer
#
# and then attaches them to SEEDOS.
#
# =====================================================================

def create_seed_os(
    storage_root=None,
    **runtime_bindings,
):

    seed_os = SEEDOS(
        storage_root=storage_root,
        **runtime_bindings,
    )

    return seed_os


# =====================================================================
# MAIN
# =====================================================================

if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO,
        format=(
            "[%(levelname)s] %(message)s"
        ),
    )

    telemetry(
        "SEED AI OS foundation starting"
    )

    seed_os = create_seed_os()

    # -------------------------------------------------------------
    # Without the authoritative runtime bindings, SEED intentionally
    # remains in WAITING_FOR_STABILITY.
    #
    # This is safer than inventing replacement systems.
    # -------------------------------------------------------------

    status = seed_os.boot()

    telemetry(
        "SEED AI OS foundation status",
        status,
    )
