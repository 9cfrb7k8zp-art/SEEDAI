# =====================================================
# FILE: voice_system.py
# PATH: seed/core/voice_system.py
# SEED MODULE: Unified TTS Engine & Manager
# COMPONENT: Adaptive Voice Output / Feedback Engine
# VERSION: 1.0.0
# STATUS: Alpha (Fully Adaptive)
# UPDATED: 2026-01-05
# =====================================================

import threading
import queue
import time
import pyttsx3
import logging
from datetime import datetime
from collections import deque, defaultdict

logger = logging.getLogger("SEEDVoiceSystem")
logging.basicConfig(level=logging.INFO)

class SEEDVoiceSystem:
    """
    Unified SEED Voice System.
    Combines VoiceEngine and VoiceManager features:
    - Threaded, priority-based TTS
    - Self-feedback and status reporting
    - Memory to prevent repetition
    - Queue monitoring and auto-cleanup
    - Adaptive learning of rate, volume, and speech style
    - Environment-aware modulation (ambient noise, user preferences)
    - TTS engine auto-recovery
    """

    def __init__(self, max_queue_size=100, memory_size=50, default_rate=160, default_volume=1.0, event_bus=None):
        self.event_bus = event_bus
        self.max_queue_size = max_queue_size
        self.memory_size = memory_size
        self.default_rate = default_rate
        self.default_volume = default_volume

        # Initialize TTS engine
        try:
            self._tts_engine = pyttsx3.init()
            self._tts_engine.setProperty("rate", self.default_rate)
            self._tts_engine.setProperty("volume", self.default_volume)
        except Exception as e:
            logger.warning(f"[SEED] Failed to initialize TTS engine: {e}")
            self._tts_engine = None

        # Queue and memory
        self._queue = queue.PriorityQueue()  # (priority, text)
        self._memory = deque(maxlen=self.memory_size)
        self._running = True

        # Analytics
        self._performance = defaultdict(lambda: {"count":0, "last_time":None, "errors":0, "duration":0})

        # Environment / user preferences
        self._ambient_noise_level = 0.0
        self._user_preferred_rate = self.default_rate
        self._user_preferred_volume = self.default_volume

        # Start background thread
        self._thread = threading.Thread(target=self._process_queue, daemon=True)
        self._thread.start()
        logger.info("[SEED] Unified VoiceSystem initialized and background TTS thread started")

    # ----------------------------
    # Public API
    # ----------------------------
    def speak(self, text: str, priority: int = 1):
        """
        Queue text to be spoken.
        priority: 0 = high, 1 = normal
        """
        if not text:
            return

        if self._queue.qsize() >= self.max_queue_size:
            logger.warning("[SEED] Voice queue full, discarding low-priority text")
            if priority > 0:
                return

        self._queue.put((priority, str(text)))

    def stop(self):
        """
        Stop the voice system gracefully.
        """
        self._running = False
        self._thread.join(timeout=2)
        if self._tts_engine:
            self._tts_engine.stop()
        logger.info("[SEED] VoiceSystem stopped")

    def set_ambient_noise_level(self, level: float):
        """
        Update ambient noise level (0.0 - 1.0)
        """
        self._ambient_noise_level = max(0.0, min(1.0, level))

    def set_user_preferences(self, rate: int = None, volume: float = None):
        """
        Update user-preferred speech settings
        """
        if rate is not None:
            self._user_preferred_rate = rate
        if volume is not None:
            self._user_preferred_volume = volume

    # ----------------------------
    # Internal Queue Processor
    # ----------------------------
    def _process_queue(self):
        while self._running:
            try:
                priority, text = self._queue.get(timeout=0.5)

                # Skip repeated text
                if text in self._memory:
                    continue

                # Apply dynamic adjustments
                self._adjust_rate_volume()
                self._apply_environment_modulation()

                # Adaptive style
                text_to_speak = self._adaptive_style(text, priority)

                # Speak
                start_time = time.time()
                try:
                    self._tts_engine.say(text_to_speak)
                    self._tts_engine.runAndWait()
                except Exception as e:
                    self._performance[text]["errors"] += 1
                    logger.warning(f"[SEED] TTS engine error: {e}")
                    self._attempt_engine_recovery()
                    continue
                end_time = time.time()

                # Record performance
                self._performance[text]["count"] += 1
                self._performance[text]["last_time"] = end_time
                self._performance[text]["duration"] = end_time - start_time

                # Store in memory
                self._memory.append(text)
                if self.event_bus is not None:
                    try:
                        publisher = getattr(self.event_bus, "publish", None)
                        if callable(publisher):
                            publisher("VOICE_OUTPUT", payload={"text": text_to_speak, "timestamp": time.time()})
                        else:
                            emitter = getattr(self.event_bus, "emit", None)
                            if callable(emitter):
                                emitter("VOICE_OUTPUT", {"text": text_to_speak, "timestamp": time.time()})
                    except Exception:
                        pass

                # Optional self-status
                self._monitor_queue()

                # Self-optimize
                self._self_optimize(text)

            except queue.Empty:
                time.sleep(0.05)
                continue
            except Exception as e:
                logger.warning(f"[SEED] Voice loop exception: {e}")
                self._attempt_engine_recovery()

    # ----------------------------
    # Internal Helpers
    # ----------------------------
    def _attempt_engine_recovery(self):
        """
        Attempt to recover TTS engine if it fails.
        """
        try:
            self._tts_engine = pyttsx3.init()
            self._tts_engine.setProperty("rate", self.default_rate)
            self._tts_engine.setProperty("volume", self.default_volume)
            logger.info("[SEED] TTS engine recovered successfully")
        except Exception as e:
            logger.warning(f"[SEED] Failed to recover TTS engine: {e}")
            time.sleep(1)

    def _adjust_rate_volume(self):
        """
        Dynamically adjust rate and volume based on queue load.
        """
        try:
            size = self._queue.qsize()
            rate = max(80, self.default_rate - size // 2)
            volume = max(0.5, min(1.0, self.default_volume - size * 0.002))
            self._tts_engine.setProperty("rate", rate)
            self._tts_engine.setProperty("volume", volume)
        except Exception as e:
            logger.warning(f"[SEED] Failed to adjust rate/volume: {e}")

    def _monitor_queue(self):
        """
        Monitor queue and optionally report high usage.
        """
        if self._queue.qsize() > self.max_queue_size * 0.8:
            logger.warning(f"[SEED] Voice queue high: {self._queue.qsize()} items")
            self.speak(f"Voice queue is at {self._queue.qsize()} items", priority=0)

    def _adaptive_style(self, text, priority):
        """
        Modify text for urgent messages.
        """
        if priority == 0:
            text = f"Attention: {text.upper()}"
        return text

    def _self_optimize(self, text):
        """
        Adjust rate/volume based on performance analytics.
        """
        record = self._performance[text]
        if record["count"] > 3:
            if record.get("duration",0) < 0.5:
                self.default_rate = max(80, self.default_rate - 5)
            if record.get("duration",0) > 2:
                self.default_volume = max(0.6, self.default_volume - 0.05)

    def _apply_environment_modulation(self):
        """
        Adjust volume and rate for ambient noise and user preferences.
        """
        noise_factor = 1.0 - self._ambient_noise_level
        adjusted_volume = max(0.5, min(1.0, self.default_volume * noise_factor))
        adjusted_rate = int(self.default_rate * (1.0 - self._ambient_noise_level * 0.1))

        adjusted_volume = min(adjusted_volume, self._user_preferred_volume)
        adjusted_rate = min(adjusted_rate, self._user_preferred_rate)

        try:
            self._tts_engine.setProperty("volume", adjusted_volume)
            self._tts_engine.setProperty("rate", adjusted_rate)
        except Exception as e:
            logger.warning(f"[SEED] Environment modulation failed: {e}")
