# ==========================================================
# FILE: fat_hud_adapter.py
# PATH: SEED_ROOT/seed/ui/fat_hud_adapter.py
# VERSION: 4.0.0
# BUILD:
#   HALO / CORE-CONTROL-OBSERVABILITY /
#   QBIT-ID / TRACK-ID / COMMAND-LIFECYCLE /
#   AUDIO / DOT-MATRIX / SYSTEM-MENU /
#   SINGLE-FATHUD
#
# ROLE:
#   SEED AI OS developer / observer interface.
#
# AUTHORITY CONTRACT:
#
#   Heartbeat
#       = signal / telemetry source
#
#   Qbit
#       = canonical data / thought identity
#
#   QbitQueueLoop
#       = authoritative Qbit transport
#
#   QbitDialer
#       = SINGLE command authority
#
#   FATHUD / HALO
#       = observer + developer command ingress
#
#   seed.ui.hud
#       = reserved SEED-controlled display surface
#
# FATHUD DOES NOT:
#   - create another Qbit
#   - create another QbitQueueLoop
#   - create another QbitDialer
#   - execute SEED commands directly
#   - become command authority
#   - create another SEED runtime
#
# ==========================================================

from __future__ import annotations

import asyncio
import base64
import inspect
import json
import logging
import threading
import time
import uuid
import webbrowser
from pathlib import Path

from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Optional


logger = logging.getLogger("FATHUD")

HUD_HTML_PATH = Path(__file__).resolve().parent / "hudwebui.html"


# ==========================================================
# HELPERS
# ==========================================================

def _utc_ts() -> float:
    return time.time()


def _safe_type(obj):
    if obj is None:
        return None

    try:
        return type(obj).__name__
    except Exception:
        return "UNKNOWN"


def _safe_string(value, default=None):
    if value is None:
        return default

    try:
        return str(value)
    except Exception:
        return default


def _extract_identity(obj, *names):
    if obj is None:
        return None

    if isinstance(obj, dict):
        for name in names:
            value = obj.get(name)

            if value not in (None, ""):
                return value

        return None

    for name in names:
        try:
            value = getattr(
                obj,
                name,
                None,
            )

            if value not in (
                None,
                "",
            ):
                return value

        except Exception:
            continue

    return None


def _json_safe(value):
    """
    FATHUD must never crash because a live SEED object cannot be
    serialized.

    Live runtime references are summarized, not deep-copied.
    """

    if value is None:
        return None

    if isinstance(
        value,
        (
            str,
            int,
            float,
            bool,
        ),
    ):
        return value

    if isinstance(value, complex):
        return {
            "real": value.real,
            "imag": value.imag,
        }

    if isinstance(value, dict):
        output = {}

        for key, item in value.items():

            try:
                safe_key = str(key)
            except Exception:
                safe_key = "unknown"

            output[safe_key] = _json_safe(
                item
            )

        return output

    if isinstance(
        value,
        (
            list,
            tuple,
            set,
            deque,
        ),
    ):
        return [
            _json_safe(item)
            for item in value
        ]

    try:
        return str(value)

    except Exception:
        return {
            "type": _safe_type(value),
            "id": id(value),
        }


# ==========================================================
# FATHUD ADAPTER
# ==========================================================

class FATHUDAdapter:

    # ======================================================
    # SINGLE HALO INSTANCE
    # ======================================================

    _instance = None
    _instance_lock = threading.RLock()

    def __new__(
        cls,
        *args,
        **kwargs,
    ):

        with cls._instance_lock:

            if cls._instance is None:

                cls._instance = super().__new__(
                    cls
                )

                cls._instance._constructed = False

        return cls._instance


    # ======================================================
    # CONSTRUCTOR
    # ======================================================

    def __init__(
        self,
        event_bus=None,
        qbit=None,
        qbit_dialer=None,
        command_plane=None,
        seedcore=None,
        queue_loop=None,
        qbit_queue_loop=None,
        track_system=None,
        registry=None,
        registry_runtime=None,
        node_registry=None,
        kernel=None,
        kernel_bus=None,
        neural_network=None,
        neural_bridge=None,
        runtime=None,
        channel_manager=None,
        hud=None,
        host="localhost",
        port=8765,
        http_port=8766,
        auto_start=True,
        **kwargs,
    ):

        # --------------------------------------------------
        # SINGLETON RE-BIND
        #
        # Calling FATHUDAdapter again must NOT create
        # another server. It may only attach newly available
        # runtime dependencies.
        # --------------------------------------------------

        if getattr(
            self,
            "_constructed",
            False,
        ):

            self.attach_seed_systems(
                event_bus=event_bus,
                qbit=qbit,
                qbit_dialer=qbit_dialer,
                command_plane=command_plane,
                seedcore=seedcore,
                queue_loop=(
                    queue_loop
                    or qbit_queue_loop
                ),
                track_system=track_system,
                registry=registry,
                registry_runtime=registry_runtime,
                node_registry=node_registry,
                kernel=kernel,
                kernel_bus=kernel_bus,
                neural_network=neural_network,
                neural_bridge=neural_bridge,
                runtime=runtime,
                channel_manager=channel_manager,
                hud=hud,
                database=kwargs.get("database"),
            )

            return

        # ==================================================
        # BASIC CONFIGURATION
        # ==================================================

        self.logger = logger

        self.host = host
        self.port = int(port)
        self.http_port = int(
            http_port
        )

        self._constructed = True
        self._closed = False

        # ==================================================
        # AUTHORITATIVE RUNTIME REFERENCES
        #
        # References only.
        # No runtime construction.
        # ==================================================

        self.event_bus = None

        self.qbit = None

        self.qbit_dialer = None
        self.dialer = None

        self.command_plane = None

        self.queue_loop = None
        self.qbit_queue_loop = None

        self.track_system = None

        self.registry = None
        self.registry_runtime = None
        self.node_registry = None

        self.seedcore = None
        self.seed_core = None
        self.core = None

        self.kernel = None
        self.kernel_bus = None

        self.neural_network = None
        self.neural_bridge = None

        self.runtime = None
        self.channel_manager = None
        self.database = None

        # --------------------------------------------------
        # RESERVED SEED-CONTROLLED DISPLAY
        #
        # This is NOT FATHUD authority.
        #
        # Future:
        #
        #   seed.ui.hud
        #
        # may expose:
        #
        #   open()
        #   close()
        #   show_request()
        #   display()
        #
        # FATHUD only retains the reference.
        # --------------------------------------------------

        self.hud = None
        self.seed_hud = None

        # ==================================================
        # OBSERVABILITY STATE
        # ==================================================

        self._events = deque(
            maxlen=500
        )

        self._logs = deque(
            maxlen=500
        )

        self._seed_output = deque(
            maxlen=250
        )

        self._command_history = deque(
            maxlen=250
        )

        self._commands = {}

        self._last_event = None
        self._last_payload = None

        # ==================================================
        # AUDIO STATE
        # ==================================================

        self._audio_state = {
            "sequence": 0,
            "mime_type": None,
            "data": None,
            "url": None,
            "amplitude": 0.0,
            "timestamp": None,
            "source": None,
        }

        # ==================================================
        # DOT MATRIX STATE
        # ==================================================

        self._dot_matrix_3d = []
        self._dot_matrix_meta = {
            "timestamp": None,
            "source": None,
            "width": None,
            "height": None,
            "depth": None,
        }

        # ==================================================
        # WEBSOCKET STATE
        # ==================================================

        self._clients = set()

        self._ws_thread = None
        self._ws_loop = None
        self._ws_server = None

        self._ws_started = False
        self._ws_running = False

        # ==================================================
        # HTTP STATE
        # ==================================================

        self._http_thread = None
        self._http_server = None

        self._http_started = False

        # ==================================================
        # PUSH COALESCING
        # ==================================================

        self._push_lock = threading.RLock()

        self._push_pending = False
        self._push_generation = 0

        # ==================================================
        # EVENTBUS SUBSCRIPTION STATE
        # ==================================================

        self._event_bus_attached = False
        self._event_bus_subscription = None

        # ==================================================
        # ATTACH EXISTING SYSTEMS
        # ==================================================

        self.attach_seed_systems(
            event_bus=event_bus,
            qbit=qbit,
            qbit_dialer=qbit_dialer,
            command_plane=command_plane,
            seedcore=seedcore,
            queue_loop=(
                queue_loop
                or qbit_queue_loop
            ),
            track_system=track_system,
            registry=registry,
            registry_runtime=registry_runtime,
            node_registry=node_registry,
            kernel=kernel,
            kernel_bus=kernel_bus,
            neural_network=neural_network,
            neural_bridge=neural_bridge,
            runtime=runtime,
            channel_manager=channel_manager,
            hud=hud,
            database=kwargs.get("database"),
        )

        self.logger.info(
            "[FATHUD] Adapter initialized | "
            "WS=ws://%s:%s | "
            "HTTP=http://%s:%s",
            self.host,
            self.port,
            self.host,
            self.http_port,
        )

        # ==================================================
        # START HALO NETWORK SURFACES
        #
        # This is FATHUD I/O only.
        # It is NOT the SEED runtime.
        # ==================================================

        if auto_start:

            self._start_websocket()
            self._start_http_server()


    # ==========================================================
    # IDENTITY-PRESERVING BIND
    # ==========================================================

    def _bind_authoritative(
        self,
        attribute,
        value,
        label,
    ):

        if value is None:
            return getattr(
                self,
                attribute,
                None,
            )

        current = getattr(
            self,
            attribute,
            None,
        )

        if (
            current is not None
            and
            current is not value
        ):

            self.logger.warning(
                "[FATHUD] %s replacement rejected | "
                "existing=%s | incoming=%s",
                label,
                id(current),
                id(value),
            )

            return current

        setattr(
            self,
            attribute,
            value,
        )

        return value

    # ==========================================================
    # ATTACH SEED SYSTEMS
    #
    # SINGLE AUTHORITATIVE RUNTIME BINDING
    #
    # FATHUD IS OBSERVER-ONLY.
    #
    # This method:
    #     - binds existing SEED runtime authorities
    #     - preserves live object identity
    #     - connects FATHUD to runtime telemetry
    #     - exposes system state to the HUD
    #
    # This method DOES NOT:
    #     - create Qbits
    #     - create QbitQueueLoop
    #     - create EventBus
    #     - create QbitDialer
    #     - create a runtime loop
    #     - create a queue
    #     - execute commands
    #     - become command authority
    #
    # Command flow remains:
    #
    #     FATHUD
    #        |
    #        v
    #     Qbit / command envelope
    #        |
    #        v
    #     QbitQueueLoop
    #        |
    #        v
    #     QbitDialer
    #
    # ==========================================================

    def attach_systems(
        self,
        *,
        event_bus=None,
        qbit=None,
        qbit_dialer=None,
        queue_loop=None,
        qbit_queue_loop=None,
        track_system=None,
        registry=None,
        registry_runtime=None,
        node_registry=None,
        nodes=None,
        kernel_bus=None,
        seed_core=None,
        seedcore=None,
        neural_bridge=None,
        compute_brain=None,
        transformer_brain=None,
        channel_manager=None,
        hud=None,
        hud_adapter=None,
        **kwargs,
    ):

        # ------------------------------------------------------
        # COMPATIBILITY ALIASES
        # ------------------------------------------------------

        if queue_loop is None:
            queue_loop = qbit_queue_loop

        if seed_core is None:
            seed_core = seedcore

        if hud is None:
            hud = hud_adapter

        if node_registry is None:
            node_registry = nodes

        # ------------------------------------------------------
        # HELPER
        #
        # Bind only when an object was actually supplied.
        # Prefer existing attach_* methods so current FATHUD
        # behavior is preserved.
        # ------------------------------------------------------

        def _bind(
            method_names,
            attribute_names,
            value,
        ):
            if value is None:
                return False

            # ----------------------------------------------
            # FIRST: USE EXISTING ATTACH METHOD
            # ----------------------------------------------

            for method_name in method_names:

                method = getattr(
                    self,
                    method_name,
                    None,
                )

                if not callable(method):
                    continue

                try:

                    result = method(
                        value
                    )

                    if inspect.isawaitable(
                        result
                    ):

                        try:
                            loop = asyncio.get_running_loop()

                            loop.create_task(
                                result
                            )

                        except RuntimeError:

                            # Do not create another loop.
                            # The authoritative runtime must
                            # schedule the awaitable.
                            self.logger.warning(
                                "[FATHUD] Async binding deferred | "
                                "method=%s",
                                method_name,
                            )

                    return True

                except TypeError:

                    # Some existing attach methods may use
                    # a different calling convention.
                    continue

                except Exception as exc:

                    self.logger.warning(
                        "[FATHUD] System binding failed | "
                        "method=%s | error=%s",
                        method_name,
                        exc,
                    )

                    return False

            # ----------------------------------------------
            # SECOND: LIVE ATTRIBUTE FALLBACK
            #
            # Only bind the existing object.
            # Never construct a replacement.
            # ----------------------------------------------

            for attribute_name in attribute_names:

                try:

                    setattr(
                        self,
                        attribute_name,
                        value,
                    )

                    return True

                except Exception as exc:

                    self.logger.warning(
                        "[FATHUD] Attribute binding failed | "
                        "attribute=%s | error=%s",
                        attribute_name,
                        exc,
                    )

            return False

        # ------------------------------------------------------
        # AUTHORITATIVE CORE RUNTIME
        # ------------------------------------------------------

        bound = {}

        bound["event_bus"] = _bind(
            (
                "attach_event_bus",
                "bind_event_bus",
            ),
            (
                "event_bus",
                "_event_bus",
            ),
            event_bus,
        )

        bound["qbit"] = _bind(
            (
                "attach_qbit",
                "bind_qbit",
            ),
            (
                "qbit",
                "_qbit",
            ),
            qbit,
        )

        bound["qbit_queue_loop"] = _bind(
            (
                "attach_queue_loop",
                "attach_qbit_queue_loop",
                "bind_queue_loop",
                "bind_qbit_queue_loop",
            ),
            (
                "queue_loop",
                "qbit_queue_loop",
                "_queue_loop",
                "_qbit_queue_loop",
            ),
            queue_loop,
        )

        bound["qbit_dialer"] = _bind(
            (
                "attach_qbit_dialer",
                "bind_qbit_dialer",
                "attach_dialer",
                "bind_dialer",
            ),
            (
                "qbit_dialer",
                "dialer",
                "_qbit_dialer",
            ),
            qbit_dialer,
        )

        bound["track_system"] = _bind(
            (
                "attach_track_system",
                "bind_track_system",
                "attach_track",
                "bind_track",
            ),
            (
                "track_system",
                "track",
                "_track_system",
            ),
            track_system,
        )

        # ------------------------------------------------------
        # REGISTRY
        # ------------------------------------------------------

        bound["registry"] = _bind(
            (
                "attach_registry",
                "bind_registry",
            ),
            (
                "registry",
                "_registry",
            ),
            registry,
        )

        bound["registry_runtime"] = _bind(
            (
                "attach_registry_runtime",
                "bind_registry_runtime",
            ),
            (
                "registry_runtime",
                "_registry_runtime",
            ),
            registry_runtime,
        )

        bound["node_registry"] = _bind(
            (
                "attach_node_registry",
                "bind_node_registry",
                "attach_nodes",
                "bind_nodes",
            ),
            (
                "node_registry",
                "nodes",
                "_node_registry",
                "_nodes",
            ),
            node_registry,
        )

        # ------------------------------------------------------
        # KERNEL / CORE
        # ------------------------------------------------------

        bound["kernel_bus"] = _bind(
            (
                "attach_kernel_bus",
                "bind_kernel_bus",
            ),
            (
                "kernel_bus",
                "_kernel_bus",
            ),
            kernel_bus,
        )

        bound["seed_core"] = _bind(
            (
                "attach_seed_core",
                "bind_seed_core",
                "attach_seedcore",
                "bind_seedcore",
            ),
            (
                "seed_core",
                "seedcore",
                "_seed_core",
                "_seedcore",
            ),
            seed_core,
        )

        # ------------------------------------------------------
        # COGNITIVE SYSTEMS
        #
        # These remain observers/dependency references.
        # FATHUD does not execute through them.
        # ------------------------------------------------------

        bound["neural_bridge"] = _bind(
            (
                "attach_neural_bridge",
                "bind_neural_bridge",
            ),
            (
                "neural_bridge",
                "_neural_bridge",
            ),
            neural_bridge,
        )

        bound["compute_brain"] = _bind(
            (
                "attach_compute_brain",
                "bind_compute_brain",
            ),
            (
                "compute_brain",
                "_compute_brain",
            ),
            compute_brain,
        )

        bound["transformer_brain"] = _bind(
            (
                "attach_transformer_brain",
                "bind_transformer_brain",
            ),
            (
                "transformer_brain",
                "_transformer_brain",
            ),
            transformer_brain,
        )

        # ------------------------------------------------------
        # CHANNEL MANAGER
        # ------------------------------------------------------

        bound["channel_manager"] = _bind(
            (
                "attach_channel_manager",
                "bind_channel_manager",
            ),
            (
                "channel_manager",
                "_channel_manager",
            ),
            channel_manager,
        )

        # ------------------------------------------------------
        # FUTURE SEED-CONTROLLED HUD
        #
        # seed/ui/hud.py remains separate from FATHUD.
        #
        # FATHUD may retain the live reference when supplied,
        # but it does not make that HUD authoritative.
        # ------------------------------------------------------

        if hud is not None:

            bound["hud"] = _bind(
                (
                    "attach_hud",
                    "bind_hud",
                    "attach_seed_hud",
                    "bind_seed_hud",
                ),
                (
                    "hud",
                    "seed_hud",
                    "_hud",
                ),
                hud,
            )

        # ------------------------------------------------------
        # STORE RUNTIME BINDING MAP
        # ------------------------------------------------------

        self._system_bindings = dict(
            bound
        )

        self._systems_attached = True

        # ------------------------------------------------------
        # AUTHORITY FLAGS
        # ------------------------------------------------------

        self._fathud_observer_only = True
        self._command_authority = "QbitDialer"
        self._queue_authority = "QbitQueueLoop"

        # ------------------------------------------------------
        # IDENTITY REFERENCES
        #
        # These are references only. Do not deepcopy them.
        # ------------------------------------------------------

        self._authoritative_qbit = getattr(
            self,
            "qbit",
            None,
        )

        self._authoritative_queue_loop = getattr(
            self,
            "qbit_queue_loop",
            getattr(
                self,
                "queue_loop",
                None,
            ),
        )

        self._authoritative_qbit_dialer = getattr(
            self,
            "qbit_dialer",
            None,
        )

        # ------------------------------------------------------
        # LOG BINDING STATE
        # ------------------------------------------------------

        self.logger.info(
            "[FATHUD] SEED systems dynamically attached | "
            "event_bus=%s | "
            "qbit=%s | "
            "queue_loop=%s | "
            "dialer=%s | "
            "track=%s | "
            "registry=%s | "
            "registry_runtime=%s | "
            "node_registry=%s | "
            "kernel_bus=%s | "
            "seed_core=%s | "
            "neural_bridge=%s",
            (
                "ONLINE"
                if getattr(
                    self,
                    "event_bus",
                    None,
                ) is not None
                else "OFFLINE"
            ),
            (
                "ONLINE"
                if getattr(
                    self,
                    "qbit",
                    None,
                ) is not None
                else "OFFLINE"
            ),
            (
                "ONLINE"
                if getattr(
                    self,
                    "qbit_queue_loop",
                    getattr(
                        self,
                        "queue_loop",
                        None,
                    ),
                ) is not None
                else "OFFLINE"
            ),
            (
                "ONLINE"
                if getattr(
                    self,
                    "qbit_dialer",
                    None,
                ) is not None
                else "OFFLINE"
            ),
            (
                "ONLINE"
                if getattr(
                    self,
                    "track_system",
                    None,
                ) is not None
                else "OFFLINE"
            ),
            (
                "ONLINE"
                if getattr(
                    self,
                    "registry",
                    None,
                ) is not None
                else "OFFLINE"
            ),
            (
                "ONLINE"
                if getattr(
                    self,
                    "registry_runtime",
                    None,
                ) is not None
                else "OFFLINE"
            ),
            (
                "ONLINE"
                if getattr(
                    self,
                    "node_registry",
                    getattr(
                        self,
                        "nodes",
                        None,
                    ),
                ) is not None
                else "OFFLINE"
            ),
            (
                "ONLINE"
                if getattr(
                    self,
                    "kernel_bus",
                    None,
                ) is not None
                else "OFFLINE"
            ),
            (
                "ONLINE"
                if getattr(
                    self,
                    "seed_core",
                    getattr(
                        self,
                        "seedcore",
                        None,
                    ),
                ) is not None
                else "OFFLINE"
            ),
            (
                "ONLINE"
                if getattr(
                    self,
                    "neural_bridge",
                    None,
                ) is not None
                else "OFFLINE"
            ),
        )

        # ------------------------------------------------------
        # PUBLISH CURRENT STATUS
        #
        # This must remain observer telemetry.
        # ------------------------------------------------------

        publish_status = getattr(
            self,
            "_publish_fathud_status",
            None,
        )

        if callable(
            publish_status
        ):

            try:

                result = publish_status()

                if inspect.isawaitable(
                    result
                ):

                    try:

                        loop = asyncio.get_running_loop()

                        loop.create_task(
                            result
                        )

                    except RuntimeError:

                        self.logger.debug(
                            "[FATHUD] Status publication "
                            "deferred | no active runtime loop"
                        )

            except Exception as exc:

                self.logger.warning(
                    "[FATHUD] Status publication failed | "
                    "error=%s",
                    exc,
                )

        return self

    # ==========================================================
    # EVENTBUS
    # ==========================================================

    def attach_event_bus(
        self,
        event_bus,
    ):

        if event_bus is None:
            return None

        bound = self._bind_authoritative(
            "event_bus",
            event_bus,
            "EventBus",
        )

        if bound is event_bus:

            self.logger.info(
                "[FATHUD] EventBus attached"
            )

            self._subscribe_event_bus()

        return self.event_bus


    # ==========================================================
    # QBIT
    # ==========================================================

    def attach_qbit(
        self,
        qbit,
    ):

        if qbit is None:
            return None

        bound = self._bind_authoritative(
            "qbit",
            qbit,
            "Qbit",
        )

        if bound is qbit:

            self.logger.info(
                "[FATHUD] Qbit attached"
            )

        self._schedule_push()

        return self.qbit


    # ==========================================================
    # QBIT DIALER
    # ==========================================================

    def attach_qbit_dialer(
        self,
        qbit_dialer,
    ):

        if qbit_dialer is None:
            return None

        bound = self._bind_authoritative(
            "qbit_dialer",
            qbit_dialer,
            "QbitDialer",
        )

        self.dialer = self.qbit_dialer

        if bound is qbit_dialer:

            self.logger.info(
                "[FATHUD] QbitDialer attached"
            )

        self._schedule_push()

        return self.qbit_dialer


    # ==========================================================
    # COMMAND PLANE
    # ==========================================================

    def attach_command_plane(
        self,
        command_plane,
    ):

        if command_plane is None:
            return None

        self.command_plane = command_plane

        self._schedule_push()

        return command_plane


    # ==========================================================
    # TRACK SYSTEM
    # ==========================================================

    def attach_track_system(
        self,
        track_system,
    ):

        if track_system is None:
            return None

        bound = self._bind_authoritative(
            "track_system",
            track_system,
            "TrackSystem",
        )

        if bound is track_system:

            self.logger.info(
                "[FATHUD] TrackSystem attached"
            )

        self._schedule_push()

        return self.track_system


    # ==========================================================
    # QBIT QUEUE LOOP
    # ==========================================================

    def attach_queue_loop(
        self,
        queue_loop,
    ):

        if queue_loop is None:
            return None

        bound = self._bind_authoritative(
            "queue_loop",
            queue_loop,
            "QbitQueueLoop",
        )

        self.qbit_queue_loop = (
            self.queue_loop
        )

        if bound is queue_loop:

            self.logger.info(
                "[FATHUD] Authoritative "
                "QbitQueueLoop attached"
            )

        self._schedule_push()

        return self.queue_loop


    # ==========================================================
    # SEEDCORE
    # ==========================================================

    def attach_seedcore(
        self,
        seedcore,
    ):

        if seedcore is None:
            return None

        bound = self._bind_authoritative(
            "seedcore",
            seedcore,
            "SEEDCore",
        )

        self.seed_core = self.seedcore
        self.core = self.seedcore

        if bound is seedcore:

            self.logger.info(
                "[FATHUD] SEEDCore attached"
            )

        self._schedule_push()

        return self.seedcore


    # ==========================================================
    # REGISTRY RUNTIME
    # ==========================================================

    def attach_registry_runtime(
        self,
        registry_runtime,
    ):

        if registry_runtime is None:
            return None

        bound = self._bind_authoritative(
            "registry_runtime",
            registry_runtime,
            "registry_runtime",
        )

        if bound is registry_runtime:

            self.logger.info(
                "[FATHUD] registry_runtime attached"
            )

        self._schedule_push()

        return self.registry_runtime


    # ==========================================================
    # RESERVED SEED HUD CONNECTION
    #
    # HALO != SEED HUD.
    #
    # HALO:
    #   developer observer
    #
    # seed.ui.hud:
    #   future SEED-controlled popup/display surface
    # ==========================================================

    def attach_hud(
        self,
        hud,
    ):

        if hud is None:
            return None

        self.hud = hud
        self.seed_hud = hud

        self.logger.info(
            "[FATHUD] SEED HUD display reference attached | "
            "type=%s",
            _safe_type(hud),
        )

        self._schedule_push()

        return hud


    # ==========================================================
    # COMPLETE LIVE SYSTEM BIND
    # ==========================================================

    def attach_seed_systems(
        self,
        **systems,
    ):

        event_bus = systems.get(
            "event_bus"
        )

        if event_bus is not None:
            self.attach_event_bus(
                event_bus
            )

        qbit = systems.get(
            "qbit"
        )

        if qbit is not None:
            self.attach_qbit(
                qbit
            )

        qbit_dialer = (
            systems.get(
                "qbit_dialer"
            )
            or systems.get(
                "dialer"
            )
        )

        if qbit_dialer is not None:
            self.attach_qbit_dialer(
                qbit_dialer
            )

        database = systems.get("database")
        if database is not None:
            self._bind_authoritative(
                "database",
                database,
                "database",
            )

        command_plane = systems.get(
            "command_plane"
        )

        if command_plane is not None:
            self.attach_command_plane(
                command_plane
            )

        queue_loop = (
            systems.get(
                "queue_loop"
            )
            or systems.get(
                "qbit_queue_loop"
            )
        )

        if queue_loop is not None:
            self.attach_queue_loop(
                queue_loop
            )

        track_system = systems.get(
            "track_system"
        )

        if track_system is not None:
            self.attach_track_system(
                track_system
            )

        seedcore = (
            systems.get(
                "seedcore"
            )
            or systems.get(
                "seed_core"
            )
            or systems.get(
                "core"
            )
        )

        if seedcore is not None:
            self.attach_seedcore(
                seedcore
            )

        registry_runtime = systems.get(
            "registry_runtime"
        )

        if registry_runtime is not None:
            self.attach_registry_runtime(
                registry_runtime
            )

        for attr in (
            "registry",
            "node_registry",
            "kernel",
            "kernel_bus",
            "neural_network",
            "neural_bridge",
            "runtime",
            "channel_manager",
        ):

            value = systems.get(
                attr
            )

            if value is not None:

                self._bind_authoritative(
                    attr,
                    value,
                    attr,
                )

        hud = (
            systems.get("hud")
            or systems.get("seed_hud")
        )

        if hud is not None:
            self.attach_hud(
                hud
            )

        states = self._system_states()

        self.logger.info(
            "[FATHUD] SEED systems dynamically attached | "
            "kernel=%s | "
            "kernel_bus=%s | "
            "core=%s | "
            "qbit=%s | "
            "queue_loop=%s | "
            "dialer=%s | "
            "track=%s | "
            "registry=%s | "
            "registry_runtime=%s | "
            "node_registry=%s | "
            "neural_network=%s | "
            "neural_bridge=%s | "
            "command_plane=%s | "
            "runtime=%s | "
            "seed_hud=%s",
            states["kernel"],
            states["kernel_bus"],
            states["core"],
            states["qbit"],
            states["queue_loop"],
            states["dialer"],
            states["track"],
            states["registry"],
            states["registry_runtime"],
            states["node_registry"],
            states["neural_network"],
            states["neural_bridge"],
            states["command_plane"],
            states["runtime"],
            states["seed_hud"],
        )

        self._schedule_push()

        return states


    # ==========================================================
    # STATUS RESOLUTION
    #
    # User-defined HALO convention:
    #
    #   no verified attachment = OFFLINE
    #
    # Do not display meaningless UNKNOWN when the reference simply
    # is not connected.
    # ==========================================================

    def _status_of(
        self,
        obj,
    ):

        if obj is None:
            return "OFFLINE"

        # --------------------------------------------------
        # BOOL PROPERTY
        # --------------------------------------------------

        for name in (
            "online",
            "running",
            "_running",
            "active",
            "_active",
            "ready",
            "_ready",
        ):

            try:
                value = getattr(
                    obj,
                    name,
                    None,
                )

            except Exception:
                continue

            if isinstance(
                value,
                bool,
            ):

                return (
                    "ONLINE"
                    if value
                    else "OFFLINE"
                )

        # --------------------------------------------------
        # STRING STATE
        # --------------------------------------------------

        for name in (
            "status",
            "state",
            "_state",
            "runtime_state",
            "_runtime_state",
            "boot_state",
        ):

            try:
                value = getattr(
                    obj,
                    name,
                    None,
                )

            except Exception:
                continue

            if not isinstance(
                value,
                str,
            ):
                continue

            normalized = (
                value
                .strip()
                .upper()
            )

            if normalized in (
                "ONLINE",
                "READY",
                "RUNNING",
                "ACTIVE",
                "STARTED",
                "HEALTHY",
            ):
                return "ONLINE"

            if normalized in (
                "OFF",
                "OFFLINE",
                "STOPPED",
                "ERROR",
                "FAILED",
                "DEAD",
                "UNAVAILABLE",
                "DISABLED",
            ):
                return "OFFLINE"

            if normalized in (
                "WAITING",
                "DEFERRED",
                "STARTING",
                "INITIALIZING",
                "REGISTERED",
            ):
                return normalized

        # --------------------------------------------------
        # A REAL LIVE REFERENCE EXISTS.
        #
        # FATHUD knows it is connected even if the subsystem
        # exposes no formal status API.
        # --------------------------------------------------

        return "ONLINE"


    def _command_plane_reference(
        self,
    ):

        if self.command_plane is not None:
            return self.command_plane

        dialer = self.qbit_dialer

        if dialer is None:
            return None

        try:
            return getattr(
                dialer,
                "command_plane",
                None,
            )

        except Exception:
            return None


    def _system_states(
        self,
    ):

        return {
            "kernel":
                self._status_of(
                    self.kernel
                ),

            "kernel_bus":
                self._status_of(
                    self.kernel_bus
                ),

            "core":
                self._status_of(
                    self.seedcore
                ),

            "qbit":
                self._status_of(
                    self.qbit
                ),

            "queue_loop":
                self._status_of(
                    self.queue_loop
                ),

            "dialer":
                self._status_of(
                    self.qbit_dialer
                ),

            "track":
                self._status_of(
                    self.track_system
                ),

            "registry":
                self._status_of(
                    self.registry
                ),

            "registry_runtime":
                self._status_of(
                    self.registry_runtime
                ),

            "node_registry":
                self._status_of(
                    self.node_registry
                ),

            "neural_network":
                self._status_of(
                    self.neural_network
                ),

            "neural_bridge":
                self._status_of(
                    self.neural_bridge
                ),

            "command_plane":
                self._status_of(
                    self._command_plane_reference()
                ),

            "runtime":
                self._runtime_status(),

            "seed_hud":
                self._status_of(
                    self.seed_hud
                ),
        }


    def _runtime_status(
        self,
    ):

        if self.runtime is not None:
            return self._status_of(
                self.runtime
            )

        # --------------------------------------------------
        # Aggregate core runtime state.
        # --------------------------------------------------

        required = (
            self.event_bus,
            self.qbit,
            self.queue_loop,
            self.qbit_dialer,
        )

        if all(
            item is not None
            for item in required
        ):
            return "ONLINE"

        return "OFFLINE"


    # ==========================================================
    # QBIT / TRACK / CHANNEL IDENTITY
    # ==========================================================

    def _qbit_identity(
        self,
    ):

        qbit = self.qbit

        return {
            "qbit_id":
                _extract_identity(
                    qbit,
                    "qbit_id",
                    "id",
                    "uid",
                ),

            "track_id":
                _extract_identity(
                    qbit,
                    "track_id",
                    "track",
                ),

            "channel_id":
                _extract_identity(
                    qbit,
                    "channel_id",
                    "channel",
                ),

            "generation":
                _extract_identity(
                    qbit,
                    "generation",
                ),

            "instance_id":
                (
                    id(qbit)
                    if qbit is not None
                    else None
                ),
        }


    # ==========================================================
    # USER COMMAND ENVELOPE
    # ==========================================================

    def _build_command_envelope(
        self,
        command,
        *,
        client_message=None,
        source="FATHUD",
    ):

        client_message = (
            client_message
            if isinstance(
                client_message,
                dict,
            )
            else {}
        )

        raw_command = (
            str(
                command or ""
            )
            .strip()
        )

        if not raw_command:
            raise ValueError(
                "empty FATHUD command"
            )

        command_id = (
            client_message.get(
                "command_id"
            )
            or
            f"FATHUD-CMD-{uuid.uuid4().hex[:12].upper()}"
        )

        qbit_identity = (
            self._qbit_identity()
        )

        qbit_id = (
            client_message.get(
                "qbit_id"
            )
            or
            qbit_identity.get(
                "qbit_id"
            )
        )

        track_id = (
            client_message.get(
                "track_id"
            )
            or
            qbit_identity.get(
                "track_id"
            )
        )

        channel_id = (
            client_message.get(
                "channel_id"
            )
            or
            client_message.get(
                "channel"
            )
            or
            qbit_identity.get(
                "channel_id"
            )
            or
            "FATHUD"
        )

        # --------------------------------------------------
        # Basic command vocabulary.
        #
        # Preserve raw input while supplying Dialer a normalized
        # command name.
        # --------------------------------------------------

        parts = raw_command.split(
            None,
            1,
        )

        command_name = (
            parts[0]
            .strip()
            .upper()
        )

        remainder = (
            parts[1]
            if len(parts) > 1
            else None
        )

        dialer = self.qbit_dialer

        envelope = {
            "type":
                "COMMAND",

            "name":
                command_name,

            "command":
                raw_command,

            "input":
                raw_command,

            "args":
                (
                    [remainder]
                    if remainder
                    else []
                ),

            "command_id":
                command_id,

            "qbit_id":
                qbit_id,

            "track_id":
                track_id,

            "channel":
                channel_id,

            "channel_id":
                channel_id,

            "source":
                source,

            "authority":
                "QbitDialer",

            "target":
                "QBIT_DIALER",

            "route":
                [
                    "FATHUD",
                    "QBIT_DIALER",
                    "COMMAND_PLANE",
                ],

            "state":
                "CREATED",

            "timestamp":
                _utc_ts(),

            "qbit_instance_id":
                (
                    id(self.qbit)
                    if self.qbit is not None
                    else None
                ),

            "queue_loop_instance_id":
                (
                    id(self.queue_loop)
                    if self.queue_loop is not None
                    else None
                ),

            "dialer_instance_id":
                (
                    id(dialer)
                    if dialer is not None
                    else None
                ),
        }

        # --------------------------------------------------
        # Preserve explicit browser-supplied metadata.
        # --------------------------------------------------

        for key in (
            "priority",
            "confidence",
            "pipeline_id",
            "task_id",
            "intent",
            "why",
            "who",
            "what",
            "where",
            "how",
        ):

            if key in client_message:

                envelope[key] = (
                    client_message[
                        key
                    ]
                )

        return envelope


    # ==========================================================
    # COMMAND HISTORY
    # ==========================================================

    def _record_command(
        self,
        envelope,
    ):

        command_id = envelope.get(
            "command_id"
        )

        if command_id:

            self._commands[
                command_id
            ] = dict(
                envelope
            )

        self._command_history.append(
            _json_safe(
                envelope
            )
        )

        self._schedule_push()


    def _update_command_state(
        self,
        command_id,
        state,
        **metadata,
    ):

        record = self._commands.get(
            command_id
        )

        if record is None:

            record = {
                "command_id":
                    command_id,
            }

            self._commands[
                command_id
            ] = record

        record["state"] = state

        record["updated_at"] = (
            _utc_ts()
        )

        record.update(
            metadata
        )

        self._command_history.append(
            _json_safe(
                record
            )
        )

        self._schedule_push()

        return record


    # ==========================================================
    # AUTHORITATIVE COMMAND SUBMISSION
    #
    # FATHUD never calls execute_command().
    #
    # It submits into the existing QbitDialer command boundary.
    # ==========================================================

    async def _submit_command_async(
        self,
        command,
        *,
        source="FATHUD",
        client_message=None,
    ):

        dialer = self.qbit_dialer

        if dialer is None:

            raise RuntimeError(
                "QbitDialer unavailable"
            )

        envelope = (
            self._build_command_envelope(
                command,
                client_message=client_message,
                source=source,
            )
        )

        command_id = envelope[
            "command_id"
        ]

        self._record_command(
            envelope
        )

        self._update_command_state(
            command_id,
            "SUBMITTING",
        )

        # --------------------------------------------------
        # AUTHORITATIVE ENTRY POINT
        # --------------------------------------------------

        submit = getattr(
            dialer,
            "submit_command",
            None,
        )

        result = None

        try:

            if callable(submit):

                self._update_command_state(
                    command_id,
                    "SUBMITTED",
                    submit_path=(
                        "QbitDialer.submit_command"
                    ),
                )

                result = submit(
                    envelope
                )

            else:

                # ------------------------------------------
                # Compatibility:
                #
                # QbitDialer.handle_message() is explicitly
                # documented as a command-plane intake.
                # ------------------------------------------

                handle_message = getattr(
                    dialer,
                    "handle_message",
                    None,
                )

                if not callable(
                    handle_message
                ):

                    raise RuntimeError(
                        "QbitDialer exposes neither "
                        "submit_command() nor handle_message()"
                    )

                self._update_command_state(
                    command_id,
                    "SUBMITTED",
                    submit_path=(
                        "QbitDialer.handle_message"
                    ),
                )

                result = handle_message(
                    envelope
                )

            if inspect.isawaitable(
                result
            ):

                result = await result

            self._update_command_state(
                command_id,
                "COMPLETE",
                result=_json_safe(
                    result
                ),
            )

            self.append_log(
                {
                    "event":
                        "FATHUD_COMMAND_COMPLETE",

                    "command_id":
                        command_id,

                    "command":
                        envelope.get(
                            "command"
                        ),

                    "qbit_id":
                        envelope.get(
                            "qbit_id"
                        ),

                    "track_id":
                        envelope.get(
                            "track_id"
                        ),

                    "channel_id":
                        envelope.get(
                            "channel_id"
                        ),

                    "result":
                        _json_safe(
                            result
                        ),
                },
                source="FATHUD",
                label="command",
            )

            return {
                "status":
                    "submitted",

                "command_id":
                    command_id,

                "qbit_id":
                    envelope.get(
                        "qbit_id"
                    ),

                "track_id":
                    envelope.get(
                        "track_id"
                    ),

                "channel_id":
                    envelope.get(
                        "channel_id"
                    ),

                "state":
                    "COMPLETE",

                "result":
                    _json_safe(
                        result
                    ),
            }

        except Exception as exc:

            self._update_command_state(
                command_id,
                "ERROR",
                error=str(exc),
                error_type=(
                    type(exc).__name__
                ),
            )

            self.logger.exception(
                "[FATHUD] Command submission failed | "
                "command_id=%s | command=%s",
                command_id,
                command,
            )

            return {
                "status":
                    "error",

                "command_id":
                    command_id,

                "state":
                    "ERROR",

                "error":
                    str(exc),
            }


    def _submit_command(
        self,
        command,
        source="FATHUD",
        client_message=None,
    ):

        """
        Synchronous compatibility entry point.

        Does not create another SEED runtime.

        When already inside an async runtime it schedules the
        command there. WebSocket requests call _submit_command_async()
        directly.
        """

        coro = self._submit_command_async(
            command,
            source=source,
            client_message=client_message,
        )

        try:

            loop = asyncio.get_running_loop()

        except RuntimeError:

            loop = None

        if loop is not None:

            return loop.create_task(
                coro,
                name="FATHUD-Command",
            )

        # --------------------------------------------------
        # No SEED loop is created here.
        #
        # A synchronous caller with no async runtime cannot
        # safely execute an async command boundary.
        # --------------------------------------------------

        try:
            coro.close()
        except Exception:
            pass

        self.logger.warning(
            "[FATHUD] Command deferred | "
            "no running async command context"
        )

        return False


    # ==========================================================
    # LOG / OUTPUT COMPATIBILITY
    # ==========================================================

    def append_log(
        self,
        message,
        source=None,
        label=None,
        **metadata,
    ):

        entry = {
            "timestamp":
                _utc_ts(),

            "source":
                source,

            "label":
                label,

            "message":
                _json_safe(
                    message
                ),
        }

        if metadata:
            entry["metadata"] = (
                _json_safe(
                    metadata
                )
            )

        self._logs.append(
            entry
        )

        self._schedule_push()

        return True


    def append_output(
        self,
        output,
        *,
        source="SEEDCore",
        event=None,
    ):

        entry = {
            "timestamp":
                _utc_ts(),

            "source":
                source,

            "event":
                event,

            "output":
                _json_safe(
                    output
                ),
        }

        self._seed_output.append(
            entry
        )

        self._schedule_push()

        return True


    # ==========================================================
    # AUDIO
    # ==========================================================

    def set_voice_amplitude(
        self,
        amplitude,
        source=None,
    ):

        try:
            amplitude = float(
                amplitude
            )

        except Exception:
            amplitude = 0.0

        amplitude = max(
            0.0,
            min(
                1.0,
                amplitude,
            ),
        )

        self._audio_state[
            "amplitude"
        ] = amplitude

        self._audio_state[
            "timestamp"
        ] = _utc_ts()

        if source is not None:

            self._audio_state[
                "source"
            ] = source

        self._schedule_push()

        return True


    def push_audio(
        self,
        data=None,
        *,
        mime_type="audio/wav",
        url=None,
        source="SEEDCore",
    ):

        encoded = None

        if isinstance(
            data,
            bytes,
        ):

            encoded = (
                base64.b64encode(
                    data
                )
                .decode("ascii")
            )

        elif isinstance(
            data,
            str,
        ):

            encoded = data

        self._audio_state[
            "sequence"
        ] += 1

        self._audio_state.update({
            "mime_type":
                mime_type,

            "data":
                encoded,

            "url":
                url,

            "source":
                source,

            "timestamp":
                _utc_ts(),
        })

        self._schedule_push()

        return True


    # ==========================================================
    # DOT MATRIX
    # ==========================================================

    def set_dot_matrix(
        self,
        matrix,
        *,
        source="SEEDCore",
        width=None,
        height=None,
        depth=None,
    ):

        if matrix is None:
            matrix = []

        self._dot_matrix_3d = (
            _json_safe(
                matrix
            )
        )

        self._dot_matrix_meta = {
            "timestamp":
                _utc_ts(),

            "source":
                source,

            "width":
                width,

            "height":
                height,

            "depth":
                depth,
        }

        self._schedule_push()

        return True


    # ==========================================================
    # EVENTBUS SUBSCRIPTION
    # ==========================================================

    def _subscribe_event_bus(
        self,
    ):

        event_bus = self.event_bus

        if (
            event_bus is None
            or
            self._event_bus_attached
        ):
            return False

        # --------------------------------------------------
        # Existing EventBus builds have used several names.
        # Attach to the existing implementation only.
        # --------------------------------------------------

        for method_name in (
            "subscribe",
            "register",
            "on",
            "listen",
        ):

            method = getattr(
                event_bus,
                method_name,
                None,
            )

            if not callable(
                method
            ):
                continue

            attempts = (
                (
                    "*",
                    self._on_event,
                ),
                (
                    self._on_event,
                ),
            )

            for args in attempts:

                try:

                    result = method(
                        *args
                    )

                    self._event_bus_subscription = (
                        result
                    )

                    self._event_bus_attached = True

                    return True

                except TypeError:
                    continue

                except Exception:

                    self.logger.debug(
                        "[FATHUD] EventBus subscription "
                        "attempt failed | method=%s",
                        method_name,
                        exc_info=True,
                    )

        return False


    # ==========================================================
    # EVENT INTAKE
    # ==========================================================

    def receive_event(
        self,
        event,
        payload=None,
    ):

        return self._on_event(
            event,
            payload,
        )


    def publish(
        self,
        event,
        payload=None,
    ):

        return self._on_event(
            event,
            payload,
        )


    def emit(
        self,
        event,
        payload=None,
    ):

        return self._on_event(
            event,
            payload,
        )


    def update(
        self,
        event,
        payload=None,
    ):

        if payload is None and isinstance(
            event,
            dict,
        ):

            return self._on_event(
                event
            )

        return self._on_event(
            event,
            payload,
        )


    def _on_event(
        self,
        event,
        payload=None,
        *args,
        **kwargs,
    ):

        # --------------------------------------------------
        # NORMALIZE EVENT SHAPES
        # --------------------------------------------------

        event_name = None
        event_payload = payload
        event_source = None

        if isinstance(
            event,
            dict,
        ):

            event_name = (
                event.get("event")
                or event.get("type")
                or event.get("name")
                or event.get("topic")
            )

            if event_payload is None:

                event_payload = (
                    event.get("payload")
                    if "payload" in event
                    else event.get("data")
                )

            event_source = (
                event.get("source")
                or event.get("origin")
                or event.get("module")
            )

        else:

            event_name = _safe_string(
                event,
                "EVENT",
            )

        if isinstance(
            event_payload,
            dict,
        ):

            event_source = (
                event_source
                or event_payload.get(
                    "source"
                )
                or event_payload.get(
                    "origin"
                )
                or event_payload.get(
                    "module"
                )
                or event_payload.get(
                    "component"
                )
            )

        event_name = (
            event_name
            or "EVENT"
        )

        entry = {
            "timestamp":
                _utc_ts(),

            "event":
                event_name,

            "source":
                event_source,

            "payload":
                _json_safe(
                    event_payload
                ),
        }

        self._last_event = (
            event_name
        )

        self._last_payload = (
            event_payload
        )

        self._append_event(
            entry
        )

        # --------------------------------------------------
        # COMMAND LIFECYCLE FEEDBACK
        # --------------------------------------------------

        if isinstance(
            event_payload,
            dict,
        ):

            command_id = (
                event_payload.get(
                    "command_id"
                )
            )

            state = (
                event_payload.get(
                    "state"
                )
                or event_payload.get(
                    "status"
                )
            )

            if (
                command_id
                and
                state
            ):

                self._update_command_state(
                    command_id,
                    str(state).upper(),
                    event=event_name,
                    event_payload=(
                        _json_safe(
                            event_payload
                        )
                    ),
                )

        # --------------------------------------------------
        # SEED OUTPUT CAPTURE
        #
        # Previous source filter was too narrow.
        # --------------------------------------------------

        source_text = (
            str(
                event_source
                or ""
            )
            .upper()
        )

        event_text = (
            str(
                event_name
                or ""
            )
            .upper()
        )

        output_source = any(
            token in source_text
            for token in (
                "SEED",
                "CORE",
                "QBIT",
                "DIALER",
                "ORACLE",
                "TRANSFORMER",
                "COMPUTE",
                "INTENT",
                "ANALYTICS",
                "AGENT",
                "ACTION",
                "MEMORY",
                "AUDIO",
                "VOICE",
            )
        )

        output_event = any(
            token in event_text
            for token in (
                "OUTPUT",
                "RESPONSE",
                "RESULT",
                "MESSAGE",
                "COMMAND",
                "THOUGHT",
                "COGNITIVE",
                "VOICE",
                "AUDIO",
                "QBIT",
            )
        )

        if (
            output_source
            or output_event
        ):

            self.append_output(
                event_payload,
                source=(
                    event_source
                    or event_name
                ),
                event=event_name,
            )

        # --------------------------------------------------
        # AUDIO OBSERVATION
        # --------------------------------------------------

        if isinstance(
            event_payload,
            dict,
        ):

            amplitude = (
                event_payload.get(
                    "voice_amplitude"
                )
            )

            if amplitude is None:

                amplitude = (
                    event_payload.get(
                        "amplitude"
                    )
                    if "VOICE" in event_text
                    or "AUDIO" in event_text
                    else None
                )

            if amplitude is not None:

                self.set_voice_amplitude(
                    amplitude,
                    source=event_source,
                )

            audio_data = (
                event_payload.get(
                    "audio_data"
                )
                or event_payload.get(
                    "audio_base64"
                )
            )

            audio_url = (
                event_payload.get(
                    "audio_url"
                )
            )

            if (
                audio_data is not None
                or
                audio_url is not None
            ):

                self.push_audio(
                    audio_data,
                    mime_type=(
                        event_payload.get(
                            "mime_type",
                            "audio/wav",
                        )
                    ),
                    url=audio_url,
                    source=(
                        event_source
                        or "SEED"
                    ),
                )

            matrix = (
                event_payload.get(
                    "dot_matrix_3d"
                )
            )

            if matrix is None:

                matrix = (
                    event_payload.get(
                        "dot_matrix"
                    )
                )

            if matrix is not None:

                self.set_dot_matrix(
                    matrix,
                    source=(
                        event_source
                        or "SEED"
                    ),
                )

        self._schedule_push()

        return True


    def _append_event(
        self,
        event,
    ):

        self._events.append(
            _json_safe(
                event
            )
        )

        return True


    # ==========================================================
    # WEBSOCKET
    # ==========================================================

    def _start_websocket(
        self,
    ):

        if self._ws_started:
            return False

        self._ws_started = True

        def runner():

            try:

                asyncio.run(
                    self._serve_websocket()
                )

            except Exception as exc:

                self._ws_started = False
                self._ws_running = False

                self.logger.error(
                    "[FATHUD][WS FAIL] %s",
                    exc,
                )

        self._ws_thread = (
            threading.Thread(
                target=runner,
                name="FATHUD-WebSocket",
                daemon=True,
            )
        )

        self._ws_thread.start()

        return True


    async def _serve_websocket(
        self,
    ):

        try:

            import websockets

        except Exception as exc:

            self.logger.error(
                "[FATHUD] websockets unavailable: %s",
                exc,
            )

            self._ws_started = False

            return False

        self._ws_loop = (
            asyncio.get_running_loop()
        )

        async def handler(
            websocket,
            *args,
        ):

            self._clients.add(
                websocket
            )

            self.logger.info(
                "[FATHUD] Client connected (%s)",
                len(self._clients),
            )

            try:

                await websocket.send(
                    json.dumps(
                        self._build_payload()
                    )
                )

                async for message in websocket:

                    await self._handle_client_message(
                        websocket,
                        message,
                    )

            except Exception:

                self.logger.debug(
                    "[FATHUD] WebSocket client closed",
                    exc_info=True,
                )

            finally:

                self._clients.discard(
                    websocket
                )

                self.logger.info(
                    "[FATHUD] Client disconnected (%s)",
                    len(self._clients),
                )

        try:

            self._ws_server = (
                await websockets.serve(
                    handler,
                    self.host,
                    self.port,
                )
            )

            self._ws_running = True

            self.logger.info(
                "[FATHUD] WebSocket running: "
                "ws://%s:%s",
                self.host,
                self.port,
            )

            await self._ws_server.wait_closed()

        except asyncio.CancelledError:
            raise

        except Exception as exc:

            self._ws_running = False
            self._ws_started = False

            self.logger.error(
                "[FATHUD][WS FAIL] %s",
                exc,
            )


    # ==========================================================
    # CLIENT MESSAGE
    # ==========================================================

    async def _handle_client_message(
        self,
        websocket,
        message,
    ):

        try:

            data = json.loads(
                message
            )

        except Exception:

            data = {
                "type":
                    "SEED_COMMAND",

                "command":
                    str(message),
            }

        if not isinstance(
            data,
            dict,
        ):

            return False

        message_type = (
            str(
                data.get(
                    "type",
                    "",
                )
            )
            .upper()
        )

        # --------------------------------------------------
        # COMMAND
        # --------------------------------------------------

        if message_type in (
            "SEED_COMMAND",
            "COMMAND",
            "QBIT_COMMAND",
            "SYSTEM_REQUEST",
        ):

            command = (
                data.get("command")
                or data.get("input")
                or data.get("name")
            )

            if not command:

                response = {
                    "type":
                        "COMMAND_ERROR",

                    "error":
                        "empty command",
                }

            else:

                result = (
                    await self._submit_command_async(
                        command,
                        source="FATHUD",
                        client_message=data,
                    )
                )

                response = {
                    "type":
                        "COMMAND_RESPONSE",

                    **result,
                }

            try:

                await websocket.send(
                    json.dumps(
                        _json_safe(
                            response
                        )
                    )
                )

            except Exception:
                pass

            return True

        # --------------------------------------------------
        # SNAPSHOT / REFRESH
        # --------------------------------------------------

        if message_type in (
            "GET_STATE",
            "SNAPSHOT",
            "REFRESH",
            "STATUS",
        ):

            try:

                await websocket.send(
                    json.dumps(
                        self._build_payload()
                    )
                )

            except Exception:
                pass

            return True

        return False


    # ==========================================================
    # HTTP SERVER
    # ==========================================================

    def _start_http_server(
        self,
    ):

        if self._http_started:
            return False

        self._http_started = True

        adapter = self

        class HUDRequestHandler(
            BaseHTTPRequestHandler
        ):

            def do_GET(self):

                if self.path not in (
                    "/",
                    "/index.html",
                    "/hudwebui.html",
                    "/health",
                ):

                    self.send_response(
                        404
                    )

                    self.end_headers()

                    return

                html_path = HUD_HTML_PATH

                if html_path.is_file():
                    body = html_path.read_text(
                        encoding="utf-8"
                    ).encode("utf-8")
                else:
                    body = (
                        adapter
                        ._build_html()
                        .encode(
                            "utf-8"
                        )
                    )

                self.send_response(
                    200
                )

                self.send_header(
                    "Content-Type",
                    "text/html; charset=utf-8",
                )

                self.send_header(
                    "Content-Length",
                    str(len(body)),
                )

                self.send_header(
                    "Cache-Control",
                    "no-store",
                )

                self.end_headers()

                self.wfile.write(
                    body
                )

            def log_message(
                self,
                format,
                *args,
            ):
                return

        def runner():

            try:

                self._http_server = (
                    ThreadingHTTPServer(
                        (
                            self.host,
                            self.http_port,
                        ),
                        HUDRequestHandler,
                    )
                )

                self.logger.info(
                    "[FATHUD] Browser HUD available: "
                    "http://%s:%s",
                    self.host,
                    self.http_port,
                )

                self._http_server.serve_forever()

            except Exception as exc:

                self._http_started = False

                self.logger.error(
                    "[FATHUD][HTTP FAIL] %s",
                    exc,
                )

        self._http_thread = (
            threading.Thread(
                target=runner,
                name="FATHUD-HTTP",
                daemon=True,
            )
        )

        self._http_thread.start()

        return True


    # ==========================================================
    # BROWSER
    # ==========================================================

    def _open_browser(
        self,
    ):

        try:

            webbrowser.open(
                self.url
            )

            self.logger.info(
                "[FATHUD] Browser HUD opened: %s",
                self.url,
            )

            return True

        except Exception:

            self.logger.exception(
                "[FATHUD] Failed to open Browser HUD"
            )

            return False


    # ==========================================================
    # PAYLOAD BUILD
    # ==========================================================

    def _build_payload(
        self,
    ):

        qbit_identity = (
            self._qbit_identity()
        )

        dialer = self.qbit_dialer

        command_plane = (
            self._command_plane_reference()
        )

        command_plane_snapshot = None

        if isinstance(
            command_plane,
            dict,
        ):

            command_plane_snapshot = (
                _json_safe(
                    command_plane
                )
            )

        elif command_plane is not None:

            snapshot = getattr(
                command_plane,
                "snapshot",
                None,
            )

            if callable(snapshot):

                try:
                    command_plane_snapshot = (
                        _json_safe(
                            snapshot()
                        )
                    )
                except Exception:
                    pass

        queue_depth = None

        queue_loop = self.queue_loop

        if queue_loop is not None:

            for target in (
                getattr(
                    queue_loop,
                    "qbit_queue",
                    None,
                ),
                queue_loop,
            ):

                if target is None:
                    continue

                qsize = getattr(
                    target,
                    "qsize",
                    None,
                )

                if callable(qsize):

                    try:

                        queue_depth = (
                            qsize()
                        )

                        break

                    except Exception:
                        pass

        dialer_runtime_state = None

        if dialer is not None:

            dialer_runtime_state = (
                getattr(
                    dialer,
                    "_runtime_state",
                    None,
                )
                or getattr(
                    dialer,
                    "runtime_state",
                    None,
                )
            )

        latest_commands = (
            list(
                self._command_history
            )[-50:]
        )

        return _json_safe({
            "type":
                "FATHUD_STATE",

            "project":
                "HALO",

            "timestamp":
                _utc_ts(),

            "online":
                self.online,

            "clients":
                self.client_count,

            "systems":
                self._system_states(),

            "qbit":
                qbit_identity,

            "command_path": {
                "authority":
                    "QbitDialer",

                "route": [
                    "FATHUD",
                    "QBIT_DIALER",
                    "COMMAND_PLANE",
                ],

                "dialer_runtime_state":
                    dialer_runtime_state,

                "queue_depth":
                    queue_depth,

                "dialer_instance_id":
                    (
                        id(dialer)
                        if dialer is not None
                        else None
                    ),

                "queue_loop_instance_id":
                    (
                        id(queue_loop)
                        if queue_loop is not None
                        else None
                    ),
            },

            "command_plane":
                command_plane_snapshot,

            "commands":
                latest_commands,

            "events":
                list(
                    self._events
                )[-100:],

            "logs":
                list(
                    self._logs
                )[-100:],

            "seed_output":
                list(
                    self._seed_output
                )[-100:],

            "voice_amplitude":
                self._audio_state.get(
                    "amplitude",
                    0.0,
                ),

            "audio":
                dict(
                    self._audio_state
                ),

            "dot_matrix_3d":
                self._dot_matrix_3d,

            "dot_matrix_meta":
                self._dot_matrix_meta,

            "seed_hud": {
                "connected":
                    self.seed_hud
                    is not None,

                "type":
                    _safe_type(
                        self.seed_hud
                    ),

                "role":
                    "SEED_CONTROLLED_DISPLAY",

                "authority":
                    False,
            },
        })


    # ==========================================================
    # PUSH
    # ==========================================================

    def _schedule_push(
        self,
    ):

        if (
            not self._ws_running
            or
            self._ws_loop is None
            or
            not self._clients
        ):
            return False

        with self._push_lock:

            self._push_generation += 1

            if self._push_pending:
                return True

            self._push_pending = True

        async def delayed():

            try:

                await asyncio.sleep(
                    0.03
                )

                await self._push_to_clients()

            finally:

                with self._push_lock:
                    self._push_pending = False

        try:

            asyncio.run_coroutine_threadsafe(
                delayed(),
                self._ws_loop,
            )

            return True

        except Exception:

            with self._push_lock:
                self._push_pending = False

            return False


    async def _push_to_clients(
        self,
    ):

        if not self._clients:
            return False

        payload = json.dumps(
            self._build_payload()
        )

        dead = []

        for client in list(
            self._clients
        ):

            try:

                await client.send(
                    payload
                )

            except Exception:

                dead.append(
                    client
                )

        for client in dead:

            self._clients.discard(
                client
            )

        return True


    def push(
        self,
        event=None,
        payload=None,
    ):

        if event is not None:

            self._on_event(
                event,
                payload,
            )

        return self._schedule_push()


    # ==========================================================
    # PROPERTIES
    # ==========================================================

    @property
    def online(
        self,
    ):

        return bool(
            self._ws_running
            or
            self._http_started
        )


    @property
    def client_count(
        self,
    ):

        return len(
            self._clients
        )


    @property
    def url(
        self,
    ):

        return (
            f"http://{self.host}:"
            f"{self.http_port}"
        )


    # ==========================================================
    # HTML / HALO
    # ==========================================================

    def _build_html(
        self,
    ):

        ws_url = (
            f"ws://{self.host}:{self.port}"
        )

        return f"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">

<title>SEED AI OS — HALO</title>

<style>

* {{
    box-sizing: border-box;
}}

html,
body {{
    margin: 0;
    padding: 0;
    width: 100%;
    height: 100%;
    background:
        radial-gradient(circle at center, #08130f 0%, #020504 58%, #000 100%);
    color: #d9ffe8;
    font-family:
        Consolas,
        "Courier New",
        monospace;
}}

body {{
    overflow: hidden;
}}

#halo {{
    display: grid;
    grid-template-columns: 280px 1fr 340px;
    grid-template-rows: 70px 1fr 210px;
    width: 100vw;
    height: 100vh;
    gap: 8px;
    padding: 8px;
}}

.panel {{
    border: 1px solid #174a32;
    background: rgba(0, 12, 8, 0.86);
    box-shadow:
        inset 0 0 24px rgba(0, 255, 145, 0.04),
        0 0 10px rgba(0, 255, 145, 0.04);
    border-radius: 6px;
    overflow: hidden;
}}

.panel-title {{
    padding: 7px 10px;
    border-bottom: 1px solid #174a32;
    color: #62ffad;
    font-size: 12px;
    font-weight: bold;
    letter-spacing: 1px;
}}

#header {{
    grid-column: 1 / 4;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 18px;
}}

#brand {{
    font-size: 23px;
    font-weight: bold;
    letter-spacing: 4px;
    color: #7effbb;
}}

#subbrand {{
    color: #5d8e76;
    font-size: 11px;
}}

#connection {{
    font-size: 12px;
}}

.online {{
    color: #55ff9c;
}}

.offline {{
    color: #ff6767;
}}

.waiting {{
    color: #ffd56a;
}}

#systems {{
    grid-column: 1;
    grid-row: 2;
    overflow-y: auto;
}}

.system-row {{
    display: flex;
    justify-content: space-between;
    border-bottom: 1px solid #0e271b;
    padding: 8px 10px;
    font-size: 12px;
}}

.system-name {{
    color: #9ecab0;
}}

.system-state {{
    font-weight: bold;
}}

#center {{
    grid-column: 2;
    grid-row: 2;
    display: grid;
    grid-template-rows: 1fr 185px;
    gap: 8px;
    min-width: 0;
}}

#matrix-panel {{
    position: relative;
}}

#matrix {{
    width: 100%;
    height: calc(100% - 29px);
    display: block;
}}

#matrix-label {{
    position: absolute;
    left: 12px;
    bottom: 8px;
    color: #43775c;
    font-size: 10px;
}}

#output {{
    overflow-y: auto;
    padding: 8px 10px;
    font-size: 11px;
    white-space: pre-wrap;
}}

.output-line {{
    border-bottom: 1px solid #0d2419;
    padding: 4px 0;
}}

#right {{
    grid-column: 3;
    grid-row: 2;
    display: grid;
    grid-template-rows: auto auto 1fr;
    gap: 8px;
}}

#identity-body,
#command-path-body {{
    padding: 10px;
    font-size: 11px;
}}

.kv {{
    display: grid;
    grid-template-columns: 108px 1fr;
    gap: 4px;
    margin-bottom: 5px;
}}

.key {{
    color: #5e9478;
}}

.value {{
    color: #c9ffe0;
    overflow-wrap: anywhere;
}}

#command-history {{
    overflow-y: auto;
    font-size: 10px;
    padding: 8px;
}}

.command-row {{
    border-bottom: 1px solid #143222;
    padding: 5px 2px;
}}

.command-id {{
    color: #71ffb5;
}}

.command-state {{
    color: #f1dc7a;
}}

#bottom-left {{
    grid-column: 1;
    grid-row: 3;
}}

#menus {{
    height: calc(100% - 29px);
    padding: 8px;
    overflow-y: auto;
}}

.menu-button {{
    width: 100%;
    margin-bottom: 5px;
    padding: 7px;
    color: #bfffd7;
    background: #07170f;
    border: 1px solid #215d3e;
    border-radius: 3px;
    cursor: pointer;
    text-align: left;
    font-family: inherit;
}}

.menu-button:hover {{
    background: #0c2619;
    border-color: #4bba7d;
}}

#command-panel {{
    grid-column: 2;
    grid-row: 3;
    display: grid;
    grid-template-rows: 29px auto 1fr;
}}

#command-input-row {{
    display: grid;
    grid-template-columns: 1fr 105px;
    gap: 7px;
    padding: 8px;
}}

#command-input {{
    background: #020905;
    border: 1px solid #286747;
    color: #d4ffe4;
    padding: 9px;
    font-family: inherit;
}}

#submit {{
    background: #0b2d1d;
    color: #8cffba;
    border: 1px solid #368a5d;
    cursor: pointer;
    font-family: inherit;
}}

#submit:hover {{
    background: #104a2d;
}}

#command-live {{
    overflow-y: auto;
    padding: 8px;
    font-size: 10px;
}}

#media {{
    grid-column: 3;
    grid-row: 3;
    display: grid;
    grid-template-rows: 29px 44px 1fr;
}}

#audio {{
    width: calc(100% - 14px);
    height: 34px;
    margin: 5px 7px;
}}

#waveform {{
    width: 100%;
    height: 100%;
}}

.small {{
    font-size: 10px;
    color: #57866d;
}}

</style>
</head>

<body>

<div id="halo">

    <div id="header" class="panel">

        <div>
            <div id="brand">HALO</div>
            <div id="subbrand">
                SEED AI OS — CORE CONTROL OBSERVABILITY
            </div>
        </div>

        <div id="connection" class="offline">
            WEBSOCKET OFFLINE
        </div>

    </div>


    <div id="systems" class="panel">

        <div class="panel-title">
            SYSTEMS
        </div>

        <div id="systems-body"></div>

    </div>


    <div id="center">

        <div id="matrix-panel" class="panel">

            <div class="panel-title">
                SEED DOT MATRIX
            </div>

            <canvas id="matrix"></canvas>

            <div id="matrix-label">
                waiting for dot_matrix_3d
            </div>

        </div>


        <div class="panel">

            <div class="panel-title">
                SEED OUTPUT
            </div>

            <div id="output"></div>

        </div>

    </div>


    <div id="right">

        <div class="panel">

            <div class="panel-title">
                QBIT IDENTITY
            </div>

            <div id="identity-body"></div>

        </div>


        <div class="panel">

            <div class="panel-title">
                COMMAND PATH
            </div>

            <div id="command-path-body"></div>

        </div>


        <div class="panel">

            <div class="panel-title">
                COMMAND LIFECYCLE
            </div>

            <div id="command-history"></div>

        </div>

    </div>


    <div id="bottom-left" class="panel">

        <div class="panel-title">
            SYSTEM REQUESTS
        </div>

        <div id="menus">

            <button class="menu-button"
                onclick="sendCommand('STATUS')">
                SYSTEM STATUS
            </button>

            <button class="menu-button"
                onclick="sendCommand('GET_STATE')">
                RUNTIME STATE
            </button>

            <button class="menu-button"
                onclick="sendCommand('QUEUE_STATUS')">
                QBIT QUEUE
            </button>

            <button class="menu-button"
                onclick="sendCommand('COGNITION_STATUS')">
                COGNITION
            </button>

            <button class="menu-button"
                onclick="sendCommand('HEARTBEAT_STATUS')">
                HEARTBEAT
            </button>

            <button class="menu-button"
                onclick="sendCommand('SNAPSHOT')">
                SNAPSHOT
            </button>

            <button class="menu-button"
                onclick="sendCommand('MEASURE')">
                QBIT MEASURE
            </button>

            <button class="menu-button"
                onclick="sendCommand('MEMORY STATUS')">
                MEMORY STATUS
            </button>

            <button class="menu-button"
                onclick="sendCommand('TRACKS STATUS')">
                TRACK SYSTEM
            </button>

            <button class="menu-button"
                onclick="sendCommand('SYSTEM HEALTH')">
                SYSTEM HEALTH
            </button>

        </div>

    </div>


    <div id="command-panel" class="panel">

        <div class="panel-title">
            USER → QBIT → QBIT DIALER
        </div>

        <div id="command-input-row">

            <input
                id="command-input"
                type="text"
                placeholder="Enter SEED command..."
                autocomplete="off"
            >

            <button
                id="submit"
                onclick="submitInput()"
            >
                SUBMIT
            </button>

        </div>

        <div id="command-live"></div>

    </div>


    <div id="media" class="panel">

        <div class="panel-title">
            SEED AUDIO
        </div>

        <audio
            id="audio"
            controls
        ></audio>

        <canvas id="waveform"></canvas>

    </div>

</div>


<script>

const WS_URL = {json.dumps(ws_url)};

let ws = null;
let state = null;

let lastAudioSequence = -1;
let voiceAmplitude = 0.0;


// ==========================================================
// DOM HELPERS
// ==========================================================

function escapeHtml(value) {{

    if (value === null || value === undefined)
        return "";

    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;");
}}


function shortValue(value) {{

    if (value === null || value === undefined)
        return "—";

    let s = String(value);

    if (s.length > 48)
        return s.substring(0, 45) + "...";

    return s;
}}


// ==========================================================
// WEBSOCKET
// ==========================================================

function connect() {{

    const indicator =
        document.getElementById("connection");

    try {{

        ws = new WebSocket(
            WS_URL
        );

    }} catch (err) {{

        indicator.textContent =
            "WEBSOCKET ERROR";

        indicator.className =
            "offline";

        setTimeout(
            connect,
            1500
        );

        return;
    }}


    ws.onopen = () => {{

        indicator.textContent =
            "WEBSOCKET ONLINE";

        indicator.className =
            "online";

        ws.send(
            JSON.stringify({{
                type: "SNAPSHOT"
            }})
        );
    }};


    ws.onclose = () => {{

        indicator.textContent =
            "WEBSOCKET OFFLINE";

        indicator.className =
            "offline";

        setTimeout(
            connect,
            1500
        );
    }};


    ws.onerror = () => {{

        indicator.textContent =
            "WEBSOCKET ERROR";

        indicator.className =
            "offline";
    }};


    ws.onmessage = (evt) => {{

        try {{

            const data =
                JSON.parse(evt.data);

            if (
                data.type ===
                "FATHUD_STATE"
            ) {{

                state = data;

                renderState(
                    data
                );

            }} else {{

                renderCommandResponse(
                    data
                );
            }}

        }} catch (err) {{

            console.error(
                "HALO message error",
                err
            );
        }}
    }};
}}


// ==========================================================
// COMMAND SUBMISSION
// ==========================================================

function newCommandId() {{

    return (
        "HALO-" +
        Date.now().toString(36).toUpperCase() +
        "-" +
        Math.random()
            .toString(16)
            .slice(2, 8)
            .toUpperCase()
    );
}}


function sendCommand(command) {{

    if (
        !ws ||
        ws.readyState !==
        WebSocket.OPEN
    ) {{

        renderCommandResponse({{
            state: "ERROR",
            error: "WebSocket offline"
        }});

        return;
    }}

    const qbit =
        state?.qbit || {{}};

    const commandId =
        newCommandId();

    const envelope = {{
        type:
            "SEED_COMMAND",

        command:
            command,

        command_id:
            commandId,

        qbit_id:
            qbit.qbit_id || null,

        track_id:
            qbit.track_id || null,

        channel_id:
            qbit.channel_id || "FATHUD",

        source:
            "FATHUD",

        target:
            "QBIT_DIALER",

        timestamp:
            Date.now() / 1000
    }};

    renderCommandResponse({{
        command_id:
            commandId,

        command:
            command,

        qbit_id:
            envelope.qbit_id,

        track_id:
            envelope.track_id,

        channel_id:
            envelope.channel_id,

        state:
            "SUBMITTING"
    }});

    ws.send(
        JSON.stringify(
            envelope
        )
    );
}}


function submitInput() {{

    const input =
        document.getElementById(
            "command-input"
        );

    const command =
        input.value.trim();

    if (!command)
        return;

    sendCommand(
        command
    );

    input.value = "";
}}


document
    .getElementById(
        "command-input"
    )
    .addEventListener(
        "keydown",
        event => {{

            if (
                event.key ===
                "Enter"
            ) {{

                submitInput();
            }}
        }}
    );


// ==========================================================
// SYSTEMS
// ==========================================================

function renderSystems(systems) {{

    const root =
        document.getElementById(
            "systems-body"
        );

    root.innerHTML = "";

    Object.entries(
        systems || {{}}
    ).forEach(
        ([name, value]) => {{

            const row =
                document.createElement(
                    "div"
                );

            row.className =
                "system-row";

            const stateText =
                String(
                    value || "OFFLINE"
                ).toUpperCase();

            let stateClass =
                "waiting";

            if (
                stateText === "ONLINE" ||
                stateText === "READY"
            ) {{

                stateClass =
                    "online";

            }} else if (
                stateText === "OFFLINE" ||
                stateText === "ERROR" ||
                stateText === "FAILED"
            ) {{

                stateClass =
                    "offline";
            }}

            row.innerHTML =
                `<span class="system-name">${{escapeHtml(name)}}</span>` +
                `<span class="system-state ${{stateClass}}">${{escapeHtml(stateText)}}</span>`;

            root.appendChild(
                row
            );
        }}
    );
}}


// ==========================================================
// QBIT IDENTITY
// ==========================================================

function renderIdentity(qbit) {{

    const root =
        document.getElementById(
            "identity-body"
        );

    const values = {{
        QBIT:
            qbit?.qbit_id,

        TRACK:
            qbit?.track_id,

        CHANNEL:
            qbit?.channel_id,

        GENERATION:
            qbit?.generation,

        INSTANCE:
            qbit?.instance_id
    }};

    root.innerHTML =
        Object.entries(values)
        .map(
            ([key, value]) =>
                `<div class="kv">` +
                `<div class="key">${{key}}</div>` +
                `<div class="value">${{escapeHtml(shortValue(value))}}</div>` +
                `</div>`
        )
        .join("");
}}


// ==========================================================
// COMMAND PATH
// ==========================================================

function renderCommandPath(path) {{

    const root =
        document.getElementById(
            "command-path-body"
        );

    const route =
        Array.isArray(
            path?.route
        )
        ? path.route.join(" → ")
        : "—";

    const values = {{
        AUTHORITY:
            path?.authority,

        ROUTE:
            route,

        DIALER:
            path?.dialer_runtime_state,

        QUEUE_DEPTH:
            path?.queue_depth,

        DIALER_ID:
            path?.dialer_instance_id,

        QUEUE_ID:
            path?.queue_loop_instance_id
    }};

    root.innerHTML =
        Object.entries(values)
        .map(
            ([key, value]) =>
                `<div class="kv">` +
                `<div class="key">${{key}}</div>` +
                `<div class="value">${{escapeHtml(shortValue(value))}}</div>` +
                `</div>`
        )
        .join("");
}}


// ==========================================================
// COMMAND HISTORY
// ==========================================================

function renderCommands(commands) {{

    const root =
        document.getElementById(
            "command-history"
        );

    const recent =
        (commands || [])
        .slice(-40)
        .reverse();

    root.innerHTML =
        recent.map(
            item => {{

                const id =
                    item.command_id || "—";

                const state =
                    item.state || "—";

                const command =
                    item.command ||
                    item.name ||
                    "";

                return (
                    `<div class="command-row">` +
                    `<div class="command-id">${{escapeHtml(id)}}</div>` +
                    `<div>${{escapeHtml(command)}}</div>` +
                    `<div class="command-state">${{escapeHtml(state)}}</div>` +
                    `<div class="small">QBIT: ${{escapeHtml(shortValue(item.qbit_id))}}</div>` +
                    `<div class="small">TRACK: ${{escapeHtml(shortValue(item.track_id))}}</div>` +
                    `</div>`
                );
            }}
        )
        .join("");
}}


function renderCommandResponse(data) {{

    const root =
        document.getElementById(
            "command-live"
        );

    const line =
        document.createElement(
            "div"
        );

    line.className =
        "command-row";

    line.innerHTML =
        `<span class="command-id">${{escapeHtml(data.command_id || "HALO")}}</span> ` +
        `<span class="command-state">${{escapeHtml(data.state || data.status || "")}}</span> ` +
        `${{escapeHtml(data.command || data.error || "")}}`;

    root.prepend(
        line
    );

    while (
        root.children.length > 40
    ) {{

        root.removeChild(
            root.lastChild
        );
    }}
}}


// ==========================================================
// SEED OUTPUT
// ==========================================================

function renderOutput(output) {{

    const root =
        document.getElementById(
            "output"
        );

    const recent =
        (output || [])
        .slice(-80);

    root.innerHTML =
        recent.map(
            item => {{

                let body =
                    item.output;

                if (
                    typeof body ===
                    "object"
                ) {{

                    try {{
                        body =
                            JSON.stringify(
                                body
                            );
                    }} catch (_) {{
                        body =
                            String(body);
                    }}
                }}

                return (
                    `<div class="output-line">` +
                    `<span class="small">${{escapeHtml(item.source || item.event || "SEED")}}</span> ` +
                    `${{escapeHtml(body)}}` +
                    `</div>`
                );
            }}
        )
        .join("");

    root.scrollTop =
        root.scrollHeight;
}}


// ==========================================================
// AUDIO
// ==========================================================

function renderAudio(audio) {{

    if (!audio)
        return;

    voiceAmplitude =
        Number(
            audio.amplitude || 0
        );

    const sequence =
        Number(
            audio.sequence || 0
        );

    if (
        sequence ===
        lastAudioSequence
    )
        return;

    lastAudioSequence =
        sequence;

    const player =
        document.getElementById(
            "audio"
        );

    if (audio.url) {{

        player.src =
            audio.url;

        player.play()
            .catch(() => {{}});

        return;
    }}

    if (audio.data) {{

        const mime =
            audio.mime_type ||
            "audio/wav";

        player.src =
            `data:${{mime}};base64,${{audio.data}}`;

        player.play()
            .catch(() => {{}});
    }}
}}


// ==========================================================
// WAVEFORM
// ==========================================================

function drawWaveform() {{

    const canvas =
        document.getElementById(
            "waveform"
        );

    const rect =
        canvas.getBoundingClientRect();

    const dpr =
        window.devicePixelRatio || 1;

    canvas.width =
        Math.max(
            1,
            Math.floor(
                rect.width * dpr
            )
        );

    canvas.height =
        Math.max(
            1,
            Math.floor(
                rect.height * dpr
            )
        );

    const ctx =
        canvas.getContext(
            "2d"
        );

    ctx.scale(
        dpr,
        dpr
    );

    const w =
        rect.width;

    const h =
        rect.height;

    ctx.clearRect(
        0,
        0,
        w,
        h
    );

    ctx.strokeStyle =
        "#1d4d35";

    ctx.beginPath();

    ctx.moveTo(
        0,
        h / 2
    );

    ctx.lineTo(
        w,
        h / 2
    );

    ctx.stroke();

    const amplitude =
        Math.max(
            0,
            Math.min(
                1,
                voiceAmplitude
            )
        );

    ctx.strokeStyle =
        "#5cff9f";

    ctx.beginPath();

    for (
        let x = 0;
        x < w;
        x += 3
    ) {{

        const phase =
            x * 0.085 +
            performance.now() * 0.004;

        const y =
            h / 2 +
            Math.sin(phase) *
            amplitude *
            h *
            0.38;

        if (x === 0)
            ctx.moveTo(x, y);
        else
            ctx.lineTo(x, y);
    }}

    ctx.stroke();

    requestAnimationFrame(
        drawWaveform
    );
}}


// ==========================================================
// DOT MATRIX
// ==========================================================

function normalizePoints(matrix) {{

    if (!Array.isArray(matrix))
        return [];

    const points = [];

    matrix.forEach(
        (item, index) => {{

            if (
                Array.isArray(item) &&
                item.length >= 2 &&
                typeof item[0] === "number"
            ) {{

                points.push({{
                    x: Number(item[0]),
                    y: Number(item[1]),
                    z: Number(item[2] || 0),
                    value:
                        item.length > 3
                        ? Number(item[3])
                        : 1
                }});

                return;
            }}

            if (
                item &&
                typeof item === "object" &&
                !Array.isArray(item)
            ) {{

                points.push({{
                    x: Number(item.x || 0),
                    y: Number(item.y || 0),
                    z: Number(item.z || 0),
                    value:
                        Number(
                            item.value ??
                            item.intensity ??
                            1
                        )
                }});

                return;
            }}

            if (Array.isArray(item)) {{

                item.forEach(
                    (value, x) => {{

                        if (Number(value)) {{

                            points.push({{
                                x: x,
                                y: index,
                                z: 0,
                                value:
                                    Number(value)
                            }});
                        }}
                    }}
                );
            }}
        }}
    );

    return points;
}}


function drawMatrix(matrix) {{

    const canvas =
        document.getElementById(
            "matrix"
        );

    const label =
        document.getElementById(
            "matrix-label"
        );

    const rect =
        canvas.getBoundingClientRect();

    const dpr =
        window.devicePixelRatio || 1;

    canvas.width =
        Math.max(
            1,
            Math.floor(
                rect.width * dpr
            )
        );

    canvas.height =
        Math.max(
            1,
            Math.floor(
                rect.height * dpr
            )
        );

    const ctx =
        canvas.getContext(
            "2d"
        );

    ctx.scale(
        dpr,
        dpr
    );

    const w =
        rect.width;

    const h =
        rect.height;

    ctx.clearRect(
        0,
        0,
        w,
        h
    );

    const points =
        normalizePoints(
            matrix
        );

    if (!points.length) {{

        label.textContent =
            "waiting for dot_matrix_3d";

        ctx.fillStyle =
            "#153826";

        ctx.font =
            "14px Consolas";

        ctx.fillText(
            "SEED MATRIX IDLE",
            18,
            28
        );

        return;
    }}

    label.textContent =
        `${{points.length}} matrix points`;

    const xs =
        points.map(p => p.x);

    const ys =
        points.map(p => p.y);

    const minX =
        Math.min(...xs);

    const maxX =
        Math.max(...xs);

    const minY =
        Math.min(...ys);

    const maxY =
        Math.max(...ys);

    const spanX =
        Math.max(
            1,
            maxX - minX
        );

    const spanY =
        Math.max(
            1,
            maxY - minY
        );

    points.forEach(
        point => {{

            const px =
                18 +
                (
                    (point.x - minX) /
                    spanX
                ) *
                (w - 36);

            const py =
                18 +
                (
                    (point.y - minY) /
                    spanY
                ) *
                (h - 36);

            const depth =
                Math.max(
                    -1,
                    Math.min(
                        1,
                        Number(point.z || 0)
                    )
                );

            const radius =
                2.2 +
                Math.abs(depth) *
                2.5;

            ctx.beginPath();

            ctx.arc(
                px,
                py,
                radius,
                0,
                Math.PI * 2
            );

            ctx.fillStyle =
                "#59ff9f";

            ctx.globalAlpha =
                Math.max(
                    0.18,
                    Math.min(
                        1,
                        Number(
                            point.value || 1
                        )
                    )
                );

            ctx.fill();

            ctx.globalAlpha =
                1;
        }}
    );
}}


// ==========================================================
// COMPLETE STATE
// ==========================================================

function renderState(data) {{

    renderSystems(
        data.systems
    );

    renderIdentity(
        data.qbit
    );

    renderCommandPath(
        data.command_path
    );

    renderCommands(
        data.commands
    );

    renderOutput(
        data.seed_output
    );

    renderAudio(
        data.audio
    );

    drawMatrix(
        data.dot_matrix_3d
    );
}}


// ==========================================================
// START
// ==========================================================

connect();

drawWaveform();

window.addEventListener(
    "resize",
    () => {{

        if (state)
            drawMatrix(
                state.dot_matrix_3d
            );
    }}
);

</script>

</body>
</html>
"""


    # ==========================================================
    # CLOSE
    # ==========================================================

    def close(
        self,
    ):

        if self._closed:
            return True

        self._closed = True

        # --------------------------------------------------
        # HTTP
        # --------------------------------------------------

        server = self._http_server

        if server is not None:

            try:
                server.shutdown()
            except Exception:
                pass

            try:
                server.server_close()
            except Exception:
                pass

        self._http_server = None
        self._http_started = False

        # --------------------------------------------------
        # WEBSOCKET
        # --------------------------------------------------

        ws_server = self._ws_server

        if (
            ws_server is not None
            and
            self._ws_loop is not None
        ):

            def shutdown_ws():

                try:

                    ws_server.close()

                except Exception:
                    pass

            try:

                self._ws_loop.call_soon_threadsafe(
                    shutdown_ws
                )

            except Exception:
                pass

        self._ws_running = False
        self._ws_started = False

        # --------------------------------------------------
        # CLIENTS
        # --------------------------------------------------

        self._clients.clear()

        self.logger.info(
            "[FATHUD] HALO adapter closed"
        )

        return True


# ==========================================================
# EXPORTS
# ==========================================================

__all__ = [
    "FATHUDAdapter",
]