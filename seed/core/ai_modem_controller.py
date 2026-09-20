# FILE: ui_hud_graphics_multi.py
# PATH: SEED_ROOT/ui/ui_hud_graphics_multi.py
# LABEL: SEEDUIGraphicalMultiHUD
# DESCRIPTION: Multi-device HUD with 3D analytics graph, live heartbeat, NLP, DeviceManager, FAT logging, and CSV export.

import tkinter as tk
from tkinter import scrolledtext
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
from collections import defaultdict
import datetime
import csv
import os
import numpy as np
import asyncio

# -----------------------------
# Core Imports
# -----------------------------
from core.nlp_interface import NLPInterface
from core.self_update import SelfUpdateEngine
from core.nlp_intent_engine import NLPIntentEngine
from core.nlp_event_router import SEEDNLPEventRouter
from core.analytics_engine import SEEDAnalyticsEngine
from seed.core.fat_layer import FATLayer
from seed.core.device_manager import DeviceManager
from seed.core.modem_layer import ModemLayer
from seed.core.qbit_layer import QbitLayer

# -----------------------------
# HUD Class
# -----------------------------
class SEEDUIGraphicalMulti:
    """HUD with Multi-Device Control + NLP + 3D Analytics Graph + DeviceManager + FAT + Qbit"""

    def __init__(self, storage_root="./SEED_ROOT", orchestrator=None):
        self.storage_root = storage_root
        self.orchestrator = orchestrator
        self.export_dir = os.path.join(self.storage_root, "exports")
        os.makedirs(self.export_dir, exist_ok=True)

        # --------------------------
        # Engines
        # --------------------------
        self.analytics = SEEDAnalyticsEngine(self.storage_root, event_bus=getattr(orchestrator, "event_bus", None))
        self.nlp = NLPInterface(storage_root)
        self.self_update = SelfUpdateEngine(storage_root)
        self.intent_engine = NLPIntentEngine()
        self.history = defaultdict(list)  # plotting history

        # --------------------------
        # Tkinter window
        # --------------------------
        self.root = tk.Tk()
        self.root.title("SEED AI Multi-Device HUD")
        self.root.geometry("1000x700")

        # Device selection
        self.device_vars = {}
        self.device_frame = tk.Frame(self.root)
        self.device_frame.pack(pady=5, fill=tk.X)

        # Mic / Voice
        self.mic_button = tk.Button(self.root, text="Mic ON", command=self.toggle_mic)
        self.mic_button.pack(pady=4)
        self.voice_button = tk.Button(self.root, text="Voice Command", command=self.voice_command)
        self.voice_button.pack(pady=4)

        # Command entry
        self.command_entry = tk.Entry(self.root, width=60)
        self.command_entry.pack(pady=4)
        self.command_entry.bind("<Return>", self.execute_command)

        # Console
        self.console = scrolledtext.ScrolledText(self.root, width=120, height=12, state='disabled')
        self.console.pack(pady=5)

        # --------------------------
        # 3D Analytics Graph
        # --------------------------
        self.fig = plt.Figure(figsize=(9,5))
        self.ax = self.fig.add_subplot(111, projection='3d')
        self.ax.set_xlabel("Logic Metric (X)")
        self.ax.set_ylabel("Success Rate (Y)")
        self.ax.set_zlabel("Time (Z)")
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.root)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, pady=5)

        # Update / Export buttons
        self.update_button = tk.Button(self.root, text="Run Self-Update", command=self.run_self_update)
        self.update_button.pack(pady=3)
        self.export_button = tk.Button(self.root, text="Export History to CSV", command=self.export_history_to_csv)
        self.export_button.pack(pady=3)

        # --------------------------
        # Device Manager & Modem
        # --------------------------
        self.device_manager = DeviceManager(self.storage_root, hud_interface=self)
        self.modem = ModemLayer(storage_root=self.storage_root)
        self.qbit_layer = QbitLayer(modem=self.modem, storage_root=os.path.join(self.storage_root, "fat"))
        self.qbit_colors = {}

        # Assign dynamic Qbit colors
        for idx, device_id in enumerate(self.device_manager.devices.keys()):
            color_list = ["magenta", "orange", "cyan", "yellow", "pink", "white"]
            self.qbit_colors[device_id] = color_list[idx % len(color_list)]

        # --------------------------
        # Initial setup
        # --------------------------
        self.refresh_device_list()
        self.update_graph()

        # Start async polling
        loop = asyncio.get_event_loop()
        loop.create_task(self.device_manager.initialize())
        self.root.after(500, self._qbit_update_loop)

    # --------------------------
    # Device Handling
    # --------------------------
    def refresh_device_list(self):
        for w in self.device_frame.winfo_children():
            w.destroy()
        self.device_vars.clear()
        devices = {did: label for did, label in self.device_manager.device_labels.items()}
        for device_id, label in devices.items():
            var = tk.BooleanVar()
            tk.Checkbutton(self.device_frame, text=label, variable=var).pack(side=tk.LEFT)
            self.device_vars[device_id] = var

    def get_selected_devices(self):
        return [d for d, v in self.device_vars.items() if v.get()]

    # --------------------------
    # Mic / Voice
    # --------------------------
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

    # --------------------------
    # Commands
    # --------------------------
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
        nlp_router = SEEDNLPEventRouter(event_bus=getattr(self.orchestrator, "event_bus", None))
        results = nlp_router.execute_command(command, devices, hud_interface=self)
        for device_id, result in results.items():
            label = self.device_manager.device_labels.get(device_id, device_id)
            self.log(f"[CMD][{label}] {result}")
        self.update_history()
        self.update_graph()

    # --------------------------
    # Self-Update
    # --------------------------
    def run_self_update(self):
        self.log("[HUD] Self-update running...")
        self.self_update.optimize(0.9)
        self.refresh_device_list()
        self.update_history()
        self.update_graph()

    # --------------------------
    # History Tracking
    # --------------------------
    def update_history(self):
        if not hasattr(self.nlp, "learning_engine"):
            return
        summary = self.nlp.learning_engine.summarize_knowledge()
        now = datetime.datetime.now()
        for device, stats in summary.items():
            self.history[device].append({
                "timestamp": now,
                "success_rate": stats["success_rate"] * 100,
                "logic_metric": stats.get("logic_metric", np.random.uniform(-10,10))
            })
            self.analytics.record_device_result(device, stats["success_rate"] * 100)

    # --------------------------
    # 3D Graph Update
    # --------------------------
    def update_graph(self):
        self.ax.cla()
        self.ax.set_xlabel("Logic / Frequency (X)")
        self.ax.set_ylabel("Success / Amplitude (Y)")
        self.ax.set_zlabel("Time / Phase (Z)")

        max_z = 10
        # History plotting
        for device, records in self.history.items():
            if not records:
                continue
            xs = [r.get("logic_metric", np.random.uniform(-10,10)) for r in records]
            ys = [r["success_rate"] - 50 for r in records]
            zs = [(r["timestamp"] - records[0]["timestamp"]).total_seconds()/60 for r in records]
            max_z = max(max_z, max(zs))
            self.ax.plot(xs, ys, zs, marker="o", label=device)

        # Qbit visualization
        with self.qbit_layer.lock:
            for device_id, states in self.qbit_layer.incoming_states.items():
                for s in states[-50:]:
                    state = s["state"]
                    ts = s["timestamp"]
                    x = state.get("frequency",0)*10
                    y = state.get("amplitude",0)*100
                    z = state.get("phase",0)*10
                    self.ax.scatter(x, y, z, color=self.qbit_colors.get(device_id,"white"), alpha=0.7)

        if any(self.history.values()):
            self.ax.legend()
        self.fig.tight_layout()
        self.canvas.draw()

    # --------------------------
    # Qbit Update Loop
    # --------------------------
    def _qbit_update_loop(self):
        self.update_graph()
        self.root.after(500, self._qbit_update_loop)

    # --------------------------
    # Logging
    # --------------------------
    def log(self, msg):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.console.config(state="normal")
        self.console.insert(tk.END, f"[{ts}] {msg}\n")
        self.console.yview(tk.END)
        self.console.config(state="disabled")

    # --------------------------
    # CSV Export
    # --------------------------
    def export_history_to_csv(self):
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = os.path.join(self.export_dir, f"seed_history_{timestamp}.csv")
        try:
            with open(file_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Timestamp", "Device ID", "Success Rate (%)", "Logic Metric"])
                for device, records in self.history.items():
                    for r in records:
                        ts = r["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
                        writer.writerow([ts, device, f"{r['success_rate']:.2f}", f"{r.get('logic_metric',0):.2f}"])
            self.log(f"[HUD] CSV Export Complete → {file_path}")
        except Exception as e:
            self.log(f"[HUD] CSV Export FAILED: {e}")

    # --------------------------
    # Run UI
    # --------------------------
    def run(self):
        self.root.mainloop()
