# ============================================================
# FILE: DEVHUD.py
# PATH: SEED_ROOT/seed/systemutils/DEVHUD.py
# ============================================================
# VERSION: 10.0.0
# RELEASE: SEED DEVHUD STABILITY REBUILD
#
# ============================================================
# DEVHUD v10 — ARCHITECTURAL BLUEPRINT
# ============================================================
#
# PURPOSE
# -------
# DEVHUD is the SEED developer/operator presentation layer.
#
# DEVHUD provides:
#   - developer diagnostics
#   - SEED runtime visibility
#   - Qbit visibility and control interface
#   - heartbeat visibility
#   - EventBus event presentation
#   - Track/Channel visibility
#   - system/device status
#   - command interface
#   - dynamic module presentation
#   - TimeTravel diagnostics
#   - memory/health diagnostics
#   - controlled developer interaction
#
# DEVHUD IS NOT:
#   - the owner of the SEED Qbit
#   - the owner of the Heartbeat
#   - the owner of the EventBus
#   - the owner of the TrackSystem
#   - the owner of system shutdown
#   - a second SEED runtime
#
# ============================================================
# CORE AUTHORITY MODEL
# ============================================================
#
#                    SEED CORE
#                        |
#          +-------------+-------------+
#          |             |             |
#      Heartbeat     QbitDialer     EventBus
#          |             |             |
#          +-------------+-------------+
#                        |
#                  DEVHUD BRIDGE
#                        |
#                 +------+------+
#                 |             |
#              HUD STATE    HUD LAYOUT
#                 |             |
#                 +------+------+
#                        |
#                    TK ROOT
#                        |
#                    DEVHUD UI
#
# DEVHUD observes and presents SEED state.
# DEVHUD may issue authorized commands through the established
# SEED command/control interfaces.
#
# DEVHUD must never create a competing authoritative runtime.
#
# ============================================================
# TKINTER SAFETY CONTRACT
# ============================================================
#
# 1. One authoritative Tk root.
# 2. DEVHUD requires an existing parent/root.
# 3. No hidden Tk() creation inside DEVHUD.
# 4. Child windows use Toplevel only when required.
# 5. UI mutations occur on the Tk main thread.
# 6. Repeating callbacks are tracked.
# 7. Repeating callbacks are cancelled during shutdown.
# 8. DEVHUD must not keep SEED alive after shutdown.
# 9. UI failures are contained inside the HUD layer.
# 10. DEVHUD must not globally monkey-patch Tkinter.
#
# ============================================================
# CPU / REFRESH CONTRACT
# ============================================================
#
# DEVHUD must not use uncontrolled GUI polling.
#
# Preferred order:
#
#   EventBus event
#        |
#        v
#   state update
#        |
#        v
#   bounded UI refresh
#
# Periodic refresh is allowed only where an event-driven source
# is not available and must use a controlled Tk after() schedule.
#
# ============================================================
# QBIT AUTHORITY CONTRACT
# ============================================================
#
# Qbit ownership remains with the SEED/Qbit pipeline.
#
# DEVHUD resolution order:
#
#   1. Qbit explicitly supplied by runtime
#   2. existing Qbit exposed by QbitDialer
#   3. safe unavailable state
#
# DEVHUD must not silently create a second authoritative Qbit.
#
# ============================================================
# EVENTBUS CONTRACT
# ============================================================
#
# DEVHUD subscribes to established SEED events through EventBus.
#
# Event handling must be:
#   - defensive
#   - thread-aware
#   - UI-safe
#   - independently recoverable
#
# A DEVHUD rendering failure must not become a SEED core failure.
#
# ============================================================
# LAYOUT AUTHORITY CONTRACT
# ============================================================
#
# The existing DEVHUD design is the visual baseline.
#
# The rebuilt HUD will separate:
#
#   BASE DESIGN
#       |
#       v
#   HUD LAYOUT STATE
#       |
#       v
#   SEED LAYOUT AUTHORITY
#       |
#       v
#   SAFE TK GEOMETRY
#
# SEED may determine presentation priority, visibility, panel
# arrangement and display state within defined safety limits.
#
# Tkinter remains responsible for valid widget ownership,
# geometry, lifecycle and main-thread execution.
#
# ============================================================
# FUNCTION PRESERVATION CONTRACT
# ============================================================
#
# Existing DEVHUD functionality is preserved unless it is:
#
#   - duplicated
#   - unsafe
#   - unreachable
#   - contradictory
#   - obsolete and isolated from active runtime
#
# Existing public methods and integration points will be
# retained where practical so existing SEED modules continue
# to communicate with DEVHUD.
#
# ============================================================
# REBUILD SECTION MAP
# ============================================================
#
# SECTION 01  Header / Blueprint / Imports
# SECTION 02  Constants / Environment / Runtime Configuration
# SECTION 03  Safe Utility Functions / Type Helpers
# SECTION 04  HUD State / Layout State / UI State
# SECTION 05  SEED Service Binding
# SECTION 06  Tk Root / Window Lifecycle
# SECTION 07  DEVHUD Core Initialization
# SECTION 08  Base Layout Construction
# SECTION 09  Main HUD UI Construction
# SECTION 10  Panels / Widgets / Console
# SECTION 11  Qbit Integration
# SECTION 12  Heartbeat Integration
# SECTION 13  EventBus Integration
# SECTION 14  TrackSystem / ChannelSystem
# SECTION 15  TimeTravel Integration
# SECTION 16  Dynamic Modules
# SECTION 17  Developer Commands / Controls
# SECTION 18  Diagnostics / Health / Logging
# SECTION 19  Refresh Scheduler / CPU Protection
# SECTION 20  SEED-Controlled Layout
# SECTION 21  Compatibility Interfaces
# SECTION 22  Error Containment / Recovery
# SECTION 23  Shutdown / Cleanup
# SECTION 24  Final Bootstrap / Public Exports
#
# ============================================================
# REBUILD RULE
# ============================================================
#
# Each following section is written to be pasted directly after
# the preceding section.
#
# No section requires manual indentation correction.
# No tabs are used.
# Python indentation standard: 4 spaces.
#
# ============================================================


# ============================================================
# SECTION 01 — IMPORT FOUNDATION
# ============================================================

from __future__ import annotations

import asyncio
import hashlib
import importlib
import json
import logging
import multiprocessing as mp
import os
import shutil
import sys
import threading
import time
import traceback
import zipfile

from collections import defaultdict
from enum import Enum
from pathlib import Path
from threading import Thread
from typing import Any, Callable, Dict, Optional


# ============================================================
# THIRD-PARTY IMPORTS
# ============================================================

import requests
import tkinter as tk

from tkinter import (
    Entry,
    filedialog,
    messagebox,
    scrolledtext,
    ttk,
)

from tkinter.scrolledtext import ScrolledText


# ============================================================
# SEED CORE IMPORTS
# ============================================================

from seed.hud.adapter.hud_adapter import HUDAdapter
from seed.hud.state import HUDState
from seed.hud.hud import HUD

from seed.core.emitters.qbit_queue_loop import QbitQueueLoop
from seed.core.time_travel_engine import TimeTravelEngine
from seed.core.event_bus import SEEDEventBus
from seed.core.track_system import TrackSystem
from seed.core.device_manager import DeviceManager
from seed.core.heartbeat import Heartbeat
from seed.core.emitters.heartbeatemitter import HeartbeatEmitter
from seed.core.hud_master_overlay import HUDMasterOverlay
from seed.core.channel_manager import ChannelManager, ChannelNode
from seed.core.module_registry import ModuleRegistry
from seed.core.device import Device
from seed.core.qbit import Qbit


# ============================================================
# SEED SYSTEM / UTILITY IMPORTS
# ============================================================

from seed.systemutils.memory_crystallizer import Memory_Crystallizer
from seed.systemutils.healthmonitor import HealthMonitor
from seed.systemutils.search_engine import SearchEngine
from seed.systemutils.fiveg import FiveG
from seed.systemutils.tk_event_bridge import TkEventBridge
from seed.systemutils.DEVHUD_channels import DEVHUDChannelController


# ============================================================
# SEED IPC / SKILL IMPORTS
# ============================================================

from seed.ipc.ipc_bridge import IPCBridge

from seed.skills.action_registry import queue_action
from seed.skills.inject_option import OptionRegistry


# ============================================================
# SEED UI IMPORTS
# ============================================================

from seed.ui.ui_seed_main import SEEDUIMain3D
from seed.ui.Seed_Ui_Main_HUD import SEEDUIMainHUD, init_hud
from seed.ui.ui_seed_unified import SEEDUIUnified


# ============================================================
# SEED RUNTIME / ORACLE IMPORTS
# ============================================================

from seed_init_full import SEEDCore
from SRegistry.registry_runtime import start_runtime_loop
from Oracle.oracle_tools import Oracle


# ============================================================
# LOGGER
# ============================================================

logger = logging.getLogger("DEVHUD")