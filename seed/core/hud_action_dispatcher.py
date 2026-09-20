# ==========================================================
# FILE: hud_action_dispatcher.py
# PATH: SEED_ROOT/seed/core/hud_action_dispatcher.py
# VERSION: 1.0 (MENU → ACTION BRIDGE | TRACK-SAFE)
# UPDATED: 2026-01-03
# ==========================================================

import threading
import time
from typing import Dict, Any, Optional

# -----------------------------
# Core imports (SAFE)
# -----------------------------
from seed.core.track_id import TrackRegistry, TrackIDTag
from seed.core.track_id_manager import TrackIDManager

# ==========================================================
# HUD Action Dispatcher
# ==========================================================
class HUDActionDispatcher:
    """
    Bridges HUD / Menu selections to Track actions.

    Responsibilities:
      - Validate target TrackID
      - Validate action availability
      - Execute Track-local actions
      - Report outcome

    Does NOT:
      - Create TrackIDs
      - Enforce permissions (L4)
      - Render UI
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True

        self._dispatch_lock = threading.Lock()
        self._history: list[Dict[str, Any]] = []

    # --------------------------------------------------
    # DISPATCH ENTRY
    # --------------------------------------------------
    def dispatch(
        self,
        *,
        track_id: str,
        action: str,
        payload: Optional[Any] = None,
        source: str = "HUD",
    ) -> Dict[str, Any]:
        """
        Dispatch a menu-triggered action to a Track.

        Returns a structured result for HUD/QBit/UI.
        """
        timestamp = time.time()

        track: Optional[TrackIDTag] = TrackRegistry.get(track_id)
        if not track:
            return self._record({
                "ok": False,
                "error": "TRACK_NOT_FOUND",
                "track_id": track_id,
                "action": action,
                "source": source,
                "timestamp": timestamp,
            })

        if action not in track.actions:
            return self._record({
                "ok": False,
                "error": "ACTION_NOT_REGISTERED",
                "track_id": track_id,
                "action": action,
                "available": list(track.actions.keys()),
                "source": source,
                "timestamp": timestamp,
            })

        # -----------------------------
        # EXECUTION (SAFE)
        # -----------------------------
        try:
            with self._dispatch_lock:
                result = track.execute_action(action, payload)

            response = {
                "ok": True,
                "track_id": track_id,
                "action": action,
                "result": result,
                "state": track.state,
                "source": source,
                "timestamp": timestamp,
            }

        except Exception as e:
            response = {
                "ok": False,
                "error": "ACTION_EXECUTION_FAILED",
                "exception": str(e),
                "track_id": track_id,
                "action": action,
                "source": source,
                "timestamp": timestamp,
            }

        return self._record(response)

    # --------------------------------------------------
    # HISTORY / REPORTING
    # --------------------------------------------------
    def _record(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        self._history.append(entry)
        if len(self._history) > 1000:
            self._history.pop(0)
        return entry

    def history(self, limit: int = 50) -> list[Dict[str, Any]]:
        return self._history[-limit:]

# ==========================================================
# GLOBAL ENTRY POINT
# ==========================================================
HUD_ACTIONS = HUDActionDispatcher()

# ==========================================================
# END OF FILE
# ==========================================================
