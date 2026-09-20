# ==========================================================
# FILE: main3.py
# PATH: C:\SEED_ROOT\main3.py
# VERSION: 6.0.0
#
# SEED AI OS â€” AUTHORITATIVE BOOT INTEGRATION
#
# BUILD:
#   FULL REBUILD / BOOT STABILIZATION
#
# ARCHITECTURE:
#   EventBus       = transport
#   Qbit           = cognitive carrier
#   QbitDialer     = brain / command authority
#   Heartbeat      = heart / system clock
#   KernelBus      = kernel transport
#   QueueLoop      = temporal processing loop
#   TrackSystem    = channel/track authority
#   SEEDCore       = system core
#   Relay          = guarded execution relay
#   TimeTravel     = temporal memory/replay
#   Oracle         = reporting/observer layer
#   DEVHUD         = optional observer/UI
#
# IMPORTANT:
#   This file owns ONE authoritative boot path.
#   Components are initialized once.
#
# ==========================================================


# ==========================================================
# SECTION 01 â€” STANDARD LIBRARY / BASE ENVIRONMENT
# ==========================================================

from __future__ import annotations

import argparse
import asyncio
import cmath
import atexit
import inspect
import json
import logging
import os
import platform
import queue
import signal
import sys
import threading
import time
import traceback
import tracemalloc
import uuid

from collections import defaultdict
from enum import Enum
from pathlib import Path
from queue import Queue
from typing import Any, Callable, Optional


# ==========================================================
# SECTION 02 â€” ROOT / PATHS / METADATA
# ==========================================================

SEED_ROOT = Path(r"C:\SEED_ROOT")
STORAGE_ROOT = SEED_ROOT / "storage"

IDENTITY_FILENAME = "seed_identity.json"
IDENTITY_PATH = SEED_ROOT / IDENTITY_FILENAME

VERSION = "6.0.0"
BUILD = "FULL-MERGE / AUTHORITATIVE-QBIT / SINGLE-RUNTIME / MAIN3"
BOOT_AUTHORITY = "main3.py"
BACKUP_ROOT = r"G:\SEED_BACKUPS"
BACKUP_INTERVAL_SEC = 24 * 60 * 60

SEED_ROOT.mkdir(parents=True, exist_ok=True)
STORAGE_ROOT.mkdir(parents=True, exist_ok=True)

if str(SEED_ROOT) not in sys.path:
    sys.path.insert(0, str(SEED_ROOT))

# Oracle observes the authoritative Main3 module directly.
# It must never alias Main3 over the real seed_init_full module.
def gen_track_id(prefix="Main"):
    return f"{prefix}-{str(uuid.uuid4())[:8]}"

# ==========================================================
# SECTION 03 â€” BOOT METADATA
# ==========================================================

BOOT_METADATA = {
    "system": "SEED AI OS",
    "launcher": "main3.py",
    "version": VERSION,
    "build": BUILD,
    "authority": BOOT_AUTHORITY,
    "root": str(SEED_ROOT),
    "architecture": {
        "transport": "SEEDEventBus",
        "brain": "QbitDialer",
        "cognitive_carrier": "Qbit",
        "heartbeat": "HeartbeatEmitter",
        "kernel_transport": "QbitKernelBus",
        "queue": "QbitQueueLoop",
        "tracks": "TrackSystem",
        "core": "SEEDCore",
        "relay": "SEEDRelay",
        "time_travel": "TimeTravelEngine",
        "observer": "Oracle",
        "ui": "DEVHUD",
        "legacy_services": ["SEEDMemoryManager", "QbitActionController", "SEEDAnalyticsEngine", "SEEDAdaptiveEngine", "SysOS", "AdimManager", "HUDReader", "SRegistry"],
    },
    "boot_policy": {
        "single_event_bus": True,
        "single_qbit_dialer": True,
        "single_queue_loop": True,
        "single_heartbeat": True,
        "ui_last": True,
        "ui_optional": True,
        "tk_main_thread_only": True,
        "no_background_tk": True,
        "qbit_dialer_single_start": True,
        "backup_root": BACKUP_ROOT,
        "backup_interval_sec": BACKUP_INTERVAL_SEC,
    },
}

# ==========================================================
# SECTION 04 â€” LOGGING
# ==========================================================

logger = logging.getLogger("SEED_Main")


# ----------------------------------------------------------
# WINDOWS / UTF-8 SAFE STREAM HANDLER
# ----------------------------------------------------------

def _configure_log_stream(handler):

    try:

        stream = getattr(
            handler,
            "stream",
            None,
        )

        if stream is not None and hasattr(
            stream,
            "reconfigure",
        ):

            stream.reconfigure(
                encoding="utf-8",
                errors="backslashreplace",
            )

    except Exception:
        # Never allow logging configuration to break boot.
        pass

    return handler


# ----------------------------------------------------------
# CREATE HANDLER ONCE
# ----------------------------------------------------------

if not logger.handlers:

    handler = logging.StreamHandler()

    # Windows console encoding protection
    _configure_log_stream(handler)

    formatter = logging.Formatter(
        "[%(levelname)s] %(asctime)s | SEEDMain | %(message)s"
    )

    handler.setFormatter(formatter)

    logger.addHandler(handler)


# ----------------------------------------------------------
# LOGGER LEVEL
# ----------------------------------------------------------

logger.setLevel(logging.INFO)

# Prevent accidental propagation into another handler that
# may still be using cp1252.
logger.propagate = False


# ==========================================================
# SAFE BOOT LOGGER
# ==========================================================
#
# Windows consoles may still expose cp1252 even when Python
# itself is running UTF-8. Boot logging must NEVER be allowed
# to crash the boot sequence because a log message contains
# Unicode.
#
# ==========================================================

def boot_log(
    message,
    level="info",
):

    try:

        text = str(message)

    except Exception:

        text = repr(message)

    # ------------------------------------------------------
    # Determine logger
    # ------------------------------------------------------

    try:

        target_logger = logger

    except NameError:

        target_logger = logging.getLogger(
            "SEEDMain"
        )

    # ------------------------------------------------------
    # Emit through the normal logging system.
    #
    # Do NOT let logging failure stop boot.
    # ------------------------------------------------------

    try:

        log_method = getattr(
            target_logger,
            str(level).lower(),
            target_logger.info,
        )

        log_method(text)

        return True

    except UnicodeEncodeError:

        # --------------------------------------------------
        # Console encoding failure.
        #
        # Preserve the meaning of the message while making
        # it safe for cp1252.
        # --------------------------------------------------

        try:

            safe_text = (
                text.encode(
                    "ascii",
                    errors="backslashreplace",
                )
                .decode(
                    "ascii",
                    errors="replace",
                )
            )

        except Exception:

            safe_text = repr(text)

        try:

            log_method(safe_text)

            return True

        except Exception:

            pass

    except Exception:

        # --------------------------------------------------
        # Logging must never become a boot dependency.
        # --------------------------------------------------

        try:

            safe_text = (
                text.encode(
                    "ascii",
                    errors="backslashreplace",
                )
                .decode(
                    "ascii",
                    errors="replace",
                )
            )

            log_method(safe_text)

            return True

        except Exception:

            pass

    return False

def boot_warn(message: str):
    print(f"[BOOT WARN] {message}")
    logger.warning(message)


def boot_error(message: str):
    print(f"[BOOT ERROR] {message}")
    logger.error(message)


# ==========================================================
# SECTION 05 â€” GLOBAL RUNTIME STATE
# ==========================================================

BOOT_STATE: dict[str, Any] = {}

MODULES_STATUS: dict[str, bool] = {}

GREEN_FLAGS = []
green_flags_count = 0

qbit_command_count = 0
MAX_QBIT_COMMANDS = 10000

# ----------------------------------------------------------
# AUTHORITATIVE REGISTRY STATE
# ----------------------------------------------------------
#
# SRegistry answers:
#     WHAT EXISTS?
#
# registry_runtime answers:
#     WHAT STATE IS IT IN?
#
# These must remain LIVE authoritative objects.
# Do NOT replace either with copied dictionaries.
#
registry = None
system_registry = None
registry_runtime = None

# ----------------------------------------------------------
# AUTHORITATIVE NODE REGISTRY
# ----------------------------------------------------------
#
# main3 must receive the existing SRegistry/node registry.
# It must NEVER construct a competing NodeRegistry.
#
node_registry = None
authoritative_nodes = None
nodes = None

# ----------------------------------------------------------
# COGNITION / BRAIN REFERENCES
# ----------------------------------------------------------

neural_bridge = None
computebrain = None
transformerbrain = None

# Canonical aliases used by newer modules.
compute_brain = None
transformer_brain = None

POST_TOP_MODULES = [
    "SEEDEventBus",
    "Qbit",
    "QbitQueueLoop",
    "QbitDialer",
    "HeartbeatEmitter",
    "TrackSystem",
    "SEEDCore",
    "TimeTravelEngine",
    "SEEDMemoryManager",
    "QbitActionController",
    "SEEDAnalyticsEngine",
    "SEEDAdaptiveEngine",
]

ui_queue: Queue = Queue()

shutdown_event = threading.Event()
async_shutdown_event: Optional[asyncio.Event] = None

# ----------------------------------------------------------
# SINGLE PRIMARY RUNTIME LEASE
# ----------------------------------------------------------
# A process must claim the local runtime before any SEED
# authority is constructed. This is the local safety gate for
# duplicate Windows startup/launcher paths. It is deliberately
# non-destructive: a second process exits cleanly and never
# starts a second Qbit/Dialer/QueueLoop.
RUNTIME_ID = None
BOOT_SESSION_ID = None
DEVICE_ID = None
PRIMARY_RUNTIME_LEASE_PATH = SEED_ROOT / "runtime" / "primary_runtime.json"
PRIMARY_RUNTIME_LEASE_TTL = 30.0
_PRIMARY_RUNTIME_HELD = False


def claim_primary_runtime(storage_root=None):
    global RUNTIME_ID, BOOT_SESSION_ID, DEVICE_ID, _PRIMARY_RUNTIME_HELD

    if _PRIMARY_RUNTIME_HELD:
        return True

    root_path = Path(storage_root or SEED_ROOT)
    lease_path = root_path / "runtime" / "primary_runtime.json"
    lease_path.parent.mkdir(parents=True, exist_ok=True)

    identity = {}
    try:
        identity = ensure_seed_identity(root_path) or {}
    except Exception:
        identity = {}

    device_id = None
    try:
        connection_path = root_path / "config" / "seed_connection.json"
        if connection_path.exists():
            connection = json.loads(connection_path.read_text(encoding="utf-8-sig"))
            device_id = connection.get("node_id")
    except Exception:
        device_id = None

    DEVICE_ID = str(device_id or identity.get("seed_id") or platform.node())
    RUNTIME_ID = f"SEED-RUNTIME-{uuid.uuid4().hex[:16]}"
    BOOT_SESSION_ID = str(uuid.uuid4())

    record = {
        "runtime_id": RUNTIME_ID,
        "boot_session_id": BOOT_SESSION_ID,
        "device_id": DEVICE_ID,
        "pid": os.getpid(),
        "started_at": time.time(),
        "expires_at": time.time() + PRIMARY_RUNTIME_LEASE_TTL,
        "state": "starting",
        "authority": "main3.py",
    }

    for attempt in range(2):
        try:
            fd = os.open(
                str(lease_path),
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
            )
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(record, handle, indent=2)
            _PRIMARY_RUNTIME_HELD = True
            BOOT_STATE.update({
                "runtime_id": RUNTIME_ID,
                "boot_session_id": BOOT_SESSION_ID,
                "device_id": DEVICE_ID,
            })
            boot_log(
                "PRIMARY RUNTIME CLAIMED | "
                f"runtime_id={RUNTIME_ID} | pid={os.getpid()}"
            )
            return True
        except FileExistsError:
            try:
                existing = json.loads(lease_path.read_text(encoding="utf-8"))
            except Exception:
                existing = {}

            existing_pid = existing.get("pid")
            existing_runtime = existing.get("runtime_id")
            alive = False
            authoritative_process = False
            if existing_pid:
                try:
                    import psutil
                    process = psutil.Process(int(existing_pid))
                    alive = process.is_running()
                    cmdline = " ".join(process.cmdline()).lower()
                    authoritative_process = "main3.py" in cmdline
                except Exception:
                    alive = int(existing_pid) == os.getpid()
                    authoritative_process = alive

            # PID reuse is possible on Windows. A reused PID is not an
            # authoritative SEED runtime unless its command line is actually
            # main3.py. This prevents a stale SEED lease from blocking boot
            # because an unrelated Python process inherited the old PID.
            if alive and authoritative_process and int(existing_pid) != os.getpid():
                boot_warn(
                    "PRIMARY RUNTIME BUSY | "
                    f"runtime_id={existing_runtime} | pid={existing_pid} | "
                    "secondary runtime will not start"
                )
                return False

            # Stale lease: the previous process is gone. Recover by
            # removing only the stale lease record, never another runtime.
            try:
                lease_path.unlink()
            except Exception:
                return False

    return False


def heartbeat_primary_runtime():
    if not _PRIMARY_RUNTIME_HELD or not RUNTIME_ID:
        return False
    try:
        path = PRIMARY_RUNTIME_LEASE_PATH
        if not path.exists():
            return False
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("runtime_id") != RUNTIME_ID or int(record.get("pid", -1)) != os.getpid():
            return False
        record["expires_at"] = time.time() + PRIMARY_RUNTIME_LEASE_TTL
        record["state"] = "online"
        record["heartbeat_at"] = time.time()
        path.write_text(json.dumps(record, indent=2), encoding="utf-8")
        return True
    except Exception:
        return False


def release_primary_runtime():
    global _PRIMARY_RUNTIME_HELD
    if not _PRIMARY_RUNTIME_HELD or not RUNTIME_ID:
        return
    try:
        path = PRIMARY_RUNTIME_LEASE_PATH
        if path.exists():
            record = json.loads(path.read_text(encoding="utf-8"))
            if record.get("runtime_id") == RUNTIME_ID and int(record.get("pid", -1)) == os.getpid():
                path.unlink()
    except Exception:
        pass
    finally:
        _PRIMARY_RUNTIME_HELD = False


atexit.register(release_primary_runtime)

root = None
parent = None
hud = None
hud_facade = None
hud_state = None
dev_hud = None
ui_enabled = False
ui_tick = 0

# ----------------------------------------------------------
# CORE AUTHORITIES
# ----------------------------------------------------------

event_bus = None
database = None

qbit = None
qbit_core = None

qbit_queue = None
queue_loop = None

qbit_dialer = None
heartbeat = None

kernel_bus = None
qbit_start_task = None

# ----------------------------------------------------------
# TRACK SYSTEM
# ----------------------------------------------------------

track_system = None
track_context = None

# ----------------------------------------------------------
# CORE SUBSYSTEMS
# ----------------------------------------------------------

fiveg = None
seed_network = None
seed_network_core = None
network_manager = None
health_monitor = None
action_engine = None
module_registry = None
agent_manager = None
intent_engine = None
orchestrator = None
orchestrator_command = None

memory_crystallizer = None
camera_qbit = None
render_engine = None
decoder = None
qbit_encoder = None
qbit_compiler = None
compute_brain = None
transformer_brain = None

# ----------------------------------------------------------
# COGNITION SUBSYSTEM REFERENCES
# ----------------------------------------------------------

cognitive_clock = None
cognitive_scheduler = None
goal_engine = None
cognition_node = None
cognition_binary_encoder = None
cognition_load_balancer = None
cognition_neural_bridge = None

guardian = None
ethics_manager = None

# ----------------------------------------------------------
# RELAY
# ----------------------------------------------------------

relay = None
relay_mission_bridge = None

# ----------------------------------------------------------
# TIME TRAVEL
# ----------------------------------------------------------

time_travel_engine = None

# ----------------------------------------------------------
# ORACLE
# ----------------------------------------------------------

oracle = None
ORACLE = None
oracle_loop = None
init_event = None

# ----------------------------------------------------------
# DEVICE
# ----------------------------------------------------------

device = None
device_manager = None

# ----------------------------------------------------------
# IPC / CONTROL
# ----------------------------------------------------------

os_control_manager = None
screen_tracker = None

cm = None
controller = None
ipc_bridge = None
blackbox = None
cli = None

# ----------------------------------------------------------
# CORE REFERENCES
# ----------------------------------------------------------

seedcore = None
core = None

loop = None

# ----------------------------------------------------------
# FULL-MERGE RUNTIME SERVICES
# ----------------------------------------------------------

memory_manager = None
seed_scheduler = None
analytics_engine = None
adaptive_engine = None
adaptive_priority_engine = None
growth_tree = None
seedos = None
adim_manager = None
hud_reader = None
seed_voice_system = None

qbit_task = None
qbit_start_task = None
kernel_start_task = None

adaptive_thread = None

# ----------------------------------------------------------
# FATHUD
# ----------------------------------------------------------

fathud = None


# ==========================================================
# REGISTRY-RUNTIME / NODE DISCOVERY HELPERS
# ==========================================================

def _resolve_live_registry_runtime():
    global registry_runtime

    if registry_runtime is not None:
        return registry_runtime

    try:
        import SRegistry.registry.registry_runtime as runtime_module

        registry_runtime = runtime_module

        return registry_runtime

    except Exception:
        pass

    try:
        from SRegistry import registry_runtime as runtime_module

        registry_runtime = runtime_module

        return registry_runtime

    except Exception as exc:
        boot_warn(
            "registry_runtime unavailable | "
            f"{type(exc).__name__}: {exc}"
        )

        registry_runtime = None

        return None


def _resolve_authoritative_node_registry():

    global node_registry
    global authoritative_nodes
    global nodes

    # ------------------------------------------------------
    # Already bound in main3
    # ------------------------------------------------------

    for candidate in (
        authoritative_nodes,
        node_registry,
        nodes,
    ):
        if candidate is not None:
            if isinstance(candidate, dict):
                continue
            if not any(
                callable_attr(candidate, method_name) is not None
                for method_name in (
                    "refresh",
                    "refresh_nodes",
                    "refresh_status",
                    "get_status",
                )
            ):
                continue
            authoritative_nodes = candidate
            node_registry = candidate
            nodes = candidate
            return candidate

    # ------------------------------------------------------
    # SRegistry package-level node registry
    # ------------------------------------------------------

    try:
        import SRegistry

        for name in (
            "node_registry",
            "authoritative_nodes",
            "nodes",
            "NODE_REGISTRY",
            "NODE_REGISTRY_INSTANCE",
        ):
            candidate = getattr(SRegistry, name, None)

            if candidate is not None and any(
                callable_attr(candidate, method_name) is not None
                for method_name in (
                    "refresh_nodes",
                    "get_status",
                    "refresh",
                )
            ):
                authoritative_nodes = candidate
                node_registry = candidate
                nodes = candidate

                return candidate

    except Exception:
        pass

    # ------------------------------------------------------
    # registry_runtime live provider
    # ------------------------------------------------------

    runtime = _resolve_live_registry_runtime()

    if runtime is not None:

        provider_names = (
            "node_registry",
            "nodes",
            "runtime_nodes",
            "authoritative_nodes",
            "NodeRegistry",
        )

        for provider_name in provider_names:

            try:
                getter = getattr(
                    runtime,
                    "get_dependency_provider",
                    None,
                )

                if callable(getter):

                    provider = getter(
                        provider_name,
                        include_reference=True,
                    )

                    if isinstance(provider, dict):

                        candidate = provider.get("_ref")

                        if candidate is None:
                            candidate = provider.get(
                                "reference"
                            )

                        if candidate is not None and any(
                            callable_attr(candidate, method_name) is not None
                            for method_name in (
                                "refresh_nodes",
                                "get_status",
                                "refresh",
                            )
                        ):

                            authoritative_nodes = candidate
                            node_registry = candidate
                            nodes = candidate

                            return candidate

            except Exception:
                continue

    # ------------------------------------------------------
    # Construct the single Node Registry Bridge only when
    # the authoritative SRegistry + registry_runtime exist.
    # SRegistry remains the discovery authority; this object
    # is only the neural/node bridge and never a replacement.
    # ------------------------------------------------------

    if runtime is not None:
        try:
            import SRegistry
            from seed.core.neural.node_registry import Node_Registry
            authoritative_registry = SRegistry

            candidate = Node_Registry(
                registry=authoritative_registry,
                registry_runtime=runtime,
                qbit_queue_loop=globals().get("queue_loop"),
                event_bus=globals().get("event_bus"),
                track_system=globals().get("track_system"),
                neural_bridge=globals().get("neural_bridge"),
                compute_brain=globals().get("computebrain") or globals().get("compute_brain"),
                transformer_brain=globals().get("transformerbrain") or globals().get("transformer_brain"),
                qbit_dialer=globals().get("qbit_dialer"),
                fathud=globals().get("fathud"),
            )

            authoritative_nodes = candidate
            node_registry = candidate
            nodes = candidate

            boot_log(
                "Node Registry Bridge constructed from authoritative SRegistry/runtime"
            )
            return candidate

        except Exception as exc:
            boot_warn(
                "Node Registry Bridge construction failed | "
                f"{type(exc).__name__}: {exc}"
            )

    # ------------------------------------------------------
    # SRegistry registry object
    # ------------------------------------------------------

    if registry is not None:

        for name in (
            "node_registry",
            "nodes",
            "authoritative_nodes",
        ):

            try:
                candidate = getattr(
                    registry,
                    name,
                    None,
                )

                if candidate is not None:

                    authoritative_nodes = candidate
                    node_registry = candidate
                    nodes = candidate

                    return candidate

            except Exception:
                continue

    return None


def _publish_registry_runtime_provider(
    name,
    ref,
    state="AVAILABLE",
    capabilities=None,
):

    runtime = _resolve_live_registry_runtime()

    if runtime is None or ref is None:
        return False

    register = callable_attr(
        runtime,
        "register_dependency_provider",
    )

    if register is None:
        return False

    try:
        register(
            name,
            ref=ref,
            state=state,
            capabilities=capabilities or [],
            authoritative=True,
            source="main3",
        )

        return True

    except TypeError:

        try:
            register(
                name,
                ref=ref,
                state=state,
            )

            return True

        except Exception as exc:
            boot_warn(
                f"registry_runtime provider registration failed | "
                f"name={name} | "
                f"{type(exc).__name__}: {exc}"
            )

            return False

    except Exception as exc:

        boot_warn(
            f"registry_runtime provider registration failed | "
            f"name={name} | "
            f"{type(exc).__name__}: {exc}"
        )

        return False


def _register_main3_node(
    name,
    path=None,
    role="runtime",
    group="seed",
    capabilities=None,
):

    reg = registry

    if reg is None:
        try:
            import SRegistry
            reg = SRegistry
        except Exception:
            reg = None

    register = callable_attr(
        reg,
        "register_node",
    )

    if register is None:
        return False

    if path is None:
        path = name

    try:
        register(
            name=name,
            path=path,
            group=group,
            role=role,
            state="ONLINE",
            capabilities=capabilities or [],
            metadata={
                "source": "main3",
                "authoritative": True,
            },
        )

        return True

    except TypeError:

        try:
            register(
                name,
                path,
                group=group,
                role=role,
                state="ONLINE",
            )

            return True

        except Exception as exc:
            boot_warn(
                f"SRegistry node registration failed | "
                f"name={name} | "
                f"{type(exc).__name__}: {exc}"
            )

            return False

    except Exception as exc:

        boot_warn(
            f"SRegistry node registration failed | "
            f"name={name} | "
            f"{type(exc).__name__}: {exc}"
        )

        return False


def _bind_authoritative_runtime_nodes():

    global node_registry
    global authoritative_nodes
    global nodes

    resolved = _resolve_authoritative_node_registry()

    if resolved is None:

        MODULES_STATUS["node_registry"] = False
        MODULES_STATUS["runtime_nodes"] = False

        boot_warn(
            "Authoritative Runtime NodeRegistry unavailable"
        )

        return None

    # All aliases MUST point to the same live object.
    authoritative_nodes = resolved
    node_registry = resolved
    nodes = resolved

    MODULES_STATUS["node_registry"] = True
    MODULES_STATUS["runtime_nodes"] = True

    _publish_registry_runtime_provider(
        "node_registry",
        resolved,
        state="AVAILABLE",
        capabilities=[
            "NODE_DISCOVERY",
            "NODE_STATUS",
            "MODULE_STATUS",
            "RUNTIME_REFRESH",
        ],
    )

    _publish_registry_runtime_provider(
        "runtime_nodes",
        resolved,
        state="AVAILABLE",
        capabilities=[
            "NODE_DISCOVERY",
            "NODE_STATUS",
            "MODULE_STATUS",
            "RUNTIME_REFRESH",
        ],
    )

    boot_log(
        "Authoritative Runtime NodeRegistry ONLINE | "
        f"type={type(resolved).__name__}"
    )

    return resolved


def _refresh_authoritative_node_status():

    runtime_nodes = _bind_authoritative_runtime_nodes()

    if runtime_nodes is None:
        return False

    refresh_methods = (
        "refresh_status",
        "refresh_node_status",
        "refresh_nodes",
        "update_status",
        "sync_status",
    )

    for method_name in refresh_methods:

        try:
            method = getattr(
                runtime_nodes,
                method_name,
                None,
            )
        except Exception:
            method = None

        if not callable(method):
            continue

        try:
            result = method()

            if inspect.isawaitable(result):

                try:
                    running_loop = asyncio.get_running_loop()

                except RuntimeError:
                    running_loop = None

                if running_loop is not None:
                    running_loop.create_task(result)
                else:
                    try:
                        result.close()
                    except Exception:
                        pass

            MODULES_STATUS[
                "runtime_node_status"
            ] = True

            boot_log(
                "Runtime node status refresh ONLINE | "
                f"api={method_name}"
            )

            return True

        except TypeError:
            continue

        except Exception as exc:

            boot_warn(
                f"Runtime node status refresh failed | "
                f"api={method_name} | "
                f"{type(exc).__name__}: {exc}"
            )

            continue

    MODULES_STATUS[
        "runtime_node_status"
    ] = False

    boot_warn(
        "Runtime node status refresh API unavailable | "
        "authoritative nodes retained"
    )

    return False


def boot_registry_runtime():

    global registry_runtime

    runtime = _resolve_live_registry_runtime()

    if runtime is None:

        MODULES_STATUS[
            "registry_runtime"
        ] = False

        return None

    registry_runtime = runtime

    MODULES_STATUS[
        "registry_runtime"
    ] = True

    # ------------------------------------------------------
    # Register the LIVE runtime provider with itself when
    # supported.
    # ------------------------------------------------------

    _publish_registry_runtime_provider(
        "registry_runtime",
        runtime,
        state="AVAILABLE",
        capabilities=[
            "RUNTIME_STATE",
            "DEPENDENCY_REGISTRY",
            "LIFECYCLE_STATE",
            "NODE_STATE",
        ],
    )

    # ------------------------------------------------------
    # Keep compatibility with system_registry if that legacy
    # structure exists, but store the LIVE object.
    # ------------------------------------------------------

    if system_registry is not None:

        try:
            system_registry.setdefault(
                "dependencies",
                {},
            )

            system_registry[
                "dependencies"
            ].setdefault(
                "providers",
                {},
            )

            system_registry[
                "dependencies"
            ]["providers"][
                "registry_runtime"
            ] = {
                "object": runtime,
                "state": "AVAILABLE",
                "authority": "SRegistry",
                "authoritative": True,
            }

        except Exception as exc:

            boot_warn(
                "Legacy system_registry runtime mirror failed | "
                f"{type(exc).__name__}: {exc}"
            )

    boot_log(
        "registry_runtime ONLINE | "
        f"type={type(runtime).__name__}"
    )

    # ------------------------------------------------------
    # Immediately attempt the node binding.
    # ------------------------------------------------------

    _bind_authoritative_runtime_nodes()

    return registry_runtime


# ==========================================================
# SECTION 06 â€” COMPATIBILITY HELPERS
# ==========================================================

def callable_attr(obj, name):
    if obj is None:
        return None

    try:
        value = getattr(obj, name, None)
    except Exception:
        return None

    return value if callable(value) else None


def discover_callable_methods(obj):
    if obj is None:
        return []

    names = []

    try:
        for name in dir(obj):

            if name.startswith("_"):
                continue

            try:
                value = getattr(
                    obj,
                    name,
                    None,
                )

                if callable(value):
                    names.append(name)

            except Exception:
                continue

    except Exception:
        pass

    return sorted(set(names))


def inspect_constructor(cls):
    try:
        return str(
            inspect.signature(cls)
        )

    except Exception:

        try:
            return str(
                inspect.signature(
                    cls.__init__
                )
            )

        except Exception:
            return "<signature unavailable>"


def safe_call(
    func: Optional[Callable],
    *args,
    default=None,
    label="operation",
    **kwargs,
):
    if not callable(func):
        return default

    try:
        result = func(
            *args,
            **kwargs,
        )

        return result

    except Exception as exc:

        boot_warn(
            f"{label} failed | "
            f"{type(exc).__name__}: {exc}"
        )

        return default


def filter_constructor_kwargs(cls, kwargs):
    # Keep only keywords accepted by the active constructor revision.

    if cls is None:
        return {}

    try:
        signature = inspect.signature(cls)

    except Exception:

        try:
            signature = inspect.signature(
                cls.__init__
            )

        except Exception:
            return dict(kwargs)

    parameters = signature.parameters

    if any(
        p.kind == inspect.Parameter.VAR_KEYWORD
        for p in parameters.values()
    ):
        return dict(kwargs)

    return {
        key: value
        for key, value in kwargs.items()
        if key in parameters
    }


def compatible_construct(
    cls,
    attempts,
    label,
    default=None,
):

    if cls is None:

        boot_warn(
            f"{label}: class unavailable"
        )

        return default

    last_error = None

    for args, kwargs in attempts:

        try:

            obj = cls(
                *args,
                **kwargs,
            )

            boot_log(
                f"{label} initialized | "
                f"type={type(obj).__name__}"
            )

            return obj

        except Exception as exc:

            last_error = exc

            boot_warn(
                f"{label} constructor attempt failed | "
                f"args={args} | "
                f"kwargs={list(kwargs.keys())} | "
                f"{type(exc).__name__}: {exc}"
            )

    if last_error is not None:

        boot_warn(
            f"{label} constructor compatibility exhausted | "
            f"{type(last_error).__name__}: {last_error}"
        )

    return default


# ==========================================================
# AUTHORITATIVE QBIT BINDING
# ==========================================================

#authoritative_qbit = qbit

#if authoritative_qbit is None:
#    raise RuntimeError(
#        "SEED runtime has no authoritative Qbit"
#    )

# QbitDialer must use the exact Qbit created by main3.py.
#dialer.qbit = authoritative_qbit

#if dialer.qbit is not authoritative_qbit:
#    raise RuntimeError(
#        "QbitDialer received non-authoritative Qbit"
#    )

#logger.info(
#    "[QbitDialer] Authoritative Qbit verified | qbit=%s",
#    authoritative_qbit
#)

# ==========================================================
# SECTION 07 â€” ERROR / TRACE UTILITIES
# ==========================================================

def trace_exception(exc):
    try:
        tb = exc.__traceback__

        if tb is None:
            logger.error(
                "[TRACE] %s: %s",
                type(exc).__name__,
                exc,
            )
            return

        while tb.tb_next:
            tb = tb.tb_next

        frame = tb.tb_frame
        lineno = tb.tb_lineno
        filename = frame.f_code.co_filename
        func_name = frame.f_code.co_name

        line_text = "<Could not read source line>"

        try:
            with open(
                filename,
                "r",
                encoding="utf-8",
            ) as source:
                lines = source.readlines()

            if 0 < lineno <= len(lines):
                line_text = lines[lineno - 1].strip()

        except Exception:
            pass

        logger.error(
            "[TRACE] Exception in file '%s', "
            "function '%s', line %d:\n"
            "  %s\n"
            "  Exception: %s: %s",
            filename,
            func_name,
            lineno,
            line_text,
            type(exc).__name__,
            exc,
        )

    except Exception:
        logger.exception("[TRACE] Failed to trace exception")


# ==========================================================
# SECTION 08 â€” IDENTITY
# ==========================================================

def ensure_seed_identity(storage_root: str | Path):
    storage_root = Path(storage_root)
    storage_root.mkdir(parents=True, exist_ok=True)

    identity_path = storage_root / IDENTITY_FILENAME

    if not identity_path.exists():

        identity = {
            "seed_id": str(uuid.uuid4()),
            "created_at": time.time(),
            "owner": "Carlos A. Clarke",
            "permissions": {
                "qbit_access": True,
                "event_bus_access": True,
                "hud_access": True,
            },
            "metadata": {
                "version": VERSION,
                "build": BUILD,
            },
        }

        try:
            with open(
                identity_path,
                "w",
                encoding="utf-8",
            ) as file:
                json.dump(
                    identity,
                    file,
                    indent=4,
                )

            boot_log(
                f"Identity created | {identity_path}"
            )

        except Exception as exc:
            trace_exception(exc)

    else:
        boot_log(
            f"Identity found | {identity_path}"
        )

    try:
        with open(
            identity_path,
            "r",
            encoding="utf-8",
        ) as file:
            return json.load(file)

    except Exception as exc:
        trace_exception(exc)

        return {
            "seed_id": "UNKNOWN",
            "created_at": time.time(),
            "owner": "UNKNOWN",
            "permissions": {},
            "metadata": {},
        }


# ==========================================================
# SECTION 09 â€” TRACK / CHANNEL IDENTIFIERS
# ==========================================================

class ChannelID(Enum):
    MAIN = "main"
    HUD = "hud"
    SYSTEM = "system"
    QBIT = "qbit"
    HEARTBEAT = "heartbeat"


def gen_track_id(prefix="MAIN"):
    return {
        "track_id": f"{prefix}.{uuid.uuid4().hex[:8]}"
    }


def convert_channel_to_qbit_number(channel_name: str) -> int:
    return abs(hash(str(channel_name))) % 1_000_000


def convert_to_qbit_tuple(data):
    if data is None:
        return (1.0, 0.0, 0.0)

    if isinstance(data, list):
        data = tuple(data)

    elif not isinstance(data, tuple):
        try:
            data = (float(data), 0.0, 0.0)
        except Exception:
            return (1.0, 0.0, 0.0)

    if not data:
        return (1.0, 0.0, 0.0)

    try:
        if all(v == 0 for v in data):
            return (1.0, 0.0, 0.0)
    except Exception:
        return (1.0, 0.0, 0.0)

    return data


# ==========================================================
# SECTION 10 â€” QBIT STATE
# ==========================================================

def safe_qbit_state():
    alpha = cmath.sqrt(0.5)
    beta = cmath.sqrt(0.5)

    state = (
        complex(alpha, 0),
        complex(beta, 0),
    )

    norm = (
        abs(state[0]) ** 2
        + abs(state[1]) ** 2
    )

    if norm == 0.0:

        value = 1 / cmath.sqrt(2)

        state = (
            complex(value, 0),
            complex(value, 0),
        )

    else:

        norm_sqrt = norm ** 0.5

        state = (
            state[0] / norm_sqrt,
            state[1] / norm_sqrt,
        )

    return state


# ==========================================================
# SECTION 11 â€” SAFE EMISSION / EVENTBUS BRIDGE
# ==========================================================
#
# RULE:
#   event_bus  = authoritative SEEDEventBus INSTANCE
#   safe_emit  = compatibility callable that forwards to it
#
# NEVER pass safe_emit into a component that expects an
# EventBus object with .emit(), .subscribe(), etc.
#
# QbitDialer must receive:
#
#     event_bus=event_bus
#
# NOT:
#
#     event_bus=safe_emit
#
# ==========================================================


# ----------------------------------------------------------
# AUTHORITATIVE EVENTBUS REFERENCE
# ----------------------------------------------------------
#
# RULE:
#   SEEDEventBus is authoritative.
#   safe_emit is ONLY a compatibility/guard bridge.
#
# FLOW:
#
#       component
#           |
#           v
#       safe_emit
#           |
#           v
#       SEEDEventBus.emit()
#
# NEVER:
#
#       SEEDEventBus.emit()
#           |
#           v
#       safe_emit
#           |
#           v
#       SEEDEventBus.emit()
#
# ----------------------------------------------------------

event_bus = None




# ----------------------------------------------------------
# EVENTBUS / SAFE EMISSION AUTHORITY
# ----------------------------------------------------------
#
# RULES:
#
#   1. There is ONE authoritative EventBus.
#   2. safe_emit is ONLY a proxy.
#   3. safe_emit NEVER becomes the EventBus.
#   4. attach_event_bus() NEVER emits an event.
#   5. QbitDialer receives the authoritative EventBus instance.
#   6. EventBus identity is preserved.
#   7. No EventBus attachment recursion is permitted.
#
# Runtime:
#
#   EventBus
#       |
#       +----> safe_emit proxy
#       |
#       +----> QbitDialer
#       |
#       +----> TrackSystem
#       |
#       +----> SEEDCore
#
# ----------------------------------------------------------


# ----------------------------------------------------------
# AUTHORITATIVE EVENTBUS STORAGE
# ----------------------------------------------------------

event_bus = None


# ----------------------------------------------------------
# SAFE EVENT EMISSION PROXY
# ----------------------------------------------------------

class SafeEmitProxy:

    def __init__(self):
        self._event_bus = None

    def attach(self, bus):

        # --------------------------------------------------
        # Never allow the proxy to attach to itself.
        # --------------------------------------------------

        if bus is self:
            return False

        # --------------------------------------------------
        # Validate authoritative EventBus.
        # --------------------------------------------------

        if bus is None:
            return False

        emit_method = getattr(
            bus,
            "emit",
            None,
        )

        if not callable(emit_method):
            return False

        # --------------------------------------------------
        # Store the authoritative EventBus.
        #
        # IMPORTANT:
        # This operation performs NO emission.
        # --------------------------------------------------

        self._event_bus = bus

        return True

    def subscribe(self, *args, **kwargs):
        bus = self._event_bus
        method = getattr(bus, "subscribe", None) if bus is not None else None
        if not callable(method):
            return True
        return safe_call(method, *args, **kwargs, default=True, label="safe_emit.subscribe")

    def unsubscribe(self, *args, **kwargs):
        bus = self._event_bus
        method = getattr(bus, "unsubscribe", None) if bus is not None else None
        if not callable(method):
            return True
        return safe_call(method, *args, **kwargs, default=True, label="safe_emit.unsubscribe")

    def subscribe(self, *args, **kwargs):
        bus = self._event_bus
        method = getattr(bus, "subscribe", None) if bus is not None else None
        if not callable(method): return True
        return safe_call(method, *args, **kwargs, default=True, label="safe_emit.subscribe")

    def unsubscribe(self, *args, **kwargs):
        bus = self._event_bus
        method = getattr(bus, "unsubscribe", None) if bus is not None else None
        if not callable(method): return True
        return safe_call(method, *args, **kwargs, default=True, label="safe_emit.unsubscribe")

    def detach(self):

        self._event_bus = None

    @property
    def event_bus(self):

        return self._event_bus

    def __call__(
        self,
        event_name,
        payload=None,
    ):

        bus = self._event_bus

        # --------------------------------------------------
        # EventBus not ready.
        #
        # Safe no-op during early boot.
        # --------------------------------------------------

        if bus is None:
            return True

        # --------------------------------------------------
        # Hard recursion protection.
        #
        # safe_emit can never call itself.
        # --------------------------------------------------

        if bus is self:
            boot_warn(
                "[EventBus] Recursion guard blocked "
                "safe_emit -> safe_emit"
            )
            return True

        # --------------------------------------------------
        # Resolve authoritative emit().
        # --------------------------------------------------

        emit_method = getattr(
            bus,
            "emit",
            None,
        )

        if not callable(emit_method):
            return True

        # --------------------------------------------------
        # Call the REAL EventBus.emit().
        #
        # IMPORTANT:
        # safe_call must NOT route back through safe_emit.
        # --------------------------------------------------

        return safe_call(
            emit_method,
            event_name,
            payload,
            default=True,
            label=f"emit:{event_name}",
        )


# ----------------------------------------------------------
# AUTHORITATIVE SAFE EMITTER
# ----------------------------------------------------------

safe_emit = SafeEmitProxy()


# ----------------------------------------------------------
# EVENTBUS ATTACHMENT
# ----------------------------------------------------------

def attach_event_bus(bus):

    global event_bus

    # ------------------------------------------------------
    # Validate object
    # ------------------------------------------------------

    if bus is None:

        boot_warn(
            "[EventBus] Cannot attach None"
        )

        return None

    # ------------------------------------------------------
    # Never allow safe_emit itself to become authoritative.
    # ------------------------------------------------------

    if bus is safe_emit:

        boot_warn(
            "[EventBus] Refusing safe_emit as "
            "authoritative EventBus"
        )

        return None

    # ------------------------------------------------------
    # Recover a bound EventBus.emit method if somebody passed
    # the method instead of the EventBus object.
    # ------------------------------------------------------

    if callable(bus) and not hasattr(bus, "emit"):

        owner = getattr(
            bus,
            "__self__",
            None,
        )

        if (
            owner is not None
            and owner is not safe_emit
            and callable(
                getattr(
                    owner,
                    "emit",
                    None,
                )
            )
        ):

            boot_warn(
                "[EventBus] Received bound emit() | "
                "recovering authoritative EventBus"
            )

            bus = owner

        else:

            boot_warn(
                "[EventBus] Invalid EventBus | "
                "received callable instead of "
                "EventBus object"
            )

            return None

    # ------------------------------------------------------
    # Validate emit()
    # ------------------------------------------------------

    emit_method = getattr(
        bus,
        "emit",
        None,
    )

    if not callable(emit_method):

        boot_warn(
            "[EventBus] Invalid EventBus | "
            "missing callable emit() | "
            "type=%s",
            type(bus).__name__,
        )

        return None

    # ------------------------------------------------------
    # Validate subscribe()
    # ------------------------------------------------------

    subscribe_method = getattr(
        bus,
        "subscribe",
        None,
    )

    subscribe_ready = callable(
        subscribe_method
    )

    if (
        subscribe_method is not None
        and not subscribe_ready
    ):

        boot_warn(
            "[EventBus] Invalid subscribe() | "
            "subscription interface unavailable"
        )

    # ------------------------------------------------------
    # Detect duplicate attachment.
    # ------------------------------------------------------

    already_attached = (
        event_bus is bus
        and safe_emit.event_bus is bus
    )

    # ------------------------------------------------------
    # Store authoritative EventBus FIRST.
    # ------------------------------------------------------

    event_bus = bus

    # ------------------------------------------------------
    # Attach safe proxy.
    #
    # IMPORTANT:
    #
    # attach() performs NO EventBus emission.
    #
    # This prevents:
    #
    # attach_event_bus()
    #      |
    #      v
    # safe_emit()
    #      |
    #      v
    # EventBus.emit()
    #      |
    #      v
    # attach_event_bus()
    #
    # ------------------------------------------------------

    if not safe_emit.attach(
        event_bus
    ):

        boot_warn(
            "[EventBus] safe_emit attachment failed"
        )

        return None

    # ------------------------------------------------------
    # Final identity verification.
    # ------------------------------------------------------

    if (
        event_bus is None
        or safe_emit.event_bus is not event_bus
    ):

        boot_warn(
            "[EventBus] Authoritative identity "
            "verification failed"
        )

        return None

    # ------------------------------------------------------
    # Authoritative state logging.
    # ------------------------------------------------------

    try:

        state_label = (
            "already attached"
            if already_attached
            else "attached"
        )

        logger.info(
            "[EventBus] Authoritative EventBus %s | "
            "type=%s | emit=READY | subscribe=%s",
            state_label,
            type(event_bus).__name__,
            (
                "READY"
                if subscribe_ready
                else "UNAVAILABLE"
            ),
        )

    except Exception:
        pass

    return event_bus


# ----------------------------------------------------------
# EVENTBUS ACCESSOR
# ----------------------------------------------------------

def get_event_bus():

    return event_bus


# ----------------------------------------------------------
# EVENTBUS STATUS
# ----------------------------------------------------------

def event_bus_ready():

    bus = event_bus

    if bus is None:
        return False

    emit_method = getattr(
        bus,
        "emit",
        None,
    )

    return callable(
        emit_method
    )


# ----------------------------------------------------------
# EVENTBUS SUBSCRIPTION STATUS
# ----------------------------------------------------------

def event_bus_subscribe_ready():

    bus = event_bus

    if bus is None:
        return False

    subscribe_method = getattr(
        bus,
        "subscribe",
        None,
    )

    return callable(
        subscribe_method
    )


# ----------------------------------------------------------
# QBITDIALER <- AUTHORITATIVE EVENTBUS
# ----------------------------------------------------------
#
# This attachment MUST occur only after:
#
#   PHASE 01 | EventBus
#
# and before QbitDialer begins runtime operation.
#
# ----------------------------------------------------------

if qbit_dialer is not None:

    priority_engine_obj = (
        adaptive_priority_engine
        if adaptive_priority_engine is not None
        else None
    )

    # ------------------------------------------------------
    # Authoritative EventBus must exist.
    # ------------------------------------------------------

    if event_bus is None:

        raise RuntimeError(
            "QbitDialer cannot attach EventBus: "
            "authoritative EventBus is None"
        )

    # ------------------------------------------------------
    # Authoritative EventBus must provide subscribe().
    # ------------------------------------------------------

    if not callable(
        getattr(
            event_bus,
            "subscribe",
            None,
        )
    ):

        raise RuntimeError(
            "QbitDialer cannot attach EventBus: "
            "authoritative EventBus has no usable "
            "subscribe() method"
        )

    # ------------------------------------------------------
    # Attach EventBus.
    # ------------------------------------------------------

    try:

        attached = qbit_dialer.attach_event_bus(
            event_bus
        )

        if not attached:

            raise RuntimeError(
                "QbitDialer EventBus attachment "
                "returned False"
            )

        # --------------------------------------------------
        # Verify identity.
        # --------------------------------------------------

        dialer_event_bus = getattr(
            qbit_dialer,
            "event_bus",
            None,
        )

        if dialer_event_bus is not event_bus:

            raise RuntimeError(
                "QbitDialer EventBus attachment "
                "failed identity check"
            )

        # --------------------------------------------------
        # Verify proxy still points to same authority.
        # --------------------------------------------------

        if safe_emit.event_bus is not event_bus:

            raise RuntimeError(
                "safe_emit/EventBus identity mismatch"
            )

        logger.info(
            "[QbitDialer] EventBus LINKED | "
            "type=%s | authoritative=True | "
            "same_instance=True",
            type(event_bus).__name__,
        )

    except Exception as exc:

        boot_warn(
            "[QbitDialer] EventBus attachment failed | "
            "%s: %s",
            type(exc).__name__,
            exc,
        )

        raise


# ----------------------------------------------------------
# BOOT-SAFE EMIT STUB
# ----------------------------------------------------------

def emit_stub(
    event_name,
    payload=None,
):

    try:

        print(
            f"[EMIT STUB] "
            f"{event_name} => {payload}"
        )

    except Exception:
        pass

    return True


# ----------------------------------------------------------
# COMPATIBILITY EMIT PROXY
# ----------------------------------------------------------

def emit_proxy(
    event,
    payload=None,
):

    return safe_emit(
        event,
        payload,
    )


# ----------------------------------------------------------
# FINAL EVENTBUS AUTHORITY CHECK
# ----------------------------------------------------------

def validate_event_bus_authority():

    bus = event_bus

    if bus is None:

        return False

    if bus is safe_emit:

        boot_warn(
            "[EventBus] INVALID AUTHORITY | "
            "safe_emit became EventBus"
        )

        return False

    if safe_emit.event_bus is not bus:

        boot_warn(
            "[EventBus] INVALID BRIDGE | "
            "safe_emit is not attached to "
            "authoritative EventBus"
        )

        return False

    if not callable(
        getattr(
            bus,
            "emit",
            None,
        )
    ):

        boot_warn(
            "[EventBus] INVALID AUTHORITY | "
            "emit() unavailable"
        )

        return False

    return True

# ==========================================================
# SECTION 12 â€” RUNTIME STATUS FLAGS
# ==========================================================
#
# SEED Runtime Flag System
#
# GREEN = READY / ONLINE / HEALTHY / VERIFIED
# YELLOW = PENDING / DEGRADED / PASSIVE / WAITING /
#          THROTTLED / RESTARTING / ON-HOLD
# RED   = CRASHED / FAILED / OFFLINE / DEPENDENCY FAILURE
# BLUE  = INFORMATIONAL / TRANSITION / INITIALIZING /
#          OBSERVING / LIFECYCLE EVENT
#
# IMPORTANT:
#   A flag describes runtime state.
#   It is NOT merely a boot counter.
#
# Every status record contains:
#
#   module
#   flag
#   state
#   reason
#   detail
#   timestamp
#   phase
#   dependency
#   recovery
#
# ==========================================================


GREEN_FLAGS = []
YELLOW_FLAGS = []
RED_FLAGS = []
BLUE_FLAGS = []

RUNTIME_FLAGS = []

green_flags_count = 0
yellow_flags_count = 0
red_flags_count = 0
blue_flags_count = 0


# ----------------------------------------------------------
# FLAG NORMALIZATION
# ----------------------------------------------------------

VALID_RUNTIME_FLAGS = {
    "GREEN",
    "YELLOW",
    "RED",
    "BLUE",
}


VALID_RUNTIME_STATES = {
    "READY",
    "ONLINE",
    "HEALTHY",
    "VERIFIED",
    "ACTIVE",

    "PENDING",
    "DEGRADED",
    "PASSIVE",
    "WAITING",
    "THROTTLED",
    "RESTARTING",
    "ON_HOLD",
    "INITIALIZING",

    "CRASHED",
    "FAILED",
    "OFFLINE",
    "STOPPED",
    "DEPENDENCY_FAILURE",

    "TRANSITION",
    "OBSERVING",
    "INFORMATIONAL",
}


# ----------------------------------------------------------
# INTERNAL FLAG RECORD
# ----------------------------------------------------------

def _build_runtime_flag(
    module,
    flag,
    state,
    reason,
    detail=None,
    phase=None,
    dependency=None,
    recovery=None,
):
    return {
        "timestamp": time.time(),
        "module": module,
        "flag": flag,
        "state": state,
        "reason": reason,
        "detail": detail,
        "phase": phase,
        "dependency": dependency,
        "recovery": recovery,
    }


# ----------------------------------------------------------
# GENERIC RUNTIME FLAG
# ----------------------------------------------------------

def add_runtime_flag(
    module,
    flag,
    state,
    reason,
    detail=None,
    phase=None,
    dependency=None,
    recovery=None,
):
    global green_flags_count
    global yellow_flags_count
    global red_flags_count
    global blue_flags_count

    flag = str(flag).upper()
    state = str(state).upper()

    if flag not in VALID_RUNTIME_FLAGS:
        flag = "BLUE"

    if state not in VALID_RUNTIME_STATES:
        state = "INFORMATIONAL"

    record = _build_runtime_flag(
        module=module,
        flag=flag,
        state=state,
        reason=reason,
        detail=detail,
        phase=phase,
        dependency=dependency,
        recovery=recovery,
    )

    RUNTIME_FLAGS.append(record)

    if flag == "GREEN":

        GREEN_FLAGS.append(record)
        green_flags_count += 1

    elif flag == "YELLOW":

        YELLOW_FLAGS.append(record)
        yellow_flags_count += 1

    elif flag == "RED":

        RED_FLAGS.append(record)
        red_flags_count += 1

    elif flag == "BLUE":

        BLUE_FLAGS.append(record)
        blue_flags_count += 1

    # ------------------------------------------------------
    # Human-readable boot log
    # ------------------------------------------------------

    log_message = (
        "[%s FLAG] %s | state=%s | reason=%s"
        % (
            flag,
            module,
            state,
            reason,
        )
    )

    if detail:
        log_message += (
            " | detail=%s"
            % detail
        )

    if dependency:
        log_message += (
            " | dependency=%s"
            % dependency
        )

    if recovery:
        log_message += (
            " | recovery=%s"
            % recovery
        )

    if flag == "GREEN":

        logger.info(
            "%s",
            log_message,
        )

    elif flag == "YELLOW":

        logger.warning(
            "%s",
            log_message,
        )

    elif flag == "RED":

        logger.error(
            "%s",
            log_message,
        )

    else:

        logger.info(
            "%s",
            log_message,
        )

    return record


# ----------------------------------------------------------
# GREEN FLAG
# ----------------------------------------------------------

def add_green_flag(
    reason: str,
    module=None,
    state="READY",
    detail=None,
    phase=None,
    dependency=None,
):
    return add_runtime_flag(
        module=module or "SEED",
        flag="GREEN",
        state=state,
        reason=reason,
        detail=detail,
        phase=phase,
        dependency=dependency,
    )


# ----------------------------------------------------------
# YELLOW FLAG
# ----------------------------------------------------------

def add_yellow_flag(
    reason: str,
    module=None,
    state="PENDING",
    detail=None,
    phase=None,
    dependency=None,
    recovery=None,
):
    return add_runtime_flag(
        module=module or "SEED",
        flag="YELLOW",
        state=state,
        reason=reason,
        detail=detail,
        phase=phase,
        dependency=dependency,
        recovery=recovery,
    )


# ----------------------------------------------------------
# RED FLAG
# ----------------------------------------------------------

def add_red_flag(
    reason: str,
    module=None,
    state="FAILED",
    detail=None,
    phase=None,
    dependency=None,
    recovery=None,
):
    return add_runtime_flag(
        module=module or "SEED",
        flag="RED",
        state=state,
        reason=reason,
        detail=detail,
        phase=phase,
        dependency=dependency,
        recovery=recovery,
    )


# ----------------------------------------------------------
# BLUE FLAG
# ----------------------------------------------------------

def add_blue_flag(
    reason: str,
    module=None,
    state="INFORMATIONAL",
    detail=None,
    phase=None,
    dependency=None,
):
    return add_runtime_flag(
        module=module or "SEED",
        flag="BLUE",
        state=state,
        reason=reason,
        detail=detail,
        phase=phase,
        dependency=dependency,
    )


# ==========================================================
# MODULE STATUS EVALUATION
# ==========================================================

def evaluate_module_status(
    module,
    status,
    reason=None,
    detail=None,
    phase=None,
    dependency=None,
):

    normalized = str(
        status or "PENDING"
    ).upper()

    if normalized in {
        "READY",
        "ONLINE",
        "HEALTHY",
        "VERIFIED",
        "ACTIVE",
    }:

        return add_green_flag(
            reason=(
                reason
                or f"{module} {normalized.lower()}"
            ),
            module=module,
            state=normalized,
            detail=detail,
            phase=phase,
            dependency=dependency,
        )

    if normalized in {
        "PENDING",
        "INITIALIZING",
        "PASSIVE",
        "WAITING",
        "THROTTLED",
        "RESTARTING",
        "ON_HOLD",
        "DEGRADED",
    }:

        return add_yellow_flag(
            reason=(
                reason
                or f"{module} {normalized.lower()}"
            ),
            module=module,
            state=normalized,
            detail=detail,
            phase=phase,
            dependency=dependency,
        )

    if normalized in {
        "CRASHED",
        "FAILED",
        "OFFLINE",
        "STOPPED",
        "DEPENDENCY_FAILURE",
    }:

        return add_red_flag(
            reason=(
                reason
                or f"{module} {normalized.lower()}"
            ),
            module=module,
            state=normalized,
            detail=detail,
            phase=phase,
            dependency=dependency,
        )

    return add_blue_flag(
        reason=(
            reason
            or f"{module} state={normalized}"
        ),
        module=module,
        state=normalized,
        detail=detail,
        phase=phase,
        dependency=dependency,
    )


# ==========================================================
# POST-BOOT FLAG EVALUATION
# ==========================================================

def post_cycle_flags(
    modules_status=None,
):

    modules_status = (
        modules_status
        if modules_status is not None
        else MODULES_STATUS
    )

    for module in POST_TOP_MODULES:

        raw_status = modules_status.get(
            module,
            None,
        )

        # --------------------------------------------------
        # Missing module
        # --------------------------------------------------

        if raw_status is None:

            add_yellow_flag(
                module=module,
                state="PENDING",
                reason=(
                    f"POST validation pending: {module}"
                ),
                detail=(
                    "Module has no authoritative runtime "
                    "status record."
                ),
                phase="POST_BOOT",
            )

            continue

        # --------------------------------------------------
        # Boolean compatibility
        # --------------------------------------------------

        if isinstance(
            raw_status,
            bool,
        ):

            if raw_status:

                add_green_flag(
                    module=module,
                    state="READY",
                    reason=(
                        f"POST success: {module}"
                    ),
                    detail=(
                        "Module reported ready through "
                        "legacy boolean status."
                    ),
                    phase="POST_BOOT",
                )

            else:

                add_red_flag(
                    module=module,
                    state="FAILED",
                    reason=(
                        f"POST failure: {module}"
                    ),
                    detail=(
                        "Module reported False through "
                        "legacy boolean status."
                    ),
                    phase="POST_BOOT",
                )

            continue

        # --------------------------------------------------
        # Structured status
        # --------------------------------------------------

        if isinstance(
            raw_status,
            dict,
        ):

            state = (
                raw_status.get(
                    "state",
                    raw_status.get(
                        "status",
                        "PENDING",
                    ),
                )
            )

            evaluate_module_status(
                module=module,
                status=state,
                reason=raw_status.get(
                    "reason"
                ),
                detail=raw_status.get(
                    "detail"
                ),
                phase="POST_BOOT",
                dependency=raw_status.get(
                    "dependency"
                ),
            )

            continue

        # --------------------------------------------------
        # String status
        # --------------------------------------------------

        if isinstance(
            raw_status,
            str,
        ):

            evaluate_module_status(
                module=module,
                status=raw_status,
                phase="POST_BOOT",
            )

            continue

        # --------------------------------------------------
        # Unknown status object
        # --------------------------------------------------

        add_blue_flag(
            module=module,
            state="INFORMATIONAL",
            reason=(
                f"POST status received: {module}"
            ),
            detail=(
                f"Unsupported status type: "
                f"{type(raw_status).__name__}"
            ),
            phase="POST_BOOT",
        )


# ==========================================================
# RUNTIME STATUS SNAPSHOT
# ==========================================================

def get_runtime_flag_status():

    return {
        "green": {
            "count": green_flags_count,
            "flags": list(GREEN_FLAGS),
        },

        "yellow": {
            "count": yellow_flags_count,
            "flags": list(YELLOW_FLAGS),
        },

        "red": {
            "count": red_flags_count,
            "flags": list(RED_FLAGS),
        },

        "blue": {
            "count": blue_flags_count,
            "flags": list(BLUE_FLAGS),
        },

        "total": len(RUNTIME_FLAGS),
    }


# ==========================================================
# MODULE LIFECYCLE SNAPSHOT
# ==========================================================

def get_module_runtime_state(module):

    matches = [
        item
        for item in RUNTIME_FLAGS
        if item.get("module") == module
    ]

    if not matches:
        return {
            "module": module,
            "flag": "YELLOW",
            "state": "PENDING",
            "reason": "No runtime status recorded",
        }

    # Most recent authoritative record.
    return dict(
        matches[-1]
    )


# ==========================================================
# RUNTIME FLAG SUMMARY
# ==========================================================

def log_runtime_flag_summary():

    logger.info(
        "================================================"
    )

    logger.info(
        "[RUNTIME FLAGS] "
        "GREEN=%d | YELLOW=%d | RED=%d | BLUE=%d | "
        "TOTAL=%d",
        green_flags_count,
        yellow_flags_count,
        red_flags_count,
        blue_flags_count,
        len(RUNTIME_FLAGS),
    )

    logger.info(
        "[RUNTIME FLAGS] "
        "GREEN=READY | "
        "YELLOW=PENDING/DEGRADED | "
        "RED=FAILED/CRASHED | "
        "BLUE=TRANSITION/INFO"
    )

    logger.info(
        "================================================"
    )


# ==========================================================
# FLAGGED STATE HELPERS
# ==========================================================

def module_ready(module):
    state = get_module_runtime_state(
        module
    )

    return (
        state.get("flag") == "GREEN"
        and state.get("state")
        in {
            "READY",
            "ONLINE",
            "HEALTHY",
            "VERIFIED",
            "ACTIVE",
        }
    )


def module_pending(module):
    state = get_module_runtime_state(
        module
    )

    return (
        state.get("flag") == "YELLOW"
        and state.get("state")
        in {
            "PENDING",
            "INITIALIZING",
            "WAITING",
            "PASSIVE",
        }
    )


def module_restarting(module):
    state = get_module_runtime_state(
        module
    )

    return (
        state.get("flag") == "YELLOW"
        and state.get("state") == "RESTARTING"
    )


def module_on_hold(module):
    state = get_module_runtime_state(
        module
    )

    return (
        state.get("flag") == "YELLOW"
        and state.get("state") == "ON_HOLD"
    )


def module_crashed(module):
    state = get_module_runtime_state(
        module
    )

    return (
        state.get("flag") == "RED"
        and state.get("state") == "CRASHED"
    )


def module_failed(module):
    state = get_module_runtime_state(
        module
    )

    return (
        state.get("flag") == "RED"
        and state.get("state")
        in {
            "FAILED",
            "DEPENDENCY_FAILURE",
        }
    )
# ==========================================================
# SECTION 13 â€” QBIT CALLBACK
# ==========================================================

def qbit_controlled_callback(payload):
    global qbit_command_count

    if not isinstance(payload, dict):
        payload = {
            "data": payload
        }

    logger.info(
        "[QBIT CALLBACK] Received payload: %s",
        payload,
    )

    if qbit_command_count >= MAX_QBIT_COMMANDS:

        logger.warning(
            "[QBIT CALLBACK] "
            "Max Qbit commands reached"
        )

        return

    qbit_command_count += 1

    if payload.get("limp"):
        add_green_flag("self-repair")

    if payload.get(
        "brain_motivation",
        0,
    ) > 0.7:

        add_green_flag(
            "motivated action"
        )

    if action_engine is None:
        return

    try:

        if (
            payload.get("limp")
            or payload.get("planning")
        ):

            safe_call(
                action_engine.system_command,
                "stabilize_flow",
                {},
                label="ActionEngine stabilize_flow",
            )

        if payload.get("limp"):

            safe_call(
                action_engine.system_command,
                "repair_qbit",
                {},
                label="ActionEngine repair_qbit",
            )

        if payload.get(
            "brain_motivation",
            0,
        ) > 0.7:

            safe_call(
                action_engine.system_command,
                "boost_progress",
                {},
                label="ActionEngine boost_progress",
            )

    except Exception as exc:
        trace_exception(exc)


# ==========================================================
# SECTION 14 â€” EVENT BUS BOOT
# ==========================================================

def boot_event_bus():
    global event_bus

    boot_log(
        "PHASE 01 | EventBus"
    )

    try:
        from seed.core.event_bus import SEEDEventBus

        event_bus = compatible_construct(
            SEEDEventBus,
            [
                ((), {}),
                ((), {"emit": safe_emit}),
            ],
            "SEEDEventBus",
        )

        if event_bus is None:
            raise RuntimeError(
                "SEEDEventBus unavailable"
            )

        if attach_event_bus(event_bus) is None:
            raise RuntimeError("SEEDEventBus authoritative attachment failed")

        MODULES_STATUS["SEEDEventBus"] = True

        boot_log(
            "EventBus authoritative instance ONLINE"
        )

        return event_bus

    except Exception as exc:

        MODULES_STATUS["SEEDEventBus"] = False

        trace_exception(exc)

        raise


# ==========================================================
# ==========================================================
# SECTION 15 â€” QBIT BOOT
# ==========================================================
#
# PURPOSE:
#
# - Create ONE authoritative Qbit
# - Start/prepare the Qbit cognitive cycle
# - Connect Qbit to registry, nodes, and runtime data
# - Never replace an existing authoritative Qbit
# - Bind it to the authoritative EventBus
# - Preserve the same Qbit object for the entire runtime
# - QbitDialer receives this exact object later
#
# ARCHITECTURE:
#
#     Main3
#        |
#        +--> EventBus  [authoritative]
#        |
#        +--> Qbit     [ONE authoritative instance]
#        |
#        +--> QbitQueueLoop [authoritative transport]
#        |
#        +--> QbitDialer    [command authority]
#
# IMPORTANT:
#
# Qbit BOOT must NEVER create:
#
# - a second Qbit
# - a second EventBus
# - a second QbitQueueLoop
# - a second runtime loop
# - a replacement registry
#
# ==========================================================

def boot_qbit():

    global qbit
    global qbit_core

    boot_log(
        "PHASE 02 | Qbit"
    )

    # ======================================================
    # 01 â€” SINGLE AUTHORITATIVE QBIT GUARD
    # ======================================================

    if qbit is not None:

        qbit_core = qbit

        MODULES_STATUS[
            "Qbit"
        ] = True

        boot_log(
            "Qbit already initialized | "
            "authoritative instance retained"
        )

        logger.info(
            "[Qbit] Existing authoritative Qbit retained | "
            "type=%s | "
            "qbit_id=%s",
            type(qbit).__name__,
            getattr(
                qbit,
                "qbit_id",
                "UNKNOWN",
            ),
        )

        # --------------------------------------------------
        # Re-validate authoritative EventBus identity.
        # Do NOT replace the Qbit.
        # --------------------------------------------------

        if event_bus is not None:

            existing_qbit_bus = getattr(
                qbit,
                "event_bus",
                None,
            )

            if existing_qbit_bus is None:

                try:

                    qbit.event_bus = event_bus

                except Exception as exc:

                    MODULES_STATUS[
                        "Qbit"
                    ] = False

                    trace_exception(
                        exc
                    )

                    raise RuntimeError(
                        "Existing Qbit EventBus binding failed"
                    ) from exc

            elif existing_qbit_bus is not event_bus:

                MODULES_STATUS[
                    "Qbit"
                ] = False

                raise RuntimeError(
                    "Existing authoritative Qbit is bound "
                    "to a different EventBus"
                )

        # --------------------------------------------------
        # Preserve exact object identity.
        # --------------------------------------------------

        if qbit_core is not qbit:

            MODULES_STATUS[
                "Qbit"
            ] = False

            raise RuntimeError(
                "Existing Qbit/QbitCore identity mismatch"
            )

        return qbit

    # ======================================================
    # 02 â€” AUTHORITATIVE EVENTBUS CHECK
    # ======================================================

    if event_bus is None:

        MODULES_STATUS[
            "Qbit"
        ] = False

        raise RuntimeError(
            "Qbit requires authoritative EventBus"
        )

    # ======================================================
    # 03 â€” RESOLVE EXISTING RUNTIME CONNECTIONS
    # ======================================================
    #
    # Do not assume registry/nodes/data are locally defined.
    #
    # Main3 has previously experienced scope failures such as:
    #
    #     NameError: name 'registry' is not defined
    #
    # Resolve them from the module namespace without creating
    # fake replacement systems.
    # ======================================================

    runtime_registry = globals().get(
        "registry",
        None,
    )

    runtime_nodes = globals().get(
        "nodes",
        None,
    )

    runtime_data = globals().get(
        "data",
        None,
    )

    # ------------------------------------------------------
    # Registry may also exist under registry_runtime.
    # Preserve whichever authoritative object already exists.
    # ------------------------------------------------------

    if runtime_registry is None:

        runtime_registry = globals().get(
            "registry_runtime",
            None,
        )

    # ======================================================
    # 04 â€” IMPORT
    # ======================================================

    try:

        from seed.core.qbit.qbit import Qbit

    except Exception as exc:

        MODULES_STATUS[
            "Qbit"
        ] = False

        trace_exception(
            exc
        )

        raise RuntimeError(
            "Qbit import failed"
        ) from exc

    # ======================================================
    # 05 â€” CONSTRUCT EXACTLY ONCE
    # ======================================================

    try:

        attempts = [
            (
                (),
                {
                    "event_bus": event_bus,
                },
            ),
            (
                (),
                {},
            ),
        ]

        constructed_qbit = compatible_construct(
            Qbit,
            attempts,
            "Qbit",
        )

    except Exception as exc:

        MODULES_STATUS[
            "Qbit"
        ] = False

        trace_exception(
            exc
        )

        raise RuntimeError(
            "Qbit construction failed"
        ) from exc

    if constructed_qbit is None:

        MODULES_STATUS[
            "Qbit"
        ] = False

        raise RuntimeError(
            "Qbit initialization returned None"
        )

    # ======================================================
    # 06 â€” AUTHORITATIVE EVENTBUS BIND
    # ======================================================

    constructed_bus = getattr(
        constructed_qbit,
        "event_bus",
        None,
    )

    if constructed_bus is not None:

        if constructed_bus is not event_bus:

            MODULES_STATUS[
                "Qbit"
            ] = False

            raise RuntimeError(
                "Qbit constructed with a different EventBus"
            )

    else:

        try:

            constructed_qbit.event_bus = event_bus

        except Exception as exc:

            MODULES_STATUS[
                "Qbit"
            ] = False

            trace_exception(
                exc
            )

            raise RuntimeError(
                "Qbit EventBus binding failed"
            ) from exc

    # ------------------------------------------------------
    # Final EventBus identity validation.
    # ------------------------------------------------------

    if getattr(
        constructed_qbit,
        "event_bus",
        None,
    ) is not event_bus:

        MODULES_STATUS[
            "Qbit"
        ] = False

        raise RuntimeError(
            "Qbit EventBus identity validation failed"
        )

    # ======================================================
    # 07 â€” CONNECT EXISTING REGISTRY
    # ======================================================
    #
    # Registry is an existing runtime authority.
    # We never construct another registry here.
    #
    # Only attach the reference when the Qbit implementation
    # exposes the corresponding connection point.
    # ======================================================

    if runtime_registry is not None:

        try:

            if hasattr(
                constructed_qbit,
                "registry",
            ):

                constructed_qbit.registry = (
                    runtime_registry
                )

            elif hasattr(
                constructed_qbit,
                "registry_runtime",
            ):

                constructed_qbit.registry_runtime = (
                    runtime_registry
                )

        except Exception as exc:

            logger.warning(
                "[Qbit] Registry attachment deferred | "
                "error=%s",
                exc,
            )

    else:

        logger.warning(
            "[Qbit] Registry reference unavailable during "
            "Qbit boot | connection deferred"
        )

    # ======================================================
    # 08 â€” CONNECT EXISTING NODES
    # ======================================================
    #
    # Never create a node container here.
    # Qbit receives the authoritative runtime node reference
    # if the Qbit implementation exposes it.
    # ======================================================

    if runtime_nodes is not None:

        try:

            if hasattr(
                constructed_qbit,
                "nodes",
            ):

                constructed_qbit.nodes = (
                    runtime_nodes
                )

            elif hasattr(
                constructed_qbit,
                "node_registry",
            ):

                constructed_qbit.node_registry = (
                    runtime_nodes
                )

        except Exception as exc:

            logger.warning(
                "[Qbit] Node attachment deferred | "
                "error=%s",
                exc,
            )

    else:

        logger.warning(
            "[Qbit] Runtime nodes unavailable during "
            "Qbit boot | connection deferred"
        )

    # ======================================================
    # 09 â€” CONNECT EXISTING RUNTIME DATA
    # ======================================================
    #
    # Do not manufacture a new data store.
    # Preserve whatever authoritative data object Main3
    # already owns.
    # ======================================================

    if runtime_data is not None:

        try:

            if hasattr(
                constructed_qbit,
                "data",
            ):

                constructed_qbit.data = (
                    runtime_data
                )

            elif hasattr(
                constructed_qbit,
                "runtime_data",
            ):

                constructed_qbit.runtime_data = (
                    runtime_data
                )

        except Exception as exc:

            logger.warning(
                "[Qbit] Runtime data attachment deferred | "
                "error=%s",
                exc,
            )

    else:

        logger.warning(
            "[Qbit] Runtime data unavailable during "
            "Qbit boot | connection deferred"
        )

    # ======================================================
    # 10 â€” PUBLISH AUTHORITATIVE INSTANCE
    # ======================================================
    #
    # IMPORTANT:
    #
    # From this point forward:
    #
    #     qbit
    #     qbit_core
    #
    # MUST reference the exact same object.
    #
    # QbitDialer MUST receive this exact object later.
    # ======================================================

    qbit = constructed_qbit

    qbit_core = constructed_qbit

    # ======================================================
    # 11 â€” FINAL IDENTITY VALIDATION
    # ======================================================

    if qbit is not qbit_core:

        MODULES_STATUS[
            "Qbit"
        ] = False

        qbit = None
        qbit_core = None

        raise RuntimeError(
            "Qbit authoritative identity validation failed"
        )

    # ======================================================
    # 12 â€” AUTHORITATIVE EVENTBUS REVALIDATION
    # ======================================================

    if getattr(
        qbit,
        "event_bus",
        None,
    ) is not event_bus:

        MODULES_STATUS[
            "Qbit"
        ] = False

        qbit = None
        qbit_core = None

        raise RuntimeError(
            "Qbit authoritative EventBus identity "
            "validation failed"
        )

    # ======================================================
    # 13 â€” STATUS
    # ======================================================

    MODULES_STATUS[
        "Qbit"
    ] = True

    boot_log(
        "Qbit cognitive carrier ONLINE"
    )

    logger.info(
        "[Qbit] Authoritative instance established | "
        "qbit_id=%s | "
        "track=%s | "
        "generation=%s | "
        "event_bus=%s | "
        "registry=%s | "
        "nodes=%s | "
        "data=%s",
        getattr(
            qbit,
            "qbit_id",
            "UNKNOWN",
        ),
        getattr(
            qbit,
            "track_id",
            getattr(
                qbit,
                "track",
                "UNKNOWN",
            ),
        ),
        getattr(
            qbit,
            "generation",
            "UNKNOWN",
        ),
        type(
            event_bus
        ).__name__,
        runtime_registry is not None,
        runtime_nodes is not None,
        runtime_data is not None,
    )

    # ======================================================
    # 14 â€” CYCLE OWNERSHIP
    # ======================================================
    #
    # DO NOT start another asyncio loop here.
    #
    # QbitQueueLoop owns Qbit transport/execution.
    # QbitDialer will receive this exact Qbit instance.
    #
    # The Qbit itself is therefore marked as the authoritative
    # cognitive carrier; runtime cycle startup remains with the
    # existing authoritative runtime.
    # ======================================================

    logger.info(
        "[Qbit] Cycle authority preserved | "
        "transport remains authoritative QbitQueueLoop"
    )

    return qbit


# ==========================================================
# SECTION 16 â€” QUEUE LOOP BOOT
# ==========================================================
#
# AUTHORITY:
#
# QbitQueueLoop is the ONE canonical Qbit transport loop.
#
# BOOT ORDER:
#
# EventBus
#     â†“
# Qbit
#     â†“
# QbitQueueLoop
#     â†“
# KernelBus
#     â†“
# QbitDialer
#     â†“
# Heartbeat / Brains / Registry / TrackSystem
#
# IMPORTANT:
#
# - Construct QbitQueueLoop EXACTLY ONCE.
# - Preserve the exact same instance for the runtime.
# - Never create a second queue loop.
# - Never create a second runtime queue.
# - Never pass queue_loop=queue_loop into its own constructor.
# - KernelBus is attached later when available.
# - QbitDialer receives THIS EXACT queue_loop instance.
#
# ==========================================================


def boot_queue_loop():

    global qbit_queue
    global queue_loop
    global qbit
    global qbit_core
    global qbit_dialer
    global kernel_bus

    boot_log(
        "PHASE 03 | QbitQueueLoop"
    )

    try:

        # ==================================================
        # 01 â€” EXISTING AUTHORITATIVE QUEUE LOOP GUARD
        # ==================================================
        #
        # Never replace an already-established QueueLoop.
        # This is critical because QbitDialer, Heartbeat,
        # KernelBus, and SEEDCore must all share this exact
        # object.
        # ==================================================

        if queue_loop is not None:

            MODULES_STATUS[
                "QbitQueueLoop"
            ] = True

            boot_log(
                "QbitQueueLoop already initialized | "
                "authoritative instance retained"
            )

            logger.info(
                "[QbitQueueLoop] Existing authoritative "
                "instance retained | "
                "type=%s | "
                "id=%s",
                type(
                    queue_loop
                ).__name__,
                id(
                    queue_loop
                ),
            )

            # ----------------------------------------------
            # Reuse the existing physical queue if present.
            # ----------------------------------------------

            existing_queue = getattr(
                queue_loop,
                "qbit_queue",
                None,
            )

            if existing_queue is not None:

                qbit_queue = existing_queue

            elif qbit_queue is not None:

                try:

                    queue_loop.qbit_queue = (
                        qbit_queue
                    )

                except Exception:
                    pass

            return queue_loop

        # ==================================================
        # 02 â€” AUTHORITATIVE EVENTBUS CHECK
        # ==================================================

        if event_bus is None:

            MODULES_STATUS[
                "QbitQueueLoop"
            ] = False

            raise RuntimeError(
                "QbitQueueLoop requires authoritative EventBus"
            )

        # ==================================================
        # 03 â€” IMPORT
        # ==================================================

        from seed.core.emitters.qbit_queue_loop import (
            QbitQueueLoop,
        )

        # ==================================================
        # 04 â€” CREATE ONE PHYSICAL QBIT QUEUE
        # ==================================================
        #
        # This queue belongs to THIS authoritative
        # QbitQueueLoop.
        #
        # Do not create another queue later.
        # ==================================================

        if qbit_queue is None:

            qbit_queue = queue.Queue()

        # ==================================================
        # 05 â€” CONSTRUCTOR COMPATIBILITY
        # ==================================================
        #
        # queue_loop MUST NOT appear in these arguments.
        #
        # kernel_bus is intentionally absent because it is
        # loaded later in Main3.
        #
        # qbit is supplied when the implementation supports
        # it, allowing the QueueLoop to know the authoritative
        # Qbit from the beginning.
        # ==================================================

        attempts = [

            # ------------------------------------------------
            # Preferred modern constructor.
            # ------------------------------------------------
            (
                (),
                {
                    "event_bus": event_bus,
                    "qbit_queue": qbit_queue,
                    "qbit": qbit,
                },
            ),

            # ------------------------------------------------
            # EventBus + queue + Qbit without keyword support.
            # ------------------------------------------------
            (
                (
                    event_bus,
                    qbit_queue,
                    qbit,
                ),
                {},
            ),

            # ------------------------------------------------
            # EventBus + queue compatibility.
            # ------------------------------------------------
            (
                (),
                {
                    "event_bus": event_bus,
                    "qbit_queue": qbit_queue,
                },
            ),

            # ------------------------------------------------
            # Positional EventBus + queue compatibility.
            # ------------------------------------------------
            (
                (
                    event_bus,
                    qbit_queue,
                ),
                {},
            ),

            # ------------------------------------------------
            # EventBus-only compatibility.
            # ------------------------------------------------
            (
                (
                    event_bus,
                ),
                {},
            ),

            # ------------------------------------------------
            # Minimal compatibility.
            # ------------------------------------------------
            (
                (),
                {},
            ),
        ]

        # ==================================================
        # 06 â€” CONSTRUCT EXACTLY ONCE
        # ==================================================

        constructed_queue_loop = compatible_construct(
            QbitQueueLoop,
            attempts,
            "QbitQueueLoop",
        )

        if constructed_queue_loop is None:

            raise RuntimeError(
                "QbitQueueLoop initialization failed"
            )

        # ==================================================
        # 07 â€” PUBLISH AUTHORITATIVE INSTANCE
        # ==================================================
        #
        # THIS IS THE ONLY CONSTRUCTION.
        #
        # Never call compatible_construct(QbitQueueLoop,...)
        # again in this function.
        # ==================================================

        queue_loop = constructed_queue_loop

        # ==================================================
        # 08 â€” BASIC IDENTITY VALIDATION
        # ==================================================

        if queue_loop is None:

            raise RuntimeError(
                "QbitQueueLoop constructed as None"
            )

        logger.info(
            "[QbitQueueLoop] Authoritative instance "
            "established | "
            "type=%s | "
            "id=%s",
            type(
                queue_loop
            ).__name__,
            id(
                queue_loop
            ),
        )

        # ==================================================
        # 09 â€” PHYSICAL QUEUE BINDING
        # ==================================================
        #
        # Preserve the exact queue used during construction.
        # ==================================================

        queue_bound = False

        for attr_name in (
            "qbit_queue",
            "queue",
            "_queue",
        ):

            try:

                current_queue = getattr(
                    queue_loop,
                    attr_name,
                    None,
                )

                if current_queue is qbit_queue:

                    queue_bound = True
                    break

                if current_queue is None:

                    setattr(
                        queue_loop,
                        attr_name,
                        qbit_queue,
                    )

                    queue_bound = True
                    break

            except Exception:

                continue

        if not queue_bound:

            logger.warning(
                "[QbitQueueLoop] Existing queue attribute "
                "could not be rebound | preserving "
                "implementation-owned queue"
            )

        # ==================================================
        # 10 â€” AUTHORITATIVE EVENTBUS BINDING
        # ==================================================

        event_bus_bound = False

        current_event_bus = getattr(
            queue_loop,
            "event_bus",
            None,
        )

        if current_event_bus is event_bus:

            event_bus_bound = True

        elif current_event_bus is None:

            for method_name in (
                "attach_event_bus",
                "set_event_bus",
                "bind_event_bus",
            ):

                method = getattr(
                    queue_loop,
                    method_name,
                    None,
                )

                if not callable(method):
                    continue

                try:

                    method(
                        event_bus
                    )

                    event_bus_bound = (
                        getattr(
                            queue_loop,
                            "event_bus",
                            event_bus,
                        )
                        is event_bus
                    )

                    if event_bus_bound:
                        break

                except TypeError:

                    try:

                        method(
                            event_bus=event_bus
                        )

                        event_bus_bound = (
                            getattr(
                                queue_loop,
                                "event_bus",
                                event_bus,
                            )
                            is event_bus
                        )

                        if event_bus_bound:
                            break

                    except Exception:
                        continue

                except Exception:

                    continue

            if not event_bus_bound:

                try:

                    queue_loop.event_bus = event_bus

                    event_bus_bound = (
                        getattr(
                            queue_loop,
                            "event_bus",
                            None,
                        )
                        is event_bus
                    )

                except Exception:
                    pass

        else:

            raise RuntimeError(
                "QbitQueueLoop is bound to a different "
                "EventBus"
            )

        if not event_bus_bound:

            raise RuntimeError(
                "QbitQueueLoop EventBus identity "
                "validation failed"
            )

        # ==================================================
        # 11 â€” AUTHORITATIVE QBIT BINDING
        # ==================================================
        #
        # QbitQueueLoop and Qbit must reference the same
        # authoritative Qbit created in Section 15.
        # ==================================================

        if qbit is not None:

            qbit_bound = False

            current_qbit = getattr(
                queue_loop,
                "qbit",
                None,
            )

            if current_qbit is qbit:

                qbit_bound = True

            elif current_qbit is None:

                for method_name in (
                    "attach_qbit",
                    "set_qbit",
                    "bind_qbit",
                ):

                    method = getattr(
                        queue_loop,
                        method_name,
                        None,
                    )

                    if not callable(method):
                        continue

                    try:

                        method(
                            qbit
                        )

                        if getattr(
                            queue_loop,
                            "qbit",
                            qbit,
                        ) is qbit:

                            qbit_bound = True
                            break

                    except TypeError:

                        try:

                            method(
                                qbit=qbit
                            )

                            if getattr(
                                queue_loop,
                                "qbit",
                                qbit,
                            ) is qbit:

                                qbit_bound = True
                                break

                        except Exception:
                            continue

                    except Exception:
                        continue

                if not qbit_bound:

                    try:

                        queue_loop.qbit = qbit

                        qbit_bound = (
                            getattr(
                                queue_loop,
                                "qbit",
                                None,
                            )
                            is qbit
                        )

                    except Exception:
                        pass

            else:

                raise RuntimeError(
                    "QbitQueueLoop is bound to a different "
                    "Qbit instance"
                )

            if not qbit_bound:

                raise RuntimeError(
                    "QbitQueueLoop Qbit identity "
                    "validation failed"
                )

        # ==================================================
        # 12 â€” QBIT CORE IDENTITY
        # ==================================================

        if qbit is not None:

            if qbit_core is None:

                qbit_core = qbit

            elif qbit_core is not qbit:

                raise RuntimeError(
                    "Qbit/QbitCore identity mismatch during "
                    "QbitQueueLoop boot"
                )

        # ==================================================
        # 13 â€” CONNECT EXISTING REGISTRY
        # ==================================================
        #
        # Never construct a registry here.
        # ==================================================

        runtime_registry = globals().get(
            "registry",
            None,
        )

        if runtime_registry is None:

            runtime_registry = globals().get(
                "registry_runtime",
                None,
            )

        if runtime_registry is not None:

            for attr_name in (
                "registry",
                "registry_runtime",
            ):

                try:

                    if hasattr(
                        queue_loop,
                        attr_name,
                    ):

                        setattr(
                            queue_loop,
                            attr_name,
                            runtime_registry,
                        )

                        break

                except Exception:

                    continue

        # ==================================================
        # 14 â€” CONNECT EXISTING NODES
        # ==================================================

        runtime_nodes = globals().get(
            "nodes",
            None,
        )

        if runtime_nodes is not None:

            for attr_name in (
                "nodes",
                "node_registry",
            ):

                try:

                    if hasattr(
                        queue_loop,
                        attr_name,
                    ):

                        setattr(
                            queue_loop,
                            attr_name,
                            runtime_nodes,
                        )

                        break

                except Exception:

                    continue

        # ==================================================
        # 15 â€” CONNECT EXISTING RUNTIME DATA
        # ==================================================

        runtime_data = globals().get(
            "data",
            None,
        )

        if runtime_data is not None:

            for attr_name in (
                "data",
                "runtime_data",
            ):

                try:

                    if hasattr(
                        queue_loop,
                        attr_name,
                    ):

                        setattr(
                            queue_loop,
                            attr_name,
                            runtime_data,
                        )

                        break

                except Exception:

                    continue

        # ==================================================
        # 16 â€” KERNEL BUS
        # ==================================================
        #
        # KernelBus may not exist yet.
        #
        # If it already exists, attach it now.
        # Otherwise later boot code must attach the SAME
        # KernelBus instance.
        # ==================================================

        runtime_kernel_bus = globals().get(
            "kernel_bus",
            None,
        )

        if runtime_kernel_bus is not None:

            for method_name in (
                "attach_kernel_bus",
                "set_kernel_bus",
                "bind_kernel_bus",
            ):

                method = getattr(
                    queue_loop,
                    method_name,
                    None,
                )

                if not callable(method):
                    continue

                try:

                    method(
                        runtime_kernel_bus
                    )

                    break

                except TypeError:

                    try:

                        method(
                            kernel_bus=runtime_kernel_bus
                        )

                        break

                    except Exception:
                        continue

                except Exception:
                    continue

            else:

                try:

                    if hasattr(
                        queue_loop,
                        "kernel_bus",
                    ):

                        queue_loop.kernel_bus = (
                            runtime_kernel_bus
                        )

                except Exception:
                    pass

        # ==================================================
        # 17 â€” QBIT DIALER BINDING
        # ==================================================
        #
        # THIS IS CRITICAL.
        #
        # QbitDialer MUST receive:
        #
        #     queue_loop
        #
        # and that object MUST be this exact authoritative
        # QbitQueueLoop instance.
        #
        # NEVER pass qbit_queue here.
        # NEVER construct another QbitQueueLoop.
        # NEVER allow a plain queue.Queue to become the
        # authoritative transport.
        # ==================================================

        runtime_dialer = globals().get(
            "qbit_dialer",
            None,
        )

        if runtime_dialer is not None:

            dialer_bound = False

            # ------------------------------------------------
            # Preferred explicit attachment APIs.
            # ------------------------------------------------

            for method_name in (
                "bind_authoritative_queue_loop",
                "attach_queue_loop",
                "set_queue_loop",
                "bind_queue_loop",
            ):

                method = getattr(
                    runtime_dialer,
                    method_name,
                    None,
                )

                if not callable(method):
                    continue

                try:

                    method(
                        queue_loop
                    )

                    dialer_bound = True

                    break

                except TypeError:

                    try:

                        method(
                            queue_loop=queue_loop
                        )

                        dialer_bound = True

                        break

                    except Exception:
                        continue

                except Exception:
                    continue

            # ------------------------------------------------
            # Direct reference fallback only if supported.
            # ------------------------------------------------

            if not dialer_bound:

                try:

                    if hasattr(
                        runtime_dialer,
                        "queue_loop",
                    ):

                        runtime_dialer.queue_loop = (
                            queue_loop
                        )

                        dialer_bound = (
                            getattr(
                                runtime_dialer,
                                "queue_loop",
                                None,
                            )
                            is queue_loop
                        )

                except Exception:
                    pass

            if not dialer_bound:

                logger.warning(
                    "[QbitQueueLoop] QbitDialer exists but "
                    "does not expose a recognized queue-loop "
                    "binding interface | binding deferred"
                )

            else:

                # --------------------------------------------
                # HARD IDENTITY VALIDATION.
                # --------------------------------------------

                dialer_queue_loop = getattr(
                    runtime_dialer,
                    "queue_loop",
                    getattr(
                        runtime_dialer,
                        "_queue_loop",
                        None,
                    ),
                )

                if (
                    dialer_queue_loop is not None
                    and
                    dialer_queue_loop is not queue_loop
                ):

                    raise RuntimeError(
                        "QbitDialer queue-loop identity "
                        "validation failed"
                    )

                logger.info(
                    "[QbitQueueLoop] QbitDialer bound | "
                    "same_instance=%s | "
                    "queue_loop=%s",
                    dialer_queue_loop is queue_loop,
                    type(
                        queue_loop
                    ).__name__,
                )

        else:

            logger.info(
                "[QbitQueueLoop] QbitDialer not yet available | "
                "binding deferred to later runtime phase"
            )

        # ==================================================
        # 18 â€” AUTHORITATIVE IDENTITY MARKERS
        # ==================================================

        try:

            queue_loop.authoritative = True

        except Exception:
            pass

        try:

            queue_loop.is_authoritative = True

        except Exception:
            pass

        try:

            queue_loop._authoritative_qbit = qbit

        except Exception:
            pass

        try:

            queue_loop._authoritative_event_bus = (
                event_bus
            )

        except Exception:
            pass

        # ==================================================
        # 19 â€” FINAL VALIDATION
        # ==================================================

        if queue_loop is None:

            raise RuntimeError(
                "Authoritative QbitQueueLoop is None"
            )

        if event_bus is not None:

            loop_event_bus = getattr(
                queue_loop,
                "event_bus",
                None,
            )

            if loop_event_bus is not event_bus:

                raise RuntimeError(
                    "Authoritative QbitQueueLoop EventBus "
                    "identity validation failed"
                )

        if qbit is not None:

            loop_qbit = getattr(
                queue_loop,
                "qbit",
                None,
            )

            if (
                loop_qbit is not None
                and
                loop_qbit is not qbit
            ):

                raise RuntimeError(
                    "Authoritative QbitQueueLoop Qbit "
                    "identity validation failed"
                )

        # ==================================================
        # 20 â€” STATUS
        # ==================================================

        MODULES_STATUS[
            "QbitQueueLoop"
        ] = True

        boot_log(
            "QbitQueueLoop ONLINE"
        )

        logger.info(
            "[QbitQueueLoop] AUTHORITATIVE TRANSPORT ONLINE | "
            "type=%s | "
            "instance=%s | "
            "qbit_id=%s | "
            "event_bus=%s | "
            "dialer=%s | "
            "kernel_bus=%s",
            type(
                queue_loop
            ).__name__,
            id(
                queue_loop
            ),
            getattr(
                qbit,
                "qbit_id",
                "UNKNOWN",
            ),
            type(
                event_bus
            ).__name__,
            qbit_dialer is not None,
            kernel_bus is not None,
        )

        return queue_loop

    except Exception as exc:

        MODULES_STATUS[
            "QbitQueueLoop"
        ] = False

        # --------------------------------------------------
        # Never leave a half-constructed global object.
        # --------------------------------------------------

        queue_loop = None
        qbit_queue = None

        trace_exception(
            exc
        )

        raise
# ==========================================================
# SECTION 17 â€” KERNEL BUS BOOT
# ==========================================================

def boot_kernel_bus():
    global kernel_bus

    boot_log(
        "PHASE 04 | QbitKernelBus"
    )

    try:

        from seed.core.kernel.qbit_bus import (
            QbitKernelBus,
        )

        kernel_bus = QbitKernelBus()

        MODULES_STATUS[
            "QbitKernelBus"
        ] = True

        boot_log(
            "QbitKernelBus ONLINE"
        )

        return kernel_bus

    except Exception as exc:

        MODULES_STATUS[
            "QbitKernelBus"
        ] = False

        trace_exception(exc)

        return None


# ==========================================================
# SECTION 18 â€” QBIT DIALER / BRAIN
# ==========================================================
#
# QbitDialer is the authoritative command / cognition
# authority for the SEED runtime.
#
# Authority chain:
#
# EventBus
#     â†“
# Qbit
#     â†“
# QbitQueueLoop
#     â†“
# QbitDialer
#     â†“
# Brain / Command Plane
#
# NEVER:
#
# - create a second Qbit
# - create a second QbitQueueLoop
# - create a second QbitDialer
# - create a second EventBus
# - replace the authoritative queue
# - replace the authoritative Qbit
#
# Heartbeat is a signal source.
# QbitDialer is command authority.
#
# IMPORTANT QUEUE CONTRACT:
#
# queue_loop / qbit_loop / qbit_queue_loop
#     â†’ authoritative QbitQueueLoop
#
# qbit_queue
#     â†’ physical queue owned/exposed by the authoritative
#       QbitQueueLoop, when required by the Dialer.
#
# NEVER assign the QbitQueueLoop object directly to
# qbit_dialer.qbit_queue.
#
# ==========================================================


def qbit_receive_handler(packet):
    if qbit_dialer is None:
        return None

    receiver = getattr(
        qbit_dialer,
        "receive_qbit",
        None,
    )

    if not callable(receiver):
        return None

    return safe_call(
        receiver,
        packet,
        default=None,
        label="QbitDialer.receive_qbit",
    )


# ==========================================================
# QBIT DIALER BOOT
# ==========================================================

async def boot_qbit_dialer(start_runtime=True):

    global qbit_dialer
    global kernel_start_task

    boot_log(
        "PHASE 18 | QbitDialer"
    )

    # ======================================================
    # 18A â€” RESOLVE AUTHORITATIVE DEPENDENCIES
    # ======================================================

    event_bus_obj = globals().get(
        "event_bus",
        None,
    )

    qbit_obj = globals().get(
        "qbit",
        None,
    )

    queue_loop_obj = globals().get(
        "queue_loop",
        None,
    )

    kernel_bus_obj = globals().get(
        "kernel_bus",
        None,
    )

    if event_bus_obj is None:

        MODULES_STATUS[
            "QbitDialer"
        ] = False

        raise RuntimeError(
            "QbitDialer requires authoritative EventBus"
        )

    if qbit_obj is None:

        MODULES_STATUS[
            "QbitDialer"
        ] = False

        raise RuntimeError(
            "QbitDialer requires authoritative Qbit"
        )

    if queue_loop_obj is None:

        MODULES_STATUS[
            "QbitDialer"
        ] = False

        raise RuntimeError(
            "QbitDialer requires authoritative QbitQueueLoop"
        )

    # ======================================================
    # 18B â€” VALIDATE QUEUE LOOP
    # ======================================================

    queue_loop_type = type(
        queue_loop_obj
    ).__name__

    if (
        "QbitQueueLoop"
        not in queue_loop_type
    ):

        MODULES_STATUS[
            "QbitDialer"
        ] = False

        raise RuntimeError(
            "QbitDialer received non-authoritative "
            "QbitQueueLoop"
        )

    # ======================================================
    # 18C â€” VALIDATE EVENTBUS
    # ======================================================

    event_emit = getattr(
        event_bus_obj,
        "emit",
        None,
    )

    if not callable(event_emit):

        MODULES_STATUS[
            "QbitDialer"
        ] = False

        raise RuntimeError(
            "QbitDialer requires EventBus.emit()"
        )

    # ======================================================
    # 18D â€” RESOLVE PHYSICAL QUEUE
    # ======================================================
    #
    # The QueueLoop is the authoritative transport object.
    #
    # qbit_queue must NOT become the QueueLoop itself.
    #
    # Search only existing attributes.
    # Never manufacture a replacement queue.
    #

    physical_qbit_queue = None

    for attribute_name in (
        "qbit_queue",
        "queue",
        "_queue",
        "physical_queue",
        "_qbit_queue",
    ):

        candidate = getattr(
            queue_loop_obj,
            attribute_name,
            None,
        )

        if candidate is None:
            continue

        # --------------------------------------------------
        # Reject the QueueLoop itself.
        # --------------------------------------------------

        if candidate is queue_loop_obj:
            continue

        candidate_type = type(
            candidate
        ).__name__

        # --------------------------------------------------
        # A physical queue must not itself be another
        # QbitQueueLoop.
        # --------------------------------------------------

        if "QbitQueueLoop" in candidate_type:
            continue

        physical_qbit_queue = candidate
        break

    # ======================================================
    # 18E â€” REUSE EXISTING DIALER
    # ======================================================

    if qbit_dialer is not None:

        existing_dialer = qbit_dialer

        # --------------------------------------------------
        # Existing Qbit identity
        # --------------------------------------------------

        existing_qbit = getattr(
            existing_dialer,
            "qbit",
            None,
        )

        if (
            existing_qbit is not None
            and existing_qbit is not qbit_obj
        ):

            MODULES_STATUS[
                "QbitDialer"
            ] = False

            raise RuntimeError(
                "Existing QbitDialer is bound to "
                "a different Qbit"
            )

        # --------------------------------------------------
        # Existing authoritative QueueLoop identity
        # --------------------------------------------------

        existing_queue_loop = None

        for attribute_name in (
            "queue_loop",
            "qbit_loop",
            "qbit_queue_loop",
        ):

            candidate = getattr(
                existing_dialer,
                attribute_name,
                None,
            )

            if candidate is not None:

                existing_queue_loop = candidate
                break

        if (
            existing_queue_loop is not None
            and existing_queue_loop
            is not queue_loop_obj
        ):

            MODULES_STATUS[
                "QbitDialer"
            ] = False

            raise RuntimeError(
                "Existing QbitDialer is bound to "
                "a different QbitQueueLoop"
            )

        # --------------------------------------------------
        # Existing qbit_queue must not contain the
        # QbitQueueLoop object.
        # --------------------------------------------------

        existing_physical_queue = getattr(
            existing_dialer,
            "qbit_queue",
            None,
        )

        if (
            existing_physical_queue
            is queue_loop_obj
        ):

            if physical_qbit_queue is not None:

                try:

                    setattr(
                        existing_dialer,
                        "qbit_queue",
                        physical_qbit_queue,
                    )

                except Exception as exc:

                    MODULES_STATUS[
                        "QbitDialer"
                    ] = False

                    raise RuntimeError(
                        "QbitDialer qbit_queue contains "
                        "QbitQueueLoop and could not be "
                        "corrected to the existing "
                        "physical queue"
                    ) from exc

            else:

                logger.warning(
                    "[QbitDialer] Existing qbit_queue "
                    "references QbitQueueLoop and no "
                    "physical queue was exposed"
                )

        # --------------------------------------------------
        # Preserve the existing Dialer.
        # --------------------------------------------------

        qbit_dialer = existing_dialer

        boot_log(
            "QbitDialer already exists | "
            "authoritative instance reused"
        )

    # ======================================================
    # 18F â€” RESOLVE OPTIONAL BRAIN / GOVERNANCE SYSTEMS
    # ======================================================

    cognition_map_obj = globals().get(
        "cognition_map",
        None,
    )

    adaptive_priority_engine_obj = globals().get(
        "adaptive_priority_engine",
        None,
    )

    cognitive_governor_obj = globals().get(
        "cognitive_governor",
        None,
    )

    memory_weighting_obj = globals().get(
        "memory_weighting_system",
        None,
    )

    qbit_watchdog_obj = globals().get(
        "qbit_watchdog",
        None,
    )

    memory_graph_obj = globals().get(
        "memory_graph",
        None,
    )
    if memory_graph_obj is None:
        try:
            from seed.core.memory.qbit_memory_graph import QbitMemoryGraph
            memory_graph_obj = QbitMemoryGraph()
            globals()["memory_graph"] = memory_graph_obj
        except Exception as exc:
            boot_warn(f"QbitMemoryGraph unavailable: {exc}")

    # ======================================================
    # 18G â€” BUILD AUTHORITATIVE CONSTRUCTOR CONTRACT
    # ======================================================

    dialer_kwargs = {
        "event_bus": event_bus_obj,
        "qbit": qbit_obj,

        # --------------------------------------------------
        # IMPORTANT:
        #
        # qbit_queue receives only the physical queue,
        # never the QbitQueueLoop.
        # --------------------------------------------------

        "qbit_queue": physical_qbit_queue,

        # --------------------------------------------------
        # These remain authoritative QueueLoop references.
        # --------------------------------------------------

        "qbit_loop": queue_loop_obj,
        "queue_loop": queue_loop_obj,
        "qbit_queue_loop": queue_loop_obj,

        "kernel_bus": kernel_bus_obj,
        "emit": event_emit,
        "cognition_map": cognition_map_obj,
        "adaptive_priority_engine": (
            adaptive_priority_engine_obj
        ),
        "cognitive_governor": (
            cognitive_governor_obj
        ),
        "memory_weighting_system": (
            memory_weighting_obj
        ),
        "qbit_watchdog": qbit_watchdog_obj,
        "memory_graph": memory_graph_obj,
    }

    # ------------------------------------------------------
    # Remove unavailable optional values.
    # ------------------------------------------------------

    dialer_kwargs = {
        key: value
        for key, value in dialer_kwargs.items()
        if value is not None
    }

    # ======================================================
    # 18H â€” IMPORT QBIT DIALER
    # ======================================================

    try:

        from seed.core.dialers.qbit_dialer import (
            QbitDialer,
        )

    except Exception as exc:

        MODULES_STATUS[
            "QbitDialer"
        ] = False

        logger.error(
            "[QbitDialer] import failed | %s",
            exc,
        )

        raise RuntimeError(
            "QbitDialer import failed"
        ) from exc

    # ======================================================
    # 18I â€” CONSTRUCTOR COMPATIBILITY
    # ======================================================

    try:

        filtered_kwargs = (
            filter_constructor_kwargs(
                QbitDialer,
                dialer_kwargs,
            )
        )

    except Exception:

        filtered_kwargs = (
            dialer_kwargs
        )

    # ======================================================
    # 18J â€” CONSTRUCT EXACTLY ONE DIALER
    # ======================================================

    if qbit_dialer is None:

        try:

            qbit_dialer = QbitDialer(
                **filtered_kwargs
            )

        except Exception as first_exc:

            logger.warning(
                "[QbitDialer] "
                "authoritative constructor compatibility "
                "attempt failed | %s",
                first_exc,
            )

            # --------------------------------------------------
            # Reduced authoritative constructor.
            #
            # Preserve EventBus, Qbit and authoritative
            # QueueLoop.
            #
            # qbit_queue is included only when a physical
            # queue actually exists.
            # --------------------------------------------------

            required_kwargs = {
                "event_bus": event_bus_obj,
                "qbit": qbit_obj,
                "qbit_loop": queue_loop_obj,
                "queue_loop": queue_loop_obj,
            }

            if physical_qbit_queue is not None:

                required_kwargs[
                    "qbit_queue"
                ] = physical_qbit_queue

            try:

                filtered_required_kwargs = (
                    filter_constructor_kwargs(
                        QbitDialer,
                        required_kwargs,
                    )
                )

            except Exception:

                filtered_required_kwargs = (
                    required_kwargs
                )

            try:

                qbit_dialer = QbitDialer(
                    **filtered_required_kwargs
                )

            except Exception as exc:

                MODULES_STATUS[
                    "QbitDialer"
                ] = False

                logger.error(
                    "[QbitDialer] "
                    "authoritative construction failed | %s",
                    exc,
                )

                raise RuntimeError(
                    "QbitDialer construction failed"
                ) from exc

    # ======================================================
    # QBIT MEMORY GRAPH — AUTHORITATIVE BINDING
    # ======================================================
    if memory_graph_obj is not None:
        try:
            memory_graph_obj.bind_runtime(
                track_system=globals().get("track_system"),
                module_registry=globals().get("module_registry"),
                adaptive_priority_engine=adaptive_priority_engine_obj,
                evolution_engine=globals().get("evolution_engine"),
            )
            MODULES_STATUS["QbitMemoryGraph"] = True
            if module_registry is not None:
                register = getattr(module_registry, "register", None)
                if callable(register):
                    try:
                        register(
                            "QbitMemoryGraph",
                            memory_graph_obj,
                            category="memory",
                        )
                    except TypeError:
                        register("QbitMemoryGraph", memory_graph_obj)
        except Exception as exc:
            MODULES_STATUS["QbitMemoryGraph"] = False
            boot_warn(f"QbitMemoryGraph binding deferred: {exc}")

    # ======================================================
    # 18K â€” AUTHORITATIVE REFERENCE ATTACHMENT
    # ======================================================
    #
    # Attach only existing runtime objects.
    # Never manufacture replacements.
    #

    attachment_map = {
        "event_bus": event_bus_obj,
        "qbit": qbit_obj,

        # --------------------------------------------------
        # Authoritative QueueLoop references.
        # --------------------------------------------------

        "queue_loop": queue_loop_obj,
        "qbit_loop": queue_loop_obj,
        "qbit_queue_loop": queue_loop_obj,

        "kernel_bus": kernel_bus_obj,
    }

    # ------------------------------------------------------
    # Only attach qbit_queue when an actual physical queue
    # exists. Never assign the QueueLoop here.
    # ------------------------------------------------------

    if physical_qbit_queue is not None:

        attachment_map[
            "qbit_queue"
        ] = physical_qbit_queue

    for (
        attribute_name,
        attribute_value,
    ) in attachment_map.items():

        if attribute_value is None:
            continue

        try:

            setattr(
                qbit_dialer,
                attribute_name,
                attribute_value,
            )

        except Exception:

            pass

    # ======================================================
    # 18L â€” QBIT IDENTITY VALIDATION
    # ======================================================

    dialer_qbit = getattr(
        qbit_dialer,
        "qbit",
        None,
    )

    if (
        dialer_qbit is not None
        and dialer_qbit is not qbit_obj
    ):

        MODULES_STATUS[
            "QbitDialer"
        ] = False

        raise RuntimeError(
            "QbitDialer lost authoritative Qbit"
        )

    # ======================================================
    # 18M â€” QUEUE LOOP IDENTITY VALIDATION
    # ======================================================

    dialer_queue_loop = None

    for attribute_name in (
        "queue_loop",
        "qbit_loop",
        "qbit_queue_loop",
    ):

        candidate = getattr(
            qbit_dialer,
            attribute_name,
            None,
        )

        if candidate is not None:

            dialer_queue_loop = candidate
            break

    if (
        dialer_queue_loop is not None
        and dialer_queue_loop
        is not queue_loop_obj
    ):

        MODULES_STATUS[
            "QbitDialer"
        ] = False

        raise RuntimeError(
            "QbitDialer lost authoritative QbitQueueLoop"
        )

    # ======================================================
    # 18N â€” QBIT QUEUE CONTRACT VALIDATION
    # ======================================================
    #
    # qbit_queue must NEVER be the QueueLoop.
    #

    dialer_physical_queue = getattr(
        qbit_dialer,
        "qbit_queue",
        None,
    )

    if (
        dialer_physical_queue
        is queue_loop_obj
    ):

        MODULES_STATUS[
            "QbitDialer"
        ] = False

        raise RuntimeError(
            "QbitDialer.qbit_queue incorrectly "
            "references QbitQueueLoop"
        )

    # ======================================================
    # 18O â€” EVENTBUS IDENTITY VALIDATION
    # ======================================================

    dialer_event_bus = getattr(
        qbit_dialer,
        "event_bus",
        None,
    )

    if (
        dialer_event_bus is not None
        and dialer_event_bus
        is not event_bus_obj
    ):

        MODULES_STATUS[
            "QbitDialer"
        ] = False

        raise RuntimeError(
            "QbitDialer lost authoritative EventBus"
        )

    # ======================================================
    # 18P â€” KERNEL BUS ATTACHMENT
    # ======================================================

    if kernel_bus_obj is not None:

        try:

            bind_kernel = getattr(
                qbit_dialer,
                "bind_kernel_bus",
                None,
            )

            if callable(bind_kernel):

                safe_call(
                    bind_kernel,
                    kernel_bus_obj,
                    label="QbitDialer.bind_kernel_bus",
                )

        except Exception as exc:

            logger.debug(
                "[QbitDialer] "
                "KernelBus binding deferred | %s",
                exc,
            )

    # ======================================================
    # 18Q â€” REGISTER RECEIVE HANDLER
    # ======================================================

    #
    # Prefer the Dialer's existing registration API.
    # If none exists, retain qbit_receive_handler as the
    # Main3-side bridge.
    #

    receive_registration = None

    for method_name in (
        "set_receive_handler",
        "register_receive_handler",
        "bind_receive_handler",
        "set_qbit_receive_handler",
    ):

        method = getattr(
            qbit_dialer,
            method_name,
            None,
        )

        if callable(method):

            try:

                receive_registration = safe_call(
                    method,
                    qbit_receive_handler,
                    default=None,
                    label=(
                        "QbitDialer."
                        f"{method_name}"
                    ),
                )

            except Exception:

                receive_registration = None

            if receive_registration is not None:
                break

    # ======================================================
    # 18R â€” QBIT RECEIVE BRIDGE
    # ======================================================

    #
    # If the Dialer exposes a compatible receive target,
    # connect the handler without replacing it.
    #

    for attribute_name in (
        "receive_handler",
        "qbit_receive_handler",
        "on_qbit",
        "qbit_handler",
    ):

        try:

            current = getattr(
                qbit_dialer,
                attribute_name,
                None,
            )

            if current is None:

                setattr(
                    qbit_dialer,
                    attribute_name,
                    qbit_receive_handler,
                )

        except Exception:

            continue

    # ======================================================
    # 18S â€” PUBLISH AUTHORITATIVE DIALER
    # ======================================================

    globals()[
        "qbit_dialer"
    ] = qbit_dialer

    # ==========================================================
    # ACTIONENGINE LATE-BIND
    # ==========================================================

    action_engine_obj = globals().get("action_engine")

    if action_engine_obj is not None:

        late_bind = getattr(
            qbit_dialer,
            "_bind_late_dependencies",
            None,
        )

        if not callable(late_bind):
            raise RuntimeError(
                "QbitDialer cannot late-bind ActionEngine"
            )
 
        late_bind(
            action_engine=action_engine_obj,
        )

        if getattr(qbit_dialer, "action_engine", None) is not action_engine_obj:
            raise RuntimeError(
                "QbitDialer ActionEngine identity mismatch"
            )

    # ======================================================
    # 18T â€” START AUTHORITATIVE DIALER
    # ======================================================
    #
    # Synchronization is NOT the same thing as RUNNING.
    #
    # Start the already-created Dialer.
    #
    # NEVER:
    # - create another QueueLoop
    # - create another asyncio runtime
    # - create another Qbit
    #
    # The Dialer's own start lifecycle remains authoritative.
    #

    # ======================================================
    # SYSTEM HANDLERS
    # Register bounded handlers into the existing Dialer.
    # ======================================================
    try:
        from seed.core.handlers.system_handlers import (
            get_system_handlers,
            bind_seed_identity,
        )
        bind_seed_identity(ensure_seed_identity(SEED_ROOT))
        register_handler = getattr(qbit_dialer, "register_command_capability", None)
        for handler_name, handler in get_system_handlers().items():
            if callable(register_handler):
                register_handler(handler_name, handler, system="SystemHandlers", source="SYSTEM", metadata={"module": "seed.core.handlers.system_handlers"})
            else:
                qbit_dialer.command_registry[handler_name] = handler
        MODULES_STATUS["SystemHandlers"] = True
        boot_log("SystemHandlers registered into authoritative QbitDialer")

        # --------------------------------------------------
        # AUTONOMOUS DEVELOPMENT TASK COMMANDS
        # --------------------------------------------------
        try:
            from seed.core.handlers.command_tasks import (
                get_command_task_handlers,
                bind_runtime as bind_command_tasks,
            )
            from seed.sandbox.seed_tictactoe import SeedTicTacToe
            seed_ttt = SeedTicTacToe(dialer=qbit_dialer, event_bus=event_bus)
            bind_command_tasks(
                hud_reader=globals().get("hud_reader"),
                ttt=seed_ttt,
                registry=registry,
                oracle=ORACLE or oracle,
            )
            for task_name, task_handler in get_command_task_handlers().items():
                if callable(register_handler):
                    register_handler(
                        task_name,
                        task_handler,
                        system="AutonomousTasks",
                        source="SEED_CORE",
                        metadata={
                            "module": "seed.core.handlers.command_tasks",
                            "command_type": "TASK",
                            "bounded": True,
                        },
                    )
            MODULES_STATUS["AutonomousTaskCommands"] = True
            MODULES_STATUS["SeedTicTacToe"] = True

            # Cognitive ingress: FATHUD/user -> submit_command(ASK_SEED)
            # -> new task Qbit -> ComputeBrain -> TransformerBrain.
            ask_seed = getattr(qbit_dialer, "_cmd_ask_seed", None)
            if callable(register_handler) and callable(ask_seed):
                register_handler(
                    "ASK_SEED",
                    ask_seed,
                    system="Cognition",
                    source="SEED_CORE",
                    metadata={
                        "module": "seed.core.dialers.qbit_dialer",
                        "command_type": "COGNITIVE_INPUT",
                        "bounded": True,
                        "executes_commands": False,
                    },
                )
                MODULES_STATUS["ASK_SEED"] = True

            boot_log(
                "Autonomous task commands registered | FULL_SYSTEM_CHECK | IDLE_READ | SANDBOX_TICTACTOE | ASK_SEED"
            )
        except Exception as task_exc:
            MODULES_STATUS["AutonomousTaskCommands"] = False
            MODULES_STATUS["SeedTicTacToe"] = False
            boot_warn(f"Autonomous task registration deferred | {type(task_exc).__name__}: {task_exc}")

    except Exception as exc:
        MODULES_STATUS["SystemHandlers"] = False
        boot_warn(f"SystemHandlers registration deferred | {type(exc).__name__}: {exc}")

    # ------------------------------------------------------
    # CONSTRUCTION-ONLY MODE
    # ------------------------------------------------------
    # Phase 5 must not activate the Dialer before Registry,
    # TrackSystem, Cognition, and ActionEngine exist.
    if not start_runtime:
        MODULES_STATUS["QbitDialer"] = True
        boot_log("QbitDialer constructed/bound | runtime activation deferred")
        return qbit_dialer

    async def _start_dialer_lifecycle():

        # --------------------------------------------------
        # Determine current state.
        # --------------------------------------------------

        def _is_running():

            for attribute_name in (
                "running",
                "_running",
                "qbit_running",
                "_qbit_running",
            ):

                try:

                    value = getattr(
                        qbit_dialer,
                        attribute_name,
                        None,
                    )

                except Exception:

                    value = None

                if value is True:
                    return True

            for method_name in (
                "is_running",
                "is_qbit_running",
            ):

                method = getattr(
                    qbit_dialer,
                    method_name,
                    None,
                )

                if callable(method):

                    try:

                        result = method()

                        if inspect.isawaitable(
                            result
                        ):

                            # Do not create another runtime
                            # loop here. This lifecycle is
                            # already running inside Main3.
                            return False

                        if result is True:
                            return True

                    except Exception:

                        continue

            for attribute_name in (
                "_runtime_state",
                "_qbit_runtime_state",
                "runtime_state",
                "state",
                "status",
            ):

                try:

                    value = getattr(
                        qbit_dialer,
                        attribute_name,
                        None,
                    )

                except Exception:

                    value = None

                if (
                    isinstance(value, str)
                    and value.upper()
                    == "RUNNING"
                ):

                    return True

            return False

        if _is_running():
            return True

        # --------------------------------------------------
        # Preferred normal Dialer lifecycle.
        # --------------------------------------------------

        start_method = getattr(
            qbit_dialer,
            "start",
            None,
        )

        if callable(start_method):

            logger.info(
                "[QbitDialer] "
                "Starting authoritative Dialer"
            )

            result = start_method()

            if inspect.isawaitable(
                result
            ):

                await result

            # ------------------------------------------------
            # start() is expected to establish the Dialer's
            # own running state. Verify instead of assuming.
            # ------------------------------------------------

            if _is_running():
                return True

        # --------------------------------------------------
        # Compatibility lifecycle.
        #
        # start_qbit_loop() is allowed only when the Dialer
        # implementation exposes it as its lifecycle entry.
        #
        # It must not create a second QueueLoop.
        # --------------------------------------------------

        start_qbit_loop = getattr(
            qbit_dialer,
            "start_qbit_loop",
            None,
        )

        if callable(start_qbit_loop):

            logger.info(
                "[QbitDialer] "
                "Starting authoritative Qbit lifecycle"
            )

            result = start_qbit_loop()

            if inspect.isawaitable(
                result
            ):

                await result

            if _is_running():
                return True

        return _is_running()

    try:

        dialer_running = (
            await _start_dialer_lifecycle()
        )

    except Exception as exc:

        MODULES_STATUS[
            "QbitDialer"
        ] = False

        logger.error(
            "[QbitDialer] "
            "authoritative start failed | %s",
            exc,
        )

        raise RuntimeError(
            "QbitDialer start failed"
        ) from exc

    if not dialer_running:

        MODULES_STATUS[
            "QbitDialer"
        ] = False

        logger.error(
            "[QbitDialer] "
            "synchronized but failed to reach RUNNING"
        )

        raise RuntimeError(
            "QbitDialer synchronized but is not RUNNING"
        )

    # ======================================================
    # 18U â€” MODULE STATUS
    # ======================================================

    MODULES_STATUS[
        "QbitDialer"
    ] = True

    # ======================================================
    # 18V â€” AUTHORITATIVE BOOT REPORT
    # ======================================================

    logger.info(
        "[QbitDialer] "
        "AUTHORITATIVE BRAIN RUNNING | "
        "dialer=%s | "
        "qbit=%s | "
        "queue_loop=%s | "
        "qbit_queue=%s | "
        "event_bus=%s | "
        "kernel_bus=%s",
        type(
            qbit_dialer
        ).__name__,
        type(
            qbit_obj
        ).__name__,
        type(
            queue_loop_obj
        ).__name__,
        (
            type(
                dialer_physical_queue
            ).__name__
            if dialer_physical_queue is not None
            else "NONE"
        ),
        type(
            event_bus_obj
        ).__name__,
        (
            type(kernel_bus_obj).__name__
            if kernel_bus_obj is not None
            else "NONE"
        ),
    )

    # ======================================================
    # 18W â€” EVENTBUS TELEMETRY
    # ======================================================

    try:

        result = event_emit(
            "QBIT_DIALER_AUTHORITY_ESTABLISHED",
            {
                "source": "main3",
                "authority": "QbitDialer",
                "state": "RUNNING",
                "qbit": type(
                    qbit_obj
                ).__name__,
                "queue_loop": type(
                    queue_loop_obj
                ).__name__,
                "qbit_queue": (
                    type(
                        dialer_physical_queue
                    ).__name__
                    if dialer_physical_queue is not None
                    else None
                ),
                "event_bus": type(
                    event_bus_obj
                ).__name__,
                "kernel_bus": (
                    type(kernel_bus_obj).__name__
                    if kernel_bus_obj is not None
                    else None
                ),
            },
        )

        #
        # This function is synchronous.
        # If EventBus.emit() returns an awaitable, do not
        # create another event loop here.
        #
        if inspect.isawaitable(
            result
        ):

            try:

                running_loop = (
                    asyncio.get_running_loop()
                )

                running_loop.create_task(
                    result
                )

            except RuntimeError:

                logger.debug(
                    "[QbitDialer] "
                    "async authority telemetry deferred"
                )

    except Exception as exc:

        logger.debug(
            "[QbitDialer] "
            "authority telemetry skipped | %s",
            exc,
        )

    # ======================================================
    # 18X - START AUTHORITATIVE KERNEL QBIT BUS
    #
    # KernelBus is transport only. It feeds the existing
    # QbitDialer receive path and never creates a Qbit or queue.
    # ======================================================

    if kernel_bus_obj is not None:

        try:
            global kernel_start_task

            kernel_bind = getattr(
                kernel_bus_obj,
                "bind_dialer",
                None,
            )
            if callable(kernel_bind):
                kernel_bind(qbit_dialer)

            kernel_start_task = kernel_bus_obj.start(
                qbit_dialer
            )

            qbit_dialer.qbit_kernel_bus = kernel_bus_obj
            qbit_dialer.kernel_bus = kernel_bus_obj

            MODULES_STATUS["QbitKernelBusRuntime"] = True

            logger.info(
                "[QbitKernelBus] RUNTIME ONLINE | "
                "dialer=%s | dispatcher=%s",
                type(qbit_dialer).__name__,
                bool(kernel_start_task),
            )

        except Exception as exc:

            MODULES_STATUS["QbitKernelBusRuntime"] = False

            logger.error(
                "[QbitKernelBus] runtime start failed | %s",
                exc,
            )

            raise RuntimeError(
                "QbitKernelBus runtime start failed"
            ) from exc

    return qbit_dialer


# ==========================================================
# SECTION 18 END
# ==========================================================
# ======================================================
# 19 â€” FATHUD ADAPTER BINDING
# ======================================================
#
# FATHUD IS AN OBSERVER / DEVELOPER INTERFACE.
#
# It receives authoritative runtime references.
# It does NOT become command authority.
#
# AUTHORITATIVE FATHUD CONNECTION:
#
# EventBus
# â”‚
# â”Œâ”€â”€â”€â”€â”¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
# â–¼    â–¼               â–¼
# Qbit  QueueLoop    QbitDialer
# â”‚
# â–¼
# SEEDCore
# â”‚
# â”Œâ”€â”€â”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”
# â–¼             â–¼
# KernelBus     TrackSystem
#
# FATHUDAdapter observes these systems.
#
# NEVER:
#
# - create a second FATHUDAdapter
# - create a second EventBus
# - create a second Qbit
# - create a second QbitQueueLoop
# - create a second QbitDialer
# - create a second KernelBus
# - create a second TrackSystem
# - create a second SEEDCore
#
# IMPORTANT:
#
# queue_loop = authoritative QbitQueueLoop
#
# qbit_queue may be a physical queue.Queue and is NOT
# automatically treated as the authoritative transport.
#
# This section does NOT start another FATHUD server.
#
# ======================================================


async def boot_fathud_adapter():

    global fathud_adapter

    boot_log(
        "PHASE 19 | FATHUD Adapter Binding"
    )

    # ==================================================
    # 19A â€” RESOLVE AUTHORITATIVE RUNTIME OBJECTS
    # ==================================================

    # --------------------------------------------------
    # EventBus
    # --------------------------------------------------

    event_bus_obj = globals().get(
        "event_bus",
        None,
    )

    if event_bus_obj is None:

        MODULES_STATUS[
            "QbitDialer"
        ] = False

        raise RuntimeError(
            "FATHUD binding requires authoritative EventBus"
        )

    # --------------------------------------------------
    # Qbit
    # --------------------------------------------------

    qbit_obj = globals().get(
        "qbit",
        None,
    )

    if qbit_obj is None:

        MODULES_STATUS[
            "QbitDialer"
        ] = False

        raise RuntimeError(
            "FATHUD binding requires authoritative Qbit"
        )

    # --------------------------------------------------
    # AUTHORITATIVE QbitQueueLoop
    #
    # NEVER substitute qbit_queue here.
    #
    # qbit_queue may be queue.Queue.
    # queue_loop is the runtime transport authority.
    # --------------------------------------------------

    authoritative_queue_loop = globals().get(
        "queue_loop",
        None,
    )

    if authoritative_queue_loop is None:

        authoritative_queue_loop = globals().get(
            "qbit_queue_loop",
            None,
        )

    if authoritative_queue_loop is None:

        MODULES_STATUS[
            "QbitDialer"
        ] = False

        raise RuntimeError(
            "FATHUD binding requires authoritative QbitQueueLoop"
        )

    # --------------------------------------------------
    # Reject an accidental physical queue as the
    # authoritative QueueLoop.
    # --------------------------------------------------

    queue_loop_type_name = type(
        authoritative_queue_loop
    ).__name__

    if (
        "QbitQueueLoop"
        not in queue_loop_type_name
    ):

        logger.error(
            "[FATHUD] "
            "authoritative queue_loop is not QbitQueueLoop | "
            "type=%s",
            queue_loop_type_name,
        )

        MODULES_STATUS[
            "QbitDialer"
        ] = False

        raise RuntimeError(
            "FATHUD binding received non-authoritative "
            "QbitQueueLoop object"
        )

    # --------------------------------------------------
    # QbitDialer
    # --------------------------------------------------

    qbit_dialer_obj = globals().get(
        "qbit_dialer",
        None,
    )

    if qbit_dialer_obj is None:

        MODULES_STATUS[
            "QbitDialer"
        ] = False

        raise RuntimeError(
            "FATHUD binding requires authoritative QbitDialer"
        )

    # --------------------------------------------------
    # SEEDCore
    #
    # Main3 may expose this under either name.
    # --------------------------------------------------

    seedcore_obj = globals().get(
        "seedcore",
        None,
    )

    if seedcore_obj is None:

        seedcore_obj = globals().get(
            "seed_core",
            None,
        )

    # --------------------------------------------------
    # KernelBus
    #
    # Optional at this point.
    # --------------------------------------------------

    kernel_bus_obj = globals().get(
        "kernel_bus",
        None,
    )

    # --------------------------------------------------
    # TrackSystem
    #
    # NEVER construct one here.
    # --------------------------------------------------

    track_system_obj = globals().get(
        "track_system",
        None,
    )

    # --------------------------------------------------
    # Registry / nodes
    #
    # These are optional FATHUD references.
    # --------------------------------------------------

    registry_obj = globals().get(
        "registry",
        None,
    )

    registry_runtime_obj = globals().get(
        "registry_runtime",
        None,
    )

    nodes_obj = globals().get(
        "nodes",
        None,
    )

    database_obj = globals().get(
        "database",
        None,
    )

    # ==================================================
    # 19B â€” EXISTING FATHUD RESOLUTION
    # ==================================================

    #
    # Reuse the exact existing adapter whenever possible.
    #
    # Never manufacture a second FATHUDAdapter.
    #

    fathud_obj = getattr(
        qbit_dialer_obj,
        "fathud",
        None,
    )

    if fathud_obj is None:

        fathud_obj = getattr(
            qbit_dialer_obj,
            "fat_layer",
            None,
        )

    if fathud_obj is None:

        fathud_obj = globals().get(
            "fathud_adapter",
            None,
        )

    # ==================================================
    # 19C â€” FATHUD ADAPTER CREATION
    # ==================================================

    if fathud_obj is None:

        try:

            from seed.ui.fat_hud_adapter import (
                FATHUDAdapter,
            )

        except Exception as exc:

            MODULES_STATUS[
                "QbitDialer"
            ] = False

            logger.error(
                "[FATHUD] "
                "FATHUDAdapter import failed | %s",
                exc,
            )

            raise RuntimeError(
                "FATHUDAdapter import failed"
            ) from exc

        # ----------------------------------------------
        # Constructor references.
        #
        # qbit_loop is the authoritative QueueLoop.
        #
        # qbit_queue is only supplied when the adapter
        # constructor explicitly supports it.
        # ----------------------------------------------

        fathud_kwargs = {
            "event_bus": event_bus_obj,
            "qbit": qbit_obj,
            "queue_loop": authoritative_queue_loop,
            "qbit_queue_loop": authoritative_queue_loop,
            "qbit_dialer": qbit_dialer_obj,
        }

        # Physical queue is optional and only passed if
        # one actually exists separately.
        physical_qbit_queue = globals().get(
            "qbit_queue",
            None,
        )

        if (
            physical_qbit_queue is not None
            and physical_qbit_queue is not authoritative_queue_loop
        ):
            fathud_kwargs[
                "qbit_queue"
            ] = physical_qbit_queue

        if seedcore_obj is not None:

            fathud_kwargs[
                "seedcore"
            ] = seedcore_obj

        if kernel_bus_obj is not None:

            fathud_kwargs[
                "kernel_bus"
            ] = kernel_bus_obj

        if track_system_obj is not None:

            fathud_kwargs[
                "track_system"
            ] = track_system_obj

        if registry_obj is not None:

            fathud_kwargs[
                "registry"
            ] = registry_obj

        if registry_runtime_obj is not None:

            fathud_kwargs[
                "registry_runtime"
            ] = registry_runtime_obj

        if nodes_obj is not None:

            fathud_kwargs[
                "nodes"
            ] = nodes_obj

        if database_obj is not None:

            fathud_kwargs[
                "database"
            ] = database_obj

        # ----------------------------------------------
        # Constructor compatibility filtering.
        # ----------------------------------------------

        try:

            filtered_fathud_kwargs = (
                filter_constructor_kwargs(
                    FATHUDAdapter,
                    fathud_kwargs,
                )
            )

        except Exception:

            filtered_fathud_kwargs = (
                fathud_kwargs
            )

        try:

            fathud_obj = FATHUDAdapter(
                **filtered_fathud_kwargs
            )

        except Exception as exc:

            MODULES_STATUS[
                "QbitDialer"
            ] = False

            logger.error(
                "[FATHUD] "
                "adapter creation failed | %s",
                exc,
            )

            raise RuntimeError(
                "QbitDialer FATHUD binding failed"
            ) from exc

    # ==================================================
    # 19D â€” CALLABLE KWARG COMPATIBILITY HELPER
    # ==================================================

    def _filter_callable_kwargs(
        callable_obj,
        kwargs,
    ):

        if not callable(
            callable_obj
        ):

            return {}

        try:

            signature = inspect.signature(
                callable_obj
            )

        except Exception:

            return kwargs

        parameters = signature.parameters

        # --------------------------------------------------
        # If the callable accepts **kwargs, preserve all
        # non-None authoritative references.
        # --------------------------------------------------

        accepts_var_kwargs = any(
            parameter.kind
            == inspect.Parameter.VAR_KEYWORD
            for parameter in parameters.values()
        )

        if accepts_var_kwargs:

            return {
                key: value
                for key, value in kwargs.items()
                if value is not None
            }

        # --------------------------------------------------
        # Otherwise only pass supported parameters.
        # --------------------------------------------------

        return {
            key: value
            for key, value in kwargs.items()
            if (
                value is not None
                and key in parameters
            )
        }

    # ==================================================
    # 19E â€” AUTHORITATIVE FATHUD REFERENCE SET
    # ==================================================

    fathud_bindings = {
        "event_bus": event_bus_obj,
        "qbit": qbit_obj,
        "qbit_loop": authoritative_queue_loop,
        "dialer": qbit_dialer_obj,
    }

    physical_qbit_queue = globals().get(
        "qbit_queue",
        None,
    )

    if (
        physical_qbit_queue is not None
        and physical_qbit_queue is not authoritative_queue_loop
    ):

        fathud_bindings[
            "qbit_queue"
        ] = physical_qbit_queue

    if seedcore_obj is not None:

        fathud_bindings[
            "seedcore"
        ] = seedcore_obj

    if kernel_bus_obj is not None:

        fathud_bindings[
            "kernel_bus"
        ] = kernel_bus_obj

    if track_system_obj is not None:

        fathud_bindings[
            "track_system"
        ] = track_system_obj

    if registry_obj is not None:

        fathud_bindings[
            "registry"
        ] = registry_obj

    if registry_runtime_obj is not None:

        fathud_bindings[
            "registry_runtime"
        ] = registry_runtime_obj

    if nodes_obj is not None:

        fathud_bindings[
            "nodes"
        ] = nodes_obj

    # ==================================================
    # 19F â€” FATHUD bind()
    # ==================================================

    bind_method = getattr(
        fathud_obj,
        "bind",
        None,
    )

    if callable(
        bind_method
    ):

        try:

            filtered_bindings = (
                _filter_callable_kwargs(
                    bind_method,
                    fathud_bindings,
                )
            )

            bind_result = bind_method(
                **filtered_bindings
            )

            if inspect.isawaitable(
                bind_result
            ):

                await bind_result

        except Exception as exc:

            logger.warning(
                "[FATHUD] "
                "bind() unavailable/failed; "
                "using direct authoritative attachment | %s",
                exc,
            )

    # ==================================================
    # 19G â€” DIRECT AUTHORITATIVE ATTRIBUTE FALLBACK
    # ==================================================

    #
    # Direct attributes are only used when the adapter
    # exposes them. We never create competing objects.
    #

    direct_bindings = {
        "event_bus": event_bus_obj,
        "qbit": qbit_obj,
        "qbit_loop": authoritative_queue_loop,
        "dialer": qbit_dialer_obj,
    }

    # qbit_queue is physical transport only.
    if (
        physical_qbit_queue is not None
        and physical_qbit_queue is not authoritative_queue_loop
    ):

        direct_bindings[
            "qbit_queue"
        ] = physical_qbit_queue

    if seedcore_obj is not None:

        direct_bindings[
            "seedcore"
        ] = seedcore_obj

    if kernel_bus_obj is not None:

        direct_bindings[
            "kernel_bus"
        ] = kernel_bus_obj

    if track_system_obj is not None:

        direct_bindings[
            "track_system"
        ] = track_system_obj

    if registry_obj is not None:

        direct_bindings[
            "registry"
        ] = registry_obj

    if registry_runtime_obj is not None:

        direct_bindings[
            "registry_runtime"
        ] = registry_runtime_obj

    if nodes_obj is not None:

        direct_bindings[
            "nodes"
        ] = nodes_obj

    for (
        attribute_name,
        attribute_value,
    ) in direct_bindings.items():

        if attribute_value is None:

            continue

        try:

            # Only set when the adapter already exposes
            # the attribute or permits normal assignment.
            if hasattr(
                fathud_obj,
                attribute_name,
            ):

                setattr(
                    fathud_obj,
                    attribute_name,
                    attribute_value,
                )

        except Exception as exc:

            logger.debug(
                "[FATHUD] "
                "direct attribute binding skipped | "
                "attribute=%s | error=%s",
                attribute_name,
                exc,
            )

    # ==================================================
    # 19H â€” attach_systems() COMPATIBILITY
    # ==================================================

    attach_systems = getattr(
        fathud_obj,
        "attach_systems",
        None,
    )

    if callable(
        attach_systems
    ):

        attach_kwargs = {
            "event_bus": event_bus_obj,
            "qbit": qbit_obj,
            "qbit_loop": authoritative_queue_loop,
            "dialer": qbit_dialer_obj,
        }

        if (
            physical_qbit_queue is not None
            and physical_qbit_queue is not authoritative_queue_loop
        ):

            attach_kwargs[
                "qbit_queue"
            ] = physical_qbit_queue

        if seedcore_obj is not None:

            # Canonical current name.
            attach_kwargs[
                "seedcore"
            ] = seedcore_obj

        if kernel_bus_obj is not None:

            attach_kwargs[
                "kernel_bus"
            ] = kernel_bus_obj

        if track_system_obj is not None:

            attach_kwargs[
                "track_system"
            ] = track_system_obj

        if registry_obj is not None:

            attach_kwargs[
                "registry"
            ] = registry_obj

        if registry_runtime_obj is not None:

            attach_kwargs[
                "registry_runtime"
            ] = registry_runtime_obj

        if nodes_obj is not None:

            attach_kwargs[
                "nodes"
            ] = nodes_obj

        try:

            filtered_attach_kwargs = (
                _filter_callable_kwargs(
                    attach_systems,
                    attach_kwargs,
                )
            )

            attach_result = attach_systems(
                **filtered_attach_kwargs
            )

            if inspect.isawaitable(
                attach_result
            ):

                await attach_result

        except Exception as exc:

            #
            # Do not repeatedly call an incompatible
            # attach_systems() method.
            #
            # Direct authoritative attributes above
            # remain the compatibility path.
            #

            logger.warning(
                "[FATHUD] "
                "attach_systems compatibility fallback | %s",
                exc,
            )

    # ==================================================
    # 19I â€” STORE THE EXACT SAME FATHUD OBJECT
    # ==================================================

    #
    # All Main3 references must point to this one object.
    #

    try:

        qbit_dialer_obj.fathud = (
            fathud_obj
        )

    except Exception as exc:

        logger.error(
            "[FATHUD] "
            "unable to store fathud on QbitDialer | %s",
            exc,
        )

        MODULES_STATUS[
            "QbitDialer"
        ] = False

        raise RuntimeError(
            "Unable to attach FATHUD to QbitDialer"
        ) from exc

    try:

        qbit_dialer_obj.fat_layer = (
            fathud_obj
        )

    except Exception:
        pass

    # --------------------------------------------------
    # Main3-level authoritative reference.
    # --------------------------------------------------

    fathud_adapter = fathud_obj

    try:

        globals()[
            "fathud_adapter"
        ] = fathud_obj

    except Exception:
        pass

    # ==================================================
    # 19J â€” FATHUD IDENTITY VALIDATION
    # ==================================================

    if getattr(
        qbit_dialer_obj,
        "fathud",
        None,
    ) is not fathud_obj:

        MODULES_STATUS[
            "QbitDialer"
        ] = False

        raise RuntimeError(
            "QbitDialer FATHUD identity validation failed"
        )

    if getattr(
        qbit_dialer_obj,
        "fat_layer",
        None,
    ) is not fathud_obj:

        MODULES_STATUS[
            "QbitDialer"
        ] = False

        raise RuntimeError(
            "QbitDialer FATHUD/FAT layer identity mismatch"
        )

    # --------------------------------------------------
    # EventBus identity
    # --------------------------------------------------

    fathud_bus = getattr(
        fathud_obj,
        "event_bus",
        None,
    )

    if (
        fathud_bus is not None
        and fathud_bus is not event_bus_obj
    ):

        MODULES_STATUS[
            "QbitDialer"
        ] = False

        raise RuntimeError(
            "FATHUD lost authoritative EventBus"
        )

    # --------------------------------------------------
    # Qbit identity
    # --------------------------------------------------

    fathud_qbit = getattr(
        fathud_obj,
        "qbit",
        None,
    )

    if (
        fathud_qbit is not None
        and fathud_qbit is not qbit_obj
    ):

        MODULES_STATUS[
            "QbitDialer"
        ] = False

        raise RuntimeError(
            "FATHUD lost authoritative Qbit"
        )

    # --------------------------------------------------
    # QueueLoop identity
    #
    # Check QueueLoop-specific attributes FIRST.
    #
    # qbit_queue is intentionally NOT treated as the
    # authoritative QueueLoop because it may be a
    # physical queue.Queue.
    # --------------------------------------------------

    fathud_queue_loop = None

    for queue_attribute in (
        "qbit_loop",
        "queue_loop",
        "qbit_queue_loop",
    ):

        candidate = getattr(
            fathud_obj,
            queue_attribute,
            None,
        )

        if candidate is not None:

            fathud_queue_loop = candidate
            break

    if (
        fathud_queue_loop is not None
        and fathud_queue_loop
        is not authoritative_queue_loop
    ):

        MODULES_STATUS[
            "QbitDialer"
        ] = False

        raise RuntimeError(
            "FATHUD lost authoritative QbitQueueLoop"
        )

    # --------------------------------------------------
    # If FATHUD exposes qbit_queue separately, make sure
    # it was not accidentally replaced by the QueueLoop.
    # --------------------------------------------------

    fathud_physical_queue = getattr(
        fathud_obj,
        "qbit_queue",
        None,
    )

    if (
        physical_qbit_queue is not None
        and fathud_physical_queue is not None
        and fathud_physical_queue
        is not physical_qbit_queue
        and fathud_physical_queue
        is not authoritative_queue_loop
    ):

        logger.warning(
            "[FATHUD] "
            "qbit_queue differs from known physical queue | "
            "adapter=%s | expected=%s",
            type(
                fathud_physical_queue
            ).__name__,
            type(
                physical_qbit_queue
            ).__name__,
        )

    # --------------------------------------------------
    # Dialer identity
    # --------------------------------------------------

    fathud_dialer = getattr(
        fathud_obj,
        "dialer",
        None,
    )

    if (
        fathud_dialer is not None
        and fathud_dialer
        is not qbit_dialer_obj
    ):

        MODULES_STATUS[
            "QbitDialer"
        ] = False

        raise RuntimeError(
            "FATHUD lost authoritative QbitDialer"
        )

    # ==================================================
    # 19K â€” SEEDCORE IDENTITY VALIDATION
    # ==================================================

    if seedcore_obj is not None:

        fathud_seedcore = getattr(
            fathud_obj,
            "seedcore",
            None,
        )

        if fathud_seedcore is None:

            fathud_seedcore = getattr(
                fathud_obj,
                "seed_core",
                None,
            )

        if (
            fathud_seedcore is not None
            and fathud_seedcore
            is not seedcore_obj
        ):

            MODULES_STATUS[
                "QbitDialer"
            ] = False

            raise RuntimeError(
                "FATHUD lost authoritative SEEDCore"
            )

    # ==================================================
    # 19L â€” KERNEL BUS IDENTITY VALIDATION
    # ==================================================

    if kernel_bus_obj is not None:

        fathud_kernel = getattr(
            fathud_obj,
            "kernel_bus",
            None,
        )

        if (
            fathud_kernel is not None
            and fathud_kernel
            is not kernel_bus_obj
        ):

            MODULES_STATUS[
                "QbitDialer"
            ] = False

            raise RuntimeError(
                "FATHUD lost authoritative KernelBus"
            )

    # ==================================================
    # 19M â€” TRACKSYSTEM IDENTITY VALIDATION
    # ==================================================

    if track_system_obj is not None:

        fathud_track_system = getattr(
            fathud_obj,
            "track_system",
            None,
        )

        if (
            fathud_track_system is not None
            and fathud_track_system
            is not track_system_obj
        ):

            MODULES_STATUS[
                "QbitDialer"
            ] = False

            raise RuntimeError(
                "FATHUD lost authoritative TrackSystem"
            )

    # ==================================================
    # 19N â€” FINAL FATHUD AUTHORITY VALIDATION
    # ==================================================

    MODULES_STATUS[
        "FATHUDAdapter"
    ] = True

    logger.info(
        "[QbitDialer] FATHUD authority validated | "
        "fathud=%s | "
        "dialer=%s | "
        "qbit=%s | "
        "queue_loop=%s | "
        "seedcore=%s | "
        "kernel_bus=%s | "
        "track_system=%s",
        type(
            fathud_obj
        ).__name__,
        type(
            qbit_dialer_obj
        ).__name__,
        type(
            qbit_obj
        ).__name__,
        type(
            authoritative_queue_loop
        ).__name__,
        (
            type(seedcore_obj).__name__
            if seedcore_obj is not None
            else "NONE"
        ),
        (
            type(kernel_bus_obj).__name__
            if kernel_bus_obj is not None
            else "NONE"
        ),
        (
            type(track_system_obj).__name__
            if track_system_obj is not None
            else "NONE"
        ),
    )

    # ==================================================
    # 19O â€” TELEMETRY
    # ==================================================

    emit = getattr(
        event_bus_obj,
        "emit",
        None,
    )

    if callable(
        emit
    ):

        try:

            result = emit(
                "FATHUD_RUNTIME_ATTACHED",
                {
                    "source": "main3",
                    "authority": "QbitDialer",
                    "observer": "FATHUDAdapter",
                    "event_bus": type(
                        event_bus_obj
                    ).__name__,
                    "qbit": type(
                        qbit_obj
                    ).__name__,
                    "queue_loop": type(
                        authoritative_queue_loop
                    ).__name__,
                    "dialer": type(
                        qbit_dialer_obj
                    ).__name__,
                    "seedcore": (
                        type(seedcore_obj).__name__
                        if seedcore_obj is not None
                        else None
                    ),
                    "kernel_bus": (
                        type(kernel_bus_obj).__name__
                        if kernel_bus_obj is not None
                        else None
                    ),
                    "track_system": (
                        type(track_system_obj).__name__
                        if track_system_obj is not None
                        else None
                    ),
                },
            )

            if inspect.isawaitable(
                result
            ):

                await result

        except Exception as exc:

            logger.debug(
                "[FATHUD] "
                "runtime telemetry emission skipped | %s",
                exc,
            )

    return fathud_obj


# ==========================================================
# SECTION 18B â€” KERNEL / REGISTRY LINK
# PURPOSE: Restore SRegistry and publish the one QbitDialer instance.
# ==========================================================

def boot_registry_link():
    global system_registry
    try:
        from SRegistry import register_node, SEED_KERNEL_REGISTRY
        register_node(
            name="QbitDialer",
            path=Path(SEED_ROOT) / "seed" / "core" / "dialers" / "qbit_dialer.py",
            role="service",
        )
        system_registry = SEED_KERNEL_REGISTRY
        try:
            SEED_KERNEL_REGISTRY.setdefault("services", {})["QbitDialer"] = qbit_dialer
        except Exception:
            pass
        MODULES_STATUS["SRegistry"] = True
        boot_log("SRegistry QbitDialer registration ONLINE")
        return system_registry
    except Exception as exc:
        MODULES_STATUS["SRegistry"] = False; trace_exception(exc); return None


# ==========================================================
# SECTION 19 â€” HEARTBEAT / HEART
# ==========================================================

def boot_heartbeat():
    global heartbeat

    boot_log(
        "PHASE 06 | HeartbeatEmitter / HEART"
    )

    try:

        from seed.core.emitters.heartbeatemitter import (
            HeartbeatEmitter,
        )

        heartbeat = compatible_construct(
            HeartbeatEmitter,
            [
                (
                    (),
                    {
                        "emit": getattr(
                            event_bus,
                            "emit",
                            safe_emit,
                        ),
                        "event_bus": event_bus,
                        "interval": 3.0,
                        "qbit_dialer": qbit_dialer,
                        "kernel_bus": kernel_bus,
                        "module_name": "core_heartbeat",
                    },
                ),
                (
                    (),
                    {
                        "event_bus": event_bus,
                        "qbit_dialer": qbit_dialer,
                        "interval": 3.0,
                    },
                ),
                (
                    (),
                    {},
                ),
            ],
            "HeartbeatEmitter",
        )

        if heartbeat is None:
            raise RuntimeError(
                "HeartbeatEmitter initialization failed"
            )

        MODULES_STATUS[
            "HeartbeatEmitter"
        ] = True

        boot_log(
            "HeartbeatEmitter HEART ONLINE"
        )

        attach_queue = getattr(
            heartbeat,
            "attach_queue_loop",
            None,
        )

        if callable(attach_queue):
            safe_call(
                attach_queue,
                queue_loop,
                label="Heartbeat.attach_queue_loop",
            )

        attach_dialer = getattr(
            heartbeat,
            "attach_qbit_dialer",
            None,
        )

        if callable(attach_dialer):
            safe_call(
                attach_dialer,
                qbit_dialer,
                label="Heartbeat.attach_qbit_dialer",
            )

        if qbit_dialer is not None:
            try:
                qbit_dialer.heartbeatemitter = heartbeat
            except Exception:
                pass

        boot_log(
            "Heartbeat â†” QbitDialer attachment COMPLETE"
        )

        return heartbeat

    except Exception as exc:

        MODULES_STATUS[
            "HeartbeatEmitter"
        ] = False

        trace_exception(exc)

        raise


# ==========================================================
# SECTION 20 â€” TRACK SYSTEM
# ==========================================================

def boot_track_system():
    global track_system
    global track_context

    boot_log(
        "PHASE 07 | TrackSystem"
    )

    try:

        from seed.core.track_system import TrackSystem

        try:
            from seed.core.track_context import (
                TrackContext as _TrackContext
            )
        except Exception:
            from seed.core.track_system import (
                TrackContext as _TrackContext
            )

        # --------------------------------------------------
        # AUTHORITATIVE EXISTING SYSTEM REFERENCES
        #
        # DO NOT construct replacements here.
        # --------------------------------------------------

        authoritative_event_bus = globals().get(
            "event_bus",
            None,
        )

        authoritative_qbit = globals().get(
            "qbit",
            None,
        )

        authoritative_queue_loop = globals().get(
            "queue_loop",
            None,
        )

        authoritative_dialer = globals().get(
            "qbit_dialer",
            None,
        )

        # --------------------------------------------------
        # REGISTRY
        #
        # Main3 has historically used both:
        #
        #   system_registry
        #   registry
        #
        # TrackSystem must receive the already-existing
        # authoritative registry. Never construct one here.
        # --------------------------------------------------

        authoritative_registry = globals().get(
            "system_registry",
            None,
        )

        if authoritative_registry is None:
            authoritative_registry = globals().get(
                "registry",
                None,
            )

        # --------------------------------------------------
        # OPTIONAL AUTHORITATIVE SYSTEMS
        # --------------------------------------------------

        authoritative_compute_brain = globals().get(
            "computebrain",
            None,
        )

        if authoritative_compute_brain is None:
            authoritative_compute_brain = globals().get(
                "compute_brain",
                None,
            )

        authoritative_transformer_brain = globals().get(
            "transformerbrain",
            None,
        )

        if authoritative_transformer_brain is None:
            authoritative_transformer_brain = globals().get(
                "transformer_brain",
                None,
            )

        authoritative_neural_bridge = globals().get(
            "neural_bridge",
            None,
        )

        authoritative_fathud = globals().get(
            "fathud",
            None,
        )

        authoritative_fat_layer = globals().get(
            "fat_layer",
            None,
        )

        authoritative_kernel_bus = globals().get(
            "kernel_bus",
            None,
        )

        authoritative_seedcore = globals().get(
            "seedcore",
            None,
        )

        if authoritative_seedcore is None:
            authoritative_seedcore = globals().get(
                "seed_core",
                None,
            )

        # --------------------------------------------------
        # AUTHORITATIVE FATHUD
        #
        # FATHUD belongs to the existing QbitDialer runtime.
        # Never construct a second adapter here.
        # --------------------------------------------------

        if authoritative_fathud is None and (
            authoritative_dialer is not None
        ):
            authoritative_fathud = getattr(
                authoritative_dialer,
                "fathud",
                None,
            )

        if authoritative_fat_layer is None and (
            authoritative_dialer is not None
        ):
            authoritative_fat_layer = getattr(
                authoritative_dialer,
                "fat_layer",
                None,
            )

        # --------------------------------------------------
        # REQUIRED AUTHORITATIVE DEPENDENCIES
        # --------------------------------------------------

        if authoritative_event_bus is None:
            raise RuntimeError(
                "Authoritative EventBus is unavailable"
            )

        if authoritative_qbit is None:
            raise RuntimeError(
                "Authoritative Qbit is unavailable"
            )

        if authoritative_queue_loop is None:
            raise RuntimeError(
                "Authoritative QbitQueueLoop is unavailable"
            )

        if authoritative_dialer is None:
            raise RuntimeError(
                "Authoritative QbitDialer is unavailable"
            )

        if authoritative_registry is None:
            raise RuntimeError(
                "Authoritative system registry is unavailable"
            )

        # --------------------------------------------------
        # TRACK CONTEXT
        # --------------------------------------------------

        track_info = gen_track_id(
            prefix="MAIN"
        )

        track_id = track_info["track_id"]

        track_context = None

        setter = getattr(
            _TrackContext,
            "set",
            None,
        )

        if callable(setter):
            track_context = safe_call(
                setter,
                track_id,
                default=None,
                label="TrackContext.set",
            )

        if track_context is None:
            track_context = compatible_construct(
                _TrackContext,
                [
                    (
                        (),
                        {
                            "track_id": track_id,
                        },
                    ),
                    (
                        (track_id,),
                        {},
                    ),
                    (
                        (),
                        {},
                    ),
                ],
                "TrackContext",
            )

        if track_context is None:
            raise RuntimeError(
                "TrackContext initialization failed"
            )

        # --------------------------------------------------
        # AUTHORITATIVE TRACK SYSTEM CONSTRUCTION
        #
        # DO NOT use positional compatibility construction.
        #
        # TrackSystem receives the real existing:
        #
        #   EventBus
        #   Qbit
        #   FATHUD
        #   registry
        #
        # TrackSystem MUST NOT construct replacements.
        # --------------------------------------------------

        track_system = TrackSystem(
            storage_root=SEED_ROOT,
            event_bus=authoritative_event_bus,
            qbit=authoritative_qbit,
            fathud=authoritative_fathud,
            fat_layer=authoritative_fat_layer,
            registry=authoritative_registry,
            node_registry=authoritative_registry,
            encoder=globals().get("cognition_binary_encoder"),
        )

        if track_system is None:
            raise RuntimeError(
                "TrackSystem initialization failed"
            )

        # --------------------------------------------------
        # AUTHORITATIVE EVENTBUS VALIDATION
        # --------------------------------------------------

        bound_event_bus = getattr(
            track_system,
            "event_bus",
            None,
        )

        if callable(bound_event_bus):
            try:
                bound_event_bus = bound_event_bus()
            except Exception:
                bound_event_bus = None

        if bound_event_bus is None:
            bound_event_bus = getattr(
                track_system,
                "_event_bus",
                None,
            )

        if bound_event_bus is not authoritative_event_bus:
            raise RuntimeError(
                "TrackSystem did not bind the authoritative EventBus"
            )

        # --------------------------------------------------
        # AUTHORITATIVE QBIT VALIDATION
        # --------------------------------------------------

        bound_qbit = getattr(
            track_system,
            "qbit",
            None,
        )

        if callable(bound_qbit):
            try:
                bound_qbit = bound_qbit()
            except Exception:
                bound_qbit = None

        if bound_qbit is None:
            bound_qbit = getattr(
                track_system,
                "_qbit",
                None,
            )

        if bound_qbit is not authoritative_qbit:
            raise RuntimeError(
                "TrackSystem did not bind the authoritative Qbit"
            )

        # --------------------------------------------------
        # TRACK CONTEXT BINDING
        # --------------------------------------------------

        for method_name in (
            "set_track_context",
            "attach_track_context",
        ):
            method = getattr(
                track_system,
                method_name,
                None,
            )

            if callable(method):
                safe_call(
                    method,
                    track_context,
                    label=f"TrackSystem.{method_name}",
                )
                break

        try:
            track_system.track_context = track_context
        except Exception:
            pass

        # --------------------------------------------------
        # AUTHORITATIVE SYSTEM BINDING
        #
        # TrackSystem may expose bind_system() in the
        # lifecycle-aware implementation.
        #
        # Every object supplied here is already authoritative.
        # TrackSystem must not create replacements.
        # --------------------------------------------------

        bind_system = getattr(
            track_system,
            "bind_system",
            None,
        )

        if callable(bind_system):

            bind_kwargs = {
                "event_bus": authoritative_event_bus,
                "registry": authoritative_registry,
                "qbit": authoritative_qbit,
                "qbit_queue_loop": authoritative_queue_loop,
                "qbit_dialer": authoritative_dialer,
                "computebrain": authoritative_compute_brain,
                "transformerbrain": authoritative_transformer_brain,
                "neural_bridge": authoritative_neural_bridge,
                "fathud": authoritative_fathud,
                "fat_layer": authoritative_fat_layer,
                "kernel_bus": authoritative_kernel_bus,
                "seedcore": authoritative_seedcore,
            }

            # ----------------------------------------------
            # FILTER OPTIONAL ARGUMENTS AGAINST THE ACTUAL
            # METHOD SIGNATURE.
            # ----------------------------------------------

            try:
                import inspect

                signature = inspect.signature(
                    bind_system
                )

                parameters = signature.parameters

                accepts_kwargs = any(
                    parameter.kind
                    == inspect.Parameter.VAR_KEYWORD
                    for parameter in parameters.values()
                )

                if not accepts_kwargs:
                    bind_kwargs = {
                        key: value
                        for key, value in bind_kwargs.items()
                        if key in parameters
                    }

            except Exception:
                pass

            safe_call(
                bind_system,
                label="TrackSystem.bind_system",
                **bind_kwargs,
            )

        # --------------------------------------------------
        # DIRECT AUTHORITATIVE REFERENCES
        #
        # Only bind attributes that exist on the TrackSystem.
        # No replacement systems are created.
        # --------------------------------------------------

        direct_bindings = {
            "qbit_queue_loop": authoritative_queue_loop,
            "qbit_dialer": authoritative_dialer,
            "registry": authoritative_registry,
            "node_registry": authoritative_registry,
            "computebrain": authoritative_compute_brain,
            "transformerbrain": authoritative_transformer_brain,
            "neural_bridge": authoritative_neural_bridge,
            "fathud": authoritative_fathud,
            "fat_layer": authoritative_fat_layer,
            "kernel_bus": authoritative_kernel_bus,
            "seedcore": authoritative_seedcore,
        }

        for attribute_name, value in direct_bindings.items():

            if value is None:
                continue

            try:
                if hasattr(
                    track_system,
                    attribute_name,
                ):
                    setattr(
                        track_system,
                        attribute_name,
                        value,
                    )
            except Exception:
                pass

        # --------------------------------------------------
        # FATHUD TRACK SYSTEM BINDING
        #
        # TrackSystem is now authoritative, so pass the SAME
        # instance to the already-existing FATHUD adapter.
        #
        # Never construct another FATHUDAdapter here.
        # --------------------------------------------------

        if authoritative_fathud is not None:

            fathud_bind = getattr(
                authoritative_fathud,
                "bind",
                None,
            )

            if callable(fathud_bind):

                fathud_bind_kwargs = {
                    "event_bus": authoritative_event_bus,
                    "qbit": authoritative_qbit,
                    "qbit_queue_loop": authoritative_queue_loop,
                    "qbit_loop": authoritative_queue_loop,
                    "dialer": authoritative_dialer,
                    "track_system": track_system,
                    "kernel_bus": authoritative_kernel_bus,
                    "seedcore": authoritative_seedcore,
                }

                try:
                    import inspect

                    signature = inspect.signature(
                        fathud_bind
                    )

                    parameters = signature.parameters

                    accepts_kwargs = any(
                        parameter.kind
                        == inspect.Parameter.VAR_KEYWORD
                        for parameter in parameters.values()
                    )

                    if not accepts_kwargs:
                        fathud_bind_kwargs = {
                            key: value
                            for key, value
                            in fathud_bind_kwargs.items()
                            if key in parameters
                        }

                except Exception:
                    pass

                safe_call(
                    fathud_bind,
                    label="FATHUDAdapter.bind TrackSystem",
                    **fathud_bind_kwargs,
                )

            # ----------------------------------------------
            # Direct reference only when the adapter exposes
            # the corresponding attribute.
            # ----------------------------------------------

            try:
                if hasattr(
                    authoritative_fathud,
                    "track_system",
                ):
                    authoritative_fathud.track_system = (
                        track_system
                    )
            except Exception:
                pass

            try:
                if hasattr(
                    authoritative_fathud,
                    "kernel_bus",
                ):
                    authoritative_fathud.kernel_bus = (
                        authoritative_kernel_bus
                    )
            except Exception:
                pass

            try:
                if hasattr(
                    authoritative_fathud,
                    "seedcore",
                ):
                    authoritative_fathud.seedcore = (
                        authoritative_seedcore
                    )
            except Exception:
                pass

        # --------------------------------------------------
        # AUTHORITATIVE GLOBAL REFERENCE
        # --------------------------------------------------

        globals()["track_system"] = track_system
        globals()["track_context"] = track_context

        # Preserve the existing registry naming contract so
        # later Main3 sections can use either name safely.
        globals()["registry"] = authoritative_registry

        # --------------------------------------------------
        # FINAL IDENTITY CHECKS
        # --------------------------------------------------

        if globals().get(
            "track_system"
        ) is not track_system:
            raise RuntimeError(
                "TrackSystem global reference is not authoritative"
            )

        if getattr(
            track_system,
            "event_bus",
            None,
        ) is not authoritative_event_bus:
            raise RuntimeError(
                "TrackSystem EventBus identity validation failed"
            )

        if getattr(
            track_system,
            "qbit",
            None,
        ) is not authoritative_qbit:
            raise RuntimeError(
                "TrackSystem Qbit identity validation failed"
            )

        # --------------------------------------------------
        # STATUS
        # --------------------------------------------------

        MODULES_STATUS[
            "TrackSystem"
        ] = True

        boot_log(
            "TrackSystem ONLINE | "
            f"event_bus={type(authoritative_event_bus).__name__} | "
            f"qbit={type(authoritative_qbit).__name__} | "
            f"queue_loop={type(authoritative_queue_loop).__name__} | "
            f"registry={type(authoritative_registry).__name__} | "
            f"track_id={track_id} | "
            f"fathud={type(authoritative_fathud).__name__ if authoritative_fathud is not None else 'None'}"
        )

        return track_system

    except Exception as exc:

        track_system = None

        MODULES_STATUS[
            "TrackSystem"
        ] = False

        trace_exception(exc)

        return None

# ==========================================================
# SECTION 21 â€” FIVEG / DEVICE / MANAGERS
# ==========================================================

# ==========================================================
# SECTION 21 â€” SUPPORT MANAGERS
#
# PHASE 08
#
# PURPOSE:
#   Connect support managers to the ONE authoritative
#   runtime without allowing them to construct competing
#   EventBus / Qbit / QueueLoop / Dialer / Registry /
#   TrackSystem / Node systems.
#
# DATA FLOW:
#
#   SYSTEM / REGISTRY / NODES
#              â†“
#         TrackSystem
#              â†“
#          EventBus
#              â†“
#            Qbit
#              â†“
#       QbitQueueLoop
#              â†“
#         QbitDialer
#              â†“
#       SUPPORT MANAGERS
#              â†“
#         STATUS / TELEMETRY
#              â†“
#       EventBus / TrackSystem
#
# COMMAND FLOW:
#
#   Heartbeat
#       â†“
#      Qbit
#       â†“
#   QueueLoop
#       â†“
#   QbitDialer
#       â†“
#   authorized command path
#
# Support managers NEVER become command authority.
#
# ==========================================================

def boot_support_modules():

    global fiveg
    global device
    global device_manager
    global module_registry
    global intent_engine
    global agent_manager
    global action_engine
    global health_monitor

    boot_log(
        "PHASE 08 | Support Managers"
    )

    try:

        # ==================================================
        # AUTHORITATIVE RUNTIME REFERENCES
        #
        # Resolve from globals instead of importing systems
        # from one another.
        #
        # This is intentional circular-import protection.
        # ==================================================

        authoritative_event_bus = globals().get(
            "event_bus",
            None,
        )

        authoritative_qbit = globals().get(
            "qbit",
            None,
        )

        authoritative_queue_loop = globals().get(
            "queue_loop",
            None,
        )

        if authoritative_queue_loop is None:
            authoritative_queue_loop = globals().get(
                "qbit_queue_loop",
                None,
            )

        authoritative_dialer = globals().get(
            "qbit_dialer",
            None,
        )

        authoritative_track_system = globals().get(
            "track_system",
            None,
        )

        authoritative_track_context = globals().get(
            "track_context",
            None,
        )

        authoritative_seedcore = globals().get(
            "seedcore",
            None,
        )

        if authoritative_seedcore is None:
            authoritative_seedcore = globals().get(
                "seed_core",
                None,
            )

        authoritative_kernel_bus = globals().get(
            "kernel_bus",
            None,
        )

        authoritative_registry = globals().get(
            "system_registry",
            None,
        )

        if authoritative_registry is None:
            authoritative_registry = globals().get(
                "registry",
                None,
            )

        # --------------------------------------------------
        # NODE / NODE REGISTRY
        #
        # Never manufacture a node registry here.
        # --------------------------------------------------

        authoritative_nodes = globals().get(
            "nodes",
            None,
        )

        if authoritative_nodes is None:
            authoritative_nodes = globals().get(
                "node_registry",
                None,
            )

        # --------------------------------------------------
        # FATHUD
        #
        # Reuse the existing adapter from QbitDialer.
        # --------------------------------------------------

        authoritative_fathud = globals().get(
            "fathud",
            None,
        )

        authoritative_fat_layer = globals().get(
            "fat_layer",
            None,
        )

        if (
            authoritative_fathud is None
            and authoritative_dialer is not None
        ):
            authoritative_fathud = getattr(
                authoritative_dialer,
                "fathud",
                None,
            )

        if (
            authoritative_fat_layer is None
            and authoritative_dialer is not None
        ):
            authoritative_fat_layer = getattr(
                authoritative_dialer,
                "fat_layer",
                None,
            )

        # ==================================================
        # REQUIRED RUNTIME VALIDATION
        # ==================================================

        if authoritative_event_bus is None:
            raise RuntimeError(
                "Support Managers require authoritative EventBus"
            )

        if authoritative_qbit is None:
            raise RuntimeError(
                "Support Managers require authoritative Qbit"
            )

        if authoritative_queue_loop is None:
            raise RuntimeError(
                "Support Managers require authoritative QbitQueueLoop"
            )

        if authoritative_dialer is None:
            raise RuntimeError(
                "Support Managers require authoritative QbitDialer"
            )

        # ==================================================
        # SAFE DEPENDENCY ATTACHMENT HELPERS
        #
        # These helpers deliberately do not import managers
        # into each other.
        #
        # They attach already-existing runtime objects.
        # ==================================================

        def _attach(
            target,
            value,
            method_names,
            attribute_names=(),
            label="runtime attachment",
        ):

            if target is None or value is None:
                return False

            # ----------------------------------------------
            # Prefer explicit lifecycle API.
            # ----------------------------------------------

            for method_name in method_names:

                method = getattr(
                    target,
                    method_name,
                    None,
                )

                if callable(method):

                    result = safe_call(
                        method,
                        value,
                        default=None,
                        label=f"{label}.{method_name}",
                    )

                    if result is not None:
                        return True

                    # Method executed even when it returns None.
                    return True

            # ----------------------------------------------
            # Attribute fallback for older module versions.
            # ----------------------------------------------

            for attribute_name in attribute_names:

                try:

                    if hasattr(
                        target,
                        attribute_name,
                    ):

                        setattr(
                            target,
                            attribute_name,
                            value,
                        )

                        return True

                except Exception as exc:
                    trace_exception(exc)

            return False

        def _bind_system(
            target,
            dependencies,
            label,
        ):

            if target is None:
                return False

            bind_method = getattr(
                target,
                "bind_system",
                None,
            )

            if not callable(bind_method):
                return False

            # ----------------------------------------------
            # Filter kwargs against the ACTUAL method
            # signature. This prevents the exact class of
            # FATHUD/TrackSystem keyword mismatch errors that
            # previously occurred.
            # ----------------------------------------------

            bind_kwargs = {
                key: value
                for key, value in dependencies.items()
                if value is not None
            }

            try:

                import inspect

                signature = inspect.signature(
                    bind_method
                )

                parameters = signature.parameters

                accepts_kwargs = any(
                    parameter.kind
                    == inspect.Parameter.VAR_KEYWORD
                    for parameter in parameters.values()
                )

                if not accepts_kwargs:

                    bind_kwargs = {
                        key: value
                        for key, value in bind_kwargs.items()
                        if key in parameters
                    }

            except Exception:
                pass

            safe_call(
                bind_method,
                default=None,
                label=label,
                **bind_kwargs,
            )

            return True

        def _emit_status(
            component,
            status,
            **extra,
        ):

            payload = {
                "source": "boot_support_modules",
                "component": component,
                "status": status,
            }

            payload.update(extra)

            try:

                emitter = getattr(
                    authoritative_event_bus,
                    "emit",
                    None,
                )

                if callable(emitter):

                    # --------------------------------------
                    # Do not assume a particular EventBus
                    # signature.
                    # --------------------------------------

                    safe_call(
                        emitter,
                        "system_status",
                        payload,
                        default=None,
                        label=(
                            f"{component}.system_status"
                        ),
                    )

            except Exception:
                pass

            # ----------------------------------------------
            # TrackSystem is the state/track layer.
            # Let it receive status when its API supports it.
            # ----------------------------------------------

            if authoritative_track_system is not None:

                for method_name in (
                    "record_status",
                    "publish_status",
                    "update_status",
                    "track_status",
                ):

                    method = getattr(
                        authoritative_track_system,
                        method_name,
                        None,
                    )

                    if callable(method):

                        safe_call(
                            method,
                            payload,
                            default=None,
                            label=(
                                f"TrackSystem.{method_name}"
                            ),
                        )

                        break

        # ==================================================
        # REGISTRY / NODE DEPENDENCY CHAIN
        #
        # Establish these references BEFORE support managers.
        #
        # No support manager imports another manager to find
        # its dependencies.
        # ==================================================

        registry_dependencies = {
            "event_bus": authoritative_event_bus,
            "qbit": authoritative_qbit,
            "qbit_queue_loop": authoritative_queue_loop,
            "qbit_dialer": authoritative_dialer,
            "track_system": authoritative_track_system,
            "track_context": authoritative_track_context,
            "nodes": authoritative_nodes,
            "node_registry": authoritative_nodes,
            "registry": authoritative_registry,
            "system_registry": authoritative_registry,
            "seedcore": authoritative_seedcore,
            "kernel_bus": authoritative_kernel_bus,
            "fathud": authoritative_fathud,
            "fat_layer": authoritative_fat_layer,
        }

        # --------------------------------------------------
        # Registry receives runtime references if supported.
        # --------------------------------------------------

        if authoritative_registry is not None:

            _bind_system(
                authoritative_registry,
                registry_dependencies,
                "SystemRegistry.bind_system",
            )

            _attach(
                authoritative_registry,
                authoritative_event_bus,
                (
                    "attach_event_bus",
                    "bind_event_bus",
                ),
                (
                    "event_bus",
                    "_event_bus",
                ),
                "SystemRegistry",
            )

            _attach(
                authoritative_registry,
                authoritative_track_system,
                (
                    "attach_track_system",
                    "bind_track_system",
                ),
                (
                    "track_system",
                    "_track_system",
                ),
                "SystemRegistry",
            )

            _attach(
                authoritative_registry,
                authoritative_nodes,
                (
                    "attach_nodes",
                    "bind_nodes",
                    "attach_node_registry",
                    "bind_node_registry",
                ),
                (
                    "nodes",
                    "node_registry",
                    "_nodes",
                    "_node_registry",
                ),
                "SystemRegistry",
            )

        # --------------------------------------------------
        # Node registry receives the SAME system registry.
        # --------------------------------------------------

        if authoritative_nodes is not None:

            _bind_system(
                authoritative_nodes,
                registry_dependencies,
                "NodeRegistry.bind_system",
            )

            _attach(
                authoritative_nodes,
                authoritative_registry,
                (
                    "attach_registry",
                    "bind_registry",
                    "attach_system_registry",
                    "bind_system_registry",
                ),
                (
                    "registry",
                    "system_registry",
                    "_registry",
                    "_system_registry",
                ),
                "NodeRegistry",
            )

            _attach(
                authoritative_nodes,
                authoritative_event_bus,
                (
                    "attach_event_bus",
                    "bind_event_bus",
                ),
                (
                    "event_bus",
                    "_event_bus",
                ),
                "NodeRegistry",
            )

            _attach(
                authoritative_nodes,
                authoritative_track_system,
                (
                    "attach_track_system",
                    "bind_track_system",
                ),
                (
                    "track_system",
                    "_track_system",
                ),
                "NodeRegistry",
            )

        # ==================================================
        # FiveG
        # ==================================================

        try:

            from seed.systemutils.fiveg import FiveG

            fiveg = FiveG()

            MODULES_STATUS[
                "FiveG"
            ] = True

            boot_log(
                "FiveG initialized"
            )

        except Exception as exc:

            fiveg = None

            MODULES_STATUS[
                "FiveG"
            ] = False

            trace_exception(exc)

        # --------------------------------------------------
        # FiveG â†’ Dialer
        # --------------------------------------------------

        if fiveg is not None:

            _attach(
                authoritative_dialer,
                fiveg,
                (
                    "attach_fiveg",
                    "bind_fiveg",
                ),
                (
                    "fiveg",
                ),
                "QbitDialer",
            )

        # ==================================================
        # DEVICE
        # ==================================================

        try:

            from seed.core.device import Device

            device = Device()

            MODULES_STATUS[
                "Device"
            ] = True

            boot_log(
                "Device initialized"
            )

        except Exception as exc:

            device = None

            MODULES_STATUS[
                "Device"
            ] = False

            trace_exception(exc)

        # ==================================================
        # MODULE REGISTRY
        #
        # If a registry already exists, do not create another.
        # ==================================================

        try:

            from seed.core.module_registry import (
                ModuleRegistry
            )

            existing_module_registry = globals().get(
                "module_registry",
                None,
            )

            if existing_module_registry is not None:

                module_registry = (
                    existing_module_registry
                )

            else:

                module_registry = ModuleRegistry(
                    qbit=authoritative_qbit,
                    dialer=authoritative_dialer,
                    event_bus=authoritative_event_bus,
                    queue_loop=authoritative_queue_loop,
                    track_system=authoritative_track_system,
                    track_context=authoritative_track_context,
                    registry=authoritative_registry,
                    registry_runtime=globals().get("registry_runtime"),
                    node_registry=authoritative_nodes,
                    nodes=authoritative_nodes,
                    kernel_bus=authoritative_kernel_bus,
                    seedcore=authoritative_seedcore,
                    fathud=authoritative_fathud,
                )

            bind_module_registry = getattr(
                module_registry,
                "bind_runtime",
                None,
            )
            if callable(bind_module_registry):
                bind_module_registry(
                    qbit=authoritative_qbit,
                    dialer=authoritative_dialer,
                    queue_loop=authoritative_queue_loop,
                    event_bus=authoritative_event_bus,
                    track_system=authoritative_track_system,
                    track=authoritative_track_context,
                    track_context=authoritative_track_context,
                    seedcore=authoritative_seedcore,
                    registry=authoritative_registry,
                    registry_runtime=globals().get("registry_runtime"),
                    node_registry=authoritative_nodes,
                    nodes=authoritative_nodes,
                    kernel_bus=authoritative_kernel_bus,
                    neural_bridge=neural_bridge,
                    fathud=authoritative_fathud,
                )

            MODULES_STATUS[
                "ModuleRegistry"
            ] = module_registry is not None

            boot_log(
                "ModuleRegistry initialized | "
                f"type={type(module_registry).__name__}"
                if module_registry is not None
                else "ModuleRegistry unavailable"
            )

        except Exception as exc:

            module_registry = None

            MODULES_STATUS[
                "ModuleRegistry"
            ] = False

            trace_exception(exc)

        # ==================================================
        # SUPPORT DEPENDENCY GRAPH
        #
        # Managers are constructed in dependency order.
        #
        # They do NOT import one another at construction time.
        # ==================================================

        common_dependencies = {
            "event_bus": authoritative_event_bus,
            "qbit": authoritative_qbit,
            "qbit_queue_loop": authoritative_queue_loop,
            "qbit_dialer": authoritative_dialer,
            "heartbeat": globals().get(
                "heartbeat",
                None,
            ),
            "track_system": authoritative_track_system,
            "track_context": authoritative_track_context,
            "registry": authoritative_registry,
            "system_registry": authoritative_registry,
            "nodes": authoritative_nodes,
            "node_registry": authoritative_nodes,
            "seedcore": authoritative_seedcore,
            "kernel_bus": authoritative_kernel_bus,
            "fathud": authoritative_fathud,
            "fat_layer": authoritative_fat_layer,
            "emit": getattr(
                authoritative_event_bus,
                "emit",
                safe_emit,
            ),
        }

        # ==================================================
        # INTENT ENGINE
        # ==================================================

        try:

            from seed.core.intent_engine import IntentEngine

            intent_engine = compatible_construct(
                IntentEngine,
                [
                    (
                        (),
                        {
                            key: value
                            for key, value
                            in common_dependencies.items()
                            if value is not None
                        },
                    ),
                    (
                        (),
                        {
                            "event_bus":
                                authoritative_event_bus,
                            "qbit":
                                authoritative_qbit,
                        },
                    ),
                    (
                        (),
                        {
                            "event_bus":
                                authoritative_event_bus,
                        },
                    ),
                ],
                "IntentEngine",
            )

            if intent_engine is None:
                raise RuntimeError(
                    "IntentEngine construction failed"
                )

            MODULES_STATUS[
                "IntentEngine"
            ] = True

            # ----------------------------------------------
            # Runtime attachments.
            # ----------------------------------------------

        # ----------------------------------------------
        # AUTHORITATIVE RUNTIME BINDING
        #
        # Constructor compatibility may use a reduced
        # dependency set. Therefore the final runtime
        # binding is explicit and authoritative.
        #
        # This NEVER creates another QueueLoop.
        # It attaches the exact QueueLoop created by main3.
        # ----------------------------------------------

            bind_runtime = getattr(
                intent_engine,
                "bind_runtime",
                None,
            )

            if callable(bind_runtime):

                safe_call(
                    bind_runtime,
                    default=None,
                    label="IntentEngine.bind_runtime",
                    emit=common_dependencies["emit"],
                    event_bus=authoritative_event_bus,
                    qbit=authoritative_qbit,
                    qbit_queue_loop=authoritative_queue_loop,
                    qbit_dialer=authoritative_dialer,
                    track_system=authoritative_track_system,
                )

            else:

            # ------------------------------------------
            # Compatibility fallback for older versions.
            # ------------------------------------------

                _attach(
                    intent_engine,
                    authoritative_queue_loop,
                    (
                        "attach_qbit_queue_loop",
                        "bind_qbit_queue_loop",
                        "attach_queue_loop",
                        "bind_queue_loop",
                    ),
                    (
                        "queue_loop",
                        "qbit_queue_loop",
                    ),
                    "IntentEngine",
                )

                _attach(
                    intent_engine,
                    authoritative_event_bus,
                    (
                        "attach_event_bus",
                        "bind_event_bus",
                    ),
                    (
                        "event_bus",
                        "_event_bus",
                    ),
                    "IntentEngine",
                )

                _attach(
                    intent_engine,
                    authoritative_qbit,
                    (
                        "attach_qbit",
                        "bind_qbit",
                    ),
                    (
                        "qbit",
                        "_qbit",
                    ),
                    "IntentEngine",
                )

                _attach(
                    intent_engine,
                    authoritative_dialer,
                    (
                        "attach_qbit_dialer",
                        "bind_qbit_dialer",
                    ),
                    (
                        "qbit_dialer",
                        "_qbit_dialer",
                    ),
                    "IntentEngine",
                )

                _attach(
                    intent_engine,
                    authoritative_track_system,
                    (
                        "attach_track_system",
                        "bind_track_system",
                    ),
                    (
                        "track_system",
                        "_track_system",
                    ),
                    "IntentEngine",
                )

                _attach(
                    intent_engine,
                    authoritative_registry,
                    (
                        "attach_registry",
                        "bind_registry",
                    ),
                    (
                        "registry",
                        "system_registry",
                    ),
                    "IntentEngine",
                )

        # ----------------------------------------------
        # HARD IDENTITY VALIDATION
        #
        # IntentEngine MUST hold the exact authoritative
        # QueueLoop object. Never accept a replacement.
        # ----------------------------------------------

            bound_queue_loop = getattr(
                intent_engine,
                "queue_loop",
                None,
            )

            if bound_queue_loop is None:

                bound_queue_loop = getattr(
                    intent_engine,
                    "qbit_queue_loop",
                    None,
                )

            if bound_queue_loop is not authoritative_queue_loop:

                raise RuntimeError(
                    "IntentEngine QueueLoop identity mismatch | "
                    "expected authoritative QbitQueueLoop"
                )

            bound_qbit = getattr(
                intent_engine,
                "qbit",
                None,
            )

            if (
                authoritative_qbit is not None
                and bound_qbit is not authoritative_qbit
            ):

                raise RuntimeError(
                    "IntentEngine Qbit identity mismatch | "
                    "expected authoritative Qbit"
                )

            bound_dialer = getattr(
                intent_engine,
                "qbit_dialer",
                None,
            )

            if (
                authoritative_dialer is not None
                and bound_dialer is not authoritative_dialer
            ):

                raise RuntimeError(
                    "IntentEngine QbitDialer identity mismatch | "
                    "expected authoritative QbitDialer"
                )

        except Exception as exc:

            intent_engine = None

            MODULES_STATUS[
                "IntentEngine"
            ] = False

            trace_exception(exc)

        # ==================================================
        # AGENT MANAGER
        # ==================================================

        try:

            from seed.core.agent_manager import AgentManager

            agent_manager = compatible_construct(
                AgentManager,
                [
                    (
                        (),
                        {
                            key: value
                            for key, value
                            in common_dependencies.items()
                            if value is not None
                        },
                    ),
                    (
                        (),
                        {
                            "event_bus":
                                authoritative_event_bus,
                            "heartbeat":
                                common_dependencies["heartbeat"],
                            "emit":
                                common_dependencies["emit"],
                        },
                    ),
                    (
                        (),
                        {
                            "event_bus":
                                authoritative_event_bus,
                        },
                    ),
                ],
                "AgentManager",
            )

            if agent_manager is None:
                raise RuntimeError(
                    "AgentManager construction failed"
                )

            MODULES_STATUS[
                "AgentManager"
            ] = True

            _attach(
                agent_manager,
                authoritative_qbit,
                (
                    "attach_qbit",
                    "bind_qbit",
                ),
                ("qbit", "_qbit"),
                "AgentManager",
            )

            _attach(
                agent_manager,
                authoritative_dialer,
                (
                    "attach_qbit_dialer",
                    "bind_qbit_dialer",
                ),
                (
                    "qbit_dialer",
                    "_qbit_dialer",
                ),
                "AgentManager",
            )

            _attach(
                agent_manager,
                authoritative_track_system,
                (
                    "attach_track_system",
                    "bind_track_system",
                ),
                (
                    "track_system",
                    "_track_system",
                ),
                "AgentManager",
            )

            _attach(
                agent_manager,
                authoritative_registry,
                (
                    "attach_registry",
                    "bind_registry",
                ),
                (
                    "registry",
                    "system_registry",
                ),
                "AgentManager",
            )

        except Exception as exc:

            agent_manager = None

            MODULES_STATUS[
                "AgentManager"
            ] = False

            trace_exception(exc)

        # ==================================================
        # ACTION ENGINE
        #
        # Observation / proposal / telemetry only.
        #
        # It does NOT become command authority.
        # ==================================================

        try:

            from seed.core.actions import ActionEngine

            action_engine = compatible_construct(
                ActionEngine,
                [
                    (
                        (),
                        {
                            key: value
                            for key, value
                            in common_dependencies.items()
                            if value is not None
                        },
                    ),
                    (
                        (),
                        {
                            "storage_root":
                                str(SEED_ROOT),
                            "track":
                                "SEED_MAIN",
                        },
                    ),
                    (
                        (),
                        {
                            "event_bus":
                                authoritative_event_bus,
                        },
                    ),
                ],
                "ActionEngine",
            )

            if action_engine is None:
                raise RuntimeError(
                    "ActionEngine construction failed"
                )

            MODULES_STATUS[
                "ActionEngine"
            ] = True

            _attach(
                action_engine,
                authoritative_qbit,
                (
                    "attach_qbit",
                    "bind_qbit",
                ),
                ("qbit", "_qbit"),
                "ActionEngine",
            )

            _attach(
                action_engine,
                authoritative_dialer,
                (
                    "attach_qbit_dialer",
                    "bind_qbit_dialer",
                ),
                (
                    "qbit_dialer",
                    "_qbit_dialer",
                ),
                "ActionEngine",
            )

            _attach(
                action_engine,
                authoritative_track_system,
                (
                    "attach_track_system",
                    "bind_track_system",
                ),
                (
                    "track_system",
                    "_track_system",
                ),
                "ActionEngine",
            )

            _attach(
                action_engine,
                authoritative_registry,
                (
                    "attach_registry",
                    "bind_registry",
                ),
                (
                    "registry",
                    "system_registry",
                ),
                "ActionEngine",
            )

        except Exception as exc:

            action_engine = None

            MODULES_STATUS[
                "ActionEngine"
            ] = False

            trace_exception(exc)

        # ==================================================
        # DEVICE MANAGER
        # ==================================================

        try:

            from seed.core.device_manager import DeviceManager

            device_manager = compatible_construct(
                DeviceManager,
                [
                    (
                        (),
                        {
                            key: value
                            for key, value
                            in {
                                **common_dependencies,
                                "device": device,
                            }.items()
                            if value is not None
                        },
                    ),
                    (
                        (),
                        {
                            "event_bus":
                                authoritative_event_bus,
                            "qbit":
                                authoritative_qbit,
                        },
                    ),
                    (
                        (),
                        {
                            "event_bus":
                                authoritative_event_bus,
                        },
                    ),
                ],
                "DeviceManager",
            )

            if device_manager is None:
                raise RuntimeError(
                    "DeviceManager construction failed"
                )

            MODULES_STATUS[
                "DeviceManager"
            ] = True

            _attach(
                device_manager,
                device,
                (
                    "attach_device",
                    "bind_device",
                    "set_device",
                ),
                ("device", "_device"),
                "DeviceManager",
            )

            _attach(
                device_manager,
                authoritative_qbit,
                (
                    "attach_qbit",
                    "bind_qbit",
                ),
                ("qbit", "_qbit"),
                "DeviceManager",
            )

            _attach(
                device_manager,
                authoritative_dialer,
                (
                    "attach_qbit_dialer",
                    "bind_qbit_dialer",
                ),
                (
                    "qbit_dialer",
                    "_qbit_dialer",
                ),
                "DeviceManager",
            )

            _attach(
                device_manager,
                authoritative_track_system,
                (
                    "attach_track_system",
                    "bind_track_system",
                ),
                (
                    "track_system",
                    "_track_system",
                ),
                "DeviceManager",
            )

            _attach(
                device_manager,
                authoritative_registry,
                (
                    "attach_registry",
                    "bind_registry",
                ),
                (
                    "registry",
                    "system_registry",
                ),
                "DeviceManager",
            )

        except Exception as exc:

            device_manager = None

            MODULES_STATUS[
                "DeviceManager"
            ] = False

            trace_exception(exc)

        # ==================================================
        # HEALTH MONITOR
        # ==================================================

        try:

            from seed.systemutils.healthmonitor import (
                HealthMonitor
            )

            health_monitor = compatible_construct(
                HealthMonitor,
                [
                    (
                        (),
                        {
                            key: value
                            for key, value
                            in {
                                **common_dependencies,
                                "live_debug": True,
                            }.items()
                            if value is not None
                        },
                    ),
                    (
                        (),
                        {
                            "qbit":
                                authoritative_dialer,
                            "live_debug":
                                True,
                        },
                    ),
                    (
                        (),
                        {
                            "emit":
                                common_dependencies["emit"],
                        },
                    ),
                ],
                "HealthMonitor",
            )

            if health_monitor is None:
                raise RuntimeError(
                    "HealthMonitor construction failed"
                )

            MODULES_STATUS[
                "HealthMonitor"
            ] = True

            _attach(
                health_monitor,
                authoritative_qbit,
                (
                    "attach_qbit",
                    "bind_qbit",
                ),
                ("qbit", "_qbit"),
                "HealthMonitor",
            )

            _attach(
                health_monitor,
                authoritative_dialer,
                (
                    "attach_qbit_dialer",
                    "bind_qbit_dialer",
                ),
                (
                    "qbit_dialer",
                    "_qbit_dialer",
                ),
                "HealthMonitor",
            )

            _attach(
                health_monitor,
                authoritative_track_context,
                (
                    "attach_track_context",
                    "bind_track_context",
                ),
                (
                    "track_context",
                    "_track_context",
                ),
                "HealthMonitor",
            )

            _attach(
                health_monitor,
                authoritative_track_system,
                (
                    "attach_track_system",
                    "bind_track_system",
                ),
                (
                    "track_system",
                    "_track_system",
                ),
                "HealthMonitor",
            )

        except Exception as exc:

            health_monitor = None

            MODULES_STATUS[
                "HealthMonitor"
            ] = False

            trace_exception(exc)

        # ==================================================
        # FINAL DIALER SUPPORT-MANAGER BINDING
        #
        # Dialer remains command authority.
        #
        # Managers are dependencies/observers/proposers.
        # ==================================================

        if authoritative_dialer is not None:

            dialer_dependencies = {
                "event_bus":
                    authoritative_event_bus,

                "heartbeat":
                    common_dependencies["heartbeat"],

                "qbit":
                    authoritative_qbit,

                "queue_loop":
                    authoritative_queue_loop,

                "qbit_queue_loop":
                    authoritative_queue_loop,

                "track_system":
                    authoritative_track_system,

                "registry":
                    authoritative_registry,

                "system_registry":
                    authoritative_registry,

                "nodes":
                    authoritative_nodes,

                "node_registry":
                    authoritative_nodes,

                "device":
                    device,

                "device_manager":
                    device_manager,

                "module_registry":
                    module_registry,

                "intent_engine":
                    intent_engine,

                "agent_manager":
                    agent_manager,

                "action_engine":
                    action_engine,

                "health_monitor":
                    health_monitor,

                "fiveg":
                    fiveg,
            }

            _bind_system(
                authoritative_dialer,
                dialer_dependencies,
                "QbitDialer.bind_system",
            )

            # ----------------------------------------------
            # Explicit fallback attachments.
            # ----------------------------------------------

            for name, value in (
                (
                    "device_manager",
                    device_manager,
                ),
                (
                    "module_registry",
                    module_registry,
                ),
                (
                    "intent_engine",
                    intent_engine,
                ),
                (
                    "agent_manager",
                    agent_manager,
                ),
                (
                    "action_engine",
                    action_engine,
                ),
                (
                    "health_monitor",
                    health_monitor,
                ),
                (
                    "track_system",
                    authoritative_track_system,
                ),
                (
                    "registry",
                    authoritative_registry,
                ),
                (
                    "nodes",
                    authoritative_nodes,
                ),
            ):

                if value is None:
                    continue

                _attach(
                    authoritative_dialer,
                    value,
                    (
                        f"attach_{name}",
                        f"bind_{name}",
                    ),
                    (
                        name,
                    ),
                    "QbitDialer",
                )

        # ==================================================
        # QBIT FINAL RUNTIME CONNECTION
        # ==================================================

        if authoritative_qbit is not None:

            _bind_system(
                authoritative_qbit,
                {
                    "event_bus":
                        authoritative_event_bus,
                    "qbit_queue_loop":
                        authoritative_queue_loop,
                    "queue_loop":
                        authoritative_queue_loop,
                    "qbit_dialer":
                        authoritative_dialer,
                    "track_system":
                        authoritative_track_system,
                    "registry":
                        authoritative_registry,
                    "nodes":
                        authoritative_nodes,
                },
                "Qbit.bind_system",
            )

            _attach(
                authoritative_qbit,
                authoritative_dialer,
                (
                    "attach_qbit_dialer",
                    "bind_qbit_dialer",
                ),
                (
                    "qbit_dialer",
                ),
                "Qbit",
            )

            _attach(
                authoritative_qbit,
                authoritative_track_system,
                (
                    "attach_track_system",
                    "bind_track_system",
                ),
                (
                    "track_system",
                ),
                "Qbit",
            )

        # ==================================================
        # TRACK SYSTEM FINAL CONNECTION
        #
        # This is the upward/downward bridge.
        # ==================================================

        if authoritative_track_system is not None:

            _bind_system(
                authoritative_track_system,
                {
                    "event_bus":
                        authoritative_event_bus,

                    "qbit":
                        authoritative_qbit,

                    "qbit_queue_loop":
                        authoritative_queue_loop,

                    "qbit_dialer":
                        authoritative_dialer,

                    "registry":
                        authoritative_registry,

                    "system_registry":
                        authoritative_registry,

                    "nodes":
                        authoritative_nodes,

                    "node_registry":
                        authoritative_nodes,

                    "seedcore":
                        authoritative_seedcore,

                    "kernel_bus":
                        authoritative_kernel_bus,

                    "fathud":
                        authoritative_fathud,

                    "fat_layer":
                        authoritative_fat_layer,
                },
                "TrackSystem.bind_system",
            )

            _attach(
                authoritative_track_system,
                authoritative_registry,
                (
                    "attach_registry",
                    "bind_registry",
                ),
                (
                    "registry",
                    "system_registry",
                ),
                "TrackSystem",
            )

            _attach(
                authoritative_track_system,
                authoritative_nodes,
                (
                    "attach_nodes",
                    "bind_nodes",
                    "attach_node_registry",
                    "bind_node_registry",
                ),
                (
                    "nodes",
                    "node_registry",
                ),
                "TrackSystem",
            )

            _attach(
                authoritative_track_system,
                authoritative_dialer,
                (
                    "attach_qbit_dialer",
                    "bind_qbit_dialer",
                ),
                (
                    "qbit_dialer",
                ),
                "TrackSystem",
            )

        # ==================================================
        # FATHUD FINAL OBSERVER CONNECTION
        #
        # Same FATHUD instance.
        # No second adapter.
        # No command authority.
        # ==================================================

        if authoritative_fathud is not None:

            _bind_system(
                authoritative_fathud,
                {
                    "event_bus":
                        authoritative_event_bus,

                    "qbit":
                        authoritative_qbit,

                    "qbit_queue_loop":
                        authoritative_queue_loop,

                    "qbit_loop":
                        authoritative_queue_loop,

                    "dialer":
                        authoritative_dialer,

                    "qbit_dialer":
                        authoritative_dialer,

                    "track_system":
                        authoritative_track_system,

                    "registry":
                        authoritative_registry,

                    "system_registry":
                        authoritative_registry,

                    "nodes":
                        authoritative_nodes,

                    "node_registry":
                        authoritative_nodes,

                    "seedcore":
                        authoritative_seedcore,

                    "kernel_bus":
                        authoritative_kernel_bus,
                },
                "FATHUDAdapter.bind_system",
            )

            # ----------------------------------------------
            # Explicit TrackSystem attachment.
            # ----------------------------------------------

            _attach(
                authoritative_fathud,
                authoritative_track_system,
                (
                    "attach_track_system",
                    "bind_track_system",
                ),
                (
                    "track_system",
                ),
                "FATHUDAdapter",
            )

            _attach(
                authoritative_fathud,
                authoritative_registry,
                (
                    "attach_registry",
                    "bind_registry",
                ),
                (
                    "registry",
                    "system_registry",
                ),
                "FATHUDAdapter",
            )

            _attach(
                authoritative_fathud,
                authoritative_nodes,
                (
                    "attach_nodes",
                    "bind_nodes",
                    "attach_node_registry",
                    "bind_node_registry",
                ),
                (
                    "nodes",
                    "node_registry",
                ),
                "FATHUDAdapter",
            )

        # ==================================================
        # PUBLISH SUPPORT MODULES TO THE AUTHORITATIVE
        # REGISTRY / NODE GRAPH
        #
        # These are references to existing objects only.
        # ==================================================

        support_modules = {
            "fiveg": fiveg,
            "device": device,
            "device_manager": device_manager,
            "module_registry": module_registry,
            "intent_engine": intent_engine,
            "agent_manager": agent_manager,
            "action_engine": action_engine,
            "health_monitor": health_monitor,
        }

        if authoritative_registry is not None:

            for name, module in support_modules.items():

                if module is None:
                    continue

                registered = False

                for method_name in (
                    "register",
                    "register_module",
                    "register_system",
                    "add",
                    "set",
                ):

                    method = getattr(
                        authoritative_registry,
                        method_name,
                        None,
                    )

                    if not callable(method):
                        continue

                    try:

                        safe_call(
                            method,
                            name,
                            module,
                            default=None,
                            label=(
                                f"SystemRegistry.{method_name}"
                                f"({name})"
                            ),
                        )

                        registered = True
                        break

                    except Exception:
                        continue

                if registered:
                    boot_log(
                        "Registry linked | "
                        f"name={name} | "
                        f"type={type(module).__name__}"
                    )

        # ==================================================
        # STATUS PROPAGATION
        #
        # Every support manager reports its state upward
        # through the authoritative EventBus / TrackSystem.
        # ==================================================

        for component_name, component in (
            ("FiveG", fiveg),
            ("Device", device),
            ("DeviceManager", device_manager),
            ("ModuleRegistry", module_registry),
            ("IntentEngine", intent_engine),
            ("AgentManager", agent_manager),
            ("ActionEngine", action_engine),
            ("HealthMonitor", health_monitor),
        ):

            _emit_status(
                component_name,
                (
                    "ONLINE"
                    if component is not None
                    else "UNAVAILABLE"
                ),
                object_type=(
                    type(component).__name__
                    if component is not None
                    else None
                ),
                track_id=(
                    getattr(
                        authoritative_track_context,
                        "track_id",
                        None,
                    )
                    if authoritative_track_context
                    is not None
                    else None
                ),
            )

        # ==================================================
        # FINAL GLOBAL REFERENCES
        # ==================================================

        globals()["fiveg"] = fiveg
        globals()["device"] = device
        globals()["device_manager"] = device_manager
        globals()["module_registry"] = module_registry
        globals()["intent_engine"] = intent_engine
        globals()["agent_manager"] = agent_manager
        globals()["action_engine"] = action_engine
        globals()["health_monitor"] = health_monitor

        # Preserve authoritative aliases.
        if authoritative_registry is not None:
            globals()["registry"] = authoritative_registry
            globals()["system_registry"] = (
                authoritative_registry
            )

        if authoritative_nodes is not None:
            globals()["nodes"] = authoritative_nodes

        # ==================================================
        # FINAL IDENTITY / DEPENDENCY VALIDATION
        # ==================================================

        if globals().get("event_bus") is not authoritative_event_bus:
            raise RuntimeError(
                "Support runtime EventBus identity changed"
            )

        if globals().get("qbit") is not authoritative_qbit:
            raise RuntimeError(
                "Support runtime Qbit identity changed"
            )

        if globals().get("qbit_dialer") is not authoritative_dialer:
            raise RuntimeError(
                "Support runtime QbitDialer identity changed"
            )

        if (
            authoritative_track_system is not None
            and globals().get("track_system")
            is not authoritative_track_system
        ):
            raise RuntimeError(
                "Support runtime TrackSystem identity changed"
            )

        if (
            authoritative_registry is not None
            and globals().get("system_registry")
            is not authoritative_registry
        ):
            raise RuntimeError(
                "Support runtime Registry identity changed"
            )

        # ==================================================
        # COMPLETE
        # ==================================================

        boot_log(
            "PHASE 08 | Support Managers COMPLETE | "
            f"registry={type(authoritative_registry).__name__} | "
            if authoritative_registry is not None
            else "registry=None | "
        )

        boot_log(
            "Support dependency chain ONLINE | "
            f"qbit={type(authoritative_qbit).__name__} | "
            f"queue_loop={type(authoritative_queue_loop).__name__} | "
            f"dialer={type(authoritative_dialer).__name__} | "
            f"track_system={type(authoritative_track_system).__name__} | "
            if authoritative_track_system is not None
            else "track_system=None | "
        )

        return {
            "fiveg": fiveg,
            "device": device,
            "device_manager": device_manager,
            "module_registry": module_registry,
            "intent_engine": intent_engine,
            "agent_manager": agent_manager,
            "action_engine": action_engine,
            "health_monitor": health_monitor,
            "registry": authoritative_registry,
            "nodes": authoritative_nodes,
            "track_system": authoritative_track_system,
            "qbit": authoritative_qbit,
            "qbit_queue_loop": authoritative_queue_loop,
            "qbit_dialer": authoritative_dialer,
            "event_bus": authoritative_event_bus,
        }

    except Exception as exc:

        boot_log(
            "PHASE 08 | Support Managers FAILED"
        )

        trace_exception(exc)

        return None
# ==========================================================
# SECTION 22 â€” COGNITION / GOVERNANCE
# ==========================================================

def boot_cognition():
    global priority_engine
    global adaptive_priority_engine
    global governor
    global memory_system
    global watchdog
    global growth_tree

    boot_log(
        "PHASE 09 | Cognition / Governance"
    )

    priority_engine = None
    governor = None
    memory_system = None
    watchdog = None
    growth_tree = None
    global neural_bridge

    try:
        from seed.core.neural.neural_bridge import NeuralBridge

        neural_bridge = NeuralBridge()

        # --------------------------------------------------
        # AUTHORITATIVE DEPENDENCIES
        # --------------------------------------------------

        neural_bridge.event_bus = event_bus
        neural_bridge.qbit = qbit
        neural_bridge.qbit_queue_loop = queue_loop
        neural_bridge.track_system = track_system
        neural_bridge.registry = system_registry
        neural_bridge.registry_runtime = registry_runtime

        if computebrain is not None:
            neural_bridge.compute_brain = computebrain

        if transformerbrain is not None:
            neural_bridge.transformer_brain = transformerbrain

        MODULES_STATUS[
            "NeuralBridge"
        ] = True

        boot_log(
            "NeuralBridge dependencies bound"
        )

    except Exception as exc:
        neural_bridge = None

        MODULES_STATUS[
            "NeuralBridge"
        ] = False

        trace_exception(exc)

    try:
        from seed.core.cognition.cognition_map import (
            start_cognition_map,
        )

        cmap = safe_call(
            start_cognition_map,
            queue_loop,
            default=None,
            label="start_cognition_map",
        )

        if queue_loop is not None:
            try:
                queue_loop.cognition_map = cmap
            except Exception:
                pass

        MODULES_STATUS[
            "CognitionMap"
        ] = cmap is not None

    except Exception as exc:
        MODULES_STATUS["CognitionMap"] = False
        trace_exception(exc)

    # ======================================================
    # COGNITION SUPPORT FABRIC
    # ======================================================
    # Construct every cognition component against the existing
    # runtime. These objects remain passive unless their explicit
    # lifecycle is authorized by SEED boot/runtime.

    global cognitive_clock
    global cognitive_scheduler
    global goal_engine
    global cognition_node
    global cognition_binary_encoder
    global cognition_load_balancer
    global cognition_neural_bridge

    cognitive_clock = None
    cognitive_scheduler = None
    goal_engine = None
    cognition_node = None
    cognition_binary_encoder = None
    cognition_load_balancer = None
    cognition_neural_bridge = None

    try:
        from seed.core.cognition.cognitive_clock import CognitiveClock
        cognitive_clock = CognitiveClock(interval=0.5, auto_start=False)
        if queue_loop is not None:
            queue_loop.cognitive_clock = cognitive_clock
        MODULES_STATUS["CognitiveClock"] = True
    except Exception as exc:
        MODULES_STATUS["CognitiveClock"] = False
        trace_exception(exc)

    try:
        from seed.core.cognition.cognitive_scheduler import CognitiveScheduler
        guardian_runtime = globals().get("guardian")
        cognitive_scheduler = CognitiveScheduler(
            queue_loop,
            qbit_dialer=qbit_dialer,
            cognitive_clock=cognitive_clock,
            event_bus=event_bus,
            constraint_guardian=guardian_runtime,
            interval=5.0,
            max_pending_scheduler_qbits=1,
        )
        if queue_loop is not None:
            queue_loop.cognitive_scheduler = cognitive_scheduler
        MODULES_STATUS["CognitiveScheduler"] = cognitive_scheduler is not None
    except Exception as exc:
        MODULES_STATUS["CognitiveScheduler"] = False
        trace_exception(exc)

    try:
        from seed.core.cognition.goal_engine import GoalEngine
        goal_engine = GoalEngine(
            queue_loop,
            qbit_dialer=qbit_dialer,
            interval=10.0,
            auto_start=False,
        )
        if queue_loop is not None:
            queue_loop.goal_engine = goal_engine
        MODULES_STATUS["GoalEngine"] = goal_engine is not None
    except Exception as exc:
        MODULES_STATUS["GoalEngine"] = False
        trace_exception(exc)

    try:
        from seed.core.cognition.qbit_binary_encoder import QbitBinaryEncoder
        cognition_binary_encoder = QbitBinaryEncoder(
            ensure_ascii=False,
            sort_keys=True,
        )
        if neural_bridge is not None:
            neural_bridge.cognition_encoder = cognition_binary_encoder
        MODULES_STATUS["CognitionQbitBinaryEncoder"] = (
            cognition_binary_encoder is not None
        )
    except Exception as exc:
        MODULES_STATUS["CognitionQbitBinaryEncoder"] = False
        trace_exception(exc)

    try:
        from seed.core.cognition.neural_bridge import NeuralBridge as CognitionNeuralBridge
        cognition_neural_bridge = CognitionNeuralBridge(
            encoder=cognition_binary_encoder,
            registry=registry,
            registry_runtime=registry_runtime,
            qbit_queue_loop=queue_loop,
            event_bus=event_bus,
            track_system=track_system,
            compute_brain=computebrain,
            transformer_brain=transformerbrain,
            qbit_dialer=qbit_dialer,
        )
        cognition_neural_bridge.bind_systems(
            registry=registry,
            registry_runtime=registry_runtime,
            qbit_queue_loop=queue_loop,
            event_bus=event_bus,
            track_system=track_system,
            compute_brain=computebrain,
            transformer_brain=transformerbrain,
            qbit_dialer=qbit_dialer,
        )
        if module_registry is not None:
            bind_registry = getattr(
                module_registry,
                "bind_runtime",
                None,
            )
            if callable(bind_registry):
                bind_registry(
                    neural_bridge=cognition_neural_bridge,
                    qbit=qbit,
                    dialer=qbit_dialer,
                    queue_loop=queue_loop,
                    event_bus=event_bus,
                    track_system=track_system,
                    registry=registry,
                    registry_runtime=registry_runtime,
                    node_registry=authoritative_nodes,
                )

        MODULES_STATUS["CognitionNeuralBridge"] = True
    except Exception as exc:
        MODULES_STATUS["CognitionNeuralBridge"] = False
        trace_exception(exc)

    try:
        from seed.core.cognition.qbit_load_balancer import QbitLoadBalancer
        guardian_runtime = globals().get("guardian")
        cognition_load_balancer = QbitLoadBalancer(
            queue_loop,
            workers=1,
            fabric_bridge=seed_network_core or seed_network,
            constraint_guardian=guardian_runtime,
            event_bus=event_bus,
            auto_start=False,
            poll_interval=0.1,
            worker_queue_size=64,
        )
        if queue_loop is not None:
            queue_loop.cognition_load_balancer = cognition_load_balancer
        MODULES_STATUS["CognitionQbitLoadBalancer"] = (
            cognition_load_balancer is not None
        )
    except Exception as exc:
        MODULES_STATUS["CognitionQbitLoadBalancer"] = False
        trace_exception(exc)

    try:
        from seed.core.cognition import CognitionNode
        cognition_node = CognitionNode(
            queue_loop=queue_loop,
            memory_graph=globals().get("memory_graph"),
            qbit_dialer=qbit_dialer,
            command_relay=relay,
            relay=relay,
            growth_manager=None,
            tool_registry=module_registry,
        )
        cognition_node.set_boot_ready(
            True,
            reason="main3_authoritative_runtime_bound",
        )
        if queue_loop is not None:
            queue_loop.cognition_node = cognition_node
        MODULES_STATUS["CognitionNode"] = cognition_node is not None
    except Exception as exc:
        MODULES_STATUS["CognitionNode"] = False
        trace_exception(exc)

    try:
        from seed.core.cognition.adaptive_priority import (
            AdaptivePriorityEngine,
        )
        from seed.core.integration.core_module_growth_tree import (
            ModuleGrowthTree,
        )

        growth_tree = ModuleGrowthTree(
            path=str(
                Path(SEED_ROOT)
                / "logs"
                / "module_growth_tree.json"
            ),
            event_bus=event_bus,
            analytics_engine=globals().get(
                "analytics_engine"
            ),
            intent_engine=globals().get(
                "intent_engine"
            ),
        )

        priority_engine = AdaptivePriorityEngine(
            growth_tree=growth_tree,
            intent_engine=globals().get(
                "intent_engine"
            ),
        )

        # Skills are a capability class for priority learning.
        # Use the already-loaded package registry when present;
        # do not import SkillNet or start another skill worker.
        try:
            import sys
            skill_package = sys.modules.get("seed.skills")
            skill_registry = getattr(
                skill_package,
                "SKILLS",
                None,
            ) if skill_package is not None else None
            priority_engine.bind_skill_registry(
                skill_registry
            )
        except Exception:
            pass

        adaptive_priority_engine = priority_engine

        intent_runtime = globals().get(
            "intent_engine"
        )
        if intent_runtime is not None:
            _intent_growth_bind = getattr(
                intent_runtime,
                "bind_adaptive_growth",
                None,
            )
            if callable(_intent_growth_bind):
                _intent_growth_bind(
                    adaptive_priority_engine=priority_engine,
                    growth_tree=growth_tree,
                )
            else:
                try:
                    intent_runtime.adaptive_priority_engine = priority_engine
                    intent_runtime.growth_tree = growth_tree
                except Exception:
                    pass
            _intent_priority_bind = getattr(
                intent_runtime,
                "bind_adaptive_priority",
                None,
            )
            if callable(_intent_priority_bind):
                _intent_priority_bind(
                    priority_engine
                )
            else:
                try:
                    intent_runtime.adaptive_priority_engine = priority_engine
                except Exception:
                    pass

        if queue_loop is not None:
            queue_loop.priority_engine = priority_engine

        if qbit_dialer is not None:
            qbit_dialer.growth_tree = growth_tree

        MODULES_STATUS[
            "AdaptivePriorityEngine"
        ] = True

        # Passive discovery connects SEED skills and integration
        # folders to the same ModuleRegistry/SRegistry node plane.
        try:
            module_registry.refresh_skill_catalog(
                roots=[
                    Path(SEED_ROOT) / "seed" / "skills",
                    Path(SEED_ROOT) / "seed" / "core" / "integration",
                ],
                max_files=500,
            )
            MODULES_STATUS["SkillIntegrationCatalog"] = True
        except Exception as exc:
            MODULES_STATUS["SkillIntegrationCatalog"] = False
            boot_warn(f"Skill/integration catalog refresh deferred: {exc}")

    except Exception as exc:
        MODULES_STATUS[
            "AdaptivePriorityEngine"
        ] = False

        trace_exception(exc)

    try:
        from seed.core.cognition.memory_weighting import (
            MemoryWeightingSystem,
        )

        memory_system = MemoryWeightingSystem()

        if queue_loop is not None:
            queue_loop.memory_system = memory_system

        if priority_engine is not None:
            priority_engine.memory_system = memory_system

        MODULES_STATUS[
            "MemoryWeightingSystem"
        ] = True

    except Exception as exc:
        MODULES_STATUS[
            "MemoryWeightingSystem"
        ] = False

        trace_exception(exc)

    # ======================================================
    # EVOLUTION ENGINE — AUTHORITATIVE RUNTIME BINDING
    # ======================================================
    # Evolution remains proposal-only here. Main3 binds the live
    # runtime but does not start another worker thread.
    try:
        from seed.core.evolution.qbit_evolution_engine import (
            QbitEvolutionEngine,
        )

        evolution_engine = QbitEvolutionEngine(
            queue_loop=queue_loop,
            memory_graph=globals().get("memory_graph"),
            qbit_dialer=qbit_dialer,
            event_bus=event_bus,
            track_system=track_system,
            track_context=track_context,
            registry=registry,
            node_registry=authoritative_nodes,
            intent_engine=globals().get("intent_engine"),
            action_engine=globals().get("action_engine"),
            analytics_engine=globals().get("analytics_engine"),
            adaptive_engine=globals().get("adaptive_engine"),
            adaptive_priority_engine=adaptive_priority_engine,
            encoder=globals().get("cognition_binary_encoder"),
            heartbeat=heartbeat,
            module_registry=module_registry,
            seedcore=globals().get("seedcore"),
            skill_registry=getattr(
                sys.modules.get("seed.skills"),
                "SKILLS",
                None,
            ) if "sys" in globals() else None,
        )
        if qbit_dialer is not None:
            qbit_dialer.evolution_engine = evolution_engine
        if queue_loop is not None:
            queue_loop.evolution_engine = evolution_engine
        MODULES_STATUS["QbitEvolutionEngine"] = True
    except Exception as exc:
        MODULES_STATUS["QbitEvolutionEngine"] = False
        boot_warn(f"Evolution engine binding deferred: {exc}")

    # ======================================================
    # OS CONTROL — SEED MOUSE / SCREEN PERCEPTION
    # ======================================================
    # Seed Mouse is the default autonomous pointer mode. USER_MOUSE
    # is selected while the host is idle. Screen perception is
    # observer-only in USER_HELP mode and publishes map data through
    # EventBus; all executable mouse commands remain behind Dialer.
    try:
        from seed.core.os_control.os_control_manager import OSControlManager
        os_control_manager = OSControlManager(
            qbit_dialer=qbit_dialer,
            event_bus=event_bus,
        )
        screen_tracker = os_control_manager.tracker
        os_control_manager.enable_seed_mouse(True)
        if qbit_dialer is not None:
            qbit_dialer.register_skill_command(
                "SEED_MOUSE_CONTROL",
                os_control_manager.handle_mouse_command,
                metadata={"authority":"QbitDialer","sandbox_safe":True},
            )
        MODULES_STATUS["OSControlManager"] = True
        MODULES_STATUS["SeedMouse"] = True
        MODULES_STATUS["ScreenTracker"] = True
        _register_main3_node(
            "SeedMouse",
            path="seed/core/os_control/seed_mouse.py",
            role="control_observer_bridge",
            group="os_control",
            capabilities=["MOVE","CLICK","USER_IDLE_MODE","SEED_DEFAULT"],
        )
        _register_main3_node(
            "ScreenTracker",
            path="seed/core/os_control/screen_tracker.py",
            role="screen_observer",
            group="os_control",
            capabilities=["SCREEN_MAP","DYNAMIC_POINTS","MOTION","HELP_MODE"],
        )
        _publish_registry_runtime_provider(
            "os_control_manager",
            os_control_manager,
            state="READY",
            capabilities=["SEED_MOUSE","USER_MOUSE","SCREEN_MAP","MOTION"],
        )
        if event_bus is not None:
            try:
                event_bus.emit("OS_CONTROL_READY", os_control_manager.status())
            except Exception:
                pass
    except Exception as exc:
        MODULES_STATUS["OSControlManager"] = False
        MODULES_STATUS["SeedMouse"] = False
        MODULES_STATUS["ScreenTracker"] = False
        boot_warn(f"OS control binding deferred: {exc}")

    try:
        from seed.core.cognition.governor import (
            CognitiveGovernor,
        )

        governor = compatible_construct(
            CognitiveGovernor,
            [
                (
                    (
                        queue_loop,
                    ),
                    {
                        "event_bus": event_bus
                    },
                ),
                (
                    (
                        queue_loop,
                        event_bus,
                    ),
                    {},
                ),
            ],
            "CognitiveGovernor",
        )

        if queue_loop is not None:
            queue_loop.governor = governor

        MODULES_STATUS[
            "CognitiveGovernor"
        ] = governor is not None

    except Exception as exc:
        MODULES_STATUS[
            "CognitiveGovernor"
        ] = False

        trace_exception(exc)

    try:
        from seed.core.supervisors.qbit_watchdog import (
            QbitWatchdog,
        )

        watchdog = QbitWatchdog(queue_loop)

        if queue_loop is not None:
            queue_loop.watchdog = watchdog

        MODULES_STATUS[
            "QbitWatchdog"
        ] = True

    except Exception as exc:
        MODULES_STATUS[
            "QbitWatchdog"
        ] = False

        trace_exception(exc)

    # ======================================================
    # FINAL COGNITION RUNTIME BIND
    # ======================================================
    # Bind support components after their dependencies exist.
    # No component is started here.
    try:
        if cognition_node is not None:
            cognition_node.attach_dependencies(
                queue_loop=queue_loop,
                memory_graph=globals().get("memory_graph"),
                qbit_dialer=qbit_dialer,
                command_relay=relay,
                relay=relay,
                growth_manager=globals().get("growth_tree"),
                tool_registry=module_registry,
            )

        if priority_engine is not None:
            priority_engine.bind_intent_growth(
                intent_engine=globals().get("intent_engine"),
                growth_tree=globals().get("growth_tree"),
            )
            priority_engine.memory_system = memory_system

        if cognitive_scheduler is not None:
            cognitive_scheduler.clock = cognitive_clock
            cognitive_scheduler.event_bus = event_bus
            cognitive_scheduler.constraint_guardian = globals().get("guardian")

        if goal_engine is not None:
            goal_engine.memory_graph = globals().get("memory_graph")

        if cognition_load_balancer is not None:
            cognition_load_balancer.fabric_bridge = (
                seed_network_core or seed_network
            )
            cognition_load_balancer.constraint_guardian = globals().get("guardian")
            cognition_load_balancer.event_bus = event_bus

        if queue_loop is not None:
            queue_loop.cognition_clock = cognitive_clock
            queue_loop.cognitive_scheduler = cognitive_scheduler
            queue_loop.goal_engine = goal_engine
            queue_loop.cognition_map = cmap
            queue_loop.cognition_node = cognition_node
            queue_loop.cognition_binary_encoder = cognition_binary_encoder
            queue_loop.cognition_neural_bridge = cognition_neural_bridge
            queue_loop.cognition_load_balancer = cognition_load_balancer
            queue_loop.memory_weighting = memory_system

        if qbit_dialer is not None:
            qbit_dialer.cognitive_clock = cognitive_clock
            qbit_dialer.cognitive_scheduler = cognitive_scheduler
            qbit_dialer.goal_engine = goal_engine
            qbit_dialer.cognition_map = cmap
            qbit_dialer.memory_weighting = memory_system
            qbit_dialer.cognition_binary_encoder = cognition_binary_encoder
            qbit_dialer.cognition_neural_bridge = cognition_neural_bridge
            qbit_dialer.cognition_load_balancer = cognition_load_balancer
            qbit_dialer.cognition_node = cognition_node

        MODULES_STATUS["CognitionRuntimeBinding"] = True
        boot_log(
            "Cognition support fabric bound | passive lifecycle preserved"
        )
    except Exception as exc:
        MODULES_STATUS["CognitionRuntimeBinding"] = False
        trace_exception(exc)


# ==========================================================
# SECTION 23 â€” RELAY 2.0
# ==========================================================

def boot_relay():
    global relay
    global relay_mission_bridge

    boot_log(
        "PHASE 10 | SEED Relay 2.0"
    )

    relay = None
    relay_mission_bridge = None

    try:

        from seed.core.relay import SEEDRelay
        from seed.core.relay.relay_mission_bridge import (
            RelayMissionBridge,
        )

        relay = SEEDRelay(
            cpu_ceiling=50.0,
            memory_ceiling=80.0,
            queue_size=100,
            allow_prepare=False,
        )

        safe_call(
            getattr(
                relay,
                "start",
                None,
            ),
            label="SEEDRelay.start",
        )

        relay_mission_bridge = (
            RelayMissionBridge(relay)
        )

        MODULES_STATUS[
            "SEEDRelay"
        ] = True

        boot_log(
            "SEED Relay 2.0 ACTIVE"
        )

    except Exception as exc:

        MODULES_STATUS[
            "SEEDRelay"
        ] = False

        relay = None
        relay_mission_bridge = None

        boot_warn(
            "SEED Relay 2.0 unavailable | "
            f"{type(exc).__name__}: {exc}"
        )


# ==========================================================
# SECTION 24 â€” ORCHESTRATOR
# ==========================================================

def boot_orchestrator():

    global orchestrator
    global orchestrator_command

    boot_log(
        "PHASE 11 | SEEDOrchestrator"
    )

    try:

        from seed.core.orchestrator import (
            SEEDOrchestrator,
        )

        orchestrator = compatible_construct(
            SEEDOrchestrator,
            [
                (
                    (),
                    {
                        "emit": getattr(
                            event_bus,
                            "emit",
                            safe_emit,
                        ),
                        "event_bus":
                            event_bus,
                        "storage_root":
                            str(SEED_ROOT),
                        "qbit":
                            qbit,
                        "queue_loop":
                            queue_loop,
                        "qbit_dialer":
                            qbit_dialer,
                        "kernel_bus":
                            kernel_bus,
                        "track_system":
                            track_system,
                        "registry":
                            registry,
                        "node_registry":
                            globals().get(
                                "runtime_nodes"
                            ),
                        "seedcore":
                            seedcore,
                        "fathud":
                            fathud,
                        "device_manager":
                            device_manager,
                        "intent_engine":
                            intent_engine,
                    },
                ),
                (
                    (),
                    {
                        "emit": getattr(
                            event_bus,
                            "emit",
                            safe_emit,
                        ),
                        "event_bus":
                            event_bus,
                        "qbit_dialer":
                            qbit_dialer,
                        "intent_engine":
                            intent_engine,
                    },
                ),
                (
                    (),
                    {
                        "emit": getattr(
                            event_bus,
                            "emit",
                            safe_emit,
                        ),
                        "event_bus":
                            event_bus,
                        "qbit_dialer":
                            qbit_dialer,
                    },
                ),
                (
                    (),
                    {
                        "event_bus":
                            event_bus,
                    },
                ),
            ],
            "SEEDOrchestrator",
        )

        if orchestrator is None:

            raise RuntimeError(
                "SEEDOrchestrator unavailable"
            )

        # --------------------------------------------------
        # AUTHORITATIVE RUNTIME BIND
        # --------------------------------------------------

        bind_runtime = getattr(
            orchestrator,
            "bind_runtime",
            None,
        )

        if callable(bind_runtime):

            bind_runtime(
                qbit=qbit,
                queue_loop=queue_loop,
                qbit_dialer=qbit_dialer,
                kernel_bus=kernel_bus,
                track_system=track_system,
                registry=registry,
                node_registry=globals().get(
                    "runtime_nodes"
                ),
                seedcore=seedcore,
                fathud=fathud,
                intent_engine=intent_engine,
            )

        # --------------------------------------------------
        # AUTHORITATIVE ORCHESTRATOR COMMAND
        # --------------------------------------------------

        activate = getattr(
            orchestrator,
            "activate",
            None,
        )

        if callable(activate):

            orchestrator_command = activate

        else:

            orchestrator_command = (
                safe_qbit_state()
            )

        MODULES_STATUS[
            "SEEDOrchestrator"
        ] = True

        boot_log(
            "SEEDOrchestrator ACTIVE"
        )

    except Exception as exc:

        MODULES_STATUS[
            "SEEDOrchestrator"
        ] = False

        trace_exception(exc)

        orchestrator = None

        orchestrator_command = (
            safe_qbit_state()
        )

# ==========================================================
# SECTION 25 â€” MEMORY / DECODER / GUARDIAN / ETHICS
#
# PHASE 12
#
# DEPENDENCY DIRECTION:
#
#   REGISTRY / NODES
#          â†“
#      TRACK SYSTEM
#          â†“
#       EVENT BUS
#          â†“
#         QBIT
#          â†“
#    QUEUE LOOP
#          â†“
#      QBIT DIALER
#          â†“
#   â”Œâ”€â”€â”€â”€â”€â”€â”¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
#   â†“      â†“          â†“
# MEMORY DECODER    GUARDIAN
#   â”‚      â”‚          â”‚
#   â””â”€â”€â”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”˜
#                  â†“
#               ETHICS
#
# These services consume the authoritative runtime.
# They do not create replacement EventBus/Qbit/Registry/
# TrackSystem/Dialer instances.
#
# ==========================================================

def boot_system_services():

    global database
    global memory_crystallizer
    global decoder
    global guardian
    global ethics_manager

    boot_log(
        "PHASE 12 | Memory / Decoder / Guardian / Ethics"
    )

    try:

        # ==================================================
        # AUTHORITATIVE RUNTIME REFERENCES
        #
        # Resolve existing objects only.
        # This prevents constructor-time circular imports
        # and prevents duplicate runtime authorities.
        # ==================================================

        authoritative_event_bus = globals().get(
            "event_bus",
            None,
        )

        authoritative_qbit = globals().get(
            "qbit",
            None,
        )

        authoritative_queue_loop = globals().get(
            "queue_loop",
            None,
        )

        if authoritative_queue_loop is None:
            authoritative_queue_loop = globals().get(
                "qbit_queue_loop",
                None,
            )

        authoritative_dialer = globals().get(
            "qbit_dialer",
            None,
        )

        authoritative_track_system = globals().get(
            "track_system",
            None,
        )

        authoritative_track_context = globals().get(
            "track_context",
            None,
        )

        authoritative_registry = globals().get(
            "system_registry",
            None,
        )

        if authoritative_registry is None:
            authoritative_registry = globals().get(
                "registry",
                None,
            )

        authoritative_nodes = globals().get(
            "nodes",
            None,
        )

        if authoritative_nodes is None:
            authoritative_nodes = globals().get(
                "node_registry",
                None,
            )

        authoritative_seedcore = globals().get(
            "seedcore",
            None,
        )

        if authoritative_seedcore is None:
            authoritative_seedcore = globals().get(
                "seed_core",
                None,
            )

        authoritative_kernel_bus = globals().get(
            "kernel_bus",
            None,
        )

        authoritative_health_monitor = globals().get(
            "health_monitor",
            None,
        )

        authoritative_module_registry = globals().get(
            "module_registry",
            None,
        )

        authoritative_intent_engine = globals().get(
            "intent_engine",
            None,
        )

        # ==================================================
        # REQUIRED RUNTIME
        # ==================================================

        if authoritative_event_bus is None:
            raise RuntimeError(
                "System services require authoritative EventBus"
            )

        if authoritative_qbit is None:
            raise RuntimeError(
                "System services require authoritative Qbit"
            )

        if authoritative_dialer is None:
            raise RuntimeError(
                "System services require authoritative QbitDialer"
            )

        # ==================================================
        # DATABASE CONNECTIVITY LAYER
        #
        # Persistent storage only. Credentials remain external.
        # ==================================================

        try:
            from seed.core.database_connector import SEEDDatabaseConnector
            database = SEEDDatabaseConnector()
            MODULES_STATUS["SEEDDatabase"] = database.enabled
            boot_log(
                f"SEEDDatabase configured | enabled={database.enabled}"
            )
        except Exception as exc:
            database = None
            MODULES_STATUS["SEEDDatabase"] = False
            boot_warn(f"SEEDDatabase unavailable: {exc}")

        # ==================================================
        # SHARED EMITTER
        # ==================================================

        emit_ref = getattr(
            authoritative_event_bus,
            "emit",
            safe_emit,
        )

        # ==================================================
        # LOCAL HELPERS
        #
        # These avoid importing one service from another.
        # ==================================================

        def _attach(
            target,
            value,
            method_names,
            attribute_names=(),
            label="runtime attachment",
        ):

            if target is None or value is None:
                return False

            for method_name in method_names:

                method = getattr(
                    target,
                    method_name,
                    None,
                )

                if callable(method):

                    safe_call(
                        method,
                        value,
                        default=None,
                        label=f"{label}.{method_name}",
                    )

                    return True

            for attribute_name in attribute_names:

                try:

                    if hasattr(
                        target,
                        attribute_name,
                    ):

                        setattr(
                            target,
                            attribute_name,
                            value,
                        )

                        return True

                except Exception as exc:
                    trace_exception(exc)

            return False

        def _bind_system(
            target,
            dependencies,
            label,
        ):

            if target is None:
                return False

            bind_method = getattr(
                target,
                "bind_system",
                None,
            )

            if not callable(bind_method):
                return False

            bind_kwargs = {
                key: value
                for key, value in dependencies.items()
                if value is not None
            }

            try:

                import inspect

                signature = inspect.signature(
                    bind_method
                )

                parameters = signature.parameters

                accepts_kwargs = any(
                    parameter.kind
                    == inspect.Parameter.VAR_KEYWORD
                    for parameter
                    in parameters.values()
                )

                if not accepts_kwargs:

                    bind_kwargs = {
                        key: value
                        for key, value
                        in bind_kwargs.items()
                        if key in parameters
                    }

            except Exception:
                pass

            safe_call(
                bind_method,
                default=None,
                label=label,
                **bind_kwargs,
            )

            return True

        def _publish_status(
            component,
            status,
            **extra,
        ):

            payload = {
                "source":
                    "boot_system_services",

                "component":
                    component,

                "status":
                    status,

                "track_id":
                    getattr(
                        authoritative_track_context,
                        "track_id",
                        None,
                    ),
            }

            payload.update(extra)

            # ----------------------------------------------
            # EVENTBUS
            # ----------------------------------------------

            try:

                safe_call(
                    emit_ref,
                    "system_status",
                    payload,
                    default=None,
                    label=(
                        f"{component}.system_status"
                    ),
                )

            except Exception:
                pass

            # ----------------------------------------------
            # TRACKSYSTEM
            # ----------------------------------------------

            if authoritative_track_system is not None:

                for method_name in (
                    "record_status",
                    "publish_status",
                    "update_status",
                    "track_status",
                ):

                    method = getattr(
                        authoritative_track_system,
                        method_name,
                        None,
                    )

                    if callable(method):

                        safe_call(
                            method,
                            payload,
                            default=None,
                            label=(
                                f"TrackSystem."
                                f"{method_name}"
                            ),
                        )

                        break

            # ----------------------------------------------
            # REGISTRY
            # ----------------------------------------------

            if authoritative_registry is not None:

                for method_name in (
                    "update_status",
                    "set_status",
                    "record_status",
                    "publish_status",
                ):

                    method = getattr(
                        authoritative_registry,
                        method_name,
                        None,
                    )

                    if not callable(method):
                        continue

                    safe_call(
                        method,
                        component,
                        payload,
                        default=None,
                        label=(
                            f"Registry."
                            f"{method_name}"
                        ),
                    )

                    break

        # ==================================================
        # COMMON SERVICE DEPENDENCY GRAPH
        # ==================================================

        service_dependencies = {

            "event_bus":
                authoritative_event_bus,

            "qbit":
                authoritative_qbit,

            "qbit_queue_loop":
                authoritative_queue_loop,

            "queue_loop":
                authoritative_queue_loop,

            "qbit_dialer":
                authoritative_dialer,

            "track_system":
                authoritative_track_system,

            "track_context":
                authoritative_track_context,

            "registry":
                authoritative_registry,

            "system_registry":
                authoritative_registry,

            "nodes":
                authoritative_nodes,

            "node_registry":
                authoritative_nodes,

            "seedcore":
                authoritative_seedcore,

            "kernel_bus":
                authoritative_kernel_bus,

            "health_monitor":
                authoritative_health_monitor,

            "module_registry":
                authoritative_module_registry,

            "intent_engine":
                authoritative_intent_engine,

            "emit":
                emit_ref,
        }

        # ==================================================
        # MEMORY CRYSTALLIZER
        # ==================================================

        memory_crystallizer = None

        try:

            from seed.systemutils.memory_crystallizer import (
                Memory_Crystallizer,
            )

            memory_kwargs = {
                "storage_root":
                    str(SEED_ROOT),

                "emit":
                    emit_ref,

                "track":
                    authoritative_track_system,

                "track_id":
                    getattr(
                        authoritative_track_context,
                        "track_id",
                        None,
                    ),

                "task":
                    None,

                "qbit":
                    authoritative_qbit,

                "event_bus":
                    authoritative_event_bus,

                "track_system":
                    authoritative_track_system,

                "registry":
                    authoritative_registry,

                "nodes":
                    authoritative_nodes,
            }

            # ----------------------------------------------
            # Filter constructor kwargs against actual
            # constructor signature.
            # ----------------------------------------------

            try:

                import inspect

                signature = inspect.signature(
                    Memory_Crystallizer
                )

                parameters = signature.parameters

                accepts_kwargs = any(
                    parameter.kind
                    == inspect.Parameter.VAR_KEYWORD
                    for parameter
                    in parameters.values()
                )

                if not accepts_kwargs:

                    memory_kwargs = {
                        key: value
                        for key, value
                        in memory_kwargs.items()
                        if key in parameters
                    }

            except Exception:
                pass

            memory_crystallizer = (
                Memory_Crystallizer(
                    **memory_kwargs
                )
            )

            if memory_crystallizer is None:
                raise RuntimeError(
                    "Memory_Crystallizer construction failed"
                )

            _bind_system(
                memory_crystallizer,
                service_dependencies,
                "Memory_Crystallizer.bind_system",
            )

            _attach(
                memory_crystallizer,
                authoritative_qbit,
                (
                    "attach_qbit",
                    "bind_qbit",
                ),
                (
                    "qbit",
                    "_qbit",
                ),
                "Memory_Crystallizer",
            )

            _attach(
                memory_crystallizer,
                authoritative_track_system,
                (
                    "attach_track_system",
                    "bind_track_system",
                ),
                (
                    "track_system",
                    "_track_system",
                ),
                "Memory_Crystallizer",
            )

            _attach(
                memory_crystallizer,
                authoritative_registry,
                (
                    "attach_registry",
                    "bind_registry",
                ),
                (
                    "registry",
                    "system_registry",
                ),
                "Memory_Crystallizer",
            )

            MODULES_STATUS[
                "Memory_Crystallizer"
            ] = True

            boot_log(
                "Memory_Crystallizer ONLINE"
            )

            _publish_status(
                "Memory_Crystallizer",
                "ONLINE",
                object_type=type(
                    memory_crystallizer
                ).__name__,
            )

        except Exception as exc:

            memory_crystallizer = None

            MODULES_STATUS[
                "Memory_Crystallizer"
            ] = False

            trace_exception(exc)

            _publish_status(
                "Memory_Crystallizer",
                "FAILED",
                error=repr(exc),
            )

        # ==================================================
        # INSTRUCTION DECODER
        # ==================================================

        decoder = None

        try:

            from seed.systemutils.instruction_decoder import (
                InstructionDecoder,
            )

            decoder_kwargs = {
                "event_bus":
                    authoritative_event_bus,

                "qbit":
                    authoritative_qbit,

                "qbit_dialer":
                    authoritative_dialer,

                "qbit_queue_loop":
                    authoritative_queue_loop,

                "memory_crystallizer":
                    memory_crystallizer,

                "track_system":
                    authoritative_track_system,

                "track_context":
                    authoritative_track_context,

                "registry":
                    authoritative_registry,

                "nodes":
                    authoritative_nodes,

                "seedcore":
                    authoritative_seedcore,

                "kernel_bus":
                    authoritative_kernel_bus,

                "emit":
                    emit_ref,
            }

            try:

                import inspect

                signature = inspect.signature(
                    InstructionDecoder
                )

                parameters = signature.parameters

                accepts_kwargs = any(
                    parameter.kind
                    == inspect.Parameter.VAR_KEYWORD
                    for parameter
                    in parameters.values()
                )

                if not accepts_kwargs:

                    decoder_kwargs = {
                        key: value
                        for key, value
                        in decoder_kwargs.items()
                        if key in parameters
                    }

            except Exception:
                pass

            decoder = InstructionDecoder(
                **decoder_kwargs
            )

            if decoder is None:
                raise RuntimeError(
                    "InstructionDecoder construction failed"
                )

            _bind_system(
                decoder,
                service_dependencies,
                "InstructionDecoder.bind_system",
            )

            _attach(
                decoder,
                memory_crystallizer,
                (
                    "attach_memory_crystallizer",
                    "bind_memory_crystallizer",
                ),
                (
                    "memory_crystallizer",
                    "_memory_crystallizer",
                ),
                "InstructionDecoder",
            )

            _attach(
                decoder,
                authoritative_qbit,
                (
                    "attach_qbit",
                    "bind_qbit",
                ),
                (
                    "qbit",
                    "_qbit",
                ),
                "InstructionDecoder",
            )

            _attach(
                decoder,
                authoritative_track_system,
                (
                    "attach_track_system",
                    "bind_track_system",
                ),
                (
                    "track_system",
                    "_track_system",
                ),
                "InstructionDecoder",
            )

            _attach(
                decoder,
                authoritative_registry,
                (
                    "attach_registry",
                    "bind_registry",
                ),
                (
                    "registry",
                    "system_registry",
                ),
                "InstructionDecoder",
            )

            # ----------------------------------------------
            # Decoder â†’ QbitDialer
            #
            # Dialer remains command authority.
            # Decoder only decodes / interprets.
            # ----------------------------------------------

            _attach(
                authoritative_dialer,
                decoder,
                (
                    "attach_decoder",
                    "bind_decoder",
                ),
                (
                    "decoder",
                ),
                "QbitDialer",
            )

            MODULES_STATUS[
                "InstructionDecoder"
            ] = True

            boot_log(
                "InstructionDecoder ONLINE"
            )

            _publish_status(
                "InstructionDecoder",
                "ONLINE",
                object_type=type(
                    decoder
                ).__name__,
            )

        except Exception as exc:

            decoder = None

            MODULES_STATUS[
                "InstructionDecoder"
            ] = False

            trace_exception(exc)

            _publish_status(
                "InstructionDecoder",
                "FAILED",
                error=repr(exc),
            )

        # ==================================================
        # CONSTRAINT GUARDIAN
        # ==================================================

        guardian = None

        try:

            from seed.systemutils.constraint_guardian import (
                Constraint_Guardian,
            )

            guardian = Constraint_Guardian(
                cpu_limit=85.0,
                mem_limit=90.0,
            )

            if guardian is None:
                raise RuntimeError(
                    "Constraint_Guardian construction failed"
                )

            _bind_system(
                guardian,
                service_dependencies,
                "Constraint_Guardian.bind_system",
            )

            _attach(
                guardian,
                authoritative_event_bus,
                (
                    "attach_event_bus",
                    "bind_event_bus",
                ),
                (
                    "event_bus",
                    "_event_bus",
                ),
                "Constraint_Guardian",
            )

            _attach(
                guardian,
                authoritative_qbit,
                (
                    "attach_qbit",
                    "bind_qbit",
                ),
                (
                    "qbit",
                    "_qbit",
                ),
                "Constraint_Guardian",
            )

            _attach(
                guardian,
                authoritative_dialer,
                (
                    "attach_qbit_dialer",
                    "bind_qbit_dialer",
                ),
                (
                    "qbit_dialer",
                    "_qbit_dialer",
                ),
                "Constraint_Guardian",
            )

            _attach(
                guardian,
                authoritative_track_system,
                (
                    "attach_track_system",
                    "bind_track_system",
                ),
                (
                    "track_system",
                    "_track_system",
                ),
                "Constraint_Guardian",
            )

            _attach(
                guardian,
                authoritative_registry,
                (
                    "attach_registry",
                    "bind_registry",
                ),
                (
                    "registry",
                    "system_registry",
                ),
                "Constraint_Guardian",
            )

            MODULES_STATUS[
                "Constraint_Guardian"
            ] = True

            boot_log(
                "Constraint_Guardian ONLINE | "
                "cpu_limit=85.0 | "
                "mem_limit=90.0"
            )

            _publish_status(
                "Constraint_Guardian",
                "ONLINE",
                object_type=type(
                    guardian
                ).__name__,
                cpu_limit=85.0,
                mem_limit=90.0,
            )

        except Exception as exc:

            guardian = None

            MODULES_STATUS[
                "Constraint_Guardian"
            ] = False

            trace_exception(exc)

            _publish_status(
                "Constraint_Guardian",
                "FAILED",
                error=repr(exc),
            )

        # ==================================================
        # ETHICS MANAGER
        #
        # Ethics sits downstream of memory, health,
        # intent, TrackSystem, Qbit and runtime status.
        #
        # It does not construct any of them.
        # ==================================================

        ethics_manager = None

        try:

            from seed.systemutils.ethics import (
                EthicsManager,
            )

            ethics_kwargs = {
                "memory_crystallizer":
                    memory_crystallizer,

                "health_monitor":
                    authoritative_health_monitor,

                "module_registry":
                    authoritative_module_registry,

                "track_system":
                    authoritative_track_system,

                "emit":
                    emit_ref,

                "event_bus":
                    authoritative_event_bus,

                "intent_engine":
                    authoritative_intent_engine,

                "qbit":
                    authoritative_qbit,

                "qbit_dialer":
                    authoritative_dialer,

                "qbit_queue_loop":
                    authoritative_queue_loop,

                "track_context":
                    authoritative_track_context,

                "registry":
                    authoritative_registry,

                "nodes":
                    authoritative_nodes,

                "seedcore":
                    authoritative_seedcore,

                "kernel_bus":
                    authoritative_kernel_bus,

                "guardian":
                    guardian,

                "decoder":
                    decoder,

                "task_id":
                    None,

                "payload":
                    {},
            }

            try:

                import inspect

                signature = inspect.signature(
                    EthicsManager
                )

                parameters = signature.parameters

                accepts_kwargs = any(
                    parameter.kind
                    == inspect.Parameter.VAR_KEYWORD
                    for parameter
                    in parameters.values()
                )

                if not accepts_kwargs:

                    ethics_kwargs = {
                        key: value
                        for key, value
                        in ethics_kwargs.items()
                        if key in parameters
                    }

            except Exception:
                pass

            ethics_manager = EthicsManager(
                **ethics_kwargs
            )

            if ethics_manager is None:
                raise RuntimeError(
                    "EthicsManager construction failed"
                )

            _bind_system(
                ethics_manager,
                {
                    **service_dependencies,
                    "memory_crystallizer":
                        memory_crystallizer,
                    "decoder":
                        decoder,
                    "guardian":
                        guardian,
                },
                "EthicsManager.bind_system",
            )

            _attach(
                ethics_manager,
                memory_crystallizer,
                (
                    "attach_memory_crystallizer",
                    "bind_memory_crystallizer",
                ),
                (
                    "memory_crystallizer",
                    "_memory_crystallizer",
                ),
                "EthicsManager",
            )

            _attach(
                ethics_manager,
                authoritative_health_monitor,
                (
                    "attach_health_monitor",
                    "bind_health_monitor",
                ),
                (
                    "health_monitor",
                    "_health_monitor",
                ),
                "EthicsManager",
            )

            _attach(
                ethics_manager,
                authoritative_intent_engine,
                (
                    "attach_intent_engine",
                    "bind_intent_engine",
                ),
                (
                    "intent_engine",
                    "_intent_engine",
                ),
                "EthicsManager",
            )

            _attach(
                ethics_manager,
                authoritative_track_system,
                (
                    "attach_track_system",
                    "bind_track_system",
                ),
                (
                    "track_system",
                    "_track_system",
                ),
                "EthicsManager",
            )

            _attach(
                ethics_manager,
                authoritative_registry,
                (
                    "attach_registry",
                    "bind_registry",
                ),
                (
                    "registry",
                    "system_registry",
                ),
                "EthicsManager",
            )

            _attach(
                ethics_manager,
                authoritative_qbit,
                (
                    "attach_qbit",
                    "bind_qbit",
                ),
                (
                    "qbit",
                    "_qbit",
                ),
                "EthicsManager",
            )

            _attach(
                ethics_manager,
                authoritative_dialer,
                (
                    "attach_qbit_dialer",
                    "bind_qbit_dialer",
                ),
                (
                    "qbit_dialer",
                    "_qbit_dialer",
                ),
                "EthicsManager",
            )

            MODULES_STATUS[
                "EthicsManager"
            ] = True

            boot_log(
                "EthicsManager ONLINE"
            )

            _publish_status(
                "EthicsManager",
                "ONLINE",
                object_type=type(
                    ethics_manager
                ).__name__,
            )

        except Exception as exc:

            ethics_manager = None

            MODULES_STATUS[
                "EthicsManager"
            ] = False

            trace_exception(exc)

            _publish_status(
                "EthicsManager",
                "FAILED",
                error=repr(exc),
            )

        # ==================================================
        # DIALER SERVICE GRAPH
        #
        # QbitDialer remains the processing / command
        # authority. These services are attached to it,
        # never the reverse authority relationship.
        # ==================================================

        if authoritative_dialer is not None:

            dialer_service_dependencies = {

                "event_bus":
                    authoritative_event_bus,

                "qbit":
                    authoritative_qbit,

                "qbit_queue_loop":
                    authoritative_queue_loop,

                "queue_loop":
                    authoritative_queue_loop,

                "track_system":
                    authoritative_track_system,

                "track_context":
                    authoritative_track_context,

                "registry":
                    authoritative_registry,

                "nodes":
                    authoritative_nodes,

                "memory_crystallizer":
                    memory_crystallizer,

                "decoder":
                    decoder,

                "guardian":
                    guardian,

                "ethics_manager":
                    ethics_manager,

                "health_monitor":
                    authoritative_health_monitor,

                "seedcore":
                    authoritative_seedcore,

                "kernel_bus":
                    authoritative_kernel_bus,
            }

            _bind_system(
                authoritative_dialer,
                dialer_service_dependencies,
                "QbitDialer.bind_system services",
            )

            _attach(
                authoritative_dialer,
                memory_crystallizer,
                (
                    "attach_memory_crystallizer",
                    "bind_memory_crystallizer",
                ),
                (
                    "memory_crystallizer",
                ),
                "QbitDialer",
            )

            _attach(
                authoritative_dialer,
                decoder,
                (
                    "attach_decoder",
                    "bind_decoder",
                ),
                (
                    "decoder",
                ),
                "QbitDialer",
            )

            _attach(
                authoritative_dialer,
                guardian,
                (
                    "attach_guardian",
                    "bind_guardian",
                ),
                (
                    "guardian",
                ),
                "QbitDialer",
            )

            _attach(
                authoritative_dialer,
                ethics_manager,
                (
                    "attach_ethics_manager",
                    "bind_ethics_manager",
                ),
                (
                    "ethics_manager",
                ),
                "QbitDialer",
            )

        # ==================================================
        # REGISTRY PUBLICATION
        #
        # Publish the service instances to the existing
        # registry. Never create a second registry.
        # ==================================================

        if authoritative_registry is not None:

            service_registry_entries = {
                "memory_crystallizer":
                    memory_crystallizer,

                "decoder":
                    decoder,

                "guardian":
                    guardian,

                "ethics_manager":
                    ethics_manager,
            }

            for name, service in (
                service_registry_entries.items()
            ):

                if service is None:
                    continue

                registered = False

                for method_name in (
                    "register",
                    "register_module",
                    "register_system",
                    "add",
                    "set",
                ):

                    method = getattr(
                        authoritative_registry,
                        method_name,
                        None,
                    )

                    if not callable(method):
                        continue

                    try:

                        safe_call(
                            method,
                            name,
                            service,
                            default=None,
                            label=(
                                f"Registry."
                                f"{method_name}"
                                f"({name})"
                            ),
                        )

                        registered = True
                        break

                    except Exception:
                        continue

                if registered:

                    boot_log(
                        "Registry linked | "
                        f"name={name} | "
                        f"type={type(service).__name__}"
                    )

        # ==================================================
        # NODE GRAPH PUBLICATION
        #
        # Nodes receive references to the same services.
        # They do not import or construct them.
        # ==================================================

        if authoritative_nodes is not None:

            node_dependencies = {
                **service_dependencies,

                "memory_crystallizer":
                    memory_crystallizer,

                "decoder":
                    decoder,

                "guardian":
                    guardian,

                "ethics_manager":
                    ethics_manager,
            }

            _bind_system(
                authoritative_nodes,
                node_dependencies,
                "NodeRegistry.bind_system services",
            )

            for name, service in (
                (
                    "memory_crystallizer",
                    memory_crystallizer,
                ),
                (
                    "decoder",
                    decoder,
                ),
                (
                    "guardian",
                    guardian,
                ),
                (
                    "ethics_manager",
                    ethics_manager,
                ),
            ):

                if service is None:
                    continue

                for method_name in (
                    "register_node",
                    "register",
                    "add_node",
                    "attach_node",
                ):

                    method = getattr(
                        authoritative_nodes,
                        method_name,
                        None,
                    )

                    if not callable(method):
                        continue

                    try:

                        safe_call(
                            method,
                            name,
                            service,
                            default=None,
                            label=(
                                f"NodeRegistry."
                                f"{method_name}"
                                f"({name})"
                            ),
                        )

                        break

                    except Exception:
                        continue

        # ==================================================
        # FINAL SERVICE STATUS SNAPSHOT
        # ==================================================

        service_status = {
            "Memory_Crystallizer":
                memory_crystallizer is not None,

            "InstructionDecoder":
                decoder is not None,

            "Constraint_Guardian":
                guardian is not None,

            "EthicsManager":
                ethics_manager is not None,
        }

        # ----------------------------------------------
        # Publish aggregate status upward.
        # ----------------------------------------------

        _publish_status(
            "SystemServices",
            (
                "ONLINE"
                if all(service_status.values())
                else "DEGRADED"
            ),
            services=service_status,
        )

        # ==================================================
        # FINAL GLOBAL REFERENCES
        # ==================================================

        globals()[
            "memory_crystallizer"
        ] = memory_crystallizer

        globals()[
            "decoder"
        ] = decoder

        globals()[
            "guardian"
        ] = guardian

        globals()[
            "ethics_manager"
        ] = ethics_manager

        # ==================================================
        # FINAL IDENTITY VALIDATION
        #
        # No service is allowed to silently replace the
        # authoritative runtime objects.
        # ==================================================

        if globals().get(
            "event_bus"
        ) is not authoritative_event_bus:

            raise RuntimeError(
                "System service boot changed EventBus identity"
            )

        if globals().get(
            "qbit"
        ) is not authoritative_qbit:

            raise RuntimeError(
                "System service boot changed Qbit identity"
            )

        if globals().get(
            "qbit_dialer"
        ) is not authoritative_dialer:

            raise RuntimeError(
                "System service boot changed QbitDialer identity"
            )

        if (
            authoritative_track_system is not None
            and globals().get(
                "track_system"
            ) is not authoritative_track_system
        ):

            raise RuntimeError(
                "System service boot changed TrackSystem identity"
            )

        if (
            authoritative_registry is not None
            and globals().get(
                "system_registry"
            ) is not authoritative_registry
        ):

            raise RuntimeError(
                "System service boot changed Registry identity"
            )

        # ==================================================
        # FINAL BOOT REPORT
        # ==================================================

        boot_log(
            "PHASE 12 | Memory / Decoder / Guardian / Ethics "
            "COMPLETE | "
            f"memory="
            f"{'ONLINE' if memory_crystallizer else 'FAILED'} | "
            f"decoder="
            f"{'ONLINE' if decoder else 'FAILED'} | "
            f"guardian="
            f"{'ONLINE' if guardian else 'FAILED'} | "
            f"ethics="
            f"{'ONLINE' if ethics_manager else 'FAILED'}"
        )

        return {
            "memory_crystallizer":
                memory_crystallizer,

            "decoder":
                decoder,

            "guardian":
                guardian,

            "ethics_manager":
                ethics_manager,

            "event_bus":
                authoritative_event_bus,

            "qbit":
                authoritative_qbit,

            "qbit_queue_loop":
                authoritative_queue_loop,

            "qbit_dialer":
                authoritative_dialer,

            "track_system":
                authoritative_track_system,

            "registry":
                authoritative_registry,

            "nodes":
                authoritative_nodes,
        }

    except Exception as exc:

        trace_exception(exc)

        boot_log(
            "PHASE 12 | System services FAILED"
        )

        return None

# ==========================================================
# FULL-MERGE SCHEDULER BRIDGE
# ==========================================================
# Purpose:
#   Provide stable scheduler entry points for the Full-Merge
#   service registry without creating a competing scheduler.
#
# Authority:
#   QbitDialer remains the command authority.
#   QbitActionController remains the scheduler/controller
#   when available.
#
# Safety:
#   Scheduler is optional during boot.
#   Missing scheduler must never abort SEED startup.
# ==========================================================

_scheduler_instance = None
_scheduler_started = False


def _resolve_scheduler_instance(
    event_bus=None,
    qbit=None,
    qbit_dialer=None,
    orchestrator_command=None,
):

    global _scheduler_instance

    if _scheduler_instance is not None:
        return _scheduler_instance

    try:
        controller_cls = globals().get("QbitActionController")

        if controller_cls is None:
            logger.warning(
                "[Scheduler] QbitActionController not available"
            )
            return None

        kwargs = {}

        if event_bus is not None:
            kwargs["event_bus"] = event_bus

        if qbit is not None:
            kwargs["qbit"] = qbit

        if qbit_dialer is not None:
            kwargs["qbit_dialer"] = qbit_dialer

        if orchestrator_command is not None:
            kwargs["orchestrator_command"] = orchestrator_command

        # Try authoritative dependency-aware construction first.
        try:
            _scheduler_instance = controller_cls(**kwargs)

        except TypeError:
            # Existing controller may expose an older constructor.
            # Fall back without inventing unsupported arguments.
            logger.debug(
                "[Scheduler] Dependency-aware constructor rejected "
                "kwargs; using compatibility constructor"
            )

            try:
                _scheduler_instance = controller_cls()

            except TypeError:
                logger.warning(
                    "[Scheduler] QbitActionController constructor "
                    "is incompatible with Full-Merge boot"
                )
                return None

        logger.info(
            "[Scheduler] QbitActionController resolved | type=%s",
            type(_scheduler_instance).__name__,
        )

        return _scheduler_instance

    except Exception as exc:
        logger.warning(
            "[Scheduler] Controller resolution failed | %s",
            exc,
        )
        return None


def start_scheduler(
    event_bus=None,
    qbit=None,
    qbit_dialer=None,
    orchestrator_command=None,
):

    global _scheduler_started

    scheduler = _resolve_scheduler_instance(
        event_bus=event_bus,
        qbit=qbit,
        qbit_dialer=qbit_dialer,
        orchestrator_command=orchestrator_command,
    )

    if scheduler is None:
        logger.warning(
            "[Scheduler] Start skipped | controller unavailable"
        )
        return None

    if _scheduler_started:
        logger.debug(
            "[Scheduler] Start ignored | already running"
        )
        return scheduler

    try:
        start_method = getattr(
            scheduler,
            "start",
            None,
        )

        if callable(start_method):

            result = start_method()

            # Handle async start() without generating an
            # un-awaited coroutine warning.
            if inspect.isawaitable(result):

                try:
                    loop = asyncio.get_running_loop()

                    loop.create_task(
                        result,
                        name="SEED.QbitActionController.start",
                    )

                except RuntimeError:
                    logger.warning(
                        "[Scheduler] Async start deferred | "
                        "no running asyncio loop"
                    )

                    # Explicitly close coroutine when it cannot
                    # be scheduled, preventing RuntimeWarning.
                    try:
                        result.close()
                    except Exception:
                        pass

                    return scheduler

            _scheduler_started = True

            logger.info(
                "[Scheduler] QbitActionController ONLINE"
            )

            return scheduler

        # Some scheduler implementations expose start_loop()
        # instead of start().
        start_loop = getattr(
            scheduler,
            "start_loop",
            None,
        )

        if callable(start_loop):

            result = start_loop()

            if inspect.isawaitable(result):

                try:
                    loop = asyncio.get_running_loop()

                    loop.create_task(
                        result,
                        name="SEED.QbitActionController.start_loop",
                    )

                except RuntimeError:
                    try:
                        result.close()
                    except Exception:
                        pass

                    return scheduler

            _scheduler_started = True

            logger.info(
                "[Scheduler] QbitActionController LOOP ONLINE"
            )

            return scheduler

        logger.warning(
            "[Scheduler] Controller has no supported start method"
        )

        return scheduler

    except Exception as exc:
        logger.warning(
            "[Scheduler] Start failed safely | %s",
            exc,
        )
        return scheduler


def stop_scheduler(
    scheduler=None,
):

    global _scheduler_instance
    global _scheduler_started

    target = scheduler or _scheduler_instance

    if target is None:
        logger.debug(
            "[Scheduler] Stop ignored | no scheduler instance"
        )
        return True

    try:

        stop_method = getattr(
            target,
            "stop",
            None,
        )

        if callable(stop_method):

            result = stop_method()

            if inspect.isawaitable(result):

                try:
                    loop = asyncio.get_running_loop()

                    loop.create_task(
                        result,
                        name="SEED.QbitActionController.stop",
                    )

                except RuntimeError:
                    try:
                        result.close()
                    except Exception:
                        pass

            _scheduler_started = False

            logger.info(
                "[Scheduler] QbitActionController OFFLINE"
            )

            return True

        stop_loop = getattr(
            target,
            "stop_loop",
            None,
        )

        if callable(stop_loop):

            result = stop_loop()

            if inspect.isawaitable(result):

                try:
                    loop = asyncio.get_running_loop()

                    loop.create_task(
                        result,
                        name="SEED.QbitActionController.stop_loop",
                    )

                except RuntimeError:
                    try:
                        result.close()
                    except Exception:
                        pass

            _scheduler_started = False

            logger.info(
                "[Scheduler] QbitActionController LOOP OFFLINE"
            )

            return True

        logger.warning(
            "[Scheduler] Controller has no supported stop method"
        )

        return False

    except Exception as exc:
        logger.warning(
            "[Scheduler] Stop failed safely | %s",
            exc,
        )

        _scheduler_started = False

        return False

# ==========================================================
# SECTION 25B â€” FULL MERGE LEGACY / ANALYTICS SERVICES
#
# PURPOSE:
# - Restore modules present in the original main.py but absent
#   from stabilized main3.py.
# - Keep all services OPTIONAL.
# - Never allow a legacy/analytics service to destroy the
#   authoritative Qbit / EventBus / Queue / Heartbeat chain.
# - Reuse authoritative runtime objects only.
# - Construct each service at most once.
# - Keep QbitDialer as the sole command authority.
# - Keep QbitQueueLoop as the sole Qbit transport authority.
# ==========================================================

def boot_full_merge_services():

    global memory_manager
    global seed_scheduler
    global analytics_engine
    global adaptive_engine
    global seedos
    global adim_manager

    boot_log(
        "PHASE 12B | Full-merge services"
    )

    # ======================================================
    # AUTHORITATIVE RUNTIME REFERENCES
    # ======================================================

    runtime_event_bus = globals().get(
        "event_bus"
    )

    runtime_qbit = globals().get(
        "qbit"
    )

    runtime_queue_loop = globals().get(
        "queue_loop"
    )

    runtime_qbit_dialer = globals().get(
        "qbit_dialer"
    )

    runtime_track_system = globals().get(
        "track_system"
    )

    runtime_track_context = globals().get(
        "track_context"
    )

    runtime_registry = globals().get(
        "system_registry",
        globals().get("registry"),
    )

    runtime_nodes = globals().get(
        "nodes",
        globals().get("node_registry"),
    )

    runtime_seed_core = globals().get(
        "seed_core"
    )

    runtime_kernel_bus = globals().get(
        "qbit_kernel_bus",
        globals().get("kernel_bus"),
    )

    runtime_action_engine = globals().get(
        "action_engine"
    )

    runtime_intent_engine = globals().get(
        "intent_engine"
    )

    runtime_health_monitor = globals().get(
        "health_monitor"
    )

    runtime_memory_crystallizer = globals().get(
        "memory_crystallizer"
    )

    runtime_constraint_guardian = globals().get(
        "constraint_guardian"
    )

    runtime_ethics_manager = globals().get(
        "ethics_manager"
    )

    runtime_instruction_decoder = globals().get(
        "instruction_decoder"
    )

    runtime_fathud = globals().get(
        "fathud",
        globals().get("fathud_adapter"),
    )

    # ======================================================
    # AUTHORITY CHECK
    #
    # These are required infrastructure.
    # Legacy services themselves remain optional.
    # ======================================================

    if runtime_event_bus is None:
        logger.warning(
            "[FullMerge] EventBus unavailable; "
            "optional services deferred"
        )

        boot_log(
            "PHASE 12B DEFERRED | EventBus unavailable"
        )

        return {
            "memory_manager": None,
            "seed_scheduler": None,
            "analytics_engine": None,
            "adaptive_engine": None,
            "seedos": None,
            "adim_manager": None,
        }

    if runtime_qbit is None:
        logger.warning(
            "[FullMerge] Authoritative Qbit unavailable; "
            "optional services deferred"
        )

        boot_log(
            "PHASE 12B DEFERRED | Qbit unavailable"
        )

        return {
            "memory_manager": None,
            "seed_scheduler": None,
            "analytics_engine": None,
            "adaptive_engine": None,
            "seedos": None,
            "adim_manager": None,
        }

    if runtime_qbit_dialer is None:
        logger.warning(
            "[FullMerge] QbitDialer unavailable; "
            "optional services will not be promoted"
        )

    if runtime_queue_loop is None:
        logger.warning(
            "[FullMerge] QbitQueueLoop unavailable; "
            "optional services will remain transport-detached"
        )

    # ======================================================
    # HELPERS
    # ======================================================

    def _attach(
        target,
        names,
        value,
    ):

        if target is None or value is None:
            return False

        attached = False

        for name in names:

            try:

                if hasattr(target, name):

                    current = getattr(
                        target,
                        name,
                        None,
                    )

                    if current is None:
                        setattr(
                            target,
                            name,
                            value,
                        )
                        attached = True

                    elif current is value:
                        attached = True

                    else:
                        logger.warning(
                            "[FullMerge] "
                            "Authority conflict prevented | "
                            "target=%s | attr=%s | "
                            "existing_id=%s | "
                            "incoming_id=%s",
                            type(target).__name__,
                            name,
                            id(current),
                            id(value),
                        )

            except Exception as exc:
                logger.debug(
                    "[FullMerge] "
                    "Optional attach failed | "
                    "target=%s | attr=%s | error=%s",
                    type(target).__name__,
                    name,
                    exc,
                )

        return attached

    def _bind_system(
        target,
        **kwargs,
    ):
 
        if target is None:
            return False

        binder = getattr(
            target,
            "bind_system",
            None,
        )

        if not callable(binder):
            return False

        clean_kwargs = {
            key: value
            for key, value in kwargs.items()
            if value is not None
        }

        try:

            try:
                binder(
                    **clean_kwargs
                )

            except TypeError:

                # Filter against the callable signature
                # when possible instead of retrying with
                # an empty/isolated constructor.
                import inspect

                try:

                    signature = inspect.signature(
                        binder
                    )

                    accepted = {}

                    for key, value in clean_kwargs.items():

                        if key in signature.parameters:
                            accepted[key] = value

                    if accepted:
                        binder(
                            **accepted
                        )

                except Exception:
                    return False

            return True

        except Exception as exc:

            logger.debug(
                "[FullMerge] "
                "bind_system failed | target=%s | error=%s",
                type(target).__name__,
                exc,
            )

            return False

    def _register(
        name,
        value,
    ):

        if value is None:
            return

        if runtime_registry is not None:

            try:

                register = getattr(
                    runtime_registry,
                    "register",
                    None,
                )

                if callable(register):
                    register(
                        name,
                        value,
                    )

            except Exception as exc:
                logger.debug(
                    "[FullMerge] "
                    "Registry publish skipped | "
                    "name=%s | error=%s",
                    name,
                    exc,
                )

            try:
                if isinstance(
                    runtime_registry,
                    dict,
                ):
                    runtime_registry[
                        name
                    ] = value

            except Exception:
                pass

        if runtime_nodes is not None:

            try:

                register_node = getattr(
                    runtime_nodes,
                    "register",
                    None,
                )

                if callable(register_node):
                    register_node(
                        name,
                        value,
                    )

            except Exception as exc:
                logger.debug(
                    "[FullMerge] "
                    "Node publish skipped | "
                    "name=%s | error=%s",
                    name,
                    exc,
                )

            try:
                if isinstance(
                    runtime_nodes,
                    dict,
                ):
                    runtime_nodes[
                        name
                    ] = value

            except Exception:
                pass

    def _emit_status(
        service_name,
        service,
    ):

        payload = {
            "service": service_name,
            "status": (
                "online"
                if service is not None
                else "offline"
            ),
            "optional": True,
            "authority": "qbit_dialer",
            "transport": (
                "qbit_queue_loop"
                if runtime_queue_loop is not None
                else None
            ),
        }

        try:
            runtime_event_bus.emit(
                "full_merge_service_status",
                payload,
            )

        except Exception:
            try:
                runtime_event_bus.emit(
                    payload
                )
            except Exception:
                pass

        if runtime_track_system is not None:

            try:

                emitter = getattr(
                    runtime_track_system,
                    "emit",
                    None,
                )

                if callable(emitter):
                    emitter(
                        "full_merge_service_status",
                        payload,
                    )

            except Exception:
                pass

    def _dialer_attach(
        service,
        name,
    ):

        if (
            runtime_qbit_dialer is None
            or service is None
        ):
            return

        _attach(
            runtime_qbit_dialer,
            (
                name,
                name.lower(),
            ),
            service,
        )

        _bind_system(
            runtime_qbit_dialer,
            **{
                name: service,
            },
        )

    # ======================================================
    # 25B.1 â€” MEMORY MANAGER
    # ======================================================

    try:

        from seed.core.memory_manager import (
            SEEDMemoryManager,
        )

        # Reuse existing instance if already booted.
        if memory_manager is None:

            memory_manager = compatible_construct(
                SEEDMemoryManager,
                [
                    (
                        (),
                        {
                            "storage_root": str(
                                SEED_ROOT
                            ),
                            "event_bus":
                                runtime_event_bus,
                            "qbit":
                                runtime_qbit,
                            "qbit_dialer":
                                runtime_qbit_dialer,
                            "track_system":
                                runtime_track_system,
                            "track_context":
                                runtime_track_context,
                            "registry":
                                runtime_registry,
                            "nodes":
                                runtime_nodes,
                        },
                    ),
                    (
                        (),
                        {
                            "storage_root": str(
                                SEED_ROOT
                            ),
                            "event_bus":
                                runtime_event_bus,
                        },
                    ),
                    (
                        (),
                        {
                            "storage_root": str(
                                SEED_ROOT
                            ),
                        },
                    ),
                ],
                "SEEDMemoryManager",
            )

        MODULES_STATUS[
            "SEEDMemoryManager"
        ] = memory_manager is not None

        if memory_manager is not None:

            _attach(
                memory_manager,
                (
                    "event_bus",
                    "bus",
                ),
                runtime_event_bus,
            )

            _attach(
                memory_manager,
                (
                    "qbit",
                    "authoritative_qbit",
                ),
                runtime_qbit,
            )

            _attach(
                memory_manager,
                (
                    "queue_loop",
                    "qbit_queue_loop",
                ),
                runtime_queue_loop,
            )

            _attach(
                memory_manager,
                (
                    "qbit_dialer",
                    "dialer",
                ),
                runtime_qbit_dialer,
            )

            _attach(
                memory_manager,
                (
                    "track_system",
                    "track",
                ),
                runtime_track_system,
            )

            _attach(
                memory_manager,
                (
                    "registry",
                    "system_registry",
                ),
                runtime_registry,
            )

            _register(
                "memory_manager",
                memory_manager,
            )

            _dialer_attach(
                memory_manager,
                "memory_manager",
            )

            _emit_status(
                "SEEDMemoryManager",
                memory_manager,
            )

            logger.info(
                "[FullMerge] "
                "SEEDMemoryManager ONLINE"
            )

    except Exception as exc:

        memory_manager = None

        MODULES_STATUS[
            "SEEDMemoryManager"
        ] = False

        trace_exception(exc)

        logger.warning(
            "[FullMerge] "
            "SEEDMemoryManager unavailable"
        )
    # ======================================================
    # 25B.2 â€” QBIT ACTION CONTROLLER / SCHEDULER
    # ======================================================

    try:

        from seed.seed_scheduler import (
            QbitActionController,
        )

        if seed_scheduler is None:

            seed_scheduler = compatible_construct(
                QbitActionController,
                [
                    (
                        (),
                        {
                            "event_bus":
                                runtime_event_bus,
                            "emit":
                                runtime_event_bus.emit,
                            "start_scheduler":
                                start_scheduler,
                            "stop_scheduler":
                                stop_scheduler,
                            "actuator_engine":
                                runtime_action_engine,
                            "action_engine":
                                runtime_action_engine,
                            "qbit":
                                runtime_qbit,
                            "qbit_dialer":
                                runtime_qbit_dialer,
                            "orchestrator_command":
                                globals().get(
                                    "orchestrator_command"
                                ),
                        },
                    ),
                    (
                        (),
                        {
                            "event_bus":
                                runtime_event_bus,
                            "emit":
                                runtime_event_bus.emit,
                            "start_scheduler":
                                start_scheduler,
                            "stop_scheduler":
                                stop_scheduler,
                            "qbit":
                                runtime_qbit,
                            "qbit_dialer":
                                runtime_qbit_dialer,
                        },
                    ),
                    (
                        (),
                        {
                            "event_bus":
                                runtime_event_bus,
                            "emit":
                                runtime_event_bus.emit,
                            "start_scheduler":
                                start_scheduler,
                            "stop_scheduler":
                                stop_scheduler,
                        },
                    ),
                ],
                "QbitActionController",
            )

        MODULES_STATUS[
            "QbitActionController"
        ] = seed_scheduler is not None

        if seed_scheduler is not None:

            _attach(
                seed_scheduler,
                (
                    "event_bus",
                    "bus",
                ),
                runtime_event_bus,
            )

            _attach(
                seed_scheduler,
                (
                    "qbit",
                    "authoritative_qbit",
                ),
                runtime_qbit,
            )

            _attach(
                seed_scheduler,
                (
                    "queue_loop",
                    "qbit_queue_loop",
                ),
                runtime_queue_loop,
            )

            _attach(
                seed_scheduler,
                (
                    "qbit_dialer",
                    "dialer",
                ),
                runtime_qbit_dialer,
            )

            _attach(
                seed_scheduler,
                (
                    "actuator_engine",
                    "action_engine",
                ),
                runtime_action_engine,
            )

            _attach(
                seed_scheduler,
                (
                    "track_system",
                    "track",
                ),
                runtime_track_system,
            )

            _attach(
                seed_scheduler,
                (
                    "registry",
                    "system_registry",
                ),
                runtime_registry,
            )

            _register(
                "seed_scheduler",
                seed_scheduler,
            )

            _dialer_attach(
                seed_scheduler,
                "seed_scheduler",
            )

            _emit_status(
                "QbitActionController",
                seed_scheduler,
            )

            logger.info(
                "[FullMerge] "
                "QbitActionController ONLINE"
            )

    except Exception as exc:

        seed_scheduler = None

        MODULES_STATUS[
            "QbitActionController"
        ] = False

        trace_exception(exc)

        logger.warning(
            "[FullMerge] "
            "QbitActionController unavailable"
        )
    # ======================================================
    # 25B.3 â€” ANALYTICS ENGINE
    # ======================================================

    try:

        from seed.analytics.analytics_engine import (
            SEEDAnalyticsEngine,
        )

        if analytics_engine is None:

            analytics_engine = compatible_construct(
                SEEDAnalyticsEngine,
                [
                    (
                        (),
                        {
                            "qbit_dialer":
                                runtime_qbit_dialer,
                            "qbit":
                                runtime_qbit,
                            "queue_loop":
                                runtime_queue_loop,
                            "storage_root":
                                str(SEED_ROOT),
                            "event_bus":
                                runtime_event_bus,
                            "emit":
                                runtime_event_bus.emit,
                            "stop_scheduler":
                                stop_scheduler,
                            "start_scheduler":
                                start_scheduler,
                            "actuator_engine":
                                runtime_action_engine,
                            "action_engine":
                                runtime_action_engine,
                            "intent_engine":
                                runtime_intent_engine,
                            "orchestrator_command":
                                globals().get(
                                    "orchestrator_command"
                                ),
                            "track_system":
                                runtime_track_system,
                            "registry":
                                runtime_registry,
                            "nodes":
                                runtime_nodes,
                        },
                    ),
                    (
                        (),
                        {
                            "qbit_dialer":
                                runtime_qbit_dialer,
                            "event_bus":
                                runtime_event_bus,
                            "emit":
                                runtime_event_bus.emit,
                        },
                    ),
                    (
                        (),
                        {
                            "qbit_dialer":
                                runtime_qbit_dialer,
                            "emit":
                                runtime_event_bus.emit,
                        },
                    ),
                ],
                "SEEDAnalyticsEngine",
            )

        MODULES_STATUS[
            "SEEDAnalyticsEngine"
        ] = analytics_engine is not None

        if analytics_engine is not None:

            _attach(
                analytics_engine,
                (
                    "event_bus",
                    "bus",
                ),
                runtime_event_bus,
            )

            _attach(
                analytics_engine,
                (
                    "qbit",
                    "authoritative_qbit",
                ),
                runtime_qbit,
            )

            _attach(
                analytics_engine,
                (
                    "qbit_dialer",
                    "dialer",
                ),
                runtime_qbit_dialer,
            )

            _attach(
                analytics_engine,
                (
                    "queue_loop",
                    "qbit_queue_loop",
                ),
                runtime_queue_loop,
            )

            _attach(
                analytics_engine,
                (
                    "track_system",
                    "track",
                ),
                runtime_track_system,
            )

            _attach(
                analytics_engine,
                (
                    "registry",
                    "system_registry",
                ),
                runtime_registry,
            )

            _attach(
                analytics_engine,
                (
                    "nodes",
                    "node_registry",
                ),
                runtime_nodes,
            )

            _attach(
                analytics_engine,
                (
                    "action_engine",
                    "actuator_engine",
                ),
                runtime_action_engine,
            )

            _register(
                "analytics_engine",
                analytics_engine,
            )

            _dialer_attach(
                analytics_engine,
                "analytics_engine",
            )

            _emit_status(
                "SEEDAnalyticsEngine",
                analytics_engine,
            )

            logger.info(
                "[FullMerge] "
                "SEEDAnalyticsEngine ONLINE"
            )

    except Exception as exc:

        analytics_engine = None

        MODULES_STATUS[
            "SEEDAnalyticsEngine"
        ] = False

        trace_exception(exc)

        logger.warning(
            "[FullMerge] "
            "SEEDAnalyticsEngine unavailable"
        )

    analytics_engine.bind_runtime(
        event_bus=runtime_event_bus,
        qbit=runtime_qbit,
        qbit_queue_loop=runtime_queue_loop,
        qbit_dialer=runtime_qbit_dialer,
        intent_engine=runtime_intent_engine,
        track_system=runtime_track_system,
        registry=runtime_registry,
        nodes=runtime_nodes,
    )

    analytics_engine.validate_runtime_identity(
        event_bus=runtime_event_bus,
        qbit=runtime_qbit,
        qbit_queue_loop=runtime_queue_loop,
        qbit_dialer=runtime_qbit_dialer,
        intent_engine=runtime_intent_engine,
    )

    # ======================================================
    # 25B.4 â€” ADAPTIVE ENGINE
    # ======================================================

    try:

        from seed.core.adaptive_engine import (
            SEEDAdaptiveEngine,
        )

        if adaptive_engine is None:

            adaptive_engine = compatible_construct(
                SEEDAdaptiveEngine,
                [
                    (
                        (),
                        {
                            "event_bus":
                                runtime_event_bus,
                            "emit":
                                runtime_event_bus.emit,
                            "qbit":
                                runtime_qbit,
                            "qbit_dialer":
                                runtime_qbit_dialer,
                            "queue_loop":
                                runtime_queue_loop,
                            "track_system":
                                runtime_track_system,
                            "track_context":
                                runtime_track_context,
                            "registry":
                                runtime_registry,
                            "nodes":
                                runtime_nodes,
                            "seedcore":
                                seedcore,
                            "analytics_engine":
                                analytics_engine,
                            "intent_engine":
                                runtime_intent_engine,
                            "adaptive_priority_engine":
                                adaptive_priority_engine,
                            "growth_tree":
                                growth_tree,
                            "memory_manager":
                                memory_manager,
                            "constraint_guardian":
                                runtime_constraint_guardian,
                            "ethics_manager":
                                runtime_ethics_manager,
                        },
                    ),
                    (
                        (),
                        {
                            "event_bus":
                                runtime_event_bus,
                            "emit":
                                runtime_event_bus.emit,
                        },
                    ),
                    (
                        (),
                        {
                            "emit":
                                runtime_event_bus.emit,
                        },
                    ),
                ],
                "SEEDAdaptiveEngine",
            )

        MODULES_STATUS[
            "SEEDAdaptiveEngine"
        ] = adaptive_engine is not None

        if adaptive_engine is not None:

            # --------------------------------------------------
            # AUTHORITATIVE RUNTIME BINDING
            # --------------------------------------------------

            bind_runtime = getattr(
                adaptive_engine,
                "bind_runtime",
                None,
            )

            if callable(bind_runtime):

                bind_runtime(
                    event_bus=runtime_event_bus,
                    qbit=runtime_qbit,
                    qbit_queue_loop=runtime_queue_loop,
                    qbit_dialer=runtime_qbit_dialer,
                    track_system=runtime_track_system,
                    registry=runtime_registry,
                    nodes=runtime_nodes,
                    analytics_engine=analytics_engine,
                    intent_engine=runtime_intent_engine,
                    adaptive_priority_engine=adaptive_priority_engine,
                    growth_tree=growth_tree,
                    memory_manager=memory_manager,
                    seedcore=seedcore,
                    constraint_guardian=runtime_constraint_guardian,
                    ethics_manager=runtime_ethics_manager,
                    track_context=runtime_track_context,
                    emit=runtime_event_bus.emit,
                )

            # --------------------------------------------------
            # DIRECT AUTHORITATIVE REFERENCES
            # --------------------------------------------------

            _attach(
                adaptive_engine,
                (
                    "event_bus",
                    "bus",
                ),
                runtime_event_bus,
            )

            _attach(
                adaptive_engine,
                (
                    "qbit",
                    "authoritative_qbit",
                ),
                runtime_qbit,
            )

            _attach(
                adaptive_engine,
                (
                    "qbit_dialer",
                    "dialer",
                ),
                runtime_qbit_dialer,
            )

            _attach(
                adaptive_engine,
                (
                    "queue_loop",
                    "qbit_queue_loop",
                ),
                runtime_queue_loop,
            )

            _attach(
                adaptive_engine,
                (
                    "track_system",
                    "track",
                ),
                runtime_track_system,
            )

            _attach(
                adaptive_engine,
                (
                    "track_context",
                    "context",
                ),
                runtime_track_context,
            )

            _attach(
                adaptive_engine,
                (
                    "registry",
                    "system_registry",
                ),
                runtime_registry,
            )

            _attach(
                adaptive_engine,
                (
                    "nodes",
                    "node_registry",
                ),
                runtime_nodes,
            )

            _attach(
                adaptive_engine,
                (
                    "seedcore",
                    "core",
                ),
                seedcore,
            )

            _attach(
                adaptive_engine,
                (
                    "analytics_engine",
                    "analytics",
                ),
                analytics_engine,
            )

            _attach(
                adaptive_engine,
                (
                    "memory_manager",
                    "memory",
                ),
                memory_manager,
            )

            _attach(
                adaptive_engine,
                (
                    "constraint_guardian",
                    "guardian",
                ),
                runtime_constraint_guardian,
            )

            _attach(
                adaptive_engine,
                (
                    "ethics_manager",
                    "ethics",
                ),
                runtime_ethics_manager,
            )

            # --------------------------------------------------
            # AUTHORITATIVE IDENTITY VALIDATION
            # --------------------------------------------------

            bound_event_bus = getattr(
                adaptive_engine,
                "event_bus",
                getattr(
                    adaptive_engine,
                    "bus",
                    None,
                ),
            )

            if (
                runtime_event_bus is not None
                and bound_event_bus is not runtime_event_bus
            ):
                raise RuntimeError(
                    "[SEEDAdaptiveEngine] "
                    "EventBus identity mismatch"
                )

            bound_qbit = getattr(
                adaptive_engine,
                "qbit",
                getattr(
                    adaptive_engine,
                    "authoritative_qbit",
                    None,
                ),
            )

            if (
                runtime_qbit is not None
                and bound_qbit is not runtime_qbit
            ):
                raise RuntimeError(
                    "[SEEDAdaptiveEngine] "
                    "Qbit identity mismatch"
                )

            bound_dialer = getattr(
                adaptive_engine,
                "qbit_dialer",
                getattr(
                    adaptive_engine,
                    "dialer",
                    None,
                ),
            )

            if (
                runtime_qbit_dialer is not None
                and bound_dialer is not runtime_qbit_dialer
            ):
                raise RuntimeError(
                    "[SEEDAdaptiveEngine] "
                    "QbitDialer identity mismatch"
                )

            bound_queue_loop = getattr(
                adaptive_engine,
                "queue_loop",
                getattr(
                    adaptive_engine,
                    "qbit_queue_loop",
                    None,
                ),
            )

            if (
                runtime_queue_loop is not None
                and bound_queue_loop is not runtime_queue_loop
            ):
                raise RuntimeError(
                    "[SEEDAdaptiveEngine] "
                    "QbitQueueLoop identity mismatch"
                )

            _register(
                "adaptive_engine",
                adaptive_engine,
            )

            _dialer_attach(
                adaptive_engine,
                "adaptive_engine",
            )

            _emit_status(
                "SEEDAdaptiveEngine",
                adaptive_engine,
            )

            logger.info(
                "[FullMerge] "
                "SEEDAdaptiveEngine ONLINE"
            )

    except Exception as exc:

        adaptive_engine = None

        MODULES_STATUS[
            "SEEDAdaptiveEngine"
        ] = False

        trace_exception(exc)

        logger.warning(
            "[FullMerge] "
            "SEEDAdaptiveEngine unavailable"
        )
    # ======================================================
    # 25B.5 â€” SYS_OS
    # ======================================================

    try:

        from seed.systemutils.Sys_OS_FullSEED_RL import (
            SEEDOS,
        )

        # IMPORTANT:
        # The authoritative global is `seedos`.
        # Do not create/use a separate `seed_os` instance.

        if seedos is None:

            seedos = compatible_construct(
                SEEDOS,
                [
                    (
                        (),
                        {
                            "storage_root":
                                str(SEED_ROOT),
                            "event_bus":
                                runtime_event_bus,
                            "qbit_dialer":
                                runtime_qbit_dialer,
                            "queue_loop":
                                runtime_queue_loop,
                            "track_system":
                                runtime_track_system,
                            "registry":
                                runtime_registry,
                            "nodes":
                                runtime_nodes,
                            "seedcore":
                                seedcore,
                        },
                    ),
                    (
                        (),
                        {
                            "storage_root":
                                str(SEED_ROOT),
                            "event_bus":
                                runtime_event_bus,
                        },
                    ),
                    (
                        (),
                        {
                            "storage_root":
                                str(SEED_ROOT),
                        },
                    ),
                ],
                "SEEDOS",
            )

        MODULES_STATUS[
            "SEEDOS"
        ] = seedos is not None

        if seedos is not None:

            _attach(
                seedos,
                (
                    "event_bus",
                    "bus",
                ),
                runtime_event_bus,
            )

            _attach(
                seedos,
                (
                    "qbit",
                    "authoritative_qbit",
                ),
                runtime_qbit,
            )

            _attach(
                seedos,
                (
                    "qbit_dialer",
                    "dialer",
                ),
                runtime_qbit_dialer,
            )

            _attach(
                seedos,
                (
                    "queue_loop",
                    "qbit_queue_loop",
                ),
                runtime_queue_loop,
            )

            _attach(
                seedos,
                (
                    "track_system",
                    "track",
                ),
                runtime_track_system,
            )

            _attach(
                seedos,
                (
                    "registry",
                    "system_registry",
                ),
                runtime_registry,
            )

            _attach(
                seedos,
                (
                    "nodes",
                    "node_registry",
                ),
                runtime_nodes,
            )

            _attach(
                seedos,
                (
                    "seedcore",
                    "core",
                ),
                seedcore,
            )

            _register(
                "seedos",
                seedos,
            )

            _dialer_attach(
                seedos,
                "seedos",
            )

            _emit_status(
                "SEEDOS",
                seedos,
            )

            logger.info(
                "[FullMerge] "
                "SEEDOS ONLINE"
            )

    except Exception as exc:

        seedos = None

        MODULES_STATUS[
            "SEEDOS"
        ] = False

        trace_exception(exc)

        logger.warning(
            "[FullMerge] "
            "SEEDOS unavailable"
        )

    # ======================================================
    # 25B.6 â€” ADIM MANAGER
    # ======================================================

    try:

        from seed.systemutils.Adim_Manager import (
            AdimManager,
        )

        if adim_manager is None:

            adim_manager = compatible_construct(
                AdimManager,
                [
                    (
                        (),
                        {
                            "event_bus":
                                runtime_event_bus,
                            "qbit":
                                runtime_qbit,
                            "qbit_dialer":
                                runtime_qbit_dialer,
                            "queue_loop":
                                runtime_queue_loop,
                            "track_system":
                                runtime_track_system,
                            "registry":
                                runtime_registry,
                            "nodes":
                                runtime_nodes,
                            "seed_core":
                                runtime_seed_core,
                        },
                    ),
                    (
                        (),
                        {
                            "event_bus":
                                runtime_event_bus,
                        },
                    ),
                    (
                        (),
                        {},
                    ),
                ],
                "AdimManager",
            )

        MODULES_STATUS[
            "AdimManager"
        ] = adim_manager is not None

        if adim_manager is not None:

            _attach(
                adim_manager,
                (
                    "event_bus",
                    "bus",
                ),
                runtime_event_bus,
            )

            _attach(
                adim_manager,
                (
                    "qbit",
                    "authoritative_qbit",
                ),
                runtime_qbit,
            )

            _attach(
                adim_manager,
                (
                    "qbit_dialer",
                    "dialer",
                ),
                runtime_qbit_dialer,
            )

            _attach(
                adim_manager,
                (
                    "queue_loop",
                    "qbit_queue_loop",
                ),
                runtime_queue_loop,
            )

            _attach(
                adim_manager,
                (
                    "track_system",
                    "track",
                ),
                runtime_track_system,
            )

            _attach(
                adim_manager,
                (
                    "registry",
                    "system_registry",
                ),
                runtime_registry,
            )

            _attach(
                adim_manager,
                (
                    "nodes",
                    "node_registry",
                ),
                runtime_nodes,
            )

            _attach(
                adim_manager,
                (
                    "seed_core",
                    "core",
                ),
                runtime_seed_core,
            )

            _register(
                "adim_manager",
                adim_manager,
            )

            _dialer_attach(
                adim_manager,
                "adim_manager",
            )

            _emit_status(
                "AdimManager",
                adim_manager,
            )

            logger.info(
                "[FullMerge] "
                "AdimManager ONLINE"
            )

    except Exception as exc:

        adim_manager = None

        MODULES_STATUS[
            "AdimManager"
        ] = False

        trace_exception(exc)

        logger.warning(
            "[FullMerge] "
            "AdimManager unavailable"
        )

    # ======================================================
    # FINAL AUTHORITATIVE IDENTITY VALIDATION
    # ======================================================

    authority_checks = {
        "event_bus":
            runtime_event_bus is globals().get(
                "event_bus"
            ),

        "qbit":
            runtime_qbit is globals().get(
                "qbit"
            ),

        "queue_loop":
            (
                runtime_queue_loop is None
                or runtime_queue_loop
                is globals().get(
                    "queue_loop"
                )
            ),

        "qbit_dialer":
            (
                runtime_qbit_dialer is None
                or runtime_qbit_dialer
                is globals().get(
                    "qbit_dialer"
                )
            ),
    }

    if not all(
        authority_checks.values()
    ):

        logger.error(
            "[FullMerge] "
            "AUTHORITATIVE IDENTITY VALIDATION FAILED | "
            "%s",
            authority_checks,
        )

    else:

        logger.info(
            "[FullMerge] "
            "Authoritative runtime identity preserved"
        )

    # ======================================================
    # FINAL SERVICE REPORT
    # ======================================================

    logger.info(
        "[FullMerge] Services complete | "
        "memory=%s | "
        "scheduler=%s | "
        "analytics=%s | "
        "adaptive=%s | "
        "sys_os=%s | "
        "adim=%s",
        bool(memory_manager),
        bool(seed_scheduler),
        bool(analytics_engine),
        bool(adaptive_engine),
        bool(seedos),
        bool(adim_manager),
    )

    boot_log(
        "PHASE 12B COMPLETE | "
        "Full-merge optional services initialized"
    )

    return {
        "memory_manager":
            memory_manager,

        "seed_scheduler":
            seed_scheduler,

        "analytics_engine":
            analytics_engine,

        "adaptive_engine":
            adaptive_engine,

        "sys_os":
            seedos,

        "adim_manager":
            adim_manager,
    }
# =========================================================================
# ==========================================================
# SECTION 25C â€” ACTION ENGINE
# VERSION: 1.0.0
# BUILD: AUTHORITATIVE CORE BINDING
#
# PURPOSE:
#
# - Construct exactly one authoritative ActionEngine
# - Bind it to the existing QbitDialer
# - Preserve the existing QbitQueueLoop
# - Preserve the existing Qbit
# - Preserve the existing cognitive systems
# - Preserve EthicsManager / TrackSystem / Registry
# - Preserve DeviceManager / Heartbeat / Oracle
# - Do NOT create another runtime authority
#
# CORE CHAIN:
#
# Qbit
#   â†“
# QbitQueueLoop
#   â†“
# QbitDialer
#   â†“
# ComputeBrain
#   â†“
# TransformerBrain
#   â†“
# ActionEngine
#   â†“
# QbitDialer command admission
#
# ==========================================================

def boot_action_engine():

    global action_engine

    boot_log(
        "PHASE 10B | ActionEngine"
    )

    # ------------------------------------------------------
    # Reset only the main-level reference.
    #
    # This does NOT create runtime infrastructure.
    # ------------------------------------------------------

    action_engine = None

    try:

        # --------------------------------------------------
        # IMPORT
        # --------------------------------------------------

        from seed.core.actions import ActionEngine

        # --------------------------------------------------
        # RESOLVE AUTHORITATIVE RUNTIME OBJECTS
        # --------------------------------------------------

        runtime_qbit = globals().get(
            "qbit",
            None,
        )

        runtime_qbit_dialer = globals().get(
            "qbit_dialer",
            None,
        )

        queue_loop_obj = globals().get(
            "queue_loop",
            None,
        )

        if queue_loop_obj is None:
            queue_loop_obj = getattr(
                runtime_qbit_dialer_dialer,
                "queue_loop",
                None,
            )

        if queue_loop_obj is None:
            queue_loop_obj = getattr(
                qbit_dialer,
                "qbit_queue_loop",
                None,
            )

        compute_brain = getattr(
            qbit_dialer,
            "compute_brain",
            None,
        )

        if compute_brain is None:
            compute_brain = getattr(
                runtime_qbit_dialer,
                "computebrain",
                None,
            )

        if compute_brain is None:
            compute_brain = globals().get(
                "compute_brain",
                None,
            )

        if compute_brain is None:
            compute_brain = globals().get(
            "computebrain",
            None,
        )


        transformer_brain = getattr(
            qbit_dialer,
            "transformer_brain",
            None,
        )

        if transformer_brain is None:
            transformer_brain = getattr(
                runtime_qbit_dialer,
                "transformerbrain",
                None,
            )

        if transformer_brain is None:
            transformer_brain = globals().get(
                "transformer_brain",
                None,
            )

        if transformer_brain is None:
            transformer_brain = globals().get(
            "transformerbrain",
            None,
        )
        ethics = globals().get(
            "ethics_manager",
            None,
        )

        track_system = globals().get(
            "track_system",
            None,
        )

        registry = globals().get(
            "registry",
            None,
        )

        if registry is None:
            registry = globals().get(
                "system_registry",
                None,
            )

        node_registry = globals().get(
            "node_registry",
            None,
        )

        device_manager = globals().get(
            "device_manager",
            None,
        )

        heartbeat = globals().get(
            "heartbeat",
            None,
        )

        oracle = globals().get(
            "oracle",
            None,
        )

        # --------------------------------------------------
        # REQUIRED AUTHORITY CHECKS
        # --------------------------------------------------

        if runtime_qbit is None:
            raise RuntimeError(
                "ActionEngine requires authoritative Qbit"
            )

        if runtime_qbit_dialer is None:
            raise RuntimeError(
                "ActionEngine requires authoritative runtime QbitDialer"
            )

        if queue_loop_obj is None:
            raise RuntimeError(
                "ActionEngine requires authoritative QbitQueueLoop"
            )

        if compute_brain is None:
            raise RuntimeError(
                "ActionEngine requires ComputeBrain"
            )

        if transformer_brain is None:
            raise RuntimeError(
                "ActionEngine requires TransformerBrain"
            )

        # --------------------------------------------------
        # CONSTRUCT EXACTLY ONE ACTION ENGINE
        # --------------------------------------------------
        #
        # ActionEngine itself does NOT create:
        #
        # - Qbit
        # - QbitQueueLoop
        # - QbitDialer
        # - EventBus
        # - worker
        # - private command plane
        #
        # It receives references to the existing authorities.
        # --------------------------------------------------
# ==========================================================
# AUTHORITATIVE QBIT DIALER BINDING
# ==========================================================

        runtime_qbit_dialer = globals().get("qbit_dialer")

        if runtime_qbit_dialer is None:
            raise RuntimeError(
                "ActionEngine boot failed: authoritative QbitDialer is not loaded"
            )

        action_engine = ActionEngine(
            qbit=runtime_qbit,
            qbit_dialer=runtime_qbit_dialer,
            qbit_queue_loop=queue_loop_obj,
            compute_brain=compute_brain,
            transformer_brain=transformer_brain,
            ethics=ethics_manager,
            track_system=track_system,
            registry=registry,
            node_registry=node_registry,
            device_manager=device_manager,
            heartbeat=heartbeat,
            oracle=oracle,
        )

        if action_engine is None:
            raise RuntimeError(
                "ActionEngine construction returned None"
            )

        # --------------------------------------------------
        # BIND TO AUTHORITATIVE QBIT DIALER
        # --------------------------------------------------
        # --------------------------------------------------
        # BIND TO AUTHORITATIVE QBIT DIALER
        # --------------------------------------------------
        #
        # QbitDialer already owns the late-binding contract.
        # Do NOT invent or require attach_action_engine().
        # --------------------------------------------------

        late_bind = getattr(
            runtime_qbit_dialer,
            "_bind_late_dependencies",
            None,
        )

        if not callable(late_bind):
            raise RuntimeError(
                "QbitDialer does not expose "
                "_bind_late_dependencies()"
            )

        late_bind(
            action_engine=action_engine,
        )
        # --------------------------------------------------
        # EXACT OBJECT IDENTITY VALIDATION
        # --------------------------------------------------

#        dialer_action_engine = getattr(
#            runtime_qbit_dialer,
#            "action_engine",
#            None,
#        )

        if qbit_dialer is not runtime_qbit_dialer:
            raise RuntimeError(
                "QbitDialer authoritative identity changed during ActionEngine binding"
            )

        if (
            getattr(
                action_engine,
                "qbit_dialer",
                None,
            )
            is not runtime_qbit_dialer
        ):
            raise RuntimeError(
                "ActionEngine QbitDialer identity mismatch"
            )
        # --------------------------------------------------
        # VERIFY AUTHORITATIVE REFERENCES
        # --------------------------------------------------

        if getattr(runtime_qbit_dialer, "action_engine", None) is not action_engine:
            raise RuntimeError(
                "QbitDialer ActionEngine identity mismatch"
            )

        if qbit is not runtime_qbit:
            raise RuntimeError(
                "Qbit authoritative identity changed during ActionEngine binding"
            )

        if (
            getattr(
                action_engine,
                "qbit_queue_loop",
                None,
            )
            is not queue_loop_obj
        ):
            raise RuntimeError(
                "ActionEngine QbitQueueLoop identity mismatch"
            )

        # --------------------------------------------------
        # STATUS
        # --------------------------------------------------

        MODULES_STATUS[
            "ActionEngine"
        ] = True

        boot_log(
            "[ActionEngine] "
            "QbitDialer â†’ ActionEngine LINKED | "
            f"id={id(action_engine)}"
        )

        logger.info(
            "[ActionEngine] Authoritative binding complete | "
            "action_engine=%s | "
            "dialer=%s | "
            "qbit=%s | "
            "queue_loop=%s | "
            "dialer_action_engine=%s | "
            "compute=%s | "
            "transformer=%s | action_engine_linked=%s",
            id(action_engine),
            id(runtime_qbit_dialer),
            id(runtime_qbit),
            id(queue_loop_obj),
            id(compute_brain),
            id(transformer_brain),
            id(getattr(runtime_qbit_dialer, "action_engine", None)),
            getattr(runtime_qbit_dialer, "action_engine", None) is action_engine,
        )

        # --------------------------------------------------
        # COMPLETE COGNITIVE INPUT BINDING
        # --------------------------------------------------
        try:
            if compute_brain is not None and hasattr(compute_brain, "bind_systems"):
                compute_brain.bind_systems(
                    event_bus=event_bus,
                    track_system=track_system,
                    action_engine=action_engine,
                    intent_engine=intent_engine,
                    analytics_engine=analytics_engine,
                    adaptive_engine=adaptive_engine,
                    adaptive_priority_engine=adaptive_priority_engine,
                    transformer_brain=transformer_brain,
                    registry=registry,
                    encoder=cognition_binary_encoder or qbit_encoder,
                )
                compute_ok = all(
                    getattr(compute_brain, name, None) is not None
                    for name in (
                        "action_engine",
                        "intent_engine",
                        "analytics_engine",
                        "adaptive_engine",
                        "adaptive_priority_engine",
                        "transformer_brain",
                    )
                )
                MODULES_STATUS["ComputeBrainFullBinding"] = compute_ok
        except Exception as bind_exc:
            MODULES_STATUS["ComputeBrainFullBinding"] = False
            boot_warn(f"ComputeBrain full cognitive binding deferred: {bind_exc}")

        return action_engine

    except Exception as exc:

        action_engine = None

        MODULES_STATUS[
            "ActionEngine"
        ] = False

        logger.error(
            "[ActionEngine] authoritative binding failed | %s",
            exc,
        )

        trace_exception(
            exc
        )

        raise
# ==========================================================
# SECTION 26 â€” SEED CORE
# VERSION: 6.1.0
# BUILD: CHANNEL-AWARE BOOT STABILIZATION
#
# PURPOSE:
# - Initialize SEEDCore after core dependencies are online
# - Preserve QbitQueueLoop integration
# - Preserve ChannelManager integration
# - Preserve EventBus / Heartbeat / TrackSystem
# - Preserve Intent / Ethics / Memory integration
# - Preserve Orchestrator command integration
# - Adapt safely to the actual SEEDCore constructor
# - Do not weaken SEEDCore dependency validation
#
# CORE CHAIN:
#
# Qbit
#   â†“
# QbitDialer
#   â†“
# QbitQueueLoop
#   â†“
# EventBus
#   â†“
# TrackSystem
#   â†“
# ChannelManager
#   â†“
# IntentEngine
#   â†“
# EthicsManager
#   â†“
# Memory_Crystallizer
#   â†“
# SEEDOrchestrator
#   â†“
# SEEDCore
#
# ==========================================================

def boot_seedcore():

    global seedcore
    global core

    boot_log(
        "PHASE 13 | SEEDCore"
    )

    seedcore = None
    core = None

    try:

        # ------------------------------------------------------
        # Import SEEDCore
        # ------------------------------------------------------

        from seed_init_full import SEEDCore

        # ------------------------------------------------------
        # Track identity
        # ------------------------------------------------------

        track_result = gen_track_id(
            "CORE"
        )

        if isinstance(
            track_result,
            dict,
        ):

            track_id = track_result.get(
                "track_id"
            )

        else:

            track_id = str(
                track_result
            )

        # ------------------------------------------------------
        # Resolve EventBus emitter
        # ------------------------------------------------------

        emit_callable = getattr(
            event_bus,
            "emit",
            None,
        )

        if not callable(
            emit_callable
        ):

            emit_callable = safe_emit

        # ------------------------------------------------------
        # Resolve parent
        # ------------------------------------------------------

        seedcore_parent = root or parent

        if seedcore_parent is None:
            raise RuntimeError("SEEDCore parent/root was not prepared by main.py")

        if threading.current_thread() is not threading.main_thread():
            raise RuntimeError("SEEDCore construction attempted outside the process main thread")

        # ------------------------------------------------------
        # Dependency diagnostics
        # ------------------------------------------------------

        boot_log(
            "[SEEDCore] "
            "Resolving dependencies"
        )

        boot_log(
            "[SEEDCore] "
            f"event_bus="
            f"{type(event_bus).__name__ if event_bus is not None else 'None'}"
        )

        boot_log(
            "[SEEDCore] "
            f"qbit="
            f"{type(qbit).__name__ if qbit is not None else 'None'}"
        )

        boot_log(
            "[SEEDCore] "
            f"qbit_loop="
            f"{type(queue_loop).__name__ if queue_loop is not None else 'None'}"
        )

        boot_log(
            "[SEEDCore] "
            f"channel_manager="
            f"{type(cm).__name__ if cm is not None else 'None'}"
        )

        boot_log(
            "[SEEDCore] "
            f"track_system="
            f"{type(track_system).__name__ if track_system is not None else 'None'}"
        )

        boot_log(
            "[SEEDCore] "
            f"intent_engine="
            f"{type(intent_engine).__name__ if intent_engine is not None else 'None'}"
        )

        boot_log(
            "[SEEDCore] "
            f"ethics_manager="
            f"{type(ethics_manager).__name__ if ethics_manager is not None else 'None'}"
        )

        boot_log(
            "[SEEDCore] "
            f"memory_crystallizer="
            f"{type(memory_crystallizer).__name__ if memory_crystallizer is not None else 'None'}"
        )

        boot_log(
            "[SEEDCore] "
            f"orchestrator_command="
            f"{type(orchestrator_command).__name__ if orchestrator_command is not None else 'None'}"
        )

        # ------------------------------------------------------
        # Validate dependencies
        # ------------------------------------------------------

        missing = []

        if not callable(
            emit_callable
        ):
            missing.append(
                "emit"
            )

        if queue_loop is None:
            missing.append(
                "qbit_loop"
            )

        if cm is None:
            missing.append(
                "channel_manager"
            )

        if ethics_manager is None:
            missing.append(
                "ethics_manager"
            )

        if intent_engine is None:
            missing.append(
                "intent_engine"
            )

        if memory_crystallizer is None:
            missing.append(
                "memory_crystallizer"
            )

        if orchestrator_command is None:
            missing.append(
                "orchestrator_command"
            )

        if missing:

            message = (
                "SEEDCore dependencies unavailable: "
                + ", ".join(
                    missing
                )
            )

            boot_log(
                "[BOOT ERROR] "
                + message
            )

            raise RuntimeError(
                message
            )

        # ------------------------------------------------------
        # Inspect the actual constructor.
        #
        # This prevents us from guessing whether
        # channel_manager is positional or keyword-based.
        # ------------------------------------------------------

        import inspect

        try:

            signature = inspect.signature(
                SEEDCore
            )

            boot_log(
                "[SEEDCore] Constructor signature: "
                f"{signature}"
            )

        except Exception as signature_error:

            signature = None

            boot_log(
                "[SEEDCore] "
                f"Signature inspection unavailable: {signature_error}"
            )

        # ------------------------------------------------------
        # Base required constructor values.
        #
        # These correspond to the seven dependencies reported
        # by the previous TypeError.
        # ------------------------------------------------------

        positional_dependencies = (
            emit_callable,
            seedcore_parent,
            queue_loop,
            ethics_manager,
            intent_engine,
            memory_crystallizer,
            orchestrator_command,
        )

        # ------------------------------------------------------
        # Build keyword extensions for constructor parameters
        # that are explicitly present.
        # ------------------------------------------------------

        optional_kwargs = {
            "channel_manager": cm,
            "track_system": track_system,
            "event_bus": event_bus,
            "fiveg": fiveg,
            "qbit": qbit,
            "track_id": track_id,
            "task_id": None,
            "payload": {},
            "intent_engine": intent_engine,
            "agent_manager": agent_manager,
            "heartbeat": heartbeat,
            "backup_root": BACKUP_ROOT,
            "backup_interval_sec": BACKUP_INTERVAL_SEC,
            "auto_backup": True,
        }

        # ------------------------------------------------------
        # Remove parameters already supplied positionally.
        #
        # This prevents:
        #
        # TypeError:
        # got multiple values for argument ...
        # ------------------------------------------------------

        if signature is not None:

            try:

                parameters = signature.parameters

                positional_names = list(
                    parameters.keys()
                )[:7]

                for name in positional_names:

                    optional_kwargs.pop(
                        name,
                        None
                    )

            except Exception as parameter_error:

                boot_log(
                    "[SEEDCore] "
                    f"Parameter analysis warning: {parameter_error}"
                )

        # ------------------------------------------------------
        # Ensure ChannelManager is explicitly present.
        # ------------------------------------------------------

        if (
            signature is None
            or "channel_manager"
            in signature.parameters
        ):

            optional_kwargs[
                "channel_manager"
            ] = cm

        # ------------------------------------------------------
        # Construct SEEDCore.
        #
        # First use the real seven required positional
        # dependencies plus recognized keyword dependencies.
        # ------------------------------------------------------

        try:

            boot_log("[SEEDCore] CONSTRUCTOR BEGIN | optional_wiring=deferred")
            seedcore = SEEDCore(
                *positional_dependencies,
                **optional_kwargs,
            )
            boot_log("[SEEDCore] CONSTRUCTOR RETURNED")

        except TypeError as constructor_error:

            boot_log(
                "[BOOT ERROR] "
                "SEEDCore constructor rejected stabilized "
                "dependency set"
            )

            boot_log(
                "[BOOT ERROR] "
                f"{constructor_error}"
            )

            boot_log(
                "[SEEDCore] "
                f"Signature={signature}"
            )

            raise

        # ------------------------------------------------------
        # Validate object
        # ------------------------------------------------------

        if seedcore is None:

            raise RuntimeError(
                "SEEDCore constructor returned None"
            )

        # ------------------------------------------------------
        # Publish global references
        # ------------------------------------------------------

        core = seedcore

        # ------------------------------------------------------
        # Type_Writter / Oracle lesson output bridge
        # ------------------------------------------------------
        try:
            from seed.systemutils.typer_writter import Type_Writter
            from seed.skills.oracle_lessons import OracleLessonSkill
            type_writter = Type_Writter()
            type_writter.bind_runtime(
                qbit_dialer=qbit_dialer,
                event_bus=event_bus,
                registry=registry,
                node_registry=globals().get("node_registry"),
                track_system=track_system,
                oracle=oracle,
                seedcore=seedcore,
            )
            oracle_lesson_skill = OracleLessonSkill(
                oracle=oracle,
                writer=type_writter,
                event_bus=event_bus,
                qbit_dialer=qbit_dialer,
            )
            globals()["type_writter"] = type_writter
            globals()["oracle_lesson_skill"] = oracle_lesson_skill
            MODULES_STATUS["TypeWritter"] = True
            MODULES_STATUS["OracleLessonSkill"] = True
            boot_log("[Type_Writter] Notepad-style artifact output LINKED | extension selects format")
            boot_log("[OracleLessonSkill] keyboard + Seed Mouse lessons READY")
        except Exception as writer_exc:
            MODULES_STATUS["TypeWritter"] = False
            MODULES_STATUS["OracleLessonSkill"] = False
            boot_warn(f"Type_Writter/Oracle lesson binding deferred: {writer_exc}")

        # ------------------------------------------------------
        # TrackID metadata
        # ------------------------------------------------------

        try:

            if not hasattr(
                seedcore,
                "track_id",
            ):

                setattr(
                    seedcore,
                    "track_id",
                    track_id,
                )

        except Exception as metadata_error:

            boot_log(
                "[SEEDCore] "
                f"TrackID attachment skipped: {metadata_error}"
            )

        # ------------------------------------------------------
        # Verify ChannelManager attachment
        # ------------------------------------------------------

        channel_verified = False

        try:

            existing_channel_manager = getattr(
                seedcore,
                "channel_manager",
                None,
            )

            if (
                existing_channel_manager is cm
            ):

                channel_verified = True

            elif (
                existing_channel_manager is not None
            ):

                channel_verified = True

        except Exception:
            channel_verified = False

        if not channel_verified:

            boot_log(
                "[BOOT WARN] "
                "SEEDCore did not expose a channel_manager "
                "attribute after construction"
            )

        else:

            boot_log(
                "[SEEDCore] "
                "ChannelManager LINKED"
            )

        # ------------------------------------------------------
        # Mark module online
        # ------------------------------------------------------

        MODULES_STATUS[
            "SEEDCore"
        ] = True

        boot_log(
            "SEEDCore INSTANCE ONLINE"
        )

        boot_log(
            "[SEEDCore] "
            "QbitQueueLoop LINKED"
        )

        boot_log(
            "[SEEDCore] "
            "ChannelManager LINKED"
        )

        boot_log(
            "[SEEDCore] "
            "IntentEngine LINKED"
        )

        boot_log(
            "[SEEDCore] "
            "EthicsManager LINKED"
        )

        boot_log(
            "[SEEDCore] "
            "Memory_Crystallizer LINKED"
        )

        boot_log(
            "[SEEDCore] "
            "Orchestrator command LINKED"
        )

        # ------------------------------------------------------
        # QbitDialer â†’ SEEDCore
        # ------------------------------------------------------

        if qbit_dialer is not None:

            attach_seedcore = getattr(
                qbit_dialer,
                "attach_seedcore",
                None,
            )

            if callable(
                attach_seedcore
            ):

                safe_call(
                    attach_seedcore,
                    seedcore,
                    label=(
                        "QbitDialer.attach_seedcore"
                    ),
                )

                boot_log(
                    "[SEEDCore] "
                    "QbitDialer â†’ SEEDCore LINKED"
                )

            else:

                boot_log(
                    "[SEEDCore] "
                    "QbitDialer.attach_seedcore unavailable"
                )

        # ------------------------------------------------------
        # Boot registry
        # ------------------------------------------------------

        try:

            import seed as seed_boot

            mark_ready = getattr(
                seed_boot,
                "mark_ready",
                None,
            )

            if callable(
                mark_ready
            ):

                mark_ready(
                    "seedcore"
                )

                boot_log(
                    "[SEEDCore] "
                    "Boot registry â†’ READY"
                )

        except Exception as registry_error:

            boot_log(
                "[SEEDCore] "
                f"Boot registry update skipped: {registry_error}"
            )

        # ------------------------------------------------------
        # Final success
        # ------------------------------------------------------

        boot_log(
            "PHASE 13 | SEEDCore READY"
        )

        return seedcore

    # ==========================================================
    # FAILURE HANDLING
    # ==========================================================

    except Exception as exc:

        MODULES_STATUS[
            "SEEDCore"
        ] = False

        seedcore = None
        core = None

        trace_exception(
            exc
        )

        raise


# ==========================================================
# END SECTION 26
# ==========================================================

# ==========================================================
# SECTION 27 â€” TIME TRAVEL
# ==========================================================

def boot_time_travel():
    global time_travel_engine

    boot_log(
        "PHASE 14 | TimeTravelEngine"
    )

    try:

        from seed.core.time_travel_engine import (
            TimeTravelEngine,
        )

        time_travel_engine = compatible_construct(
            TimeTravelEngine,
            [
                (
                    (),
                    {
                        "emit": getattr(
                            event_bus,
                            "emit",
                            safe_emit,
                        ),
                        "command":
                            lambda x: True,
                        "boot_cycle":
                            BootCycle()
                            if "BootCycle" in globals()
                            else None,
                        "event_bus": event_bus,
                        "dialer": qbit_dialer,
                    },
                ),
                (
                    (),
                    {
                        "event_bus": event_bus,
                        "dialer": qbit_dialer,
                    },
                ),
            ],
            "TimeTravelEngine",
        )

        if time_travel_engine is None:
            raise RuntimeError(
                "TimeTravelEngine unavailable"
            )

        MODULES_STATUS[
            "TimeTravelEngine"
        ] = True

        attach = getattr(
            time_travel_engine,
            "attach",
            None,
        )

        if callable(attach) and seedcore is not None:
            safe_call(
                attach,
                seedcore,
                label="TimeTravelEngine.attach",
            )

        try:
            time_travel_engine.auto_persist = True
        except Exception:
            pass

        boot_log(
            "TimeTravelEngine ONLINE"
        )

    except Exception as exc:

        MODULES_STATUS[
            "TimeTravelEngine"
        ] = False

        trace_exception(exc)


# ==========================================================
# SECTION 28 â€” TIME TRAVEL COMMAND BRIDGE
#
# PURPOSE:
# - Create the initial SEED boot command.
# - Record the boot event in TimeTravelEngine.
# - Seed the FIRST authoritative Qbit into the existing
#   QbitQueueLoop.
# - Allow that first Qbit to enter the normal thought cycle.
# - The first Qbit is intentionally allowed to change,
#   develop, accumulate state, and produce a later thought.
# - Never create a second Qbit, queue, queue loop, or Dialer.
# - Retry only the bridge operation when the authoritative
#   runtime is temporarily unavailable.
# - Preserve boot flags so later phases know whether the
#   initial thought was accepted, processed, deferred, or
#   failed.
# ==========================================================

def create_boot_command():

    return {
        "action": "boot",
        "target": "SEED",

        "payload": {
            "source": "main.py",
            "version": VERSION,

            # --------------------------------------------------
            # FIRST-THOUGHT FLAGS
            # --------------------------------------------------
            #
            # This is the initial seed only.
            # It is NOT the final command/thought.
            #
            "first_qbit": True,
            "initial_thought": True,
            "allow_evolution": True,
            "allow_reassessment": True,
            "allow_context_update": True,
            "allow_development": True,

            # The authoritative QbitDialer remains the command
            # authority after the seed enters the pipeline.
            "command_authority": "qbit_dialer",

            # The authoritative QbitQueueLoop remains transport.
            "transport_authority": "qbit_queue_loop",

            # TimeTravel observes/records the lifecycle.
            "time_travel_observer": True,
        },

        "timestamp": time.time(),
    }


def record_boot_command():

    global time_travel_engine

    # ======================================================
    # BOOT BRIDGE STATE
    # ======================================================

    boot_state = globals().setdefault(
        "BOOT_COMMAND_STATE",
        {},
    )

    boot_state.setdefault(
        "attempts",
        0,
    )

    boot_state.setdefault(
        "first_qbit_seeded",
        False,
    )

    boot_state.setdefault(
        "first_qbit_cycled",
        False,
    )

    boot_state.setdefault(
        "first_qbit_evolving",
        False,
    )

    boot_state.setdefault(
        "time_travel_recorded",
        False,
    )

    boot_state.setdefault(
        "retry_required",
        False,
    )

    boot_state.setdefault(
        "last_error",
        None,
    )

    # ======================================================
    # AUTHORITATIVE RUNTIME REFERENCES
    # ======================================================

    runtime_qbit = globals().get(
        "qbit"
    )

    runtime_queue_loop = globals().get(
        "queue_loop"
    )

    runtime_qbit_dialer = globals().get(
        "qbit_dialer"
    )

    runtime_event_bus = globals().get(
        "event_bus"
    )

    # ======================================================
    # TIME TRAVEL IS OPTIONAL
    # ======================================================

    if time_travel_engine is None:

        boot_state[
            "time_travel_recorded"
        ] = False

        logger.debug(
            "[TimeTravel] "
            "Engine unavailable; boot record skipped"
        )

    else:

        command_obj = create_boot_command()

        # ==================================================
        # RECORD COMMAND
        # ==================================================

        record = getattr(
            time_travel_engine,
            "record_command",
            None,
        )

        if callable(record):

            result = safe_call(
                record,
                command_obj=command_obj,
                event_name="SYSTEM_BOOT",
                payload={
                    "status": "initiated",
                    "first_qbit": True,
                    "allow_evolution": True,
                },
                label="TimeTravel.record_command",
            )

            if result is not None:

                boot_state[
                    "time_travel_recorded"
                ] = True

        # ==================================================
        # RELAY BOOT EVENT
        # ==================================================

        relay = getattr(
            time_travel_engine,
            "relay",
            None,
        )

        if callable(relay):

            safe_call(
                relay,
                {
                    "event_name": "SYSTEM_START",
                    "payload": {
                        "status": "initiated",
                        "first_qbit": True,
                        "allow_evolution": True,
                    },
                },
                label="TimeTravel.relay",
            )

    # ======================================================
    # FIRST QBIT SEED
    #
    # IMPORTANT:
    #
    # Do NOT construct a Qbit here.
    #
    # boot_qbit() already established the authoritative
    # Qbit instance.
    #
    # The first thought must be the SAME Qbit object.
    # ======================================================

    if runtime_qbit is None:

        boot_state[
            "retry_required"
        ] = True

        boot_state[
            "last_error"
        ] = "authoritative_qbit_unavailable"

        logger.warning(
            "[TimeTravel] "
            "First Qbit seed deferred | "
            "authoritative Qbit unavailable"
        )

        return {
            "status": "deferred",
            "reason": "qbit_unavailable",
        }

    if runtime_queue_loop is None:

        boot_state[
            "retry_required"
        ] = True

        boot_state[
            "last_error"
        ] = "authoritative_queue_loop_unavailable"

        logger.warning(
            "[TimeTravel] "
            "First Qbit seed deferred | "
            "QbitQueueLoop unavailable"
        )

        return {
            "status": "deferred",
            "reason": "queue_loop_unavailable",
        }

    # ======================================================
    # AUTHORITATIVE IDENTITY CHECK
    # ======================================================

    if (
        runtime_qbit_dialer is not None
        and hasattr(
            runtime_qbit_dialer,
            "qbit",
        )
    ):

        dialer_qbit = getattr(
            runtime_qbit_dialer,
            "qbit",
            None,
        )

        if (
            dialer_qbit is not None
            and dialer_qbit is not runtime_qbit
        ):

            boot_state[
                "retry_required"
            ] = True

            boot_state[
                "last_error"
            ] = "qbit_identity_mismatch"

            logger.error(
                "[TimeTravel] "
                "FIRST QBIT REJECTED | "
                "Dialer Qbit is not authoritative Qbit"
            )

            return {
                "status": "rejected",
                "reason": "qbit_identity_mismatch",
            }

    # ======================================================
    # BUILD FIRST THOUGHT PAYLOAD
    #
    # This is intentionally a SEED.
    #
    # It tells the thought system:
    #
    #   "Here is where boot begins."
    #
    # It does NOT tell the thought system what the final
    # answer/action must be.
    # ======================================================

    command_obj = create_boot_command()

    first_thought = {
        "type": "initial_boot_thought",

        "source": "SYSTEM_BOOT",

        "seed": command_obj,

        "first_qbit": True,

        # --------------------------------------------------
        # DEVELOPMENT FLAGS
        # --------------------------------------------------

        "evolution": {
            "enabled": True,
            "reassess": True,
            "context_update": True,
            "adaptive": True,
            "allow_new_state": True,
            "allow_new_intent": True,
            "allow_new_proposal": True,
        },

        # --------------------------------------------------
        # AUTHORITY FLAGS
        # --------------------------------------------------

        "authority": {
            "qbit": True,
            "queue_loop": True,
            "qbit_dialer": (
                runtime_qbit_dialer is not None
            ),
            "time_travel": (
                time_travel_engine is not None
            ),
        },

        "timestamp": time.time(),
    }

    # ======================================================
    # ATTACH SEED TO EXISTING QBIT
    #
    # Only if the Qbit exposes a compatible state/input
    # attribute. We do not replace existing Qbit state.
    # ======================================================

    attached = False

    for attr_name in (
        "initial_thought",
        "boot_thought",
        "thought_seed",
        "initial_seed",
    ):

        try:

            if hasattr(
                runtime_qbit,
                attr_name,
            ):

                current = getattr(
                    runtime_qbit,
                    attr_name,
                    None,
                )

                if current is None:

                    setattr(
                        runtime_qbit,
                        attr_name,
                        first_thought,
                    )

                    attached = True
                    break

                elif current is first_thought:

                    attached = True
                    break

        except Exception as exc:

            logger.debug(
                "[TimeTravel] "
                "Qbit seed attachment skipped | "
                "attribute=%s | error=%s",
                attr_name,
                exc,
            )

    # ======================================================
    # BUILD QBIT ENVELOPE WITHOUT CREATING A NEW QBIT
    # ======================================================

    qbit_envelope = {
        "qbit": runtime_qbit,

        "payload": first_thought,

        "source": "time_travel_boot",

        "first_qbit": True,

        "initial_thought": True,

        "allow_evolution": True,

        "allow_reassessment": True,

        "timestamp": time.time(),
    }

    # ======================================================
    # SUBMIT TO THE EXISTING AUTHORITATIVE QUEUE LOOP
    #
    # Try only APIs that belong to the existing loop.
    #
    # Never instantiate another queue.
    # Never instantiate another loop.
    # Never call asyncio.run().
    # Never create another Qbit.
    # ======================================================

    submit_methods = (
        "submit",
        "enqueue",
        "put",
        "submit_qbit",
        "enqueue_qbit",
    )

    submitted = False
    submit_result = None

    for method_name in submit_methods:

        submitter = getattr(
            runtime_queue_loop,
            method_name,
            None,
        )

        if not callable(submitter):
            continue

        try:

            # ------------------------------------------------
            # First try the full authoritative envelope.
            # ------------------------------------------------

            try:

                submit_result = submitter(
                    qbit_envelope
                )

                submitted = True

                break

            except TypeError:

                # --------------------------------------------
                # Some QueueLoop implementations accept the
                # Qbit directly.
                # --------------------------------------------

                submit_result = submitter(
                    runtime_qbit
                )

                submitted = True

                break

        except Exception as exc:

            logger.debug(
                "[TimeTravel] "
                "First Qbit submission attempt failed | "
                "method=%s | error=%s",
                method_name,
                exc,
            )

    # ======================================================
    # SUBMISSION RESULT
    # ======================================================

    if not submitted:

        boot_state[
            "retry_required"
        ] = True

        boot_state[
            "last_error"
        ] = "qbit_submission_failed"

        logger.warning(
            "[TimeTravel] "
            "First Qbit submission deferred | "
            "no compatible QueueLoop submit API"
        )

        return {
            "status": "deferred",
            "reason": "submission_failed",
            "attached": attached,
        }

    # ======================================================
    # SUCCESS
    # ======================================================

    boot_state[
        "attempts"
    ] += 1

    boot_state[
        "first_qbit_seeded"
    ] = True

    boot_state[
        "first_qbit_cycled"
    ] = True

    boot_state[
        "first_qbit_evolving"
    ] = True

    boot_state[
        "retry_required"
    ] = False

    boot_state[
        "last_error"
    ] = None

    # ======================================================
    # TELEMETRY ONLY
    # ======================================================

    status_payload = {
        "status": "first_qbit_seeded",
        "first_qbit": True,
        "thought_cycle": True,
        "evolution_enabled": True,
        "qbit_id": id(runtime_qbit),
        "queue_loop_id": id(
            runtime_queue_loop
        ),
        "dialer_id": (
            id(runtime_qbit_dialer)
            if runtime_qbit_dialer is not None
            else None
        ),
        "timestamp": time.time(),
    }

    if runtime_event_bus is not None:

        try:

            runtime_event_bus.emit(
                "FIRST_QBIT_SEEDED",
                status_payload,
            )

        except Exception:
            try:
                runtime_event_bus.emit(
                    status_payload
                )
            except Exception:
                pass

    logger.info(
        "[TimeTravel] "
        "FIRST QBIT SEEDED | "
        "qbit_id=%s | "
        "queue_loop_id=%s | "
        "dialer_id=%s | "
        "thought_cycle=ACTIVE | "
        "evolution=ENABLED",
        id(runtime_qbit),
        id(runtime_queue_loop),
        (
            id(runtime_qbit_dialer)
            if runtime_qbit_dialer is not None
            else None
        ),
    )

    return {
        "status": "seeded",

        "qbit": runtime_qbit,

        "queue_loop": runtime_queue_loop,

        "qbit_dialer": runtime_qbit_dialer,

        "first_qbit": True,

        "thought_cycle": True,

        "evolution_enabled": True,

        "attached": attached,

        "submit_result": submit_result,
    }



# ==========================================================
# SECTION 29 â€” ORACLE
#
# PURPOSE:
# - Boot Oracle as a system observer/intelligence source.
# - Give Oracle the EXACT authoritative QbitQueueLoop.
# - Allow Oracle-generated Qbits to enter the authoritative
#   QbitQueueLoop correctly.
# - Never create a second QbitQueueLoop.
# - Never create a second transport queue.
# - Never create a second QbitDialer.
# - Oracle may PRODUCE Qbits.
# - QbitQueueLoop remains the sole Qbit transport authority.
# - QbitDialer remains the sole command authority.
# ==========================================================

def boot_oracle():

    global oracle
    global ORACLE
    global oracle_loop

    boot_log(
        "PHASE 15 | Oracle"
    )

    try:

        from Oracle.oracle_tools import (
            Oracle,
            attach as Oracle_attach,
        )

        # ==================================================
        # AUTHORITATIVE RUNTIME REFERENCES
        # ==================================================

        runtime_queue_loop = globals().get(
            "queue_loop"
        )

        runtime_qbit = globals().get(
            "qbit"
        )

        runtime_qbit_dialer = globals().get(
            "qbit_dialer"
        )

        runtime_event_bus = globals().get(
            "event_bus"
        )

        runtime_track_system = globals().get(
            "track_system"
        )

        runtime_registry = globals().get(
            "system_registry",
            globals().get("registry"),
        )

        runtime_seed_core = globals().get(
            "seedcore",
            globals().get("seed_core"),
        )

        # ==================================================
        # AUTHORITATIVE QUEUE LOOP REQUIRED
        #
        # Oracle never constructs transport.
        # ==================================================

        if runtime_queue_loop is None:

            raise RuntimeError(
                "Oracle requires the authoritative "
                "QbitQueueLoop reference"
            )

        oracle_loop = runtime_queue_loop

        # ==================================================
        # QUEUE LOOP TYPE / IDENTITY VALIDATION
        # ==================================================

        queue_loop_type = type(
            runtime_queue_loop
        ).__name__

        logger.info(
            "[Oracle] "
            "Authoritative QbitQueueLoop acquired | "
            "type=%s | id=%s",
            queue_loop_type,
            id(runtime_queue_loop),
        )

        # ==================================================
        # ORACLE CONSTRUCTION
        #
        # First choice:
        #   exact authoritative queue loop.
        #
        # No private queue/loop fallback.
        # ==================================================

        if oracle is None:

            oracle = compatible_construct(
                Oracle,
                [
                    (
                        (runtime_queue_loop,),
                        {},
                    ),
                    (
                        (),
                        {
                            "queue_loop":
                                runtime_queue_loop,
                        },
                    ),
                    (
                        (),
                        {
                            "qbit_queue_loop":
                                runtime_queue_loop,
                        },
                    ),
                ],
                "Oracle",
            )

        if oracle is None:

            raise RuntimeError(
                "Oracle initialization failed"
            )

        # ==================================================
        # ORACLE â†’ AUTHORITATIVE RUNTIME ATTACHMENT
        # ==================================================

        def _attach_existing(
            target,
            names,
            value,
        ):
            if target is None or value is None:
                return False

            attached = False

            for name in names:

                try:

                    if not hasattr(
                        target,
                        name,
                    ):
                        continue

                    current = getattr(
                        target,
                        name,
                        None,
                    )

                    if current is None:

                        setattr(
                            target,
                            name,
                            value,
                        )

                        attached = True

                    elif current is value:

                        attached = True

                    elif current is not value:

                        logger.error(
                            "[Oracle] "
                            "Authority conflict prevented | "
                            "attr=%s | "
                            "existing_id=%s | "
                            "authoritative_id=%s",
                            name,
                            id(current),
                            id(value),
                        )

                except Exception as exc:

                    logger.debug(
                        "[Oracle] "
                        "Optional attachment failed | "
                        "attr=%s | error=%s",
                        name,
                        exc,
                    )

            return attached

        # ==================================================
        # ATTACH AUTHORITATIVE RUNTIME OBJECTS
        # ==================================================

        _attach_existing(
            oracle,
            (
                "queue_loop",
                "qbit_queue_loop",
                "oracle_loop",
            ),
            runtime_queue_loop,
        )

        _attach_existing(
            oracle,
            (
                "qbit",
                "authoritative_qbit",
                "seed_qbit",
            ),
            runtime_qbit,
        )

        _attach_existing(
            oracle,
            (
                "qbit_dialer",
                "dialer",
            ),
            runtime_qbit_dialer,
        )

        _attach_existing(
            oracle,
            (
                "event_bus",
                "bus",
            ),
            runtime_event_bus,
        )

        _attach_existing(
            oracle,
            (
                "track_system",
                "track",
            ),
            runtime_track_system,
        )

        _attach_existing(
            oracle,
            (
                "registry",
                "system_registry",
            ),
            runtime_registry,
        )

        _attach_existing(
            oracle,
            (
                "seedcore",
                "seed_core",
                "core",
            ),
            runtime_seed_core,
        )

        # ==================================================
        # QUEUE IDENTITY VERIFICATION
        # ==================================================

        oracle_bound_loop = None

        for attr_name in (
            "queue_loop",
            "qbit_queue_loop",
            "oracle_loop",
        ):

            candidate = getattr(
                oracle,
                attr_name,
                None,
            )

            if candidate is not None:

                oracle_bound_loop = candidate
                break

        if (
            oracle_bound_loop is not None
            and oracle_bound_loop is not runtime_queue_loop
        ):

            raise RuntimeError(
                "Oracle attempted to bind a non-authoritative "
                "QbitQueueLoop instance"
            )

        # ==================================================
        # ORACLE QBIT SUBMISSION BRIDGE
        #
        # This is the important part.
        #
        # Oracle is allowed to CREATE/PRODUCE a Qbit.
        #
        # Oracle is NOT allowed to create transport.
        #
        # Every Oracle Qbit must enter the EXISTING
        # authoritative QbitQueueLoop.
        # ==================================================

        def _submit_oracle_qbit(
            oracle_qbit,
            metadata=None,
        ):

            if oracle_qbit is None:

                logger.warning(
                    "[Oracle] "
                    "Oracle Qbit submission rejected | "
                    "qbit=None"
                )

                return False

            if runtime_queue_loop is None:

                logger.error(
                    "[Oracle] "
                    "Oracle Qbit submission rejected | "
                    "authoritative QueueLoop unavailable"
                )

                return False

            # ----------------------------------------------
            # DO NOT ACCEPT A SECOND TRANSPORT OBJECT
            # ----------------------------------------------

            candidate_loop = getattr(
                oracle,
                "queue_loop",
                runtime_queue_loop,
            )

            if (
                candidate_loop is not None
                and candidate_loop is not runtime_queue_loop
            ):

                logger.error(
                    "[Oracle] "
                    "Oracle Qbit rejected | "
                    "non-authoritative QueueLoop"
                )

                return False

            # ----------------------------------------------
            # PRESERVE THE EXACT ORACLE QBIT INSTANCE
            # ----------------------------------------------

            envelope = {
                "qbit": oracle_qbit,

                "source": "oracle",

                "oracle_qbit": True,

                "authoritative_transport": True,

                "allow_thought_cycle": True,

                "allow_evolution": True,

                "timestamp": time.time(),

                "metadata": (
                    metadata
                    if isinstance(
                        metadata,
                        dict,
                    )
                    else {}
                ),
            }

            # ----------------------------------------------
            # SUBMISSION API DISCOVERY
            #
            # Use the existing QueueLoop API.
            # ----------------------------------------------

            submission_methods = (
                "submit_qbit",
                "enqueue_qbit",
                "submit",
                "enqueue",
                "put",
            )

            for method_name in submission_methods:

                submitter = getattr(
                    runtime_queue_loop,
                    method_name,
                    None,
                )

                if not callable(
                    submitter
                ):
                    continue

                # ------------------------------------------
                # FIRST: Qbit-aware API
                # ------------------------------------------

                try:

                    result = submitter(
                        oracle_qbit
                    )

                    logger.info(
                        "[Oracle] "
                        "Oracle Qbit admitted | "
                        "method=%s | "
                        "qbit_id=%s | "
                        "queue_loop_id=%s",
                        method_name,
                        id(oracle_qbit),
                        id(runtime_queue_loop),
                    )

                    return result

                except TypeError:
                    pass

                except Exception as exc:

                    logger.warning(
                        "[Oracle] "
                        "Oracle Qbit submission failed | "
                        "method=%s | error=%s",
                        method_name,
                        exc,
                    )

            # ----------------------------------------------
            # SECOND: Envelope-aware API
            #
            # Only attempted if the existing transport API
            # rejects the direct Qbit signature.
            # ----------------------------------------------

            for method_name in (
                "submit",
                "enqueue",
            ):

                submitter = getattr(
                    runtime_queue_loop,
                    method_name,
                    None,
                )

                if not callable(
                    submitter
                ):
                    continue

                try:

                    result = submitter(
                        envelope
                    )

                    logger.info(
                        "[Oracle] "
                        "Oracle Qbit envelope admitted | "
                        "method=%s | "
                        "qbit_id=%s | "
                        "queue_loop_id=%s",
                        method_name,
                        id(oracle_qbit),
                        id(runtime_queue_loop),
                    )

                    return result

                except Exception as exc:

                    logger.debug(
                        "[Oracle] "
                        "Envelope submission failed | "
                        "method=%s | error=%s",
                        method_name,
                        exc,
                    )

            logger.error(
                "[Oracle] "
                "Oracle Qbit could not be admitted | "
                "no compatible authoritative QueueLoop API"
            )

            return False

        # ==================================================
        # EXPOSE THE BRIDGE TO ORACLE
        #
        # We attach the bridge only if Oracle has a suitable
        # attribute. We do NOT overwrite an existing callable
        # unless it is clearly absent.
        # ==================================================

        bridge_attached = False

        for bridge_name in (
            "submit_qbit",
            "enqueue_qbit",
            "queue_qbit",
            "submit_oracle_qbit",
        ):

            try:

                if hasattr(
                    oracle,
                    bridge_name,
                ):

                    current_bridge = getattr(
                        oracle,
                        bridge_name,
                        None,
                    )

                    if current_bridge is None:

                        setattr(
                            oracle,
                            bridge_name,
                            _submit_oracle_qbit,
                        )

                        bridge_attached = True
                        break

                    if callable(
                        current_bridge
                    ):

                        bridge_attached = True
                        break

            except Exception:
                continue

        # Always expose the canonical bridge on the Oracle
        # object under a dedicated name when possible.
        try:

            if getattr(
                oracle,
                "_seed_qbit_submit",
                None,
            ) is None:

                setattr(
                    oracle,
                    "_seed_qbit_submit",
                    _submit_oracle_qbit,
                )

                bridge_attached = True

        except Exception as exc:

            logger.debug(
                "[Oracle] "
                "Canonical Qbit bridge attachment skipped | "
                "error=%s",
                exc,
            )

        # ==================================================
        # ATTACH COGNITIVE / REGISTRY RUNTIME REFERENCES
        # ==================================================
        #
        # Oracle remains observer/proposal-only. These are
        # authoritative references; no subsystem is created here.
        # ==================================================

        runtime_heartbeat = globals().get(
            "heartbeat",
            None,
        )

        runtime_module_registry = globals().get(
            "module_registry",
            None,
        )

        runtime_neural_bridge = globals().get(
            "neural_bridge",
            None,
        )

        runtime_cognition_neural_bridge = globals().get(
            "cognition_neural_bridge",
            None,
        )

        for attribute, value in (
            ("heartbeatemitter", runtime_heartbeat),
            ("heartbeat", runtime_heartbeat),
            ("module_registry", runtime_module_registry),
            ("neural_bridge", runtime_neural_bridge),
            (
                "cognition_neural_bridge",
                runtime_cognition_neural_bridge,
            ),
            ("compute_brain", globals().get("compute_brain")),
            ("computebrain", globals().get("computebrain")),
            (
                "transformer_brain",
                globals().get("transformer_brain"),
            ),
            (
                "transformerbrain",
                globals().get("transformerbrain"),
            ),
        ):
            if value is None:
                continue

            try:
                current = getattr(
                    oracle,
                    attribute,
                    None,
                )

                if current is None or current is value:
                    setattr(
                        oracle,
                        attribute,
                        value,
                    )
                else:
                    logger.error(
                        "[Oracle] authority conflict prevented | "
                        "attr=%s | existing_id=%s | authoritative_id=%s",
                        attribute,
                        id(current),
                        id(value),
                    )
            except Exception:
                pass

        # ==================================================
        # ATTACH TO SEEDCORE
        # ==================================================

        if runtime_seed_core is not None:

            ORACLE = safe_call(
                Oracle_attach,
                runtime_seed_core,
                default=oracle,
                label="Oracle.attach",
            )

        else:

            ORACLE = oracle

        if ORACLE is None:

            raise RuntimeError(
                "Oracle attachment failed"
            )

        # ==================================================
        # MAKE THE BRIDGE AVAILABLE THROUGH ORACLE
        # AFTER SEEDCORE ATTACHMENT
        # ==================================================

        try:

            if getattr(
                ORACLE,
                "_seed_qbit_submit",
                None,
            ) is None:

                setattr(
                    ORACLE,
                    "_seed_qbit_submit",
                    _submit_oracle_qbit,
                )

        except Exception:
            pass

        # ==================================================
        # FINAL QUEUE IDENTITY CHECK
        # ==================================================

        final_oracle_loop = None

        for attr_name in (
            "queue_loop",
            "qbit_queue_loop",
            "oracle_loop",
        ):

            candidate = getattr(
                ORACLE,
                attr_name,
                None,
            )

            if candidate is not None:

                final_oracle_loop = candidate
                break

        if (
            final_oracle_loop is not None
            and final_oracle_loop is not runtime_queue_loop
        ):

            raise RuntimeError(
                "Oracle final binding is not the "
                "authoritative QbitQueueLoop"
            )

        # ==================================================
        # BOOT REPORT
        # ==================================================

        receive_report = getattr(
            ORACLE,
            "receive_report",
            None,
        )

        if callable(
            receive_report
        ):

            safe_call(
                receive_report,
                {
                    "source": "SEEDMain",

                    "level": "info",

                    "msg":
                        "Boot sequence started",

                    "queue_loop":
                        "authoritative",

                    "qbit_transport":
                        "QbitQueueLoop",

                    "qbit_bridge":
                        "enabled",

                    "qbit_evolution":
                        True,
                },
                label="Oracle.receive_report",
            )

        # ==================================================
        # SANDBOX / COGNITIVE LESSON RELAY
        # ==================================================
        try:
            if event_bus is not None and callable(receive_report):
                event_bus.on(
                    "ORACLE_LESSON",
                    lambda lesson: safe_call(
                        receive_report,
                        {"source":"SEED_TTT_SANDBOX","lesson":lesson},
                        label="Oracle.receive_report.lesson",
                    ),
                )
                MODULES_STATUS["OracleLessonRelay"] = True
        except Exception as exc:
            MODULES_STATUS["OracleLessonRelay"] = False
            boot_warn(f"Oracle lesson relay deferred: {exc}")

        # ==================================================
        # OPTIONAL EVENTBUS TELEMETRY
        #
        # Observer/status only.
        # Does NOT submit commands.
        # ==================================================

        if runtime_event_bus is not None:

            try:

                runtime_event_bus.emit(
                    "ORACLE_RUNTIME_ATTACHED",
                    {
                        "source":
                            "Oracle",

                        "queue_loop":
                            "authoritative",

                        "queue_loop_id":
                            id(runtime_queue_loop),

                        "oracle_id":
                            id(ORACLE),

                        "bridge_attached":
                            bridge_attached,

                        "qbit_transport":
                            "QbitQueueLoop",

                        "command_authority":
                            "QbitDialer",

                        "timestamp":
                            time.time(),
                    },
                )

            except Exception:
                pass

        # ==================================================
        # REGISTRY PUBLICATION
        # ==================================================

        if runtime_registry is not None:

            try:

                register = getattr(
                    runtime_registry,
                    "register",
                    None,
                )

                if callable(
                    register
                ):

                    register(
                        "Oracle",
                        ORACLE,
                    )

            except Exception as exc:

                logger.debug(
                    "[Oracle] "
                    "Registry publication skipped | "
                    "error=%s",
                    exc,
                )

            try:

                if isinstance(
                    runtime_registry,
                    dict,
                ):

                    runtime_registry[
                        "Oracle"
                    ] = ORACLE

            except Exception:
                pass

        # ==================================================
        # FINAL STATUS
        # ==================================================

        MODULES_STATUS[
            "Oracle"
        ] = True

        boot_log(
            "Oracle observer ONLINE | "
            "queue_loop=AUTHORITATIVE | "
            f"same_instance="
            f"{oracle_loop is runtime_queue_loop} | "
            f"qbit_bridge="
            f"{bridge_attached}"
        )

        logger.info(
            "[Oracle] "
            "Runtime bridge ONLINE | "
            "oracle_id=%s | "
            "queue_loop_id=%s | "
            "same_instance=%s | "
            "qbit_bridge=%s | "
            "command_authority=QbitDialer",
            id(ORACLE),
            id(runtime_queue_loop),
            oracle_loop is runtime_queue_loop,
            bridge_attached,
        )

        return ORACLE

    except Exception as exc:

        oracle = None
        ORACLE = None
        oracle_loop = None

        MODULES_STATUS[
            "Oracle"
        ] = False

        trace_exception(exc)

        return None


# ==========================================================
# SECTION 30 â€” IPC / CHANNEL MANAGER
#
# PURPOSE:
# - Establish the authoritative ChannelManager.
# - Connect channels to the existing SEED runtime.
# - Reuse the existing EventBus / Qbit / QueueLoop /
#   QbitDialer / TrackSystem / Registry / Nodes.
# - Allow IPC to communicate through the established
#   channel infrastructure.
# - Keep QbitDialer as the sole command authority.
# - Keep QbitQueueLoop as the sole Qbit transport loop.
# - Never create a second EventBus, Qbit, QueueLoop, or Dialer.
# - Never allow DEVHUD or IPC to bypass submit_command.
# - Construct each channel/IPC service at most once.
# ==========================================================

def boot_channels():

    global cm
    global controller
    global ipc_bridge

    boot_log(
        "PHASE 16 | Channels / IPC"
    )

    # ======================================================
    # AUTHORITATIVE RUNTIME REFERENCES
    # ======================================================

    runtime_event_bus = globals().get(
        "event_bus"
    )

    runtime_qbit = globals().get(
        "qbit"
    )

    runtime_queue_loop = globals().get(
        "queue_loop"
    )

    runtime_qbit_dialer = globals().get(
        "qbit_dialer"
    )

    runtime_track_system = globals().get(
        "track_system"
    )

    runtime_track_context = globals().get(
        "track_context"
    )

    runtime_registry = globals().get(
        "system_registry",
        globals().get("registry"),
    )

    runtime_nodes = globals().get(
        "nodes",
        globals().get("node_registry"),
    )

    runtime_seedcore = globals().get(
        "seedcore",
        globals().get("seed_core"),
    )

    runtime_kernel_bus = globals().get(
        "qbit_kernel_bus",
        globals().get("kernel_bus"),
    )

    runtime_fathud = globals().get(
        "fathud",
        globals().get("fathud_adapter"),
    )

    # ======================================================
    # REQUIRED AUTHORITIES
    # ======================================================

    if runtime_event_bus is None:

        raise RuntimeError(
            "ChannelManager requires the "
            "authoritative EventBus"
        )

    if runtime_qbit is None:

        raise RuntimeError(
            "ChannelManager requires the "
            "authoritative Qbit"
        )

    if runtime_queue_loop is None:

        raise RuntimeError(
            "ChannelManager requires the "
            "authoritative QbitQueueLoop"
        )

    # ======================================================
    # HELPERS
    # ======================================================

    def _attach(
        target,
        names,
        value,
    ):

        if target is None or value is None:
            return False

        attached = False

        for name in names:

            try:

                if not hasattr(
                    target,
                    name,
                ):
                    continue

                current = getattr(
                    target,
                    name,
                    None,
                )

                if current is None:

                    setattr(
                        target,
                        name,
                        value,
                    )

                    attached = True

                elif current is value:

                    attached = True

                else:

                    logger.warning(
                        "[Channels] "
                        "Authority conflict prevented | "
                        "target=%s | attr=%s | "
                        "existing_id=%s | "
                        "authoritative_id=%s",
                        type(target).__name__,
                        name,
                        id(current),
                        id(value),
                    )

            except Exception as exc:

                logger.debug(
                    "[Channels] "
                    "Attachment skipped | "
                    "attr=%s | error=%s",
                    name,
                    exc,
                )

        return attached

    def _bind_system(
        target,
        **kwargs,
    ):

        if target is None:
            return False

        binder = getattr(
            target,
            "bind_system",
            None,
        )

        if not callable(binder):
            return False

        clean = {
            key: value
            for key, value in kwargs.items()
            if value is not None
        }

        try:

            binder(
                **clean
            )

            return True

        except TypeError:

            # ----------------------------------------------
            # Filter unsupported arguments when the existing
            # class exposes a narrower bind_system signature.
            # ----------------------------------------------

            try:

                import inspect

                signature = inspect.signature(
                    binder
                )

                accepted = {
                    key: value
                    for key, value in clean.items()
                    if key in signature.parameters
                }

                if accepted:

                    binder(
                        **accepted
                    )

                    return True

            except Exception:
                pass

        except Exception as exc:

            logger.debug(
                "[Channels] "
                "bind_system failed | "
                "target=%s | error=%s",
                type(target).__name__,
                exc,
            )

        return False

    def _register(
        name,
        value,
    ):

        if value is None:
            return

        if runtime_registry is not None:

            try:

                register = getattr(
                    runtime_registry,
                    "register",
                    None,
                )

                if callable(register):

                    register(
                        name,
                        value,
                    )

            except Exception as exc:

                logger.debug(
                    "[Channels] "
                    "Registry registration skipped | "
                    "name=%s | error=%s",
                    name,
                    exc,
                )

            try:

                if isinstance(
                    runtime_registry,
                    dict,
                ):

                    runtime_registry[
                        name
                    ] = value

            except Exception:
                pass

        if runtime_nodes is not None:

            try:

                register_node = getattr(
                    runtime_nodes,
                    "register",
                    None,
                )

                if callable(register_node):

                    register_node(
                        name,
                        value,
                    )

            except Exception as exc:

                logger.debug(
                    "[Channels] "
                    "Node registration skipped | "
                    "name=%s | error=%s",
                    name,
                    exc,
                )

            try:

                if isinstance(
                    runtime_nodes,
                    dict,
                ):

                    runtime_nodes[
                        name
                    ] = value

            except Exception:
                pass

    # ======================================================
    # 30.1 â€” CHANNEL MANAGER
    # ======================================================

    try:

        from seed.core.channel_manager import (
            ChannelManager,
            ChannelNode,
        )
        from seed.core.channel_id import ChannelID

        channel_id_authority = ChannelID

        # --------------------------------------------------
        # ROOT CHANNEL NODE
        #
        # Construct once.
        # --------------------------------------------------

        root_node = globals().get(
            "root_channel_node"
        )

        if root_node is None:

            root_node = compatible_construct(
                ChannelNode,
                [
                    (
                        ("ROOT",),
                        {
                            "event_bus":
                                runtime_event_bus,
                            "qbit":
                                runtime_qbit,
                            "queue_loop":
                                runtime_queue_loop,
                            "qbit_dialer":
                                runtime_qbit_dialer,
                            "track_system":
                                runtime_track_system,
                            "registry":
                                runtime_registry,
                        },
                    ),
                    (
                        ("ROOT",),
                        {},
                    ),
                    (
                        (),
                        {},
                    ),
                ],
                "Root ChannelNode",
            )

        if root_node is None:

            raise RuntimeError(
                "Root ChannelNode initialization failed"
            )

        globals()[
            "root_channel_node"
        ] = root_node

        # --------------------------------------------------
        # CHANNEL MANAGER
        # --------------------------------------------------

        if cm is None:

            cm = compatible_construct(
                ChannelManager,
                [
                    (
                        (),
                        {
                            "root":
                                root_node,
                            "event_bus":
                                runtime_event_bus,
                            "qbit":
                                runtime_qbit,
                            "queue_loop":
                                runtime_queue_loop,
                            "qbit_dialer":
                                runtime_qbit_dialer,
                            "track_system":
                                runtime_track_system,
                            "track_context":
                                runtime_track_context,
                            "registry":
                                runtime_registry,
                            "nodes":
                                runtime_nodes,
                            "channel_id":
                                channel_id_authority,
                        },
                    ),
                    (
                        (),
                        {
                            "root":
                                root_node,
                            "channel_id":
                                channel_id_authority,
                        },
                    ),
                    (
                        (root_node,),
                        {},
                    ),
                ],
                "ChannelManager",
            )

        if cm is None:

            raise RuntimeError(
                "ChannelManager initialization failed"
            )

        MODULES_STATUS[
            "ChannelManager"
        ] = True

        # ==================================================
        # ATTACH AUTHORITATIVE RUNTIME
        # ==================================================

        _attach(
            cm,
            (
                "event_bus",
                "bus",
            ),
            runtime_event_bus,
        )

        _attach(
            cm,
            (
                "qbit",
                "authoritative_qbit",
            ),
            runtime_qbit,
        )

        _attach(
            cm,
            (
                "queue_loop",
                "qbit_queue_loop",
            ),
            runtime_queue_loop,
        )

        _attach(
            cm,
            (
                "qbit_dialer",
                "dialer",
            ),
            runtime_qbit_dialer,
        )

        _attach(
            cm,
            (
                "track_system",
                "track",
            ),
            runtime_track_system,
        )

        _attach(
            cm,
            (
                "track_context",
                "context",
            ),
            runtime_track_context,
        )

        _attach(
            cm,
            (
                "registry",
                "system_registry",
            ),
            runtime_registry,
        )

        _attach(
            cm,
            (
                "nodes",
                "node_registry",
            ),
            runtime_nodes,
        )

        _attach(
            cm,
            (
                "seedcore",
                "seedcore",
                "core",
            ),
            runtime_seedcore,
        )

        _attach(
            cm,
            (
                "kernel_bus",
                "qbit_kernel_bus",
            ),
            runtime_kernel_bus,
        )

        _attach(
            cm,
            (
                "fathud",
                "fathud_adapter",
            ),
            runtime_fathud,
        )

        _bind_system(
            cm,
            event_bus=runtime_event_bus,
            qbit=runtime_qbit,
            queue_loop=runtime_queue_loop,
            qbit_dialer=runtime_qbit_dialer,
            track_system=runtime_track_system,
            track_context=runtime_track_context,
            registry=runtime_registry,
            nodes=runtime_nodes,
            seedcore=runtime_seedcore,
            kernel_bus=runtime_kernel_bus,
            fathud=runtime_fathud,
        )

        # --------------------------------------------------
        # ROOT NODE RUNTIME CONNECTION
        # --------------------------------------------------

        _attach(
            root_node,
            (
                "event_bus",
                "bus",
            ),
            runtime_event_bus,
        )

        _attach(
            root_node,
            (
                "qbit",
                "authoritative_qbit",
            ),
            runtime_qbit,
        )

        _attach(
            root_node,
            (
                "queue_loop",
                "qbit_queue_loop",
            ),
            runtime_queue_loop,
        )

        _attach(
            root_node,
            (
                "qbit_dialer",
                "dialer",
            ),
            runtime_qbit_dialer,
        )

        _attach(
            root_node,
            (
                "track_system",
                "track",
            ),
            runtime_track_system,
        )

        _attach(
            root_node,
            (
                "registry",
                "system_registry",
            ),
            runtime_registry,
        )

        _attach(
            root_node,
            (
                "channel_id",
                "channelid",
            ),
            channel_id_authority,
        )

        # --------------------------------------------------
        # REGISTRY
        # --------------------------------------------------

        _register(
            "ChannelManager",
            cm,
        )

        _register(
            "RootChannelNode",
            root_node,
        )

        _register(
            "ChannelID",
            channel_id_authority,
        )

        logger.info(
            "[Channels] "
            "ChannelManager ONLINE | "
            "qbit_id=%s | "
            "queue_loop_id=%s | "
            "event_bus_id=%s",
            id(runtime_qbit),
            id(runtime_queue_loop),
            id(runtime_event_bus),
        )

    except Exception as exc:

        cm = None

        MODULES_STATUS[
            "ChannelManager"
        ] = False

        trace_exception(exc)

        logger.error(
            "[Channels] "
            "ChannelManager unavailable"
        )

    # ======================================================
    # 30.2 â€” DEVHUD CHANNEL CONTROLLER
    # ======================================================

    try:

        from seed.systemutils.DEVHUD_channels import (
            DEVHUDChannelController,
        )

        if cm is None:

            raise RuntimeError(
                "DEVHUDChannelController requires "
                "ChannelManager"
            )

        if controller is None:

            controller = DEVHUDChannelController(
                channel_manager=cm,
                channel_id=getattr(
                    cm,
                    "channel_id",
                    None,
                ),
                track_system=runtime_track_system,
                storage_root=str(SEED_ROOT),
                engines={
                    "qbit_dialer": runtime_qbit_dialer,
                    "compute_brain": globals().get(
                        "compute_brain"
                    ) or globals().get(
                        "computebrain"
                    ),
                    "transformer_brain": globals().get(
                        "transformer_brain"
                    ) or globals().get(
                        "transformerbrain"
                    ),
                    "intent_engine": globals().get(
                        "intent_engine"
                    ),
                    "analytics_engine": globals().get(
                        "analytics_engine"
                    ),
                    "action_engine": globals().get(
                        "action_engine"
                    ),
                    "adaptive_engine": globals().get(
                        "adaptive_engine"
                    ),
                    "oracle": globals().get(
                        "ORACLE"
                    ) or globals().get(
                        "oracle"
                    ),
                },
            )

        # --------------------------------------------------
        # Attach runtime references where supported.
        # --------------------------------------------------

        _attach(
            controller,
            (
                "channel_manager",
                "cm",
            ),
            cm,
        )

        _attach(
            controller,
            (
                "event_bus",
                "bus",
            ),
            runtime_event_bus,
        )

        _attach(
            controller,
            (
                "qbit",
                "authoritative_qbit",
            ),
            runtime_qbit,
        )

        _attach(
            controller,
            (
                "queue_loop",
                "qbit_queue_loop",
            ),
            runtime_queue_loop,
        )

        _attach(
            controller,
            (
                "qbit_dialer",
                "dialer",
            ),
            runtime_qbit_dialer,
        )

        _attach(
            controller,
            (
                "track_system",
                "track",
            ),
            runtime_track_system,
        )

        _attach(
            controller,
            (
                "channel_id",
            ),
            getattr(
                cm,
                "channel_id",
                None,
            ),
        )

        _attach(
            controller,
            (
                "registry",
                "system_registry",
            ),
            runtime_registry,
        )

        bind_runtime = getattr(
            controller,
            "bind_runtime",
            None,
        )

        if callable(bind_runtime):
            safe_call(
                bind_runtime,
                channel_manager=cm,
                channel_id=getattr(
                    cm,
                    "channel_id",
                    None,
                ),
                track_system=runtime_track_system,
                engines={
                    "qbit_dialer": runtime_qbit_dialer,
                    "compute_brain": globals().get(
                        "compute_brain"
                    ) or globals().get(
                        "computebrain"
                    ),
                    "transformer_brain": globals().get(
                        "transformer_brain"
                    ) or globals().get(
                        "transformerbrain"
                    ),
                    "intent_engine": globals().get(
                        "intent_engine"
                    ),
                    "analytics_engine": globals().get(
                        "analytics_engine"
                    ),
                    "action_engine": globals().get(
                        "action_engine"
                    ),
                    "adaptive_engine": globals().get(
                        "adaptive_engine"
                    ),
                    "oracle": globals().get(
                        "ORACLE"
                    ) or globals().get(
                        "oracle"
                    ),
                },
                label="DEVHUDChannelController.bind_runtime",
            )

        # --------------------------------------------------
        # Select ROOT channel.
        # --------------------------------------------------

        select_channel = getattr(
            controller,
            "select_channel",
            None,
        )

        if callable(
            select_channel
        ):

            safe_call(
                select_channel,
                "ROOT",
                label=(
                    "DEVHUDChannelController."
                    "select_channel"
                ),
            )

        MODULES_STATUS[
            "DEVHUDChannelController"
        ] = True

        _register(
            "DEVHUDChannelController",
            controller,
        )

        logger.info(
            "[Channels] "
            "DEVHUDChannelController ONLINE"
        )

    except Exception as exc:

        controller = None

        MODULES_STATUS[
            "DEVHUDChannelController"
        ] = False

        trace_exception(exc)

        logger.warning(
            "[Channels] "
            "DEVHUDChannelController unavailable"
        )

    # ======================================================
    # 30.3 â€” IPC BRIDGE
    # ======================================================

    try:

        from seed.ipc.ipc_bridge import (
            IPCBridge,
        )

        if ipc_bridge is None:

            ipc_bridge = compatible_construct(
                IPCBridge,
                [
                    (
                        (),
                        {
                            "channel_manager":
                                cm,
                            "event_bus":
                                runtime_event_bus,
                            "qbit":
                                runtime_qbit,
                            "queue_loop":
                                runtime_queue_loop,
                            "qbit_dialer":
                                runtime_qbit_dialer,
                            "track_system":
                                runtime_track_system,
                            "registry":
                                runtime_registry,
                            "nodes":
                                runtime_nodes,
                            "seedcore":
                                runtime_seedcore,
                        },
                    ),
                    (
                        (),
                        {
                            "channel_manager":
                                cm,
                            "event_bus":
                                runtime_event_bus,
                        },
                    ),
                    (
                        (),
                        {},
                    ),
                ],
                "IPCBridge",
            )

        if ipc_bridge is None:

            raise RuntimeError(
                "IPCBridge initialization failed"
            )

        # ==================================================
        # ATTACH AUTHORITATIVE SYSTEM
        # ==================================================

        _attach(
            ipc_bridge,
            (
                "channel_manager",
                "channels",
                "cm",
            ),
            cm,
        )

        _attach(
            ipc_bridge,
            (
                "event_bus",
                "bus",
            ),
            runtime_event_bus,
        )

        _attach(
            ipc_bridge,
            (
                "qbit",
                "authoritative_qbit",
            ),
            runtime_qbit,
        )

        _attach(
            ipc_bridge,
            (
                "queue_loop",
                "qbit_queue_loop",
            ),
            runtime_queue_loop,
        )

        _attach(
            ipc_bridge,
            (
                "qbit_dialer",
                "dialer",
            ),
            runtime_qbit_dialer,
        )

        _attach(
            ipc_bridge,
            (
                "track_system",
                "track",
            ),
            runtime_track_system,
        )

        _attach(
            ipc_bridge,
            (
                "registry",
                "system_registry",
            ),
            runtime_registry,
        )

        _attach(
            ipc_bridge,
            (
                "nodes",
                "node_registry",
            ),
            runtime_nodes,
        )

        _attach(
            ipc_bridge,
            (
                "seedcore",
                "seedcore",
                "core",
            ),
            runtime_seedcore,
        )

        _bind_system(
            ipc_bridge,
            channel_manager=cm,
            event_bus=runtime_event_bus,
            qbit=runtime_qbit,
            queue_loop=runtime_queue_loop,
            qbit_dialer=runtime_qbit_dialer,
            track_system=runtime_track_system,
            registry=runtime_registry,
            nodes=runtime_nodes,
            seed_core=runtime_seedcore,
        )

        # --------------------------------------------------
        # IPC IS NOT COMMAND AUTHORITY.
        #
        # If the bridge exposes command submission, point
        # it toward the EXISTING Dialer rather than allowing
        # it to execute commands independently.
        # --------------------------------------------------

        _attach(
            ipc_bridge,
            (
                "command_authority",
                "command_handler",
                "dialer",
            ),
            runtime_qbit_dialer,
        )

        _register(
            "IPCBridge",
            ipc_bridge,
        )

        MODULES_STATUS[
            "IPCBridge"
        ] = True

        logger.info(
            "[Channels] "
            "IPCBridge ONLINE | "
            "channel_manager=%s | "
            "qbit=%s | "
            "queue_loop=%s | "
            "dialer=%s",
            bool(cm),
            bool(runtime_qbit),
            bool(runtime_queue_loop),
            bool(runtime_qbit_dialer),
        )

    except Exception as exc:

        ipc_bridge = None

        MODULES_STATUS[
            "IPCBridge"
        ] = False

        trace_exception(exc)

        logger.warning(
            "[Channels] "
            "IPCBridge unavailable"
        )

    # ======================================================
    # 30.4 â€” FINAL AUTHORITY VALIDATION
    # ======================================================

    authority_ok = True

    if cm is not None:

        for attr_names, expected in (
            (
                (
                    "event_bus",
                    "bus",
                ),
                runtime_event_bus,
            ),
            (
                (
                    "qbit",
                    "authoritative_qbit",
                ),
                runtime_qbit,
            ),
            (
                (
                    "queue_loop",
                    "qbit_queue_loop",
                ),
                runtime_queue_loop,
            ),
        ):

            found = None

            for attr_name in attr_names:

                candidate = getattr(
                    cm,
                    attr_name,
                    None,
                )

                if candidate is not None:

                    found = candidate
                    break

            if (
                found is not None
                and found is not expected
            ):

                authority_ok = False

                logger.error(
                    "[Channels] "
                    "Authority mismatch | "
                    "attr=%s | "
                    "existing_id=%s | "
                    "expected_id=%s",
                    attr_names,
                    id(found),
                    id(expected),
                )

    if authority_ok:

        logger.info(
            "[Channels] "
            "Authoritative runtime identity preserved"
        )

    else:

        logger.error(
            "[Channels] "
            "AUTHORITATIVE IDENTITY VALIDATION FAILED"
        )

    # ======================================================
    # 30.5 â€” TELEMETRY
    # ======================================================

    if runtime_event_bus is not None:

        try:

            runtime_event_bus.emit(
                "CHANNELS_RUNTIME_ATTACHED",
                {
                    "channel_manager":
                        bool(cm),

                    "devhud_controller":
                        bool(controller),

                    "ipc_bridge":
                        bool(ipc_bridge),

                    "qbit_id":
                        id(runtime_qbit)
                        if runtime_qbit is not None
                        else None,

                    "queue_loop_id":
                        id(runtime_queue_loop)
                        if runtime_queue_loop is not None
                        else None,

                    "qbit_dialer_id":
                        id(runtime_qbit_dialer)
                        if runtime_qbit_dialer is not None
                        else None,

                    "authoritative":
                        authority_ok,

                    "command_authority":
                        "QbitDialer",

                    "transport_authority":
                        "QbitQueueLoop",

                    "timestamp":
                        time.time(),
                },
            )

        except Exception:
            pass

    # ======================================================
    # FINAL REPORT
    # ======================================================

    boot_log(
        "PHASE 16 COMPLETE | "
        "Channels / IPC initialized | "
        f"channel_manager={bool(cm)} | "
        f"controller={bool(controller)} | "
        f"ipc={bool(ipc_bridge)} | "
        f"authoritative={authority_ok}"
    )

    return {
        "channel_manager":
            cm,

        "controller":
            controller,

        "ipc_bridge":
            ipc_bridge,

        "authoritative":
            authority_ok,
    }



# ==========================================================
# SECTION 30.6 â€” SEED INIT EVENT / DUAL CORE BINDING
# ==========================================================
#
# SeedInitEvent and SEEDCore are two layers of the same runtime.
# SeedInitEvent owns initialization and identity context; SEEDCore owns
# the live application core. Both use the same authoritative runtime.
# ==========================================================
def boot_init_event():
    global init_event
    global core

    try:
        from seed.core.init_event import SeedInitEvent
        identity = ensure_seed_identity(SEED_ROOT)
        key_path = SEED_ROOT / "keys" / "seed_private.key"
        key_data = key_path.read_bytes()
        if len(key_data) != 32:
            from cryptography.hazmat.primitives import serialization
            key = serialization.load_pem_private_key(key_data, password=None)
            key_data = key.private_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PrivateFormat.Raw,
                encryption_algorithm=serialization.NoEncryption(),
            )

        runtime_registry = registry or system_registry
        runtime_nodes = authoritative_nodes or nodes or node_registry
        init_event = SeedInitEvent(
            identity,
            key_data,
            storage_root=str(SEED_ROOT),
            orchestrator=orchestrator,
            control_layer=seedcore,
            qbit_dialer=qbit_dialer,
            event_bus=event_bus,
            registry=runtime_registry,
            node_registry=node_registry or runtime_nodes,
            node_manager=globals().get("node_manager"),
            intent_engine=intent_engine,
            analytics_engine=analytics_engine,
            agent_manager=agent_manager,
            memory_manager=memory_manager,
            adaptive_priority_engine=adaptive_priority_engine,
            growth_tree=growth_tree,
            oracle=ORACLE or oracle,
            track_system=track_system,
            track_context=track_context,
            nodes=runtime_nodes,
            qbit=qbit,
        )

        runtime = {
            "init_event": init_event,
            "qbit": qbit,
            "qbit_dialer": qbit_dialer,
            "qbit_loop": queue_loop,
            "event_bus": event_bus,
            "track_system": track_system,
            "track_context": track_context,
            "registry": runtime_registry,
            "node_registry": node_registry or runtime_nodes,
            "nodes": runtime_nodes,
            "intent_engine": intent_engine,
            "analytics_engine": analytics_engine,
            "agent_manager": agent_manager,
            "adaptive_priority_engine": adaptive_priority_engine,
            "growth_tree": growth_tree,
            "oracle": ORACLE or oracle,
            "heartbeatemitter": heartbeat,
            "compute_brain": globals().get("computebrain"),
            "transformer_brain": globals().get("transformerbrain"),
            "seedos": seedos,
            "seed_os": seedos,
            "action_engine": action_engine,
            "seed_network": seed_network,
            "camera_qbit": camera_qbit,
            "render_engine": render_engine,
            "hud_reader": hud_reader,
            "os_control_manager": os_control_manager,
            "screen_tracker": screen_tracker,
            "seed_voice_system": seed_voice_system,
            "cognition_binary_encoder": cognition_binary_encoder,
            "database": database,
        }

        if seedcore is not None and hasattr(seedcore, "bind_authoritative_runtime"):
            seedcore.bind_authoritative_runtime(**runtime)
        else:
            init_event.bind_seedcore_ai(seedcore, **runtime)

        if database is not None and database.enabled:
            try:
                database.record_event(
                    "SEED_BOOT_RUNTIME_BOUND",
                    {
                        "version": VERSION,
                        "build": BUILD,
                        "qbit_id": getattr(qbit, "qbit_id", None),
                        "track_id": getattr(qbit, "track_id", None),
                        "modules_online": sum(1 for value in MODULES_STATUS.values() if value),
                    },
                    track_id=getattr(track_system, "track_id", None) or getattr(qbit, "track_id", None),
                    source="SEED_AI_OS",
                )
            except Exception as exc:
                boot_warn(f"SEEDDatabase boot event write failed: {exc}")

        if seedcore is not None:
            core = seedcore
            if seedcore.qbit_dialer is not qbit_dialer:
                raise RuntimeError("SEEDCore/Dialer identity mismatch")
            if seedcore.qbit is not qbit:
                raise RuntimeError("SEEDCore/Qbit identity mismatch")

        authoritative_registry = globals().get("registry") or globals().get("system_registry")
        registered = False
        if authoritative_registry is not None:
            for method_name in (
                "register",
                "register_module",
                "register_system",
                "add",
                "set",
            ):
                method = getattr(authoritative_registry, method_name, None)
                if not callable(method):
                    continue
                try:
                    method("SeedInitEvent", init_event)
                    registered = True
                    break
                except TypeError:
                    try:
                        method("SeedInitEvent", init_event, "initialization")
                        registered = True
                        break
                    except Exception:
                        continue
                except Exception:
                    continue

        MODULES_STATUS["SeedInitEvent"] = True
        boot_log(
            "SeedInitEvent ONLINE | SEEDCore dual-core runtime bound"
            f" | registry_registered={registered}"
        )
        return init_event

    except Exception as exc:
        MODULES_STATUS["SeedInitEvent"] = False
        trace_exception(exc)
        boot_warn(f"SeedInitEvent binding failed: {exc}")
        return None


# ==========================================================
# SECTION 31 â€” DEVHUD / UI
# ==========================================================

def prepare_tk_root(show_ui=False):

    global root, parent, ui_enabled

    if threading.current_thread() is not threading.main_thread():
        raise RuntimeError(
            "Tk root creation is restricted to the process main thread"
        )

    # Never create a second Tk root.
    if root is not None:
        ui_enabled = bool(show_ui)

        if show_ui:
            try:
                root.deiconify()
            except Exception:
                pass
        else:
            try:
                root.withdraw()
            except Exception:
                pass

        return root

    import tkinter as tk

    root = tk.Tk()
    parent = root
    ui_enabled = bool(show_ui)

    root.title(
        "SEED AI OS â€” DEVHUD"
        if show_ui
        else "SEED AI OS"
    )

    root.geometry("1200x800")

    try:
        root.grid_rowconfigure(0, weight=1)
        root.grid_columnconfigure(0, weight=1)
    except Exception:
        pass

    if not show_ui:
        try:
            root.withdraw()
        except Exception:
            pass

    boot_log(
        "Tk root created on main thread | "
        f"UI={'ENABLED' if show_ui else 'HEADLESS'}"
    )

    return root


def hud_message_handler(payload):

    try:
        print(f"[HUD] {payload}")
    except Exception:
        pass


def boot_ui(load_ui=True):

    global root
    global hud
    global hud_facade
    global hud_state
    global ui_queue
    global dev_hud
    global blackbox

    if not load_ui:
        MODULES_STATUS["DEVHUD"] = False
        boot_log("PHASE 17 | UI disabled")
        return None

    boot_log("PHASE 17 | DEVHUD / UI")

    # ----------------------------------------------------------
    # MAIN-THREAD ENFORCEMENT
    # ----------------------------------------------------------

    if threading.current_thread() is not threading.main_thread():
        MODULES_STATUS["DEVHUD"] = False

        boot_warn(
            "DEVHUD attachment refused: "
            "not the process main thread"
        )

        return None

    # ----------------------------------------------------------
    # TK ROOT
    # ----------------------------------------------------------

    if root is None:
        MODULES_STATUS["DEVHUD"] = False

        boot_warn(
            "DEVHUD attachment refused: "
            "Tk root is missing"
        )

        return None

    # ----------------------------------------------------------
    # AUTHORITATIVE RUNTIME REFERENCES
    # ----------------------------------------------------------

    authoritative_event_bus = globals().get("event_bus")
    authoritative_qbit = globals().get("qbit")
    authoritative_queue_loop = globals().get("queue_loop")
    authoritative_dialer = globals().get("qbit_dialer")
    authoritative_track_system = globals().get("track_system")
    authoritative_track_context = globals().get("track_context")
    authoritative_registry = globals().get("registry")
    authoritative_nodes = globals().get("nodes")
    authoritative_seed_core = globals().get("seedcore")
    authoritative_kernel_bus = globals().get("kernel_bus")
    authoritative_oracle = globals().get("oracle")
    authoritative_oracle_loop = globals().get("oracle_loop")
    authoritative_channel_manager = globals().get("cm")
    authoritative_ipc_bridge = globals().get("ipc_bridge")
    authoritative_channel_controller = globals().get("controller")
    authoritative_device = globals().get("device")
    authoritative_device_manager = globals().get("device_manager")
    authoritative_fathud = globals().get("fathud")

    # ----------------------------------------------------------
    # PRESENTATION STATE / UI QUEUE
    # ----------------------------------------------------------
    # The UI queue is presentation transport only. It is never
    # passed to QbitDialer or QbitQueueLoop.
    # ----------------------------------------------------------
    try:
        from seed.hud.state import HUDState
        from seed.hud.hud import HUD

        if hud_state is None:
            hud_state = HUDState(
                event_bus=authoritative_event_bus,
                track_system=authoritative_track_system,
                registry=authoritative_registry,
                registry_runtime=globals().get("registry_runtime"),
                neural_bridge=globals().get("neural_bridge"),
                oracle=authoritative_oracle,
                qbit_queue_loop=authoritative_queue_loop,
                qbit_dialer=authoritative_dialer,
            )

        ui_queue = hud_state.ui_queue

        if hud_facade is None:
            hud_facade = HUD(
                event_bus=authoritative_event_bus,
                channelmanager=authoritative_channel_manager,
                state=hud_state,
                parent=root,
            )

        hud_facade.ui_queue = hud_state.ui_queue
        bind_hud_runtime = getattr(hud_facade, "bind_runtime", None)
        if callable(bind_hud_runtime):
            bind_hud_runtime(
                event_bus=authoritative_event_bus,
                track_system=authoritative_track_system,
                registry=authoritative_registry,
                qbit_queue_loop=authoritative_queue_loop,
                qbit_dialer=authoritative_dialer,
            )

        boot_log("HUDState ONLINE | UI queue routed to HUD presentation state")

    except Exception as exc:
        hud_state = None
        boot_warn("HUDState/HUD presentation binding deferred | " + str(exc))

    # ----------------------------------------------------------
    # REQUIRED AUTHORITY CHECKS
    # ----------------------------------------------------------

    if authoritative_event_bus is None:
        MODULES_STATUS["DEVHUD"] = False

        boot_warn(
            "DEVHUD attachment deferred: "
            "authoritative EventBus is missing"
        )

        return None

    if authoritative_qbit is None:
        boot_warn(
            "DEVHUD warning: authoritative Qbit is missing"
        )

    if authoritative_queue_loop is None:
        boot_warn(
            "DEVHUD warning: authoritative QbitQueueLoop is missing"
        )

    if authoritative_dialer is None:
        boot_warn(
            "DEVHUD warning: authoritative QbitDialer is missing"
        )

    # ----------------------------------------------------------
    # PREVENT DUPLICATE DEVHUD
    # ----------------------------------------------------------

    if dev_hud is not None:
        try:
            if getattr(dev_hud, "winfo_exists", lambda: True)():
                MODULES_STATUS["DEVHUD"] = True

                boot_log(
                    "DEVHUD already exists | "
                    "reusing authoritative UI instance"
                )

                return dev_hud
        except Exception:
            pass

    try:

        # ======================================================
        # IMPORT DEVHUD
        # ======================================================

        boot_log("DEVHUD import BEGIN")

        from seed.systemutils.DEVHUD import DEVHUD

        boot_log("DEVHUD import RETURNED")

        # ======================================================
        # SHOW ROOT
        # ======================================================

        try:
            root.deiconify()
        except Exception:
            pass

        # ======================================================
        # CONSTRUCT EXACTLY ONE DEVHUD
        # ======================================================

        hud = compatible_construct(
            DEVHUD,
            [
                (
                    (),
                    {
                        "parent": root,

                        # Authoritative runtime
                        "event_bus": authoritative_event_bus,
                        "qbit": authoritative_qbit,
                        "qbit_queue_loop": authoritative_queue_loop,
                        "queue_loop": authoritative_queue_loop,
                        "qbit_dialer": authoritative_dialer,

                        # Core/runtime
                        "seedcore": authoritative_seed_core,
                        "seed_core": authoritative_seed_core,
                        "seedos": seedos,
                        "seed_os": seedos,
                        "track_system": authoritative_track_system,
                        "track_context": authoritative_track_context,
                        "registry": authoritative_registry,
                        "nodes": authoritative_nodes,
                        "kernel_bus": authoritative_kernel_bus,

                        # Oracle
                        "oracle": authoritative_oracle,
                        "oracle_loop": authoritative_oracle_loop,

                        # Device/runtime managers
                        "device": authoritative_device,
                        "device_manager": authoritative_device_manager,

                        # Channels / IPC
                        "channelmanager": authoritative_channel_manager,
                        "channel_manager": authoritative_channel_manager,
                        "channel_id": getattr(
                            authoritative_channel_manager,
                            "channel_id",
                            None,
                        ),
                        "track_system": authoritative_track_system,
                        "engines": {
                            "qbit_dialer": authoritative_dialer,
                            "compute_brain": globals().get(
                                "compute_brain"
                            ) or globals().get(
                                "computebrain"
                            ),
                            "transformer_brain": globals().get(
                                "transformer_brain"
                            ) or globals().get(
                                "transformerbrain"
                            ),
                            "intent_engine": globals().get(
                                "intent_engine"
                            ),
                            "analytics_engine": globals().get(
                                "analytics_engine"
                            ),
                            "action_engine": globals().get(
                                "action_engine"
                            ),
                            "adaptive_engine": globals().get(
                                "adaptive_engine"
                            ),
                            "oracle": authoritative_oracle,
                        },
                        "ipc_bridge": authoritative_ipc_bridge,
                        "channel_controller": authoritative_channel_controller,

                        # Existing EventBus emitter
                        "emit": getattr(
                            authoritative_event_bus,
                            "emit",
                            safe_emit,
                        ),

                        # Runtime storage
                        "storage_root": str(SEED_ROOT),

                        # UI state
                        "build_ui": True,
                        "headless": False,
                        "load_ui": True,

                        # Presentation state / UI transport only
                        "hud": hud_facade,
                        "state": hud_state,
                        "hud_state": hud_state,
                        "ui_queue": ui_queue,
                    },
                ),

                (
                    (),
                    {
                        "parent": root,
                        "event_bus": authoritative_event_bus,
                        "qbit": authoritative_qbit,
                        "qbit_dialer": authoritative_dialer,
                    },
                ),

                (
                    (),
                    {
                        "parent": root,
                        "event_bus": authoritative_event_bus,
                    },
                ),

                (
                    (),
                    {},
                ),
            ],
            "DEVHUD",
        )

        if hud is None:
            raise RuntimeError(
                "DEVHUD failed to initialize"
            )

        # ------------------------------------------------------
        # FULL DEVHUD LAYOUT — DEFERRED / NON-BLOCKING
        #
        # The lightweight DEVHUD shell is already constructed.
        # Heavy UI/ML dependencies are loaded only after Tk owns
        # the mainloop. This keeps boot and processing admission
        # independent of the developer interface.
        # ------------------------------------------------------

        try:
            build_ui = getattr(
                hud,
                "_build_ui",
                None,
            )

            if callable(build_ui) and root is not None:
                root.after(
                    0,
                    lambda: safe_call(
                        build_ui,
                        label="DEVHUD._build_ui",
                    ),
                )
        except Exception as exc:
            boot_warn(
                "DEVHUD full-layout scheduling deferred | "
                f"{exc}"
            )

        boot_log(
            "DEVHUD shell ONLINE | full layout deferred to Tk mainloop"
        )

        # One authoritative DEVHUD reference.
        dev_hud = hud

        # Presentation queue/state are owned by HUDState.
        try:
            hud.hud_state = hud_state
            hud.ui_queue = ui_queue
            hud.hud_facade = hud_facade
        except Exception:
            pass

        # Preserve legacy alias.
        globals()["hud"] = hud

        # ======================================================
        # GRID INTO EXISTING ROOT
        # ======================================================

        try:
            hud.grid(
                row=0,
                column=0,
                sticky="nsew",
            )
        except Exception:
            pass

        # ======================================================
        # ATTACH AUTHORITATIVE RUNTIME REFERENCES
        # ======================================================

        runtime_refs = {
            "event_bus": authoritative_event_bus,
            "qbit": authoritative_qbit,
            "qbit_queue_loop": authoritative_queue_loop,
            "queue_loop": authoritative_queue_loop,
            "qbit_dialer": authoritative_dialer,
            "seedcore": authoritative_seed_core,
            "seed_core": authoritative_seed_core,
            "track_system": authoritative_track_system,
            "track_context": authoritative_track_context,
            "registry": authoritative_registry,
            "nodes": authoritative_nodes,
            "kernel_bus": authoritative_kernel_bus,
            "oracle": authoritative_oracle,
            "oracle_loop": authoritative_oracle_loop,
            "channelmanager": authoritative_channel_manager,
            "channel_manager": authoritative_channel_manager,
            "ipc_bridge": authoritative_ipc_bridge,
            "channel_controller": authoritative_channel_controller,
            "device": authoritative_device,
            "device_manager": authoritative_device_manager,
            "fathud": authoritative_fathud,
        }

        for attr_name, value in runtime_refs.items():

            if value is None:
                continue

            try:
                if hasattr(hud, attr_name):
                    setattr(
                        hud,
                        attr_name,
                        value,
                    )
            except Exception:
                pass

        # ======================================================
        # IPC ROOT ATTACHMENT
        # ======================================================

        if authoritative_ipc_bridge is not None:
            safe_call(
                getattr(
                    authoritative_ipc_bridge,
                    "attach_root",
                    None,
                ),
                root,
                label="IPCBridge.attach_root",
            )

        # ======================================================
        # SEEDCORE HUD ATTACHMENT
        # ======================================================

        if authoritative_seed_core is not None:

            safe_call(
                getattr(
                    authoritative_seed_core,
                    "attach_hud",
                    None,
                ),
                hud,
                label="SEEDCore.attach_hud",
            )

        # ======================================================
        # QBIT DIALER HUD ATTACHMENT
        # ======================================================

        if authoritative_dialer is not None:

            for method_name in (
                "attach_hud",
                "attach_devhud",
                "bind_hud",
                "set_hud",
            ):

                method = getattr(
                    authoritative_dialer,
                    method_name,
                    None,
                )

                if callable(method):

                    result = safe_call(
                        method,
                        hud,
                        label=f"QbitDialer.{method_name}",
                    )

                    if result is not None:
                        break

        # ======================================================
        # TRACK SYSTEM HUD ATTACHMENT
        # ======================================================

        if authoritative_track_system is not None:

            for method_name in (
                "attach_hud",
                "bind_hud",
                "set_hud",
            ):

                method = getattr(
                    authoritative_track_system,
                    method_name,
                    None,
                )

                if callable(method):

                    safe_call(
                        method,
                        hud,
                        label=f"TrackSystem.{method_name}",
                    )

        # ======================================================
        # FATHUD RELATIONSHIP
        # ======================================================
        #
        # FATHUD is already the browser/runtime observer.
        # DEVHUD must not start another FATHUD server.
        #
        # We only expose the existing adapter if DEVHUD supports it.
        # ======================================================

        if authoritative_fathud is not None:

            for method_name in (
                "attach_fathud",
                "bind_fathud",
                "set_fathud",
            ):

                method = getattr(
                    hud,
                    method_name,
                    None,
                )

                if callable(method):

                    safe_call(
                        method,
                        authoritative_fathud,
                        label=f"DEVHUD.{method_name}",
                    )

                    break

        # ======================================================
        # BLACKBOX â€” OPTIONAL OBSERVER
        # ======================================================

        try:

            from seed.systemutils.blackbox import BlackBox

            # Reuse an existing BlackBox if one already exists.
            if blackbox is None:

                blackbox = BlackBox(
                    name="HomeZone"
                )

            safe_call(
                getattr(
                    blackbox,
                    "connect_devhud",
                    None,
                ),
                getattr(
                    hud,
                    "push_message",
                    None,
                ),
                label="BlackBox.connect_devhud",
            )

            safe_call(
                getattr(
                    blackbox,
                    "connect_audio_output",
                    None,
                ),
                getattr(
                    hud,
                    "play_audio_alert",
                    None,
                ),
                label="BlackBox.connect_audio_output",
            )

        except Exception as exc:

            boot_warn(
                "BlackBox/DEVHUD optional attachment failed | "
                f"{exc}"
            )

        # ======================================================
        # DEVHUD CONTROLS
        # ======================================================
        #
        # These are UI intents only.
        #
        # They must ultimately route through QbitDialer.
        # DEVHUD must NOT execute commands directly.
        # ======================================================

        try:

            add_to_hud = getattr(
                hud,
                "add_to_hud",
                None,
            )

            if callable(add_to_hud):

                add_to_hud(
                    "buttons",
                    {
                        "label": "Run Diagnostics",
                        "action": "diag",
                        "authority": "QbitDialer",
                    },
                )

                add_to_hud(
                    "buttons",
                    {
                        "label": "Start AI",
                        "action": "run_ai",
                        "authority": "QbitDialer",
                    },
                )

        except Exception as exc:

            boot_warn(
                "DEVHUD button registration failed | "
                f"{exc}"
            )

        # ======================================================
        # EVENTBUS -> DEVHUD
        # ======================================================

        safe_call(
            getattr(
                authoritative_event_bus,
                "subscribe",
                None,
            ),
            "HUD_MESSAGE",
            hud_message_handler,
            label="EventBus HUD_MESSAGE subscription",
        )

        # ======================================================
        # AUTHORITATIVE IDENTITY VALIDATION
        # ======================================================

        authority_errors = []

        def _verify_identity(
            owner,
            attr_names,
            expected,
            label,
        ):

            if owner is None or expected is None:
                return

            for attr_name in attr_names:

                if not hasattr(owner, attr_name):
                    continue

                try:
                    actual = getattr(
                        owner,
                        attr_name,
                    )
                except Exception:
                    continue

                if actual is not None and actual is not expected:

                    authority_errors.append(
                        f"{label}.{attr_name} "
                        f"is not the authoritative instance"
                    )

                break

        _verify_identity(
            hud,
            ("event_bus",),
            authoritative_event_bus,
            "DEVHUD",
        )

        _verify_identity(
            hud,
            ("qbit",),
            authoritative_qbit,
            "DEVHUD",
        )

        _verify_identity(
            hud,
            ("qbit_queue_loop", "queue_loop"),
            authoritative_queue_loop,
            "DEVHUD",
        )

        _verify_identity(
            hud,
            ("qbit_dialer",),
            authoritative_dialer,
            "DEVHUD",
        )

        _verify_identity(
            hud,
            ("track_system",),
            authoritative_track_system,
            "DEVHUD",
        )

        if authority_errors:

            for error in authority_errors:
                boot_warn(
                    f"DEVHUD authority validation | {error}"
                )

            # Do not replace the bad dependency.
            # DEVHUD remains optional rather than becoming
            # a competing runtime authority.
            MODULES_STATUS["DEVHUD"] = False

            boot_warn(
                "DEVHUD authority validation failed; "
                "SEED runtime remains authoritative"
            )

            return None

        # ======================================================
        # FINAL STATUS
        # ======================================================

        MODULES_STATUS["DEVHUD"] = True

        boot_log(
            "DEVHUD ONLINE | "
            "main-thread UI | "
            "observer attached after SEEDCore | "
            "QbitDialer remains command authority"
        )

        return hud

    except Exception as exc:

        MODULES_STATUS["DEVHUD"] = False

        trace_exception(exc)

        hud = None
        dev_hud = None

        boot_warn(
            "DEVHUD unavailable; "
            "SEEDCore remains authoritative"
        )

        return None

# ==========================================================
# SECTION 32 â€” CLI
# ==========================================================

def boot_cli():
    global cli

    try:

        from interfaces.seed_cli import (
            SEEDCLI,
        )

        cli = compatible_construct(
            SEEDCLI,
            [
                (
                    (),
                    {
                        "event_bus": event_bus,
                        "qbit_dialer": qbit_dialer,
                        "loop": getattr(qbit_dialer, "loop", None),
                    },
                ),
                (
                    (),
                    {
                        "event_bus": event_bus,
                        "qbit_dialer": qbit_dialer,
                    },
                ),
                (
                    (),
                    {},
                ),
            ],
            "SEEDCLI",
        )

        MODULES_STATUS[
            "SEEDCLI"
        ] = cli is not None

    except Exception as exc:

        MODULES_STATUS[
            "SEEDCLI"
        ] = False

        trace_exception(exc)


# ==========================================================
# SECTION 33 â€” QBIT TASK
# ==========================================================

def create_initial_qbit_task():

    global qbit
    global qbit_dialer
    global queue_loop

    # ----------------------------------------------------------
    # AUTHORITATIVE REFERENCES
    # ----------------------------------------------------------

    authoritative_qbit = globals().get("qbit")
    authoritative_queue_loop = globals().get("queue_loop")
    authoritative_dialer = globals().get("qbit_dialer")

    if authoritative_dialer is None:
        boot_warn(
            "Initial Qbit task deferred: "
            "authoritative QbitDialer is unavailable"
        )
        return None

    if authoritative_qbit is None:
        boot_warn(
            "Initial Qbit task deferred: "
            "authoritative Qbit is unavailable"
        )
        return None

    if authoritative_queue_loop is None:
        boot_warn(
            "Initial Qbit task deferred: "
            "authoritative QbitQueueLoop is unavailable"
        )
        return None

    # ----------------------------------------------------------
    # VERIFY DIALER AUTHORITY
    # ----------------------------------------------------------

    dialer_qbit = getattr(
        authoritative_dialer,
        "qbit",
        None,
    )

    if (
        dialer_qbit is not None
        and dialer_qbit is not authoritative_qbit
    ):
        boot_warn(
            "Initial Qbit task refused: "
            "QbitDialer is bound to a different Qbit instance"
        )
        return None

    dialer_queue_loop = getattr(
        authoritative_dialer,
        "queue_loop",
        None,
    )

    if (
        dialer_queue_loop is not None
        and dialer_queue_loop is not authoritative_queue_loop
    ):
        boot_warn(
            "Initial Qbit task refused: "
            "QbitDialer is bound to a different QbitQueueLoop"
        )
        return None

    # ----------------------------------------------------------
    # VERIFY CREATE_TASK API
    # ----------------------------------------------------------

    create_task = getattr(
        authoritative_dialer,
        "create_task",
        None,
    )

    if not callable(create_task):
        boot_warn(
            "Initial Qbit task unavailable: "
            "QbitDialer.create_task is not callable"
        )
        return None

    # ----------------------------------------------------------
    # INITIAL THOUGHT / TASK SEED
    # ----------------------------------------------------------
    #
    # This is intentionally NOT a final command.
    #
    # The existing Qbit thought cycle is allowed to:
    #     reassess
    #     update context
    #     develop
    #     evolve
    #     produce an actionable command later
    #
    # Command authority remains QbitDialer.
    # ----------------------------------------------------------

    payload = {
        "source": "SEED_MAIN",
        "status": "boot",

        "qbit": authoritative_qbit,
        "queue_loop": authoritative_queue_loop,

        "task_type": "INITIAL_THOUGHT",
        "initial_thought": True,

        "allow_evolution": True,
        "allow_reassessment": True,
        "allow_context_update": True,
        "allow_development": True,

        "authority": "QbitDialer",
        "transport": "QbitQueueLoop",
    }

    # ----------------------------------------------------------
    # CREATE THROUGH EXISTING DIALER
    # ----------------------------------------------------------

    try:

        result = safe_call(
            create_task,
            payload,
            default=None,
            label="QbitDialer.create_task",
        )

        if result is None:
            boot_warn(
                "Initial Qbit task was not created | "
                "QbitDialer returned no task"
            )
            return None

        boot_log(
            "Initial Qbit task created | "
            "source=SEED_MAIN | "
            "thought_cycle=enabled | "
            "evolution=enabled"
        )

        # ------------------------------------------------------
        # OPTIONAL TELEMETRY
        # ------------------------------------------------------

        event_bus_ref = globals().get("event_bus")

        if event_bus_ref is not None:

            safe_call(
                getattr(
                    event_bus_ref,
                    "emit",
                    None,
                ),
                "INITIAL_QBIT_TASK_CREATED",
                {
                    "source": "SEED_MAIN",
                    "task_type": "INITIAL_THOUGHT",
                    "evolving": True,
                    "reassessment": True,
                    "qbit_authoritative": (
                        authoritative_qbit
                    ),
                    "queue_loop_authoritative": (
                        authoritative_queue_loop
                    ),
                },
                label="EventBus INITIAL_QBIT_TASK_CREATED",
            )

        return result

    except Exception as exc:

        trace_exception(exc)

        boot_warn(
            "Initial Qbit task creation failed | "
            f"{type(exc).__name__}: {exc}"
        )

        return None

# ==========================================================
# SECTION 34 â€” QUEUE / WATCHDOG START
# ==========================================================
#
# PURPOSE:
#
# - Start the authoritative QbitQueueLoop exactly once.
# - Do NOT start QbitDialer here.
# - Do NOT create a Qbit here.
# - Do NOT create a queue here.
# - Start Heartbeat only if it has not already been started.
# - Verify QbitDialer after its dedicated boot phase.
# - Preserve exact Qbit / QueueLoop / EventBus identity.
#
# AUTHORITATIVE CHAIN:
#
# EventBus
#     â†“
# Qbit
#     â†“
# QbitQueueLoop
#     â†“
# QbitDialer
#
# QbitDialer startup belongs exclusively to:
#
#     boot_qbit_dialer()
#
# ==========================================================


async def start_processing_loops():

    global qbit_core
    global qbit
    global queue_loop
    global qbit_dialer
    global heartbeat

    boot_log(
        "PHASE 18 | Processing loops"
    )

    # ======================================================
    # 00 â€” RESOLVE AUTHORITATIVE RUNTIME
    # ======================================================
    #
    # Do not manufacture missing dependencies here.
    # This phase only starts already-booted authorities.
    # ======================================================

    authoritative_qbit = globals().get(
        "qbit"
    )

    authoritative_queue_loop = globals().get(
        "queue_loop"
    )

    authoritative_dialer = globals().get(
        "qbit_dialer"
    )

    authoritative_event_bus = globals().get(
        "event_bus"
    )

    authoritative_heartbeat = globals().get(
        "heartbeat"
    )

    # ======================================================
    # 01 â€” REQUIRED QBIT
    # ======================================================

    if authoritative_qbit is None:

        MODULES_STATUS[
            "Qbit"
        ] = False

        raise RuntimeError(
            "Processing loops require "
            "authoritative Qbit"
        )

    # ======================================================
    # 02 â€” AUTHORITATIVE QBIT QUEUE LOOP
    # ======================================================
    #
    # queue_loop MUST already have been created by
    # boot_queue_loop().
    #
    # NEVER construct another QbitQueueLoop here.
    # NEVER construct another queue here.
    # NEVER construct another Qbit here.
    # ======================================================

    if authoritative_queue_loop is None:

        MODULES_STATUS[
            "QbitQueueLoop"
        ] = False

        raise RuntimeError(
            "Processing loops require "
            "authoritative QbitQueueLoop"
        )

    # ======================================================
    # 03 â€” EVENTBUS IDENTITY
    # ======================================================

    if authoritative_event_bus is None:

        MODULES_STATUS[
            "EventBus"
        ] = False

        raise RuntimeError(
            "Processing loops require "
            "authoritative EventBus"
        )

    # ======================================================
    # 04 â€” QBIT IDENTITY BEFORE START
    # ======================================================
    #
    # qbit_core is an alias/reference to the same Qbit.
    # It is NOT a second Qbit.
    # ======================================================

    if qbit_core is not None:

        if qbit_core is not authoritative_qbit:

            MODULES_STATUS[
                "Qbit"
            ] = False

            raise RuntimeError(
                "Qbit core identity mismatch before "
                "processing-loop startup"
            )

    else:

        qbit_core = authoritative_qbit

    # ======================================================
    # 05 â€” QUEUE LOOP IDENTITY BEFORE START
    # ======================================================
    #
    # The object itself must be the authoritative
    # QbitQueueLoop instance.
    #
    # A plain queue.Queue is NOT acceptable here.
    # ======================================================

    queue_loop_type_name = type(
        authoritative_queue_loop
    ).__name__

    if (
        "QbitQueueLoop"
        not in queue_loop_type_name
    ):

        # Do not automatically replace it.
        # The dedicated queue boot phase owns construction.
        MODULES_STATUS[
            "QbitQueueLoop"
        ] = False

        raise RuntimeError(
            "Authoritative queue_loop is not a "
            "QbitQueueLoop instance | "
            f"type={type(authoritative_queue_loop)!r}"
        )

    # ======================================================
    # 06 â€” AUTHORITATIVE QBIT QUEUE LOOP START
    # ======================================================
    #
    # Start exactly once.
    #
    # Different versions of QbitQueueLoop may expose
    # different running flags, so inspect existing flags
    # without creating another state machine.
    # ======================================================

    try:

        queue_running = bool(

            getattr(
                authoritative_queue_loop,
                "_running",
                False,
            )

            or

            getattr(
                authoritative_queue_loop,
                "running",
                False,
            )

            or

            getattr(
                authoritative_queue_loop,
                "_loop_running",
                False,
            )

            or

            getattr(
                authoritative_queue_loop,
                "is_running",
                False,
            )
        )

        if not queue_running:

            start_queue = getattr(
                authoritative_queue_loop,
                "start",
                None,
            )

            if not callable(
                start_queue
            ):

                start_queue = getattr(
                    authoritative_queue_loop,
                    "start_loop",
                    None,
                )

            if not callable(
                start_queue
            ):

                raise RuntimeError(
                    "Authoritative QbitQueueLoop has no "
                    "start() or start_loop() method"
                )

            result = start_queue()

            if inspect.isawaitable(
                result
            ):

                await result

            boot_log(
                "QbitQueueLoop started | "
                "authoritative instance"
            )

        else:

            boot_log(
                "QbitQueueLoop already RUNNING | "
                "no duplicate start"
            )

        MODULES_STATUS[
            "QbitQueueLoop"
        ] = True

    except Exception as exc:

        MODULES_STATUS[
            "QbitQueueLoop"
        ] = False

        trace_exception(
            exc
        )

        raise RuntimeError(
            "QbitQueueLoop processing start failed"
        ) from exc

    # ======================================================
    # 07 â€” HEARTBEAT
    # ======================================================
    #
    # Heartbeat is a SIGNAL SOURCE.
    #
    # It does NOT become command authority.
    # It does NOT start QbitDialer.
    # It does NOT create another queue.
    #
    # Heartbeat starts only after the authoritative
    # QbitQueueLoop is available.
    # ======================================================

    if authoritative_heartbeat is not None:

        try:

            heartbeat_running = bool(

                getattr(
                    authoritative_heartbeat,
                    "_running",
                    False,
                )

                or

                getattr(
                    authoritative_heartbeat,
                    "running",
                    False,
                )

                or

                getattr(
                    authoritative_heartbeat,
                    "_loop_running",
                    False,
                )

                or

                getattr(
                    authoritative_heartbeat,
                    "is_running",
                    False,
                )
            )

            if not heartbeat_running:

                start_heartbeat = getattr(
                    authoritative_heartbeat,
                    "start",
                    None,
                )

                if callable(
                    start_heartbeat
                ):

                    result = start_heartbeat()

                    if inspect.isawaitable(
                        result
                    ):

                        await result

                    boot_log(
                        "Heartbeat started | "
                        "signal source"
                    )

                else:

                    boot_warn(
                        "Heartbeat exposes no "
                        "start() method"
                    )

            else:

                boot_log(
                    "Heartbeat already RUNNING | "
                    "no duplicate start"
                )

        except Exception as exc:

            trace_exception(
                exc
            )

            logger.error(
                "[Heartbeat] processing startup failed | %s",
                exc,
            )

    else:

        boot_warn(
            "Heartbeat unavailable | "
            "processing continues without heartbeat start"
        )

    # ======================================================
    # 08 â€” QBIT DIALER MUST ALREADY EXIST
    # ======================================================
    #
    # IMPORTANT:
    #
    # This phase NEVER starts the Dialer.
    #
    # boot_qbit_dialer() owns Dialer startup.
    # ======================================================

    if authoritative_dialer is None:

        MODULES_STATUS[
            "QbitDialer"
        ] = False

        raise RuntimeError(
            "Processing loops require "
            "authoritative QbitDialer"
        )

    # ======================================================
    # 09 â€” HARD QBIT IDENTITY CHECK
    # ======================================================
    #
    # The Dialer must reference the exact same Qbit object.
    # ======================================================

    dialer_qbit = getattr(
        authoritative_dialer,
        "qbit",
        None,
    )

    if dialer_qbit is not authoritative_qbit:

        MODULES_STATUS[
            "QbitDialer"
        ] = False

        raise RuntimeError(
            "QbitDialer lost authoritative Qbit "
            "during processing-loop startup"
        )

    # ======================================================
    # 10 â€” HARD QUEUE LOOP IDENTITY CHECK
    # ======================================================
    #
    # IMPORTANT:
    #
    # Do NOT use qbit_queue as the authoritative identity
    # check. qbit_queue may legitimately be the physical
    # queue owned by QbitQueueLoop.
    #
    # The Dialer must point to the exact QbitQueueLoop
    # object through one of its loop references.
    # ======================================================

    dialer_queue_loop = None

    for attr_name in (
        "queue_loop",
        "qbit_loop",
        "qbit_queue_loop",
    ):

        candidate = getattr(
            authoritative_dialer,
            attr_name,
            None,
        )

        if candidate is not None:

            dialer_queue_loop = candidate
            break

    if dialer_queue_loop is None:

        MODULES_STATUS[
            "QbitDialer"
        ] = False

        raise RuntimeError(
            "QbitDialer has no authoritative "
            "QbitQueueLoop binding"
        )

    if dialer_queue_loop is not authoritative_queue_loop:

        MODULES_STATUS[
            "QbitDialer"
        ] = False

        raise RuntimeError(
            "QbitDialer lost authoritative "
            "QbitQueueLoop during "
            "processing-loop startup | "
            f"received={type(dialer_queue_loop)!r} | "
            f"expected={type(authoritative_queue_loop)!r}"
        )

    # ======================================================
    # 11 â€” PHYSICAL QUEUE SANITY CHECK
    # ======================================================
    #
    # qbit_queue is allowed to be a physical queue.
    #
    # It must NOT be confused with queue_loop.
    #
    # If the Dialer exposes qbit_queue and it is the same
    # object as queue_loop, that is suspicious because the
    # authoritative loop and physical transport are separate
    # concepts in this architecture.
    #
    # We report rather than silently replacing anything.
    # ======================================================

    dialer_physical_queue = getattr(
        authoritative_dialer,
        "qbit_queue",
        None,
    )

    if (
        dialer_physical_queue is not None
        and dialer_physical_queue
        is authoritative_queue_loop
    ):

        boot_warn(
            "QbitDialer.qbit_queue references "
            "QbitQueueLoop directly; verify Dialer "
            "queue/loop contract"
        )

    # ======================================================
    # 12 â€” EVENTBUS IDENTITY
    # ======================================================

    dialer_event_bus = getattr(
        authoritative_dialer,
        "event_bus",
        None,
    )

    if dialer_event_bus is not authoritative_event_bus:

        MODULES_STATUS[
            "QbitDialer"
        ] = False

        raise RuntimeError(
            "QbitDialer lost authoritative EventBus "
            "during processing-loop startup"
        )

    # ======================================================
    # 13 â€” DIALER RUNNING STATUS ONLY
    # ======================================================
    #
    # Do NOT call:
    #
    #     qbit_dialer.start()
    #     qbit_dialer.start_loop()
    #
    # Those belong exclusively to boot_qbit_dialer().
    #
    # This section only verifies state.
    # ======================================================

    dialer_running = bool(

        getattr(
            authoritative_dialer,
            "_running",
            False,
        )

        or

        getattr(
            authoritative_dialer,
            "running",
            False,
        )

        or

        getattr(
            authoritative_dialer,
            "_online",
            False,
        )

        or

        getattr(
            authoritative_dialer,
            "online",
            False,
        )
    )

    if dialer_running:

        boot_log(
            "QbitDialer RUNNING | "
            "dedicated boot already completed | "
            "no duplicate start"
        )

    else:

        boot_warn(
            "QbitDialer synchronized but is not "
            "reporting RUNNING | "
            "no start attempted in PHASE 18"
        )

    # The Dialer itself remains structurally valid even if
    # its implementation does not expose a conventional
    # running flag.
    MODULES_STATUS[
        "QbitDialer"
    ] = True

    # ======================================================
    # 14 â€” FINAL QBIT IDENTITY CHECK
    # ======================================================
    #
    # Processing startup is never allowed to replace Qbit.
    # ======================================================

    if qbit is None:

        MODULES_STATUS[
            "Qbit"
        ] = False

        raise RuntimeError(
            "Authoritative Qbit disappeared during "
            "processing-loop startup"
        )

    if qbit is not authoritative_qbit:

        MODULES_STATUS[
            "Qbit"
        ] = False

        raise RuntimeError(
            "Authoritative Qbit reference changed "
            "during processing-loop startup"
        )

    if qbit_core is not qbit:

        # qbit_core is only an alias.
        qbit_core = qbit

    MODULES_STATUS[
        "Qbit"
    ] = True

    # ======================================================
    # 15 â€” FINAL QUEUE IDENTITY CHECK
    # ======================================================

    if queue_loop is not authoritative_queue_loop:

        MODULES_STATUS[
            "QbitQueueLoop"
        ] = False

        raise RuntimeError(
            "Authoritative QbitQueueLoop reference "
            "changed during processing-loop startup"
        )

    MODULES_STATUS[
        "QbitQueueLoop"
    ] = True

    # ======================================================
    # 16 â€” FINAL AUTHORITY REPORT
    # ======================================================

    boot_log(
        "Processing loops synchronized | "
        "EventBus -> Qbit -> QbitQueueLoop -> QbitDialer"
    )

    return None
# ==========================================================
# SECTION 35 â€” SYSTEM BOOT EVENT
# ==========================================================

async def async_system_boot_event():

    authoritative_event_bus = globals().get(
        "event_bus"
    )

    if authoritative_event_bus is None:
        boot_warn(
            "SYSTEM_BOOT event skipped | "
            "authoritative EventBus unavailable"
        )
        return None

    emit = getattr(
        authoritative_event_bus,
        "emit",
        None,
    )

    if not callable(emit):
        boot_warn(
            "SYSTEM_BOOT event skipped | "
            "EventBus.emit unavailable"
        )
        return None

    payload = {
        "source": "main.py",
        "version": VERSION,
        "build": BUILD,
        "timestamp": time.time(),

        # Runtime authority
        "qbit": (
            "available"
            if globals().get("qbit") is not None
            else "missing"
        ),
        "queue_loop": (
            "available"
            if globals().get("queue_loop") is not None
            else "missing"
        ),
        "qbit_dialer": (
            "available"
            if globals().get("qbit_dialer") is not None
            else "missing"
        ),
    }

    try:

        result = emit(
            "SYSTEM_BOOT",
            payload,
        )

        if inspect.isawaitable(result):
            await result

        boot_log(
            "SYSTEM_BOOT event emitted | "
            "authoritative EventBus"
        )

        return result

    except Exception as exc:

        trace_exception(exc)

        boot_warn(
            "SYSTEM_BOOT event emission failed | "
            f"{type(exc).__name__}: {exc}"
        )

        return None


# ==========================================================
# SECTION 36 â€” RUNTIME HEARTBEAT
# ==========================================================

async def runtime_tick():

    global async_shutdown_event

    # ------------------------------------------------------
    # SHARED ASYNC SHUTDOWN EVENT
    # ------------------------------------------------------

    if async_shutdown_event is None:
        async_shutdown_event = asyncio.Event()

    tick = 0

    boot_log(
        "Runtime telemetry tick ONLINE"
    )

    while not async_shutdown_event.is_set():

        tick += 1
        if tick % 10 == 0:
            heartbeat_primary_runtime()

        try:

            authoritative_event_bus = globals().get(
                "event_bus"
            )

            if authoritative_event_bus is not None:

                emit = getattr(
                    authoritative_event_bus,
                    "emit",
                    None,
                )

                if callable(emit):

                    payload = {
                        "tick": tick,
                        "timestamp": time.time(),
                        "source": "runtime_tick",

                        "qbit": (
                            globals().get("qbit")
                            is not None
                        ),

                        "queue_loop": (
                            globals().get("queue_loop")
                            is not None
                        ),

                        "qbit_dialer": (
                            globals().get("qbit_dialer")
                            is not None
                        ),
                    }

                    result = emit(
                        "SEED_RUNTIME_TICK",
                        payload,
                    )

                    if inspect.isawaitable(result):
                        await result

        except asyncio.CancelledError:

            break

        except Exception as exc:

            trace_exception(exc)

            logger.error(
                "[RuntimeTick] telemetry tick failed | %s",
                exc,
            )

        # --------------------------------------------------
        # ONE SECOND TELEMETRY INTERVAL
        # --------------------------------------------------

        try:

            await asyncio.wait_for(
                async_shutdown_event.wait(),
                timeout=1.0,
            )

        except asyncio.TimeoutError:

            # Normal one-second tick interval.
            continue

        except asyncio.CancelledError:

            break

        except Exception as exc:

            trace_exception(exc)

            # Preserve runtime operation if the shutdown
            # event itself encounters an unexpected failure.
            await asyncio.sleep(1.0)

    boot_log(
        "Runtime telemetry tick STOPPED"
    )


# ==========================================================
# UI RUNTIME TICK
# ==========================================================

def start_ui_runtime_tick():

    global ui_tick

    if root is None:
        boot_warn(
            "UI runtime tick skipped | "
            "Tk root unavailable"
        )
        return None

    # ------------------------------------------------------
    # PREVENT DUPLICATE UI TICK SCHEDULING
    # ------------------------------------------------------

    if globals().get(
        "_ui_runtime_tick_started",
        False,
    ):

        boot_log(
            "UI runtime tick already scheduled | "
            "no duplicate timer"
        )

        return None

    globals()[
        "_ui_runtime_tick_started"
    ] = True

    # ------------------------------------------------------
    # UI TICK
    # ------------------------------------------------------

    def tick():

        global ui_tick

        # ----------------------------------------------
        # SHUTDOWN CHECK
        # ----------------------------------------------

        try:

            if shutdown_event.is_set():

                globals()[
                    "_ui_runtime_tick_started"
                ] = False

                return

        except Exception:
            pass

        try:

            if (
                async_shutdown_event is not None
                and async_shutdown_event.is_set()
            ):

                globals()[
                    "_ui_runtime_tick_started"
                ] = False

                return

        except Exception:
            pass

        # ----------------------------------------------
        # INCREMENT UI TICK
        # ----------------------------------------------

        ui_tick += 1

        try:

            # ------------------------------------------
            # DEVHUD PRESENTATION UPDATE
            # ------------------------------------------

            authoritative_hud = globals().get(
                "dev_hud"
            )

            if authoritative_hud is not None:

                update_tick_method = getattr(
                    authoritative_hud,
                    "update_tick",
                    None,
                )

                if callable(
                    update_tick_method
                ):

                    update_tick_method(
                        ui_tick
                    )

            # ------------------------------------------
            # EVENTBUS TELEMETRY
            # ------------------------------------------
            #
            # This is still observer telemetry.
            # It is not a command and does not enter
            # QbitDialer as an action.
            # ------------------------------------------

            authoritative_event_bus = globals().get(
                "event_bus"
            )

            if authoritative_event_bus is not None:

                emit = getattr(
                    authoritative_event_bus,
                    "emit",
                    None,
                )

                if callable(emit):

                    result = emit(
                        "SEED_RUNTIME_TICK",
                        {
                            "tick": ui_tick,
                            "timestamp": time.time(),
                            "source": "devhud_ui_tick",
                            "presentation": True,
                        },
                    )

                    # Tk's callback cannot await.
                    #
                    # If EventBus.emit is async, schedule the
                    # existing coroutine on the already-running
                    # event loop rather than creating a new loop.
                    if inspect.isawaitable(result):

                        try:

                            running_loop = (
                                asyncio.get_running_loop()
                            )

                            running_loop.create_task(
                                result
                            )

                        except RuntimeError:

                            # No async loop is running on the
                            # Tk thread. Do not create one here.
                            #
                            # Close the coroutine when possible
                            # so it is not left unawaited.
                            try:
                                result.close()
                            except Exception:
                                pass

        except Exception as exc:

            trace_exception(
                exc
            )

        # ----------------------------------------------
        # RESCHEDULE ON THE EXISTING TK ROOT
        # ----------------------------------------------

        try:

            if root is not None:

                root.after(
                    1000,
                    tick,
                )

            else:

                globals()[
                    "_ui_runtime_tick_started"
                ] = False

        except Exception:

            globals()[
                "_ui_runtime_tick_started"
            ] = False

    # ------------------------------------------------------
    # INITIAL SCHEDULE
    # ------------------------------------------------------

    try:

        root.after(
            1000,
            tick,
        )

        boot_log(
            "UI runtime tick ONLINE | "
            "Tk main-thread scheduler"
        )

    except Exception as exc:

        globals()[
            "_ui_runtime_tick_started"
        ] = False

        trace_exception(
            exc
        )

        boot_warn(
            "UI runtime tick could not be scheduled | "
            f"{exc}"
        )

        return None

    return None

# ==========================================================
# SECTION 37 â€” MENU UPDATE LOOP
# ==========================================================

async def menu_update_loop(
    ui,
    track_system,
    interval=5,
):

    global async_shutdown_event

    # ------------------------------------------------------
    # VALIDATE INTERVAL
    # ------------------------------------------------------

    try:
        interval = max(
            0.1,
            float(interval),
        )
    except Exception:
        interval = 5.0

    # ------------------------------------------------------
    # SHARED ASYNC SHUTDOWN EVENT
    # ------------------------------------------------------

    if async_shutdown_event is None:
        async_shutdown_event = asyncio.Event()

    boot_log(
        "Menu update loop ONLINE | "
        f"interval={interval}s"
    )

    # ------------------------------------------------------
    # MAIN LOOP
    # ------------------------------------------------------

    while not async_shutdown_event.is_set():

        try:

            # ==================================================
            # AUTHORITATIVE TRACK SYSTEM
            # ==================================================

            authoritative_track_system = (
                track_system
            )

            if authoritative_track_system is None:

                boot_warn(
                    "Menu update loop waiting | "
                    "TrackSystem unavailable"
                )

                # Wait without creating another task/loop.
                try:
                    await asyncio.wait_for(
                        async_shutdown_event.wait(),
                        timeout=interval,
                    )
                except asyncio.TimeoutError:
                    continue

                break

            # ==================================================
            # CHANNELS
            # ==================================================

            channels = safe_call(
                getattr(
                    authoritative_track_system,
                    "all_channels",
                    None,
                ),
                default={},
                label="TrackSystem.all_channels",
            )

            if channels is None:
                channels = {}

            # ==================================================
            # OVERLAYS
            # ==================================================

            overlays = safe_call(
                getattr(
                    authoritative_track_system,
                    "all_overlays",
                    None,
                ),
                default={},
                label="TrackSystem.all_overlays",
            )

            if overlays is None:
                overlays = {}

            # ==================================================
            # CHANNEL LABELS
            # ==================================================

            channel_labels = {}

            try:

                channel_items = (
                    channels.items()
                    if hasattr(
                        channels,
                        "items",
                    )
                    else []
                )

                for name, channel in channel_items:

                    try:

                        channel_labels[name] = {
                            "id": getattr(
                                channel,
                                "id",
                                None,
                            ),

                            "qbit_code":
                                convert_channel_to_qbit_number(
                                    name
                                ),
                        }

                    except Exception as exc:

                        trace_exception(
                            exc
                        )

            except Exception as exc:

                trace_exception(
                    exc
                )

            # ==================================================
            # OVERLAY LABELS
            # ==================================================

            overlay_labels = {}

            try:

                overlay_items = (
                    overlays.items()
                    if hasattr(
                        overlays,
                        "items",
                    )
                    else []
                )

                for name, overlay in overlay_items:

                    try:

                        overlay_labels[name] = {
                            "id": getattr(
                                overlay,
                                "id",
                                None,
                            ),

                            "qbit_code":
                                convert_channel_to_qbit_number(
                                    name
                                ),
                        }

                    except Exception as exc:

                        trace_exception(
                            exc
                        )

            except Exception as exc:

                trace_exception(
                    exc
                )

            # ==================================================
            # UI UPDATE
            # ==================================================
            #
            # UI remains presentation-only.
            # No command submission occurs here.
            # ==================================================

            if ui is not None:

                update = getattr(
                    ui,
                    "update_menu_channels",
                    None,
                )

                if callable(update):

                    result = update(
                        channel_labels,
                        overlay_labels,
                    )

                    # A UI implementation should normally be
                    # synchronous. If an existing implementation
                    # returns an awaitable, honor it without
                    # creating another event loop.
                    if inspect.isawaitable(
                        result
                    ):

                        await result

        except asyncio.CancelledError:

            break

        except Exception as exc:

            trace_exception(
                exc
            )

            logger.error(
                "[MenuUpdateLoop] update failed | %s",
                exc,
            )

        # ======================================================
        # SHUTDOWN-AWARE WAIT
        # ======================================================
        #
        # Prefer waiting on the existing shutdown event over
        # an unconditional sleep so shutdown does not have to
        # wait for the full interval.
        # ======================================================

        try:

            await asyncio.wait_for(
                async_shutdown_event.wait(),
                timeout=interval,
            )

        except asyncio.TimeoutError:

            # Normal interval expiration.
            continue

        except asyncio.CancelledError:

            break

        except Exception as exc:

            trace_exception(
                exc
            )

            # Preserve the loop if shutdown waiting itself
            # encounters an unexpected implementation issue.
            await asyncio.sleep(
                interval
            )

    boot_log(
        "Menu update loop STOPPED"
    )

    return None
# ==========================================================
# SECTION 38 â€” HEALTH TRACKING
# ==========================================================

def my_track():
    status = "unknown"

    try:

        if qbit is not None:

            status_method = getattr(
                qbit,
                "status",
                None,
            )

            if callable(
                status_method
            ):
                status = status_method()

    except Exception:
        status = "error"

    return {
        "cpu": 0,
        "memory": 0,
        "qbit_status": status,
    }



def seed_track():

    global health_monitor

    try:
        import psutil
    except ImportError:
        psutil = None

    # ----------------------------------------------------------
    # AUTHORITATIVE RUNTIME REFERENCES
    # ----------------------------------------------------------

    authoritative_qbit = globals().get(
        "qbit",
        None,
    )

    health_monitor = globals().get(
        "health_monitor",
        None,
    )

    authoritative_event_bus = globals().get(
        "event_bus",
        None,
    )

    # ----------------------------------------------------------
    # QBIT STATUS
    # ----------------------------------------------------------

    qbit_status = "Unknown"
    qbit_error = None

    try:
        if authoritative_qbit is not None:

            status_method = getattr(
                authoritative_qbit,
                "status",
                None,
            )

            if callable(status_method):

                status_result = status_method()

                if inspect.isawaitable(status_result):
                    qbit_status = "AsyncStatusPending"
                else:
                    qbit_status = status_result

    except Exception as exc:

        qbit_error = str(exc)
        qbit_status = "Error"

    # ----------------------------------------------------------
    # SYSTEM METRICS
    # ----------------------------------------------------------

    cpu = (
        psutil.cpu_percent()
        if psutil is not None
        else None
    )

    memory = (
        psutil.virtual_memory().used
        if psutil is not None
        else None
    )

    disk = (
        psutil.disk_usage(
            str(SEED_ROOT)
        ).percent
        if psutil is not None
        else None
    )

    memory_used_mb = (
        memory / (1024 * 1024)
        if memory is not None
        else None
    )

    # ----------------------------------------------------------
    # CANONICAL HEALTH SNAPSHOT
    # ----------------------------------------------------------

    health_snapshot = {
        "cpu_percent": cpu,
        "memory_used_mb": memory_used_mb,
        "disk_percent": disk,
        "qbit_status": qbit_status,
        "qbit_error": qbit_error,
        "timestamp": time.time(),
        "source": "seed_track",
        "authority": "HealthMonitor",
    }

    # ----------------------------------------------------------
    # HEALTHMONITOR HANDOFF
    # ----------------------------------------------------------
    #
    # HealthMonitor is downstream of this observation.
    # We only call methods that actually exist.
    #

    if health_monitor is not None:

        health_methods = (
            "record_health",
            "record_snapshot",
            "update_health",
            "update",
            "ingest",
            "process",
            "observe",
        )

        health_delivered = False

        for method_name in health_methods:

            method = getattr(
                health_monitor,
                method_name,
                None,
            )

            if not callable(method):
                continue

            try:

                result = method(
                    health_snapshot
                )

                health_delivered = True

                if inspect.isawaitable(result):

                    try:
                        running_loop = asyncio.get_running_loop()
                    except RuntimeError:
                        running_loop = None

                    if running_loop is not None:
                        running_loop.create_task(
                            result
                        )

                break

            except TypeError:
                # Some HealthMonitor implementations may expect
                # keyword fields rather than a snapshot dictionary.
                try:

                    result = method(
                        **health_snapshot
                    )

                    health_delivered = True

                    if inspect.isawaitable(result):

                        try:
                            running_loop = asyncio.get_running_loop()
                        except RuntimeError:
                            running_loop = None

                        if running_loop is not None:
                            running_loop.create_task(
                                result
                            )

                    break

                except Exception:
                    continue

            except Exception as exc:

                trace_exception(exc)
                break

        if not health_delivered:

            try:
                health_monitor.last_snapshot = (
                    health_snapshot
                )
            except Exception:
                pass

    # ----------------------------------------------------------
    # EVENTBUS TELEMETRY
    # ----------------------------------------------------------
    #
    # EventBus is observer telemetry only.
    # It does not become command authority.
    #

    if authoritative_event_bus is not None:

        emit = getattr(
            authoritative_event_bus,
            "emit",
            None,
        )

        if callable(emit):

            try:

                result = emit(
                    "SEED_HEALTH_SNAPSHOT",
                    health_snapshot,
                )

                if inspect.isawaitable(result):

                    try:
                        running_loop = asyncio.get_running_loop()
                    except RuntimeError:
                        running_loop = None

                    if running_loop is not None:
                        running_loop.create_task(
                            result
                        )

            except Exception as exc:

                trace_exception(exc)

    # ----------------------------------------------------------
    # RETURN CANONICAL SNAPSHOT
    # ----------------------------------------------------------

    return health_snapshot


# ==========================================================
# SECTION 39 â€” ADAPTIVE LOOP
# ==========================================================
#
# HEALTH
#   â†“
# HealthMonitor / Guardian
#   â†“
# IntentEngine
#   â†“
# ComputeBrain
#   â†“
# TransformerBrain
#   â†“
# AnalyticsEngine
#   â†“
# QbitDialer
#
# This loop is an observation / cognition / analytics bridge.
# It does NOT become command authority.
#
# QbitDialer remains the sole command authority.
# ==========================================================

def adaptive_loop():

    global shutdown_event

    while not shutdown_event.is_set():

        try:

            import psutil

            # --------------------------------------------------
            # AUTHORITATIVE RUNTIME REFERENCES
            # --------------------------------------------------

            authoritative_event_bus = globals().get(
                "event_bus",
                None,
            )

            authoritative_health_monitor = globals().get(
                "health_monitor",
                None,
            )

            authoritative_guardian = globals().get(
                "guardian",
                None,
            )

            authoritative_intent_engine = globals().get(
                "intent_engine",
                None,
            )

            authoritative_analytics_engine = globals().get(
                "analytics_engine",
                None,
            )

            authoritative_compute_brain = globals().get(
                "compute_brain",
                None,
            )

            authoritative_transformer_brain = globals().get(
                "transformer_brain",
                None,
            )

            authoritative_qbit = globals().get(
                "qbit",
                None,
            )

            authoritative_qbit_dialer = globals().get(
                "qbit_dialer",
                None,
            )

            # --------------------------------------------------
            # SYSTEM HEALTH SAMPLE
            # --------------------------------------------------

            cpu = psutil.cpu_percent()

            mem_percent = (
                psutil.virtual_memory().percent
            )

            memory_used = (
                psutil.virtual_memory().used
            )

            disk_percent = (
                psutil.disk_usage(
                    str(SEED_ROOT)
                ).percent
            )

            health_sample = {
                "cpu": cpu,
                "mem": mem_percent,
                "memory_used": memory_used,
                "disk": disk_percent,
                "timestamp": time.time(),
                "source": "adaptive_loop",
            }

            # --------------------------------------------------
            # HEALTHMONITOR
            # --------------------------------------------------
            #
            # HealthMonitor owns health state.
            # Do not construct another monitor here.
            #

            if authoritative_health_monitor is not None:

                health_snapshot = {
                    **health_sample,
                    "qbit": (
                        authoritative_qbit
                        if authoritative_qbit is not None
                        else None
                    ),
                }

                for method_name in (
                    "record_health",
                    "record_snapshot",
                    "update_health",
                    "update",
                    "ingest",
                    "observe",
                ):

                    method = getattr(
                        authoritative_health_monitor,
                        method_name,
                        None,
                    )

                    if not callable(method):
                        continue

                    try:

                        result = method(
                            health_snapshot
                        )

                        if inspect.isawaitable(result):

                            try:
                                loop = asyncio.get_running_loop()
                            except RuntimeError:
                                loop = None

                            if loop is not None:
                                loop.create_task(
                                    result
                                )

                        break

                    except TypeError:

                        try:

                            result = method(
                                **health_snapshot
                            )

                            if inspect.isawaitable(result):

                                try:
                                    loop = asyncio.get_running_loop()
                                except RuntimeError:
                                    loop = None

                                if loop is not None:
                                    loop.create_task(
                                        result
                                    )

                            break

                        except Exception:
                            continue

                    except Exception as exc:

                        trace_exception(exc)
                        break

            # --------------------------------------------------
            # GUARDIAN
            # --------------------------------------------------

            guardian_result = None

            if authoritative_guardian is not None:

                check = getattr(
                    authoritative_guardian,
                    "check",
                    None,
                )

                if callable(check):

                    guardian_result = safe_call(
                        check,
                        cpu,
                        mem_percent,
                        default=None,
                        label="ConstraintGuardian.check",
                    )

            # --------------------------------------------------
            # BUILD ADAPTIVE CONTEXT
            # --------------------------------------------------

            adaptive_context = {
                "health": health_sample,
                "guardian": guardian_result,
                "qbit": authoritative_qbit,
                "source": "adaptive_loop",
                "timestamp": time.time(),
                "authority": "QbitDialer",
            }

            # --------------------------------------------------
            # INTENT ENGINE
            # --------------------------------------------------
            #
            # IntentEngine interprets the current system state.
            # It does not execute commands.
            #

            intent_result = None

            if authoritative_intent_engine is not None:

                for method_name in (
                    "process",
                    "evaluate",
                    "infer",
                    "interpret",
                    "analyze",
                    "observe",
                    "handle",
                ):

                    method = getattr(
                        authoritative_intent_engine,
                        method_name,
                        None,
                    )

                    if not callable(method):
                        continue

                    try:

                        intent_result = method(
                            adaptive_context
                        )

                        if inspect.isawaitable(
                            intent_result
                        ):

                            try:
                                loop = asyncio.get_running_loop()
                            except RuntimeError:
                                loop = None

                            if loop is not None:
                                intent_result = (
                                    loop.create_task(
                                        intent_result
                                    )
                                )

                        break

                    except TypeError:

                        try:

                            intent_result = method(
                                **adaptive_context
                            )
                            break

                        except Exception:
                            continue

                    except Exception as exc:

                        trace_exception(exc)
                        break

            # --------------------------------------------------
            # COMPUTE BRAIN
            # --------------------------------------------------
            #
            # ComputeBrain receives the observed context and
            # intent interpretation.
            #
            # It does NOT directly execute commands.
            #

            compute_context = {
                **adaptive_context,
                "intent": intent_result,
            }

            compute_result = None

            if authoritative_compute_brain is not None:

                for method_name in (
                    "process",
                    "compute",
                    "evaluate",
                    "infer",
                    "analyze",
                    "observe",
                    "think",
                ):

                    method = getattr(
                        authoritative_compute_brain,
                        method_name,
                        None,
                    )

                    if not callable(method):
                        continue

                    try:

                        compute_result = method(
                            compute_context
                        )

                        if inspect.isawaitable(
                            compute_result
                        ):

                            try:
                                loop = asyncio.get_running_loop()
                            except RuntimeError:
                                loop = None

                            if loop is not None:
                                compute_result = (
                                    loop.create_task(
                                        compute_result
                                    )
                                )

                        break

                    except TypeError:

                        try:

                            compute_result = method(
                                **compute_context
                            )
                            break

                        except Exception:
                            continue

                    except Exception as exc:

                        trace_exception(exc)
                        break

            # --------------------------------------------------
            # TRANSFORMER BRAIN
            # --------------------------------------------------
            #
            # TransformerBrain receives the computed state and
            # transforms it into higher-level cognition/metadata.
            #

            transformer_context = {
                **compute_context,
                "compute": compute_result,
            }

            transformer_result = None

            if authoritative_transformer_brain is not None:

                for method_name in (
                    "process",
                    "transform",
                    "evaluate",
                    "infer",
                    "analyze",
                    "observe",
                    "think",
                ):

                    method = getattr(
                        authoritative_transformer_brain,
                        method_name,
                        None,
                    )

                    if not callable(method):
                        continue

                    try:

                        transformer_result = method(
                            transformer_context
                        )

                        if inspect.isawaitable(
                            transformer_result
                        ):

                            try:
                                loop = asyncio.get_running_loop()
                            except RuntimeError:
                                loop = None

                            if loop is not None:
                                transformer_result = (
                                    loop.create_task(
                                        transformer_result
                                    )
                                )

                        break

                    except TypeError:

                        try:

                            transformer_result = method(
                                **transformer_context
                            )
                            break

                        except Exception:
                            continue

                    except Exception as exc:

                        trace_exception(exc)
                        break

            # --------------------------------------------------
            # ANALYTICS ENGINE
            # --------------------------------------------------
            #
            # Analytics records the adaptive/cognitive cycle.
            # It does not become command authority.
            #

            analytics_context = {
                **transformer_context,
                "transformer": transformer_result,
                "analytics_timestamp": time.time(),
            }

            if authoritative_analytics_engine is not None:

                for method_name in (
                    "record",
                    "record_event",
                    "record_sample",
                    "ingest",
                    "observe",
                    "process",
                    "analyze",
                    "track",
                ):

                    method = getattr(
                        authoritative_analytics_engine,
                        method_name,
                        None,
                    )

                    if not callable(method):
                        continue

                    try:

                        analytics_result = method(
                            analytics_context
                        )

                        if inspect.isawaitable(
                            analytics_result
                        ):

                            try:
                                loop = asyncio.get_running_loop()
                            except RuntimeError:
                                loop = None

                            if loop is not None:
                                loop.create_task(
                                    analytics_result
                                )

                        break

                    except TypeError:

                        try:

                            analytics_result = method(
                                **analytics_context
                            )

                            if inspect.isawaitable(
                                analytics_result
                            ):

                                try:
                                    loop = asyncio.get_running_loop()
                                except RuntimeError:
                                    loop = None

                                if loop is not None:
                                    loop.create_task(
                                        analytics_result
                                    )

                            break

                        except Exception:
                            continue

                    except Exception as exc:

                        trace_exception(exc)
                        break

            # --------------------------------------------------
            # EVENTBUS TELEMETRY
            # --------------------------------------------------
            #
            # Telemetry exposes the adaptive cycle.
            # EventBus does NOT execute the result.
            #

            if authoritative_event_bus is not None:

                emit = getattr(
                    authoritative_event_bus,
                    "emit",
                    None,
                )

                if callable(emit):

                    telemetry = {
                        "cpu": cpu,
                        "mem": mem_percent,
                        "disk": disk_percent,
                        "guardian": guardian_result,
                        "intent": intent_result,
                        "compute": compute_result,
                        "transformer": transformer_result,
                        "timestamp": time.time(),
                        "source": "adaptive_loop",
                        "authority": "QbitDialer",
                    }

                    try:

                        result = emit(
                            "QBIT_ADAPTIVE_SAMPLE",
                            telemetry,
                        )

                        if inspect.isawaitable(result):

                            try:
                                loop = asyncio.get_running_loop()
                            except RuntimeError:
                                loop = None

                            if loop is not None:
                                loop.create_task(
                                    result
                                )

                    except Exception as exc:

                        trace_exception(exc)

            # --------------------------------------------------
            # COMMAND AUTHORITY BOUNDARY
            # --------------------------------------------------
            #
            # Results may be interpreted by QbitDialer, but this
            # adaptive loop never calls an actuator directly.
            #
            # No:
            #     execute()
            #     actuator command
            #     subprocess command
            #     second command authority
            #
            # Any actionable result must enter the existing
            # QbitDialer command admission path.
            # --------------------------------------------------

            if (
                authoritative_qbit_dialer is not None
                and transformer_result is not None
            ):

                # Preserve the result as cognition/telemetry
                # unless the existing Dialer exposes an explicit
                # proposal/admission interface.
                #
                # Never invent a command API.

                proposal_method = getattr(
                    authoritative_qbit_dialer,
                    "submit_proposal",
                    None,
                )

                if callable(proposal_method):

                    proposal = {
                        "source": "adaptive_loop",
                        "intent": intent_result,
                        "compute": compute_result,
                        "transformer": transformer_result,
                        "health": health_sample,
                        "timestamp": time.time(),
                    }

                    try:

                        proposal_result = proposal_method(
                            proposal
                        )

                        if inspect.isawaitable(
                            proposal_result
                        ):

                            try:
                                loop = asyncio.get_running_loop()
                            except RuntimeError:
                                loop = None

                            if loop is not None:
                                loop.create_task(
                                    proposal_result
                                )

                    except Exception as exc:

                        trace_exception(exc)

        except Exception as exc:

            trace_exception(exc)

        # ------------------------------------------------------
        # ADAPTIVE SAMPLE INTERVAL
        # ------------------------------------------------------

        try:

            shutdown_event.wait(
                0.5
            )

        except Exception as exc:

            trace_exception(exc)

# ==========================================================
# SECTION 40 â€” AUTOSTART
# VERSION: 2.0.0
# BUILD: SINGLE-RUN / QBIT-AWARE
#
# PURPOSE:
# - Register SEED for OS startup
# - Execute registration only once per process
# - Safe to call after QbitDialer startup
# - Prevent duplicate registration work
# - Windows: HKCU Run
# - Linux: cron @reboot
# - macOS: LaunchAgent
# - Never crash SEED boot because autostart fails
# ==========================================================

_AUTOSTART_REGISTERED = False
_AUTOSTART_LOCK = threading.RLock()


def register_autostart():

    global _AUTOSTART_REGISTERED

    # ----------------------------------------------------------
    # Prevent multiple executions during the same SEED process
    # ----------------------------------------------------------

    with _AUTOSTART_LOCK:

        if _AUTOSTART_REGISTERED:

            logger.debug(
                "[AUTOSTART] "
                "Already processed this boot cycle"
            )

            return True

        _AUTOSTART_REGISTERED = True

    try:

        # ------------------------------------------------------
        # Resolve executable and SEED entry path
        # ------------------------------------------------------

        seed_path = os.path.abspath(
            __file__
        )

        python_path = os.path.abspath(
            sys.executable
        )

        system = (
            platform.system()
            .lower()
        )

        # ------------------------------------------------------
        # Windows
        # ------------------------------------------------------

        if system == "windows":

            import winreg

            run_key_path = (
                r"Software\Microsoft\Windows"
                r"\CurrentVersion\Run"
            )

            command = (
                f'"{python_path}" '
                f'"{seed_path}" --ui'
            )

            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                run_key_path,
                0,
                winreg.KEY_READ
                | winreg.KEY_SET_VALUE,
            ) as key:

                try:

                    existing_value, value_type = (
                        winreg.QueryValueEx(
                            key,
                            "SEED_AI",
                        )
                    )

                except FileNotFoundError:

                    existing_value = None
                    value_type = None

                # --------------------------------------------------
                # Only write when the registration is missing or
                # actually changed.
                # --------------------------------------------------

                if (
                    existing_value != command
                    or value_type != winreg.REG_SZ
                ):

                    winreg.SetValueEx(
                        key,
                        "SEED_AI",
                        0,
                        winreg.REG_SZ,
                        command,
                    )

                    logger.info(
                        "[AUTOSTART] "
                        "Windows startup registration updated"
                    )

                else:

                    logger.info(
                        "[AUTOSTART] "
                        "Windows startup registration already valid"
                    )

        # ------------------------------------------------------
        # Linux
        # ------------------------------------------------------

        elif system == "linux":

            cron_file = (
                Path.home()
                / ".seed_autostart_cron"
            )

            cron_line = (
                "@reboot "
                f'"{python_path}" '
                f'"{seed_path}"'
            )

            existing = ""

            if cron_file.exists():

                try:

                    existing = (
                        cron_file.read_text(
                            encoding="utf-8"
                        )
                    )

                except Exception as read_error:

                    logger.warning(
                        "[AUTOSTART] "
                        f"Unable to read existing cron file: {read_error}"
                    )

            # --------------------------------------------------
            # Do not duplicate the @reboot entry.
            # --------------------------------------------------

            if cron_line not in existing.splitlines():

                lines = [
                    line
                    for line in existing.splitlines()
                    if line.strip()
                ]

                lines = [
                    line
                    for line in lines
                    if not line.startswith(
                        "@reboot"
                    )
                ]

                lines.append(
                    cron_line
                )

                cron_file.write_text(
                    "\n".join(lines)
                    + "\n",
                    encoding="utf-8",
                )

                logger.info(
                    "[AUTOSTART] "
                    "Linux startup registration updated"
                )

            else:

                logger.info(
                    "[AUTOSTART] "
                    "Linux startup registration already valid"
                )

        # ------------------------------------------------------
        # macOS
        # ------------------------------------------------------

        elif system == "darwin":

            plist_path = (
                Path.home()
                / "Library"
                / "LaunchAgents"
                / "com.centralconnect.seed.plist"
            )

            plist_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            # --------------------------------------------------
            # XML-safe executable/path values
            # --------------------------------------------------

            import xml.sax.saxutils as xml_utils

            safe_python_path = (
                xml_utils.escape(
                    python_path
                )
            )

            safe_seed_path = (
                xml_utils.escape(
                    seed_path
                )
            )

            plist_content = (
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                '<plist version="1.0">\n'
                '<dict>\n'
                '    <key>Label</key>\n'
                '    <string>com.centralconnect.seed</string>\n'
                '\n'
                '    <key>ProgramArguments</key>\n'
                '    <array>\n'
                f'        <string>{safe_python_path}</string>\n'
                f'        <string>{safe_seed_path}</string>\n'
                '    </array>\n'
                '\n'
                '    <key>RunAtLoad</key>\n'
                '    <true/>\n'
                '\n'
                '    <key>KeepAlive</key>\n'
                '    <true/>\n'
                '</dict>\n'
                '</plist>\n'
            )

            existing = None

            if plist_path.exists():

                try:

                    existing = (
                        plist_path.read_text(
                            encoding="utf-8"
                        )
                    )

                except Exception:
                    existing = None

            if existing != plist_content:

                plist_path.write_text(
                    plist_content,
                    encoding="utf-8",
                )

                logger.info(
                    "[AUTOSTART] "
                    "macOS LaunchAgent updated"
                )

            else:

                logger.info(
                    "[AUTOSTART] "
                    "macOS LaunchAgent already valid"
                )

        # ------------------------------------------------------
        # Unknown platform
        # ------------------------------------------------------

        else:

            logger.warning(
                "[AUTOSTART] "
                f"Unsupported platform: {system}"
            )

            return False

        # ------------------------------------------------------
        # Success
        # ------------------------------------------------------

        logger.info(
            "[AUTOSTART] "
            "Registration complete"
        )

        return True

    # ----------------------------------------------------------
    # Autostart must NEVER kill the SEED boot cycle
    # ----------------------------------------------------------

    except Exception as exc:

        logger.warning(
            "[AUTOSTART] "
            f"Registration failed safely: {exc}"
        )

        try:

            trace_exception(
                exc
            )

        except Exception:
            pass

        return False


# ==========================================================
# SECTION 40A â€” AUTOSTART BOOT HOOK
#
# Call this ONCE immediately after QbitDialer reports ONLINE.
#
# Example:
#
#     boot_qbit_dialer()
#     register_autostart_once()
#
# ==========================================================

def register_autostart_once():

    global _AUTOSTART_REGISTERED

    with _AUTOSTART_LOCK:

        if _AUTOSTART_REGISTERED:

            logger.debug(
                "[AUTOSTART] "
                "Startup registration already executed"
            )

            return True

    return register_autostart()


# ==========================================================
# END SECTION 40
# ==========================================================

# ==========================================================
# SECTION 41 â€” SHUTDOWN
# ==========================================================

async def async_shutdown():
    global async_shutdown_event

    boot_log(
        "Shutdown sequence initiated"
    )

    if async_shutdown_event is not None:
        async_shutdown_event.set()

    shutdown_event.set()

    components = [
        ("DEVHUD", hud),
        ("HeartbeatEmitter", heartbeat),
        ("QbitDialer", qbit_dialer),
        ("QbitQueueLoop", queue_loop),
        ("SEEDRelay", relay),
        ("SEEDCore", seedcore),
    ]

    for name, component in components:

        if component is None:
            continue

        for method_name in (
            "stop",
            "shutdown",
            "close",
        ):

            method = getattr(
                component,
                method_name,
                None,
            )

            if callable(method):

                try:

                    result = method()

                    if inspect.isawaitable(
                        result
                    ):
                        await result

                    boot_log(
                        f"{name}.{method_name} complete"
                    )

                    break

                except Exception as exc:

                    boot_warn(
                        f"{name}.{method_name} failed | "
                        f"{type(exc).__name__}: {exc}"
                    )

    boot_log(
        "Shutdown sequence complete"
    )


def shutdown_handler(
    signum=None,
    frame=None,
):
    boot_log(
        f"Shutdown signal received: {signum}"
    )

    shutdown_event.set()
    release_primary_runtime()

    if async_shutdown_event is not None:

        try:
            async_shutdown_event.set()
        except Exception:
            pass

    try:

        if root is not None:
            root.after(
                0,
                root.quit,
            )

    except Exception:
        pass


# ==========================================================
# SECTION 42 â€” TK / ASYNC BRIDGE
# ==========================================================

def start_tk_async_bridge():

    if root is None:
        return

    def pump():
        if shutdown_event.is_set():
            return

        root.after(
            50,
            pump,
        )

    root.after(
        50,
        pump,
    )


# ==========================================================
# SECTION 43 â€” POST BOOT VALIDATION
# ==========================================================
#
# POST-BOOT AUTHORITY CHECK
#
# EventBus
#    â†“
# Qbit
#    â†“
# QbitQueueLoop
#    â†“
# QbitDialer
#    â†“
# Heartbeat / TrackSystem / SEEDCore
#    â†“
# SRegistry / registry_runtime / nodes
#    â†“
# MODULE STATUS REFRESH
#
# Registry and nodes are authoritative runtime references.
# They do not create replacement modules.
#
# QbitDialer remains command authority.
# EventBus remains event authority.
# QbitQueueLoop remains transport authority.
# ==========================================================

def validate_boot():

    global MODULES_STATUS

    # ==========================================================
    # PHASE 18.9 — ORACLE AUTHORITATIVE GATE CONTEXT
    # ==========================================================
    #
    # Publish the exact live runtime into Oracle before its
    # stability gate evaluates. Oracle observes; it does not
    # construct or replace any of these authorities.
    # ==========================================================

    try:
        from Oracle import bind_runtime_context as oracle_bind_runtime

        oracle_bind_runtime(
            event_bus=event_bus,
            qbit=qbit,
            qbit_dialer=qbit_dialer,
            qbit_queue_loop=queue_loop,
            heartbeat=heartbeat,
            track_system=track_system,
            device_manager=device,
            module_registry=module_registry,
            seed_core=globals().get("seedcore"),
            registry=registry,
            registry_runtime=registry_runtime,
            node_registry=(
                globals().get("nodes")
                or globals().get("node_registry")
                or globals().get("authoritative_nodes")
            ),
        )

        MODULES_STATUS["OracleRuntimeGate"] = True

        # Main3 is the authoritative module inventory. Oracle uses
        # this report to observe live modules/nodes and update its
        # lifecycle state; it does not construct replacements.
        try:
            from Oracle import report_seed_modules
            online_modules = {
                name: bool(value)
                for name, value in MODULES_STATUS.items()
            }
            report_seed_modules(
                online_modules,
                nodes=[
                    name
                    for name, value in online_modules.items()
                    if value
                ],
                status="ONLINE",
            )
        except Exception as report_exc:
            boot_warn(
                f"Oracle module report deferred: {report_exc}"
            )

        boot_log(
            "Oracle authoritative runtime gate context ONLINE"
        )
    except Exception as exc:
        MODULES_STATUS["OracleRuntimeGate"] = False
        trace_exception(exc)

    boot_log(
        "PHASE 19 | POST boot validation"
    )

    # ==========================================================
    # AUTHORITATIVE REFERENCES
    # ==========================================================

    authoritative_event_bus = globals().get(
        "event_bus",
        None,
    )

    authoritative_qbit = globals().get(
        "qbit",
        None,
    )

    authoritative_queue_loop = globals().get(
        "queue_loop",
        None,
    )

    authoritative_qbit_dialer = globals().get(
        "qbit_dialer",
        None,
    )

    authoritative_heartbeat = globals().get(
        "heartbeat",
        None,
    )

    authoritative_track_system = globals().get(
        "track_system",
        None,
    )

    authoritative_seedcore = globals().get(
        "seedcore",
        None,
    )

    authoritative_system_registry = globals().get(
        "system_registry",
        None,
    )

    authoritative_registry_runtime = globals().get(
        "registry_runtime",
        None,
    )

    authoritative_nodes = globals().get(
        "nodes",
        None,
    )

    authoritative_neural_bridge = globals().get(
        "neural_bridge",
        None,
    )

    authoritative_fathud = None

    # ==========================================================
    # REQUIRED CORE RUNTIME
    # ==========================================================

    required = {
        "EventBus":
            authoritative_event_bus,

        "Qbit":
            authoritative_qbit,

        "QbitQueueLoop":
            authoritative_queue_loop,

        "QbitDialer":
            authoritative_qbit_dialer,

        "HeartbeatEmitter":
            authoritative_heartbeat,

        "TrackSystem":
            authoritative_track_system,

        "SEEDCore":
            authoritative_seedcore,
    }

    for name, component in required.items():

        healthy = (
            component is not None
        )

        MODULES_STATUS[name] = healthy

        if healthy:

            add_green_flag(
                f"{name} online"
            )

        else:

            boot_warn(
                f"{name} missing"
            )

    # ==========================================================
    # AUTHORITATIVE RUNTIME IDENTITY
    # ==========================================================

    if authoritative_qbit_dialer is not None:

        # ------------------------------------------------------
        # QBITDIALER â†’ AUTHORITATIVE QBIT QUEUE LOOP
        # ------------------------------------------------------

        dialer_queue_loop = None

        for attr_name in (
            "qbit_queue_loop",
            "queue_loop",
            "qbit_loop",
            "qbit_queue_loop_ref",
        ):

            candidate = getattr(
                authoritative_qbit_dialer,
                attr_name,
                None,
            )

            if candidate is not None:

                dialer_queue_loop = candidate
                break

        if (
            authoritative_queue_loop is not None
            and dialer_queue_loop is not authoritative_queue_loop
        ):

            add_red_flag(
                "QbitDialer is not bound to authoritative QbitQueueLoop",
                module="QbitDialer",
                state="DEPENDENCY_FAILURE",
                phase="POST_BOOT",
            )

            MODULES_STATUS[
                "QbitDialer"
            ] = False

        # ------------------------------------------------------
        # QBITDIALER â†’ AUTHORITATIVE QBIT
        # ------------------------------------------------------

        dialer_qbit = getattr(
            authoritative_qbit_dialer,
            "qbit",
            None,
        )

        if (
            authoritative_qbit is not None
            and dialer_qbit is not authoritative_qbit
        ):

            add_red_flag(
                "QbitDialer/Qbit identity mismatch",
                module="QbitDialer",
                state="DEPENDENCY_FAILURE",
                phase="POST_BOOT",
            )

            MODULES_STATUS[
                "QbitDialer"
            ] = False

    # ==========================================================
    # TRACK SYSTEM IDENTITY
    # ==========================================================

    if authoritative_track_system is not None:

        track_event_bus = getattr(
            authoritative_track_system,
            "event_bus",
            None,
        )

        if (
            authoritative_event_bus is not None
            and track_event_bus is not authoritative_event_bus
        ):

            add_red_flag(
                "TrackSystem/EventBus identity mismatch",
                module="TrackSystem",
                state="DEPENDENCY_FAILURE",
                phase="POST_BOOT",
            )

            MODULES_STATUS[
                "TrackSystem"
            ] = False

        track_qbit = getattr(
            authoritative_track_system,
            "qbit",
            None,
        )

        if (
            authoritative_qbit is not None
            and track_qbit is not None
            and track_qbit is not authoritative_qbit
        ):

            add_red_flag(
                "TrackSystem/Qbit identity mismatch",
                module="TrackSystem",
                state="DEPENDENCY_FAILURE",
                phase="POST_BOOT",
            )

            MODULES_STATUS[
                "TrackSystem"
            ] = False

    # ==========================================================
    # EVENTBUS AUTHORITY
    # ==========================================================

    try:

        event_authority_ok = (
            validate_event_bus_authority()
        )

    except Exception as exc:

        event_authority_ok = False

        trace_exception(exc)

    if not event_authority_ok:

        add_red_flag(
            "EventBus authority validation failed",
            module="SEEDEventBus",
            state="DEPENDENCY_FAILURE",
            phase="POST_BOOT",
        )

        MODULES_STATUS[
            "SEEDEventBus"
        ] = False

    # ==========================================================
    # REGISTRY / REGISTRY RUNTIME / NODES
    # ==========================================================
    #
    # These are status/control-plane references only.
    # They must already exist.
    # This section never creates replacements.
    # ==========================================================

    # Refresh local diagnostic aliases from the live authoritative
    # runtime before evaluating registry/node health. The earlier
    # boot snapshot may have been taken before NodeRegistry binding.
    authoritative_system_registry = globals().get(
        "registry",
        None,
    )

    if not callable_attr(
        authoritative_system_registry,
        "get_discovery_status",
    ):
        try:
            import SRegistry
            authoritative_system_registry = SRegistry
        except Exception:
            authoritative_system_registry = globals().get(
                "system_registry",
                None,
            )

    authoritative_registry_runtime = (
        _resolve_live_registry_runtime()
    ) or globals().get(
        "registry_runtime",
        None,
    )

    resolved_nodes = _bind_authoritative_runtime_nodes()
    if resolved_nodes is not None:
        authoritative_nodes = resolved_nodes

    if authoritative_system_registry is None:

        add_red_flag(
            "SRegistry unavailable",
            module="SRegistry",
            state="DEPENDENCY_FAILURE",
            phase="POST_BOOT",
        )

        MODULES_STATUS[
            "SRegistry"
        ] = False

    else:

        MODULES_STATUS[
            "SRegistry"
        ] = True

        add_green_flag(
            "SRegistry online"
        )

    if authoritative_registry_runtime is None:

        add_red_flag(
            "registry_runtime unavailable",
            module="registry_runtime",
            state="DEPENDENCY_FAILURE",
            phase="POST_BOOT",
        )

        MODULES_STATUS[
            "registry_runtime"
        ] = False

    else:

        MODULES_STATUS[
            "registry_runtime"
        ] = True

        add_green_flag(
            "registry_runtime online"
        )

    if authoritative_nodes is None:

        boot_warn(
            "Runtime nodes unavailable; module-node refresh deferred"
        )

        MODULES_STATUS[
            "nodes"
        ] = False

    else:

        MODULES_STATUS[
            "nodes"
        ] = True

        add_green_flag(
            "Runtime nodes online"
        )

    # ==========================================================
    # NEURAL BRIDGE
    # ==========================================================

    if authoritative_neural_bridge is None:

        add_red_flag(
            "NeuralBridge unavailable",
            module="NeuralBridge",
            state="DEPENDENCY_FAILURE",
            phase="POST_BOOT",
        )

        MODULES_STATUS[
            "NeuralBridge"
        ] = False

    else:

        MODULES_STATUS[
            "NeuralBridge"
        ] = True

    # ==========================================================
    # REGISTRY MODULE STATUS REFRESH
    # ==========================================================
    #
    # Push the current MODULES_STATUS into the existing
    # registry/runtime/node structures.
    #
    # We only use methods that already exist.
    # No registry API is invented here.
    # ==========================================================

    registry_status_refreshed = False

    registry_targets = (
        (
            "SRegistry",
            authoritative_system_registry,
        ),
        (
            "registry_runtime",
            authoritative_registry_runtime,
        ),
    )

    for registry_name, registry_obj in registry_targets:

        if registry_obj is None:
            continue

        # ------------------------------------------------------
        # Attach authoritative runtime references when exposed.
        # ------------------------------------------------------

        runtime_refs = {
            "event_bus":
                authoritative_event_bus,

            "qbit":
                authoritative_qbit,

            "queue_loop":
                authoritative_queue_loop,

            "qbit_queue_loop":
                authoritative_queue_loop,

            "qbit_dialer":
                authoritative_qbit_dialer,

            "heartbeat":
                authoritative_heartbeat,

            "track_system":
                authoritative_track_system,

            "seedcore":
                authoritative_seedcore,

            "nodes":
                authoritative_nodes,

        }

        for attr_name, value in runtime_refs.items():

            if value is None:
                continue

            try:

                if hasattr(
                    registry_obj,
                    attr_name,
                ):

                    setattr(
                        registry_obj,
                        attr_name,
                        value,
                    )

            except Exception:
                pass

        # ------------------------------------------------------
        # Try existing registry refresh/update APIs.
        # ------------------------------------------------------

        refreshed = False

        for method_name in (
            "refresh_status",
            "refresh_module_status",
            "update_module_status",
            "update_status",
            "sync_status",
            "refresh",
            "sync",
        ):

            method = getattr(
                registry_obj,
                method_name,
                None,
            )

            if not callable(method):
                continue

            try:

                result = method(
                    MODULES_STATUS
                )

                if inspect.isawaitable(result):

                    try:
                        running_loop = (
                            asyncio.get_running_loop()
                        )
                    except RuntimeError:
                        running_loop = None

                    if running_loop is not None:
                        running_loop.create_task(
                            result
                        )

                refreshed = True
                registry_status_refreshed = True
                break

            except TypeError:

                try:

                    result = method(
                        status=MODULES_STATUS
                    )

                    if inspect.isawaitable(result):

                        try:
                            running_loop = (
                                asyncio.get_running_loop()
                            )
                        except RuntimeError:
                            running_loop = None

                        if running_loop is not None:
                            running_loop.create_task(
                                result
                            )

                    refreshed = True
                    registry_status_refreshed = True
                    break

                except Exception:
                    continue

            except Exception as exc:

                trace_exception(exc)
                break

        # ------------------------------------------------------
        # Preserve status locally when the registry exposes
        # a compatible status container.
        # ------------------------------------------------------

        if not refreshed:

            for attr_name in (
                "module_status",
                "modules_status",
                "status",
                "health_status",
            ):

                try:

                    existing = getattr(
                        registry_obj,
                        attr_name,
                        None,
                    )

                    if isinstance(
                        existing,
                        dict,
                    ):

                        existing.update(
                            MODULES_STATUS
                        )

                        registry_status_refreshed = True
                        break

                except Exception:
                    continue

        # SRegistry exposes discovery status rather than a module
        # status refresh API. A clean authoritative discovery scan
        # confirms the registry state without inventing a refresh API.
        if registry_name == "SRegistry" and not registry_status_refreshed:
            try:
                discovery_status = registry_obj.get_discovery_status()
                if isinstance(discovery_status, dict):
                    registry_status_refreshed = bool(
                        discovery_status.get("enabled", True)
                    ) and not bool(
                        discovery_status.get("errors")
                    )
            except Exception:
                pass

    if registry_status_refreshed:

        MODULES_STATUS[
            "RegistryStatusRefresh"
        ] = True

        add_green_flag(
            "Registry module status refreshed"
        )

    else:

        MODULES_STATUS[
            "RegistryStatusRefresh"
        ] = False

        boot_warn(
            "Registry status refresh API unavailable; "
            "current MODULES_STATUS retained"
        )

    # ==========================================================
    # NODE STATUS REFRESH
    # ==========================================================
    #
    # Nodes receive the same current module status.
    # This is observational/status synchronization only.
    # ==========================================================

    node_status_refreshed = False

    if authoritative_nodes is not None:

        if not node_status_refreshed:
            node_status_refreshed = _refresh_authoritative_node_status()

        # ------------------------------------------------------
        # Container-style nodes
        # ------------------------------------------------------

        if isinstance(
            authoritative_nodes,
            dict,
        ):

            for node_name, node in (
                authoritative_nodes.items()
            ):

                if node is None:
                    continue

                try:

                    if hasattr(
                        node,
                        "module_status",
                    ):

                        node.module_status = dict(
                            MODULES_STATUS
                        )

                        node_status_refreshed = True

                    elif hasattr(
                        node,
                        "modules_status",
                    ):

                        node.modules_status = dict(
                            MODULES_STATUS
                        )

                        node_status_refreshed = True

                    elif hasattr(
                        node,
                        "status",
                    ):

                        current_status = getattr(
                            node,
                            "status",
                            None,
                        )

                        if isinstance(
                            current_status,
                            dict,
                        ):

                            current_status.update(
                                MODULES_STATUS
                            )

                            node_status_refreshed = True

                except Exception:
                    continue

        # ------------------------------------------------------
        # Node manager/container APIs
        # ------------------------------------------------------

        for method_name in (
            "refresh_status",
            "refresh_module_status",
            "update_module_status",
            "update_status",
            "sync_status",
            "refresh",
            "sync",
        ):

            method = getattr(
                authoritative_nodes,
                method_name,
                None,
            )

            if not callable(method):
                continue

            try:

                result = method()

                if inspect.isawaitable(result):

                    try:
                        running_loop = (
                            asyncio.get_running_loop()
                        )
                    except RuntimeError:
                        running_loop = None

                    if running_loop is not None:
                        running_loop.create_task(
                            result
                        )

                node_status_refreshed = True
                break

            except TypeError:

                try:

                    result = method(
                        status=MODULES_STATUS
                    )

                    if inspect.isawaitable(result):

                        try:
                            running_loop = (
                                asyncio.get_running_loop()
                            )
                        except RuntimeError:
                            running_loop = None

                        if running_loop is not None:
                            running_loop.create_task(
                                result
                            )

                    node_status_refreshed = True
                    break

                except Exception:
                    continue

            except Exception as exc:

                trace_exception(exc)
                break

    MODULES_STATUS[
        "NodeStatusRefresh"
    ] = node_status_refreshed

    if node_status_refreshed:

        add_green_flag(
            "Runtime node status refreshed"
        )

    else:

        boot_warn(
            "Runtime node status refresh unavailable"
        )

    # ==========================================================
    # FATHUD â€” POST-BOOT SYSTEM HANDOFF
    # ==========================================================
    #
    # FATHUD observes the already-running runtime.
    # It does not start SEED systems here.
    #
    # QbitDialer remains command authority.
    # ==========================================================

    try:

        if authoritative_qbit_dialer is not None:

            authoritative_fathud = getattr(
                authoritative_qbit_dialer,
                "fathud",
                None,
            )

            if authoritative_fathud is None:

                authoritative_fathud = getattr(
                    authoritative_qbit_dialer,
                    "fat_layer",
                    None,
                )

        if authoritative_fathud is not None:

            attach_systems = getattr(
                authoritative_fathud,
                "attach_systems",
                None,
            )

            if callable(attach_systems):

                fathud_payload = {
                    "event_bus":
                        authoritative_event_bus,

                    "qbit":
                        authoritative_qbit,

                    "qbit_dialer":
                        authoritative_qbit_dialer,

                    "command_plane":
                        authoritative_qbit_dialer,

                    "seed_core":
                        authoritative_seedcore,

                    "runtime":
                        authoritative_queue_loop,

                    "queue_loop":
                        authoritative_queue_loop,

                    "qbit_queue_loop":
                        authoritative_queue_loop,

                    "track_system":
                        authoritative_track_system,

                    "system_registry":
                        authoritative_system_registry,

                    "registry_runtime":
                        authoritative_registry_runtime,

                    "nodes":
                        authoritative_nodes,
                }

                # --------------------------------------------------
                # Only pass parameters the existing FATHUD method
                # actually accepts.
                # --------------------------------------------------

                try:

                    signature = inspect.signature(
                        attach_systems
                    )

                    accepted = {}

                    for key, value in (
                        fathud_payload.items()
                    ):

                        if value is None:
                            continue

                        if key in signature.parameters:

                            accepted[
                                key
                            ] = value

                    result = attach_systems(
                        **accepted
                    )

                except (
                    TypeError,
                    ValueError,
                ):

                    # Fallback: use only the core parameters
                    # already known to be part of the handoff.
                    result = attach_systems(
                        event_bus=authoritative_event_bus,
                        qbit=authoritative_qbit,
                        qbit_dialer=authoritative_qbit_dialer,
                        command_plane=authoritative_qbit_dialer,
                        runtime=authoritative_queue_loop,
                    )

                if inspect.isawaitable(result):

                    try:
                        running_loop = (
                            asyncio.get_running_loop()
                        )
                    except RuntimeError:
                        running_loop = None

                    if running_loop is not None:
                        running_loop.create_task(
                            result
                        )

                MODULES_STATUS[
                    "FATHUD"
                ] = True

                add_green_flag(
                    "FATHUD connected to authoritative runtime"
                )

            else:

                MODULES_STATUS[
                    "FATHUD"
                ] = False

                boot_warn(
                    "FATHUD adapter has no attach_systems method"
                )

        else:

            MODULES_STATUS[
                "FATHUD"
            ] = False

            boot_warn(
                "FATHUD adapter missing from QbitDialer"
            )

    except Exception as exc:

        MODULES_STATUS[
            "FATHUD"
        ] = False

        add_red_flag(
            f"FATHUD runtime handoff failed: {exc}",
            module="FATHUD",
            state="DEPENDENCY_FAILURE",
            phase="POST_BOOT",
        )

    # ==========================================================
    # FINAL REGISTRY STATUS REFRESH
    # ==========================================================
    #
    # FATHUD and all post-boot checks have now updated
    # MODULES_STATUS. Push the final state one more time so
    # Registry/Nodes see the actual final boot result.
    # ==========================================================

    final_registry_refresh = False

    for registry_obj in (
        authoritative_system_registry,
        authoritative_registry_runtime,
    ):

        if registry_obj is None:
            continue

        for method_name in (
            "refresh_status",
            "refresh_module_status",
            "update_module_status",
            "update_status",
            "sync_status",
        ):

            method = getattr(
                registry_obj,
                method_name,
                None,
            )

            if not callable(method):
                continue

            try:

                result = method(
                    MODULES_STATUS
                )

                if inspect.isawaitable(result):

                    try:
                        running_loop = (
                            asyncio.get_running_loop()
                        )
                    except RuntimeError:
                        running_loop = None

                    if running_loop is not None:
                        running_loop.create_task(
                            result
                        )

                final_registry_refresh = True
                break

            except TypeError:

                try:

                    result = method(
                        status=MODULES_STATUS
                    )

                    if inspect.isawaitable(result):

                        try:
                            running_loop = (
                                asyncio.get_running_loop()
                            )
                        except RuntimeError:
                            running_loop = None

                        if running_loop is not None:
                            running_loop.create_task(
                                result
                            )

                    final_registry_refresh = True
                    break

                except Exception:
                    continue

            except Exception as exc:

                trace_exception(exc)
                break

    if final_registry_refresh:

        MODULES_STATUS[
            "RegistryFinalStatusRefresh"
        ] = True

    # ==========================================================
    # POST-BOOT STATUS REPORT
    # ==========================================================

    post_cycle_flags(
        MODULES_STATUS
    )

    # Final authoritative report: include every post-boot status
    # change so Oracle/SRegistry do not retain the earlier snapshot.
    try:
        from Oracle import report_seed_modules
        final_online = {
            name: bool(value)
            for name, value in MODULES_STATUS.items()
        }
        report_seed_modules(
            final_online,
            nodes=[
                name for name, value in final_online.items()
                if value
            ],
            status="ONLINE",
        )
    except Exception as report_exc:
        boot_warn(f"Final Oracle module report deferred: {report_exc}")

    # ==========================================================
    # FINAL CORE RESULT
    # ==========================================================

    return all(
        required.values()
    )




# ==========================================================
# SECTION 44 â€” SYSTEM BOOT
# ==========================================================
#
# AUTHORITATIVE SEED AI OS BOOT SEQUENCE
#
# EventBus
#     â†“
# Qbit
#     â†“
# QbitQueueLoop
#     â†“
# QbitKernelBus
#     â†“
# QbitDialer
#     â†“
# Registry / Nodes
#     â†“
# Heartbeat
#     â†“
# TrackSystem
#     â†“
# Support Systems
#     â†“
# Cognition / Brains
#     â†“
# Relay / Orchestrator
#     â†“
# Memory / Guardian / Ethics / Decoder
#     â†“
# Legacy / Analytics / Adaptive
#     â†“
# Channels / IPC
#     â†“
# SEEDCore
#     â†“
# TimeTravel / Oracle
#     â†“
# Initial Qbit Thought
#     â†“
# Processing
#     â†“
# Boot Event
#     â†“
# Optional UI
#     â†“
# POST-BOOT VALIDATION
#     â†“
# Adaptive Monitoring
#
# IMPORTANT:
# - One EventBus
# - One Qbit
# - One QbitQueueLoop
# - One QbitKernelBus
# - One QbitDialer
# - One registry
# - One runtime node set
# - One HeartbeatEmitter
# - One TrackSystem
# - One SEEDCore
#
# No section below may create competing runtime authorities.
# ==========================================================

# POST-UI VISUAL / NETWORK INTEGRATION
# ==========================================================

def boot_visual_network_subsystems():
    global seed_network, seed_network_core, network_manager
    global camera_qbit, render_engine

    runtime = {
        "event_bus": globals().get("event_bus"),
        "qbit": globals().get("qbit"),
        "qbit_dialer": globals().get("qbit_dialer"),
        "queue_loop": globals().get("queue_loop"),
        "track_system": globals().get("track_system"),
        "registry": globals().get("registry", globals().get("system_registry")),
        "oracle": globals().get("oracle"),
        "seedcore": globals().get("seedcore"),
    }

    try:
        from seed.network.network import SEEDNetwork
        seed_network = SEEDNetwork(event_bus=runtime["event_bus"], storage_root=str(SEED_ROOT))
        seed_network.start()
        MODULES_STATUS["SEEDNetwork"] = True
        boot_log("SEEDNetwork connected to EventBus")
    except Exception as exc:
        seed_network = None
        MODULES_STATUS["SEEDNetwork"] = False
        boot_warn(f"SEEDNetwork unavailable | {exc}")

    try:
        from seed.network.network_manager import NetworkManager
        network_manager = NetworkManager()
        MODULES_STATUS["NetworkManager"] = True
        boot_log("NetworkManager loaded")
    except Exception as exc:
        network_manager = None
        MODULES_STATUS["NetworkManager"] = False
        boot_warn(f"NetworkManager unavailable | {exc}")

    try:
        from seed.network.seed_network_core import SEEDNetworkCore
        seed_network_core = SEEDNetworkCore()
        MODULES_STATUS["SEEDNetworkCore"] = True
        boot_log("SEEDNetworkCore loaded")
    except Exception as exc:
        seed_network_core = None
        MODULES_STATUS["SEEDNetworkCore"] = False
        boot_warn(f"SEEDNetworkCore unavailable | {exc}")

    stable = bool(BOOT_STATE.get("healthy"))
    memory_ok = True
    try:
        import psutil
        memory_ok = psutil.virtual_memory().percent < 85.0
    except Exception:
        pass

    try:
        from seed.core.seed_camera_qbit import SEEDCameraQbit
        camera_qbit = SEEDCameraQbit(
            storage_root=str(SEED_ROOT),
            event_bus=runtime["event_bus"],
            qbit_dialer=runtime["qbit_dialer"],
        )
        camera_qbit.mark_boot_complete()
        if stable:
            camera_qbit.mark_os_stable()
        MODULES_STATUS["SEEDCameraQbit"] = True
        if stable and memory_ok:
            camera_qbit.start()
            boot_log("SEEDCameraQbit ONLINE | capture started")
        else:
            boot_log("SEEDCameraQbit ONLINE | capture deferred by stability/resource gate")
    except Exception as exc:
        camera_qbit = None
        MODULES_STATUS["SEEDCameraQbit"] = False
        boot_warn(f"SEEDCameraQbit unavailable | {exc}")

    # ==========================================================
    # VOICE / AUDIO OUTPUT — EVENTBUS → RENDER OVERLAY
    # ==========================================================
    global seed_voice_system
    try:
        from seed.core.voice_system import SEEDVoiceSystem
        seed_voice_system = SEEDVoiceSystem(event_bus=runtime["event_bus"])
        MODULES_STATUS["SEEDVoiceSystem"] = True
    except Exception as exc:
        seed_voice_system = None
        MODULES_STATUS["SEEDVoiceSystem"] = False
        boot_warn(f"SEEDVoiceSystem unavailable | {exc}")

    try:
        from seed.systemutils.Render import Render
        render_engine = Render(
            event_bus=runtime["event_bus"],
            storage_root=str(SEED_ROOT),
            camera_qbit=camera_qbit,
            control_layer=runtime["seedcore"],
            track_system=runtime["track_system"],
            registry=runtime["registry"],
            oracle=runtime["oracle"],
            qbit_dialer=runtime["qbit_dialer"],
            qbit_queue_loop=runtime["queue_loop"],
        )
        try:
            render_engine.set_render_mode("dot_matrix")
        except Exception:
            pass
        MODULES_STATUS["Render"] = True
        if stable and memory_ok:
            start_render = getattr(render_engine, "start", None)
            if callable(start_render):
                start_render()
            boot_log("Render ONLINE | presentation started")
        else:
            boot_log("Render ONLINE | presentation start deferred by stability/resource gate")
    except Exception as exc:
        render_engine = None
        MODULES_STATUS["Render"] = False
        boot_warn(f"Render unavailable | {exc}")

    seedcore = runtime.get("seedcore")
    if seedcore is not None and hasattr(seedcore, "bind_authoritative_runtime"):
        try:
            seedcore.bind_authoritative_runtime(
                seed_network=seed_network,
                camera_qbit=camera_qbit,
                render_engine=render_engine,
                compute_brain=globals().get("computebrain"),
                transformer_brain=globals().get("transformerbrain"),
                action_engine=globals().get("action_engine"),
                oracle=globals().get("ORACLE") or globals().get("oracle"),
            )
        except Exception as exc:
            boot_warn(f"SEEDCore visual/AI rebind deferred | {exc}")
    return bool(MODULES_STATUS.get("SEEDNetwork") or MODULES_STATUS.get("Render") or MODULES_STATUS.get("SEEDCameraQbit"))








# ==========================================================
# MODULE / NODE RUNTIME REFRESH
# ==========================================================
# PURPOSE:
#   Reconcile live MODULES_STATUS into the authoritative
#   ModuleRegistry. ModuleRegistry then publishes each module
#   as an SRegistry structural node and registry_runtime provider.
#
# AUTHORITY:
#   SRegistry      = structural node authority
#   ModuleRegistry = module inventory/health observer
#   Qbit           = telemetry carrier
#   QbitDialer     = command authority
#
# No worker, queue, Qbit, or registry is created here.
# ==========================================================

def refresh_module_registry():
    global module_registry

    registry_obj = globals().get("module_registry")
    if registry_obj is None:
        MODULES_STATUS["ModuleRegistry"] = False
        return {
            "ok": False,
            "reason": "ModuleRegistry unavailable",
            "registered": 0,
            "refreshed": 0,
        }

    registered = 0
    refreshed = 0

    try:
        start = getattr(registry_obj, "start", None)
        if callable(start):
            start()
    except Exception as exc:
        logger.warning("[ModuleRegistry] start during refresh failed | %s", exc)

    statuses = dict(MODULES_STATUS)

    for name, online in statuses.items():
        if not online:
            continue

        try:
            existing = registry_obj.get(name)
        except Exception:
            existing = None

        try:
            if existing is None:
                result = registry_obj.register(
                    name,
                    restartable=False,
                    critical=name in {
                        "EventBus",
                        "Qbit",
                        "QbitQueueLoop",
                        "QbitDialer",
                        "HeartbeatEmitter",
                        "TrackSystem",
                        "ModuleRegistry",
                        "Oracle",
                    },
                    priority="HIGH" if name in {
                        "EventBus",
                        "Qbit",
                        "QbitQueueLoop",
                        "QbitDialer",
                        "HeartbeatEmitter",
                        "TrackSystem",
                        "ModuleRegistry",
                        "Oracle",
                    } else "MED",
                    inventory={
                        "source": "main3.MODULES_STATUS",
                        "online": True,
                        "component": name,
                        "node_role": "module",
                    },
                )
                if result is not None:
                    registered += 1
            else:
                heartbeat = getattr(registry_obj, "update_heartbeat", None)
                if callable(heartbeat):
                    heartbeat(name)
                refreshed += 1
        except Exception as exc:
            logger.warning(
                "[ModuleRegistry] refresh failed | module=%s | %s",
                name,
                exc,
            )

    try:
        sync = getattr(
            registry_obj,
            "_synchronize_registered_modules",
            None,
        )
        if callable(sync):
            sync()
    except Exception as exc:
        logger.warning("[ModuleRegistry] node synchronization failed | %s", exc)

    MODULES_STATUS["ModuleRegistry"] = True

    result = {
        "ok": True,
        "registered": registered,
        "refreshed": refreshed,
        "module_count": len(registry_obj.all()),
        "runtime": registry_obj.runtime_status(),
    }

    try:
        if event_bus is not None:
            event_bus.emit(
                "MODULE_REGISTRY_REFRESHED",
                {
                    "source": "main3",
                    "authority": "ModuleRegistry",
                    "node_authority": "SRegistry",
                    "module_count": result["module_count"],
                    "registered": registered,
                    "refreshed": refreshed,
                    "timestamp": time.time(),
                },
            )
    except Exception:
        pass

    boot_log(
        "ModuleRegistry refresh COMPLETE | "
        f"modules={result['module_count']} | "
        f"registered={registered} | refreshed={refreshed}"
    )

    return result


async def boot_system(
    storage_root=None,
    load_ui=False,
):

    global loop
    global async_shutdown_event
    global adaptive_thread
    global qbit_task
    global computebrain
    global transformerbrain
    global compute_brain
    global transformer_brain


    # ==========================================================
    # STORAGE / RUNTIME INITIALIZATION
    # ==========================================================

    if storage_root is None:

        storage_root = SEED_ROOT

    storage_root = Path(
        storage_root
    )

    storage_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    # ----------------------------------------------------------
    # ONE SHARED ASYNC SHUTDOWN EVENT
    # ----------------------------------------------------------

    existing_shutdown_event = globals().get(
        "async_shutdown_event",
        None,
    )

    if existing_shutdown_event is None:

        async_shutdown_event = asyncio.Event()

    else:

        async_shutdown_event = (
            existing_shutdown_event
        )

    # ==========================================================
    # TK CONTRACT
    # ==========================================================
    # SEEDCore is a ttk.Frame and therefore requires a Tk parent,
    # even when DEVHUD is disabled. Tk remains presentation-only:
    # headless mode creates exactly one hidden root and never shows
    # it. DEVHUD may later attach to that same root.
    # ==========================================================

    existing_root = globals().get(
        "root",
        None,
    )

    if existing_root is None:

        if threading.current_thread() is not threading.main_thread():
            raise RuntimeError(
                "boot_system Tk root creation requires the process main thread"
            )

        prepare_tk_root(show_ui=bool(load_ui))

    elif not load_ui:

        try:
            existing_root.withdraw()
        except Exception:
            pass

    ui_enabled = bool(load_ui)

    # ==========================================================
    # CURRENT ASYNC LOOP
    # ==========================================================

    loop = asyncio.get_running_loop()

    boot_log(
        "================================================"
    )

    boot_log(
        "SEED AI OS BOOT START"
    )

    boot_log(
        f"Version={VERSION} | "
        f"Build={BUILD}"
    )

    # ==========================================================
    # SEED IDENTITY / STORAGE
    # ==========================================================

    ensure_seed_identity(
        storage_root
    )

    # ==========================================================
    # PHASE 1 â€” EVENT AUTHORITY
    # ==========================================================

    boot_event_bus()

    if event_bus is None:

        raise RuntimeError(
            "Authoritative EventBus failed to initialize"
        )

    # ==========================================================
    # PHASE 2 â€” AUTHORITATIVE QBIT
    # ==========================================================

    boot_qbit()

    if qbit is None:

        raise RuntimeError(
            "Authoritative Qbit failed to initialize"
        )

    # ==========================================================
    # PHASE 3 â€” AUTHORITATIVE QBIT QUEUE LOOP
    # ==========================================================

    boot_queue_loop()

    if queue_loop is None:

        raise RuntimeError(
            "Authoritative QbitQueueLoop failed to initialize"
        )

    # ==========================================================
    # PHASE 4 â€” KERNEL BUS
    # ==========================================================

    boot_kernel_bus()

    # ==========================================================
    # PHASE 5 â€” QBIT DIALER
    # ==========================================================
    #
    # IMPORTANT:
    # boot_qbit_dialer() occurs ONCE.
    #
    # Do not call it again later in this boot cycle.
    # Re-entering the Dialer constructor/binding path was the
    # source of the late queue binding / WAITING behavior.
    # ==========================================================

    await boot_qbit_dialer(start_runtime=False)

    if qbit_dialer is None:

        raise RuntimeError(
            "Authoritative QbitDialer failed to initialize"
        )

    # ----------------------------------------------------------
    # Verify exact Qbit identity immediately.
    # ----------------------------------------------------------

    dialer_qbit = getattr(
        qbit_dialer,
        "qbit",
        None,
    )

    if (
        dialer_qbit is not None
        and dialer_qbit is not qbit
    ):

        raise RuntimeError(
            "QbitDialer is not bound to the authoritative Qbit"
        )

    # ----------------------------------------------------------
    # Verify exact QueueLoop identity immediately.
    # ----------------------------------------------------------

    dialer_queue_loop = None

    for attr_name in (
        "qbit_queue_loop",
        "queue_loop",
        "qbit_loop",
        "qbit_queue_loop_ref",
    ):

        candidate = getattr(
            qbit_dialer,
            attr_name,
            None,
        )

        if candidate is not None:

            dialer_queue_loop = candidate
            break

    if (
        dialer_queue_loop is not None
        and dialer_queue_loop is not queue_loop
    ):

        raise RuntimeError(
            "QbitDialer is not bound to the authoritative QbitQueueLoop"
        )

    # ==========================================================
    # PHASE 6 â€” REGISTRY
    # ==========================================================

    boot_registry_link()

    boot_registry_runtime()

    # ==========================================================
    # PHASE 7 â€” HEARTBEAT
    # ==========================================================
    #
    # Heartbeat is the signal source.
    # It does not issue commands.
    # ==========================================================

    boot_heartbeat()

    # ==========================================================
    # PHASE 8 â€” TRACK SYSTEM
    # ==========================================================

    boot_track_system()

    if track_system is None:

        raise RuntimeError(
            "TrackSystem failed to initialize"
        )

    # ==========================================================
    # PHASE 9 â€” SUPPORT MODULES
    # ==========================================================

    boot_support_modules()

    # ==========================================================
    # PHASE 10 â€” COGNITION
    # ==========================================================
    #
    # ComputeBrain / TransformerBrain must exist before the
    # first Qbit task is created.
    # ==========================================================

    boot_cognition()

    # ==========================================================
    # PHASE 10A.5 — NEURAL BRIDGE / HEARTBEAT UNIFICATION
    # ==========================================================
    #
    # HeartbeatEmitter is the signal source. NeuralBridge is the
    # cognitive representation bridge. Both bind to the exact
    # authoritative runtime objects; neither creates transport.
    # ==========================================================

    try:
        if neural_bridge is not None:
            neural_bridge.bind_runtime(
                registry=system_registry,
                registry_runtime=registry_runtime,
                qbit_queue_loop=queue_loop,
                event_bus=event_bus,
                track_system=track_system,
                compute_brain=(
                    computebrain
                    or getattr(qbit_dialer, "compute_brain", None)
                ),
                transformer_brain=(
                    transformerbrain
                    or getattr(
                        qbit_dialer,
                        "transformer_brain",
                        None,
                    )
                ),
                qbit_dialer=qbit_dialer,
                node_registry=authoritative_nodes,
                qbit=qbit,
                seed_core=globals().get("seedcore"),
            )

        if heartbeat is not None and neural_bridge is not None:
            heartbeat.neural = neural_bridge

        MODULES_STATUS["NeuralBridge"] = (
            neural_bridge is not None
            and neural_bridge.dependencies_ready()
        )

        boot_log(
            "NeuralBridge ↔ HeartbeatEmitter runtime binding COMPLETE | "
            f"ready={MODULES_STATUS['NeuralBridge']}"
        )
    except Exception as exc:
        MODULES_STATUS["NeuralBridge"] = False
        trace_exception(exc)

    # ==========================================================
    # PHASE 10B â€” ACTION ENGINE
    # ==========================================================
    #
    # ActionEngine MUST be bound before the first Qbit reaches
    # QbitDialer._process_received_qbit().
    #
    # QbitQueueLoop remains the sole transport authority.
    # QbitDialer remains the sole command authority.
    #
    # ==========================================================

    boot_action_engine()

    if action_engine is None:
        raise RuntimeError(
            "Authoritative ActionEngine failed to initialize"
        )

    # ----------------------------------------------------------
    # Late-bind the already-authoritative ActionEngine now that
    # Phase 10B has created it. Phase 5 is construction-only.
    # ----------------------------------------------------------
    late_bind_action = getattr(
        qbit_dialer,
        "_bind_late_dependencies",
        None,
    )
    if not callable(late_bind_action):
        raise RuntimeError(
            "QbitDialer cannot late-bind ActionEngine"
        )
    late_bind_action(action_engine=action_engine)

    if (
        getattr(
            qbit_dialer,
            "action_engine",
            None,
        )
        is not action_engine
    ):
        raise RuntimeError(
            "QbitDialer is not bound to "
            "the authoritative ActionEngine"
        )

    boot_log(
        "[ActionEngine] "
        "AUTHORITATIVE CORE LINK VERIFIED"
    )

    # ==========================================================
    # PHASE 11 â€” QBIT RUNTIME START TASK
    # ==========================================================
    # Runtime activation is deliberately deferred until all
    # required authoritative dependencies are online.
    # ==========================================================

    start_dialer = getattr(qbit_dialer, "start", None)
    if not callable(start_dialer):
        raise RuntimeError("QbitDialer start lifecycle is unavailable")

    dialer_start_result = start_dialer()
    if inspect.isawaitable(dialer_start_result):
        dialer_start_result = await dialer_start_result

    if dialer_start_result is False:
        raise RuntimeError("QbitDialer failed to enter RUNNING state")

    if not (
        getattr(qbit_dialer, "running", False)
        or getattr(qbit_dialer, "_running", False)
    ):
        raise RuntimeError("QbitDialer start returned without RUNNING state")

    MODULES_STATUS["QbitDialer"] = True
    boot_log("QbitDialer runtime activated after Cognition + ActionEngine")

    # ==========================================================
    # BRAIN VALIDATION
    # ==========================================================

    computebrain = globals().get(
        "computebrain",
        None,
    )

    transformerbrain = globals().get(
        "transformerbrain",
        None,
    )

    if computebrain is not None:

        boot_log(
            "ComputeBrain available"
        )

    else:

        boot_warn(
            "ComputeBrain unavailable"
        )

    if transformerbrain is not None:

        boot_log(
            "TransformerBrain available"
        )

    else:

        boot_warn(
            "TransformerBrain unavailable"
        )

    # ==========================================================
    # PHASE 11 â€” QBIT RUNTIME START TASK
    # ==========================================================
    #
    # QbitQueueLoop owns Qbit transport.
    #
    # The dedicated Qbit runtime task is awaited only if
    # boot_qbit_dialer() created one.
    #
    # No second Dialer boot occurs here.
    # ==========================================================

    qbit_start_task = globals().get(
        "qbit_start_task",
        None,
    )

    if qbit_start_task is not None:

        try:

            if inspect.isawaitable(qbit_start_task):
                await qbit_start_task
            else:
                logger.info(
                    "[QbitDialer] runtime start already active | handle=%s",
                    type(qbit_start_task).__name__,
                )

        except Exception as exc:

            trace_exception(
                exc
            )

            MODULES_STATUS[
                "QbitDialer"
            ] = False

            raise

    # ==========================================================
    # KERNEL START TASK
    # ==========================================================
    # KernelBus was also deferred with Dialer construction.
    # Start the existing authoritative dispatcher now.
    # ==========================================================

    if kernel_bus is not None and globals().get("kernel_start_task") is None:
        try:
            kernel_bind = getattr(kernel_bus, "bind_dialer", None)
            if callable(kernel_bind):
                kernel_bind(qbit_dialer)
            kernel_start_task = kernel_bus.start(qbit_dialer)
            globals()["kernel_start_task"] = kernel_start_task
            MODULES_STATUS["QbitKernelBusRuntime"] = True
        except Exception as exc:
            MODULES_STATUS["QbitKernelBusRuntime"] = False
            raise RuntimeError("QbitKernelBus runtime start failed") from exc

    kernel_start_task = globals().get(
        "kernel_start_task",
        None,
    )

    if kernel_start_task is not None:

        try:

            if inspect.isawaitable(kernel_start_task):
                await kernel_start_task
            else:
                logger.info(
                    "[QbitKernelBus] dispatcher already active | handle=%s",
                    type(kernel_start_task).__name__,
                )

        except Exception as exc:

            MODULES_STATUS[
                "QbitKernelBus"
            ] = False

            trace_exception(
                exc
            )

            raise

    # ==========================================================
    # PHASE 12 â€” RELAY
    # ==========================================================

    boot_relay()

    # ----------------------------------------------------------
    # Complete late cognition dependency binding now that Relay
    # is authoritative and available.
    # ----------------------------------------------------------
    try:
        if cognition_node is not None:
            cognition_node.attach_dependencies(
                queue_loop=queue_loop,
                memory_graph=globals().get("memory_graph"),
                qbit_dialer=qbit_dialer,
                command_relay=relay,
                relay=relay,
                growth_manager=globals().get("growth_tree"),
                tool_registry=module_registry,
            )
        if qbit_dialer is not None:
            qbit_dialer.cognition_node = cognition_node
        MODULES_STATUS["CognitionRelayBinding"] = relay is not None
    except Exception as exc:
        MODULES_STATUS["CognitionRelayBinding"] = False
        trace_exception(exc)

    # ==========================================================
    # PHASE 13 â€” ORCHESTRATOR
    # ==========================================================

    boot_orchestrator()

    # ==========================================================
    # PHASE 14 â€” SYSTEM SERVICES
    # ==========================================================

    boot_system_services()

    # ==========================================================
    # PHASE 15 â€” FULL MERGE / ANALYTICS / ADAPTIVE SERVICES
    # ==========================================================

    boot_full_merge_services()

    # ==========================================================
    # PHASE 16 â€” CHANNELS / IPC
    # ==========================================================

    boot_channels()

    # ==========================================================
    # DEVHUD — FINAL PRE-PROCESSING UI GATE
    # ==========================================================
    #
    # Channels/IPC are now authoritative. DEVHUD is attached
    # immediately after the transport/context plane is stable
    # and before SEEDCore/Oracle/module reconciliation releases
    # processing.
    # ==========================================================

    if load_ui:
        try:
            devhud_result = boot_ui(load_ui=True)

            if (
                devhud_result is None
                or not MODULES_STATUS.get("DEVHUD", False)
            ):
                boot_warn(
                    "DEVHUD UI gate returned no live UI instance"
                )
            else:
                try:
                    if root is not None:
                        root.deiconify()
                        root.update_idletasks()
                        root.update()
                except Exception:
                    pass

                boot_log(
                    "DEVHUD SHELL ONLINE | ChannelID + ChannelNodes "
                    "+ TrackSystem + Dialer/QueueLoop stabilized | "
                    "processing not yet released"
                )

        except Exception as exc:
            trace_exception(exc)
            boot_warn(
                "DEVHUD UI gate failed; "
                "processing runtime remains authoritative"
            )

    # ==========================================================
    # PHASE 17 â€” SEEDCORE
    # ==========================================================

    boot_seedcore()

    # ==========================================================
    # PHASE 18 â€” TIME TRAVEL
    # ==========================================================

    boot_time_travel()

    # ==========================================================
    # PHASE 19 â€” ORACLE
    # ==========================================================

    boot_oracle()

    # Oracle is the input/learning branch, not a second runtime.
    # Free-form DEVHUD input enters ASK_SEED through the one
    # authoritative QbitDialer command plane.
    try:
        if event_bus is not None and qbit_dialer is not None and not globals().get("_oracle_input_bridge_bound", False):
            def _on_seed_input(payload=None):
                if not isinstance(payload, dict):
                    payload = {"user_input": payload}
                user_input = payload.get("user_input") or payload.get("text") or payload.get("message") or payload.get("command")
                if not user_input:
                    return {"status": "ignored", "reason": "empty_input"}
                oracle_obj = globals().get("oracle") or globals().get("ORACLE")
                if oracle_obj is not None:
                    try:
                        oracle_obj.receive_report({
                            "event": "USER_COGNITIVE_INPUT",
                            "input": str(user_input),
                            "source": payload.get("source", "DEVHUD"),
                        })
                    except Exception:
                        pass
                envelope = {
                    "name": "ASK_SEED",
                    "command": "ASK_SEED",
                    "data": {
                        "user_input": str(user_input),
                        "text": str(user_input),
                        "source": payload.get("source", "DEVHUD"),
                        "oracle_branch": True,
                    },
                    "source": "ORACLE_INPUT_BRIDGE",
                    "qbit_id": getattr(qbit, "qbit_id", None),
                    "track_id": getattr(qbit, "track_id", None),
                    "authority": "QbitDialer",
                    "command_admission": "submit_command",
                }
                try:
                    result = qbit_dialer.submit_command(envelope)
                    event_bus.emit("ORACLE_INPUT_ADMITTED", {
                        "input": str(user_input),
                        "result": result,
                    })
                    return result
                except Exception as exc:
                    event_bus.emit("ORACLE_INPUT_REJECTED", {
                        "input": str(user_input),
                        "error": str(exc),
                    })
                    return {"status": "rejected", "error": str(exc)}

            event_bus.subscribe("SEED_INPUT", _on_seed_input)
            globals()["_oracle_input_bridge_bound"] = True
            MODULES_STATUS["OracleInputBridge"] = True
            boot_log("Oracle input bridge ONLINE | SEED_INPUT -> ASK_SEED -> QbitDialer")
    except Exception as exc:
        MODULES_STATUS["OracleInputBridge"] = False
        boot_warn(f"Oracle input bridge deferred | {type(exc).__name__}: {exc}")

    await boot_fathud_adapter()

    # ==========================================================
    # PHASE 19.5 â€” INIT EVENT / SEEDCORE UNIFICATION
    # ==========================================================
    #
    # Bind the initialization AI layer to the same live runtime
    # already owned by SEEDCore. This is reference binding only.
    # ==========================================================

    boot_init_event()

    # ==========================================================
    # PHASE 19.6 — MODULE/NODE RECONCILIATION
    # ==========================================================
    #
    # Reconcile every currently-online module into the
    # authoritative ModuleRegistry -> SRegistry node path
    # before the first thought is released.
    # ==========================================================

    try:
        module_refresh = refresh_module_registry()
        MODULES_STATUS["ModuleRegistry"] = bool(
            module_refresh.get("ok")
        )
    except Exception as exc:
        MODULES_STATUS["ModuleRegistry"] = False
        trace_exception(exc)

    # ==========================================================
    # ==========================================================
# HUD READER
    # ==========================================================
    #
    # HUDReader is observer-side only.
    # It does not create another runtime authority.
    # ==========================================================

    try:

        from seed.hud.hud_reader import HUDReader

        hud_reader = compatible_construct(
            HUDReader,
            [
                (
                    (
                        system_registry,
                        event_bus,
                    ),
                    {},
                ),
                (
                    (
                        system_registry,
                    ),
                    {},
                ),
                (
                    (),
                    {},
                ),
            ],
            "HUDReader",
        )

        MODULES_STATUS[
            "HUDReader"
        ] = (
            hud_reader is not None
        )

    except Exception as exc:

        MODULES_STATUS[
            "HUDReader"
        ] = False

        trace_exception(
            exc
        )

    # ==========================================================
    # FIRST QBIT THOUGHT
    # ==========================================================
    #
    # This occurs AFTER:
    #
    # Qbit
    # QueueLoop
    # Dialer
    # Registry
    # Heartbeat
    # TrackSystem
    # ComputeBrain
    # TransformerBrain
    # IntentEngine
    # AnalyticsEngine
    #
    # The first Qbit is a SEED thought, not a fixed final
    # command. It is allowed to cycle, evolve, reassess, and
    # develop through the existing Qbit thought pipeline.
    # ==========================================================

    qbit_task = create_initial_qbit_task()

    if qbit_task is not None:

        MODULES_STATUS[
            "QbitTask"
        ] = True

        boot_log(
            "Initial Qbit thought task created"
        )

    else:

        MODULES_STATUS[
            "QbitTask"
        ] = False

        boot_warn(
            "Initial Qbit thought task unavailable"
        )

    # ==========================================================
    # TIME TRAVEL BOOT RECORD
    # ==========================================================
    #
    # The boot command is recorded only after the major
    # dependencies and first-thought seed exist.
    # ==========================================================

    record_boot_command()

    # ==========================================================
    # PROCESSING START
    # ==========================================================
    #
    # Construction is complete.
    # Now processing may begin.
    # ==========================================================

    # ==========================================================
    # PROCESSING START
    # ==========================================================

    start_result = (
        start_processing_loops()
    )

    if inspect.isawaitable(
        start_result
    ):

        try:

            await start_result

        except Exception as exc:

            trace_exception(
                exc
            )

    # ==========================================================
    # SYSTEM BOOT EVENT
    # ==========================================================

    await async_system_boot_event()

    # ==========================================================
    # OPTIONAL UI â€” LAST
    # ==========================================================
    #
    # UI is presentation only.
    # It cannot replace or create command authority.
    # ==========================================================

    # ==========================================================
    # OPTIONAL CLI
    # ==========================================================

    boot_cli()

    # ==========================================================
    # POST-BOOT VALIDATION
    # ==========================================================
    #
    # Validate BEFORE launching adaptive monitoring.
    #
    # Section 43 refreshes:
    #
    # MODULES_STATUS
    # SRegistry
    # registry_runtime
    # nodes
    # FATHUD
    #
    # This gives the adaptive loop a validated runtime state.
    # ==========================================================

    healthy = validate_boot()

    # ----------------------------------------------------------
    # FINAL RUNTIME READINESS SIGNAL
    # ----------------------------------------------------------
    # UI readiness is separate from core readiness. The HUD may
    # attach early, but it is only READY after validated runtime,
    # Oracle input, ActionEngine, AdaptiveEngine and Dialer exist.
    runtime_ready = all((
        healthy,
        event_bus is not None,
        qbit is not None,
        queue_loop is not None,
        qbit_dialer is not None,
        intent_engine is not None,
        action_engine is not None,
        adaptive_engine is not None,
        oracle is not None or ORACLE is not None,
    ))
    MODULES_STATUS["SEED_RUNTIME_READY"] = runtime_ready
    if runtime_ready and event_bus is not None:
        try:
            event_bus.emit("SEED_RUNTIME_READY", {
                "runtime_id": RUNTIME_ID,
                "boot_session_id": BOOT_SESSION_ID,
                "device_id": DEVICE_ID,
                "healthy": healthy,
                "source": "main3",
                "ui": "attach_only",
            })
        except Exception:
            pass

        # Optional external-tool bridge. It observes pressure and creates
        # structured tool requests; it never becomes SEED authority.
        try:
            from seed.tools.desktop_commander_adapter import DesktopCommanderAdapter
            desktop_commander_adapter = DesktopCommanderAdapter(
                event_bus=event_bus,
                dialer=qbit_dialer,
            )
            globals()["desktop_commander_adapter"] = desktop_commander_adapter
            MODULES_STATUS["DesktopCommanderAdapter"] = True
        except Exception as exc:
            MODULES_STATUS["DesktopCommanderAdapter"] = False
            boot_warn(f"Desktop Commander adapter unavailable | {type(exc).__name__}: {exc}")

        # Publish a non-blocking system mirror. Database failure must never
        # prevent local SEED from operating.
        try:
            from seed.core.system_mirror import SEEDSystemMirror
            mirror = SEEDSystemMirror()
            components = []
            for key, state in MODULES_STATUS.items():
                components.append({
                    "component_key": str(key),
                    "component_type": "runtime_module",
                    "status": "online" if state else "offline",
                    "authority": "main3",
                    "metadata": {"source": "MODULES_STATUS"},
                })
            mirror.publish_async(
                runtime={
                    "runtime_id": RUNTIME_ID,
                    "boot_session_id": BOOT_SESSION_ID,
                    "device_id": DEVICE_ID,
                    "healthy": healthy,
                    "git_remote": "https://github.com/9cfrb7k8zp-art/SEEDAI.git",
                    "git_branch": "main",
                },
                model=getattr(
                    getattr(globals().get("seed_init_event"), "ai_model_oracle", None),
                    "snapshot",
                    lambda: {"status": "unknown"},
                )(),
                components=components,
                health_state="healthy" if healthy else "degraded",
            )
            MODULES_STATUS["DatabaseSystemMirror"] = True
        except Exception as exc:
            MODULES_STATUS["DatabaseSystemMirror"] = False
            boot_warn(f"Database system mirror deferred | {type(exc).__name__}: {exc}")

    # ==========================================================
    # ADAPTIVE MONITOR
    # ==========================================================
    #
    # Section 39 now connects:
    #
    # HealthMonitor
    # Guardian
    # IntentEngine
    # ComputeBrain
    # TransformerBrain
    # AnalyticsEngine
    # QbitDialer proposal/admission boundary
    #
    # It starts ONLY after post-boot validation.
    #
    # Prevent duplicate adaptive threads.
    # ==========================================================

    existing_adaptive_thread = globals().get(
        "adaptive_thread",
        None,
    )

    if (
        existing_adaptive_thread is None
        or not existing_adaptive_thread.is_alive()
    ):

        adaptive_thread = threading.Thread(
            target=adaptive_loop,
            name="SEED-AdaptiveMonitor",
            daemon=True,
        )

        adaptive_thread.start()

        MODULES_STATUS[
            "AdaptiveMonitor"
        ] = True

        boot_log(
            "Adaptive monitoring online"
        )

    else:

        MODULES_STATUS[
            "AdaptiveMonitor"
        ] = True

        boot_log(
            "Adaptive monitoring already online"
        )

    # ==========================================================
    # FINAL BOOT STATE
    # ==========================================================

    BOOT_STATE.update({

        "healthy":
            healthy,

        "timestamp":
            time.time(),

        "version":
            VERSION,

        "build":
            BUILD,

        "modules":
            dict(
                MODULES_STATUS
            ),

        "green_flags":
            green_flags_count,
    })

    # ==========================================================
    # POST-UI STABLE NETWORK / VISION / RENDER
    # ==========================================================
    # UI has already loaded. BOOT_STATE now carries the validated stability result.
    # Camera capture and Render threads remain resource-gated.
    # ==========================================================

    boot_visual_network_subsystems()

    if network_manager is not None:
        try:
            network_ok = await network_manager.connect()
            MODULES_STATUS["NetworkConnectivity"] = bool(network_ok)
            boot_log(f"Network connectivity check | connected={network_ok}")
        except Exception as exc:
            MODULES_STATUS["NetworkConnectivity"] = False
            boot_warn(f"Network connectivity check failed | {exc}")

    # ==========================================================
    # FINAL SEED OUTPUT
    # ==========================================================

    authoritative_event_bus = globals().get(
        "event_bus",
        None,
    )

    if authoritative_event_bus is not None:

        safe_call(
            getattr(
                authoritative_event_bus,
                "emit",
                None,
            ),
            "SEED_OUTPUT",
            {
                "source":
                    "SEED_AI",

                "text":
                    "System boot complete.",

                "level":
                    "info",

                "healthy":
                    healthy,

                "modules":
                    dict(
                        MODULES_STATUS
                    ),

                "timestamp":
                    time.time(),
            },
            label="SEED_OUTPUT",
        )

    # ==========================================================
    # FINAL BOOT LOG
    # ==========================================================

    boot_log(
        "================================================"
    )

    boot_log(
        "SEED AI OS BOOT COMPLETE"
    )

    boot_log(
        f"HEALTHY={healthy} | "
        f"GREEN_FLAGS={green_flags_count}"
    )

    return BOOT_STATE


# ==========================================================
# SECTION 45 â€” ASYNC MAIN
# ==========================================================

async def async_main(
    storage_root=None,
    seed_key=None,
    load_ui=False,
):

    global async_shutdown_event

    await boot_system(
        storage_root=storage_root,
        load_ui=load_ui,
    )

    runtime_task = asyncio.create_task(
        runtime_tick()
    )

    menu_task = None

    if load_ui and dev_hud is not None:

        menu_task = asyncio.create_task(
            menu_update_loop(
                dev_hud,
                track_system,
            )
        )

    try:

        while not shutdown_event.is_set():

            await asyncio.sleep(
                1.0
            )

    except asyncio.CancelledError:

        raise

    finally:

        if menu_task is not None:
            menu_task.cancel()

        runtime_task.cancel()

        await async_shutdown()


# ==========================================================
# SECTION 46 â€” ARGUMENT PARSER
# ==========================================================

def parse_arguments():

    parser = argparse.ArgumentParser(
        description=
            "SEED AI OS Main Launcher"
    )

    parser.add_argument(
        "--storage",
        type=str,
        default=str(SEED_ROOT),
    )

    parser.add_argument(
        "--seed_key",
        type=str,
        default=None,
        help=
            "Optional path to SEED private key",
    )

    parser.add_argument(
        "--ui",
        dest="ui",
        action="store_true",
        default=True,
        help=
            "Enable DEVHUD UI (default)",
    )

    parser.add_argument(
        "--no-ui",
        dest="ui",
        action="store_false",
        help=
            "Run headless without DEVHUD",
    )

    parser.add_argument(
        "--autostart",
        action="store_true",
        help=
            "Register SEED for OS startup",
    )

    parser.add_argument(
        "--trace-memory",
        action="store_true",
        help=
            "Enable tracemalloc",
    )

    parser.add_argument(
        "--cli-command",
        type=str,
        default=None,
        help=
            "Submit one command through the authoritative SEEDCLI/QbitDialer path and exit",
    )

    parser.add_argument(
        "--autonomous-demo",
        action="store_true",
        help=
            "Run bounded autonomous Qbit self-check: system check, idle read, sandbox game, then exit",
    )

    return parser.parse_args()


# ==========================================================
# SECTION 47 â€” UI ENTRY
# ==========================================================

def run_ui_after_boot():

    if root is None:
        return

    try:
        root.deiconify()
        root.lift()
        try:
            root.attributes("-topmost", True)
            root.after(500, lambda: root.attributes("-topmost", False))
        except Exception:
            pass

        start_ui_runtime_tick()
        start_tk_async_bridge()

        boot_log(
            "Entering DEVHUD Tk mainloop | "
            "main-thread ownership confirmed"
        )

        root.mainloop()

    except KeyboardInterrupt:
        shutdown_handler()

    except Exception as exc:
        trace_exception(exc)

    finally:
        shutdown_event.set()

        # The async shutdown function is only used for orderly component
        # shutdown.  It does not own Tk and therefore runs after mainloop exits.
        try:
            asyncio.run(async_shutdown())
        except Exception as exc:
            trace_exception(exc)

        try:
            root.destroy()
        except Exception:
            pass


# ==========================================================
# SECTION 48 â€” MAIN ENTRY POINT
# ==========================================================
#
# RUNTIME CONTRACT
#
# main3.py does NOT declare the entire SEED OS "booted"
# merely because the core modules are online.
#
# CORE BOOT:
#
#     EventBus
#     Qbit
#     QbitQueueLoop
#     QbitDialer
#     Heartbeat
#     TrackSystem
#     SEEDCore
#     Registry
#     registry_runtime
#
#     â†“
#
# CORE MODULES ONLINE
#
# This is only the authoritative foundation.
#
# SUBSYSTEMS remain dynamically loadable as they are built
# and registered.
#
# UI / DEVHUD are observers and remain outside the core
# authority chain.
#
# IMPORTANT:
#
#     DO NOT use asyncio.run(boot_system(...))
#
# for the authoritative runtime because asyncio.run() closes
# the event loop when boot_system() returns.
#
# The SEED runtime requires a persistent authoritative loop.
# ==========================================================


def _get_runtime_loop():

    global loop

    if loop is not None:

        try:
            if not loop.is_closed():
                return loop
        except Exception:
            pass

    try:
        loop = asyncio.get_running_loop()
        return loop

    except RuntimeError:
        pass

    try:
        # Python 3.11+: never implicitly request a current event loop.
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop

    except Exception:

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        return loop


def _run_authoritative_boot(coro):

    global loop

    runtime_loop = _get_runtime_loop()

    if runtime_loop.is_running():

        try:
            return asyncio.create_task(coro)
        except Exception:
            return None

    try:

        return runtime_loop.run_until_complete(coro)

    except KeyboardInterrupt:

        shutdown_handler()
        return None

    except Exception as exc:

        trace_exception(exc)

        boot_error(
            "Authoritative SEED runtime boot failed"
        )

        return None


def _runtime_component_online(obj):

    if obj is None:
        return False

    for attribute in (
        "online",
        "is_online",
        "ready",
        "is_ready",
        "active",
        "running",
    ):

        try:

            value = getattr(
                obj,
                attribute,
                None,
            )

            if callable(value):
                value = value()

            if value is True:
                return True

        except Exception:
            continue

    # Existing object with no explicit lifecycle property is
    # still considered present, but only after construction.
    return True


def _publish_main3_runtime_signal():

    global event_bus
    global qbit
    global qbit_queue
    global queue_loop
    global qbit_dialer
    global heartbeat
    global track_system

    payload = {
        "event": "SEED_CORE_MODULES_ONLINE",
        "source": "main3",
        "authority": "SEED_CORE",
        "state": "CORE_MODULES_ONLINE",

        "event_bus": _runtime_component_online(
            event_bus
        ),

        "qbit": _runtime_component_online(
            qbit
        ),

        "qbit_queue_loop": _runtime_component_online(
            queue_loop
        ),

        "qbit_dialer": _runtime_component_online(
            qbit_dialer
        ),

        "heartbeat": _runtime_component_online(
            heartbeat
        ),

        "track_system": _runtime_component_online(
            track_system
        ),

        "registry": registry is not None,

        "registry_runtime": (
            registry_runtime is not None
        ),

        "node_registry": (
            authoritative_nodes is not None
        ),
    }

    # ------------------------------------------------------
    # EventBus is authoritative.
    # ------------------------------------------------------

    if event_bus is not None:

        for method_name in (
            "emit",
            "publish",
        ):

            method = callable_attr(
                event_bus,
                method_name,
            )

            if method is None:
                continue

            try:

                result = method(
                    "SEED_CORE_MODULES_ONLINE",
                    payload,
                )

                if inspect.isawaitable(result):

                    runtime_loop = _get_runtime_loop()

                    if runtime_loop.is_running():
                        runtime_loop.create_task(
                            result
                        )
                    else:
                        try:
                            runtime_loop.run_until_complete(
                                result
                            )
                        except Exception:
                            pass

                boot_log(
                    "SEED core start signal published | "
                    "state=CORE_MODULES_ONLINE"
                )

                return True

            except TypeError:
                continue

            except Exception as exc:

                boot_warn(
                    "SEED core start signal failed | "
                    f"{type(exc).__name__}: {exc}"
                )

                break

    boot_warn(
        "SEED core start signal unavailable | "
        "EventBus publish API not available"
    )

    return False


def _bind_core_runtime_authorities():
    global event_bus
    global qbit
    global qbit_core
    global qbit_queue
    global queue_loop
    global qbit_dialer
    global track_system
    global track_context
    global kernel_bus

    global computebrain
    global transformerbrain
    global compute_brain
    global transformer_brain

    global neural_bridge

    global registry
    global registry_runtime

    global node_registry
    global authoritative_nodes
    global nodes

    global fathud

    # ------------------------------------------------------
    # Registry
    # ------------------------------------------------------

    if registry is None:

        try:

            import SRegistry

            registry = SRegistry

        except Exception:
            pass

    # ------------------------------------------------------
    # Registry runtime
    # ------------------------------------------------------

    if registry_runtime is None:
        boot_registry_runtime()

    # ------------------------------------------------------
    # Nodes
    # ------------------------------------------------------

    _bind_authoritative_runtime_nodes()

    # ------------------------------------------------------
    # Qbit aliases
    # ------------------------------------------------------

    if qbit_core is not None and qbit is None:
        qbit = qbit_core

    if qbit is not None and qbit_core is None:
        qbit_core = qbit

    # ------------------------------------------------------
    # Brain aliases
    #
    # Preserve BOTH naming contracts.
    # ------------------------------------------------------

    if compute_brain is None and computebrain is not None:
        compute_brain = computebrain

    if computebrain is None and compute_brain is not None:
        computebrain = compute_brain

    if transformer_brain is None and transformerbrain is not None:
        transformer_brain = transformerbrain

    if transformerbrain is None and transformer_brain is not None:
        transformerbrain = transformer_brain

    # ------------------------------------------------------
    # NeuralBridge late binding
    #
    # Do not directly assign only:
    #
    #     neural_bridge.computebrain
    #
    # The canonical NeuralBridge names are:
    #
    #     compute_brain
    #     transformer_brain
    #
    # Use bind_runtime() when available.
    # ------------------------------------------------------

    if neural_bridge is not None:

        bind_runtime = callable_attr(
            neural_bridge,
            "bind_runtime",
        )

        if bind_runtime is not None:

            runtime_kwargs = {
                "registry": registry,
                "registry_runtime": registry_runtime,
                "qbit_queue_loop": queue_loop,
                "event_bus": event_bus,
                "track_system": track_system,
                "track_context": track_context,
                "compute_brain": compute_brain,
                "transformer_brain": transformer_brain,
                "qbit_dialer": qbit_dialer,
                "node_registry": node_registry,
                "qbit": qbit,
                "kernel_bus": kernel_bus,
                "fathud": fathud,
            }

            try:

                filtered = filter_constructor_kwargs(
                    bind_runtime,
                    runtime_kwargs,
                )

            except Exception:
                filtered = runtime_kwargs

            try:

                bind_runtime(
                    **filtered
                )

            except TypeError:

                try:
                    bind_runtime(
                        **runtime_kwargs
                    )

                except Exception as exc:

                    boot_warn(
                        "NeuralBridge runtime bind deferred | "
                        f"{type(exc).__name__}: {exc}"
                    )

            except Exception as exc:

                boot_warn(
                    "NeuralBridge runtime bind failed | "
                    f"{type(exc).__name__}: {exc}"
                )

        else:

            # Compatibility fallback for older bridge revisions.
            for name, value in (
                ("registry", registry),
                ("registry_runtime", registry_runtime),
                ("qbit_queue_loop", queue_loop),
                ("event_bus", event_bus),
                ("track_system", track_system),
                ("track_context", track_context),
                ("compute_brain", compute_brain),
                ("transformer_brain", transformer_brain),
                ("qbit_dialer", qbit_dialer),
                ("node_registry", node_registry),
                ("qbit", qbit),
                ("kernel_bus", kernel_bus),
                ("fathud", fathud),
            ):

                if value is None:
                    continue

                try:
                    setattr(
                        neural_bridge,
                        name,
                        value,
                    )
                except Exception:
                    pass

    # ------------------------------------------------------
    # RELAY RUNTIME BINDING
    # ------------------------------------------------------

    try:
        from seed.core import relay as relay_runtime

        relay_bind = getattr(relay_runtime, "bind_runtime", None)
        if callable(relay_bind):
            relay_bind(
                qbit=qbit,
                qbit_dialer=qbit_dialer,
                event_handler=callable_attr(event_bus, "emit"),
                track_id_manager=track_system,
                sregistry=registry,
            )
            # Keep `relay` as the authoritative SEEDRelay instance.
            # The package-level bind_runtime API stores shared references;
            # it must not replace the live relay object in main3.
            MODULES_STATUS["RelayRuntime"] = True
            boot_log("Relay runtime bound to authoritative Qbit/Dialer/Track/SRegistry")
    except Exception as exc:
        MODULES_STATUS["RelayRuntime"] = False
        boot_warn(
            "Relay runtime binding deferred | "
            f"{type(exc).__name__}: {exc}"
        )

    # ------------------------------------------------------
    # QBIT COMPILER / ENCODER / DECODER / BRAIN BRIDGE
    #
    # One canonical Qbit enters the binary cognition boundary,
    # then continues through the existing brain and Dialer path.
    # ------------------------------------------------------
    global qbit_encoder
    global qbit_compiler

    try:
        from seed.core.qbit.qbit_encoder import create_qbit_encoder
        from seed.core.compiler.qbit_compiler import QbitCompiler

        if qbit_encoder is None:
            qbit_encoder = create_qbit_encoder(
                qbit_dialer=qbit_dialer,
                qbit_queue_loop=queue_loop,
                heartbeat_emitter=heartbeat,
                track_system=track_system,
            )

        if qbit_compiler is None:
            qbit_compiler = QbitCompiler(
                qbit_dialer=qbit_dialer,
                qbit_queue_loop=queue_loop,
                qbit_encoder=qbit_encoder,
                qbit_decoder=decoder,
                compute_brain=compute_brain,
                transformer_brain=transformer_brain,
                intent_engine=intent_engine,
                action_engine=action_engine,
                analytics_engine=globals().get("analytics_engine"),
                adaptive_engine=globals().get("adaptive_engine"),
                adaptive_priority_engine=adaptive_priority_engine,
                event_bus=event_bus,
                track_system=track_system,
                registry=registry,
                node_registry=node_registry,
            )
        else:
            qbit_compiler.bind_runtime(
                qbit_dialer=qbit_dialer,
                qbit_queue_loop=queue_loop,
                qbit_encoder=qbit_encoder,
                qbit_decoder=decoder,
                compute_brain=compute_brain,
                transformer_brain=transformer_brain,
                intent_engine=intent_engine,
                action_engine=action_engine,
                analytics_engine=globals().get("analytics_engine"),
                adaptive_engine=globals().get("adaptive_engine"),
                adaptive_priority_engine=adaptive_priority_engine,
                event_bus=event_bus,
                track_system=track_system,
                registry=registry,
                node_registry=node_registry,
            )

        if qbit_dialer is not None:
            for name, value in (
                ("qbit_encoder", qbit_encoder),
                ("qbit_compiler", qbit_compiler),
                ("encoder", qbit_encoder),
                ("decoder", decoder),
                ("compute_brain", compute_brain),
                ("transformer_brain", transformer_brain),
                ("intent_engine", intent_engine),
                ("action_engine", action_engine),
                ("analytics_engine", globals().get("analytics_engine")),
                ("adaptive_engine", globals().get("adaptive_engine")),
                ("adaptive_priority_engine", adaptive_priority_engine),
                ("track_system", track_system),
                ("registry", registry),
                ("node_registry", node_registry),
            ):
                if value is not None:
                    try:
                        setattr(qbit_dialer, name, value)
                    except Exception:
                        pass

        MODULES_STATUS["QbitEncoder"] = qbit_encoder is not None
        MODULES_STATUS["QbitCompiler"] = qbit_compiler is not None
        boot_log("Qbit compiler/encoder/brain runtime bound")

    except Exception as exc:
        MODULES_STATUS["QbitEncoder"] = False
        MODULES_STATUS["QbitCompiler"] = False
        boot_warn(
            "Qbit compiler/encoder runtime bind deferred | "
            f"{type(exc).__name__}: {exc}"
        )

    # ------------------------------------------------------
    # FATHUD
    #
    # Main3 may use attach_systems() on the updated adapter.
    # Do NOT construct another FATHUD here.
    # ------------------------------------------------------

    if fathud is not None:

        attach_systems = callable_attr(
            fathud,
            "attach_systems",
        )

        if attach_systems is not None:

            try:

                attach_systems(
                    event_bus=event_bus,
                    qbit=qbit,
                    qbit_queue_loop=queue_loop,
                    qbit_dialer=qbit_dialer,
                    track_system=track_system,
                    registry=registry,
                    registry_runtime=registry_runtime,
                    nodes=authoritative_nodes,
                    node_registry=node_registry,
                    neural_bridge=neural_bridge,
                    neural_network=globals().get("neural_network"),
                    compute_brain=compute_brain,
                    transformer_brain=transformer_brain,
                    kernel_bus=kernel_bus,
                    runtime=queue_loop,
                    hud=globals().get("hud"),
                    database=database,
                    seedcore=seedcore,
                    seed_core=core,
                )

                boot_log(
                    "FATHUD authoritative systems attached"
                )

            except TypeError as exc:

                boot_warn(
                    "FATHUD attach_systems compatibility mismatch | "
                    f"{exc}"
                )

            except Exception as exc:

                boot_warn(
                    "FATHUD system attachment failed | "
                    f"{type(exc).__name__}: {exc}"
                )

    return {
        "event_bus": event_bus,
        "qbit": qbit,
        "queue_loop": queue_loop,
        "qbit_dialer": qbit_dialer,
        "heartbeat": heartbeat,
        "track_system": track_system,
        "registry": registry,
        "registry_runtime": registry_runtime,
        "node_registry": node_registry,
        "nodes": authoritative_nodes,
        "compute_brain": compute_brain,
        "transformer_brain": transformer_brain,
        "neural_bridge": neural_bridge,
        "fathud": fathud,
    }


def _start_core_signal_chain():

    global heartbeat
    global qbit
    global queue_loop
    global qbit_dialer

    # ------------------------------------------------------
    # Queue loop must exist before signal traffic.
    # ------------------------------------------------------

    if queue_loop is None:

        boot_warn(
            "Core signal chain deferred | "
            "authoritative QbitQueueLoop unavailable"
        )

        return False

    # ------------------------------------------------------
    # Dialer must exist before command-capable Qbits are
    # admitted.
    # ------------------------------------------------------

    if qbit_dialer is None:

        boot_warn(
            "Core signal chain deferred | "
            "authoritative QbitDialer unavailable"
        )

        return False

    # ------------------------------------------------------
    # Bind exact authoritative Qbit.
    # ------------------------------------------------------

    if qbit is not None:

        bind_qbit = callable_attr(
            qbit_dialer,
            "bind_qbit",
        )

        if bind_qbit is not None:

            try:

                bind_qbit(qbit)

            except Exception as exc:

                boot_warn(
                    "QbitDialer authoritative Qbit bind failed | "
                    f"{type(exc).__name__}: {exc}"
                )

    # ------------------------------------------------------
    # Bind exact authoritative QueueLoop.
    # ------------------------------------------------------

    bind_queue = callable_attr(
        qbit_dialer,
        "bind_queue_loop",
    )

    if bind_queue is not None:

        try:

            bind_queue(queue_loop)

        except Exception as exc:

            boot_warn(
                "QbitDialer authoritative QueueLoop bind failed | "
                f"{type(exc).__name__}: {exc}"
            )

    # ------------------------------------------------------
    # Start Dialer only through its existing lifecycle API.
    # ------------------------------------------------------

    for method_name in (
        "start",
        "start_async",
        "activate",
    ):

        method = callable_attr(
            qbit_dialer,
            method_name,
        )

        if method is None:
            continue

        try:

            result = method()

            if inspect.isawaitable(result):

                runtime_loop = _get_runtime_loop()

                if runtime_loop.is_running():

                    runtime_loop.create_task(
                        result
                    )

                else:

                    runtime_loop.run_until_complete(
                        result
                    )

            boot_log(
                "QbitDialer signal chain ACTIVE | "
                f"api={method_name}"
            )

            MODULES_STATUS[
                "qbit_dialer_runtime"
            ] = True

            break

        except TypeError:
            continue

        except Exception as exc:

            boot_warn(
                "QbitDialer runtime start failed | "
                f"{type(exc).__name__}: {exc}"
            )

    # ------------------------------------------------------
    # Heartbeat remains the source of the first runtime
    # signal.
    # ------------------------------------------------------

    if heartbeat is None:

        boot_warn(
            "Heartbeat signal source unavailable | "
            "core remains online but signal chain is waiting"
        )

        MODULES_STATUS[
            "signal_chain"
        ] = False

        return False

    # ------------------------------------------------------
    # Do NOT manufacture a command here.
    #
    # Start/activate the existing Heartbeat lifecycle only.
    # ------------------------------------------------------

    for method_name in (
        "start",
        "start_async",
        "activate",
        "emit_heartbeat",
        "emit",
    ):

        method = callable_attr(
            heartbeat,
            method_name,
        )

        if method is None:
            continue

        try:

            result = method()

            if inspect.isawaitable(result):

                runtime_loop = _get_runtime_loop()

                if runtime_loop.is_running():

                    runtime_loop.create_task(
                        result
                    )

                else:

                    runtime_loop.run_until_complete(
                        result
                    )

            boot_log(
                "SEED heartbeat signal source ACTIVE | "
                f"api={method_name}"
            )

            MODULES_STATUS[
                "heartbeat_runtime"
            ] = True

            MODULES_STATUS[
                "signal_chain"
            ] = True

            return True

        except TypeError:
            continue

        except Exception as exc:

            boot_warn(
                "Heartbeat signal start failed | "
                f"{type(exc).__name__}: {exc}"
            )

    MODULES_STATUS[
        "heartbeat_runtime"
    ] = False

    MODULES_STATUS[
        "signal_chain"
    ] = False

    boot_warn(
        "Heartbeat lifecycle API unavailable | "
        "signal chain remains waiting"
    )

    return False


def _start_dynamic_subsystem_loader():

    candidates = (
        ("seed_scheduler", seed_scheduler),
        ("module_registry", module_registry),
        ("adaptive_engine", adaptive_engine),
        ("agent_manager", agent_manager),
        ("intent_engine", intent_engine),
        ("orchestrator", orchestrator),
        ("module_loader", globals().get("module_loader")),
        ("subsystem_manager", globals().get("subsystem_manager")),
        ("system_manager", globals().get("system_manager")),
    )

    started = False

    for name, obj in candidates:

        if obj is None:
            continue

        # --------------------------------------------------
        # Prefer explicit dynamic lifecycle APIs.
        # --------------------------------------------------

        for method_name in (
            "start_dynamic",
            "start_monitor",
            "start_watcher",
            "watch",
            "discover",
            "discover_modules",
            "load_available",
            "activate",
            "start",
        ):

            method = callable_attr(
                obj,
                method_name,
            )

            if method is None:
                continue

            try:

                result = method()

                if inspect.isawaitable(result):

                    runtime_loop = _get_runtime_loop()

                    if runtime_loop.is_running():

                        runtime_loop.create_task(
                            result
                        )

                    else:

                        runtime_loop.run_until_complete(
                            result
                        )

                boot_log(
                    "Dynamic subsystem lifecycle active | "
                    f"owner={name} | "
                    f"api={method_name}"
                )

                MODULES_STATUS[
                    f"{name}_lifecycle"
                ] = True

                started = True

                break

            except TypeError:
                continue

            except Exception as exc:

                boot_warn(
                    "Dynamic subsystem lifecycle deferred | "
                    f"owner={name} | "
                    f"{type(exc).__name__}: {exc}"
                )

    if not started:

        boot_log(
            "Dynamic subsystem lifecycle waiting | "
            "core remains online; future modules may register"
        )

    return started


def _core_runtime_is_ready():

    required = (
        event_bus,
        qbit,
        queue_loop,
        qbit_dialer,
        track_system,
    )

    return all(
        item is not None
        for item in required
    )


def _mark_core_online():
    core_ready = _core_runtime_is_ready()

    BOOT_STATE[
        "core_modules_online"
    ] = core_ready

    BOOT_STATE[
        "full_system_boot"
    ] = False

    BOOT_STATE[
        "subsystems_dynamic"
    ] = True

    BOOT_STATE[
        "system_idle"
    ] = not bool(
        MODULES_STATUS.get(
            "signal_chain",
            False,
        )
    )

    if core_ready:

        boot_log(
            "SEED CORE MODULES ONLINE | "
            "dynamic subsystem loading remains active"
        )

        _publish_main3_runtime_signal()

    else:

        boot_warn(
            "SEED core module readiness incomplete | "
            "runtime remains in staged boot"
        )

    return core_ready


def main():

    global loop

    args = parse_arguments()

    if args.trace_memory:
        tracemalloc.start()

    if args.autostart:
        register_autostart()

    storage_root = Path(
        args.storage
    )

    storage_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    # ----------------------------------------------------------
    # PRIMARY RUNTIME GATE
    # ----------------------------------------------------------
    # Claim before EventBus/Qbit/QueueLoop/Dialer construction.
    # This is the hard boundary that the previous "single runtime"
    # comments did not enforce.
    if not claim_primary_runtime(storage_root):
        boot_warn(
            "Secondary SEED launch refused | "
            "authoritative runtime already exists"
        )
        return

    try:

        signal.signal(
            signal.SIGINT,
            shutdown_handler,
        )

    except Exception:
        pass

    try:

        signal.signal(
            signal.SIGTERM,
            shutdown_handler,
        )

    except Exception:
        pass

    boot_log(
        "Starting authoritative SEED runtime"
    )

    # ======================================================
    # ONE AUTHORITATIVE ASYNCIO LOOP
    # ======================================================
    #
    # This loop belongs to the SEED runtime.
    #
    # DO NOT replace this with asyncio.run().
    #
    # ======================================================

    try:

        loop = _get_runtime_loop()

    except Exception as exc:

        trace_exception(exc)

        boot_error(
            "Authoritative SEED runtime loop initialization failed"
        )

        return

    # ======================================================
    # ONE TK OWNER — UI ONLY
    # ======================================================
    # Headless mode must not create or initialize Tk at all.
    # DEVHUD remains an optional observer/presentation layer.

    if args.ui:
        try:
            prepare_tk_root(
                show_ui=True
            )
        except Exception as exc:
            trace_exception(exc)
            boot_error(
                "Tk root initialization failed"
            )
            return

    # ======================================================
    # CORE BOOT
    # ======================================================
    #
    # boot_system() establishes the foundation.
    #
    # It does NOT mean every subsystem must already exist.
    #
    # ======================================================

    try:

        boot_result = _run_authoritative_boot(
            boot_system(
                storage_root=storage_root,
                load_ui=bool(args.ui),
            )
        )

    except Exception as exc:

        trace_exception(exc)

        boot_error(
            "SEED core boot invocation failed"
        )

        shutdown_handler()

        return

    # ======================================================
    # RE-BIND AUTHORITATIVE OBJECTS
    # ======================================================

    try:

        _bind_core_runtime_authorities()

    except Exception as exc:

        trace_exception(exc)

        boot_warn(
            "Core authority rebinding encountered errors"
        )

    # ======================================================
    # CORE MODULES ONLINE
    # ======================================================

    core_online = _mark_core_online()

    # ======================================================
    # OPTIONAL ONE-SHOT CLI COMMAND
    # ======================================================
    #
    # Uses the real SEEDCLI -> QbitDialer path.
    # It never invokes a command handler directly.
    if args.cli_command or args.autonomous_demo:
        try:
            from seed.core.qbit.command_qbit import CommandQbit

            async def _submit_structured_command(command_name, why):
                command_qbit = CommandQbit.build(
                    command_name,
                    who=ensure_seed_identity(SEED_ROOT),
                    what={"command": command_name, "task": "autonomous_runtime_test"},
                    where={"root": str(SEED_ROOT), "runtime": "MAIN3"},
                    why=why,
                    data={
                        "oracle": {
                            "attached": bool(ORACLE or oracle),
                            "authority": "observer",
                        },
                        "nodes": {
                            "registry_attached": registry is not None,
                            "node_registry_attached": authoritative_nodes is not None,
                        },
                    },
                    track_id=getattr(qbit, "track_id", None),
                    parent_qbit_id=getattr(qbit, "qbit_id", None),
                    generation=int(getattr(qbit, "generation", 0)) + 1,
                    source="MAIN3_AUTONOMOUS_COMMAND",
                )
                result = await CommandQbit.submit(command_qbit, qbit_dialer)
                return {
                    "command": command_name,
                    "qbit_id": command_qbit.qbit_id,
                    "track_id": getattr(command_qbit, "track_id", None),
                    "result": result,
                }

            if args.autonomous_demo:
                demo_results = []
                for command_name, why in (
                    ("FULL_SYSTEM_CHECK", "system recovery/boot validation"),
                    ("IDLE_READ", "system idle observation"),
                    ("SANDBOX_TICTACTOE", "bounded autonomous development lesson"),
                ):
                    demo_results.append(
                        loop.run_until_complete(
                            _submit_structured_command(command_name, why)
                        )
                    )
                cli_result = {"status": "AUTONOMOUS_DEMO_COMPLETE", "results": demo_results}
            else:
                command_name = args.cli_command.strip()
                if command_name.upper().startswith("QBIT:"):
                    command_name = command_name.split(":", 1)[1].strip().upper()
                    cli_result = loop.run_until_complete(
                        _submit_structured_command(
                            command_name,
                            "system start/recovery/boot command",
                        )
                    )
                else:
                    cli_result = (
                        cli.submit(args.cli_command)
                        if cli is not None
                        else {"status": "failed", "reason": "SEEDCLI unavailable"}
                    )

            print(json.dumps(cli_result, indent=2, default=str))
        except Exception as exc:
            print(json.dumps({
                "status": "failed",
                "reason": "cli_command_failed",
                "error": str(exc),
            }, indent=2, default=str))
        shutdown_handler()
        return

    # ======================================================
    # SIGNAL CHAIN
    # ======================================================
    #
    # Heartbeat starts the signal.
    #
    # No command is manufactured here.
    #
    # ======================================================

    if core_online:

        _start_core_signal_chain()

    # ======================================================
    # DYNAMIC SUBSYSTEM LIFECYCLE
    # ======================================================
    #
    # Existing subsystems start when available.
    #
    # Future subsystems remain loadable.
    #
    # ======================================================

    _start_dynamic_subsystem_loader()

    # ======================================================
    # SEED.UI PACKAGE RUNTIME BINDING
    #
    # This binds the existing runtime into seed.ui so the local
    # UI components share the same EventBus, TrackSystem, Registry,
    # Qbit, QueueLoop, Dialer, Core, Oracle and FATHUD references.
    # ======================================================

    try:
        from seed.ui import bind_runtime

        bind_runtime(
            event_bus=event_bus,
            qbit=qbit,
            qbit_queue_loop=queue_loop,
            qbit_dialer=qbit_dialer,
            track_system=track_system,
            registry=registry,
            registry_runtime=registry_runtime,
            node_registry=node_registry,
            neural_bridge=neural_bridge,
            oracle=oracle,
            seedcore=seedcore,
            fathud=fathud,
        )

        MODULES_STATUS["SEEDUIRuntime"] = True
        boot_log("SEED UI runtime bindings ONLINE")

    except Exception as exc:
        MODULES_STATUS["SEEDUIRuntime"] = False
        boot_warn(
            "SEED UI runtime binding deferred | "
            f"{type(exc).__name__}: {exc}"
        )

    # ======================================================
    # UI / DEVHUD
    # ======================================================
    #
    # UI is NOT part of core authority.
    #
    # It is attached after core authorities exist.
    #
    # DEVHUD should observe the live runtime rather than
    # becoming the thing that keeps the runtime alive.
    #
    # ======================================================

    if args.ui:

        boot_log("UI requested | attaching DEVHUD after core modules online")

        try:

            # ------------------------------------------------
            # Existing UI bootstrap.
            # ------------------------------------------------

            devhud_result = dev_hud

            if devhud_result is None or not MODULES_STATUS.get("DEVHUD", False):
                raise RuntimeError("DEVHUD pre-processing attachment did not produce a live UI instance")

            if seedcore is not None and callable_attr(seedcore, "bind_authoritative_runtime") is not None:
                seedcore.bind_authoritative_runtime(
                    hud_interface=dev_hud,
                    dev_hud=dev_hud,
                )
                MODULES_STATUS["SEEDCore_DEVHUD"] = True
                boot_log("SEEDCore bound to the existing DEVHUD observer")

            boot_log(
                "SEED UI observer attached | DEVHUD ONLINE | "
                "core remains authoritative"
            )

        except Exception as exc:

            trace_exception(exc)

            boot_warn(
                "SEED UI attachment deferred"
            )

        try:

            if fathud is not None:

                attach_systems = callable_attr(
                    fathud,
                    "attach_systems",
                )

                if attach_systems is not None:

                    attach_systems(
                        event_bus=event_bus,
                        qbit=qbit,
                        qbit_queue_loop=queue_loop,
                        qbit_dialer=qbit_dialer,
                        track_system=track_system,
                        registry=registry,
                        registry_runtime=registry_runtime,
                        nodes=authoritative_nodes,
                        node_registry=node_registry,
                        neural_bridge=neural_bridge,
                        compute_brain=compute_brain,
                        transformer_brain=transformer_brain,
                        kernel_bus=kernel_bus,
                        seedcore=seedcore,
                        seed_core=core,
                    )

                boot_log(
                    "FATHUD observer attached to live SEED runtime"
                )

        except Exception as exc:

            trace_exception(exc)

            boot_warn(
                "FATHUD observer attachment deferred"
            )

        # --------------------------------------------------
        # IMPORTANT:
        #
        # run_ui_after_boot() must be an observer loop.
        # It must not replace or recreate the authoritative
        # asyncio runtime.
        # --------------------------------------------------

        try:

            run_ui_after_boot()

        except KeyboardInterrupt:

            shutdown_handler()

        except Exception as exc:

            trace_exception(exc)

            shutdown_handler()

        return

    # ======================================================
    # HEADLESS RUNTIME
    # ======================================================
    #
    # The runtime loop must remain alive.
    #
    # Do NOT let run_until_complete() return and then allow
    # main() to exit while the Qbit/Dialer runtime is alive.
    #
    # ======================================================

    try:

        while not shutdown_event.is_set():

            runtime_loop = _get_runtime_loop()

            # ------------------------------------------------
            # Advance the authoritative runtime.
            #
            # A subsystem may register after core boot and
            # become available without requiring another
            # complete system boot.
            # ------------------------------------------------

            runtime_loop.run_until_complete(
                asyncio.sleep(
                    0.05
                )
            )

    except KeyboardInterrupt:

        shutdown_handler()

    except Exception as exc:

        trace_exception(exc)

        shutdown_handler()

    finally:

        try:

            if not shutdown_event.is_set():

                try:

                    _run_authoritative_boot(
                        async_shutdown()
                    )

                except Exception:
                    pass

        except Exception:
            pass

        try:

            if root is not None:
                root.destroy()

        except Exception:
            pass
# ==========================================================
# SECTION 49 â€” PUBLIC COMPATIBILITY FUNCTIONS
# ==========================================================

def update_tick(
    self,
    tick: int,
):

    self.tick = tick


def schedule_async_task(
    root_widget,
    coro,
):

    if root_widget is None:
        return

    def schedule():

        try:

            running_loop = (
                asyncio.get_running_loop()
            )

            running_loop.create_task(
                coro
            )

        except RuntimeError:

            try:

                new_loop = (
                    _get_runtime_loop()
                )

                new_loop.create_task(
                    coro
                )

            except Exception as exc:

                trace_exception(exc)

    root_widget.after(
        0,
        schedule,
    )


def emit(
    self,
    event,
    payload=None,
):

    if not getattr(
        self,
        "_emit_enabled",
        True,
    ):
        return None

    return emit_proxy(
        event,
        payload,
    )

# ==========================================================

# ==========================================================
# FINAL RUNTIME BINDING RECONCILIATION
# ==========================================================
def reconcile_cognitive_binding():
    """Rebind existing cognitive objects after late subsystem discovery.
    No object creation; QbitDialer/QueueLoop remain authoritative.
    """
    global compute_brain, transformer_brain
    compute_brain = (
        globals().get("compute_brain")
        or getattr(globals().get("qbit_dialer"), "compute_brain", None)
        or getattr(globals().get("qbit_dialer"), "computebrain", None)
    )
    transformer_brain = (
        globals().get("transformer_brain")
        or getattr(globals().get("qbit_dialer"), "transformer_brain", None)
        or getattr(globals().get("qbit_dialer"), "transformerbrain", None)
    )
    if compute_brain is None or not hasattr(compute_brain, "bind_systems"):
        MODULES_STATUS["ComputeBrainFullBinding"] = False
        return False
    try:
        compute_brain.bind_systems(
            event_bus=globals().get("event_bus"),
            track_system=globals().get("track_system"),
            action_engine=globals().get("action_engine"),
            intent_engine=globals().get("intent_engine"),
            analytics_engine=globals().get("analytics_engine"),
            adaptive_engine=globals().get("adaptive_engine"),
            adaptive_priority_engine=globals().get("adaptive_priority_engine"),
            transformer_brain=transformer_brain,
            registry=globals().get("registry"),
            encoder=globals().get("cognition_binary_encoder") or globals().get("qbit_encoder"),
        )
        required = (
            "action_engine", "intent_engine", "analytics_engine",
            "transformer_brain",
        )
        missing = [name for name in required if getattr(compute_brain, name, None) is None]
        MODULES_STATUS["ComputeBrainFullBinding"] = not missing
        if missing:
            logger.warning("[CognitiveBinding] incomplete | missing=%s", missing)
        else:
            logger.info("[CognitiveBinding] reconciled | compute=%s | transformer=%s",
                        type(compute_brain).__name__, type(transformer_brain).__name__)
        return not missing
    except Exception as exc:
        MODULES_STATUS["ComputeBrainFullBinding"] = False
        boot_warn(f"ComputeBrain binding reconciliation failed: {exc}")
        return False

# SECTION 50 â€” BOOT DIAGNOSTICS
# ==========================================================

def print_boot_diagnostics():

    # Reconcile late-bound cognitive providers before reporting status.
    reconcile_cognitive_binding()

    print()
    print("=" * 72)
    print(" SEED AI OS â€” BOOT DIAGNOSTICS")
    print("=" * 72)

    print(
        f"Version        : {VERSION}"
    )

    print(
        f"Build          : {BUILD}"
    )

    print(
        f"Root           : {SEED_ROOT}"
    )

    print()

    for name, status in (
        MODULES_STATUS.items()
    ):

        print(
            f"{name:<32} "
            f"{'ONLINE' if status else 'FAILED'}"
        )

    print()

    print(
        f"Green Flags    : "
        f"{green_flags_count}"
    )

    # Report the authoritative QbitDialer command plane.
    # qbit_command_count tracks emitted callback commands and can
    # legitimately remain zero during an idle-only boot.
    diagnostic_command_count = qbit_command_count

    if qbit_dialer is not None:
        try:
            diagnostic_command_count = int(
                qbit_dialer.command_count
            )
        except Exception:
            diagnostic_command_count = qbit_command_count

    print(
        f"Qbit Commands  : "
        f"{diagnostic_command_count}"
    )

    print(
        f"EventBus       : "
        f"{type(event_bus).__name__ if event_bus else None}"
    )

    print(
        f"QbitDialer     : "
        f"{type(qbit_dialer).__name__ if qbit_dialer else None}"
    )

    print(
        f"Heartbeat      : "
        f"{type(heartbeat).__name__ if heartbeat else None}"
    )

    print(
        f"SEEDCore       : "
        f"{type(seedcore).__name__ if seedcore else None}"
    )

    print("=" * 72)


# ==========================================================
# SECTION 51 â€” MODULE EXECUTION
# ==========================================================

if __name__ == "__main__":

    print()
    print("=" * 72)
    print(" SEED AI OS â€” MAIN")
    print("=" * 72)
    print(
        f" Version : {VERSION}"
    )
    print(
        f" Build   : {BUILD}"
    )
    print(
        f" Root    : {SEED_ROOT}"
    )
    print("=" * 72)
    print()

    try:

        main()

    except KeyboardInterrupt:

        print(
            "\n[BOOT] KeyboardInterrupt"
        )
			
    except Exception as exc:

        print(
            "\n[BOOT FATAL] "
            f"{type(exc).__name__}: {exc}"
        )

        traceback.print_exc()

    finally:

        try:
            print_boot_diagnostics()
        except Exception:
            pass

        print(
            "\n[BOOT] SEED main.py terminated."
        )