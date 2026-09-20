# ==========================================================
# FILE: fat_visual_replay.py
# PATH: seed/core/fat_visual_replay.py
# ==========================================================

import time

class FATVisualReplay:
    def __init__(self, fat_layer, hud_overlay):
        self.fat = fat_layer
        self.hud = hud_overlay

    def replay(self, speed=1.0):
        logs = self.fat.get_logs(source="camera")
        start = logs[0]["timestamp"]

        for entry in logs:
            delay = (entry["timestamp"] - start) / speed
            time.sleep(max(0, delay))
            self.hud.push(entry["data"])
