# =========================================================
# MAIN.PY TRACE WRAPPER FOR BOOT ERRORS
# Purpose: Trace top-down where EventBus fails (self not defined)
# =========================================================
# from seed.systemutils.boottrace import trace_boot_error


import sys
import traceback
import importlib

# -------------------------
# Helper: full top-down traceback printer
# -------------------------
def trace_boot_error(entry_point_module):
    try:
        # Dynamically import your main bootstrap module
        importlib.import_module(entry_point_module)
    except Exception as e:
        print("\n[BOOT ERROR DETECTED]")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {e}")
        print("\nFull top-down traceback (most recent last):")
        traceback.print_exc()  # Prints every frame from top to bottom

        # Optional: show last 15 frames only for quick focus
        tb_lines = traceback.format_exc().splitlines()
        print("\n[LAST 15 FRAMES FOR FOCUS]")
        print("\n".join(tb_lines[-15:]))


if __name__ == "__main__":
    # This will fully trace all errors during bootstrap, top-down
    trace_boot_error("main_boot")