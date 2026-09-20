# ==========================================================
# FILE: hud_master.py
# PATH: SEED_ROOT/seed/core/hud_master.py
# Master integrated HUD for SEED
# ==========================================================

import time
import threading
import tkinter as tk

from seed.core.hud_memory_overlay_qbit_dynamic import HUDMemoryOverlayQbitDynamic
from seed.core.hud_qbit_autobalance import QbitAutoBalancer
from seed.core.hud_qbit_alerts import QbitChannelAlerts
from seed.core.hud_qbit_per_device import QbitPerDeviceTraffic

class HUDMaster:
    """
    Master HUD combining:
    - Dynamic Qbit channels
    - Auto-balancing multipliers
    - Per-channel alert flashing
    - Per-device contribution visualization
    - Live + playback support
    """

    def __init__(self, device_manager=None, modem=None, log_source=None, channels=None):
        # -----------------------------
        # Initialize overlay
        # -----------------------------
        self.hud_overlay = HUDMemoryOverlayQbitDynamic(
            device_manager=device_manager,
            modem=modem,
            log_source=log_source,
            channels=channels
        )

        # -----------------------------
        # Auto-balancer
        # -----------------------------
        self.qbit_balancer = QbitAutoBalancer(self.hud_overlay)

        # -----------------------------
        # Alert flashing
        # -----------------------------
        self.alert_manager = QbitChannelAlerts(self.hud_overlay)

        # -----------------------------
        # Per-device traffic
        # -----------------------------
        self.device_tracker = QbitPerDeviceTraffic(self.hud_overlay)

        # -----------------------------
        # GUI
        # -----------------------------
        self.root = tk.Tk()
        self.root.title("SEED Master HUD")
        self.root.geometry("700x600")
        self.running = True

        # Playback controls
        self.create_controls()

        # Canvas for visualization
        self.canvas = tk.Canvas(self.root, width=650, height=400, bg="black")
        self.canvas.pack(pady=10)

        # Event log
        self.event_text = tk.Text(self.root, height=10, width=80, bg="black", fg="white")
        self.event_text.pack(pady=5)
        self.event_text.insert(tk.END, "Device Events:\n")
        self.event_text.config(state=tk.DISABLED)

        # Start update thread
        self.update_thread = threading.Thread(target=self.update_loop, daemon=True)
        self.update_thread.start()

    # -----------------------------
    # Playback controls
    # -----------------------------
    def create_controls(self):
        frame = tk.Frame(self.root)
        frame.pack(pady=5)
        tk.Button(frame, text="Play", command=self.hud_overlay.resume_playback).grid(row=0, column=0, padx=5)
        tk.Button(frame, text="Pause", command=self.hud_overlay.pause_playback).grid(row=0, column=1, padx=5)
        tk.Button(frame, text="Rewind", command=lambda: self.hud_overlay.rewind_playback(steps=10)).grid(row=0, column=2, padx=5)
        tk.Button(frame, text="Fast Forward", command=lambda: self.hud_overlay.fast_forward_playback(steps=10)).grid(row=0, column=3, padx=5)
        tk.Label(frame, text="Speed:").grid(row=1, column=0)
        self.speed_var = tk.DoubleVar(value=1.0)
        tk.Entry(frame, textvariable=self.speed_var, width=5).grid(row=1, column=1)
        tk.Button(frame, text="Set Speed", command=lambda: self.hud_overlay.set_playback_speed(self.speed_var.get())).grid(row=1, column=2, columnspan=2)

    # -----------------------------
    # Update loop
    # -----------------------------
    def update_loop(self):
        while self.running:
            self.canvas.delete("all")

            # 1. Update overlay
            self.hud_overlay.update_memory()

            # 2. Auto-balance Qbit multipliers
            self.qbit_balancer.update_multipliers()

            # 3. Update per-device traffic
            self.device_tracker.update()
            per_device_snapshot = self.device_tracker.get_device_channel_snapshot()

            # 4. Get current state
            mem, channel_snapshot, device_events = self.hud_overlay.get_current_state()

            # -----------------------------
            # Draw memory bar
            # -----------------------------
            mem_color = "blue"
            if mem >= 100: mem_color = "yellow"
            if mem >= 150: mem_color = "red"
            mem_bar_width = min(600, int(mem*2))
            self.canvas.create_rectangle(50, 20, 50 + mem_bar_width, 50, fill=mem_color)
            self.canvas.create_text(325, 35, text=f"Memory: {mem:.2f} MB", fill="white")

            # -----------------------------
            # Draw per-channel bars
            # -----------------------------
            bar_start_y = 70
            bar_height = 20
            spacing = 10
            bar_offset = 0
            for dev_id, channels in per_device_snapshot.items():
                for i, ch in enumerate(self.hud_overlay.channels):
                    weight = channels.get(ch, 0)
                    y = bar_start_y + i*(bar_height + spacing) + bar_offset
                    bar_width = min(550, int(weight*20))
                    # Channel color with alert flashing
                    bar_color = self.alert_manager.get_channel_color(weight)
                    self.canvas.create_rectangle(50, y, 50 + bar_width, y + bar_height, fill=bar_color)
                    self.canvas.create_text(610, y + bar_height/2, text=f"{dev_id[:4]} Ch{ch}: {weight:.2f}", fill="white", font=("Arial", 8))
                bar_offset += len(self.hud_overlay.channels) * 5

            # -----------------------------
            # Update event log
            # -----------------------------
            self.event_text.config(state=tk.NORMAL)
            self.event_text.delete(2.0, tk.END)
            for dev in device_events.keys():
                self.event_text.insert(tk.END, f"{dev} active\n")
            self.event_text.config(state=tk.DISABLED)

            self.root.update()
            time.sleep(0.1)

    # -----------------------------
    # Run / Stop
    # -----------------------------
    def run(self):
        self.root.mainloop()

    def stop(self):
        self.running = False
        self.root.quit()
