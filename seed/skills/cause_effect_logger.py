# FILE: cause_effect_logger.py
# PATH: SEED_ROOT/seed/skills/cause_effect_logger.py

import time

def run(payload: dict) -> dict:
    if_condition = payload.get("if_condition")
    then_action = payload.get("then_action")
    context = payload.get("context", {})

    response = {
        "skill": "cause_effect_logger",
        "status": "unknown",
        "timestamp": time.time(),
        "data": {}
    }

    try:
        if callable(if_condition) and callable(then_action):
            if if_condition(context):
                then_action(context)
            response["status"] = "success"
        else:
            response["status"] = "error"
            response["error"] = "Invalid callable in payload"
    except Exception as e:
        response["status"] = "error"
        response["error"] = str(e)

    return response
