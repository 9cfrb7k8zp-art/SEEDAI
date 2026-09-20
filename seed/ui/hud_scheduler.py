# ==========================================================
# FILE: hud_scheduler.py
# PATH: SEED_ROOT/seed/ui/hud_scheduler.py
# Safe Tkinter scheduler for SEED HUD
# ==========================================================

class HUDScheduler:
    def __init__(self, root):
        self.root = root
        self.tasks = {}
        self.running = True

    # -----------------------------
    # Schedule repeating task
    # -----------------------------
    def every(self, name, ms, callback):
        self.cancel(name)

        def _run():
            if not self.running:
                return
            callback()
            self.tasks[name] = self.root.after(ms, _run)

        self.tasks[name] = self.root.after(ms, _run)

    # -----------------------------
    # Cancel task
    # -----------------------------
    def cancel(self, name):
        task = self.tasks.pop(name, None)
        if task:
            try:
                self.root.after_cancel(task)
            except Exception:
                pass

    # -----------------------------
    # Stop everything
    # -----------------------------
    def shutdown(self):
        self.running = False
        for name in list(self.tasks.keys()):
            self.cancel(name)
