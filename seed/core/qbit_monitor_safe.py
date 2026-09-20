# ==========================================================
# FILE: qbit_monitor_safe.py
# PATH: SEED_ROOT/seed/core/qbit_monitor_safe.py
# VERSION: 1.0 (SAFE MONITOR LOOP)
# NOTES: Replaces _monitor_loop to prevent limp-mode spam
#        Handles float comparisons and SEEDEventBus safely
# ==========================================================

import time
import logging

logger = logging.getLogger("QbitMonitorSafe")

# Default numeric thresholds
DEFAULT_CPU_THRESHOLD = 60.0  # percent
DEFAULT_MEM_THRESHOLD = 65.0  # percent
LIMP_MODE_COOLDOWN = 10.0  # seconds between limp mode triggers

last_limp_time = 0.0

def _monitor_loop(event_source, cpu_threshold=None, mem_threshold=None):
    """
    Monitors CPU and memory usage, activating limp mode if exceeded.
    event_source: generator or iterable providing system events
    cpu_threshold / mem_threshold: numeric values for triggering limp mode
    """
    global last_limp_time

    # Fallback to defaults if thresholds not provided
    cpu_threshold = cpu_threshold if isinstance(cpu_threshold, (int, float)) else DEFAULT_CPU_THRESHOLD
    mem_threshold = mem_threshold if isinstance(mem_threshold, (int, float)) else DEFAULT_MEM_THRESHOLD

    for event in event_source:
        try:
            # Extract CPU/MEM from event safely
            cpu_usage = getattr(event, "cpu", None)
            mem_usage = getattr(event, "mem", None)

            # Skip events without numeric values
            if not isinstance(cpu_usage, (int, float)):
                logger.warning(f"Invalid CPU value from event: {cpu_usage}")
                continue
            if not isinstance(mem_usage, (int, float)):
                logger.warning(f"Invalid MEM value from event: {mem_usage}")
                continue

            # Check thresholds
            current_time = time.time()
            if (cpu_usage > cpu_threshold or mem_usage > mem_threshold):
                if current_time - last_limp_time > LIMP_MODE_COOLDOWN:
                    logger.warning(
                        f"Limp mode activated (global): [SystemMonitor] "
                        f"Resource limit exceeded: CPU {cpu_usage}%, MEM {mem_usage}%"
                    )
                    last_limp_time = current_time
                    # Call your limp mode handler here
                    activate_limp_mode()
            else:
                # Optional: log normal usage
                logger.info(f"CPU {cpu_usage}%, MEM {mem_usage}% - within limits")

        except Exception as e:
            logger.error(f"Error in _monitor_loop(): {e}", exc_info=True)

def activate_limp_mode():
    """
    Placeholder for SEED limp mode handler.
    Replace this with your actual limp-mode logic.
    """
    logger.info(">>> Limp mode logic triggered safely <<<")
