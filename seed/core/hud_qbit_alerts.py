# ==========================================================
# FILE: hud_qbit_alerts.py
# PATH: SEED_ROOT/seed/core/hud_qbit_alerts.py
# Per-channel alert flashing for HUD Qbit channels
# ==========================================================

import time
import threading
import logging

logger = logging.getLogger("HUDQbitAlerts")

class HUDQbitChannelAlerts:
    """
    Handles per-channel alert flashing based on load thresholds.
    Safe update loop for HUD overlays without using 'event' commands.
    """

    def __init__(self, hud_overlay, warning_threshold=20, critical_threshold=40, flash_interval=0.5, update_interval=0.1):
        """
        hud_overlay: HUDMemoryOverlayQbitDynamic instance
        warning_threshold: load at which channel turns orange
        critical_threshold: load at which channel turns red and flashes
        flash_interval: seconds for flash toggle
        update_interval: seconds for sensor polling
        """
        self.hud_overlay = hud_overlay
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold
        self.flash_interval = flash_interval
        self.flash_interval = flash_interval
        self.update_interval = update_interval

        self.last_flash_time = time.time()
        self.flash_state = False  # True = highlighted, False = normal

        self.running = False
        self.thread = None
        self.channel_colors = {}  # current colors per channel

    # -----------------------------
    # Determine color per channel
    # -----------------------------
    def get_channel_color(self, channel_weight):
        now = time.time()
        if now - self.last_flash_time > self.flash_interval:
            self.flash_state = not self.flash_state
            self.last_flash_time = now

        if channel_weight >= self.critical_threshold:
            return "red" if self.flash_state else "orange"
        elif channel_weight >= self.warning_threshold:
            return "orange"
        else:
            return "green"

    # -----------------------------
    # Sensor update loop
    # -----------------------------
    def sensor_update_loop(self):
        while self.running:
            try:
                channels = getattr(self.hud_overlay, "channels", [])
                weights = getattr(self.hud_overlay, "channel_weights", {})

                for ch in channels:
                    weight = weights.get(ch, 0)
                    self.channel_colors[ch] = self.get_channel_color(weight)

                # Safe sleep for next iteration
                time.sleep(self.update_interval)
            except Exception as e:
                logger.warning(f"HUDQbitAlerts sensor loop error: {e}")

    # -----------------------------
    # Start / Stop
    # -----------------------------
    def start(self):
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self.sensor_update_loop, daemon=True)
            self.thread.start()
            logger.info("HUDQbitAlerts sensor loop started")

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=1)
            self.thread = None
        logger.info("HUDQbitAlerts sensor loop stopped")
