# ==========================================================
# FILE: hud_health_panel.py
# PATH: SEED_ROOT/seed/ui/hud_health_panel.py
# Visual system health & failure heatmap
# ==========================================================

import tkinter as tk
import time

class HUDHealthPanel:
    """
    Displays:
    - Module health score
    - Failure heatmap
    - Recovery activity
    """

    def __init__(self, root, registry, recovery_timeline):
        self.registry = registry
        self.timeline = recovery_timeline

        self.frame = tk.Frame(root, bg="black")
        self.frame.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(self.frame, bg="black", height=200)
        self.canvas.pack(fill="x")

        self.text = tk.Text(
            self.frame,
            bg="black",
            fg="lime",
            height=10
        )
        self.text.pack(fill="both", expand=True)

    # -----------------------------
    # Render panel
    # -----------------------------
    def render(self):
        self.canvas.delete("all")
        self.text.delete("1.0", "end")

        now = time.time()
        x = 20
        y = 30

        for module, cfg in self.registry.all():
            failures = [
                e for e in self.timeline.events
                if e["module"] == module and e["action"] == "failure"
            ]

            color = "green"
            if len(failures) >= 3:
                color = "red"
            elif failures:
                color = "yellow"

            self.canvas.create_rectangle(x, y, x + 100, y + 40, fill=color)
            self.canvas.create_text(x + 50, y + 20, text=module, fill="black")

            self.text.insert(
                "end",
                f"{module}: {len(failures)} failures\n"
            )

            y += 50
