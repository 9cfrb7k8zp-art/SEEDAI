# ==========================================================
# FILE: multi_agent_arbitrator.py
# PATH: SEED_ROOT/seed/core/multi_agent_arbitrator.py
# SYSTEM LAYER: Multi-Agent Arbitration
# VERSION: 1.0
#
#    """
#    Resolves competing intents from multiple agents
#    into a single authoritative intent snapshot.
#
#    Guarantees:
#    - Deterministic resolution
#    - No actuator flooding
#    - TrackID lineage preserved
#    - Headless safe
#    """
# ==========================================================

import time
import threading
import logging
from typing import Dict, List, Optional
from collections import defaultdict

logger = logging.getLogger("MultiAgentArbitrator")


# ==========================================================
# ARBITRATION POLICY DEFAULTS
# ==========================================================

DEFAULT_AGENT_WEIGHTS = {
    "system": 1.0,
    "primary": 0.9,
    "assistant": 0.7,
    "observer": 0.4,
    "external": 0.3,
}

CONFLICT_WINDOW_SEC = 0.25
MIN_CONFIDENCE = 0.2


# ==========================================================
# MULTI-AGENT ARBITRATOR
# ==========================================================

class MultiAgentArbitrator:

    def __init__(
        self,
        agent_weights: Dict[str, float] = None,
        conflict_window: float = CONFLICT_WINDOW_SEC,
    ):
        self.agent_weights = agent_weights or DEFAULT_AGENT_WEIGHTS
        self.conflict_window = conflict_window

        self._lock = threading.Lock()
        self._intent_buffer: Dict[str, List[dict]] = defaultdict(list)
        self._last_emit_ts = 0.0

    # ======================================================
    # INGEST
    # ======================================================

    def ingest(self, intent_event: dict):
        if not isinstance(intent_event, dict):
            return

        intent = intent_event.get("intent")
        confidence = float(intent_event.get("confidence", 0.0))
        agent_id = intent_event.get("agent_id", "unknown")

        if not intent or confidence < MIN_CONFIDENCE:
            return

        with self._lock:
            self._intent_buffer[intent].append(intent_event)

    # ======================================================
    # RESOLVE
    # ======================================================

    def resolve(self) -> Optional[dict]:
        now = time.time()
        if now - self._last_emit_ts < self.conflict_window:
            return None

        with self._lock:
            if not self._intent_buffer:
                return None

            scored_intents = []

            for intent, events in self._intent_buffer.items():
                for e in events:
                    agent_id = e.get("agent_id", "unknown")
                    base_conf = float(e.get("confidence", 0.0))
                    priority = float(e.get("priority", 0.5))
                    qbit = float(e.get("qbit", 0.0))

                    weight = self.agent_weights.get(agent_id, 0.5)

                    score = (
                        base_conf *
                        weight *
                        (0.5 + 0.5 * priority) *
                        (0.5 + 0.5 * qbit)
                    )

                    scored_intents.append((score, e))

            if not scored_intents:
                self._intent_buffer.clear()
                return None

            # Deterministic winner
            scored_intents.sort(key=lambda x: x[0], reverse=True)
            winner = scored_intents[0][1]

            # Cleanup
            self._intent_buffer.clear()
            self._last_emit_ts = now

            winner["_arbitrated"] = True
            winner["_arbitration_ts"] = now
            winner["_arbitration_score"] = scored_intents[0][0]

            logger.info(
                f"[ARBITRATOR] Winner intent={winner.get('intent')} "
                f"agent={winner.get('agent_id')} "
                f"score={scored_intents[0][0]:.3f}"
            )

            return winner

    # ======================================================
    # RESET
    # ======================================================

    def reset(self):
        with self._lock:
            self._intent_buffer.clear()
            self._last_emit_ts = 0.0
