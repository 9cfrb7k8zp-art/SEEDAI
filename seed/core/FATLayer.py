# ==========================================================
# SEED FAT LAYER
# Manages storage & retrieval of device/sensor/Qbit data
# Implements a simplified File Allocation Table (FAT)
# ==========================================================

import os
import json
import threading
import datetime
import logging

logger = logging.getLogger("SEEDFAT")


class FATLayer:

    def __init__(self, storage_root="./SEED_ROOT/fat", max_file_size=1024*1024*5):
        self.storage_root = storage_root
        self.max_file_size = max_file_size  # 5MB default
        self.lock = threading.Lock()
        os.makedirs(self.storage_root, exist_ok=True)

        # File index: device_id → list of segment files
        self.index_file = os.path.join(self.storage_root, "index.json")
        if os.path.exists(self.index_file):
            with open(self.index_file, "r") as f:
                self.index = json.load(f)
        else:
            self.index = {}

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
    # APPEND LOG (fix for AudioModem)
    # ======================================================
    def append_log(self, device_id, record):
        self.write_record(device_id, record)

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
