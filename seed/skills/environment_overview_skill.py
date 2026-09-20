# ==========================================================
# FILE: environment_overview_skill.py
# PATH: ./SEED_ROOT/seed/skills/environment_overview_skill.py
# SKILL: Environment Overview
# PURPOSE: Aggregate multiple sensor readings into concise summaries
#          with entropy scoring, TrackID, Qbit push, HUD telemetry,
#          delta tracking, and rolling historical aggregation.
# VERSION: 6.0 | Async + TrackID + Qbit + Entropy + HUD + Delta + History
# ==========================================================

import asyncio
import logging
import datetime
import random
from typing import List, Dict, Any, Optional
from collections import deque

from seed.core.track_id_manager import TrackIDManager

# Optional runtime bindings — never construct runtime authorities here.
qbit_dialer = None
HudEngine = None
track_system = None
event_bus = None
oracle = None

try:
    from seed.core.qbit_dialer import QbitDialer as _QbitDialer
except ImportError:
    _QbitDialer = None

try:
    from seed.core.hud_engine import HudEngine as _HudEngine
    HudEngine = _HudEngine
except ImportError:
    pass

def bind_runtime(
    *,
    qbit_dialer=None,
    track_system=None,
    event_bus=None,
    oracle=None,
    **_kwargs,
):
    globals()["qbit_dialer"] = qbit_dialer
    globals()["track_system"] = track_system
    globals()["event_bus"] = event_bus
    globals()["oracle"] = oracle
    return True

logger = logging.getLogger("EnvOverviewSkill")
logger.setLevel(logging.INFO)


# ----------------------------------------------------------
# Skill: History & State
# ----------------------------------------------------------
HISTORY_SIZE = 50  # rolling history size
env_history: deque = deque(maxlen=HISTORY_SIZE)


# ----------------------------------------------------------
# Skill: Single Snapshot Processing with Delta
# ----------------------------------------------------------
async def process_snapshot(
    snapshot=None,
    previous_snapshot=None,
) -> Dict[str, Any]:
    snapshot = (
        snapshot
        if isinstance(snapshot, dict)
        else {}
    )
    previous_snapshot = (
        previous_snapshot
        if isinstance(previous_snapshot, dict)
        else {}
    )

    # Safe defaults
    light = float(snapshot.get("vision", 0.3))
    user = float(snapshot.get("user", 0.0))
    qbit = float(snapshot.get("qbit_motion", 0.5))
    temp = float(snapshot.get("temperature", 25.0))

    # Generate summary string
    summary = f"Light: {light:.2f}, User: {user:.2f}, Qbit: {qbit:.2f}, Temp: {temp:.1f}"

    # Delta tracking
    delta = {}
    if previous_snapshot:
        delta["vision"] = light - float(previous_snapshot.get("vision", 0.3))
        delta["user"] = user - float(previous_snapshot.get("user", 0.0))
        delta["qbit_motion"] = qbit - float(previous_snapshot.get("qbit_motion", 0.5))
        delta["temperature"] = temp - float(previous_snapshot.get("temperature", 25.0))

    # Entropy score (0.0-1.0)
    entropy = round(random.random() * 0.5 + 0.25, 4)  # 0.25 - 0.75

    # Generate TrackID
    track_id = TrackIDManager.generate(skill_name="environment_overview")

    # Update rolling history
    env_history.append({
        "vision": light,
        "user": user,
        "qbit_motion": qbit,
        "temperature": temp,
        "timestamp": datetime.datetime.now().isoformat()
    })

    # Aggregated stats
    history_stats = {
        "vision_avg": sum(h["vision"] for h in env_history) / len(env_history),
        "user_avg": sum(h["user"] for h in env_history) / len(env_history),
        "qbit_avg": sum(h["qbit_motion"] for h in env_history) / len(env_history),
        "temperature_avg": sum(h["temperature"] for h in env_history) / len(env_history),
        "history_count": len(env_history)
    }

    # Anomaly detection (basic threshold)
    anomalies = {}
    for key in ["vision", "user", "qbit_motion", "temperature"]:
        recent_val = snapshot.get(key, 0.0)
        avg_val = history_stats[f"{key}_avg"]
        if abs(recent_val - avg_val) > 0.5 * avg_val:  # threshold
            anomalies[key] = recent_val

    # HUD telemetry
    if HudEngine:
        try:
            HudEngine.publish(
                channel="ENV_OVERVIEW",
                payload={
                    "track_id": track_id,
                    "summary": summary,
                    "delta": delta,
                    "entropy": entropy,
                    "anomalies": anomalies,
                    "history_stats": history_stats,
                    "timestamp": datetime.datetime.now().isoformat()
                }
            )
        except Exception as e:
            logger.warning(f"[HUD] Failed to publish telemetry | TrackID={track_id} | Error={e}")

    # Log
    logger.info(
        f"[Skill: environment_overview | TrackID={track_id}] {summary} | "
        f"Entropy={entropy} | Delta={delta} | Anomalies={anomalies}"
    )
    print(f"[Skill: environment_overview] {summary} | Entropy={entropy} | Delta={delta} | Anomalies={anomalies}")

    # Result payload
    result = {
        "skill": "environment_overview",
        "status": "success",
        "track_id": track_id,
        "timestamp": datetime.datetime.now().isoformat(),
        "summary": summary,
        "entropy": entropy,
        "delta": delta,
        "anomalies": anomalies,
        "history_stats": history_stats,
        "payload": snapshot
    }

    # QbitDialer push
    if qbit_dialer and hasattr(qbit_dialer, "push_data"):
        try:
            push_func = qbit_dialer.push_data
            if asyncio.iscoroutinefunction(push_func):
                await push_func(result)
            else:
                push_func(result)
        except Exception as e:
            logger.error(f"[Skill: environment_overview | TrackID={track_id}] Qbit push failed: {e}")

    return result


# ----------------------------------------------------------
# Skill: Batch Snapshot Processing
# ----------------------------------------------------------
async def run(payload=None) -> List[Dict[str, Any]]:
    """
    Payload format:
    {
        "payload": [
            {
                "vision": float,
                "user": float,
                "qbit_motion": float,
                "temperature": float,
            },
            ...
        ]
    }
    """
    payload = payload or {}
    snapshots = payload.get("payload", [])

    # Wrap single snapshot into list
    if not isinstance(snapshots, list):
        snapshots = [snapshots]

    results = []
    previous_snapshot = None

    for snap in snapshots:
        result = await process_snapshot(snap, previous_snapshot)
        results.append(result)
        previous_snapshot = snap

    return results


# ----------------------------------------------------------
# Optional: Synchronous wrapper for non-async usage
# ----------------------------------------------------------
def run_sync(payload=None) -> List[Dict[str, Any]]:
    return asyncio.run(
        run(payload or {})
    )
