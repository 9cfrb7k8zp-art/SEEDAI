# ==========================================================
# FILE: command_tasks.py
# PATH: SEED_ROOT/seed/core/handlers/command_tasks.py
# VERSION: 1.0.0
# ROLE: Bounded autonomous development tasks
# AUTHORITY: QbitDialer
# ==========================================================
from __future__ import annotations
import time

_RUNTIME = {}

def bind_runtime(*, hud_reader=None, ttt=None, registry=None, oracle=None):
    _RUNTIME.update({"hud_reader": hud_reader, "ttt": ttt, "registry": registry, "oracle": oracle})
    return dict(_RUNTIME)

def _data(qbit):
    return getattr(qbit, "data", {}) if qbit is not None else {}

def handle_full_system_check(qbit):
    data = _data(qbit)
    registry = _RUNTIME.get("registry")
    status = {}
    if registry is not None:
        for name in ("status", "snapshot", "get_all", "all"):
            fn = getattr(registry, name, None)
            if callable(fn):
                try:
                    value = fn()
                    status = value if isinstance(value, dict) else {"items": value}
                    break
                except Exception:
                    pass
    data.update({"handler":"FULL_SYSTEM_CHECK","checked_at":time.time(),"system_status":status})
    return qbit

def handle_idle_read(qbit):
    data = _data(qbit)
    reader = _RUNTIME.get("hud_reader")
    if reader is None:
        data.update({"handler":"IDLE_READ","status":"DEFERRED","reason":"HUDReader unavailable"})
        return qbit
    result = reader.read_text()
    data.update({"handler":"IDLE_READ","status":result.get("status"),"text":result.get("text",""),"reader_result":result})
    return qbit

def handle_sandbox_tictactoe(qbit):
    data = _data(qbit)
    game = _RUNTIME.get("ttt")
    if game is None:
        data.update({"handler":"SANDBOX_TICTACTOE","status":"DEFERRED","reason":"sandbox unavailable"})
        return qbit
    try:
        result = game.seed_win_demo()
        data.update({"handler":"SANDBOX_TICTACTOE","status":"COMPLETE","game_result":result})
    except Exception as exc:
        data.update({"handler":"SANDBOX_TICTACTOE","status":"FAILED","error":f"{type(exc).__name__}: {exc}"})
    return qbit

def get_command_task_handlers():
    return {
        "FULL_SYSTEM_CHECK": handle_full_system_check,
        "IDLE_READ": handle_idle_read,
        "SANDBOX_TICTACTOE": handle_sandbox_tictactoe,
    }
