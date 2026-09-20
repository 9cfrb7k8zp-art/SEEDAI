# ======================================================================
# FILE: network_fetcher.py
# PATH: SEED_ROOT/seed/skills/network_fetcher.py
#
#
# SEED SKILL: Network Fetcher
# VERSION: 0.1.0
# TYPE: External Knowledge Skill
#
# RESPONSIBILITY:
# - Fetch public web resources
# - Return clean, structured content
# - Respect size & safety limits
#
# LABELS:
# - NETWORK_SKILL
# - EXTERNAL_KNOWLEDGE 
# - CAUSE_EFFECT
# =============================================================================

import time
import requests

MAX_BYTES = 500_000  # 500 KB safety cap
TIMEOUT = 10         # seconds

event_bus = None
track_system = None
oracle = None

def bind_runtime(
    *,
    event_bus=None,
    track_system=None,
    oracle=None,
    **_kwargs,
):
    globals()["event_bus"] = event_bus
    globals()["track_system"] = track_system
    globals()["oracle"] = oracle
    return True


def run(payload: dict) -> dict:
    url = payload.get("url")
    method = payload.get("method", "GET").upper()

    response = {
        "skill": "network_fetcher",
        "url": url,
        "status": "unknown",
        "timestamp": time.time(),
        "metadata": {},
        "data": {}
    }

    if not url:
        response["status"] = "error"
        response["error"] = "No URL provided"
        return response

    try:
        r = requests.request(method=method, url=url, headers=payload.get("headers", {}), timeout=TIMEOUT, stream=True)
        content = r.content[:MAX_BYTES]

        response["status"] = "success"
        response["metadata"] = {
            "http_status": r.status_code,
            "content_type": r.headers.get("Content-Type", ""),
            "content_length": len(content)
        }

        if "text" in r.headers.get("Content-Type", ""):
            response["data"]["text"] = content.decode(errors="ignore")[:5000]
        else:
            response["data"]["note"] = "Non-text content received"

    except requests.exceptions.RequestException as e:
        response["status"] = "network_error"
        response["error"] = str(e)
    except Exception as e:
        response["status"] = "error"
        response["error"] = str(e)

    return response


