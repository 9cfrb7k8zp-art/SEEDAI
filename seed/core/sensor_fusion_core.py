# ==========================================================
# FILE: sensor_fusion_core.py
# PATH: seed/core/sensor_fusion_core.py
# VERSION: 2.1 (Full TrackID + Entropy + Qbit/HUD + Batch Fusion + Sensor Presets + Confidence Normalization + Adaptive Weighting + Predictive Smoothing)
# PURPOSE: Fuses multiple sensor channels with confidence weighting, adaptive learning, predictive smoothing, and domain-specific presets
# UPDATED: 2026-01-01
# ==========================================================

import random
import time
import logging
from typing import Dict, Any, Optional, List

from seed.core.track_id_manager import TrackIDManager

# Optional Qbit/HUD integration
try:
    from seed.core.qbit_dialer import qbit_dialer
except ImportError:
    qbit_dialer = None

try:
    from seed.core.hud_engine import HudEngine
except ImportError:
    HudEngine = None

logger = logging.getLogger("SensorFusionCore")
logger.setLevel(logging.INFO)

# --------------------------
# Default sensor type weights (domain-specific)
# --------------------------
SENSOR_TYPE_WEIGHTS = {
    "vision": 0.6,
    "audio": 0.4,
    "temperature": 0.2,
    "user_presence": 0.3,
    "qbit_motion": 0.5,
}

# Historical sensor accuracy for adaptive weighting
SENSOR_HISTORY_WEIGHTS = {}

# Historical sensor values for predictive smoothing
SENSOR_PREDICTIVE_HISTORY = {}


class SensorFusionCore:
    """
    Core fusion logic for multiple sensor channels with:
    - confidence weighting
    - TrackID lineage
    - optional Qbit/HUD push
    - entropy scoring
    - batch fusion
    - confidence normalization
    - adaptive per-sensor weighting
    - predictive smoothing based on recent sensor history
    """

    def fuse(self, cam_qbit: Dict[str, Any], audio_qbit: Dict[str, Any], parent_track_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Fuse camera and audio Qbit sensor data into a single perception event.
        """
        fused_confidence = self._weighted_conf(cam_qbit) + self._weighted_conf(audio_qbit)
        fused_value = max(cam_qbit.get("value", 0.0), audio_qbit.get("value", 0.0))

        # Apply predictive smoothing
        fused_value = self._predictive_smooth(cam_qbit, audio_qbit, fused_value)

        track_id = TrackIDManager.generate(skill_name="SENSOR_FUSION")
        if parent_track_id:
            track_id = f"{track_id}_PARENT-{parent_track_id}"

        entropy = round(random.random() * 0.5 + 0.25, 4)  # 0.25–0.75 entropy

        fused_event = {
            "track_id": track_id,
            "type": "fused_perception",
            "value": fused_value,
            "confidence": round(fused_confidence, 4),
            "sources": [cam_qbit.get("channel"), audio_qbit.get("channel")],
            "entropy": entropy,
            "timestamp": time.time(),
        }

        self._publish_event(fused_event)
        return fused_event

    def fuse_batch(self, sensor_list: List[Dict[str, Any]], parent_track_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Fuse multiple sensor readings (2 or more) into a single perception event.
        Applies per-sensor-type weighting, adaptive historical weighting, predictive smoothing, and normalizes confidence.
        """
        if not sensor_list:
            raise ValueError("No sensors provided for batch fusion.")

        # Normalize confidence
        confs = [s.get("confidence", 0.5) for s in sensor_list]
        max_conf = max(confs) if confs else 1.0
        norm_factor = max_conf if max_conf > 0 else 1.0

        total_weight = 0.0
        weighted_sum = 0.0
        channels = []

        for sensor in sensor_list:
            conf = sensor.get("confidence", 0.5) / norm_factor
            val = sensor.get("value", 0.0)
            sensor_type = sensor.get("type", sensor.get("channel", "unknown"))

            # Combine static and adaptive weights
            static_weight = SENSOR_TYPE_WEIGHTS.get(sensor_type, 0.5)
            adaptive_weight = SENSOR_HISTORY_WEIGHTS.get(sensor_type, 1.0)
            weight = conf * static_weight * adaptive_weight

            total_weight += weight
            weighted_sum += val * weight
            channels.append(sensor.get("channel", "UNKNOWN"))

        fused_value = weighted_sum / total_weight if total_weight else 0.0

        # Apply predictive smoothing across batch
        fused_value = self._predictive_smooth_batch(sensor_list, fused_value)

        fused_confidence = sum(s.get("confidence", 0.5) for s in sensor_list) / len(sensor_list)

        track_id = TrackIDManager.generate(skill_name="SENSOR_BATCH_FUSION")
        if parent_track_id:
            track_id = f"{track_id}_PARENT-{parent_track_id}"

        entropy = round(random.random() * 0.5 + 0.25, 4)

        fused_event = {
            "track_id": track_id,
            "type": "fused_batch_perception",
            "value": fused_value,
            "confidence": round(fused_confidence, 4),
            "sources": channels,
            "entropy": entropy,
            "timestamp": time.time(),
        }

        # Update adaptive weights
        self._update_adaptive_weights(sensor_list, fused_value)

        self._publish_event(fused_event)
        return fused_event

    # --------------------------
    # Weighted confidence
    # --------------------------
    def _weighted_conf(self, sensor: Dict[str, Any]) -> float:
        sensor_type = sensor.get("type", sensor.get("channel", "unknown"))
        static_weight = SENSOR_TYPE_WEIGHTS.get(sensor_type, 0.5)
        adaptive_weight = SENSOR_HISTORY_WEIGHTS.get(sensor_type, 1.0)
        conf = sensor.get("confidence", 0.5)
        return conf * static_weight * adaptive_weight

    # --------------------------
    # Predictive smoothing (single-pair)
    # --------------------------
    def _predictive_smooth(self, *sensors, fused_value: float) -> float:
        for sensor in sensors:
            sensor_type = sensor.get("type", sensor.get("channel", "unknown"))
            history = SENSOR_PREDICTIVE_HISTORY.get(sensor_type, [])
            history.append(sensor.get("value", 0.0))
            if len(history) > 5:
                history.pop(0)
            SENSOR_PREDICTIVE_HISTORY[sensor_type] = history

            # Smooth using simple moving average
            fused_value = (fused_value + sum(history) / len(history)) / 2.0
        return fused_value

    # --------------------------
    # Predictive smoothing for batch
    # --------------------------
    def _predictive_smooth_batch(self, sensor_list: List[Dict[str, Any]], fused_value: float) -> float:
        all_values = []
        for sensor in sensor_list:
            sensor_type = sensor.get("type", sensor.get("channel", "unknown"))
            history = SENSOR_PREDICTIVE_HISTORY.get(sensor_type, [])
            history.append(sensor.get("value", 0.0))
            if len(history) > 5:
                history.pop(0)
            SENSOR_PREDICTIVE_HISTORY[sensor_type] = history
            all_values.extend(history)
        if all_values:
            fused_value = (fused_value + sum(all_values) / len(all_values)) / 2.0
        return fused_value

    # --------------------------
    # Adaptive weighting update
    # --------------------------
    def _update_adaptive_weights(self, sensor_list: List[Dict[str, Any]], fused_value: float):
        for sensor in sensor_list:
            sensor_type = sensor.get("type", sensor.get("channel", "unknown"))
            sensor_value = sensor.get("value", 0.0)
            deviation = abs(sensor_value - fused_value)
            adjustment = max(0.5, 1.0 - deviation)
            SENSOR_HISTORY_WEIGHTS[sensor_type] = adjustment

    # --------------------------
    # Event publishing
    # --------------------------
    def _publish_event(self, fused_event: Dict[str, Any]):
        logger.info(
            f"[SensorFusion] Fused event | TrackID={fused_event['track_id']} | "
            f"Value={fused_event['value']:.4f} | Confidence={fused_event['confidence']:.4f} | Entropy={fused_event['entropy']}"
        )

        if HudEngine:
            try:
                HudEngine.publish(channel="SENSOR_FUSION", payload=fused_event)
            except Exception as e:
                logger.warning(f"[HUD] Failed to publish fused sensor event | TrackID={fused_event['track_id']} | Error={e}")

        if qbit_dialer and hasattr(qbit_dialer, "push_data"):
            try:
                push_func = qbit_dialer.push_data
                if callable(push_func):
                    push_func(fused_event)
            except Exception as e:
                logger.error(f"[QbitDialer] Failed to push fused sensor event | TrackID={fused_event['track_id']} | Error={e}")
