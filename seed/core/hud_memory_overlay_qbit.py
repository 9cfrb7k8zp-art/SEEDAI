# ========================================================== 
# FILE: hud_memory_overlay_qbit.py
# PATH: SEED_ROOT/seed/core/hud_memory_overlay_qbit.py
# VERSION: 2.0.0 – TrackID-enhanced memory overlay
# UPDATED: 2025-12-30
# ==========================================================

from collections import deque
import time
import tracemalloc
import uuid

class HUDMemoryOverlayQbit:
    """
    Memory overlay with:
    - Real-time memory snapshots
    - Per-channel weighted traffic (Qbit scaling)
    - Device events logging
    - TrackID integrated for each snapshot
    """

    def __init__(self, device_manager=None, channels=None, max_points=200, track_manager=None):
        self.device_manager = device_manager
        self.channels = channels or [3, 6, 9]
        self.max_points = max_points

        # Logs with TrackID
        self.memory_log = deque(maxlen=max_points)             # (ts, mem, track_id)
        self.channel_load_log = {ch: deque(maxlen=max_points) for ch in self.channels}  # (ts, val, track_id)
        self.device_events_log = deque(maxlen=max_points)      # (ts, events, track_id)

        # Playback state
        self.playback_mode = False
        self.playback_paused = False
        self.playback_index = 0
        self.playback_speed = 1.0
        self.last_playback_time = time.time()
        self.start_time = time.time()

        self.last_memory_mb = 0

        # Qbit equalizer multipliers
        self.qbit_factors = {ch: 1.0 for ch in self.channels}

        # TrackID manager
        self.track_manager = track_manager
        self.session_id = str(uuid.uuid4())

    # -----------------------------
    # Generate snapshot TrackID
    # -----------------------------
    def _gen_track_id(self, parent_id=None):
        return f"HUD-MEM-{str(uuid.uuid4())[:8]}" if not self.track_manager else \
               self.track_manager.new(channel="HUD_MEM", skill_name="HUDMemoryOverlayQbit", parent_id=parent_id)

    # -----------------------------
    # Update memory and channels
    # -----------------------------
    def update_memory(self, channel_inputs=None):
        """
        channel_inputs: dict {channel: base_value}
        Applies Qbit multiplier for weighted display
        """
        # Memory snapshot
        snapshot = tracemalloc.take_snapshot()
        current_mem_mb = sum(stat.size for stat in snapshot.statistics('lineno')) / (1024 * 1024)
        timestamp = time.time() - self.start_time

        track_id = self._gen_track_id(parent_id=self.session_id)
        self.memory_log.append((timestamp, current_mem_mb, track_id))
        self.last_memory_mb = current_mem_mb

        # Update channels with Qbit multipliers
        channel_inputs = channel_inputs or {ch: 0 for ch in self.channels}
        for ch in self.channels:
            base_value = channel_inputs.get(ch, 0)
            factor = self.qbit_factors.get(ch, 1.0)
            weighted_value = base_value * factor
            self.channel_load_log[ch].append((timestamp, weighted_value, track_id))

        # Update device events
        if self.device_manager:
            events_snapshot = {dev: ts for dev, ts in self.device_manager.get_active_sessions().items()}
            self.device_events_log.append((timestamp, events_snapshot, track_id))

        return current_mem_mb, track_id

    # -----------------------------
    # Adjust Qbit multipliers dynamically
    # -----------------------------
    def set_qbit_factor(self, channel, factor):
        if channel in self.qbit_factors:
            self.qbit_factors[channel] = factor

    # -----------------------------
    # Playback controls
    # -----------------------------
    def start_playback(self):
        self.playback_mode = True
        self.playback_paused = False
        self.playback_index = 0
        self.last_playback_time = time.time()

    def pause_playback(self):
        self.playback_paused = True

    def resume_playback(self):
        self.playback_paused = False
        self.last_playback_time = time.time()

    def rewind_playback(self, steps=10):
        self.playback_index = max(0, self.playback_index - steps)

    def fast_forward_playback(self, steps=10):
        self.playback_index = min(len(self.memory_log) - 1, self.playback_index + steps)

    def set_playback_speed(self, speed: float):
        self.playback_speed = max(0.01, speed)

    # -----------------------------
    # Get current state for HUD drawing
    # -----------------------------
    def get_current_state(self):
        if self.playback_mode:
            if not self.memory_log:
                return 0, {ch: 0 for ch in self.channels}, {}, None
            if not self.playback_paused:
                now = time.time()
                dt = (now - self.last_playback_time) * self.playback_speed
                steps = max(1, int(dt))
                self.playback_index = min(len(self.memory_log) - 1, self.playback_index + steps)
                self.last_playback_time = now
            idx = self.playback_index
            timestamp, mem, mem_track = self.memory_log[idx]
            channel_snapshot = {ch: (self.channel_load_log[ch][idx][1] if idx < len(self.channel_load_log[ch]) else 0)
                                for ch in self.channels}
            device_events = self.device_events_log[idx][1] if idx < len(self.device_events_log) else {}
            track_id = mem_track
            return mem, channel_snapshot, device_events, track_id
        else:
            if not self.memory_log:
                return 0, {ch: 0 for ch in self.channels}, {}, None
            timestamp, mem, mem_track = self.memory_log[-1]
            channel_snapshot = {ch: (self.channel_load_log[ch][-1][1] if self.channel_load_log[ch] else 0)
                                for ch in self.channels}
            device_events = self.device_events_log[-1][1] if self.device_events_log else {}
            track_id = mem_track
            return mem, channel_snapshot, device_events, track_id
