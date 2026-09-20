# FILE: ui_seed_main_enhanced.py
# PATH: SEED_ROOT/ui/ui_seed_main_enhanced.py
# Label: SEEDUIMain3D_Enhanced

import tkinter as tk
from tkinter import ttk, scrolledtext
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
from collections import defaultdict
import datetime
import csv
import os
import numpy as np
import platform
import socket
import psutil  # for CPU and memory metrics

from seed.core.nlp_interface import NLPInterface
from seed.core.self_update import SelfUpdateEngine
from seed.core.nlp_intent_engine import NLPIntentEngine
from seed.core.nlp_event_router import SEEDNLPEventRouter
from seed.analytics.analytics_engine import SEEDAnalyticsEngine
from seed.core.event_bus import SYSTEM_WARNING

class SEEDUIMain3D_Enhanced:
    """Enhanced HUD + AI Voice Output + 3D Analytics + System Tab"""

    def __init__(self, storage_root="./SEED_ROOT", orchestrator=None):
        self.storage_root = storage_root
        self.orchestrator = orchestrator
        self.export_dir = os.path.join(self.storage_root, "exports")
        os.makedirs(self.export_dir, exist_ok=True)

# inside the SEEDUIMain3D_Enhanced class:

    def _build_system_tab(self, parent):
        ttk.Label(parent, text="System Metrics / Heartbeat / Logs", font=("Arial", 12, "bold")).pack(pady=5)

    # Heartbeat & Metrics Frame
        self.metrics_frame = ttk.Frame(parent)
        self.metrics_frame.pack(fill=tk.X, pady=5)
    
        self.heartbeat_label = ttk.Label(self.metrics_frame, text="Heartbeats: --", font=("Courier", 10))
        self.heartbeat_label.pack(anchor="w", padx=10)

        self.cpu_label = ttk.Label(self.metrics_frame, text="CPU Usage: --%", font=("Courier", 10))
        self.cpu_label.pack(anchor="w", padx=10)
 
        self.mem_label = ttk.Label(self.metrics_frame, text="Memory Usage: --%", font=("Courier", 10))
        self.mem_label.pack(anchor="w", padx=10)

    # System log console
        self.sys_console = scrolledtext.ScrolledText(parent, width=140, height=20, state='disabled')
        self.sys_console.pack(fill=tk.BOTH, expand=True, pady=5)

    def _update_system_console(self):
    # Update metrics
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory().percent
        self.cpu_label.config(text=f"CPU Usage: {cpu:.1f}%")
        self.mem_label.config(text=f"Memory Usage: {mem:.1f}%")

    # Heartbeat status for modules
        heartbeats = []
        if hasattr(self.analytics.heartbeat, "last_emit"):
            heartbeats.append(f"Analytics: {self.analytics.heartbeat.last_emit.strftime('%H:%M:%S')}")
    # Add other module heartbeats here if implemented
        self.heartbeat_label.config(text="Heartbeats: " + " | ".join(heartbeats))

    # Update logs
        self.sys_console.config(state='normal')
        self.sys_console.delete(1.0, tk.END)
        self.sys_console.insert(tk.END, "[System Logs]\n")
        for device_id, records in self.history.items():
            self.sys_console.insert(tk.END, f"{device_id}: {len(records)} events\n")
        self.sys_console.yview(tk.END)
        self.sys_console.config(state='disabled')


        # --------------------------
        # Engines
        # --------------------------
        self.analytics = SEEDAnalyticsEngine(
            self.storage_root, event_bus=getattr(orchestrator, "event_bus", None)
        )
        self.nlp = NLPInterface(storage_root)
        self.self_update = SelfUpdateEngine(storage_root)
        self.intent_engine = NLPIntentEngine()
        self.history = defaultdict(list)

        # Auto-register local PC as device
        hostname = socket.gethostname()
        sys_info = f"{platform.system()}-{platform.release()}"
        self.nlp.devices["LocalPC"] = {"label": f"{hostname} ({sys_info})"}

        # --------------------------
        # Tk window
        # --------------------------
        self.root = tk.Tk()
        self.root.title("SEED AI HUD + 3D Analytics + System")
        self.root.geometry("1200x800")

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # --------------------------
        # HUD tab
        # --------------------------
        self.hud_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.hud_frame, text="HUD")
        self._build_hud_tab(self.hud_frame)

        # --------------------------
        # 3D Analytics tab
        # --------------------------
        self.analytics_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.analytics_frame, text="3D Analytics")
        self._build_analytics_tab(self.analytics_frame)

        # --------------------------
        # System tab
        # --------------------------
        self.system_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.system_frame, text="System")
        self._build_system_tab(self.system_frame)

        # Subscribe to system warnings
        if self.orchestrator:
            self.orchestrator.event_bus.subscribe(SYSTEM_WARNING, self._on_system_warning)

        # Initial graph update
        self.update_graph()

        # Auto-refresh loop
        self.root.after(5000, self._refresh_loop)

    # --------------------------
    # HUD tab UI
    # --------------------------
    def _build_hud_tab(self, parent):
        # Left panel: Devices + Commands
        self.device_vars = {}
        self.device_frame = ttk.Frame(parent)
        self.device_frame.pack(pady=5, fill=tk.X)
        self.refresh_device_list()

        self.mic_button = ttk.Button(parent, text="Mic ON", command=self.toggle_mic)
        self.mic_button.pack(pady=2)
        self.voice_button = ttk.Button(parent, text="Voice Command", command=self.voice_command)
        self.voice_button.pack(pady=2)

        self.command_entry = ttk.Entry(parent, width=80)
        self.command_entry.pack(pady=2)
        self.command_entry.bind("<Return>", self.execute_command)

        self.console = scrolledtext.ScrolledText(parent, width=100, height=12, state='disabled')
        self.console.pack(pady=5)

        self.update_button = ttk.Button(parent, text="Run Self-Update", command=self.run_self_update)
        self.update_button.pack(pady=2)
        self.export_button = ttk.Button(parent, text="Export History to CSV", command=self.export_history_to_csv)
        self.export_button.pack(pady=2)

        # Right panel: AI Voice Output (Dot-Matrix Display)
        self.voice_frame = ttk.LabelFrame(parent, text="AI Voice Output")
        self.voice_frame.place(relx=0.65, rely=0.05, width=300, height=300)

        self.voice_display = scrolledtext.ScrolledText(
            self.voice_frame, width=36, height=16, state='disabled', background="black", foreground="lime", font=("Courier", 10)
        )
        self.voice_display.pack(fill=tk.BOTH, expand=True)

    # --------------------------
    # Analytics tab (3D)
    # --------------------------
    def _build_analytics_tab(self, parent):
        self.fig = plt.Figure(figsize=(10, 6))
        self.ax = self.fig.add_subplot(111, projection='3d')
        self.ax.set_xlabel("Logic Metric (X)")
        self.ax.set_ylabel("Success Rate (Y)")
        self.ax.set_zlabel("Time Index (Z)")
        self.canvas = FigureCanvasTkAgg(self.fig, master=parent)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, pady=5)

    # --------------------------
    # System tab UI
    # --------------------------
    def _build_system_tab(self, parent):
        ttk.Label(parent, text="System Metrics / Devices / Logs", font=("Arial", 12, "bold")).pack(pady=5)
        self.sys_console = scrolledtext.ScrolledText(parent, width=140, height=30, state='disabled')
        self.sys_console.pack(fill=tk.BOTH, expand=True, pady=5)

    # --------------------------
    # Device Handling
    # --------------------------
    def refresh_device_list(self):
        for w in self.device_frame.winfo_children():
            w.destroy()
        self.device_vars.clear()
        for device_id, data in self.nlp.devices.items():
            label = data.get("label", device_id)
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
    # Command processing
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
        if not self.orchestrator:
            self.log("[HUD] Orchestrator not defined")
            return

        nlp_router = SEEDNLPEventRouter(event_bus=self.orchestrator.event_bus)
        results = nlp_router.execute_command(command, devices, hud_interface=self)

        now = datetime.datetime.now()
        for device_id, data in results.items():
            ts_index = len(self.history[device_id])
            self.history[device_id].append((
                data.get("logic_metric", np.random.uniform(-10,10)),
                data.get("success_rate", 0.5)*100,
                ts_index,
                now
            ))
            self.analytics.record_device_result(device_id, data.get("success_rate", 0.5)*100)
            # Update AI voice output display
            self._update_voice_display(f"[{device_id}] {command} executed at {now.strftime('%H:%M:%S')}")

        self.update_graph()
        self._update_system_console()

    # --------------------------
    # AI Voice Display Update
    # --------------------------
    def _update_voice_display(self, text):
        self.voice_display.config(state='normal')
        self.voice_display.insert(tk.END, text + "\n")
        self.voice_display.yview(tk.END)
        self.voice_display.config(state='disabled')

    # --------------------------
    # Self-update
    # --------------------------
    def run_self_update(self):
        self.log("[HUD] Self-update running...")
        self.self_update.optimize(0.9)
        self.refresh_device_list()
        self.update_graph()
        self._update_system_console()

    # --------------------------
    # Graph update (3D)
    # --------------------------
    def update_graph(self):
        self.ax.cla()
        self.ax.set_xlabel("Logic Metric (X)")
        self.ax.set_ylabel("Success Rate (Y)")
        self.ax.set_zlabel("Time Index (Z)")

        max_z = 0
        for device, records in self.history.items():
            if records:
                xs, ys, zs = [], [], []
                for rec in records:
                    x, y, z, ts = rec
                    xs.append(x)
                    ys.append(y)
                    zs.append(z)
                    max_z = max(max_z, z)
                self.ax.plot(xs, ys, zs, marker='o', label=device)

        self.ax.set_xlim(-10, 10)
        self.ax.set_ylim(0, 100)
        self.ax.set_zlim(0, max(max_z,10))
        if any(self.history.values()):
            self.ax.legend()
        self.fig.tight_layout()
        self.canvas.draw()

    # --------------------------
    # Logging
    # --------------------------
    def log(self, msg):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.console.config(state='normal')
        self.console.insert(tk.END, f"[{ts}] {msg}\n")
        self.console.yview(tk.END)
        self.console.config(state='disabled')

    # --------------------------
    # System console update
    # --------------------------
    def _update_system_console(self):
        self.sys_console.config(state='normal')
        self.sys_console.delete(1.0, tk.END)
        self.sys_console.insert(tk.END, "[System Metrics]\n")
        for device_id, records in self.history.items():
            self.sys_console.insert(tk.END, f"{device_id}: {len(records)} events\n")
        self.sys_console.yview(tk.END)
        self.sys_console.config(state='disabled')

    # --------------------------
    # Event Bus Warning Handler
    # --------------------------
    def _on_system_warning(self, event):
        payload = event.get("payload", {})
        source = payload.get("source", "unknown")
        error = payload.get("error", "unspecified")
        self.log(f"[ALERT] {source}: {error}")
        self._update_voice_display(f"[ALERT] {source}: {error}")
        self._update_system_console()

    # --------------------------
    # CSV Export
    # --------------------------
    def export_history_to_csv(self):
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = os.path.join(self.export_dir, f"seed_history_{timestamp}.csv")
        try:
            with open(file_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Device ID", "Logic Metric", "Success Rate", "Time Index", "Timestamp"])
                for device_id, records in self.history.items():
                    for rec in records:
                        x, y, z, ts = rec
                        writer.writerow([device_id, x, y, z, ts.strftime("%Y-%m-%d %H:%M:%S")])
            self.log(f"[HUD] CSV Export Complete → {file_path}")
        except Exception as e:
            self.log(f"[HUD] CSV Export FAILED: {e}")

    # --------------------------
    # Refresh loop
    # --------------------------
    def _refresh_loop(self):
        self.update_graph()
        self._update_system_console()
        self.root.after(5000, self._refresh_loop)

    # --------------------------
    # Run UI
    # --------------------------
    def run(self):
        self.root.mainloop()
