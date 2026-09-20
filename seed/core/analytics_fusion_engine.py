# ==========================================================
# FILE: analytics_fusion_engine.py
# PATH: SEED_ROOT/seed/core/analytics_fusion_engine.py
# SEED Analytics Fusion Engine v2.2
#
# PURPOSE:
#   - Fuse multiple QBIT insights per channel
#   - Apply trust weighting and smoothing
#   - Generate actionable analytics for higher cognition
#   - Emit fused events via EventBus
#
# FIXED (v2.2):
#   - Guaranteed async worker startup
#   - Normalized event name (ANALYTICS_FUSED)
#   - Safer ingestion & queue handling
# ==========================================================

import logging
import asyncio
from collections import defaultdict, deque
from copy import deepcopy

logger = logging.getLogger("AnalyticsFusionEngine")


class AnalyticsFusionEngine:
    def __init__(self, event_bus=None, history_size=20):
        self.event_bus = event_bus
        self.history_size = history_size

        # Per-channel fused history
        self.fused_history = defaultdict(lambda: deque(maxlen=self.history_size))

        # Async ingestion queue
        self._ingest_queue = asyncio.Queue()
        self._running = False
        self._worker_task = None
        self.loop = asyncio.get_event_loop()

    # -------------------- Ingest Insights --------------------
    def ingest_insight(self, insight: dict):

        if not isinstance(insight, dict):
            logger.warning("[Fusion] Invalid insight type")
            return

        if "channel" not in insight or "weighted_value" not in insight:
            logger.warning("[Fusion] Invalid insight, missing fields")
            return

        try:
            self._ingest_queue.put_nowait(insight)
        except Exception as e:
            logger.warning(f"[Fusion] Failed to enqueue insight: {e}")

    # -------------------- Worker Loop --------------------
    async def _worker_loop(self):
        logger.info("[Fusion] Worker loop running")
        while self._running:
            try:
                insight = await self._ingest_queue.get()
                await asyncio.to_thread(self._process_insight, insight)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"[Fusion] Worker loop exception: {e}")

            await asyncio.sleep(0.001)

    # -------------------- Process & Fuse --------------------
    def _process_insight(self, insight: dict):
        channel = insight["channel"]

        # Store in fused history
        self.fused_history[channel].append(insight)

        history = self.fused_history[channel]
        count = len(history)

        if count == 0:
            return

        # Compute fused metrics
        weighted_sum = sum(e.get("weighted_value", 0.0) for e in history)
        confidence_sum = sum(e.get("confidence", 0.0) for e in history)
        trust_sum = sum(e.get("trust", 0.0) for e in history)

        fused_packet = {
            "channel": channel,
            "fused_value": weighted_sum / count,
            "avg_confidence": confidence_sum / count,
            "avg_trust": trust_sum / count,
            "sample_count": count,
            "raw_history": deepcopy(list(history)),
            "timestamp": insight.get("timestamp"),
            "_source": "AnalyticsFusionEngine"
        }

        # Emit fused analytics event
        try:
            if self.event_bus:
                self.event_bus.emit("ANALYTICS_FUSED", fused_packet)
        except Exception as e:
            logger.warning(f"[Fusion] Failed to emit fused packet: {e}")

        logger.info(
            f"[Fusion] Fused → {channel} "
            f"value={fused_packet['fused_value']:.3f} "
            f"conf={fused_packet['avg_confidence']:.3f} "
            f"trust={fused_packet['avg_trust']:.3f}"
        )

    # -------------------- Async Control --------------------
    def start_async(self):
        if self._running:
            return

        self._running = True
        self._worker_task = self.loop.create_task(self._worker_loop())
        logger.info("[Fusion] Async worker started")

    def stop_async(self):
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
        logger.info("[Fusion] Async worker stopped")

    # -------------------- Accessors --------------------
    def get_fused_history(self, channel: str):
        return list(self.fused_history.get(channel, []))

    def get_all_channels(self):
        return list(self.fused_history.keys())

    def get_latest_fused(self, channel: str):
        history = self.fused_history.get(channel)
        if history:
            return deepcopy(history[-1])
        return None
