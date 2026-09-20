import random
import datetime

class NLPIntentEngine:
    """
    Enhanced NLP Intent Engine for SEED.
    Returns metrics for HUD 3D plotting and success tracking.
    """

    def execute_command(self, command, hud_interface=None, devices=None):
        devices = devices or []
        result_data = {}

        for device in devices:
            # Example logic metric (X-axis) can be AI confidence, reasoning weight, etc.
            logic_metric = round(random.uniform(-10, 10), 2)

            # Success rate (Y-axis) 0-1 scaled to 0-100
            success_rate = round(random.uniform(0, 1), 2)

            # Timestamp (Z-axis) for plotting
            timestamp = datetime.datetime.now()

            # Collect metrics per device
            result_data[device] = {
                "status": "success",
                "command": command,
                "logic_metric": logic_metric,
                "success_rate": success_rate,
                "timestamp": timestamp
            }

            # Log to HUD if available
            if hud_interface:
                hud_interface.log(
                    f"[NLP] Executed '{command}' on {device} | "
                    f"Logic: {logic_metric}, Success: {success_rate*100:.1f}%, Time: {timestamp.strftime('%H:%M:%S')}"
                )

        return result_data
