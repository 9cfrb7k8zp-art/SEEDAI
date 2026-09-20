# ==========================================================
# FILE: system_handlers.py
# PATH: C:\SEED_ROOT\seed\core\handlers\system_handlers.py
# VERSION: 2.0.0
# ROLE: Authoritative system Qbit handlers
# AUTHORITY: QbitDialer command registry
# PURPOSE: Handle bounded system commands without bypassing Dialer
# ==========================================================

import logging
import time

log = logging.getLogger("SEEDSystemHandlers")


def _qbit_data(qbit):
    data = getattr(qbit, "data", None)
    if isinstance(data, dict):
        return data
    if isinstance(qbit, dict):
        data = qbit.get("data")
        return data if isinstance(data, dict) else qbit
    return {}


def handle_log(qbit):
    data = _qbit_data(qbit)
    msg = data.get("message", "")
    log.info("[SYSTEM LOG] %s", msg)
    return qbit


def handle_noop(qbit):
    return qbit


def handle_status(qbit):
    data = _qbit_data(qbit)
    data.setdefault("handler", "STATUS")
    data["handler_timestamp"] = time.time()
    return qbit


def handle_observe_system(qbit):
    data = _qbit_data(qbit)
    data.setdefault("handler", "OBSERVE_SYSTEM")
    data["observed_at"] = time.time()
    return qbit


# Bound by Main3 to the authoritative identity record.
_SEED_IDENTITY = None


def bind_seed_identity(identity):
    global _SEED_IDENTITY
    _SEED_IDENTITY = identity if isinstance(identity, dict) else None
    return _SEED_IDENTITY


def handle_whoami(qbit):
    data = _qbit_data(qbit)
    identity = _SEED_IDENTITY or {}
    data["handler"] = "WHOAMI"
    data["identity"] = {
        "seed_id": identity.get("seed_id", "UNKNOWN"),
        "owner": identity.get("owner", "UNKNOWN"),
        "version": identity.get("metadata", {}).get("version"),
        "build": identity.get("metadata", {}).get("build"),
        "platform": identity.get("metadata", {}).get("platform"),
    }
    data["qbit_id"] = getattr(qbit, "qbit_id", None)
    data["track_id"] = getattr(qbit, "track_id", None)
    data["responded_at"] = time.time()
    return qbit


SYSTEM_HANDLERS = {
    "LOG": handle_log,
    "NOOP": handle_noop,
    "STATUS": handle_status,
    "OBSERVE_SYSTEM": handle_observe_system,
    "WHOAMI": handle_whoami,
}


def get_system_handlers():
    return dict(SYSTEM_HANDLERS)
