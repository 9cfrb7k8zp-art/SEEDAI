# ==========================================================
# FILE: notify_operator.py
# PATH: SEED_ROOT/seed/skills/notify_operator.py
# VERSION: 3.3 (TrackID + Thought Loop + Recovery-aware + LimpMode + Build Queue)
# UPDATED: 2025-12-31
# ==========================================================

import asyncio
import logging
from seed.core.track_id_manager import TrackIDManager
from seed.core.sparkplug import TrackContext, track
from seed.skills.module_registry import ModuleRegistry

logger = logging.getLogger("NotifyOperator")

NAME = "notify_operator"
CHANNEL = "HUD_ALERTS"

THRESHOLD_INTENSITY = 200
THRESHOLD_MOTION = 50

# -----------------------------
# Resource allocation and action suggestions
# -----------------------------
def suggest_actions(intensity, motion, limp_mode=False):
    actions = []
    if limp_mode:
        intensity *= 0.5
        motion *= 0.5

    if intensity >= THRESHOLD_INTENSITY:
        actions.append({"action": "increase_lighting", "priority": 0.8, "resource": "power"})
    if motion >= THRESHOLD_MOTION:
        actions.append({"action": "focus_camera", "priority": 0.9, "resource": "camera"})
        actions.append({"action": "notify_security", "priority": 1.0, "resource": "operator"})
    return actions

# -----------------------------
# Main notify operator function
# -----------------------------
async def notify_operator(event_payload: dict, agent_manager=None, event_bus=None,
                          limp_mode=False, qbit_dialer=None, analytics_engine=None,
                          sparkplug=None, recovery_timeline=None, shutdown_flag=None):

    parent_id = TrackContext.get_current()
    track_id = TrackIDManager.generate(
        channel_marker=CHANNEL,
        skill_name=NAME,
        parent_id=parent_id,
        qbit_callback=qbit_dialer.submit_track if qbit_dialer else None
    )

    TrackContext.push(channel=CHANNEL, skill=NAME,
                      qbit_callback=qbit_dialer.submit_track if qbit_dialer else None)

    try:
        # Skip processing if system is shutting down
        if shutdown_flag and shutdown_flag.is_set():
            logger.warning(f"[{NAME}] Shutdown in progress, skipping alert. TrackID={track_id}")
            if recovery_timeline:
                recovery_timeline.record(NAME, "skipped_due_to_shutdown", reason="system_shutdown", track_id=track_id)
            return {"track_id": track_id, "status": "skipped_shutdown"}

        intensity = event_payload.get("avg_intensity", 0)
        motion = event_payload.get("motion_level", 0)
        camera_id = event_payload.get("camera_id", "CAM_UNKNOWN")

        result = {"track_id": track_id, "status": "no_alert", "actions": []}

        # Suggest actions with limp mode applied
        actions = suggest_actions(intensity, motion, limp_mode=limp_mode)

        if actions:
            if event_bus:
                event_bus.emit("HUD_ALERT", {
                    "camera_id": camera_id,
                    "intensity": intensity,
                    "motion": motion,
                    "track_id": track_id
                })

            result["actions"] = actions

            if agent_manager and sparkplug:
                for act in actions:
                    action_payload = {
                        "suggested_by": NAME,
                        "camera_id": camera_id,
                        "intensity": intensity,
                        "motion": motion,
                        "resource": act["resource"],
                        "limp_mode": limp_mode
                    }
                    # Enqueue actions for thought loop or build plan
                    sparkplug.enqueue_skill(act["action"], payload=action_payload, priority=act["priority"])

            track(CHANNEL, "ALERT_SENT",
                  note=f"Camera={camera_id} Intensity={intensity} Motion={motion} Limp={limp_mode}",
                  qbit_callback=qbit_dialer.submit_track if qbit_dialer else None)

            if recovery_timeline:
                recovery_timeline.record(NAME, "alert_sent", reason=f"Camera={camera_id}", track_id=track_id)

            logger.info(f"[HUD ALERT] TrackID={track_id} Camera={camera_id} Intensity={intensity} Motion={motion} Limp={limp_mode}")
            result["status"] = "alert_sent"

        else:
            track(CHANNEL, "NO_ALERT",
                  note=f"Camera={camera_id} Intensity={intensity} Motion={motion} Limp={limp_mode}",
                  qbit_callback=qbit_dialer.submit_track if qbit_dialer else None)

        if analytics_engine:
            analytics_engine.log_skill_event(NAME, track_id=track_id, payload=result)

        return result

    except Exception as e:
        logger.exception(f"[{NAME}] TrackID={track_id} Error: {e}")
        track(CHANNEL, "ERROR", note=str(e),
              qbit_callback=qbit_dialer.submit_track if qbit_dialer else None)
        if recovery_timeline:
            recovery_timeline.record(NAME, "error", reason=str(e), track_id=track_id)
        return {"track_id": track_id, "status": "error", "message": str(e)}

    finally:
        TrackContext.pop()


# -----------------------------
# Loader entry for SparkPlug
# -----------------------------
def run(event_payload=None, agent_manager=None, event_bus=None,
        limp_mode=False, qbit_dialer=None, analytics_engine=None,
        sparkplug=None, recovery_timeline=None, shutdown_flag=None):

    if event_payload:
        asyncio.run(notify_operator(
            event_payload,
            agent_manager=agent_manager,
            event_bus=event_bus,
            limp_mode=limp_mode,
            qbit_dialer=qbit_dialer,
            analytics_engine=analytics_engine,
            sparkplug=sparkplug,
            recovery_timeline=recovery_timeline,
            shutdown_flag=shutdown_flag
        ))
    return notify_operator
