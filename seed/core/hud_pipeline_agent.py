# ==========================================================
# FILE: hud_pipeline_agent.py
# PATH: SEED_ROOT/seed/core/hud_pipeline_agent.py
# VERSION: v2.0.0 (BOOT-STABLE + TRACKED + ASYNC-SAFE + HUD-ID + LIVE HUD FEED + UI-INTEGRATED + TRACKEDATA-INTEGRATION)
# UPDATED: 2025-12-30
# ==========================================================

import asyncio
import logging
from seed.core.track_id_manager import TrackIDManager
from seed.core.qbit_dialer import QbitDialer
from seed.core.sparkplug_loader import SparkPlugLoader
from seed.core.agent_manager import AgentManager
from seed.core.tracked_data import TrackedData


logger = logging.getLogger("HUDPipelineAgent")
logger.setLevel(logging.INFO)

# ---------------------------------------------------------
# HUD Pipeline Agent
# ---------------------------------------------------------
class HUDPipelineAgent:
    """
    Handles HUD input/output feed distribution:
    - Receives updates from modules via EventBus
    - Uses TrackIDManager for traceable events
    - Integrates QbitDialer for weighted prioritization
    - SparkPlugLoader for skill execution
    - Supports Limp Mode switch for safe degraded operation
    - Prepares feeds for HUD UI overlay
    - Provides live feed routing with module IDs, resonance, alert highlights, and tracked TrackIDs
    """

    def __init__(self, event_bus, agent_manager: AgentManager,
                 qbit_dialer: QbitDialer = None,
                 sparkplug_loader: SparkPlugLoader = None,
                 track_manager: TrackIDManager = None,
                 hud_overlay=None,
                 limp_mode: bool = False):

        self.event_bus = event_bus
        self.agent_manager = agent_manager
        self.qbit_dialer = qbit_dialer
        self.sparkplug_loader = sparkplug_loader
        self.track_manager = track_manager
        self.hud_overlay = hud_overlay
        self.limp_mode = limp_mode

        self.hud_feeds = {}  # module_name -> latest HUD data
        self._running = False
        self._loop_task = None

        # Subscribe to EventBus for HUD updates
        self.event_bus.subscribe("HUD_FEED_UPDATE", self._on_hud_feed_update)

    # ---------------------------------------------------------
    async def _process_feed(self, module_name, feed_data, domain="S"):
        """Process incoming HUD feed, apply Qbit weighting & SparkPlug skills, generate TrackID"""

        if self.limp_mode:
            logger.warning(f"[HUD] Limp mode active. Skipping processing for {module_name}")
            return

        # TrackID generation
        parent_id = feed_data.get("parent_track_id")
        track_info = TrackedData.generate_input_track(
            category=feed_data.get("category", module_name),
            domain=domain,
            parent_id=parent_id,
            track_manager=self.track_manager,
            actuator_bridge=True,
            emit_hud=True
        )

        track_id = track_info["track_id"]

        # Qbit adjustment
        resonance = feed_data.get("resonance", 0.5)
        if self.qbit_dialer:
            qbit_value = self.qbit_dialer.calculate()
            if isinstance(qbit_value, (float, int)):
                resonance = (resonance + qbit_value) / 2.0

        # Store feed
        self.hud_feeds[module_name] = {
            "data": feed_data,
            "resonance": resonance,
            "track_id": track_id,
            "domain": domain,
            "stream": track_info.get("stream"),
            "hud_channel": track_info.get("hud_channel"),
            "actuator_bridge": track_info.get("actuator_bridge"),
            "timestamp": track_info.get("timestamp")
        }

        # Execute optional SparkPlug skill
        if self.sparkplug_loader:
            TrackContext.push("HUD")
            try:
                await self.sparkplug_loader.execute_skill(
                    "hud_pipeline_process",
                    {
                        "module": module_name,
                        "feed": feed_data,
                        "resonance": resonance,
                        "track_info": track_info
                    }
                )
            finally:
                TrackContext.pop()

        # Forward feed to HUD UI overlay if available
        if self.hud_overlay:
            self.hud_overlay.update_feed(
                module_name=module_name,
                feed_data=feed_data,
                resonance=resonance,
                track_id=track_id,
                domain=domain,
                stream=track_info.get("stream"),
                hud_channel=track_info.get("hud_channel"),
                actuator_bridge=track_info.get("actuator_bridge")
            )

        # Publish to EventBus for any other listeners
        self.event_bus.publish(
            "HUD_UI_UPDATE",
            payload={
                "module": module_name,
                "feed": feed_data,
                "resonance": resonance,
                "track_id": track_id,
                "domain": domain,
                "stream": track_info.get("stream"),
                "hud_channel": track_info.get("hud_channel"),
                "actuator_bridge": track_info.get("actuator_bridge"),
                "timestamp": track_info.get("timestamp")
            }
        )

        logger.info(f"[HUD] Processed feed from {module_name} | track_id={track_id} | domain={domain}")

    # ---------------------------------------------------------
    def _on_hud_feed_update(self, payload):
        """EventBus callback for HUD feed updates"""
        module_name = payload.get("module", "unknown")
        feed_data = payload.get("data", {})
        domain = payload.get("domain", "S")  # default to S (SeedCore)

        try:
            loop = asyncio.get_running_loop()
            asyncio.run_coroutine_threadsafe(
                self._process_feed(module_name, feed_data, domain), loop
            )
        except RuntimeError:
            asyncio.create_task(self._process_feed(module_name, feed_data, domain))

    # ---------------------------------------------------------
    async def run_loop(self, update_interval=0.05):
        """Main loop for HUD pipeline agent"""
        self._running = True
        logger.info("[HUD] Pipeline agent loop started")
        while self._running:
            try:
                # Periodically push all feeds to HUD overlay
                if self.hud_overlay:
                    self.route_feeds_to_ui()
                await asyncio.sleep(update_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[HUD] Loop error: {e}")

    # ---------------------------------------------------------
    def start(self, update_interval=0.05):
        """Start the async loop safely"""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        self._loop_task = loop.create_task(self.run_loop(update_interval))
        logger.info("[HUD] Pipeline agent started")

    # ---------------------------------------------------------
    async def stop(self):
        """Stop the HUD pipeline agent"""
        self._running = False
        if self._loop_task:
            self._loop_task.cancel()
        logger.info("[HUD] Pipeline agent stopped")

    # ---------------------------------------------------------
    def get_latest_feed(self, module_name):
        """Retrieve the latest HUD feed for a module"""
        return self.hud_feeds.get(module_name, None)

    # ---------------------------------------------------------
    def enable_limp_mode(self):
        """Activate limp mode for safe operation"""
        self.limp_mode = True
        logger.warning("[HUD] Limp mode enabled")

    # ---------------------------------------------------------
    def disable_limp_mode(self):
        """Deactivate limp mode"""
        self.limp_mode = False
        logger.info("[HUD] Limp mode disabled")

    # ---------------------------------------------------------
    def clear_feed(self, module_name):
        """Clear stored HUD feed for a module"""
        if module_name in self.hud_feeds:
            del self.hud_feeds[module_name]
            logger.info(f"[HUD] Cleared feed for module {module_name}")

    # ---------------------------------------------------------
    def route_feeds_to_ui(self):
        """Push all HUD feeds to UI overlay"""
        if not self.hud_overlay:
            return

        for module_name, feed_info in self.hud_feeds.items():
            self.hud_overlay.update_feed(
                module_name=module_name,
                feed_data=feed_info.get("data", {}),
                resonance=feed_info.get("resonance", 0.5),
                track_id=feed_info.get("track_id"),
                domain=feed_info.get("domain"),
                stream=feed_info.get("stream"),
                hud_channel=feed_info.get("hud_channel"),
                actuator_bridge=feed_info.get("actuator_bridge")
            )
        logger.info("[HUD] Routed all HUD feeds to UI overlay")
