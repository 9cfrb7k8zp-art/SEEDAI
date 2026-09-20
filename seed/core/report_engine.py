# FILE: report_engine.py
# PATH: SEED_ROOT/core/report_engine.py

import datetime
from core.event_bus import SEEDEventBus, SYSTEM_WARNING

class SEEDReportEngine:
    """
    Generates automated reports and sends notifications.
    """

    def __init__(self, analytics_engine, memory_manager, agent_manager, event_bus: SEEDEventBus):
        self.analytics = analytics_engine
        self.memory = memory_manager
        self.agents = agent_manager
        self.event_bus = event_bus
        self.event_bus.subscribe(SYSTEM_WARNING, self._handle_warning)

    # ----------------------------
    # GENERATE REPORT
    # ----------------------------
    def generate_report(self):
        report = {
            "timestamp": datetime.datetime.now().isoformat(),
            "analytics_summary": self._analytics_summary(),
            "memory_summary": self._memory_summary(),
            "agents": self.agents.list_agents() if self.agents else {}
        }
        # Save or send report (file, email, webhook)
        # Placeholder: printing
        print(f"[REPORT] {report}")
        return report

    # ----------------------------
    # ANALYTICS SUMMARY
    # ----------------------------
    def _analytics_summary(self):
        summary = {}
        metrics = getattr(self.analytics, "metrics", {})
        devices = metrics.get("devices", {})
        for device_id, data in devices.items():
            history = data.get("history", [])
            if history:
                latest_rate = history[-1]["success_rate"]
                summary[device_id] = {"latest": latest_rate, "count": len(history)}
        return summary

    # ----------------------------
    # MEMORY SUMMARY
    # ----------------------------
    def _memory_summary(self):
        short_len = len(getattr(self.memory, "short_term", []))
        long_len = len(getattr(self.memory, "long_term", []))
        return {"short_term": short_len, "long_term": long_len}

    # ----------------------------
    # WARNING HANDLER
    # ----------------------------
    def _handle_warning(self, event):
        payload = event.get("payload", {})
        source = payload.get("source", "unknown")
        error = payload.get("error", "unspecified")
        message = f"[ALERT] {source}: {error}"
        self.notify(message)

    # ----------------------------
    # NOTIFICATION
    # ----------------------------
    def notify(self, message):
        # Placeholder: extend to email, webhook, logging, etc.
        print(f"[NOTIFICATION] {message}")
