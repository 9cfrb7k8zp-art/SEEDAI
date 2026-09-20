# ==========================================================
# FILE: hud_memory_overlay.py
# PATH: SEED_ROOT/seed/core/hud_memory_overlay.py
# HUD overlay with historical playback mode
# ==========================================================

class HUDMemoryOverlay:
    """
    Memory overlay with:
    - Real-time memory visualization
    - Growth-aware warnings
    - Per-channel weighted traffic
    - Historical playback mode
    - Dynamic thresholds
    """

    def __init__(self, hud, device_manager=None, channels=None, max_points=50,
                 predict_steps=10, smoothing_window=3, base_warning_mb=MEMORY_WARNING_THRESHOLD_MB * 0.7,
                 base_critical_mb=MEMORY_WARNING_THRESHOLD_MB):
        self.hud = hud
        self.device_manager = device_manager
        self.channels = channels or [3, 6, 9]
        self.max_points = max_points
        self.predict_steps = predict_steps
        self.smoothing_window = smoothing_window
        self.memory_log = deque(maxlen=max_points)
        self.channel_load_log = {ch: deque(maxlen=max_points) for ch in self.channels}
        self.start_time = time.time()
        self.base_warning = base_warning_mb
        self.base_critical = base_critical_mb
        self.warning_threshold = self.base_warning
        self.critical_threshold = self.base_critical
        self.last_memory_mb = 0
        self.playback_index = 0
        self.playback_mode = False

    # -----------------------------
    # Real-time memory update
    # -----------------------------
    def update_memory(self, channel_weights=None):
        snapshot = tracemalloc.take_snapshot()
        current_mem_mb = sum(stat.size for stat in snapshot.statistics('lineno')) / (1024 * 1024)
        timestamp = time.time() - self.start_time
        self.memory_log.append((timestamp, current_mem_mb))
        self.last_memory_mb = current_mem_mb

        if channel_weights:
            for ch, weight in channel_weights.items():
                self.channel_load_log[ch].append((timestamp, weight))

        self.dynamic_threshold_adaptation()
        self.network_aware_scaling()

        if not self.playback_mode:
            self.draw_overlay()

        return current_mem_mb

    # -----------------------------
    # Enable playback mode
    # -----------------------------
    def start_playback(self):
        self.playback_mode = True
        self.playback_index = 0

    # -----------------------------
    # Stop playback mode
    # -----------------------------
    def stop_playback(self):
        self.playback_mode = False
        self.playback_index = 0

    # -----------------------------
    # Draw HUD overlay
    # -----------------------------
    def draw_overlay(self):
        if not self.hud:
            return

        # Determine source of data: live or playback
        if self.playback_mode:
            if self.playback_index >= len(self.memory_log):
                self.stop_playback()
                return
            timestamp, latest_mem = list(self.memory_log)[self.playback_index]
            channel_snapshot = {ch: list(self.channel_load_log[ch])[self.playback_index][1]
                                if self.playback_index < len(self.channel_load_log[ch]) else 0
                                for ch in self.channels}
            self.playback_index += 1
        else:
            timestamp, latest_mem = self.memory_log[-1]
            channel_snapshot = {ch: self.channel_load_log[ch][-1][1] if self.channel_load_log[ch] else 0
                                for ch in self.channels}

        # Clear HUD
        self.hud.clear()

        # Memory usage
        mem_color = "blue"
        if latest_mem >= self.warning_threshold:
            mem_color = "yellow"
        if latest_mem >= self.critical_threshold:
            mem_color = "red"
        self.hud.draw_text(f"Memory: {latest_mem:.2f} MB", color=mem_color, pos=(10, 10))

        # Per-channel load bars
        bar_start_y = 40
        bar_height = 15
        spacing = 5
        for i, ch in enumerate(self.channels):
            weight = channel_snapshot.get(ch, 0)
            bar_width = min(200, int(weight * 20))
            self.hud.draw_rect((10, bar_start_y + i * (bar_height + spacing)),
                               (bar_width, bar_height),
                               color="green")
            self.hud.draw_text(f"Channel {ch} weight: {weight:.2f}",
                               pos=(220, bar_start_y + i * (bar_height + spacing)))

    # -----------------------------
    # Threshold adaptation
    # -----------------------------
    def dynamic_threshold_adaptation(self):
        if len(self.memory_log) < self.smoothing_window + 1:
            return
        recent_points = list(self.memory_log)[-self.smoothing_window - 1:]
        slopes = [(recent_points[i + 1][1] - recent_points[i][1]) /
                  (recent_points[i + 1][0] - recent_points[i][0] if recent_points[i + 1][0] != recent_points[i][0] else 1)
                  for i in range(len(recent_points) - 1)]
        avg_slope = sum(slopes) / len(slopes)
        adaptation_factor = avg_slope * 0.5
        self.warning_threshold = max(self.base_warning, self.warning_threshold + adaptation_factor)
        self.critical_threshold = max(self.base_critical, self.critical_threshold + adaptation_factor)
        self.warning_threshold = min(self.warning_threshold, self.base_critical * 0.95)
        self.critical_threshold = min(self.critical_threshold, self.base_critical * 1.5)

    # -----------------------------
    # Network-aware scaling
    # -----------------------------
    def network_aware_scaling(self):
        if not self.device_manager:
            return
        device_count = len(self.device_manager.devices)
        scale_factor = 1 + device_count * 0.05
        self.warning_threshold = min(self.warning_threshold * scale_factor, self.base_critical * 1.5)
        self.critical_threshold = min(self.critical_threshold * scale_factor, self.base_critical * 2.0)
