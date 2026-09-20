# ==========================================================
# FILE: qbit_layer.py
# PATH: SEED_ROOT/seed/core/qbit_layer.py
# SEED QBIT LAYER
# Handles multiverse / Qbit communication
# Integrates with Modem and FAT layers
# ==========================================================

import threading
import time
import random
import logging
from seed.core.modem_layer import ModemLayer
from seed.core.fat_layer import FATLayer

logger = logging.getLogger("SEEDQBIT")

class QbitLayer:
    """
    Qbit / Multiverse communication layer
    - Encodes "Qbit states"
    - Sends via ModemLayer
    - Receives and decodes signals
    - Logs everything via FAT
    - Provides plug read/write interface for QbitAggregator
    """

    def __init__(self, modem: ModemLayer, storage_root="./SEED_ROOT/fat"):
        self.modem = modem
        self.fat = FATLayer(storage_root)
        self.incoming_states = {}  # device_id -> list of state dicts
        self.lock = threading.Lock()
        self.outgoing_queue = []  # For aggregator writes

        # Start listener loop
        threading.Thread(target=self._listen_loop, daemon=True).start()

    # ======================================================
    # ENCODE / DECODE QBIT STATES
    # ======================================================
    @staticmethod
    def encode_qbit_state(state_dict):
        import json, base64
        json_str = json.dumps(state_dict)
        encoded = base64.b64encode(json_str.encode("utf-8")).decode("utf-8")
        return encoded

    @staticmethod
    def decode_qbit_state(packet):
        import json, base64
        try:
            json_str = base64.b64decode(packet.encode("utf-8")).decode("utf-8")
            return json.loads(json_str)
        except Exception:
            return None

    # ======================================================
    # SEND QBIT STATE
    # ======================================================
    def send_state(self, device_id, state_dict):
        """
        Send a Qbit state to a device via the modem
        """
        encoded = self.encode_qbit_state(state_dict)
        self.modem.send(device_id, {"qbit": encoded})
        # Log to FAT
        self.fat.write_record(device_id, {
            "direction": "TX_QBIT",
            "payload": state_dict,
            "timestamp": time.time()
        })
        logger.info(f"[QBIT] Sent Qbit state to {device_id}: {state_dict}")

    # ======================================================
    # PLUG INTERFACE
    # ======================================================
    def write(self, channel, value):
        """
        Write a new value from QbitAggregator.
        Aggregator -> QbitLayer
        """
        state_dict = {"channel": channel, "value": value, "timestamp": time.time()}
        self.outgoing_queue.append(state_dict)
        # Broadcast to all known devices
        for device_id in getattr(self.modem, "known_devices", []):
            self.send_state(device_id, state_dict)

    def read(self):
        """
        Read the latest values received.
        QbitLayer -> QbitAggregator
        Returns a dict: {device_id: latest_state}
        """
        latest = {}
        with self.lock:
            for device_id, states in self.incoming_states.items():
                if states:
                    latest[device_id] = states[-1]
        return latest

    # ======================================================
    # RECEIVE LOOP
    # ======================================================
    def _listen_loop(self):
        """
        Poll the modem for incoming Qbit packets
        """
        while True:
            with self.modem.lock:
                for i, (device_id, packet) in enumerate(list(self.modem.incoming_queue)):
                    decoded = self.modem.decode(packet)
                    if decoded and "qbit" in decoded:
                        qbit_state = self.decode_qbit_state(decoded["qbit"])
                        if qbit_state:
                            self._store_incoming(device_id, qbit_state)
                            # Log to FAT
                            self.fat.write_record(device_id, {
                                "direction": "RX_QBIT",
                                "payload": qbit_state,
                                "timestamp": time.time()
                            })
                        # Remove processed packet
                        self.modem.incoming_queue.pop(i)
            time.sleep(0.02)

    # ======================================================
    # STORE INCOMING STATES
    # ======================================================
    def _store_incoming(self, device_id, state_dict):
        """
        Store received Qbit states
        """
        with self.lock:
            if device_id not in self.incoming_states:
                self.incoming_states[device_id] = []
            self.incoming_states[device_id].append({
                "state": state_dict,
                "timestamp": time.time()
            })
        logger.info(f"[QBIT] Received Qbit state from {device_id}: {state_dict}")

    # ======================================================
    # GET LATEST STATE
    # ======================================================
    def get_latest_state(self, device_id):
        """
        Returns the most recent Qbit state for a device
        """
        with self.lock:
            if device_id in self.incoming_states and self.incoming_states[device_id]:
                return self.incoming_states[device_id][-1]
        return None
