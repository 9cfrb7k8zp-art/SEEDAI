# ==========================================================
# File: 5g.py
# Path: SEED_ROOT/seed/systemutils/5g.py
# Version: 1.1
# Notes: 5G - full communications interface for SEED
#        network controller, protocol & domain control
#        Added delivery callbacks and improved thread safety
# ==========================================================

import threading
import time
from typing import List, Dict, Any, Callable, Optional
import queue
import os
import uuid
import logging

logger = logging.getLogger("SEED5G")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(name)s] %(levelname)s: %(message)s"))
    logger.addHandler(handler)

# ==========================================================
# 5G Network Controller with Callbacks
# ==========================================================
class FiveG:
    """
    5G network interface controller for SEED.
    Handles device connections, messaging, file transfers,
    protocol and domain management, async communication,
    and delivery callbacks.
    """

    def __init__(self):
        self.connected_devices: List[str] = []
        self.active_domains: Dict[str, Dict[str, Any]] = {}  # domain_name → config
        self.message_queue: queue.Queue = queue.Queue()
        self.file_queue: queue.Queue = queue.Queue()
        self.lock = threading.Lock()
        self.running = True

        # Callbacks
        self.on_message_delivered = None  # function(packet: dict)
        self.on_file_delivered = None     # function(packet: dict)

        self._start_processing_threads()

    # ======================================================
    # Device Management (unchanged)
    # ======================================================
    def connect_device(self, device_name: str):
        with self.lock:
            if device_name not in self.connected_devices:
                self.connected_devices.append(device_name)
                logger.info(f"Device connected: {device_name}")

    def disconnect_device(self, device_name: str):
        with self.lock:
            if device_name in self.connected_devices:
                self.connected_devices.remove(device_name)
                logger.info(f"Device disconnected: {device_name}")

    def list_devices(self) -> List[str]:
        with self.lock:
            return list(self.connected_devices)

    # ======================================================
    # Messaging
    # ======================================================
    def send_message(self, device_name: str, message: str, domain: str = "default"):
        if device_name not in self.connected_devices:
            logger.warning(f"Cannot send message, device {device_name} not connected")
            return
        msg_id = uuid.uuid4().hex
        packet = {
            "id": msg_id,
            "device": device_name,
            "domain": domain,
            "type": "message",
            "payload": message,
            "timestamp": time.time()
        }
        self.message_queue.put(packet)
        logger.info(f"Queued message to {device_name} | ID: {msg_id}")

    # ======================================================
    # File Transfer
    # ======================================================
    def send_file(self, device_name: str, file_path: str, domain: str = "default"):
        if device_name not in self.connected_devices:
            logger.warning(f"Cannot send file, device {device_name} not connected")
            return
        if not os.path.exists(file_path):
            logger.warning(f"File not found: {file_path}")
            return
        file_id = uuid.uuid4().hex
        packet = {
            "id": file_id,
            "device": device_name,
            "domain": domain,
            "type": "file",
            "file_path": file_path,
            "timestamp": time.time()
        }
        self.file_queue.put(packet)
        logger.info(f"Queued file transfer to {device_name} | ID: {file_id}")

    # ======================================================
    # Domain Management (unchanged)
    # ======================================================
    def add_domain(self, domain_name: str, config: Dict[str, Any]):
        with self.lock:
            self.active_domains[domain_name] = config
            logger.info(f"Domain added: {domain_name} | Config: {config}")

    def remove_domain(self, domain_name: str):
        with self.lock:
            if domain_name in self.active_domains:
                del self.active_domains[domain_name]
                logger.info(f"Domain removed: {domain_name}")

    def list_domains(self) -> List[str]:
        with self.lock:
            return list(self.active_domains.keys())

    # ======================================================
    # Internal Processing Loops
    # ======================================================
    def _start_processing_threads(self):
        threading.Thread(target=self._process_messages, daemon=True).start()
        threading.Thread(target=self._process_files, daemon=True).start()

    def _process_messages(self):
        while self.running:
            try:
                packet = self.message_queue.get(timeout=0.2)
                self._deliver_packet(packet)
                # Trigger callback
                if self.on_message_delivered:
                    try:
                        self.on_message_delivered(packet)
                    except Exception as e:
                        logger.warning(f"[5G] Message callback error: {e}")
            except queue.Empty:
                time.sleep(0.1)

    def _process_files(self):
        while self.running:
            try:
                packet = self.file_queue.get(timeout=0.2)
                self._deliver_packet(packet)
                # Trigger callback
                if self.on_file_delivered:
                    try:
                        self.on_file_delivered(packet)
                    except Exception as e:
                        logger.warning(f"[5G] File callback error: {e}")
            except queue.Empty:
                time.sleep(0.1)

    def _deliver_packet(self, packet: Dict[str, Any]):
        device = packet.get("device")
        domain = packet.get("domain")
        pkt_type = packet.get("type")
        if pkt_type == "message":
            payload = packet.get("payload")
            logger.info(f"[Deliver] Message → {device} | Domain: {domain} | Payload: {payload}")
        elif pkt_type == "file":
            file_path = packet.get("file_path")
            logger.info(f"[Deliver] File → {device} | Domain: {domain} | File: {file_path}")

    # ======================================================
    # Shutdown
    # ======================================================
    def shutdown(self):
        self.running = False
        logger.info("[5G] Controller shutdown initiated")

