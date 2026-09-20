# FILE: local_file_reader.py
# PATH: SEED_ROOT/seed/skills/local_file_reader.py

import os
import time

def run(payload: dict) -> dict:
    path = payload.get("path")
    response = {
        "skill": "local_file_reader",
        "path": path,
        "status": "unknown",
        "timestamp": time.time(),
        "metadata": {},
        "data": {}
    }

    if not path or not os.path.exists(path):
        response["status"] = "error"
        response["error"] = "File not found"
        return response

    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read(100_000)  # max 100 KB
        response["status"] = "success"
        response["metadata"]["length"] = len(content)
        response["data"]["text"] = content
    except Exception as e:
        response["status"] = "error"
        response["error"] = str(e)

    return response
