# ==========================================================
# FILE: bios_control_handoff.py
# PATH: SEED_ROOT/seed/core/bios/bios_control_handoff.py
# PURPOSE: Control handoff to Heartbeat + Qbit + Reasoning
# NOTES:
# - Thread-safe
# - Supports first-boot system initialization
# - Emits TrackID events via Qbit
# ==========================================================

import logging
import threading
import time

logger = logging.getLogger("BIOS.ControlHandoff")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter("[%(name)s] %(levelname)s: %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

class BIOSControlHandoff:
    def __init__(self, heartbeat=None, qbit_dialer=None, reasoning_loop=None):
        self.heartbeat = heartbeat
        self.qbit = qbit_dialer
        self.reasoning = reasoning_loop
        self.active = False
        self._lock = threading.Lock()

    def start(self):
        with self._lock:
            if self.active:
                logger.warning("[BIOS] Control handoff already active")
                return

            logger.info("[BIOS] Control handoff initiated")
            self.active = True

            # 1️⃣ Heartbeat becomes master clock
            if self.heartbeat:
                try:
                    self.heartbeat.start()
                    logger.info("[BIOS] Heartbeat online")
                except Exception as e:
                    logger.error(f"[BIOS] Heartbeat failed to start: {e}")

            # 2️⃣ Qbit becomes signal bus
            if self.qbit:
                try:
                    track_id = getattr(self.qbit, "generate_track_id", lambda *a, **k: None)()
                    self.qbit.emit(event="SYSTEM_ONLINE", source="BIOS", track_id=track_id)
                    logger.info("[BIOS] Qbit dialer active")
                except Exception as e:
                    logger.error(f"[BIOS] Qbit emit failed: {e}")

            # 3️⃣ Reasoning loop is allowed to think
            if self.reasoning:
                try:
                    threading.Thread(
                        target=self.reasoning.run,
                        daemon=True
                    ).start()
                    logger.info("[BIOS] Reasoning loop granted control")
                except Exception as e:
                    logger.error(f"[BIOS] Reasoning loop failed to start: {e}")

    def stop(self):
        with self._lock:
            if not self.active:
                logger.warning("[BIOS] Control handoff already stopped")
                return
            self.active = False
            # Optionally stop heartbeat/reasoning if they support stop
            if self.heartbeat and hasattr(self.heartbeat, "stop"):
                try:
                    self.heartbeat.stop()
                    logger.info("[BIOS] Heartbeat stopped")
                except Exception as e:
                    logger.error(f"[BIOS] Heartbeat failed to stop: {e}")
            if self.reasoning and hasattr(self.reasoning, "stop"):
                try:
                    self.reasoning.stop()
                    logger.info("[BIOS] Reasoning loop stopped")
                except Exception as e:
                    logger.error(f"[BIOS] Reasoning loop failed to stop: {e}")

            logger.warning("[BIOS] Control revoked")
