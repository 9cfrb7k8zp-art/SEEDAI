# FILE: ui_hud_graphics_multi.py
# PATH: SEED_ROOT/ui/ui_hud_graphics_multi.py
# DESCRIPTION: Multi-device HUD with 3D analytics, live Qbit visualization, NLP, device alerts, heartbeat, logging, CSV export.

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
from seed.core.nlp_interface import NLPInterface
from seed.core.self_update import SelfUpdateEngine
from seed.core.nlp_intent_engine import NLPIntentEngine
from seed.core.nlp_event_router import SEEDNLPEventRouter
from seed.analytics.analytics_engine import SEEDAnalyticsEngine
from seed.core.fat_layer import FATLayer
from seed.core.device_manager import DeviceManager
from seed.core.modem_layer import ModemLayer
from seed.core.qbit_layer import QbitLayer
from seed.core.dialers.qbit_dialer import QbitDialer

# -----------------------------
# HUD Class
# -----------------------------
class SEEDUIGraphicalMulti:
    def __init__(self, storage_root="./SEED_ROOT", orchestrator=None):
        self.storage_root = storage_root
        self.orchestrator = orchestrator

        # --------------------------
        # Engines
        # --------------------------
        self.analytics = SEEDAnalyticsEngine(storage_root, event_bus=getattr(orchestrator, "event_bus", None))
        self.nlp = NLPInterface(storage_root)
        self.self_update = SelfUpdateEngine(storage_root)
        self.intent_engine = NLPIntentEngine()
        self.history = defaultdict(list)

        # Qbit dialer and layer
        self.modem = ModemLayer(storage_root=self.storage_root)
        self.qbit_layer = QbitLayer(modem=self.modem, storage_root=os.path.join(self.storage_root, "fat"))
        self.qbit_dialer = QbitDialer(storage_root, event_bus=getattr(orchestrator, "event_bus", None))

        # Device manager
        self.device_manager = DeviceManager(self.storage_root, hud_interface=self)
        self.device_vars = {}
        self.device_status_labels = {}
        self.device_heartbeat_labels = {}
        self.qbit_colors = {}

        # --------------------------
        # Tkinter window setup
        # --------------------------
        self.root = tk.Tk()
        self.root.title("SEED AI Multi-Device HUD")
        self.root.geometry("1100x750")

        # Device frame
        self.device_frame = tk.Frame(self.root)
        self.device_frame.pack(pady=5, fill=tk.X)

        # Mic / Voice
        self.mic_button = tk.Button(self.root, text="Mic ON", command=self.toggle_mic)
        self.mic_button.pack(pady=2)
        self.voice_button = tk.Button(self.root, text="Voice Command", command=self.voice_command)
        self.voice_button.pack(pady=2)

        # Command entry
        self.command_entry = tk.Entry(self.root, width=60)
        self.command_entry.pack(pady=2)
        self.command_entry.bind("<Return>", self.execute_command)

        # Console
        self.console = scrolledtext.ScrolledText(self.root, width=120, height=12, state='disabled')
        self.console.pack(pady=5)

        # 3D Analytics Graph
        self.fig = plt.Figure(figsize=(10,5))
        self.ax = self.fig.add_subplot(111, projection='3d')
        self.ax.set_xlabel("Logic / Frequency (X)")
        self.ax.set_ylabel("Success / Amplitude (Y)")
        self.ax.set_zlabel("Time / Phase (Z)")
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.root)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, pady=5)

        # Update / Export buttons
        self.update_button = tk.Button(self.root, text="Run Self-Update", command=self.run_self_update)
        self.update_button.pack(pady=2)
        self.export_button = tk.Button(self.root, text="Export History to CSV", command=self.export_history_to_csv)
        self.export_button.pack(pady=2)

        # --------------------------
        # Alert Panel
        # --------------------------
        self.setup_alert_panel()

        # Assign dynamic Qbit colors
        for idx, device_id in enumerate(self.device_manager.devices.keys()):
            color_list = ["magenta", "orange", "cyan", "yellow", "pink", "white"]
            self.qbit_colors[device_id] = color_list[idx % len(color_list)]

        # Device status labels
        for device_id in self.device_manager.devices.keys():
            status_label = tk.Label(self.device_frame, text=device_id, width=25)
            status_label.pack(side=tk.LEFT, padx=2)
            self.device_status_labels[device_id] = status_label

            hb_label = tk.Label(self.device_frame, text="●")
            hb_label.pack(side=tk.LEFT)
            self.device_heartbeat_labels[device_id] = hb_label

        # Export directory
        self.export_dir = os.path.join(self.storage_root, "exports")
        os.makedirs(self.export_dir, exist_ok=True)

        # Start async polling for devices
        loop = asyncio.get_event_loop()
        loop.create_task(self.device_manager.initialize())

        # Start Qbit update loop
        self._qbit_update_loop()

    # --------------------------
    # Alert Panel Setup
    # --------------------------
    def setup_alert_panel(self):
        self.alert_frame = tk.Frame(self.root, bd=2, relief=tk.SUNKEN)
        self.alert_frame.pack(pady=5, fill=tk.X)

        tk.Label(self.alert_frame, text="Alert Configuration", font=("Arial", 12, "bold")).grid(row=0, column=0, columnspan=6)
        headers = ["Device", "Success Rate Min", "Logic Min", "Logic Max", "Qbit Max", "Enable Sound"]
        for idx, text in enumerate(headers):
            tk.Label(self.alert_frame, text=text).grid(row=1, column=idx)

        self.alert_vars = {}
        for row_idx, device_id in enumerate(self.device_manager.devices.keys(), start=2):
            sr_var = tk.DoubleVar(value=30)
            logic_min_var = tk.DoubleVar(value=-8)
            logic_max_var = tk.DoubleVar(value=8)
            qbit_max_var = tk.DoubleVar(value=80)
            sound_var = tk.BooleanVar(value=True)

            self.alert_vars[device_id] = {
                "success_min": sr_var,
                "logic_min": logic_min_var,
                "logic_max": logic_max_var,
                "qbit_max": qbit_max_var,
                "sound": sound_var
            }

            tk.Label(self.alert_frame, text=device_id).grid(row=row_idx, column=0)
            tk.Entry(self.alert_frame, textvariable=sr_var, width=6).grid(row=row_idx, column=1)
            tk.Entry(self.alert_frame, textvariable=logic_min_var, width=6).grid(row=row_idx, column=2)
            tk.Entry(self.alert_frame, textvariable=logic_max_var, width=6).grid(row=row_idx, column=3)
            tk.Entry(self.alert_frame, textvariable=qbit_max_var, width=6).grid(row=row_idx, column=4)
            tk.Checkbutton(self.alert_frame, variable=sound_var).grid(row=row_idx, column=5)

    # --------------------------
    # Qbit Update Loop + Alerts
    # --------------------------
    def _qbit_update_loop(self):
        self.update_graph()
        now = datetime.datetime.now()

        for device_id in self.device_manager.devices.keys():
            thresholds = self.alert_vars.get(device_id, {})
            if not thresholds:
                continue

            # Latest values
            latest_succ = self.history[device_id][-1]["success_rate"] if self.history[device_id] else 50
            latest_logic = self.history[device_id][-1]["logic_metric"] if self.history[device_id] else 0
            latest_qbit = 0
            with self.qbit_layer.lock:
                if device_id in self.qbit_layer.incoming_states and self.qbit_layer.incoming_states[device_id]:
                    latest_qbit = self.qbit_layer.incoming_states[device_id][-1]["state"].get("frequency",0)

            # Thresholds
            sr_min = thresholds["success_min"].get()
            logic_min = thresholds["logic_min"].get()
            logic_max = thresholds["logic_max"].get()
            qbit_max = thresholds["qbit_max"].get()
            sound_enabled = thresholds["sound"].get()

            # Determine alert color
            if latest_succ < sr_min:
                status_color = "red"
            elif not (logic_min <= latest_logic <= logic_max):
                status_color = "orange"
            elif latest_qbit > qbit_max:
                status_color = "magenta"
            else:
                status_color = "green"

            # Update status label
            self.device_status_labels[device_id].config(fg=status_color,
                                                        text=f"{device_id}: {latest_succ:.1f}% | {latest_logic:.1f} | {latest_qbit:.1f}")

            # Sound alert
            if sound_enabled and status_color in ["red", "orange", "magenta"]:
                self.root.bell()  # beep

            # Heartbeat
            hb_color = "green" if now.second % 2 == 0 else "red"
            self.device_heartbeat_labels[device_id].config(fg=hb_color)

        self.root.after(500, self._qbit_update_loop)

    # --------------------------
    # Graph Update
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
    # Device / Mic / Command Handling
    # --------------------------
    def refresh_device_list(self):
        for w in self.device_frame.winfo_children():
            w.destroy()
        self.device_vars.clear()
        for device_id, label in self.device_manager.device_labels.items():
            var = tk.BooleanVar()
            tk.Checkbutton(self.device_frame, text=label, variable=var).pack(side=tk.LEFT)
            self.device_vars[device_id] = var

    def get_selected_devices(self):
        return [d for d, v in self.device_vars.items() if v.get()]

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
    # Self-Update / History
    # --------------------------
    def run_self_update(self):
        self.log("[HUD] Self-update running...")
        self.self_update.optimize(0.9)
        self.refresh_device_list()
        self.update_history()
        self.update_graph()

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
    # Logging / CSV
    # --------------------------
    def log(self, msg):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.console.config(state="normal")
        self.console.insert(tk.END, f"[{ts}] {msg}\n")
        self.console.yview(tk.END)
        self.console.config(state="disabled")

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
