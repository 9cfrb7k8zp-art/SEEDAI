# ==========================================================
# FILE: DEVHUD.py
# PATH: SEED_ROOT/seed/systemutils/DEVHUD.py
# VERSION: 10.0.0
# BUILD: DEVHUD FOUNDATION / RUNTIME-SAFE / QBIT-AUTHORITY
# ==========================================================

# ==========================================================
# STANDARD LIBRARY
# ==========================================================
import os
import sys
import json
import traceback
import importlib
import multiprocessing as mp
import threading
from threading import Thread
import zipfile
import shutil
import time
import hashlib
import logging
import asyncio

from collections import defaultdict, deque
from enum import Enum
from pathlib import Path
from typing import Dict, Any, Callable, Optional


# ==========================================================
# TK / UI
# ==========================================================
import tkinter as tk
from tkinter import (
    ttk,
    scrolledtext,
    filedialog,
    messagebox,
    Entry,
)
from tkinter.scrolledtext import ScrolledText


# ==========================================================
# EXTERNAL
# ==========================================================
import requests

from seed.systemutils.devhud_3x3_layout import build_3x3


# ==========================================================
# LAZY SEED RUNTIME DEPENDENCIES
# ==========================================================
#
# DEVHUD is a late observer. Importing it must not import the
# entire SEED/ML/runtime graph or start discovery work.
#
# These names are populated only when the actual DEVHUD UI or
# a feature that needs the corresponding runtime service is
# activated.
# ==========================================================

HUDAdapter = None
HUDState = None
HUD = None

QbitQueueLoop = None
TimeTravelEngine = None
SEEDEventBus = None
TrackSystem = None
DeviceManager = None
Heartbeat = None
HeartbeatEmitter = None
HUDMasterOverlay = None
ChannelManager = None
ChannelNode = None
ModuleRegistry = None
Device = None
Qbit = None

Memory_Crystallizer = None
HealthMonitor = None
SearchEngine = None
FiveG = None
TkEventBridge = None
DEVHUDChannelController = None

IPCBridge = None
queue_action = None
OptionRegistry = None

SEEDUIMain3D = None
SEEDUIMainHUD = None
init_hud = None
SEEDUIUnified = None

SEEDCore = None
start_runtime_loop = None
Oracle = None

CHANNEL_MANAGER = None
CHANNEL_CONTROLLER = None


def _lazy_runtime_imports():
    """Load heavy SEED dependencies only after DEVHUD is visible."""
    global HUDAdapter, HUDState, HUD
    global QbitQueueLoop, TimeTravelEngine, SEEDEventBus
    global TrackSystem, DeviceManager, Heartbeat, HeartbeatEmitter
    global HUDMasterOverlay, ChannelManager, ChannelNode
    global ModuleRegistry, Device, Qbit
    global Memory_Crystallizer, HealthMonitor, SearchEngine, FiveG
    global TkEventBridge, DEVHUDChannelController
    global IPCBridge, queue_action, OptionRegistry
    global SEEDUIMain3D, SEEDUIMainHUD, init_hud, SEEDUIUnified
    global SEEDCore, start_runtime_loop, Oracle

    if HUDAdapter is not None:
        return True

    from seed.hud.adapter.hud_adapter import HUDAdapter as _HUDAdapter
    from seed.hud.state import HUDState as _HUDState
    from seed.hud.hud import HUD as _HUD

    from seed.core.emitters.qbit_queue_loop import QbitQueueLoop as _QbitQueueLoop
    from seed.core.time_travel_engine import TimeTravelEngine as _TimeTravelEngine
    from seed.core.event_bus import SEEDEventBus as _SEEDEventBus
    from seed.core.track_system import TrackSystem as _TrackSystem
    from seed.core.device_manager import DeviceManager as _DeviceManager
    from seed.core.heartbeat import Heartbeat as _Heartbeat
    from seed.core.emitters.heartbeatemitter import HeartbeatEmitter as _HeartbeatEmitter
    from seed.core.hud_master_overlay import HUDMasterOverlay as _HUDMasterOverlay
    from seed.core.channel_manager import ChannelManager as _ChannelManager, ChannelNode as _ChannelNode
    from seed.core.module_registry import ModuleRegistry as _ModuleRegistry
    from seed.core.device import Device as _Device
    from seed.core.qbit import Qbit as _Qbit

    from seed.systemutils.memory_crystallizer import Memory_Crystallizer as _Memory_Crystallizer
    from seed.systemutils.healthmonitor import HealthMonitor as _HealthMonitor
    from seed.systemutils.search_engine import SearchEngine as _SearchEngine
    from seed.systemutils.fiveg import FiveG as _FiveG
    from seed.systemutils.tk_event_bridge import TkEventBridge as _TkEventBridge
    from seed.systemutils.DEVHUD_channels import DEVHUDChannelController as _DEVHUDChannelController

    from seed.ipc.ipc_bridge import IPCBridge as _IPCBridge
    from seed.skills.action_registry import queue_action as _queue_action
    from seed.skills.inject_option import OptionRegistry as _OptionRegistry

    from seed.ui.ui_seed_main import SEEDUIMain3D as _SEEDUIMain3D
    from seed.ui.Seed_Ui_Main_HUD import SEEDUIMainHUD as _SEEDUIMainHUD, init_hud as _init_hud
    from seed.ui.ui_seed_unified import SEEDUIUnified as _SEEDUIUnified

    from seed_init_full import SEEDCore as _SEEDCore
    from SRegistry.registry_runtime import start_runtime_loop as _start_runtime_loop
    from Oracle.oracle_tools import Oracle as _Oracle

    HUDAdapter = _HUDAdapter
    HUDState = _HUDState
    HUD = _HUD
    QbitQueueLoop = _QbitQueueLoop
    TimeTravelEngine = _TimeTravelEngine
    SEEDEventBus = _SEEDEventBus
    TrackSystem = _TrackSystem
    DeviceManager = _DeviceManager
    Heartbeat = _Heartbeat
    HeartbeatEmitter = _HeartbeatEmitter
    HUDMasterOverlay = _HUDMasterOverlay
    ChannelManager = _ChannelManager
    ChannelNode = _ChannelNode
    ModuleRegistry = _ModuleRegistry
    Device = _Device
    Qbit = _Qbit
    Memory_Crystallizer = _Memory_Crystallizer
    HealthMonitor = _HealthMonitor
    SearchEngine = _SearchEngine
    FiveG = _FiveG
    TkEventBridge = _TkEventBridge
    DEVHUDChannelController = _DEVHUDChannelController
    IPCBridge = _IPCBridge
    queue_action = _queue_action
    OptionRegistry = _OptionRegistry
    SEEDUIMain3D = _SEEDUIMain3D
    SEEDUIMainHUD = _SEEDUIMainHUD
    init_hud = _init_hud
    SEEDUIUnified = _SEEDUIUnified
    SEEDCore = _SEEDCore
    start_runtime_loop = _start_runtime_loop
    Oracle = _Oracle

    return True


def _ensure_channel_defaults():
    """Create DEVHUD-local channel defaults only if runtime did not supply them."""
    global CHANNEL_MANAGER, CHANNEL_CONTROLLER

    if CHANNEL_MANAGER is None or CHANNEL_CONTROLLER is None:
        _lazy_runtime_imports()

        if CHANNEL_MANAGER is None:
            CHANNEL_MANAGER = ChannelManager(root=None)
            CHANNEL_MANAGER.register_channel(
                "ROOT",
                metadata={"authority": "SYSTEM"},
            )
            CHANNEL_MANAGER.register_channel(
                "ROOT/DEVHUD",
                metadata={"controller": "DEVHUD"},
            )
            CHANNEL_MANAGER.register_channel(
                "ROOT/USER",
                metadata={"authority": "USER"},
            )

        if CHANNEL_CONTROLLER is None:
            CHANNEL_CONTROLLER = DEVHUDChannelController(
                channel_manager=CHANNEL_MANAGER,
            )

    return CHANNEL_MANAGER, CHANNEL_CONTROLLER


# ==========================================================
# LOGGING
# ==========================================================
logger = logging.getLogger("DEVHUD")

if not logger.handlers:
    logging.basicConfig(level=logging.INFO)

logger.setLevel(logging.INFO)


# ==========================================================
# CONSTANTS / ENVIRONMENT
# ==========================================================
SEED_ROOT = os.getenv(
    "SEED_ROOT",
    "./SEED_ROOT",
)

HUD_STATE_FILE = os.path.join(
    SEED_ROOT,
    ".hud_state.json",
)

LOAD_UI_DEFAULT = True
load_ui = LOAD_UI_DEFAULT


# ==========================================================
# DEVHUD CONTROL SIGNALS
# ==========================================================
SEED_START = "SEED_START"
SEED_STOP = "SEED_STOP"
SEED_PAUSE = "SEED_PAUSE"
SEED_SNAPSHOT = "SEED_SNAPSHOT"
SEED_STATUS = "SEED_STATUS"
SEED_HEARTBEAT = "SEED_HEARTBEAT"
SEED_ERROR = "SEED_ERROR"
SEED_COMMAND = "SEED_COMMAND"

SEED_COMMAND_RESULT = "SEED_COMMAND_RESULT"
SEED_COMMAND_DENIED = "SEED_COMMAND_DENIED"


# ==========================================================
# DEVHUD CHANNEL ID
# ==========================================================
class ChannelID(Enum):
    DEVELOPER = "developer"
    USER = "user"


# ==========================================================
# DEVHUD RUNTIME AUTHORITY
#
# DEVHUD is NOT the owner of:
#   - Qbit
#   - QbitQueueLoop
#   - EventBus
#   - TrackSystem
#   - Heartbeat
#
# Those systems are supplied by the authoritative runtime.
# DEVHUD observes and requests through existing boundaries.
# ==========================================================
DEVHUD_AUTHORITY = "DEVHUD"
QBIT_AUTHORITY = "QbitDialer"
TRANSPORT_AUTHORITY = "QbitQueueLoop"
EVENT_AUTHORITY = "SEEDEventBus"
TRACK_AUTHORITY = "TrackSystem"
OBSERVER_AUTHORITY = "Oracle"


# ==========================================================
# IMPORT / STARTUP SAFETY
#
# IMPORTANT:
# Do NOT start SRegistry or another runtime loop merely by
# importing DEVHUD.py.
#
# The original file executed:
#
#     start_runtime_loop(interval=0.5)
#
# during module import.
#
# That is removed from the foundation section.
# Runtime startup belongs to the SEED boot sequence.
# ==========================================================
RUNTIME_START_ON_IMPORT = False
NETWORK_ACTIVITY_ON_IMPORT = False
COMMAND_EXECUTION_ON_IMPORT = False


# ==========================================================
# CHANNEL SYSTEM
# ==========================================================
#
# No ChannelManager/Controller is constructed during import.
# main3 supplies the authoritative runtime instances.
# Local defaults are created only if a standalone DEVHUD feature
# explicitly requests them through _ensure_channel_defaults().
# ==========================================================


# ==========================================================
# DEVHUD CLASS
# ==========================================================
class DEVHUD(ttk.Frame):

    def __init__(
        self,
        parent,
        emit,
        *,
        device,
        qbit_dialer,
        channelmanager,
        channel_id=None,
        track_system=None,
        engines=None,
        qbit=None,
        search_engine=None,
        hud=None,
        ipc_bridge=None,
        state=None,
        core=None,
        oracle_loop=None,
        channel_controller=None,
        loop=None,
        qbit_queue=None,
        hud_state=None,
        time_travel_engine=None,
        memory_crystallizer=None,
        load_ui=True,
        headless=False,
        event_bus=None,
        storage_root="./SEED_ROOT",
        **kwargs,
    ):
        # --------------------------------------------------
        # TK ROOT REQUIREMENT
        # --------------------------------------------------
        if parent is None:
            raise RuntimeError(
                "DEVHUD requires a Tk root parent"
            )

        super().__init__(parent)

        # --------------------------------------------------
        # CORE REFERENCES
        #
        # These remain references supplied by the runtime.
        # DEVHUD does not manufacture competing core systems.
        # --------------------------------------------------
        self.parent = parent

        self.emit = emit
        self.event_bus = event_bus

        self.device = device
        self.qbit_dialer = qbit_dialer
        self.qbit = qbit

        self.channelmanager = channelmanager
        self.channel_id = channel_id
        self.track_system = track_system
        self.engines = dict(engines or {})
        self.channel_controller = (
            channel_controller
            or CHANNEL_CONTROLLER
        )

        if self.channel_controller is not None:
            try:
                self.channel_controller.bind_runtime(
                    channel_manager=self.channelmanager,
                    channel_id=self.channel_id,
                    track_system=self.track_system,
                    engines=self.engines,
                )
            except Exception:
                logger.exception(
                    "[DEVHUD] Channel controller runtime bind failed"
                )

        self.qbit_queue = qbit_queue
        self.loop = loop

        self.ipc_bridge = ipc_bridge

        self.hud_state = hud_state
        self.state = state

        self.oracle_loop = oracle_loop
        self.core = core

        self.memory_crystallizer = (
            memory_crystallizer
        )

        self.search_engine = search_engine
        self.seedos = kwargs.get("seedos", getattr(self, "seedos", None))

        self.storage_root = Path(
            storage_root
        )

        self.load_ui = bool(load_ui)
        self.headless = bool(headless)

        self.running = True

        # --------------------------------------------------
        # HUD OBJECT
        # --------------------------------------------------
        if hud is None:
            self.hud = {
                "buttons": [],
                "labels": [],
                "panels": [],
                "menus": [],
                "widgets": [],
            }
        else:
            self.hud = defaultdict(list)

        # --------------------------------------------------
        # RUNTIME AUTHORITY REFERENCES
        # --------------------------------------------------
        self.runtime_authority = {
            "devhud": DEVHUD_AUTHORITY,
            "qbit": QBIT_AUTHORITY,
            "transport": TRANSPORT_AUTHORITY,
            "event_bus": EVENT_AUTHORITY,
            "tracking": TRACK_AUTHORITY,
            "observer": OBSERVER_AUTHORITY,
        }

        # --------------------------------------------------
        # COMMAND POLICY
        # --------------------------------------------------
        self.command_policy = {
            "status": True,
            "whoami": True,
            "state": True,
            "threads": True,
            "reload": True,
            "patch": True,

            # Protected operations remain disabled here.
            "shutdown": False,
            "rm": False,
            "format": False,
        }

        # --------------------------------------------------
        # ROOT GRID CONFIGURATION
        # --------------------------------------------------
        self.grid(
            row=0,
            column=0,
            sticky="nsew",
        )

        parent.grid_rowconfigure(
            0,
            weight=1,
        )

        parent.grid_columnconfigure(
            0,
            weight=1,
        )

        self.grid_rowconfigure(
            0,
            weight=1,
        )

        self.grid_columnconfigure(
            1,
            weight=1,
        )

        # --------------------------------------------------
        # SECTION 1 COMPLETE
        #
        # Section 2 continues with the existing DEVHUD
        # layout/UI construction methods.
        # --------------------------------------------------


        # ==========================================================
        # SECTION 2
        # AUTHORITATIVE RUNTIME BINDING
        # ==========================================================
        #
        # DEVHUD is an observer / interface.
        #
        # It does NOT:
        #   - create a competing Qbit
        #   - create a competing QbitDialer
        #   - create a competing QbitQueueLoop
        #   - create a competing EventBus
        #   - create a competing TrackSystem
        #   - start the heartbeat pipeline
        #
        # Those systems belong to the authoritative SEED runtime.
        # DEVHUD binds to the objects supplied by that runtime.
        # ==========================================================

        self.qbit_dialer = qbit_dialer
        self.qbit = qbit

        if self.qbit_dialer is None:
            raise RuntimeError(
                "DEVHUD requires the authoritative QbitDialer"
            )

        # ----------------------------------------------------------
        # AUTHORITATIVE QBIT RESOLUTION
        # ----------------------------------------------------------
        #
        # Prefer the Qbit explicitly supplied by the boot/runtime
        # layer. If it was not supplied, resolve an already-existing
        # Qbit from QbitDialer.
        #
        # NEVER construct a Qbit here.
        # ----------------------------------------------------------

        if self.qbit is None:

            for attr in (
                "qbit",
                "current_qbit",
                "active_qbit",
            ):
                try:
                    candidate = getattr(
                        self.qbit_dialer,
                        attr,
                        None,
                    )
                except Exception:
                    candidate = None

                if candidate is not None:
                    self.qbit = candidate

                    logger.info(
                        "[DEVHUD] Bound existing Qbit from "
                        "QbitDialer | attr=%s | qbit=%r",
                        attr,
                        candidate,
                    )

                    break

        if self.qbit is not None:

            logger.info(
                "[DEVHUD] Qbit bound | id=%s | type=%s",
                getattr(
                    self.qbit,
                    "qbit_id",
                    getattr(
                        self.qbit,
                        "id",
                        None,
                    ),
                ),
                type(self.qbit).__name__,
            )

        else:

            logger.warning(
                "[DEVHUD] No authoritative Qbit supplied; "
                "DEVHUD will remain Qbit-reference-safe"
            )

        # ----------------------------------------------------------
        # EVENT BUS
        # ----------------------------------------------------------
        #
        # EventBus is supplied by the runtime.
        # DEVHUD does not instantiate one.
        # ----------------------------------------------------------

        if self.event_bus is None:
            raise RuntimeError(
                "DEVHUD requires the authoritative SEEDEventBus"
            )

        logger.info(
            "[DEVHUD] SEEDEventBus bound | type=%s",
            type(self.event_bus).__name__,
        )

        # ----------------------------------------------------------
        # DEVICE
        # ----------------------------------------------------------
        #
        # Device ownership remains outside DEVHUD.
        # Bind only the supplied runtime object.
        # ----------------------------------------------------------

        self.device = device

        # Do NOT create:
        #
        #     DeviceManager()
        #
        # here.
        #
        # If the boot/runtime supplied a DeviceManager through
        # kwargs, preserve that reference.
        # ----------------------------------------------------------

        self.device_manager = kwargs.get(
            "device_manager",
            getattr(
                self,
                "device_manager",
                None,
            ),
        )

        # ----------------------------------------------------------
        # TRACK SYSTEM
        # ----------------------------------------------------------
        #
        # TrackSystem is authoritative outside DEVHUD.
        # DEVHUD observes/binds; it does not create another instance.
        # ----------------------------------------------------------

        self.track_system = kwargs.get(
            "track_system",
            getattr(
                self,
                "track_system",
                None,
            ),
        )

        # ----------------------------------------------------------
        # IPC BRIDGE
        # ----------------------------------------------------------

        self.ipc_bridge = ipc_bridge

        if self.ipc_bridge is None:
            logger.info(
                "[DEVHUD] IPCBridge not yet available | "
                "late binding deferred to main3"
            )

        # ----------------------------------------------------------
        # CHANNEL SYSTEM
        # ----------------------------------------------------------
        #
        # Use the existing authoritative channel manager/controller.
        # Do not create another ChannelManager for DEVHUD.
        # ----------------------------------------------------------

        self.cm = self.channelmanager

        self.channel_controller = self.channel_controller

        # Channel authority may arrive later at Phase 16.
        # Keep an empty observer-side tree until main3 binds the
        # existing authoritative ChannelManager/Controller.
        if self.channel_controller is not None:
            try:
                self.tree = self.channel_controller.get_channel_tree()
            except Exception:
                self.tree = {}
        else:
            self.tree = {}

        # ----------------------------------------------------------
        # RUNTIME AUTHORITY MAP
        # ----------------------------------------------------------

        self.runtime_authority = {
            "devhud": DEVHUD_AUTHORITY,
            "qbit": QBIT_AUTHORITY,
            "transport": TRANSPORT_AUTHORITY,
            "event_bus": EVENT_AUTHORITY,
            "tracking": TRACK_AUTHORITY,
            "observer": OBSERVER_AUTHORITY,
        }

        # ----------------------------------------------------------
        # HEARTBEAT BINDING
        # ----------------------------------------------------------
        #
        # DEVHUD does NOT construct or start Heartbeat.
        #
        # Heartbeat is part of the SEED runtime pipeline:
        #
        #     Heartbeat
        #         ↓
        #     HeartbeatEmitter
        #         ↓
        #     Qbit
        #         ↓
        #     QbitQueueLoop / QbitDialer
        #
        # DEVHUD may receive a runtime-supplied reference.
        # ----------------------------------------------------------

        self.heartbeat = kwargs.get(
            "heartbeat",
            getattr(
                self,
                "heartbeat",
                None,
            ),
        )

        self.heartbeatemitter = kwargs.get(
            "heartbeatemitter",
            getattr(
                self,
                "heartbeatemitter",
                None,
            ),
        )

        # ----------------------------------------------------------
        # QBIT QUEUE LOOP
        # ----------------------------------------------------------
        #
        # Bind the authoritative QueueLoop when supplied.
        # DEVHUD never creates another transport loop.
        # ----------------------------------------------------------

        self.qbit_queue = (
            qbit_queue
            if qbit_queue is not None
            else kwargs.get(
                "qbit_queue_loop",
                self.qbit_queue,
            )
        )

        # ----------------------------------------------------------
        # TIME TRAVEL
        # ----------------------------------------------------------
        #
        # Use a runtime-supplied TimeTravelEngine when available.
        # DEVHUD does not force replay during initialization.
        # ----------------------------------------------------------

        self.time_travel_engine = (
            time_travel_engine
            if time_travel_engine is not None
            else kwargs.get(
                "time_travel_engine",
                None,
            )
        )

        if self.time_travel_engine is not None:

            try:
                self.time_travel_engine.event_bus = (
                    self.event_bus
                )
            except Exception as exc:
                logger.warning(
                    "[DEVHUD] Unable to synchronize "
                    "TimeTravelEngine EventBus | %s: %s",
                    type(exc).__name__,
                    exc,
                )

        # ----------------------------------------------------------
        # ORACLE OBSERVER
        # ----------------------------------------------------------
        #
        # Oracle remains an observer/governance reference.
        # DEVHUD does not instantiate Oracle here.
        # ----------------------------------------------------------

        self.oracle_loop = oracle_loop

        self.oracle = kwargs.get(
            "oracle",
            getattr(
                self,
                "oracle",
                None,
            ),
        )

        # ----------------------------------------------------------
        # DYNAMIC MODULE STATE
        # ----------------------------------------------------------

        self.dynamic_module = {
            "3DView": None,
            "WebApp": None,
            "ControlPanel": None,
        }

        self.active_dynamic_module = None

        # ----------------------------------------------------------
        # UNIFIED INPUT / OUTPUT BUFFERS
        # ----------------------------------------------------------

        self._seed_input_buffer = []

        self._seed_output_buffer = []

        # ----------------------------------------------------------
        # STATUS
        # ----------------------------------------------------------

        self.status_var = tk.StringVar()

        self.status_var.set(
            "DEVHUD runtime binding complete"
        )

        self.console_mode = "seed"

        self.current_module = None
        self.current_center_module = None

        # ----------------------------------------------------------
        # UI REFERENCES
        #
        # Existing layout/UI construction remains responsible for
        # creating the actual widgets.
        # ----------------------------------------------------------

        self.seed_console_frame = None

        self.loaded_object = None

        self.seed_nodes = {}

        self.active_node = None

        self.introspection_state = {}

        # ----------------------------------------------------------
        # THREAD-SAFE MESSAGE STATE
        # ----------------------------------------------------------

        self._message_queue = []

        self._lock = threading.Lock()

        # ----------------------------------------------------------
        # AUDIO CALLBACK
        # ----------------------------------------------------------

        self.audio_callback = None

        # ----------------------------------------------------------
        # TRAINING STATE
        # ----------------------------------------------------------

        self.seed_training_enabled = True

        logger.info(
            "[DEVHUD] Authoritative runtime bindings established"
        )


        # ============================================================
        # SECTION 3 — EVENTBUS / CHANNEL / HUD BRIDGE
        # ============================================================
        #
        # FILE: DEVHUD.py
        # PATH: SEED_ROOT/seed/systemutils/DEVHUD.py
        # COMPONENT: DEVHUD runtime event integration
        # PHASE: Runtime / HUD Integration
        #
        # AUTHORITY:
        #     QbitDialer       = command authority
        #     QbitQueueLoop    = execution/transport authority
        #     SEEDEventBus     = event transport
        #     TrackSystem      = track/context authority
        #     DEVHUD           = observer + human interface
        #
        # CONTRACT:
        #     DEVHUD subscribes to the existing EventBus.
        #     DEVHUD does not create another EventBus.
        #     DEVHUD does not execute commands directly from events.
        #     DEVHUD renders/forwards runtime state through existing handlers.
        # ============================================================

        # ------------------------------------------------------------
        # EVENT BUS — SINGLE EXISTING INSTANCE
        # ------------------------------------------------------------
        if self.event_bus is None:
            raise RuntimeError(
                "[DEVHUD] SEEDEventBus is required; "
                "DEVHUD cannot create a competing EventBus."
            )

        # Keep the public event_bus reference synchronized.
        self.event_bus = self.event_bus

        # ------------------------------------------------------------
        # CHANNEL MANAGER — EXISTING AUTHORITY
        # ------------------------------------------------------------
        if self.channelmanager is not None:
            self.cm = self.channelmanager
        else:
            self.cm = None

        # ChannelManager/Controller are allowed to bind later.
        # DEVHUD never manufactures a competing authority.
        if self.channel_controller is None:
            self.channel_controller = None

        if self.channel_controller is not None:
            try:
                self.tree = self.channel_controller.get_channel_tree()
            except Exception:
                self.tree = {}
        else:
            self.tree = {}

        # ------------------------------------------------------------
        # INTROSPECTION / MESSAGE STATE
        # ------------------------------------------------------------
        self.loaded_object = None

        self.seed_nodes = {}
        self.active_node = None
        self.introspection_state = {}

        self.audio_callback = None

        self._message_queue = []
        self._lock = threading.Lock()

        # ------------------------------------------------------------
        # EVENT SUBSCRIPTIONS — DEFERRED
        # ------------------------------------------------------------
        #
        # EventBus is authoritative and may be servicing runtime
        # traffic when DEVHUD is constructed. Subscription takes the
        # EventBus lock, so doing a large subscription batch inline
        # can stall the UI boot gate.
        #
        # Schedule the existing subscriptions on Tk's main-thread
        # event queue. No EventBus, Qbit, QueueLoop, or Dialer is
        # created here.
        # ------------------------------------------------------------

        self._event_subscriptions_pending = True

        try:
            self.after(
                0,
                self._connect_event_bus,
            )
        except Exception:
            # Boot remains non-blocking; mainloop can retry later.
            pass

        # ------------------------------------------------------------
        # TRAINING STATE
        # ------------------------------------------------------------
        self.seed_training_enabled = True

        # ------------------------------------------------------------
        # HUD RUNTIME STATE
        # ------------------------------------------------------------
        self.loaded_object = None
        self.current_module = None
        self.current_module_name = None

        self.dynamic_modules = {}
        self.module_registry = getattr(
            self,
            "module_registry",
            None,
        )

        self.status = "READY"

        # ------------------------------------------------------------
        # COMMAND / INPUT BUFFER
        # ------------------------------------------------------------
        self.command_buffer = []
        self.input_buffer = []

        # ------------------------------------------------------------
        # DEVHUD MESSAGE ROUTING
        # ------------------------------------------------------------
        self._last_seed_output = None
        self._last_command_result = None
        self._last_command_denied = None

        # ----------------------------------------------------------
        # NON-BLOCKING UI SHELL
        #
        # Give the developer an immediate visible surface without
        # importing the heavy SEED UI/ML dependency graph.
        # The full DEVHUD layout is scheduled by main3 after the
        # authoritative boot reaches the UI gate.
        # ----------------------------------------------------------

        self._boot_placeholder = None

        if self.load_ui and not self.headless:
            try:
                self._boot_placeholder = ttk.Label(
                    self,
                    text="SEED DEVHUD — loading runtime UI…",
                )
                self._boot_placeholder.grid(
                    row=0,
                    column=0,
                    sticky="nsew",
                    padx=12,
                    pady=12,
                )
            except Exception:
                self._boot_placeholder = None

        logger.info(
            "[DEVHUD] EventBus and channel integration initialized"
        )


     # ==========================================================
    # SECTION 4 — EVENT BUS / UI CONTROL / MESSAGE FLOW
    # ==========================================================

    def _connect_event_bus(self):

        if getattr(self, "event_bus", None) is None:
            return False

        subscriptions = (
            ("INTROSPECT", self._on_introspect),
            ("HUD_MESSAGE", self.push_message),
            ("SEED_OUTPUT", self._on_seed_output),
            ("QBIT_EXECUTE", self.on_qbit_execute),
            (SEED_STATUS, self._status_handler),
            (SEED_HEARTBEAT, self._status_handler),
            (SEED_ERROR, self._status_handler),
            (SEED_COMMAND, self.on_command),
            ("SEED_COMMAND_RESULT", self._render_command_result),
            ("SEED_COMMAND_DENIED", self._render_command_denied),
            ("SEED_COMMAND", self._handle_seed_command),
            ("STATUS", self._on_status),
            ("THOUGHT", self._on_thought),
            ("STATE", self._on_state_update),
            ("ERROR", self._on_error),
            ("SEED_INPUT", self._route_seed_input),
            (SEED_COMMAND_RESULT, self._handle_result),
            (SEED_ERROR, self._handle_error),
            (SEED_HEARTBEAT, self._handle_heartbeat),
        )

        completed = 0

        for event_name, handler in subscriptions:
            try:
                self.event_bus.subscribe(
                    event_name,
                    handler,
                )
                completed += 1
            except Exception:
                logger.exception(
                    "[DEVHUD] Event subscription failed | event=%s",
                    event_name,
                )

        self._event_subscriptions_pending = (
            completed != len(subscriptions)
        )

        logger.info(
            "[DEVHUD] EventBus subscriptions ready | "
            "completed=%s/%s | pending=%s",
            completed,
            len(subscriptions),
            self._event_subscriptions_pending,
        )

        return completed > 0


    def _wire_events(self):
        """Complete the UI event wiring without creating another runtime."""
        try:
            return self._connect_event_bus()
        except Exception as exc:
            logger.debug("[DEVHUD] event wiring deferred | %s", exc)
            return False

    def _log_output(self, message):
        self._last_seed_output = message
        try:
            self.push_message(message)
        except Exception:
            pass
        return message

    def _on_seed_output(self, data=None):
        return self._log_output(f"[SEED_OUTPUT] {data}")

    def _on_status(self, data=None):
        return self._log_output(f"[STATUS] {data}")

    def _status_handler(self, data=None):
        return self._on_status(data)

    def _on_thought(self, data=None):
        return self._log_output(f"[THOUGHT] {data}")

    def _on_state_update(self, data=None):
        return self._log_output(f"[STATE] {data}")

    def _on_error(self, data=None):
        return self._log_output(f"[ERROR] {data}")

    def _render_command_result(self, data=None):
        self._last_command_result = data
        return self._log_output(f"[COMMAND_RESULT] {data}")

    def _render_command_denied(self, data=None):
        self._last_command_denied = data
        return self._log_output(f"[COMMAND_DENIED] {data}")

    def _handle_seed_command(self, data=None):
        payload = data if isinstance(data, dict) else {"command": data}
        command = payload.get("command") or payload.get("name")
        if command:
            return self._emit_seed_input(command, "DEVHUD_EVENT")
        return self._route_seed_input(payload)

    def on_command(self, data=None):
        return self._handle_seed_command(data)

    def on_qbit_execute(self, data=None):
        """Observer-only Qbit execution event handler."""
        return self._log_output(f"[QBIT_EXECUTE] {data}")

    def _on_loop_action(self, event=None):
        return self._log_output("[LOOP] selected")

    def _on_tree_select(self, event=None):
        return event

    def _file_selected(self, event=None):
        try:
            selection = self.files_listbox.curselection()
            self._file_selected_path = self.files_listbox.get(selection[0]) if selection else None
        except Exception:
            self._file_selected_path = None
        return self._file_selected_path

    def refresh_files_list(self):
        try:
            box = getattr(self, "files_listbox", None)
            if box is None:
                return []
            box.delete(0, "end")
            root = Path.cwd()
            entries = []
            for item in sorted(root.iterdir(), key=lambda p: p.name.lower())[:100]:
                entries.append(item.name)
                box.insert("end", item.name)
            return entries
        except Exception:
            return []

    def _build_admin_tab(self, parent):
        parent.grid_columnconfigure(0, weight=1)
        ttk.Label(parent, text="SEED Administration — runtime observer").grid(row=0, column=0, sticky="w", padx=8, pady=8)

    def _build_share_tab(self, parent):
        parent.grid_columnconfigure(0, weight=1)
        ttk.Label(parent, text="SEED Share — controlled output / mirror").grid(row=0, column=0, sticky="w", padx=8, pady=8)

    def _build_options_tab(self, parent):
        parent.grid_columnconfigure(0, weight=1)
        ttk.Label(parent, text="SEED Options — authority remains with QbitDialer").grid(row=0, column=0, sticky="w", padx=8, pady=8)

    def _on_introspect(self, data=None):
        """Observer-only introspection callback for the DEVHUD."""
        payload = data if isinstance(data, dict) else {"data": data}
        snapshot = {
            "status": getattr(self, "status", "READY"),
            "qbit": getattr(getattr(self, "qbit", None), "qbit_id", None),
            "runtime_authority": "QbitDialer",
            "event_bus": type(getattr(self, "event_bus", None)).__name__ if getattr(self, "event_bus", None) is not None else None,
            "input_bridge": "SEED_INPUT -> Oracle -> ASK_SEED -> QbitDialer",
            "payload": payload,
        }
        try:
            self.push_message(f"[INTROSPECT] {snapshot}")
        except Exception:
            pass
        return snapshot


    def _handle_result(self, data):

        self._log_output(
            f"[RESULT] {data}"
        )


    def _handle_error(self, data):
        self._log_output(
            f"[ERROR] {data}"
        )


    def _handle_heartbeat(self, data):


        self._log_output(
            f"[HEARTBEAT] {data}"
        )


    def _hud_storage_file(self):


        return (
            Path(self.storage_root)
            / "hud_dynamic_storage.json"
        )


    # ==========================================================
    # WIDGET BUILD — UI ONLY
    # ==========================================================

    def _build_footer_controls(self):

        if not hasattr(self, "hud_left"):
            return

        self.hud_left.grid_columnconfigure(
            0,
            weight=1,
        )

        buttons = (
            ("Start", self.start_system),
            ("Stop", self.stop_system),
            ("Pause", self.pause_system),
            ("Status", self.request_status),
            ("Snapshot", self.snapshot_system),
        )

        for index, (label, command) in enumerate(buttons):
            ttk.Button(
                self.hud_left,
                text=label,
                command=command,
            ).grid(
                row=index,
                column=0,
                sticky="ew",
                padx=4,
                pady=2,
            )


    def _add_widget(
        self,
        parent,
        widget,
        **grid_kwargs,
    ):

        if parent is None or widget is None:
            return

        if not grid_kwargs:
            grid_kwargs = {
                "row": 0,
                "column": 0,
                "sticky": "nsew",
            }

        widget.grid(**grid_kwargs)


    def _init_channel_controller(self):

        if getattr(self, "cm", None) is None:
            return None

        try:
            from seed.systemutils.DEVHUD_channels import (
                DEVHUDChannelController,
            )

            controller = getattr(
                self,
                "channel_controller",
                None,
            )

            if controller is None:
                controller = DEVHUDChannelController(
                    channel_manager=self.cm,
                    channel_id=getattr(
                        self,
                        "channel_id",
                        None,
                    ),
                    track_system=getattr(
                        self,
                        "track_system",
                        None,
                    ),
                    storage_root=str(
                        self.storage_root
                    ),
                    engines=getattr(
                        self,
                        "engines",
                        {},
                    ),
                )

            controller.bind_runtime(
                channel_manager=self.cm,
                channel_id=getattr(
                    self,
                    "channel_id",
                    None,
                ),
                track_system=getattr(
                    self,
                    "track_system",
                    None,
                ),
                engines=getattr(
                    self,
                    "engines",
                    {},
                ),
            )

            self.channel_controller = controller
            return controller

        except Exception:
            logger.exception(
                "[DEVHUD] Channel controller initialization failed"
            )
            return None


    # ==========================================================
    # INPUT BRIDGE
    # ==========================================================

    def _emit_seed_input(self, command, source="DEVHUD"):
        command = str(command or "").strip()
        if not command:
            return False

        event_bus = getattr(self, "event_bus", None)
        if event_bus is None:
            self.push_message("[DEVHUD] EventBus unavailable")
            return False

        # Known command names remain command-plane input; free-form
        # text enters the Oracle/ASK_SEED cognitive branch.
        try:
            dialer = getattr(self, "qbit_dialer", None)
            registry = getattr(dialer, "command_registry", {}) if dialer is not None else {}
            if command.upper() in registry:
                event_bus.emit("SEED_COMMAND", {
                    "command": command.upper(),
                    "source": source,
                })
            else:
                event_bus.emit("SEED_INPUT", {
                    "user_input": command,
                    "text": command,
                    "source": source,
                })
            return True
        except Exception:
            logger.exception("[DEVHUD] Input routing failed")
            return False

    def _route_seed_input(self, payload=None):
        if not isinstance(payload, dict):
            payload = {"user_input": payload}
        value = (
            payload.get("user_input")
            or payload.get("command")
            or payload.get("text")
            or payload.get("message")
        )
        if not value:
            return {"status": "ignored", "reason": "empty_input"}
        return self._emit_seed_input(value, payload.get("source", "DEVHUD"))

    def _seed_cli_submit(self, event=None):
        entry = getattr(self, "seed_cli_entry", None)
        if entry is not None:
            try:
                value = entry.get().strip()
                entry.delete(0, "end")
            except Exception:
                value = ""
        else:
            value = getattr(self, "command_var", tk.StringVar()).get().strip()
            try:
                self.command_var.set("")
            except Exception:
                pass
        return self._emit_seed_input(value, "DEVHUD_CLI")

    def _submit_command(self, event=None):
        try:
            value = self.command_var.get().strip()
            self.command_var.set("")
        except Exception:
            value = ""
        return self._emit_seed_input(value, "DEVHUD_COMMAND")

    def _on_cli_submit(self, event=None):

        entry = getattr(
            self,
            "seed_cli_entry",
            None,
        )

        if entry is None:
            return

        try:
            command = entry.get().strip()
        except Exception:
            return

        if not command:
            return

        try:
            entry.delete(
                0,
                "end",
            )
        except Exception:
            pass

        event_bus = getattr(
            self,
            "event_bus",
            None,
        )

        if event_bus is None:
            self.push_message(
                "[DEVHUD] EventBus unavailable"
            )
            return

        try:
            event_bus.emit(
                "SEED_INPUT",
                {
                    "command": command,
                    "source": "DEVHUD",
                },
            )

        except Exception:
            logger.exception(
                "[DEVHUD] Failed to emit SEED_INPUT"
            )


    # ==========================================================
    # UI UPDATE LOOP
    # ==========================================================

    def _update_loop(self):
        if not getattr(
            self,
            "running",
            False,
        ):
            return

        try:
            while self._message_queue:

                with self._lock:
                    if not self._message_queue:
                        break

                    message = self._message_queue.pop(
                        0
                    )

                if (
                    getattr(
                        self,
                        "output_box",
                        None,
                    ) is not None
                ):
                    try:
                        self.output_box.configure(
                            state="normal"
                        )

                        self.output_box.insert(
                            "end",
                            f"{message}\n",
                        )

                        self.output_box.see(
                            "end"
                        )

                        self.output_box.configure(
                            state="disabled"
                        )

                    except Exception:
                        logger.exception(
                            "[DEVHUD] UI message render failed"
                        )

        except Exception:
            logger.exception(
                "[DEVHUD] UI update loop failed"
            )

        if (
            getattr(
                self,
                "parent",
                None,
            ) is not None
        ):
            try:
                self.after(
                    100,
                    self._update_loop,
                )
            except Exception:
                pass


    # ==========================================================
    # MESSAGE OUTPUT
    # ==========================================================

    def push_message(self, msg):
        message = str(msg)

        output_box = getattr(
            self,
            "output_box",
            None,
        )

        if (
            output_box is not None
            and self.load_ui
        ):
            try:
                if output_box.winfo_exists():

                    output_box.configure(
                        state="normal"
                    )

                    output_box.insert(
                        "end",
                        f"{message}\n",
                    )

                    output_box.see(
                        "end"
                    )

                    output_box.configure(
                        state="disabled"
                    )

                    return

            except Exception:
                logger.exception(
                    "[DEVHUD] Direct message render failed"
                )

        if not hasattr(
            self,
            "_message_queue",
        ):
            self._message_queue = []

        with self._lock:
            self._message_queue.append(
                message
            )


    def seed_output_handler(self, msg):

        if not isinstance(
            msg,
            dict,
        ):
            self.push_message(
                msg
            )
            return

        text = msg.get(
            "text",
            msg,
        )

        self.push_message(
            text
        )


    # ==========================================================
    # DEVICE SELECTION
    # ==========================================================

    def on_device_selected(self, event):


        try:
            device_id = getattr(
                event,
                "payload",
                event,
            )

            self.active_device_id = (
                device_id
            )

            self.push_message(
                f"[DEVICE] Selected: {device_id}"
            )

        except Exception:
            logger.exception(
                "[DEVHUD] Device selection handling failed"
            )


    # ==========================================================
    # SEARCH
    # ==========================================================

    def _run_search(self):


        engine = getattr(
            self,
            "search_engine",
            None,
        )

        if engine is None:
            self.push_message(
                "[SEARCH] SearchEngine unavailable"
            )
            return None

        try:
            return engine

        except Exception:
            logger.exception(
                "[DEVHUD] Search request failed"
            )
            return None

    # ==========================================================
    # SECTION 5 — MAIN UI BUILD
    # ==========================================================

    def _build_menu_bar(self):
        """Install the single DEVHUD root menu; views stay inside DEVHUD."""
        if getattr(self, "_menu_bar", None) is not None:
            return self._menu_bar

        root = self.winfo_toplevel()
        menu_bar = tk.Menu(root, tearoff=False)
        seed_menu = tk.Menu(menu_bar, tearoff=False)
        seed_menu.add_command(label="Open SEEDOS View", command=self._show_seedos_view)
        seed_menu.add_separator()
        for profile in ("Development Setup", "Learning Setup", "Creative Programmer", "Analyst", "Coder", "Customer Skill Profile"):
            seed_menu.add_command(label=profile, command=lambda p=profile: self._show_seedos_view(p))
        seed_menu.add_separator()
        seed_menu.add_command(
            label="Engine Settings",
            command=self._show_engine_settings,
        )
        menu_bar.add_cascade(label="SEEDOS", menu=seed_menu)
        root.configure(menu=menu_bar)
        self._menu_bar = menu_bar
        self._seedos_menu = seed_menu
        return menu_bar

    def _show_seedos_view(self, profile="Development Setup"):
        """Render SEEDOS configuration and learning controls in DEVHUD."""
        container = getattr(self, "dynamic_container", None)
        if container is None:
            self.push_message("[SEEDOS] DEVHUD view container unavailable")
            return None
        for child in container.winfo_children():
            child.destroy()
        frame = ttk.LabelFrame(container, text=f"SEEDOS — {profile}")
        frame.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)
        seedos = getattr(self, "seedos", None)
        status = getattr(seedos, "status", None) if seedos is not None else None
        ttk.Label(frame, text=f"Runtime: {status or 'BOUND / waiting for runtime'}").grid(row=0, column=0, columnspan=2, sticky="w", padx=8, pady=6)
        ttk.Label(frame, text="Capability focus").grid(row=1, column=0, sticky="w", padx=8, pady=4)
        focus = tk.StringVar(value=profile)
        ttk.Combobox(frame, textvariable=focus, values=("Development Setup", "Learning Setup", "Creative Programmer", "Analyst", "Coder", "Customer Skill Profile"), state="readonly").grid(row=1, column=1, sticky="ew", padx=8, pady=4)
        skills = (
            "Programming: requirements -> design -> code -> test -> debug",
            "Analysis: evidence -> data -> hypotheses -> validation -> report",
            "Creative: composition -> layout -> typography -> color -> assets",
            "UI/UX: interaction -> accessibility -> visual hierarchy -> iteration",
            "Design tools: learn approved tool workflows from examples and outcomes",
            "Customer goals: map requested work to skills, constraints, and deliverables",
        )
        skill_box = ScrolledText(frame, height=10, wrap="word")
        skill_box.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=8, pady=6)
        skill_box.insert("1.0", "\n".join(f"• {item}" for item in skills))
        skill_box.configure(state="disabled")
        ttk.Label(frame, text="Learning is configuration/data; execution remains routed through the SEED command authority.").grid(row=3, column=0, columnspan=2, sticky="w", padx=8, pady=6)
        frame.grid_rowconfigure(2, weight=1)
        frame.grid_columnconfigure(1, weight=1)
        self.current_center_module = frame
        return frame

    def _show_engine_settings(self):
        """Expose allowlisted engine controls without source edits."""
        container = getattr(
            self,
            "dynamic_container",
            None,
        )

        controller = getattr(
            self,
            "channel_controller",
            None,
        )

        if container is None or controller is None:
            self.push_message(
                "[ENGINES] Channel controller is not bound"
            )
            return None

        for child in container.winfo_children():
            child.destroy()

        frame = ttk.LabelFrame(
            container,
            text="SEED Engine Settings",
        )
        frame.grid(
            row=0,
            column=0,
            sticky="nsew",
            padx=8,
            pady=8,
        )

        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        settings = controller.get_engine_settings()
        variables = {}

        row = 0

        ttk.Label(
            frame,
            text=(
                "Runtime settings are persisted to config and applied "
                "only through the existing engine objects."
            ),
        ).grid(
            row=row,
            column=0,
            columnspan=4,
            sticky="w",
            padx=8,
            pady=6,
        )
        row += 1

        for engine_name, values in settings.items():
            ttk.Label(
                frame,
                text=engine_name,
            ).grid(
                row=row,
                column=0,
                sticky="w",
                padx=8,
                pady=3,
            )

            row += 1

            for setting, value in values.items():
                ttk.Label(
                    frame,
                    text=setting,
                ).grid(
                    row=row,
                    column=0,
                    sticky="w",
                    padx=18,
                    pady=2,
                )

                variable = tk.StringVar(
                    value=str(value),
                )

                ttk.Entry(
                    frame,
                    textvariable=variable,
                    width=22,
                ).grid(
                    row=row,
                    column=1,
                    sticky="ew",
                    padx=6,
                    pady=2,
                )

                variables[
                    (engine_name, setting)
                ] = variable

                row += 1

        def apply_settings():
            changed = 0
            errors = []

            for (
                engine_name,
                setting,
            ), variable in variables.items():
                try:
                    result = controller.set_engine_setting(
                        engine_name,
                        setting,
                        variable.get(),
                    )
                    if result.get("ok"):
                        changed += 1
                except Exception as exc:
                    errors.append(
                        f"{engine_name}.{setting}: {exc}"
                    )

            self.push_message(
                f"[ENGINES] Applied {changed} settings"
            )

            for error in errors:
                self.push_message(
                    f"[ENGINES] {error}"
                )

        button_row = ttk.Frame(frame)
        button_row.grid(
            row=row,
            column=0,
            columnspan=4,
            sticky="ew",
            padx=8,
            pady=8,
        )

        ttk.Button(
            button_row,
            text="Apply / Save",
            command=apply_settings,
        ).grid(
            row=0,
            column=0,
            padx=4,
        )

        ttk.Button(
            button_row,
            text="Refresh",
            command=self._show_engine_settings,
        ).grid(
            row=0,
            column=1,
            padx=4,
        )

        frame.grid_columnconfigure(
            1,
            weight=1,
        )

        self.current_center_module = frame
        return frame

    def _build_ui(self):
        """Build the single authoritative DEVHUD 3x3 layout."""
        build_3x3(self)
        return

        # ==========================================================
        # LEGACY UI PATH (retained below for rollback/reference only)
        # ==========================================================
        # LAZY RUNTIME/UI DEPENDENCIES
        # ==========================================================
        #
        # Heavy SEED/ML/UI dependencies are deliberately loaded
        # after the DEVHUD object exists and Tk mainloop can own
        # the UI. This keeps main3 boot non-blocking.
        # ==========================================================

        if SEEDUIMain3D is None:
            _lazy_runtime_imports()

        # The constructor's lightweight placeholder is only a boot
        # surface. Remove it before building the real HUD so the UI
        # cannot remain visually stuck on "loading" after the runtime
        # is already online.
        placeholder = getattr(self, "_boot_placeholder", None)
        if placeholder is not None:
            try:
                placeholder.destroy()
            except Exception:
                pass
            self._boot_placeholder = None

        self.status = "READY"
        try:
            self.status_var.set("SEED DEVHUD Ready — runtime attached")
        except Exception:
            pass

        # The full layout is built here rather than relying on the
        # legacy _build_layout() path. This creates the authoritative
        # center container before tabs are attached and prevents the
        # scheduled UI build from falling back to the old loading shell.
        if not hasattr(self, "hud_center"):
            self.hud_center = ttk.Frame(self)
            self.hud_center.grid(row=0, column=1, sticky="nsew")
            self.hud_center.grid_rowconfigure(0, weight=1)
            self.hud_center.grid_columnconfigure(0, weight=1)
            self.grid_rowconfigure(0, weight=1)
            self.grid_columnconfigure(1, weight=1)

        # ==========================================================
        # MENU + TABS
        # ==========================================================

        self._build_tabs(
            self.hud_center
        )

        self._build_menu_bar()

        # ==========================================================
        # MAIN 3-COLUMN CONTAINER
        # ==========================================================

        self.hud_container = ttk.Frame(
            self.hud_center
        )

        self.hud_container.grid(
            row=0,
            column=0,
            sticky="nsew"
        )

        self.hud_center.grid_rowconfigure(
            0,
            weight=1
        )

        self.hud_center.grid_columnconfigure(
            0,
            weight=1
        )

        self.hud_container.grid_rowconfigure(
            0,
            weight=1
        )

        self.hud_container.grid_columnconfigure(
            0,
            weight=0
        )

        self.hud_container.grid_columnconfigure(
            1,
            weight=1
        )

        self.hud_container.grid_columnconfigure(
            2,
            weight=0
        )

        # ==========================================================
        # LEFT PANEL
        # ==========================================================

        self.hud_left = ttk.Frame(
            self.hud_container,
            width=260
        )

        self.hud_left.grid(
            row=0,
            column=0,
            sticky="nsew"
        )

        self.hud_left.grid_propagate(
            False
        )

        self.hud_left.grid_rowconfigure(
            1,
            weight=1
        )

        self.hud_left.grid_columnconfigure(
            0,
            weight=1
        )

        # ----------------------------------------------------------
        # FILES NOTEBOOK
        # ----------------------------------------------------------

        self.left_hud = ttk.Notebook(
            self.hud_left
        )

        self.left_hud.grid(
            row=0,
            column=0,
            sticky="nsew"
        )

        left_tab = ttk.Frame(
            self.left_hud
        )

        self.left_hud.add(
            left_tab,
            text="Files"
        )

        # SearchEngine remains a UI component.
        # Reuse an injected engine if one already exists.
        if getattr(
            self,
            "search_engine",
            None
        ) is None:

            self.search_engine = SearchEngine(
                left_tab
            )

        else:
            try:
                self.search_engine.master = left_tab
            except Exception:
                pass

        if hasattr(
            self.search_engine,
            "grid"
        ):
            try:
                self.search_engine.grid(
                    row=0,
                    column=0,
                    sticky="nsew"
                )
            except Exception:
                pass

        left_tab.grid_rowconfigure(
            0,
            weight=1
        )

        left_tab.grid_columnconfigure(
            0,
            weight=1
        )

        # ----------------------------------------------------------
        # CAMERA / VISUAL FRAME
        # ----------------------------------------------------------

        self.camera_feed_frame = ttk.Frame(
            self.hud_left
        )

        self.camera_feed_frame.grid(
            row=1,
            column=0,
            sticky="nsew",
            padx=4,
            pady=2
        )

        # ----------------------------------------------------------
        # INPUT MODE SELECTION
        # ----------------------------------------------------------

        self.mode_row = ttk.Frame(
            self.hud_left
        )

        self.mode_row.grid(
            row=2,
            column=0,
            sticky="ew",
            padx=4,
            pady=2
        )

        self.seed_input_mode = tk.StringVar(
            value="CLI"
        )

        for index, mode in enumerate(
            (
                "CLI",
                "TEXT",
                "VOICE",
            )
        ):
            ttk.Radiobutton(
                self.mode_row,
                text=mode,
                value=mode,
                variable=self.seed_input_mode,
            ).grid(
                row=0,
                column=index,
                sticky="nsew"
            )

        for index in range(3):
            self.mode_row.grid_columnconfigure(
                index,
                weight=1
            )

        # ----------------------------------------------------------
        # SEND BUTTON
        # ----------------------------------------------------------

        self.input_row = ttk.Frame(
            self.hud_left
        )

        self.input_row.grid(
            row=3,
            column=0,
            sticky="ew",
            padx=4,
            pady=2
        )

        ttk.Button(
            self.input_row,
            text="SEND",
            command=self._seed_cli_submit,
        ).grid(
            row=0,
            column=0,
            sticky="ew"
        )

        self.input_row.grid_columnconfigure(
            0,
            weight=1
        )

        # ==========================================================
        # CENTER PANEL
        # ==========================================================

        self.hud_center_panel = ttk.Frame(
            self.hud_container
        )

        self.hud_center_panel.grid(
            row=0,
            column=1,
            sticky="nsew"
        )

        self.hud_center_panel.grid_rowconfigure(
            1,
            weight=1
        )

        self.hud_center_panel.grid_columnconfigure(
            0,
            weight=1
        )

        # ----------------------------------------------------------
        # MODULE NOTEBOOK
        # ----------------------------------------------------------

        self.hud_container_notebook = ttk.Notebook(
            self.hud_center_panel
        )

        self.hud_container_notebook.grid(
            row=0,
            column=0,
            sticky="ew"
        )

        self.modules_tab = ttk.Frame(
            self.hud_container_notebook
        )

        self.hud_container_notebook.add(
            self.modules_tab,
            text="Modules"
        )

        # ----------------------------------------------------------
        # DYNAMIC CONTAINER
        # ----------------------------------------------------------

        self.dynamic_container = ttk.Frame(
            self.hud_center_panel
        )

        self.dynamic_container.grid(
            row=1,
            column=0,
            sticky="nsew"
        )

        self.dynamic_container.grid_rowconfigure(
            0,
            weight=1
        )

        self.dynamic_container.grid_columnconfigure(
            0,
            weight=1
        )

        # ==========================================================
        # INSPECT NOTEBOOK
        # ==========================================================

        self.inspect_notebook = ttk.Notebook(
            self.dynamic_container
        )

        self.inspect_notebook.grid(
            row=0,
            column=0,
            sticky="nsew"
        )

        self.inspect_status = ttk.Frame(
            self.inspect_notebook
        )

        self.inspect_loops = ttk.Frame(
            self.inspect_notebook
        )

        self.inspect_network = ttk.Frame(
            self.inspect_notebook
        )

        self.inspect_memory = ttk.Frame(
            self.inspect_notebook
        )

        self.inspect_notebook.add(
            self.inspect_status,
            text="Status"
        )

        self.inspect_notebook.add(
            self.inspect_loops,
            text="Loops"
        )

        self.inspect_notebook.add(
            self.inspect_network,
            text="Network"
        )

        self.inspect_notebook.add(
            self.inspect_memory,
            text="Memory"
        )

        # ----------------------------------------------------------
        # LOOP TREE
        # ----------------------------------------------------------

        self.loop_tree = ttk.Treeview(
            self.inspect_loops,
            columns=(
                "state",
                "entropy",
                "tps",
                "latency",
                "memory",
            ),
            show="headings",
            height=6,
        )

        for column in self.loop_tree["columns"]:
            self.loop_tree.heading(
                column,
                text=column.upper()
            )

            self.loop_tree.column(
                column,
                width=90,
                anchor="center"
            )

        self.loop_tree.grid(
            row=0,
            column=0,
            sticky="nsew"
        )

        self.loop_tree.bind(
            "<Double-1>",
            self._on_loop_action
        )

        self.inspect_loops.grid_rowconfigure(
            0,
            weight=1
        )

        self.inspect_loops.grid_columnconfigure(
            0,
            weight=1
        )

        # ----------------------------------------------------------
        # NETWORK TREE
        # ----------------------------------------------------------

        self.network_list = ttk.Treeview(
            self.inspect_network,
            columns=(
                "type",
                "status",
                "latency",
            ),
            show="headings"
        )

        for column in (
            "type",
            "status",
            "latency",
        ):
            self.network_list.heading(
                column,
                text=column.upper()
            )

            self.network_list.column(
                column,
                width=100,
                anchor="center"
            )

        self.network_list.grid(
            row=0,
            column=0,
            sticky="nsew"
        )

        self.inspect_network.grid_rowconfigure(
            0,
            weight=1
        )

        self.inspect_network.grid_columnconfigure(
            0,
            weight=1
        )

        # ----------------------------------------------------------
        # MEMORY LABEL
        # ----------------------------------------------------------

        self.mem_label = ttk.Label(
            self.inspect_memory,
            text="Memory usage stabilizing…",
            font=("Consolas", 9),
        )

        self.mem_label.grid(
            row=0,
            column=0,
            sticky="nsew"
        )

        self.inspect_memory.grid_rowconfigure(
            0,
            weight=1
        )

        self.inspect_memory.grid_columnconfigure(
            0,
            weight=1
        )

        # ==========================================================
        # SEED UI MAIN — 3D
        # ==========================================================

        self.seed_ui_main = SEEDUIMain3D(
            hud=self.hud,
            state=self.state,
            event_bus=self.event_bus,
            emit=self.event_bus.emit,
            loop=self.loop,
            qbit_queue=self.qbit_queue,
            parent=self.dynamic_container,
        )

        if hasattr(
            self.seed_ui_main,
            "_build_ui"
        ):
            self.seed_ui_main._build_ui()

        self.seed_ui_main.grid(
            row=1,
            column=0,
            sticky="nsew"
        )

        # ==========================================================
        # SEED UI UNIFIED
        # ==========================================================

        self.ui_seed_unified = SEEDUIUnified(
            parent=self.dynamic_container,
            container=self.dynamic_container,
            hud=self,
            storage_root=self.storage_root,
            orchestrator=getattr(
                self,
                "orchestrator",
                None,
            ),
        )

        self.ui_seed_unified.grid(
            row=2,
            column=0,
            sticky="nsew"
        )

        # ==========================================================
        # RIGHT PANEL
        # ==========================================================

        self.hud_right = ttk.Frame(
            self.hud_container,
            width=320
        )

        self.hud_right.grid(
            row=0,
            column=2,
            sticky="nsew"
        )

        self.hud_right.grid_propagate(
            False
        )

        self.hud_right.grid_rowconfigure(
            1,
            weight=1
        )

        self.hud_right.grid_columnconfigure(
            0,
            weight=1
        )

        # ----------------------------------------------------------
        # RIGHT PANEL HEADER
        # ----------------------------------------------------------

        ttk.Label(
            self.hud_right,
            text="SEED AI — Input / Output Gate",
            font=("Consolas", 10, "bold"),
        ).grid(
            row=0,
            column=0,
            sticky="w",
            padx=5,
            pady=2
        )

        # ----------------------------------------------------------
        # CONSOLE
        # ----------------------------------------------------------

        self.console = tk.Text(
            self.hud_right,
            state="disabled",
            wrap="word",
            bg="#0b0f14",
            fg="#00ff88",
            insertbackground="#00ff88",
            font=("Consolas", 10),
        )

        self.console.grid(
            row=1,
            column=0,
            sticky="nsew",
            padx=5,
            pady=2
        )

        # ----------------------------------------------------------
        # COMMAND ENTRY
        # ----------------------------------------------------------

        self.command_var = tk.StringVar()

        self.command_entry = ttk.Entry(
            self.hud_right,
            textvariable=self.command_var,
        )

        self.command_entry.grid(
            row=2,
            column=0,
            sticky="ew",
            padx=5,
            pady=2
        )

        self.command_entry.bind(
            "<Return>",
            self._submit_command
        )

        # ----------------------------------------------------------
        # VOICE CONTROLS
        # ----------------------------------------------------------

        self.voice_frame = ttk.Frame(
            self.hud_right
        )

        self.voice_frame.grid(
            row=3,
            column=0,
            sticky="w",
            padx=5,
            pady=2
        )

        self.mic_button = ttk.Button(
            self.voice_frame,
            text="Mic ON",
            command=self.toggle_mic,
        )

        self.mic_button.grid(
            row=0,
            column=0,
            padx=2
        )

        self.voice_button = ttk.Button(
            self.voice_frame,
            text="Voice Command",
            command=self.voice_command,
        )

        self.voice_button.grid(
            row=0,
            column=1,
            padx=2
        )

        # ==========================================================
        # STATUS BAR
        # ==========================================================

        self.status_var = tk.StringVar(
            value="SEED DEVHUD Ready"
        )

        self.status_bar = tk.Label(
            self,
            textvariable=self.status_var,
            relief=tk.SUNKEN,
            anchor="w",
            bg="#111111",
            fg="#00ff00",
            font=("Consolas", 9),
        )

        self.status_bar.grid(
            row=1,
            column=0,
            columnspan=3,
            sticky="ew"
        )

        # ==========================================================
        # FINAL UI STATE
        # ==========================================================

        self.active_dynamic_module = None

        # Wire existing UI/event relationships.
        if hasattr(
            self,
            "_wire_events"
        ):
            self._wire_events()

        # IMPORTANT:
        # Do not create or start a second asyncio runtime loop here.
        # The runtime loop belongs to the existing SEED runtime.
        #
        # Existing runtime references remain bound through:
        #     self.loop
        #     self.qbit_queue
        #     self.qbit_dialer
        #     self.event_bus

        logger.info(
            "[DEVHUD] UI built cleanly — "
            "left | center | right STABLE"
        )


    # ==========================================================
    # SECTION 6 — TABS / LAYOUT / DYNAMIC UI
    # ==========================================================

    def _build_layout(self):
 
        # ======================================================
        # LEFT PANEL
        # ======================================================

        self.hud_left = ttk.Frame(
            self,
            width=220
        )

        self.hud_left.grid(
            row=0,
            column=0,
            sticky="nsew"
        )

        self.hud_left.grid_propagate(
            False
        )

        # ======================================================
        # CENTER PANEL
        # ======================================================

        self.hud_center = ttk.Frame(
            self
        )

        self.hud_center.grid(
            row=0,
            column=1,
            sticky="nsew"
        )

        self.hud_center.grid_rowconfigure(
            1,
            weight=1
        )

        self.hud_center.grid_columnconfigure(
            0,
            weight=1
        )

        # ======================================================
        # RIGHT PANEL
        # ======================================================

        self.hud_right = ttk.Frame(
            self,
            width=260
        )

        self.hud_right.grid(
            row=0,
            column=2,
            sticky="nsew"
        )

        self.hud_right.grid_propagate(
            False
        )

        # ======================================================
        # ROOT GRID
        # ======================================================

        self.grid_rowconfigure(
            0,
            weight=1
        )

        self.grid_columnconfigure(
            0,
            weight=0
        )

        self.grid_columnconfigure(
            1,
            weight=1
        )

        self.grid_columnconfigure(
            2,
            weight=0
        )


    # ==========================================================
    # MAIN DEVHUD TABS
    # ==========================================================

    def _build_tabs(self, parent):

        if parent is None:
            raise RuntimeError(
                "_build_tabs parent is None"
            )

        # Clear only the supplied UI parent.
        for child in parent.winfo_children():
            child.destroy()

        parent.grid_rowconfigure(
            0,
            weight=1
        )

        parent.grid_columnconfigure(
            0,
            weight=1
        )

        self.main_notebook = ttk.Notebook(
            parent
        )

        self.main_notebook.grid(
            row=0,
            column=0,
            sticky="nsew"
        )

        # ======================================================
        # TAB FRAMES
        # ======================================================

        self.hud_tab = ttk.Frame(
            self.main_notebook
        )

        self.files_tab = ttk.Frame(
            self.main_notebook
        )

        self.update_tab = ttk.Frame(
            self.main_notebook
        )

        self.channels_tab = ttk.Frame(
            self.main_notebook
        )

        self.admin_tab = ttk.Frame(
            self.main_notebook
        )

        self.share_tab = ttk.Frame(
            self.main_notebook
        )

        self.options_tab = ttk.Frame(
            self.main_notebook
        )

        # ======================================================
        # REGISTER TABS
        # ======================================================

        self.main_notebook.add(
            self.hud_tab,
            text="HUD"
        )

        self.main_notebook.add(
            self.files_tab,
            text="Files"
        )

        self.main_notebook.add(
            self.update_tab,
            text="Updates"
        )

        self.main_notebook.add(
            self.channels_tab,
            text="Channels"
        )

        self.main_notebook.add(
            self.admin_tab,
            text="Admin"
        )

        self.main_notebook.add(
            self.share_tab,
            text="Share"
        )

        self.main_notebook.add(
            self.options_tab,
            text="Options"
        )

        # ======================================================
        # BUILD TAB CONTENT
        # ======================================================

        self._build_hud_tab(
            self.hud_tab
        )

        self._build_files_tab(
            self.files_tab
        )

        self._build_update_tab(
            self.update_tab
        )

        self._build_channels_tab(
            self.channels_tab
        )

        self._build_admin_tab(
            self.admin_tab
        )

        self._build_share_tab(
            self.share_tab
        )

        self._build_options_tab(
            self.options_tab
        )


    # ==========================================================
    # HUD TAB
    # ==========================================================

    def _build_hud_tab(self, parent):

        if parent is None:
            raise RuntimeError(
                "_build_hud_tab parent is None"
            )

        parent.grid_rowconfigure(
            0,
            weight=1
        )

        parent.grid_columnconfigure(
            0,
            weight=1
        )

        root_frame = ttk.Frame(
            parent
        )

        root_frame.grid(
            row=0,
            column=0,
            sticky="nsew"
        )

        root_frame.grid_rowconfigure(
            0,
            weight=0
        )

        root_frame.grid_rowconfigure(
            1,
            weight=1
        )

        root_frame.grid_columnconfigure(
            0,
            weight=1
        )

        # ======================================================
        # HUD TOP NOTEBOOK
        # ======================================================

        self.center_notebook = ttk.Notebook(
            root_frame
        )

        self.center_notebook.grid(
            row=0,
            column=0,
            sticky="ew"
        )

        hud_main_tab = ttk.Frame(
            self.center_notebook
        )

        self.center_notebook.add(
            hud_main_tab,
            text="HUD"
        )

        hud_main_tab.grid_rowconfigure(
            0,
            weight=1
        )

        hud_main_tab.grid_columnconfigure(
            0,
            weight=1
        )

        # ======================================================
        # DYNAMIC MAIN CONTENT
        # ======================================================

        self.dynamic_container = ttk.Frame(
            root_frame
        )

        self.dynamic_container.grid(
            row=1,
            column=0,
            sticky="nsew"
        )

        self.dynamic_container.grid_rowconfigure(
            0,
            weight=1
        )

        self.dynamic_container.grid_columnconfigure(
            0,
            weight=1
        )


    # ==========================================================
    # FILES TAB
    # ==========================================================

    def _build_files_tab(self, parent=None):

        if parent is None:
            raise RuntimeError(
                "_build_files_tab parent is None"
            )

        parent.grid_rowconfigure(
            1,
            weight=1
        )

        parent.grid_columnconfigure(
            0,
            weight=1
        )

        ttk.Label(
            parent,
            text="Files Tab"
        ).grid(
            row=0,
            column=0,
            sticky="w",
            padx=5,
            pady=(5, 2)
        )

        self.files_listbox = tk.Listbox(
            parent
        )

        self.files_listbox.grid(
            row=1,
            column=0,
            sticky="nsew",
            padx=5
        )

        self.files_listbox.bind(
            "<<ListboxSelect>>",
            self._file_selected
        )

        self.refresh_files_button = ttk.Button(
            parent,
            text="Refresh Files",
            command=self.refresh_files_list
        )

        self.refresh_files_button.grid(
            row=2,
            column=0,
            sticky="ew",
            padx=5,
            pady=5
        )

        self.refresh_files_list()


    # ==========================================================
    # UPDATE TAB
    # ==========================================================

    def _build_update_tab(self, parent=None):

        if parent is None:
            parent = self.update_tab

        parent.grid_rowconfigure(
            0,
            weight=1
        )

        parent.grid_columnconfigure(
            0,
            weight=1
        )

        self.update_output = tk.Text(
            parent,
            wrap="word"
        )

        scroll = ttk.Scrollbar(
            parent,
            orient="vertical",
            command=self.update_output.yview
        )

        self.update_output.configure(
            yscrollcommand=scroll.set
        )

        self.update_output.grid(
            row=0,
            column=0,
            sticky="nsew"
        )

        scroll.grid(
            row=0,
            column=1,
            sticky="ns"
        )


    # ==========================================================
    # CHANNELS TAB
    # ==========================================================

    def _build_channels_tab(self, parent=None):

        if parent is None:
            parent = self.channels_tab

        parent.grid_rowconfigure(
            0,
            weight=1
        )

        parent.grid_columnconfigure(
            0,
            weight=1
        )

        container = ttk.Frame(
            parent
        )

        container.grid(
            row=0,
            column=0,
            sticky="nsew"
        )

        container.grid_rowconfigure(
            0,
            weight=1
        )

        container.grid_columnconfigure(
            0,
            weight=1
        )

        self.tree = ttk.Treeview(
            container,
            show="tree"
        )

        self.tree.grid(
            row=0,
            column=0,
            sticky="nsew"
        )

        self.tree.bind(
            "<<TreeviewSelect>>",
            self._on_tree_select
        )

        scroll = ttk.Scrollbar(
            container,
            orient="vertical",
            command=self.tree.yview
        )

        scroll.grid(
            row=0,
            column=1,
            sticky="ns"
        )

        self.tree.configure(
            yscrollcommand=scroll.set
        )

        self.detail_frame = ttk.Frame(
            container
        )

        self.detail_frame.grid(
            row=0,
            column=2,
            sticky="nsew"
        )

        self.detail_frame.grid_columnconfigure(
            1,
            weight=1
        )

        labels = (
            "Path",
            "Tracks",
            "Enabled",
            "Flow Enabled",
            "Qbit Allowed",
            "Sequence",
            "Last Timestamp",
        )

        self.detail_vars = {}

        for index, label in enumerate(labels):

            ttk.Label(
                self.detail_frame,
                text=f"{label}:"
            ).grid(
                row=index,
                column=0,
                sticky="w",
                padx=4,
                pady=2
            )

            variable = tk.StringVar(
                value=""
            )

            self.detail_vars[
                label
            ] = variable

            ttk.Label(
                self.detail_frame,
                textvariable=variable
            ).grid(
                row=index,
                column=1,
                sticky="w",
                padx=4,
                pady=2
            )


    # ==========================================================
    # DYNAMIC CONTENT HELPERS
    # ==========================================================

    def set_dynamic_content(
        self,
        frame_class
    ):

        if not hasattr(
            self,
            "dynamic_container"
        ):
            raise RuntimeError(
                "dynamic_container not built."
            )

        for widget in (
            self.dynamic_container.winfo_children()
        ):
            widget.destroy()

        frame = frame_class(
            self.dynamic_container
        )

        frame.grid(
            row=0,
            column=0,
            sticky="nsew"
        )

        self.active_dynamic_module = frame

        return frame


    def clear_dynamic(self):

        if not hasattr(
            self,
            "dynamic_container"
        ):
            return

        for widget in (
            self.dynamic_container.winfo_children()
        ):
            widget.destroy()

        self.active_dynamic_module = None


    def load_module(
        self,
        module_class
    ):


        self.clear_dynamic()

        if not hasattr(
            self,
            "dynamic_container"
        ):
            return None

        module = module_class(
            self.dynamic_container
        )

        module.grid(
            row=0,
            column=0,
            sticky="nsew"
        )

        self.active_dynamic_module = module

        return module


    def set_left_tab_content(
        self,
        frame_class,
        tab_name="Module"
    ):

        if not hasattr(
            self,
            "left_hud"
        ):
            raise RuntimeError(
                "left_hud not built."
            )

        frame = frame_class(
            self.left_hud
        )

        self.left_hud.add(
            frame,
            text=tab_name
        )

        return frame

# ==========================================================
# SECTION 12 — SEED OS REGISTRY GROWTH FABRIC
# ==========================================================
# PURPOSE:
#     Give SEED OS a persistent runtime-facing development
#     fabric for learning, discovering, connecting, and growing
#     without making DEVHUD or FATHUD an execution authority.
#
# AUTHORITY:
#     QbitDialer -> command authority
#     QbitQueueLoop -> execution / transport authority
#     ModuleRegistry / OptionRegistry -> capability registry
#     TrackSystem -> lineage / track context
#     SEEDEventBus -> shared event transport
#     Oracle -> observer / governance
#     DEVHUD / FATHUD -> developer interfaces / observers
#
# DEVELOPMENT MODEL:
#     Developer suggestion
#         ->
#     SEED_INPUT
#         ->
#     registry discovery / capability resolution
#         ->
#     cognition
#         ->
#     ActionEngine proposal
#         ->
#     QbitDialer authorization
#         ->
#     submit_command()
#         ->
#     QbitQueueLoop
#
# IMPORTANT:
#     This section does NOT:
#         - execute commands directly
#         - construct Qbits for execution
#         - start another runtime
#         - install packages
#         - start MCP servers
#         - bypass QbitDialer
#         - make DEVHUD authoritative
#         - make FATHUD authoritative
# ==========================================================


def _initialize_registry_growth_fabric(self):
    """
    Initialize the registry-backed SEED OS growth fabric.

    This binds to already-existing registry instances whenever
    available. It does not create a competing registry or runtime.
    """

    # ------------------------------------------------------
    # CORE REGISTRY REFERENCES
    # ------------------------------------------------------

    self.module_registry = getattr(
        self,
        "module_registry",
        None,
    )

    self.option_registry = getattr(
        self,
        "option_registry",
        None,
    )

    # Runtime may provide registry objects through kwargs or
    # another already-bound runtime component.
    if self.module_registry is None:
        self.module_registry = getattr(
            self,
            "registry",
            None,
        )

    if self.module_registry is None:
        self.module_registry = getattr(
            self,
            "_module_registry",
            None,
        )

    if self.option_registry is None:
        self.option_registry = getattr(
            self,
            "_option_registry",
            None,
        )

    # ------------------------------------------------------
    # GROWTH STATE
    # ------------------------------------------------------

    self._seedos_growth_initialized = True

    self._seedos_growth_sequence = int(
        getattr(
            self,
            "_seedos_growth_sequence",
            0,
        )
        or 0
    )

    self._seedos_growth_ledger = getattr(
        self,
        "_seedos_growth_ledger",
        [],
    )

    self._seedos_capability_index = getattr(
        self,
        "_seedos_capability_index",
        {},
    )

    self._seedos_system_index = getattr(
        self,
        "_seedos_system_index",
        {},
    )

    self._seedos_learning_index = getattr(
        self,
        "_seedos_learning_index",
        {},
    )

    self._seedos_registry_events = getattr(
        self,
        "_seedos_registry_events",
        [],
    )

    # ------------------------------------------------------
    # CONNECT KNOWN RUNTIME SYSTEMS
    # ------------------------------------------------------

    self._seedos_register_known_runtime_systems()

    # ------------------------------------------------------
    # CONNECT EXISTING CAPABILITY REGISTRIES
    # ------------------------------------------------------

    self._seedos_discover_registry_capabilities()

    # ------------------------------------------------------
    # EVENT BRIDGE
    # ------------------------------------------------------

    self._seedos_register_growth_events()

    return {
        "status": "initialized",
        "module_registry": (
            self.module_registry is not None
        ),
        "option_registry": (
            self.option_registry is not None
        ),
        "capabilities": len(
            self._seedos_capability_index
        ),
        "systems": len(
            self._seedos_system_index
        ),
    }


def _seedos_registry_call(
    self,
    registry,
    method_names,
    *args,
    **kwargs,
):
    """
    Safely call an existing registry API without assuming a
    particular registry implementation.

    This keeps DEVHUD compatible with whichever authoritative
    registry implementation SEED OS currently provides.
    """

    if registry is None:
        return None

    for method_name in method_names:

        method = getattr(
            registry,
            method_name,
            None,
        )

        if not callable(method):
            continue

        try:
            return method(
                *args,
                **kwargs,
            )

        except TypeError:
            # Registry APIs may differ in argument shape.
            continue

        except Exception as exc:
            self.logger.debug(
                "[DEVHUD] Registry call failed | "
                "method=%s | error=%s",
                method_name,
                exc,
            )

            return None

    return None


def _seedos_registry_register(
    self,
    descriptor,
):
    """
    Register a capability/system with the existing registry
    when that registry exposes a compatible registration API.

    Local indexing remains available even when the external
    registry implementation does not expose registration.
    """

    if not isinstance(
        descriptor,
        dict,
    ):
        return False

    name = str(
        descriptor.get(
            "name",
            descriptor.get(
                "id",
                "",
            ),
        )
    ).strip()

    if not name:
        return False

    descriptor = dict(descriptor)

    descriptor.setdefault(
        "authority",
        "QbitDialer",
    )

    descriptor.setdefault(
        "transport",
        "SEEDEventBus",
    )

    descriptor.setdefault(
        "observer",
        "Oracle",
    )

    descriptor.setdefault(
        "interface",
        "DEVHUD/FATHUD",
    )

    descriptor.setdefault(
        "execution_required",
        False,
    )

    descriptor.setdefault(
        "registered_by",
        "SEED_OS_DEVELOPER_FABRIC",
    )

    # Local authoritative view used by the developer interface.
    self._seedos_capability_index[name] = descriptor

    result = self._seedos_registry_call(
        self.module_registry,
        (
            "register",
            "register_module",
            "register_capability",
            "add",
            "add_module",
        ),
        name,
        descriptor,
    )

    if result is None:
        # Some registries use descriptor-only registration.
        result = self._seedos_registry_call(
            self.module_registry,
            (
                "register",
                "register_module",
                "register_capability",
                "add",
                "add_module",
            ),
            descriptor,
        )

    return True


def _seedos_register_known_runtime_systems(self):
    """
    Describe the systems already known to DEVHUD/SEED OS.

    These are references/descriptors only. No new runtime system
    is created here.
    """

    systems = {
        "QbitDialer": {
            "name": "QbitDialer",
            "type": "authority",
            "role": "command_authority",
            "execution": True,
        },

        "QbitQueueLoop": {
            "name": "QbitQueueLoop",
            "type": "transport",
            "role": "execution_transport",
            "execution": True,
        },

        "ComputeBrain": {
            "name": "ComputeBrain",
            "type": "cognition",
            "role": "thought_generation",
            "execution": False,
        },

        "TransformerBrain": {
            "name": "TransformerBrain",
            "type": "cognition",
            "role": "thought_transformation",
            "execution": False,
        },

        "IntentEngine": {
            "name": "IntentEngine",
            "type": "cognition",
            "role": "intent_interpretation",
            "execution": False,
        },

        "ActionEngine": {
            "name": "ActionEngine",
            "type": "cognition",
            "role": "action_proposal",
            "execution": False,
        },

        "AnalyticsEngine": {
            "name": "AnalyticsEngine",
            "type": "analytics",
            "role": "cycle_observation",
            "execution": False,
        },

        "ThoughtFeedback": {
            "name": "ThoughtFeedback",
            "type": "learning",
            "role": "feedback",
            "execution": False,
        },

        "TrackSystem": {
            "name": "TrackSystem",
            "type": "lineage",
            "role": "track_context",
            "execution": False,
        },

        "SEEDEventBus": {
            "name": "SEEDEventBus",
            "type": "transport",
            "role": "shared_event_transport",
            "execution": False,
        },

        "Oracle": {
            "name": "Oracle",
            "type": "observer",
            "role": "governance_observer",
            "execution": False,
        },

        "DEVHUD": {
            "name": "DEVHUD",
            "type": "interface",
            "role": "developer_interface",
            "execution": False,
        },

        "FATHUD": {
            "name": "FATHUD",
            "type": "interface",
            "role": "developer_observer_interface",
            "execution": False,
        },

        "MemoryCrystallizer": {
            "name": "MemoryCrystallizer",
            "type": "memory",
            "role": "memory_persistence",
            "execution": False,
        },

        "TimeTravelEngine": {
            "name": "TimeTravelEngine",
            "type": "history",
            "role": "historical_state_observation",
            "execution": False,
        },
    }

    for name, descriptor in systems.items():

        self._seedos_system_index[name] = dict(
            descriptor
        )

        self._seedos_registry_register(
            {
                **descriptor,
                "category": "runtime_system",
            }
        )


def _seedos_discover_registry_capabilities(self):
    """
    Discover capabilities already exposed by the registry.

    Discovery is passive. It does not instantiate or execute
    discovered systems.
    """

    registries = (
        (
            "module_registry",
            self.module_registry,
        ),
        (
            "option_registry",
            self.option_registry,
        ),
    )

    for registry_name, registry in registries:

        if registry is None:
            continue

        result = self._seedos_registry_call(
            registry,
            (
                "list",
                "list_modules",
                "list_capabilities",
                "get_all",
                "all",
                "snapshot",
                "describe",
            ),
        )

        if result is None:
            continue

        if isinstance(
            result,
            dict,
        ):
            items = result.items()

        elif isinstance(
            result,
            (list, tuple, set),
        ):
            items = (
                (
                    str(item),
                    item,
                )
                for item in result
            )

        else:
            continue

        for name, item in items:

            key = str(
                name
            ).strip()

            if not key:
                continue

            if isinstance(
                item,
                dict,
            ):
                descriptor = dict(item)

            else:
                descriptor = {
                    "value": item,
                }

            descriptor.setdefault(
                "name",
                key,
            )

            descriptor.setdefault(
                "registry",
                registry_name,
            )

            descriptor.setdefault(
                "discovered",
                True,
            )

            self._seedos_capability_index[
                key
            ] = descriptor


def _seedos_register_growth_events(self):
    """
    Connect the growth fabric to the existing EventBus.

    The EventBus remains transport only.
    """

    event_bus = getattr(
        self,
        "event_bus",
        None,
    )

    if event_bus is None:
        return False

    subscriptions = {
        "SEED_INPUT":
            self._seedos_growth_input_event,

        "SEED_DEVELOPMENT_PROPOSAL":
            self._seedos_growth_proposal_event,

        "SEED_DEVELOPMENT_FEEDBACK":
            self._seedos_growth_feedback_event,

        "SEED_COMMAND_RESULT":
            self._seedos_growth_execution_result,

        "SEED_COMMAND_DENIED":
            self._seedos_growth_command_denied,

        "SEED_ERROR":
            self._seedos_growth_error,

        "THOUGHT":
            self._seedos_growth_thought,

        "STATE":
            self._seedos_growth_state,

        "SEED_HEARTBEAT":
            self._seedos_growth_heartbeat,

    }

    for event_name, handler in subscriptions.items():

        subscribe = getattr(
            event_bus,
            "subscribe",
            None,
        )

        if not callable(subscribe):
            continue

        try:
            subscribe(
                event_name,
                handler,
            )

            self._seedos_registry_events.append(
                event_name
            )

        except Exception as exc:

            self.logger.debug(
                "[DEVHUD] Growth event subscription "
                "failed | event=%s | error=%s",
                event_name,
                exc,
            )

    return True


def _seedos_growth_event_record(
    self,
    event_type,
    payload=None,
):
    """
    Record a learning/development event without treating the
    event as an instruction.
    """

    self._seedos_growth_sequence += 1

    record = {
        "sequence":
            self._seedos_growth_sequence,

        "event":
            str(event_type),

        "timestamp":
            time.time(),

        "payload":
            payload if isinstance(
                payload,
                dict,
            )
            else {
                "value": payload,
            },

        "authority":
            "QbitDialer",

        "interface":
            "DEVHUD/FATHUD",

        "observer":
            "Oracle",

        "transport":
            "SEEDEventBus",
    }

    self._seedos_growth_ledger.append(
        record
    )

    # Keep the in-memory developer ledger bounded.
    if len(
        self._seedos_growth_ledger
    ) > 2000:

        del self._seedos_growth_ledger[
            :-2000
        ]

    return record


def _seedos_growth_input_event(
    self,
    payload=None,
):
    """
    Developer/user input enters the growth fabric as data.

    It does not become a direct command.
    """

    return self._seedos_growth_event_record(
        "input",
        payload,
    )


def _seedos_growth_proposal_event(
    self,
    payload=None,
):
    return self._seedos_growth_event_record(
        "development_proposal",
        payload,
    )


def _seedos_growth_feedback_event(
    self,
    payload=None,
):
    return self._seedos_growth_event_record(
        "development_feedback",
        payload,
    )


def _seedos_growth_execution_result(
    self,
    payload=None,
):
    """
    Observe completed execution.

    This is where SEED can learn from the result of a
    QbitDialer/QbitQueueLoop-authorized cycle.
    """

    record = self._seedos_growth_event_record(
        "execution_result",
        payload,
    )

    self._seedos_update_learning_index(
        payload,
        outcome="completed",
    )

    return record


def _seedos_growth_command_denied(
    self,
    payload=None,
):
    """
    A denial is learning data, not an error to bypass.
    """

    record = self._seedos_growth_event_record(
        "command_denied",
        payload,
    )

    self._seedos_update_learning_index(
        payload,
        outcome="denied",
    )

    return record


def _seedos_growth_error(
    self,
    payload=None,
):
    record = self._seedos_growth_event_record(
        "error",
        payload,
    )

    self._seedos_update_learning_index(
        payload,
        outcome="error",
    )

    return record


def _seedos_growth_thought(
    self,
    payload=None,
):
    return self._seedos_growth_event_record(
        "thought",
        payload,
    )


def _seedos_growth_state(
    self,
    payload=None,
):
    return self._seedos_growth_event_record(
        "state",
        payload,
    )


def _seedos_growth_heartbeat(
    self,
    payload=None,
):
    return self._seedos_growth_event_record(
        "heartbeat",
        payload,
    )


def _seedos_update_learning_index(
    self,
    payload,
    *,
    outcome,
):
    """
    Build lightweight learning statistics from completed
    system cycles.

    This does not alter cognition or execute anything.
    """

    if not isinstance(
        payload,
        dict,
    ):
        return None

    category = str(
        payload.get(
            "category",
            payload.get(
                "command",
                payload.get(
                    "action",
                    "unknown",
                ),
            ),
        )
    ).strip()

    if not category:
        category = "unknown"

    entry = self._seedos_learning_index.setdefault(
        category,
        {
            "attempts": 0,
            "completed": 0,
            "denied": 0,
            "errors": 0,
        },
    )

    entry["attempts"] += 1

    if outcome == "completed":
        entry["completed"] += 1

    elif outcome == "denied":
        entry["denied"] += 1

    elif outcome == "error":
        entry["errors"] += 1

    return entry


def _seedos_learn_from_feedback(
    self,
    feedback,
    *,
    source="developer",
):
    """
    Convert explicit developer feedback into learning data.

    Feedback remains a suggestion. SEED cognition determines
    whether and how it becomes operational behavior.
    """

    if feedback is None:
        return {
            "status": "ignored",
            "reason": "empty_feedback",
        }

    if isinstance(
        feedback,
        dict,
    ):
        data = dict(feedback)

    else:
        data = {
            "feedback": str(
                feedback
            ),
        }

    data.setdefault(
        "source",
        source,
    )

    data.setdefault(
        "type",
        "learning_feedback",
    )

    data.setdefault(
        "execution_required",
        False,
    )

    data.setdefault(
        "authority",
        "QbitDialer",
    )

    record = self._seedos_growth_event_record(
        "learning_feedback",
        data,
    )

    # Existing memory bridge, if already attached.
    memory = getattr(
        self,
        "memory_crystallizer",
        None,
    )

    if memory is not None:

        self._seedos_memory_observe(
            memory,
            data,
        )

    return {
        "status": "recorded",
        "record": record,
    }


def _seedos_memory_observe(
    self,
    memory,
    data,
):
    """
    Safely connect learning data to MemoryCrystallizer without
    assuming one particular implementation.
    """

    for method_name in (
        "attach_memory",
        "remember",
        "store",
        "record",
        "crystallize",
        "add",
    ):

        method = getattr(
            memory,
            method_name,
            None,
        )

        if not callable(method):
            continue

        try:
            return method(
                data
            )

        except TypeError:
            try:
                return method(
                    data=data
                )

            except Exception:
                continue

        except Exception:
            continue

    return None


def _seedos_suggest_growth(
    self,
    suggestion,
    *,
    category="DEVELOP",
    target=None,
    source="DEVHUD",
):
    """
    Primary developer-to-SEED growth interface.

    A suggestion is never directly executed.

    It becomes SEED_INPUT plus development metadata so the
    normal cognitive pipeline can evaluate it.
    """

    if suggestion is None:
        return {
            "status": "ignored",
            "reason": "empty_suggestion",
        }

    text = str(
        suggestion
    ).strip()

    if not text:
        return {
            "status": "ignored",
            "reason": "empty_suggestion",
        }

    self._seedos_growth_sequence += 1

    proposal = {
        "proposal_id":
            "DEVPROP.%08d"
            % self._seedos_growth_sequence,

        "category":
            str(category).upper(),

        "suggestion":
            text,

        "target":
            target,

        "source":
            source,

        "interface":
            "DEVHUD/FATHUD",

        "operating_system":
            "SEED OS",

        "authority":
            "QbitDialer",

        "execution_required":
            False,

        "proposal_only":
            True,

        "registry_backed":
            True,

        "timestamp":
            time.time(),
    }

    # ------------------------------------------------------
    # REGISTRY CONTEXT
    # ------------------------------------------------------

    proposal["known_capabilities"] = list(
        self._seedos_capability_index.keys()
    )

    proposal["known_systems"] = list(
        self._seedos_system_index.keys()
    )

    # ------------------------------------------------------
    # EVENTBUS -> COGNITION
    # ------------------------------------------------------

    event_bus = getattr(
        self,
        "event_bus",
        None,
    )

    emitted = False

    if event_bus is not None:

        emit = getattr(
            event_bus,
            "emit",
            None,
        )

        if callable(emit):

            try:
                emit(
                    "SEED_INPUT",
                    proposal,
                )

                emitted = True

            except Exception as exc:

                self.logger.debug(
                    "[DEVHUD] SEED_INPUT emission failed | "
                    "error=%s",
                    exc,
                )

    self._seedos_growth_event_record(
        "development_suggestion",
        proposal,
    )

    # ------------------------------------------------------
    # ORACLE OBSERVATION
    # ------------------------------------------------------

    oracle = getattr(
        self,
        "oracle",
        getattr(
            self,
            "oracle_loop",
            None,
        ),
    )

    if oracle is not None:

        observer = getattr(
            oracle,
            "observe",
            None,
        )

        if callable(observer):

            try:
                observer(
                    proposal
                )

            except Exception:
                pass

    # ------------------------------------------------------
    # MEMORY
    # ------------------------------------------------------

    self._seedos_learn_from_feedback(
        proposal,
        source=source,
    )

    return {
        "status":
            "submitted"
            if emitted
            else "recorded",

        "proposal":
            proposal,

        "cognition_entry":
            emitted,

        "execution":
            "NOT_EXECUTED",

        "authority":
            "QbitDialer",
    }


def _seedos_connect_dynamic_system(
    self,
    name,
    *,
    system_type="dynamic",
    capabilities=None,
    source="developer",
    metadata=None,
):
    """
    Add a dynamic system to SEED's registry-facing knowledge
    without instantiating or executing the system.

    The actual adapter/provider remains responsible for its
    implementation.
    """

    key = str(
        name
    ).strip()

    if not key:
        return {
            "status": "rejected",
            "reason": "missing_name",
        }

    descriptor = {
        "name":
            key,

        "type":
            system_type,

        "capabilities":
            list(
                capabilities or []
            ),

        "source":
            source,

        "metadata":
            dict(
                metadata or {}
            ),

        "dynamic":
            True,

        "connected":
            False,

        "execution_required":
            False,

        "authority":
            "QbitDialer",

        "observer":
            "Oracle",

        "transport":
            "SEEDEventBus",

        "interface":
            "DEVHUD/FATHUD",
    }

    self._seedos_system_index[
        key
    ] = descriptor

    self._seedos_registry_register(
        descriptor
    )

    self._seedos_growth_event_record(
        "dynamic_system_registered",
        descriptor,
    )

    return {
        "status": "registered",
        "system": descriptor,
    }


def _seedos_registry_growth_snapshot(self):
    """
    Return the complete developer-facing map of what SEED OS
    currently knows through this bridge.
    """

    return {
        "operating_system":
            "SEED OS",

        "authority":
            "QbitDialer",

        "transport":
            "QbitQueueLoop",

        "event_transport":
            "SEEDEventBus",

        "tracking":
            "TrackSystem",

        "observer":
            "Oracle",

        "developer_interfaces": [
            "DEVHUD",
            "FATHUD",
        ],

        "module_registry_available":
            self.module_registry is not None,

        "option_registry_available":
            self.option_registry is not None,

        "systems":
            dict(
                self._seedos_system_index
            ),

        "capabilities":
            dict(
                self._seedos_capability_index
            ),

        "learning":
            dict(
                self._seedos_learning_index
            ),

        "growth_events":
            len(
                self._seedos_growth_ledger
            ),

        "development_model":
            "SUGGEST -> COGNITION -> PROPOSE -> "
            "QBITDIALER -> SUBMIT_COMMAND -> "
            "QBITQUEUELOOP",

        "direct_execution_from_devhud":
            False,

        "direct_execution_from_fathud":
            False,
    }


def _seedos_growth_status(self):
    """
    Compact status used by DEVHUD/FATHUD and future developer
    interface controls.
    """

    return {
        "initialized":
            bool(
                getattr(
                    self,
                    "_seedos_growth_initialized",
                    False,
                )
            ),

        "registry":
            {
                "module":
                    self.module_registry is not None,

                "option":
                    self.option_registry is not None,
            },

        "systems":
            len(
                self._seedos_system_index
            ),

        "capabilities":
            len(
                self._seedos_capability_index
            ),

        "learning_categories":
            len(
                self._seedos_learning_index
            ),

        "growth_events":
            len(
                self._seedos_growth_ledger
            ),

        "oracle":
            getattr(
                self,
                "oracle",
                getattr(
                    self,
                    "oracle_loop",
                    None,
                ),
            )
            is not None,

        "fathud":
            getattr(
                self,
                "fathud",
                None,
            )
            is not None,

        "qbit_dialer":
            getattr(
                self,
                "qbit_dialer",
                None,
            )
            is not None,

        "qbit_queue_loop":
            getattr(
                self,
                "qbit_queue_loop",
                getattr(
                    self,
                    "qbit_queue",
                    None,
                ),
            )
            is not None,
    }


# ----------------------------------------------------------
# PUBLIC DEVHUD METHODS
# ----------------------------------------------------------

def suggest_to_seed_os(
    self,
    suggestion,
    category="DEVELOP",
    target=None,
):
    """
    Public developer interface.

    The developer suggests.
    SEED OS decides what the suggestion means.
    """

    return self._seedos_suggest_growth(
        suggestion,
        category=category,
        target=target,
        source="DEVHUD",
    )


def teach_seed_os(
    self,
    teaching,
    target=None,
):
    """
    Explicit teaching interface.

    Teaching becomes learning data and SEED_INPUT.
    It is not an immediate command.
    """

    result = self._seedos_suggest_growth(
        teaching,
        category="TEACH",
        target=target,
        source="DEVHUD",
    )

    return result


def connect_dynamic_system(
    self,
    name,
    capabilities=None,
    metadata=None,
):
    """
    Register a dynamic system/capability source for SEED OS
    consideration without executing it.
    """

    return self._seedos_connect_dynamic_system(
        name,
        capabilities=capabilities,
        metadata=metadata,
        source="DEVHUD",
    )


def get_seed_os_growth_status(self):
    return self._seedos_growth_status()


def get_seed_os_registry_map(self):
    return self._seedos_registry_growth_snapshot()



# ==========================================================
# SEED OS GROWTH FABRIC
# ==========================================================
# Initialization is instance-bound; module import must not require a local self.
try:
    _devhud_instance = globals().get("self")
    if _devhud_instance is not None:
        _devhud_instance._initialize_registry_growth_fabric()
except Exception as exc:
    _devhud_logger = globals().get("logger")
    if _devhud_logger is not None:
        _devhud_logger.warning(
            "[DEVHUD] SEED OS growth fabric initialization deferred | error=%s",
            exc,
        )

    # ==========================================================
    # SECTION 13 — SEED OS DEVELOPER SANDBOX CORE
    # ==========================================================
    # PURPOSE:
    #     Provide the first real developer workspace for SEED OS.
    #
    #     Developer interaction is a SUGGESTION / OBSERVATION /
    #     DEVELOPMENT request. It is never direct authority.
    #
    # FLOW:
    #
    #     DEVHUD / FATHUD
    #             |
    #             v
    #     Developer Sandbox
    #             |
    #             v
    #     Registry / Capability Map
    #             |
    #             v
    #     SEED_INPUT
    #             |
    #             v
    #     ComputeBrain
    #             |
    #             v
    #     TransformerBrain
    #             |
    #             v
    #     IntentEngine
    #             |
    #             v
    #     ActionEngine
    #             |
    #             v
    #     QbitDialer
    #             |
    #             v
    #     submit_command()
    #             |
    #             v
    #     QbitQueueLoop
    #
    #     Results / feedback return through EventBus and learning.
    #
    # AUTHORITY:
    #     QbitDialer = command authority
    #     QbitQueueLoop = execution / transport authority
    #     Registry = capability/system knowledge
    #     TrackSystem = lineage
    #     SEEDEventBus = event transport
    #     Oracle = observer / governance
    #     DEVHUD = developer interface
    #     FATHUD = developer/observer interface
    #
    # NO DIRECT EXECUTION FROM THIS SECTION.
    # ==========================================================

    def _initialize_seedos_sandbox(self):
        """
        Initialize the SEED OS developer sandbox.

        The sandbox is an interface layer over the existing
        runtime. It does not create another execution engine.
        """

        self._seedos_sandbox_initialized = True

        self._seedos_sandbox_session_id = (
            "SANDBOX.%s"
            % uuid.uuid4().hex[:16]
        )

        self._seedos_sandbox_history = getattr(
            self,
            "_seedos_sandbox_history",
            [],
        )

        self._seedos_sandbox_pending = getattr(
            self,
            "_seedos_sandbox_pending",
            {},
        )

        self._seedos_sandbox_results = getattr(
            self,
            "_seedos_sandbox_results",
            [],
        )

        self._seedos_sandbox_mode = getattr(
            self,
            "_seedos_sandbox_mode",
            "observe",
        )

        self._seedos_sandbox_capabilities = {
            "teach": True,
            "suggest": True,
            "inspect": True,
            "connect": True,
            "develop": True,
            "test": True,
            "review": True,
            "grow": True,
            "mcp": True,
            "sdk": True,
            "dynamic": True,
        }

        self._seedos_register_sandbox_events()

        return {
            "status": "initialized",
            "session_id":
                self._seedos_sandbox_session_id,
            "mode":
                self._seedos_sandbox_mode,
            "capabilities":
                dict(
                    self._seedos_sandbox_capabilities
                ),
        }

    def _seedos_register_sandbox_events(self):
        """
        Connect sandbox result/feedback handling to the
        existing EventBus.

        No second EventBus is created.
        """

        event_bus = getattr(
            self,
            "event_bus",
            None,
        )

        if event_bus is None:
            return False

        subscribe = getattr(
            event_bus,
            "subscribe",
            None,
        )

        if not callable(subscribe):
            return False

        handlers = {
            "SEED_INPUT":
                self._seedos_sandbox_input_observer,

            "SEED_OUTPUT":
                self._seedos_sandbox_output_observer,

            "SEED_COMMAND_RESULT":
                self._seedos_sandbox_result_observer,

            "SEED_COMMAND_DENIED":
                self._seedos_sandbox_denied_observer,

            "SEED_ERROR":
                self._seedos_sandbox_error_observer,

            "THOUGHT":
                self._seedos_sandbox_thought_observer,

            "STATE":
                self._seedos_sandbox_state_observer,
        }

        for event_name, handler in handlers.items():

            try:
                subscribe(
                    event_name,
                    handler,
                )

            except Exception as exc:

                self.logger.debug(
                    "[DEVHUD] Sandbox subscription failed | "
                    "event=%s | error=%s",
                    event_name,
                    exc,
                )

        return True

    def _seedos_sandbox_record(
        self,
        event_type,
        payload=None,
    ):
        """
        Record sandbox activity for developer inspection.
        """

        record = {
            "event":
                str(event_type),

            "timestamp":
                time.time(),

            "session_id":
                getattr(
                    self,
                    "_seedos_sandbox_session_id",
                    None,
                ),

            "payload":
                payload
                if isinstance(
                    payload,
                    dict,
                )
                else {
                    "value": payload,
                },

            "authority":
                "QbitDialer",

            "interface":
                "DEVHUD/FATHUD",

            "operating_system":
                "SEED OS",
        }

        self._seedos_sandbox_history.append(
            record
        )

        if len(
            self._seedos_sandbox_history
        ) > 2000:

            del self._seedos_sandbox_history[
                :-2000
            ]

        return record

    def _seedos_sandbox_input_observer(
        self,
        payload=None,
    ):
        return self._seedos_sandbox_record(
            "input",
            payload,
        )

    def _seedos_sandbox_output_observer(
        self,
        payload=None,
    ):
        return self._seedos_sandbox_record(
            "output",
            payload,
        )

    def _seedos_sandbox_result_observer(
        self,
        payload=None,
    ):
        """
        Capture completed execution results.

        Execution itself remains owned by QbitQueueLoop.
        """

        record = self._seedos_sandbox_record(
            "execution_result",
            payload,
        )

        self._seedos_sandbox_results.append(
            record
        )

        if len(
            self._seedos_sandbox_results
        ) > 1000:

            del self._seedos_sandbox_results[
                :-1000
            ]

        return record

    def _seedos_sandbox_denied_observer(
        self,
        payload=None,
    ):
        return self._seedos_sandbox_record(
            "command_denied",
            payload,
        )

    def _seedos_sandbox_error_observer(
        self,
        payload=None,
    ):
        return self._seedos_sandbox_record(
            "error",
            payload,
        )

    def _seedos_sandbox_thought_observer(
        self,
        payload=None,
    ):
        return self._seedos_sandbox_record(
            "thought",
            payload,
        )

    def _seedos_sandbox_state_observer(
        self,
        payload=None,
    ):
        return self._seedos_sandbox_record(
            "state",
            payload,
        )

    def _seedos_sandbox_submit(
        self,
        text,
        *,
        category="DEVELOP",
        target=None,
        metadata=None,
    ):
        """
        Main developer sandbox submission path.

        IMPORTANT:
            This method does NOT call submit_command().
            It sends developer intent into SEED's normal
            cognitive input path.

        Qbit creation and command admission remain downstream
        responsibilities.
        """

        if text is None:
            return {
                "status": "ignored",
                "reason": "empty_input",
            }

        text = str(
            text
        ).strip()

        if not text:
            return {
                "status": "ignored",
                "reason": "empty_input",
            }

        proposal = {
            "sandbox_session":
                getattr(
                    self,
                    "_seedos_sandbox_session_id",
                    None,
                ),

            "input":
                text,

            "category":
                str(
                    category
                ).upper(),

            "target":
                target,

            "metadata":
                dict(
                    metadata or {}
                ),

            "source":
                "SEED_OS_DEVELOPER_SANDBOX",

            "operating_system":
                "SEED OS",

            "proposal_only":
                True,

            "execution_required":
                False,

            "authority":
                "QbitDialer",

            "interface":
                "DEVHUD/FATHUD",

            "timestamp":
                time.time(),
        }

        # --------------------------------------------------
        # REGISTRY CONTEXT
        # --------------------------------------------------

        proposal[
            "known_systems"
        ] = list(
            getattr(
                self,
                "_seedos_system_index",
                {},
            ).keys()
        )

        proposal[
            "known_capabilities"
        ] = list(
            getattr(
                self,
                "_seedos_capability_index",
                {},
            ).keys()
        )

        # --------------------------------------------------
        # LOCAL SANDBOX RECORD
        # --------------------------------------------------

        record = self._seedos_sandbox_record(
            "developer_submission",
            proposal,
        )

        proposal[
            "record_sequence"
        ] = len(
            self._seedos_sandbox_history
        )

        # --------------------------------------------------
        # EXISTING SEED GROWTH BRIDGE
        # --------------------------------------------------

        growth_method = getattr(
            self,
            "_seedos_suggest_growth",
            None,
        )

        if callable(
            growth_method
        ):

            try:

                result = growth_method(
                    text,
                    category=category,
                    target=target,
                    source=(
                        "SEED_OS_DEVELOPER_SANDBOX"
                    ),
                )

                self._seedos_sandbox_pending[
                    proposal[
                        "sandbox_session"
                    ]
                ] = proposal

                return {
                    "status":
                        "submitted",

                    "sandbox":
                        proposal,

                    "growth":
                        result,

                    "record":
                        record,

                    "execution":
                        "NOT_EXECUTED",
                }

            except Exception as exc:

                self.logger.warning(
                    "[DEVHUD] Sandbox growth "
                    "submission failed | error=%s",
                    exc,
                )

        # --------------------------------------------------
        # FALLBACK EVENTBUS INPUT
        # --------------------------------------------------

        event_bus = getattr(
            self,
            "event_bus",
            None,
        )

        if event_bus is not None:

            emit = getattr(
                event_bus,
                "emit",
                None,
            )

            if callable(
                emit
            ):

                try:

                    emit(
                        "SEED_INPUT",
                        proposal,
                    )

                    self._seedos_sandbox_pending[
                        proposal[
                            "sandbox_session"
                        ]
                    ] = proposal

                    return {
                        "status":
                            "submitted",

                        "sandbox":
                            proposal,

                        "record":
                            record,

                        "execution":
                            "NOT_EXECUTED",
                    }

                except Exception as exc:

                    self.logger.debug(
                        "[DEVHUD] Sandbox "
                        "SEED_INPUT failed | "
                        "error=%s",
                        exc,
                    )

        return {
            "status":
                "recorded",

            "sandbox":
                proposal,

            "record":
                record,

            "execution":
                "NOT_EXECUTED",

            "reason":
                "no_seed_input_transport",
        }

    def seedos_teach(
        self,
        teaching,
        target=None,
        metadata=None,
    ):
        """
        Teach SEED OS through the developer interface.

        Teaching is data supplied to cognition. It does not
        directly modify core modules.
        """

        return self._seedos_sandbox_submit(
            teaching,
            category="TEACH",
            target=target,
            metadata=metadata,
        )

    def seedos_suggest(
        self,
        suggestion,
        target=None,
        metadata=None,
    ):
        """
        Suggest a development direction to SEED OS.
        """

        return self._seedos_sandbox_submit(
            suggestion,
            category="DEVELOP",
            target=target,
            metadata=metadata,
        )

    def seedos_inspect(
        self,
        request,
        target=None,
        metadata=None,
    ):
        """
        Ask SEED to inspect a system/capability.
        """

        return self._seedos_sandbox_submit(
            request,
            category="INSPECT",
            target=target,
            metadata=metadata,
        )

    def seedos_grow(
        self,
        request,
        target=None,
        metadata=None,
    ):
        """
        Ask SEED OS to evaluate how it could grow.
        """

        return self._seedos_sandbox_submit(
            request,
            category="GROW",
            target=target,
            metadata=metadata,
        )

    def seedos_test(
        self,
        request,
        target=None,
        metadata=None,
    ):
        """
        Ask SEED to evaluate/test a development idea.

        This records the request; it does not execute arbitrary
        developer code from the HUD.
        """

        return self._seedos_sandbox_submit(
            request,
            category="TEST",
            target=target,
            metadata=metadata,
        )

    def seedos_connect(
        self,
        request,
        target=None,
        metadata=None,
    ):
        """
        Ask SEED OS to evaluate connecting a dynamic system,
        SDK, MCP server, provider, adapter, or capability.
        """

        return self._seedos_sandbox_submit(
            request,
            category="CONNECT",
            target=target,
            metadata=metadata,
        )

    def seedos_review(
        self,
        request,
        target=None,
        metadata=None,
    ):
        """
        Request a review of a capability, system, proposal,
        or development path.
        """

        return self._seedos_sandbox_submit(
            request,
            category="REVIEW",
            target=target,
            metadata=metadata,
        )

    def _seedos_sandbox_system_lookup(
        self,
        name,
    ):
        """
        Resolve a known system from the local registry-backed
        developer map.
        """

        if name is None:
            return None

        key = str(
            name
        ).strip()

        if not key:
            return None

        systems = getattr(
            self,
            "_seedos_system_index",
            {},
        )

        if key in systems:
            return dict(
                systems[key]
            )

        lowered = key.lower()

        for system_name, descriptor in systems.items():

            if str(
                system_name
            ).lower() == lowered:

                return dict(
                    descriptor
                )

        return None

    def _seedos_sandbox_capability_lookup(
        self,
        name,
    ):
        """
        Resolve a known capability from the registry-backed
        developer map.
        """

        if name is None:
            return None

        key = str(
            name
        ).strip()

        if not key:
            return None

        capabilities = getattr(
            self,
            "_seedos_capability_index",
            {},
        )

        if key in capabilities:
            return dict(
                capabilities[key]
            )

        lowered = key.lower()

        for capability_name, descriptor in (
            capabilities.items()
        ):

            if str(
                capability_name
            ).lower() == lowered:

                return dict(
                    descriptor
                )

        return None

    def seedos_lookup(
        self,
        name,
    ):
        """
        Developer-facing registry lookup.

        Returns system and capability information without
        instantiation or execution.
        """

        system = (
            self._seedos_sandbox_system_lookup(
                name
            )
        )

        capability = (
            self._seedos_sandbox_capability_lookup(
                name
            )
        )

        return {
            "name":
                name,

            "system":
                system,

            "capability":
                capability,

            "found":
                system is not None
                or capability is not None,
        }

    def seedos_sandbox_snapshot(self):
        """
        Return the complete developer sandbox state.
        """

        return {
            "initialized":
                bool(
                    getattr(
                        self,
                        "_seedos_sandbox_initialized",
                        False,
                    )
                ),

            "session_id":
                getattr(
                    self,
                    "_seedos_sandbox_session_id",
                    None,
                ),

            "mode":
                getattr(
                    self,
                    "_seedos_sandbox_mode",
                    "observe",
                ),

            "capabilities":
                dict(
                    getattr(
                        self,
                        "_seedos_sandbox_capabilities",
                        {},
                    )
                ),

            "pending":
                len(
                    getattr(
                        self,
                        "_seedos_sandbox_pending",
                        {},
                    )
                ),

            "results":
                len(
                    getattr(
                        self,
                        "_seedos_sandbox_results",
                        [],
                    )
                ),

            "history":
                len(
                    getattr(
                        self,
                        "_seedos_sandbox_history",
                        [],
                    )
                ),

            "registry":
                self._seedos_registry_growth_snapshot(),

            "growth":
                self._seedos_growth_status(),
        }

    def seedos_sandbox_clear_session(
        self,
    ):
        """
        Start a new sandbox session without deleting SEED
        learning, registry, or runtime state.
        """

        old_session = getattr(
            self,
            "_seedos_sandbox_session_id",
            None,
        )

        self._seedos_sandbox_session_id = (
            "SANDBOX.%s"
            % uuid.uuid4().hex[:16]
        )

        self._seedos_sandbox_pending = {}

        self._seedos_sandbox_record(
            "session_reset",
            {
                "previous_session":
                    old_session,

                "new_session":
                    self._seedos_sandbox_session_id,
            },
        )

        return {
            "status":
                "reset",

            "session_id":
                self._seedos_sandbox_session_id,
        }

    def seedos_sandbox_set_mode(
        self,
        mode,
    ):
        """
        Change developer observation mode.

        Modes are interface states only and do not alter
        command authority.
        """

        allowed_modes = {
            "observe",
            "teach",
            "develop",
            "inspect",
            "review",
            "test",
        }

        requested = str(
            mode
        ).strip().lower()

        if requested not in allowed_modes:

            return {
                "status":
                    "rejected",

                "reason":
                    "invalid_mode",

                "allowed":
                    sorted(
                        allowed_modes
                    ),
            }

        self._seedos_sandbox_mode = requested

        self._seedos_sandbox_record(
            "mode_changed",
            {
                "mode":
                    requested,
            },
        )

        return {
            "status":
                "updated",

            "mode":
                requested,
        }

    def _seedos_sandbox_fathud_snapshot(
        self,
    ):
        """
        Return FATHUD state as an observer/interface.

        FATHUD does not receive execution authority here.
        """

        fathud = getattr(
            self,
            "fathud",
            None,
        )

        if fathud is None:
            fathud = getattr(
                self,
                "fathud_adapter",
                None,
            )

        if fathud is None:
            return {
                "available":
                    False,

                "authority":
                    "QbitDialer",

                "execution":
                    False,
            }

        snapshot = {
            "available":
                True,

            "authority":
                "QbitDialer",

            "execution":
                False,

            "interface":
                "FATHUD",
        }

        for attribute in (
            "running",
            "connected",
            "ws_port",
            "http_port",
            "status",
        ):

            try:

                value = getattr(
                    fathud,
                    attribute,
                )

                snapshot[
                    attribute
                ] = value

            except Exception:
                pass

        return snapshot

    def seedos_developer_map(
        self,
    ):
        """
        Unified developer map.

        This is intended to become the information surface
        behind the future SEED OS developer interface.
        """

        return {
            "operating_system":
                "SEED OS",

            "sandbox":
                self.seedos_sandbox_snapshot(),

            "registry":
                self._seedos_registry_growth_snapshot(),

            "fathud":
                self._seedos_sandbox_fathud_snapshot(),

            "qbit_dialer":
                {
                    "available":
                        getattr(
                            self,
                            "qbit_dialer",
                            None,
                        )
                        is not None,

                    "authority":
                        "QbitDialer",

                    "command_admission":
                        "submit_command",
                },

            "qbit_queue_loop":
                {
                    "available":
                        getattr(
                            self,
                            "qbit_queue_loop",
                            getattr(
                                self,
                                "qbit_queue",
                                None,
                            ),
                        )
                        is not None,

                    "authority":
                        "QbitQueueLoop",

                    "role":
                        "execution_transport",
                },

            "oracle":
                {
                    "available":
                        getattr(
                            self,
                            "oracle",
                            getattr(
                                self,
                                "oracle_loop",
                                None,
                            ),
                        )
                        is not None,

                    "role":
                        "observer_governance",
                },

            "dynamic_systems":
                list(
                    getattr(
                        self,
                        "_seedos_system_index",
                        {},
                    ).keys()
                ),
        }






    # ==========================================================
    # SECTION 14 — SEED OS DEVELOPER WORKSPACE
    #
    # PURPOSE
    # -------
    # Provide the creator/developer with one persistent workspace
    # for teaching, suggesting, inspecting, connecting, testing,
    # reviewing, and growing SEED.
    #
    # DEVELOPER SEMANTICS
    # -------------------
    # Developer input is KNOWLEDGE / SUGGESTION / PROPOSAL DATA.
    #
    # It is NOT:
    #     - direct command execution
    #     - direct Qbit construction
    #     - direct queue insertion
    #     - direct handler invocation
    #     - second command authority
    #
    # COGNITIVE PATH
    # --------------
    #
    #     CREATOR / DEVELOPER
    #             |
    #             v
    #     Developer Workspace
    #             |
    #             v
    #     SEED_INPUT / DEVELOPMENT_PROPOSAL
    #             |
    #             v
    #     Qbit / cognition pipeline
    #             |
    #             v
    #     ComputeBrain
    #             |
    #             v
    #     ThoughtPacket
    #             |
    #             v
    #     TransformerBrain
    #             |
    #             v
    #     CognitiveResult
    #             |
    #             v
    #     IntentEngine
    #             |
    #             v
    #     ActionEngine
    #             |
    #             v
    #     QbitDialer
    #             |
    #             v
    #     submit_command()
    #             |
    #             v
    #     QbitQueueLoop
    #
    # KNOWLEDGE GROWTH
    # ----------------
    #
    # Human knowledge, developer teaching, SEED system knowledge,
    # SDK knowledge, MCP capability knowledge, AI-team knowledge,
    # provider knowledge, and problem-solving patterns are stored
    # as development/cognitive data first.
    #
    # They may later become capabilities through:
    #
    #     Section 15  Capability / Adapter Builder
    #     Section 16  Sandboxed Validation
    #     Section 17  Controlled Promotion
    #     Section 18  Dynamic Capability Layer
    #
    # AUTHORITY
    # ---------
    # QbitDialer = command authority
    # QbitQueueLoop = transport/execution authority
    # EventBus = shared transport
    # TrackSystem = tracking authority
    # Oracle = observer/governance
    # FATHUD = observer/developer interface
    # DEVHUD = developer workspace
    #
    # ==========================================================


    def _initialize_seedos_developer_workspace(self):

        if getattr(
            self,
            "_seedos_workspace_initialized",
            False,
        ):
            return True

        self._seedos_workspace_initialized = True

        self._seedos_workspace_mode = "SUGGEST"

        self._seedos_workspace_modes = [
            "TEACH",
            "SUGGEST",
            "INSPECT",
            "CONNECT",
            "DEVELOP",
            "TEST",
            "REVIEW",
            "GROW",
        ]

        self._seedos_workspace_selected_system = None
        self._seedos_workspace_selected_capability = None

        self._seedos_workspace_history = []

        self._seedos_workspace_results = []

        self._seedos_workspace_input_history = []

        self._seedos_workspace_session_id = (
            f"DEV-{uuid.uuid4().hex[:12].upper()}"
        )

        self._seedos_workspace_learning_state = {
            "inputs": 0,
            "teaching_events": 0,
            "suggestions": 0,
            "inspections": 0,
            "connections": 0,
            "development_events": 0,
            "tests": 0,
            "reviews": 0,
            "growth_requests": 0,
            "last_input": None,
            "last_result": None,
        }

        self._seedos_workspace_runtime_state = {
            "event_bus": False,
            "qbit_dialer": False,
            "qbit_queue_loop": False,
            "track_system": False,
            "oracle": False,
            "fathud": False,
            "module_registry": False,
            "option_registry": False,
            "memory": False,
            "mcp": False,
            "sdk": False,
        }

        self._seedos_workspace_refresh_runtime_state()

        self.logger.info(
            "[DEVHUD] SEED OS Developer Workspace initialized | "
            "session=%s",
            self._seedos_workspace_session_id,
        )

        return True


    def _seedos_workspace_refresh_runtime_state(self):
        """
        Refresh developer-visible runtime references.

        This is observation only.
        """

        state = getattr(
            self,
            "_seedos_workspace_runtime_state",
            None,
        )

        if not isinstance(state, dict):
            state = {}
            self._seedos_workspace_runtime_state = state

        state["event_bus"] = (
            getattr(
                self,
                "event_bus",
                None,
            )
            is not None
        )

        state["qbit_dialer"] = (
            getattr(
                self,
                "qbit_dialer",
                None,
            )
            is not None
        )

        state["qbit_queue_loop"] = (
            getattr(
                self,
                "qbit_queue_loop",
                None,
            )
            is not None
            or getattr(
                self,
                "qbit_queue",
                None,
            )
            is not None
        )

        state["track_system"] = (
            getattr(
                self,
                "track_system",
                None,
            )
            is not None
        )

        state["oracle"] = (
            getattr(
                self,
                "oracle",
                None,
            )
            is not None
        )

        state["fathud"] = (
            getattr(
                self,
                "fathud",
                None,
            )
            is not None
            or getattr(
                self,
                "fathud_adapter",
                None,
            )
            is not None
        )

        state["module_registry"] = (
            getattr(
                self,
                "module_registry",
                None,
            )
            is not None
        )

        state["option_registry"] = (
            getattr(
                self,
                "option_registry",
                None,
            )
            is not None
        )

        state["memory"] = (
            getattr(
                self,
                "memory_crystallizer",
                None,
            )
            is not None
        )

        state["mcp"] = bool(
            getattr(
                self,
                "_mcp_capability_state",
                None,
            )
        )

        state["sdk"] = bool(
            getattr(
                self,
                "_sdk_capability_state",
                None,
            )
        )

        return dict(state)


    def _build_seedos_developer_workspace(self):
        """
        Build the visible developer workspace.

        The workspace delegates actual SEED development semantics to
        the Section 13 sandbox and Section 12 growth fabric.
        """

        self._initialize_seedos_developer_workspace()

        if not getattr(
            self,
            "dynamic_container",
            None,
        ):
            return None

        workspace = ttk.Frame(
            self.dynamic_container
        )

        workspace.grid(
            row=0,
            column=0,
            sticky="nsew",
        )

        workspace.grid_rowconfigure(
            2,
            weight=1,
        )

        workspace.grid_columnconfigure(
            0,
            weight=1,
        )

        self._seedos_workspace_frame = workspace

        self._build_seedos_workspace_header(
            workspace
        )

        self._build_seedos_workspace_input(
            workspace
        )

        self._build_seedos_workspace_actions(
            workspace
        )

        self._build_seedos_registry_panel(
            workspace
        )

        self._build_seedos_sandbox_panel(
            workspace
        )

        self._build_seedos_learning_panel(
            workspace
        )

        self._build_seedos_runtime_panel(
            workspace
        )

        self._build_seedos_development_history(
            workspace
        )

        self._seedos_workspace_refresh()

        return workspace


    def _build_seedos_workspace_header(
        self,
        parent,
    ):
        header = ttk.Frame(
            parent
        )

        header.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=6,
            pady=4,
        )

        header.grid_columnconfigure(
            1,
            weight=1,
        )

        ttk.Label(
            header,
            text="SEED OS — DEVELOPER WORKSPACE",
            font=(
                "Consolas",
                11,
                "bold",
            ),
        ).grid(
            row=0,
            column=0,
            sticky="w",
        )

        self._seedos_workspace_status_var = (
            tk.StringVar(
                value="CREATOR / SUGGESTION MODE"
            )
        )

        ttk.Label(
            header,
            textvariable=(
                self._seedos_workspace_status_var
            ),
        ).grid(
            row=0,
            column=1,
            sticky="e",
        )


    def _build_seedos_workspace_input(
        self,
        parent,
    ):
        input_frame = ttk.LabelFrame(
            parent,
            text="Teach / Suggest to SEED",
        )

        input_frame.grid(
            row=1,
            column=0,
            sticky="ew",
            padx=6,
            pady=4,
        )

        input_frame.grid_columnconfigure(
            1,
            weight=1,
        )

        ttk.Label(
            input_frame,
            text="Mode",
        ).grid(
            row=0,
            column=0,
            padx=4,
            pady=4,
            sticky="w",
        )

        self._seedos_workspace_mode_var = (
            tk.StringVar(
                value="SUGGEST"
            )
        )

        mode_box = ttk.Combobox(
            input_frame,
            textvariable=(
                self._seedos_workspace_mode_var
            ),
            values=(
                self._seedos_workspace_modes
            ),
            state="readonly",
            width=14,
        )

        mode_box.grid(
            row=0,
            column=1,
            sticky="w",
            padx=4,
            pady=4,
        )

        mode_box.bind(
            "<<ComboboxSelected>>",
            self._seedos_workspace_mode_changed,
        )

        ttk.Label(
            input_frame,
            text="Developer input",
        ).grid(
            row=1,
            column=0,
            padx=4,
            pady=4,
            sticky="nw",
        )

        self._seedos_workspace_input_var = (
            tk.StringVar()
        )

        self._seedos_workspace_input = ttk.Entry(
            input_frame,
            textvariable=(
                self._seedos_workspace_input_var
            ),
        )

        self._seedos_workspace_input.grid(
            row=1,
            column=1,
            sticky="ew",
            padx=4,
            pady=4,
        )

        self._seedos_workspace_input.bind(
            "<Return>",
            self._seedos_workspace_submit,
        )


    def _build_seedos_workspace_actions(
        self,
        parent,
    ):
        actions = ttk.Frame(
            parent
        )

        actions.grid(
            row=2,
            column=0,
            sticky="ew",
            padx=6,
            pady=4,
        )

        buttons = (
            (
                "TEACH",
                self._seedos_workspace_teach,
            ),
            (
                "SUGGEST",
                self._seedos_workspace_suggest,
            ),
            (
                "INSPECT",
                self._seedos_workspace_inspect,
            ),
            (
                "CONNECT",
                self._seedos_workspace_connect,
            ),
            (
                "TEST",
                self._seedos_workspace_test,
            ),
            (
                "REVIEW",
                self._seedos_workspace_review,
            ),
            (
                "GROW",
                self._seedos_workspace_grow,
            ),
        )

        for index, (
            label,
            callback,
        ) in enumerate(buttons):

            ttk.Button(
                actions,
                text=label,
                command=callback,
            ).grid(
                row=0,
                column=index,
                padx=2,
                pady=2,
                sticky="ew",
            )

            actions.grid_columnconfigure(
                index,
                weight=1,
            )


    def _build_seedos_registry_panel(
        self,
        parent,
    ):
        frame = ttk.LabelFrame(
            parent,
            text="SEED OS Systems / Capabilities",
        )

        frame.grid(
            row=3,
            column=0,
            sticky="nsew",
            padx=6,
            pady=4,
        )

        frame.grid_rowconfigure(
            0,
            weight=1,
        )

        frame.grid_columnconfigure(
            0,
            weight=1,
        )

        self._seedos_workspace_registry_tree = (
            ttk.Treeview(
                frame,
                columns=(
                    "type",
                    "status",
                    "authority",
                    "source",
                ),
                show="tree headings",
                height=8,
            )
        )

        self._seedos_workspace_registry_tree.heading(
            "#0",
            text="System / Capability",
        )

        self._seedos_workspace_registry_tree.heading(
            "type",
            text="Type",
        )

        self._seedos_workspace_registry_tree.heading(
            "status",
            text="Status",
        )

        self._seedos_workspace_registry_tree.heading(
            "authority",
            text="Authority",
        )

        self._seedos_workspace_registry_tree.heading(
            "source",
            text="Source",
        )

        self._seedos_workspace_registry_tree.grid(
            row=0,
            column=0,
            sticky="nsew",
        )

        self._seedos_workspace_registry_tree.bind(
            "<<TreeviewSelect>>",
            self._seedos_workspace_registry_selected,
        )


    def _build_seedos_sandbox_panel(
        self,
        parent,
    ):
        frame = ttk.LabelFrame(
            parent,
            text="Developer Sandbox",
        )

        frame.grid(
            row=4,
            column=0,
            sticky="nsew",
            padx=6,
            pady=4,
        )

        frame.grid_rowconfigure(
            0,
            weight=1,
        )

        frame.grid_columnconfigure(
            0,
            weight=1,
        )

        self._seedos_workspace_sandbox_output = (
            ScrolledText(
                frame,
                height=8,
                wrap="word",
            )
        )

        self._seedos_workspace_sandbox_output.grid(
            row=0,
            column=0,
            sticky="nsew",
        )


    def _build_seedos_learning_panel(
        self,
        parent,
    ):
        frame = ttk.LabelFrame(
            parent,
            text="Learning / Knowledge Growth",
        )

        frame.grid(
            row=5,
            column=0,
            sticky="ew",
            padx=6,
            pady=4,
        )

        self._seedos_workspace_learning_var = (
            tk.StringVar(
                value="Learning state unavailable"
            )
        )

        ttk.Label(
            frame,
            textvariable=(
                self._seedos_workspace_learning_var
            ),
            justify="left",
        ).grid(
            row=0,
            column=0,
            sticky="w",
            padx=4,
            pady=4,
        )


    def _build_seedos_runtime_panel(
        self,
        parent,
    ):
        frame = ttk.LabelFrame(
            parent,
            text="SEED Runtime Connections",
        )

        frame.grid(
            row=6,
            column=0,
            sticky="ew",
            padx=6,
            pady=4,
        )

        self._seedos_workspace_runtime_var = (
            tk.StringVar(
                value="Runtime state unavailable"
            )
        )

        ttk.Label(
            frame,
            textvariable=(
                self._seedos_workspace_runtime_var
            ),
            justify="left",
        ).grid(
            row=0,
            column=0,
            sticky="w",
            padx=4,
            pady=4,
        )


    def _build_seedos_development_history(
        self,
        parent,
    ):
        frame = ttk.LabelFrame(
            parent,
            text="Development Lineage",
        )

        frame.grid(
            row=7,
            column=0,
            sticky="ew",
            padx=6,
            pady=4,
        )

        frame.grid_columnconfigure(
            0,
            weight=1,
        )

        self._seedos_workspace_history_var = (
            tk.StringVar(
                value="No development activity yet."
            )
        )

        ttk.Label(
            frame,
            textvariable=(
                self._seedos_workspace_history_var
            ),
            justify="left",
        ).grid(
            row=0,
            column=0,
            sticky="w",
            padx=4,
            pady=4,
        )


    def _seedos_workspace_mode_changed(
        self,
        event=None,
    ):
        mode = (
            self._seedos_workspace_mode_var.get()
            .strip()
            .upper()
        )

        if mode not in getattr(
            self,
            "_seedos_workspace_modes",
            [],
        ):
            mode = "SUGGEST"

        self._seedos_workspace_mode = mode

        if hasattr(
            self,
            "_seedos_workspace_status_var",
        ):
            self._seedos_workspace_status_var.set(
                f"CREATOR / {mode} MODE"
            )

        return mode


    def _seedos_workspace_submit(
        self,
        event=None,
    ):
        text = (
            self._seedos_workspace_input_var.get()
            .strip()
        )

        if not text:
            return None

        mode = self._seedos_workspace_mode_changed()

        self._seedos_workspace_input_var.set("")

        self._seedos_workspace_input_history.append(
            {
                "timestamp": time.time(),
                "mode": mode,
                "input": text,
                "session": (
                    self._seedos_workspace_session_id
                ),
            }
        )

        self._seedos_workspace_learning_state[
            "inputs"
        ] += 1

        result = self._seedos_workspace_dispatch(
            mode,
            text,
        )

        self._seedos_workspace_results.append(
            result
        )

        self._seedos_workspace_refresh()

        return result


    def _seedos_workspace_dispatch(
        self,
        mode,
        text,
    ):

        mode = str(
            mode or "SUGGEST"
        ).strip().upper()

        if mode == "TEACH":
            return self.seedos_teach(
                text
            )

        if mode == "INSPECT":
            return self.seedos_inspect(
                text
            )

        if mode == "CONNECT":
            return self.seedos_connect(
                text
            )

        if mode == "DEVELOP":
            return self._seedos_workspace_develop(
                text
            )

        if mode == "TEST":
            return self.seedos_test(
                text
            )

        if mode == "REVIEW":
            return self.seedos_review(
                text
            )

        if mode == "GROW":
            return self.seedos_grow(
                text
            )

        return self.seedos_suggest(
            text
        )


    def _seedos_workspace_teach(
        self,
    ):
        self._seedos_workspace_mode_var.set(
            "TEACH"
        )

        self._seedos_workspace_mode_changed()

        return self._seedos_workspace_submit()


    def _seedos_workspace_suggest(
        self,
    ):
        self._seedos_workspace_mode_var.set(
            "SUGGEST"
        )

        self._seedos_workspace_mode_changed()

        return self._seedos_workspace_submit()


    def _seedos_workspace_inspect(
        self,
    ):
        self._seedos_workspace_mode_var.set(
            "INSPECT"
        )

        self._seedos_workspace_mode_changed()

        return self._seedos_workspace_submit()


    def _seedos_workspace_connect(
        self,
    ):
        self._seedos_workspace_mode_var.set(
            "CONNECT"
        )

        self._seedos_workspace_mode_changed()

        return self._seedos_workspace_submit()


    def _seedos_workspace_test(
        self,
    ):
        self._seedos_workspace_mode_var.set(
            "TEST"
        )

        self._seedos_workspace_mode_changed()

        return self._seedos_workspace_submit()


    def _seedos_workspace_review(
        self,
    ):
        self._seedos_workspace_mode_var.set(
            "REVIEW"
        )

        self._seedos_workspace_mode_changed()

        return self._seedos_workspace_submit()


    def _seedos_workspace_grow(
        self,
    ):
        self._seedos_workspace_mode_var.set(
            "GROW"
        )

        self._seedos_workspace_mode_changed()

        return self._seedos_workspace_submit()


    def _seedos_workspace_develop(
        self,
        text,
    ):

        proposal = {
            "type": "DEVELOPMENT_PROPOSAL",
            "input": str(text),
            "source": "DEVHUD",
            "developer": True,
            "session_id": (
                self._seedos_workspace_session_id
            ),
            "timestamp": time.time(),
            "target": (
                self._seedos_workspace_selected_system
            ),
        }

        self._seedos_workspace_learning_state[
            "development_events"
        ] += 1

        self._seedos_workspace_history.append(
            proposal
        )

        try:
            if hasattr(
                self,
                "_seedos_sandbox_submit",
            ):
                result = self._seedos_sandbox_submit(
                    proposal
                )
            else:
                result = proposal

        except Exception as exc:
            result = {
                "status": "development_proposal_recorded",
                "error": str(exc),
                "proposal": proposal,
            }

        return result


    def _seedos_workspace_registry_selected(
        self,
        event=None,
    ):
        tree = getattr(
            self,
            "_seedos_workspace_registry_tree",
            None,
        )

        if tree is None:
            return None

        selection = tree.selection()

        if not selection:
            return None

        item_id = selection[0]

        values = tree.item(
            item_id
        )

        self._seedos_workspace_selected_system = (
            values.get(
                "text"
            )
        )

        item_values = values.get(
            "values",
            (),
        )

        if item_values:
            self._seedos_workspace_selected_capability = (
                item_values[0]
            )

        return {
            "system": (
                self._seedos_workspace_selected_system
            ),
            "values": item_values,
        }


    def _seedos_workspace_refresh_registry(
        self,
    ):
        tree = getattr(
            self,
            "_seedos_workspace_registry_tree",
            None,
        )

        if tree is None:
            return None

        for item in tree.get_children():
            tree.delete(item)

        systems = {}

        try:
            systems.update(
                getattr(
                    self,
                    "_seedos_dynamic_systems",
                    {},
                )
                or {}
            )
        except Exception:
            pass

        try:
            registry_map = (
                self.get_seed_os_registry_map()
            )

            if isinstance(
                registry_map,
                dict,
            ):
                registry_systems = (
                    registry_map.get(
                        "systems",
                        registry_map.get(
                            "modules",
                            {},
                        ),
                    )
                )

                if isinstance(
                    registry_systems,
                    dict,
                ):
                    systems.update(
                        registry_systems
                    )

        except Exception:
            pass

        for name, descriptor in systems.items():

            if not isinstance(
                descriptor,
                dict,
            ):
                descriptor = {
                    "value": descriptor
                }

            tree.insert(
                "",
                "end",
                text=str(name),
                values=(
                    descriptor.get(
                        "type",
                        "system",
                    ),
                    descriptor.get(
                        "status",
                        "KNOWN",
                    ),
                    descriptor.get(
                        "authority",
                        "SEED",
                    ),
                    descriptor.get(
                        "source",
                        "runtime",
                    ),
                ),
            )

        return len(
            tree.get_children()
        )


    def _seedos_workspace_refresh_learning(
        self,
    ):
        state = getattr(
            self,
            "_seedos_workspace_learning_state",
            {},
        )

        if not isinstance(
            state,
            dict,
        ):
            return

        text = (
            f"Inputs: {state.get('inputs', 0)}    "
            f"Teaching: {state.get('teaching_events', 0)}    "
            f"Suggestions: {state.get('suggestions', 0)}\n"
            f"Inspections: {state.get('inspections', 0)}    "
            f"Connections: {state.get('connections', 0)}    "
            f"Development: {state.get('development_events', 0)}\n"
            f"Tests: {state.get('tests', 0)}    "
            f"Reviews: {state.get('reviews', 0)}    "
            f"Growth: {state.get('growth_requests', 0)}"
        )

        if hasattr(
            self,
            "_seedos_workspace_learning_var",
        ):
            self._seedos_workspace_learning_var.set(
                text
            )

        return text


    def _seedos_workspace_refresh_runtime(
        self,
    ):
        state = (
            self._seedos_workspace_refresh_runtime_state()
        )

        connected = [
            name
            for name, value in state.items()
            if value
        ]

        unavailable = [
            name
            for name, value in state.items()
            if not value
        ]

        text = (
            "CONNECTED:\n"
            + (
                ", ".join(connected)
                if connected
                else "none"
            )
            + "\n\n"
            "NOT CURRENTLY BOUND:\n"
            + (
                ", ".join(unavailable)
                if unavailable
                else "none"
            )
        )

        if hasattr(
            self,
            "_seedos_workspace_runtime_var",
        ):
            self._seedos_workspace_runtime_var.set(
                text
            )

        return state


    def _seedos_workspace_refresh_history(
        self,
    ):
        history = getattr(
            self,
            "_seedos_workspace_history",
            [],
        )

        if not history:
            text = "No development activity yet."

        else:
            recent = history[-8:]

            lines = []

            for item in recent:

                if not isinstance(
                    item,
                    dict,
                ):
                    lines.append(
                        str(item)
                    )
                    continue

                timestamp = item.get(
                    "timestamp",
                    0,
                )

                try:
                    stamp = time.strftime(
                        "%H:%M:%S",
                        time.localtime(
                            timestamp
                        ),
                    )
                except Exception:
                    stamp = "UNKNOWN"

                kind = item.get(
                    "type",
                    item.get(
                        "category",
                        "EVENT",
                    ),
                )

                value = item.get(
                    "input",
                    item.get(
                        "suggestion",
                        item.get(
                            "target",
                            "",
                        ),
                    ),
                )

                lines.append(
                    f"[{stamp}] {kind}: {value}"
                )

            text = "\n".join(
                lines
            )

        if hasattr(
            self,
            "_seedos_workspace_history_var",
        ):
            self._seedos_workspace_history_var.set(
                text
            )

        return text


    def _seedos_workspace_refresh_sandbox(
        self,
    ):
        output = getattr(
            self,
            "_seedos_workspace_sandbox_output",
            None,
        )

        if output is None:
            return

        results = getattr(
            self,
            "_seedos_workspace_results",
            [],
        )

        if not results:
            return

        result = results[-1]

        try:
            rendered = json.dumps(
                result,
                indent=2,
                default=str,
            )
        except Exception:
            rendered = str(
                result
            )

        output.configure(
            state="normal"
        )

        output.delete(
            "1.0",
            tk.END,
        )

        output.insert(
            tk.END,
            rendered,
        )

        output.see(
            tk.END
        )

        output.configure(
            state="disabled"
        )


    def _seedos_workspace_refresh(
        self,
    ):

        try:
            self._seedos_workspace_refresh_runtime()
        except Exception:
            self.logger.debug(
                "[DEVHUD] Workspace runtime refresh failed",
                exc_info=True,
            )

        try:
            self._seedos_workspace_refresh_registry()
        except Exception:
            self.logger.debug(
                "[DEVHUD] Workspace registry refresh failed",
                exc_info=True,
            )

        try:
            self._seedos_workspace_refresh_learning()
        except Exception:
            self.logger.debug(
                "[DEVHUD] Workspace learning refresh failed",
                exc_info=True,
            )

        try:
            self._seedos_workspace_refresh_history()
        except Exception:
            self.logger.debug(
                "[DEVHUD] Workspace history refresh failed",
                exc_info=True,
            )

        try:
            self._seedos_workspace_refresh_sandbox()
        except Exception:
            self.logger.debug(
                "[DEVHUD] Workspace sandbox refresh failed",
                exc_info=True,
            )

        return True


    def _seedos_workspace_inspect_selected(
        self,
    ):
        target = (
            self._seedos_workspace_selected_system
        )

        if not target:
            return {
                "status": "no_selection"
            }

        return self.seedos_inspect(
            target
        )


    def _seedos_workspace_connect_selected(
        self,
    ):
        target = (
            self._seedos_workspace_selected_system
        )

        if not target:
            return {
                "status": "no_selection"
            }

        return self.seedos_connect(
            target
        )


    def _seedos_workspace_status(
        self,
    ):

        self._seedos_workspace_refresh_runtime_state()

        return {
            "status": "READY",
            "workspace": "SEED_OS_DEVELOPER_WORKSPACE",
            "session_id": (
                self._seedos_workspace_session_id
            ),
            "mode": (
                self._seedos_workspace_mode
            ),
            "runtime": dict(
                self._seedos_workspace_runtime_state
            ),
            "learning": dict(
                self._seedos_workspace_learning_state
            ),
            "selected_system": (
                self._seedos_workspace_selected_system
            ),
            "selected_capability": (
                self._seedos_workspace_selected_capability
            ),
            "history_count": len(
                self._seedos_workspace_history
            ),
            "result_count": len(
                self._seedos_workspace_results
            ),
            "authority": {
                "developer": "INPUT / KNOWLEDGE / PROPOSAL",
                "qbit_dialer": "COMMAND",
                "qbit_queue_loop": "EXECUTION / TRANSPORT",
                "event_bus": "SHARED TRANSPORT",
                "track_system": "TRACKING",
                "oracle": "OBSERVATION / GOVERNANCE",
                "fathud": "OBSERVATION / INTERFACE",
            },
        }


    def seedos_workspace_open(
        self,
    ):
        self._initialize_seedos_developer_workspace()

        if not getattr(
            self,
            "_seedos_workspace_frame",
            None,
        ):
            return self._build_seedos_developer_workspace()

        try:
            self._seedos_workspace_frame.tkraise()
        except Exception:
            pass

        self._seedos_workspace_refresh()

        return self._seedos_workspace_frame


    def seedos_workspace_teach(
        self,
        knowledge,
    ):

        self._initialize_seedos_developer_workspace()

        self._seedos_workspace_mode = "TEACH"

        result = self.seedos_teach(
            knowledge
        )

        self._seedos_workspace_learning_state[
            "teaching_events"
        ] += 1

        self._seedos_workspace_history.append(
            {
                "type": "TEACH",
                "input": knowledge,
                "timestamp": time.time(),
                "session": (
                    self._seedos_workspace_session_id
                ),
            }
        )

        self._seedos_workspace_results.append(
            result
        )

        self._seedos_workspace_refresh()

        return result


    def seedos_workspace_suggest(
        self,
        suggestion,
    ):

        self._initialize_seedos_developer_workspace()

        self._seedos_workspace_mode = "SUGGEST"

        result = self.seedos_suggest(
            suggestion
        )

        self._seedos_workspace_learning_state[
            "suggestions"
        ] += 1

        self._seedos_workspace_history.append(
            {
                "type": "SUGGEST",
                "input": suggestion,
                "timestamp": time.time(),
                "session": (
                    self._seedos_workspace_session_id
                ),
            }
        )

        self._seedos_workspace_results.append(
            result
        )

        self._seedos_workspace_refresh()

        return result


    def seedos_workspace_grow(
        self,
        proposal,
    ):
        self._initialize_seedos_developer_workspace()

        self._seedos_workspace_mode = "GROW"

        result = self.seedos_grow(
            proposal
        )

        self._seedos_workspace_learning_state[
            "growth_requests"
        ] += 1

        self._seedos_workspace_history.append(
            {
                "type": "GROW",
                "input": proposal,
                "timestamp": time.time(),
                "session": (
                    self._seedos_workspace_session_id
                ),
            }
        )

        self._seedos_workspace_results.append(
            result
        )

        self._seedos_workspace_refresh()

        return result


    def get_seedos_workspace_status(
        self,
    ):
        """
        Public status API for DEVHUD/FATHUD/Oracle observers.
        """

        return self._seedos_workspace_status()


    # ==========================================================
    # DEVELOPER KNOWLEDGE BRIDGE
    #
    # This is intentionally generic.
    #
    # The workspace can accept:
    #
    #     human knowledge
    #     problem-solving examples
    #     engineering concepts
    #     AI concepts
    #     LLM concepts
    #     SEED architecture knowledge
    #     SDK knowledge
    #     MCP knowledge
    #     provider knowledge
    #     AI-team knowledge
    #     ChatDev knowledge
    #     research observations
    #     creative ideas
    #
    # The actual knowledge source remains external to this UI.
    #
    # ==========================================================


    def _seedos_workspace_knowledge_descriptor(
        self,
        knowledge,
    ):
        if isinstance(
            knowledge,
            dict,
        ):
            content = knowledge.get(
                "content",
                knowledge.get(
                    "text",
                    knowledge.get(
                        "input",
                        knowledge,
                    ),
                ),
            )

            category = knowledge.get(
                "category",
                "human_knowledge",
            )

            source = knowledge.get(
                "source",
                "DEVELOPER",
            )

        else:
            content = str(
                knowledge
            )

            category = (
                "human_knowledge"
            )

            source = "DEVELOPER"

        return {
            "type": "KNOWLEDGE_INPUT",
            "content": content,
            "category": category,
            "source": source,
            "developer": True,
            "session_id": (
                self._seedos_workspace_session_id
            ),
            "timestamp": time.time(),
        }


    def seedos_workspace_load_knowledge(
        self,
        knowledge,
    ):

        descriptor = (
            self._seedos_workspace_knowledge_descriptor(
                knowledge
            )
        )

        self._seedos_workspace_history.append(
            descriptor
        )

        self._seedos_workspace_learning_state[
            "inputs"
        ] += 1

        try:
            if hasattr(
                self,
                "_emit_learning_input",
            ):
                result = self._emit_learning_input(
                    descriptor
                )

            elif hasattr(
                self,
                "_unified_growth_input",
            ):
                result = self._unified_growth_input(
                    descriptor
                )

            elif hasattr(
                self,
                "_emit_hud_event",
            ):
                result = self._emit_hud_event(
                    "SEED_INPUT",
                    descriptor,
                )

            elif getattr(
                self,
                "event_bus",
                None,
            ) is not None:

                self.event_bus.emit(
                    "SEED_INPUT",
                    descriptor,
                )

                result = {
                    "status": "knowledge_submitted",
                    "transport": "SEED_INPUT",
                    "descriptor": descriptor,
                }

            else:
                result = {
                    "status": "knowledge_buffered",
                    "descriptor": descriptor,
                }

        except Exception as exc:
            result = {
                "status": "knowledge_submission_error",
                "error": str(exc),
                "descriptor": descriptor,
            }

        self._seedos_workspace_results.append(
            result
        )

        self._seedos_workspace_refresh()

        return result


    def seedos_workspace_status_text(
        self,
    ):

        status = (
            self._seedos_workspace_status()
        )

        runtime = status.get(
            "runtime",
            {},
        )

        learning = status.get(
            "learning",
            {},
        )

        return (
            "SEED OS DEVELOPER WORKSPACE\n"
            f"Session: {status.get('session_id')}\n"
            f"Mode: {status.get('mode')}\n\n"
            "RUNTIME\n"
            f"{json.dumps(runtime, indent=2, default=str)}\n\n"
            "LEARNING\n"
            f"{json.dumps(learning, indent=2, default=str)}"
        )


    # ==========================================================
    # OPTIONAL INITIALIZATION HOOK
    #
    # Add this call to the existing DEVHUD initialization path
    # AFTER Sections 12 and 13 are initialized and AFTER the
    # authoritative runtime references are bound.
    #
    # DO NOT call this at module import time.
    #
    # ==========================================================

    def _initialize_developer_workspace_bridge(
        self,
    ):
        try:
            self._initialize_seedos_developer_workspace()

            if getattr(
                self,
                "load_ui",
                True,
            ):
                self.seedos_workspace_open()

            return True

        except Exception as exc:
            self.logger.warning(
                "[DEVHUD] Developer Workspace initialization "
                "deferred: %s",
                exc,
            )

            return False

# ==========================================================================
# SECTION 14 — SEED OS DEVELOPER WORKSPACE
#
# PURPOSE:
# - Give the Creator one persistent development surface.
# - Allow the Creator to teach, suggest, inspect, connect, test, review,
#   and request growth without manually editing SEED core modules.
# - Route developer knowledge into SEED's existing cognitive pipeline.
# - Expose the existing SEED runtime registry and knowledge fabric.
# - Surface init_event.py AI knowledge-base context.
# - Keep Oracle observational.
# - Keep FATHUD observational.
# - Keep QbitDialer as command authority.
# - Keep QbitQueueLoop as execution/transport authority.
#
# AUTHORITY:
#     Creator
#          |
#          v
#     DEVHUD Developer Workspace
#          |
#          v
#     SEED_INPUT / DEVELOPMENT_PROPOSAL
#          |
#          v
#     ComputeBrain / TransformerBrain
#          |
#          v
#     IntentEngine / AnalyticsEngine
#          |
#          v
#     ActionEngine
#          |
#          v
#     QbitDialer
#          |
#          v
#     submit_command()
#          |
#          v
#     QbitQueueLoop
#
# NOTE:
# This section does not create another runtime.
# This section does not create another Qbit.
# This section does not create another EventBus.
# This section does not start MCP or install packages.
# ==========================================================================


    def _initialize_seedos_developer_workspace(self):
        """
        Initialize the Creator-facing SEED OS developer workspace.

        The workspace is an interface over the already-running SEED systems.
        It does not become a new authority or execution runtime.
        """

        if getattr(
            self,
            "_seedos_workspace_initialized",
            False,
        ):
            return

        self._seedos_workspace_initialized = True

        self._seedos_workspace_mode = "SUGGEST"

        self._seedos_workspace_history = getattr(
            self,
            "_seedos_workspace_history",
            [],
        )

        self._seedos_workspace_results = getattr(
            self,
            "_seedos_workspace_results",
            [],
        )

        self._seedos_workspace_selection = None

        self._seedos_workspace_knowledge = {
            "source": "SEED",
            "init_event": True,
            "runtime": {},
            "seed_systems": [],
            "ai_tools": {},
        }

        self._seedos_collect_init_event_knowledge()

        try:
            self._build_seedos_developer_workspace()
        except Exception as exc:
            self.logger.warning(
                "[DEVHUD] SEED OS Developer Workspace build deferred | error=%s",
                exc,
            )


    def _seedos_collect_init_event_knowledge(self):
        """
        Collect compatible knowledge exposed by SeedInitEvent.

        This is observation only.

        No SeedInitEvent instance is constructed.
        No runtime object is replaced.
        """

        knowledge = getattr(
            self,
            "_seedos_workspace_knowledge",
            {},
        )

        knowledge["runtime"] = {
            "qbit_dialer": getattr(
                self,
                "qbit_dialer",
                None,
            )
            is not None,
            "event_bus": getattr(
                self,
                "event_bus",
                None,
            )
            is not None,
            "registry": getattr(
                self,
                "registry",
                None,
            )
            is not None,
            "track_system": getattr(
                self,
                "track_system",
                None,
            )
            is not None,
            "intent_engine": getattr(
                self,
                "intent_engine",
                None,
            )
            is not None,
            "analytics_engine": getattr(
                self,
                "analytics_engine",
                None,
            )
            is not None,
            "memory_crystallizer": getattr(
                self,
                "memory_crystallizer",
                None,
            )
            is not None,
            "oracle": getattr(
                self,
                "oracle",
                None,
            )
            is not None,
            "heartbeat": getattr(
                self,
                "heartbeat",
                None,
            )
            is not None,
            "heartbeat_emitter": getattr(
                self,
                "heartbeat_emitter",
                None,
            )
            is not None,
            "qbit_queue_loop": getattr(
                self,
                "qbit_queue_loop",
                None,
            )
            is not None
            or getattr(
                self,
                "qbit_queue",
                None,
            )
            is not None,
        }

        # --------------------------------------------------------------
        # Read the authoritative initialization knowledge if it is
        # already exposed by an existing SeedInitEvent/runtime object.
        # --------------------------------------------------------------

        init_event = getattr(
            self,
            "seed_init_event",
            None,
        )

        if init_event is None:
            init_event = getattr(
                self,
                "init_event",
                None,
            )

        ai_base_kb = getattr(
            init_event,
            "ai_base_kb",
            None,
        )

        if isinstance(
            ai_base_kb,
            dict,
        ):
            self._seedos_workspace_knowledge[
                "init_event_kb_version"
            ] = ai_base_kb.get(
                "version"
            )

            seed_systems = ai_base_kb.get(
                "seed_systems",
                [],
            )

            if isinstance(
                seed_systems,
                (list, tuple, set),
            ):
                self._seedos_workspace_knowledge[
                    "seed_systems"
                ] = [
                    str(item)
                    for item in seed_systems
                ]

            ai_tools = ai_base_kb.get(
                "ai_tools",
                {},
            )

            if isinstance(
                ai_tools,
                dict,
            ):
                self._seedos_workspace_knowledge[
                    "ai_tools"
                ] = dict(
                    ai_tools
                )

        # --------------------------------------------------------------
        # Also inspect the module-level SeedInitEvent context when the
        # module is already imported. This does not instantiate anything.
        # --------------------------------------------------------------

        try:
            init_module = importlib.import_module(
                "seed.core.init.init_event"
            )
        except Exception:
            init_module = None

        if init_module is not None:

            module_context = getattr(
                init_module,
                "MODULE_CONTEXT",
                None,
            )

            if isinstance(
                module_context,
                dict,
            ):
                self._seedos_workspace_knowledge[
                    "module_context"
                ] = dict(
                    module_context
                )

            tool_status = getattr(
                init_module,
                "AI_TOOL_STATUS",
                None,
            )

            if isinstance(
                tool_status,
                dict,
            ):
                self._seedos_workspace_knowledge[
                    "ai_tools"
                ] = dict(
                    tool_status
                )


    def _build_seedos_developer_workspace(self):
        """
        Build the persistent Creator workspace.

        The workspace is deliberately lightweight and can operate even when
        optional UI components are unavailable.
        """

        if not getattr(
            self,
            "load_ui",
            True,
        ):
            return

        parent = getattr(
            self,
            "center_frame",
            None,
        )

        if parent is None:
            parent = getattr(
                self,
                "main_frame",
                None,
            )

        if parent is None:
            parent = getattr(
                self,
                "root",
                None,
            )

        if parent is None:
            return

        if getattr(
            self,
            "_seedos_workspace_frame",
            None,
        ) is not None:
            try:
                if self._seedos_workspace_frame.winfo_exists():
                    return
            except Exception:
                pass

        self._seedos_workspace_frame = ttk.Frame(
            parent
        )

        self._seedos_workspace_frame.grid(
            row=0,
            column=0,
            sticky="nsew",
            padx=6,
            pady=6,
        )

        try:
            parent.grid_rowconfigure(
                0,
                weight=1,
            )
            parent.grid_columnconfigure(
                0,
                weight=1,
            )
        except Exception:
            pass

        self._build_seedos_workspace_header()
        self._build_seedos_workspace_input()
        self._build_seedos_workspace_actions()
        self._build_seedos_registry_panel()
        self._build_seedos_sandbox_panel()
        self._build_seedos_learning_panel()
        self._build_seedos_runtime_panel()
        self._build_seedos_development_history()

        self._seedos_workspace_refresh()


    def _build_seedos_workspace_header(self):
        """Build workspace identity/status header."""

        frame = self._seedos_workspace_frame

        header = ttk.Frame(
            frame
        )

        header.grid(
            row=0,
            column=0,
            columnspan=3,
            sticky="ew",
            padx=4,
            pady=(4, 2),
        )

        try:
            header.grid_columnconfigure(
                1,
                weight=1,
            )
        except Exception:
            pass

        ttk.Label(
            header,
            text="SEED OS — DEVELOPER WORKSPACE",
        ).grid(
            row=0,
            column=0,
            sticky="w",
            padx=4,
        )

        self._seedos_workspace_status_var = tk.StringVar(
            value="READY"
        )

        ttk.Label(
            header,
            textvariable=self._seedos_workspace_status_var,
        ).grid(
            row=0,
            column=1,
            sticky="e",
            padx=4,
        )

        self._seedos_workspace_authority_var = tk.StringVar(
            value="Authority: QbitDialer"
        )

        ttk.Label(
            header,
            textvariable=self._seedos_workspace_authority_var,
        ).grid(
            row=0,
            column=2,
            sticky="e",
            padx=4,
        )


    def _build_seedos_workspace_input(self):
        """Build the single persistent Creator input surface."""

        frame = self._seedos_workspace_frame

        container = ttk.LabelFrame(
            frame,
            text="Creator → SEED",
        )

        container.grid(
            row=1,
            column=0,
            columnspan=3,
            sticky="ew",
            padx=4,
            pady=4,
        )

        try:
            container.grid_columnconfigure(
                1,
                weight=1,
            )
        except Exception:
            pass

        ttk.Label(
            container,
            text="Mode",
        ).grid(
            row=0,
            column=0,
            sticky="w",
            padx=4,
            pady=4,
        )

        self._seedos_workspace_mode_var = tk.StringVar(
            value="SUGGEST"
        )

        self._seedos_workspace_mode_box = ttk.Combobox(
            container,
            textvariable=self._seedos_workspace_mode_var,
            values=(
                "TEACH",
                "SUGGEST",
                "INSPECT",
                "CONNECT",
                "DEVELOP",
                "TEST",
                "REVIEW",
                "GROW",
            ),
            state="readonly",
            width=14,
        )

        self._seedos_workspace_mode_box.grid(
            row=0,
            column=1,
            sticky="w",
            padx=4,
            pady=4,
        )

        self._seedos_workspace_mode_box.bind(
            "<<ComboboxSelected>>",
            self._seedos_workspace_mode_changed,
        )

        ttk.Label(
            container,
            text="Input",
        ).grid(
            row=1,
            column=0,
            sticky="nw",
            padx=4,
            pady=4,
        )

        self._seedos_workspace_input = ScrolledText(
            container,
            height=5,
            wrap=tk.WORD,
        )

        self._seedos_workspace_input.grid(
            row=1,
            column=1,
            columnspan=2,
            sticky="ew",
            padx=4,
            pady=4,
        )

        self._seedos_workspace_input.bind(
            "<Control-Return>",
            self._seedos_workspace_submit,
        )


    def _build_seedos_workspace_actions(self):
        """Build explicit developer operations."""

        frame = self._seedos_workspace_frame

        actions = ttk.Frame(
            frame
        )

        actions.grid(
            row=2,
            column=0,
            columnspan=3,
            sticky="ew",
            padx=4,
            pady=4,
        )

        buttons = (
            (
                "SUBMIT",
                self._seedos_workspace_submit,
            ),
            (
                "TEACH",
                self._seedos_workspace_teach,
            ),
            (
                "SUGGEST",
                self._seedos_workspace_suggest,
            ),
            (
                "INSPECT",
                self._seedos_workspace_inspect,
            ),
            (
                "CONNECT",
                self._seedos_workspace_connect,
            ),
            (
                "TEST",
                self._seedos_workspace_test,
            ),
            (
                "REVIEW",
                self._seedos_workspace_review,
            ),
            (
                "GROW",
                self._seedos_workspace_grow,
            ),
        )

        for index, (
            label,
            callback,
        ) in enumerate(
            buttons
        ):
            ttk.Button(
                actions,
                text=label,
                command=callback,
            ).grid(
                row=0,
                column=index,
                padx=2,
                pady=2,
            )


    def _build_seedos_registry_panel(self):
        """Build runtime system/registry explorer."""

        frame = self._seedos_workspace_frame

        panel = ttk.LabelFrame(
            frame,
            text="SEED System Registry",
        )

        panel.grid(
            row=3,
            column=0,
            sticky="nsew",
            padx=4,
            pady=4,
        )

        self._seedos_workspace_registry_tree = ttk.Treeview(
            panel,
            columns=(
                "system",
                "kind",
                "state",
                "capabilities",
            ),
            show="headings",
            height=12,
        )

        headings = (
            ("system", "System"),
            ("kind", "Kind"),
            ("state", "State"),
            ("capabilities", "Capabilities"),
        )

        for column, title in headings:
            self._seedos_workspace_registry_tree.heading(
                column,
                text=title,
            )

        self._seedos_workspace_registry_tree.column(
            "system",
            width=150,
        )
        self._seedos_workspace_registry_tree.column(
            "kind",
            width=90,
        )
        self._seedos_workspace_registry_tree.column(
            "state",
            width=90,
        )
        self._seedos_workspace_registry_tree.column(
            "capabilities",
            width=220,
        )

        self._seedos_workspace_registry_tree.grid(
            row=0,
            column=0,
            sticky="nsew",
            padx=4,
            pady=4,
        )

        try:
            panel.grid_rowconfigure(
                0,
                weight=1,
            )
            panel.grid_columnconfigure(
                0,
                weight=1,
            )
        except Exception:
            pass

        self._seedos_workspace_registry_tree.bind(
            "<<TreeviewSelect>>",
            self._seedos_workspace_registry_selected,
        )

        ttk.Button(
            panel,
            text="REFRESH REGISTRY",
            command=self._seedos_workspace_refresh_registry,
        ).grid(
            row=1,
            column=0,
            sticky="ew",
            padx=4,
            pady=4,
        )


    def _build_seedos_sandbox_panel(self):
        """Build the development sandbox result surface."""

        frame = self._seedos_workspace_frame

        panel = ttk.LabelFrame(
            frame,
            text="Developer Sandbox",
        )

        panel.grid(
            row=3,
            column=1,
            sticky="nsew",
            padx=4,
            pady=4,
        )

        self._seedos_workspace_sandbox_output = ScrolledText(
            panel,
            height=12,
            width=42,
            wrap=tk.WORD,
            state="disabled",
        )

        self._seedos_workspace_sandbox_output.grid(
            row=0,
            column=0,
            sticky="nsew",
            padx=4,
            pady=4,
        )

        try:
            panel.grid_rowconfigure(
                0,
                weight=1,
            )
            panel.grid_columnconfigure(
                0,
                weight=1,
            )
        except Exception:
            pass

        self._seedos_workspace_sandbox_mode_var = tk.StringVar(
            value="SANDBOX"
        )

        ttk.Label(
            panel,
            textvariable=self._seedos_workspace_sandbox_mode_var,
        ).grid(
            row=1,
            column=0,
            sticky="w",
            padx=4,
            pady=2,
        )


    def _build_seedos_learning_panel(self):
        """Build the learning/knowledge surface."""

        frame = self._seedos_workspace_frame

        panel = ttk.LabelFrame(
            frame,
            text="SEED Learning / Knowledge",
        )

        panel.grid(
            row=3,
            column=2,
            sticky="nsew",
            padx=4,
            pady=4,
        )

        self._seedos_workspace_learning_output = ScrolledText(
            panel,
            height=12,
            width=42,
            wrap=tk.WORD,
            state="disabled",
        )

        self._seedos_workspace_learning_output.grid(
            row=0,
            column=0,
            sticky="nsew",
            padx=4,
            pady=4,
        )

        try:
            panel.grid_rowconfigure(
                0,
                weight=1,
            )
            panel.grid_columnconfigure(
                0,
                weight=1,
            )
        except Exception:
            pass


    def _build_seedos_runtime_panel(self):
        """Build live runtime connection status."""

        frame = self._seedos_workspace_frame

        panel = ttk.LabelFrame(
            frame,
            text="Runtime Connections",
        )

        panel.grid(
            row=4,
            column=0,
            columnspan=3,
            sticky="ew",
            padx=4,
            pady=4,
        )

        self._seedos_workspace_runtime_output = ScrolledText(
            panel,
            height=6,
            wrap=tk.WORD,
            state="disabled",
        )

        self._seedos_workspace_runtime_output.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=4,
            pady=4,
        )

        try:
            panel.grid_columnconfigure(
                0,
                weight=1,
            )
        except Exception:
            pass


    def _build_seedos_development_history(self):
        """Build development lineage/history display."""

        frame = self._seedos_workspace_frame

        panel = ttk.LabelFrame(
            frame,
            text="Development Lineage",
        )

        panel.grid(
            row=5,
            column=0,
            columnspan=3,
            sticky="ew",
            padx=4,
            pady=4,
        )

        self._seedos_workspace_history_output = ScrolledText(
            panel,
            height=5,
            wrap=tk.WORD,
            state="disabled",
        )

        self._seedos_workspace_history_output.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=4,
            pady=4,
        )

        try:
            panel.grid_columnconfigure(
                0,
                weight=1,
            )
        except Exception:
            pass


    def _seedos_workspace_mode_changed(self, event=None):
        """Update the active developer operation mode."""

        mode = self._seedos_workspace_mode_var.get().strip().upper()

        if not mode:
            mode = "SUGGEST"

        self._seedos_workspace_mode = mode

        if hasattr(
            self,
            "_seedos_workspace_sandbox_mode_var",
        ):
            self._seedos_workspace_sandbox_mode_var.set(
                f"SANDBOX MODE: {mode}"
            )

        self._seedos_workspace_write(
            (
                self._seedos_workspace_sandbox_output
                if hasattr(
                    self,
                    "_seedos_workspace_sandbox_output",
                )
                else None
            ),
            f"[WORKSPACE] Developer mode = {mode}",
        )


    def _seedos_workspace_get_input(self):
        """Return the current Creator input."""

        widget = getattr(
            self,
            "_seedos_workspace_input",
            None,
        )

        if widget is None:
            return ""

        try:
            return widget.get(
                "1.0",
                tk.END,
            ).strip()
        except Exception:
            return ""


    def _seedos_workspace_clear_input(self):
        """Clear the persistent Creator input field."""

        widget = getattr(
            self,
            "_seedos_workspace_input",
            None,
        )

        if widget is None:
            return

        try:
            widget.delete(
                "1.0",
                tk.END,
            )
        except Exception:
            pass


    def _seedos_workspace_submit(self, event=None):
        """
        Route Creator input into the Section 13 sandbox/development path.

        The workspace never directly calls a Qbit execution method.
        """

        content = self._seedos_workspace_get_input()

        if not content:
            return "break"

        mode = getattr(
            self,
            "_seedos_workspace_mode",
            "SUGGEST",
        )

        try:
            result = self._seedos_sandbox_submit(
                content=content,
                mode=mode,
            )
        except TypeError:
            try:
                result = self._seedos_sandbox_submit(
                    content,
                    mode,
                )
            except Exception as exc:
                result = {
                    "status": "ERROR",
                    "error": str(exc),
                }
        except Exception as exc:
            result = {
                "status": "ERROR",
                "error": str(exc),
            }

        self._seedos_workspace_record_result(
            mode,
            content,
            result,
        )

        self._seedos_workspace_clear_input()

        return "break"


    def _seedos_workspace_teach(self):
        """Explicit Creator teaching operation."""

        content = self._seedos_workspace_get_input()

        if not content:
            return

        method = getattr(
            self,
            "seedos_teach",
            None,
        )

        if callable(method):
            result = method(
                content
            )
        else:
            result = self._seedos_workspace_submit(
                mode="TEACH",
                content=content,
            )

        self._seedos_workspace_record_result(
            "TEACH",
            content,
            result,
        )


    def _seedos_workspace_suggest(self):
        """Explicit Creator suggestion operation."""

        content = self._seedos_workspace_get_input()

        if not content:
            return

        method = getattr(
            self,
            "seedos_suggest",
            None,
        )

        if callable(method):
            result = method(
                content
            )
        else:
            result = self._seedos_workspace_submit(
                mode="SUGGEST",
                content=content,
            )

        self._seedos_workspace_record_result(
            "SUGGEST",
            content,
            result,
        )


    def _seedos_workspace_inspect(self):
        """Inspect an existing SEED system or capability."""

        content = self._seedos_workspace_get_input()

        if not content:
            content = self._seedos_workspace_selection

        if not content:
            return

        method = getattr(
            self,
            "seedos_inspect",
            None,
        )

        if callable(method):
            result = method(
                content
            )
        else:
            result = self.seedos_lookup(
                content
            )

        self._seedos_workspace_record_result(
            "INSPECT",
            str(content),
            result,
        )


    def _seedos_workspace_connect(self):
        """Request connection of a known dynamic capability."""

        content = self._seedos_workspace_get_input()

        if not content:
            content = self._seedos_workspace_selection

        if not content:
            return

        method = getattr(
            self,
            "seedos_connect",
            None,
        )

        if callable(method):
            result = method(
                content
            )
        else:
            result = self._seedos_workspace_submit(
                mode="CONNECT",
                content=content,
            )

        self._seedos_workspace_record_result(
            "CONNECT",
            str(content),
            result,
        )


    def _seedos_workspace_test(self):
        """Request sandbox validation without promotion."""

        content = self._seedos_workspace_get_input()

        if not content:
            content = self._seedos_workspace_selection

        if not content:
            return

        method = getattr(
            self,
            "seedos_test",
            None,
        )

        if callable(method):
            result = method(
                content
            )
        else:
            result = self._seedos_workspace_submit(
                mode="TEST",
                content=content,
            )

        self._seedos_workspace_record_result(
            "TEST",
            str(content),
            result,
        )


    def _seedos_workspace_review(self):
        """Ask SEED to review a proposed development direction."""

        content = self._seedos_workspace_get_input()

        if not content:
            content = self._seedos_workspace_selection

        if not content:
            return

        method = getattr(
            self,
            "seedos_review",
            None,
        )

        if callable(method):
            result = method(
                content
            )
        else:
            result = self._seedos_workspace_submit(
                mode="REVIEW",
                content=content,
            )

        self._seedos_workspace_record_result(
            "REVIEW",
            str(content),
            result,
        )


    def _seedos_workspace_grow(self):
        """
        Submit a growth request.

        GROW remains a proposal to SEED. It does not directly mutate a
        running module.
        """

        content = self._seedos_workspace_get_input()

        if not content:
            return

        method = getattr(
            self,
            "seedos_grow",
            None,
        )

        if callable(method):
            result = method(
                content
            )
        else:
            result = self._seedos_workspace_submit(
                mode="GROW",
                content=content,
            )

        self._seedos_workspace_record_result(
            "GROW",
            content,
            result,
        )


    def _seedos_workspace_registry_selected(self, event=None):
        """Capture the selected runtime system."""

        tree = getattr(
            self,
            "_seedos_workspace_registry_tree",
            None,
        )

        if tree is None:
            return

        try:
            selection = tree.selection()

            if not selection:
                return

            item = tree.item(
                selection[0]
            )

            values = item.get(
                "values",
                (),
            )

            if values:
                self._seedos_workspace_selection = str(
                    values[0]
                )

        except Exception:
            self._seedos_workspace_selection = None


    def _seedos_workspace_refresh_registry(self):
        """Refresh the registry explorer from the existing SEED map."""

        tree = getattr(
            self,
            "_seedos_workspace_registry_tree",
            None,
        )

        if tree is None:
            return

        try:
            for item in tree.get_children():
                tree.delete(
                    item
                )
        except Exception:
            return

        systems = {}

        try:
            systems = self.get_seedos_developer_map()
        except Exception:
            pass

        if not isinstance(
            systems,
            dict,
        ):
            systems = {}

        runtime_systems = systems.get(
            "dynamic_systems",
            {},
        )

        if isinstance(
            runtime_systems,
            dict,
        ):
            iterable = runtime_systems.items()
        elif isinstance(
            runtime_systems,
            (list, tuple, set),
        ):
            iterable = (
                (
                    str(item),
                    {},
                )
                for item in runtime_systems
            )
        else:
            iterable = ()

        for name, descriptor in iterable:

            if not isinstance(
                descriptor,
                dict,
            ):
                descriptor = {}

            capabilities = descriptor.get(
                "capabilities",
                descriptor.get(
                    "capability",
                    [],
                ),
            )

            if isinstance(
                capabilities,
                (list, tuple, set),
            ):
                capability_text = ", ".join(
                    str(item)
                    for item in capabilities
                )
            else:
                capability_text = str(
                    capabilities
                )

            tree.insert(
                "",
                "end",
                values=(
                    str(name),
                    descriptor.get(
                        "kind",
                        "dynamic",
                    ),
                    descriptor.get(
                        "state",
                        descriptor.get(
                            "status",
                            "KNOWN",
                        ),
                    ),
                    capability_text,
                ),
            )

        # ----------------------------------------------------------
        # Add the core systems from the live workspace map.
        # These are references, not newly-created objects.
        # ----------------------------------------------------------

        runtime = self._seedos_workspace_knowledge.get(
            "runtime",
            {},
        )

        for name, connected in runtime.items():

            if not connected:
                continue

            existing = False

            try:
                for item in tree.get_children():
                    values = tree.item(
                        item
                    ).get(
                        "values",
                        (),
                    )

                    if values and values[0] == name:
                        existing = True
                        break
            except Exception:
                pass

            if existing:
                continue

            tree.insert(
                "",
                "end",
                values=(
                    name,
                    "runtime",
                    "CONNECTED",
                    "runtime reference",
                ),
            )


    def _seedos_workspace_refresh_runtime(self):
        """Refresh live runtime connection information."""

        runtime = self._seedos_workspace_knowledge.get(
            "runtime",
            {},
        )

        lines = [
            "SEED OS RUNTIME CONNECTIONS",
            "---------------------------",
        ]

        for name, connected in sorted(
            runtime.items()
        ):
            lines.append(
                f"{name}: "
                f"{'CONNECTED' if connected else 'NOT_BOUND'}"
            )

        dialer = getattr(
            self,
            "qbit_dialer",
            None,
        )

        queue_loop = getattr(
            self,
            "qbit_queue_loop",
            None,
        )

        if queue_loop is None:
            queue_loop = getattr(
                self,
                "qbit_queue",
                None,
            )

        lines.append(
            ""
        )
        lines.append(
            "AUTHORITY"
        )
        lines.append(
            "QbitDialer: "
            f"{'BOUND' if dialer is not None else 'MISSING'}"
        )
        lines.append(
            "QbitQueueLoop: "
            f"{'BOUND' if queue_loop is not None else 'MISSING'}"
        )

        self._seedos_workspace_write(
            self._seedos_workspace_runtime_output,
            "\n".join(
                lines
            ),
            replace=True,
        )


    def _seedos_workspace_refresh_learning(self):
        """Refresh the AI knowledge-base view."""

        knowledge = self._seedos_workspace_knowledge

        lines = [
            "SEED KNOWLEDGE FABRIC",
            "---------------------",
        ]

        kb_version = knowledge.get(
            "init_event_kb_version"
        )

        if kb_version is not None:
            lines.append(
                f"SeedInitEvent KB version: {kb_version}"
            )

        seed_systems = knowledge.get(
            "seed_systems",
            [],
        )

        if seed_systems:
            lines.append(
                ""
            )
            lines.append(
                "Known SEED systems:"
            )

            for system_name in seed_systems:
                lines.append(
                    f"  • {system_name}"
                )

        ai_tools = knowledge.get(
            "ai_tools",
            {},
        )

        if ai_tools:
            lines.append(
                ""
            )
            lines.append(
                "AI knowledge/tool availability:"
            )

            for tool_name, available in sorted(
                ai_tools.items()
            ):
                lines.append(
                    f"  • {tool_name}: "
                    f"{'AVAILABLE' if available else 'UNAVAILABLE'}"
                )

        module_context = knowledge.get(
            "module_context",
            {},
        )

        if isinstance(
            module_context,
            dict,
        ):
            lines.append(
                ""
            )
            lines.append(
                "Initialization context:"
            )

            for key in (
                "version",
                "component",
                "status",
                "cbor_available",
                "qbit_available",
                "devhud_available",
                "task_manager_available",
                "project4_available",
                "orchestrator_available",
            ):
                if key in module_context:
                    lines.append(
                        f"  • {key}: "
                        f"{module_context[key]}"
                    )

        self._seedos_workspace_write(
            self._seedos_workspace_learning_output,
            "\n".join(
                lines
            ),
            replace=True,
        )


    def _seedos_workspace_refresh_history(self):
        """Refresh development lineage/history."""

        history = getattr(
            self,
            "_seedos_workspace_history",
            [],
        )

        lines = [
            "CREATOR → SEED DEVELOPMENT LINEAGE",
            "----------------------------------",
        ]

        if not history:
            lines.append(
                "No developer proposals recorded in this workspace session."
            )
        else:
            for entry in history[-25:]:

                if not isinstance(
                    entry,
                    dict,
                ):
                    lines.append(
                        str(entry)
                    )
                    continue

                timestamp = entry.get(
                    "timestamp",
                    "",
                )

                mode = entry.get(
                    "mode",
                    "UNKNOWN",
                )

                content = entry.get(
                    "content",
                    "",
                )

                status = entry.get(
                    "status",
                    "UNKNOWN",
                )

                lines.append(
                    f"[{timestamp}] "
                    f"{mode} | "
                    f"{status}"
                )

                if content:
                    lines.append(
                        f"  {content}"
                    )

        self._seedos_workspace_write(
            self._seedos_workspace_history_output,
            "\n".join(
                lines
            ),
            replace=True,
        )


    def _seedos_workspace_refresh(self):
        """Refresh every workspace surface."""

        try:
            self._seedos_collect_init_event_knowledge()
        except Exception:
            pass

        try:
            self._seedos_workspace_refresh_registry()
        except Exception:
            pass

        try:
            self._seedos_workspace_refresh_runtime()
        except Exception:
            pass

        try:
            self._seedos_workspace_refresh_learning()
        except Exception:
            pass

        try:
            self._seedos_workspace_refresh_history()
        except Exception:
            pass

        try:
            snapshot = self.seedos_sandbox_snapshot()

            status = snapshot.get(
                "status",
                "READY",
            )

            self._seedos_workspace_status_var.set(
                f"Sandbox: {status}"
            )

        except Exception:
            try:
                self._seedos_workspace_status_var.set(
                    "READY"
                )
            except Exception:
                pass


    def _seedos_workspace_record_result(
        self,
        mode,
        content,
        result,
    ):
        """Record a Creator development operation without executing it."""

        if isinstance(
            result,
            dict,
        ):
            status = result.get(
                "status",
                result.get(
                    "state",
                    "RECORDED",
                ),
            )
        else:
            status = "RECORDED"

        entry = {
            "timestamp": time.time(),
            "mode": str(
                mode
            ).upper(),
            "content": str(
                content
            ),
            "status": str(
                status
            ),
        }

        self._seedos_workspace_history.append(
            entry
        )

        if len(
            self._seedos_workspace_history
        ) > 250:
            del self._seedos_workspace_history[:-250]

        self._seedos_workspace_results.append(
            result
        )

        if len(
            self._seedos_workspace_results
        ) > 100:
            del self._seedos_workspace_results[:-100]

        self._seedos_workspace_write(
            getattr(
                self,
                "_seedos_workspace_sandbox_output",
                None,
            ),
            self._seedos_format_result(
                result
            ),
            replace=False,
        )

        try:
            self._seedos_workspace_refresh_history()
        except Exception:
            pass


    def _seedos_workspace_write(
        self,
        widget,
        text,
        *,
        replace=False,
    ):
        """Thread-safe-ish text writer for the workspace widgets."""

        if widget is None:
            return

        try:
            widget.configure(
                state="normal"
            )

            if replace:
                widget.delete(
                    "1.0",
                    tk.END,
                )

            widget.insert(
                tk.END,
                str(text)
                + "\n",
            )

            widget.see(
                tk.END
            )

            widget.configure(
                state="disabled"
            )

        except Exception:
            pass


    def _seedos_format_result(self, result):
        """Convert a sandbox/development result to readable workspace text."""

        if result is None:
            return "SEED returned no result."

        if isinstance(
            result,
            dict,
        ):
            lines = []

            for key, value in result.items():

                if key in (
                    "qbit",
                    "qbit_object",
                    "raw_qbit",
                ):
                    continue

                if isinstance(
                    value,
                    (dict, list, tuple),
                ):
                    try:
                        value_text = json.dumps(
                            value,
                            indent=2,
                            default=str,
                        )
                    except Exception:
                        value_text = str(
                            value
                        )
                else:
                    value_text = str(
                        value
                    )

                lines.append(
                    f"{key}: {value_text}"
                )

            return "\n".join(
                lines
            )

        return str(
            result
        )


    def _seedos_workspace_route_to_seed(
        self,
        content,
        mode,
    ):
        """
        Central developer-to-SEED routing point.

        This is intentionally an input/proposal route.

        It does not:
            - call qbit.execute_command()
            - construct a Qbit
            - call QbitQueueLoop directly
            - invoke ActionEngine execution
            - bypass QbitDialer
        """

        payload = {
            "source": "DEVHUD",
            "origin": "CREATOR",
            "interface": "SEED_OS_DEVELOPER_WORKSPACE",
            "mode": str(
                mode
            ).upper(),
            "content": str(
                content
            ),
            "proposal": True,
            "developer_input": True,
            "learning_candidate": True,
            "authority": "QbitDialer",
            "transport": "SEEDEventBus",
        }

        # --------------------------------------------------------------
        # First preference: Section 13 sandbox submission.
        # --------------------------------------------------------------

        sandbox_submit = getattr(
            self,
            "_seedos_sandbox_submit",
            None,
        )

        if callable(
            sandbox_submit
        ):
            try:
                return sandbox_submit(
                    content=content,
                    mode=mode,
                )
            except TypeError:
                try:
                    return sandbox_submit(
                        content,
                        mode,
                    )
                except Exception:
                    pass
            except Exception:
                pass

        # --------------------------------------------------------------
        # Second preference: existing unified suggestion bridge.
        # --------------------------------------------------------------

        suggest = getattr(
            self,
            "suggest_to_seed",
            None,
        )

        if callable(
            suggest
        ):
            try:
                return suggest(
                    content,
                    category=str(
                        mode
                    ).lower(),
                    source="DEVHUD",
                )
            except TypeError:
                try:
                    return suggest(
                        content
                    )
                except Exception:
                    pass
            except Exception:
                pass

        # --------------------------------------------------------------
        # Final fallback: existing EventBus only.
        #
        # The EventBus carries the input.
        # SEED cognition determines what happens next.
        # --------------------------------------------------------------

        event_bus = getattr(
            self,
            "event_bus",
            None,
        )

        emit = getattr(
            event_bus,
            "emit",
            None,
        )

        if callable(
            emit
        ):
            try:
                result = emit(
                    "SEED_INPUT",
                    payload,
                )

                if inspect.isawaitable(result):
                    return {
                        "status": "QUEUED",
                        "mode": mode,
                        "transport": "SEEDEventBus",
                    }

                return {
                    "status": "SUBMITTED",
                    "mode": mode,
                    "transport": "SEEDEventBus",
                    "result": result,
                }

            except TypeError:
                try:
                    result = emit(
                        {
                            "type": "SEED_INPUT",
                            "payload": payload,
                        }
                    )

                    return {
                        "status": "SUBMITTED",
                        "mode": mode,
                        "transport": "SEEDEventBus",
                        "result": result,
                    }

                except Exception as exc:
                    return {
                        "status": "ERROR",
                        "mode": mode,
                        "error": str(exc),
                    }

            except Exception as exc:
                return {
                    "status": "ERROR",
                    "mode": mode,
                    "error": str(exc),
                }

        return {
            "status": "DEFERRED",
            "mode": mode,
            "reason": (
                "No developer input transport is currently bound."
            ),
        }


    def _seedos_workspace_direct_submit(
        self,
        content,
        mode,
    ):
        """
        Compatibility helper for callers that use the workspace as a
        programmatic developer interface.
        """

        return self._seedos_workspace_route_to_seed(
            content,
            mode,
        )


        try:
            self._initialize_seedos_developer_workspace()
        except Exception as exc:
            self.logger.warning(
                "[DEVHUD] Developer Workspace initialization deferred | error=%s",
                exc,
            )




    # ==========================================================
    # SECTION 14 — SEED OS DEVELOPER WORKSPACE
    # ==========================================================
    #
    # PURPOSE:
    #   Provide the creator/developer with one persistent workspace
    #   for teaching, suggesting, inspecting, connecting, testing,
    #   reviewing, and growing SEED OS.
    #
    # AUTHORITY:
    #   DEVHUD = developer interface / observer
    #   QbitDialer = command authority
    #   QbitQueueLoop = execution / transport authority
    #   SEEDEventBus = existing event transport
    #   TrackSystem = tracking authority
    #   Oracle = observer / governance lane
    #   ModuleRegistry / OptionRegistry = runtime registry references
    #
    # IMPORTANT:
    #   This section does NOT construct a second runtime.
    #   This section does NOT construct Qbits for developer input.
    #   This section does NOT execute commands directly.
    #   Developer input becomes SEED input/proposal and is evaluated
    #   by the existing SEED cognitive/control pipeline.
    #
    #   init_event.py is treated as a knowledge source only.
    #   Existing SeedInitEvent references are reused when available.
    #   No SeedInitEvent runtime is constructed here.
    # ==========================================================

    def _initialize_seedos_developer_workspace(self):
        """
        Initialize the persistent SEED OS developer workspace state.

        The workspace is an interface into the existing runtime rather
        than a second runtime or command system.
        """
        try:
            self._seedos_workspace_initialized = True
            self._seedos_workspace_mounted = False

            self._seedos_workspace_mode = "SUGGEST"
            self._seedos_workspace_target = ""
            self._seedos_workspace_input_text = ""

            self._seedos_workspace_session = []
            self._seedos_workspace_results = []
            self._seedos_workspace_history = []

            self._seedos_workspace_registry = {}
            self._seedos_workspace_runtime = {}
            self._seedos_workspace_learning = {}
            self._seedos_workspace_init_event = {}

            self._seedos_workspace_status = {
                "initialized": True,
                "mode": "SUGGEST",
                "seed_os": True,
                "qbit_dialer": False,
                "qbit_queue_loop": False,
                "event_bus": False,
                "track_system": False,
                "oracle": False,
                "fathud": False,
                "module_registry": False,
                "option_registry": False,
                "init_event_knowledge": False,
            }

            self._seedos_load_init_event_knowledge()

            self._seedos_workspace_status["qbit_dialer"] = (
                self.qbit_dialer is not None
            )

            self._seedos_workspace_status["qbit_queue_loop"] = (
                self.qbit_queue is not None
                or getattr(self, "qbit_queue_loop", None) is not None
            )

            self._seedos_workspace_status["event_bus"] = (
                self.event_bus is not None
            )

            self._seedos_workspace_status["track_system"] = (
                getattr(self, "track_system", None) is not None
            )

            self._seedos_workspace_status["oracle"] = (
                getattr(self, "oracle", None) is not None
                or getattr(self, "oracle_loop", None) is not None
            )

            self._seedos_workspace_status["fathud"] = (
                getattr(self, "fathud", None) is not None
                or getattr(self, "fathud_adapter", None) is not None
            )

            self._seedos_workspace_status["module_registry"] = (
                getattr(self, "module_registry", None) is not None
                or globals().get("ModuleRegistry") is not None
            )

            self._seedos_workspace_status["option_registry"] = (
                getattr(self, "option_registry", None) is not None
                or globals().get("OptionRegistry") is not None
            )

            self._seedos_workspace_refresh_registry()
            self._seedos_workspace_refresh_runtime()
            self._seedos_workspace_refresh_learning()

        except Exception as exc:
            self.logger.warning(
                "[DEVHUD] SEED OS developer workspace initialization failed: %s",
                exc,
            )

            self._seedos_workspace_initialized = False

    def _seedos_load_init_event_knowledge(self):
        """
        Load the existing init_event knowledge base into the developer
        workspace without constructing SeedInitEvent.

        Preferred source:
            existing runtime SeedInitEvent / init_event reference.

        Fallback:
            static knowledge descriptor based on the verified
            init_event.py contract.
        """
        try:
            init_event = getattr(self, "init_event", None)

            if init_event is None:
                init_event = getattr(self, "seed_init_event", None)

            if init_event is None:
                init_event = getattr(self, "seed_init", None)

            if init_event is None and self.core is not None:
                init_event = getattr(self.core, "init_event", None)

            if init_event is None and self.core is not None:
                init_event = getattr(
                    self.core,
                    "seed_init_event",
                    None,
                )

            if init_event is not None:
                knowledge = getattr(
                    init_event,
                    "ai_base_kb",
                    None,
                )

                module_context = getattr(
                    init_event,
                    "MODULE_CONTEXT",
                    None,
                )

                if module_context is None:
                    module_context = getattr(
                        init_event,
                        "module_context",
                        None,
                    )

                self._seedos_workspace_init_event = {
                    "source": "runtime.init_event",
                    "available": True,
                    "knowledge_base": (
                        knowledge
                        if isinstance(knowledge, dict)
                        else {}
                    ),
                    "module_context": (
                        module_context
                        if isinstance(module_context, dict)
                        else {}
                    ),
                }

                self._seedos_workspace_status[
                    "init_event_knowledge"
                ] = bool(
                    isinstance(knowledge, dict)
                    and knowledge
                )

                return self._seedos_workspace_init_event

            # ------------------------------------------------------
            # Static descriptor.
            #
            # This does not instantiate init_event.py.
            # It records the verified knowledge contract so the
            # developer workspace can expose what the runtime
            # knowledge layer is expected to contain.
            # ------------------------------------------------------

            self._seedos_workspace_init_event = {
                "source": "init_event.py",
                "available": False,
                "runtime_instance": False,
                "knowledge_base_descriptor": {
                    "version": "6.9",
                    "contains": [
                        "history",
                        "guidance",
                        "seed_systems",
                        "modules_loaded",
                        "network_rules",
                        "event_history",
                        "canonical_chain",
                        "predictive_branches",
                        "node_scores",
                        "peer_trust",
                        "event_validation_scores",
                        "devhud_integration",
                        "task_manager_integration",
                        "qbit_integration",
                        "project4_integration",
                    ],
                    "capabilities": [
                        "dynamic_module_expansion",
                        "predictive_task_execution",
                        "self_replicating_kb",
                        "cross_device_replication",
                        "instant_kb_sync",
                        "self_healing_chain",
                        "autonomous_module_replication",
                        "cross_project_intelligence_fusion",
                        "ai_self_evolution",
                        "multi_seed_collaboration",
                        "dynamic_ai_replication",
                    ],
                    "ai_tools": [
                        "transformers",
                        "torch",
                        "sentence-transformers",
                        "numpy",
                        "networkx",
                        "scipy",
                        "ray",
                        "fastapi",
                        "uvicorn",
                    ],
                },
                "module_context_descriptor": {
                    "source": "init_event.py",
                    "runtime_construction": False,
                    "package_installation": False,
                    "network_activity_on_import": False,
                    "command_execution_on_import": False,
                },
            }

            self._seedos_workspace_status[
                "init_event_knowledge"
            ] = True

            return self._seedos_workspace_init_event

        except Exception as exc:
            self.logger.warning(
                "[DEVHUD] init_event knowledge bridge failed: %s",
                exc,
            )

            self._seedos_workspace_init_event = {
                "source": "init_event.py",
                "available": False,
                "error": str(exc),
            }

            return self._seedos_workspace_init_event

    def _build_seedos_developer_workspace(self, parent=None):
        """
        Mount the developer workspace into an existing DEVHUD surface.

        No Tk root is created here.
        """
        if getattr(
            self,
            "_seedos_workspace_mounted",
            False,
        ):
            return getattr(
                self,
                "_seedos_workspace_frame",
                None,
            )

        try:
            host = parent

            if host is None:
                host = getattr(self, "dynamic_frame", None)

            if host is None:
                host = getattr(self, "center", None)

            if host is None:
                host = self

            frame = ttk.Frame(host)

            self._seedos_workspace_frame = frame
            self._seedos_workspace_mounted = True

            self._build_seedos_workspace_header(frame)
            self._build_seedos_workspace_input(frame)
            self._build_seedos_workspace_actions(frame)

            body = ttk.Frame(frame)
            body.grid(
                row=3,
                column=0,
                sticky="nsew",
                padx=6,
                pady=6,
            )

            frame.grid_rowconfigure(
                3,
                weight=1,
            )
            frame.grid_columnconfigure(
                0,
                weight=1,
            )

            body.grid_columnconfigure(
                0,
                weight=1,
            )
            body.grid_columnconfigure(
                1,
                weight=2,
            )
            body.grid_columnconfigure(
                2,
                weight=1,
            )
            body.grid_rowconfigure(
                0,
                weight=1,
            )

            self._build_seedos_registry_panel(body)
            self._build_seedos_sandbox_panel(body)
            self._build_seedos_learning_panel(body)

            self._seedos_workspace_refresh()

            return frame

        except Exception as exc:
            self.logger.warning(
                "[DEVHUD] Could not build SEED OS developer workspace: %s",
                exc,
            )

            self._seedos_workspace_mounted = False
            return None

    def _build_seedos_workspace_header(self, parent):
        """
        Build workspace identity/status header.
        """
        header = ttk.Frame(parent)

        header.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=6,
            pady=(6, 2),
        )

        header.grid_columnconfigure(
            1,
            weight=1,
        )

        title = ttk.Label(
            header,
            text="SEED OS — DEVELOPER WORKSPACE",
        )

        title.grid(
            row=0,
            column=0,
            sticky="w",
            padx=(0, 12),
        )

        self._seedos_workspace_status_var = tk.StringVar(
            value="SEED OS workspace initializing..."
        )

        status = ttk.Label(
            header,
            textvariable=self._seedos_workspace_status_var,
        )

        status.grid(
            row=0,
            column=1,
            sticky="e",
        )

    def _build_seedos_workspace_input(self, parent):
        """
        Build the single developer suggestion/teaching input surface.
        """
        input_frame = ttk.Frame(parent)

        input_frame.grid(
            row=1,
            column=0,
            sticky="ew",
            padx=6,
            pady=4,
        )

        input_frame.grid_columnconfigure(
            1,
            weight=1,
        )

        ttk.Label(
            input_frame,
            text="MODE",
        ).grid(
            row=0,
            column=0,
            sticky="w",
            padx=(0, 6),
        )

        self._seedos_workspace_mode_var = tk.StringVar(
            value="SUGGEST"
        )

        mode_box = ttk.Combobox(
            input_frame,
            textvariable=self._seedos_workspace_mode_var,
            values=(
                "TEACH",
                "SUGGEST",
                "INSPECT",
                "CONNECT",
                "DEVELOP",
                "TEST",
                "REVIEW",
                "GROW",
            ),
            state="readonly",
            width=12,
        )

        mode_box.grid(
            row=0,
            column=1,
            sticky="w",
        )

        mode_box.bind(
            "<<ComboboxSelected>>",
            self._seedos_workspace_mode_changed,
        )

        ttk.Label(
            input_frame,
            text="TARGET",
        ).grid(
            row=0,
            column=2,
            sticky="w",
            padx=(12, 6),
        )

        self._seedos_workspace_target_var = tk.StringVar()

        target_entry = ttk.Entry(
            input_frame,
            textvariable=self._seedos_workspace_target_var,
        )

        target_entry.grid(
            row=0,
            column=3,
            sticky="ew",
        )

        input_frame.grid_columnconfigure(
            3,
            weight=1,
        )

        ttk.Label(
            input_frame,
            text="INPUT",
        ).grid(
            row=1,
            column=0,
            sticky="nw",
            pady=(6, 0),
        )

        self._seedos_workspace_input_var = tk.StringVar()

        input_entry = ttk.Entry(
            input_frame,
            textvariable=self._seedos_workspace_input_var,
        )

        input_entry.grid(
            row=1,
            column=1,
            columnspan=3,
            sticky="ew",
            pady=(6, 0),
        )

        input_entry.bind(
            "<Return>",
            self._seedos_workspace_submit,
        )

        self._seedos_workspace_input_entry = input_entry

    def _build_seedos_workspace_actions(self, parent):
        """
        Build explicit developer operations.

        These buttons call the Section 13 developer bridge rather
        than creating a parallel command path.
        """
        actions = ttk.Frame(parent)

        actions.grid(
            row=2,
            column=0,
            sticky="ew",
            padx=6,
            pady=4,
        )

        buttons = (
            ("TEACH", self._seedos_workspace_teach),
            ("SUGGEST", self._seedos_workspace_suggest),
            ("INSPECT", self._seedos_workspace_inspect),
            ("CONNECT", self._seedos_workspace_connect),
            ("TEST", self._seedos_workspace_test),
            ("REVIEW", self._seedos_workspace_review),
            ("GROW", self._seedos_workspace_grow),
            ("REFRESH", self._seedos_workspace_refresh),
        )

        for index, (label, callback) in enumerate(buttons):
            button = ttk.Button(
                actions,
                text=label,
                command=callback,
            )

            button.grid(
                row=0,
                column=index,
                sticky="ew",
                padx=2,
            )

            actions.grid_columnconfigure(
                index,
                weight=1,
            )

    def _build_seedos_registry_panel(self, parent):
        """
        Runtime system / registry explorer.
        """
        panel = ttk.LabelFrame(
            parent,
            text="SEED OS SYSTEM REGISTRY",
        )

        panel.grid(
            row=0,
            column=0,
            sticky="nsew",
            padx=(0, 4),
        )

        panel.grid_rowconfigure(
            1,
            weight=1,
        )
        panel.grid_columnconfigure(
            0,
            weight=1,
        )

        ttk.Button(
            panel,
            text="REFRESH REGISTRY",
            command=self._seedos_workspace_refresh_registry,
        ).grid(
            row=0,
            column=0,
            sticky="ew",
            padx=4,
            pady=4,
        )

        self._seedos_workspace_registry_list = tk.Listbox(
            panel,
            exportselection=False,
        )

        self._seedos_workspace_registry_list.grid(
            row=1,
            column=0,
            sticky="nsew",
            padx=4,
            pady=4,
        )

        self._seedos_workspace_registry_list.bind(
            "<<ListboxSelect>>",
            self._seedos_workspace_registry_selected,
        )

        self._seedos_workspace_registry_detail = tk.Text(
            panel,
            height=8,
            wrap="word",
        )

        self._seedos_workspace_registry_detail.grid(
            row=2,
            column=0,
            sticky="ew",
            padx=4,
            pady=4,
        )

    def _build_seedos_sandbox_panel(self, parent):
        """
        Developer sandbox session view.

        The sandbox records proposals, observations, tests and
        development lineage without becoming an execution authority.
        """
        panel = ttk.LabelFrame(
            parent,
            text="DEVELOPER SANDBOX",
        )

        panel.grid(
            row=0,
            column=1,
            sticky="nsew",
            padx=4,
        )

        panel.grid_rowconfigure(
            0,
            weight=1,
        )
        panel.grid_columnconfigure(
            0,
            weight=1,
        )

        self._seedos_workspace_sandbox_text = tk.Text(
            panel,
            wrap="word",
        )

        self._seedos_workspace_sandbox_text.grid(
            row=0,
            column=0,
            sticky="nsew",
            padx=4,
            pady=4,
        )

        ttk.Button(
            panel,
            text="CLEAR SESSION",
            command=self.seedos_sandbox_clear_session,
        ).grid(
            row=1,
            column=0,
            sticky="ew",
            padx=4,
            pady=4,
        )

    def _build_seedos_learning_panel(self, parent):
        """
        Learning / init_event / Oracle / FATHUD observation surface.
        """
        panel = ttk.LabelFrame(
            parent,
            text="SEED LEARNING + RUNTIME",
        )

        panel.grid(
            row=0,
            column=2,
            sticky="nsew",
            padx=(4, 0),
        )

        panel.grid_rowconfigure(
            0,
            weight=1,
        )
        panel.grid_columnconfigure(
            0,
            weight=1,
        )

        self._seedos_workspace_learning_text = tk.Text(
            panel,
            wrap="word",
        )

        self._seedos_workspace_learning_text.grid(
            row=0,
            column=0,
            sticky="nsew",
            padx=4,
            pady=4,
        )

        ttk.Button(
            panel,
            text="REFRESH RUNTIME",
            command=self._seedos_workspace_refresh_runtime,
        ).grid(
            row=1,
            column=0,
            sticky="ew",
            padx=4,
            pady=2,
        )

        ttk.Button(
            panel,
            text="REFRESH LEARNING",
            command=self._seedos_workspace_refresh_learning,
        ).grid(
            row=2,
            column=0,
            sticky="ew",
            padx=4,
            pady=2,
        )

        ttk.Button(
            panel,
            text="REFRESH HISTORY",
            command=self._seedos_workspace_refresh_history,
        ).grid(
            row=3,
            column=0,
            sticky="ew",
            padx=4,
            pady=2,
        )

    def _seedos_workspace_mode_changed(self, event=None):
        """
        Update the active developer workspace mode.
        """
        try:
            mode = self._seedos_workspace_mode_var.get().strip().upper()

            if not mode:
                mode = "SUGGEST"

            self._seedos_workspace_mode = mode

            self._seedos_workspace_status[
                "mode"
            ] = mode

            self._seedos_workspace_refresh()

        except Exception as exc:
            self.logger.debug(
                "[DEVHUD] Workspace mode update failed: %s",
                exc,
            )

    def _seedos_workspace_submit(self, event=None):
        """
        Submit the current developer input through the existing
        Section 13 SEED OS developer bridge.
        """
        try:
            text = (
                self._seedos_workspace_input_var
                .get()
                .strip()
            )

            target = (
                self._seedos_workspace_target_var
                .get()
                .strip()
            )

            mode = (
                self._seedos_workspace_mode_var
                .get()
                .strip()
                .upper()
            )

            if not text:
                return "break"

            payload = {
                "mode": mode,
                "target": target,
                "input": text,
                "source": "DEVHUD.DEVELOPER_WORKSPACE",
                "interface": "DEVHUD",
                "developer_proposal": True,
            }

            result = self._seedos_sandbox_submit(
                payload
            )

            self._seedos_workspace_session.append(
                {
                    "mode": mode,
                    "target": target,
                    "input": text,
                    "result": result,
                }
            )

            self._seedos_workspace_input_var.set("")

            self._seedos_workspace_refresh()

            return "break"

        except Exception as exc:
            self.logger.warning(
                "[DEVHUD] Developer workspace submit failed: %s",
                exc,
            )

            return "break"

    def _seedos_workspace_teach(self):
        """
        Teach SEED through the Section 13 developer bridge.
        """
        self._seedos_workspace_dispatch(
            "TEACH"
        )

    def _seedos_workspace_suggest(self):
        """
        Submit a developer suggestion.
        """
        self._seedos_workspace_dispatch(
            "SUGGEST"
        )

    def _seedos_workspace_inspect(self):
        """
        Request inspection of an existing SEED OS system.
        """
        self._seedos_workspace_dispatch(
            "INSPECT"
        )

    def _seedos_workspace_connect(self):
        """
        Request a dynamic-system/capability connection proposal.
        """
        self._seedos_workspace_dispatch(
            "CONNECT"
        )

    def _seedos_workspace_test(self):
        """
        Place a development test request into the sandbox.
        """
        self._seedos_workspace_dispatch(
            "TEST"
        )

    def _seedos_workspace_review(self):
        """
        Request a development review.
        """
        self._seedos_workspace_dispatch(
            "REVIEW"
        )

    def _seedos_workspace_grow(self):
        """
        Submit a growth proposal.

        Growth remains a proposal until SEED's existing cognitive
        and command architecture evaluates it.
        """
        self._seedos_workspace_dispatch(
            "GROW"
        )

    def _seedos_workspace_dispatch(self, mode):
        """
        Centralize workspace button dispatch.

        No button directly executes a system command.
        """
        try:
            self._seedos_workspace_mode = mode

            if hasattr(
                self,
                "_seedos_workspace_mode_var",
            ):
                self._seedos_workspace_mode_var.set(
                    mode
                )

            self._seedos_workspace_submit()

        except Exception as exc:
            self.logger.warning(
                "[DEVHUD] Workspace dispatch failed | mode=%s | %s",
                mode,
                exc,
            )

    def _seedos_workspace_registry_selected(self, event=None):
        """
        Display details for the selected runtime system.
        """
        try:
            selection = (
                self._seedos_workspace_registry_list
                .curselection()
            )

            if not selection:
                return

            index = selection[0]

            names = list(
                self._seedos_workspace_registry.keys()
            )

            if index >= len(names):
                return

            name = names[index]

            descriptor = (
                self._seedos_workspace_registry
                .get(name, {})
            )

            self._seedos_workspace_registry_detail.delete(
                "1.0",
                tk.END,
            )

            self._seedos_workspace_registry_detail.insert(
                tk.END,
                json.dumps(
                    descriptor,
                    indent=2,
                    default=str,
                ),
            )

        except Exception as exc:
            self.logger.debug(
                "[DEVHUD] Registry selection failed: %s",
                exc,
            )

    def _seedos_workspace_refresh_registry(self):
        """
        Refresh registry information from existing runtime references
        and the Section 12/13 developer registry bridge.
        """
        try:
            registry_map = {}

            getter = getattr(
                self,
                "get_seed_os_registry_map",
                None,
            )

            if callable(getter):
                result = getter()

                if isinstance(result, dict):
                    registry_map.update(result)

            discover = getattr(
                self,
                "discover_runtime_systems",
                None,
            )

            if callable(discover):
                result = discover()

                if isinstance(result, dict):
                    registry_map.update(result)

            self._seedos_workspace_registry = registry_map

            listbox = getattr(
                self,
                "_seedos_workspace_registry_list",
                None,
            )

            if listbox is not None:
                listbox.delete(
                    0,
                    tk.END,
                )

                for name in registry_map.keys():
                    listbox.insert(
                        tk.END,
                        str(name),
                    )

            return registry_map

        except Exception as exc:
            self.logger.warning(
                "[DEVHUD] Registry workspace refresh failed: %s",
                exc,
            )

            return {}

    def _seedos_workspace_refresh_runtime(self):
        """
        Capture runtime authority references without constructing
        or starting anything.
        """
        try:
            qbit_queue = getattr(
                self,
                "qbit_queue_loop",
                None,
            )

            if qbit_queue is None:
                qbit_queue = getattr(
                    self,
                    "qbit_queue",
                    None,
                )

            self._seedos_workspace_runtime = {
                "qbit_dialer": self.qbit_dialer,
                "qbit_queue_loop": qbit_queue,
                "event_bus": self.event_bus,
                "track_system": getattr(
                    self,
                    "track_system",
                    None,
                ),
                "oracle": getattr(
                    self,
                    "oracle",
                    None,
                ),
                "oracle_loop": getattr(
                    self,
                    "oracle_loop",
                    None,
                ),
                "fathud": getattr(
                    self,
                    "fathud",
                    None,
                ),
                "fathud_adapter": getattr(
                    self,
                    "fathud_adapter",
                    None,
                ),
                "heartbeat": getattr(
                    self,
                    "heartbeat",
                    None,
                ),
                "heartbeat_emitter": getattr(
                    self,
                    "heartbeat_emitter",
                    None,
                ),
            }

            return self._seedos_workspace_runtime

        except Exception as exc:
            self.logger.debug(
                "[DEVHUD] Runtime workspace refresh failed: %s",
                exc,
            )

            return {}

    def _seedos_workspace_refresh_learning(self):
        """
        Refresh the learning view from the existing Section 13
        sandbox plus init_event knowledge.
        """
        try:
            sandbox_snapshot = {}

            snapshot = getattr(
                self,
                "seedos_sandbox_snapshot",
                None,
            )

            if callable(snapshot):
                result = snapshot()

                if isinstance(result, dict):
                    sandbox_snapshot = result

            learning_status = {}

            status = getattr(
                self,
                "get_seed_os_growth_status",
                None,
            )

            if callable(status):
                result = status()

                if isinstance(result, dict):
                    learning_status = result

            self._seedos_workspace_learning = {
                "growth": learning_status,
                "sandbox": sandbox_snapshot,
                "init_event": (
                    self._seedos_workspace_init_event
                ),
                "oracle": self._seedos_workspace_oracle_snapshot(),
                "fathud": self._seedos_workspace_fathud_snapshot(),
            }

            return self._seedos_workspace_learning

        except Exception as exc:
            self.logger.debug(
                "[DEVHUD] Learning workspace refresh failed: %s",
                exc,
            )

            return {}

    def _seedos_workspace_oracle_snapshot(self):
        """
        Read Oracle state if an existing Oracle observer reference
        is available.
        """
        try:
            oracle = getattr(
                self,
                "oracle",
                None,
            )

            if oracle is None:
                oracle = getattr(
                    self,
                    "oracle_loop",
                    None,
                )

            if oracle is None:
                return {
                    "available": False,
                }

            snapshot = getattr(
                oracle,
                "snapshot",
                None,
            )

            if callable(snapshot):
                result = snapshot()

                if isinstance(result, dict):
                    return {
                        "available": True,
                        "snapshot": result,
                    }

            status = getattr(
                oracle,
                "get_status",
                None,
            )

            if callable(status):
                result = status()

                if isinstance(result, dict):
                    return {
                        "available": True,
                        "status": result,
                    }

            return {
                "available": True,
                "type": type(oracle).__name__,
            }

        except Exception as exc:
            return {
                "available": False,
                "error": str(exc),
            }

    def _seedos_workspace_refresh_history(self):
        """
        Refresh developer history from the existing sandbox and
        development bridge.
        """
        try:
            history = []

            if isinstance(
                getattr(
                    self,
                    "_seedos_workspace_session",
                    None,
                ),
                list,
            ):
                history.extend(
                    self._seedos_workspace_session
                )

            if isinstance(
                getattr(
                    self,
                    "_seedos_workspace_results",
                    None,
                ),
                list,
            ):
                history.extend(
                    self._seedos_workspace_results
                )

            development_history = getattr(
                self,
                "_seedos_development_history",
                None,
            )

            if isinstance(
                development_history,
                list,
            ):
                history.extend(
                    development_history
                )

            self._seedos_workspace_history = history

            return history

        except Exception as exc:
            self.logger.debug(
                "[DEVHUD] Workspace history refresh failed: %s",
                exc,
            )

            return []

    def _seedos_workspace_refresh(self):
        """
        Refresh every developer workspace surface.
        """
        try:
            self._seedos_workspace_refresh_registry()
            self._seedos_workspace_refresh_runtime()
            self._seedos_workspace_refresh_learning()
            self._seedos_workspace_refresh_history()

            status = getattr(
                self,
                "_seedos_workspace_status",
                {},
            )

            status_text = (
                "MODE={mode} | "
                "QBIT_DIALER={dialer} | "
                "QUEUE={queue} | "
                "EVENTBUS={event_bus} | "
                "ORACLE={oracle} | "
                "FATHUD={fathud} | "
                "INIT_EVENT_KB={init_event}"
            ).format(
                mode=status.get(
                    "mode",
                    "SUGGEST",
                ),
                dialer=status.get(
                    "qbit_dialer",
                    False,
                ),
                queue=status.get(
                    "qbit_queue_loop",
                    False,
                ),
                event_bus=status.get(
                    "event_bus",
                    False,
                ),
                oracle=status.get(
                    "oracle",
                    False,
                ),
                fathud=status.get(
                    "fathud",
                    False,
                ),
                init_event=status.get(
                    "init_event_knowledge",
                    False,
                ),
            )

            status_var = getattr(
                self,
                "_seedos_workspace_status_var",
                None,
            )

            if status_var is not None:
                status_var.set(
                    status_text
                )

            sandbox_text = getattr(
                self,
                "_seedos_workspace_sandbox_text",
                None,
            )

            if sandbox_text is not None:
                sandbox_text.delete(
                    "1.0",
                    tk.END,
                )

                sandbox_text.insert(
                    tk.END,
                    json.dumps(
                        {
                            "session": self._seedos_workspace_session[
                                -25:
                            ],
                            "results": self._seedos_workspace_results[
                                -25:
                            ],
                        },
                        indent=2,
                        default=str,
                    ),
                )

            learning_text = getattr(
                self,
                "_seedos_workspace_learning_text",
                None,
            )

            if learning_text is not None:
                learning_text.delete(
                    "1.0",
                    tk.END,
                )

                learning_text.insert(
                    tk.END,
                    json.dumps(
                        self._seedos_workspace_learning,
                        indent=2,
                        default=str,
                    ),
                )

            return {
                "status": "refreshed",
                "workspace": True,
            }

        except Exception as exc:
            self.logger.debug(
                "[DEVHUD] Developer workspace refresh failed: %s",
                exc,
            )

            return {
                "status": "error",
                "error": str(exc),
            }




    # ==========================================================
    # SECTION 15 — CAPABILITY / ADAPTER BUILDER
    # ==========================================================
    #
    # PURPOSE:
    #   Convert creator/developer suggestions into structured
    #   capability, SDK, MCP, adapter, provider, or subsystem
    #   proposals that SEED can inspect and evaluate.
    #
    # AUTHORITY:
    #   DEVHUD       = developer interface
    #   SEED OS      = evaluates development proposal
    #   Oracle       = observes / governs
    #   QbitDialer   = command authority
    #   QueueLoop    = execution authority
    #   EventBus     = existing transport
    #   Registry     = runtime registration authority
    #
    # IMPORTANT:
    #   This builder does NOT install packages.
    #   This builder does NOT execute external tools.
    #   This builder does NOT create another runtime.
    #   This builder does NOT bypass QbitDialer.
    #
    #   It creates structured capability proposals.
    #   SEED decides what happens with them.
    # ==========================================================

    def _initialize_seedos_capability_builder(self):
        """
        Initialize the dynamic capability / adapter proposal fabric.
        """
        try:
            self._seedos_capability_builder_initialized = True

            self._seedos_capabilities = {}
            self._seedos_adapter_proposals = {}
            self._seedos_provider_proposals = {}
            self._seedos_sdk_proposals = {}
            self._seedos_mcp_proposals = {}

            self._seedos_capability_history = []

            self._seedos_capability_status = {
                "initialized": True,
                "capabilities": 0,
                "adapters": 0,
                "providers": 0,
                "sdks": 0,
                "mcp": 0,
            }

            self._seedos_register_builtin_capability_descriptors()

        except Exception as exc:
            self.logger.warning(
                "[DEVHUD] Capability builder initialization failed: %s",
                exc,
            )

            self._seedos_capability_builder_initialized = False

    def _seedos_register_builtin_capability_descriptors(self):
        """
        Register knowledge descriptors for existing SEED systems.

        These are descriptors only. They do not instantiate systems.
        """
        descriptors = {
            "QbitDialer": {
                "type": "core_authority",
                "authority": "command",
                "execution": True,
                "status": "existing_runtime",
            },
            "QbitQueueLoop": {
                "type": "core_transport",
                "authority": "execution_transport",
                "execution": True,
                "status": "existing_runtime",
            },
            "SEEDEventBus": {
                "type": "transport",
                "authority": "event_transport",
                "execution": False,
                "status": "existing_runtime",
            },
            "TrackSystem": {
                "type": "tracking",
                "authority": "track_context",
                "execution": False,
                "status": "existing_runtime",
            },
            "Oracle": {
                "type": "observer",
                "authority": "governance_observer",
                "execution": False,
                "status": "existing_runtime_or_optional",
            },
            "FATHUD": {
                "type": "interface",
                "authority": "developer_observer",
                "execution": False,
                "status": "existing_runtime_or_optional",
            },
            "ComputeBrain": {
                "type": "cognition",
                "authority": "thought_generation",
                "execution": False,
                "status": "existing_runtime",
            },
            "TransformerBrain": {
                "type": "cognition",
                "authority": "thought_transformation",
                "execution": False,
                "status": "existing_runtime",
            },
            "IntentEngine": {
                "type": "cognition",
                "authority": "intent_interpretation",
                "execution": False,
                "status": "existing_runtime",
            },
            "ActionEngine": {
                "type": "cognition",
                "authority": "action_proposal",
                "execution": False,
                "status": "existing_runtime",
            },
            "AnalyticsEngine": {
                "type": "cognition",
                "authority": "cycle_observation",
                "execution": False,
                "status": "existing_runtime",
            },
            "ThoughtFeedback": {
                "type": "learning",
                "authority": "feedback",
                "execution": False,
                "status": "existing_runtime_or_optional",
            },
            "init_event.py": {
                "type": "knowledge",
                "authority": "baseline_knowledge_descriptor",
                "execution": False,
                "status": "knowledge_source",
            },
        }

        for name, descriptor in descriptors.items():
            self._seedos_capabilities[name] = {
                "name": name,
                "descriptor": descriptor,
                "source": "DEVHUD.SEED_OS_CAPABILITY_BUILDER",
            }

        self._seedos_update_capability_counts()

    def _seedos_update_capability_counts(self):
        """
        Refresh capability-builder counters.
        """
        self._seedos_capability_status.update(
            {
                "capabilities": len(
                    self._seedos_capabilities
                ),
                "adapters": len(
                    self._seedos_adapter_proposals
                ),
                "providers": len(
                    self._seedos_provider_proposals
                ),
                "sdks": len(
                    self._seedos_sdk_proposals
                ),
                "mcp": len(
                    self._seedos_mcp_proposals
                ),
            }
        )

    def _seedos_build_capability_proposal(
        self,
        name,
        *,
        capability_type="capability",
        target=None,
        purpose="",
        source=None,
        metadata=None,
    ):
        """
        Build a normalized development proposal.

        This creates data for SEED to evaluate; it does not execute it.
        """
        try:
            proposal_id = uuid.uuid4().hex

            proposal = {
                "proposal_id": proposal_id,
                "name": str(name).strip(),
                "type": capability_type,
                "target": (
                    str(target).strip()
                    if target is not None
                    else ""
                ),
                "purpose": str(purpose).strip(),
                "source": (
                    source
                    or "DEVHUD.DEVELOPER_WORKSPACE"
                ),
                "metadata": (
                    dict(metadata)
                    if isinstance(metadata, dict)
                    else {}
                ),
                "status": "PROPOSED",
                "approved": False,
                "execution_required": False,
                "created_at": time.time(),
                "authority": "SEED_OS_EVALUATION",
            }

            self._seedos_capability_history.append(
                proposal
            )

            return proposal

        except Exception as exc:
            self.logger.warning(
                "[DEVHUD] Capability proposal build failed: %s",
                exc,
            )

            return {
                "status": "ERROR",
                "error": str(exc),
            }

    def register_seedos_capability(
        self,
        name,
        *,
        target=None,
        purpose="",
        metadata=None,
    ):
        """
        Register a capability descriptor.
        """
        proposal = self._seedos_build_capability_proposal(
            name,
            capability_type="capability",
            target=target,
            purpose=purpose,
            metadata=metadata,
        )

        if proposal.get("status") == "ERROR":
            return proposal

        self._seedos_capabilities[
            proposal["name"]
        ] = proposal

        self._seedos_update_capability_counts()

        self._seedos_emit_capability_proposal(
            proposal
        )

        return proposal

    def build_seedos_adapter(
        self,
        name,
        target,
        *,
        purpose="",
        protocol="",
        metadata=None,
    ):
        """
        Create an adapter proposal.

        Adapter details remain outside the core authority layer.
        """
        proposal = self._seedos_build_capability_proposal(
            name,
            capability_type="adapter",
            target=target,
            purpose=purpose,
            metadata={
                "protocol": protocol,
                **(
                    metadata
                    if isinstance(metadata, dict)
                    else {}
                ),
            },
        )

        if proposal.get("status") == "ERROR":
            return proposal

        self._seedos_adapter_proposals[
            proposal["proposal_id"]
        ] = proposal

        self._seedos_update_capability_counts()

        self._seedos_emit_capability_proposal(
            proposal
        )

        return proposal

    def build_seedos_provider(
        self,
        name,
        target,
        *,
        purpose="",
        protocol="",
        metadata=None,
    ):
        """
        Create an external-provider proposal.
        """
        proposal = self._seedos_build_capability_proposal(
            name,
            capability_type="provider",
            target=target,
            purpose=purpose,
            metadata={
                "protocol": protocol,
                "provider_boundary": True,
                **(
                    metadata
                    if isinstance(metadata, dict)
                    else {}
                ),
            },
        )

        if proposal.get("status") == "ERROR":
            return proposal

        self._seedos_provider_proposals[
            proposal["proposal_id"]
        ] = proposal

        self._seedos_update_capability_counts()

        self._seedos_emit_capability_proposal(
            proposal
        )

        return proposal

    def build_seedos_sdk(
        self,
        name,
        target,
        *,
        purpose="",
        package="",
        metadata=None,
    ):
        """
        Create an SDK capability proposal.

        Package installation remains outside DEVHUD.
        """
        proposal = self._seedos_build_capability_proposal(
            name,
            capability_type="sdk",
            target=target,
            purpose=purpose,
            metadata={
                "package": package,
                "installation_requested": False,
                "runtime_import_requested": False,
                **(
                    metadata
                    if isinstance(metadata, dict)
                    else {}
                ),
            },
        )

        if proposal.get("status") == "ERROR":
            return proposal

        self._seedos_sdk_proposals[
            proposal["proposal_id"]
        ] = proposal

        self._seedos_update_capability_counts()

        self._seedos_emit_capability_proposal(
            proposal
        )

        return proposal

    def build_seedos_mcp(
        self,
        name,
        target,
        *,
        purpose="",
        transport="",
        metadata=None,
    ):
        """
        Create an MCP capability proposal.

        MCP is treated as an adapter/provider capability here.
        No MCP client/server is started by this method.
        """
        proposal = self._seedos_build_capability_proposal(
            name,
            capability_type="mcp",
            target=target,
            purpose=purpose,
            metadata={
                "transport": transport,
                "mcp_runtime_started": False,
                "tool_execution": False,
                **(
                    metadata
                    if isinstance(metadata, dict)
                    else {}
                ),
            },
        )

        if proposal.get("status") == "ERROR":
            return proposal

        self._seedos_mcp_proposals[
            proposal["proposal_id"]
        ] = proposal

        self._seedos_update_capability_counts()

        self._seedos_emit_capability_proposal(
            proposal
        )

        return proposal

    def _seedos_emit_capability_proposal(
        self,
        proposal,
    ):
        """
        Send a capability proposal through the existing EventBus.
        """
        try:
            if self.event_bus is None:
                return False

            emit = getattr(
                self.event_bus,
                "emit",
                None,
            )

            if not callable(emit):
                return False

            payload = {
                "event": "SEED_DEVELOPMENT_CAPABILITY",
                "source": "DEVHUD",
                "authority": "SEED_OS_EVALUATION",
                "proposal": proposal,
            }

            emit(
                "SEED_DEVELOPMENT_CAPABILITY",
                payload,
            )

            return True

        except Exception as exc:
            self.logger.debug(
                "[DEVHUD] Capability proposal event failed: %s",
                exc,
            )

            return False

    def suggest_seedos_capability(
        self,
        name,
        *,
        target=None,
        purpose="",
        capability_type="capability",
        metadata=None,
    ):
        """
        Public creator/developer capability suggestion.

        The suggestion enters the existing SEED developer bridge.
        """
        try:
            proposal = self._seedos_build_capability_proposal(
                name,
                capability_type=capability_type,
                target=target,
                purpose=purpose,
                metadata=metadata,
            )

            if proposal.get("status") == "ERROR":
                return proposal

            self._seedos_capability_history.append(
                {
                    "event": "CAPABILITY_SUGGESTED",
                    "proposal_id": proposal[
                        "proposal_id"
                    ],
                    "name": proposal["name"],
                    "time": time.time(),
                }
            )

            suggest = getattr(
                self,
                "suggest_to_seed",
                None,
            )

            if callable(suggest):
                result = suggest(
                    purpose
                    or name,
                    category="DEVELOP",
                    target=target or name,
                )
            else:
                result = {
                    "status": "proposal_created",
                }

            proposal["seed_result"] = result

            self._seedos_emit_capability_proposal(
                proposal
            )

            return proposal

        except Exception as exc:
            self.logger.warning(
                "[DEVHUD] SEED capability suggestion failed: %s",
                exc,
            )

            return {
                "status": "ERROR",
                "error": str(exc),
            }

    def inspect_seedos_capability(
        self,
        name,
    ):
        """
        Inspect a known capability or development proposal.
        """
        name = str(name).strip()

        if name in self._seedos_capabilities:
            return self._seedos_capabilities[name]

        for collection in (
            self._seedos_adapter_proposals,
            self._seedos_provider_proposals,
            self._seedos_sdk_proposals,
            self._seedos_mcp_proposals,
        ):
            for proposal in collection.values():
                if proposal.get("name") == name:
                    return proposal

        return {
            "status": "not_found",
            "name": name,
        }

    def get_seedos_capability_map(self):
        """
        Return the complete developer capability map.
        """
        self._seedos_update_capability_counts()

        return {
            "status": "ok",
            "capabilities": dict(
                self._seedos_capabilities
            ),
            "adapters": dict(
                self._seedos_adapter_proposals
            ),
            "providers": dict(
                self._seedos_provider_proposals
            ),
            "sdks": dict(
                self._seedos_sdk_proposals
            ),
            "mcp": dict(
                self._seedos_mcp_proposals
            ),
            "status_counts": dict(
                self._seedos_capability_status
            ),
        }

    def _seedos_capability_from_workspace(
        self,
        text,
        mode=None,
        target=None,
    ):
        """
        Interpret developer workspace input as a capability proposal.

        This method intentionally creates a proposal rather than
        attempting to perform the requested external operation.
        """
        mode = (
            str(mode).strip().upper()
            if mode
            else "DEVELOP"
        )

        text = str(text).strip()
        target = (
            str(target).strip()
            if target
            else ""
        )

        lowered = (
            f"{text} {target}".lower()
        )

        if "mcp" in lowered:
            capability_type = "mcp"
        elif (
            "sdk" in lowered
            or "package" in lowered
        ):
            capability_type = "sdk"
        elif (
            "adapter" in lowered
            or "api" in lowered
        ):
            capability_type = "adapter"
        elif (
            "provider" in lowered
            or "service" in lowered
        ):
            capability_type = "provider"
        else:
            capability_type = "capability"

        proposal = self.suggest_seedos_capability(
            target or text,
            target=target,
            purpose=text,
            capability_type=capability_type,
            metadata={
                "workspace_mode": mode,
                "developer_input": text,
            },
        )

        return proposal

    def _seedos_capability_builder_status(self):
        """
        Return builder status for DEVHUD and Oracle observation.
        """
        self._seedos_update_capability_counts()

        return {
            "initialized": getattr(
                self,
                "_seedos_capability_builder_initialized",
                False,
            ),
            **dict(
                self._seedos_capability_status
            ),
        }


    # ==========================================================
    # SECTION 16 — SANDBOXED VALIDATION & TESTING
    # ==========================================================
    #
    # PURPOSE:
    #   Give SEED OS a controlled development/testing surface for
    #   capability, SDK, MCP, adapter, provider, and subsystem
    #   proposals created by the Developer Workspace.
    #
    # AUTHORITY:
    #   DEVHUD       = interface / observation
    #   SEED OS      = evaluation
    #   Oracle       = observation / governance
    #   QbitDialer   = command authority
    #   QbitQueueLoop = execution / transport
    #   EventBus     = existing transport
    #
    # IMPORTANT:
    #   SANDBOX != LIVE RUNTIME
    #
    #   A sandbox test records and evaluates a proposal.
    #   It does not silently promote, install, execute, or replace
    #   an existing SEED OS subsystem.
    #
    #   No second Qbit runtime.
    #   No second EventBus.
    #   No second QbitDialer.
    #   No second QueueLoop.
    #   No package installation.
    #   No MCP server/client startup.
    # ==========================================================

    def _initialize_seedos_sandbox_validation(self):
        """
        Initialize the validation/testing fabric.
        """
        try:
            self._seedos_validation_initialized = True

            self._seedos_test_sessions = {}
            self._seedos_test_results = {}
            self._seedos_validation_history = []

            self._seedos_validation_status = {
                "initialized": True,
                "active_session": None,
                "tests_created": 0,
                "tests_completed": 0,
                "passed": 0,
                "failed": 0,
                "blocked": 0,
            }

        except Exception as exc:
            self.logger.warning(
                "[DEVHUD] Sandbox validation initialization failed: %s",
                exc,
            )

            self._seedos_validation_initialized = False

    def _seedos_create_test_session(
        self,
        proposal=None,
        *,
        name=None,
        purpose="",
        metadata=None,
    ):
        """
        Create a sandbox validation session around a proposal.

        The session contains state only; it does not execute the
        proposed capability.
        """
        try:
            proposal_data = (
                dict(proposal)
                if isinstance(proposal, dict)
                else {}
            )

            session_id = (
                "SANDBOX."
                + uuid.uuid4().hex[:16]
            )

            session = {
                "session_id": session_id,
                "proposal_id": proposal_data.get(
                    "proposal_id"
                ),
                "name": (
                    name
                    or proposal_data.get(
                        "name",
                        "unnamed",
                    )
                ),
                "purpose": (
                    purpose
                    or proposal_data.get(
                        "purpose",
                        "",
                    )
                ),
                "type": proposal_data.get(
                    "type",
                    "capability",
                ),
                "target": proposal_data.get(
                    "target",
                    "",
                ),
                "status": "CREATED",
                "execution_allowed": False,
                "promotion_allowed": False,
                "created_at": time.time(),
                "metadata": (
                    dict(metadata)
                    if isinstance(metadata, dict)
                    else {}
                ),
                "checks": [],
                "results": [],
            }

            self._seedos_test_sessions[
                session_id
            ] = session

            self._seedos_validation_status[
                "active_session"
            ] = session_id

            self._seedos_validation_status[
                "tests_created"
            ] += 1

            self._seedos_validation_history.append(
                {
                    "event": "SESSION_CREATED",
                    "session_id": session_id,
                    "proposal_id": session[
                        "proposal_id"
                    ],
                    "time": time.time(),
                }
            )

            self._seedos_emit_validation_event(
                "SEED_SANDBOX_SESSION_CREATED",
                session,
            )

            return session

        except Exception as exc:
            self.logger.warning(
                "[DEVHUD] Sandbox session creation failed: %s",
                exc,
            )

            return {
                "status": "ERROR",
                "error": str(exc),
            }

    def _seedos_add_validation_check(
        self,
        session_id,
        check_name,
        *,
        expected=None,
        actual=None,
        status="PENDING",
        details=None,
    ):
        """
        Add a deterministic validation record.
        """
        try:
            session = self._seedos_test_sessions.get(
                session_id
            )

            if session is None:
                return {
                    "status": "ERROR",
                    "error": "sandbox_session_not_found",
                    "session_id": session_id,
                }

            check = {
                "check_id": uuid.uuid4().hex,
                "name": str(check_name),
                "expected": expected,
                "actual": actual,
                "status": str(status).upper(),
                "details": (
                    dict(details)
                    if isinstance(details, dict)
                    else {}
                ),
                "time": time.time(),
            }

            session["checks"].append(
                check
            )

            return check

        except Exception as exc:
            return {
                "status": "ERROR",
                "error": str(exc),
            }

    def _seedos_validate_authority_boundary(
        self,
        session,
    ):
        """
        Verify that a proposed capability does not replace or bypass
        the existing SEED authority chain.
        """
        checks = []

        proposal_type = session.get(
            "type",
            "",
        )

        authority = session.get(
            "metadata",
            {},
        ).get(
            "authority",
            "",
        )

        checks.append(
            self._seedos_add_validation_check(
                session["session_id"],
                "QbitDialer authority preserved",
                expected="QbitDialer",
                actual=getattr(
                    self,
                    "qbit_dialer",
                    None,
                ).__class__.__name__
                if getattr(
                    self,
                    "qbit_dialer",
                    None,
                )
                is not None
                else None,
                status=(
                    "PASS"
                    if getattr(
                        self,
                        "qbit_dialer",
                        None,
                    )
                    is not None
                    else "BLOCKED"
                ),
            )
        )

        checks.append(
            self._seedos_add_validation_check(
                session["session_id"],
                "Execution authority preserved",
                expected="QbitQueueLoop",
                actual=(
                    getattr(
                        self,
                        "qbit_queue_loop",
                        None,
                    )
                    or getattr(
                        self,
                        "qbit_queue",
                        None,
                    )
                ).__class__.__name__
                if (
                    getattr(
                        self,
                        "qbit_queue_loop",
                        None,
                    )
                    or getattr(
                        self,
                        "qbit_queue",
                        None,
                    )
                )
                is not None
                else None,
                status=(
                    "PASS"
                    if (
                        getattr(
                            self,
                            "qbit_queue_loop",
                            None,
                        )
                        or getattr(
                            self,
                            "qbit_queue",
                            None,
                        )
                    )
                    is not None
                    else "BLOCKED"
                ),
            )
        )

        checks.append(
            self._seedos_add_validation_check(
                session["session_id"],
                "No direct developer execution",
                expected=False,
                actual=session.get(
                    "execution_allowed",
                    False,
                ),
                status=(
                    "PASS"
                    if not session.get(
                        "execution_allowed",
                        False,
                    )
                    else "FAIL"
                ),
            )
        )

        if authority:
            checks.append(
                self._seedos_add_validation_check(
                    session["session_id"],
                    "Authority metadata",
                    expected="SEED_OS_EVALUATION",
                    actual=authority,
                    status=(
                        "PASS"
                        if authority
                        == "SEED_OS_EVALUATION"
                        else "REVIEW"
                    ),
                )
            )

        return checks

    def _seedos_validate_runtime_bindings(
        self,
        session,
    ):
        """
        Validate that the proposal can coexist with the current
        runtime without creating replacement infrastructure.
        """
        bindings = {
            "event_bus": getattr(
                self,
                "event_bus",
                None,
            ),
            "qbit_dialer": getattr(
                self,
                "qbit_dialer",
                None,
            ),
            "qbit_queue_loop": (
                getattr(
                    self,
                    "qbit_queue_loop",
                    None,
                )
                or getattr(
                    self,
                    "qbit_queue",
                    None,
                )
            ),
            "track_system": getattr(
                self,
                "track_system",
                None,
            ),
        }

        for name, instance in bindings.items():
            self._seedos_add_validation_check(
                session["session_id"],
                f"Existing runtime binding: {name}",
                expected="existing_reference",
                actual=(
                    type(instance).__name__
                    if instance is not None
                    else None
                ),
                status=(
                    "PASS"
                    if instance is not None
                    else "REVIEW"
                ),
            )

        return bindings

    def _seedos_validate_external_capability(
        self,
        session,
    ):
        """
        Validate the descriptor for SDK/MCP/provider/adapter proposals.

        This intentionally performs metadata validation only.
        """
        proposal_type = str(
            session.get(
                "type",
                "",
            )
        ).lower()

        metadata = session.get(
            "metadata",
            {},
        )

        checks = []

        if proposal_type == "sdk":
            checks.append(
                self._seedos_add_validation_check(
                    session["session_id"],
                    "SDK installation disabled in sandbox",
                    expected=False,
                    actual=metadata.get(
                        "installation_requested",
                        False,
                    ),
                    status=(
                        "PASS"
                        if not metadata.get(
                            "installation_requested",
                            False,
                        )
                        else "BLOCKED"
                    ),
                )
            )

        if proposal_type == "mcp":
            checks.append(
                self._seedos_add_validation_check(
                    session["session_id"],
                    "MCP runtime startup disabled",
                    expected=False,
                    actual=metadata.get(
                        "mcp_runtime_started",
                        False,
                    ),
                    status=(
                        "PASS"
                        if not metadata.get(
                            "mcp_runtime_started",
                            False,
                        )
                        else "BLOCKED"
                    ),
                )
            )

            checks.append(
                self._seedos_add_validation_check(
                    session["session_id"],
                    "MCP tool execution disabled",
                    expected=False,
                    actual=metadata.get(
                        "tool_execution",
                        False,
                    ),
                    status=(
                        "PASS"
                        if not metadata.get(
                            "tool_execution",
                            False,
                        )
                        else "BLOCKED"
                    ),
                )
            )

        if proposal_type in (
            "provider",
            "adapter",
        ):
            checks.append(
                self._seedos_add_validation_check(
                    session["session_id"],
                    "External execution deferred",
                    expected=False,
                    actual=metadata.get(
                        "execution_requested",
                        False,
                    ),
                    status=(
                        "PASS"
                        if not metadata.get(
                            "execution_requested",
                            False,
                        )
                        else "BLOCKED"
                    ),
                )
            )

        return checks

    def _seedos_validate_init_event_compatibility(
        self,
        session,
    ):
        """
        Verify compatibility with the knowledge contract exposed by
        init_event.py.
        """
        init_event = getattr(
            self,
            "_seedos_workspace_init_event",
            {},
        )

        available = bool(
            isinstance(
                init_event,
                dict,
            )
            and init_event
        )

        return self._seedos_add_validation_check(
            session["session_id"],
            "init_event knowledge bridge",
            expected=True,
            actual=available,
            status=(
                "PASS"
                if available
                else "REVIEW"
            ),
            details={
                "source": (
                    init_event.get(
                        "source"
                    )
                    if isinstance(
                        init_event,
                        dict,
                    )
                    else None
                ),
            },
        )

    def _seedos_validate_developer_proposal(
        self,
        session_id,
    ):
        """
        Run all sandbox validation checks for a session.
        """
        try:
            session = self._seedos_test_sessions.get(
                session_id
            )

            if session is None:
                return {
                    "status": "ERROR",
                    "error": "sandbox_session_not_found",
                }

            session["status"] = "VALIDATING"

            self._seedos_validate_authority_boundary(
                session
            )

            self._seedos_validate_runtime_bindings(
                session
            )

            self._seedos_validate_external_capability(
                session
            )

            self._seedos_validate_init_event_compatibility(
                session
            )

            checks = session.get(
                "checks",
                [],
            )

            failed = [
                check
                for check in checks
                if check.get("status")
                == "FAIL"
            ]

            blocked = [
                check
                for check in checks
                if check.get("status")
                == "BLOCKED"
            ]

            review = [
                check
                for check in checks
                if check.get("status")
                == "REVIEW"
            ]

            passed = [
                check
                for check in checks
                if check.get("status")
                == "PASS"
            ]

            if failed:
                final_status = "FAILED"
            elif blocked:
                final_status = "BLOCKED"
            elif review:
                final_status = "REVIEW"
            else:
                final_status = "PASSED"

            session["status"] = final_status
            session["validation_completed_at"] = (
                time.time()
            )

            session["summary"] = {
                "passed": len(passed),
                "failed": len(failed),
                "blocked": len(blocked),
                "review": len(review),
                "total": len(checks),
            }

            self._seedos_validation_status[
                "tests_completed"
            ] += 1

            if final_status == "PASSED":
                self._seedos_validation_status[
                    "passed"
                ] += 1

            elif final_status == "FAILED":
                self._seedos_validation_status[
                    "failed"
                ] += 1

            elif final_status == "BLOCKED":
                self._seedos_validation_status[
                    "blocked"
                ] += 1

            self._seedos_validation_history.append(
                {
                    "event": "VALIDATION_COMPLETED",
                    "session_id": session_id,
                    "status": final_status,
                    "summary": dict(
                        session["summary"]
                    ),
                    "time": time.time(),
                }
            )

            self._seedos_emit_validation_event(
                "SEED_SANDBOX_VALIDATION_RESULT",
                session,
            )

            return session

        except Exception as exc:
            self.logger.warning(
                "[DEVHUD] Sandbox validation failed: %s",
                exc,
            )

            return {
                "status": "ERROR",
                "error": str(exc),
            }

    def seedos_test_capability(
        self,
        capability,
        *,
        purpose="",
        metadata=None,
    ):
        """
        Public sandbox test entry point.

        Accepts an existing capability/proposal descriptor and
        evaluates its compatibility with the current SEED OS runtime.
        """
        try:
            if isinstance(
                capability,
                str,
            ):
                inspector = getattr(
                    self,
                    "inspect_seedos_capability",
                    None,
                )

                if callable(inspector):
                    capability = inspector(
                        capability
                    )

                else:
                    capability = {
                        "name": capability,
                    }

            if not isinstance(
                capability,
                dict,
            ):
                return {
                    "status": "ERROR",
                    "error": "invalid_capability",
                }

            session = self._seedos_create_test_session(
                capability,
                purpose=purpose,
                metadata=metadata,
            )

            if session.get("status") == "ERROR":
                return session

            return self._seedos_validate_developer_proposal(
                session["session_id"]
            )

        except Exception as exc:
            self.logger.warning(
                "[DEVHUD] Capability sandbox test failed: %s",
                exc,
            )

            return {
                "status": "ERROR",
                "error": str(exc),
            }

    def seedos_test_development_request(
        self,
        text,
        *,
        target=None,
        mode="TEST",
    ):
        """
        Convert raw developer input into a sandbox test request.

        The request remains a proposal.
        """
        try:
            capability_builder = getattr(
                self,
                "_seedos_capability_from_workspace",
                None,
            )

            if callable(capability_builder):
                proposal = capability_builder(
                    text,
                    mode=mode,
                    target=target,
                )
            else:
                proposal = {
                    "name": target or text,
                    "type": "capability",
                    "target": target or "",
                    "purpose": text,
                }

            return self.seedos_test_capability(
                proposal,
                purpose=text,
                metadata={
                    "workspace_mode": mode,
                    "developer_test": True,
                },
            )

        except Exception as exc:
            return {
                "status": "ERROR",
                "error": str(exc),
            }

    def _seedos_emit_validation_event(
        self,
        event_name,
        payload,
    ):
        """
        Emit validation telemetry through the existing EventBus.
        """
        try:
            event_bus = getattr(
                self,
                "event_bus",
                None,
            )

            if event_bus is None:
                return False

            emit = getattr(
                event_bus,
                "emit",
                None,
            )

            if not callable(emit):
                return False

            emit(
                event_name,
                {
                    "source": "DEVHUD",
                    "authority": "SEED_OS_EVALUATION",
                    "payload": payload,
                },
            )

            return True

        except Exception as exc:
            self.logger.debug(
                "[DEVHUD] Validation event emission failed: %s",
                exc,
            )

            return False

    def seedos_get_test_result(
        self,
        session_id,
    ):
        """
        Return a single sandbox validation session.
        """
        return self._seedos_test_sessions.get(
            session_id,
            {
                "status": "not_found",
                "session_id": session_id,
            },
        )

    def seedos_get_validation_status(self):
        """
        Return current sandbox validation status.
        """
        return {
            "status": "ok",
            **dict(
                self._seedos_validation_status
            ),
        }

    def seedos_get_validation_history(
        self,
        limit=50,
    ):
        """
        Return recent validation history.
        """
        try:
            limit = max(
                1,
                int(limit),
            )
        except Exception:
            limit = 50

        return list(
            self._seedos_validation_history[
                -limit:
            ]
        )

    def seedos_clear_validation_session(
        self,
        session_id,
    ):
        """
        Remove a completed development session from the active
        sandbox session map.

        Historical validation records remain intact.
        """
        session = self._seedos_test_sessions.pop(
            session_id,
            None,
        )

        if session is None:
            return {
                "status": "not_found",
                "session_id": session_id,
            }

        if (
            self._seedos_validation_status.get(
                "active_session"
            )
            == session_id
        ):
            self._seedos_validation_status[
                "active_session"
            ] = None

        return {
            "status": "cleared",
            "session_id": session_id,
        }

    def seedos_review_test(
        self,
        session_id,
    ):
        """
        Produce a human/SEED-readable review package for a sandbox
        result.

        This does not promote the capability.
        """
        session = self._seedos_test_sessions.get(
            session_id
        )

        if session is None:
            return {
                "status": "not_found",
                "session_id": session_id,
            }

        return {
            "status": "review",
            "session_id": session_id,
            "proposal": {
                "name": session.get(
                    "name"
                ),
                "type": session.get(
                    "type"
                ),
                "target": session.get(
                    "target"
                ),
                "purpose": session.get(
                    "purpose"
                ),
            },
            "validation": dict(
                session.get(
                    "summary",
                    {},
                )
            ),
            "checks": list(
                session.get(
                    "checks",
                    [],
                )
            ),
            "promotion": {
                "allowed": False,
                "reason": (
                    "Promotion belongs to the controlled "
                    "SEED OS promotion layer."
                ),
            },
        }


    # ==========================================================
    # SECTION 17 — SEED OS CONTROLLED DEVELOPMENT /
    #                 KNOWLEDGE FUSION
    # ==========================================================
    #
    # PURPOSE:
    #   Make DEVHUD the creator-facing development input point into
    #   the existing SEED OS intelligence fabric.
    #
    #   The developer does not manually control individual modules.
    #   The developer teaches, suggests, questions, supplies context,
    #   reports errors, proposes connections, and provides knowledge.
    #
    #   SEED OS receives that input and correlates it with:
    #
    #       Qbit
    #       QbitDialer
    #       QbitQueueLoop
    #       ComputeBrain
    #       TransformerBrain
    #       IntentEngine
    #       ActionEngine
    #       AnalyticsEngine
    #       ThoughtFeedback
    #       SEEDEventBus
    #       TrackSystem
    #       IPCBridge
    #       Oracle
    #       FATHUD
    #       ModuleRegistry
    #       OptionRegistry
    #       init_event knowledge
    #       developer sandbox
    #       capability / adapter proposals
    #       runtime errors
    #       execution results
    #       development history
    #
    # AUTHORITY:
    #   Creator input       = development knowledge / suggestion
    #   DEVHUD              = interface / aggregation
    #   SEED cognition      = interpretation
    #   Oracle              = observation / governance
    #   QbitDialer          = command authority
    #   QbitQueueLoop       = execution / transport
    #   EventBus            = existing event transport
    #   TrackSystem         = lineage / tracking
    #
    # IMPORTANT:
    #   This section does not create another runtime.
    #   This section does not replace existing authorities.
    #   This section does not execute arbitrary developer text.
    #
    #   It creates the bridge that lets SEED understand the COMPLETE
    #   development context surrounding a creator input.
    # ==========================================================

    def _initialize_seedos_development_fusion(self):
        """
        Initialize the unified development/intelligence input fabric.
        """
        try:
            self._seedos_development_fusion_initialized = True

            self._seedos_development_inputs = []
            self._seedos_development_context = []
            self._seedos_development_errors = []
            self._seedos_development_feedback = []
            self._seedos_development_observations = []

            self._seedos_development_fusion_status = {
                "initialized": True,
                "inputs": 0,
                "context_records": 0,
                "errors": 0,
                "feedback": 0,
                "observations": 0,
                "ipc_bridge": False,
                "oracle": False,
                "fathud": False,
                "init_event": False,
                "cognition": False,
                "registries": False,
                "sandbox": False,
            }

            self._seedos_refresh_development_fusion()

        except Exception as exc:
            self.logger.warning(
                "[DEVHUD] Development fusion initialization failed: %s",
                exc,
            )

            self._seedos_development_fusion_initialized = False

    def _seedos_refresh_development_fusion(self):
        """
        Refresh references to every existing intelligence source.

        This is intentionally reference-based. No subsystem is created.
        """
        try:
            self._seedos_development_fusion_status.update(
                {
                    "ipc_bridge": (
                        getattr(
                            self,
                            "ipc_bridge",
                            None,
                        )
                        is not None
                    ),
                    "oracle": (
                        getattr(
                            self,
                            "oracle",
                            None,
                        )
                        is not None
                        or getattr(
                            self,
                            "oracle_loop",
                            None,
                        )
                        is not None
                    ),
                    "fathud": (
                        getattr(
                            self,
                            "fathud",
                            None,
                        )
                        is not None
                        or getattr(
                            self,
                            "fathud_adapter",
                            None,
                        )
                        is not None
                    ),
                    "init_event": bool(
                        getattr(
                            self,
                            "_seedos_workspace_init_event",
                            None,
                        )
                    ),
                    "cognition": (
                        getattr(
                            self,
                            "qbit_dialer",
                            None,
                        ) is not None
                        and (
                            getattr(
                                self.qbit_dialer,
                                "compute_brain",
                                None,
                            )
                            is not None
                            or getattr(
                                self.qbit_dialer,
                                "transformer_brain",
                                None,
                            )
                            is not None
                        )
                    ),
                    "registries": (
                        getattr(
                            self,
                            "module_registry",
                            None,
                        )
                        is not None
                        or getattr(
                            self,
                            "option_registry",
                            None,
                        )
                        is not None
                    ),
                    "sandbox": getattr(
                        self,
                        "_seedos_validation_initialized",
                        False,
                    ),
                }
            )

            return dict(
                self._seedos_development_fusion_status
            )

        except Exception as exc:
            self.logger.debug(
                "[DEVHUD] Development fusion refresh failed: %s",
                exc,
            )

            return {}

    def _seedos_collect_system_context(self):
        """
        Collect a normalized snapshot of the existing SEED OS
        development environment.

        The result is context for cognition/learning, not a command.
        """
        try:
            self._seedos_refresh_development_fusion()

            runtime = (
                getattr(
                    self,
                    "_seedos_workspace_runtime",
                    {},
                )
                or {}
            )

            init_event = (
                getattr(
                    self,
                    "_seedos_workspace_init_event",
                    {},
                )
                or {}
            )

            registry = (
                getattr(
                    self,
                    "_seedos_workspace_registry",
                    {},
                )
                or {}
            )

            capability_map = {}

            get_capabilities = getattr(
                self,
                "get_seedos_capability_map",
                None,
            )

            if callable(get_capabilities):
                result = get_capabilities()

                if isinstance(result, dict):
                    capability_map = result

            context = {
                "timestamp": time.time(),
                "interface": "DEVHUD",
                "runtime": {
                    name: (
                        type(value).__name__
                        if value is not None
                        else None
                    )
                    for name, value in runtime.items()
                },
                "authorities": {
                    "command": "QbitDialer",
                    "execution": "QbitQueueLoop",
                    "transport": "SEEDEventBus",
                    "tracking": "TrackSystem",
                    "observation": "Oracle",
                    "developer_interface": "DEVHUD",
                },
                "registries": registry,
                "capabilities": capability_map,
                "init_event": init_event,
                "fusion_status": dict(
                    self._seedos_development_fusion_status
                ),
            }

            self._seedos_development_context.append(
                context
            )

            if len(
                self._seedos_development_context
            ) > 250:
                self._seedos_development_context = (
                    self._seedos_development_context[
                        -250:
                    ]
                )

            self._seedos_development_fusion_status[
                "context_records"
            ] = len(
                self._seedos_development_context
            )

            return context

        except Exception as exc:
            self.logger.warning(
                "[DEVHUD] System context collection failed: %s",
                exc,
            )

            return {
                "status": "ERROR",
                "error": str(exc),
            }

    def _seedos_build_developer_input_envelope(
        self,
        text,
        *,
        mode="SUGGEST",
        target="",
        metadata=None,
    ):
        """
        Normalize creator input into a SEED development envelope.

        This is the key convergence object for the developer interface.
        """
        try:
            text = str(text).strip()

            mode = (
                str(mode).strip().upper()
                or "SUGGEST"
            )

            target = str(
                target or ""
            ).strip()

            context = (
                self._seedos_collect_system_context()
            )

            envelope = {
                "input_id": (
                    "DEV."
                    + uuid.uuid4().hex
                ),
                "source": "DEVHUD",
                "interface": "DEVELOPER_WORKSPACE",
                "mode": mode,
                "target": target,
                "text": text,
                "creator_input": True,
                "developer_proposal": True,
                "timestamp": time.time(),
                "authority": "SEED_OS_EVALUATION",
                "context": context,
                "metadata": (
                    dict(metadata)
                    if isinstance(
                        metadata,
                        dict,
                    )
                    else {}
                ),
                "execution_requested": False,
                "direct_execution": False,
            }

            return envelope

        except Exception as exc:
            self.logger.warning(
                "[DEVHUD] Developer envelope creation failed: %s",
                exc,
            )

            return {
                "status": "ERROR",
                "error": str(exc),
            }

    def _seedos_submit_developer_input(
        self,
        text,
        *,
        mode="SUGGEST",
        target="",
        metadata=None,
    ):
        """
        Main creator-facing input bridge.

        Every developer input gets:
            1. normalized
            2. system context attached
            3. development history recorded
            4. SEED_INPUT emitted
            5. Oracle observation offered
            6. existing cognitive pipeline allowed to interpret it
        """
        try:
            envelope = (
                self._seedos_build_developer_input_envelope(
                    text,
                    mode=mode,
                    target=target,
                    metadata=metadata,
                )
            )

            if envelope.get("status") == "ERROR":
                return envelope

            self._seedos_development_inputs.append(
                envelope
            )

            if len(
                self._seedos_development_inputs
            ) > 500:
                self._seedos_development_inputs = (
                    self._seedos_development_inputs[
                        -500:
                    ]
                )

            self._seedos_development_fusion_status[
                "inputs"
            ] = len(
                self._seedos_development_inputs
            )

            self._seedos_record_development_input(
                envelope
            )

            self._seedos_observe_developer_input(
                envelope
            )

            self._seedos_emit_developer_input(
                envelope
            )

            return {
                "status": "submitted",
                "input_id": envelope[
                    "input_id"
                ],
                "mode": envelope[
                    "mode"
                ],
                "target": envelope[
                    "target"
                ],
            }

        except Exception as exc:
            self.logger.warning(
                "[DEVHUD] Developer input submission failed: %s",
                exc,
            )

            return {
                "status": "ERROR",
                "error": str(exc),
            }

    def _seedos_emit_developer_input(
        self,
        envelope,
    ):
        """
        Send the normalized developer input through the EXISTING
        EventBus as SEED_INPUT.

        No Qbit is constructed here.
        """
        try:
            event_bus = getattr(
                self,
                "event_bus",
                None,
            )

            if event_bus is None:
                return False

            emit = getattr(
                event_bus,
                "emit",
                None,
            )

            if not callable(emit):
                return False

            emit(
                "SEED_INPUT",
                envelope,
            )

            return True

        except Exception as exc:
            self.logger.debug(
                "[DEVHUD] SEED_INPUT emission failed: %s",
                exc,
            )

            return False

    def _seedos_record_development_input(
        self,
        envelope,
    ):
        """
        Record developer input as development lineage.
        """
        try:
            record = {
                "event": "DEVELOPER_INPUT",
                "input_id": envelope.get(
                    "input_id"
                ),
                "mode": envelope.get(
                    "mode"
                ),
                "target": envelope.get(
                    "target"
                ),
                "text": envelope.get(
                    "text"
                ),
                "timestamp": envelope.get(
                    "timestamp"
                ),
            }

            history = getattr(
                self,
                "_seedos_development_history",
                None,
            )

            if not isinstance(
                history,
                list,
            ):
                history = []
                self._seedos_development_history = (
                    history
                )

            history.append(
                record
            )

            if len(history) > 500:
                del history[:-500]

            remember = getattr(
                self,
                "_remember_development_event",
                None,
            )

            if callable(remember):
                remember(
                    record
                )

            return record

        except Exception as exc:
            self.logger.debug(
                "[DEVHUD] Development input record failed: %s",
                exc,
            )

            return None

    def _seedos_observe_developer_input(
        self,
        envelope,
    ):
        """
        Send the input into the existing Oracle observation lane
        when Oracle is already attached.
        """
        try:
            oracle = getattr(
                self,
                "oracle",
                None,
            )

            if oracle is None:
                oracle = getattr(
                    self,
                    "oracle_loop",
                    None,
                )

            if oracle is None:
                return {
                    "available": False,
                }

            self._seedos_development_observations.append(
                {
                    "type": "developer_input",
                    "input_id": envelope.get(
                        "input_id"
                    ),
                    "mode": envelope.get(
                        "mode"
                    ),
                    "target": envelope.get(
                        "target"
                    ),
                    "timestamp": time.time(),
                }
            )

            observe = getattr(
                oracle,
                "observe",
                None,
            )

            if callable(observe):
                try:
                    result = observe(
                        envelope
                    )

                    return {
                        "available": True,
                        "result": result,
                    }

                except TypeError:
                    pass

            record = getattr(
                oracle,
                "record",
                None,
            )

            if callable(record):
                try:
                    result = record(
                        envelope
                    )

                    return {
                        "available": True,
                        "result": result,
                    }

                except TypeError:
                    pass

            return {
                "available": True,
                "observed": True,
            }

        except Exception as exc:
            return {
                "available": False,
                "error": str(exc),
            }

    def _seedos_capture_runtime_error(
        self,
        error,
        *,
        source="runtime",
        qbit_id=None,
        task_id=None,
        track_id=None,
        metadata=None,
    ):
        """
        Convert runtime errors into development knowledge.

        Errors become inspectable learning context rather than merely
        disappearing into the log.
        """
        try:
            record = {
                "error_id": (
                    "ERR."
                    + uuid.uuid4().hex
                ),
                "source": source,
                "error": str(error),
                "error_type": type(
                    error
                ).__name__,
                "qbit_id": qbit_id,
                "task_id": task_id,
                "track_id": track_id,
                "timestamp": time.time(),
                "metadata": (
                    dict(metadata)
                    if isinstance(
                        metadata,
                        dict,
                    )
                    else {}
                ),
            }

            self._seedos_development_errors.append(
                record
            )

            if len(
                self._seedos_development_errors
            ) > 500:
                self._seedos_development_errors = (
                    self._seedos_development_errors[
                        -500:
                    ]
                )

            self._seedos_development_fusion_status[
                "errors"
            ] = len(
                self._seedos_development_errors
            )

            self._seedos_emit_developer_input(
                self._seedos_build_developer_input_envelope(
                    (
                        "Runtime error observed: "
                        + str(error)
                    ),
                    mode="REVIEW",
                    target=source,
                    metadata={
                        "runtime_error": True,
                        "error_record": record,
                    },
                )
            )

            return record

        except Exception as exc:
            self.logger.debug(
                "[DEVHUD] Runtime error capture failed: %s",
                exc,
            )

            return {
                "status": "ERROR",
                "error": str(exc),
            }

    def _seedos_capture_development_feedback(
        self,
        feedback,
        *,
        source="developer",
        target="",
        metadata=None,
    ):
        """
        Record feedback as first-class development information.
        """
        try:
            record = {
                "feedback_id": (
                    "FDBK."
                    + uuid.uuid4().hex
                ),
                "feedback": str(
                    feedback
                ),
                "source": source,
                "target": target,
                "timestamp": time.time(),
                "metadata": (
                    dict(metadata)
                    if isinstance(
                        metadata,
                        dict,
                    )
                    else {}
                ),
            }

            self._seedos_development_feedback.append(
                record
            )

            if len(
                self._seedos_development_feedback
            ) > 500:
                self._seedos_development_feedback = (
                    self._seedos_development_feedback[
                        -500:
                    ]
                )

            self._seedos_development_fusion_status[
                "feedback"
            ] = len(
                self._seedos_development_feedback
            )

            self._seedos_emit_developer_input(
                self._seedos_build_developer_input_envelope(
                    str(feedback),
                    mode="TEACH",
                    target=target,
                    metadata={
                        "feedback": True,
                        "feedback_record": record,
                        **(
                            metadata
                            if isinstance(
                                metadata,
                                dict,
                            )
                            else {}
                        ),
                    },
                )
            )

            return record

        except Exception as exc:
            self.logger.debug(
                "[DEVHUD] Development feedback capture failed: %s",
                exc,
            )

            return {
                "status": "ERROR",
                "error": str(exc),
            }

    def seedos_develop(
        self,
        text,
        *,
        target="",
        mode="DEVELOP",
        metadata=None,
    ):
        """
        Public creator/developer entry point.

        This is the method the future Developer Workspace can call
        regardless of whether the input is teaching, suggesting,
        inspecting, connecting, testing, or growing SEED.
        """
        return self._seedos_submit_developer_input(
            text,
            mode=mode,
            target=target,
            metadata=metadata,
        )

    def seedos_teach_system(
        self,
        text,
        *,
        target="",
        metadata=None,
    ):
        """
        Explicit teaching entry point.
        """
        return self._seedos_submit_developer_input(
            text,
            mode="TEACH",
            target=target,
            metadata=metadata,
        )

    def seedos_report_error(
        self,
        error,
        *,
        source="developer",
        target="",
        metadata=None,
    ):
        """
        Allow the creator to teach SEED from an observed error.
        """
        return self._seedos_capture_runtime_error(
            error,
            source=source,
            metadata={
                "developer_reported": True,
                "target": target,
                **(
                    metadata
                    if isinstance(
                        metadata,
                        dict,
                    )
                    else {}
                ),
            },
        )

    def seedos_feedback(
        self,
        feedback,
        *,
        target="",
        metadata=None,
    ):
        """
        Explicit creator feedback path.
        """
        return self._seedos_capture_development_feedback(
            feedback,
            target=target,
            metadata=metadata,
        )

    def seedos_development_snapshot(self):
        """
        Return the complete developer-facing intelligence snapshot.
        """
        try:
            return {
                "status": "ok",
                "fusion": dict(
                    self._seedos_development_fusion_status
                ),
                "runtime": self._seedos_collect_system_context(),
                "inputs": list(
                    self._seedos_development_inputs[
                        -50:
                    ]
                ),
                "errors": list(
                    self._seedos_development_errors[
                        -50:
                    ]
                ),
                "feedback": list(
                    self._seedos_development_feedback[
                        -50:
                    ]
                ),
                "observations": list(
                    self._seedos_development_observations[
                        -50:
                    ]
                ),
                "history": list(
                    getattr(
                        self,
                        "_seedos_development_history",
                        [],
                    )[-50:]
                ),
            }

        except Exception as exc:
            return {
                "status": "ERROR",
                "error": str(exc),
            }

    def seedos_development_context_for_seed(
        self,
    ):
        """
        Build the consolidated context package that can accompany
        developer input into SEED's existing cognitive path.

        This is DATA, not a command.
        """
        snapshot = (
            self.seedos_development_snapshot()
        )

        return {
            "type": "SEED_DEVELOPMENT_CONTEXT",
            "source": "DEVHUD",
            "authority": "SEED_OS_EVALUATION",
            "creator_interface": True,
            "runtime": snapshot,
            "knowledge": getattr(
                self,
                "_seedos_workspace_init_event",
                {},
            ),
            "capabilities": (
                self.get_seedos_capability_map()
                if callable(
                    getattr(
                        self,
                        "get_seedos_capability_map",
                        None,
                    )
                )
                else {}
            ),
            "sandbox": (
                self.seedos_get_validation_status()
                if callable(
                    getattr(
                        self,
                        "seedos_get_validation_status",
                        None,
                    )
                )
                else {}
            ),
        }


# ==========================================================
# SECTION 18 — SEED OS LEARNING COMMAND / ASK / DEVELOPMENT BRIDGE
# ==========================================================
#
# PURPOSE:
#   Give DEVHUD a structured learning-command plane so the
#   Creator can teach, suggest, answer, review, and guide SEED
#   without directly controlling runtime execution.
#
# CORE LOOP:
#
#   Creator
#       ↓
#   DEVHUD
#       ↓
#   Learning Command
#       ↓
#   SEED_INPUT / SEED_ASK / SEED_LEARNING
#       ↓
#   Cognition
#       ↓
#   Track / Evaluate / Learn
#       ↓
#   If blocked → ASK
#       ↓
#   Creator answer / system knowledge
#       ↓
#   Re-evaluate
#       ↓
#   Development proposal
#       ↓
#   ActionEngine proposal
#       ↓
#   QbitDialer authority
#       ↓
#   QbitQueueLoop execution
#
# IMPORTANT:
#   DEVHUD does NOT execute commands directly.
#   DEVHUD creates learning/development input.
#   QbitDialer remains command authority.
#   QbitQueueLoop remains execution authority.
# ==========================================================

    def _initialize_seedos_learning_command_bridge(self):
        """
        Initialize the learning-command plane.

        Learning commands are structured knowledge/development
        requests. They are not runtime execution commands.
        """

        self._seedos_learning_commands = {}
        self._seedos_learning_history = []
        self._seedos_pending_questions = {}
        self._seedos_learning_sequence = 0
        self._seedos_learning_active = True

        self._seedos_learning_command_types = {
            "TEACH": {
                "purpose": "Provide knowledge or a rule to SEED.",
                "requires_answer": False,
                "development": True,
            },
            "SUGGEST": {
                "purpose": "Suggest a possible direction without forcing execution.",
                "requires_answer": False,
                "development": True,
            },
            "ASK": {
                "purpose": "Request clarification or missing knowledge.",
                "requires_answer": True,
                "development": True,
            },
            "ANSWER": {
                "purpose": "Answer an outstanding SEED question.",
                "requires_answer": False,
                "development": True,
            },
            "INSPECT": {
                "purpose": "Request observation or system inspection.",
                "requires_answer": False,
                "development": True,
            },
            "LEARN": {
                "purpose": "Record and correlate knowledge for future reasoning.",
                "requires_answer": False,
                "development": True,
            },
            "DEVELOP": {
                "purpose": "Propose development of a capability or subsystem.",
                "requires_answer": False,
                "development": True,
            },
            "CONNECT": {
                "purpose": "Suggest a relationship between existing systems.",
                "requires_answer": False,
                "development": True,
            },
            "TEST": {
                "purpose": "Request sandbox validation before promotion.",
                "requires_answer": False,
                "development": True,
            },
            "REVIEW": {
                "purpose": "Request review of an existing proposal or result.",
                "requires_answer": False,
                "development": True,
            },
        }

        self._seedos_learning_command_capabilities = {
            "creator_input": True,
            "developer_input": True,
            "seed_ask": True,
            "seed_answer": True,
            "learning_history": True,
            "tracked_learning": True,
            "development_proposals": True,
            "sandbox_validation": True,
            "oracle_observation": True,
            "fathud_observation": True,
            "qbit_authority": True,
            "queue_authority": True,
            "direct_execution": False,
            "direct_qbit_creation": False,
            "runtime_construction": False,
        }

        self._seedos_register_learning_command_events()

    def _seedos_register_learning_command_events(self):
        """
        Register learning events against the existing EventBus.

        No second EventBus is created.
        """

        event_bus = getattr(self, "event_bus", None)

        if event_bus is None:
            return

        subscriptions = {
            "SEED_ASK": self._seedos_on_ask_event,
            "SEED_ANSWER": self._seedos_on_answer_event,
            "SEED_LEARNING": self._seedos_on_learning_event,
            "SEED_DEVELOPMENT_PROPOSAL": self._seedos_on_development_proposal,
            "SEED_INPUT": self._seedos_on_learning_input,
            "SEED_COMMAND_RESULT": self._seedos_on_learning_command_result,
            "SEED_COMMAND_DENIED": self._seedos_on_learning_command_denied,
            "SEED_ERROR": self._seedos_on_learning_error,
        }

        self._seedos_learning_subscriptions = []

        for event_name, handler in subscriptions.items():
            try:
                event_bus.subscribe(event_name, handler)
                self._seedos_learning_subscriptions.append(event_name)
            except Exception as exc:
                self.logger.debug(
                    "[DEVHUD] Learning event subscription skipped | "
                    "event=%s | error=%s",
                    event_name,
                    exc,
                )

    def _seedos_next_learning_id(self, prefix="LEARN"):
        """
        Generate a local learning identifier.

        This is an identifier for the development/learning record,
        not a Qbit identifier.
        """

        self._seedos_learning_sequence = (
            getattr(self, "_seedos_learning_sequence", 0) + 1
        )

        return (
            f"{prefix}."
            f"{int(time.time() * 1000)}."
            f"{self._seedos_learning_sequence}"
        )

    def _seedos_normalize_learning_command(
        self,
        command_type,
        content=None,
        *,
        source="DEVHUD",
        target=None,
        context=None,
        requires_answer=False,
        parent_learning_id=None,
    ):
        """
        Build a canonical learning command.

        This object is data.
        It is not submitted directly to QbitQueueLoop.
        """

        command_type = str(
            command_type or "SUGGEST"
        ).strip().upper()

        if command_type not in self._seedos_learning_command_types:
            command_type = "SUGGEST"

        learning_id = self._seedos_next_learning_id()

        envelope = {
            "learning_id": learning_id,
            "type": command_type,
            "source": source,
            "target": target,
            "content": content,
            "context": context or {},
            "requires_answer": bool(
                requires_answer
                or command_type == "ASK"
            ),
            "parent_learning_id": parent_learning_id,
            "authority": "DEVHUD",
            "execution_required": False,
            "direct_execution": False,
            "qbit_created": False,
            "qbit_authority": "QbitDialer",
            "transport_authority": "QbitQueueLoop",
            "event_authority": "SEEDEventBus",
            "observer_authority": "Oracle",
            "status": "CREATED",
            "created_at": time.time(),
        }

        return envelope

    def _seedos_record_learning_command(self, command):
        """
        Persist the learning command in the DEVHUD development
        workspace and learning history.
        """

        if not isinstance(command, dict):
            return None

        learning_id = command.get("learning_id")

        if not learning_id:
            return None

        self._seedos_learning_commands[learning_id] = dict(command)

        self._seedos_learning_history.append(
            dict(command)
        )

        if len(self._seedos_learning_history) > 1000:
            self._seedos_learning_history = (
                self._seedos_learning_history[-1000:]
            )

        return learning_id

    def _seedos_emit_learning_command(
        self,
        command,
        *,
        event_name="SEED_LEARNING",
    ):
        """
        Send a learning command into the existing SEED EventBus.

        This intentionally does NOT call QbitDialer directly.
        Cognition decides what the learning input means.
        """

        event_bus = getattr(self, "event_bus", None)

        if event_bus is None:
            return False

        if not isinstance(command, dict):
            return False

        try:
            event_bus.emit(
                event_name,
                command,
            )
            return True
        except Exception as exc:
            self.logger.debug(
                "[DEVHUD] Learning event emission failed | "
                "event=%s | error=%s",
                event_name,
                exc,
            )
            return False

    def _seedos_submit_learning_command(
        self,
        command_type,
        content=None,
        *,
        source="DEVHUD",
        target=None,
        context=None,
        requires_answer=False,
        parent_learning_id=None,
    ):
        """
        Canonical entry point for DEVHUD learning commands.
        """

        command = self._seedos_normalize_learning_command(
            command_type,
            content,
            source=source,
            target=target,
            context=context,
            requires_answer=requires_answer,
            parent_learning_id=parent_learning_id,
        )

        self._seedos_record_learning_command(command)

        self._seedos_emit_learning_command(
            command,
            event_name="SEED_LEARNING",
        )

        self._seedos_emit_developer_input(
            command,
        )

        self._seedos_observe_developer_input(
            command,
        )

        return command

    def seedos_teach_learning(self, knowledge, *, target=None, context=None):
        """
        Creator → SEED teaching path.
        """

        return self._seedos_submit_learning_command(
            "TEACH",
            knowledge,
            target=target,
            context=context,
        )

    def seedos_suggest_learning(
        self,
        suggestion,
        *,
        target=None,
        context=None,
    ):
        """
        Creator → SEED suggestion path.

        A suggestion never becomes an execution command merely
        because DEVHUD submitted it.
        """

        return self._seedos_submit_learning_command(
            "SUGGEST",
            suggestion,
            target=target,
            context=context,
        )

    def seedos_learn(
        self,
        knowledge,
        *,
        source="DEVHUD",
        target=None,
        context=None,
        parent_learning_id=None,
    ):
        """
        Explicit learning record.

        Useful when SEED has already observed or derived
        information and the Creator wants that information
        correlated into the development workspace.
        """

        return self._seedos_submit_learning_command(
            "LEARN",
            knowledge,
            source=source,
            target=target,
            context=context,
            parent_learning_id=parent_learning_id,
        )

    def seedos_develop_learning(
        self,
        development_request,
        *,
        target=None,
        context=None,
        parent_learning_id=None,
    ):
        """
        Request development of a capability/system.

        The request enters the development pipeline.
        It does not modify code or start a runtime.
        """

        return self._seedos_submit_learning_command(
            "DEVELOP",
            development_request,
            target=target,
            context=context,
            parent_learning_id=parent_learning_id,
        )

    def seedos_connect_learning(
        self,
        connection_request,
        *,
        target=None,
        context=None,
        parent_learning_id=None,
    ):
        """
        Suggest a relationship between existing SEED systems.
        """

        return self._seedos_submit_learning_command(
            "CONNECT",
            connection_request,
            target=target,
            context=context,
            parent_learning_id=parent_learning_id,
        )

    def seedos_inspect_learning(
        self,
        inspection_request,
        *,
        target=None,
        context=None,
        parent_learning_id=None,
    ):
        """
        Ask SEED to inspect a system or capability.
        """

        return self._seedos_submit_learning_command(
            "INSPECT",
            inspection_request,
            target=target,
            context=context,
            parent_learning_id=parent_learning_id,
        )

    def seedos_test_learning(
        self,
        test_request,
        *,
        target=None,
        context=None,
        parent_learning_id=None,
    ):
        """
        Send a development test request into the sandbox path.
        """

        return self._seedos_submit_learning_command(
            "TEST",
            test_request,
            target=target,
            context=context,
            parent_learning_id=parent_learning_id,
        )

    def seedos_review_learning(
        self,
        review_request,
        *,
        target=None,
        context=None,
        parent_learning_id=None,
    ):
        """
        Request review of a development result/proposal.
        """

        return self._seedos_submit_learning_command(
            "REVIEW",
            review_request,
            target=target,
            context=context,
            parent_learning_id=parent_learning_id,
        )

    def seedos_ask(
        self,
        question,
        *,
        target=None,
        context=None,
        parent_learning_id=None,
        reason=None,
    ):
        """
        FIRST-CLASS ASK PATH.

        When SEED cannot safely determine how to proceed, it can
        create an ASK learning command.

        The question becomes tracked state instead of an error.

        SEED may then:
            ASK
              ↓
            receive answer
              ↓
            LEARN
              ↓
            reassess
              ↓
            DEVELOP / TEST / SUGGEST
              ↓
            action proposal if appropriate
        """

        command = self._seedos_submit_learning_command(
            "ASK",
            question,
            target=target,
            context=context,
            requires_answer=True,
            parent_learning_id=parent_learning_id,
        )

        question_id = command["learning_id"]

        command["status"] = "WAITING_FOR_ANSWER"
        command["reason"] = reason

        self._seedos_pending_questions[question_id] = {
            "question_id": question_id,
            "learning_id": question_id,
            "question": question,
            "target": target,
            "context": context or {},
            "reason": reason,
            "parent_learning_id": parent_learning_id,
            "created_at": time.time(),
            "status": "WAITING_FOR_ANSWER",
        }

        self._seedos_learning_commands[question_id] = dict(
            command
        )

        self._seedos_emit_learning_command(
            command,
            event_name="SEED_ASK",
        )

        return command

    def seedos_answer(
        self,
        question_id,
        answer,
        *,
        context=None,
    ):
        """
        Creator/system answer path.

        The answer is linked to the exact outstanding question,
        allowing SEED to correlate the new information.
        """

        question = self._seedos_pending_questions.get(
            question_id
        )

        if question is None:
            return {
                "status": "unknown_question",
                "question_id": question_id,
            }

        command = self._seedos_normalize_learning_command(
            "ANSWER",
            answer,
            source="CREATOR",
            target=question.get("target"),
            context={
                "question_id": question_id,
                "question": question.get("question"),
                "original_context": question.get(
                    "context",
                    {},
                ),
                **(context or {}),
            },
            parent_learning_id=question_id,
        )

        command["status"] = "ANSWERED"

        question["status"] = "ANSWERED"
        question["answered_at"] = time.time()
        question["answer_learning_id"] = command[
            "learning_id"
        ]

        self._seedos_record_learning_command(command)

        self._seedos_emit_learning_command(
            command,
            event_name="SEED_ANSWER",
        )

        # Turn the answer into explicit learning context.
        self.seedos_learn(
            {
                "question": question.get("question"),
                "answer": answer,
                "question_id": question_id,
                "source": "CREATOR",
            },
            source="CREATOR",
            target=question.get("target"),
            context=context,
            parent_learning_id=question_id,
        )

        return command

    def _seedos_on_ask_event(self, event=None, *args, **kwargs):
        """
        Observe SEED-generated questions.
        """

        payload = event

        if not isinstance(payload, dict):
            payload = {
                "event": event,
                "args": args,
                "kwargs": kwargs,
            }

        self._seedos_last_ask = payload

        try:
            self.push_message(
                "SEED ASK: "
                + str(
                    payload.get(
                        "content",
                        payload.get(
                            "question",
                            payload,
                        ),
                    )
                )
            )
        except Exception:
            pass

        return payload

    def _seedos_on_answer_event(self, event=None, *args, **kwargs):
        """
        Observe answers entering the learning system.
        """

        payload = event

        if not isinstance(payload, dict):
            payload = {
                "event": event,
                "args": args,
                "kwargs": kwargs,
            }

        self._seedos_last_answer = payload

        return payload

    def _seedos_on_learning_event(self, event=None, *args, **kwargs):
        """
        Observe learning records.
        """

        payload = event

        if not isinstance(payload, dict):
            payload = {
                "event": event,
                "args": args,
                "kwargs": kwargs,
            }

        self._seedos_last_learning_event = payload

        return payload

    def _seedos_on_learning_input(self, event=None, *args, **kwargs):
        """
        Observe the common SEED_INPUT channel.

        This does not execute anything.
        """

        payload = event

        if not isinstance(payload, dict):
            payload = {
                "event": event,
                "args": args,
                "kwargs": kwargs,
            }

        self._seedos_last_learning_input = payload

        return payload

    def _seedos_on_development_proposal(
        self,
        event=None,
        *args,
        **kwargs,
    ):
        """
        Track development proposals generated from learning.
        """

        payload = event

        if not isinstance(payload, dict):
            payload = {
                "event": event,
                "args": args,
                "kwargs": kwargs,
            }

        self._seedos_last_development_proposal = payload

        return payload

    def _seedos_on_learning_command_result(
        self,
        event=None,
        *args,
        **kwargs,
    ):
        """
        Observe results without becoming execution authority.
        """

        payload = event

        if not isinstance(payload, dict):
            payload = {
                "event": event,
                "args": args,
                "kwargs": kwargs,
            }

        self._seedos_last_learning_result = payload

        return payload

    def _seedos_on_learning_command_denied(
        self,
        event=None,
        *args,
        **kwargs,
    ):
        """
        A denied command becomes learning information.

        Denial is not treated as a dead end.
        SEED can inspect why it was denied and ASK for
        whatever information or authorization is missing.
        """

        payload = event

        if not isinstance(payload, dict):
            payload = {
                "event": event,
                "args": args,
                "kwargs": kwargs,
            }

        self._seedos_last_learning_denial = payload

        return payload

    def _seedos_on_learning_error(
        self,
        event=None,
        *args,
        **kwargs,
    ):
        """
        Convert development/runtime errors into tracked learning
        context rather than silently losing them.
        """

        payload = event

        if not isinstance(payload, dict):
            payload = {
                "event": event,
                "args": args,
                "kwargs": kwargs,
            }

        self._seedos_last_learning_error = payload

        return payload

    def _seedos_learning_command_for_seed(
        self,
        command,
    ):
        """
        Produce the cognition-facing representation of a learning
        command.

        The command remains advisory data.
        """

        if not isinstance(command, dict):
            return None

        return {
            "learning_id": command.get("learning_id"),
            "type": command.get("type"),
            "content": command.get("content"),
            "source": command.get("source"),
            "target": command.get("target"),
            "context": command.get("context", {}),
            "requires_answer": command.get(
                "requires_answer",
                False,
            ),
            "parent_learning_id": command.get(
                "parent_learning_id"
            ),
            "status": command.get("status"),
            "development": True,
            "execution_required": False,
            "authority": "DEVHUD_INPUT",
            "next_authority": "SEED_COGNITION",
            "command_authority": "QbitDialer",
            "transport_authority": "QbitQueueLoop",
        }

    def _seedos_learning_command_to_development(
        self,
        command,
    ):
        """
        Convert learning knowledge into a development proposal
        only after cognition/development logic determines that
        development is appropriate.
        """

        if not isinstance(command, dict):
            return None

        command_type = str(
            command.get("type", "")
        ).upper()

        if command_type not in {
            "DEVELOP",
            "CONNECT",
            "TEST",
            "SUGGEST",
            "TEACH",
            "LEARN",
        }:
            return None

        return {
            "proposal_id": self._seedos_next_learning_id(
                "DEV"
            ),
            "learning_id": command.get(
                "learning_id"
            ),
            "proposal_type": command_type,
            "target": command.get("target"),
            "content": command.get("content"),
            "context": command.get("context", {}),
            "parent_learning_id": command.get(
                "parent_learning_id"
            ),
            "status": "PROPOSED",
            "execution_required": False,
            "authority": "SEED_DEVELOPMENT",
            "command_authority": "QbitDialer",
            "validation_authority": "SEEDOS_SANDBOX",
        }

    def seedos_learning_command(
        self,
        command_type,
        content=None,
        *,
        target=None,
        context=None,
        requires_answer=False,
    ):
        """
        Generic public learning-command interface.

        This gives the developer workspace one simple entry point
        while preserving explicit command types internally.
        """

        return self._seedos_submit_learning_command(
            command_type,
            content,
            target=target,
            context=context,
            requires_answer=requires_answer,
        )

    def seedos_learning_status(self):
        """
        Return current learning/ASK/development state.
        """

        pending = []

        for question_id, question in (
            self._seedos_pending_questions.items()
        ):
            if question.get("status") == "WAITING_FOR_ANSWER":
                pending.append(
                    {
                        "question_id": question_id,
                        "question": question.get(
                            "question"
                        ),
                        "target": question.get(
                            "target"
                        ),
                        "reason": question.get(
                            "reason"
                        ),
                        "created_at": question.get(
                            "created_at"
                        ),
                    }
                )

        return {
            "active": bool(
                getattr(
                    self,
                    "_seedos_learning_active",
                    False,
                )
            ),
            "learning_commands": len(
                getattr(
                    self,
                    "_seedos_learning_commands",
                    {},
                )
            ),
            "learning_history": len(
                getattr(
                    self,
                    "_seedos_learning_history",
                    [],
                )
            ),
            "pending_questions": len(pending),
            "questions": pending,
            "command_types": list(
                getattr(
                    self,
                    "_seedos_learning_command_types",
                    {},
                ).keys()
            ),
            "qbit_authority": "QbitDialer",
            "transport_authority": "QbitQueueLoop",
            "event_authority": "SEEDEventBus",
            "observer_authority": "Oracle",
            "direct_execution": False,
        }

    def seedos_get_learning_context(self):
        """
        Full developer/cognition context for the current learning
        session.

        Combines the last development-fusion context with the
        current learning/ASK state.
        """

        base_context = {}

        try:
            base_context = (
                self.seedos_development_context_for_seed()
                or {}
            )
        except Exception:
            base_context = {}

        return {
            "development_context": base_context,
            "learning_status": (
                self.seedos_learning_status()
            ),
            "last_ask": getattr(
                self,
                "_seedos_last_ask",
                None,
            ),
            "last_answer": getattr(
                self,
                "_seedos_last_answer",
                None,
            ),
            "last_learning": getattr(
                self,
                "_seedos_last_learning_event",
                None,
            ),
            "last_proposal": getattr(
                self,
                "_seedos_last_development_proposal",
                None,
            ),
        }

    def seedos_resolve_blocked_state(
        self,
        blocked_reason,
        *,
        target=None,
        context=None,
        parent_learning_id=None,
    ):
        """
        Convert an inability to proceed into an ASK instead of
        forcing an action.

        This is the central "if SEED can't move, let it ask"
        mechanism.
        """

        question = (
            "SEED requires additional information before proceeding. "
            f"Blocked reason: {blocked_reason}"
        )

        return self.seedos_ask(
            question,
            target=target,
            context={
                "blocked_reason": blocked_reason,
                "developer_context": (
                    context or {}
                ),
            },
            parent_learning_id=parent_learning_id,
            reason=blocked_reason,
        )

    def seedos_continue_after_answer(
        self,
        question_id,
        answer,
        *,
        context=None,
    ):
        """
        Answer → learn → continue development.

        This does not bypass cognition or command authority.
        """

        answer_command = self.seedos_answer(
            question_id,
            answer,
            context=context,
        )

        if answer_command.get("status") != "ANSWERED":
            return answer_command

        return {
            "status": "LEARNED_AND_READY_FOR_REASSESSMENT",
            "question_id": question_id,
            "answer_learning_id": answer_command.get(
                "learning_id"
            ),
            "next_stage": "SEED_COGNITION_REASSESS",
            "command_authority": "QbitDialer",
            "transport_authority": "QbitQueueLoop",
            "execution_started": False,
        }

    def seedos_learning_history(self, limit=100):
        """
        Return recent learning commands for the developer
        workspace.
        """

        history = getattr(
            self,
            "_seedos_learning_history",
            [],
        )

        try:
            limit = max(1, int(limit))
        except Exception:
            limit = 100

        return list(history[-limit:])

    def seedos_learning_snapshot(self):
        """
        Snapshot consumed by DEVHUD, Oracle observation, and
        future developer tooling.
        """

        return {
            "status": self.seedos_learning_status(),
            "history": self.seedos_learning_history(
                100
            ),
            "pending_questions": dict(
                getattr(
                    self,
                    "_seedos_pending_questions",
                    {},
                )
            ),
            "last_ask": getattr(
                self,
                "_seedos_last_ask",
                None,
            ),
            "last_answer": getattr(
                self,
                "_seedos_last_answer",
                None,
            ),
            "last_learning": getattr(
                self,
                "_seedos_last_learning_event",
                None,
            ),
            "last_development_proposal": getattr(
                self,
                "_seedos_last_development_proposal",
                None,
            ),
        }



# ==========================================================
# SECTION 19 — SEED OS DEFINITION MAP / PLAN LINK /
#              DEVELOPMENT TRACKER
# ==========================================================
#
# PURPOSE:
#   Connect the DEVHUD methods/defs already present in this
#   development stream to one living SEED OS development plan.
#
# DESIGN:
#
#   DEF
#    ↓
#   READ / DESCRIBE
#    ↓
#   SYSTEM
#    ↓
#   CAPABILITY
#    ↓
#   PLAN STEP
#    ↓
#   DEPENDENCIES
#    ↓
#   VALIDATION
#    ↓
#   UPDATE
#    ↓
#   NEXT STEP
#
# IMPORTANT:
#   This layer READS definitions.
#   It does not execute arbitrary definitions.
#   It does not mutate runtime architecture.
#   It does not create Qbits.
#   It does not create another EventBus.
#   It does not start external systems.
#
# AUTHORITY:
#   DEVHUD      = developer observation / proposal interface
#   SEED        = cognition / evaluation
#   Oracle      = observation / governance
#   QbitDialer  = command authority
#   QueueLoop   = execution / transport authority
#
# ==========================================================

    def _initialize_seedos_definition_plan(self):
        """
        Initialize the living definition → plan mapping.

        The plan is intentionally data-driven so DEVHUD can
        inspect what has already been built and identify what
        remains without executing definitions.
        """

        self._seedos_definition_map = {}
        self._seedos_development_plan = {}
        self._seedos_plan_updates = []
        self._seedos_plan_sequence = 0

        self._seedos_plan_steps = {
            "FOUNDATION": {
                "title": "SEED OS architecture foundation",
                "status": "ESTABLISHED",
                "systems": [
                    "QbitDialer",
                    "QbitQueueLoop",
                    "SEEDEventBus",
                    "TrackSystem",
                ],
            },
            "COGNITION": {
                "title": "Cognitive processing pipeline",
                "status": "ESTABLISHED",
                "systems": [
                    "ComputeBrain",
                    "TransformerBrain",
                    "IntentEngine",
                    "ActionEngine",
                    "AnalyticsEngine",
                    "ThoughtFeedback",
                ],
            },
            "DEVELOPER_SANDBOX": {
                "title": "Developer sandbox and validation",
                "status": "ESTABLISHED",
                "systems": [
                    "DEVHUD",
                    "SeedOSDeveloperSandbox",
                    "CapabilityBuilder",
                    "SandboxValidation",
                ],
            },
            "KNOWLEDGE_FUSION": {
                "title": "Developer knowledge and system context fusion",
                "status": "ESTABLISHED",
                "systems": [
                    "DEVHUD",
                    "SeedInitEvent",
                    "Oracle",
                    "FATHUD",
                    "MemoryCrystallizer",
                ],
            },
            "LEARNING_COMMANDS": {
                "title": "Learning command and ASK loop",
                "status": "ESTABLISHED",
                "systems": [
                    "DEVHUD",
                    "SEED_INPUT",
                    "SEED_ASK",
                    "SEED_ANSWER",
                    "SEED_LEARNING",
                ],
            },
            "DEFINITION_PLAN": {
                "title": "Definition mapping and development planning",
                "status": "ACTIVE",
                "systems": [
                    "DEVHUD",
                    "DeveloperWorkspace",
                    "SandboxValidation",
                    "LearningCommandBridge",
                ],
            },
            "DYNAMIC_EXPANSION": {
                "title": "Controlled dynamic system expansion",
                "status": "NEXT",
                "systems": [
                    "ModuleRegistry",
                    "OptionRegistry",
                    "CapabilityBuilder",
                    "SDK",
                    "MCP",
                    "Provider",
                    "Adapter",
                ],
            },
            "SELF_DEVELOPMENT": {
                "title": "SEED-guided development loop",
                "status": "PLANNED",
                "systems": [
                    "ASK",
                    "LEARN",
                    "DEVELOP",
                    "TEST",
                    "REVIEW",
                    "PROMOTE",
                ],
            },
        }

        self._seedos_register_known_definition_plan()

    def _seedos_register_known_definition_plan(self):
        """
        Register the major defs created by the developer workspace
        work so far.

        These entries describe purpose and relationships.
        They do not execute the methods.
        """

        definitions = {
            # --------------------------------------------------
            # DEVELOPER WORKSPACE
            # --------------------------------------------------

            "_initialize_seedos_developer_workspace": {
                "system": "DeveloperWorkspace",
                "capability": "developer_workspace",
                "plan_step": "KNOWLEDGE_FUSION",
                "role": "initialization",
                "reads": [
                    "existing runtime references",
                    "init_event knowledge",
                ],
                "produces": [
                    "developer workspace state",
                ],
            },

            "_seedos_load_init_event_knowledge": {
                "system": "SeedInitEvent",
                "capability": "knowledge_ingestion",
                "plan_step": "KNOWLEDGE_FUSION",
                "role": "knowledge_bridge",
                "reads": [
                    "init_event.py knowledge",
                    "runtime capability descriptions",
                ],
                "produces": [
                    "SEED system knowledge",
                    "AI baseline knowledge",
                ],
            },

            # --------------------------------------------------
            # CAPABILITY BUILDER
            # --------------------------------------------------

            "_initialize_seedos_capability_builder": {
                "system": "CapabilityBuilder",
                "capability": "dynamic_capability_design",
                "plan_step": "DYNAMIC_EXPANSION",
                "role": "initialization",
                "reads": [
                    "known SEED systems",
                    "SDK metadata",
                    "MCP metadata",
                ],
                "produces": [
                    "capability descriptors",
                    "development proposals",
                ],
            },

            "build_seedos_adapter": {
                "system": "CapabilityBuilder",
                "capability": "adapter_design",
                "plan_step": "DYNAMIC_EXPANSION",
                "role": "builder",
                "reads": [
                    "provider requirements",
                    "system context",
                ],
                "produces": [
                    "adapter proposal",
                ],
            },

            "build_seedos_provider": {
                "system": "CapabilityBuilder",
                "capability": "provider_design",
                "plan_step": "DYNAMIC_EXPANSION",
                "role": "builder",
                "reads": [
                    "provider requirements",
                    "authority boundaries",
                ],
                "produces": [
                    "provider proposal",
                ],
            },

            "build_seedos_sdk": {
                "system": "CapabilityBuilder",
                "capability": "sdk_design",
                "plan_step": "DYNAMIC_EXPANSION",
                "role": "builder",
                "reads": [
                    "SDK capability metadata",
                ],
                "produces": [
                    "SDK proposal",
                ],
            },

            "build_seedos_mcp": {
                "system": "CapabilityBuilder",
                "capability": "mcp_design",
                "plan_step": "DYNAMIC_EXPANSION",
                "role": "builder",
                "reads": [
                    "MCP capability metadata",
                ],
                "produces": [
                    "MCP proposal",
                ],
            },

            # --------------------------------------------------
            # SANDBOX VALIDATION
            # --------------------------------------------------

            "_initialize_seedos_sandbox_validation": {
                "system": "SandboxValidation",
                "capability": "development_validation",
                "plan_step": "DEVELOPER_SANDBOX",
                "role": "initialization",
                "reads": [
                    "development proposals",
                    "runtime bindings",
                    "authority metadata",
                ],
                "produces": [
                    "validation sessions",
                ],
            },

            "seedos_test_capability": {
                "system": "SandboxValidation",
                "capability": "capability_test",
                "plan_step": "DEVELOPER_SANDBOX",
                "role": "validator",
                "reads": [
                    "capability proposal",
                ],
                "produces": [
                    "validation result",
                ],
            },

            "seedos_review_test": {
                "system": "SandboxValidation",
                "capability": "validation_review",
                "plan_step": "SELF_DEVELOPMENT",
                "role": "reviewer",
                "reads": [
                    "validation result",
                    "authority checks",
                ],
                "produces": [
                    "review state",
                    "development feedback",
                ],
            },

            # --------------------------------------------------
            # DEVELOPMENT FUSION
            # --------------------------------------------------

            "_initialize_seedos_development_fusion": {
                "system": "DevelopmentFusion",
                "capability": "system_context_fusion",
                "plan_step": "KNOWLEDGE_FUSION",
                "role": "initialization",
                "reads": [
                    "runtime systems",
                    "registries",
                    "Oracle",
                    "FATHUD",
                    "init_event knowledge",
                ],
                "produces": [
                    "developer input envelope",
                ],
            },

            "seedos_develop": {
                "system": "DevelopmentFusion",
                "capability": "developer_development_request",
                "plan_step": "SELF_DEVELOPMENT",
                "role": "development_input",
                "reads": [
                    "developer request",
                    "system context",
                ],
                "produces": [
                    "development input",
                ],
            },

            "seedos_teach_system": {
                "system": "DevelopmentFusion",
                "capability": "system_teaching",
                "plan_step": "LEARNING_COMMANDS",
                "role": "teaching_input",
                "reads": [
                    "creator knowledge",
                    "system context",
                ],
                "produces": [
                    "learning input",
                ],
            },

            "seedos_report_error": {
                "system": "DevelopmentFusion",
                "capability": "error_learning",
                "plan_step": "LEARNING_COMMANDS",
                "role": "error_input",
                "reads": [
                    "runtime/development error",
                ],
                "produces": [
                    "development learning record",
                ],
            },

            "seedos_feedback": {
                "system": "DevelopmentFusion",
                "capability": "development_feedback",
                "plan_step": "SELF_DEVELOPMENT",
                "role": "feedback_input",
                "reads": [
                    "developer feedback",
                    "validation results",
                ],
                "produces": [
                    "development feedback record",
                ],
            },

            # --------------------------------------------------
            # LEARNING COMMAND BRIDGE
            # --------------------------------------------------

            "_initialize_seedos_learning_command_bridge": {
                "system": "LearningCommandBridge",
                "capability": "learning_command_plane",
                "plan_step": "LEARNING_COMMANDS",
                "role": "initialization",
                "reads": [
                    "developer commands",
                    "SEED learning events",
                ],
                "produces": [
                    "learning command state",
                ],
            },

            "seedos_teach_learning": {
                "system": "LearningCommandBridge",
                "capability": "TEACH",
                "plan_step": "LEARNING_COMMANDS",
                "role": "learning_command",
                "produces": [
                    "TEACH learning command",
                ],
            },

            "seedos_suggest_learning": {
                "system": "LearningCommandBridge",
                "capability": "SUGGEST",
                "plan_step": "LEARNING_COMMANDS",
                "role": "learning_command",
                "produces": [
                    "SUGGEST learning command",
                ],
            },

            "seedos_learn": {
                "system": "LearningCommandBridge",
                "capability": "LEARN",
                "plan_step": "LEARNING_COMMANDS",
                "role": "learning_command",
                "produces": [
                    "learning record",
                ],
            },

            "seedos_develop_learning": {
                "system": "LearningCommandBridge",
                "capability": "DEVELOP",
                "plan_step": "SELF_DEVELOPMENT",
                "role": "development_command",
                "produces": [
                    "development proposal",
                ],
            },

            "seedos_test_learning": {
                "system": "LearningCommandBridge",
                "capability": "TEST",
                "plan_step": "DEVELOPER_SANDBOX",
                "role": "validation_command",
                "produces": [
                    "test request",
                ],
            },

            "seedos_review_learning": {
                "system": "LearningCommandBridge",
                "capability": "REVIEW",
                "plan_step": "SELF_DEVELOPMENT",
                "role": "review_command",
                "produces": [
                    "review request",
                ],
            },

            # --------------------------------------------------
            # ASK
            # --------------------------------------------------

            "seedos_ask": {
                "system": "LearningCommandBridge",
                "capability": "ASK",
                "plan_step": "LEARNING_COMMANDS",
                "role": "knowledge_request",
                "reads": [
                    "blocked state",
                    "missing knowledge",
                    "uncertainty",
                ],
                "produces": [
                    "tracked question",
                    "pending learning state",
                ],
            },

            "seedos_answer": {
                "system": "LearningCommandBridge",
                "capability": "ANSWER",
                "plan_step": "LEARNING_COMMANDS",
                "role": "knowledge_response",
                "reads": [
                    "pending question",
                    "creator answer",
                ],
                "produces": [
                    "answer record",
                    "learning record",
                ],
            },

            "seedos_resolve_blocked_state": {
                "system": "LearningCommandBridge",
                "capability": "blocked_state_resolution",
                "plan_step": "SELF_DEVELOPMENT",
                "role": "uncertainty_handler",
                "reads": [
                    "blocked reason",
                    "system context",
                ],
                "produces": [
                    "ASK command",
                ],
            },

            "seedos_continue_after_answer": {
                "system": "LearningCommandBridge",
                "capability": "answer_reassessment",
                "plan_step": "SELF_DEVELOPMENT",
                "role": "learning_continuation",
                "reads": [
                    "answer",
                    "question",
                    "learning context",
                ],
                "produces": [
                    "reassessment request",
                ],
            },
        }

        for name, descriptor in definitions.items():
            self._seedos_definition_map[name] = dict(
                descriptor
            )

    def _seedos_read_definition(self, definition_name):
        """
        Read a definition's metadata and, when available, its
        actual bound Python definition metadata.

        This intentionally inspects only. It does not invoke the
        definition.
        """

        result = {
            "name": definition_name,
            "known": False,
            "callable": False,
            "module": None,
            "doc": None,
            "signature": None,
            "plan": None,
            "descriptor": None,
        }

        descriptor = self._seedos_definition_map.get(
            definition_name
        )

        if descriptor is not None:
            result["known"] = True
            result["descriptor"] = dict(
                descriptor
            )

        definition = getattr(
            self,
            definition_name,
            None,
        )

        if definition is None:
            return result

        result["callable"] = callable(definition)

        try:
            import inspect

            result["module"] = getattr(
                definition,
                "__module__",
                None,
            )

            result["doc"] = (
                inspect.getdoc(definition)
            )

            try:
                result["signature"] = str(
                    inspect.signature(definition)
                )
            except Exception:
                result["signature"] = None

        except Exception as exc:
            result["inspection_error"] = str(exc)

        if descriptor is not None:
            plan_step = descriptor.get(
                "plan_step"
            )

            if plan_step:
                result["plan"] = dict(
                    self._seedos_plan_steps.get(
                        plan_step,
                        {},
                    )
                )

        return result

    def seedos_read_definition(
        self,
        definition_name,
    ):
        """
        Public developer inspection method.

        Reads what a DEVHUD definition does according to its
        registered development descriptor and Python metadata.
        """

        return self._seedos_read_definition(
            definition_name
        )

    def seedos_map_definitions(self):
        """
        Build the current definition map without executing any
        mapped definition.
        """

        mapped = {}

        for definition_name in sorted(
            self._seedos_definition_map.keys()
        ):
            mapped[definition_name] = (
                self._seedos_read_definition(
                    definition_name
                )
            )

        self._seedos_definition_map_snapshot = mapped

        return mapped

    def _seedos_plan_update(
        self,
        plan_step,
        status,
        *,
        message=None,
        definition=None,
        capability=None,
        source="DEVHUD",
        metadata=None,
    ):
        """
        Record a development-plan update.

        Updates are append-only observations. They do not
        automatically modify runtime code.
        """

        self._seedos_plan_sequence = (
            getattr(
                self,
                "_seedos_plan_sequence",
                0,
            ) + 1
        )

        update = {
            "update_id": (
                f"PLAN."
                f"{int(time.time() * 1000)}."
                f"{self._seedos_plan_sequence}"
            ),
            "plan_step": plan_step,
            "status": status,
            "message": message,
            "definition": definition,
            "capability": capability,
            "source": source,
            "metadata": metadata or {},
            "created_at": time.time(),
        }

        self._seedos_plan_updates.append(
            update
        )

        if len(self._seedos_plan_updates) > 1000:
            self._seedos_plan_updates = (
                self._seedos_plan_updates[-1000:]
            )

        if plan_step in self._seedos_plan_steps:
            self._seedos_plan_steps[
                plan_step
            ]["status"] = status

            if message:
                self._seedos_plan_steps[
                    plan_step
                ]["last_update"] = message

        return update

    def seedos_update_plan(
        self,
        plan_step,
        status,
        *,
        message=None,
        definition=None,
        capability=None,
        metadata=None,
    ):
        """
        Public development-plan update interface.
        """

        return self._seedos_plan_update(
            plan_step,
            status,
            message=message,
            definition=definition,
            capability=capability,
            metadata=metadata,
        )

    def _seedos_link_definition_to_plan(
        self,
        definition_name,
    ):
        """
        Link one definition to its plan step.
        """

        descriptor = (
            self._seedos_definition_map.get(
                definition_name
            )
        )

        if descriptor is None:
            return {
                "status": "unmapped",
                "definition": definition_name,
            }

        plan_step = descriptor.get(
            "plan_step"
        )

        plan = self._seedos_plan_steps.get(
            plan_step,
            {},
        )

        return {
            "status": "linked",
            "definition": definition_name,
            "system": descriptor.get(
                "system"
            ),
            "capability": descriptor.get(
                "capability"
            ),
            "plan_step": plan_step,
            "plan": dict(plan),
        }

    def seedos_link_definition_to_plan(
        self,
        definition_name,
    ):
        """
        Public definition → plan lookup.
        """

        return (
            self._seedos_link_definition_to_plan(
                definition_name
            )
        )

    def seedos_development_plan(
        self,
        *,
        include_definitions=True,
        include_updates=True,
    ):
        """
        Return the complete current development plan.

        This is the single DEVHUD view of:
            what exists
            what is active
            what is next
            what changed
        """

        result = {
            "plan": {
                key: dict(value)
                for key, value in (
                    self._seedos_plan_steps.items()
                )
            },
            "next_steps": [],
        }

        for key, value in (
            self._seedos_plan_steps.items()
        ):
            status = str(
                value.get("status", "")
            ).upper()

            if status in {
                "NEXT",
                "PLANNED",
                "BLOCKED",
            }:
                result["next_steps"].append(
                    {
                        "plan_step": key,
                        "title": value.get(
                            "title"
                        ),
                        "status": status,
                    }
                )

        if include_definitions:
            result["definitions"] = (
                self.seedos_map_definitions()
            )

        if include_updates:
            result["updates"] = list(
                self._seedos_plan_updates[-100:]
            )

        return result

    def seedos_next_development_step(self):
        """
        Determine the next declared development step from the
        current plan.

        This is planning information only.
        """

        priority = [
            "BLOCKED",
            "NEXT",
            "ACTIVE",
            "PLANNED",
        ]

        for wanted_status in priority:
            for key, value in (
                self._seedos_plan_steps.items()
            ):
                status = str(
                    value.get("status", "")
                ).upper()

                if status == wanted_status:
                    return {
                        "plan_step": key,
                        "title": value.get(
                            "title"
                        ),
                        "status": status,
                        "systems": list(
                            value.get(
                                "systems",
                                [],
                            )
                        ),
                    }

        return {
            "status": "NO_DECLARED_NEXT_STEP"
        }

    def seedos_record_definition_update(
        self,
        definition_name,
        *,
        status="OBSERVED",
        message=None,
        metadata=None,
    ):
        """
        Record progress against a specific definition and its
        linked plan step.
        """

        link = (
            self._seedos_link_definition_to_plan(
                definition_name
            )
        )

        if link.get("status") != "linked":
            return link

        return self._seedos_plan_update(
            link["plan_step"],
            status,
            message=message,
            definition=definition_name,
            capability=link.get(
                "capability"
            ),
            metadata=metadata,
        )

    def seedos_plan_status(self):
        """
        Compact status for DEVHUD, Oracle, and the developer
        workspace.
        """

        next_step = (
            self.seedos_next_development_step()
        )

        return {
            "active_plan_steps": len(
                self._seedos_plan_steps
            ),
            "mapped_definitions": len(
                self._seedos_definition_map
            ),
            "plan_updates": len(
                self._seedos_plan_updates
            ),
            "next_step": next_step,
            "learning_command_bridge": True,
            "ask_path": True,
            "sandbox_validation": True,
            "capability_builder": True,
            "init_event_knowledge": True,
            "oracle_observer": True,
            "fathud_observer": True,
            "qbit_authority": "QbitDialer",
            "transport_authority": "QbitQueueLoop",
            "direct_execution": False,
        }

# ==========================================================
# SECTION 20 — SEED OS SELF-DESCRIBING JSON /
#              IDLE READ / DEF EXTRACTION /
#              CODE DEVELOPMENT BRIDGE
# ==========================================================
#
# PURPOSE:
#   Give SEED a structured way to represent what it knows,
#   what it observes, what commands/defs it discovers, how
#   systems connect, and what new code it proposes developing.
#
# CORE DEVELOPMENT ROAD:
#
#   QbitDialer
#        ↓
#   idle/read observation
#        ↓
#   DEVHUD observation bridge
#        ↓
#   SEED analysis
#        ↓
#   extract DEF / command / capability
#        ↓
#   JSON knowledge record
#        ↓
#   connection analysis
#        ↓
#   development proposal
#        ↓
#   sandbox
#        ↓
#   validation
#        ↓
#   review
#        ↓
#   promotion proposal
#
# IMPORTANT:
#   JSON is DATA / KNOWLEDGE / PLAN representation.
#   JSON is NOT executable Python.
#
#   A discovered "def" is recorded as knowledge first.
#   Generated code is a development artifact/proposal.
#
# AUTHORITY:
#   DEVHUD      = developer interface / observation bridge
#   SEED        = cognition / interpretation
#   Oracle      = observation / governance
#   QbitDialer  = command authority
#   QueueLoop   = execution / transport authority
#   Sandbox     = development validation boundary
#
# ==========================================================

    def _initialize_seedos_json_development_bridge(self):
        """
        Initialize SEED's structured JSON development knowledge.

        These records allow SEED to describe itself without
        requiring every piece of knowledge to be hard-coded into
        one Python module.
        """

        self._seedos_json_records = {}
        self._seedos_json_history = []
        self._seedos_json_sequence = 0

        self._seedos_json_record_types = {
            "SYSTEM": "SEED system description",
            "CAPABILITY": "system capability description",
            "COMMAND": "command description",
            "DEF": "Python definition description",
            "CONNECTION": "system relationship",
            "OBSERVATION": "runtime/read-loop observation",
            "LEARNING": "learned knowledge",
            "QUESTION": "SEED knowledge request",
            "ANSWER": "answer to a SEED question",
            "DEVELOPMENT": "development proposal",
            "CODE_ARTIFACT": "proposed/generated code artifact",
            "TEST": "sandbox validation record",
            "REVIEW": "development review",
            "PLAN": "development plan state",
        }

    def _seedos_next_json_id(self, record_type="JSON"):
        """
        Create an identifier for a structured development record.

        This is not a Qbit ID.
        """

        self._seedos_json_sequence = (
            getattr(
                self,
                "_seedos_json_sequence",
                0,
            ) + 1
        )

        return (
            f"{record_type}."
            f"{int(time.time() * 1000)}."
            f"{self._seedos_json_sequence}"
        )

    def _seedos_build_json_record(
        self,
        record_type,
        data=None,
        *,
        source="DEVHUD",
        parent_id=None,
        status="RECORDED",
    ):
        """
        Build a canonical SEED JSON knowledge record.

        The returned object is JSON-serializable data.
        """

        record_type = str(
            record_type or "OBSERVATION"
        ).strip().upper()

        if record_type not in (
            getattr(
                self,
                "_seedos_json_record_types",
                {},
            )
        ):
            record_type = "OBSERVATION"

        return {
            "record_id": self._seedos_next_json_id(
                record_type
            ),
            "record_type": record_type,
            "source": source,
            "parent_id": parent_id,
            "status": status,
            "created_at": time.time(),
            "seed_os": {
                "authority": "SEED",
                "command_authority": "QbitDialer",
                "transport_authority": "QbitQueueLoop",
                "event_authority": "SEEDEventBus",
                "observer_authority": "Oracle",
                "development_authority": "SEEDOS_SANDBOX",
            },
            "data": data or {},
        }

    def _seedos_record_json_knowledge(
        self,
        record,
    ):
        """
        Store structured knowledge in the DEVHUD development
        workspace.

        This is the in-memory representation. Persistence can
        later use the existing storage root.
        """

        if not isinstance(record, dict):
            return None

        record_id = record.get(
            "record_id"
        )

        if not record_id:
            return None

        self._seedos_json_records[
            record_id
        ] = dict(record)

        self._seedos_json_history.append(
            dict(record)
        )

        if len(self._seedos_json_history) > 5000:
            self._seedos_json_history = (
                self._seedos_json_history[-5000:]
            )

        return record_id

    def seedos_json_record(
        self,
        record_type,
        data=None,
        *,
        source="DEVHUD",
        parent_id=None,
        status="RECORDED",
    ):
        """
        Public structured-knowledge entry point.
        """

        record = self._seedos_build_json_record(
            record_type,
            data,
            source=source,
            parent_id=parent_id,
            status=status,
        )

        self._seedos_record_json_knowledge(
            record
        )

        return record

    def _seedos_json_safe_copy(self, value):
        """
        Produce a JSON-safe representation.

        Runtime objects are represented by descriptors rather than
        being serialized directly.
        """

        try:
            import json

            return json.loads(
                json.dumps(
                    value,
                    default=str,
                )
            )

        except Exception:
            return str(value)

    def _seedos_describe_runtime_object(
        self,
        name,
        obj,
    ):
        """
        Describe an existing runtime object without constructing
        or invoking it.
        """

        if obj is None:
            return {
                "name": name,
                "present": False,
            }

        descriptor = {
            "name": name,
            "present": True,
            "type": type(obj).__name__,
            "module": getattr(
                type(obj),
                "__module__",
                None,
            ),
        }

        try:
            import inspect

            descriptor["callable"] = callable(obj)

            if callable(obj):
                try:
                    descriptor["signature"] = str(
                        inspect.signature(obj)
                    )
                except Exception:
                    descriptor["signature"] = None

            descriptor["doc"] = (
                inspect.getdoc(obj)
            )

        except Exception:
            pass

        return descriptor

    def _seedos_extract_defs_from_class(
        self,
        cls,
        *,
        system=None,
        source="RUNTIME",
    ):
        """
        Read Python definitions from an existing class.

        No definition is called.

        The result is structured knowledge describing what the
        definitions appear to do.
        """

        extracted = []

        if cls is None:
            return extracted

        try:
            import inspect

            members = inspect.getmembers(
                cls,
                predicate=inspect.isfunction,
            )

            for name, definition in members:
                if name.startswith("__"):
                    continue

                descriptor = {
                    "def_name": name,
                    "system": system,
                    "source": source,
                    "module": getattr(
                        definition,
                        "__module__",
                        None,
                    ),
                    "qualname": getattr(
                        definition,
                        "__qualname__",
                        name,
                    ),
                    "doc": inspect.getdoc(
                        definition
                    ),
                    "signature": None,
                    "callable": True,
                }

                try:
                    descriptor["signature"] = str(
                        inspect.signature(
                            definition
                        )
                    )
                except Exception:
                    pass

                extracted.append(
                    descriptor
                )

        except Exception as exc:
            self.logger.debug(
                "[DEVHUD] DEF extraction failed | "
                "system=%s | error=%s",
                system,
                exc,
            )

        return extracted

    def seedos_extract_defs(
        self,
        system_name,
        system_object=None,
    ):
        """
        Extract definition metadata from an existing system.

        If no object is supplied, DEVHUD resolves the already
        bound runtime reference where possible.
        """

        obj = system_object

        if obj is None:
            obj = getattr(
                self,
                system_name,
                None,
            )

        if obj is None:
            return {
                "status": "system_not_bound",
                "system": system_name,
                "defs": [],
            }

        defs = self._seedos_extract_defs_from_class(
            type(obj),
            system=system_name,
            source="BOUND_RUNTIME",
        )

        record = self.seedos_json_record(
            "DEF",
            {
                "system": system_name,
                "definitions": defs,
                "count": len(defs),
            },
            source="DEVHUD_DEF_READER",
        )

        return {
            "status": "extracted",
            "system": system_name,
            "count": len(defs),
            "defs": defs,
            "record_id": record.get(
                "record_id"
            ),
        }

    def _seedos_extract_command_from_def(
        self,
        definition,
        *,
        system=None,
    ):
        """
        Determine whether a definition looks like a candidate
        command/capability.

        This is semantic metadata, not automatic execution.
        """

        if not isinstance(definition, dict):
            return None

        name = str(
            definition.get(
                "def_name",
                "",
            )
        )

        doc = str(
            definition.get(
                "doc",
                "",
            )
            or ""
        )

        command_words = (
            "command",
            "submit",
            "execute",
            "send",
            "route",
            "start",
            "stop",
            "pause",
            "resume",
            "connect",
            "build",
            "create",
            "load",
            "update",
            "snapshot",
            "inspect",
            "learn",
            "teach",
            "ask",
            "develop",
            "test",
        )

        combined = (
            f"{name} {doc}"
        ).lower()

        matches = [
            word
            for word in command_words
            if word in combined
        ]

        if not matches:
            return None

        return {
            "command_candidate": True,
            "def_name": name,
            "system": system
                or definition.get(
                    "system"
                ),
            "matched_terms": matches,
            "signature": definition.get(
                "signature"
            ),
            "doc": doc,
            "execution_authority": (
                "QbitDialer"
            ),
            "requires_cognition": True,
            "direct_execution": False,
        }

    def seedos_extract_commands_from_defs(
        self,
        definitions,
        *,
        system=None,
    ):
        """
        Extract command candidates from DEF metadata.

        The result is registered as knowledge/capability data.
        It does not become executable merely by being discovered.
        """

        if not isinstance(
            definitions,
            (list, tuple),
        ):
            return {
                "status": "invalid_definitions",
                "commands": [],
            }

        commands = []

        for definition in definitions:
            candidate = (
                self._seedos_extract_command_from_def(
                    definition,
                    system=system,
                )
            )

            if candidate is None:
                continue

            commands.append(candidate)

        record = self.seedos_json_record(
            "COMMAND",
            {
                "system": system,
                "commands": commands,
                "count": len(commands),
            },
            source="DEF_COMMAND_EXTRACTOR",
        )

        return {
            "status": "extracted",
            "system": system,
            "count": len(commands),
            "commands": commands,
            "record_id": record.get(
                "record_id"
            ),
        }

    def _seedos_collect_idle_read_context(self):
        """
        Collect what DEVHUD can safely observe from the existing
        Dialer/read-loop environment.

        No new read loop is created.
        """

        dialer = getattr(
            self,
            "qbit_dialer",
            None,
        )

        queue_loop = getattr(
            self,
            "qbit_queue",
            None,
        )

        context = {
            "timestamp": time.time(),
            "dialer": (
                self._seedos_describe_runtime_object(
                    "QbitDialer",
                    dialer,
                )
            ),
            "queue_loop": (
                self._seedos_describe_runtime_object(
                    "QbitQueueLoop",
                    queue_loop,
                )
            ),
            "dialer_state": {},
            "queue_state": {},
        }

        for obj, target in (
            (dialer, "dialer_state"),
            (queue_loop, "queue_state"),
        ):
            if obj is None:
                continue

            for attribute in (
                "active",
                "running",
                "online",
                "status",
                "state",
                "commands",
                "command_count",
                "qbit_rate",
                "telemetry_rate",
            ):
                try:
                    value = getattr(
                        obj,
                        attribute,
                    )

                    if not callable(value):
                        context[
                            target
                        ][attribute] = (
                            self._seedos_json_safe_copy(
                                value
                            )
                        )

                except Exception:
                    continue

        return context

    def seedos_read_idle_state(self):
        """
        Read the existing Dialer/QueueLoop state and turn the
        observation into SEED knowledge.

        This does not create or start another loop.
        """

        context = (
            self._seedos_collect_idle_read_context()
        )

        record = self.seedos_json_record(
            "OBSERVATION",
            {
                "observation_type": (
                    "DIALER_IDLE_READ"
                ),
                "runtime": context,
            },
            source="QBIT_DIALER_IDLE_READ",
        )

        try:
            self._seedos_observe_developer_input(
                record
            )
        except Exception:
            pass

        return record

    def _seedos_build_system_connection(
        self,
        source_system,
        target_system,
        *,
        relationship,
        reason=None,
        source_def=None,
        target_def=None,
    ):
        """
        Build a structured system relationship.

        Connections are knowledge until SEED/cognition determines
        that a development action is appropriate.
        """

        return {
            "connection_id": self._seedos_next_json_id(
                "CONNECTION"
            ),
            "source_system": source_system,
            "target_system": target_system,
            "relationship": relationship,
            "reason": reason,
            "source_def": source_def,
            "target_def": target_def,
            "status": "PROPOSED",
            "execution_required": False,
        }

    def seedos_connect_defs(
        self,
        source_def,
        target_def,
        *,
        relationship="USES",
        reason=None,
    ):
        """
        Connect two discovered definitions.

        This is how SEED can learn that one DEF provides a
        capability another DEF needs.
        """

        source_system = None
        target_system = None

        source = self._seedos_definition_map.get(
            source_def
        )

        target = self._seedos_definition_map.get(
            target_def
        )

        if source:
            source_system = source.get(
                "system"
            )

        if target:
            target_system = target.get(
                "system"
            )

        connection = (
            self._seedos_build_system_connection(
                source_system or "UNKNOWN",
                target_system or "UNKNOWN",
                relationship=relationship,
                reason=reason,
                source_def=source_def,
                target_def=target_def,
            )
        )

        record = self.seedos_json_record(
            "CONNECTION",
            connection,
            source="DEF_CONNECTION_ANALYZER",
        )

        return {
            "status": "connection_proposed",
            "connection": connection,
            "record_id": record.get(
                "record_id"
            ),
        }

    def _seedos_build_code_development_record(
        self,
        *,
        name,
        purpose,
        target_system,
        source_defs=None,
        dependencies=None,
        requested_by="SEED",
        language="python",
    ):
        """
        Build a code-development specification.

        This is the bridge between understanding a DEF and
        proposing a new script/module.
        """

        development_id = (
            self._seedos_next_json_id(
                "DEVELOP"
            )
        )

        return {
            "development_id": development_id,
            "name": name,
            "purpose": purpose,
            "target_system": target_system,
            "language": language,
            "source_defs": source_defs or [],
            "dependencies": dependencies or [],
            "requested_by": requested_by,
            "status": "PROPOSED",
            "execution_required": False,
            "write_to_core": False,
            "sandbox_required": True,
            "validation_required": True,
            "review_required": True,
            "promotion_required": True,
            "authority": {
                "cognition": "SEED",
                "command": "QbitDialer",
                "execution": "QbitQueueLoop",
                "validation": "SEEDOS_SANDBOX",
                "observation": "Oracle",
            },
        }

    def seedos_propose_code(
        self,
        name,
        purpose,
        *,
        target_system=None,
        source_defs=None,
        dependencies=None,
        requested_by="SEED",
    ):
        """
        Create a structured code-development proposal.

        The proposal describes what SEED believes should be built.
        It does not execute or install the proposed code.
        """

        proposal = (
            self._seedos_build_code_development_record(
                name=name,
                purpose=purpose,
                target_system=(
                    target_system
                    or "SEED_OS"
                ),
                source_defs=source_defs,
                dependencies=dependencies,
                requested_by=requested_by,
            )
        )

        record = self.seedos_json_record(
            "DEVELOPMENT",
            proposal,
            source="SEED_DEVELOPMENT",
        )

        try:
            self._seedos_emit_capability_proposal(
                proposal
            )
        except Exception:
            pass

        return {
            "status": "development_proposed",
            "proposal": proposal,
            "record_id": record.get(
                "record_id"
            ),
        }

    def seedos_build_json_plan(
        self,
        *,
        name="seed_development_plan",
        include_history=True,
    ):
        """
        Build the JSON representation of the current SEED
        development state.

        This is the foundation for future persisted .json
        knowledge/plan files.
        """

        plan = {
            "schema": "SEED_OS_DEVELOPMENT_PLAN",
            "schema_version": "1.0",
            "generated_at": time.time(),
            "name": name,
            "authority": {
                "seed": True,
                "qbit_dialer": "QbitDialer",
                "queue_loop": "QbitQueueLoop",
                "event_bus": "SEEDEventBus",
                "oracle": "Oracle",
                "sandbox": "SEEDOS_SANDBOX",
            },
            "learning": (
                self.seedos_learning_status()
                if hasattr(
                    self,
                    "seedos_learning_status",
                )
                else {}
            ),
            "development": (
                self.seedos_plan_status()
                if hasattr(
                    self,
                    "seedos_plan_status",
                )
                else {}
            ),
            "definitions": (
                self.seedos_map_definitions()
                if hasattr(
                    self,
                    "seedos_map_definitions",
                )
                else {}
            ),
            "records": {},
        }

        if include_history:
            plan["records"] = {
                record_id: dict(record)
                for record_id, record in (
                    self._seedos_json_records.items()
                )
            }

        return plan

    def seedos_json_snapshot(self):
        """
        Return the complete structured development/learning
        snapshot available to DEVHUD.
        """

        return {
            "status": "ACTIVE",
            "json_records": len(
                getattr(
                    self,
                    "_seedos_json_records",
                    {},
                )
            ),
            "json_history": len(
                getattr(
                    self,
                    "_seedos_json_history",
                    [],
                )
            ),
            "record_types": dict(
                getattr(
                    self,
                    "_seedos_json_record_types",
                    {},
                )
            ),
            "idle_read": (
                self._seedos_collect_idle_read_context()
            ),
            "learning": (
                self.seedos_learning_snapshot()
                if hasattr(
                    self,
                    "seedos_learning_snapshot",
                )
                else {}
            ),
            "plan": (
                self.seedos_development_plan()
                if hasattr(
                    self,
                    "seedos_development_plan",
                )
                else {}
            ),
            "authority": {
                "qbit_dialer": True,
                "queue_loop": True,
                "event_bus": True,
                "oracle": True,
                "sandbox": True,
                "direct_execution": False,
            },
        }

    def seedos_development_roadmap(self):
        """
        Return the development road from observation through
        controlled code creation.
        """

        return {
            "road": [
                {
                    "step": 1,
                    "name": "READ",
                    "purpose": (
                        "Observe existing Dialer/runtime state."
                    ),
                },
                {
                    "step": 2,
                    "name": "EXTRACT",
                    "purpose": (
                        "Identify DEFs, commands, and capabilities."
                    ),
                },
                {
                    "step": 3,
                    "name": "DESCRIBE",
                    "purpose": (
                        "Represent discovered knowledge as JSON."
                    ),
                },
                {
                    "step": 4,
                    "name": "CONNECT",
                    "purpose": (
                        "Identify relationships between systems and DEFs."
                    ),
                },
                {
                    "step": 5,
                    "name": "ASK",
                    "purpose": (
                        "Request missing knowledge instead of guessing."
                    ),
                },
                {
                    "step": 6,
                    "name": "LEARN",
                    "purpose": (
                        "Integrate answers, observations, and feedback."
                    ),
                },
                {
                    "step": 7,
                    "name": "DEVELOP",
                    "purpose": (
                        "Create a structured proposal for new code."
                    ),
                },
                {
                    "step": 8,
                    "name": "SANDBOX",
                    "purpose": (
                        "Test the proposed capability separately."
                    ),
                },
                {
                    "step": 9,
                    "name": "VALIDATE",
                    "purpose": (
                        "Check authority, dependencies, and compatibility."
                    ),
                },
                {
                    "step": 10,
                    "name": "REVIEW",
                    "purpose": (
                        "Evaluate whether the development should continue."
                    ),
                },
                {
                    "step": 11,
                    "name": "PROMOTE",
                    "purpose": (
                        "Make a controlled proposal for integration."
                    ),
                },
                {
                    "step": 12,
                    "name": "EXECUTE",
                    "purpose": (
                        "Only through existing QbitDialer/"
                        "QbitQueueLoop authority."
                    ),
                },
            ],
            "blocked_behavior": {
                "if_unknown": "ASK",
                "if_missing_knowledge": "ASK",
                "if_ambiguous": "ASK",
                "if_validation_fails": "LEARN_AND_REASSESS",
                "if_command_denied": "LEARN_AND_REASSESS",
                "never_force_unknown_action": True,
            },
            "development_principle": (
                "SEED develops from observed knowledge, "
                "connections, learning, validation, and review."
            ),
        }

# ==========================================================
# SECTION 21 — SEED OS PERSISTENT JSON KNOWLEDGE FABRIC
# ==========================================================
#
# PURPOSE:
#   Turn the structured knowledge created by Sections 18–20
#   into controlled SEED OS JSON knowledge artifacts.
#
#   JSON represents:
#       SYSTEMS
#       DEFS
#       COMMANDS
#       CONNECTIONS
#       LEARNING
#       QUESTIONS / ANSWERS
#       DEVELOPMENT
#       TESTS
#       REVIEWS
#       PLAN
#
#   JSON is descriptive state/knowledge.
#   Python remains executable implementation.
#
# ROAD:
#
#   DIALER IDLE/READ
#          ↓
#   OBSERVATION
#          ↓
#   DEF / COMMAND EXTRACTION
#          ↓
#   JSON KNOWLEDGE
#          ↓
#   CONNECTION MAP
#          ↓
#   LEARNING
#          ↓
#   ASK WHEN NEEDED
#          ↓
#   DEVELOPMENT
#          ↓
#   SANDBOX
#          ↓
#   VALIDATION
#          ↓
#   REVIEW
#          ↓
#   PROMOTION PROPOSAL
#
# ==========================================================

    def _initialize_seedos_json_knowledge_fabric(self):
        """
        Initialize the persistent JSON knowledge fabric.

        Uses the existing DEVHUD storage root.
        Does not create another runtime or transport system.
        """

        from pathlib import Path

        self._seedos_json_root = Path(
            getattr(
                self,
                "storage_root",
                "./SEED_ROOT",
            )
        )

        self._seedos_json_root = (
            self._seedos_json_root
            / "seed_os_knowledge"
        )

        self._seedos_json_files = {
            "system": "system_map.json",
            "def": "def_map.json",
            "command": "command_map.json",
            "connection": "connection_map.json",
            "learning": "learning_map.json",
            "question": "question_map.json",
            "development": "development_map.json",
            "test": "test_map.json",
            "review": "review_map.json",
            "plan": "development_plan.json",
            "snapshot": "seed_os_knowledge_snapshot.json",
        }

        self._seedos_json_write_enabled = True
        self._seedos_json_loaded = False
        self._seedos_json_last_write = None

    def _seedos_json_path(self, record_name):
        """
        Resolve a known SEED JSON artifact path.
        """

        from pathlib import Path

        filename = self._seedos_json_files.get(
            record_name
        )

        if filename is None:
            return None

        root = getattr(
            self,
            "_seedos_json_root",
            None,
        )

        if root is None:
            return None

        return Path(root) / filename

    def _seedos_json_default_document(
        self,
        record_name,
    ):
        """
        Build the canonical envelope for a SEED JSON artifact.
        """

        return {
            "schema": (
                f"SEED_OS_{str(record_name).upper()}_MAP"
            ),
            "schema_version": "1.0",
            "generated_by": "DEVHUD",
            "authority": {
                "knowledge": "SEED",
                "command": "QbitDialer",
                "transport": "QbitQueueLoop",
                "events": "SEEDEventBus",
                "tracking": "TrackSystem",
                "observation": "Oracle",
                "developer_interface": "DEVHUD",
                "validation": "SEEDOS_SANDBOX",
            },
            "execution": {
                "direct_execution": False,
                "runtime_creation": False,
                "qbit_creation": False,
                "package_installation": False,
                "external_startup": False,
            },
            "records": {},
            "updated_at": time.time(),
        }

    def _seedos_json_serialize(
        self,
        value,
    ):
        """
        Convert SEED knowledge into JSON-safe data.
        """

        import json

        try:
            return json.loads(
                json.dumps(
                    value,
                    default=str,
                )
            )
        except Exception:
            return str(value)

    def _seedos_json_read_file(
        self,
        record_name,
    ):
        """
        Read one existing SEED knowledge artifact.

        Missing files are represented as empty knowledge.
        """

        import json

        path = self._seedos_json_path(
            record_name
        )

        if path is None:
            return None

        try:
            if not path.exists():
                return (
                    self._seedos_json_default_document(
                        record_name
                    )
                )

            with path.open(
                "r",
                encoding="utf-8",
            ) as handle:
                document = json.load(handle)

            if not isinstance(
                document,
                dict,
            ):
                return (
                    self._seedos_json_default_document(
                        record_name
                    )
                )

            return document

        except Exception as exc:
            self.logger.warning(
                "[DEVHUD] JSON knowledge read failed | "
                "name=%s | error=%s",
                record_name,
                exc,
            )

            return (
                self._seedos_json_default_document(
                    record_name
                )
            )

    def _seedos_json_write_file(
        self,
        record_name,
        document,
    ):
        """
        Persist one SEED knowledge artifact.

        Writes are atomic from DEVHUD's perspective:
        temporary file → replace.

        No executable code is written by this method.
        """

        import json
        from pathlib import Path

        if not getattr(
            self,
            "_seedos_json_write_enabled",
            False,
        ):
            return False

        path = self._seedos_json_path(
            record_name
        )

        if path is None:
            return False

        try:
            path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            safe_document = (
                self._seedos_json_serialize(
                    document
                )
            )

            temporary_path = Path(
                str(path) + ".tmp"
            )

            with temporary_path.open(
                "w",
                encoding="utf-8",
            ) as handle:
                json.dump(
                    safe_document,
                    handle,
                    indent=2,
                    ensure_ascii=False,
                    sort_keys=True,
                )

            temporary_path.replace(
                path
            )

            self._seedos_json_last_write = {
                "record_name": record_name,
                "path": str(path),
                "timestamp": time.time(),
            }

            return True

        except Exception as exc:
            self.logger.warning(
                "[DEVHUD] JSON knowledge write failed | "
                "name=%s | error=%s",
                record_name,
                exc,
            )
            return False

    def _seedos_json_record_bucket(
        self,
        record_type,
    ):
        """
        Translate internal record types to persistent JSON maps.
        """

        mapping = {
            "SYSTEM": "system",
            "CAPABILITY": "system",
            "DEF": "def",
            "COMMAND": "command",
            "CONNECTION": "connection",
            "OBSERVATION": "system",
            "LEARNING": "learning",
            "QUESTION": "question",
            "ANSWER": "learning",
            "DEVELOPMENT": "development",
            "CODE_ARTIFACT": "development",
            "TEST": "test",
            "REVIEW": "review",
            "PLAN": "plan",
        }

        return mapping.get(
            str(
                record_type or ""
            ).upper()
        )

    def _seedos_persist_json_record(
        self,
        record,
    ):
        """
        Persist one structured SEED record into its appropriate
        JSON knowledge artifact.
        """

        if not isinstance(
            record,
            dict,
        ):
            return False

        record_type = record.get(
            "record_type"
        )

        bucket = (
            self._seedos_json_record_bucket(
                record_type
            )
        )

        if bucket is None:
            return False

        record_id = record.get(
            "record_id"
        )

        if not record_id:
            return False

        document = (
            self._seedos_json_read_file(
                bucket
            )
        )

        if not isinstance(
            document,
            dict,
        ):
            document = (
                self._seedos_json_default_document(
                    bucket
                )
            )

        records = document.setdefault(
            "records",
            {},
        )

        records[record_id] = (
            self._seedos_json_serialize(
                record
            )
        )

        document["updated_at"] = time.time()

        return self._seedos_json_write_file(
            bucket,
            document,
        )

    def seedos_persist_knowledge(
        self,
        record=None,
    ):
        """
        Public persistence interface.

        If no record is supplied, persist all currently known
        in-memory JSON records.
        """

        if record is not None:
            return self._seedos_persist_json_record(
                record
            )

        records = getattr(
            self,
            "_seedos_json_records",
            {},
        )

        results = {}

        for record_id, item in records.items():
            results[record_id] = (
                self._seedos_persist_json_record(
                    item
                )
            )

        return {
            "status": "persisted",
            "count": len(results),
            "results": results,
        }

    def _seedos_load_persistent_knowledge(self):
        """
        Load existing JSON knowledge into DEVHUD's local
        development knowledge state.
        """

        loaded = {}

        for record_name in (
            self._seedos_json_files.keys()
        ):
            if record_name == "snapshot":
                continue

            document = (
                self._seedos_json_read_file(
                    record_name
                )
            )

            if not isinstance(
                document,
                dict,
            ):
                continue

            records = document.get(
                "records",
                {},
            )

            if not isinstance(
                records,
                dict,
            ):
                continue

            for record_id, record in records.items():
                if isinstance(
                    record,
                    dict,
                ):
                    self._seedos_json_records[
                        record_id
                    ] = record

            loaded[record_name] = len(
                records
            )

        self._seedos_json_loaded = True

        return {
            "status": "loaded",
            "maps": loaded,
            "total_records": sum(
                loaded.values()
            ),
        }

    def seedos_load_knowledge(self):
        """
        Public JSON knowledge loading interface.
        """

        return (
            self._seedos_load_persistent_knowledge()
        )

    def _seedos_rebuild_def_map(self):
        """
        Rebuild the persistent DEF map from known definitions.
        """

        document = (
            self._seedos_json_default_document(
                "def"
            )
        )

        definitions = {}

        for name, descriptor in (
            getattr(
                self,
                "_seedos_definition_map",
                {},
            ).items()
        ):
            definitions[name] = (
                self._seedos_json_serialize(
                    descriptor
                )
            )

        document["definitions"] = definitions
        document["definition_count"] = len(
            definitions
        )
        document["updated_at"] = time.time()

        return self._seedos_json_write_file(
            "def",
            document,
        )

    def _seedos_rebuild_command_map(self):
        """
        Rebuild the persistent command map from discovered
        learning/DEF command knowledge.
        """

        document = (
            self._seedos_json_default_document(
                "command"
            )
        )

        commands = {}

        for record in getattr(
            self,
            "_seedos_json_records",
            {},
        ).values():

            if not isinstance(
                record,
                dict,
            ):
                continue

            if record.get(
                "record_type"
            ) != "COMMAND":
                continue

            record_id = record.get(
                "record_id"
            )

            if record_id:
                commands[record_id] = (
                    self._seedos_json_serialize(
                        record
                    )
                )

        document["commands"] = commands
        document["command_count"] = len(
            commands
        )
        document["updated_at"] = time.time()

        return self._seedos_json_write_file(
            "command",
            document,
        )

    def _seedos_rebuild_connection_map(self):
        """
        Rebuild the persistent system/DEF connection map.
        """

        document = (
            self._seedos_json_default_document(
                "connection"
            )
        )

        connections = {}

        for record in getattr(
            self,
            "_seedos_json_records",
            {},
        ).values():

            if not isinstance(
                record,
                dict,
            ):
                continue

            if record.get(
                "record_type"
            ) != "CONNECTION":
                continue

            record_id = record.get(
                "record_id"
            )

            if record_id:
                connections[record_id] = (
                    self._seedos_json_serialize(
                        record
                    )
                )

        document["connections"] = connections
        document["connection_count"] = len(
            connections
        )
        document["updated_at"] = time.time()

        return self._seedos_json_write_file(
            "connection",
            document,
        )

    def _seedos_rebuild_learning_map(self):
        """
        Rebuild persistent learning state including ASK/ANSWER
        relationships.
        """

        document = (
            self._seedos_json_default_document(
                "learning"
            )
        )

        learning = {}

        for record in getattr(
            self,
            "_seedos_json_records",
            {},
        ).values():

            if not isinstance(
                record,
                dict,
            ):
                continue

            if record.get(
                "record_type"
            ) not in {
                "LEARNING",
                "ANSWER",
            }:
                continue

            record_id = record.get(
                "record_id"
            )

            if record_id:
                learning[record_id] = (
                    self._seedos_json_serialize(
                        record
                    )
                )

        document["learning"] = learning
        document["learning_count"] = len(
            learning
        )
        document["pending_questions"] = (
            self._seedos_json_serialize(
                getattr(
                    self,
                    "_seedos_pending_questions",
                    {},
                )
            )
        )
        document["updated_at"] = time.time()

        return self._seedos_json_write_file(
            "learning",
            document,
        )

    def _seedos_rebuild_question_map(self):
        """
        Persist SEED questions separately so unanswered knowledge
        requests survive the current GUI session.
        """

        document = (
            self._seedos_json_default_document(
                "question"
            )
        )

        questions = (
            getattr(
                self,
                "_seedos_pending_questions",
                {},
            )
        )

        document["questions"] = (
            self._seedos_json_serialize(
                questions
            )
        )

        document["question_count"] = len(
            questions
        )

        document["updated_at"] = time.time()

        return self._seedos_json_write_file(
            "question",
            document,
        )

    def _seedos_rebuild_development_map(self):
        """
        Persist development proposals and generated-code
        specifications.
        """

        document = (
            self._seedos_json_default_document(
                "development"
            )
        )

        development = {}

        for record in getattr(
            self,
            "_seedos_json_records",
            {},
        ).values():

            if not isinstance(
                record,
                dict,
            ):
                continue

            if record.get(
                "record_type"
            ) not in {
                "DEVELOPMENT",
                "CODE_ARTIFACT",
            }:
                continue

            record_id = record.get(
                "record_id"
            )

            if record_id:
                development[record_id] = (
                    self._seedos_json_serialize(
                        record
                    )
                )

        document["development"] = development
        document["development_count"] = len(
            development
        )
        document["updated_at"] = time.time()

        return self._seedos_json_write_file(
            "development",
            document,
        )

    def _seedos_rebuild_plan_map(self):
        """
        Persist the living development plan and its updates.
        """

        document = (
            self._seedos_json_default_document(
                "plan"
            )
        )

        document["plan"] = (
            self._seedos_json_serialize(
                self.seedos_development_plan()
                if hasattr(
                    self,
                    "seedos_development_plan",
                )
                else {}
            )
        )

        document["roadmap"] = (
            self._seedos_json_serialize(
                self.seedos_development_roadmap()
                if hasattr(
                    self,
                    "seedos_development_roadmap",
                )
                else {}
            )
        )

        document["updated_at"] = time.time()

        return self._seedos_json_write_file(
            "plan",
            document,
        )

    def _seedos_rebuild_knowledge_snapshot(self):
        """
        Produce one complete JSON snapshot of the current
        SEED development knowledge fabric.
        """

        snapshot = (
            self.seedos_json_snapshot()
            if hasattr(
                self,
                "seedos_json_snapshot",
            )
            else {}
        )

        snapshot["persistent_maps"] = (
            dict(
                self._seedos_json_files
            )
        )

        snapshot["generated_at"] = time.time()

        return self._seedos_json_write_file(
            "snapshot",
            snapshot,
        )

    def seedos_sync_json_knowledge(self):
        """
        Synchronize all structured development knowledge into
        the persistent JSON maps.
        """

        operations = {
            "def": self._seedos_rebuild_def_map,
            "command": self._seedos_rebuild_command_map,
            "connection": (
                self._seedos_rebuild_connection_map
            ),
            "learning": (
                self._seedos_rebuild_learning_map
            ),
            "question": (
                self._seedos_rebuild_question_map
            ),
            "development": (
                self._seedos_rebuild_development_map
            ),
            "plan": (
                self._seedos_rebuild_plan_map
            ),
            "snapshot": (
                self._seedos_rebuild_knowledge_snapshot
            ),
        }

        results = {}

        for name, operation in operations.items():
            try:
                results[name] = bool(
                    operation()
                )
            except Exception as exc:
                results[name] = {
                    "status": "error",
                    "error": str(exc),
                }

        return {
            "status": "synchronized",
            "results": results,
            "timestamp": time.time(),
        }

    def seedos_json_knowledge_status(self):
        """
        Return the state of the persistent SEED knowledge fabric.
        """

        maps = {}

        for name in (
            self._seedos_json_files.keys()
        ):
            path = (
                self._seedos_json_path(name)
            )

            maps[name] = {
                "path": (
                    str(path)
                    if path is not None
                    else None
                ),
                "exists": (
                    bool(
                        path
                        and path.exists()
                    )
                ),
            }

        return {
            "active": True,
            "loaded": bool(
                getattr(
                    self,
                    "_seedos_json_loaded",
                    False,
                )
            ),
            "write_enabled": bool(
                getattr(
                    self,
                    "_seedos_json_write_enabled",
                    False,
                )
            ),
            "records": len(
                getattr(
                    self,
                    "_seedos_json_records",
                    {},
                )
            ),
            "maps": maps,
            "last_write": getattr(
                self,
                "_seedos_json_last_write",
                None,
            ),
            "json_is_knowledge": True,
            "json_is_executable": False,
            "direct_execution": False,
        }


    # ==========================================================
    # SECTION 22
    # SEED OS DIALER IDLE / READ LEARNING ADAPTER
    # ==========================================================
    #
    # PURPOSE:
    #     Observe the EXISTING QbitDialer / EventBus runtime and
    #     convert readable system structure into SEED knowledge.
    #
    #     This adapter allows SEED to:
    #
    #         READ existing runtime systems
    #         DISCOVER definitions
    #         EXTRACT candidate capabilities
    #         EXTRACT candidate commands
    #         MAP system relationships
    #         RECORD observations as JSON knowledge
    #         ASK when meaning cannot be safely determined
    #
    # IMPORTANT:
    #
    #     DEVHUD DOES NOT:
    #
    #         - create another QbitDialer
    #         - create another QbitQueueLoop
    #         - create another EventBus
    #         - create Qbits here
    #         - execute discovered defs
    #         - promote defs directly into commands
    #         - create another idle loop
    #
    #     QbitDialer remains command authority.
    #     QbitQueueLoop remains execution / transport authority.
    #
    # ==========================================================


    def _initialize_seedos_dialer_learning_adapter(self):
        """
        Initialize the SEED OS Dialer learning adapter.

        The adapter observes the already-running SEED runtime.

        It does not start a polling loop.

        Existing runtime events and explicit idle/read observations
        are converted into structured learning records.
        """

        if getattr(
            self,
            "_seedos_dialer_learning_initialized",
            False,
        ):
            return

        self._seedos_dialer_learning_initialized = True

        self._seedos_dialer_learning_enabled = True

        self._seedos_dialer_observation_count = 0
        self._seedos_dialer_definition_count = 0
        self._seedos_dialer_command_count = 0
        self._seedos_dialer_connection_count = 0
        self._seedos_dialer_question_count = 0

        self._seedos_dialer_seen_defs = set()
        self._seedos_dialer_seen_commands = set()
        self._seedos_dialer_seen_connections = set()

        self._seedos_dialer_learning_history = []

        self._seedos_dialer_runtime_map = {}

        self._seedos_register_dialer_learning_events()

        self._seedos_discover_dialer_runtime()

        try:
            self._seedos_read_bound_runtime_definitions()
        except Exception as exc:
            logger = getattr(
                self,
                "logger",
                logging.getLogger(__name__),
            )

            logger.debug(
                "[DEVHUD] Initial Dialer definition read skipped: %s",
                exc,
            )


    # ==========================================================
    # EXISTING EVENTBUS OBSERVATION
    # ==========================================================

    def _seedos_register_dialer_learning_events(self):
        """
        Observe existing SEED runtime events.

        Uses the already-bound SEEDEventBus only.
        """

        event_bus = getattr(
            self,
            "event_bus",
            None,
        )

        if event_bus is None:
            return False

        subscribe = getattr(
            event_bus,
            "subscribe",
            None,
        )

        if not callable(subscribe):
            return False

        subscriptions = {
            "SEED_INPUT":
                self._seedos_dialer_observe_input,

            "SEED_OUTPUT":
                self._seedos_dialer_observe_output,

            "SEED_COMMAND":
                self._seedos_dialer_observe_command,

            "SEED_COMMAND_RESULT":
                self._seedos_dialer_observe_command_result,

            "SEED_COMMAND_DENIED":
                self._seedos_dialer_observe_command_denied,

            "QBIT_EXECUTE":
                self._seedos_dialer_observe_qbit_execution,

            "SEED_STATUS":
                self._seedos_dialer_observe_status,

            "SEED_HEARTBEAT":
                self._seedos_dialer_observe_heartbeat,

            "THOUGHT":
                self._seedos_dialer_observe_thought,

            "STATE":
                self._seedos_dialer_observe_state,

            "SEED_ERROR":
                self._seedos_dialer_observe_error,

            "ERROR":
                self._seedos_dialer_observe_error,
        }

        registered = 0

        for event_name, callback in subscriptions.items():

            try:
                subscribe(
                    event_name,
                    callback,
                )

                registered += 1

            except Exception:
                continue

        return bool(registered)


    # ==========================================================
    # RUNTIME DISCOVERY
    # ==========================================================

    def _seedos_discover_dialer_runtime(self):
        """
        Build a map of already-bound SEED systems.

        No runtime objects are constructed.
        """

        runtime_candidates = {
            "DEVHUD":
                self,

            "QbitDialer":
                getattr(
                    self,
                    "qbit_dialer",
                    None,
                ),

            "QbitQueueLoop":
                getattr(
                    self,
                    "qbit_queue",
                    None,
                ),

            "SEEDEventBus":
                getattr(
                    self,
                    "event_bus",
                    None,
                ),

            "TrackSystem":
                getattr(
                    self,
                    "track_system",
                    None,
                ),

            "IPCBridge":
                getattr(
                    self,
                    "ipc_bridge",
                    None,
                ),

            "Oracle":
                getattr(
                    self,
                    "oracle",
                    None,
                )
                or getattr(
                    self,
                    "oracle_loop",
                    None,
                ),

            "Heartbeat":
                getattr(
                    self,
                    "heartbeat",
                    None,
                ),

            "HeartbeatEmitter":
                getattr(
                    self,
                    "heartbeat_emitter",
                    None,
                ),

            "SEEDCore":
                getattr(
                    self,
                    "core",
                    None,
                ),

            "ModuleRegistry":
                getattr(
                    self,
                    "module_registry",
                    None,
                ),

            "OptionRegistry":
                getattr(
                    self,
                    "option_registry",
                    None,
                ),

            "MemoryCrystallizer":
                getattr(
                    self,
                    "memory_crystallizer",
                    None,
                ),
        }

        dialer = runtime_candidates.get(
            "QbitDialer"
        )

        if dialer is not None:

            cognition_candidates = {
                "ComputeBrain":
                    "compute_brain",

                "TransformerBrain":
                    "transformer_brain",

                "IntentEngine":
                    "intent_engine",

                "ActionEngine":
                    "action_engine",

                "AnalyticsEngine":
                    "analytics_engine",

                "ThoughtFeedback":
                    "thought_feedback",

                "PriorityEngine":
                    "priority_engine",

                "CognitionMap":
                    "cognition_map",
            }

            for system_name, attr_name in cognition_candidates.items():

                runtime_candidates[
                    system_name
                ] = getattr(
                    dialer,
                    attr_name,
                    None,
                )

        self._seedos_dialer_runtime_map = {
            name: obj
            for name, obj in runtime_candidates.items()
            if obj is not None
        }

        return dict(
            self._seedos_dialer_runtime_map
        )


    # ==========================================================
    # SAFE RUNTIME DESCRIPTION
    # ==========================================================

    def _seedos_describe_bound_runtime_system(
        self,
        name,
        system,
    ):
        """
        Describe a bound system without invoking it.
        """

        if system is None:
            return None

        system_class = getattr(
            system,
            "__class__",
            None,
        )

        class_name = (
            getattr(
                system_class,
                "__name__",
                None,
            )
            if system_class is not None
            else None
        )

        module_name = (
            getattr(
                system_class,
                "__module__",
                None,
            )
            if system_class is not None
            else None
        )

        return {
            "system":
                str(name),

            "class":
                class_name,

            "module":
                module_name,

            "bound":
                True,

            "runtime_instance":
                True,

            "authority":
                self._seedos_runtime_authority_for_system(
                    str(name)
                ),

            "source":
                "BOUND_RUNTIME",

            "executable":
                False,
        }


    def _seedos_runtime_authority_for_system(
        self,
        system_name,
    ):
        """
        Return the known SEED authority role for a runtime system.
        """

        authorities = {
            "QbitDialer":
                "COMMAND_AUTHORITY",

            "QbitQueueLoop":
                "EXECUTION_TRANSPORT",

            "SEEDEventBus":
                "EVENT_TRANSPORT",

            "TrackSystem":
                "TRACK_CONTEXT",

            "Heartbeat":
                "CLOCK_OBSERVER",

            "HeartbeatEmitter":
                "QBIT_SIGNAL_SOURCE",

            "Oracle":
                "OBSERVER_GOVERNANCE",

            "ComputeBrain":
                "THOUGHT_GENERATION",

            "TransformerBrain":
                "THOUGHT_TRANSFORMATION",

            "IntentEngine":
                "INTERPRETATION",

            "ActionEngine":
                "ACTION_PROPOSAL",

            "AnalyticsEngine":
                "CYCLE_OBSERVATION",

            "ThoughtFeedback":
                "LEARNING_FEEDBACK",

            "DEVHUD":
                "DEVELOPER_INTERFACE",

            "FATHUD":
                "DEVELOPER_OBSERVER",

            "IPCBridge":
                "INTERPROCESS_BRIDGE",

            "ModuleRegistry":
                "MODULE_REGISTRY",

            "OptionRegistry":
                "OPTION_REGISTRY",
        }

        return authorities.get(
            system_name,
            "OBSERVED_RUNTIME_SYSTEM",
        )


    # ==========================================================
    # DEFINITION READER
    # ==========================================================

    def _seedos_read_bound_runtime_definitions(self):
        """
        Read Python definitions from already-bound runtime systems.

        Nothing is executed.
        """

        runtime_map = (
            getattr(
                self,
                "_seedos_dialer_runtime_map",
                None,
            )
            or self._seedos_discover_dialer_runtime()
        )

        results = {}

        for system_name, system in runtime_map.items():

            try:
                extracted = self._seedos_extract_runtime_defs(
                    system_name,
                    system,
                )

                results[
                    system_name
                ] = extracted

            except Exception as exc:
                results[
                    system_name
                ] = {
                    "status":
                        "ERROR",

                    "error":
                        str(exc),
                }

        return results


    def _seedos_extract_runtime_defs(
        self,
        system_name,
        system,
    ):
        """
        Extract method definitions from a bound runtime class.

        Uses inspect only.

        Functions are never called.
        """

        if system is None:
            return {
                "status":
                    "UNBOUND",

                "definitions":
                    [],
            }

        try:
            import inspect
        except Exception:
            return {
                "status":
                    "INSPECT_UNAVAILABLE",

                "definitions":
                    [],
            }

        system_class = getattr(
            system,
            "__class__",
            None,
        )

        if system_class is None:
            return {
                "status":
                    "NO_CLASS",

                "definitions":
                    [],
            }

        definitions = []

        try:
            members = inspect.getmembers(
                system_class,
            )
        except Exception:
            members = []

        for def_name, member in members:

            if not (
                inspect.isfunction(member)
                or inspect.ismethod(member)
            ):
                continue

            try:
                signature = str(
                    inspect.signature(
                        member
                    )
                )
            except Exception:
                signature = None

            try:
                doc = inspect.getdoc(
                    member
                )
            except Exception:
                doc = None

            definition = {
                "system":
                    system_name,

                "name":
                    def_name,

                "signature":
                    signature,

                "doc":
                    doc,

                "class":
                    getattr(
                        system_class,
                        "__name__",
                        None,
                    ),

                "module":
                    getattr(
                        system_class,
                        "__module__",
                        None,
                    ),

                "source":
                    "RUNTIME_DEF_READ",

                "executed":
                    False,
            }

            definitions.append(
                definition
            )

            self._seedos_learn_definition(
                definition
            )

        return {
            "status":
                "READ",

            "system":
                system_name,

            "definition_count":
                len(definitions),

            "definitions":
                definitions,
        }


    # ==========================================================
    # DEFINITION LEARNING
    # ==========================================================

    def _seedos_definition_key(
        self,
        definition,
    ):
        """
        Produce a stable identifier for a discovered definition.
        """

        system_name = str(
            definition.get(
                "system",
                ""
            )
        )

        def_name = str(
            definition.get(
                "name",
                ""
            )
        )

        signature = str(
            definition.get(
                "signature",
                ""
            )
        )

        return (
            system_name,
            def_name,
            signature,
        )


    def _seedos_learn_definition(
        self,
        definition,
    ):
        """
        Store a discovered definition in the SEED JSON knowledge fabric.
        """

        if not isinstance(
            definition,
            dict,
        ):
            return None

        key = self._seedos_definition_key(
            definition
        )

        seen = getattr(
            self,
            "_seedos_dialer_seen_defs",
            set(),
        )

        if key in seen:
            return None

        seen.add(
            key
        )

        self._seedos_dialer_seen_defs = seen

        self._seedos_dialer_definition_count += 1

        record = None

        json_record = getattr(
            self,
            "seedos_json_record",
            None,
        )

        if callable(json_record):

            try:
                record = json_record(
                    "DEF",
                    definition,
                )
            except Exception:
                record = None

        self._seedos_extract_candidate_command(
            definition
        )

        self._seedos_infer_definition_connections(
            definition
        )

        return record or definition


    # ==========================================================
    # COMMAND CANDIDATE EXTRACTION
    # ==========================================================

    def _seedos_extract_candidate_command(
        self,
        definition,
    ):
        """
        Determine whether a discovered definition resembles
        a SEED command capability.

        This creates KNOWLEDGE ONLY.

        It does not register or execute the command.
        """

        if not isinstance(
            definition,
            dict,
        ):
            return None

        def_name = str(
            definition.get(
                "name",
                ""
            )
        )

        if not def_name:
            return None

        lowered = def_name.lower()

        ignored_prefixes = (
            "__",
            "_seedos_",
            "_build_",
            "_handle_",
            "_on_",
        )

        if lowered.startswith(
            ignored_prefixes
        ):
            return None

        command_words = (
            "command",
            "submit",
            "send",
            "status",
            "pause",
            "resume",
            "snapshot",
            "measure",
            "prioritize",
            "defer",
            "throttle",
            "queue",
            "execute",
            "dispatch",
            "route",
            "connect",
            "inspect",
            "test",
            "review",
            "learn",
            "teach",
            "suggest",
            "develop",
            "register",
        )

        looks_like_command = any(
            word in lowered
            for word in command_words
        )

        if not looks_like_command:
            return None

        command_name = (
            def_name
            .strip("_")
            .upper()
        )

        command_key = (
            str(
                definition.get(
                    "system",
                    ""
                )
            ),
            command_name,
        )

        seen = getattr(
            self,
            "_seedos_dialer_seen_commands",
            set(),
        )

        if command_key in seen:
            return None

        seen.add(
            command_key
        )

        self._seedos_dialer_seen_commands = seen

        candidate = {
            "command":
                command_name,

            "source_def":
                def_name,

            "system":
                definition.get(
                    "system"
                ),

            "signature":
                definition.get(
                    "signature"
                ),

            "description":
                definition.get(
                    "doc"
                ),

            "classification":
                "COMMAND_CANDIDATE",

            "command_authority":
                "QbitDialer",

            "requires_submit_command":
                True,

            "execution_authority":
                "QbitQueueLoop",

            "registered":
                False,

            "executable":
                False,

            "discovered":
                True,

            "source":
                "DEF_EXTRACTION",
        }

        self._seedos_dialer_command_count += 1

        json_record = getattr(
            self,
            "seedos_json_record",
            None,
        )

        if callable(json_record):

            try:
                json_record(
                    "COMMAND",
                    candidate,
                )
            except Exception:
                pass

        return candidate


    # ==========================================================
    # CONNECTION DISCOVERY
    # ==========================================================

    def _seedos_infer_definition_connections(
        self,
        definition,
    ):
        """
        Discover possible relationships between a definition
        and known SEED systems.

        Relationships remain candidates until SEED has evidence.
        """

        if not isinstance(
            definition,
            dict,
        ):
            return []

        source_system = str(
            definition.get(
                "system",
                ""
            )
        )

        text = " ".join(
            str(
                definition.get(
                    field,
                    ""
                )
            )
            for field in (
                "name",
                "signature",
                "doc",
            )
        ).lower()

        known_systems = {
            "qbit":
                "Qbit",

            "dialer":
                "QbitDialer",

            "queue":
                "QbitQueueLoop",

            "event":
                "SEEDEventBus",

            "track":
                "TrackSystem",

            "oracle":
                "Oracle",

            "heartbeat":
                "Heartbeat",

            "intent":
                "IntentEngine",

            "action":
                "ActionEngine",

            "analytic":
                "AnalyticsEngine",

            "thought":
                "ThoughtFeedback",

            "compute":
                "ComputeBrain",

            "transformer":
                "TransformerBrain",

            "memory":
                "MemoryCrystallizer",

            "ipc":
                "IPCBridge",

            "registry":
                "ModuleRegistry",

            "module":
                "ModuleRegistry",

            "fathud":
                "FATHUD",

            "devhud":
                "DEVHUD",
        }

        discovered = []

        for token, target_system in known_systems.items():

            if token not in text:
                continue

            if target_system == source_system:
                continue

            connection = {
                "source_system":
                    source_system,

                "source_def":
                    definition.get(
                        "name"
                    ),

                "target_system":
                    target_system,

                "relationship":
                    "CANDIDATE",

                "evidence":
                    "DEF_TEXT_REFERENCE",

                "confidence":
                    "UNVERIFIED",

                "executed":
                    False,
            }

            connection_key = (
                source_system,
                definition.get(
                    "name"
                ),
                target_system,
            )

            seen = getattr(
                self,
                "_seedos_dialer_seen_connections",
                set(),
            )

            if connection_key in seen:
                continue

            seen.add(
                connection_key
            )

            self._seedos_dialer_seen_connections = seen

            self._seedos_dialer_connection_count += 1

            discovered.append(
                connection
            )

            json_record = getattr(
                self,
                "seedos_json_record",
                None,
            )

            if callable(json_record):

                try:
                    json_record(
                        "CONNECTION",
                        connection,
                    )
                except Exception:
                    pass

        return discovered


    # ==========================================================
    # EXISTING DIALER IDLE / READ STATE
    # ==========================================================

    def seedos_read_dialer_idle_state(self):
        """
        Read the current QbitDialer state.

        This method DOES NOT start an idle loop.

        It is designed to be called by an existing Dialer idle/read
        cycle, heartbeat observation, DEVHUD refresh, or other
        authorized runtime callback.
        """

        dialer = getattr(
            self,
            "qbit_dialer",
            None,
        )

        if dialer is None:
            return self._seedos_dialer_ask(
                reason="QbitDialer is not bound.",
                context={
                    "operation":
                        "READ_DIALER_IDLE_STATE",
                },
            )

        state_fields = (
            "active",
            "running",
            "online",
            "runtime",
            "state",
            "status",
            "commands",
            "qbit_commands",
            "current_qbit",
            "active_qbit",
            "current_task",
            "active_task",
            "single_task",
            "heartbeat_supervised",
            "qbit_rate",
            "telemetry_rate",
        )

        observation = {
            "type":
                "DIALER_IDLE_READ",

            "authority":
                "QbitDialer",

            "execution":
                False,

            "fields":
                {},
        }

        for field_name in state_fields:

            try:
                value = getattr(
                    dialer,
                    field_name,
                )
            except Exception:
                continue

            if callable(value):
                continue

            try:
                safe_value = (
                    self._seedos_json_safe_copy(
                        value
                    )
                    if hasattr(
                        self,
                        "_seedos_json_safe_copy",
                    )
                    else repr(
                        value
                    )
                )
            except Exception:
                safe_value = repr(
                    value
                )

            observation[
                "fields"
            ][
                field_name
            ] = safe_value

        self._seedos_process_dialer_observation(
            observation
        )

        return observation


    # ==========================================================
    # EXTERNAL IDLE / READ ADAPTER ENTRY
    # ==========================================================

    def seedos_process_dialer_idle_read(
        self,
        payload=None,
        *,
        source="QbitDialer",
        metadata=None,
    ):
        """
        Public adapter entry for the EXISTING Dialer idle/read cycle.

        QbitDialer may call this method when it has readable idle
        observations available.

        DEVHUD does not schedule that cycle.
        """

        observation = {
            "type":
                "DIALER_IDLE_READ",

            "source":
                source,

            "payload":
                payload,

            "metadata":
                metadata or {},

            "command_authority":
                "QbitDialer",

            "execution_authority":
                "QbitQueueLoop",

            "executed":
                False,
        }

        return self._seedos_process_dialer_observation(
            observation
        )


    # ==========================================================
    # OBSERVATION PROCESSOR
    # ==========================================================

    def _seedos_process_dialer_observation(
        self,
        observation,
    ):
        """
        Convert runtime observations into structured SEED knowledge.
        """

        if not isinstance(
            observation,
            dict,
        ):
            return self._seedos_dialer_ask(
                reason="Dialer observation was not a mapping.",
                context={
                    "observation":
                        repr(
                            observation
                        ),
                },
            )

        self._seedos_dialer_observation_count += 1

        self._seedos_dialer_learning_history.append(
            observation
        )

        if len(
            self._seedos_dialer_learning_history
        ) > 500:

            self._seedos_dialer_learning_history = (
                self._seedos_dialer_learning_history[
                    -500:
                ]
            )

        json_record = getattr(
            self,
            "seedos_json_record",
            None,
        )

        if callable(json_record):

            try:
                json_record(
                    "OBSERVATION",
                    observation,
                )
            except Exception:
                pass

        self._seedos_discover_dialer_runtime()

        return {
            "status":
                "OBSERVED",

            "observation_count":
                self._seedos_dialer_observation_count,

            "definition_count":
                self._seedos_dialer_definition_count,

            "command_candidate_count":
                self._seedos_dialer_command_count,

            "connection_count":
                self._seedos_dialer_connection_count,
        }


    # ==========================================================
    # ASK FALLBACK
    # ==========================================================

    def _seedos_dialer_ask(
        self,
        *,
        reason,
        context=None,
    ):
        """
        ASK rather than invent meaning when the adapter cannot
        safely determine what an observation represents.
        """

        self._seedos_dialer_question_count += 1

        question = {
            "type":
                "SYSTEM_QUESTION",

            "system":
                "DEVHUD",

            "target":
                "SEED",

            "reason":
                str(
                    reason
                ),

            "context":
                context or {},

            "requires_answer":
                True,

            "authority":
                "QbitDialer",

            "execution":
                False,
        }

        resolver = getattr(
            self,
            "seedos_resolve_blocked_state",
            None,
        )

        if callable(resolver):

            try:
                return resolver(
                    reason=str(
                        reason
                    ),
                    context=context or {},
                )
            except TypeError:
                pass
            except Exception:
                pass

        command = getattr(
            self,
            "seedos_ask",
            None,
        )

        if callable(command):

            try:
                return command(
                    str(
                        reason
                    ),
                    context=context or {},
                )
            except TypeError:
                pass
            except Exception:
                pass

        json_record = getattr(
            self,
            "seedos_json_record",
            None,
        )

        if callable(json_record):

            try:
                json_record(
                    "QUESTION",
                    question,
                )
            except Exception:
                pass

        return question


    # ==========================================================
    # EVENT OBSERVERS
    # ==========================================================

    def _seedos_dialer_observe_input(
        self,
        payload=None,
        *args,
        **kwargs,
    ):
        return self._seedos_process_dialer_observation({
            "event":
                "SEED_INPUT",

            "payload":
                payload,

            "metadata":
                kwargs,
        })


    def _seedos_dialer_observe_output(
        self,
        payload=None,
        *args,
        **kwargs,
    ):
        return self._seedos_process_dialer_observation({
            "event":
                "SEED_OUTPUT",

            "payload":
                payload,

            "metadata":
                kwargs,
        })


    def _seedos_dialer_observe_command(
        self,
        payload=None,
        *args,
        **kwargs,
    ):
        return self._seedos_process_dialer_observation({
            "event":
                "SEED_COMMAND",

            "payload":
                payload,

            "authority":
                "QbitDialer",

            "metadata":
                kwargs,
        })


    def _seedos_dialer_observe_command_result(
        self,
        payload=None,
        *args,
        **kwargs,
    ):
        return self._seedos_process_dialer_observation({
            "event":
                "SEED_COMMAND_RESULT",

            "payload":
                payload,

            "authority":
                "QbitDialer",

            "execution_authority":
                "QbitQueueLoop",

            "metadata":
                kwargs,
        })


    def _seedos_dialer_observe_command_denied(
        self,
        payload=None,
        *args,
        **kwargs,
    ):
        return self._seedos_process_dialer_observation({
            "event":
                "SEED_COMMAND_DENIED",

            "payload":
                payload,

            "authority":
                "QbitDialer",

            "metadata":
                kwargs,
        })


    def _seedos_dialer_observe_qbit_execution(
        self,
        payload=None,
        *args,
        **kwargs,
    ):
        return self._seedos_process_dialer_observation({
            "event":
                "QBIT_EXECUTE",

            "payload":
                payload,

            "transport":
                "QbitQueueLoop",

            "metadata":
                kwargs,
        })


    def _seedos_dialer_observe_status(
        self,
        payload=None,
        *args,
        **kwargs,
    ):
        return self._seedos_process_dialer_observation({
            "event":
                "SEED_STATUS",

            "payload":
                payload,

            "metadata":
                kwargs,
        })


    def _seedos_dialer_observe_heartbeat(
        self,
        payload=None,
        *args,
        **kwargs,
    ):
        observation = {
            "event":
                "SEED_HEARTBEAT",

            "payload":
                payload,

            "source":
                "Heartbeat",

            "metadata":
                kwargs,
        }

        result = self._seedos_process_dialer_observation(
            observation
        )

        try:
            self.seedos_read_dialer_idle_state()
        except Exception:
            pass

        return result


    def _seedos_dialer_observe_thought(
        self,
        payload=None,
        *args,
        **kwargs,
    ):
        return self._seedos_process_dialer_observation({
            "event":
                "THOUGHT",

            "payload":
                payload,

            "pipeline":
                "COGNITION",

            "metadata":
                kwargs,
        })


    def _seedos_dialer_observe_state(
        self,
        payload=None,
        *args,
        **kwargs,
    ):
        return self._seedos_process_dialer_observation({
            "event":
                "STATE",

            "payload":
                payload,

            "metadata":
                kwargs,
        })


    def _seedos_dialer_observe_error(
        self,
        payload=None,
        *args,
        **kwargs,
    ):
        return self._seedos_process_dialer_observation({
            "event":
                "SEED_ERROR",

            "payload":
                payload,

            "metadata":
                kwargs,
        })


    # ==========================================================
    # MANUAL / EXISTING-RUNTIME READ
    # ==========================================================

    def seedos_refresh_runtime_definitions(self):
        """
        Re-read bound runtime definitions and discover anything new.

        Existing definitions are deduplicated.
        """

        self._seedos_discover_dialer_runtime()

        return self._seedos_read_bound_runtime_definitions()


    # ==========================================================
    # DIALER LEARNING STATUS
    # ==========================================================

    def seedos_dialer_learning_status(self):
        """
        Return the current Dialer learning adapter state.
        """

        return {
            "initialized":
                getattr(
                    self,
                    "_seedos_dialer_learning_initialized",
                    False,
                ),

            "enabled":
                getattr(
                    self,
                    "_seedos_dialer_learning_enabled",
                    False,
                ),

            "command_authority":
                "QbitDialer",

            "execution_transport":
                "QbitQueueLoop",

            "event_transport":
                "SEEDEventBus",

            "creates_runtime_loop":
                False,

            "creates_qbits":
                False,

            "executes_discovered_defs":
                False,

            "observations":
                getattr(
                    self,
                    "_seedos_dialer_observation_count",
                    0,
                ),

            "definitions":
                getattr(
                    self,
                    "_seedos_dialer_definition_count",
                    0,
                ),

            "command_candidates":
                getattr(
                    self,
                    "_seedos_dialer_command_count",
                    0,
                ),

            "connections":
                getattr(
                    self,
                    "_seedos_dialer_connection_count",
                    0,
                ),

            "questions":
                getattr(
                    self,
                    "_seedos_dialer_question_count",
                    0,
                ),

            "runtime_systems":
                sorted(
                    list(
                        getattr(
                            self,
                            "_seedos_dialer_runtime_map",
                            {},
                        ).keys()
                    )
                ),
        }


    # ==========================================================
    # DIALER LEARNING SNAPSHOT
    # ==========================================================

    def seedos_dialer_learning_snapshot(self):
        """
        Produce a snapshot suitable for DEVHUD, Oracle,
        FATHUD observation, JSON persistence, or SEED cognition.
        """

        return {
            "status":
                self.seedos_dialer_learning_status(),

            "runtime":
                {
                    name:
                        self._seedos_describe_bound_runtime_system(
                            name,
                            system,
                        )

                    for name, system in getattr(
                        self,
                        "_seedos_dialer_runtime_map",
                        {},
                    ).items()
                },

            "recent_observations":
                list(
                    getattr(
                        self,
                        "_seedos_dialer_learning_history",
                        [],
                    )[
                        -50:
                    ]
                ),

            "learning_path": [
                "QbitDialer idle/read observation",
                "DEVHUD Dialer Learning Adapter",
                "runtime DEF inspection",
                "DEF knowledge",
                "command candidate extraction",
                "connection candidate extraction",
                "JSON Knowledge Fabric",
                "SEED cognition",
                "ASK when uncertain",
                "QbitDialer submit_command authority",
                "QbitQueueLoop execution",
            ],
        }

    # ==========================================================
    # SECTION 23
    # SEED OS DYNAMIC EXPANSION / DISCOVERY RESOLUTION FABRIC
    # ==========================================================
    #
    # PURPOSE:
    #     Take definitions and command candidates discovered by
    #     Section 22 and compare them against the existing SEED
    #     dynamic capability architecture.
    #
    #     Discovery is NOT promotion.
    #
    #     The path is:
    #
    #         Dialer READ
    #             ↓
    #         DEF discovered
    #             ↓
    #         COMMAND candidate
    #             ↓
    #         Registry comparison
    #             ↓
    #         Capability classification
    #             ↓
    #         SDK / MCP / Provider / Adapter relationship
    #             ↓
    #         Sandbox
    #             ↓
    #         Validation
    #             ↓
    #         Review
    #             ↓
    #         SEED decision
    #             ↓
    #         QbitDialer authority
    #
    #     Nothing in this section executes discovered code.
    #
    # ==========================================================


    def _initialize_seedos_dynamic_expansion_fabric(self):
        """
        Initialize the dynamic expansion fabric.

        This fabric connects runtime discovery to the existing
        capability builder, registries, sandbox, learning system,
        SDK/MCP descriptors, and development plan.
        """

        if getattr(
            self,
            "_seedos_dynamic_expansion_initialized",
            False,
        ):
            return

        self._seedos_dynamic_expansion_initialized = True

        self._seedos_dynamic_expansion_enabled = True

        self._seedos_dynamic_discoveries = {}

        self._seedos_dynamic_candidates = {}

        self._seedos_dynamic_matches = {}

        self._seedos_dynamic_unresolved = {}

        self._seedos_dynamic_history = []

        self._seedos_dynamic_counts = {
            "discoveries": 0,
            "new_definitions": 0,
            "command_candidates": 0,
            "existing_matches": 0,
            "capability_matches": 0,
            "sdk_candidates": 0,
            "mcp_candidates": 0,
            "provider_candidates": 0,
            "adapter_candidates": 0,
            "unresolved": 0,
            "questions": 0,
        }


    # ==========================================================
    # DISCOVERY KEY
    # ==========================================================

    def _seedos_dynamic_discovery_key(
        self,
        discovery,
    ):
        """
        Create a stable key for a discovered runtime capability.
        """

        if not isinstance(
            discovery,
            dict,
        ):
            return (
                "UNKNOWN",
                repr(
                    discovery
                ),
            )

        system = str(
            discovery.get(
                "system",
                ""
            )
        )

        name = str(
            discovery.get(
                "name",
                discovery.get(
                    "command",
                    ""
                ),
            )
        )

        signature = str(
            discovery.get(
                "signature",
                ""
            )
        )

        return (
            system,
            name,
            signature,
        )


    # ==========================================================
    # DISCOVERY REGISTRATION
    # ==========================================================

    def seedos_register_dynamic_discovery(
        self,
        discovery,
    ):
        """
        Register a discovery produced by the Dialer learning
        adapter.

        Registration is knowledge storage only.
        """

        if not isinstance(
            discovery,
            dict,
        ):
            return self._seedos_dynamic_ask(
                "Dynamic discovery must be a mapping.",
                {
                    "discovery":
                        repr(
                            discovery
                        ),
                },
            )

        key = self._seedos_dynamic_discovery_key(
            discovery
        )

        if key in self._seedos_dynamic_discoveries:
            return self._seedos_dynamic_discoveries[
                key
            ]

        record = dict(
            discovery
        )

        record[
            "discovery_key"
        ] = key

        record[
            "status"
        ] = "DISCOVERED"

        record[
            "promoted"
        ] = False

        record[
            "executed"
        ] = False

        record[
            "authority"
        ] = "QbitDialer"

        record[
            "execution_authority"
        ] = "QbitQueueLoop"

        self._seedos_dynamic_discoveries[
            key
        ] = record

        self._seedos_dynamic_counts[
            "discoveries"
        ] += 1

        self._seedos_dynamic_history.append(
            record
        )

        return record


    # ==========================================================
    # REGISTRY RESOLUTION
    # ==========================================================

    def _seedos_dynamic_registry_objects(self):
        """
        Return existing registry references.

        No registry is constructed here.
        """

        return {
            "ModuleRegistry":
                getattr(
                    self,
                    "module_registry",
                    None,
                ),

            "OptionRegistry":
                getattr(
                    self,
                    "option_registry",
                    None,
                ),

            "Registry":
                getattr(
                    self,
                    "registry",
                    None,
                ),

            "NodeRegistry":
                getattr(
                    self,
                    "node_registry",
                    None,
                ),

            "NodeManager":
                getattr(
                    self,
                    "node_manager",
                    None,
                ),
        }


    def _seedos_dynamic_registry_match(
        self,
        discovery,
    ):
        """
        Compare a discovery against existing registry objects.

        Registry APIs are not assumed.
        """

        matches = []

        if not isinstance(
            discovery,
            dict,
        ):
            return matches

        name_text = " ".join(
            str(
                discovery.get(
                    field,
                    ""
                )
            )
            for field in (
                "name",
                "command",
                "system",
                "description",
                "doc",
            )
        ).lower()

        for registry_name, registry in (
            self._seedos_dynamic_registry_objects()
        ).items():

            if registry is None:
                continue

            registry_class = getattr(
                registry,
                "__class__",
                None,
            )

            registry_text = " ".join(
                str(
                    value
                )
                for value in (
                    getattr(
                        registry_class,
                        "__name__",
                        ""
                    ),
                    getattr(
                        registry_class,
                        "__module__",
                        ""
                    ),
                )
            ).lower()

            candidate = {
                "registry":
                    registry_name,

                "discovery":
                    self._seedos_dynamic_discovery_key(
                        discovery
                    ),

                "relationship":
                    "POTENTIAL_REGISTRY_MATCH",

                "evidence":
                    [],

                "confidence":
                    "LOW",

                "executed":
                    False,
            }

            if registry_name.lower() in name_text:
                candidate[
                    "evidence"
                ].append(
                    "DISCOVERY_NAME_REFERENCE"
                )

            if registry_text and any(
                token in name_text
                for token in (
                    registry_name.lower(),
                    "registry",
                    "module",
                    "option",
                    "node",
                )
            ):
                candidate[
                    "evidence"
                ].append(
                    "REGISTRY_CONTEXT_REFERENCE"
                )

            if candidate[
                "evidence"
            ]:
                candidate[
                    "confidence"
                ] = "CANDIDATE"

                matches.append(
                    candidate
                )

        return matches


    # ==========================================================
    # CAPABILITY CLASSIFICATION
    # ==========================================================

    def _seedos_classify_dynamic_discovery(
        self,
        discovery,
    ):
        """
        Classify a discovery into one or more development paths.

        Classification does not authorize execution.
        """

        if not isinstance(
            discovery,
            dict,
        ):
            return {
                "classification":
                    "UNKNOWN",
                "paths":
                    [],
            }

        text = " ".join(
            str(
                discovery.get(
                    field,
                    ""
                )
            )
            for field in (
                "name",
                "command",
                "system",
                "description",
                "doc",
                "source",
            )
        ).lower()

        paths = []

        if any(
            token in text
            for token in (
                "sdk",
                "software development",
                "api",
                "client",
            )
        ):
            paths.append(
                "SDK"
            )

        if any(
            token in text
            for token in (
                "mcp",
                "model context protocol",
                "tool server",
                "tool client",
            )
        ):
            paths.append(
                "MCP"
            )

        if any(
            token in text
            for token in (
                "provider",
                "external service",
                "service",
                "integration",
            )
        ):
            paths.append(
                "PROVIDER"
            )

        if any(
            token in text
            for token in (
                "adapter",
                "translate",
                "normalize",
                "connector",
            )
        ):
            paths.append(
                "ADAPTER"
            )

        if any(
            token in text
            for token in (
                "module",
                "plugin",
                "capability",
                "subsystem",
            )
        ):
            paths.append(
                "CAPABILITY"
            )

        if not paths:
            paths.append(
                "GENERAL_DEVELOPMENT"
            )

        return {
            "classification":
                "DYNAMIC_DISCOVERY",

            "paths":
                list(
                    dict.fromkeys(
                        paths
                    )
                ),

            "executed":
                False,
        }


    # ==========================================================
    # FULL DISCOVERY RESOLUTION
    # ==========================================================

    def seedos_resolve_dynamic_discovery(
        self,
        discovery,
    ):
        """
        Resolve a discovered DEF/COMMAND against SEED's
        existing development architecture.
        """

        registered = (
            self.seedos_register_dynamic_discovery(
                discovery
            )
        )

        classification = (
            self._seedos_classify_dynamic_discovery(
                registered
            )
        )

        registry_matches = (
            self._seedos_dynamic_registry_match(
                registered
            )
        )

        capability_matches = []

        capability_lookup = getattr(
            self,
            "inspect_seedos_capability",
            None,
        )

        if callable(
            capability_lookup
        ):

            lookup_values = []

            for value in (
                registered.get(
                    "name"
                ),
                registered.get(
                    "command"
                ),
                registered.get(
                    "system"
                ),
            ):

                if value:
                    lookup_values.append(
                        str(
                            value
                        )
                    )

            for value in lookup_values:

                try:
                    result = capability_lookup(
                        value
                    )

                    if result:
                        capability_matches.append(
                            result
                        )

                except Exception:
                    continue

        resolved = {
            "discovery":
                registered,

            "classification":
                classification,

            "registry_matches":
                registry_matches,

            "capability_matches":
                capability_matches,

            "paths":
                classification.get(
                    "paths",
                    [],
                ),

            "status":
                "RESOLVED"
                if (
                    registry_matches
                    or capability_matches
                )
                else "UNRESOLVED",

            "promotion_required":
                True,

            "execution_required":
                False,

            "authority":
                "QbitDialer",
        }

        key = registered[
            "discovery_key"
        ]

        self._seedos_dynamic_matches[
            key
        ] = resolved

        if registry_matches:
            self._seedos_dynamic_counts[
                "existing_matches"
            ] += len(
                registry_matches
            )

        if capability_matches:
            self._seedos_dynamic_counts[
                "capability_matches"
            ] += len(
                capability_matches
            )

        if resolved[
            "status"
        ] == "UNRESOLVED":

            self._seedos_dynamic_unresolved[
                key
            ] = resolved

            self._seedos_dynamic_counts[
                "unresolved"
            ] += 1

        self._seedos_dynamic_history.append(
            resolved
        )

        return resolved


    # ==========================================================
    # SDK / MCP / PROVIDER / ADAPTER CANDIDATES
    # ==========================================================

    def _seedos_build_dynamic_capability_paths(
        self,
        resolved,
    ):
        """
        Convert discovery classification into structured
        development proposals.

        Proposals are not installations or executions.
        """

        if not isinstance(
            resolved,
            dict,
        ):
            return []

        discovery = resolved.get(
            "discovery",
            {},
        )

        paths = resolved.get(
            "paths",
            [],
        )

        proposals = []

        for path in paths:

            proposal = {
                "type":
                    path,

                "status":
                    "PROPOSAL",

                "source":
                    discovery,

                "authority":
                    "QbitDialer",

                "execution_authority":
                    "QbitQueueLoop",

                "requires_sandbox":
                    True,

                "requires_validation":
                    True,

                "requires_review":
                    True,

                "install":
                    False,

                "execute":
                    False,
            }

            proposals.append(
                proposal
            )

            if path == "SDK":
                self._seedos_dynamic_counts[
                    "sdk_candidates"
                ] += 1

            elif path == "MCP":
                self._seedos_dynamic_counts[
                    "mcp_candidates"
                ] += 1

            elif path == "PROVIDER":
                self._seedos_dynamic_counts[
                    "provider_candidates"
                ] += 1

            elif path == "ADAPTER":
                self._seedos_dynamic_counts[
                    "adapter_candidates"
                ] += 1

        return proposals


    def seedos_build_dynamic_proposal(
        self,
        discovery,
    ):
        """
        Build the complete development proposal for a
        runtime discovery.
        """

        resolved = (
            self.seedos_resolve_dynamic_discovery(
                discovery
            )
        )

        proposals = (
            self._seedos_build_dynamic_capability_paths(
                resolved
            )
        )

        result = {
            "status":
                "PROPOSAL_READY",

            "resolved":
                resolved,

            "proposals":
                proposals,

            "requires":
                [
                    "SANDBOX",
                    "VALIDATION",
                    "REVIEW",
                    "PROMOTION",
                ],

            "execution":
                False,

            "installation":
                False,
        }

        json_record = getattr(
            self,
            "seedos_json_record",
            None,
        )

        if callable(
            json_record
        ):

            try:
                json_record(
                    "DEVELOPMENT",
                    result,
                )
            except Exception:
                pass

        return result


    # ==========================================================
    # PROCESS DISCOVERED DEFINITION
    # ==========================================================

    def seedos_process_discovered_definition(
        self,
        definition,
    ):
        """
        Main bridge from Section 22 DEF discovery into the
        dynamic expansion fabric.
        """

        if not isinstance(
            definition,
            dict,
        ):
            return self._seedos_dynamic_ask(
                "Discovered definition is not valid structured data.",
                {
                    "definition":
                        repr(
                            definition
                        ),
                },
            )

        self._seedos_dynamic_counts[
            "new_definitions"
        ] += 1

        return self.seedos_build_dynamic_proposal(
            definition
        )


    # ==========================================================
    # PROCESS COMMAND CANDIDATE
    # ==========================================================

    def seedos_process_discovered_command(
        self,
        command,
    ):
        """
        Process a command candidate without registering it
        as executable.

        QbitDialer remains the only command authority.
        """

        if not isinstance(
            command,
            dict,
        ):
            return self._seedos_dynamic_ask(
                "Discovered command is not valid structured data.",
                {
                    "command":
                        repr(
                            command
                        ),
                },
            )

        candidate = dict(
            command
        )

        candidate[
            "command_authority"
        ] = "QbitDialer"

        candidate[
            "execution_authority"
        ] = "QbitQueueLoop"

        candidate[
            "requires_submit_command"
        ] = True

        candidate[
            "registered"
        ] = False

        candidate[
            "executable"
        ] = False

        result = self.seedos_build_dynamic_proposal(
            candidate
        )

        self._seedos_dynamic_counts[
            "command_candidates"
        ] += 1

        return result


    # ==========================================================
    # UNCERTAINTY / ASK
    # ==========================================================

    def _seedos_dynamic_ask(
        self,
        reason,
        context=None,
    ):
        """
        Ask SEED instead of guessing when dynamic discovery
        cannot be safely classified.
        """

        self._seedos_dynamic_counts[
            "questions"
        ] += 1

        question = {
            "type":
                "DYNAMIC_EXPANSION_QUESTION",

            "reason":
                str(
                    reason
                ),

            "context":
                context or {},

            "target":
                "SEED",

            "authority":
                "QbitDialer",

            "execution":
                False,

            "requires_answer":
                True,
        }

        ask = getattr(
            self,
            "seedos_ask",
            None,
        )

        if callable(
            ask
        ):

            try:
                return ask(
                    str(
                        reason
                    ),
                    context=context or {},
                )
            except Exception:
                pass

        json_record = getattr(
            self,
            "seedos_json_record",
            None,
        )

        if callable(
            json_record
        ):

            try:
                json_record(
                    "QUESTION",
                    question,
                )
            except Exception:
                pass

        return question


    # ==========================================================
    # DISCOVERY SNAPSHOT
    # ==========================================================

    def seedos_dynamic_expansion_status(
        self,
    ):
        """
        Return the current dynamic expansion state.
        """

        return {
            "initialized":
                getattr(
                    self,
                    "_seedos_dynamic_expansion_initialized",
                    False,
                ),

            "enabled":
                getattr(
                    self,
                    "_seedos_dynamic_expansion_enabled",
                    False,
                ),

            "authority":
                "QbitDialer",

            "execution_authority":
                "QbitQueueLoop",

            "discovery_count":
                len(
                    getattr(
                        self,
                        "_seedos_dynamic_discoveries",
                        {},
                    )
                ),

            "match_count":
                len(
                    getattr(
                        self,
                        "_seedos_dynamic_matches",
                        {},
                    )
                ),

            "unresolved_count":
                len(
                    getattr(
                        self,
                        "_seedos_dynamic_unresolved",
                        {},
                    )
                ),

            "counts":
                dict(
                    getattr(
                        self,
                        "_seedos_dynamic_counts",
                        {},
                    )
                ),
        }


    def seedos_dynamic_expansion_snapshot(
        self,
    ):
        """
        Complete snapshot for DEVHUD, Oracle, FATHUD,
        cognition, JSON persistence, and developer review.
        """

        return {
            "status":
                self.seedos_dynamic_expansion_status(),

            "discoveries":
                dict(
                    getattr(
                        self,
                        "_seedos_dynamic_discoveries",
                        {},
                    )
                ),

            "matches":
                dict(
                    getattr(
                        self,
                        "_seedos_dynamic_matches",
                        {},
                    )
                ),

            "unresolved":
                dict(
                    getattr(
                        self,
                        "_seedos_dynamic_unresolved",
                        {},
                    )
                ),

            "history":
                list(
                    getattr(
                        self,
                        "_seedos_dynamic_history",
                        [],
                    )[
                        -100:
                    ]
                ),

            "promotion_pipeline":
                [
                    "DISCOVER",
                    "DESCRIBE",
                    "CLASSIFY",
                    "MATCH",
                    "PROPOSE",
                    "SANDBOX",
                    "VALIDATE",
                    "REVIEW",
                    "PROMOTE",
                    "QBITDIALER_AUTHORITY",
                    "QBITQUEUELOOP_EXECUTION",
                ],
        }


    # ==========================================================
    # PUBLIC DEVELOPMENT ENTRY
    # ==========================================================

    def seedos_expand(
        self,
        subject,
        *,
        kind="DEVELOPMENT",
    ):
        """
        Creator-facing dynamic expansion entry.

        A creator suggestion becomes a development proposal.
        It does not directly modify or execute the runtime.
        """

        payload = {
            "kind":
                str(
                    kind
                ).upper(),

            "subject":
                subject,

            "creator_input":
                True,

            "authority":
                "QbitDialer",

            "execution":
                False,
        }

        submit = getattr(
            self,
            "seedos_develop",
            None,
        )

        if callable(
            submit
        ):

            try:
                return submit(
                    subject,
                    kind=kind,
                    context=payload,
                )
            except TypeError:
                try:
                    return submit(
                        subject
                    )
                except Exception:
                    pass
            except Exception:
                pass

        return self.seedos_build_dynamic_proposal(
            payload
        )


    # ==========================================================
    # SECTION 24
    # SEED OS PROMOTION GATE
    # ==========================================================
    #
    # PURPOSE:
    #     Establish the boundary between:
    #
    #         DISCOVERY
    #         PROPOSAL
    #         SANDBOX
    #         VALIDATION
    #         REVIEW
    #         PROMOTION
    #
    #     A discovered definition or capability must NEVER become
    #     executable merely because it was discovered.
    #
    #     Promotion produces an approved development record.
    #
    #     Actual command admission remains:
    #
    #         QbitDialer.submit_command()
    #
    #     Actual execution remains:
    #
    #         QbitQueueLoop
    #
    # ==========================================================


    def _initialize_seedos_promotion_gate(self):
        """
        Initialize the promotion gate.

        The gate is intentionally state-only.

        It does not install packages, load external code,
        execute commands, or start runtime components.
        """

        if getattr(
            self,
            "_seedos_promotion_gate_initialized",
            False,
        ):
            return

        self._seedos_promotion_gate_initialized = True

        self._seedos_promotion_records = {}

        self._seedos_promotion_history = []

        self._seedos_promotion_counts = {
            "requested": 0,
            "sandbox_required": 0,
            "validation_required": 0,
            "review_required": 0,
            "approved": 0,
            "rejected": 0,
            "deferred": 0,
            "blocked": 0,
            "pending": 0,
        }


    # ==========================================================
    # PROMOTION KEY
    # ==========================================================

    def _seedos_promotion_key(
        self,
        proposal,
    ):
        """
        Create a stable promotion key.
        """

        if not isinstance(
            proposal,
            dict,
        ):
            return (
                "UNKNOWN",
                repr(
                    proposal
                ),
            )

        source = proposal.get(
            "source",
            proposal,
        )

        if isinstance(
            source,
            dict,
        ):
            system = str(
                source.get(
                    "system",
                    ""
                )
            )

            name = str(
                source.get(
                    "name",
                    source.get(
                        "command",
                        ""
                    ),
                )
            )

            signature = str(
                source.get(
                    "signature",
                    ""
                )
            )

        else:
            system = ""
            name = str(
                source
            )
            signature = ""

        return (
            system,
            name,
            signature,
        )


    # ==========================================================
    # PROMOTION REQUEST
    # ==========================================================

    def seedos_request_promotion(
        self,
        proposal,
        *,
        reason=None,
    ):
        """
        Create a promotion request.

        Promotion is a decision record only.

        It does not:
            - execute
            - install
            - register an executable command
            - mutate runtime code
        """

        if not isinstance(
            proposal,
            dict,
        ):
            return {
                "status":
                    "BLOCKED",

                "reason":
                    "Promotion proposal must be a mapping.",
            }

        key = self._seedos_promotion_key(
            proposal
        )

        existing = (
            self._seedos_promotion_records.get(
                key
            )
        )

        if existing is not None:
            return existing

        self._seedos_promotion_counts[
            "requested"
        ] += 1

        record = {
            "promotion_id":
                f"PROMOTE.{len(self._seedos_promotion_records) + 1:06d}",

            "promotion_key":
                key,

            "proposal":
                dict(
                    proposal
                ),

            "reason":
                reason,

            "status":
                "PENDING",

            "sandbox":
                {
                    "required":
                        True,

                    "status":
                        "REQUIRED",
                },

            "validation":
                {
                    "required":
                        True,

                    "status":
                        "REQUIRED",
                },

            "review":
                {
                    "required":
                        True,

                    "status":
                        "REQUIRED",
                },

            "approved":
                False,

            "promoted":
                False,

            "executable":
                False,

            "installed":
                False,

            "authority":
                "QbitDialer",

            "execution_authority":
                "QbitQueueLoop",

            "created_by":
                "SEED_OS_DEVELOPER_WORKSPACE",
        }

        self._seedos_promotion_records[
            key
        ] = record

        self._seedos_promotion_history.append(
            record
        )

        self._seedos_promotion_counts[
            "sandbox_required"
        ] += 1

        self._seedos_promotion_counts[
            "validation_required"
        ] += 1

        self._seedos_promotion_counts[
            "review_required"
        ] += 1

        self._seedos_promotion_counts[
            "pending"
        ] += 1

        json_record = getattr(
            self,
            "seedos_json_record",
            None,
        )

        if callable(
            json_record
        ):

            try:
                json_record(
                    "REVIEW",
                    record,
                )
            except Exception:
                pass

        return record


    # ==========================================================
    # SANDBOX GATE
    # ==========================================================

    def seedos_promotion_sandbox(
        self,
        promotion,
    ):
        """
        Mark the promotion request as having entered the sandbox
        stage.

        Actual sandbox validation remains handled by the existing
        Section 16 validation fabric.
        """

        record = self._seedos_get_promotion_record(
            promotion
        )

        if record is None:
            return {
                "status":
                    "BLOCKED",

                "reason":
                    "Promotion record not found.",
            }

        record[
            "sandbox"
        ][
            "status"
        ] = "READY"

        record[
            "status"
        ] = "SANDBOX_READY"

        return record


    # ==========================================================
    # VALIDATION GATE
    # ==========================================================

    def seedos_promotion_validate(
        self,
        promotion,
    ):
        """
        Run the existing SEED sandbox validation layer against
        the promotion proposal.

        No execution occurs here.
        """

        record = self._seedos_get_promotion_record(
            promotion
        )

        if record is None:
            return {
                "status":
                    "BLOCKED",

                "reason":
                    "Promotion record not found.",
            }

        validator = getattr(
            self,
            "seedos_test_development_request",
            None,
        )

        if not callable(
            validator
        ):
            validator = getattr(
                self,
                "seedos_test_capability",
                None,
            )

        if not callable(
            validator
        ):
            record[
                "validation"
            ][
                "status"
            ] = "UNAVAILABLE"

            record[
                "status"
            ] = "BLOCKED"

            self._seedos_promotion_counts[
                "blocked"
            ] += 1

            return record

        proposal = record.get(
            "proposal",
            {},
        )

        try:
            validation = validator(
                proposal
            )
        except TypeError:
            try:
                validation = validator(
                    proposal,
                    session_id=record[
                        "promotion_id"
                    ],
                )
            except Exception as exc:
                validation = {
                    "status":
                        "ERROR",

                    "error":
                        str(
                            exc
                        ),
                }
        except Exception as exc:
            validation = {
                "status":
                    "ERROR",

                "error":
                    str(
                        exc
                    ),
            }

        record[
            "validation"
        ][
            "result"
        ] = validation

        if isinstance(
            validation,
            dict,
        ):

            validation_status = str(
                validation.get(
                    "status",
                    ""
                )
            ).upper()

        else:
            validation_status = ""

        if validation_status in (
            "PASS",
            "PASSED",
            "VALID",
            "VALIDATED",
            "SUCCESS",
        ):

            record[
                "validation"
            ][
                "status"
            ] = "PASSED"

            record[
                "status"
            ] = "VALIDATED"

        elif validation_status in (
            "FAIL",
            "FAILED",
            "INVALID",
            "BLOCKED",
            "ERROR",
        ):

            record[
                "validation"
            ][
                "status"
            ] = "FAILED"

            record[
                "status"
            ] = "BLOCKED"

        else:

            record[
                "validation"
            ][
                "status"
            ] = "REVIEW_REQUIRED"

            record[
                "status"
            ] = "REVIEW_REQUIRED"

        return record


    # ==========================================================
    # REVIEW GATE
    # ==========================================================

    def seedos_promotion_review(
        self,
        promotion,
        *,
        decision=None,
        rationale=None,
    ):
        """
        Record a promotion review.

        Review is separate from validation.

        No runtime execution occurs here.
        """

        record = self._seedos_get_promotion_record(
            promotion
        )

        if record is None:
            return {
                "status":
                    "BLOCKED",

                "reason":
                    "Promotion record not found.",
            }

        if decision is None:
            record[
                "review"
            ][
                "status"
            ] = "PENDING"

            return record

        normalized = str(
            decision
        ).strip().upper()

        allowed = {
            "APPROVE":
                "APPROVED",

            "APPROVED":
                "APPROVED",

            "REJECT":
                "REJECTED",

            "REJECTED":
                "REJECTED",

            "DEFER":
                "DEFERRED",

            "DEFERRED":
                "DEFERRED",

            "BLOCK":
                "BLOCKED",

            "BLOCKED":
                "BLOCKED",
        }

        resolved = allowed.get(
            normalized
        )

        if resolved is None:

            record[
                "review"
            ][
                "status"
            ] = "INVALID_DECISION"

            return record

        record[
            "review"
        ][
            "status"
        ] = resolved

        record[
            "review"
        ][
            "rationale"
        ] = rationale

        if resolved == "APPROVED":

            record[
                "status"
            ] = "APPROVED"

            record[
                "approved"
            ] = True

            self._seedos_promotion_counts[
                "approved"
            ] += 1

        elif resolved == "REJECTED":

            record[
                "status"
            ] = "REJECTED"

            record[
                "approved"
            ] = False

            self._seedos_promotion_counts[
                "rejected"
            ] += 1

        elif resolved == "DEFERRED":

            record[
                "status"
            ] = "DEFERRED"

            self._seedos_promotion_counts[
                "deferred"
            ] += 1

        elif resolved == "BLOCKED":

            record[
                "status"
            ] = "BLOCKED"

            self._seedos_promotion_counts[
                "blocked"
            ] += 1

        if self._seedos_promotion_counts[
            "pending"
        ] > 0:

            self._seedos_promotion_counts[
                "pending"
            ] -= 1

        return record


    # ==========================================================
    # PROMOTION COMPLETION
    # ==========================================================

    def seedos_promote_validated(
        self,
        promotion,
    ):
        """
        Complete promotion only after sandbox, validation,
        and review have passed.

        This creates a PROMOTED knowledge record.

        It does NOT execute the resulting capability.
        """

        record = self._seedos_get_promotion_record(
            promotion
        )

        if record is None:
            return {
                "status":
                    "BLOCKED",

                "reason":
                    "Promotion record not found.",
            }

        sandbox_status = str(
            record.get(
                "sandbox",
                {}
            ).get(
                "status",
                ""
            )
        ).upper()

        validation_status = str(
            record.get(
                "validation",
                {}
            ).get(
                "status",
                ""
            )
        ).upper()

        review_status = str(
            record.get(
                "review",
                {}
            ).get(
                "status",
                ""
            )
        ).upper()

        if sandbox_status not in (
            "READY",
            "PASSED",
            "VALIDATED",
        ):
            record[
                "status"
            ] = "SANDBOX_REQUIRED"

            return record

        if validation_status not in (
            "PASSED",
            "VALIDATED",
        ):
            record[
                "status"
            ] = "VALIDATION_REQUIRED"

            return record

        if review_status != "APPROVED":
            record[
                "status"
            ] = "REVIEW_REQUIRED"

            return record

        record[
            "promoted"
        ] = True

        record[
            "executable"
        ] = False

        record[
            "installed"
        ] = False

        record[
            "status"
        ] = "PROMOTED_KNOWLEDGE"

        record[
            "next_authority"
        ] = "QbitDialer"

        record[
            "next_execution_transport"
        ] = "QbitQueueLoop"

        record[
            "promotion_boundary"
        ] = (
            "PROMOTION_DOES_NOT_EQUAL_EXECUTION"
        )

        json_record = getattr(
            self,
            "seedos_json_record",
            None,
        )

        if callable(
            json_record
        ):

            try:
                json_record(
                    "DEVELOPMENT",
                    record,
                )
            except Exception:
                pass

        return record


    # ==========================================================
    # RECORD LOOKUP
    # ==========================================================

    def _seedos_get_promotion_record(
        self,
        promotion,
    ):
        """
        Resolve a promotion record from either:
            - promotion key
            - promotion id
            - promotion mapping
        """

        if isinstance(
            promotion,
            dict,
        ):

            if (
                promotion.get(
                    "promotion_key"
                )
                in self._seedos_promotion_records
            ):

                return self._seedos_promotion_records[
                    promotion[
                        "promotion_key"
                    ]
                ]

            key = self._seedos_promotion_key(
                promotion
            )

            if key in self._seedos_promotion_records:
                return self._seedos_promotion_records[
                    key
                ]

            promotion_id = promotion.get(
                "promotion_id"
            )

            if promotion_id:

                for record in (
                    self._seedos_promotion_records.values()
                ):

                    if record.get(
                        "promotion_id"
                    ) == promotion_id:
                        return record

            return None

        for record in (
            self._seedos_promotion_records.values()
        ):

            if (
                record.get(
                    "promotion_id"
                )
                == promotion
            ):
                return record

            if (
                record.get(
                    "promotion_key"
                )
                == promotion
            ):
                return record

        return None


    # ==========================================================
    # PROMOTION STATUS
    # ==========================================================

    def seedos_promotion_status(
        self,
    ):
        """
        Return promotion gate state.
        """

        return {
            "initialized":
                getattr(
                    self,
                    "_seedos_promotion_gate_initialized",
                    False,
                ),

            "authority":
                "QbitDialer",

            "execution_authority":
                "QbitQueueLoop",

            "execution_from_promotion":
                False,

            "installation_from_promotion":
                False,

            "counts":
                dict(
                    getattr(
                        self,
                        "_seedos_promotion_counts",
                        {},
                    )
                ),

            "records":
                len(
                    getattr(
                        self,
                        "_seedos_promotion_records",
                        {},
                    )
                ),
        }


    def seedos_promotion_snapshot(
        self,
    ):
        """
        Complete promotion-gate snapshot.
        """

        return {
            "status":
                self.seedos_promotion_status(),

            "records":
                dict(
                    getattr(
                        self,
                        "_seedos_promotion_records",
                        {},
                    )
                ),

            "history":
                list(
                    getattr(
                        self,
                        "_seedos_promotion_history",
                        [],
                    )[
                        -100:
                    ]
                ),

            "pipeline":
                [
                    "DISCOVERY",
                    "PROPOSAL",
                    "SANDBOX",
                    "VALIDATION",
                    "REVIEW",
                    "PROMOTED_KNOWLEDGE",
                    "QBITDIALER_AUTHORIZATION",
                    "QBITQUEUELOOP_EXECUTION",
                ],
        }

    # ==========================================================
    # SECTION 25
    # SEED OS DEVELOPER DECISION / PROMOTION WORKFLOW
    # ==========================================================
    #
    # PURPOSE:
    #     Connect the creator-facing development workspace to the
    #     discovery, sandbox, validation, review, and promotion
    #     systems already built.
    #
    #     The developer expresses intent.
    #     SEED evaluates the proposal.
    #
    #     The developer does NOT directly manipulate runtime
    #     authority from this interface.
    #
    #     DEVELOPMENT FLOW:
    #
    #         CREATOR INPUT
    #              ↓
    #         DEVELOPMENT ENVELOPE
    #              ↓
    #         DISCOVERY / KNOWLEDGE
    #              ↓
    #         DYNAMIC CLASSIFICATION
    #              ↓
    #         CAPABILITY PROPOSAL
    #              ↓
    #         SANDBOX
    #              ↓
    #         VALIDATION
    #              ↓
    #         REVIEW
    #              ↓
    #         PROMOTION
    #              ↓
    #         QbitDialer AUTHORIZATION
    #              ↓
    #         QbitQueueLoop EXECUTION
    #
    # ==========================================================


    def _initialize_seedos_developer_decision_workflow(self):
        """
        Initialize the creator-facing development decision layer.
        """

        if getattr(
            self,
            "_seedos_developer_decision_initialized",
            False,
        ):
            return

        self._seedos_developer_decision_initialized = True

        self._seedos_developer_decisions = {}

        self._seedos_developer_decision_history = []

        self._seedos_developer_decision_counts = {
            "requests": 0,
            "proposals": 0,
            "sandbox": 0,
            "validated": 0,
            "reviewed": 0,
            "approved": 0,
            "rejected": 0,
            "deferred": 0,
            "blocked": 0,
        }


    # ==========================================================
    # DECISION KEY
    # ==========================================================

    def _seedos_developer_decision_key(
        self,
        subject,
        *,
        kind="DEVELOPMENT",
    ):
        """
        Produce a stable key for creator development requests.
        """

        try:
            import hashlib

            payload = (
                f"{str(kind).upper()}|"
                f"{repr(subject)}"
            )

            return hashlib.sha256(
                payload.encode(
                    "utf-8"
                )
            ).hexdigest()[:24]

        except Exception:

            return (
                str(
                    kind
                ).upper(),
                repr(
                    subject
                ),
            )


    # ==========================================================
    # CREATOR DEVELOPMENT REQUEST
    # ==========================================================

    def seedos_request_development(
        self,
        subject,
        *,
        kind="DEVELOPMENT",
        context=None,
    ):
        """
        Convert creator input into a tracked development request.

        The request is a proposal.

        It is not an instruction to execute code.
        """

        self._seedos_developer_decision_counts[
            "requests"
        ] += 1

        decision_key = (
            self._seedos_developer_decision_key(
                subject,
                kind=kind,
            )
        )

        existing = (
            self._seedos_developer_decisions.get(
                decision_key
            )
        )

        if existing is not None:
            return existing

        request = {
            "decision_id":
                f"DEVREQ.{len(self._seedos_developer_decisions) + 1:06d}",

            "decision_key":
                decision_key,

            "kind":
                str(
                    kind
                ).upper(),

            "subject":
                subject,

            "context":
                context or {},

            "creator_input":
                True,

            "status":
                "RECEIVED",

            "proposal":
                None,

            "promotion":
                None,

            "approved":
                False,

            "promoted":
                False,

            "executed":
                False,

            "authority":
                "QbitDialer",

            "execution_authority":
                "QbitQueueLoop",
        }

        self._seedos_developer_decisions[
            decision_key
        ] = request

        self._seedos_developer_decision_history.append(
            request
        )

        return request


    # ==========================================================
    # BUILD DEVELOPMENT PROPOSAL
    # ==========================================================

    def seedos_build_development_decision(
        self,
        request,
    ):
        """
        Resolve a development request through the existing
        dynamic expansion fabric.
        """

        if not isinstance(
            request,
            dict,
        ):
            return {
                "status":
                    "BLOCKED",

                "reason":
                    "Development request must be a mapping.",
            }

        subject = request.get(
            "subject"
        )

        kind = request.get(
            "kind",
            "DEVELOPMENT",
        )

        dynamic_expand = getattr(
            self,
            "seedos_expand",
            None,
        )

        if not callable(
            dynamic_expand
        ):
            request[
                "status"
            ] = "BLOCKED"

            return request

        try:
            proposal = dynamic_expand(
                subject,
                kind=kind,
            )
        except Exception as exc:

            request[
                "status"
            ] = "ERROR"

            request[
                "error"
            ] = str(
                exc
            )

            self._seedos_developer_decision_counts[
                "blocked"
            ] += 1

            return request

        request[
            "proposal"
        ] = proposal

        request[
            "status"
        ] = "PROPOSAL_READY"

        self._seedos_developer_decision_counts[
            "proposals"
        ] += 1

        return request


    # ==========================================================
    # CREATE PROMOTION RECORD
    # ==========================================================

    def seedos_prepare_development_promotion(
        self,
        request,
        *,
        reason=None,
    ):
        """
        Create the Section 24 promotion record for a development
        proposal.
        """

        if not isinstance(
            request,
            dict,
        ):
            return {
                "status":
                    "BLOCKED",

                "reason":
                    "Invalid development request.",
            }

        proposal = request.get(
            "proposal"
        )

        if not isinstance(
            proposal,
            dict,
        ):
            return {
                "status":
                    "BLOCKED",

                "reason":
                    "No development proposal is available.",
            }

        promotion_builder = getattr(
            self,
            "seedos_request_promotion",
            None,
        )

        if not callable(
            promotion_builder
        ):
            return {
                "status":
                    "BLOCKED",

                "reason":
                    "Promotion gate is unavailable.",
            }

        promotion = promotion_builder(
            proposal,
            reason=reason,
        )

        request[
            "promotion"
        ] = promotion

        request[
            "status"
        ] = "PROMOTION_PENDING"

        return promotion


    # ==========================================================
    # SANDBOX DEVELOPMENT REQUEST
    # ==========================================================

    def seedos_sandbox_development(
        self,
        request,
    ):
        """
        Move a development request into the existing sandbox
        stage.
        """

        if not isinstance(
            request,
            dict,
        ):
            return {
                "status":
                    "BLOCKED",
            }

        promotion = request.get(
            "promotion"
        )

        if not promotion:
            promotion = (
                self.seedos_prepare_development_promotion(
                    request
                )
            )

        if not isinstance(
            promotion,
            dict,
        ):
            return promotion

        sandbox = getattr(
            self,
            "seedos_promotion_sandbox",
            None,
        )

        if not callable(
            sandbox
        ):
            request[
                "status"
            ] = "BLOCKED"

            return request

        result = sandbox(
            promotion
        )

        request[
            "sandbox"
        ] = result

        request[
            "status"
        ] = "SANDBOX_READY"

        self._seedos_developer_decision_counts[
            "sandbox"
        ] += 1

        return request


    # ==========================================================
    # VALIDATE DEVELOPMENT REQUEST
    # ==========================================================

    def seedos_validate_development(
        self,
        request,
    ):
        """
        Send the development request through the existing
        sandbox-validation system.
        """

        if not isinstance(
            request,
            dict,
        ):
            return {
                "status":
                    "BLOCKED",
            }

        promotion = request.get(
            "promotion"
        )

        if not isinstance(
            promotion,
            dict,
        ):
            return {
                "status":
                    "BLOCKED",

                "reason":
                    "Promotion record is missing.",
            }

        validator = getattr(
            self,
            "seedos_promotion_validate",
            None,
        )

        if not callable(
            validator
        ):
            return {
                "status":
                    "BLOCKED",

                "reason":
                    "Validation gate is unavailable.",
            }

        result = validator(
            promotion
        )

        request[
            "validation"
        ] = result

        validation_status = str(
            result.get(
                "validation",
                {}
            ).get(
                "status",
                ""
            )
        ).upper()

        if validation_status in (
            "PASSED",
            "VALIDATED",
        ):

            request[
                "status"
            ] = "VALIDATED"

            self._seedos_developer_decision_counts[
                "validated"
            ] += 1

        else:

            request[
                "status"
            ] = result.get(
                "status",
                "VALIDATION_REVIEW",
            )

        return request


    # ==========================================================
    # CREATOR REVIEW
    # ==========================================================

    def seedos_review_development(
        self,
        request,
        *,
        decision=None,
        rationale=None,
    ):
        """
        Record the development review decision.
        """

        if not isinstance(
            request,
            dict,
        ):
            return {
                "status":
                    "BLOCKED",
            }

        promotion = request.get(
            "promotion"
        )

        if not isinstance(
            promotion,
            dict,
        ):
            return {
                "status":
                    "BLOCKED",

                "reason":
                    "Promotion record is missing.",
            }

        reviewer = getattr(
            self,
            "seedos_promotion_review",
            None,
        )

        if not callable(
            reviewer
        ):
            return {
                "status":
                    "BLOCKED",

                "reason":
                    "Review gate is unavailable.",
            }

        result = reviewer(
            promotion,
            decision=decision,
            rationale=rationale,
        )

        request[
            "review"
        ] = result

        status = str(
            result.get(
                "status",
                ""
            )
        ).upper()

        request[
            "status"
        ] = status

        self._seedos_developer_decision_counts[
            "reviewed"
        ] += 1

        if status == "APPROVED":

            self._seedos_developer_decision_counts[
                "approved"
            ] += 1

        elif status == "REJECTED":

            self._seedos_developer_decision_counts[
                "rejected"
            ] += 1

        elif status == "DEFERRED":

            self._seedos_developer_decision_counts[
                "deferred"
            ] += 1

        elif status == "BLOCKED":

            self._seedos_developer_decision_counts[
                "blocked"
            ] += 1

        return request


    # ==========================================================
    # PROMOTE KNOWLEDGE
    # ==========================================================

    def seedos_promote_development(
        self,
        request,
    ):
        """
        Promote an approved, validated development proposal
        into SEED's knowledge/development state.

        Promotion does not execute it.
        """

        if not isinstance(
            request,
            dict,
        ):
            return {
                "status":
                    "BLOCKED",
            }

        promotion = request.get(
            "promotion"
        )

        if not isinstance(
            promotion,
            dict,
        ):
            return {
                "status":
                    "BLOCKED",
            }

        promoter = getattr(
            self,
            "seedos_promote_validated",
            None,
        )

        if not callable(
            promoter
        ):
            return {
                "status":
                    "BLOCKED",

                "reason":
                    "Promotion gate is unavailable.",
            }

        result = promoter(
            promotion
        )

        request[
            "promotion_result"
        ] = result

        if result.get(
            "status"
        ) == "PROMOTED_KNOWLEDGE":

            request[
                "status"
            ] = "PROMOTED_KNOWLEDGE"

            request[
                "promoted"
            ] = True

        else:

            request[
                "status"
            ] = result.get(
                "status",
                "PROMOTION_PENDING",
            )

        return request


    # ==========================================================
    # COMPLETE DEVELOPMENT PIPELINE
    # ==========================================================

    def seedos_developer_pipeline(
        self,
        subject,
        *,
        kind="DEVELOPMENT",
        context=None,
        auto_review=False,
    ):
        """
        Run the non-executing portion of the creator development
        pipeline.

        The pipeline may discover, classify, sandbox, and validate.

        Review remains a distinct decision boundary.

        No runtime command is executed by this method.
        """

        request = (
            self.seedos_request_development(
                subject,
                kind=kind,
                context=context,
            )
        )

        request = (
            self.seedos_build_development_decision(
                request
            )
        )

        if request.get(
            "status"
        ) != "PROPOSAL_READY":
            return request

        request = (
            self.seedos_prepare_development_promotion(
                request
            )
        )

        if not isinstance(
            request.get(
                "promotion"
            ),
            dict,
        ):
            return request

        request = (
            self.seedos_sandbox_development(
                request
            )
        )

        request = (
            self.seedos_validate_development(
                request
            )
        )

        if auto_review:
            request = (
                self.seedos_review_development(
                    request,
                    decision="DEFER",
                    rationale=(
                        "Automatic pipeline does not "
                        "self-approve promotion."
                    ),
                )
            )

        return request


    # ==========================================================
    # APPROVAL CHECK
    # ==========================================================

    def seedos_development_is_promotable(
        self,
        request,
    ):
        """
        Determine whether a development request has satisfied
        the promotion prerequisites.
        """

        if not isinstance(
            request,
            dict,
        ):
            return False

        promotion = request.get(
            "promotion"
        )

        if not isinstance(
            promotion,
            dict,
        ):
            return False

        sandbox_status = str(
            promotion.get(
                "sandbox",
                {}
            ).get(
                "status",
                ""
            )
        ).upper()

        validation_status = str(
            promotion.get(
                "validation",
                {}
            ).get(
                "status",
                ""
            )
        ).upper()

        review_status = str(
            promotion.get(
                "review",
                {}
            ).get(
                "status",
                ""
            )
        ).upper()

        return (
            sandbox_status
            in (
                "READY",
                "PASSED",
                "VALIDATED",
            )
            and
            validation_status
            in (
                "PASSED",
                "VALIDATED",
            )
            and
            review_status
            == "APPROVED"
        )


    # ==========================================================
    # DEVELOPMENT LOOKUP
    # ==========================================================

    def seedos_get_development_request(
        self,
        identifier,
    ):
        """
        Retrieve a tracked development request.
        """

        if identifier in (
            getattr(
                self,
                "_seedos_developer_decisions",
                {},
            )
        ):
            return self._seedos_developer_decisions[
                identifier
            ]

        for request in (
            getattr(
                self,
                "_seedos_developer_decisions",
                {},
            ).values()
        ):

            if request.get(
                "decision_id"
            ) == identifier:
                return request

        return None


    # ==========================================================
    # DEVELOPMENT STATUS
    # ==========================================================

    def seedos_developer_decision_status(
        self,
    ):
        """
        Return creator development workflow state.
        """

        return {
            "initialized":
                getattr(
                    self,
                    "_seedos_developer_decision_initialized",
                    False,
                ),

            "creator_interface":
                "DEVHUD",

            "developer_input":
                "PROPOSAL",

            "command_authority":
                "QbitDialer",

            "execution_authority":
                "QbitQueueLoop",

            "direct_execution":
                False,

            "direct_installation":
                False,

            "counts":
                dict(
                    getattr(
                        self,
                        "_seedos_developer_decision_counts",
                        {},
                    )
                ),

            "requests":
                len(
                    getattr(
                        self,
                        "_seedos_developer_decisions",
                        {},
                    )
                ),
        }


    # ==========================================================
    # COMPLETE WORKFLOW SNAPSHOT
    # ==========================================================

    def seedos_developer_decision_snapshot(
        self,
    ):
        """
        Return the complete creator/developer workflow state.
        """

        return {
            "status":
                self.seedos_developer_decision_status(),

            "requests":
                dict(
                    getattr(
                        self,
                        "_seedos_developer_decisions",
                        {},
                    )
                ),

            "history":
                list(
                    getattr(
                        self,
                        "_seedos_developer_decision_history",
                        [],
                    )[
                        -100:
                    ]
                ),

            "workflow":
                [
                    "CREATOR_INPUT",
                    "DEVELOPMENT_REQUEST",
                    "DISCOVERY",
                    "CLASSIFICATION",
                    "CAPABILITY_PROPOSAL",
                    "PROMOTION_REQUEST",
                    "SANDBOX",
                    "VALIDATION",
                    "REVIEW",
                    "PROMOTED_KNOWLEDGE",
                    "QBITDIALER_AUTHORIZATION",
                    "QBITQUEUELOOP_EXECUTION",
                ],
        }


