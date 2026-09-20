# ==========================================================
# FILE: os_control_manager.py
# PATH: SEED_ROOT/seed/core/os_control/os_control_manager.py
# VERSION: 1.0.0
# PURPOSE: Authority bridge for Seed Mouse and screen mapping.
# ==========================================================
from __future__ import annotations
from .seed_mouse import SeedMouse
from .screen_mapper import ScreenMapper
from .screen_tracker import ScreenTracker

class OSControlManager:
    MODE_HELP = "USER_HELP"
    def __init__(self, qbit_dialer=None, event_bus=None):
        self.qbit_dialer = qbit_dialer
        self.event_bus = event_bus
        try:
            import pyautogui
        except Exception:
            pyautogui = None
        self.mouse = SeedMouse(pyautogui_module=pyautogui)
        self.mapper = ScreenMapper()
        self.tracker = ScreenTracker(event_bus=event_bus)
        self.mode = self.MODE_HELP
        self.enabled = False

    def bind_runtime(self, qbit_dialer=None, event_bus=None):
        if qbit_dialer is not None: self.qbit_dialer = qbit_dialer
        if event_bus is not None: self.event_bus = event_bus
        return self

    def set_user_idle(self, idle: bool):
        self.mouse.set_mode(SeedMouse.MODE_SEED if not idle else SeedMouse.MODE_USER)
        return self.mouse.mode

    def enable_seed_mouse(self, enabled=True):
        self.enabled = bool(enabled)
        self.mouse.enable(enabled)
        return self.status()

    def map_screen(self, regions, detail="normal"):
        result = self.mapper.map_regions(regions, detail=detail, source=self.MODE_HELP)
        return result

    def track_screen(self, detail="normal"):
        return self.tracker.analyze(detail=detail, help_mode=(self.mode == self.MODE_HELP))

    def motion_status(self):
        return self.tracker.motion()

    def handle_mouse_command(self, envelope=None, **kwargs):
        data = envelope if isinstance(envelope, dict) else dict(kwargs)
        action = str(data.get("mouse_action") or data.get("action") or "STATUS").upper()
        if action == "MOVE":
            return self.mouse.move(data.get("x",0), data.get("y",0), execute=bool(data.get("execute",False)))
        if action == "CLICK":
            return self.mouse.click(data.get("x"), data.get("y"), data.get("button","left"), execute=bool(data.get("execute",False)))
        return self.status()

    def status(self):
        return {"subsystem":"OSControl","mode":self.mouse.mode,"seed_mouse_enabled":self.enabled,"mouse":self.mouse.status(),"screen_mapper":self.mapper.status(),"screen_tracker":self.tracker.last or {"status":"IDLE"},"authority":"QbitDialer"}