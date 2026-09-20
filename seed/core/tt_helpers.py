# ==========================================================
# FILE: tt_helpers.py
# PATH: SEED_ROOT/seed/core/tt_helpers.py
# VERSION: 5.2.2a (Bootable / Self-Healing / AI-Safe)
# ==========================================================


import threading
import asyncio
import logging
import time
import uuid
import sys
from collections import defaultdict, deque
from enum import Enum
from typing import Callable


import logging

log = logging.getLogger("TT.Helpers")


def send_qbit_command(
    tt_engine,
    event_bus,
    cmd,
    command_obj,
    payload,
    event_name,
):
    """
    Unified helper for dispatching QBIT-related commands
    while recording them into the TimeTravelEngine.
    """

    # --------------------------------------------------
    # Canonical normalization (NO FREE SYMBOLS)
    # --------------------------------------------------
    command = cmd
    action = cmd

    # --------------------------------------------------
    # Record into TimeTravelEngine
    # --------------------------------------------------
    try:
        if tt_engine:
            tt_engine.record_command(
                command_obj=command_obj,
                event_name=event_name,
                payload=payload,
            )
    except Exception as e:
        log.warning(f"[TT] Failed to record command: {e}")

    # --------------------------------------------------
    # Publish onto EventBus
    # --------------------------------------------------
    try:
        if event_bus:
            event_bus.publish(
                event_name,
                {
                    "command": command,
                    "action": action,
                    "command_obj": command_obj,
                    "payload": payload,
                },
            )
    except Exception as e:
        log.warning(f"[TT] Failed to publish command: {e}")
