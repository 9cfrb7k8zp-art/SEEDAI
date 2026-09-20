# ==========================================================
# FILE: audio_modem_manager.py
# PATH: SEED_ROOT/seed/core/audio_modem_manager.py
# MODULE: Audio Modem Manager v2.8 (DYNAMIC MODEM | CONTRACT-SAFE | TRACK-AWARE)
# ==========================================================

import asyncio
import logging
import threading
import uuid
from typing import Callable, Dict, Any

from seed.core.modem import SEEDModem
from seed.core.modem_controller import ModemController
from seed.core.track_id_manager import TrackIDManager
from seed.core.track_context import TrackContext

logger = logging.getLogger("AudioModemManager")
logger.setLevel(logging.INFO)

# ==========================================================
# TRACK ID HELPER
# ==========================================================
def gen_track_id(prefix="AUDIO", parent_id=None, origin="System") -> Dict[str, str]:
    if parent_id is None:
        parent_id = TrackContext.get()
    return {
        "track_id": f"{prefix}-{str(uuid.uuid4())[:8]}",
        "parent_id": parent_id,
        "origin": origin
    }

# ==========================================================
# BOOT-SAFE STUBS
# ==========================================================
class TrackStub:
    def __call__(self, *args, **kwargs):
        return {}
    def subscribe(self, *args, **kwargs):
        pass

class EmitStub:
    def __call__(self, event_type, payload=None):
        return True
    def subscribe(self, *args, **kwargs):
        pass
    def publish(self, event_type, payload=None):
        return True

class AudioStub:
    def register_qbit_callback(self, callback):
        # Accept callback but do nothing (boot-safe)
        return True

# In AudioModemManager.__init__():
#self.audio = getattr(self, "audio", None) or AudioStub()

# Ensure push_data exists (stub if missing)
#self.push_data = getattr(self, "push_data", lambda data: True)

# Register safely
#self.audio.register_qbit_callback(self.push_data)

# ==========================================================
# AUDIO MODEM MANAGER
# ==========================================================
class AudioModemManager:

    def __init__(self, storage_root="./SEED_ROOT", fat_layer=None, qbit_dialer=None, event_bus=None, **kwargs):
        self.storage_root = storage_root
        self.fat_layer = fat_layer
        self.qbit_dialer = qbit_dialer
        self.event_bus = event_bus or EmitStub()
        self.audio_processor = SEEDModem(name="audio_processor")

        self.modems = {}
        self._qbit_callbacks = []
        self._running = False
        self._tasks = []
        self._lock = threading.Lock()

        # Boot-safe loop
        try:
            self.loop = asyncio.get_running_loop()
        except RuntimeError:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

        # Boot-safe audio stub
        self.audio = AudioStub()

        # Boot-safe push_data registration
        self.push_data = getattr(self, "push_data", None)
        self.audio.register_qbit_callback(self.push_data or (lambda data: True))

        logger.info("[AudioModemManager] Initialized")

    # ======================================================
    # MODEM REGISTRATION (DYNAMIC)
    # ======================================================
    def register_modem(self, name: str, modem: Any):
        with self._lock:
            if name in self.modems:
                raise KeyError(f"Modem '{name}' already registered")
            # Contract enforcement
            for attr in ("start", "stop", "send"):
                if not hasattr(modem, attr):
                    raise TypeError(f"Invalid modem '{name}': missing required method '{attr}'")
            # Inject Qbit callback
            setattr(modem, "on_qbit_frame", self._on_qbit_frame)
            self.modems[name] = modem
            logger.info(f"[AudioModemManager] Registered modem '{name}' ({type(modem).__name__})")

    # ======================================================
    # QBIT CALLBACK
    # ======================================================
    def register_qbit_callback(self, callback: Callable):
        if callable(callback):
            self._qbit_callbacks.append(callback)
            logger.info("[AudioModemManager] Qbit callback registered")

    async def _on_qbit_frame(self, frame: Dict[str, Any]):
        if "track_id" not in frame:
            frame.update(gen_track_id(origin="AudioModem"))
        TrackIDManager.generate_sub_id(channel="AUDIO", parent_id=frame.get("parent_id"), metadata=frame)
        for cb in self._qbit_callbacks:
            try:
                if asyncio.iscoroutinefunction(cb):
                    await cb(frame)
                else:
                    cb(frame)
            except Exception as e:
                logger.error(f"[AudioModemManager] Callback error: {e}")
        # Push to QbitDialer
        if self.qbit_dialer and hasattr(self.qbit_dialer, "push_data"):
            try:
                push = self.qbit_dialer.push_data
                if asyncio.iscoroutinefunction(push):
                    await push(frame)
                else:
                    push(frame)
            except Exception as e:
                logger.error(f"[AudioModemManager] QbitDialer push error: {e}")
        # EventBus
        if self.event_bus:
            try:
                self.event_bus.publish("AUDIO_QBIT", payload=frame)
            except Exception as e:
                logger.warning(f"[AudioModemManager] EventBus error: {e}")
        # FAT
        if self.fat_layer:
            try:
                self.fat_layer.append_log(frame, source="audio_modem", label="audio")
            except Exception as e:
                logger.warning(f"[AudioModemManager] FAT log failed: {e}")

    # ======================================================
    # START / STOP
    # ======================================================
    async def start_all(self):
        if self._running:
            return
        self._running = True
        for modem in self.modems.values():
            modem.start()
        self._tasks.append(self.loop.create_task(self._manager_loop()))
        logger.info("[AudioModemManager] All modems started")

    async def stop_all(self):
        if not self._running:
            return
        self._running = False
        for modem in self.modems.values():
            modem.stop()
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        logger.info("[AudioModemManager] All modems stopped")

    async def _manager_loop(self):
        try:
            while self._running:
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            logger.info("[AudioModemManager] Manager loop cancelled")

# ==========================================================
# SINGLETON INSTANCE
# ==========================================================
audio_modem_manager = AudioModemManager()
