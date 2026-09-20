# ================================================
# File: base.py 
# Path: seed/ui/modules/base.py
#
#
# ================================================

from tkinter import ttk

class BaseModule(ttk.Frame):
    def __init__(self, parent, hud):
        super().__init__(parent)
        self.hud = hud

    def on_load(self): pass
    def on_unload(self): pass
    def handle_command(self, cmd): pass
