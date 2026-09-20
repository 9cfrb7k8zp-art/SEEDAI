# boottrace_runtime.py
# =========================================================
# FILE: boottrace_runtime.py
# PURPOSE: Full import + runtime + thread + async tracing
# =========================================================

import sys
import traceback
import importlib
import threading
import asyncio

# -------------------------
# GLOBAL EXCEPTION HOOK
# -------------------------
def global_exception_hook(exc_type, exc_value, exc_tb):
    print("\n[FATAL RUNTIME ERROR]")
    print(f"Type: {exc_type.__name__}")
    print(f"Message: {exc_value}")
    print("\n[FULL TRACEBACK]")
    traceback.print_exception(exc_type, exc_value, exc_tb)

sys.excepthook = global_exception_hook


# -------------------------
# THREAD EXCEPTION HOOK (Python 3.8+)
# -------------------------
def thread_exception_hook(args):
    print("\n[THREAD ERROR]")
    print(f"Thread: {args.thread.name}")
    traceback.print_exception(
        args.exc_type,
        args.exc_value,
        args.exc_traceback
    )

threading.excepthook = thread_exception_hook


# -------------------------
# ASYNCIO EXCEPTION HOOK
# -------------------------
def install_asyncio_exception_handler():
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        return

    def handle_async_exception(loop, context):
        print("\n[ASYNCIO ERROR]")
        exception = context.get("exception")
        if exception:
            traceback.print_exception(
                type(exception),
                exception,
                exception.__traceback__
            )
        else:
            print(context)

    loop.set_exception_handler(handle_async_exception)


# -------------------------
# BOOT + RUNTIME WRAPPER
# -------------------------
def trace_boot_and_runtime(entry_module):
    print(f"[BOOT TRACE START] -> {entry_module}")

    try:
        module = importlib.import_module(entry_module)

        # Install asyncio hook AFTER import
        install_asyncio_exception_handler()

        # Optional: auto-run main() if present
        if hasattr(module, "main") and callable(module.main):
            print("[BOOT] Calling main()")
            module.main()

        print("[BOOT COMPLETE] Runtime tracing active")

    except Exception as e:
        print("\n[BOOT FAILURE]")
        traceback.print_exc()
        raise   # HARD FAIL — do NOT hide errors
