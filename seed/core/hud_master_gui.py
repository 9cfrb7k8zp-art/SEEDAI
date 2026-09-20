# ==========================================================
# FILE: hud_master_gui.py
# PATH: SEED_ROOT/seed/ui/hud_master_gui.py
# Master HUD GUI wired directly to HUDMasterOverlay
# ==========================================================

import time
import tkinter as tk
from tkinter import ttk

# Import the authoritative overlay
from seed.core.hud_master_overlay import HUDMasterOverlay


class HUDMasterGUI(tk.Tk):
    """
    Visual HUD bound to HUDMasterOverlay
    """

    def __init__(self, overlay: HUDMasterOverlay, refresh_ms=100):
        super().__init__()

        self.overlay = overlay
        self.refresh_ms = refresh_ms

        self.title("SEED :: Master HUD")
        self.geometry("460x320")
        self.resizable(False, False)

        self._build_ui()
        self._update_loop()

    # ==========================================================
    # UI BUILD
    # ==========================================================

    def _build_ui(self):
        self.style = ttk.Style(self)
        self.style.theme_use("default")

        # -------------------------
        # MEMORY
        # -------------------------
        mem_frame = ttk.LabelFrame(self, text="Memory")
        mem_frame.pack(fill="x", padx=10, pady=5)

        self.mem_var = tk.StringVar()
        ttk.Label(mem_frame, textvariable=self.mem_var).pack(anchor="w", padx=10)

        # -------------------------
        # QBIT CHANNELS
        # -------------------------
        qbit_frame = ttk.LabelFrame(self, text="Qbit Channels")
        qbit_frame.pack(fill="x", padx=10, pady=5)

        self.channel_vars = {}
        for ch in self.overlay.channels:
            var = tk.StringVar()
            ttk.Label(qbit_frame, textvariable=var).pack(anchor="w", padx=10)
            self.channel_vars[ch] = var

        # -------------------------
        # DEVICES
        # -------------------------
        dev_frame = ttk.LabelFrame(self, text="Devices")
        dev_frame.pack(fill="x", padx=10, pady=5)

        self.dev_var = tk.StringVar()
        ttk.Label(dev_frame, textvariable=self.dev_var).pack(anchor="w", padx=10)

        # -------------------------
        # PLAYBACK CONTROLS
        # -------------------------
        pb_frame = ttk.LabelFrame(self, text="Playback")
        pb_frame.pack(fill="x", padx=10, pady=5)

        ttk.Button(pb_frame, text="⏸ Pause", command=self.overlay.pause_playback).pack(side="left", padx=5)
        ttk.Button(pb_frame, text="▶ Live", command=self.overlay.resume_playback).pack(side="left", padx=5)
        ttk.Button(pb_frame, text="⏪", command=lambda: self.overlay.rewind(20)).pack(side="left", padx=5)
        ttk.Button(pb_frame, text="⏩", command=lambda: self.overlay.fast_forward(20)).pack(side="left", padx=5)

    # ==========================================================
    # UPDATE LOOP
    # ==========================================================

    def _update_loop(self):
        mem, channels, devices = self.overlay.get_state()

        self.mem_var.set(f"{mem:.2f} MB")

        for ch, val in channels.items():
            self.channel_vars[ch].set(f"Channel {ch}: {val:.2f}")

        self.dev_var.set(f"Active devices: {len(devices)}")

        self.after(self.refresh_ms, self._update_loop)


# ==========================================================
# STANDALONE TEST MODE
# ==========================================================

if __name__ == "__main__":
    # Dummy overlay for GUI test
    overlay = HUDMasterOverlay()
    gui = HUDMasterGUI(overlay)

    def fake_update():
        overlay.update()
        gui.after(100, fake_update)

    fake_update()
    gui.mainloop()
