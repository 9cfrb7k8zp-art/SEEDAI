# ==========================================================
# FILE: hud_qbit_autobalance.py
# PATH: SEED_ROOT/seed/core/hud_qbit_autobalance.py
# Automatic Qbit multiplier balancing for HUD channels
# ==========================================================

import time

class HUDQbitAutoBalance:
    """
    Automatically adjusts Qbit multipliers for channels based on activity
    """

    def __init__(self, hud_overlay, min_factor=0.5, max_factor=3.0, smoothing=0.1):
        """
        hud_overlay: HUDMemoryOverlayQbitDynamic instance
        min_factor: minimum Qbit multiplier
        max_factor: maximum Qbit multiplier
        smoothing: how quickly multipliers adapt (0-1)
        """
        self.hud_overlay = hud_overlay
        self.min_factor = min_factor
        self.max_factor = max_factor
        self.smoothing = smoothing

    # -----------------------------
    # Update multipliers dynamically
    # -----------------------------
    def update_multipliers(self):
        """
        Analyze current channel loads and adjust Qbit factors
        """
        _, channel_snapshot, _ = self.hud_overlay.get_current_state()

        for ch, weight in channel_snapshot.items():
            # Normalize weight to a factor between min_factor and max_factor
            target_factor = min(max(weight / 20.0, self.min_factor), self.max_factor)  # 20.0 = example nominal load

            # Smooth adjustment to avoid sudden jumps
            current_factor = self.hud_overlay.qbit_factors.get(ch, 1.0)
            new_factor = current_factor + self.smoothing * (target_factor - current_factor)

            self.hud_overlay.qbit_factors[ch] = new_factor
