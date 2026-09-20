# ==========================================================
# FILE: fat_layer.py
# PATH: SEED_ROOT/seed/core/fat_layer.py
# PURPOSE:
#   FAT = Frame / Activity / Trace Layer
#   Central time-ordered buffer for all system signals.
#
# ROLE IN THINKING LOOP:
#   - Memory substrate
#   - Traceability for reasoning
#   - Replay + audit of thought evolution
#
# NEW (v2.1):
#   - Thought-loop frame support
#   - Analytic state vector trace compatibility
#   - Explicit labels for cognition stages
#
# EDIT GUIDE (IMPORTANT):
#   - Frame indexing logic        → see _next_frame_index()
#   - Waveform / FFT processing   → see _process_signal()
#   - Async buffering rules       → see append()
#   - Legacy sync entry point     → see append_log()
# ==========================================================

import os
import asyncio
import json
import logging
import time
from typing import Any, Dict, List
import threading
import numpy as np  # REQUIRED for waveform / FFT

logger = logging.getLogger("FATLayer")
logger.setLevel(logging.INFO)


class FATLayer:

    def __init__(self, storage_root="./SEED_ROOT/fat", max_buffer=10000, max_file_size=1024*1024*5):
        self.storage_root = storage_root
        self.max_buffer = max_buffer
        self.max_file_size = max_file_size  # 5MB default
        self.lock = threading.Lock()
        os.makedirs(self.storage_root, exist_ok=True)

        self._buffer: List[Dict[str, Any]] = []
        self._lock = asyncio.Lock()
        self._frame_counter = 0

        # File index: device_id → list of segment files
        self.index_file = os.path.join(self.storage_root, "index.json")
        if os.path.exists(self.index_file):
            with open(self.index_file, "r") as f:
                self.index = json.load(f)
        else:
            self.index = {}

        logger.info("[FATLayer] Initialized")

    # --------------------------------------------------
    # Frame index (SINGLE SOURCE OF TRUTH)
    # --------------------------------------------------
    def _next_frame_index(self) -> int:
        idx = self._frame_counter
        self._frame_counter += 1
        return idx

    # --------------------------------------------------
    # Signal processing (WAVEFORM / FFT)
    # --------------------------------------------------
    def _process_signal(self, data: Any) -> Dict[str, Any]:
        waveform = np.array(data, dtype=float)
        fft = np.abs(np.fft.fft(waveform))

        if fft.max() != 0:
            fft = fft / fft.max()

        return {
            "waveform": waveform.tolist(),
            "fft": fft.tolist(),
        }

    # --------------------------------------------------
    # Core async append (SAFE)
    # --------------------------------------------------
    async def append(self, entry: Dict[str, Any]):
        async with self._lock:
            if len(self._buffer) >= self.max_buffer:
                self._buffer.pop(0)
            self._buffer.append(entry)

    # ======================================================
    # APPEND LOG (fix for AudioModem)
    # ======================================================
    # --------------------------------------------------
    # Legacy + primary entry point (SYNC SAFE)
    # --------------------------------------------------
    def append_log(self, device_id, record, data: Any, source="unknown", label=None):
        self.write_record(device_id, record)
        entry: Dict[str, Any] = {
            "frame_index": self._next_frame_index(),
            "timestamp": time.time(),
            "source": source,
            "label": label,
            "meta": {
                "type": type(data).__name__,
                "origin": "append_log",
            },
            "data": data,
        }

        # ------------------------------
        # Signal detection (FFT path)
        # ------------------------------
        try:
            if isinstance(data, (list, np.ndarray)):
                entry["data"] = self._process_signal(data)
                entry["meta"]["signal"] = True
            else:
                entry["meta"]["signal"] = False
        except Exception as e:
            entry["meta"]["signal_error"] = str(e)

        # ------------------------------
        # Async-safe enqueue
        # ------------------------------
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self.append(entry))
            else:
                asyncio.run(self.append(entry))
        except Exception as e:
            logger.debug(f"[FATLayer] append_log suppressed error: {e}")

        return entry

    # ==================================================
    # NEW: Thought / Analytics Logging Helpers
    # ==================================================

    def log_thought_input(self, thought_payload: Dict[str, Any]):
        self.append_log(
            thought_payload,
            source="analytics",
            label="thought"
        )

    def log_state_vector(self, vector_payload: Dict[str, Any]):
        self.append_log(
            vector_payload,
            source="analytics",
            label="state_vector"
        )

    # --------------------------------------------------
    # Frame helpers (existing, unchanged behavior)
    # --------------------------------------------------
    def log_audio_frame(self, frame: Dict[str, Any]):
        self.append_log(frame, source="audio", label="frame")

    def log_qbit_frame(self, frame: Dict[str, Any]):
        self.append_log(frame, source="qbit", label="frame")

    def log_modem_packet(self, packet: Any):
        self.append_log(packet, source="modem", label="packet")

    def log_event(self, event: Any):
        self.append_log(event, source="event")

    # --------------------------------------------------
    # Retrieval
    # --------------------------------------------------
    def snapshot(self) -> List[Dict[str, Any]]:
        return list(self._buffer)

    def clear(self):
        self._buffer.clear()
        logger.info("[FATLayer] Buffer cleared")


    # ======================================================
    # WRITE RECORD
    # ======================================================
    def write_record(self, device_id, record):
        with self.lock:
            files = self.index.get(device_id, [])
            if files:
                latest_file = files[-1]
            else:
                latest_file = self._new_segment_file(device_id)
                files.append(latest_file)
                self.index[device_id] = files

            file_path = os.path.join(self.storage_root, latest_file)
            if os.path.exists(file_path) and os.path.getsize(file_path) >= self.max_file_size:
                latest_file = self._new_segment_file(device_id)
                files.append(latest_file)
                self.index[device_id] = files
                file_path = os.path.join(self.storage_root, latest_file)

            with open(file_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
            self._save_index()

    # ======================================================
    # READ RECORDS
    # ======================================================
    def read_records(self, device_id):
        with self.lock:
            records = []
            files = self.index.get(device_id, [])
            for file_name in files:
                file_path = os.path.join(self.storage_root, file_name)
                if os.path.exists(file_path):
                    with open(file_path, "r", encoding="utf-8") as f:
                        for line in f:
                            try:
                                rec = json.loads(line.strip())
                                records.append(rec)
                            except Exception:
                                continue
            return records

    # ======================================================
    # CREATE NEW SEGMENT FILE
    # ======================================================
    def _new_segment_file(self, device_id):
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"{device_id}_{ts}.seg"
        return file_name

    # ======================================================
    # SAVE INDEX
    # ======================================================
    def _save_index(self):
        with open(self.index_file, "w", encoding="utf-8") as f:
            json.dump(self.index, f, indent=2)

    # ======================================================
    # DELETE DEVICE DATA
    # ======================================================
    def delete_device(self, device_id):
        with self.lock:
            files = self.index.get(device_id, [])
            for f_name in files:
                f_path = os.path.join(self.storage_root, f_name)
                if os.path.exists(f_path):
                    os.remove(f_path)
            if device_id in self.index:
                del self.index[device_id]
            self._save_index()
            logger.info(f"Deleted all data for {device_id}")

