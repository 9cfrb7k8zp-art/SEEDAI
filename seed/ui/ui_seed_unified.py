# FILE: ui_seed_unified.py
# PATH: SEED_ROOT/ui/ui_seed_unified.py

import tkinter as tk
from tkinter import ttk, scrolledtext
from collections import defaultdict
import datetime
import csv
import os
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
from seed.hud.state import HUDState
from seed.core.nlp_interface import NLPInterface
from seed.core.self_update import SelfUpdateEngine
from seed.core.nlp_intent_engine import NLPIntentEngine
from seed.core.nlp_event_router import SEEDNLPEventRouter
from seed.analytics.analytics_engine import SEEDAnalyticsEngine
from seed.core.event_bus import SYSTEM_WARNING

class SEEDUIUnified(ttk.Frame):
    _instance = None  # singleton reference

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, container, parent, event_bus=None, hud=None, state=HUDState, storage_root="./SEED_ROOT", orchestrator=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.container = ttk.Frame(parent)
        self.container.grid(row=0, column=0, sticky="nsew")
        self.hud = hud  # back-reference to DEVHUD

        assert "tk" in globals(), "tk not imported at module level"
        from seed.hud.state import HUDState

        if getattr(self, "_initialized", False):
            return  # avoid re-initialization

        self.state = state or HUDState()
#        self.state = (initial.state)
        self.storage_root = storage_root
        self.orchestrator = orchestrator
        self.event_bus = event_bus
        self.export_dir = os.path.join(self.storage_root, "exports")
        os.makedirs(self.export_dir, exist_ok=True)

        self._active = False
        self._initialized = False
        if state is None:
            from seed.hud.state import HUDState
            state = HUDState(root=self.container, state={})

        # -------------------------------
        # HUD Tab
        # -------------------------------

        self.grid(row=0, column=0, sticky="nsew")
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.notebook = ttk.Notebook(self)
        self.notebook.grid(row=0, column=0, sticky="nsew")
        self.hud_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.hud_frame, text="HUD Controls")
        self._build_hud_tab(self.hud_frame)

        # -------------------------------
        # Analytics Tab
        # -------------------------------
        self.analytics_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.analytics_frame, text="3D Analytics Dashboard")
        self._build_analytics_tab(self.analytics_frame)

        # -------------------------------
        # Engines
        # -------------------------------
        self.analytics = SEEDAnalyticsEngine(self.storage_root)
        self.nlp = NLPInterface(self.storage_root)
        self.self_update = SelfUpdateEngine(self.storage_root)
        self.intent_engine = NLPIntentEngine()
        self.history = defaultdict(list)

        # Subscribe to system warnings
        if self.orchestrator:
            self.orchestrator.event_bus.subscribe(SYSTEM_WARNING, self._on_system_warning)

        # Initial graph
        self.update_graph()
        
        self._build_frames()
        self._initialized = True

        # Auto-refresh loop
        self.after(5000, self._refresh_loop)

    def on_load(self):
        ttk.Label(self, text="3D ENGINE ONLINE").pack()

    def on_unload(self): pass

    def handle_command(self, cmd):
        print("[3D CMD]", cmd)


    # ======================================================
    # FRAME STRUCTURE (SAFE)
    # ======================================================
    def _build_frames(self):

        self.main_frame = ttk.Frame(self)
        self.main_frame.grid(row=0, column=0, sticky="nsew")

        self.main_frame.grid_rowconfigure(0, weight=0)  # header
        self.main_frame.grid_rowconfigure(1, weight=1)  # content
        self.main_frame.grid_rowconfigure(2, weight=0)  # footer
        self.main_frame.grid_columnconfigure(0, weight=1)

        # Header
        self.header_frame = ttk.Frame(self.main_frame)
        self.header_frame.grid(row=0, column=0, sticky="ew")

        # Content
        self.content_frame = ttk.Frame(self.main_frame)
        self.content_frame.grid(row=1, column=0, sticky="nsew")

        self.content_frame.grid_rowconfigure(0, weight=1)
        self.content_frame.grid_columnconfigure(0, weight=1)

        # Footer
        self.footer_frame = ttk.Frame(self.main_frame)
        self.footer_frame.grid(row=2, column=0, sticky="ew")

    # -------------------------------
    # HUD Tab
    # -------------------------------
    def _build_hud_tab(self, parent):
        # Configure the parent grid
        parent.grid_rowconfigure(0, weight=0)  # Device frame
        parent.grid_rowconfigure(1, weight=0)  # Mic & Voice
        parent.grid_rowconfigure(2, weight=0)  # Command entry
        parent.grid_rowconfigure(3, weight=1)  # Console (expandable)
        parent.grid_rowconfigure(4, weight=0)  # Update & Export buttons
        parent.grid_columnconfigure(0, weight=1)

        # Device selection
        self.device_vars = {}
        self.device_frame = ttk.Frame(parent)
        self.device_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        self.refresh_device_list()

        # Mic & Voice buttons frame
        self.voice_frame = ttk.Frame(parent)
        self.voice_frame.grid(row=1, column=0, sticky="w", padx=5, pady=4)

        self.mic_button = ttk.Button(self.voice_frame, text="Mic ON", command=self.toggle_mic)
        self.mic_button.grid(row=0, column=0, padx=2)

        self.voice_button = ttk.Button(self.voice_frame, text="Voice Command", command=self.voice_command)
        self.voice_button.grid(row=0, column=1, padx=2)

        # Command entry
        self.command_entry = ttk.Entry(parent, width=60)
        self.command_entry.grid(row=2, column=0, sticky="ew", padx=5, pady=4)
        self.command_entry.bind("<Return>", self.execute_command)

        # -----------------------------
        # Console: Text widget + Scrollbar
        # -----------------------------
        self.console_frame = ttk.Frame(parent)
        self.console_frame.grid(row=3, column=0, sticky="nsew", padx=5, pady=5)
        self.console_frame.grid_rowconfigure(0, weight=1)
        self.console_frame.grid_columnconfigure(0, weight=1)

        self.console = tk.Text(self.console_frame, width=100, height=10, state='disabled', wrap='word')
        self.console.grid(row=0, column=0, sticky="nsew")

        self.console_scrollbar = ttk.Scrollbar(self.console_frame, orient="vertical", command=self.console.yview)
        self.console_scrollbar.grid(row=0, column=1, sticky="ns")

        self.console.configure(yscrollcommand=self.console_scrollbar.set)

        # Self-update & Export buttons frame
        self.update_export_frame = ttk.Frame(parent)
        self.update_export_frame.grid(row=4, column=0, sticky="w", padx=5, pady=3)

        self.update_button = ttk.Button(self.update_export_frame, text="Run Self-Update", command=self.run_self_update)
        self.update_button.grid(row=0, column=0, padx=2)

        self.export_button = ttk.Button(self.update_export_frame, text="Export History to CSV", command=self.export_history_to_csv)
        self.export_button.grid(row=0, column=1, padx=2)


    # -------------------------------
    # Analytics Tab (3D)
    # -------------------------------
    def _build_analytics_tab(self, parent):
        # Configure parent grid
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        # Create figure and 3D axes
        self.fig = plt.Figure(figsize=(10,6))
        self.ax = self.fig.add_subplot(111, projection='3d')

        self.ax.set_xlabel('Logic Marker (X)')
        self.ax.set_ylabel('Metric Y')
        self.ax.set_zlabel('Time (Z)')

        self.ax.set_xlim(-10, 10)
        self.ax.set_ylim(-50, 50)
        self.ax.set_zlim(0, 100)

        # Embed matplotlib canvas into Tkinter using grid
        self.canvas = FigureCanvasTkAgg(self.fig, master=parent)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

    # -------------------------------
    # Device Handling
    # -------------------------------
    def refresh_device_list(self):
        for w in self.device_frame.winfo_children():
            w.destroy()
        self.device_vars.clear()
        devices = {}
        if self.orchestrator:
            devices = {did: self.orchestrator.device_manager.device_labels.get(did, did)
                       for did in self.orchestrator.device_manager.devices.keys()}
        for device_id, label in devices.items():
            var = tk.BooleanVar()
            tk.Checkbutton(self.device_frame, text=label, variable=var).pack(side=tk.LEFT)
            self.device_vars[device_id] = var

    def get_selected_devices(self):
        return [d for d, v in self.device_vars.items() if v.get()]

    # -------------------------------
    # Mic / Voice
    # -------------------------------
    def toggle_mic(self):
        state = self.nlp.toggle_mic()
        self.mic_button.config(text=f"Mic {'ON' if state else 'OFF'}")
        self.log(f"[HUD] Mic {'enabled' if state else 'disabled'}")

    def voice_command(self):
        if not getattr(self.nlp, "mic_enabled", False):
            self.log("[HUD] Mic OFF")
            return
        command = self.nlp.listen()
        if command:
            self.process_command(command)

    # -------------------------------
    # Commands
    # -------------------------------
    def execute_command(self, event=None):
        cmd = self.command_entry.get().strip()
        self.command_entry.delete(0, tk.END)
        if cmd:
            self.process_command(cmd)

    def process_command(self, command):
        devices = self.get_selected_devices()
        if not devices:
            self.log("[HUD] No devices selected")
            return
        if not self.orchestrator:
            self.log("[HUD] Orchestrator not defined.")
            return
        nlp_router = SEEDNLPEventRouter(event_bus=self.orchestrator.event_bus)
        results = nlp_router.execute_command(command, devices, hud_interface=self)
        for device_id, result in results.items():
            label = self.orchestrator.device_manager.device_labels.get(device_id, device_id)
            self.log(f"[CMD][{label}] {result}")
        self.update_history()
        self.update_graph()

    # -------------------------------
    # Self-update
    # -------------------------------
    def run_self_update(self):
        self.log("[HUD] Self-update running...")
        self.self_update.optimize(0.9)
        self.refresh_device_list()
        self.update_history()
        self.update_graph()

    # -------------------------------
    # Analytics / Graph
    # -------------------------------
    def update_history(self):
        if not hasattr(self.nlp, "learning_engine"):
            self.log("[HUD] NLP Learning Engine not available")
            return
        summary = self.nlp.learning_engine.summarize_knowledge()
        now = datetime.datetime.now()
        for device, stats in summary.items():
            # Store: timestamp, logic marker (X), metric (Y)
            x = np.random.uniform(-10,10)  # Example logic marker
            y = stats["success_rate"] * 100 - 50  # map 0-100 → -50 to 50
            self.history[device].append((x, y, len(self.history[device])))  # Z = index / time
            self.analytics.record_device_result(device, stats["success_rate"] * 100)

    # -------------------------------
    # Update 3D graph with moving timeline
    # -------------------------------
    def update_graph(self, max_history=50):
        self.ax.cla()
        self.ax.set_xlabel('Logic Marker (X)')
        self.ax.set_ylabel('Metric Y')
        self.ax.set_zlabel('Time (Z)')
        self.ax.set_xlim(-10, 10)
        self.ax.set_ylim(-50, 50)

        # Determine Z sliding window
        for device, records in self.history.items():
            if records:
                # Keep only last max_history points
                recent = records[-max_history:]
                xs, ys, zs = [], [], []
                for idx, (x, y, z) in enumerate(recent):
                    xs.append(x)
                    ys.append(y)
                    # Map Z to sliding window (-max_history/2 to +max_history/2)
                    zs.append(idx - max_history//2)
                self.ax.plot(xs, ys, zs, marker='o', label=device)

        self.ax.set_zlim(-max_history//2, max_history//2)
        if any(self.history.values()):
            self.ax.legend()
            self.canvas.draw()

    # -------------------------------
    # Refresh loop with auto-update
    # Refresh loop
    # -------------------------------
    def _refresh_loop(self):
        self.update_graph()
        self.after(5000, self._refresh_loop)
        max_z = 0
        for device, records in self.history.items():
            if records:
                xs, ys, zs = zip(*records)
                self.ax.plot(xs, ys, zs, marker='o', label=device)
                max_z = max(max_z, max(zs))
        self.ax.set_zlim(0, max(max_z, 10))
        if any(self.history.values()):
            self.ax.legend()
        self.canvas.draw()

    def update_tick(self, tick: int):
        pass

    # -------------------------------
    # System Warnings
    # -------------------------------
    def _on_system_warning(self, event):
        payload = event.get("payload", {})
        source = payload.get("source", "unknown")
        error = payload.get("error", "unspecified")
        self.log(f"[ALERT] {source}: {error}")

    # ======================================================
    # LIFECYCLE CONTROL
    # ======================================================
    def on_load(self):
        if self._active:
            return

        self._active = True
        self._build_widgets()


    def on_unload(self):
        self._active = False


    # ======================================================
    # WIDGET BUILD (UI ONLY)
    # ======================================================
    def _build_widgets(self):

        ttk.Label(
            self.header_frame,
            text="SEED MODULE ACTIVE"
        ).grid(row=0, column=0, sticky="w", padx=6, pady=4)

        self.output_box = tk.Text(
            self.content_frame,
            state="disabled",
            wrap="word"
        )
        self.output_box.grid(row=0, column=0, sticky="nsew")

        self.scrollbar = ttk.Scrollbar(
            self.content_frame,
            orient="vertical",
            command=self.output_box.yview
        )
        self.scrollbar.grid(row=0, column=1, sticky="ns")

        self.output_box.configure(yscrollcommand=self.scrollbar.set)

        ttk.Button(
            self.footer_frame,
            text="Test Action",
            command=self._test_action
        ).grid(row=0, column=0, padx=6, pady=4)


    # -------------------------------
    # Logging
    # -------------------------------
    def log(self, text):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.console.config(state='normal')
        self.console.insert(tk.END, f"[{ts}] {text}\n")
        self.console.yview(tk.END)
        self.console.config(state='disabled')
        if not self._active:
            return

        def _write():
            self.output_box.config(state="normal")
            self.output_box.insert(tk.END, message + "\n")
            self.output_box.see(tk.END)
            self.output_box.config(state="disabled")

        self.after(0, _write)

    # -------------------------------
    # CSV Export
    # -------------------------------
    def export_history_to_csv(self):
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = os.path.join(self.export_dir, f"seed_history_{timestamp}.csv")
        try:
            with open(file_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Timestamp", "Device ID", "Logic X", "Metric Y", "Time Z"])
                for device_id, records in self.history.items():
                    for i, (x, y, z) in enumerate(records):
                        writer.writerow([datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                         device_id, f"{x:.2f}", f"{y:.2f}", z])
            self.log(f"[HUD] CSV Export Complete → {file_path}")
        except Exception as e:
            self.log(f"[HUD] CSV Export FAILED: {e}")

    # -------------------------------
    # ======================================================
    # COMMAND ENTRY (OPTIONAL STANDARD)
    # ======================================================
    def handle_command(self, command: str):
        self.log(f"[CMD] {command}")


    # ======================================================
    # INTERNAL TEST
    # ======================================================
    def _test_action(self):
        self.log("Action executed.")