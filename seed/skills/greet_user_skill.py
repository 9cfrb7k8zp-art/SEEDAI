# ==========================================================
# greet_user_skill.py
# Path: ./SEED_ROOT/seed/skills/greet_user_skill.py
# Skill: Greet User
# Purpose: Interact with user if detected
# ==========================================================

def run(payload=None):
    payload = payload or {}
    sensors = payload.get("payload", {})

    user_level = sensors.get("user", 0.0)
    if user_level > 0.5:
        message = "Hello, user! How are you today?"
    else:
        message = "User not detected, standing by."

    print(f"[Skill: greet_user] {message}")

    return {
        "skill": "greet_user",
        "status": "success",
        "user_level": user_level,
        "message": message
    }
