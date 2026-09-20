# =====================================================
# FILE: seed_init_full.py
# PATH: SEED_ROOT/seed_init_full.py
# SYSTEM: SEED AI OS
# COMPONENT: SEEDCore
# VERSION: 5.1.0
# BUILD: LIFECYCLE-SAFE / TK-SAFE / QBIT-SAFE / BACKUP-SAFE
# =====================================================

# """SEEDCore integration layer.
 
# This module deliberately does NOT create a Tk root at import time and does
# not start background work from the constructor.  Boot owns lifecycle start.
# DEVHUD/Tk is attached explicitly and only from the process main thread.
#
# Backup policy:
#    * never on import
#    * never in a tight loop
#    * first backup only when ``mark_seed_ready()`` is called
#    * subsequent backups no more often than once per 24 hours
#    * destination defaults to G:\\SEED_BACKUPS
#    * backup work is performed in a single daemon thread and cannot overlap
#"""
# ===========================================================

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import os
import shutil
import sys
import threading
import time
import uuid
from copy import deepcopy
from pathlib import Path
from queue import Queue, Empty
from typing import Any, Callable, List, Optional

import psutil

try:
    import resource  # Unix only
except ImportError:
    resource = None

import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox, Entry

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

from seed.core.authorization import AuthorizationEngine
from seed.core.authorization_helpers import PermissionManager
from seed.hud.view_tk import HUDView
from seed.core.fat_layer import FATLayer
from seed.core.fat_persistence import FATPersistence
from seed.ui.fat_hud_adapter import FATHUDAdapter
from seed.core.qbit import Qbit
from seed.network.network_manager import NetworkManager
from seed.core.agent_manager import AgentManager
from seed.core.voice_engine import SEEDVoiceEngine
from seed.core.system_commentary import SEEDSystemCommentary
from seed.core.permission_record import PermissionRecord as PermissionGate
from seed.skills.module_registry import ModuleRegistry
from seed.core.dialers.qbit_dialer import QbitDialer
from seed.core.heartbeat import Heartbeat
from COM.qtv import QuantumTV

log = logging.getLogger("SEEDCore")

HUD_HTML_PATH = "seed/ui/hudwebui.html"
DEFAULT_BACKUP_ROOT = r"G:\SEED_BACKUPS"
BACKUP_INTERVAL_SEC = 24 * 60 * 60


def gen_track_id(prefix="SEED"):
    return f"{prefix}-{str(uuid.uuid4())[:8]}"


def handle_loop_control(payload):

    if not isinstance(payload, dict):
        return
    action = str(payload.get("action", "")).lower()
    reason = payload.get("reason")
    qbit_loop = payload.get("loop")
    if not qbit_loop:
        return
    try:
        if action == "pause" and hasattr(qbit_loop, "pause"):
            qbit_loop.pause(reason=reason)
        elif action == "resume" and hasattr(qbit_loop, "resume"):
            qbit_loop.resume()
        elif action == "stop" and hasattr(qbit_loop, "stop"):
            qbit_loop.stop()
    except Exception:
        log.exception("[SEEDCore] LOOP_CONTROL failed: %s", action)

# =====================================================
# Helpers
# =====================================================


def ensure_keys_dir():
    key_dir = r"C:\SEED_ROOT\keys"
    os.makedirs(key_dir, exist_ok=True)
    return key_dir


def generate_ed25519_key():
    key_dir = ensure_keys_dir()
    private_key = Ed25519PrivateKey.generate()
    pem_path = os.path.join(key_dir, "seed_private.key")
    raw_path = os.path.join(key_dir, "seed_private.raw")

    # Save PEM
    with open(pem_path, "wb") as f:
        f.write(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
        )

    # Save RAW
    with open(raw_path, "wb") as f:
        f.write(
            private_key.private_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PrivateFormat.Raw,
                encryption_algorithm=serialization.NoEncryption()
            )
        )

    logger.info(f"[KeyGen] Ed25519 key generated: PEM={pem_path}, RAW={raw_path}")
    return private_key


def load_seed_private_key(path: str) -> bytes:
    if not os.path.exists(path):
        logger.warning(f"[KeyLoad] Key missing at {path}, regenerating...")
        private_key = generate_ed25519_key()
        return private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption()
        )

    with open(path, "rb") as f:
        data = f.read()

    if len(data) == 32:
        return data

    try:
        key = serialization.load_pem_private_key(data, password=None)
        raw_bytes = key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption()
        )
        if len(raw_bytes) != 32:
            raise ValueError(f"Loaded PEM key is not 32 bytes (got {len(raw_bytes)})")
        return raw_bytes
    except Exception as e:
        logger.warning(f"[KeyLoad] PEM load failed: {e}, regenerating key...")
        private_key = generate_ed25519_key()
        return private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption()
        )


class SEEDCore(ttk.Frame):


    DEEP_SCAN_THROTTLE = 30.0

    def __init__(
        self,
        emit,
        parent,
        qbit_loop,
        ethics_manager,
        intent_engine,
        memory_crystallizer,
        orchestrator_command,
        loop=None,
        track_system=None,
        event_name=None,
        qbit_dialer=None,
        track_context=None,
        track_id=None,
        task_id=None,
        fat=None,
        payload=None,
        hud=HUDView,
        quantum_tv=QuantumTV,
        heartbeat=Heartbeat,
        module_registry=ModuleRegistry,
        heartbeatemitter=None,
        analytics_engine=None,
        channel_manager=None,
        agent_manager=AgentManager,
        skills_root="./seed/core/skills",
        storage_root="./SEED_ROOT",
        device_id="Core",
        hud_interface=None,
        fat_layer=FATLayer,
        fat_hud=None,
        health_monitor=None,
        fat_hud_adapter=FATHUDAdapter,
        fat_disk=FATPersistence,
        network_manager=NetworkManager,
        private_key_bytes=None,
        event_bus=None,
        qbit=Qbit,
        fiveg=None,
        backup_root=DEFAULT_BACKUP_ROOT,
        backup_interval_sec=BACKUP_INTERVAL_SEC,
        auto_backup=True,
        defer_optional_wiring=True,
        **kwargs,
    ):
        if parent is None:
            raise ValueError("SEEDCore requires a Tk parent/root created by the main thread")
        if threading.current_thread() is not threading.main_thread():
            raise RuntimeError("SEEDCore Tk construction must occur on the main thread")

        super().__init__(parent)

        self.root = parent
        self.hud = hud
        self.device_id = device_id
        self.storage_root = os.path.abspath(storage_root)
        self.skills_root = skills_root
        self.private_key_bytes = private_key_bytes or {}
        self.emit = event_bus.emit or (lambda *a, **k: None)
        self.loop = loop
        self.async_loop = loop if loop is not None else self._get_running_loop()
        self.track_id = track_id or str(uuid.uuid4())
        self.task_id = task_id or str(uuid.uuid4())
        self.track_context = track_context or (lambda event, msg, priority=None: None)
        self.payload = payload
        self.event_name = event_name
        self.orchestrator_command = orchestrator_command
        self.event_bus = event_bus
        self.qbit_loop = qbit_loop
        self.qbit = None if inspect.isclass(qbit) else qbit
        self.qbit_dialer = qbit_dialer if not inspect.isclass(qbit_dialer) else None
        self.heartbeat = None
        self.heartbeatemitter = heartbeatemitter
        self.module_registry = None if inspect.isclass(module_registry) else module_registry
        self.memory_crystallizer = memory_crystallizer
        self.health_monitor = None if inspect.isclass(health_monitor) else health_monitor
        self.track_system = track_system
        self.channel_manager = channel_manager
        self.fat = fat
        self.fat_hud = fat_hud
        self._fat_layer_factory = fat_layer
        self._fat_disk_factory = fat_disk
        self._fat_hud_adapter_factory = fat_hud_adapter
        self._agent_manager_factory = agent_manager
        self._heartbeat_factory = heartbeat
        self._network_manager_factory = network_manager

        # IMPORTANT: expose the concrete dependency before _wire_core().
        # _wire_core() may lazily construct EthicsManager when the supplied
        # value is None, so the instance attribute must always exist first.
        self.ethics_manager = None if inspect.isclass(ethics_manager) else ethics_manager
        self._ethics_manager_factory = ethics_manager

        self._module_registry_factory = module_registry
        self._health_monitor_factory = health_monitor
        self._qbit_factory = qbit
        self.hud_interface = hud_interface
        self.fiveg = fiveg
        self.network_manager = network_manager
        self.network = None
        self.fat_layer = None
        self.fat_disk = None
        self.fat_hud_adapter = None
        self.device_manager = None
        self.sparkplug = None
        self.actuator_engine = None
        self.agent_manager = None
        self.memory_manager = None
        self.skill_memory = None
        self.analytics_engine = analytics_engine
        self.intent_engine = None if inspect.isclass(intent_engine) else intent_engine
        self.core_system = None
        self.audio_modem_manager = None
        self.voice_engine = None
        self.commentary = None
        self.quantum_tv = None
        self.permission_gate = None
        self.permission_manager = None
        self.light_scan_skill = None
        self.deep_scan_skill = None
        self.sparkplug_loader = None
        self.analytics = analytics_engine
        self._fat_queue: asyncio.Queue | None = None
        self._fat_worker_task = None
        self._backup_maintenance_task = None
        self._intent_lock = None
        self._current_intent_snapshot = {
            "intent": "idle", "dominant_intent": "idle", "intent_scores": {},
            "resonance": 0.5, "timestamp": time.time()
        }
        self._event_subscriptions = []
        self._started = False
        self._stopping = False
        self._stopped = False
        self._ready = False
        self._hud_attached = False
        self._device_poll_started = False
        self._backup_lock = threading.Lock()
        self._backup_thread = None
        self._backup_last = 0.0
        self._backup_pending = False
        self._backup_root = os.path.abspath(backup_root) if backup_root else DEFAULT_BACKUP_ROOT
        self._backup_interval_sec = max(3600.0, float(backup_interval_sec))
        self._auto_backup = bool(auto_backup)
        # Constructor must stay bounded: heavy optional services are wired by start().
        # main3.py owns the authoritative runtime; this flag prevents legacy-style
        # constructor fan-out from stalling the boot thread.
        self._defer_optional_wiring = bool(defer_optional_wiring)
        self.event_log: list = []
        self.seed_init_event = None
        self.oracle = None
        self.compute_brain = None
        self.transformer_brain = None
        self.ai_model_oracle = None
        self.ai_input_weights = {}

        self._safe_imports()
        self._wire_core()

        # Lifecycle invariant: runtime wiring must always see these attributes.
        if not hasattr(self, "ethics_manager"):
            self.ethics_manager = None
        if not hasattr(self, "intent_engine"):
            self.intent_engine = None
        if not hasattr(self, "memory_crystallizer"):
            self.memory_crystallizer = memory_crystallizer

        self._register_event_handlers()

        log.info("[SEEDCore] constructed; lifecycle start deferred")

    # ---------------------------------------------------------
    # Lifecycle / safety helpers
    # ---------------------------------------------------------
    @staticmethod
    def _get_running_loop():
        try:
            return asyncio.get_running_loop()
        except RuntimeError:
            return None

    def _safe_imports(self):

        try:
            from seed.core.event_bus import SEEDEventBus
            if self.event_bus is None:
                self.event_bus = SEEDEventBus(emit=self.emit)
        except Exception as exc:
            log.exception("[SEEDCore] EventBus initialization failed: %s", exc)
            raise

        optional = {
            "DeviceManager": ("seed.core.device_manager", "DeviceManager"),
            "ManagedDevice": ("seed.core.device_manager", "ManagedDevice"),
            "DummyDevice": ("seed.core.device_manager", "DummyDevice"),
            "SEEDMemoryManager": ("seed.core.memory_manager", "SEEDMemoryManager"),
            "SkillMemory": ("seed.core.skill_memory", "SkillMemory"),
            "SEEDAnalyticsEngine": ("seed.analytics.analytics_engine", "SEEDAnalyticsEngine"),
            "ActuatorEngine": ("seed.core.actuator_engine", "ActuatorEngine"),
            "IntentEngine": ("seed.core.intent_engine", "IntentEngine"),
            "AudioModemManager": ("seed.core.audio_modem_manager", "AudioModemManager"),
            "SparkPlugLoader": ("seed.core.sparkplug_loader", "SparkPlugLoader"),
            "SEEDCoreFullSystem": ("seed.core.seed_core_system", "SEEDCoreFullSystem"),
            "TrackSystem": ("seed.core.track_system", "TrackSystem"),
            "EmitWrapper": ("seed.core.emitters.emit_wrapper", "EmitWrapper"),
            "EthicsManager": ("seed.systemutils.ethics", "EthicsManager"),
            "Memory_Crystallizer": ("seed.systemutils.memory_crystallizer", "Memory_Crystallizer"),
            "ChannelManager": ("seed.core.channel_manager", "ChannelManager"),
        }
        for name, (module_name, attr) in optional.items():
            try:
                module = __import__(module_name, fromlist=[attr])
                setattr(self, name, getattr(module, attr))
            except Exception as exc:
                log.warning("[SEEDCore] optional import %s unavailable: %s", name, exc)
                setattr(self, name, None)

    def _wire_core(self):
    
        if self.channel_manager is None:
            raise ValueError("SEEDCore requires a ChannelManager instance")

        if self.track_system is None and self.TrackSystem:
            try:
                self.track_system = self.TrackSystem()
                if hasattr(self.track_system, "set_event_bus"):
                    self.track_system.set_event_bus(self.event_bus)
            except Exception as exc:
                log.warning("[SEEDCore] TrackSystem setup deferred: %s", exc)

        try:
            if self.fat_layer is None and self._fat_layer_factory:
                self.fat_layer = self._fat_layer_factory(storage_root=self.storage_root)
        except Exception as exc:
            log.warning("[SEEDCore] FATLayer unavailable: %s", exc)
        try:
            if self.fat_disk is None and self._fat_disk_factory:
                self.fat_disk = self._fat_disk_factory(storage_root=self.storage_root)
        except Exception as exc:
            log.warning("[SEEDCore] FATPersistence unavailable: %s", exc)

        if self.fat_hud_adapter is None and self._fat_hud_adapter_factory:
            try:
                factory = self._fat_hud_adapter_factory
                self.fat_hud_adapter = factory(event_bus=self.event_bus) if inspect.isclass(factory) else factory
            except Exception as exc:
                log.warning("[SEEDCore] FATHUDAdapter unavailable: %s", exc)

        # Device polling is deliberately deferred until start().
        self._init_qbit_pipeline(create_if_missing=True)

        # Required runtime references are already supplied by main3.py.  Do not
        # eagerly construct optional managers during SEEDCore construction.
        if self._defer_optional_wiring:
            return

        if self.module_registry is None and self._module_registry_factory:
            try:
                self.module_registry = (self._module_registry_factory()
                                        if inspect.isclass(self._module_registry_factory)
                                        else self._module_registry_factory)
            except Exception as exc:
                log.warning("[SEEDCore] ModuleRegistry unavailable: %s", exc)

        if self.health_monitor is None and self._health_monitor_factory:
            try:
                self.health_monitor = (self._health_monitor_factory()
                                       if inspect.isclass(self._health_monitor_factory)
                                       else self._health_monitor_factory)
            except Exception as exc:
                log.warning("[SEEDCore] HealthMonitor unavailable: %s", exc)

        if self.memory_manager is None and self.SEEDMemoryManager:
            try:
                self.memory_manager = self.SEEDMemoryManager(storage_root=self.storage_root)
                self.skill_memory = self.SkillMemory(self.memory_manager) if self.SkillMemory else None
            except Exception as exc:
                log.warning("[SEEDCore] memory setup deferred: %s", exc)

        if self.analytics_engine is None and self.SEEDAnalyticsEngine:
            try:
                self.analytics_engine = self.SEEDAnalyticsEngine(
                    emit=self.emit, storage_root=self.storage_root, event_bus=self.event_bus
                )
                self.analytics = self.analytics_engine
            except Exception as exc:
                log.warning("[SEEDCore] analytics setup deferred: %s", exc)

        if self.intent_engine is None and self.IntentEngine:
            try:
                self.intent_engine = self.IntentEngine(event_bus=self.event_bus, fat_layer=self.fat)
            except Exception as exc:
                log.warning("[SEEDCore] intent engine setup deferred: %s", exc)

        if self.ethics_manager is None and self._ethics_manager_factory:
            try:
                factory = self._ethics_manager_factory
                if inspect.isclass(factory):
                    self.ethics_manager = factory(
                        memory_crystallizer=self.memory_crystallizer,
                        health_monitor=self.health_monitor, module_registry=self.module_registry,
                        track_system=self.track_system, emit=self.emit, track_context=self.track_context,
                        task_id=self.task_id, qbit=self.qbit, track_id=self.track_id,
                        payload=self.payload, event_bus=self.event_bus, intent_engine=self.intent_engine,
                    )
                else:
                    self.ethics_manager = factory
            except Exception as exc:
                log.warning("[SEEDCore] EthicsManager unavailable: %s", exc)

        if self.actuator_engine is None and self.ActuatorEngine:
            try:
                self.actuator_engine = self.ActuatorEngine(fat_layer=self.fat_layer, hud_interface=self.fat_hud)
            except Exception as exc:
                log.warning("[SEEDCore] actuator setup deferred: %s", exc)

        self._intent_lock = asyncio.Lock() if self.async_loop and self.async_loop.is_running() else None

    def _register_event_handlers(self):
        for name, handler in (
            ("INTENT_UPDATED", self._on_intent_update),
            ("SEED_CLI_COMMAND", self._handle_cli_command),
            ("SEED_USER_INPUT", self._handle_command),
            ("DEVICE_INPUT", self._qbit_feed_device_input),
            ("LOOP_CONTROL", handle_loop_control),
        ):
            try:
                if hasattr(self.event_bus, "subscribe"):
                    self.event_bus.subscribe(name, handler)
                    self._event_subscriptions.append((name, handler))
            except Exception as exc:
                log.warning("[SEEDCore] subscribe %s failed: %s", name, exc)

    async def start(self):
     
        if self._started:
            return False
        if self._stopping or self._stopped:
            return False
        self._started = True
        self._stopping = False

        if self.async_loop is None:
            self.async_loop = asyncio.get_running_loop()
        if self._intent_lock is None:
            self._intent_lock = asyncio.Lock()

        self._ensure_runtime_components()

        if self.device_manager and not self._device_poll_started:
            try:
                self.device_manager.start_polling(qbit=self.qbit)
                self._device_poll_started = True
            except Exception as exc:
                log.warning("[SEEDCore] Device polling not started: %s", exc)

        self._fat_queue = asyncio.Queue(maxsize=1000)
        if self._fat_worker_task is None:
            self._fat_worker_task = asyncio.create_task(self._start_fat_worker(), name="SEEDCore-FAT")
        if self._auto_backup and self._backup_maintenance_task is None:
            self._backup_maintenance_task = asyncio.create_task(
                self._backup_maintenance_loop(), name="SEEDCore-BackupMaintenance"
            )

        # Backup is explicitly tied to readiness, never to constructor/import.
        log.info("[SEEDCore] runtime started")
        return True

    async def start_all(self):
        await self.start()
        return self

    async def stop(self):

        if self._stopped:
            return
        self._stopping = True
        if self._backup_maintenance_task:
            self._backup_maintenance_task.cancel()
            try:
                await self._backup_maintenance_task
            except asyncio.CancelledError:
                pass
            self._backup_maintenance_task = None

        if self._fat_worker_task:
            self._fat_worker_task.cancel()
            try:
                await self._fat_worker_task
            except asyncio.CancelledError:
                pass
            except Exception:
                log.exception("[SEEDCore] FAT worker shutdown failed")
            self._fat_worker_task = None

        if self.device_manager and self._device_poll_started:
            for method in ("stop_polling", "stop"):
                fn = getattr(self.device_manager, method, None)
                if fn:
                    try:
                        result = fn()
                        if inspect.isawaitable(result):
                            await result
                    except Exception:
                        log.exception("[SEEDCore] DeviceManager shutdown failed")
                    break
            self._device_poll_started = False

        self._stopped = True
        self._started = False
        self._stopping = False
        log.info("[SEEDCore] stopped")

    def _ensure_runtime_components(self):
        if self.device_manager is None and self.DeviceManager:
            self.device_manager = self.DeviceManager(
                name="SEEDCoreDeviceManager", event_bus=self.event_bus, storage_root=self.storage_root
            )
            try:
                if self.qbit is not None and hasattr(self.qbit, "link_device_manager"):
                    self.qbit.link_device_manager(self.device_manager)
            except Exception:
                log.exception("[SEEDCore] Qbit/device link failed")

        if self.network is None and self._network_manager_factory:
            try:
                self.network = (self._network_manager_factory()
                                 if inspect.isclass(self._network_manager_factory)
                                 else self._network_manager_factory)
            except Exception as exc:
                log.warning("[SEEDCore] NetworkManager unavailable: %s", exc)

        if self.heartbeat is None and self._heartbeat_factory:
            try:
                factory = self._heartbeat_factory
                if inspect.isclass(factory):
                    kwargs = {"qbit": self.qbit, "qbit_dialer": self.qbit_dialer,
                              "loop": self.async_loop, "emit": getattr(self.event_bus, "emit", self.emit),
                              "event_bus": self.event_bus}
                    try:
                        self.heartbeat = factory(**kwargs)
                    except TypeError:
                        self.heartbeat = factory(emit=self.emit, loop=self.loop, event_bus=self.event_bus, qbit=self.qbit)
                else:
                    self.heartbeat = factory
                self.heartbeatemitter = self.heartbeatemitter or self.heartbeat
            except Exception as exc:
                log.warning("[SEEDCore] Heartbeat binding unavailable: %s", exc)

        if self.agent_manager is None and self._agent_manager_factory:
            try:
                factory = self._agent_manager_factory
                if inspect.isclass(factory):
                    self.agent_manager = factory(
                        heartbeatemitter=self.heartbeatemitter or self.heartbeat,
                        qbit_dialer=self.qbit_dialer, track_context=self.track_context,
                        module_registry=self.module_registry, event_bus=self.event_bus,
                        actuator=self.actuator_engine, sparkplug=self.sparkplug,
                        track_id=self.track_id, task_id=self.task_id, emit=self.emit, qbit=self.qbit,
                        ethics_manager=self.ethics_manager,
                    )
                else:
                    self.agent_manager = factory
            except Exception as exc:
                log.warning("[SEEDCore] AgentManager unavailable: %s", exc)

        if self.sparkplug is None and self.SparkPlugLoader:
            try:
                self.sparkplug = self.SparkPlugLoader(event_bus=self.event_bus, debug_trace=True)
                self.sparkplug_loader = self.sparkplug
            except Exception as exc:
                log.warning("[SEEDCore] SparkPlug unavailable: %s", exc)
        if self.audio_modem_manager is None and self.AudioModemManager:
            try:
                self.audio_modem_manager = self.AudioModemManager(event_bus=self.event_bus)
            except Exception as exc:
                log.warning("[SEEDCore] AudioModem unavailable: %s", exc)
        if self.voice_engine is None:
            try:
                self.voice_engine = SEEDVoiceEngine(event_bus=self.event_bus)
                self.commentary = SEEDSystemCommentary(event_bus=self.event_bus, voice_engine=self.voice_engine)
            except Exception as exc:
                log.warning("[SEEDCore] voice/commentary unavailable: %s", exc)

    def mark_seed_ready(self, reason="SEED_READY"):
       
        self._ready = True
        self._backup_pending = True
        if self._auto_backup:
            self._request_backup(reason=reason, force_if_never=True)
        log.info("[SEEDCore] READY: %s", reason)
        return True

    async def _backup_maintenance_loop(self):

        try:
            while not self._stopping:
                await asyncio.sleep(self._backup_interval_sec)
                if self._stopping or not self._ready or not self._auto_backup:
                    continue
                self._request_backup(reason="24h scheduled")
        except asyncio.CancelledError:
            raise

    def _request_backup(self, reason="scheduled", force_if_never=False):
        now = time.time()
        with self._backup_lock:
            if self._backup_thread and self._backup_thread.is_alive():
                return False
            if not force_if_never and now - self._backup_last < self._backup_interval_sec:
                return False
            if not os.path.exists(os.path.dirname(self._backup_root)) and not self._backup_root.startswith("G:\\"):
                # Do not create a surprising non-G drive tree automatically.
                return False
            self._backup_thread = threading.Thread(
                target=self._backup_worker, args=(reason,), daemon=True, name="SEEDCore-Backup"
            )
            self._backup_thread.start()
            return True

    def _backup_worker(self, reason):
        with self._backup_lock:
            try:
                source = Path(self.storage_root).resolve()
                destination_root = Path(self._backup_root)
                if not destination_root.drive or destination_root.drive.upper() != "G:":
                    log.warning("[SEEDCore] Backup disabled: destination is not G: %s", destination_root)
                    return
                if not source.exists():
                    log.warning("[SEEDCore] Backup skipped; source missing: %s", source)
                    return
                destination_root.mkdir(parents=True, exist_ok=True)
                stamp = time.strftime("%Y%m%d_%H%M%S")
                destination = destination_root / f"SEED_{stamp}"
                shutil.copytree(
                    source,
                    destination,
                    dirs_exist_ok=False,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo", ".git"),
                )
                manifest = {
                    "timestamp": time.time(),
                    "reason": reason,
                    "source": str(source),
                    "destination": str(destination),
                    "version": "5.1.0",
                }
                (destination / "SEED_BACKUP_MANIFEST.json").write_text(
                    json.dumps(manifest, indent=2), encoding="utf-8"
                )
                self._backup_last = time.time()
                self._backup_pending = False
                log.info("[SEEDCore] backup complete: %s", destination)
            except Exception as exc:
                log.error("[SEEDCore] backup failed: %s", exc, exc_info=True)

    # ---------------------------------------------------------
    # HUD / UI — main-thread only
    # ---------------------------------------------------------
    def attach_hud(self, hud):
        if threading.current_thread() is not threading.main_thread():
            raise RuntimeError("DEVHUD/Tk attachment must occur on the main thread")
        self.hud = hud
        self._hud_attached = hud is not None
        return self.hud

    def attach_devhud(self, hud_factory=HUDView):

        if threading.current_thread() is not threading.main_thread():
            raise RuntimeError("DEVHUD creation must occur on the main thread")
        if self._hud_attached:
            return self.hud
        try:
            self.hud = hud_factory(self.root, self)
            self._hud_attached = True
            return self.hud
        except Exception:
            log.exception("[SEEDCore] DEVHUD attach failed")
            self.hud = None
            return None

    def on_load(self):
        try:
            ttk.Label(self, text="3D ENGINE ONLINE").pack()
        except Exception:
            log.exception("[SEEDCore] on_load failed")

    def on_unload(self):
        return None

    def handle_command(self, cmd):
        log.info("[3D CMD] %s", cmd)

    # ---------------------------------------------------------
    # Qbit / Heartbeat
    # ---------------------------------------------------------
    def _init_qbit_pipeline(self, create_if_missing=True):
        if self.qbit is None and create_if_missing:
            try:
                factory = self._qbit_factory or Qbit
                self.qbit = factory(event_bus=self.event_bus) if inspect.isclass(factory) else factory
            except Exception:
                log.exception("[SEEDCore] Qbit creation failed")
                raise

        if self.qbit is not None and self.device_manager is not None:
            try:
                if hasattr(self.qbit, "link_device_manager"):
                    self.qbit.link_device_manager(self.device_manager)
            except Exception:
                log.exception("[SEEDCore] Qbit/device link failed")

        # Critical rule: never instantiate a second QbitDialer if main.py
        # already supplied the live instance.
        if self.qbit_dialer is None and QbitDialer is not None:
            try:
                resolver = getattr(
                    self,
                    "resolve_queue_loop",
                    None,
                )
                if callable(resolver):
                    authoritative_queue_loop = resolver()
                else:
                    authoritative_queue_loop = self.qbit_loop
                    queue_loop_type = (
                        type(authoritative_queue_loop).__name__
                        if authoritative_queue_loop is not None
                        else ""
                    )
                    queue_loop_put = getattr(
                        authoritative_queue_loop,
                        "put",
                        None,
                    )
                    if (
                        queue_loop_type != "QbitQueueLoop"
                        or not callable(queue_loop_put)
                    ):
                        dialer_candidate = self.qbit_dialer
                        if dialer_candidate is not None:
                            authoritative_queue_loop = getattr(
                                dialer_candidate,
                                "qbit_queue_loop",
                                None,
                            )
                self.qbit_dialer = QbitDialer(
                    qbit_queue_loop=authoritative_queue_loop,
                    queue_loop=authoritative_queue_loop,
                    handler=self._process_qbit,
                    qbit_loop=authoritative_queue_loop,
                    emit=self.emit, event_bus=self.event_bus, qbit=self.qbit,
                    fat_layer=self.fat_layer, hud_interface=self.fat_hud_adapter,
                )
            except Exception as exc:
                log.warning("[SEEDCore] QbitDialer creation deferred: %s", exc)

        if self.qbit is not None:
            self.heartbeat_emitter = self.qbit

    def bind_ai_input_weights(self, weights, model_oracle=None):
        self.ai_input_weights = dict(weights or {})
        self.ai_model_oracle = model_oracle
        brain = getattr(self, "compute_brain", None)
        if brain is not None and hasattr(brain, "bind_ai_input_weights"):
            brain.bind_ai_input_weights(
                self.ai_input_weights,
                model_oracle=model_oracle,
            )
        return True

    def bind_authoritative_runtime(self, **runtime):
        for name, value in runtime.items():
            if value is not None:
                setattr(self, name, value)

        self.qbit_dialer = runtime.get("qbit_dialer", self.qbit_dialer)
        self.qbit = runtime.get("qbit", self.qbit)
        self.qbit_loop = runtime.get("qbit_loop", getattr(self, "qbit_loop", self.qbit_loop))
        self.event_bus = runtime.get("event_bus", self.event_bus)
        self.track_system = runtime.get("track_system", self.track_system)
        self.track_context = runtime.get("track_context", self.track_context)
        self.registry = runtime.get("registry", getattr(self, "registry", None))
        self.node_registry = runtime.get("node_registry", getattr(self, "node_registry", None))
        self.nodes = runtime.get("nodes", getattr(self, "nodes", None))
        self.compute_brain = runtime.get("compute_brain", getattr(self, "compute_brain", None))
        self.transformer_brain = runtime.get("transformer_brain", getattr(self, "transformer_brain", None))
        self.action_engine = runtime.get("action_engine", getattr(self, "action_engine", None))
        self.intent_engine = runtime.get("intent_engine", self.intent_engine)
        self.analytics_engine = runtime.get("analytics_engine", self.analytics_engine)
        self.agent_manager = runtime.get("agent_manager", self.agent_manager)
        self.adaptive_priority_engine = runtime.get("adaptive_priority_engine", getattr(self, "adaptive_priority_engine", None))
        self.adaptive_engine = runtime.get("adaptive_engine", getattr(self, "adaptive_engine", None))
        self.growth_tree = runtime.get("growth_tree", getattr(self, "growth_tree", None))
        self.oracle = runtime.get("oracle", getattr(self, "oracle", None))
        self.heartbeatemitter = runtime.get("heartbeatemitter", self.heartbeatemitter)
        self.camera_qbit = runtime.get("camera_qbit", getattr(self, "camera_qbit", None))
        self.render_engine = runtime.get("render_engine", getattr(self, "render_engine", None))
        self.seed_network = runtime.get("seed_network", getattr(self, "seed_network", None))

        init_event = runtime.get("init_event")
        if init_event is not None:
            self.seed_init_event = init_event
            try:
                init_event.bind_seedcore_ai(self, **runtime)
            except Exception as exc:
                log.warning("[SEEDCore] InitEvent binding deferred: %s", exc)

        if self.qbit_dialer is not None:
            self.bind_qbit_dialer(self.qbit_dialer)

        log.info("[SEEDCore] authoritative runtime bound | dialer=%s | qbit=%s | track=%s | registry=%s | nodes=%s | oracle=%s", type(self.qbit_dialer).__name__ if self.qbit_dialer else "NONE", type(self.qbit).__name__ if self.qbit else "NONE", type(self.track_system).__name__ if self.track_system else "NONE", type(getattr(self, "registry", None)).__name__ if getattr(self, "registry", None) else "NONE", type(getattr(self, "node_registry", None)).__name__ if getattr(self, "node_registry", None) else "NONE", type(getattr(self, "oracle", None)).__name__ if getattr(self, "oracle", None) else "NONE")
        return True

    def bind_qbit_dialer(self, dialer):
        if dialer is None:
            return False

        self.qbit_dialer = dialer

    # ---------------------------------------------------------
    # Preserve the authoritative QbitDialer instance.
    # Attach the SAME FATHUD adapter owned by SEEDCore.
    # Never create a second adapter.
    # ---------------------------------------------------------
        if self.fat_hud_adapter is not None:

            try:
                if hasattr(dialer, "attach"):

                    dialer.attach(
                        fat_hud_adapter=self.fat_hud_adapter,
                    )

                else:
                    existing = getattr(
                        dialer,
                        "fat_hud_adapter",
                        None,
                    )

                    if existing is None:
                        dialer.fat_hud_adapter = (
                            self.fat_hud_adapter
                        )

            except Exception as exc:
                log.warning(
                    "[SEEDCore] FATHUDAdapter binding failed: %s",
                    exc,
                )
                return False

        log.info(
            "[SEEDCore] existing QbitDialer bound; "
            "FATHUD attached=%s; no replacement created",
            self.fat_hud_adapter is not None,
        )

        return True

    def _process_qbit(self, qbit):
        try:
            payload = getattr(qbit, "payload", qbit)
            if self.heartbeatemitter and hasattr(self.heartbeatemitter, "push"):
                self.heartbeatemitter.push({
                    "type": "QBIT_ECHO", "payload": payload,
                    "track": getattr(qbit, "track", None), "timestamp": time.time(),
                })
            self.event_log.append({"type": "QBIT", "timestamp": time.time()})
        except Exception:
            log.exception("[SEEDCore] Qbit processing failed")

    # ---------------------------------------------------------
    # Intent / action pipeline
    # ---------------------------------------------------------
    def _init_intent_action_loop(self):
        # Retained compatibility method. Event-driven dispatch is used now.
        return True

    async def intent_listener(self, intent_payload):
        if not isinstance(intent_payload, dict):
            return
        try:
            dominant = intent_payload.get("dominant_intent") or intent_payload.get("intent")
            if dominant:
                await self._execute_intent_actions(dominant, intent_payload)
            feedback = {
                "source": "intent_feedback", "intent": intent_payload.get("intent"),
                "dominant_intent": dominant, "timestamp": time.time()
            }
            if self.qbit is not None and hasattr(self.qbit, "push"):
                result = self.qbit.push(feedback)
                if inspect.isawaitable(result):
                    await result
            await self._queue_fat(feedback)
        except Exception:
            log.exception("[SEEDCore] intent listener failed")

    async def _execute_intent_actions(self, intent_name, payload):
        try:
            skill_map = {
                "scan_area": [self.light_scan_skill, self.deep_scan_skill],
                "communicate": [self.audio_modem_manager, self.voice_engine],
                "analyze_data": [self.analytics_engine],
            }
            for skill in filter(None, skill_map.get(intent_name, [])):
                fn = getattr(skill, "run", None) or getattr(skill, "execute", None)
                if fn:
                    result = fn(payload)
                    if inspect.isawaitable(result):
                        await result
            if self.agent_manager and hasattr(self.agent_manager, "dispatch_intent"):
                result = self.agent_manager.dispatch_intent(intent_name, payload)
                if inspect.isawaitable(result):
                    await result
            if self.actuator_engine and hasattr(self.actuator_engine, "actuate_intent"):
                result = self.actuator_engine.actuate_intent(intent_name, payload)
                if inspect.isawaitable(result):
                    await result
        except Exception:
            log.exception("[SEEDCore] intent action failed: %s", intent_name)

    async def _on_intent_update(self, payload):
        if not isinstance(payload, dict):
            return
        if self._intent_lock is None:
            self._intent_lock = asyncio.Lock()
        async with self._intent_lock:
            self._current_intent_snapshot.update({
                "intent": payload.get("intent", "idle"),
                "dominant_intent": payload.get("dominant_intent", payload.get("intent", "idle")),
                "intent_scores": payload.get("intent_scores", {}),
                "resonance": payload.get("resonance", 0.5),
                "timestamp": time.time(),
            })

    async def get_current_intent(self):
        if self._intent_lock is None:
            return dict(self._current_intent_snapshot)
        async with self._intent_lock:
            return deepcopy(self._current_intent_snapshot)

    def _trigger_deep_scan(self, payload=None):
        skill = self.deep_scan_skill
        if skill is None:
            return False
        now = time.time()
        last = getattr(skill, "_last_execution", 0.0)
        if now - last < self.DEEP_SCAN_THROTTLE:
            return False
        skill._last_execution = now
        track_id = gen_track_id("DPS")
        loader = self.sparkplug_loader or self.sparkplug
        submit = getattr(loader, "submit_skill", None) if loader else None
        if submit and self.async_loop and self.async_loop.is_running():
            coro = submit(
                skill_name="deep_scan_skill",
                payload={"input": payload, "track_id": track_id},
                priority=0.9, channel_marker="DPS", track_id=track_id,
            )
            asyncio.create_task(coro)
            return True
        return False

    # ---------------------------------------------------------
    # FAT / persistence
    # ---------------------------------------------------------
    async def _queue_fat(self, entry):
        if self._fat_queue is None:
            return
        try:
            self._fat_queue.put_nowait(entry)
        except asyncio.QueueFull:
            log.warning("[SEEDCore] FAT queue full; dropping telemetry entry")

    async def _start_fat_worker(self):
        if self._fat_queue is None:
            return
        while not self._stopping:
            try:
                entry = await self._fat_queue.get()
                if entry is None:
                    return
                if self.analytics_engine and hasattr(self.analytics_engine, "ingest_fat_entry"):
                    await asyncio.to_thread(self.analytics_engine.ingest_fat_entry, entry)
                if self.fat_disk and hasattr(self.fat_disk, "persist"):
                    await asyncio.to_thread(self.fat_disk.persist, entry)
                if self.fat_hud and hasattr(self.fat_hud, "push"):
                    result = self.fat_hud.push(entry)
                    if inspect.isawaitable(result):
                        await result
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("[SEEDCore] FAT worker error")

    # ---------------------------------------------------------
    # Devices / network
    # ---------------------------------------------------------
    async def send_to_device(self, device_id, data):
        if not self.device_manager:
            raise RuntimeError("DeviceManager is not available")
        device = self.device_manager.devices.get(device_id)
        if not device:
            if not hasattr(self, "ManagedDevice") or not self.DummyDevice:
                raise KeyError(device_id)
            device = self.ManagedDevice(self.DummyDevice(), self.event_bus)
        return await device.send(data)

    async def read_device(self, device_id):
        if not self.device_manager:
            raise RuntimeError("DeviceManager is not available")
        device = self.device_manager.devices.get(device_id)
        if not device:
            if not self.DummyDevice:
                raise KeyError(device_id)
            device = self.ManagedDevice(self.DummyDevice(), self.event_bus)
        return await device.read(self.qbit)

    def fetch_best_device(self, required_capabilities=None, preferred_types=None):
        required_capabilities = required_capabilities or []
        preferred_types = preferred_types or []
        if not self.device_manager:
            return None
        return self.device_manager.fetch_best_device(required_capabilities, preferred_types)

    def _on_net_msg(self, message, packet=None):

        if self.event_bus:
            try:
                if hasattr(self.event_bus, "publish"):
                    self.event_bus.publish("NETWORK_MESSAGE", {"message": message, "packet": packet})
                fn = getattr(self.event_bus, "emit_async", None)
                if fn and self.async_loop and self.async_loop.is_running():
                    asyncio.create_task(fn("NETWORK_MESSAGE", {"message": message, "packet": packet}))
            except Exception:
                log.exception("[SEEDCore] network event failed")
        return True

    async def _on_net_msg_async(self, msg, packet=None):
        if self.event_bus:
            fn = getattr(self.event_bus, "emit_async", None)
            if fn:
                await fn("NETWORK_MESSAGE", {"message": msg, "packet": packet})
            elif hasattr(self.event_bus, "publish"):
                self.event_bus.publish("NETWORK_MESSAGE", {"message": msg, "packet": packet})

    def _on_net_msg_sync(self, message, packet=None):
        device = packet.get("device") if isinstance(packet, dict) else None
        self._emit(f"[NET] Delivered → {device or 'unknown'}")
        if self.event_bus:
            try:
                if hasattr(self.event_bus, "publish"):
                    self.event_bus.publish("NETWORK_MESSAGE", {"message": message, "packet": packet})
            except Exception:
                log.exception("[SEEDCore] network event publish failed")

    # ---------------------------------------------------------
    # CLI / commands
    # ---------------------------------------------------------
    def _handle_cli_command(self, payload):
        if not isinstance(payload, dict):
            return
        text = str(payload.get("text", "")).strip()
        if text.startswith("send ") and self.network:
            parts = text.split(" ", 2)
            if len(parts) == 3:
                self.network.connect_device(parts[1])
                self.network.send_message(parts[1], parts[2])
        self.event_bus.publish("SEED_OUTPUT", {"text": f"[SEED] {text}"})

    def _handle_command(self, payload):
        if not isinstance(payload, dict):
            return
        text = str(payload.get("text", "")).strip()
        if not text:
            return
        cmd = text.split()[0].lower()
        if cmd in ("send", "exec", "file") and self.permission_gate:
            self.permission_gate.request(
                command_text=text,
                on_approve=lambda: self._execute_command(text),
                on_deny=lambda: self._emit("Permission denied"),
            )
            return
        self._execute_command(text)

    def _execute_command(self, text):
        parts = text.split()
        if not parts:
            return
        cmd = parts[0].lower()
        if cmd == "help":
            self._emit("Commands: help, send <device> <msg>, devices")
        elif cmd == "send" and len(parts) >= 3 and self.network:
            device, msg = parts[1], " ".join(parts[2:])
            self.network.connect_device(device)
            self.network.send_message(device, msg)
            self._emit(f"Sent to {device}")
        else:
            self._emit(f"Unknown command: {text}")

    def _emit(self, text):
        try:
            if self.event_bus and hasattr(self.event_bus, "publish"):
                self.event_bus.publish("SEED_OUTPUT", {"text": f"[SEED] {text}"})
            else:
                self.emit("SEED_OUTPUT", {"text": f"[SEED] {text}"})
        except Exception:
            log.exception("[SEEDCore] output failed")

    def _qbit_feed_device_input(self, data):
        if self.qbit is not None and hasattr(self.qbit, "push"):
            try:
                result = self.qbit.push({"source": "device", "data": data, "timestamp": time.time()})
                if inspect.isawaitable(result) and self.async_loop and self.async_loop.is_running():
                    asyncio.create_task(result)
            except Exception:
                log.exception("[SEEDCore] device input -> Qbit failed")

    # ---------------------------------------------------------
    # Compatibility / diagnostics
    # ---------------------------------------------------------
    def handle_loop_control(self, cmd):
        if not isinstance(cmd, dict) or cmd.get("authority") == "LOCKED":
            return False
        loop_obj = cmd.get("loop")
        action = str(cmd.get("action", "")).upper()
        try:
            if action == "PAUSE" and hasattr(loop_obj, "pause"):
                loop_obj.pause(reason=cmd.get("reason"))
            elif action == "RESUME" and hasattr(loop_obj, "resume"):
                loop_obj.resume()
            elif action == "STOP" and hasattr(loop_obj, "stop"):
                loop_obj.stop()
            else:
                return False
            return True
        except Exception:
            log.exception("[SEEDCore] loop control failed")
            return False

    def get_status(self):
        return {
            "started": self._started,
            "stopping": self._stopping,
            "stopped": self._stopped,
            "ready": self._ready,
            "hud_attached": self._hud_attached,
            "qbit": self.qbit is not None,
            "qbit_dialer": self.qbit_dialer is not None,
            "heartbeat": self.heartbeat is not None,
            "device_polling": self._device_poll_started,
            "backup_last": self._backup_last,
            "backup_root": self._backup_root,
        }

    def _seed_default_permissions(self):
        if not self.permission_manager:
            return False
        self.permission_manager.create_permission(
            private_key_bytes=self.private_key_bytes,
            permission_code="ADMIN_FULL",
            scope_hierarchy=["system", "authorization", "all"],
            devices=[self.device_id], consent_level="red", weight_level=9,
        )
        return True


# Backward-compatible alias used by older boot code.
SEEDCoreFull = SEEDCore

# ==========================================================
# SEED RUNTIME BINDING GATE
#
# PURPOSE:
#     Lazy-bind late startup dependencies without creating
#     duplicate runtime infrastructure.
#
# IMPORTANT:
#     This class NEVER creates:
#
#         - Qbit
#         - QbitQueueLoop
#         - QbitDialer
#         - EventBus
#         - Registry
#         - processing thread
#         - asyncio task
#
#     It only discovers and connects existing authoritative
#     runtime objects.
#
# ==========================================================

class SEEDRuntimeBindingGate:

    VERSION = "1.0.0"

    def __init__(
        self,
        *,
        seed_core=None,
        qbit=None,
        qbit_dialer=None,
        qbit_loop=None,
        event_bus=None,
        registry=None,
        init_event=None,
        logger=None,
        fat_hud_adapter=None,
    ):

        self.seed_core = seed_core
        self.qbit = qbit
        self.qbit_dialer = qbit_dialer
        self.qbit_loop = qbit_loop
        self.event_bus = event_bus
        self.registry = registry
        self.init_event = init_event

        self.logger = (
            logger
            or logging.getLogger(
                "SEED.RuntimeBindingGate"
            )
        )

        self.bound = False
        self.waiting = True
        self.last_error = None
        self.bind_attempts = 0
        self.fat_hud_adapter = None


    # ======================================================
    # AUTHORITATIVE QUEUE TEST
    # ======================================================

    @staticmethod
    def _is_qbit_queue_loop(obj):

        if obj is None:
            return False

        name = type(obj).__name__

        if name != "QbitQueueLoop":
            return False

        return callable(
            getattr(
                obj,
                "put",
                None,
            )
        )

    # ======================================================
    # DISCOVER EXISTING INIT EVENT
    # ======================================================

    def discover_init_event(self):

        if self.init_event is not None:
            return self.init_event

        # --------------------------------------------------
        # Registry lookup
        # --------------------------------------------------

        registry = self.registry

        if registry is not None:

            for key in (
                "SeedInitEvent",
                "init_event",
                "seed_init_event",
                "INIT_EVENT",
            ):

                try:

                    candidate = (
                        registry.get(key)
                        if hasattr(
                            registry,
                            "get",
                        )
                        else None
                    )

                    if candidate is not None:

                        self.init_event = candidate

                        self.logger.info(
                            "[BindingGate] InitEvent discovered "
                            "from registry | type=%s",
                            type(candidate).__name__,
                        )

                        return candidate

                except Exception:
                    pass

        # --------------------------------------------------
        # Module-level discovery
        #
        # Import is intentionally lazy.
        # --------------------------------------------------

        try:

            import seed.core.init_event as init_module

            candidate = getattr(
                init_module,
                "SEED_INIT_EVENT",
                None,
            )

            if candidate is not None:

                self.init_event = candidate

                return candidate

        except Exception:
            pass

        return None

    # ======================================================
    # REFRESH RUNTIME REFERENCES
    # ======================================================

    def refresh(self):

        self.bind_attempts += 1

        # --------------------------------------------------
        # SEED CORE
        # --------------------------------------------------

        core = self.seed_core

        if core is not None:

            self.event_bus = (
                self.event_bus
                or getattr(
                    core,
                    "event_bus",
                    None,
                )
            )

            self.qbit = (
                self.qbit
                or getattr(
                    core,
                    "qbit",
                    None,
                )
                or getattr(
                    core,
                    "qbit_instance",
                    None,
                )
            )

            self.qbit_dialer = (
                self.qbit_dialer
                or getattr(
                    core,
                    "qbit_dialer",
                    None,
                )
            )

            self.qbit_loop = (
                self.qbit_loop
                or getattr(
                    core,
                    "qbit_loop",
                    None,
                )
                or getattr(
                    core,
                    "queue_loop",
                    None,
                )
            )

            self.registry = (
                self.registry
                or getattr(
                    core,
                    "registry",
                    None,
                )
                or getattr(
                    core,
                    "module_registry",
                    None,
                )
            )

            self.fat_hud_adapter = (
                getattr(
                    core,
                    "fat_hud_adapter",
                    None,
                )
            )

        # --------------------------------------------------
        # InitEvent is discovered, never created.
        # --------------------------------------------------

        self.discover_init_event()

        return self.status()

    # ======================================================
    # AUTHORITATIVE QUEUE RESOLUTION
    # ======================================================

    def resolve_queue_loop(self):

        candidate = self.qbit_loop

        if self._is_qbit_queue_loop(
            candidate
        ):

            return candidate

        # --------------------------------------------------
        # Check QbitDialer reference.
        # --------------------------------------------------

        dialer = self.qbit_dialer

        if dialer is not None:

            for attr in (
                "qbit_queue_loop",
                "queue_loop",
            ):

                candidate = getattr(
                    dialer,
                    attr,
                    None,
                )

                if self._is_qbit_queue_loop(
                    candidate
                ):

                    return candidate

        # --------------------------------------------------
        # Check SEEDCore one more time.
        # --------------------------------------------------

        core = self.seed_core

        if core is not None:

            for attr in (
                "qbit_loop",
                "queue_loop",
            ):

                candidate = getattr(
                    core,
                    attr,
                    None,
                )

                if self._is_qbit_queue_loop(
                    candidate
                ):

                    return candidate

        return None

    # ======================================================
    # BIND EXISTING RUNTIME
    # ======================================================

    def bind(self):

        self.refresh()

        queue_loop = (
            self.resolve_queue_loop()
        )

        # --------------------------------------------------
        # DO NOT ACCEPT stdlib queue.Queue
        # --------------------------------------------------

        if queue_loop is None:

            self.waiting = True

            self.logger.debug(
                "[BindingGate] Waiting for authoritative "
                "QbitQueueLoop"
            )

            return False

        # --------------------------------------------------
        # Bind local reference.
        # --------------------------------------------------

        self.qbit_loop = queue_loop

        # --------------------------------------------------
        # Bind Qbit.
        # --------------------------------------------------

        if self.qbit is not None:

            bind_runtime = getattr(
                self.qbit,
                "bind_runtime",
                None,
            )

            if callable(bind_runtime):

                try:

                    bind_runtime(
                        event_bus=self.event_bus,
                        qbit_dialer=self.qbit_dialer,
                        queue_loop=queue_loop,
                        node_registry=self.registry,
                    )

                except TypeError:

                    # Compatibility with older bind_runtime()
                    # signatures.

                    bind_runtime(
                        event_bus=self.event_bus,
                        qbit_dialer=self.qbit_dialer,
                        queue_loop=queue_loop,
                    )

        # --------------------------------------------------
        # Bind Dialer.
        #
        # IMPORTANT:
        #
        # We bind the QbitQueueLoop object itself.
        #
        # We NEVER pass queue_loop.queue as qbit_queue.
        # --------------------------------------------------

        dialer = self.qbit_dialer

        if dialer is not None and self.fat_hud_adapter is not None:

            try:

                if hasattr(dialer, "attach"):

                    dialer.attach(
                        fat_hud_adapter=self.fat_hud_adapter,
                    )

                elif getattr(
                    dialer,
                    "fat_hud_adapter",
                    None,
                ) is None:

                    dialer.fat_hud_adapter = (
                        self.fat_hud_adapter
                    )

            except Exception as exc:

                self.last_error = str(exc)

                self.logger.error(
                    "[BindingGate] FATHUD binding failed | "
                    "error=%s",
                    exc,
                )

                return False

        # --------------------------------------------------
        # SUCCESS
        # --------------------------------------------------

        self.bound = True
        self.waiting = False
        self.last_error = None

        self.logger.info(
            "[BindingGate] AUTHORITATIVE RUNTIME BOUND | "
            "qbit=%s | queue_loop=%s | dialer=%s | "
            "init_event=%s",
            type(self.qbit).__name__
            if self.qbit is not None
            else "NONE",
            type(queue_loop).__name__,
            type(self.qbit_dialer).__name__
            if self.qbit_dialer is not None
            else "NONE",
            type(self.init_event).__name__
            if self.init_event is not None
            else "WAITING",
        )

        return True

    # ======================================================
    # STATUS
    # ======================================================

    def status(self):

        queue_loop = (
            self.resolve_queue_loop()
        )

        return {
            "version": self.VERSION,
            "bound": self.bound,
            "waiting": self.waiting,
            "init_event": (
                self.init_event is not None
            ),
            "event_bus": (
                self.event_bus is not None
            ),
            "qbit": (
                self.qbit is not None
            ),
            "qbit_dialer": (
                self.qbit_dialer is not None
            ),
            "qbit_queue_loop": (
                queue_loop is not None
            ),
            "qbit_queue_loop_type": (
                type(queue_loop).__name__
                if queue_loop is not None
                else None
            ),
            "bind_attempts": (
                self.bind_attempts
            ),
            "fat_hud_adapter": (
                self.fat_hud_adapter is not None
            ),
            "last_error": self.last_error,
        }