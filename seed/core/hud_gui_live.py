# ==========================================================
# FILE: hud_gui_live.py
# PATH: SEED_ROOT/seed/core/hud_gui_live.py
# GUI overlay with live memory & channel visualization
# ==========================================================

import tkinter as tk
import threading
import time

class HUDGUILive:
    """
    GUI overlay for SEED HUD with:
    - Interactive playback controls
    - Live memory visualization
    - Per-channel weighted traffic bars
    """

    def __init__(self, hud_overlay):
        self.hud_overlay = hud_overlay
        self.root = tk.Tk()
        self.root.title("SEED HUD Live Controls")
        self.root.geometry("500x400")
        self.running = True

        # Playback controls
        self.create_controls()

        # Canvas for live visualization
        self.canvas = tk.Canvas(self.root, width=480, height=200, bg="black")
        self.canvas.pack(pady=10)

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

        # Speed control
        tk.Label(frame, text="Speed:").grid(row=1, column=0)
        self.speed_var = tk.DoubleVar(value=1.0)
        tk.Entry(frame, textvariable=self.speed_var, width=5).grid(row=1, column=1)
        tk.Button(frame, text="Set Speed", command=self.set_speed).grid(row=1, column=2, columnspan=2)

    # -----------------------------
    # Button commands
    # -----------------------------
    def play(self): self.hud_overlay.start_playback()
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
    # Update loop for live visualization
    # -----------------------------
    def update_loop(self):
        while self.running:
            self.canvas.delete("all")  # Clear canvas

            # Draw memory usage
            mem = self.hud_overlay.last_memory_mb
            mem_color = "blue"
            if mem >= self.hud_overlay.warning_threshold: mem_color = "yellow"
            if mem >= self.hud_overlay.critical_threshold: mem_color = "red"
            mem_bar_width = min(400, int(mem * 2))  # scale to canvas
            self.canvas.create_rectangle(50, 20, 50 + mem_bar_width, 50, fill=mem_color)
            self.canvas.create_text(250, 35, text=f"Memory: {mem:.2f} MB", fill="white")

            # Draw per-channel weighted traffic bars
            bar_start_y = 70
            bar_height = 20
            spacing = 10
            for i, ch in enumerate(self.hud_overlay.channels):
                if self.hud_overlay.channel_load_log[ch]:
                    weight = self.hud_overlay.channel_load_log[ch][-1][1]
                else:
                    weight = 0
                bar_width = min(400, int(weight * 20))
                y = bar_start_y + i * (bar_height + spacing)
                self.canvas.create_rectangle(50, y, 50 + bar_width, y + bar_height, fill="green")
                self.canvas.create_text(460, y + bar_height / 2, text=f"Channel {ch}: {weight:.2f}", fill="white")

            self.root.update()
            time.sleep(0.1)

    def run(self):
        self.root.mainloop()

    def stop(self):
        self.running = False
        self.root.quit()
