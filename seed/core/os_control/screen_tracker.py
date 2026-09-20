# ==========================================================
# FILE: screen_tracker.py
# PATH: SEED_ROOT/seed/core/os_control/screen_tracker.py
# VERSION: 1.0.0
# PURPOSE: Lightweight screen perception for help-mode mapping.
# ==========================================================
from __future__ import annotations
import time

class ScreenTracker:
    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self.previous = None
        self.last = None

    def capture(self):
        try:
            import mss
            with mss.mss() as sct:
                monitor = sct.monitors[1]
                return sct.grab(monitor)
        except Exception:
            return None

    def analyze(self, frame=None, detail="normal", help_mode=True):
        if not help_mode:
            return {"status":"DISABLED","points":[],"groups":[]}
        frame = frame if frame is not None else self.capture()
        if frame is None:
            return {"status":"NO_FRAME","points":[],"groups":[]}
        try:
            import cv2, numpy as np
            arr = np.asarray(frame)[:, :, :3]
            gray = cv2.cvtColor(arr, cv2.COLOR_BGRA2GRAY) if arr.shape[2] == 4 else cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 60, 160)
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            scale = {"low":0.003,"normal":0.001,"high":0.0004}.get(str(detail).lower(),0.001)
            min_area = max(120, int(arr.shape[0]*arr.shape[1]*scale))
            groups=[]
            for idx, c in enumerate(sorted(contours, key=cv2.contourArea, reverse=True)[:80]):
                x,y,w,h=cv2.boundingRect(c)
                if w*h < min_area or w < 12 or h < 10: continue
                label="object"
                if w > 80 and h < 80: label="text_or_control"
                elif w > 120 and h > 80: label="image_or_panel"
                groups.append({"id":idx,"label":label,"bounds":(x,y,w,h),"area":w*h,"points":[]})
            for g in groups:
                x,y,w,h=g["bounds"]
                g["points"]=[{"x":x,"y":y},{"x":x+w,"y":y},{"x":x+w,"y":y+h},{"x":x,"y":y+h},{"x":x+w//2,"y":y+h//2}]
            result={"status":"MAPPED","timestamp":time.time(),"detail":detail,"groups":groups,"points":[p for g in groups for p in g["points"]],"size":(arr.shape[1],arr.shape[0])}
            if self.event_bus:
                try: self.event_bus.emit("SCREEN_MAP_UPDATED", result)
                except Exception: pass
            self.last=result
            self.previous=gray
            return result
        except Exception as exc:
            return {"status":"ERROR","error":str(exc),"points":[],"groups":[]}

    def motion(self, frame=None):
        frame = frame if frame is not None else self.capture()
        if frame is None: return {"status":"NO_FRAME","motion":0.0}
        try:
            import cv2, numpy as np
            arr=np.asarray(frame)
            gray=cv2.cvtColor(arr[:,:,:3],cv2.COLOR_BGRA2GRAY) if arr.shape[2]==4 else cv2.cvtColor(arr,cv2.COLOR_BGR2GRAY)
            if self.previous is None: self.previous=gray; return {"status":"BASELINE","motion":0.0}
            delta=cv2.absdiff(self.previous,gray)
            score=float((delta>25).mean())
            self.previous=gray
            return {"status":"MOTION","motion":score,"timestamp":time.time()}
        except Exception as exc: return {"status":"ERROR","error":str(exc),"motion":0.0}