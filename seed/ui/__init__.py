# =====================================================================
# FILE: __init__.py
# PATH: C:/SEED_ROOT/seed/ui/__init__.py
#
# SEED UI PACKAGE
#
# VERSION:
#   0.3.0-DYNAMIC-BROWSER
#
# PURPOSE:
#   - Full dynamic UI component discovery
#   - Headless-safe import
#   - No automatic GUI/thread/server startup on import
#   - Registry-aware UI lifecycle
#   - Browser launch available as an explicit runtime action
#   - Supports FATHUD / DEVHUD websocket browser interface
#
# =====================================================================

import logging
import importlib
import pkgutil
import webbrowser

from pathlib import Path


# =====================================================================
# 1. IDENTITY
# =====================================================================

UI_PACKAGE_NAME = "seed.ui"
UI_PACKAGE_VERSION = "0.3.0-DYNAMIC-BROWSER"

THIS_PATH = Path(__file__).resolve().parent


# =====================================================================
# 2. LOGGING
# =====================================================================

logger = logging.getLogger("SEED.ui")


# =====================================================================
# 3. REGISTRY
# =====================================================================

try:

    from SRegistry import register_node

except ImportError:

    register_node = None

    logger.warning(
        "[SEED-UI][REGISTRY] SRegistry unavailable"
    )


def _register_ui_package():

    if register_node is None:
        return

    try:

        register_node(
            name="seed.ui",
            path=THIS_PATH.parent,
            parent=THIS_PATH.parent.parent,
            group="ui",
            role="ui-package",
            update_domain="ui-runtime",
        )

        logger.info(
            "[SEED-UI][REGISTRY] seed.ui registered"
        )

    except Exception as exc:

        logger.warning(
            "[SEED-UI][REGISTRY] Registration failed: %s",
            exc,
        )


_register_ui_package()


# =====================================================================
# 4. EXPLICIT COMPONENT REFERENCES
# =====================================================================

HUDScheduler = None
HUDWaveformRenderer = None
SEEDUIMainHUD = None
SEEDUIMain3D = None
SEEDUIMainExternal = None


# =====================================================================
# 5. COMPONENT / FILE REGISTRIES
# =====================================================================

UI_COMPONENTS = {}

UI_FILES = {}


# =====================================================================
# 6. PUBLIC API
# =====================================================================

__all__ = [
    "HUDScheduler",
    "HUDWaveformRenderer",
    "SEEDUIMainHUD",
    "SEEDUIMain3D",
    "SEEDUIMainExternal",

    "register_component",
    "register_file",
    "discover_components",

    "launch_browser",
    "open_fathud",
    "open_devhud",

    "UI_COMPONENTS",
    "UI_FILES",

    "UI_PACKAGE_NAME",
    "UI_PACKAGE_VERSION",
]


# =====================================================================
# 7. COMPONENT REGISTRATION
# =====================================================================

def register_component(
    name,
    component_cls,
):

    if not name or component_cls is None:
        return False

    UI_COMPONENTS[name] = component_cls

    globals()[name] = component_cls

    if name not in __all__:
        __all__.append(name)

    logger.info(
        "[SEED-UI] Registered component: %s",
        name,
    )

    return True


# =====================================================================
# 8. FILE REGISTRATION
# =====================================================================

def register_file(
    name,
    path,
):

    if not name or path is None:
        return False

    UI_FILES[name] = str(path)

    logger.info(
        "[SEED-UI] Registered file: %s",
        name,
    )

    return True


# =====================================================================
# 9. BROWSER CONTROL
#
# IMPORTANT:
#   Importing seed.ui NEVER opens a browser.
#
#   The browser is opened only when one of these functions is
#   explicitly called by the runtime / HUD controller.
# =====================================================================

def launch_browser(
    url="http://localhost:8765",
    *,
    new_window=True,
):

    if not url:
        raise ValueError(
            "Browser URL cannot be empty"
        )

    try:

        logger.info(
            "[SEED-UI][BROWSER] Opening %s",
            url,
        )

        if new_window:

            opened = webbrowser.open_new(
                str(url)
            )

        else:

            opened = webbrowser.open(
                str(url)
            )

        if not opened:

            logger.warning(
                "[SEED-UI][BROWSER] "
                "Browser launch was not confirmed"
            )

        return bool(opened)

    except Exception as exc:

        logger.warning(
            "[SEED-UI][BROWSER FAIL] %s",
            exc,
        )

        return False


# =====================================================================
# 10. FATHUD
# =====================================================================

def open_fathud(
    host="localhost",
    port=8766,
):

    url = (
        f"http://{host}:{int(port)}"
    )

    return launch_browser(url)


# =====================================================================
# 11. DEVHUD
# =====================================================================

def open_devhud(
    host="localhost",
    port=8766,
):

    url = (
        f"http://{host}:{int(port)}"
    )

    return launch_browser(url)


# =====================================================================
# 12. DYNAMIC DISCOVERY
# =====================================================================

def discover_components(
    headless=True,
):

    ui_path = Path(__file__).resolve().parent

    logger.info(
        "[SEED-UI] Starting full component discovery..."
    )

    # -------------------------------------------------------------
    # Package modules
    # -------------------------------------------------------------

    try:

        modules = pkgutil.iter_modules(
            [str(ui_path)]
        )

    except Exception as exc:

        logger.warning(
            "[SEED-UI][DISCOVERY FAIL] %s",
            exc,
        )

        return UI_COMPONENTS

    for module_info in modules:

        module_name = module_info.name

        if module_name.startswith("_"):
            continue

        # ---------------------------------------------------------
        # GUI root modules remain lazy in headless mode.
        # ---------------------------------------------------------

        if (
            headless
            and module_name.lower().startswith("seedui")
        ):

            logger.debug(
                "[SEED-UI] "
                "Skipping GUI root module: %s",
                module_name,
            )

            continue

        try:

            full_module_name = (
                f"{__name__}.{module_name}"
            )

            module = importlib.import_module(
                full_module_name
            )

            # -----------------------------------------------------
            # Explicit module __all__
            # -----------------------------------------------------

            if hasattr(
                module,
                "__all__",
            ):

                for cls_name in module.__all__:

                    cls = getattr(
                        module,
                        cls_name,
                        None,
                    )

                    if isinstance(
                        cls,
                        type,
                    ):

                        register_component(
                            cls_name,
                            cls,
                        )

            # -----------------------------------------------------
            # Fallback class discovery
            # -----------------------------------------------------

            else:

                for attr_name in dir(module):

                    if attr_name.startswith("_"):
                        continue

                    try:

                        attr = getattr(
                            module,
                            attr_name,
                        )

                    except Exception:
                        continue

                    if (
                        isinstance(attr, type)
                        and attr.__module__
                        == module.__name__
                    ):

                        register_component(
                            attr_name,
                            attr,
                        )

            logger.info(
                "[SEED-UI] "
                "Loaded Python module: %s",
                module_name,
            )

        except Exception as exc:

            logger.warning(
                "[SEED-UI] "
                "Failed to load module %s: %s",
                module_name,
                exc,
            )

    # -------------------------------------------------------------
    # Non-Python assets
    # -------------------------------------------------------------

    try:

        for item in ui_path.iterdir():

            if item.name.startswith("_"):
                continue

            if item.suffix.lower() == ".py":
                continue

            register_file(
                item.name,
                item.resolve(),
            )

    except Exception as exc:

        logger.warning(
            "[SEED-UI][ASSET DISCOVERY FAIL] %s",
            exc,
        )

    logger.info(
        "[SEED-UI] Full discovery complete | "
        "components=%d | files=%d",
        len(UI_COMPONENTS),
        len(UI_FILES),
    )

    return UI_COMPONENTS
# =====================================================================
# 13. AUTHORITATIVE RUNTIME BINDING
#
# UI components receive existing runtime authorities only.
# =====================================================================

UI_RUNTIME = {}


def bind_runtime(**runtime):
    global UI_RUNTIME

    accepted = {
        key: value
        for key, value in runtime.items()
        if value is not None
    }

    UI_RUNTIME.update(accepted)

    fathud = accepted.get("fathud")
    if fathud is not None:
        attach = getattr(fathud, "attach_systems", None)
        if callable(attach):
            attach(**accepted)

    hud_channel = accepted.get("hud_channel")
    if hud_channel is not None and fathud is not None:
        bind_gui = getattr(hud_channel, "bind_gui", None)
        if callable(bind_gui):
            bind_gui(fathud)

    # Register the UI runtime through the existing registry API only.
    if register_node is not None:
        try:
            register_node(
                name="SEEDUIRuntime",
                path=THIS_PATH,
                parent=THIS_PATH.parent,
                group="ui",
                role="observer",
                update_domain="ui-runtime",
            )
        except Exception as exc:
            logger.warning(
                "[SEED-UI][REGISTRY] Runtime registration deferred: %s",
                exc,
            )

    logger.info(
        "[SEED-UI] Runtime bound | authorities=%s",
        sorted(accepted.keys()),
    )

    return dict(UI_RUNTIME)


# =====================================================================
# 14. LOCAL WEB HUD
# =====================================================================

def local_web_hud_path():
    return THIS_PATH / "hudwebui.html"


def local_web_hud_url(host="localhost", port=8766):
    return f"http://{host}:{int(port)}"


__all__.extend([
    "UI_RUNTIME",
    "bind_runtime",
    "local_web_hud_path",
    "local_web_hud_url",
])


# ==========================================================
# END __init__.py
# ==========================================================

