# =====================================================
# FILE: voice_engine.py
# PATH: SEED_ROOT/seed/core/voice_engine.py
# SEED Voice Output & Self-Feedback Engine
# FULL SYSTEM SPECS UPDATE - PARTS 1-5
# UPDATED: 2026-01-05
# =====================================================

import threading
import queue
import time
import pyttsx3
from datetime import datetime
from collections import deque, defaultdict

class SEEDVoiceEngine:
    """
    Handles voice output, self-feedback, adaptive commentary, self-optimization, and environment-aware modulation.
    Features:
    - Threaded voice processing
    - Priority queue support
    - Self-feedback and dynamic rate/volume adjustment
    - Queue monitoring and memory cleanup
    - Adaptive learning to improve speech style and avoid repetition
    - Voice performance analytics and self-optimization
    - Environment-aware speech modulation
    """

    def __init__(self, event_bus=None, rate=160, volume=1.0, max_queue_size=100, memory_size=50):
        self.event_bus = event_bus
        self.default_rate = rate
        self.default_volume = volume
        self.max_queue_size = max_queue_size
        self.memory_size = memory_size

        # Initialize pyttsx3 engine safely
        try:
            self.engine = pyttsx3.init()
            self.engine.setProperty("rate", self.default_rate)
            self.engine.setProperty("volume", self.default_volume)
        except Exception as e:
            self.engine = None
            self._log_warning(f"Failed to initialize TTS engine: {e}")

        # Priority queue: normal=1, high=0
        self._queue = queue.PriorityQueue()
        self._running = True

        # Memory of last spoken texts
        self._memory = deque(maxlen=self.memory_size)

        # Analytics data
        self._performance = defaultdict(lambda: {"count":0, "last_time":None, "errors":0, "duration":0})

        # Environment simulation variables
        self._ambient_noise_level = 0.0  # range 0.0 - 1.0
        self._user_preferred_rate = self.default_rate
        self._user_preferred_volume = self.default_volume

        # Start background thread
        self._thread = threading.Thread(
            target=self._voice_loop,
            daemon=True
        )
        self._thread.start()

    # =========================
    # INTERNAL LOOP
    # =========================
    def _voice_loop(self):
        while self._running:
            try:
                priority, text = self._queue.get(timeout=0.5)

                if not self.engine:
                    self._attempt_engine_recovery()
                    continue

                # Avoid repetition
                if text in self._memory:
                    continue

                # Dynamic adjustments
                self._adjust_rate_volume()
                self._apply_environment_modulation()

                # Adaptive style
                text_to_speak = self._adaptive_style(text, priority)

                # Speak text
                start_time = time.time()
                try:
                    self.engine.say(text_to_speak)
                    self.engine.runAndWait()
                except Exception as e:
                    self._performance[text]["errors"] += 1
                    raise e
                end_time = time.time()

                # Record performance
                self._performance[text]["count"] += 1
                self._performance[text]["last_time"] = end_time
                self._performance[text]["duration"] = end_time - start_time

                # Save to memory
                self._memory.append(text)

                # Publish feedback
                self._publish_event("VOICE_OUTPUT", text_to_speak)

                # Auto-cleanup queue
                self._manage_queue()

                # Self-optimize
                self._self_optimize(text)

            except queue.Empty:
                time.sleep(0.05)
                self._self_monitor()
                continue
            except Exception as e:
                self._publish_event("SYSTEM_WARNING", f"Voice loop error: {e}")
                self._attempt_engine_recovery()

    # =========================
    # PUBLIC API
    # =========================
    def speak(self, text: str, priority: int = 1):
        """
        Queue text for speech.
        priority: 0 = high, 1 = normal
        """
        if not text:
            return

        if self._queue.qsize() >= self.max_queue_size:
            self._publish_event("SYSTEM_WARNING", "Voice queue full, discarding low-priority text")
            if priority > 0:
                return

        self._queue.put((priority, str(text)))

    def stop(self):
        """
        Stop the voice engine gracefully.
        """
        self._running = False
        self._thread.join(timeout=2)
        if self.engine:
            self.engine.stop()
        self._publish_event("SYSTEM_INFO", "Voice engine stopped.")

    # =========================
    # INTERNAL HELPERS
    # =========================
    def _publish_event(self, event_type, text):
        if self.event_bus:
            self.event_bus.publish(
                event_type,
                payload={
                    "text": text,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )

    def _log_warning(self, message):
        print(f"[VoiceEngine WARNING] {message}")
        self._publish_event("SYSTEM_WARNING", message)

    def _attempt_engine_recovery(self):
        try:
            self.engine = pyttsx3.init()
            self.engine.setProperty("rate", self.default_rate)
            self.engine.setProperty("volume", self.default_volume)
            self._publish_event("SYSTEM_INFO", "Voice engine recovered successfully.")
        except Exception as e:
            self._log_warning(f"Engine recovery failed: {e}")
            time.sleep(1)

    def _adjust_rate_volume(self):
        """
        Dynamically adjust rate and volume based on queue load.
        """
        try:
            size = self._queue.qsize()
            rate = max(80, self.default_rate - size // 2)
            volume = max(0.5, min(1.0, self.default_volume - size * 0.002))
            self.engine.setProperty("rate", rate)
            self.engine.setProperty("volume", volume)
        except Exception as e:
            self._log_warning(f"Failed to adjust rate/volume: {e}")

    def _manage_queue(self):
        """
        Auto-cleanup old messages if queue exceeds limits.
        """
        while self._queue.qsize() > self.max_queue_size:
            try:
                removed = self._queue.get_nowait()
                self._publish_event("SYSTEM_WARNING", f"Removed from queue: {removed[1]}")
            except queue.Empty:
                break

    # =========================
    # SELF-FEEDBACK & ADAPTIVE
    # =========================
    def report_status(self):
        """
        Speak engine status automatically.
        """
        queue_size = self._queue.qsize()
        status = f"Voice engine running. Queue size: {queue_size} messages."
        self.speak(status, priority=0)

    def _self_monitor(self):
        """
        Idle monitoring: report queue health occasionally.
        """
        if self._queue.qsize() > self.max_queue_size * 0.8:
            self.report_status()

    def _adaptive_style(self, text, priority):
        """
        Modify speech style for urgent messages or repeated content.
        """
        if priority == 0:
            text = f"Attention: {text.upper()}"
        return text

    def _self_optimize(self, text):
        """
        Analyze past performance and adjust rate/volume for efficiency.
        """
        record = self._performance[text]
        if record["count"] > 3:
            # Slow down repeated messages slightly if duration too fast
            if record.get("duration",0) < 0.5:
                self.default_rate = max(80, self.default_rate - 5)
            # Reduce volume if repeated messages too loud
            if record.get("duration",0) > 2:
                self.default_volume = max(0.6, self.default_volume - 0.05)

    # =========================
    # ENVIRONMENT-AWARE MODULATION
    # =========================
    def _apply_environment_modulation(self):
        """
        Adjust volume and rate based on ambient noise and user preference.
        """
        # Simulated ambient noise impact
        noise_factor = 1.0 - self._ambient_noise_level  # quieter if high ambient
        adjusted_volume = max(0.5, min(1.0, self.default_volume * noise_factor))
        adjusted_rate = int(self.default_rate * (1.0 - self._ambient_noise_level * 0.1))

        # Apply user preferences
        adjusted_volume = min(adjusted_volume, self._user_preferred_volume)
        adjusted_rate = min(adjusted_rate, self._user_preferred_rate)

        try:
            self.engine.setProperty("volume", adjusted_volume)
            self.engine.setProperty("rate", adjusted_rate)
        except Exception as e:
            self._log_warning(f"Environment modulation failed: {e}")

    def set_ambient_noise_level(self, level: float):
        """
        Update ambient noise level (0.0 to 1.0)
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
