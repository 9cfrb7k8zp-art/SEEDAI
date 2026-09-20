# ==========================================================
# FILE: predictive_motion_engine.py
# PATH: SEED_ROOT/seed/core/predictive_motion_engine.py
# PREDICTIVE MOTION ENGINE – Level 2 Forward Extrapolation
# Purpose: Predict near-future intent motion & stability
# ==========================================================

import time
import math
import logging
from collections import deque

logger = logging.getLogger("PredictiveMotionEngine")


class PredictiveMotionEngine:
    """
    LEVEL 2 – PREDICTIVE MOTION

    Responsibilities:
      - Listen to stabilized INTENT_STATE events
      - Track recent direction + confidence
      - Predict short-horizon future motion
      - Emit MOTION_PREDICTION events

    This layer DOES NOT:
      - Read raw sensors
      - Control actuators
      - Render UI
    """

    def __init__(
        self,
        event_bus=None,
        horizon_seconds=0.35,
        history_size=12,
        min_confidence=0.25,
    ):
        self.event_bus = event_bus
        self.horizon = horizon_seconds
        self.min_confidence = min_confidence

        # intent -> deque of states
        self._history = {}
        self.history_size = history_size

        if self.event_bus:
            self.event_bus.subscribe(
                "INTENT_STATE",
                self.ingest_intent_state,
            )

    # --------------------------------------------------
    # INGEST INTENT STATE
    # --------------------------------------------------
    def ingest_intent_state(self, event):
        """
        Expected payload:
          intent, confidence, direction, timestamp
        """
        try:
            data = event.get("data", event)
            intent = data.get("intent")

            if not intent:
                return

            if intent not in self._history:
                self._history[intent] = deque(maxlen=self.history_size)

            self._history[intent].append(data)

            self._predict(intent)

        except Exception as e:
            logger.warning(f"[PredictiveMotion] ingest failed: {e}")

    # --------------------------------------------------
    # PREDICTION CORE
    # --------------------------------------------------
    def _predict(self, intent):
        records = self._history.get(intent)
        if not records or len(records) < 2:
            return

        latest = records[-1]
        confidence = latest.get("confidence", 0.0)

        if confidence < self.min_confidence:
            return

        # Use last two directional samples
        prev = records[-2]
        d1 = prev.get("direction")
        d2 = latest.get("direction")

        if d1 is None or d2 is None:
            return

        t1 = prev.get("timestamp")
        t2 = latest.get("timestamp")
        dt = max(t2 - t1, 1e-6)

        # Angular velocity
        angular_velocity = (d2 - d1) / dt

        # Project forward
        projected_heading = d2 + angular_velocity * self.horizon

        # Normalize angle (-pi, pi)
        projected_heading = math.atan2(
            math.sin(projected_heading),
            math.cos(projected_heading),
        )

        prediction = {
            "intent": intent,
            "predicted_heading": projected_heading,
            "angular_velocity": angular_velocity,
            "confidence": round(confidence, 4),
            "horizon": self.horizon,
            "timestamp": time.time(),
        }

        logger.info(
            f"[MotionPrediction] {intent} "
            f"θ→{projected_heading:.2f} "
            f"ω={angular_velocity:.2f}"
        )

        if self.event_bus:
            try:
                self.event_bus.emit(
                    "MOTION_PREDICTION",
                    data=prediction,
                )
            except Exception as e:
                logger.warning(
                    f"[PredictiveMotion] emit failed: {e}"
                )

    # --------------------------------------------------
    # OPTIONAL QUERY API
    # --------------------------------------------------
    def get_latest_prediction(self, intent):
        """
        Pull-based access if needed.
        """
        records = self._history.get(intent)
        if not records:
            return None
        return records[-1]
