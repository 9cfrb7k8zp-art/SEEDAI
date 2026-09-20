# ==========================================================
# FILE: hud_gui.py
# PATH: SEED_ROOT/seed/core/hud_gui.py
# GUI overlay for HUD interactive controls
# ==========================================================

import tkinter as tk
import threading
import time

class HUDGUI:
    """
    GUI overlay for SEED HUD
    - Play / Pause
    - Rewind / Fast-forward
    - Playback speed adjustment
    """

    def __init__(self, hud_overlay):
        self.hud_overlay = hud_overlay
        self.root = tk.Tk()
        self.root.title("SEED HUD Controls")
        self.root.geometry("400x150")
        self.create_widgets()
        self.running = True

        # Start update thread
        self.update_thread = threading.Thread(target=self.update_loop, daemon=True)
        self.update_thread.start()

    def create_widgets(self):
        # Play / Pause
        self.play_button = tk.Button(self.root, text="Play", command=self.play)
        self.play_button.pack(pady=5)

        self.pause_button = tk.Button(self.root, text="Pause", command=self.pause)
        self.pause_button.pack(pady=5)

        # Rewind / Fast-forward
        self.rewind_button = tk.Button(self.root, text="Rewind", command=self.rewind)
        self.rewind_button.pack(pady=5)

        self.fast_forward_button = tk.Button(self.root, text="Fast Forward", command=self.fast_forward)
        self.fast_forward_button.pack(pady=5)

        # Playback speed
        self.speed_label = tk.Label(self.root, text="Speed:")
        self.speed_label.pack(pady=5)

        self.speed_var = tk.DoubleVar(value=1.0)
        self.speed_entry = tk.Entry(self.root, textvariable=self.speed_var)
        self.speed_entry.pack(pady=5)

        self.set_speed_button = tk.Button(self.root, text="Set Speed", command=self.set_speed)
        self.set_speed_button.pack(pady=5)

    # -----------------------------
    # Button commands
    # -----------------------------
    def play(self):
        self.hud_overlay.start_playback()

    def pause(self):
        self.hud_overlay.pause_playback()

    def rewind(self):
        self.hud_overlay.rewind_playback(steps=10)

    def fast_forward(self):
        self.hud_overlay.fast_forward_playback(steps=10)

    def set_speed(self):
        try:
            speed = float(self.speed_var.get())
            self.hud_overlay.set_playback_speed(speed)
        except ValueError:
            print("Invalid speed value")

    # -----------------------------
    # Update loop (optional visual feedback)
    # -----------------------------
    def update_loop(self):
        while self.running:
            # Optional: update HUD GUI with memory & channel stats
            # Could add labels, bars, etc.
            time.sleep(0.1)

    def run(self):
        self.root.mainloop()

    def stop(self):
        self.running = False
        self.root.quit()
