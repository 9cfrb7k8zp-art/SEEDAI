# ==========================================================
# FILE: hud_memory_overlay_qbit_dynamic.py
# PATH: SEED_ROOT/seed/core/hud_memory_overlay_qbit_dynamic.py
# HUD overlay with Qbit equalizer driven by real inputs
# ==========================================================

from collections import deque
import time
import tracemalloc

class HUDMemoryOverlayQbitDynamic:
    """
    Memory overlay with:
    - Real-time memory
    - Per-channel weighted traffic (Qbit)
    - Device events logging
    - Dynamic Qbit input from handshake, modem, and logs
    """

    def __init__(self, device_manager=None, modem=None, log_source=None, channels=None, max_points=200):
        self.device_manager = device_manager
        self.modem = modem
        self.log_source = log_source  # function returning system log metrics
        self.channels = channels or [3, 6, 9]  # Qbit base frequencies
        self.max_points = max_points

        # Logs
        self.memory_log = deque(maxlen=max_points)
        self.channel_load_log = {ch: deque(maxlen=max_points) for ch in self.channels}
        self.device_events_log = deque(maxlen=max_points)

        # Playback
        self.playback_mode = False
        self.playback_paused = False
        self.playback_index = 0
        self.playback_speed = 1.0
        self.last_playback_time = time.time()
        self.start_time = time.time()

        self.last_memory_mb = 0

        # Qbit multipliers per channel
        self.qbit_factors = {3: 1.0, 6: 1.0, 9: 1.0}

    # -----------------------------
    # Update memory and channels dynamically
    # -----------------------------
    def update_memory(self):
        """
        Calculate memory and weighted channels from real inputs
        """
        timestamp = time.time() - self.start_time

        # Memory snapshot
        snapshot = tracemalloc.take_snapshot()
        current_mem_mb = sum(stat.size for stat in snapshot.statistics('lineno')) / (1024 * 1024)
        self.memory_log.append((timestamp, current_mem_mb))
        self.last_memory_mb = current_mem_mb

        # Channel input calculation
        channel_inputs = {}
        for ch in self.channels:
            # 1. Handshake input: number of active sessions
            handshake_input = len(self.device_manager.active_sessions) if self.device_manager else 0

            # 2. Modem input: TX+RX activity (example: total packets)
            modem_input = sum(self.modem.tx_log) + sum(self.modem.rx_log) if self.modem else 0

            # 3. Log input: optional system metric from log_source
            log_input = self.log_source(ch) if self.log_source else 0

            # Sum inputs for this channel
            base_value = handshake_input + modem_input + log_input

            # Apply Qbit multiplier
            weighted_value = base_value * self.qbit_factors.get(ch, 1.0)
            self.channel_load_log[ch].append((timestamp, weighted_value))

        # Device events
        if self.device_manager:
            events_snapshot = {dev: ts for dev, ts in self.device_manager.get_active_sessions().items()}
            self.device_events_log.append((timestamp, events_snapshot))

        return current_mem_mb

    # -----------------------------
    # Adjust Qbit multipliers dynamically
    # -----------------------------
    def set_qbit_factor(self, channel, factor):
        if channel in self.qbit_factors:
            self.qbit_factors[channel] = factor

    # -----------------------------
    # Playback functions
    # -----------------------------
    def start_playback(self):
        self.playback_mode = True
        self.playback_paused = False
        self.playback_index = 0
        self.last_playback_time = time.time()

    def pause_playback(self): self.playback_paused = True
    def resume_playback(self): self.playback_paused = False; self.last_playback_time = time.time()
    def rewind_playback(self, steps=10): self.playback_index = max(0, self.playback_index - steps)
    def fast_forward_playback(self, steps=10): self.playback_index = min(len(self.memory_log)-1, self.playback_index + steps)
    def set_playback_speed(self, speed: float): self.playback_speed = max(0.01, speed)

    # -----------------------------
    # Get current state for HUD
    # -----------------------------
    def get_current_state(self):
        if self.playback_mode:
            if not self.memory_log:
                return 0, {ch:0 for ch in self.channels}, {}
            if not self.playback_paused:
                now = time.time()
                dt = (now - self.last_playback_time) * self.playback_speed
                steps = max(1, int(dt))
                self.playback_index = min(len(self.memory_log)-1, self.playback_index + steps)
                self.last_playback_time = now
            idx = self.playback_index
            timestamp, mem = self.memory_log[idx]
            channel_snapshot = {ch: (self.channel_load_log[ch][idx][1] if idx < len(self.channel_load_log[ch]) else 0)
                                for ch in self.channels}
            device_events = self.device_events_log[idx][1] if idx < len(self.device_events_log) else {}
            return mem, channel_snapshot, device_events
        else:
            if not self.memory_log:
                return 0, {ch:0 for ch in self.channels}, {}
            timestamp, mem = self.memory_log[-1]
            channel_snapshot = {ch: (self.channel_load_log[ch][-1][1] if self.channel_load_log[ch] else 0)
                                for ch in self.channels}
            device_events = self.device_events_log[-1][1] if self.device_events_log else {}
            return mem, channel_snapshot, device_events
