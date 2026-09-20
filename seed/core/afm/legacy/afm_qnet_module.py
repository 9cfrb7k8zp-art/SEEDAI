# AFM_QNet_Module.py

import os
import sys
import json
import time
import socket
import shutil
import psutil
import logging
import zipfile
import platform
import threading
from pathlib import Path
from datetime import datetime
from uuid import uuid4

# === CONFIG ===
BASE_DIR = Path("C:/AFM")
SCRIPT_DIR = BASE_DIR / "scripts"
TEMP_DIR = BASE_DIR / "temp"
LOGS_DIR = BASE_DIR / "logs"
RETRIES_TRACKER = BASE_DIR / "retry_tracker.json"
STRUCTURE_GUIDE = BASE_DIR / "structure_map.json"

RETRY_LIMITS = {"minor": 15, "medium": 10, "critical": 5}


class AFMQNetModule:
    def __init__(self):
        self.modules = []
        self.network = NetworkIntegration()
        self.self_heal = SelfHealingSystem()
        self.qdm_logic = QuantumDecisionMaking()
        self.logs = []

    def start(self):
        print("AFMQNet: Initializing system...")

    def stop(self):
        print("AFMQNet: System Stopped...")


# === LOGGER SETUP ===
logging.basicConfig(
    filename=LOGS_DIR / "afm_qnet.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
)


def log(message):
    logging.info(message)
    print(f"[AFM_QNET] {message}")


# === ERROR TRACKER ===
def load_tracker():
    if RETRIES_TRACKER.exists():
        with open(RETRIES_TRACKER, "r") as f:
            return json.load(f)
    return {}


def save_tracker(data):
    with open(RETRIES_TRACKER, "w") as f:
        json.dump(data, f)


def track_retry(task_name, level):
    tracker = load_tracker()
    task = tracker.get(task_name, {"level": level, "attempts": 0})
    task["attempts"] += 1
    tracker[task_name] = task
    save_tracker(tracker)
    return task["attempts"] <= RETRY_LIMITS.get(level, 5)


# === JSON STRUCTURE READ ===
def read_structure_guide():
    if STRUCTURE_GUIDE.exists():
        try:
            with open(STRUCTURE_GUIDE, "r") as f:
                return json.load(f)
        except Exception as e:
            log(f"Failed to read structure guide: {e}")
    return {}


# === NETWORK DISCOVERY & QNET ===
def detect_io_signals():
    signals = []
    try:
        if platform.system() == "Windows":
            import win32com.client

            wmi = win32com.client.GetObject("winmgmts:")
            for usb in wmi.InstancesOf("Win32_USBHub"):
                signals.append(usb.DeviceID)
        # Dummy Bluetooth & WiFi adapter placeholder
        signals.extend([i.address for i in psutil.net_if_addrs().values() if i])
    except Exception as e:
        log(f"[medium] IO signal scan failed: {e}")
    return signals


def establish_ghost_network():
    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        log(f"Ghost network init from {hostname} @ {ip}")
    except Exception as e:
        log(f"[critical] Ghost net failure: {e}")
        if not track_retry("ghost_net", "critical"):
            return
        time.sleep(5)
        establish_ghost_network()


# === ZIP ANALYSIS ===
def extract_and_scan():
    for zip_path in TEMP_DIR.rglob("*.zip"):
        try:
            dest = TEMP_DIR / f"extracted_{uuid4().hex[:6]}"
            shutil.unpack_archive(str(zip_path), str(dest))
            log(f"Extracted: {zip_path.name} to {dest}")
        except zipfile.BadZipFile:
            log(f"[minor] Bad zip: {zip_path.name}")
        except Exception as e:
            log(f"[medium] Extraction error for {zip_path.name}: {e}")


# === GUI FEED ===
def send_to_gui(status_message):
    try:
        status_path = BASE_DIR / "gui_feed.json"
        with open(status_path, "w") as f:
            json.dump(
                {"status": status_message, "timestamp": datetime.now().isoformat()}, f
            )
        log("GUI status updated.")
    except Exception as e:
        log(f"[minor] GUI feed failure: {e}")


# === MAIN PROCESS ===
def afm_qnet_main():
    send_to_gui("AFM_QNET initializing...")
    extract_and_scan()
    signals = detect_io_signals()
    send_to_gui(f"Detected IO devices: {len(signals)}")
    establish_ghost_network()
    structure = read_structure_guide()
    log(f"Loaded structure blueprint with {len(structure)} keys.")
    send_to_gui("AFM_QNET active and monitoring...")


# === LOOP ===
if __name__ == "__main__":
    while True:
        try:
            afm_qnet_main()
        except Exception as e:
            log(f"[critical] System crash in AFM_QNET: {e}")
        time.sleep(90)


def run():
    print("🛠️ Auto-generated run() for module: afm_qnet_module.py")
