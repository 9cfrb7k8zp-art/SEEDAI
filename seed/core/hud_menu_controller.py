# ==========================================================
# FILE: hud_menu_controller.py
# PATH: SEED_ROOT/seed/core/hud_menu_controller.py
# VERSION: 1.0 (MAIN MENU | TRACK-AWARE | LIFECYCLE-GROWTH)
# UPDATED: 2026-01-03
# ==========================================================

import time
import threading
from typing import Dict, Any, List

# -----------------------------
# Core Imports (Safe)
# -----------------------------
from seed.core.track_id_manager import TrackIDManager
from seed.core.track_id import TrackRegistry
from seed.core.channel_id import ChannelID

# ==========================================================
# HUD Menu Controller — Main Menu Authority
# ==========================================================
class HUDMenuController:
    """
    Authoritative HUD / Main Menu controller.

    Responsibilities:
      - Build dynamic menu state
      - Reflect live Track + Channel activity
      - Grow menu complexity over system lifetime
      - Refresh on timed awake cycles

    Does NOT:
      - Render UI
      - Execute commands
    """

    _instance = None
    _lock = threading.Lock()

    REFRESH_INTERVAL = 300  # 5 minutes (awake cycle)

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return

        self._initialized = True

        self._start_time = time.time()
        self._last_refresh = 0.0

        self._menu_state: Dict[str, Any] = {}
        self._menu_lock = threading.Lock()

        self._running = True
        self._thread = threading.Thread(
            target=self._lifecycle_loop,
            daemon=True,
        )
        self._thread.start()

    # --------------------------------------------------
    # LIFECYCLE LOOP
    # --------------------------------------------------
    def _lifecycle_loop(self):
        while self._running:
            now = time.time()
            if now - self._last_refresh >= self.REFRESH_INTERVAL:
                self.refresh_menu()
                self._last_refresh = now
            time.sleep(1)

    # --------------------------------------------------
    # MENU BUILD LOGIC
    # --------------------------------------------------
    def refresh_menu(self):
        """
        Rebuild menu snapshot from live system state.
        """
        manager = TrackIDManager()
        uptime = int(time.time() - self._start_time)

        # Lifecycle growth tiers
        tier = self._determine_tier(uptime)

        menu = {
            "meta": {
                "uptime_seconds": uptime,
                "lifecycle_tier": tier,
                "active_tracks": TrackRegistry.count(),
                "channels": ChannelID.snapshot(),
                "timestamp": time.time(),
            },
            "domains": {},
            "priority_queues": {},
        }

        # -----------------------------
        # DOMAIN / HUD VIEW
        # -----------------------------
        for track_id, track in TrackRegistry.all().items():
            domain = track.domain
            hud = manager.hud_of(track_id)

            menu["domains"].setdefault(domain, {
                "hud": hud,
                "tracks": [],
            })

            menu["domains"][domain]["tracks"].append({
                "track_id": track_id,
                "channel": track.channel,
                "skill": track.skill,
                "priority": track.priority,
                "parent": track.parent_id,
            })

        # -----------------------------
        # PRIORITY QUEUES (VISIBLE AT TIER ≥ 2)
        # -----------------------------
        if tier >= 2:
            for level in sorted(manager._priority_queue.keys()):
                menu["priority_queues"][level] = list(
                    manager._priority_queue[level]
                )

        # -----------------------------
        # ADVANCED DIAGNOSTICS (TIER ≥ 3)
        # -----------------------------
        if tier >= 3:
            menu["diagnostics"] = {
                "seen_track_ids": len(manager._seen_ids),
                "build_queue_depth": len(manager._build_queue),
            }

        with self._menu_lock:
            self._menu_state = menu

    # --------------------------------------------------
    # LIFECYCLE GROWTH
    # --------------------------------------------------
    def _determine_tier(self, uptime: int) -> int:
        """
        Determines menu complexity level based on system life.
        """
        if uptime < 600:
            return 1  # Basic
        elif uptime < 3600:
            return 2  # Expanded
        else:
            return 3  # Full / Diagnostic

    # --------------------------------------------------
    # PUBLIC API
    # --------------------------------------------------
    def get_menu_state(self) -> Dict[str, Any]:
        with self._menu_lock:
            return dict(self._menu_state)

    def shutdown(self):
        self._running = False

# ==========================================================
# GLOBAL ENTRY POINT
# ==========================================================
HUD_MENU = HUDMenuController()

# ==========================================================
# END OF FILE
# ==========================================================
