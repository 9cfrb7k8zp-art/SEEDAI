# ==========================================================
# FILE: actuator_consensus_engine.py
# PATH: SEED_ROOT/seed/core/actuator_consensus_engine.py
# SYSTEM LAYER: Distributed Actuator Consensus
# VERSION: 1.0
# ==========================================================

import time
import threading
import logging
from collections import defaultdict
from statistics import mean
from copy import deepcopy

logger = logging.getLogger("ActuatorConsensus")

DEFAULT_QUORUM = 2
MAX_QUEUE_DEPTH = 1000
CONSENSUS_TIMEOUT = 0.25  # seconds


# ==========================================================
# ACTUATOR CONSENSUS ENGINE
# ==========================================================

class ActuatorConsensusEngine:

    def __init__(
        self,
        event_bus=None,
        actuators=None,
        quorum: int = DEFAULT_QUORUM,
        enable_hardware: bool = False,
    ):
        self.event_bus = event_bus
        self.actuators = actuators or {}
        self.quorum = quorum
        self.enable_hardware = enable_hardware

        self._lock = threading.Lock()
        self._queues = defaultdict(list)
        self._last_emit = {}

        # Subscribe to actuator commands
        if hasattr(self.event_bus, "subscribe"):
            self.event_bus.subscribe(
                "ACTUATOR_COMMAND",
                self._handle_actuator_command
            )

        logger.info("[Consensus] Actuator Consensus Engine online")

    # ======================================================
    # INGEST
    # ======================================================

    def _handle_actuator_command(self, event):
        data = event.get("data", event)
        actuator = data.get("actuator")

        if not actuator:
            return

        with self._lock:
            queue = self._queues[actuator]
            queue.append(deepcopy(data))

            if len(queue) > MAX_QUEUE_DEPTH:
                queue.pop(0)

        self._attempt_consensus(actuator)

    # ======================================================
    # CONSENSUS
    # ======================================================

    def _attempt_consensus(self, actuator):
        with self._lock:
            queue = self._queues.get(actuator, [])
            if len(queue) < self.quorum:
                return

            now = time.time()
            last_emit = self._last_emit.get(actuator, 0)

            if now - last_emit < CONSENSUS_TIMEOUT:
                return

            # Build weighted vote set
            values = []
            weights = []
            track_ids = set()
            agents = set()

            for cmd in queue:
                v = float(cmd.get("value", 0.0))
                confidence = float(cmd.get("confidence", 1.0))
                qbit = float(cmd.get("qbit", 0.0))
                priority = float(cmd.get("priority", 0.5))

                weight = confidence * (0.5 + qbit) * (0.5 + priority)
                values.append(v * weight)
                weights.append(weight)

                if cmd.get("track_id"):
                    track_ids.add(cmd["track_id"])
                if cmd.get("agent_id"):
                    agents.add(cmd["agent_id"])

            if not weights or sum(weights) == 0:
                return

            consensus_value = sum(values) / sum(weights)

            consensus_cmd = {
                "actuator": actuator,
                "value": consensus_value,
                "confidence": mean([c.get("confidence", 1.0) for c in queue]),
                "qbit": mean([c.get("qbit", 0.0) for c in queue]),
                "priority": mean([c.get("priority", 0.5) for c in queue]),
                "agents": list(agents),
                "track_ids": list(track_ids),
                "timestamp": now,
                "_source": "ActuatorConsensusEngine",
            }

            # Clear queue
            queue.clear()
            self._last_emit[actuator] = now

        self._emit_consensus(consensus_cmd)

    # ======================================================
    # EMIT
    # ======================================================

    def _emit_consensus(self, command):
        logger.info(
            f"[Consensus] {command['actuator']} → {command['value']:.3f} "
            f"agents={len(command['agents'])}"
        )

        # Emit consensus event
        if hasattr(self.event_bus, "emit"):
            try:
                self.event_bus.emit(
                    "ACTUATOR_CONSENSUS",
                    data=deepcopy(command)
                )
            except Exception as e:
                logger.warning(f"[Consensus] Event emit failed: {e}")

        # Apply to hardware only if enabled
        if not self.enable_hardware:
            return

        actuator_name = command.get("actuator")
        actuator_obj = self.actuators.get(actuator_name)

        if actuator_obj and hasattr(actuator_obj, "apply"):
            try:
                actuator_obj.apply(command)
            except Exception as e:
                logger.error(
                    f"[Consensus] Actuator apply failed ({actuator_name}): {e}"
                )


    # ==============================
    # HealthMonitor track() function for SEED
    # ==============================

    def seed_track():
        # Gather basic system info
        try:
            import psutil  # For CPU, memory, disk info
        except ImportError:
            psutil = None

        # Qbit status
        qbit_status = "Unknown"
        qbit_error = None
        try:
            if qbit is not None:
                # Assuming your Qbit object has a .status() method
                qbit_status = qbit.status()
        except Exception as e:
            qbit_error = str(e)
            qbit_status = "Error"

        # CPU and Memory stats
        cpu = psutil.cpu_percent() if psutil else None
        memory = psutil.virtual_memory().used if psutil else None
        disk = psutil.disk_usage("/").percent if psutil else None

        # Return a dictionary HealthMonitor can read
        return {
            "cpu_percent": cpu,
            "memory_used_mb": memory,
            "disk_percent": disk,
            "qbit_status": qbit_status,
            "qbit_error": qbit_error
        }

    # ==============================
    # Initialize HealthMonitor with track
    # ==============================
    health_monitor = HealthMonitor(qbit=qbit, live_debug=True, track=seed_track)


