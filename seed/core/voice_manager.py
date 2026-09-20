# =====================================================
# FILE: voice_manager.py
# PATH: seed/core/voice_manager.py
# SEED MODULE: Core Voice Output / Feedback Engine
# COMPONENT: TTS Manager
# VERSION: 0.2.0
# STATUS: Alpha (Enhanced)
# =====================================================

import threading
import queue
import time
import pyttsx3
import logging
from datetime import datetime
from collections import deque

logger = logging.getLogger("SEEDVoiceManager")
logging.basicConfig(level=logging.INFO)

class VoiceManager:
    """
    LABEL: SEED_VOICE_MANAGER_OBJECT
    Handles offline TTS output for SEED events.
    Features:
    - Threaded TTS processing
    - Priority queue support (urgent messages)
    - Queue monitoring and memory cleanup
    - Auto-recovery on engine failure
    - Optional self-status reporting
    """

    def __init__(self, max_queue_size=100, memory_size=50):
        self.max_queue_size = max_queue_size
        self.memory_size = memory_size

        # Initialize TTS engine
        try:
            self._tts_engine = pyttsx3.init()
        except Exception as e:
            logger.warning(f"[SEED] Failed to initialize TTS engine: {e}")
            self._tts_engine = None

        # Queue and memory
        self._queue = queue.PriorityQueue()  # (priority, text)
        self._memory = deque(maxlen=self.memory_size)
        self._running = True

        # Start background thread
        self._thread = threading.Thread(target=self._process_queue, daemon=True)
        self._thread.start()
        logger.info("[SEED] VoiceManager initialized and background TTS thread started")

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

        # Prevent queue overflow
        if self._queue.qsize() >= self.max_queue_size:
            logger.warning("[SEED] Voice queue full, discarding low-priority text")
            if priority > 0:
                return

        self._queue.put((priority, str(text)))

    def stop(self):
        """
        Stop the VoiceManager gracefully.
        """
        self._running = False
        logger.info("[SEED] VoiceManager stopping...")
        self._thread.join(timeout=2)
        if self._tts_engine:
            self._tts_engine.stop()
        logger.info("[SEED] VoiceManager stopped")

    # ----------------------------
    # Internal Queue Processor
    # ----------------------------
    def _process_queue(self):
        while self._running:
            try:
                priority, text = self._queue.get(timeout=0.5)

                # Skip if already spoken recently
                if text in self._memory:
                    continue

                # Attempt to speak text
                if self._tts_engine:
                    try:
                        self._tts_engine.say(text)
                        self._tts_engine.runAndWait()
                    except Exception as e:
                        logger.warning(f"[SEED] TTS engine error: {e}")
                        self._attempt_engine_recovery()
                        continue

                # Store in memory to avoid repetition
                self._memory.append(text)

                # Optional self-status report if queue too large
                self._monitor_queue()

            except queue.Empty:
                time.sleep(0.05)
                continue

    # ----------------------------
    # Internal Helpers
    # ----------------------------
    def _attempt_engine_recovery(self):
        """
        Attempt to recover TTS engine if it fails.
        """
        try:
            self._tts_engine = pyttsx3.init()
            logger.info("[SEED] TTS engine recovered successfully")
        except Exception as e:
            logger.warning(f"[SEED] Failed to recover TTS engine: {e}")
            time.sleep(1)

    def _monitor_queue(self):
        """
        Monitor queue size and log warnings if needed.
        """
        if self._queue.qsize() > self.max_queue_size * 0.8:
            logger.warning(f"[SEED] Voice queue high: {self._queue.qsize()} items")
            self.speak(f"Voice queue is at {self._queue.qsize()} items", priority=0)
