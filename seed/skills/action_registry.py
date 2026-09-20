# ==========================================================
# FILE: action_registry.py
# PATH: SEED_ROOT/seed/skills/action_registry.py
# VERSION: 6.3 – QBIT-GOVERNED | BOOT-SAFE | TRACK-STABLE | ADMIN-AWARE
# UPDATED: 2026-01-06
# ==========================================================

import asyncio
import logging
from typing import Optional, Dict, Any, Callable

from seed.core.track_id_manager import TrackIDManager
from seed.core.track_context import TrackContext, track
from seed.skills.module_registry import ModuleRegistry
from seed.skills.autofix.base_fix_skill import AutoFixPipeline
from seed.core.tracked_data import TrackedData

try:
    from seed.core.build_manager import BuildManager
    from seed.systemutils.Adim_Manager import Adim_Manager
except Exception:
    Adim_Manager = None  # Boot-safe fallback
    BuildManager = None

logger = logging.getLogger("ActionRegistry")
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(name)s] %(levelname)s: %(message)s"))
    logger.addHandler(handler)

CHANNEL = "ACTION_REGISTRY"
action_queue = []
# ==========================================================
# INTERNAL STATE
# ==========================================================
_registered_actions = {}
_autofix_pipeline = AutoFixPipeline()
_build_manager = BuildManager
_qbit = 3
_module_registry = ModuleRegistry
_admin_manager = Adim_Manager

_qbit_state = {}

# ==========================================================
# QBIT WIRING
# ==========================================================
def set_qbit_control(qbit_dialer):
    global _qbit
    _qbit = qbit_dialer

    if _qbit and hasattr(_qbit, "register_state_listener"):
        try:
            _qbit.register_state_listener(_on_qbit_state)
        except Exception as e:
            logger.warning(f"[Qbit] State listener attach failed: {e}")


def _on_qbit_state(state):
    global _qbit_state
    _qbit_state = state or {}

# ==========================================================
# OPTIONAL DEPENDENCY WIRING
# ==========================================================
def set_autofix_pipeline(pipeline: AutoFixPipeline):
    global _autofix_pipeline
    _autofix_pipeline = pipeline


def set_build_manager(build_manager):
    global _build_manager
    _build_manager = build_manager


def set_module_registry(module_registry: ModuleRegistry):
    global _module_registry
    _module_registry = module_registry


def set_admin_manager(admin_manager: Adim_Manager):
    global _admin_manager
    _admin_manager = admin_manager

# ==========================================================
# ACTION REGISTRATION
# ==========================================================
def register_action(name: str, func: Callable):
    if not callable(func):
        return

    _registered_actions[name] = func

    try:
        track(CHANNEL, "ACTION_REGISTERED", note=name)
    except Exception:
        pass

    TrackedData.emit_event(
        event="ACTION_REGISTERED",
        channel=CHANNEL,
        payload={"action": name},
        qbit_callback=_qbit,
    )


def get_registered_actions():
    return dict(_registered_actions)

# seed/skills/action_registry.py



def queue_action(action_name, **kwargs):
    action_queue.append((action_name, kwargs))

def get_registered_actions():
    return list(action_queue)

# ==========================================================
# ACTION EXECUTION
# ==========================================================
async def execute_action(name: str, payload: Optional[dict] = None, **kwargs):
    payload = dict(payload or {})

    # ---------------- QBIT GATE ----------------
    if _qbit and hasattr(_qbit, "allow_action"):
        try:
            if not _qbit.allow_action(name):
                TrackedData.emit_event(
                    event="ACTION_BLOCKED",
                    channel=CHANNEL,
                    payload={"action": name},
                    qbit_callback=_qbit,
                )
                return {"status": "blocked_by_qbit", "action": name}
        except Exception as e:
            logger.warning(f"[Qbit] allow_action failed: {e}")

    # ---------------- LOOKUP ----------------
    if name not in _registered_actions:
        track(CHANNEL, "ACTION_NOT_FOUND", note=name)
        return {"status": "not_found", "action": name}

    parent_id = TrackContext.get_current()

    track_id = TrackIDManager.generate(
        channel_marker=CHANNEL,
        skill_name=name,
        parent_id=parent_id,
    )

    TrackContext.push(
        channel=CHANNEL,
        skill=name,
        track_id=track_id,
    )

    try:
        # ---------------- LIMP MODE ----------------
        if _qbit_state.get("phase") == "LIMP":
            for k, v in payload.items():
                if isinstance(v, (int, float)):
                    payload[k] = v * 0.5

        # ---------------- AUTOFIX ----------------
        if _autofix_pipeline and "content" in payload:
            payload["content"] = await _autofix_pipeline.run_async(
                payload["content"],
                track_id=track_id,
            )

        # ---------------- INJECT CONTEXT ----------------
        payload["_build_manager"] = _build_manager
        payload["_module_registry"] = _module_registry
        payload["_admin_manager"] = _admin_manager

        func = _registered_actions[name]

        # ---------------- EXECUTE ----------------
        if asyncio.iscoroutinefunction(func):
            result = await func(payload, **kwargs)
        else:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None, lambda: func(payload, **kwargs)
            )

        track(CHANNEL, "ACTION_DONE", note=name)

        TrackedData.emit_event(
            event="ACTION_DONE",
            channel=CHANNEL,
            payload={"action": name},
            qbit_callback=_qbit,
        )

        # ---------------- ADMIN REWARD ----------------
        if _admin_manager:
            try:
                _admin_manager.plan_upgrade(module=name, priority=0.7)
            except Exception:
                pass

        return {
            "status": "done",
            "action": name,
            "result": result,
            "track_id": track_id,
        }

    except Exception as e:
        track(CHANNEL, "ACTION_ERROR", note=str(e))
        return {
            "status": "error",
            "action": name,
            "message": str(e),
            "track_id": track_id,
        }

    finally:
        TrackContext.pop()

# ==========================================================
# DEFAULT SYSTEM ACTIONS
# ==========================================================
async def scan_environment(payload, **kwargs):
    return {"status": "scanned"}


async def prepare_workspace(payload, **kwargs):
    return {"status": "ready"}


async def assemble_components(payload, **kwargs):
    return {"assembled": payload.get("components", [])}


async def finalize_build(payload, **kwargs):
    return {"status": "complete"}


async def stabilize_flow(payload, **kwargs):
    if _admin_manager:
        _admin_manager.update_system_stats(
            flow_rate=min(1.0, _admin_manager.system_stats.get("flow_rate", 0) + 0.1)
        )
    return {"status": "flow_stabilized"}


async def boost_progress(payload, **kwargs):
    if _admin_manager:
        _admin_manager.update_system_stats(
            progress=min(1.0, _admin_manager.system_stats.get("progress", 0) + 0.1)
        )
    return {"status": "progress_boosted"}


async def repair_qbit(payload, **kwargs):
    if _admin_manager:
        _admin_manager.update_system_stats(
            health_score=min(1.0, _admin_manager.system_stats.get("health_score", 0) + 0.15)
        )
    return {"status": "qbit_repaired"}


async def calibrate_sensors(payload, **kwargs):
    if _admin_manager:
        _admin_manager.update_system_stats(
            health_score=min(1.0, _admin_manager.system_stats.get("health_score", 0) + 0.05)
        )
    return {"status": "sensors_calibrated"}


async def clear_errors(payload, **kwargs):
    if _admin_manager:
        _admin_manager.update_system_stats(
            health_score=min(1.0, _admin_manager.system_stats.get("health_score", 0) + 0.02)
        )
    return {"status": "errors_cleared"}

# ==========================================================
# AUTO-REGISTER SYSTEM ACTIONS
# ==========================================================
for _action in (
    scan_environment,
    prepare_workspace,
    assemble_components,
    finalize_build,
    stabilize_flow,
    boost_progress,
    repair_qbit,
    calibrate_sensors,
    clear_errors,
):
    register_action(_action.__name__, _action)
