# ==========================================================
# FILE: hud_watchdog_controls.py
# PATH: SEED_ROOT/seed/core/hud_watchdog_controls.py
# HUD controls for Watchdog fault injection
# ==========================================================

class HUDWatchdogControls:
    """
    Provides HUD buttons / commands for injecting watchdog faults.
    """

    def __init__(self, event_bus):
        self.event_bus = event_bus

    # -----------------------------
    # Inject failure
    # -----------------------------
    def inject_failure(self, module_name: str):
        self.event_bus.publish(
            "hud.watchdog.inject",
            {
                "action": "fail",
                "module": module_name
            }
        )

    # -----------------------------
    # Simulate heartbeat loss
    # -----------------------------
    def inject_heartbeat_loss(self, module_name: str):
        self.event_bus.publish(
            "hud.watchdog.inject",
            {
                "action": "heartbeat_loss",
                "module": module_name
            }
        )

    # -----------------------------
    # Recover module
    # -----------------------------
    def recover_module(self, module_name: str):
        self.event_bus.publish(
            "hud.watchdog.inject",
            {
                "action": "recover",
                "module": module_name
            }
        )
