# ==========================================================
# temperature_check_skill.py
# Path: ./SEED_ROOT/seed/skills/temperature_check_skill.py
# Skill: Temperature Check
# Purpose: Monitor temperature and report status
# ==========================================================

def run(payload=None):
    payload = payload or {}
    sensors = payload.get("payload", {})

    temp = sensors.get("temperature", 0)
    if temp > 75:
        status = "Warning: High temperature!"
    elif temp > 45:
        status = "Temperature above normal"
    else:
        status = "Temperature normal"

    print(f"[Skill: temperature_check] {status}")

    return {
        "skill": "temperature_check",
        "status": "success",
        "temperature": temp,
        "message": status
    }
