# ==========================================================
# FILE: hud_gui_qbit.py
# PATH: SEED_ROOT/seed/core/hud_gui_qbit.py
# GUI overlay for SEED with Qbit-equalized channels
# ==========================================================

import tkinter as tk
import threading
import time
from seed.core.hud_qbit_alerts import HUDQbitChannelAlerts
from seed.core.hud_qbit_per_device import QbitPerDeviceTraffic




class HUDGUIQbit:
    """
    HUD GUI overlay for SEED with:
    - Memory bar
    - Qbit-equalized per-channel traffic
    - Device event markers
    - Playback support
    """

    def __init__(self, hud_overlay):
        self.hud_overlay = hud_overlay
        self.root = tk.Tk()
        self.root.title("SEED HUD Qbit Equalizer")
        self.root.geometry("620x480")
        self.running = True

# Initialize alert manager after HUD overlay
        self.alert_manager = QbitChannelAlerts(self.hud_overlay)

# Initialize per-device tracker after HUD overlay
        self.device_tracker = QbitPerDeviceTraffic(self.hud_overlay)

        # Playback controls
        self.create_controls()

        # Canvas for visualization
        self.canvas = tk.Canvas(self.root, width=600, height=300, bg="black")
        self.canvas.pack(pady=10)

        # Event log
        self.event_text = tk.Text(self.root, height=10, width=75, bg="black", fg="white")
        self.event_text.pack(pady=5)
        self.event_text.insert(tk.END, "Device Events:\n")
        self.event_text.config(state=tk.DISABLED)

        # Track known devices
        self.known_devices = set()

        # Start update thread
        self.update_thread = threading.Thread(target=self.update_loop, daemon=True)
        self.update_thread.start()

    def create_controls(self):
        frame = tk.Frame(self.root)
        frame.pack(pady=5)

        tk.Button(frame, text="Play", command=self.play).grid(row=0, column=0, padx=5)
        tk.Button(frame, text="Pause", command=self.pause).grid(row=0, column=1, padx=5)
        tk.Button(frame, text="Rewind", command=self.rewind).grid(row=0, column=2, padx=5)
        tk.Button(frame, text="Fast Forward", command=self.fast_forward).grid(row=0, column=3, padx=5)

        tk.Label(frame, text="Speed:").grid(row=1, column=0)
        self.speed_var = tk.DoubleVar(value=1.0)
        tk.Entry(frame, textvariable=self.speed_var, width=5).grid(row=1, column=1)
        tk.Button(frame, text="Set Speed", command=self.set_speed).grid(row=1, column=2, columnspan=2)

    # -----------------------------
    # Button commands
    # -----------------------------
    def play(self): self.hud_overlay.resume_playback()
    def pause(self): self.hud_overlay.pause_playback()
    def rewind(self): self.hud_overlay.rewind_playback(steps=10)
    def fast_forward(self): self.hud_overlay.fast_forward_playback(steps=10)
    def set_speed(self):
        try:
            speed = float(self.speed_var.get())
            self.hud_overlay.set_playback_speed(speed)
        except ValueError:
            print("Invalid speed value")

    # -----------------------------
    # Update loop for visualization
    # -----------------------------
    def update_loop(self):
        while self.running:
            self.canvas.delete("all")

# In update_loop(), for each channel:
        for i, ch in enumerate(self.hud_overlay.channels):
            weight = channel_snapshot.get(ch, 0)
            bar_color = self.alert_manager.get_channel_color(weight)
            bar_width = min(550, int(weight * 20))
            y = bar_start_y + i * (bar_height + spacing)
            self.canvas.create_rectangle(50, y, 50 + bar_width, y + bar_height, fill=bar_color)
            self.canvas.create_text(570, y + bar_height / 2, text=f"Ch {ch}: {weight:.2f}", fill="white")



# In update_loop():
        self.device_tracker.update()
        per_device_snapshot = self.device_tracker.get_device_channel_snapshot()

# Draw per-device bars under each channel
        bar_offset = 0
        for dev_id, channels in per_device_snapshot.items():
            for i, ch in enumerate(self.hud_overlay.channels):
                weight = channels.get(ch, 0)
                y = bar_start_y + i * (bar_height + spacing) + bar_offset
                bar_width = min(500, int(weight * 20))
        # Use a distinct color per device (example: hash of device_id)
                color_val = int(int(dev_id[:4], 16) % 255)
                bar_color = f"#{color_val:02x}{(255-color_val):02x}80"
                self.canvas.create_rectangle(50, y, 50 + bar_width, y + bar_height, fill=bar_color)
            bar_offset += len(self.hud_overlay.channels) * 5  # spacing between devices



            # Get current state from HUD overlay
            mem, channel_snapshot, device_events = self.hud_overlay.get_current_state()

            # 1. Memory bar
            mem_color = "blue"
            if mem >= getattr(self.hud_overlay, "warning_threshold", 100):
                mem_color = "yellow"
            if mem >= getattr(self.hud_overlay, "critical_threshold", 150):
                mem_color = "red"
            mem_bar_width = min(550, int(mem * 2))
            self.canvas.create_rectangle(50, 20, 50 + mem_bar_width, 50, fill=mem_color)
            self.canvas.create_text(300, 35, text=f"Memory: {mem:.2f} MB", fill="white")

            # 2. Qbit-equalized channel bars
            bar_start_y = 70
            bar_height = 20
            spacing = 10
            for i, ch in enumerate(self.hud_overlay.channels):
                weight = channel_snapshot.get(ch, 0)
                # Color based on weight (optional overload threshold)
                bar_color = "green" if weight <= 20 else "orange"
                bar_width = min(550, int(weight * 20))  # scaled by Qbit multiplier
                y = bar_start_y + i * (bar_height + spacing)
                self.canvas.create_rectangle(50, y, 50 + bar_width, y + bar_height, fill=bar_color)
                self.canvas.create_text(570, y + bar_height / 2, text=f"Ch {ch}: {weight:.2f}", fill="white")

            # 3. Device event markers
            marker_y = 150
            current_device_set = set(device_events.keys())
            new_devices = current_device_set - self.known_devices
            expired_devices = self.known_devices - current_device_set

            # Draw new devices
            for i, dev in enumerate(new_devices):
                x = 50 + int((i / max(1, len(current_device_set))) * 500)
                self.canvas.create_oval(x-4, marker_y + i*12, x+4, marker_y + i*12 + 6, fill="cyan")
            # Draw expired devices
            for i, dev in enumerate(expired_devices):
                x = 50 + int((i / max(1, len(self.known_devices))) * 500)
                self.canvas.create_oval(x-4, marker_y + i*12, x+4, marker_y + i*12 + 6, fill="red")

            self.known_devices = current_device_set

            # Draw current device labels
            for i, dev in enumerate(device_events.keys()):
                x = 50 + int((i / max(1, len(device_events))) * 500)
                self.canvas.create_text(x, marker_y + i*12 - 6, text=dev[:4], fill="white", font=("Arial", 8))

            # 4. Update event log
            self.event_text.config(state=tk.NORMAL)
            self.event_text.delete(2.0, tk.END)
            for dev in device_events.keys():
                self.event_text.insert(tk.END, f"{dev} active\n")
            for dev in expired_devices:
                self.event_text.insert(tk.END, f"{dev} expired\n")
            self.event_text.config(state=tk.DISABLED)

            self.root.update()
            time.sleep(0.1)

    def run(self):
        self.root.mainloop()

    def stop(self):
        self.running = False
        self.root.quit()
