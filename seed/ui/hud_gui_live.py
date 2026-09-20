# ==========================================================
# FILE: hud_gui_live.py
# PATH: SEED_ROOT/seed/ui/hud_gui_live.py
# SEED HUD Live Overlay v03
# Updates:
# - Full handshake_manager & hud_overlay integration
# - Safe method checks
# - Dynamic per-channel visualization
# ==========================================================

import tkinter as tk
import logging

logger = logging.getLogger("HUDGUILive")


class HUDGUILive:
    def __init__(self, hud_overlay=None, handshake_manager=None, event_bus=None):
        self.hud_overlay = hud_overlay
        self.handshake_manager = handshake_manager
        self.event_bus = event_bus
        self.root = tk.Tk()
        self.root.title("SEED HUD Live")
        self.root.geometry("600x400")
        self.running = True

        # -----------------------------
        # Verify handshake manager safely
        # -----------------------------
        if self.handshake_manager is None:
            logger.warning("[HUDGUILive] No handshake_manager provided!")
        elif not hasattr(self.handshake_manager, "modem"):
            logger.warning("[HUDGUILive] handshake_manager missing 'modem' attribute!")

        # -----------------------------
        # Playback controls
        # -----------------------------
        self.create_controls()

        # -----------------------------
        # Canvas for live visualization
        # -----------------------------
        self.canvas = tk.Canvas(self.root, width=580, height=250, bg="black")
        self.canvas.pack(pady=10)

        # -----------------------------
        # Start update loop
        # -----------------------------
        self.root.after(100, self.update_loop)
        print("[HUDGUILive v03] Loaded successfully")

    # -----------------------------
    # Playback controls
    # -----------------------------
    def create_controls(self):
        frame = tk.Frame(self.root)
        frame.pack(pady=5)
        tk.Button(frame, text="Play", command=self.safe_play).grid(row=0, column=0, padx=5)
        tk.Button(frame, text="Pause", command=self.safe_pause).grid(row=0, column=1, padx=5)
        tk.Button(frame, text="Rewind", command=self.safe_rewind).grid(row=0, column=2, padx=5)
        tk.Button(frame, text="Fast Forward", command=self.safe_fast_forward).grid(row=0, column=3, padx=5)
        tk.Label(frame, text="Speed:").grid(row=1, column=0)
        self.speed_var = tk.DoubleVar(value=1.0)
        tk.Entry(frame, textvariable=self.speed_var, width=5).grid(row=1, column=1)
        tk.Button(frame, text="Set Speed", command=self.safe_set_speed).grid(row=1, column=2, columnspan=2)

    # -----------------------------
    # Playback safe wrappers
    # -----------------------------
    def safe_play(self):
        if self.hud_overlay and hasattr(self.hud_overlay, "start_playback"):
            try:
                self.hud_overlay.start_playback()
            except Exception as e:
                logger.warning(f"Play command failed: {e}")

    def safe_pause(self):
        if self.hud_overlay and hasattr(self.hud_overlay, "pause_playback"):
            try:
                self.hud_overlay.pause_playback()
            except Exception as e:
                logger.warning(f"Pause command failed: {e}")

    def safe_rewind(self):
        if self.hud_overlay and hasattr(self.hud_overlay, "rewind_playback"):
            try:
                self.hud_overlay.rewind_playback(steps=10)
            except Exception as e:
                logger.warning(f"Rewind command failed: {e}")

    def safe_fast_forward(self):
        if self.hud_overlay and hasattr(self.hud_overlay, "fast_forward_playback"):
            try:
                self.hud_overlay.fast_forward_playback(steps=10)
            except Exception as e:
                logger.warning(f"Fast Forward command failed: {e}")

    def safe_set_speed(self):
        if self.hud_overlay and hasattr(self.hud_overlay, "set_playback_speed"):
            try:
                speed = float(self.speed_var.get())
                self.hud_overlay.set_playback_speed(speed)
            except ValueError:
                logger.warning("Invalid speed value")
            except Exception as e:
                logger.warning(f"Set speed failed: {e}")

    # -----------------------------
    # Update loop using .after()
    # -----------------------------
    def update_loop(self):
        if not self.running:
            return

        self.canvas.delete("all")

        # 1. Memory usage
        mem = 0
        warning_threshold = 50
        critical_threshold = 100
        if self.hud_overlay:
            mem = getattr(self.hud_overlay, "last_memory_mb", 0)
            warning_threshold = getattr(self.hud_overlay, "warning_threshold", 50)
            critical_threshold = getattr(self.hud_overlay, "critical_threshold", 100)
        mem_color = "blue"
        if mem >= warning_threshold:
            mem_color = "yellow"
        if mem >= critical_threshold:
            mem_color = "red"
        mem_bar_width = min(500, int(mem * 2))
        self.canvas.create_rectangle(50, 20, 50 + mem_bar_width, 50, fill=mem_color)
        self.canvas.create_text(300, 35, text=f"Memory: {mem:.2f} MB", fill="white")

        # 2. Per-channel weighted traffic
        bar_start_y, bar_height, spacing = 70, 20, 10
        channels = getattr(self.hud_overlay, "channels", []) if self.hud_overlay else []
        channel_log = getattr(self.hud_overlay, "channel_weights", {}) if self.hud_overlay else {}
        for i, ch in enumerate(channels):
            weight = channel_log.get(ch, 0)
            bar_width = min(500, int(weight * 20))
            y = bar_start_y + i * (bar_height + spacing)
            self.canvas.create_rectangle(50, y, 50 + bar_width, y + bar_height, fill="green")
            self.canvas.create_text(520, y + bar_height / 2, text=f"Channel {ch}: {weight:.2f}", fill="white")

        # Debug logging
        if getattr(self.hud_overlay, "debug_hud", False):
            logger.debug(f"HUD Update - Memory: {mem:.2f} MB, Channels: {channels}")

        self.root.after(100, self.update_loop)

    # -----------------------------
    # Run / Stop
    # -----------------------------
    def run(self):
        self.root.mainloop()

    def stop(self):
        self.running = False
        self.root.quit()
