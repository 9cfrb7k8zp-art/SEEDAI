# ==========================================================
# qbit_monitor_skill.py
# Path: ./SEED_ROOT/seed/skills/qbit_monitor_skill.py
# Skill: Qbit Monitor
# Purpose: Simulate monitoring Qbit motion/resonance
# ==========================================================

def run(payload=None):
    payload = payload or {}
    sensors = payload.get("payload", {})

    qbit_motion = sensors.get("qbit_motion", 0.5)
    resonance = sensors.get("resonance", 0.5)

    # Example thresholds
    if qbit_motion > 0.7:
        status = "High Qbit activity detected"
    else:
        status = "Normal Qbit activity"

    print(f"[Skill: qbit_monitor] {status}")

    return {
        "skill": "qbit_monitor",
        "status": "success",
        "qbit_motion": qbit_motion,
        "resonance": resonance,
        "message": status
    }
