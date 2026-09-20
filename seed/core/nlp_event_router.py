import random
import datetime

# ✅ Fix missing imports
from seed.core.event_bus import SEEDEventBus       # Adjust path if needed
from seed.core.nlp_intent_engine import NLPIntentEngine  # Avoid circular import if possible

class SEEDNLPEventRouter:
    """
    Routes NLP commands to EventBus for downstream consumption.
    """

    def __init__(self, event_bus: SEEDEventBus):
        # Ensure a proper EventBus instance is passed
        if not isinstance(event_bus, SEEDEventBus):
            raise TypeError("event_bus must be an instance of SEEDEventBus")
        self.event_bus = event_bus
        self.intent_engine = NLPIntentEngine()

    def execute_command(self, command: str, devices: list = None, hud_interface=None):
        devices = devices or []
        results = self.intent_engine.execute_command(
            command, hud_interface=hud_interface, devices=devices
        )

        # Publish each result to EventBus
        for device_id, data in results.items():
            self.event_bus.publish(
                "COMMAND_EXECUTED",
                payload={
                    "command": command,
                    "device": device_id,
                    "logic_metric": data.get("logic_metric", 0),
                    "success_rate": data.get("success_rate", 0.0),
                    "timestamp": data.get("timestamp", datetime.datetime.now())
                }
            )

        return results
