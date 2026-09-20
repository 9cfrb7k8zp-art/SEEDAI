# ==========================================================
# FILE: hud_gui_playback.py
# PATH: SEED_ROOT/seed/core/hud_gui_playback.py
# GUI overlay with playback visualization for memory,
# channel traffic, and device events
# ==========================================================

import tkinter as tk
import threading
import time

class HUDGUIPlayback:
    """
    GUI overlay for SEED HUD with:
    - Interactive playback controls
    - Live memory visualization
    - Per-channel weighted traffic
    - Device event markers with playback support
    """

    def __init__(self, hud_overlay):
        self.hud_overlay = hud_overlay
        self.root = tk.Tk()
        self.root.title("SEED HUD Playback")
        self.root.geometry("600x450")
        self.running = True

        # Playback controls
        self.create_controls()

        # Canvas for memory & channel visualization
        self.canvas = tk.Canvas(self.root, width=580, height=250, bg="black")
        self.canvas.pack(pady=10)

        # Event log text
        self.event_text = tk.Text(self.root, height=8, width=70, bg="black", fg="white")
        self.event_text.pack(pady=5)
        self.event_text.insert(tk.END, "Device Events:\n")
        self.event_text.config(state=tk.DISABLED)

        # Start update thread
        self.update_thread = threading.Thread(target=self.update_loop, daemon=True)
        self.update_thread.start()

    def create_controls(self):
        frame = tk.Frame(self.root)
        frame.pack(pady=5)

        # Play / Pause
        tk.Button(frame, text="Play", command=self.play).grid(row=0, column=0, padx=5)
        tk.Button(frame, text="Pause", command=self.pause).grid(row=0, column=1, padx=5)

        # Rewind / Fast-forward
        tk.Button(frame, text="Rewind", command=self.rewind).grid(row=0, column=2, padx=5)
        tk.Button(frame, text="Fast Forward", command=self.fast_forward).grid(row=0, column=3, padx=5)

        # Playback speed
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

            # Get current state from HUD overlay (supports playback)
            mem, channel_snapshot, device_events = self.hud_overlay.get_current_state()

            # 1. Memory usage bar
            mem_color = "blue"
            if mem >= self.hud_overlay.warning_threshold: mem_color = "yellow"
            if mem >= self.hud_overlay.critical_threshold: mem_color = "red"
            mem_bar_width = min(500, int(mem * 2))
            self.canvas.create_rectangle(50, 20, 50 + mem_bar_width, 50, fill=mem_color)
            self.canvas.create_text(300, 35, text=f"Memory: {mem:.2f} MB", fill="white")

            # 2. Per-channel weighted traffic
            bar_start_y = 70
            bar_height = 20
            spacing = 10
            for i, ch in enumerate(self.hud_overlay.channels):
                weight = channel_snapshot.get(ch, 0)
                bar_width = min(500, int(weight * 20))
                y = bar_start_y + i * (bar_height + spacing)
                self.canvas.create_rectangle(50, y, 50 + bar_width, y + bar_height, fill="green")
                self.canvas.create_text(520, y + bar_height / 2, text=f"Channel {ch}: {weight:.2f}", fill="white")

            # 3. Device event markers
            marker_y = 150
            for i, (device_id, ts) in enumerate(device_events.items()):
                x = 50 + int((i / max(1, len(device_events))) * 500)
                self.canvas.create_oval(x-3, marker_y + i*10, x+3, marker_y + i*10 + 6, fill="cyan")
                self.canvas.create_text(x, marker_y + i*10 - 5, text=device_id[:4], fill="white", font=("Arial", 8))

            # 4. Update event log
            self.event_text.config(state=tk.NORMAL)
            self.event_text.delete(2.0, tk.END)  # Keep header
            for dev, ts in device_events.items():
                self.event_text.insert(tk.END, f"{dev} @ {ts:.2f}\n")
            self.event_text.config(state=tk.DISABLED)

            self.root.update()
            time.sleep(0.1)

    def run(self):
        self.root.mainloop()

    def stop(self):
        self.running = False
        self.root.quit()
