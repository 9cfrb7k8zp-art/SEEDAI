# =====================================================
# FILE: system_commentary.py
# PATH: SEED_ROOT/seed/core/system_commentary.py
# SEED Internal Commentary Generator
# =====================================================

import time

class SEEDSystemCommentary:
    """
    Generates structured self-commentary for SEED.
    """

    def __init__(self, event_bus=None, voice_engine=None):
        self.event_bus = event_bus
        self.voice = voice_engine

    def announce(self, message, importance="normal"):
        payload = {
            "timestamp": time.time(),
            "message": message,
            "importance": importance
        }

        # Publish thought
        if self.event_bus:
            self.event_bus.publish(
                "SYSTEM_COMMENTARY",
                payload=payload
            )

        # Speak if important
        if self.voice and importance in ("high", "critical"):
            self.voice.speak(message)

    def status(self, message):
        self.announce(message, importance="normal")

    def warning(self, message):
        self.announce(message, importance="high")

    def critical(self, message):
        self.announce(message, importance="critical")
