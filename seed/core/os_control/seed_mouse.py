# ==========================================================
# FILE: seed_mouse.py
# PATH: SEED_ROOT/seed/core/os_control/seed_mouse.py
# VERSION: 1.0.0
# PURPOSE: Two-mode SEED mouse authority.
# ==========================================================
from __future__ import annotations
import time
from typing import Any, Optional

class SeedMouse:
    MODE_SEED = "SEED_MOUSE"
    MODE_USER = "USER_MOUSE"
    def __init__(self, pyautogui_module=None):
        self.mode = self.MODE_SEED
        self.enabled = False
        self.last_point = None
        self.pyautogui = pyautogui_module

    def set_mode(self, mode: str):
        mode = str(mode).upper()
        if mode not in (self.MODE_SEED, self.MODE_USER):
            raise ValueError(f"invalid mouse mode: {mode}")
        self.mode = mode
        return self.mode

    def enable(self, enabled=True):
        self.enabled = bool(enabled)
        return self.enabled

    def move(self, x: int, y: int, duration=0.0, *, execute=False):
        point = {"x": int(x), "y": int(y), "mode": self.mode, "timestamp": time.time()}
        self.last_point = point
        if execute and self.enabled and self.mode == self.MODE_SEED and self.pyautogui is not None:
            self.pyautogui.moveTo(point["x"], point["y"], duration=float(duration))
            point["executed"] = True
        else:
            point["executed"] = False
        return point

    def cursor_position(self):
        if self.pyautogui is not None:
            try:
                pos = self.pyautogui.position()
                return {"x":int(pos.x),"y":int(pos.y),"mode":self.mode}
            except Exception:
                pass
        return self.last_point or {"x":None,"y":None,"mode":self.mode}

    def click(self, x=None, y=None, button="left", *, execute=False):
        if x is not None and y is not None:
            self.move(x, y, execute=execute)
        executed = False
        if execute and self.enabled and self.mode == self.MODE_SEED and self.pyautogui is not None:
            self.pyautogui.click(button=button)
            executed = True
        return {"action":"CLICK", "x":x, "y":y, "button":button, "mode":self.mode, "executed":executed}

    def status(self):
        return {"mode":self.mode, "enabled":self.enabled, "last_point":self.last_point}