# ==========================================================
# FILE: audio_modem.py
# PATH: SEED_ROOT/seed/core/audio_modem.py
# MODULE: SEED Audio Modem v4.3 (SAFE / AUTO-HISTORY CLEAN / MOCK TEST)
# PURPOSE: Audio modem with thread-safe, Qbit-safe interface
# UPDATED: 2026-01-07 (Normalized storage_root)
# ==========================================================

import os
import time
import queue
import asyncio
import threading
import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger("SEEDAudioModem")
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
formatter = logging.Formatter("[%(levelname)s] %(name)s | %(message)s")
ch.setFormatter(formatter)
logger.addHandler(ch)

# ==========================================================
# External Libraries (with warnings if missing)
# ==========================================================
try:
    import numpy as np
except ImportError:
    np = None
    logger.warning("numpy not found — numeric operations will be mocked")

try:
    import sounddevice as sd
except ImportError:
    sd = None
    logger.warning("sounddevice not found — audio TX/RX will be disabled")

try:
    from scipy.fft import fft
except ImportError:
    fft = None
    logger.warning("scipy.fft not found — FFT analysis will be disabled")

# ==========================================================
# Internal SEED modules (mocked if missing)
# ==========================================================
try:
    from seed.core.modem_layer import SignalFrame, ModemLayer
except ImportError:
    logger.warning("seed.core.modem_layer not found — using mock classes")
    class SignalFrame:
        def __init__(self, **kwargs):
            self.frequency = kwargs.get("frequency", 0)
            self.amplitude = kwargs.get("amplitude", 0)
            self.phase = kwargs.get("phase", 0)
            self.payload = kwargs.get("payload", {})
            self.timestamp = kwargs.get("timestamp", time.time())
            self.noise = kwargs.get("noise", 0.0)

    class ModemLayer:
        receive_external = lambda self, frame: None
        loop = asyncio.get_event_loop()
        storage_root = None

try:
    from seed.core.track_id import TrackIDTag
except ImportError:
    logger.warning("seed.core.track_id not found — using mock TrackIDTag")
    class TrackIDTag:
        def __init__(self, **kwargs):
            self.track_id = kwargs.get("agent", "MOCK_TRACK")

try:
    from seed.core.track_context import TrackContext
except ImportError:
    logger.warning("seed.core.track_context not found — using mock TrackContext")
    class TrackContext:
        @staticmethod
        def get():
            return "MOCK_PARENT_TRACK"

try:
    from seed.core.tracked_data import TrackedData
except ImportError:
    logger.warning("seed.core.tracked_data not found — using mock TrackedData")
    class TrackedData:
        def __init__(self, **kwargs):
            self.data = kwargs.get("data", {})
            self.payload = kwargs.get("payload", {})

# ==========================================================
# NUMERIC COERCION (QBIT SAFE)
# ==========================================================
def numericize(value):
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, dict):
        return {k: numericize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [numericize(v) for v in value]
    return 0.0

# ==========================================================
# HELPER: NORMALIZE STORAGE ROOT
# ==========================================================
def normalize_root(root: Optional[str]) -> str:
    base_root = root or os.environ.get("SEED_ROOT", r"C:\SEED_ROOT")
    base_root = os.path.abspath(base_root)
    if os.path.basename(base_root).upper() != "SEED_ROOT":
        base_root = os.path.join(base_root, "SEED_ROOT")
    return os.path.abspath(base_root)

# ==========================================================
# BASE MODEM CONTRACT
# ==========================================================
class Modem:
    def __init__(self):
        self.modem_id = None
        self.channels = []
        self._running = False

    def start(self):
        self._running = True

    def stop(self):
        self._running = False

    def send(self, data: Any):
        raise NotImplementedError

    async def receive(self) -> Any:
        raise NotImplementedError

# ==========================================================
# SEED AUDIO MODEM
# ==========================================================
class SEEDAudioModem(Modem):
    HISTORY_LIMIT = 500  # keep last 500 entries

    def __init__(
        self,
        modem_layer = ModemLayer,
        storage_root = "./SEED_ROOT",
        event_bus = None,
        name = "SEED_AUDIO_MODEM",
        sample_rate = 44100,
        frame_duration = 0.2,
        channels = 1,
        device_index = None,
        base_freq: float = 10.0,
        freq_step: float = 1.0,
        track_domain: str = "SS",
        track_channel: str = "AUDIO",
        agent: str = "AUDIOMODEM",
        test_mode: bool = False,
    ):
        super().__init__()

        self.modem_layer = modem_layer or ModemLayer()
        self.event_bus = event_bus
        self.name = name

        # -----------------------------
        # STORAGE ROOT (normalized)
        # -----------------------------
        root_from_layer = getattr(self.modem_layer, "storage_root", None)
        self.storage_root = normalize_root(storage_root or root_from_layer)
        os.makedirs(self.storage_root, exist_ok=True)

        # -----------------------------
        # AUDIO CONFIG
        # -----------------------------
        self.sample_rate = sample_rate
        self.frame_size = int(sample_rate * frame_duration)
        self.channels = channels
        self.selected_input_device = device_index
        self.base_freq = base_freq
        self.freq_step = freq_step
        self.track_domain = track_domain
        self.track_channel = track_channel
        self.agent = agent

        # -----------------------------
        # QUEUES
        # -----------------------------
        self._tx_queue: queue.Queue[SignalFrame] = queue.Queue()
        self._rx_queue: asyncio.Queue = asyncio.Queue()

        # -----------------------------
        # HISTORY
        # -----------------------------
        self.history = []

        # -----------------------------
        # THREADS
        # -----------------------------
        self._tx_thread = threading.Thread(target=self._tx_loop, daemon=True)
        self._rx_thread = threading.Thread(target=self._rx_loop, daemon=True)

        # -----------------------------
        # TEST MODE
        # -----------------------------
        self.test_mode = test_mode

        logger.info(f"[SEEDAudioModem] ONLINE | root={self.storage_root}")

    # ======================================================
    # LIFECYCLE
    # ======================================================
    def start(self):
        if self._running:
            return
        self._running = True
        self._tx_thread.start()
        self._rx_thread.start()
        logger.info("[SEEDAudioModem] AUDIO SYSTEM ACTIVE")

    def stop(self):
        self._running = False
        logger.info("[SEEDAudioModem] AUDIO SYSTEM STOPPED")

    # ======================================================
    # MODEM API
    # ======================================================
    def send(self, frame: SignalFrame):
        if self._running:
            self._tx_queue.put(frame)

    async def receive(self) -> Optional[SignalFrame]:
        if self._running:
            return await self._rx_queue.get()
        return None

    # ======================================================
    # TX — SPEAK
    # ======================================================
    def _tx_loop(self):
        if self.test_mode or (sd and np):
            while self._running:
                try:
                    if self.test_mode:
                        time.sleep(0.05)
                        continue
                    frame = self._tx_queue.get(timeout=0.1)
                    tone = self._generate_tone(frame.frequency, frame.amplitude, frame.phase)
                    if tone is not None:
                        sd.play(tone, self.sample_rate)
                        sd.wait()
                except queue.Empty:
                    continue
                except Exception as e:
                    logger.error(f"[SEEDAudioModem][TX] {e}")
        else:
            logger.warning("TX loop skipped — missing numpy/sounddevice and test_mode=False")

    # ======================================================
    # RX — HEAR
    # ======================================================
    def _rx_loop(self):
        if self.test_mode or (sd and np):
            try:
                if self.test_mode:
                    while self._running:
                        time.sleep(0.05)
                        mock_frame = SignalFrame(
                            frequency=440.0,
                            amplitude=0.5,
                            phase=0.0,
                            payload={"track_id": "MOCK_RX"},
                            timestamp=time.time(),
                            noise=0.0,
                        )
                        self._rx_queue.put_nowait(mock_frame)
                        self._auto_append_history(mock_frame)
                    return
                with sd.InputStream(
                    samplerate=self.sample_rate,
                    channels=self.channels,
                    blocksize=self.frame_size,
                    device=self.selected_input_device,
                ) as stream:
                    while self._running:
                        audio, _ = stream.read(self.frame_size)
                        freq, amp, rms = self._analyze(audio[:, 0])
                        if freq is None:
                            continue
                        parent_track = TrackContext.get()
                        tag = TrackIDTag(
                            domain=self.track_domain,
                            channel=self.track_channel,
                            agent=self.agent,
                            skill="RX",
                            parent_id=parent_track,
                            reasoning_input={"freq": freq, "amp": amp, "rms": rms},
                        )
                        frame = SignalFrame(
                            frequency=freq,
                            amplitude=amp,
                            phase=0.0,
                            payload={"track_id": tag.track_id},
                            timestamp=time.time(),
                            noise=0.0,
                        )
                        self.modem_layer.receive_external(frame)
                        asyncio.run_coroutine_threadsafe(
                            self._rx_queue.put(frame),
                            self.modem_layer.loop,
                        )
                        self._auto_append_history(frame)
            except Exception as e:
                logger.error(f"[SEEDAudioModem][RX] {e}")
        else:
            logger.warning("RX loop skipped — missing numpy/sounddevice and test_mode=False")

    # ======================================================
    # HISTORY APPEND WITH CLEANING
    # ======================================================
    def _auto_append_history(self, frame: SignalFrame):
        self.history.append({"ts": float(time.time()), "freq": float(frame.frequency), "amp": float(frame.amplitude), "rms": 0.0})
        if len(self.history) > self.HISTORY_LIMIT:
            self.history = self.history[-self.HISTORY_LIMIT:]

    # ======================================================
    # DSP
    # ======================================================
    def _generate_tone(self, freq: float, amp: float, phase: float):
        if not np:
            return None
        t = np.linspace(0, self.frame_size / self.sample_rate, self.frame_size, False)
        return amp * np.sin(2 * np.pi * freq * t + phase)

    def _analyze(self, samples):
        if not np or not fft:
            return None, None, 0.0
        spectrum = np.abs(fft(samples))
        freqs = np.fft.fftfreq(len(spectrum), 1 / self.sample_rate)
        idx = int(np.argmax(spectrum[: len(spectrum) // 2]))
        peak_freq = abs(freqs[idx])
        peak_amp = spectrum[idx] / len(samples)
        rms = float(np.sqrt(np.mean(samples ** 2)))
        if peak_amp > 0.01:
            return peak_freq, peak_amp, rms
        return None, None, rms

# ==========================================================
# END FILE
# ==========================================================
