# ==========================================================
# FILE: utils.py
# PATH: SEED_ROOT/seed/core/utils.py
# VERSION: 0.4
# DESCRIPTION:
#   General utilities for SEED OS
#   - Device ID generation
#   - HUD display helpers
#   - Limp mode & confidence checks
#   - Build manager utilities
#   - Modem & Voice support helpers integrated with Qbit
# ==========================================================

import uuid
import os
import logging
import asyncio
from typing import Optional, Dict, Any

from seed.core.qbit_dialer import qbit_dialer

logger = logging.getLogger("SEEDUtils")
logger.setLevel(logging.INFO)

# ==========================================================
# DEVICE & SYSTEM
# ==========================================================
def generate_device_id() -> str:
    """
    Generate a unique device identifier.
    Format: SEED-<UUID8>
    """
    return f"SEED-{str(uuid.uuid4())[:8]}"


def ensure_directory(path: str):
    """Ensure a directory exists, create if missing."""
    if not os.path.exists(path):
        os.makedirs(path)
        logger.info(f"[Utils] Created missing directory: {path}")


def register_device(name: str, device: Any):
    """
    Register a device with QbitDialer for tracking.
    """
    if qbit_dialer:
        qbit_dialer.devices.register(name, device)
        logger.info(f"[Utils] Device registered with Qbit: {name}")


# ==========================================================
# LIMB MODE / RESOURCE CHECKS
# ==========================================================
def check_limp_mode(cpu_usage: float, mem_usage: float, cpu_limit: float = 80.0, mem_limit: float = 75.0) -> bool:
    """
    Check if system should enter limp mode based on resource usage.
    Returns True if limp mode should be activated.
    """
    limp = cpu_usage > cpu_limit or mem_usage > mem_limit
    if limp:
        logger.warning(f"[Utils] Limp mode triggered: CPU={cpu_usage}%, MEM={mem_usage}%")
    return limp


def check_qbit_confidence(channel: str = "QBIT") -> float:
    """
    Returns the current confidence of Qbit for a specific channel.
    """
    if qbit_dialer:
        return qbit_dialer.confidence.get(channel, 1.0)
    return 1.0


# ==========================================================
# HUD / LOGGING HELPERS
# ==========================================================
def hud_log(message: str, label: str = "INFO"):
    """
    Generic HUD / on-screen logging helper.
    Push event to Qbit buffers if available.
    """
    print(f"[HUD][{label}] {message}")
    if qbit_dialer and qbit_dialer.operational:
        qbit_dialer.buffers[label.lower()].append(1.0)


def hud_error(message: str):
    hud_log(message, label="ERROR")


def hud_warn(message: str):
    hud_log(message, label="WARN")


# ==========================================================
# BUILD MANAGER / AUTO FIX HELPERS
# ==========================================================
def build_manager_verify_files(file_list: list[str], base_path: str) -> bool:
    """
    Check that required build files exist.
    Returns True if all files exist.
    """
    missing = [f for f in file_list if not os.path.exists(os.path.join(base_path, f))]
    if missing:
        logger.warning(f"[Utils] Missing build files: {missing}")
    return not missing


def build_manager_create_placeholder(file_name: str, base_path: str, content: str = ""):
    """Create placeholder file if missing."""
    path = os.path.join(base_path, file_name)
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"[Utils] Created placeholder: {path}")


# ==========================================================
# MODEM / VOICE / NETWORK HELPERS
# ==========================================================
async def send_modem_data(modem, data: bytes, channel: Optional[str] = None):
    """
    Async helper to send data via any SEED-compliant modem.
    Push event to Qbit buffer if available.
    """
    if hasattr(modem, "send"):
        if asyncio.iscoroutinefunction(modem.send):
            result = await modem.send(data, channel)
        else:
            result = modem.send(data, channel)
        if qbit_dialer:
            qbit_dialer.buffers["modem"].append(1.0)
        return result
    raise AttributeError("[Utils] Modem missing 'send' method")


async def receive_modem_data(modem, channel: Optional[str] = None) -> bytes:
    """
    Async helper to receive data via any SEED-compliant modem.
    Push event to Qbit buffer if available.
    """
    if hasattr(modem, "receive"):
        if asyncio.iscoroutinefunction(modem.receive):
            result = await modem.receive(channel)
        else:
            result = modem.receive(channel)
        if qbit_dialer:
            qbit_dialer.buffers["modem"].append(1.0)
        return result
    raise AttributeError("[Utils] Modem missing 'receive' method")


async def record_voice_activity(level: float = 1.0):
    """
    Register voice activity to Qbit buffer.
    """
    if qbit_dialer:
        qbit_dialer.buffers["voice"].append(level)


# ==========================================================
# TRACKID HELPERS
# ==========================================================
def create_track_metadata(channel: str = "SYSTEM", parent_id: Optional[str] = None, priority: int = 5) -> Dict[str, Any]:
    """
    Generate a basic TrackID metadata dict.
    """
    track_id = f"{channel}-{str(uuid.uuid4())[:8]}"
    return {
        "track_id": track_id,
        "parent_id": parent_id,
        "priority": priority
    }
