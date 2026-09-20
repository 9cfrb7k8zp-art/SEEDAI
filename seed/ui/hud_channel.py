# ==========================================================
# FILE: hud_channel.py
# PATH: SEED_ROOT/seed/ui/hud_channel.py
# VERSION: 5.1 (POST-SAFE | QBIT-CONTROLLED | TRACK-HARDENED)
# UPDATED: 2026-01-01
# ==========================================================

import logging
import asyncio
import time
from typing import Any, Optional, Callable, Dict

from seed.core.channel_id import ChannelID
from seed.core.track_context import TrackContext
from seed.core.track_id import TrackRegistry

logger = logging.getLogger("HUDChannel")
logger.setLevel(logging.INFO)


class HUDChannel:
    # --------------------------------------------------
    # INIT
    # --------------------------------------------------
    def __init__(
        self,
        name: str = "CORE",
        *,
        domain: str = "SEED",
        group: str = "HUD",
        max_queue_size: int = 2048,
    ):
        self.name = name.upper()
        self.domain = domain.upper()
        self.group = group.upper()

        # Full Channel Identity
        self.channel_id = ChannelID.build(
            self.name,
            domain=self.domain,
            group=self.group,
        )

        self.active = True

        # Output targets
        self.console_enabled = True
        self.gui_adapter = None
        self.remote_adapter = None

        # Optional formatter
        self.format_hook: Optional[Callable[[dict], dict]] = None

        # Per-channel priority filters
        self.channel_filters: Dict[str, int] = {}

        # Async queue
        self._queue = asyncio.Queue(maxsize=max_queue_size)

        # Event loop (POST-safe)
        try:
            self.loop = asyncio.get_running_loop()
            self._owns_loop = False
        except RuntimeError:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self._owns_loop = True

        # Worker task (lazy-safe)
        self._worker_task = self.loop.create_task(self._process_queue())

        # Organized feeds: channel -> seq -> payload
        self._feeds: Dict[str, Dict[int, dict]] = {}

        # Register channel (Qbit + HUD discovery)
        ChannelID.register(
            self.channel_id,
            controller="QBIT",
            metadata={
                "type": "HUD",
                "name": self.name,
                "domain": self.domain,
                "group": self.group,
            },
        )

        logger.info(f"[HUDChannel] Registered {self.channel_id}")

    # ======================================================
    # INTERNAL HELPERS
    # ======================================================
    def _safe_track_context(self):
        try:
            track_id = TrackContext.get()
            parent_id = TrackContext.get_parent()
            return track_id, parent_id
        except Exception:
            return None, None

    # ======================================================
    # PUBLISH API
    # ======================================================
    def publish(
        self,
        event: str,
        payload: Any = None,
        *,
        channel: Optional[str] = None,
        priority: int = 0,
        track_id: Optional[str] = None,
        parent_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        source: str = "SYSTEM",
    ):

        if not self.active:
            return

        resolved_channel = channel or self.channel_id

        # Obey Qbit state
        state = ChannelID.get_state(resolved_channel)
        if state in ("PAUSED", "MUTED"):
            return

        # Resolve Track context (POST-safe)
        ctx_track, ctx_parent = self._safe_track_context()
        resolved_track = track_id or ctx_track
        resolved_parent = parent_id or ctx_parent

        # Generate sequence ID (Qbit-enforced)
        seq = ChannelID.next(
            resolved_channel,
            track_id=resolved_track,
            parent_id=resolved_parent,
        )

        if seq is None:
            return  # blocked by Qbit

        display = {
            "event": event,
            "seq": seq,
            "channel": resolved_channel,
            "priority": priority,
            "source": source,
            "track_id": resolved_track,
            "parent_id": resolved_parent,
            "payload": payload,
            "metadata": metadata or {},
            "timestamp": int(time.time() * 1000),
            "valid_track": bool(
                resolved_track and TrackRegistry.get(resolved_track)
            ),
            "state": state,
        }

        # Priority filtering
        min_priority = self.channel_filters.get(resolved_channel, 0)
        if priority < min_priority:
            return

        # Optional formatting
        if self.format_hook:
            try:
                display = self.format_hook(display)
            except Exception as e:
                logger.warning(f"[HUDChannel] Format hook error: {e}")

        # Store feed
        self._feeds.setdefault(resolved_channel, {})
        self._feeds[resolved_channel][seq] = display

        self._emit(display)

    # ======================================================
    # EMIT
    # ======================================================
    def _emit(self, data: dict):
        if self.console_enabled:
            logger.info(f"[HUD] {data}")

        if self.gui_adapter or self.remote_adapter:
            try:
                self._queue.put_nowait(data)
            except asyncio.QueueFull:
                logger.warning(
                    f"[HUDChannel] Queue full, dropping event: {data.get('event')}"
                )

    # ======================================================
    # ASYNC WORKER
    # ======================================================
    async def _process_queue(self):
        while self.active or not self._queue.empty():
            try:
                data = await self._queue.get()
            except asyncio.CancelledError:
                break

            if self.gui_adapter:
                await self._safe_call(self.gui_adapter.render, data)

            if self.remote_adapter:
                await self._safe_call(self.remote_adapter.send, data)

            self._queue.task_done()

    async def _safe_call(self, fn, *args):
        try:
            if asyncio.iscoroutinefunction(fn):
                await fn(*args)
            else:
                fn(*args)
        except Exception as e:
            logger.warning(f"[HUDChannel] Adapter error: {e}")

    # ======================================================
    # ADAPTER MANAGEMENT
    # ======================================================
    def bind_gui(self, adapter):
        self.gui_adapter = adapter
        logger.info("[HUDChannel] GUI adapter bound")

    def bind_remote(self, adapter):
        self.remote_adapter = adapter
        logger.info("[HUDChannel] Remote adapter bound")

    def set_format_hook(self, hook: Callable[[dict], dict]):
        self.format_hook = hook
        logger.info("[HUDChannel] Format hook set")

    def set_channel_filter(self, channel: str, min_priority: int):
        self.channel_filters[channel] = min_priority
        logger.info(f"[HUDChannel] Filter: {channel} >= {min_priority}")

    # ======================================================
    # FEED ACCESS
    # ======================================================
    def get_feed(self, channel: Optional[str] = None) -> Dict[str, dict]:
        if channel:
            return self._feeds.get(channel, {})
        return self._feeds

    # ======================================================
    # LIFECYCLE
    # ======================================================
    async def flush(self, timeout: float = 5.0):
        start = self.loop.time()
        while not self._queue.empty():
            await asyncio.sleep(0.01)
            if self.loop.time() - start > timeout:
                logger.warning("[HUDChannel] Flush timeout")
                break

    def stop(self):
        self.active = False

        if self._worker_task:
            self._worker_task.cancel()

        logger.info("[HUDChannel] Stopped")

# ==========================================================
# END FILE
# ==========================================================
