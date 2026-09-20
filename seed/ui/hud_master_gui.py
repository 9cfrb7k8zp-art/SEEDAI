# ==========================================================
# FILE: hud_master_gui.py
# PATH: SEED_ROOT/seed/ui/hud_master_gui.py
# Master HUD GUI with safe scheduling
# ==========================================================

import tkinter as tk
from seed.ui.hud_scheduler import HUDScheduler
from seed.ui.hud_health_panel import HUDHealthPanel

class HUDMasterGUI:
    """
    Main HUD container.
    Owns Tk root & scheduler.
    """

    def __init__(self, hud_overlay, registry=None, recovery_timeline=None):
        self.hud_overlay = hud_overlay

        self.root = tk.Tk()
        self.root.title("SEED HUD")
        self.root.geometry("900x600")

        self.scheduler = HUDScheduler(self.root)

        if registry and recovery_timeline:
            self.health_panel = HUDHealthPanel(
                self.root,
                registry,
                recovery_timeline
            )
            self.scheduler.every(
                "health_update",
                500,
                self.health_panel.render
            )

        self.root.protocol("WM_DELETE_WINDOW", self.shutdown)

    # -----------------------------
    # Start UI
    # -----------------------------
    def run(self):
        self.root.mainloop()

    # -----------------------------
    # Shutdown safely
    # -----------------------------
    def shutdown(self):
        self.scheduler.shutdown()
        self.root.destroy()
