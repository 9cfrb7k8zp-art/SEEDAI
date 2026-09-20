"""
FILE: ui_hud_graphics.py
PATH: SEED_ROOT/ui_hud_graphics.py

SEED MODULE: HUD with Graphical AI Metrics
COMPONENT: Device Performance Visualization

VERSION: 0.3.0
STATUS: Alpha
PLATFORM: Cross-platform

RESPONSIBILITY:
- Display real-time AI learning metrics graphically
- Integrates with enhanced HUD: voice, text, dynamic devices, self-update
- Show device success rates and total attempts
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt

from seed.core.nlp_interface import NLPInterface
from seed.core.self_update import SelfUpdateEngine

class SEEDUIGraphical:
    def __init__(self, storage_root="./SEED_ROOT", device_id="LocalDevice"):
        self.storage_root = storage_root
        self.device_id = device_id

        # Initialize engines
        self.nlp = NLPInterface(storage_root, device_id)
        self.self_update = SelfUpdateEngine(storage_root, device_id)

        # Tkinter window
        self.root = tk.Tk()
        self.root.title("SEED AI Graphical HUD")

        # Device selection dropdown
        self.device_var = tk.StringVar()
        self.device_dropdown = ttk.Combobox(self.root, textvariable=self.device_var)
        self.refresh_device_list()
        self.device_dropdown.pack(pady=5)
        self.device_dropdown.bind("<<ComboboxSelected>>", self.change_device)

        # Mic and Voice Buttons
        self.mic_button = tk.Button(self.root, text="Mic ON", command=self.toggle_mic)
        self.mic_button.pack(pady=5)

        self.voice_button = tk.Button(self.root, text="Start Voice Command", command=self.voice_command)
        self.voice_button.pack(pady=5)

        # Command input
        self.command_entry = tk.Entry(self.root, width=50)
        self.command_entry.pack(pady=5)
        self.command_entry.bind("<Return>", self.execute_command)

        # Console output
        self.console = scrolledtext.ScrolledText(self.root, width=60, height=10, state='disabled')
        self.console.pack(pady=5)

        # Graphical Metrics Panel
        self.fig, self.ax = plt.subplots(figsize=(6,3))
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.root)
        self.canvas.get_tk_widget().pack(pady=5)

        # Self-Update button
        self.update_button = tk.Button(self.root, text="Run Self-Update", command=self.run_self_update)
        self.update_button.pack(pady=5)

        # Initial plot
        self.update_graph()

    # -------------------- Device Selection --------------------
    def refresh_device_list(self):
        devices = list(self.nlp.devices.keys())
        self.device_dropdown['values'] = devices
        if devices:
            self.device_var.set(devices[0])
            self.nlp.device_id = devices[0]

    def change_device(self, event=None):
        selected = self.device_var.get()
        self.nlp.device_id = selected
        self.log(f"[HUD] Device changed to: {selected}")
        self.update_graph()

    # -------------------- Mic & Voice --------------------
    def toggle_mic(self):
        state = self.nlp.toggle_mic()
        self.mic_button.config(text=f"Mic {'ON' if state else 'OFF'}")
        self.log(f"[HUD] Microphone {'enabled' if state else 'disabled'}")

    def voice_command(self):
        if not self.nlp.mic_enabled:
            self.log("[HUD] Mic is OFF. Please enable mic first.")
            return
        self.log("[HUD] Listening for voice command...")
        command = self.nlp.listen()
        if command:
            self.log(f"[VOICE] Heard: {command}")
            self.process_command(command)
        else:
            self.log("[VOICE] No command detected or recognition failed.")

    # -------------------- Command Execution --------------------
    def execute_command(self, event=None):
        command = self.command_entry.get().strip()
        if not command:
            return
        self.command_entry.delete(0, tk.END)
        self.process_command(command)

    def process_command(self, command):
        result = self.nlp.process_command(command)
        status = result.get("status")
        message = result.get("message", "")
        self.log(f"[COMMAND] {command} -> Status: {status}, Message: {message}")
        self.update_graph()

    # -------------------- Self-Update --------------------
    def run_self_update(self):
        self.log("[HUD] Running Self-Update...")
        self.self_update.optimize(success_threshold=0.9)
        self.log("[HUD] Self-Update completed.")
        self.refresh_device_list()
        self.update_graph()

    # -------------------- AI Graphical Metrics --------------------
    def update_graph(self):
        summary = self.nlp.learning_engine.summarize_knowledge()
        devices = list(summary.keys())
        success_rates = [summary[d]['success_rate']*100 for d in devices]
        attempts = [summary[d]['total_attempts'] for d in devices]

        self.ax.clear()
        bars = self.ax.bar(devices, success_rates, color='skyblue', alpha=0.7)
        self.ax.set_ylim(0, 100)
        self.ax.set_ylabel("Success Rate (%)")
        self.ax.set_title("Device Performance Overview")

        # Add attempts as text labels on top of bars
        for bar, attempt in zip(bars, attempts):
            height = bar.get_height()
            self.ax.text(bar.get_x() + bar.get_width()/2, height + 2, f"Attempts: {attempt}", ha='center', fontsize=8)

        self.canvas.draw()

    # -------------------- Console Logging --------------------
    def log(self, text):
        self.console.config(state='normal')
        self.console.insert(tk.END, text + "\n")
        self.console.yview(tk.END)
        self.console.config(state='disabled')

    # -------------------- Run HUD --------------------
    def run(self):
        self.root.mainloop()
