# ================================================
# File: seed_3d.py
# Path: seed/ui/modules/seed_3d.py
#
#
# ================================================


from tkinter import ttk
from seed.ui.modules.base import BaseModule

class SEED3DModule(BaseModule):
    def __init__(self, parent, hud):
        super().__init__(parent, hud)
        self.canvas_frame = None

    def on_load(self):
        ttk.Label(
            self,
            text="SEED 3D CORE ONLINE",
            font=("Consolas", 11, "bold")
        ).pack(anchor="w", padx=6, pady=4)

        self.canvas_frame = ttk.Frame(self)
        self.canvas_frame.pack(fill="both", expand=True)

        # SAFE IMPORT (no circulars)
        from seed.ui.ui_seed_main import SEEDUIMain3D

        self.seed_3d = SEEDUIMain3D(
            parent=self.canvas_frame,
            ipc_bridge=self.hud.ipc_bridge,
            event_bus=self.hud.event_bus,
            storage_root=self.hud.storage_root,
            orchestrator=getattr(self.hud, "orchestrator", None)
        )
        self.seed_3d.pack(fill="both", expand=True)

        self.hud.status_var.set("SEED 3D Module Loaded")
        self.hud.event_bus.subscribe("NODE_CONNECTED", self.on_node_change)
        self.hud.event_bus.subscribe("NODE_DISCONNECTED", self.on_node_change)

    def on_node_change(self, payload):
        node_id = payload.get("node_id")
        if hasattr(self.seed_3d, "set_node"):
            self.seed_3d.set_node(node_id)


    def on_unload(self):
        if self.seed_3d:
            try:
                self.seed_3d.destroy()
            except Exception:
                pass

    def handle_command(self, cmd):
        if hasattr(self.seed_3d, "handle_command"):
            self.seed_3d.handle_command(cmd)
