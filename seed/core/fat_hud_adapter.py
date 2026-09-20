# ==========================================================
# FILE: fat_hud_adapter.py
# ==========================================================

class FATHUDAdapter:
    def __init__(self, event_bus):
        self.event_bus = event_bus

    def push(self, entry):

        self.event_bus.publish("HUD_FAT_EVENT", entry)
