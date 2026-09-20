# ==========================================================
# FILE: constants.py
# PATH: SEED_ROOT/seed/core/constants.py
# VERSION: 1.0 (Centralized Constants for SEED)
# UPDATED: 2026-01-04
# ==========================================================
"""
System-wide constants for SEED AI.
Central hub for event names, channel IDs, and global flags.

Purpose:
- Break circular imports between EventBus, Heartbeat, Analytics, Qbit.
- Provide a single source of truth for all constants.
- Easy to extend with new events or channels in the future.
"""

# -----------------------------
# System-wide Event Names
# -----------------------------
SYSTEM_WARNING = "SYSTEM_WARNING"
SYSTEM_SHUTDOWN = "SYSTEM_SHUTDOWN"
SYSTEM_LIMP = "SYSTEM_LIMP"
COMMAND_EXECUTED = "COMMAND_EXECUTED"
ANALYTICS_UPDATED = "ANALYTICS_UPDATED"
HEARTBEAT = "HEARTBEAT"
DEVICE_CONNECTED = "DEVICE_CONNECTED"
DEVICE_DISCONNECTED = "DEVICE_DISCONNECTED"
SKILL_LOADED = "SKILL_LOADED"
SKILL_FAILED = "SKILL_FAILED"
CUSTOM_EVENT = "CUSTOM_EVENT"
QBIT_TICK = "QBIT_TICK"
QBIT_RESULT = "QBIT_RESULT"
INTENT_UPDATED = "INTENT_UPDATED"
INTENT_STATE = "INTENT_STATE"
SKILL_COMMAND = "SKILL_COMMAND"
LIMP_MODE = "LIMP_MODE"
VECTOR_TICK = "VECTOR_TICK"
INTENT_TTL = 5.0

# -----------------------------
# Heartbeat Channels
# -----------------------------
HEART_HUD = "HEARTBEAT_HUD"
LIFE_CYCLE = "LIFE_CYCLE"
SYSTEMS = "SYSTEMS"
USER_CHANNEL = "USER"
CORE_CHANNEL = "CORE"
SYSTEM_CHANNEL = "SYSTEM"
QBIT_CHANNEL = "QBIT"
VECTOR_CHANNEL = "VECTOR"

# -----------------------------
# Channel Enum / IDs
# -----------------------------
class ChannelID:
    CORE = type("CORE", (), {"value": CORE_CHANNEL})()
    SYSTEM = type("SYSTEM", (), {"value": SYSTEM_CHANNEL})()
    USER = type("USER", (), {"value": USER_CHANNEL})()
    QBIT = type("QBIT", (), {"value": QBIT_CHANNEL})()
    VECTOR = type("VECTOR", (), {"value": VECTOR_CHANNEL})()

# -----------------------------
# Default Limits (Heartbeat / System)
# -----------------------------
DEFAULT_CPU_LIMIT = 80.0   # Percent
DEFAULT_MEM_LIMIT = 85.0   # Percent
DEFAULT_INTERVAL = 1.0     # Seconds
DEFAULT_COOLDOWN_SEC = 0.05
CACHE_EXPIRATION_SEC = 5.0

# -----------------------------
# Misc
# -----------------------------
# These can expand later with new events, flags, or identifiers
DEFAULT_MODULE_WAIT_TIMEOUT = 5.0

# ==========================================================
# END OF CONSTANTS
# ==========================================================
