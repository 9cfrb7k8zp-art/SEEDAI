# ==========================================================
# FILE: ai_core.py
# PATH: SEED_ROOT/seed/core/ai_core.py
# MODULE: SEED AI Core Integration (Runtime + Qbit + Reasoning)
# VERSION: 1.1
# UPDATED: 2026-01-07
# ==========================================================

import time
import threading
import logging
from copy import deepcopy

from seed.core.intent_engine import IntentEngine
from seed.core.init_event import SeedInitEvent

logger = logging.getLogger("SEED.AI")
logger.setLevel(logging.INFO)

# ==========================================================
# SEED AI Core
# ==========================================================
class SEEDAI:
    """
    Central AI brain for SEED OS.
    Connects IntentEngine, QbitDialer, and AgentManager.
    Runs reasoning loop in background.
    """

    def __init__(self, event_bus, seed_core, agent_manager, qbit_dialer, speed=1.0):
        self.event_bus = event_bus
        self.seed_core = seed_core
        self.agent_manager = agent_manager
        self.qbit_dialer = qbit_dialer
        self.speed = speed

        # Instantiate IntentEngine
        self.intent_engine = IntentEngine(
            analytics_engine=getattr(seed_core, "analytics_engine", None),
            agent_manager=agent_manager,
            event_bus=event_bus,
            qbit_dialer=qbit_dialer,
            seed_core=seed_core,
            speed=speed
        )

        self._active = False
        self._shutdown = False

        # Subscribe to SEED boot completion
        event_bus.subscribe("SEED_INIT_COMPLETE", self._on_seed_boot)

        logger.info("[SEEDAI] Initialized — waiting for SEED boot completion")

    # ======================================================
    # Boot Handler
    # ======================================================
    def _on_seed_boot(self, payload=None):
        logger.info("[SEEDAI] SEED system boot complete — starting reasoning loop")
        self.seed_core.allow_thinking_loop = True
        self._active = True

        # Optional: inject initial intent
        self.intent_engine.score_intents(source="boot")

        # Start background reasoning thread
        threading.Thread(target=self._ai_loop, daemon=True).start()

    # ======================================================
    # Background AI Loop
    # ======================================================
    def _ai_loop(self, update_interval=0.05):
        while not self._shutdown:
            if not self._active:
                time.sleep(0.2)
                continue

            try:
                if getattr(self.seed_core, "allow_thinking_loop", False):
                    # Run intent scoring
                    dominant_intent, fused_scores = self.intent_engine.score_intents(
                        source="background"
                    )

                    # Send feedback to Qbit Dialer
                    if self.qbit_dialer and hasattr(self.qbit_dialer, "push_data"):
                        self.qbit_dialer.push_data({
                            "dominant_intent": dominant_intent,
                            "scores": deepcopy(fused_scores),
                            "timestamp": time.time(),
                            "source": "SEEDAI"
                        })

                    # Optionally trigger AgentManager for reasoning tasks
                    if self.agent_manager and hasattr(self.agent_manager, "trigger_skill_chain_safe"):
                        try:
                            loop = getattr(self.agent_manager, "loop", None)
                            if loop and loop.is_running():
                                threading.Thread(
                                    target=lambda: asyncio.run_coroutine_threadsafe(
                                        self.agent_manager.trigger_skill_chain_safe(
                                            f"{dominant_intent}_sequence",
                                            {"dominant_intent": dominant_intent, "speed": self.speed},
                                        ),
                                        loop
                                    ),
                                    daemon=True
                                ).start()
                        except Exception as e:
                            logger.warning(f"[SEEDAI] AgentManager dispatch failed: {e}")

            except Exception as e:
                logger.warning(f"[SEEDAI Loop] {e}")

            time.sleep(update_interval / max(self.speed, 0.01))

    # ======================================================
    # Shutdown
    # ======================================================
    def shutdown(self):
        if self._shutdown:
            return
        logger.info("[SEEDAI] Shutting down AI brain")
        self._shutdown = True
        self._active = False

# ==========================================================
# Global AI Brain Instance
# ==========================================================
ai_brain = None

def init_ai(event_bus, seed_core, agent_manager, qbit_dialer, speed=1.0):
    """
    Initialize the SEED AI brain after SEED boot.
    """
    global ai_brain
    if ai_brain is None:
        ai_brain = SEEDAI(
            event_bus=event_bus,
            seed_core=seed_core,
            agent_manager=agent_manager,
            qbit_dialer=qbit_dialer,
            speed=speed
        )
    return ai_brain

# ==========================================================
# END FILE: ai_core.py v1.1
# ==========================================================
