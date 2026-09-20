# ==========================================================
# FILE: ui_seed_main.py
# PATH: SEED_ROOT/seed/ui/ui_seed_main.py
# MODULE: SEEDUIMain3D (PASSIVE / OPTIONAL UI MODULE)
# VERSION: 4.2-STABLE
# UPDATED: 2026-01-07
#
# ----------------------------------------------------------
# DESIGN NOTES (READ THIS – THIS FIXES THE SYSTEM):
#
# 1. THIS MODULE IS **NOT** A PRIMARY UI ENTRYPOINT.
#    - It is a SUBSYSTEM UI.
#    - It MUST NOT auto-start threads, asyncio, or Tk callbacks.
#
# 2. THE AI / CORE SYSTEM MUST RUN **WITHOUT UI**.
#    - UI is OPTIONAL.
#    - UI is ACTIVATED EXPLICITLY.
#
# 3. ALL TKINTER OPERATIONS MUST RUN ON THE MAIN THREAD
#    *AND ONLY AFTER mainloop() IS ACTIVE*.
#
# 4. NO BACKGROUND THREAD MAY TOUCH TK DIRECTLY.
#
# 5. THIS FILE WAS STABILIZED AFTER MULTIPLE FAILURES CAUSED BY:
#    - Auto-started threads
#    - Async loops inside __init__
#    - UI assuming mainloop existed
#
# TIME SPENT FIXING THIS:
# - Multiple hours tracking lifecycle violations
# - Errors were NOT logic errors, but ORDER-OF-EXECUTION errors
# - Fix = CONTROL + GATES, not more code
#
# ==========================================================

import tkinter as tk
from tkinter import ttk
from tkinter import scrolledtext
import logging
import asyncio
import time
from threading import Thread
import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox, Entry

#from seed.hud.hud import HUDState

# -----------------------------
# Logging
# -----------------------------
logger = logging.getLogger("SEEDUI")
logging.basicConfig(level=logging.INFO)

# -----------------------------
# HUD import (visual only)
# -----------------------------
from seed.ui.Seed_Ui_Main_HUD import SEEDUIMainHUD as HUD

# -----------------------------
# Backend imports (OPTIONAL)
# -----------------------------
try:
    from seed.core.tracked_data import TrackedData
    from seed.core.nlp_intent_engine import SEEDNLPEventRouter, NLPIntentEngine
    from seed.core.event_bus import SEEDEventBus
except ImportError:
    TrackedData = None
    SEEDNLPEventRouter = None
    NLPIntentEngine = None
    SEEDEventBus = None


class SEEDUIMain3D(ttk.Frame):


    def __init__(
        self,
        state,
        parent,
        hud,

#        *,
        ipc_bridge=None,
        event_bus=None,
        orchestrator=None,
#        hud=None,
        wait_for_ready=True,
        storage_root="./SEED_ROOT",
        *args,
        **kwargs
    ):
        print("INIT parent type:", type(parent))
        print("INIT parent value:", parent)
#        print("INIT args:", args)
        kwargs.pop("master", None)
        kwargs.pop("root", None)
        super().__init__(parent)
#        ttk.Frame.__init__(self, parent)


        # -----------------------------
        # Core references (NO SIDE EFFECTS)
        # -----------------------------
#        self.root = root
        self.state = state
        self.hud = hud
        self.parent = parent

        self.root = self.winfo_toplevel()

        self.storage_root = storage_root
        self.event_bus = event_bus
        self.orchestrator = orchestrator

        self._active = False
        self._initialized = False

        # --------------------------------------------------
        # GRID CONTRACT (MANDATORY)
        # --------------------------------------------------
        self.grid(row=0, column=0, sticky="nsew")
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)


        # -----------------------------
        # UI lifecycle control
        # -----------------------------
        self.ui_active = False   # HARD GATE — UI is OFF by default
        self.listener_thread = None

        # -----------------------------
        # Backend references (lazy)
        # -----------------------------

        self.ipc = ipc_bridge
        self.nlp_engine = None
        self.nlp_router = None


        if self.orchestrator:
            self.event_bus = self.orchestrator.event_bus
            self.nlp_engine = getattr(self.orchestrator, "nlp_engine", None)
            self.nlp_router = getattr(self.orchestrator, "nlp_router", None)

        # -----------------------------
        # Build frames ONLY (safe before mainloop)
        # -----------------------------
        self._build_frames()

        # -----------------------------
        # UI widgets are built ONLY when activated
        # -----------------------------
        self._initialized = True
        self._build_ui()

    # ======================================================
    # FRAME SETUP (SAFE — NO THREADS, NO CALLBACKS)
    # ======================================================

    def _build_ui(self):
        label = tk.Label(self, text="HUD Initialized")
        label.grid(row=0, column=0, sticky="nsew")

    def on_load(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        ttk.Label(
            self,
            text="3D ENGINE ONLINE"
        ).grid(row=0, column=0, sticky="w", padx=6, pady=4)


    def on_unload(self):
        self._active = False

    def handle_command(self, cmd):
        print("[3D CMD]", cmd)

    def _build_frames(self):

        # ROOT (self) grid config
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # MAIN FRAME
        self.main_frame = tk.Frame(self)
        self.main_frame.grid(row=0, column=0, sticky="nsew")

        self.main_frame.grid_rowconfigure(1, weight=1)
        self.main_frame.grid_columnconfigure(0, weight=1)

        # HUD (top bar)
        self.hud_frame = tk.Frame(self.main_frame, bg="black", height=150)
        self.hud_frame.grid(row=0, column=0, sticky="ew")

        # DASHBOARD (center / expandable)
        self.dashboard_frame = tk.Frame(self.main_frame, bg="gray15")
        self.dashboard_frame.grid(row=1, column=0, sticky="nsew")

    # UI layout uses grid locally. Do not monkey-patch Tk globally;
    # other SEED UI components may legitimately use their own layout managers.

    # ======================================================
    # EXPLICIT UI ACTIVATION (THIS FIXES THE ERRORS)
    # ======================================================
    def activate_ui(self):
        if self.ui_active:
            return

        logger.info("[UI] Activating UI subsystem")
        self.ui_active = True

        self._init_hud()
        self._build_dashboard(self.dashboard_frame)

        if self.event_bus:
            self._start_eventbus_listener_async()

    # ======================================================
    # HUD INITIALIZATION (VISUAL ONLY)
    # ======================================================
    def _init_hud(self):
        try:
            self.hud = HUD(parent=self.hud_frame)
            if hasattr(self.hud, "build"):
                self.hud.build()
        except Exception as e:
            logger.error(f"[UI] HUD init failed: {e}")

    # ======================================================
    # ======================================================
    # DASHBOARD
    # ======================================================
    def _build_dashboard(self, parent_frame):

        # Parent grid config
        parent_frame.grid_rowconfigure(0, weight=1)
        parent_frame.grid_columnconfigure(0, weight=1)

        # Container frame (so text + scrollbar live together cleanly)
        console_frame = ttk.Frame(parent_frame)
        console_frame.grid(row=0, column=0, sticky="nsew")

        console_frame.grid_rowconfigure(0, weight=1)
        console_frame.grid_columnconfigure(0, weight=1)

        # Text widget
        self.dashboard_console = tk.Text(
            console_frame,
            bg="black",
            fg="lime",
            font=("Consolas", 10),
            wrap="word"
        )

        self.dashboard_console.grid(
            row=0,
            column=0,
            sticky="nsew"
        )

        # Scrollbar
        scrollbar = ttk.Scrollbar(
            console_frame,
            orient="vertical",
            command=self.dashboard_console.yview
        )

        scrollbar.grid(
            row=0,
            column=1,
            sticky="ns"
        )

        # Connect scrollbar to text
        self.dashboard_console.configure(yscrollcommand=scrollbar.set)

        self._log_to_dashboard("[Dashboard] UI Activated")

    # ======================================================
    # SAFE UI LOGGING
    # ======================================================
    def _log_to_dashboard(self, message):
        if not self.ui_active:
            return

        self.dashboard_console.configure(state="normal")
        self.dashboard_console.insert(tk.END, f"{message}\n")
        self.dashboard_console.see(tk.END)
        self.dashboard_console.configure(state="disabled")

    def _log_to_dashboard_threadsafe(self, message):
        if not self.ui_active:
            return

        try:
            self.after(0, lambda: self._log_to_dashboard(message))
        except RuntimeError:
            # mainloop not running — ignore safely
            pass

    # ======================================================
    # EVENT BUS LISTENER (OPTIONAL, ISOLATED)
    # ======================================================
    def _start_eventbus_listener_async(self):

        async def event_listener():
            try:
                if hasattr(self.event_bus, "listen_events"):
                    async for evt in self.event_bus.listen_events():
                        self._log_to_dashboard_threadsafe(
                            f"[EventBus] {evt}"
                        )
                else:
                    self._log_to_dashboard_threadsafe(
                        "[EventBus] No async listener available"
                    )
            except Exception as e:
                self._log_to_dashboard_threadsafe(
                    f"[EventBus] Listener error: {e}"
                )

        def thread_loop():
            try:
                asyncio.run(event_listener())
            except Exception:
                pass  # NEVER crash system

        self.listener_thread = Thread(
            target=thread_loop,
            daemon=True
        )
        self.listener_thread.start()


# ==========================================================
# MANUAL TEST MODE ONLY
# ==========================================================
if __name__ == "__main__":
    root = tk.Tk()
    root.title("SEED UI (TEST MODE)")
    root.geometry("900x700")

    ui = SEEDUIMain3D(
        root=root,
        storage_root="./SEED_ROOT",
        event_bus=None
    )

    # IMPORTANT:
    # UI is NOT ACTIVE until this call
    root.after(100, ui.activate_ui)

    root.mainloop()
#