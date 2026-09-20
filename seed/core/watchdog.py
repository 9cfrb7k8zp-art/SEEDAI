# ==========================================================
# FILE: watchdog.py
# PATH: SEED_ROOT/seed/core/watchdog.py
# VERSION: 2.3 (TRACKID + QBIT + ASYNC PATCHED + PARENT TRACKID)
# UPDATED: 2025-12-30
# ==========================================================

import threading
import time
import asyncio

from seed.core.shutdown_recovery import SEEDShutdownRecovery
from seed.core.channel_id import generate_track_id


class SEEDWatchdog:
    def __init__(self, event_bus, emit, qbit=None, heartbeatemitter=None, device_manager=None, shutdown_recovery=SEEDShutdownRecovery, registry=None, qbit_dialer=None, check_interval=5):
        from seed.core.event_bus import SYSTEM_WARNING, SYSTEM_SHUTDOWN
        self.event_bus = event_bus
        self.heartbeatemitter = heartbeatemitter
        self.channel_id = generate_track_id
        self.device_manager = device_manager
        self.shutdown_manager = shutdown_recovery() if isinstance(shutdown_recovery, type) else shutdown_recovery
        self.registry = registry
        if self.registry is None:
            try:
                from seed.skills.action_registry import _registered_actions
                self.registry = _registered_actions()
            except Exception:
                self.registry = None
        self.qbit = qbit
        self.qbit_dialer = qbit_dialer
        self.check_interval = max(0.5, float(check_interval))
        self.emit = emit if callable(emit) else (lambda event_type, payload=None: None)
        self.HEARTBEAT_EVENT = "HEARTBEAT"
        self.SYSTEM_WARNING = SYSTEM_WARNING
        self.SYSTEM_SHUTDOWN = SYSTEM_SHUTDOWN

        # Internal tracking
        self._running = False
        self._thread = None
        self._heartbeats = {}            # Heartbeats per module
        self._failures = {}              # Failure counts
        self._last_failure_time = {}     # Debouncing

        # Device callbacks
        if self.device_manager is not None:
            add_callback = getattr(self.device_manager, "add_event_callback", None)
            if callable(add_callback):
                add_callback(self._on_device_input)

        # EventBus subscriptions remain passive and reference-only.
        if self.event_bus is not None:
            on = getattr(self.event_bus, "on", None)
            if callable(on):
                on("hud.command", self.handle_hud_command)
            subscribe = getattr(self.event_bus, "subscribe", None)
            if callable(subscribe):
                subscribe(self.HEARTBEAT_EVENT, self._on_heartbeat)
                subscribe(self.SYSTEM_WARNING, self._on_warning)

        print("[WATCHDOG] Initialized with full monitoring and device integration.")

    # -----------------------------
    # Device input callback
    # -----------------------------
    def _on_device_input(self, device_id: str, data: str, parent_track_id=None):
        label = self.device_manager.device_labels.get(device_id, device_id)
        track_id = generate_track_id("DEVICE")
        print(f"[WATCHDOG][DEVICE INPUT] {label} ({device_id}): {data} | ID={track_id}")
        self.event_bus.publish("device.input", {"device_id": device_id, "label": label, "data": data, "track_id": track_id})
        if self.qbit_dialer:
            self.qbit_dialer.submit_track(track_id, parent_id=parent_track_id)

    # -----------------------------
    # EventBus callbacks
    # -----------------------------
    def _on_heartbeat(self, event, parent_track_id=None):
        payload = event.get("payload", {})
        module = payload.get("module")
        if module:
            self._heartbeats[module] = payload

    def _on_warning(self, event, parent_track_id=None):
        payload = event.get("payload", {})
        source = payload.get("source", "unknown")
        error = payload.get("error") or payload.get("message") or "unspecified"

        # Debounce repeated warnings within 2 seconds
        now = time.time()
        last_time = self._last_failure_time.get(source, 0)
        if now - last_time < 2.0:
            return
        self._last_failure_time[source] = now

        track_id = generate_track_id("WATCHDOG")
        print(f"[WATCHDOG] Warning from {source}: {error} | ID={track_id}")
        if self.qbit_dialer:
            self.qbit_dialer.submit_track(track_id, parent_id=parent_track_id)

        self._record_failure(source, reason=error, parent_track_id=track_id)

    # -----------------------------
    # HUD Command Handler
    # -----------------------------
    def handle_hud_command(self, packet, parent_track_id=None):
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        for device_id in packet.get("targets", []):
            asyncio.run_coroutine_threadsafe(
                self.device_manager.send_output(device_id, packet.get("payload")),
                loop
            )
            label = self.device_manager.device_labels.get(device_id, device_id)
            track_id = generate_track_id("HUD")
            print({
                "status": "ack",
                "device": device_id,
                "label": label,
                "intent": packet.get("intent"),
                "payload": packet.get("payload"),
                "track_id": track_id
            })
            if self.qbit_dialer:
                self.qbit_dialer.submit_track(track_id, parent_id=parent_track_id)

    # -----------------------------
    # Monitor loop for heartbeats
    # -----------------------------
    def _monitor_loop(self):
        print("[WATCHDOG] Monitor loop started.")
        while self._running:
            now = time.time()
            if self.registry is not None:
                entries = self.registry.all() if hasattr(self.registry, "all") else []
                for module, config in entries:
                    hb = self._heartbeats.get(module)
                    if not hb:
                        continue
                    age = now - hb.get("timestamp", now)
                    if age > config.get("heartbeat_timeout", 10):
                        self._record_failure(module, reason="heartbeat timeout")
            time.sleep(self.check_interval)
        print("[WATCHDOG] Monitor loop stopped.")

    # -----------------------------
    # Failure handling
    # -----------------------------
    def _record_failure(self, module, reason, parent_track_id=None):
        count = self._failures.get(module, 0) + 1
        self._failures[module] = count

        track_id = generate_track_id("WATCHDOG")
        print(f"[WATCHDOG] Failure #{count} in {module}: {reason} | ID={track_id}")
        if self.qbit_dialer:
            self.qbit_dialer.submit_track(track_id, parent_id=parent_track_id)

        config = self.registry.get(module) if self.registry is not None and hasattr(self.registry, "get") else None
        if not config:
            return

        if count == 1 and config.get("restartable", False) and self.shutdown_manager is not None:
            self.shutdown_manager.restart_module(module)
            print(f"[WATCHDOG] Restarted module {module} | ID={track_id}")
            return
        if count >= 3 and config.get("critical", False) and self.shutdown_manager is not None:
            print(f"[WATCHDOG] CRITICAL FAILURE: {module} | ID={track_id}")
            self.shutdown_manager.emergency_recover()
            return
        if count >= 5:
            print("[WATCHDOG] SYSTEM UNSTABLE — SHUTDOWN")
            if self.event_bus is not None:
                self.event_bus.publish(self.SYSTEM_SHUTDOWN)
            if self.shutdown_manager is not None:
                self.shutdown_manager.shutdown_all()

    # -----------------------------
    # Start / Stop
    # -----------------------------
    def start(self):
        if self._running:
            return
        self._running = True

        # Device initialization is optional and only scheduled when the
        # supplied runtime loop is actually running.
        if self.device_manager is not None:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None
            if loop is not None and hasattr(self.device_manager, "initialize"):
                loop.create_task(self.device_manager.initialize())

        # Start monitoring thread
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        print("[WATCHDOG] Started.")

    def stop(self):
        self._running = False
        if self.device_manager is not None:
            stop_polling = getattr(self.device_manager, "stop_polling", None)
            if callable(stop_polling):
                stop_polling()
        if self._thread:
            self._thread.join()
            self._thread = None
        print("[WATCHDOG] Stopped.")
