# ==========================================================
# FILE: hud_memory_overlay_events.py
# PATH: SEED_ROOT/seed/core/hud_memory_overlay_events.py
# HUD overlay with memory, channel weights, and device event playback
# ==========================================================

from collections import deque
import time
import tracemalloc

MEMORY_WARNING_THRESHOLD_MB = 100  # example base

class HUDMemoryOverlayEvents:
    """
    Memory overlay with:
    - Real-time memory visualization
    - Channel-weighted traffic
    - Device event logging and playback
    - Interactive playback controls
    """

    def __init__(self, hud=None, device_manager=None, channels=None, max_points=200):
        self.hud = hud
        self.device_manager = device_manager
        self.channels = channels or [3, 6, 9]
        self.max_points = max_points

        self.memory_log = deque(maxlen=max_points)
        self.channel_load_log = {ch: deque(maxlen=max_points) for ch in self.channels}
        self.device_events_log = deque(maxlen=max_points)  # Store (timestamp, events snapshot)

        # Playback
        self.playback_mode = False
        self.playback_paused = False
        self.playback_index = 0
        self.playback_speed = 1.0
        self.last_playback_time = time.time()
        self.start_time = time.time()

        self.last_memory_mb = 0

    # -----------------------------
    # Update memory and channels
    # -----------------------------
    def update_memory(self, channel_weights=None):
        snapshot = tracemalloc.take_snapshot()
        current_mem_mb = sum(stat.size for stat in snapshot.statistics('lineno')) / (1024 * 1024)
        timestamp = time.time() - self.start_time
        self.memory_log.append((timestamp, current_mem_mb))
        self.last_memory_mb = current_mem_mb

        # Update channel weights
        if channel_weights:
            for ch, weight in channel_weights.items():
                self.channel_load_log[ch].append((timestamp, weight))

        # Update device events snapshot
        if self.device_manager:
            # Copy of active sessions at this timestamp
            events_snapshot = {dev: ts for dev, ts in self.device_manager.get_active_sessions().items()}
            self.device_events_log.append((timestamp, events_snapshot))

        return current_mem_mb

    # -----------------------------
    # Playback controls
    # -----------------------------
    def start_playback(self):
        self.playback_mode = True
        self.playback_paused = False
        self.playback_index = 0
        self.last_playback_time = time.time()

    def stop_playback(self):
        self.playback_mode = False
        self.playback_paused = False
        self.playback_index = 0

    def pause_playback(self):
        self.playback_paused = True

    def resume_playback(self):
        self.playback_paused = False
        self.last_playback_time = time.time()

    def set_playback_speed(self, speed: float):
        self.playback_speed = max(0.01, speed)

    def rewind_playback(self, steps=10):
        self.playback_index = max(0, self.playback_index - steps)

    def fast_forward_playback(self, steps=10):
        self.playback_index = min(len(self.memory_log) - 1, self.playback_index + steps)

    # -----------------------------
    # Get current data for drawing
    # -----------------------------
    def get_current_state(self):
        """
        Returns memory, channel weights, and device events for current index or live
        """
        if self.playback_mode:
            if not self.memory_log:
                return 0, {ch: 0 for ch in self.channels}, {}
            if not self.playback_paused:
                now = time.time()
                dt = (now - self.last_playback_time) * self.playback_speed
                steps = max(1, int(dt))
                self.playback_index = min(len(self.memory_log) - 1, self.playback_index + steps)
                self.last_playback_time = now
            idx = self.playback_index
            timestamp, mem = self.memory_log[idx]
            channel_snapshot = {ch: (self.channel_load_log[ch][idx][1] if idx < len(self.channel_load_log[ch]) else 0)
                                for ch in self.channels}
            device_events = self.device_events_log[idx][1] if idx < len(self.device_events_log) else {}
            return mem, channel_snapshot, device_events
        else:
            if not self.memory_log:
                return 0, {ch: 0 for ch in self.channels}, {}
            timestamp, mem = self.memory_log[-1]
            channel_snapshot = {ch: (self.channel_load_log[ch][-1][1] if self.channel_load_log[ch] else 0)
                                for ch in self.channels}
            device_events = self.device_events_log[-1][1] if self.device_events_log else {}
            return mem, channel_snapshot, device_events
