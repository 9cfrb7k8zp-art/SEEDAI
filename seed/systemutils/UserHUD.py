# ==========================================================
# File: UserHUD.py
# Path: SEED_ROOT/seed/systemutils/UserHUD.py
# Version: 1.1 (HUD → DEVHUB Command Launch)
# Updated: 2026-01-03
# ==========================================================

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import time
import webbrowser
import uuid
import platform
from typing import Dict, Any, List
import socket
import json

try:
    from tkhtmlview import HTMLLabel
    HTML_AVAILABLE = True
except ImportError:
    HTML_AVAILABLE = False

from seed.systemutils.Render import Render, RenderMode

# ----------------------------------------------------------
class TrackContext:
    _current = None

    @classmethod
    def get_current(cls):
        return cls._current

# ==========================================================
# UserHUD
# ==========================================================
class UserHUD:
    TIERS = ["Free", "Consumer", "Enterprise", "Education", "Government", "Military"]

    def __init__(self, render_engine: Render, width: int = 1280, height: int = 720,
                 remote_port: int = 5555, event_bus=None):
        self.render = render_engine
        self.width = width
        self.height = height
        self.event_bus = event_bus
        self.hud_channel_id = f"HUD-{str(uuid.uuid4())[:8]}"  # unique channel for DEVHUB

        # --------------------------------------------------
        # Only create root when explicitly started
        # --------------------------------------------------
        self.root = None

        # ==================================================
        # User / Company Data
        # ==================================================
        self.device_id = self._get_device_id()
        self.user_tier = "Free"
        self.user_consented = False
        self.company_monitor_log: List[str] = []
        self.active_users: Dict[str, str] = {}  # user_id -> name
        self.remote_port = remote_port
        self.remote_clients: List[socket.socket] = []

        # ==================================================
        # 3D Camera
        # ==================================================
        self.cam_roll = 0.0
        self.cam_pitch = 0.0
        self.cam_yaw = 0.0
        self.zoom_scale = 1.0
        self.dragging = False
        self.last_mouse = (0, 0)

        # ==================================================
        # HUD overlay tracking
        # ==================================================
        self.overlays: Dict[str, Dict[str, Any]] = {}

        # ==================================================
        # Running state
        # ==================================================
        self.running = False

        # Threads placeholders
        self.update_thread = None
        self.remote_thread = None

    # ======================================================
    # Device ID / hardware
    # ======================================================
    def _get_device_id(self) -> str:
        system = platform.system()
        node = platform.node()
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{system}-{node}"))

    # ======================================================
    # License / consent
    # ======================================================
    def _check_license(self):
        if self.user_tier != "Free":
            licensed = self._validate_hardware_license()
            if not licensed:
                messagebox.showerror("License Error", "Hardware not licensed for this tier. Defaulting to Free.")
                self.user_tier = "Free"

    def _validate_hardware_license(self) -> bool:
        return False

    def _get_user_consent(self):
        if not self.user_consented:
            consent = messagebox.askyesno("User Consent",
                                          "Do you agree to SEED AI Terms of Use and monitoring by the company?")
            if not consent:
                messagebox.showwarning("Consent Required", "SEED AI cannot run without user consent.")
                exit()
            self.user_consented = True
            self._log_company_usage("User consent granted")

    # ======================================================
    # Logging / DEVHUB
    # ======================================================
    def _publish_channel(self, message_type: str, payload: Any):
        if self.event_bus:
            try:
                self.event_bus.publish(self.hud_channel_id, {"type": message_type, "payload": payload})
            except Exception as e:
                self.log(f"[HUD Channel Error] {e}")

    def log(self, message: str):
        timestamped = f"{time.strftime('%H:%M:%S')} - {message}"

        def _update_log():
            if self.root:
                self.log_panel.config(state=tk.NORMAL)
                self.log_panel.insert(tk.END, f"{timestamped}\n")
                self.log_panel.yview(tk.END)
                self.log_panel.config(state=tk.DISABLED)
            self._publish_channel("log", timestamped)
            self._log_company_usage(message)

        if threading.current_thread() != threading.main_thread() and self.root:
            self.root.after(0, _update_log)
        else:
            _update_log()

    def _log_company_usage(self, message: str):
        self.company_monitor_log.append(f"{time.strftime('%Y-%m-%d %H:%M:%S')} [{self.user_tier}] {message}")
        self._publish_channel("company_log", message)

    # ======================================================
    # Start / Stop
    # ======================================================
    def start(self):
        """Initialize GUI and threads on command from DEVHUD."""
        if self.running:
            return
        self.running = True

        # GUI root
        self.root = tk.Tk()
        self.root.title(f"SEED AI - Dockable HUD [{self.user_tier}]")
        self.root.geometry(f"{self.width}x{self.height}")

        self._check_license()
        self._get_user_consent()

        # Main panes
        self.main_pane = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.main_pane.pack(fill=tk.BOTH, expand=True)

        # Render canvas
        self.render_frame = tk.Frame(self.main_pane)
        self.canvas = tk.Canvas(self.render_frame, width=int(self.width*0.7), height=self.height, bg="black")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<ButtonPress-1>", self._on_mouse_down)
        self.canvas.bind("<ButtonRelease-1>", self._on_mouse_up)
        self.canvas.bind("<B1-Motion>", self._on_mouse_drag)
        self.canvas.bind("<MouseWheel>", self._on_mouse_wheel)
        self.main_pane.add(self.render_frame, weight=3)

        # Right pane
        self.right_pane = ttk.PanedWindow(self.main_pane, orient=tk.VERTICAL)
        self.main_pane.add(self.right_pane, weight=1)

        # Web/App panel
        self.web_frame = tk.Frame(self.right_pane, bg="gray20", height=250)
        self.web_label = tk.Label(self.web_frame, text="Web/App Panel", bg="gray20", fg="white")
        self.web_label.pack(fill=tk.X)
        if HTML_AVAILABLE:
            self.html_display = HTMLLabel(self.web_frame, html="<h2>Welcome to SEED Web Panel</h2>")
            self.html_display.pack(fill=tk.BOTH, expand=True)
        else:
            tk.Button(self.web_frame, text="Open SEED Website",
                      command=lambda: webbrowser.open("https://centralconnect.io")).pack(pady=10)
        self.right_pane.add(self.web_frame, weight=1)

        # Log panel
        self.log_frame = tk.Frame(self.right_pane, height=200, bg="black")
        self.log_panel = scrolledtext.ScrolledText(self.log_frame, height=10, width=50, bg="gray10", fg="white")
        self.log_panel.pack(fill=tk.BOTH, expand=True)
        self.right_pane.add(self.log_frame, weight=1)
        self._log_company_usage("HUD started")

        # Input and user list
        self.input_frame = tk.Frame(self.right_pane, height=100)
        self.input_box = tk.Entry(self.input_frame)
        self.input_box.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.input_box.bind("<Return>", self._on_user_input)
        tk.Button(self.input_frame, text="Send", command=self._on_user_input).pack(side=tk.RIGHT)
        self.right_pane.add(self.input_frame, weight=0)

        self.user_list_frame = tk.Frame(self.right_pane, height=100)
        self.user_list_label = tk.Label(self.user_list_frame, text="Active Users", bg="gray30", fg="white")
        self.user_list_label.pack(fill=tk.X)
        self.user_listbox = tk.Listbox(self.user_list_frame)
        self.user_listbox.pack(fill=tk.BOTH, expand=True)
        self.right_pane.add(self.user_list_frame, weight=0)

        # Start threads
        self.update_thread = threading.Thread(target=self._update_loop, daemon=True)
        self.update_thread.start()
        self.remote_thread = threading.Thread(target=self._start_remote_server, daemon=True)
        self.remote_thread.start()

        # Start Tkinter main loop
        self.root.protocol("WM_DELETE_WINDOW", self.stop)
        self.root.mainloop()

    def stop(self):
        self.running = False
        self._log_company_usage("HUD stopped")
        if self.root:
            try:
                self.root.destroy()
            except:
                pass
