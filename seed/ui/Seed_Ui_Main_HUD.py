# ==========================================================
# SEEDUIMainHUD.py - Grid-only Layout Fix
# ==========================================================
import importlib
import logging
import threading
import time
import asyncio
import tkinter as tk
from tkinter import ttk
from collections import defaultdict
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from seed.hud.hud import HUD
from seed.ipc.ipc_bridge import IPCBridge
from seed.core.nlp_interface import NLPInterface
from seed.core.self_update import SelfUpdateEngine
from seed.core.nlp_intent_engine import NLPIntentEngine
from seed.systemutils.Render import Render

import matplotlib
matplotlib.use("TkAgg")
matplotlib.rcParams['toolbar'] = 'None'

logger = logging.getLogger("SEED.UI.MainHUD")
logger.setLevel(logging.INFO)

class SEEDUIMainHUD(ttk.Frame):
    REQUIRED_MODULES = [
        "seed.core.analytics_engine",
        "seed.core.dialers.qbit_dialer",
        "seed.systemutils.Render"
    ]

    # DEVHUB COMMANDS - must exist before __init__ subscribes
    def _on_launch_command(self, payload=None):
        if self._active:
            logger.warning("[UI] Launch ignored — already active")
            return
        logger.info("[UI] DEVHUB launch command received")
        if not self._verify_modules():
            logger.error("[UI] Module verification failed — aborting UI launch")
            return
        self._build_hud_tab(None)
        self._build_ui()
        self._active = True

    def _on_shutdown_command(self, payload=None):
        logger.info("[UI] DEVHUB shutdown command received")
        self.shutdown()

    def __init__(self, hud, loop=None, event_bus=None, emit=None, track=None,
                 track_id=None, task=None, track_system=None,
                 analytics_engine=None, qbit_dialer=None, qbit_queue=None,
                 state=HUD, ipc_bridge=IPCBridge, storage_root="./SEED_ROOT",
                 parent=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.hud = hud
        self.ipc_bridge = None if ipc_bridge is IPCBridge else ipc_bridge
        self.event_bus = event_bus
        self.storage_root = storage_root
        self.loop = loop
        self.qbit_queue = qbit_queue
        self.track_id = track_id
        self._active = False
        self._shutdown = False
        self.state = state
        self.container = ttk.Frame(parent)
        self.container.grid(row=0, column=0, sticky="nsew")

        # Bind authoritative runtime services only.
        self.track_system = track_system
        self.qbit_dialer = qbit_dialer
        self.analytics_engine = analytics_engine
        self.nlp = NLPInterface(self.storage_root)
        self.intent_engine = NLPIntentEngine()
        self.self_update = SelfUpdateEngine(self.storage_root)

        # HUD frame is built only after UI_MAIN_LAUNCH.
        self.history = defaultdict(list)

        # Matplotlib 3D figure
        self.fig = Figure()
        self.ax = self.fig.add_subplot(111, projection="3d")
        self.canvas = None

        if self.event_bus is not None:
            self.event_bus.subscribe("UI_MAIN_LAUNCH", self._on_launch_command)
            self.event_bus.subscribe("UI_MAIN_SHUTDOWN", self._on_shutdown_command)

        logger.info("[UI] Constructed — waiting for DEVHUB launch command")

    # -----------------------------
    # IPC
    # -----------------------------
    def _async_subscribe(self):
        if self.ipc_bridge is None or self.loop is None:
            return False
        try:
            asyncio.run_coroutine_threadsafe(
                self.ipc_bridge.subscribe("channel.event", self.receive_ipc_event),
                self.loop
            )
            return True
        except Exception:
            logger.exception("[UI] IPC subscription deferred")
            return False

    # -----------------------------
    # HUD Tab Frame
    # -----------------------------
    def _build_hud_tab(self, parent_frame):
        container = parent_frame if parent_frame else self
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)
        self.hud_frame = tk.Frame(container)
        self.hud_frame.grid(row=0, column=0, sticky="nsew")

    # -----------------------------
    # UI Build
    # -----------------------------
    def _build_ui(self):
#        self.root = self.winfo_toplevel()

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Notebook
        self.notebook = ttk.Notebook(self)
        self.notebook.grid(row=0, column=0, sticky="nsew")

        # Tabs
        self.feed_tab = ttk.Frame(self.notebook)
        self.data_tab = ttk.Frame(self.notebook)

        self.notebook.add(self.feed_tab, text="Live Feed")
        self.notebook.add(self.data_tab, text="Data / Logs")

        for tab in (self.feed_tab, self.data_tab):
            tab.grid_rowconfigure(0, weight=1)
            tab.grid_columnconfigure(0, weight=1)

        # Feed Canvas + Buttons (grid only)
        canvas_frame = ttk.Frame(self.feed_tab)
        canvas_frame.grid(row=0, column=0, sticky="nsew")
        canvas_frame.grid_rowconfigure(0, weight=1)
        canvas_frame.grid_columnconfigure(0, weight=1)

        self.canvas = FigureCanvasTkAgg(self.fig, master=canvas_frame)
        self.canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")
        self.canvas.draw()

        button_frame = ttk.Frame(self.feed_tab)
        button_frame.grid(row=1, column=0, sticky="ew")
        ttk.Button(button_frame, text="Zoom").grid(row=0, column=0)
        ttk.Button(button_frame, text="Pan").grid(row=0, column=1)
        ttk.Button(button_frame, text="Save", command=lambda: self.fig.savefig("plot.png")).grid(row=0, column=2)

        self.feed_tab.grid_rowconfigure(0, weight=1)
        self.feed_tab.grid_rowconfigure(1, weight=0)
        self.feed_tab.grid_columnconfigure(0, weight=1)

        # Data / Logs
        self.log_box = tk.Text(self.data_tab, state="disabled", bg="black", fg="lime", wrap="word")
        self.log_box.grid(row=0, column=0, sticky="nsew")
        self.log_scroll = ttk.Scrollbar(self.data_tab, orient="vertical", command=self.log_box.yview)
        self.log_scroll.grid(row=0, column=1, sticky="ns")
        self.log_box.configure(yscrollcommand=self.log_scroll.set)
        self.data_tab.grid_rowconfigure(0, weight=1)
        self.data_tab.grid_columnconfigure(0, weight=1)

        # Configure data tab grid
        self.data_tab.grid_rowconfigure(0, weight=1)
        self.data_tab.grid_columnconfigure(0, weight=1)

        # -----------------------------
        # Start background updates
        # -----------------------------
        threading.Thread(target=self._ui_update_loop, daemon=True).start()
 
        logger.info("[UI] SEED - HUD - console frame hud_right activated")

        # -----------------------------
        # Commands, IPC, Update, Logging, Shutdown
        # -----------------------------

    # -----------------------------------------------------------
    def receive_ipc_event(self, payload):
        self._log(f"[IPC] Received event: {payload}")

    # ======================================================
    # UPDATE LOOP
    # ======================================================
    def _ui_update_loop(self):
        while not self._shutdown:
            packet = {
                "channel": "DEV",
                "payload": time.time()
            }
            self.after(0, lambda p=packet: self._update_visual(p))
            time.sleep(0.5)


    # ======================================================
    # VISUAL UPDATE
    # ======================================================
    def _update_visual(self, packet=[]):
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
    def _log(self, message):
        def _write():
            self.log_box.config(state=tk.NORMAL)
            self.log_box.insert(tk.END, message + "\n")
            self.log_box.see(tk.END)
            self.log_box.config(state=tk.DISABLED)

        if threading.current_thread() is threading.main_thread():
            _write()
        else:
            self.after(0, _write)

    # ======================================================
    # SHUTDOWN
    # ======================================================
    def shutdown(self):
        if self._shutdown:
            return

        logger.info("[UI] Shutting down Developer HUD")
        self._shutdown = True

        try:
            self.destroy()
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
