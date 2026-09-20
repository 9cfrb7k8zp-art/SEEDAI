# =====================================================================
# FILE: __init__.py
# PATH: C:\SEED_ROOT\seed\core\integration\__init__.py
#
# SEED CORE INTEGRATION PACKAGE
#
# VERSION: 4.0.0 — ORACLE REPAIR GATE / THOUGHT LOOP INTEGRATION
#
# PURPOSE
# -------
# Dynamic package boundary for SEED integration components.
#
# The package may contain:
#   - integration engines
#   - growth systems
#   - actuator bridges
#   - auto-fix systems
#   - orchestration components
#   - repair-gate components
#   - Oracle integration
#   - future integration modules
#
# =====================================================================
#
# ARCHITECTURE — LOCKED
#
# Filesystem/package discovery
#          |
#          v
#     Integration package
#          |
#          v
#       SRegistry
#          |
#          v
# authoritative runtime wiring
#
#
# ORACLE 4 — REPAIR GATE / THOUGHT LOOP
# -------------------------------------
#
# Oracle
#   |
#   | observes / diagnoses / proposes
#   v
# Complete Repair / Command Qbit
#   |
#   | system data
#   | channel data + ChannelID
#   | track data + TrackID
#   | metadata + MetadataID
#   | command OR request
#   | source / lineage / timestamps
#   v
# HeartbeatEmitter
#   |
#   v
# QbitQueueLoop
#   |
#   v
# QbitDialer.create_task()
#   |
#   v
# normal Thought Loop / cognition path
#   |
#   v
# ComputeBrain
#   |
#   v
# ThoughtPacket
#   |
#   v
# TransformerBrain
#   |
#   v
# command proposal
#   |
#   v
# QbitDialer.submit_command()
#   |
#   v
# authoritative execution
#   |
#   +----> EventBus
#   |
#   +----> TrackSystem
#   |
#   +----> telemetry
#             |
#             v
#           Oracle verification
#
#
# OWNERSHIP — LOCKED
# ------------------
#
# Oracle
#   = observer / diagnostician / repair proposer
#
# HeartbeatEmitter
#   = heartbeat transport / input path
#
# QbitQueueLoop
#   = temporal queue / thought-loop admission path
#
# Qbit
#   = data + identity + lineage transport
#
# TrackSystem
#   = track ownership / context
#
# ComputeBrain
#   = Qbit interpretation / ThoughtPacket generation
#
# TransformerBrain
#   = ThoughtPacket transformation / command proposal
#
# QbitDialer
#   = sole command authority
#
# create_task()
#   = authoritative Qbit/task construction contract
#
# submit_command()
#   = sole command admission authority
#
# SRegistry
#   = authoritative runtime registry
#
#
# ORACLE MUST NEVER BYPASS:
#   - QbitQueueLoop
#   - HeartbeatEmitter transport
#   - QbitDialer.create_task()
#   - ComputeBrain
#   - TransformerBrain
#   - QbitDialer.submit_command()
#
# Oracle NEVER directly executes a command.
#
#
# IMPORTANT
# ---------
# This __init__.py:
#
#   - dynamically discovers Python modules actually present
#   - exposes discovered modules safely
#   - registers the package with SRegistry
#   - registers Oracle's integration contract with SRegistry
#   - provides explicit runtime registration when needed
#   - defines integration metadata for the authoritative boot path
#
# This __init__.py DOES NOT:
#
#   - instantiate integration components
#   - instantiate Oracle
#   - instantiate Qbits
#   - create queues
#   - create EventBus instances
#   - create HeartbeatEmitter instances
#   - create QbitQueueLoop instances
#   - import QbitDialer
#   - call QbitDialer.create_task()
#   - call QbitDialer.submit_command()
#   - start runtime loops
#   - automatically start anything
#
# Runtime construction remains with the authoritative boot path.
# =====================================================================

from __future__ import annotations

import importlib
import logging
import pkgutil

from pathlib import Path
from typing import Any


logger = logging.getLogger(
    "SEED.core.integration"
)


# =====================================================================
# PACKAGE METADATA
# =====================================================================

PACKAGE_NAME = "integration"

PACKAGE_ROLE = "integration"

PACKAGE_VERSION = "4.0.0"

PACKAGE_ROOT = Path(
    __file__
).resolve().parent

PACKAGE_FILE = Path(
    __file__
).resolve()


# =====================================================================
# ORACLE INTEGRATION CONTRACT
#
# Metadata only.
#
# This describes the connection Oracle will use at runtime.
# It does NOT construct or import any runtime component.
# =====================================================================

ORACLE_NAME = "oracle"

ORACLE_ROLE = "repair-gate"

ORACLE_VERSION = "4.0"

ORACLE_REGISTRY_GROUP = "mentor"

ORACLE_RUNTIME_OWNER = "authoritative_boot"

ORACLE_REQUIRED_PIPELINE = [
    "HeartbeatEmitter",
    "QbitQueueLoop",
    "Qbit",
    "QbitDialer.create_task",
    "ComputeBrain",
    "ThoughtPacket",
    "TransformerBrain",
    "QbitDialer.submit_command",
]

ORACLE_QBIT_REQUIRED_DATA = [
    "system_data",
    "channel_data",
    "channel_id",
    "track_data",
    "track_id",
    "metadata",
    "metadata_id",
    "source",
    "lineage",
    "timestamp",
    "command_or_request",
]

ORACLE_FORBIDDEN_DIRECT_ACTIONS = [
    "direct_command_execution",
    "direct_submit_command",
    "direct_qbit_dialer_execution",
    "queue_bypass",
    "create_task_bypass",
    "cognition_bypass",
]


# =====================================================================
# SREGISTRY CONNECTION
#
# Metadata registration only.
# No runtime component is constructed here.
# =====================================================================

try:

    from SRegistry import register_node

except Exception as exc:

    register_node = None

    logger.debug(
        "[SEED-INTEGRATION] "
        "SRegistry unavailable during package import: %s",
        exc,
    )


# =====================================================================
# REGISTRY — INTEGRATION PACKAGE
# =====================================================================

def register_seed_node() -> None:

    if not callable(register_node):
        return

    modules = discover_modules(
        register=False
    )

    register_node(
        name=PACKAGE_NAME,
        path=PACKAGE_ROOT,
        parent=PACKAGE_ROOT.parent,
        group="seed.core",
        role=PACKAGE_ROLE,
        state="REGISTERED",
        capabilities=[
            "python_package",
            "integration",
            "dynamic_module_discovery",
            "runtime_registration",
            "oracle_integration_boundary",
        ],
        metadata={
            "package": True,
            "package_name": PACKAGE_NAME,
            "package_role": PACKAGE_ROLE,
            "package_version": PACKAGE_VERSION,
            "package_root": str(
                PACKAGE_ROOT
            ),
            "package_file": str(
                PACKAGE_FILE
            ),
            "dynamic": True,
            "runtime_owner":
                "authoritative_boot",
            "modules": modules,
            "oracle": True,
            "oracle_node": ORACLE_NAME,
            "oracle_role": ORACLE_ROLE,
            "oracle_version": ORACLE_VERSION,
        },
    )

    logger.info(
        "[SEED-INTEGRATION] "
        "SRegistry node registered | modules=%d",
        len(modules),
    )


# =====================================================================
# REGISTRY — ORACLE
#
# Oracle is explicitly linked to SRegistry here.
#
# This is a registry declaration, NOT Oracle construction.
# =====================================================================

def register_oracle_node() -> None:

    if not callable(register_node):
        return

    register_node(
        name=ORACLE_NAME,
        path=PACKAGE_ROOT.parent.parent / "Oracle",
        parent=PACKAGE_ROOT.parent.parent,
        group=ORACLE_REGISTRY_GROUP,
        role=ORACLE_ROLE,
        state="REGISTERED",
        capabilities=[
            "observation",
            "diagnostics",
            "repair_gate",
            "repair_proposal",
            "qbit_proposal",
            "thought_loop_input",
            "system_verification",
        ],
        metadata={
            "component": "Oracle",
            "version": ORACLE_VERSION,
            "role": ORACLE_ROLE,

            "runtime_owner":
                ORACLE_RUNTIME_OWNER,

            "authority":
                "proposal_only",

            "direct_execution":
                False,

            "command_authority":
                "QbitDialer",

            "command_admission":
                "QbitDialer.submit_command",

            "task_construction":
                "QbitDialer.create_task",

            "transport":
                "HeartbeatEmitter",

            "queue":
                "QbitQueueLoop",

            "cognition": [
                "ComputeBrain",
                "ThoughtPacket",
                "TransformerBrain",
            ],

            "context_owner":
                "TrackSystem",

            "registry":
                "SRegistry",

            "required_pipeline":
                list(
                    ORACLE_REQUIRED_PIPELINE
                ),

            "required_qbit_data":
                list(
                    ORACLE_QBIT_REQUIRED_DATA
                ),

            "forbidden_direct_actions":
                list(
                    ORACLE_FORBIDDEN_DIRECT_ACTIONS
                ),

            "lifecycle":
                "lifecycle_gated",

            "boot_behavior":
                "observe_only_until_SEED_stable",
        },
    )

    logger.info(
        "[SEED-INTEGRATION] "
        "Oracle registered with SRegistry | role=%s",
        ORACLE_ROLE,
    )


# =====================================================================
# RUNTIME MODULE REGISTRATION
#
# Explicit exposure only.
#
# A module may expose a class/function that the authoritative boot
# path wants to register into this package namespace.
#
# This does not instantiate the component.
# =====================================================================

def register_module(
    name: str,
    module_cls: Any,
) -> Any:

    if not name:

        raise ValueError(
            "register_module requires name"
        )

    if module_cls is None:

        raise ValueError(
            f"register_module received None for {name}"
        )

    globals()[name] = module_cls

    if name not in __all__:

        __all__.append(
            name
        )

    logger.info(
        "[SEED-INTEGRATION] "
        "Registered runtime component: %s",
        name,
    )

    return module_cls


# =====================================================================
# ORACLE RUNTIME BINDING
#
# Explicit runtime binding only.
#
# This provides a safe namespace/registry bridge for the authoritative
# boot path once the actual runtime objects already exist.
#
# It does NOT construct any of them.
# =====================================================================

_ORACLE_RUNTIME = {}


def register_oracle_runtime(
    *,
    oracle: Any = None,
    heartbeat_emitter: Any = None,
    qbit_queue_loop: Any = None,
    qbit: Any = None,
    qbit_dialer: Any = None,
    event_bus: Any = None,
    track_system: Any = None,
    compute_brain: Any = None,
    transformer_brain: Any = None,
) -> dict:

    runtime = {
        "oracle": oracle,
        "heartbeat_emitter": heartbeat_emitter,
        "qbit_queue_loop": qbit_queue_loop,
        "qbit": qbit,
        "qbit_dialer": qbit_dialer,
        "event_bus": event_bus,
        "track_system": track_system,
        "compute_brain": compute_brain,
        "transformer_brain": transformer_brain,
    }

    for name, value in runtime.items():

        if value is not None:

            _ORACLE_RUNTIME[name] = value

    logger.info(
        "[SEED-INTEGRATION] "
        "Oracle runtime references registered | "
        "objects=%d",
        len(_ORACLE_RUNTIME),
    )

    return dict(
        _ORACLE_RUNTIME
    )


def get_oracle_runtime(
    name: str | None = None,
) -> Any:


    if name is None:

        return dict(
            _ORACLE_RUNTIME
        )

    return _ORACLE_RUNTIME.get(
        name
    )


# =====================================================================
# ORACLE QBIT CONTRACT
# =====================================================================

def get_oracle_qbit_contract() -> dict:

    return {
        "source": "Oracle",
        "role": ORACLE_ROLE,
        "authority": "proposal_only",

        "transport": [
            "HeartbeatEmitter",
            "QbitQueueLoop",
        ],

        "construction": (
            "QbitDialer.create_task"
        ),

        "cognition": [
            "ComputeBrain",
            "ThoughtPacket",
            "TransformerBrain",
        ],

        "command_admission": (
            "QbitDialer.submit_command"
        ),

        "required_data": list(
            ORACLE_QBIT_REQUIRED_DATA
        ),

        "context_owner": "TrackSystem",

        "registry": "SRegistry",

        "direct_execution": False,
    }


# =====================================================================
# DYNAMIC MODULE DISCOVERY
#
# Uses actual filesystem contents instead of maintaining a manual
# module list.
#
# IMPORTANT:
# Discovery does NOT import modules by default.
#
# It reports Python modules/packages that physically exist.
# =====================================================================

def discover_modules(
    *,
    import_modules: bool = False,
    register: bool = False,
) -> list:

    discovered = []

    try:

        for module_info in pkgutil.iter_modules(
            [str(PACKAGE_ROOT)]
        ):

            module_name = module_info.name

            # ---------------------------------------------------------
            # Ignore private implementation modules.
            # ---------------------------------------------------------

            if module_name.startswith("_"):

                continue

            is_package = bool(
                module_info.ispkg
            )

            record = {
                "name":
                    module_name,

                "package":
                    is_package,

                "path":
                    str(
                        PACKAGE_ROOT
                        / (
                            module_name
                            if is_package
                            else f"{module_name}.py"
                        )
                    ),

                "state":
                    "DISCOVERED",

                "imported":
                    False,
            }

            # ---------------------------------------------------------
            # Optional runtime import.
            #
            # NEVER performed unless explicitly requested.
            # ---------------------------------------------------------

            if import_modules:

                try:

                    module = importlib.import_module(
                        f"{__name__}.{module_name}"
                    )

                    record[
                        "imported"
                    ] = True

                    if register:

                        globals()[
                            module_name
                        ] = module

                        if module_name not in __all__:

                            __all__.append(
                                module_name
                            )

                except Exception as exc:

                    record[
                        "state"
                    ] = "IMPORT_FAILED"

                    record[
                        "error"
                    ] = str(exc)

                    logger.error(
                        "[SEED-INTEGRATION] "
                        "Module import failed: %s | %s",
                        module_name,
                        exc,
                    )

            discovered.append(
                record
            )

    except Exception as exc:

        logger.error(
            "[SEED-INTEGRATION] "
            "Module discovery failed: %s",
            exc,
        )

    logger.debug(
        "[SEED-INTEGRATION] "
        "Discovered %d filesystem components",
        len(discovered),
    )

    return discovered


# =====================================================================
# COMPONENT LOOKUP
# =====================================================================

def get_module(
    name: str,
) -> Any:

    if not name:

        return None

    return globals().get(
        name
    )


# =====================================================================
# PACKAGE STATUS
# =====================================================================

def get_package_status() -> dict:

    modules = discover_modules(
        register=False
    )

    return {
        "package": PACKAGE_NAME,
        "role": PACKAGE_ROLE,
        "version": PACKAGE_VERSION,
        "root": str(
            PACKAGE_ROOT
        ),
        "dynamic": True,
        "modules": modules,

        "oracle": {
            "registered": callable(
                register_node
            ),
            "name": ORACLE_NAME,
            "role": ORACLE_ROLE,
            "version": ORACLE_VERSION,
            "contract": get_oracle_qbit_contract(),
            "runtime_objects": list(
                _ORACLE_RUNTIME.keys()
            ),
        },

        "registered_components": [
            name
            for name in __all__
            if globals().get(name) is not None
        ],
    }


# =====================================================================
# PUBLIC PACKAGE EXPORTS
#
# Actual integration classes are NOT hard-coded here.
#
# They can be exposed through register_module() by the authoritative
# runtime when their actual implementation is required.
# =====================================================================

__all__ = [

    "PACKAGE_NAME",
    "PACKAGE_ROLE",
    "PACKAGE_VERSION",
    "PACKAGE_ROOT",
    "PACKAGE_FILE",

    "ORACLE_NAME",
    "ORACLE_ROLE",
    "ORACLE_VERSION",
    "ORACLE_REQUIRED_PIPELINE",
    "ORACLE_QBIT_REQUIRED_DATA",
    "ORACLE_FORBIDDEN_DIRECT_ACTIONS",

    "register_seed_node",
    "register_oracle_node",

    "register_module",

    "register_oracle_runtime",
    "get_oracle_runtime",
    "get_oracle_qbit_contract",

    "discover_modules",
    "get_module",
    "get_package_status",
]

