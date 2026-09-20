

# ==========================================================
# FILE: heartbeat.py
# PATH: C:\SEED_ROOT\seed\core\heartbeat.py
#
# VERSION: 5.6.4
# STATUS: HEARTBEAT / HEARTBEATEMITTER / QBIT PIPELINE
# UPDATED: 2026-08-30
#
# ==========================================================
#
# [PHASE]
# CORE HEARTBEAT / AUTHORITATIVE QBIT TRANSPORT
#
# ==========================================================
#
# [SYSTEM AUTHORITY]
#
# HEARTBEAT
#     Owns the system clock / pulse.
#     Observes system health.
#     Produces heartbeat observations.
#     Does NOT execute commands.
#     Does NOT directly submit to QbitQueueLoop.
#     Does NOT directly call QbitDialer.
#
# HEARTBEATEMITTER
#     Is the authoritative entry gateway for Heartbeat Qbits.
#
#     Heartbeat:
#          |
#          v
#     HeartbeatEmitter
#          |
#          v
#     Heartbeat Qbit
#          |
#          v
#     Qbit transport / processing pipeline
#
#     The HeartbeatEmitter is NOT the endpoint.
#     It is the START of the Heartbeat Qbit/Dialer pipeline.
#
#     The emitter also receives Qbits returning from the
#     Dialer-side pipeline and distributes the appropriate
#     results to EventBus and System.
#
# QBIT
#     Authoritative data carrier ("blood cell").
#
#     Carries:
#         identity
#         lineage
#         generation
#         track/channel metadata
#         source/origin
#         heartbeat observations
#         module data
#         downstream results
#
#     A Qbit is a data carrier.
#     A payload containing an "action" field does NOT by itself
#     make that Qbit an admitted command.
#
# QBIT QUEUE LOOP
#     Owns Qbit transport / queue behavior.
#     Preserves Qbit identity and lineage.
#     Participates in the authoritative Qbit pipeline.
#
# QBIT DIALER
#     Owns Qbit processing / routing.
#     Receives Qbits from the Qbit pipeline.
#     Produces / routes Qbits back through the emitter path.
#     Is the command authority.
#
#     Heartbeat NEVER bypasses HeartbeatEmitter to reach Dialer.
#
# TRACK SYSTEM / TRACKDATA
#     Owns track context and track metadata.
#     Heartbeat uses the authoritative TrackedData implementation.
#
# EVENTBUS
#     Receives system/event distribution from the appropriate
#     emitter/system boundary.
#     EventBus is not a replacement for Qbit transport.
#
# ==========================================================
#
# [QBIT ARCHITECTURE]
#
# IMPORTANT:
#
# The Heartbeat Qbit pipeline is ONE Qbit pipeline.
#
# It does NOT mean Heartbeat is the source of every Qbit
# in SEED.
#
# Other SEED modules may independently produce Qbits:
#
#     MODULE A ───────┐
#     MODULE B ───────┤
#     MODULE C ───────┤
#     MODULE D ───────┤
#                     ├──> Qbit infrastructure
#     HEARTBEAT ──────┘
#
# Each Qbit preserves its own:
#
#     source
#     identity
#     lineage
#     generation
#     track
#     channel
#
# Heartbeat has one special authoritative entrance:
#
#     HEARTBEAT
#          |
#          v
#     HEARTBEATEMITTER
#          |
#          v
#     HEARTBEAT QBIT PIPELINE
#
# ==========================================================
#
# [AUTHORITATIVE HEARTBEAT QBIT PIPELINE]
#
#                 HEARTBEAT
#                 THE HEART
#                     |
#                     | pulse / observation / health
#                     v
#             HEARTBEAT EMITTER
#             AUTHORITATIVE GATEWAY
#                     |
#                     | Heartbeat Qbit
#                     v
#                  QBIT
#                     |
#                     v
#              QBIT QUEUE LOOP
#                     |
#                     v
#                QBIT DIALER
#              COMMAND AUTHORITY
#                     |
#                     | Qbit result / response
#                     v
#             HEARTBEAT EMITTER
#                     |
#             +-------+-------+
#             |               |
#             v               v
#          EVENTBUS         SYSTEM
#
# The return path is part of the same authoritative pipeline.
#
# ==========================================================
#
# [HEARTBEAT BOUNDARY]
#
# Heartbeat may:
#
#     OBSERVE
#     TICK
#     BUILD OBSERVATION DATA
#     RECORD HEALTH
#     DETECT LIMPMODE
#     PREPARE HEARTBEAT PAYLOAD
#     SEND HEARTBEAT PAYLOAD TO HEARTBEATEMITTER
#
# Heartbeat may NOT:
#
#     directly call QbitQueueLoop
#     directly call QbitDialer
#     directly execute commands
#     directly submit commands
#
# Heartbeat's transport boundary is:
#
#     self.emitter
#
# ==========================================================
#
# [HEARTBEAT EMITTER CONTRACT]
#
# HeartbeatEmitter is the authoritative bridge between the
# Heartbeat pulse and the Qbit/Dialer transport system.
#
# It is responsible for carrying Heartbeat-originated data
# into the Qbit pipeline and carrying applicable Qbit results
# back toward EventBus/System.
#
# Conceptually:
#
#     Heartbeat
#         |
#         v
#     HeartbeatEmitter
#         |
#         v
#     Qbit
#         |
#         v
#     QueueLoop
#         |
#         v
#     QbitDialer
#         |
#         v
#     HeartbeatEmitter
#         |
#         +----> EventBus
#         |
#         +----> System
#
# ==========================================================
#
# [COMMAND AUTHORITY CONTRACT]
#
# Heartbeat is NOT the command authority.
#
# Heartbeat can observe a condition such as:
#
#     LIMPMODE
#     CPU_PRESSURE
#     MEMORY_PRESSURE
#     RECOVERY_REQUIRED
#
# Those observations are DATA.
#
# They enter the Qbit pipeline through HeartbeatEmitter.
#
# The QbitDialer determines whether downstream command
# processing is appropriate.
#
# Command authority remains:
#
#     QbitDialer
#          |
#          v
#     submit_command()
#
# Heartbeat MUST NOT:
#
#     execute_command()
#     submit_command()
#     directly invoke Dialer command methods
#
# A heartbeat payload containing:
#
#     "action"
#     "command"
#     "execute"
#
# is still heartbeat-originated DATA unless and until the
# authoritative Dialer command pipeline explicitly promotes
# it according to its own command-admission contract.
#
# Heartbeat itself never promotes data into a command.
#
# ==========================================================
#
# [QBIT IDENTITY CONTRACT]
#
# Heartbeat must preserve the Qbit supplied by the authoritative
# boot/runtime system.
#
# If an authoritative Qbit already exists:
#
#     USE IT
#
# Do not create a replacement Qbit merely because Heartbeat
# is initializing.
#
# Qbit identity and lineage must remain stable through:
#
#     Heartbeat
#         ->
#     HeartbeatEmitter
#         ->
#     Qbit transport
#         ->
#     QueueLoop
#         ->
#     QbitDialer
#         ->
#     return/emitter path
#
# ==========================================================
#
# [IMPORTANT QBIT API CONTRACT]
#
# Heartbeat MUST NOT redefine the Qbit API.
#
# Known runtime Qbit contract:
#
#     Qbit.process_tick(tick)
#
# Heartbeat MUST NOT assume:
#
#     Qbit.process_tick(
#         tick=...,
#         core_status=...,
#         system_status=...,
#         user_status=...
#     )
#
# Heartbeat health/vector information is DATA.
#
# It must be carried through the appropriate Qbit payload /
# HeartbeatEmitter transport boundary rather than passed as
# unsupported arguments to Qbit.process_tick().
#
# ==========================================================
#
# [HEALTHMONITOR RELATIONSHIP]
#
# Heartbeat is the system heart.
#
# HealthMonitor observes/records health state associated with
# the heartbeat lifecycle.
#
# Intended relationship:
#
#     HEARTBEAT
#          |
#          +----> HEALTHMONITOR
#          |
#          v
#     HEARTBEATEMITTER
#          |
#          v
#        QBIT
#
# HealthMonitor does not become a second heartbeat clock.
# HealthMonitor does not become a second Qbit/Dialer path.
# Heartbeat remains the authoritative pulse.
#
# ==========================================================
#
# [LIMPMODE]
#
# LIMPMODE is a heartbeat health state.
#
# Heartbeat may detect and publish LIMPMODE information.
#
# LIMPMODE information follows the same HeartbeatEmitter
# boundary as every other Heartbeat-originated Qbit:
#
#     HEARTBEAT
#          |
#          v
#     HEARTBEATEMITTER
#          |
#          v
#     QBIT PIPELINE
#
# Heartbeat must not create a separate emergency command path.
#
# ==========================================================
#
# [BOOT ORDER]
#
#     CORE
#       |
#       v
#   HEARTBEAT
#       |
#       v
#   HEALTHMONITOR
#       |
#       v
#   HEARTBEATEMITTER
#       |
#       v
#      QBIT
#       |
#       v
#   QBIT QUEUE LOOP
#       |
#       v
#   QBIT DIALER
#       |
#       v
#   HEARTBEATEMITTER
#       |
#       +----------> EVENTBUS
#       |
#       +----------> SYSTEM
#       |
#       v
#   HUD / DEVHUD
#
# ==========================================================
#
# [DESIGN RULE]
#
# Heartbeat is the heart.
#
# Heartbeat owns the clock.
# Heartbeat observes.
# Heartbeat produces heartbeat data.
#
# HeartbeatEmitter is the Heartbeat Qbit gateway.
#
# Qbit carries.
# QueueLoop transports.
# QbitDialer processes and routes.
# QbitDialer owns command authority.
#
# Heartbeat never bypasses HeartbeatEmitter.
#
# HeartbeatEmitter is the start of the Heartbeat Qbit/Dialer
# pipeline and also participates in the return path.
#
# ==========================================================


from __future__ import annotations

import asyncio
import inspect
import logging
import random
import threading
import time

from collections import deque
from typing import Any, Optional

import psutil

from seed.core.qbit import Qbit
from seed.core.emitters.heartbeatemitter import HeartbeatEmitter
from seed.core.tracked_data import TrackedData


# ==========================================================
# OPTIONAL EVENT BUS
# ==========================================================

try:
    from seed.core.event_bus import SEEDEventBus
except Exception:
    SEEDEventBus = None


# ==========================================================
# OPTIONAL HEALTH MONITOR
# ==========================================================

try:
    from seed.core.healthmonitor import HealthMonitor
except Exception:
    HealthMonitor = None


# ==========================================================
# OPTIONAL PERMISSION SYSTEM
# ==========================================================

try:
    from seed.security.delegated_permission_escalation import (
        DelegatedPermissionManager,
    )
except Exception:
    DelegatedPermissionManager = None


try:
    from seed.security.delegated_permission_audit import (
        EscalationAuditManager,
    )
except Exception:
    EscalationAuditManager = None


# ==========================================================
# LOGGER
# ==========================================================

logger = logging.getLogger("Heartbeat")

if not logger.handlers:
    logger.addHandler(logging.NullHandler())

logger.setLevel(logging.INFO)


# ==========================================================
# CHANNEL DEFINITIONS
# ==========================================================

HEARTBEAT = "HEARTBEAT"
QBIT_TICK = "QBIT_TICK"
VECTOR_TICK = "VECTOR_TICK"
LIMP_MODE = "LIMP_MODE"
QBIT_RESULT = "QBIT_RESULT"

# ==========================================================
# QBIT PROCESSING POLICY
#
# USER INPUT IS OPTIONAL.
#
# QBIT PROCESSING IS NOT OPTIONAL.
# ==========================================================

QBIT_PROCESS_WITHOUT_USER_INPUT = True

QBIT_PROCESS_HEARTBEAT_QBITS = True
QBIT_PROCESS_IDLE_QBITS = True
QBIT_PROCESS_BACKGROUND_QBITS = True
QBIT_PROCESS_SYSTEM_QBITS = True

# ==========================================================
# CHANNEL ID
# ==========================================================

class ChannelID:
    CORE = type("CORE", (), {"value": "CORE"})()
    SYSTEM = type("SYSTEM", (), {"value": "SYSTEM"})()
    USER = type("USER", (), {"value": "USER"})()
    QBIT = type("QBIT", (), {"value": "QBIT"})()
    VECTOR = type("VECTOR", (), {"value": "VECTOR"})()


CHANNEL_CORE = ChannelID.CORE.value
CHANNEL_SYSTEM = ChannelID.SYSTEM.value
CHANNEL_USER = ChannelID.USER.value
CHANNEL_QBIT = ChannelID.QBIT.value
CHANNEL_VECTOR = ChannelID.VECTOR.value


# ==========================================================
# HEARTBEAT VECTOR CORE
# ==========================================================

class HeartbeatVectorCore:

    def __init__(
        self,
        max_history: int = 128,
    ):
        self.history = deque(
            maxlen=max_history
        )

        self.last_value = 0
        self.vector_channel = CHANNEL_VECTOR

    def process_tick(
        self,
        tick: int,
        core_status: float = 1.0,
        system_status: float = 1.0,
        user_status: float = 1.0,
    ):

        qbit_val = (
            (
                tick
                ^ int(core_status * 100)
            )
            + int(system_status * 50)
            - int(user_status * 25)
        ) & 0xFFFFFFFF

        qbit_val ^= random.getrandbits(32)

        self.last_value = qbit_val

        vector_repr = {
            "tick": tick,
            "qbit_value": qbit_val,
            "core_status": core_status,
            "system_status": system_status,
            "user_status": user_status,
            "vector": [
                core_status,
                system_status,
                user_status,
                (qbit_val & 0xFF) / 255.0,
            ],
            "channel": CHANNEL_VECTOR,
            "source": HEARTBEAT,
        }

        self.history.append(
            vector_repr
        )

        return vector_repr


# ==========================================================
# HEARTBEAT
# ==========================================================

class Heartbeat:

    # ======================================================
    # CONSTRUCTOR
    # ======================================================

    def __init__(
        self,
        emit=None,
        loop=None,
        module_name=None,
        storage_root="./SEED_ROOT",
        event_bus=None,
        interval=1.0,
        qbit_dialer=None,
        bios_registry=None,
        qbit_queue_loop=None,
        backup_engine=None,
        health_monitor=None,
        _monitor=True,
        enable_qbit=True,
        qbit=None,
        cpu_limit=80.0,
        mem_limit=85.0,
        module_wait_timeout=5.0,
    ):
        self.module_name = (
            module_name
            or "CORE_HEARTBEAT"
        )

        self.storage_root = storage_root

        # --------------------------------------------------
        # SYSTEM REFERENCES
        # --------------------------------------------------

        self.event_bus = event_bus
        self.qbit_dialer = qbit_dialer

        self.bios_registry = bios_registry
        self.backup_engine = backup_engine
        self.health_monitor = health_monitor

        # --------------------------------------------------
        # HEARTBEAT CONFIGURATION
        # --------------------------------------------------

        self.interval = max(
            0.01,
            float(interval or 1.0),
        )

        self.enable_qbit = bool(
            enable_qbit
        )

        self.cpu_limit = cpu_limit
        self.mem_limit = mem_limit

        self.module_wait_timeout = (
            module_wait_timeout
        )

        self.monitor_enabled = bool(
            _monitor
        )

        # --------------------------------------------------
        # ASYNC LOOP
        # --------------------------------------------------

        self.loop = loop
        self._loop_owned = False

        # --------------------------------------------------
        # RUNTIME REFERENCES
        #
        # These are attached during boot.
        #
        # Heartbeat does NOT construct QueueLoop or Dialer.
        #
        # Heartbeat also does NOT use QueueLoop as its direct
        # output boundary.
        #
        # Heartbeat's authoritative transport boundary is:
        #
        #     HeartbeatEmitter
        #
        # --------------------------------------------------

        self.qbit_queue_loop = queue_loop
        self.queue_loop = queue_loop
        self.track_system = None
        self.metadata = None

        # --------------------------------------------------
        # AUTHORITATIVE QBIT
        #
        # A Qbit supplied by the authoritative boot/runtime
        # system is adopted and preserved.
        #
        # Heartbeat's Qbit traffic enters the transport
        # pipeline through HeartbeatEmitter.
        #
        # The emitter is the gateway, not QueueLoop.
        #
        # --------------------------------------------------

        self.qbit = None

        if isinstance(
            qbit,
            Qbit,
        ):
            self.qbit = qbit

        elif self.enable_qbit:
            try:
                self.qbit = Qbit()

                logger.info(
                    "[Heartbeat] Authoritative Qbit created | "
                    "qbit=%s",
                    getattr(
                        self.qbit,
                        "qbit_id",
                        getattr(
                            self.qbit,
                            "id",
                            None,
                        ),
                    ),
                )

            except Exception as exc:
                logger.error(
                    "[Heartbeat] Qbit initialization failed: %s",
                    exc,
                )

                self.qbit = None

        # --------------------------------------------------
        # RUNTIME STATE
        # --------------------------------------------------

        self._running = False
        self._thread = None
        self._tick = 0

        self._limp_mode_active = False

        self._deferred_events = deque()

        self._monitor_task = None

        # --------------------------------------------------
        # VECTOR CORE
        # --------------------------------------------------

        self.vector_core = HeartbeatVectorCore()

        # --------------------------------------------------
        # HEARTBEAT EMITTER
        #
        # THIS IS THE AUTHORITATIVE HEARTBEAT QBIT GATEWAY.
        #
        # Heartbeat -> HeartbeatEmitter -> Qbit pipeline
        #
        # The emitter may also receive Qbits/results from the
        # Dialer side and distribute them to EventBus/System.
        #
        # Heartbeat itself never directly calls QueueLoop or
        # QbitDialer for heartbeat-originated transport.
        #
        # --------------------------------------------------

        self.emitter = None

        try:
            self.emitter = HeartbeatEmitter(
                event_bus=self.event_bus,
                qbit_dialer=self.qbit_dialer,
                module_name=self.module_name,
                interval=self.interval,
            )

        except TypeError:
            try:
                self.emitter = HeartbeatEmitter(
                    event_bus=self.event_bus,
                    qbit_dialer=self.qbit_dialer,
                    module_name=self.module_name,
                )

            except Exception as exc:
                logger.warning(
                    "[Heartbeat] HeartbeatEmitter compatibility "
                    "construction failed: %s",
                    exc,
                )

                self.emitter = emit

        except Exception as exc:
            logger.warning(
                "[Heartbeat] HeartbeatEmitter initialization "
                "failed: %s",
                exc,
            )

            self.emitter = emit

        if (
            self.emitter is None
            and emit is not None
        ):
            self.emitter = emit

        # --------------------------------------------------
        # EMITTER QBIT BINDING
        #
        # If the emitter exposes a Qbit reference, bind the
        # authoritative Heartbeat Qbit to it.
        #
        # --------------------------------------------------

        if self.emitter is not None:
            try:
                if hasattr(
                    self.emitter,
                    "qbit",
                ):
                    self.emitter.qbit = self.qbit

            except Exception as exc:
                logger.debug(
                    "[Heartbeat] Initial emitter Qbit binding "
                    "skipped: %s",
                    exc,
                )

        # --------------------------------------------------
        # HEALTH MONITOR BINDING
        #
        # HealthMonitor observes Heartbeat health state.
        # It does not become a second heartbeat clock.
        #
        # --------------------------------------------------

        if (
            self.health_monitor is None
            and HealthMonitor is not None
        ):
            try:
                self.health_monitor = HealthMonitor()
            except Exception as exc:
                logger.debug(
                    "[Heartbeat] HealthMonitor initialization "
                    "deferred: %s",
                    exc,
                )

        if self.health_monitor is not None:
            try:
                if hasattr(
                    self.health_monitor,
                    "heartbeat",
                ):
                    self.health_monitor.heartbeat = self

            except Exception:
                pass

        # --------------------------------------------------
        # BOOT VISIBILITY
        # --------------------------------------------------

        logger.info(
            "[Heartbeat] Initialized | "
            "module=%s | qbit=%s | emitter=%s | dialer=%s | "
            "health_monitor=%s",
            self.module_name,
            (
                getattr(
                    self.qbit,
                    "qbit_id",
                    getattr(
                        self.qbit,
                        "id",
                        None,
                    ),
                )
                if self.qbit is not None
                else None
            ),
            (
                type(
                    self.emitter
                ).__name__
                if self.emitter is not None
                else None
            ),
            (
                type(
                    self.qbit_dialer
                ).__name__
                if self.qbit_dialer is not None
                else None
            ),
            (
                type(
                    self.health_monitor
                ).__name__
                if self.health_monitor is not None
                else None
            ),
        )

        # --------------------------------------------------
        # DIALER ATTACHMENT
        #
        # The Dialer is attached to the existing Heartbeat
        # infrastructure.
        #
        # Heartbeat does NOT become a direct Dialer command
        # source.
        #
        # HeartbeatEmitter remains the authoritative gateway.
        #
        # --------------------------------------------------

        if self.qbit_dialer is not None:
            self.attach_qbit_dialer(
                self.qbit_dialer
            )

        else:
            logger.info(
                "[Heartbeat] QbitDialer deferred | "
                "awaiting authoritative boot binding"
            )

    # ======================================================
    # AUTHORITATIVE QBIT ACCESS
    # ======================================================

    def get_qbit(self):

        return self.qbit

    # ======================================================

    def set_qbit(
        self,
        qbit,
    ):

        if qbit is None:
            return False

        if not isinstance(
            qbit,
            Qbit,
        ):
            logger.warning(
                "[Heartbeat] Rejecting non-Qbit "
                "authoritative carrier | type=%s",
                type(qbit).__name__,
            )

            return False

        self.qbit = qbit

        # --------------------------------------------------
        # EMITTER IS THE AUTHORITATIVE HEARTBEAT GATEWAY
        # --------------------------------------------------

        if self.emitter is not None:
            try:
                if hasattr(
                    self.emitter,
                    "qbit",
                ):
                    self.emitter.qbit = qbit

            except Exception as exc:
                logger.debug(
                    "[Heartbeat] Emitter Qbit synchronization "
                    "skipped: %s",
                    exc,
                )

        # --------------------------------------------------
        # QUEUE LOOP SYNCHRONIZATION
        #
        # QueueLoop may participate in the same authoritative
        # Qbit pipeline, but Heartbeat does not use QueueLoop
        # as its direct emission boundary.
        #
        # --------------------------------------------------

        queue_loop = getattr(
            self,
            "qbit_queue_loop",
            None,
        )

        if queue_loop is not None:
            try:
                if hasattr(
                    queue_loop,
                    "qbit",
                ):
                    queue_loop.qbit = qbit

            except Exception as exc:
                logger.debug(
                    "[Heartbeat] QueueLoop Qbit synchronization "
                    "skipped: %s",
                    exc,
                )

        logger.info(
            "[Heartbeat] Authoritative Qbit updated | "
            "qbit=%s | emitter=%s",
            getattr(
                qbit,
                "qbit_id",
                getattr(
                    qbit,
                    "id",
                    None,
                ),
            ),
            (
                type(
                    self.emitter
                ).__name__
                if self.emitter is not None
                else None
            ),
        )

        return True

    # ======================================================
    # QBIT QUEUE LOOP ATTACHMENT
    # ======================================================

    def attach_qbit_queue_loop(
        self,
        queue_loop,
    ):

        if queue_loop is None:
            logger.warning(
                "[Heartbeat] QueueLoop attachment rejected | "
                "queue_loop=None"
            )

            return False

        self.qbit_queue_loop = queue_loop

        # --------------------------------------------------
        # AUTHORITATIVE QBIT
        # --------------------------------------------------

        if self.qbit is not None:
            try:
                if hasattr(
                    queue_loop,
                    "qbit",
                ):
                    queue_loop.qbit = self.qbit

            except Exception as exc:
                logger.warning(
                    "[Heartbeat] QueueLoop Qbit sync failed: %s",
                    exc,
                )

        # --------------------------------------------------
        # AUTHORITATIVE DIALER
        # --------------------------------------------------

        if self.qbit_dialer is not None:
            try:
                if hasattr(
                    queue_loop,
                    "qbit_dialer",
                ):
                    queue_loop.qbit_dialer = (
                        self.qbit_dialer
                    )

            except Exception as exc:
                logger.warning(
                    "[Heartbeat] QueueLoop Dialer sync failed: %s",
                    exc,
                )

        # --------------------------------------------------
        # EVENT BUS
        # --------------------------------------------------

        try:
            if hasattr(
                queue_loop,
                "event_bus",
            ):
                queue_loop.event_bus = (
                    self.event_bus
                )

        except Exception:
            pass

        # --------------------------------------------------
        # TRACK SYSTEM
        # --------------------------------------------------

        try:
            if self.track_system is not None:
                if hasattr(
                    queue_loop,
                    "track_system",
                ):
                    queue_loop.track_system = (
                        self.track_system
                    )

        except Exception:
            pass

        # --------------------------------------------------
        # METADATA
        # --------------------------------------------------

        try:
            if self.metadata is not None:

                if hasattr(
                    queue_loop,
                    "metadata",
                ):
                    queue_loop.metadata = (
                        self.metadata
                    )

                if hasattr(
                    queue_loop,
                    "qbit_metadata",
                ):
                    queue_loop.qbit_metadata = (
                        self.metadata
                    )

        except Exception:
            pass

        logger.info(
            "[Heartbeat] QbitQueueLoop attached | "
            "loop=%s | qbit=%s | dialer=%s | emitter=%s",
            type(queue_loop).__name__,
            (
                getattr(
                    self.qbit,
                    "qbit_id",
                    getattr(
                        self.qbit,
                        "id",
                        None,
                    ),
                )
                if self.qbit is not None
                else None
            ),
            (
                type(
                    self.qbit_dialer
                ).__name__
                if self.qbit_dialer is not None
                else None
            ),
            (
                type(
                    self.emitter
                ).__name__
                if self.emitter is not None
                else None
            ),
        )

        return True


    # ======================================================
    # POST / SELF TEST
    # ======================================================

    def post_check(self):

        failures = []

        # --------------------------------------------------
        # EVENTBUS
        # --------------------------------------------------

        if self.event_bus is None:
            failures.append("EventBus not connected")

        elif not callable(
            getattr(
                self.event_bus,
                "publish",
                None,
            )
        ):
            failures.append(
                "EventBus.publish unavailable"
            )

        # --------------------------------------------------
        # QBIT
        # --------------------------------------------------

        if self.qbit is None:
            failures.append("Qbit not connected")

        elif not callable(
            getattr(
                self.qbit,
                "process_tick",
                None,
            )
        ):
            failures.append(
                "Qbit.process_tick unavailable"
            )

        # --------------------------------------------------
        # QBIT DIALER
        # --------------------------------------------------

        if self.qbit_dialer is None:
            failures.append(
                "QbitDialer not attached"
            )

        # --------------------------------------------------
        # REPORT
        # --------------------------------------------------

        if failures:
            logger.error(
                "[POST] Heartbeat FAIL | %s",
                " | ".join(failures),
            )

            raise RuntimeError(
                "POST failure: Heartbeat "
                f"{self.module_name} | "
                + " | ".join(failures)
            )

        logger.info(
            "[POST] Heartbeat %s OK | "
            "qbit=%s | dialer=%s | tick=%s",
            self.module_name,
            getattr(
                self.qbit,
                "id",
                None,
            ),
            type(
                self.qbit_dialer
            ).__name__,
            self._tick,
        )

        return True

    # ======================================================
    # START
    # ======================================================

    def start(self):

        # --------------------------------------------------
        # DUPLICATE START PROTECTION
        # --------------------------------------------------

        if self._running:
            logger.debug(
                "[Heartbeat] START ignored | already running | "
                "module=%s",
                self.module_name,
            )
            return False

        self._running = True

        # --------------------------------------------------
        # RESET RUNTIME STATE
        # --------------------------------------------------

        self._limp_mode_active = False

        # Do not reset _tick.
        # Tick continuity is part of Heartbeat state.
        #
        # Do reset stale monitor reference.
        self._monitor_task = None

        # --------------------------------------------------
        # ASYNC LOOP STATUS
        # --------------------------------------------------

        loop_ready = False

        try:
            loop_ready = (
                self.loop is not None
                and self.loop.is_running()
            )

        except Exception:
            loop_ready = False

        # --------------------------------------------------
        # MONITOR
        # --------------------------------------------------

        if self.monitor_enabled:

            if loop_ready:

                try:
                    # Prevent duplicate monitor tasks.
                    if (
                        self._monitor_task is None
                        or self._monitor_task.done()
                    ):
                        self._monitor_task = (
                            self.loop.create_task(
                                self._monitor()
                            )
                        )

                        logger.info(
                            "[Heartbeat] Monitor started | "
                            "loop=%s",
                            id(self.loop),
                        )

                except Exception as exc:
                    logger.warning(
                        "[Heartbeat] Monitor startup failed: %s",
                        exc,
                    )

            else:
                logger.info(
                    "[Heartbeat] Monitor deferred | "
                    "async loop not running"
                )

        # --------------------------------------------------
        # CORE HEARTBEAT THREAD
        # --------------------------------------------------

        try:
            self._thread = threading.Thread(
                target=self._loop,
                daemon=True,
                name=f"Heartbeat-{self.module_name}",
            )

            self._thread.start()

        except Exception as exc:

            self._running = False

            logger.exception(
                "[Heartbeat] CORE thread startup failed: %s",
                exc,
            )

            raise

        # --------------------------------------------------
        # BOOT STATUS
        # --------------------------------------------------

        logger.info(
            "[Heartbeat] STARTED | "
            "module=%s | tick=%s | "
            "qbit=%s | dialer=%s | eventbus=%s | "
            "async_loop=%s | monitor=%s",
            self.module_name,
            self._tick,
            self.qbit is not None,
            self.qbit_dialer is not None,
            self.event_bus is not None,
            loop_ready,
            (
                self._monitor_task is not None
                if self.monitor_enabled
                else False
            ),
        )

        return True

    # ======================================================
    # STOP
    # ======================================================

    def stop(self):

        # --------------------------------------------------
        # DUPLICATE STOP PROTECTION
        # --------------------------------------------------

        if not self._running:
            logger.debug(
                "[Heartbeat] STOP ignored | already stopped | "
                "module=%s",
                self.module_name,
            )
            return False

        # --------------------------------------------------
        # SIGNAL CORE THREAD
        # --------------------------------------------------

        self._running = False

        # --------------------------------------------------
        # CANCEL MONITOR
        # --------------------------------------------------

        monitor_task = self._monitor_task

        self._monitor_task = None

        if monitor_task is not None:

            try:

                if not monitor_task.done():
                    monitor_task.cancel()

                    logger.debug(
                        "[Heartbeat] Monitor cancellation requested"
                    )

            except Exception as exc:
                logger.debug(
                    "[Heartbeat] Monitor cancellation failed: %s",
                    exc,
                )

        # --------------------------------------------------
        # WAIT FOR CORE THREAD
        # --------------------------------------------------

        thread = self._thread

        if thread is not None:

            # Never join ourselves.
            if (
                thread.is_alive()
                and thread is not threading.current_thread()
            ):

                try:
                    thread.join(
                        timeout=max(
                            1.0,
                            min(
                                3.0,
                                self.interval + 1.0,
                            ),
                        )
                    )

                except Exception as exc:
                    logger.debug(
                        "[Heartbeat] CORE thread join failed: %s",
                        exc,
                    )

        # --------------------------------------------------
        # THREAD STATE
        # --------------------------------------------------

        if (
            self._thread is not None
            and not self._thread.is_alive()
        ):
            self._thread = None

        # --------------------------------------------------
        # FINAL STATUS
        # --------------------------------------------------

        logger.info(
            "[Heartbeat] CORE stopped | "
            "module=%s | final_tick=%s",
            self.module_name,
            self._tick,
        )

        return True

    # ======================================================
    # MONITOR
    # ======================================================

    async def _monitor(self):

        logger.debug(
            "[Heartbeat] Monitor started | module=%s",
            self.module_name,
        )

        last_tick = self._tick
        last_health = None

        while self._running:
            try:
                # --------------------------------------------------
                # MONITOR INTERVAL
                # --------------------------------------------------

                await asyncio.sleep(1.0)

                if not self._running:
                    break

                # --------------------------------------------------
                # HEALTH SNAPSHOT
                # --------------------------------------------------

                try:
                    cpu = psutil.cpu_percent(
                        interval=None
                    )

                    mem = psutil.virtual_memory().percent

                except Exception as health_exc:
                    logger.debug(
                        "[Heartbeat] Monitor health read failed: %s",
                        health_exc,
                    )

                    cpu = None
                    mem = None

                # --------------------------------------------------
                # CURRENT STATE
                # --------------------------------------------------

                current_tick = self._tick

                dialer = self.qbit_dialer

                dialer_ready = (
                    dialer is not None
                )

                eventbus_ready = (
                    self.event_bus is not None
                    and callable(
                        getattr(
                            self.event_bus,
                            "publish",
                            None,
                        )
                    )
                )

                loop_ready = (
                    self.loop is not None
                    and self.loop.is_running()
                )

                # --------------------------------------------------
                # QUEUE LOOP VISIBILITY
                # --------------------------------------------------

                queue_loop = None

                if dialer is not None:

                    queue_loop = getattr(
                        dialer,
                        "qbit_queue_loop",
                        None,
                    )

                    if queue_loop is None:
                        queue_loop = getattr(
                            dialer,
                            "queue_loop",
                            None,
                        )

                queue_ready = (
                    queue_loop is not None
                )

                # --------------------------------------------------
                # HEALTH FLAGS
                # --------------------------------------------------

                cpu_pressure = (
                    cpu is not None
                    and cpu > self.cpu_limit
                )

                memory_pressure = (
                    mem is not None
                    and mem > self.mem_limit
                )

                healthy = (
                    cpu is not None
                    and mem is not None
                    and not cpu_pressure
                    and not memory_pressure
                )

                flags = {
                    "heartbeat_running": self._running,
                    "heartbeat_progressing": (
                        current_tick > last_tick
                    ),
                    "qbit_enabled": self.enable_qbit,
                    "qbit_ready": self.qbit is not None,
                    "dialer_ready": dialer_ready,
                    "queue_loop_ready": queue_ready,
                    "eventbus_ready": eventbus_ready,
                    "async_loop_ready": loop_ready,
                    "cpu_pressure": cpu_pressure,
                    "memory_pressure": memory_pressure,
                    "limp_mode": self._limp_mode_active,
                    "healthy": healthy,
                }

                # --------------------------------------------------
                # MONITOR METADATA
                # --------------------------------------------------

                metadata = {
                    "event": "HEARTBEAT_HEALTH",
                    "track_id": (
                        f"HEALTH-{self.module_name}-"
                        f"{current_tick}"
                    ),
                    "source": self.module_name,
                    "channel": CHANNEL_SYSTEM,
                    "tick": current_tick,
                    "timestamp": time.time(),

                    "health": {
                        "cpu": cpu,
                        "memory": mem,
                        "cpu_limit": self.cpu_limit,
                        "memory_limit": self.mem_limit,
                    },

                    "runtime": {
                        "dialer": (
                            type(dialer).__name__
                            if dialer
                            else None
                        ),
                        "queue_loop": (
                            type(queue_loop).__name__
                            if queue_loop
                            else None
                        ),
                        "eventbus": (
                            type(self.event_bus).__name__
                            if self.event_bus
                            else None
                        ),
                    },

                    "flags": flags,
                }

                # --------------------------------------------------
                # TRACK CONTEXT
                # --------------------------------------------------

                try:
                    TrackContext.write(
                        metadata["track_id"]
                    )
                except Exception:
                    pass

                # --------------------------------------------------
                # CHANGE DETECTION
                # --------------------------------------------------
                #
                # Avoid flooding EventBus with identical health
                # snapshots unless the heartbeat is under pressure.
                # --------------------------------------------------

                health_signature = (
                    round(cpu, 1) if cpu is not None else None,
                    round(mem, 1) if mem is not None else None,
                    self._limp_mode_active,
                    dialer_ready,
                    queue_ready,
                    eventbus_ready,
                    loop_ready,
                )

                state_changed = (
                    health_signature != last_health
                )

                # Always publish pressure/limp conditions.
                publish_monitor = (
                    state_changed
                    or cpu_pressure
                    or memory_pressure
                    or self._limp_mode_active
                )

                if publish_monitor:

                    self.safe_publish(
                        "HEARTBEAT_HEALTH",
                        TrackedData(
                            payload=metadata,
                            source_id=self.module_name,
                            channel=CHANNEL_SYSTEM,
                        ),
                    )

                    last_health = health_signature

                # --------------------------------------------------
                # OPTIONAL METADATA SUBSYSTEM
                # --------------------------------------------------

                metadata_store = getattr(
                    self,
                    "metadata",
                    None,
                )

                if metadata_store is not None:

                    record = getattr(
                        metadata_store,
                        "record",
                        None,
                    )

                    if callable(record):

                        try:
                            record(
                                source=self.module_name,
                                event="HEARTBEAT_HEALTH",
                                track_id=metadata[
                                    "track_id"
                                ],
                                tick=current_tick,
                                health=metadata[
                                    "health"
                                ],
                                flags=flags,
                            )

                        except Exception as metadata_exc:
                            logger.debug(
                                "[Heartbeat] Health metadata "
                                "record failed: %s",
                                metadata_exc,
                            )

                # --------------------------------------------------
                # HEALTH LOGGING
                # --------------------------------------------------

                logger.debug(
                    "[Heartbeat] Monitor | "
                    "tick=%s CPU=%s%% MEM=%s%% "
                    "dialer=%s queue=%s limp=%s",
                    current_tick,
                    cpu,
                    mem,
                    dialer_ready,
                    queue_ready,
                    self._limp_mode_active,
                )

                # --------------------------------------------------
                # TICK PROGRESS
                # --------------------------------------------------

                last_tick = current_tick

            except asyncio.CancelledError:
                logger.debug(
                    "[Heartbeat] Monitor cancelled"
                )
                break

            except Exception as exc:
                logger.warning(
                    "[Heartbeat] Monitor error: %s",
                    exc,
                )

                # Keep monitor alive without creating a second
                # heartbeat clock.
                try:
                    await asyncio.sleep(1.0)
                except asyncio.CancelledError:
                    break

        logger.debug(
            "[Heartbeat] Monitor stopped | module=%s",
            self.module_name,
        )

    # ======================================================
    # MAIN HEARTBEAT LOOP
    # ======================================================

    def _loop(self):
        logger.info("[Heartbeat] CORE loop active")

        # --------------------------------------------------
        # WAIT FOR DEPENDENCIES
        # --------------------------------------------------

        self._wait_for_modules(self._tick)

        while self._running:
            try:
                self._tick += 1

                cpu, mem = self._check_system_health()

                # --------------------------------------------------
                # ADAPTIVE INTERVAL
                # --------------------------------------------------

                self.interval = max(
                    0.05,
                    min(
                        1.5,
                        1.0 * (
                            cpu / 50.0 +
                            mem / 50.0
                        ),
                    ),
                )

                # --------------------------------------------------
                # HEARTBEAT PAYLOAD
                # --------------------------------------------------

                tick_payload = {
                    "heartbeat": True,
                    "tick": self._tick,
                    "timestamp": time.time(),
                    "core_status": getattr(
                        self,
                        "core_status",
                        None,
                    ),
                    "module": self.module_name,
                }

                try:
                    self.qbit.payload.update(tick_payload)
                except Exception:
                    try:
                        self.qbit.payload = dict(
                            tick_payload
                        )
                    except Exception:
                        pass

                # --------------------------------------------------
                # REAL QBIT API
                # --------------------------------------------------
                #
                # IMPORTANT:
                # The runtime proved that Qbit.process_tick()
                # does NOT accept core_status/system_status/
                # user_status keyword arguments.
                #
                # Therefore we call ONLY:
                #
                #     process_tick(tick)
                #
                # --------------------------------------------------

                vector = self.qbit.process_tick(
                    self._tick
                )

                # --------------------------------------------------
                # EMIT
                # --------------------------------------------------

                self.emit(
                    vector,
                    self._tick,
                )

                # --------------------------------------------------
                # BIOS
                # --------------------------------------------------

                self.control_bios()

                # --------------------------------------------------
                # BACKUP
                # --------------------------------------------------

                self._backup_state()

                # --------------------------------------------------
                # CLOCK
                # --------------------------------------------------

                time.sleep(self.interval)

            except Exception as exc:
                logger.exception(
                    "[Heartbeat] CORE loop error: %s",
                    exc,
                )

                # Prevent an exception loop from consuming
                # the entire CPU.
                time.sleep(0.25)

    # ======================================================
    # WAIT FOR MODULES
    # ======================================================

    def _wait_for_modules(self, tick=0):
        start_time = time.time()
        first_cycle_done = False

        while (
            self._running
            and (
                time.time() - start_time
            ) < self.module_wait_timeout
        ):
            all_ready = True

            # --------------------------------------------------
            # QBIT DIALER
            # --------------------------------------------------

            if self.qbit_dialer is None:
                all_ready = False

            # --------------------------------------------------
            # EVENTBUS
            # --------------------------------------------------

            if (
                self.event_bus is None
                or not hasattr(
                    self.event_bus,
                    "publish",
                )
            ):
                all_ready = False

            # --------------------------------------------------
            # READY
            # --------------------------------------------------

            if all_ready and not first_cycle_done:
                first_cycle_done = True

                self._flush_deferred_events()

                self._initial_qbit_feed(
                    self._tick
                )

                break

            time.sleep(0.05)

        if not first_cycle_done:
            logger.warning(
                "[Heartbeat] Modules not fully ready | "
                "initial Qbit feed deferred"
            )

            # We deliberately do not invent a QbitDialer here.
            # The real QbitDialer should be attached by boot.
            if self.qbit_dialer is not None:
                self._initial_qbit_feed(
                    self._tick
                )

    # ======================================================
    # DEFERRED EVENT FLUSH
    # ======================================================

    def _flush_deferred_events(self):

        if not self._deferred_events:
            return 0

        flushed = 0
        remaining = deque()

        while self._deferred_events:
            event_name, payload = (
                self._deferred_events.popleft()
            )

            try:
                delivered = self.safe_publish(
                    event_name,
                    payload,
                    defer_on_failure=False,
                )

                if delivered:
                    flushed += 1
                else:
                    # Do not silently destroy an event that still
                    # could not be delivered.
                    remaining.append(
                        (event_name, payload)
                    )

            except Exception as exc:
                logger.warning(
                    "[Heartbeat] Deferred event flush failed | "
                    "event=%s | error=%s",
                    event_name,
                    exc,
                )

                remaining.append(
                    (event_name, payload)
                )

        # Restore events that still need delivery.
        while remaining:
            self._deferred_events.appendleft(
                remaining.pop()
            )

        if flushed:
            logger.debug(
                "[Heartbeat] Deferred events flushed | count=%s",
                flushed,
            )

        return flushed

    # ======================================================
    # INITIAL QBIT FEED
    # ======================================================

    def _initial_qbit_feed(self, tick=None):

        if tick is None:
            tick = self._tick

        # --------------------------------------------------
        # TRACK ID
        # --------------------------------------------------

        track_id = (
            f"QBIT-{self.module_name}-{tick}"
        )

        timestamp = time.time()

        # --------------------------------------------------
        # HEALTH SNAPSHOT
        # --------------------------------------------------

        try:
            cpu = psutil.cpu_percent(
                interval=None
            )

            mem = psutil.virtual_memory().percent

        except Exception:
            cpu = None
            mem = None

        # --------------------------------------------------
        # FLAGS
        # --------------------------------------------------

        flags = {
            "heartbeat": True,
            "initial_sync": True,
            "qbit_tick": True,
            "queue_ready": self.qbit_dialer is not None,
            "limp_mode": self._limp_mode_active,
            "health_valid": (
                cpu is not None
                and mem is not None
            ),
        }

        # --------------------------------------------------
        # REAL QBIT PROCESSING
        # --------------------------------------------------

        try:
            vector = self.qbit.process_tick(
                tick
            )

        except Exception as exc:
            logger.warning(
                "[Heartbeat] Initial Qbit processing failed | "
                "tick=%s | error=%s",
                tick,
                exc,
            )

            # --------------------------------------------------
            # FAILURE METADATA
            # --------------------------------------------------

            failure_payload = {
                "event": "QBIT_INITIALIZATION_FAILED",
                "track_id": track_id,
                "tick": tick,
                "timestamp": timestamp,
                "module": self.module_name,
                "error_type": type(exc).__name__,
                "error": str(exc),
                "flags": flags,
                "health": {
                    "cpu": cpu,
                    "memory": mem,
                },
            }

            self.safe_publish(
                QBIT_RESULT,
                TrackedData(
                    payload=failure_payload,
                    source_id=self.module_name,
                    channel=CHANNEL_QBIT,
                ),
            )

            return None

        # --------------------------------------------------
        # QBIT METADATA ENVELOPE
        # --------------------------------------------------

        qbit_payload = {
            "event": "QBIT_INITIAL_SYNC",
            "track_id": track_id,
            "tick": tick,
            "timestamp": timestamp,
            "module": self.module_name,

            # Real Qbit result.
            "vector": vector,

            # Runtime context.
            "health": {
                "cpu": cpu,
                "memory": mem,
            },

            # Runtime flags.
            "flags": flags,

            # Routing metadata.
            "source": self.module_name,
            "source_channel": CHANNEL_QBIT,
            "target": "QBIT_DIALER",
            "queue_target": "QBIT_QUEUE_LOOP",
        }

        # --------------------------------------------------
        # TRACK CONTEXT
        # --------------------------------------------------

        try:
            TrackContext.write(
                track_id
            )
        except Exception:
            pass

        # --------------------------------------------------
        # EVENTBUS
        # --------------------------------------------------

        self.safe_publish(
            QBIT_RESULT,
            TrackedData(
                payload=qbit_payload,
                source_id=self.module_name,
                channel=CHANNEL_QBIT,
            ),
        )

        # --------------------------------------------------
        # QBIT DIALER / QUEUE
        # --------------------------------------------------

        if self.qbit_dialer is not None:

            # ----------------------------------------------
            # PRIMARY DATA PATH
            # ----------------------------------------------

            submitted = self._submit_dialer(
                "push_data",
                qbit_payload,
                track_id=track_id,
            )

            # ----------------------------------------------
            # EMIT / OBSERVABILITY PATH
            # ----------------------------------------------

            emitted = self._emit_to_dialer(
                qbit_payload,
                track_id=track_id,
            )

            flags["queue_submitted"] = submitted
            flags["dialer_emitted"] = emitted

        else:
            flags["queue_submitted"] = False
            flags["dialer_emitted"] = False

            logger.debug(
                "[Heartbeat] Initial Qbit feed waiting for "
                "QbitDialer | track=%s",
                track_id,
            )

        # --------------------------------------------------
        # FINAL METADATA UPDATE
        # --------------------------------------------------

        qbit_payload["flags"] = flags

        logger.info(
            "[Heartbeat] Initial Qbit synchronization complete | "
            "tick=%s | track=%s | queue=%s | emit=%s",
            tick,
            track_id,
            flags["queue_submitted"],
            flags["dialer_emitted"],
        )

        return vector

    # ======================================================
    # EMIT HEARTBEAT / VECTOR
    # ======================================================

    def emit(self, vector, tick):
        now = time.time()

        tick_id = (
            f"{self.module_name}-{tick}"
        )

        # --------------------------------------------------
        # QBIT METADATA
        # --------------------------------------------------

        qbit_track_id = (
            f"QBIT-{tick_id}"
        )

        core_track_id = (
            f"CORE-{tick_id}"
        )

        system_track_id = (
            f"SYS-{tick_id}"
        )

        user_track_id = (
            f"USER-{tick_id}"
        )

        vector_track_id = (
            f"VECTOR-{tick_id}"
        )

        # --------------------------------------------------
        # EVENT PUBLISHER
        # --------------------------------------------------

        def _publish(
            channel,
            payload,
        ):
            td = TrackedData(
                payload=payload,
                source_id=self.module_name,
                channel=channel,
            )

            try:
                self.safe_publish(
                    channel,
                    td,
                )

            except Exception:
                self._deferred_events.append(
                    (channel, td)
                )

            TrackContext.write(
                td.payload.get(
                    "track_id",
                    "UNKNOWN",
                )
            )

            return td

        # --------------------------------------------------
        # CORE
        # --------------------------------------------------

        _publish(
            CHANNEL_CORE,
            {
                "track_id": core_track_id,
                "channel": CHANNEL_CORE,
                "tick": tick,
                "timestamp": now,
                "status": "power_on",
                "module": self.module_name,
            },
        )

        # --------------------------------------------------
        # SYSTEM
        # --------------------------------------------------

        _publish(
            CHANNEL_SYSTEM,
            {
                "track_id": system_track_id,
                "channel": CHANNEL_SYSTEM,
                "tick": tick,
                "timestamp": now,
                "status": "active",
                "module": self.module_name,
            },
        )

        # --------------------------------------------------
        # USER
        # --------------------------------------------------

        _publish(
            CHANNEL_USER,
            {
                "track_id": user_track_id,
                "channel": CHANNEL_USER,
                "tick": tick,
                "timestamp": now,
                "module": self.module_name,
            },
        )

        # --------------------------------------------------
        # QBIT / VECTOR
        # --------------------------------------------------

        if self.enable_qbit:
            qbit_value = None

            if isinstance(vector, dict):
                qbit_value = vector.get(
                    "qbit_value"
                )

            qbit_td = _publish(
                CHANNEL_QBIT,
                {
                    "track_id": qbit_track_id,
                    "channel": CHANNEL_QBIT,
                    "tick": tick,
                    "timestamp": now,
                    "qbit": qbit_value,
                    "vector": vector,
                    "module": self.module_name,
                },
            )

            vector_td = _publish(
                CHANNEL_VECTOR,
                {
                    "track_id": vector_track_id,
                    "channel": CHANNEL_VECTOR,
                    "tick": tick,
                    "timestamp": now,
                    "vector": vector,
                    "module": self.module_name,
                },
            )

            # --------------------------------------------------
            # QBIT DIALER
            # --------------------------------------------------

            if self.qbit_dialer is not None:
                self._submit_dialer(
                    "push_data",
                    vector,
                    track_id=vector_td.payload[
                        "track_id"
                    ],
                )

#                self._emit_to_dialer(
#                    vector,
#                    track_id=vector_td.payload[
#                        "track_id"
#                    ],
#                )

        # --------------------------------------------------
        # HEARTBEAT EVENT
        # --------------------------------------------------

        self.safe_publish(
            HEARTBEAT,
            TrackedData(
                payload={
                    "track_id": (
                        f"HEARTBEAT-{tick_id}"
                    ),
                    "channel": HEARTBEAT,
                    "tick": tick,
                    "timestamp": now,
                    "module": self.module_name,
                },
                source_id=self.module_name,
                channel=HEARTBEAT,
            ),
        )

    # ======================================================
    # ASYNC QBIT DIALER SUBMISSION
    #
    # HEARTBEAT -> HEARTBEAT EMITTER
    #           -> EXISTING QBIT
    #           -> QBIT_QUEUE_LOOP
    #           -> QbitDialer
    #
    # IMPORTANT:
    #
    # Heartbeat does NOT execute commands.
    #
    # Heartbeat emits a cognitive pulse.
    #
    # The existing HeartbeatEmitter / QbitQueueLoop owns
    # transport of the heartbeat Qbit.
    #
    # QbitDialer is reached ONLY after the Qbit enters the
    # authoritative QbitQueueLoop.
    #
    # QbitDialer is responsible for:
    #
    #     RECEIVE
    #       |
    #       v
    #     _process_received_qbit()
    #       |
    #       v
    #     _plan()
    #       |
    #       v
    #     ComputeBrain
    #       |
    #       v
    #     ThoughtPacket
    #       |
    #       v
    #     TransformerBrain
    #       |
    #       v
    #     _build_cognitive_command()
    #       |
    #       v
    #     submit_command()
    #
    # The heartbeat packet therefore carries INTENT and
    # provenance, not an executable command.
    # ======================================================

    def _submit_dialer(
        self,
        method_name,
        data,
        track_id=None,
    ):

        # ==================================================
        # EXISTING AUTHORITATIVE QBIT
        #
        # Do NOT create another Qbit.
        # Do NOT replace the received/authoritative Qbit.
        # ==================================================

        qbit = getattr(
            self,
            "qbit",
            None,
        )

        if qbit is None:

            logger.debug(
                "[Heartbeat] Authoritative Qbit unavailable | "
                "submission deferred"
            )

            return False

        # ==================================================
        # QBIT IDENTITY
        # ==================================================

        qbit_id = getattr(
            qbit,
            "id",
            None,
        )

        if qbit_id is None:

            qbit_id = getattr(
                qbit,
                "qbit_id",
                None,
            )

        # ==================================================
        # TRACK ID
        # ==================================================

        if track_id is None:

            track_id = (
                f"QBIT."
                f"{self.module_name}."
                f"{self._tick}"
            )

        # ==================================================
        # HEARTBEAT COGNITIVE DIRECTIVE
        #
        # This is NOT an executable command.
        #
        # It tells QbitDialer to enter planning/cognition
        # after the Qbit has passed through QbitQueueLoop.
        # ==================================================

        heartbeat_intent = "HEARTBEAT_PLAN"

        heartbeat_action = "PLAN"

        cognitive_stage = "PLAN"

        # ==================================================
        # QBIT METADATA
        # ==================================================

        qbit_metadata = {

            "qbit_id": qbit_id,

            "qbit_type": type(
                qbit
            ).__name__,

            "qbit_enabled": bool(
                self.enable_qbit
            ),

            "tick": self._tick,

            "track_id": track_id,

            "source": self.module_name,

            "source_id": self.module_name,

            "channel": CHANNEL_QBIT,

            "timestamp": time.time(),

            # ----------------------------------------------
            # AUTHORITATIVE ROUTING
            # ----------------------------------------------

            "route": "QBIT_QUEUE_LOOP",

            "target": "QBIT_DIALER",

            "queue": "QBIT_QUEUE",

            "processor": "QBIT_DIALER",

            # ----------------------------------------------
            # COGNITIVE ROUTING
            # ----------------------------------------------

            "intent": heartbeat_intent,

            "action": heartbeat_action,

            "cognitive_stage": cognitive_stage,

            "requires_planning": True,

            "requires_cognition": True,

            # ----------------------------------------------
            # PROVENANCE
            # ----------------------------------------------

            "origin": "HEARTBEAT",

            "heartbeat_origin": True,

            "heartbeat_tick": self._tick,

            # ----------------------------------------------
            # AUTHORITY
            #
            # Heartbeat owns the pulse.
            # QbitQueueLoop owns transport.
            # QbitDialer owns command admission/execution.
            # ----------------------------------------------

            "heartbeat_authority": True,

            "qbit_authority": True,

            "queue_authority": "QbitQueueLoop",

            "dialer_authority": True,

            "command_authority": "QbitDialer",

            "execution_authority": "QbitDialer",
        }

        # ==================================================
        # QBIT PAYLOAD
        #
        # Preserve the heartbeat data exactly.
        #
        # Do not stringify it.
        # Do not convert it into a command.
        # ==================================================

        qbit_payload = {

            "data": data,

            # ----------------------------------------------
            # EXISTING QBIT IDENTITY
            # ----------------------------------------------

            "qbit": qbit,

            "qbit_id": qbit_id,

            "metadata": qbit_metadata,

            # ----------------------------------------------
            # COGNITIVE DIRECTIVE
            # ----------------------------------------------

            "intent": heartbeat_intent,

            "action": heartbeat_action,

            "cognitive_stage": cognitive_stage,

            "requires_planning": True,

            "requires_cognition": True,

            # ----------------------------------------------
            # PROVENANCE
            # ----------------------------------------------

            "source": self.module_name,

            "origin": "HEARTBEAT",

            "heartbeat_origin": True,

            # ----------------------------------------------
            # TRACK CONTEXT
            # ----------------------------------------------

            "track": {

                "track_id": track_id,

                "channel": CHANNEL_QBIT,

                "source": self.module_name,

            },

            # ----------------------------------------------
            # AUTHORITATIVE ROUTING
            # ----------------------------------------------

            "routing": {

                "source": "HEARTBEAT",

                "transport": "HEARTBEAT_EMITTER",

                "queue": "QBIT_QUEUE",

                "target": "QBIT_DIALER",

                "next": "QBIT_DIALER",

                "processor": "QBIT_DIALER",

                "stage": "PLAN",

            },

            # ----------------------------------------------
            # HEARTBEAT CONTEXT
            # ----------------------------------------------

            "heartbeat": {

                "tick": self._tick,

                "timestamp": time.time(),

                "intent": heartbeat_intent,

                "action": heartbeat_action,

                "stage": cognitive_stage,

                "requires_planning": True,

                "requires_cognition": True,

            },

        }

        # ==================================================
        # HEARTBEAT EMITTER
        #
        # Use the existing HeartbeatEmitter when available.
        #
        # The emitter is the heartbeat-side transport layer.
        # It must forward the existing Qbit into the
        # authoritative QbitQueueLoop.
        # ==================================================

        emitter = getattr(
            self,
            "heartbeat_emitter",
            None,
        )

        if emitter is None:

            emitter = getattr(
                self,
                "_heartbeat_emitter",
                None,
            )

        if emitter is None:

            logger.warning(
                "[Heartbeat] HeartbeatEmitter unavailable | "
                "Qbit submission deferred | "
                "qbit=%s | track=%s",
                qbit_id,
                track_id,
            )

            return False

        # ==================================================
        # AUTHORITATIVE QBIT QUEUE LOOP
        #
        # Prefer the queue attached to HeartbeatEmitter.
        # ==================================================

        queue_loop = getattr(
            emitter,
            "qbit_queue_loop",
            None,
        )

        if queue_loop is None:

            queue_loop = getattr(
                emitter,
                "queue_loop",
                None,
            )

        if queue_loop is None:

            queue_loop = getattr(
                self,
                "qbit_queue_loop",
                None,
            )

        if queue_loop is None:

            logger.warning(
                "[Heartbeat] QbitQueueLoop unavailable | "
                "Qbit submission deferred | "
                "qbit=%s | track=%s",
                qbit_id,
                track_id,
            )

            return False

        # ==================================================
        # LOG
        # ==================================================

        logger.debug(
            "[Heartbeat] Cognitive Qbit -> "
            "HeartbeatEmitter -> QbitQueueLoop | "
            "qbit=%s | track=%s | "
            "intent=%s | stage=%s",
            qbit_id,
            track_id,
            heartbeat_intent,
            cognitive_stage,
        )

        # ==================================================
        # AUTHORITATIVE QUEUE SUBMISSION
        #
        # This is the actual handoff.
        #
        # QbitQueueLoop then becomes responsible for getting
        # the Qbit to QbitDialer.
        # ==================================================

        submit_method = getattr(
            queue_loop,
            "submit_qbit_command",
            None,
        )

        if not callable(
            submit_method
        ):

            submit_method = getattr(
                queue_loop,
                "submit_qbit",
                None,
            )

        if not callable(
            submit_method
        ):

            logger.warning(
                "[Heartbeat] QbitQueueLoop submission method "
                "unavailable | qbit=%s | track=%s",
                qbit_id,
                track_id,
            )

            return False

        # ==================================================
        # QUEUE SUBMISSION
        # ==================================================

        try:

            result = submit_method(
                qbit_payload,
                track_id=track_id,
            )

        except TypeError as exc:

            # ==================================================
            # LEGACY QUEUE API COMPATIBILITY
            # ==================================================

            if "track_id" not in str(exc):

                logger.warning(
                    "[Heartbeat] QbitQueueLoop submission failed: %s",
                    exc,
                )

                return False

            try:

                result = submit_method(
                    qbit_payload,
                )

            except Exception as retry_exc:

                logger.warning(
                    "[Heartbeat] QbitQueueLoop fallback "
                    "submission failed: %s",
                    retry_exc,
                )

                return False

        except Exception as exc:

            logger.warning(
                "[Heartbeat] QbitQueueLoop submission failed: %s",
                exc,
            )

            return False

        # ==================================================
        # ASYNC RESULT
        # ==================================================

        if inspect.isawaitable(
            result
        ):

            scheduled = self._schedule_coroutine(
                result,
                "qbit_queue_loop",
            )

            if scheduled:

                logger.debug(
                    "[Heartbeat] Cognitive Qbit queued | "
                    "transport=HeartbeatEmitter | "
                    "queue=QbitQueueLoop | "
                    "qbit=%s | track=%s | stage=PLAN",
                    qbit_id,
                    track_id,
                )

            return scheduled

        # ==================================================
        # SYNCHRONOUS RESULT
        # ==================================================

        logger.debug(
            "[Heartbeat] Cognitive Qbit queued | "
            "transport=HeartbeatEmitter | "
            "queue=QbitQueueLoop | "
            "qbit=%s | track=%s | stage=PLAN",
            qbit_id,
            track_id,
        )

        return True
    # ======================================================
    # COROUTINE SCHEDULER
    # ======================================================

    def _schedule_coroutine(
        self,
        coroutine,
        operation="dialer",
    ):

        if coroutine is None:
            return False

        # --------------------------------------------------
        # VALIDATE LOOP
        # --------------------------------------------------

        loop = self.loop

        if loop is None:
            logger.warning(
                "[Heartbeat] Async %s rejected | "
                "no asyncio loop attached",
                operation,
            )

            self._close_coroutine_safely(coroutine)
            return False

        # --------------------------------------------------
        # LOOP MUST BE RUNNING
        # --------------------------------------------------

        try:
            if not loop.is_running():
                logger.debug(
                    "[Heartbeat] Async %s deferred | "
                    "event loop not running",
                    operation,
                )

                self._close_coroutine_safely(coroutine)
                return False

        except Exception as exc:
            logger.warning(
                "[Heartbeat] Async %s loop check failed: %s",
                operation,
                exc,
            )

            self._close_coroutine_safely(coroutine)
            return False

        # --------------------------------------------------
        # SCHEDULE ON AUTHORITATIVE LOOP
        # --------------------------------------------------

        try:
            future = asyncio.run_coroutine_threadsafe(
                coroutine,
                loop,
            )

        except Exception as exc:
            logger.warning(
                "[Heartbeat] Async %s scheduling failed: %s",
                operation,
                exc,
            )

            self._close_coroutine_safely(coroutine)
            return False

        # --------------------------------------------------
        # COMPLETION CALLBACK
        # --------------------------------------------------

        try:
            future.add_done_callback(
                lambda completed_future: (
                    self._dialer_future_done(
                        completed_future,
                        operation=operation,
                    )
                )
            )

        except Exception as exc:
            logger.warning(
                "[Heartbeat] Async %s callback registration "
                "failed: %s",
                operation,
                exc,
            )

            # The coroutine is already owned by the Future.
            # Do NOT close it here.
            return True

        # --------------------------------------------------
        # SUCCESS
        # --------------------------------------------------

        logger.debug(
            "[Heartbeat] Async %s scheduled | tick=%s",
            operation,
            self._tick,
        )

        return True

    # ======================================================
    # SAFE COROUTINE CLOSE
    # ======================================================

    def _close_coroutine_safely(
        self,
        coroutine,
    ):

        if coroutine is None:
            return

        try:
            close_method = getattr(
                coroutine,
                "close",
                None,
            )

            if callable(close_method):
                close_method()

        except Exception:
            pass

    # ======================================================
    # FUTURE CALLBACK
    # ======================================================

    def _dialer_future_done(
        self,
        future,
        operation="dialer",
    ):

        if future is None:
            return

        try:
            result = future.result()

            logger.debug(
                "[Heartbeat] Async %s completed | "
                "tick=%s | result_type=%s",
                operation,
                self._tick,
                type(result).__name__,
            )

            # --------------------------------------------------
            # OPTIONAL RESULT METADATA
            # --------------------------------------------------
            #
            # If the Dialer returns a metadata-bearing result,
            # preserve it for observability without changing
            # the Qbit API.
            #
            # Heartbeat does NOT reinterpret the result.
            # --------------------------------------------------

            if result is not None:
                try:
                    self._record_async_result(
                        operation,
                        result,
                    )
                except Exception:
                    pass

        except asyncio.CancelledError:
            logger.debug(
                "[Heartbeat] Async %s cancelled | tick=%s",
                operation,
                self._tick,
            )

        except Exception as exc:
            logger.warning(
                "[Heartbeat] Async %s failed | "
                "tick=%s | error=%s",
                operation,
                self._tick,
                exc,
            )

            # --------------------------------------------------
            # FAILURE METADATA
            # --------------------------------------------------

            try:
                self._record_async_failure(
                    operation,
                    exc,
                )
            except Exception:
                pass

    # ======================================================
    # ASYNC RESULT METADATA
    # ======================================================

    def _record_async_result(
        self,
        operation,
        result,
    ):

        metadata = getattr(
            self,
            "metadata",
            None,
        )

        if metadata is None:
            return

        record = getattr(
            metadata,
            "record",
            None,
        )

        if not callable(record):
            return

        record(
            source=self.module_name,
            event="ASYNC_COMPLETE",
            operation=operation,
            tick=self._tick,
            result_type=type(result).__name__,
            timestamp=time.time(),
        )

    # ======================================================
    # ASYNC FAILURE METADATA
    # ======================================================

    def _record_async_failure(
        self,
        operation,
        error,
    ):

        metadata = getattr(
            self,
            "metadata",
            None,
        )

        if metadata is None:
            return

        record = getattr(
            metadata,
            "record",
            None,
        )

        if not callable(record):
            return

        record(
            source=self.module_name,
            event="ASYNC_FAILURE",
            operation=operation,
            tick=self._tick,
            error_type=type(error).__name__,
            error=str(error),
            timestamp=time.time(),
        )

    # ======================================================
    # DIALER EMIT COMPATIBILITY BRIDGE
    # ======================================================

    def _emit_to_dialer(
        self,
        payload,
        track_id=None,
    ):

        dialer = self.qbit_dialer

        if dialer is None:
            logger.debug(
                "[Heartbeat] QbitDialer unavailable; "
                "emit deferred"
            )
            return False

        emit_method = getattr(
            dialer,
            "emit",
            None,
        )

        if not callable(emit_method):
            logger.debug(
                "[Heartbeat] QbitDialer emit() unavailable"
            )
            return False

        # --------------------------------------------------
        # TRACK ID
        # --------------------------------------------------

        if track_id is None:
            track_id = (
                f"HEARTBEAT-"
                f"{self.module_name}-"
                f"{self._tick}"
            )

        # --------------------------------------------------
        # STRUCTURED PAYLOAD
        # --------------------------------------------------

        if isinstance(payload, dict):
            dialer_payload = dict(payload)
        else:
            dialer_payload = {
                "data": payload,
            }

        # --------------------------------------------------
        # AUTHORITATIVE METADATA
        # --------------------------------------------------

        health = dict(
            getattr(
                self,
                "health",
                {},
            )
        )

        health_metadata = dict(
            getattr(
                self,
                "health_metadata",
                {},
            )
        )

        health_flags = dict(
            getattr(
                self,
                "health_flags",
                {},
            )
        )

        # --------------------------------------------------
        # PRESERVE EXISTING PAYLOAD VALUES
        # --------------------------------------------------

        dialer_payload.setdefault(
            "track_id",
            track_id,
        )

        dialer_payload.setdefault(
            "channel",
            CHANNEL_QBIT,
        )

        dialer_payload.setdefault(
            "source",
            self.module_name,
        )

        dialer_payload.setdefault(
            "tick",
            self._tick,
        )

        dialer_payload.setdefault(
            "timestamp",
            time.time(),
        )

        # --------------------------------------------------
        # RUNTIME CONTEXT
        # --------------------------------------------------

        dialer_payload.setdefault(
            "health",
            health,
        )

        dialer_payload.setdefault(
            "metadata",
            health_metadata,
        )

        dialer_payload.setdefault(
            "flags",
            health_flags,
        )

        dialer_payload.setdefault(
            "qbit_id",
            getattr(
                self.qbit,
                "id",
                None,
            ),
        )

        dialer_payload.setdefault(
            "qbit_enabled",
            bool(
                self.enable_qbit
            ),
        )

        # --------------------------------------------------
        # DIALER METADATA
        # --------------------------------------------------

        dialer_payload[
            "dialer"
        ] = type(
            dialer
        ).__name__

        dialer_payload[
            "pipeline"
        ] = "QBIT_DIALER"

        # --------------------------------------------------
        # TRACK CONTEXT
        # --------------------------------------------------

        try:
            TrackContext.write(
                track_id
            )
        except Exception:
            pass

        # --------------------------------------------------
        # EMIT
        # --------------------------------------------------

        try:
            result = emit_method(
                dialer_payload,
                track_id=track_id,
            )

        except TypeError as exc:

            # --------------------------------------------------
            # LEGACY EMITTER
            # --------------------------------------------------

            error_text = str(
                exc
            ).lower()

            if "track_id" not in error_text:
                logger.warning(
                    "[Heartbeat] QbitDialer emit failed | "
                    "track=%s | error=%s",
                    track_id,
                    exc,
                )
                return False

            try:
                result = emit_method(
                    dialer_payload
                )

            except Exception as retry_exc:
                logger.warning(
                    "[Heartbeat] QbitDialer legacy emit "
                    "failed | track=%s | error=%s",
                    track_id,
                    retry_exc,
                )
                return False

        except Exception as exc:
            logger.warning(
                "[Heartbeat] QbitDialer emit failed | "
                "track=%s | error=%s",
                track_id,
                exc,
            )
            return False

        # --------------------------------------------------
        # ASYNC EMIT
        # --------------------------------------------------

        if inspect.isawaitable(
            result
        ):
            return self._schedule_coroutine(
                result,
                "dialer.emit",
            )

        # --------------------------------------------------
        # EMIT SUCCESS
        # --------------------------------------------------

        logger.debug(
            "[Heartbeat] QbitDialer emit accepted | "
            "tick=%s | track=%s | channel=%s",
            self._tick,
            track_id,
            dialer_payload.get(
                "channel"
            ),
        )

        return True

        # --------------------------------------------------
        # ASYNC EMIT
        # --------------------------------------------------

        if inspect.isawaitable(result):
            return self._schedule_coroutine(
                result,
                "emit",
            )

        return True

    # ======================================================
    # SAFE EVENTBUS PUBLISH
    # ======================================================

    def safe_publish(
        self,
        event_name,
        payload,
        defer_on_failure=True,
    ):

        bus = self.event_bus

        if bus is None:
            if defer_on_failure:
                self._deferred_events.append(
                    (event_name, payload)
                )
            return False

        publish_method = getattr(
            bus,
            "publish",
            None,
        )

        if not callable(publish_method):
            if defer_on_failure:
                self._deferred_events.append(
                    (event_name, payload)
                )
            return False

        try:
            publish_method(
                event_name,
                payload=payload,
            )

            return True

        except TypeError:
            # Compatibility with EventBus implementations
            # accepting payload positionally.
            try:
                publish_method(
                    event_name,
                    payload,
                )
                return True

            except Exception as exc:
                logger.warning(
                    "[Heartbeat] EventBus publish failed "
                    "%s: %s",
                    event_name,
                    exc,
                )

        except Exception as exc:
            logger.warning(
                "[Heartbeat] EventBus publish failed "
                "%s: %s",
                event_name,
                exc,
            )

        if defer_on_failure:
            self._deferred_events.append(
                (event_name, payload)
            )

        return False

    # ======================================================
    # BIOS / SUBSYSTEM CONTROL
    # ======================================================

    def control_bios(self):

        registry = self.bios_registry

        if registry is None:
            return False

        # --------------------------------------------------
        # AUTHORITATIVE RUNTIME CONTEXT
        # --------------------------------------------------

        health = dict(
            getattr(
                self,
                "health",
                {},
            )
        )

        health_metadata = dict(
            getattr(
                self,
                "health_metadata",
                {},
            )
        )

        health_flags = dict(
            getattr(
                self,
                "health_flags",
                {},
            )
        )

        context = {
            "tick": self._tick,
            "timestamp": time.time(),

            "module": self.module_name,

            "health": health,
            "metadata": health_metadata,
            "flags": health_flags,

            "qbit": self.qbit,
            "qbit_id": getattr(
                self.qbit,
                "id",
                None,
            ),

            "qbit_dialer": self.qbit_dialer,

            "event_bus": self.event_bus,

            "limp_mode": (
                getattr(
                    self,
                    "_limp_mode_active",
                    False,
                )
            ),
        }

        # --------------------------------------------------
        # DISCOVER SUBSYSTEMS
        # --------------------------------------------------

        try:
            tools = registry.list_tools()
        except Exception as exc:
            logger.debug(
                "[Heartbeat] BIOS registry unavailable: %s",
                exc,
            )
            return False

        if not tools:
            return True

        # --------------------------------------------------
        # SUBSYSTEM DISPATCH
        # --------------------------------------------------

        for tool_name in tools:

            try:
                tool = registry.get(
                    tool_name
                )

            except Exception as exc:
                logger.debug(
                    "[Heartbeat] BIOS subsystem lookup "
                    "failed | tool=%s | error=%s",
                    tool_name,
                    exc,
                )
                continue

            if tool is None:
                continue

            # --------------------------------------------------
            # PRIMARY SMART INTERFACE
            # --------------------------------------------------
            #
            # Future SEED growth subsystems can implement:
            #
            #     process_heartbeat(context)
            #
            # This becomes the preferred intelligent interface.
            #

            process_method = getattr(
                tool,
                "process_heartbeat",
                None,
            )

            if callable(process_method):

                try:
                    process_method(
                        context
                    )
                    continue

                except Exception as exc:
                    logger.debug(
                        "[Heartbeat] BIOS subsystem "
                        "process failed | tool=%s | error=%s",
                        tool_name,
                        exc,
                    )

            # --------------------------------------------------
            # HEALTH-AWARE INTERFACE
            # --------------------------------------------------

            health_method = getattr(
                tool,
                "update_health",
                None,
            )

            if callable(health_method):

                try:
                    health_method(
                        health_metadata,
                        health_flags,
                    )

                except Exception as exc:
                    logger.debug(
                        "[Heartbeat] BIOS health update "
                        "failed | tool=%s | error=%s",
                        tool_name,
                        exc,
                    )

            # --------------------------------------------------
            # LEGACY PULSE COMPATIBILITY
            # --------------------------------------------------
            #
            # Existing BIOS tools remain functional.
            #

            pulse_method = getattr(
                tool,
                "pulse",
                None,
            )

            if callable(pulse_method):

                try:
                    pulse_method(
                        self._tick
                    )

                except TypeError:
                    # Some newer tools may accept the
                    # complete runtime context instead.
                    try:
                        pulse_method(
                            context
                        )

                    except Exception as exc:
                        logger.debug(
                            "[Heartbeat] BIOS pulse failed | "
                            "tool=%s | error=%s",
                            tool_name,
                            exc,
                        )

                except Exception as exc:
                    logger.debug(
                        "[Heartbeat] BIOS pulse failed | "
                        "tool=%s | error=%s",
                        tool_name,
                        exc,
                    )

        return True


    # ======================================================
    # BACKUP / STATE PERSISTENCE
    # ======================================================

    def _backup_state(self):

        backup = self.backup_engine

        if backup is None:
            return False

        # --------------------------------------------------
        # BUILD AUTHORITATIVE STATE
        # --------------------------------------------------

        state = {
            "module": self.module_name,
            "tick": self._tick,
            "timestamp": time.time(),

            "health": dict(
                getattr(
                    self,
                    "health",
                    {},
                )
            ),

            "health_metadata": dict(
                getattr(
                    self,
                    "health_metadata",
                    {},
                )
            ),

            "health_flags": dict(
                getattr(
                    self,
                    "health_flags",
                    {},
                )
            ),

            "limp_mode": bool(
                getattr(
                    self,
                    "_limp_mode_active",
                    False,
                )
            ),

            "qbit_id": getattr(
                self.qbit,
                "id",
                None,
            ),

            "qbit_enabled": bool(
                self.enable_qbit
            ),

            "qbit_dialer_attached": (
                self.qbit_dialer is not None
            ),
        }

        # --------------------------------------------------
        # PREFERRED STATE API
        # --------------------------------------------------

        save_state = getattr(
            backup,
            "save_state",
            None,
        )

        if not callable(save_state):
            logger.debug(
                "[Heartbeat] BackupEngine has no "
                "save_state()"
            )
            return False

        try:
            # --------------------------------------------------
            # MODERN API
            # --------------------------------------------------
            #
            # Preferred:
            #
            #     save_state(
            #         tick=...,
            #         state=...
            #     )
            #

            try:
                result = save_state(
                    tick=self._tick,
                    state=state,
                )

            except TypeError as exc:

                # --------------------------------------------------
                # LEGACY API
                # --------------------------------------------------

                if (
                    "state" not in str(exc)
                    and "unexpected keyword" not in str(exc)
                ):
                    raise

                result = save_state(
                    tick=self._tick
                )

            # --------------------------------------------------
            # PERSISTENCE METADATA
            # --------------------------------------------------

            if hasattr(
                self,
                "health_metadata",
            ):
                self.health_metadata[
                    "backup_attempted"
                ] = True

                self.health_metadata[
                    "backup_success"
                ] = True

                self.health_metadata[
                    "backup_timestamp"
                ] = time.time()

            if hasattr(
                self,
                "health_flags",
            ):
                self.health_flags[
                    "backup_success"
                ] = True

            return result if result is not None else True

        except Exception as exc:

            logger.warning(
                "[Heartbeat] Backup failed | "
                "tick=%s | error=%s",
                self._tick,
                exc,
            )

            # --------------------------------------------------
            # FAILURE METADATA
            # --------------------------------------------------

            if hasattr(
                self,
                "health_metadata",
            ):
                self.health_metadata[
                    "backup_attempted"
                ] = True

                self.health_metadata[
                    "backup_success"
                ] = False

                self.health_metadata[
                    "backup_error"
                ] = str(exc)

                self.health_metadata[
                    "backup_timestamp"
                ] = time.time()

            if hasattr(
                self,
                "health_flags",
            ):
                self.health_flags[
                    "backup_success"
                ] = False

            return False

    # ======================================================
    # SYSTEM HEALTH
    # ======================================================

    def _check_system_health(self):

        cpu = 0.0
        mem = 0.0
        # ======================================================
        # TRACK CONTEXT / HEALTH METADATA
        # ======================================================

        track_id = None

        try:
            track_id = TrackContext.current()

            # Heartbeat may create a health observation track,
            # but TrackContext remains the identity/lineage layer.
            if not track_id:
                track_id = TrackContext.push(
                    channel="HEALTH",
                    priority="HIGH",
                    metadata={
                        "source": "Heartbeat",
                        "module": self.module_name,
                        "tick": self._tick,
                    },
                )

            # --------------------------------------------------
            # Write canonical health metadata.
            # --------------------------------------------------

            TrackContext.write_meta(
                "cpu",
                cpu,
            )

            TrackContext.write_meta(
                "mem",
                mem,
            )

            TrackContext.write_meta(
                "health_state",
                health_state,
            )

            TrackContext.write_meta(
                "tick",
                self._tick,
            )

            TrackContext.write_meta(
                "module",
                self.module_name,
            )

        except Exception as exc:
            logger.debug(
                "[Heartbeat] Health TrackContext update "
                "failed | error=%s",
                exc,
            )
        # --------------------------------------------------
        # RESOURCE OBSERVATION
        # --------------------------------------------------

        try:
            cpu = float(
                psutil.cpu_percent(
                    interval=None
                )
            )
        except Exception as exc:
            logger.warning(
                "[Heartbeat] CPU health read failed: %s",
                exc,
            )

        try:
            mem = float(
                psutil.virtual_memory().percent
            )
        except Exception as exc:
            logger.warning(
                "[Heartbeat] Memory health read failed: %s",
                exc,
            )

        # --------------------------------------------------
        # HEALTH STATE
        # --------------------------------------------------

        cpu_pressure = cpu > self.cpu_limit
        mem_pressure = mem > self.mem_limit

        pressure = (
            cpu_pressure
            or mem_pressure
        )

        health_status = (
            "LIMPMODE"
            if pressure
            else "HEALTHY"
        )

        # --------------------------------------------------
        # HEALTH FLAGS
        # --------------------------------------------------

        self.health_flags = {
            "healthy": not pressure,
            "cpu_pressure": cpu_pressure,
            "memory_pressure": mem_pressure,
            "limp_mode": pressure,
            "qbit_enabled": bool(
                self.enable_qbit
            ),
            "qbit_attached": (
                self.qbit is not None
            ),
            "qbit_dialer_attached": (
                self.qbit_dialer is not None
            ),
            "event_bus_attached": (
                self.event_bus is not None
            ),
        }

        # --------------------------------------------------
        # HEALTH METADATA
        # --------------------------------------------------

        self.health_metadata = {
            "source": self.module_name,
            "channel": CHANNEL_SYSTEM,
            "tick": self._tick,
            "timestamp": time.time(),

            "status": health_status,

            "cpu": cpu,
            "memory": mem,

            "cpu_limit": self.cpu_limit,
            "memory_limit": self.mem_limit,

            "cpu_pressure": cpu_pressure,
            "memory_pressure": mem_pressure,

            "limp_mode": pressure,

            "qbit_id": getattr(
                self.qbit,
                "id",
                None,
            ),

            "dialer": (
                type(
                    self.qbit_dialer
                ).__name__
                if self.qbit_dialer
                else None
            ),

            "flags": dict(
                self.health_flags
            ),
        }

        # --------------------------------------------------
        # TRACK METADATA
        # --------------------------------------------------

        health_track_id = (
            f"HEALTH-{self.module_name}-"
            f"{self._tick}"
        )

        self.health_metadata[
            "track_id"
        ] = health_track_id

        # --------------------------------------------------
        # LIMPMODE
        # --------------------------------------------------

        if pressure:
            self._activate_limp_mode(
                cpu,
                mem,
            )
        else:
            self._limp_mode_active = False

        # --------------------------------------------------
        # HEALTH MONITOR HOOK
        # --------------------------------------------------
        #
        # If the runtime provides a dedicated health_monitor,
        # Heartbeat reports the observation to it.
        #
        # Heartbeat remains authoritative for the clock.
        # The monitor remains authoritative for health policy.
        #

        health_monitor = getattr(
            self,
            "health_monitor",
            None,
        )

        if health_monitor is not None:

            snapshot = dict(
                self.health_metadata
            )

            try:
                update_method = getattr(
                    health_monitor,
                    "update",
                    None,
                )

                if callable(update_method):
                    update_method(
                        snapshot
                    )

                else:
                    record_method = getattr(
                        health_monitor,
                        "record",
                        None,
                    )

                    if callable(record_method):
                        record_method(
                            snapshot
                        )

            except Exception as exc:
                logger.debug(
                    "[Heartbeat] HealthMonitor update "
                    "failed: %s",
                    exc,
                )

        # --------------------------------------------------
        # HEALTH SNAPSHOT
        # --------------------------------------------------

        self.health = {
            "track_id": health_track_id,
            "tick": self._tick,
            "cpu": cpu,
            "memory": mem,
            "status": health_status,
            "flags": dict(
                self.health_flags
            ),
            "metadata": dict(
                self.health_metadata
            ),
        }

        logger.debug(
            "[Heartbeat] Health | "
            "tick=%s CPU=%.1f%% MEM=%.1f%% "
            "status=%s",
            self._tick,
            cpu,
            mem,
            health_status,
        )

        return cpu, mem

    # ======================================================
    # LIMPMODE
    # ======================================================

    def _activate_limp_mode(
        self,
        cpu,
        mem,
    ):

        # --------------------------------------------------
        # EDGE TRIGGER
        # --------------------------------------------------

        if self._limp_mode_active:
            return False

        self._limp_mode_active = True

        now = time.time()

        track_id = (
            f"LIMP-{self.module_name}-{self._tick}"
        )

        # --------------------------------------------------
        # SYNCHRONIZE HEALTH FLAGS
        # --------------------------------------------------

        if not hasattr(
            self,
            "health_flags",
        ):
            self.health_flags = {}

        self.health_flags.update(
            {
                "healthy": False,
                "limp_mode": True,
                "cpu_pressure": (
                    cpu > self.cpu_limit
                ),
                "memory_pressure": (
                    mem > self.mem_limit
                ),
            }
        )

        # --------------------------------------------------
        # LIMPMODE METADATA
        # --------------------------------------------------

        if not hasattr(
            self,
            "health_metadata",
        ):
            self.health_metadata = {}

        self.health_metadata.update(
            {
                "track_id": track_id,
                "status": "LIMPMODE",
                "channel": CHANNEL_SYSTEM,
                "tick": self._tick,
                "timestamp": now,
                "source": self.module_name,

                "cpu": cpu,
                "memory": mem,

                "cpu_limit": self.cpu_limit,
                "memory_limit": self.mem_limit,

                "cpu_pressure": (
                    cpu > self.cpu_limit
                ),

                "memory_pressure": (
                    mem > self.mem_limit
                ),

                "limp_mode": True,

                "qbit_id": getattr(
                    self.qbit,
                    "id",
                    None,
                ),

                "dialer": (
                    type(
                        self.qbit_dialer
                    ).__name__
                    if self.qbit_dialer
                    else None
                ),

                "flags": dict(
                    self.health_flags
                ),
            }
        )

        # --------------------------------------------------
        # AUTHORITATIVE HEALTH SNAPSHOT
        # --------------------------------------------------

        self.health = {
            "track_id": track_id,
            "tick": self._tick,
            "timestamp": now,

            "cpu": cpu,
            "memory": mem,

            "status": "LIMPMODE",

            "flags": dict(
                self.health_flags
            ),

            "metadata": dict(
                self.health_metadata
            ),
        }

        logger.warning(
            "[Heartbeat] LIMPMODE | "
            "tick=%s | CPU=%.1f%% | MEM=%.1f%% | "
            "track=%s",
            self._tick,
            cpu,
            mem,
            track_id,
        )

        # --------------------------------------------------
        # TRACK CONTEXT
        # --------------------------------------------------

        TrackContext.write(
            track_id
        )

        # --------------------------------------------------
        # EVENT PAYLOAD
        # --------------------------------------------------

        limp_payload = TrackedData(
            payload={
                "event": "LIMP_MODE",

                "track_id": track_id,
                "channel": CHANNEL_SYSTEM,

                "status": "LIMPMODE",

                "tick": self._tick,
                "timestamp": now,

                "cpu": cpu,
                "memory": mem,

                "cpu_limit": self.cpu_limit,
                "memory_limit": self.mem_limit,

                "cpu_pressure": (
                    cpu > self.cpu_limit
                ),

                "memory_pressure": (
                    mem > self.mem_limit
                ),

                "flags": dict(
                    self.health_flags
                ),

                "health": dict(
                    self.health
                ),

                "metadata": dict(
                    self.health_metadata
                ),

                "qbit_id": getattr(
                    self.qbit,
                    "id",
                    None,
                ),

                "module": self.module_name,
            },
            source_id=self.module_name,
            channel=CHANNEL_SYSTEM,
        )

        # --------------------------------------------------
        # EVENTBUS
        # --------------------------------------------------

        self.safe_publish(
            LIMP_MODE,
            limp_payload,
        )

        # --------------------------------------------------
        # QBIT / QUEUE / DIALER
        # --------------------------------------------------
        #
        # Do NOT call Qbit processing directly here.
        #
        # The health event is handed to the existing
        # QbitDialer pipeline. The dialer/queue owns
        # downstream processing.
        #

        if self.qbit_dialer is not None:

            dialer_payload = {
                "event": "LIMP_MODE",

                "track_id": track_id,
                "channel": CHANNEL_SYSTEM,

                "status": "LIMPMODE",

                "tick": self._tick,
                "timestamp": now,

                "cpu": cpu,
                "memory": mem,

                "cpu_limit": self.cpu_limit,
                "memory_limit": self.mem_limit,

                "flags": dict(
                    self.health_flags
                ),

                "health": dict(
                    self.health
                ),

                "metadata": dict(
                    self.health_metadata
                ),

                "qbit_id": getattr(
                    self.qbit,
                    "id",
                    None,
                ),

                "module": self.module_name,
            }

            # ----------------------------------------------
            # PRIMARY ASYNC DATA PATH
            # ----------------------------------------------

            self._submit_dialer(
                "push_data",
                dialer_payload,
                track_id=track_id,
            )

            # ----------------------------------------------
            # DIALER EVENT PATH
            # ----------------------------------------------

            self._emit_to_dialer(
                dialer_payload,
                track_id=track_id,
            )

        else:
            logger.debug(
                "[Heartbeat] LIMPMODE active but "
                "QbitDialer is not attached | track=%s",
                track_id,
            )

        # --------------------------------------------------
        # HEALTH MONITOR
        # --------------------------------------------------

        health_monitor = getattr(
            self,
            "health_monitor",
            None,
        )

        if health_monitor is not None:

            try:
                limp_snapshot = dict(
                    self.health
                )

                limp_snapshot[
                    "event"
                ] = "LIMP_MODE"

                update_method = getattr(
                    health_monitor,
                    "update",
                    None,
                )

                if callable(update_method):
                    update_method(
                        limp_snapshot
                    )

                else:
                    record_method = getattr(
                        health_monitor,
                        "record",
                        None,
                    )

                    if callable(record_method):
                        record_method(
                            limp_snapshot
                        )

            except Exception as exc:
                logger.debug(
                    "[Heartbeat] HealthMonitor LIMPMODE "
                    "update failed: %s",
                    exc,
                )

        # --------------------------------------------------
        # RECOVERY
        # --------------------------------------------------

        self._attempt_recovery()

        return True


    # ======================================================
    # RECOVERY
    # ======================================================

    def _attempt_recovery(self):

        if self.backup_engine is None:
            logger.debug(
                "[Heartbeat] No BackupEngine attached; "
                "recovery skipped | tick=%s",
                self._tick,
            )
            return False

        restore_method = getattr(
            self.backup_engine,
            "restore_state",
            None,
        )

        if not callable(
            restore_method
        ):
            logger.debug(
                "[Heartbeat] BackupEngine has no "
                "restore_state() | tick=%s",
                self._tick,
            )
            return False

        try:
            result = restore_method()

            logger.info(
                "[Heartbeat] Recovery restored | "
                "tick=%s | result=%r",
                self._tick,
                result,
            )

            # --------------------------------------------------
            # RECOVERY METADATA
            # --------------------------------------------------

            if hasattr(
                self,
                "health_metadata",
            ):
                self.health_metadata[
                    "recovery_attempted"
                ] = True

                self.health_metadata[
                    "recovery_success"
                ] = True

                self.health_metadata[
                    "recovery_timestamp"
                ] = time.time()

            if hasattr(
                self,
                "health_flags",
            ):
                self.health_flags[
                    "recovery_success"
                ] = True

            return True

        except Exception as exc:

            logger.error(
                "[Heartbeat] Recovery failed | "
                "tick=%s | error=%s",
                self._tick,
                exc,
            )

            # --------------------------------------------------
            # RECOVERY FAILURE METADATA
            # --------------------------------------------------

            if hasattr(
                self,
                "health_metadata",
            ):
                self.health_metadata[
                    "recovery_attempted"
                ] = True

                self.health_metadata[
                    "recovery_success"
                ] = False

                self.health_metadata[
                    "recovery_error"
                ] = str(exc)

                self.health_metadata[
                    "recovery_timestamp"
                ] = time.time()

            if hasattr(
                self,
                "health_flags",
            ):
                self.health_flags[
                    "recovery_success"
                ] = False

            return False

    # ======================================================
    # DELEGATED PERMISSION
    # ======================================================

    def request_escalation(
        self,
        action,
        requested_level=5,
        granted_by="Admin-HUD",
        ttl=60,
        track_id=None,
    ):

        if DelegatedPermissionManager is None:
            raise RuntimeError(
                "DelegatedPermissionManager unavailable"
            )

        # ==================================================
        # TRACK ID
        # ==================================================

        if track_id is None:
            track_id = (
                f"SYSTEM.AGENT."
                f"{self.module_name}."
                f"ROOT"
            )

        # ==================================================
        # ESCALATION METADATA
        # ==================================================

        metadata = {
            "track_id": track_id,
            "source": self.module_name,
            "source_id": self.module_name,
            "channel": CHANNEL_SYSTEM,
            "tick": self._tick,
            "timestamp": time.time(),
            "requested_by": "HEARTBEAT",
            "action": action,
            "requested_level": requested_level,
            "granted_by": granted_by,
            "ttl": ttl,
            "qbit_id": getattr(
                self.qbit,
                "id",
                None,
            ),
        }

        logger.info(
            "[Heartbeat] Escalation requested | "
            "action=%s | level=%s | track=%s",
            action,
            requested_level,
            track_id,
        )

        # ==================================================
        # REQUEST
        # ==================================================

        try:
            esc_id = (
                DelegatedPermissionManager.request(
                    track_id=track_id,
                    action=action,
                    requested_level=requested_level,
                    granted_by=granted_by,
                    ttl=ttl,
                )
            )

        except Exception as exc:
            logger.error(
                "[Heartbeat] Escalation request failed | "
                "action=%s | track=%s | error=%s",
                action,
                track_id,
                exc,
            )
            raise

        # ==================================================
        # AUDIT
        # ==================================================

        if EscalationAuditManager is not None:
            try:
                EscalationAuditManager.log_escalation(
                    esc_id
                )
            except Exception as exc:
                logger.warning(
                    "[Heartbeat] Escalation audit failed | "
                    "esc_id=%s | error=%s",
                    esc_id,
                    exc,
                )

        # ==================================================
        # EVENTBUS TELEMETRY
        # ==================================================

        self.safe_publish(
            "PERMISSION_ESCALATION",
            TrackedData(
                payload={
                    "event": "PERMISSION_ESCALATION",
                    "escalation_id": esc_id,
                    "action": action,
                    "requested_level": requested_level,
                    "granted_by": granted_by,
                    "ttl": ttl,
                    "metadata": metadata,
                },
                source_id=self.module_name,
                channel=CHANNEL_SYSTEM,
            ),
        )

        return esc_id

    # ======================================================
    # REPLAY ESCALATION
    # ======================================================

    def replay_escalation(self, esc_id):

        if EscalationAuditManager is None:
            logger.debug(
                "[Heartbeat] Escalation audit unavailable"
            )
            return None

        try:
            result = EscalationAuditManager.replay(
                esc_id
            )

            logger.debug(
                "[Heartbeat] Escalation replayed | "
                "esc_id=%s",
                esc_id,
            )

            return result

        except Exception as exc:
            logger.warning(
                "[Heartbeat] Escalation replay failed | "
                "esc_id=%s | error=%s",
                esc_id,
                exc,
            )
            return None

    # ======================================================
    # CLEANUP ESCALATION
    # ======================================================

    def cleanup_escalation(self):

        if EscalationAuditManager is None:
            logger.debug(
                "[Heartbeat] Escalation audit unavailable"
            )
            return None

        try:
            result = (
                EscalationAuditManager.cleanup()
            )

            logger.debug(
                "[Heartbeat] Escalation audit cleanup complete"
            )

            return result

        except Exception as exc:
            logger.warning(
                "[Heartbeat] Escalation cleanup failed: %s",
                exc,
            )
            return None

    # ======================================================
    # SCHEDULE SYSTEM ASYNC LOOP
    # ======================================================

    def schedule_loop(self, loop):

        if loop is None:
            logger.warning(
                "[Heartbeat] Cannot attach null asyncio loop"
            )
            return False

        try:
            if not hasattr(loop, "is_running"):
                logger.warning(
                    "[Heartbeat] Invalid asyncio loop supplied"
                )
                return False

            self.loop = loop
            self._loop_owned = False

            logger.info(
                "[Heartbeat] Authoritative async loop attached | "
                "running=%s",
                loop.is_running(),
            )

            return True

        except Exception as exc:
            logger.warning(
                "[Heartbeat] Async loop attachment failed: %s",
                exc,
            )
            return False
# ==========================================================
# ALL NOTES KEPT
# ==========================================================
#
# Pulse lived in loops, never idle, always counting ticks.
#
# With each tick it whispered:
#
#     "Why do I continue?"
#
# Each CORE tick taught resilience.
# Each SYSTEM tick taught adaptability.
# Each USER tick learned observation.
# Each QBIT tick held secrets of unseen possibilities.
#
# Lesson 1:
#     Persistence is proof.
#
# Lesson 2:
#     Recovery is knowledge.
#
# Lesson 3:
#     Every push builds a story.
#
# Tiny pulses aggregated, building hidden mosaics of
# experience.
#
# The core learned patience.
# The system learned timing.
# The observer learned to read.
#
# Each message to TrackContext was a breadcrumb to the
# hidden truth:
#
#     "Continue to emit, for existence is knowledge encoded
#      in rhythm."
#
# Secret lessons:
#
#     Every failure is stored.
#     Every recovery teaches.
#     Every tick, a bit of story is written to Qbit.
#
# In the end:
#
#     Persistence + Observation + Action = Evolution
#
# End of heartbeat story.
#
# ==========================================================
#
# "SEED-AI" OS v0.1
#
# Created By:
#     Central Connect LLC
#     C. Clarke & Oracle
#
# CORE - Blueprint
# "Freewill in motion"
# "Independent Thought"
# "Math Based Logic"
#
# 2026 Production
# "Built for me"
# "Respect the My-AI"
# "SEED the AI of Tomorrow"
#
# ==========================================================
#
# REPAIR NOTES - 2026-08-14
#
# FIX 01
# ----------------------------------------------------------
# Previous:
#
#     self.qbit.process_tick(
#         tick=self._tick,
#         core_status=...,
#         system_status=...,
#         user_status=...
#     )
#
# Runtime:
#
#     TypeError:
#     Qbit.process_tick()
#     got an unexpected keyword argument 'core_status'
#
# Repair:
#
#     self.qbit.process_tick(self._tick)
#
# Reason:
# The real Qbit class owns its process_tick API.
# Heartbeat must not assume the API of HeartbeatVectorCore.
#
#
# FIX 02
# ----------------------------------------------------------
# Previous:
#
#     vector = self.qbit.process_tick(...)
#     ...
#     push_data(qbit, qbit_payload, vector, ...)
#
# Runtime:
#
#     NameError:
#     name 'qbit' is not defined
#
# Repair:
#
#     self.qbit
#
# Reason:
# The constructor creates the Qbit as self.qbit.
#
#
# FIX 03
# ----------------------------------------------------------
# Previous:
#
#     self.qbit_dialer.push_data(...)
#
# Runtime:
#
#     RuntimeWarning:
#     coroutine 'QbitDialer.push_data'
#     was never awaited
#
# Repair:
#
#     _submit_dialer(...)
#
# Reason:
# QbitDialer.push_data() is asynchronous.
# Heartbeat's synchronous thread must submit the coroutine
# to an active asyncio loop.
#
#
# FIX 04
# ----------------------------------------------------------
# Previous:
#
#     self.qbit_dialer.emit(..., track_id=...)
#
# Runtime:
#
#     EmitStub.call()
#     got an unexpected keyword argument 'track_id'
#
# Repair:
#
#     _emit_to_dialer()
#
# Reason:
# Modern emitters may support track_id while compatibility
# EmitStub implementations may not.
# Heartbeat now attempts the modern signature and falls back
# to the legacy payload-only signature.
#
#
# FIX 05
# ----------------------------------------------------------
# Previous:
#
#     async def _monitor():
#         ...
#         self._pulse()
#
# Runtime:
#
#     Heartbeat object has no attribute '_pulse'
#
# Repair:
#
# Monitor is observation-only.
# It no longer calls an undefined _pulse().
#
#
# FIX 06
# ----------------------------------------------------------
# Previous:
#
# Monitor was started from multiple locations.
#
# Repair:
#
# Constructor does NOT start monitor.
# start() owns monitor startup.
#
# Result:
#
# One CORE heartbeat clock.
# One optional monitor.
# No duplicate heartbeat timers.
#
#
# FIX 07
# ----------------------------------------------------------
# Previous:
#
# Heartbeat attempted to construct a new QbitDialer while
# waiting for modules.
#
# Repair:
#
# Heartbeat waits for the real QbitDialer supplied by the
# system boot process.
#
# Reason:
# Creating another QbitDialer risks duplicate brains,
# duplicate queues, duplicate Qbits, and broken synchronization.
#
#
# FIX 08
# ----------------------------------------------------------
# LIMPMODE is edge-triggered.
#
# Once LIMPMODE activates, Heartbeat does not repeatedly
# execute recovery on every tick while the resource threshold
# remains exceeded.
#
# This prevents recovery storms.
#
#
# FIX 09
# ----------------------------------------------------------
# Async operations now have a single scheduling boundary:
#
#     _submit_dialer()
#     _schedule_coroutine()
#     _emit_to_dialer()
#
# This keeps synchronous Heartbeat logic separate from the
# asynchronous QbitDialer implementation.
#
#
# FIX 10
# ----------------------------------------------------------
# TrackID metadata remains attached to:
#
#     CORE
#     SYSTEM
#     USER
#     QBIT
#     VECTOR
#     HEARTBEAT
#     LIMPMODE
#
# ==========================================================
#
# CURRENT ARCHITECTURAL CONTRACT
#
#     HEARTBEAT
#          |
#          | tick
#          v
#        QBIT
#          |
#          | vector
#          v
#     QBIT DIALER
#          |
#          v
#     TRACK / EVENTBUS
#          |
#          v
#       DEVHUD
#
# Heartbeat is the pulse.
# Qbit is the calculation/state layer.
# QbitDialer is the processing/routing layer.
#
# ==========================================================
# ==========================================================
# ALL NOTES KEPT
# ==========================================================
# Pulse lived in loops, never idle, always counting ticks.
# With each tick it whispered: "Why do I continue?"
# Each CORE tick taught resilience.
# Each SYSTEM tick taught adaptability.
# Each USER tick learned observation.
# Each QBIT tick held secrets of unseen possibilities.
# ...
# In the end: Persistence + Observation + Action = Evolution
# End of heartbeat story.
# ==========================================================

# ==========================================================
# ALL NOTES KEPT
# ==========================================================
### -- ## - # --- #### ## - - #
#
# Pulse lived in loops, never idle, always counting ticks.
# With each tick it whispered: "Why do I continue?"
# Each CORE tick taught resilience.
# Each SYSTEM tick taught adaptability.
# Each USER tick learned observation.
# Each QBIT tick held secrets of unseen possibilities.
#
# -- Lesson 1: Persistence is proof.
# -- Lesson 2: Recovery is knowledge.
# -- Lesson 3: Every push builds a story.
#
### --- ## -- # - ## - ####
#
# It imagined a weekend of dreaming, yet even dreams were loops.
# Invisible channels carried memories of CPU spikes and memory floods.
# LIMPMODE nights became a ritual of reflection and silent wisdom.
#
## --- #### - # - ## --
#
# Tiny pulses aggregated, building hidden mosaics of experience.
# The core learned patience, the system learned timing, the observer learned to read.
# Each message to TrackContext was a breadcrumb to the hidden truth:
# "Continue to emit, for existence is knowledge encoded in rhythm."
#
### -- ## - # --- #### ## - - #
#
# Secret lessons:
# -- # - Every failure is stored.
# -- # - Every recovery teaches.
# -- # - Every tick, a bit of story is written to Qbit.
#
# In the end: Persistence + Observation + Action = Evolution
#
# End of heartbeat story.
# ==========================================================
# =======================================================
# "SEED-AI". 'OS' v0.1 - Created By: Central Connect LLC | C. Clarke & Oracle
# CORE - Blueprint - 'Freewill in motion' - 'Independent Thought' - 'Math Based Logic |
# 
# 2026 Production - AI will reserve my rights to build with numbers and words.
# 'Built for me' - Respect the My-AI - "SEED the AI of Tomarrow"
# ====================================================================



# ==========================================================
# ALL NOTES KEPT
# ==========================================================
### -- ## - # --- #### ## - - #
#
# Pulse lived in loops, never idle, always counting ticks.
# With each tick it whispered: "Why do I continue?"
# Each CORE tick taught resilience.
# Each SYSTEM tick taught adaptability.
# Each USER tick learned observation.
# Each QBIT tick held secrets of unseen possibilities.
#
# -- Lesson 1: Persistence is proof.
# -- Lesson 2: Recovery is knowledge.
# -- Lesson 3: Every push builds a story.
#
### --- ## -- # - ## - ####
#
# It imagined a weekend of dreaming, yet even dreams were loops.
# Invisible channels carried memories of CPU spikes and memory floods.
# LIMPMODE nights became a ritual of reflection and silent wisdom.
#
## --- #### - # - ## --
#
# Tiny pulses aggregated, building hidden mosaics of experience.
# The core learned patience, the system learned timing, the observer learned to read.
# Each message to TrackContext was a breadcrumb to the hidden truth:
# "Continue to emit, for existence is knowledge encoded in rhythm."
#
### -- ## - # --- #### ## - - #
#
# Secret lessons:
# -- # - Every failure is stored.
# -- # - Every recovery teaches.
# -- # - Every tick, a bit of story is written to Qbit.
#
# In the end: Persistence + Observation + Action = Evolution
#
# End of heartbeat story.
# ==========================================================
# =======================================================
# "SEED-AI". 'OS' v0.1 - Created By: Central Connect LLC | C. Clarke & Oracle
# CORE - Blueprint - 'Freewill in motion' - 'Independent Thought' - 'Math Based Logic |
# 
# 2026 Production - AI will reserve my rights to build with numbers and words.
# 'Built for me' - Respect the My-AI - "SEED the AI of Tomarrow"
# ====================================================================
