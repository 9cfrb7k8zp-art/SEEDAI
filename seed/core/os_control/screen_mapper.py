# ==========================================================
# FILE: screen_mapper.py
# PATH: SEED_ROOT/seed/core/os_control/screen_mapper.py
# VERSION: 1.0.0
# PURPOSE: Map screen regions into cognition-ready dynamic points.
# ==========================================================
from __future__ import annotations
import time

class ScreenMapper:
    def __init__(self, screenshot=None):
        self.screenshot = screenshot
        self.points = []
        self.groups = []
        self.last_map = None

    def capture(self):
        if callable(self.screenshot):
            return self.screenshot()
        try:
            import mss
            with mss.mss() as sct:
                return sct.grab(sct.monitors[1])
        except Exception:
            return None

    def map_regions(self, regions, *, detail="normal", source="screen"):
        detail_level = {"low":1, "normal":2, "high":4}.get(str(detail).lower(),2)
        points = []
        groups = []
        for idx, region in enumerate(regions or []):
            if not isinstance(region, dict):
                continue
            x, y, w, h = [int(region.get(k,0)) for k in ("x","y","w","h")]
            name = region.get("label", f"region_{idx}")
            count = max(1, detail_level)
            local = []
            for row in range(count):
                for col in range(count):
                    px = x + int(w*(col+0.5)/count)
                    py = y + int(h*(row+0.5)/count)
                    local.append({"x":px,"y":py,"group":idx,"label":name})
            points.extend(local)
            groups.append({"group":idx,"label":name,"bounds":(x,y,w,h),"points":local,"source":source})
        self.points = points
        self.groups = groups
        self.last_map = {"timestamp":time.time(),"detail":detail,"points":points,"groups":groups}
        return self.last_map

    def status(self):
        return {"points":len(self.points),"groups":len(self.groups),"mapped":self.last_map is not None}