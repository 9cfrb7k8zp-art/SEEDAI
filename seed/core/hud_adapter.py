# ==========================================================
# FILE: hud_adapter.py
# PATH: SEED_ROOT/seed/core/hud_adapter.py
# HUD Push Adapter – Safe numeric push & data normalization
# ==========================================================

import logging
import time

logger = logging.getLogger("HUDAdapter")


class HUDPushAdapter:
    """
    Wraps a HUD overlay instance to sanitize all push() calls.
    Converts all dict/list fields to numeric-friendly values.
    Prevents HUD warnings from unsupported types.
    """

    def __init__(self, hud_overlay):
        self.hud_overlay = hud_overlay

    # --------------------------------------------------
    def push(self, data):
        """
        Sanitize and push data to HUD overlay.
        Rules:
          - Dicts/lists -> replaced with safe numeric summaries (sum, mean)
          - Non-numeric fields -> ignored or converted to 0
          - timestamp added if missing
        """
        safe_data = self._sanitize_data(data)
        try:
            self.hud_overlay.push(safe_data)
        except Exception as e:
            logger.warning(f"[HUDAdapter] push failed: {e}")

    # --------------------------------------------------
    def _sanitize_data(self, data):
        if not isinstance(data, dict):
            return {"value": float(data) if isinstance(data, (int, float)) else 0.0,
                    "timestamp": time.time()}

        safe = {}
        for k, v in data.items():
            if isinstance(v, (int, float)):
                safe[k] = v
            elif isinstance(v, dict):
                # Summarize dict as sum of numeric values
                safe[k] = sum([x for x in v.values() if isinstance(x, (int, float))])
            elif isinstance(v, list):
                # Summarize list as sum of numeric elements
                safe[k] = sum([x for x in v if isinstance(x, (int, float))])
            else:
                # Non-numeric fallback
                safe[k] = 0.0

        if "timestamp" not in safe:
            safe["timestamp"] = time.time()
        return safe

    # --------------------------------------------------
    def __getattr__(self, name):
        # Forward all other HUD methods transparently
        return getattr(self.hud_overlay, name)
