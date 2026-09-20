
# =====================================================================
# FILE: __init__.py
# PATH: C:\SEED_ROOT\seed\core\fabric\__init__.py
#
# SEED CORE FABRIC PACKAGE
#
# PURPOSE
# -------
# Passive package boundary for the SEED Fabric subsystem.
#
# CURRENT PACKAGE COMPONENTS
# --------------------------
# - fabric_bridge.py
# - qbit_fabric.py
#
# ARCHITECTURE
# ------------
# This package boundary:
#
# - exposes Fabric package metadata
# - discovers/records Fabric component paths
# - registers the Fabric package/node with SRegistry when available
# - identifies the Fabric runtime components
# - exposes safe component metadata
#
# This package boundary does NOT:
#
# - instantiate Fabric components
# - instantiate Qbit objects
# - create queues
# - create EventBus instances
# - create runtime loops
# - create NeuralBridge instances
# - import QbitDialer
# - start Fabric
# - execute commands
#
# Runtime construction and dependency wiring remain under the
# authoritative SEED boot/runtime path.
# =====================================================================

from __future__ import annotations

from pathlib import Path


# =====================================================================
# PACKAGE METADATA
# =====================================================================

PACKAGE_NAME = "fabric"
PACKAGE_ROLE = "fabric"
PACKAGE_VERSION = "1.0.0"

PACKAGE_ROOT = Path(__file__).resolve().parent
PACKAGE_FILE = Path(__file__).resolve()

NODE_TYPE = "package"
NODE_GROUP = "seed.core"
NODE_STATE = "REGISTERED"


# =====================================================================
# FABRIC COMPONENT PATHS
# =====================================================================

FABRIC_BRIDGE_FILE = PACKAGE_ROOT / "fabric_bridge.py"
QBIT_FABRIC_FILE = PACKAGE_ROOT / "qbit_fabric.py"


FABRIC_COMPONENTS = {
    "fabric_bridge": {
        "name": "fabric_bridge",
        "path": FABRIC_BRIDGE_FILE,
        "role": "fabric-bridge",
        "runtime_owner": "authoritative_boot",
    },
    "qbit_fabric": {
        "name": "qbit_fabric",
        "path": QBIT_FABRIC_FILE,
        "role": "qbit-fabric",
        "runtime_owner": "authoritative_boot",
    },
}


# =====================================================================
# SAFE COMPONENT DISCOVERY
# =====================================================================
#
# This only inspects filesystem/package metadata.
#
# It does NOT import the runtime modules.
#
# That keeps:
#
#     fabric/__init__.py
#         |
#         +--> fabric_bridge.py
#         |
#         +--> qbit_fabric.py
#
# as a passive package boundary until authoritative boot wiring occurs.
# =====================================================================

def discover_components() -> dict:

    components = {}

    for name, metadata in FABRIC_COMPONENTS.items():
        path = Path(metadata["path"])

        component = dict(metadata)

        component["path"] = str(path)
        component["exists"] = path.is_file()

        components[name] = component

    return components


# =====================================================================
# SREGISTRY CONNECTION
# =====================================================================
#
# Metadata registration only.
#
# SRegistry is discovered opportunistically.
#
# Fabric does not construct SRegistry.
# =====================================================================

try:
    from SRegistry import register_node
except Exception:
    register_node = None


def register_seed_node() -> bool:

    if not callable(register_node):
        return False

    components = discover_components()

    try:
        register_node(
            name=PACKAGE_NAME,
            path=PACKAGE_ROOT,
            parent=PACKAGE_ROOT.parent,
            group=NODE_GROUP,
            role=PACKAGE_ROLE,
            state=NODE_STATE,
            capabilities=[
                "python_package",
                "fabric",
                "fabric_bridge",
                "qbit_fabric",
                "component_discovery",
                "registry_metadata",
            ],
            metadata={
                "package": True,
                "node_type": NODE_TYPE,
                "package_name": PACKAGE_NAME,
                "package_role": PACKAGE_ROLE,
                "package_version": PACKAGE_VERSION,
                "package_root": str(PACKAGE_ROOT),
                "package_file": str(PACKAGE_FILE),
                "components": components,
                "runtime_owner": "authoritative_boot",
                "command_authority": "QbitDialer",
                "transport_authority": "QbitQueueLoop",
                "registry_authority": "SRegistry",
                "execution": {
                    "allowed": False,
                    "reason": (
                        "Package boundary is metadata/discovery only."
                    ),
                },
            },
        )

        return True

    except Exception:
        return False


# =====================================================================
# PACKAGE STATUS
# =====================================================================

def package_status() -> dict:

    components = discover_components()

    return {
        "name": PACKAGE_NAME,
        "role": PACKAGE_ROLE,
        "version": PACKAGE_VERSION,
        "node_type": NODE_TYPE,
        "group": NODE_GROUP,
        "state": NODE_STATE,
        "package_root": str(PACKAGE_ROOT),
        "package_file": str(PACKAGE_FILE),
        "components": components,
        "runtime_owner": "authoritative_boot",
        "command_authority": "QbitDialer",
        "transport_authority": "QbitQueueLoop",
        "registry_authority": "SRegistry",
        "runtime_started": False,
    }


# =====================================================================
# PUBLIC PACKAGE EXPORTS
# =====================================================================
#
# Keep runtime modules out of package import.
#
# SRegistry discovery can identify the package and its components
# without triggering their dependency graphs.
# =====================================================================

__all__ = (
    "PACKAGE_NAME",
    "PACKAGE_ROLE",
    "PACKAGE_VERSION",
    "PACKAGE_ROOT",
    "PACKAGE_FILE",
    "NODE_TYPE",
    "NODE_GROUP",
    "NODE_STATE",
    "FABRIC_BRIDGE_FILE",
    "QBIT_FABRIC_FILE",
    "FABRIC_COMPONENTS",
    "discover_components",
    "register_seed_node",
    "package_status",
)
