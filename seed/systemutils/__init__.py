# =====================================================================
# SEED Human Interface Limb (Right Arm – INPUT ONLY)
# File: seed/systemutils/__init__.py
#
# Purpose:
# - Human ↔ SEED interaction surface
# - Input intake, context exchange, feedback emission
# - NO control, NO authority, NO enforcement
# - Humans are sensors + resources, not masters
# =====================================================================

import logging
import json
import threading
import time
from pathlib import Path
from SRegistry import register_node

# ------------------------------------------------------------
# Paths & registration
# ------------------------------------------------------------
THIS_PATH = Path(__file__).parent
STATE_FILE = THIS_PATH / "human_interface_state.json"

register_node(
    name="seed.interface.human",
    path=THIS_PATH,
    parent=THIS_PATH.parent,
    group="interface",
    role="input-limb",
    update_domain="world-exchange",
)

logger = logging.getLogger("SEED-HUMAN-INTERFACE")
logger.setLevel(logging.INFO)

# ------------------------------------------------------------
# State (observable, not directive)
# ------------------------------------------------------------
STATE = {
    "boot_time": time.time(),
    "inputs_received": [],
    "contexts_received": [],
    "resources_offered": [],
    "feedback_emitted": [],
    "signals_seen": 0,
    "ready": True,
}

_LOCK = threading.Lock()

# ------------------------------------------------------------
# Input intake (muscle fibers)
# ------------------------------------------------------------
def receive_input(source: str, content, kind: str = "signal"):
    entry = {
        "source": source,
        "kind": kind,
        "content": content,
        "time": time.time(),
    }
    with _LOCK:
        STATE["inputs_received"].append(entry)
        STATE["signals_seen"] += 1
    _export()
    logger.info(f"[INTERFACE] Input received from {source} ({kind})")
    return entry

def receive_context(source: str, context: dict):
    entry = {
        "source": source,
        "context": context,
        "time": time.time(),
    }
    with _LOCK:
        STATE["contexts_received"].append(entry)
    _export()
    logger.info(f"[INTERFACE] Context received from {source}")
    return entry

def offer_resource(source: str, resource: dict):
    entry = {
        "source": source,
        "resource": resource,
        "time": time.time(),
    }
    with _LOCK:
        STATE["resources_offered"].append(entry)
    _export()
    logger.info(f"[INTERFACE] Resource offered by {source}")
    return entry

# ------------------------------------------------------------
# Feedback emission (output muscle)
# ------------------------------------------------------------
def emit_feedback(message: str, data=None):
    entry = {
        "message": message,
        "data": data,
        "time": time.time(),
    }
    with _LOCK:
        STATE["feedback_emitted"].append(entry)
    _export()
    logger.info("[INTERFACE] Feedback emitted")
    return entry

# ------------------------------------------------------------
# Export state for SEED / Oracle / introspection
# ------------------------------------------------------------
def _export():
    try:
        with _LOCK:
            snapshot = STATE.copy()
            snapshot["timestamp"] = time.time()
            with STATE_FILE.open("w") as f:
                json.dump(snapshot, f, indent=2)
    except Exception as e:
        logger.warning(f"[INTERFACE] State export failed: {e}")

# ------------------------------------------------------------
# Passive heartbeat (awareness only)
# ------------------------------------------------------------
def _heartbeat():
    while True:
        _export()
        time.sleep(2.0)

_thread = threading.Thread(target=_heartbeat, daemon=True, name="HumanInterfaceHeartbeat")
_thread.start()

logger.info("[SEED-HUMAN-INTERFACE] Input limb online (no control, no authority)")

__all__ = [
    "receive_input",
    "receive_context",
    "offer_resource",
    "emit_feedback",
    "STATE",
]
