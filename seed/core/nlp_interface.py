# ==========================================================
# FILE: nlp_interface.py
# PATH: SEED_ROOT/seed/core/nlp_interface.py
# VERSION: v09 (TrackID + Qbit Feedback + Limp Mode + Brain Integration)
# LABEL: SEEDNLPInterface
# DESCRIPTION: NLP interface feeding reasoning loop with TrackID lineage, Qbit numeric brain integration, and limp mode
# ==========================================================

import random
import datetime
import asyncio
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger("SEEDNLPInterface")
logger.setLevel(logging.INFO)

try:
    from seed.core.agent_manager import SEEDAgentManager
except ImportError:
    SEEDAgentManager = None

try:
    from seed.core.analytics_engine import SEEDAnalyticsEngine
except ImportError:
    SEEDAnalyticsEngine = None

try:
    from seed.core.qbit_dialer import qbit_dialer
except ImportError:
    qbit_dialer = None

try:
    from seed.core.tracked_data import TrackedData
except ImportError:
    TrackedData = None


# ==========================================================
# DUMMY LEARNING ENGINE
# ==========================================================
class DummyLearningEngine:
    """Simulates a learning engine tracking device success rates and metrics."""

    async def summarize_knowledge(self) -> Dict[str, Any]:
        return {
            "DeviceA": {
                "success_rate": random.uniform(0.5, 1.0),
                "logic_metric": random.uniform(-10, 10),
            },
            "DeviceB": {
                "success_rate": random.uniform(0.3, 0.9),
                "logic_metric": random.uniform(-10, 10),
            },
        }


# ==========================================================
# NLP INTERFACE
# ==========================================================
class NLPInterface:
    """
    NLP Interface v09 for SEED reasoning loop.
    - Async mic toggle + listening
    - TrackID lineage for all events
    - QbitDialer numeric brain feedback
    - Analytics and AgentManager integration
    - Limp mode safe operation
    """

    def __init__(
        self,
        storage_root: str = "./SEED_ROOT",
        agent_manager: SEEDAgentManager = None,
        analytics_engine: SEEDAnalyticsEngine = None,
        limp_mode: bool = False,
    ):
        self.storage_root = storage_root
        self.mic_enabled = False
        self.devices: Dict[str, Any] = {"DeviceA": {}, "DeviceB": {}}
        self.learning_engine = DummyLearningEngine()
        self.agent_manager = agent_manager
        self.analytics_engine = analytics_engine
        self.qbit_dialer = qbit_dialer
        self.limp_mode = limp_mode

    # --------------------------
    # Mic Control
    # --------------------------
    async def toggle_mic(self) -> bool:
        self.mic_enabled = not self.mic_enabled
        track_id = self._generate_track_id("MIC")
        logger.info(f"[NLP] Mic toggled: {self.mic_enabled} | TrackID={track_id}")
        await self._push_to_qbit({"event": "MIC_TOGGLE", "state": self.mic_enabled, "track_id": track_id})
        return self.mic_enabled

    # --------------------------
    # Listen / Observation
    # --------------------------
    async def listen(self) -> Optional[Dict[str, Any]]:
        if not self.mic_enabled:
            return None

        obs_track_id = self._generate_track_id("OBSERVATION")
        device_feedback = await self.learning_engine.summarize_knowledge()
        observation = {
            "track_id": obs_track_id,
            "timestamp": datetime.datetime.now().isoformat(),
            "device_feedback": device_feedback,
            "command": "TEST_COMMAND",
        }

        # Feed numeric brain
        await self._feed_qbit_brain(observation, obs_track_id, signal_type="voice")

        # Analytics Engine
        if self.analytics_engine and not self.limp_mode:
            await self._update_analytics(observation, obs_track_id)

        # Spawn Agent
        if self.agent_manager and not self.limp_mode:
            agent_track_id = self._generate_track_id("AGENT_TASK", parent_track_id=obs_track_id)
            asyncio.create_task(self._spawn_agent_task(observation, agent_track_id))
            logger.info(f"[NLP] Agent spawned | TrackID={agent_track_id}")
        else:
            logger.warning(f"[NLP][LIMP MODE] Observation stored locally | TrackID={obs_track_id}")

        # QbitDialer push
        await self._push_to_qbit({"event": "OBSERVATION", "payload": observation, "track_id": obs_track_id})

        return observation

    async def _spawn_agent_task(self, observation: Dict[str, Any], agent_track_id: str):
        try:
            if self.agent_manager:
                await self.agent_manager.spawn_agent_async(
                    lambda: self._process_command(observation, parent_track_id=agent_track_id),
                    name="NLP_Task",
                    parent_track_id=agent_track_id,
                )
        except Exception as e:
            logger.error(f"[NLP] Agent spawn failed | TrackID={agent_track_id} | Error={e}")

    async def _process_command(self, observation: Dict[str, Any], parent_track_id: Optional[str] = None) -> Dict[str, Any]:
        process_track_id = self._generate_track_id("PROCESS", parent_track_id=parent_track_id)
        await asyncio.sleep(random.uniform(0.01, 0.1))  # simulate processing

        # Feed numeric brain
        await self._feed_qbit_brain(observation, process_track_id, signal_type="cpu")

        # Analytics update
        if self.analytics_engine and not self.limp_mode:
            await self._update_analytics(observation, process_track_id, process=True)
        else:
            logger.warning(f"[NLP][LIMP MODE] Command processed locally | TrackID={process_track_id}")

        # QbitDialer push
        await self._push_to_qbit({"event": "COMMAND_PROCESSED", "payload": observation, "track_id": process_track_id})

        return {"track_id": process_track_id, "status": "processed"}

    # --------------------------
    # Device Management
    # --------------------------
    async def add_device(self, device_id: str) -> Dict[str, Any]:
        if device_id not in self.devices:
            self.devices[device_id] = {}
        track_id = self._generate_track_id("DEVICE_ADD")
        logger.info(f"[NLP] Device added: {device_id} | TrackID={track_id}")
        await self._push_to_qbit({"event": "DEVICE_ADD", "device_id": device_id, "track_id": track_id})
        return self.devices[device_id]

    async def remove_device(self, device_id: str):
        if device_id in self.devices:
            del self.devices[device_id]
            track_id = self._generate_track_id("DEVICE_REMOVE")
            logger.info(f"[NLP] Device removed: {device_id} | TrackID={track_id}")
            await self._push_to_qbit({"event": "DEVICE_REMOVE", "device_id": device_id, "track_id": track_id})

    # --------------------------
    # Analytics Helper
    # --------------------------
    async def _update_analytics(self, observation: Dict[str, Any], track_id: str, process: bool = False):
        try:
            problem_id = f"nlp_{'process' if process else 'obs'}_{int(datetime.datetime.now().timestamp())}"
            outcome = "success" if random.random() > (0.1 if process else 0.2) else "failure"
            if asyncio.iscoroutinefunction(self.analytics_engine.update_problem_metrics):
                await self.analytics_engine.update_problem_metrics(problem_id, outcome)
            else:
                self.analytics_engine.update_problem_metrics(problem_id, outcome)
            logger.info(f"[NLP] Analytics updated | Outcome={outcome} | TrackID={track_id}")
        except Exception as e:
            logger.error(f"[NLP] Analytics update failed | TrackID={track_id} | Error={e}")

    # --------------------------
    # QbitDialer Push
    # --------------------------
    async def _push_to_qbit(self, packet: Dict[str, Any]):
        if self.qbit_dialer and hasattr(self.qbit_dialer, "push_data"):
            try:
                push = self.qbit_dialer.push_data
                if asyncio.iscoroutinefunction(push):
                    await push(packet)
                else:
                    push(packet)
            except Exception as e:
                logger.error(f"[NLP] QbitDialer push failed | Packet={packet} | Error={e}")
        else:
            if self.limp_mode:
                logger.warning(f"[NLP][LIMP MODE] Qbit push skipped | Packet={packet}")
            else:
                logger.error(f"[NLP] QbitDialer unavailable | Packet={packet}")

    # --------------------------
    # Feed Qbit Numeric Brain
    # --------------------------
    async def _feed_qbit_brain(self, observation: Dict[str, Any], track_id: str, signal_type: str = "cpu"):
        if self.qbit_dialer and hasattr(self.qbit_dialer, "buffers"):
            # Increment the buffer for numeric brain learning
            self.qbit_dialer.buffers.setdefault(signal_type, []).append(1.0)
            logger.debug(f"[NLP] Brain signal fed: {signal_type} | TrackID={track_id}")

    # --------------------------
    # TrackID Helper
    # --------------------------
    def _generate_track_id(self, prefix: str = "NLP", parent_track_id: Optional[str] = None) -> str:
        import uuid
        tid = f"{prefix}-{str(uuid.uuid4())[:8]}"
        if parent_track_id:
            tid = f"{tid}_PARENT-{parent_track_id}"
        return tid
