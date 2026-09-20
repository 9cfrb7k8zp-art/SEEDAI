# ==========================================================
# FILE: hud_motion_overlay.py
# PATH: seed/core/hud_motion_overlay.py
# ==========================================================

import math
import time

class HUDMotionOverlay:
    def __init__(self, canvas):
        self.canvas = canvas
        self.arrows = {}

    def draw_vector(self, qbit):
        if not qbit.get("vector"):
            return

        mag = qbit["vector"]["magnitude"]
        heading = qbit["vector"]["heading"]
        conf = qbit["confidence"]

        length = min(80, mag * 400)
        dx = math.cos(heading) * length
        dy = math.sin(heading) * length

        color = "#%02x%02x00" % (int(255 * conf), int(255 * (1 - conf)))

        cx, cy = 200, 200  # center HUD point
        arrow = self.canvas.create_line(
            cx, cy, cx + dx, cy + dy,
            arrow="last",
            fill=color,
            width=3
        )

        self.canvas.after(120, lambda: self.canvas.delete(arrow))
