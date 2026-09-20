# ==========================================================
# FILE: SEEDUIMainHUD.py
# PATH: SEED_ROOT/seed/ui/SEEDUIMainHUD.py
# MODULE: SEED AI OS — MAIN DEV HUD (COMMAND-GATED)
# VERSION: 15.2 (PATCHED | PARENT-SAFE)
# UPDATED: 2026-01-07
# ==========================================================

import importlib
import logging
import threading
import time
import tkinter as tk
from tkinter import ttk, scrolledtext
from collections import defaultdict
from typing import Dict, Any

from seed.ipc.ipc_bridge import ipc_bridge

from seed.core.nlp_interface import NLPInterface
from seed.core.self_update import SelfUpdateEngine
from seed.core.nlp_intent_engine import NLPIntentEngine

from seed.systemutils.Render import Render

import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# -----------------------------
# Logging
# -----------------------------
logger = logging.getLogger("SEED.UI.MainHUD")
logger.setLevel(logging.INFO)

# ==========================================================
# SEED UI MAIN HUD (DEV MODE ONLY)
# ==========================================================
class SEEDUIMainHUD:
    REQUIRED_MODULES = [
        "seed.core.analytics_engine",
        "seed.core.qbit_dialer",
        "seed.systemutils.Render"
    ]

    def __init__(
        self,
        ipc,
        emit=None,
        track=None,
        track_id=None,
        task=None,
        event_bus=None,
        track_system=None,
        analytics_engine=None,
        qbit_dialer=None,
        storage_root="./SEED_ROOT",
        width=1800,
        height=1000,
        parent=None,  # NEW: optional parent window
    ):
        from seed.core.dialers.qbit_dialer import QbitDialer
        from seed.core.event_bus import SEEDEventBus
        from seed.core.track_system import TrackSystem
        from seed.analytics.analytics_engine import SEEDAnalyticsEngine
        self.ipc_bridge = ipc
        self.event_bus = event_bus
        self.storage_root = storage_root
        self.width = width
        self.height = height
        self.parent = parent  # store optional parent

        self.track = track
        self.emit = emit
        self.analytics_engine = analytics_engine
        self.track_system = track_system
        self.qbit_dialer = qbit_dialer 
        self.track_id = "DEV-HUD"
        self._active = False
        self._shutdown = False

        self.history = defaultdict(list)
        self.hud_frame = None

        # The actual HUD frame is created only after the authoritative
        # Tk parent/root exists. Never create an implicit default Tk root.

        # -----------------------------
        # Subscribe to IPC events
        # -----------------------------
        threading.Thread(target=self._async_subscribe, daemon=True).start()

        # -----------------------------
        # Subscribe to DEVHUB commands
        # -----------------------------
        self.event_bus.subscribe("UI_MAIN_LAUNCH", self._on_launch_command)
        self.event_bus.subscribe("UI_MAIN_SHUTDOWN", self._on_shutdown_command)

        logger.info("[UI] Constructed — waiting for DEVHUB launch command")

    def _async_subscribe(self):
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.ipc_bridge.subscribe("channel.event", self.receive_ipc_event))

    # ======================================================
    # DEVHUB COMMANDS
    # ======================================================
    def _on_launch_command(self, payload=None):
        if self._active:
            logger.warning("[UI] Launch ignored — already active")
            return

        logger.info("[UI] DEVHUB launch command received")

        if not self._verify_modules():
            logger.error("[UI] Module verification failed — aborting UI launch")
            return

        self._build_ui()
        self._active = True
        self.root.mainloop()

    def _on_shutdown_command(self, payload=None):
        logger.info("[UI] DEVHUB shutdown command received")
        self.shutdown()

    # ======================================================
    # MODULE VERIFICATION
    # ======================================================
    def _verify_modules(self) -> bool:
        missing = []
        for mod in self.REQUIRED_MODULES:
            try:
                importlib.import_module(mod)
            except Exception:
                missing.append(mod)

        if missing:
            logger.error(f"[UI] Missing required modules: {missing}")
            return False

        logger.info("[UI] All required modules verified")
        return True

    # ======================================================
    # UI BUILD (DEFERRED)
    # ======================================================

    def _build_hud_tab(self, parent_frame):
        import tkinter as tk
        hud_label = tk.Label(parent_frame or tk.Frame(), text="HUD Tab Placeholder")
        hud_label.pack()
        self.hud_frame = hud_label  # store reference

    def _build_ui(self):
        logger.info("[UI] Building Developer HUD UI")

        # -----------------------------
        # Core engines
        # -----------------------------
        # Reuse authoritative runtime references when supplied.
        # UI must never create competing core authorities.
        self.track_system = self.track_system
        self.qbit_dialer = self.qbit_dialer
        self.analytics = self.analytics_engine
        self.nlp = getattr(self, "nlp", None) or NLPInterface(self.storage_root)
        self.intent_engine = getattr(self, "intent_engine", None) or NLPIntentEngine()
        self.self_update = getattr(self, "self_update", None) or SelfUpdateEngine(self.storage_root)

        # -----------------------------
        # Tk root
        # -----------------------------
        if self.parent:
            self.root = tk.Toplevel(self.parent)
        else:
            self.root = tk.Tk()

        self.root.title("SEED AI — Developer Main Hub")
        self.root.geometry(f"{self.width}x{self.height}")
        self.root.protocol("WM_DELETE_WINDOW", self.shutdown)

        # -----------------------------
        # Notebook
        # -----------------------------
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self.feed_tab = ttk.Frame(self.notebook)
        self.data_tab = ttk.Frame(self.notebook)

        self.notebook.add(self.feed_tab, text="Live Feed")
        self.notebook.add(self.data_tab, text="Data / Logs")

        # -----------------------------
        # Feed Canvas (Matplotlib)
        # -----------------------------
        self.fig = plt.figure(figsize=(6, 4))
        self.ax = self.fig.add_subplot(111, projection="3d")
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.feed_tab)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # -----------------------------
        # Data / Logs
        # -----------------------------
        self.log_box = scrolledtext.ScrolledText(
            self.data_tab,
            state="disabled",
            bg="black",
            fg="lime"
        )
        self.log_box.pack(fill=tk.BOTH, expand=True)

        # -----------------------------
        # Start background updates
        # -----------------------------
        threading.Thread(target=self._ui_update_loop, daemon=True).start()

        logger.info("[UI] Developer HUD activated")

    # -----------------------------------------------------------
    def receive_ipc_event(self, payload: dict):
        self._log(f"[IPC] Received event: {payload}")

    # ======================================================
    # UPDATE LOOP
    # ======================================================
    def _ui_update_loop(self):
        while not self._shutdown:
            try:
                fake_packet = {
                    "channel": "DEV",
                    "payload": time.time()
                }
                self._update_visual(fake_packet)
            except Exception as e:
                logger.error(f"[UI] Update loop error: {e}")
            time.sleep(0.5)

    # ======================================================
    # VISUAL UPDATE
    # ======================================================
    def _update_visual(self, packet: Dict[str, Any]):
        self.ax.cla()
        x = list(range(10))
        y = [i * 0.5 for i in x]
        z = [hash(packet["channel"]) % 10 for _ in x]

        self.ax.scatter(x, y, z, c="cyan")
        self.ax.set_title(f"Channel: {packet['channel']}")
        self.canvas.draw()

        self._log(f"Packet: {packet}")

    # ======================================================
    # LOGGING
    # ======================================================
    def _log(self, message: str):
        def _write():
            self.log_box.config(state=tk.NORMAL)
            self.log_box.insert(tk.END, message + "\n")
            self.log_box.see(tk.END)
            self.log_box.config(state=tk.DISABLED)

        if threading.current_thread() is threading.main_thread():
            _write()
        else:
            self.root.after(0, _write)

    # ======================================================
    # SHUTDOWN
    # ======================================================
    def shutdown(self):
        if self._shutdown:
            return

        logger.info("[UI] Shutting down Developer HUD")
        self._shutdown = True

        try:
            self.root.destroy()
        except Exception:
            pass

# ==========================================================
# Instantiate HUD safely (after ipc_bridge loaded)
# ==========================================================
hud = None

def init_hud(event_bus, parent=None):
    global hud
    hud = SEEDUIMainHUD(ipc_bridge, event_bus, parent=parent)
    return hud
