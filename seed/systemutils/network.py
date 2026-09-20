# ==========================================================
# File: network.py
# Path: SEED_ROOT/seed/systemutils/network.py
# Version: 0.3 (SEED CORE NETWORK)
#
# Purpose:
#   - Central communications backbone for SEED AI
#   - Internal message routing & delivery
#   - Future HTML / SQL / PHP gateway bridge
#   - Protocol, domain & IP registry (future)
#   - Internal E-sim router (future)
#
# Design Philosophy:
#   - BIG FILE, CLEAR ZONES
#   - Stackable modules
#   - Safe even when subsystems do not yet exist
#   - Thread-safe, callback-driven
#
# Status:
#   - Fully runnable
#   - Future-ready
# ==========================================================

# ==========================================================
# ----------------------------- Imports --------------------
# ==========================================================
import threading
import queue
import logging
import time
import uuid
from dataclasses import dataclass
from typing import Callable, Any, Dict, List, Optional

# ==========================================================
# ----------------------------- Logging --------------------
# ==========================================================
logger = logging.getLogger("SEED.Network")
logger.setLevel(logging.INFO)

# ==========================================================
# ---------------------- Message Definition ----------------
# ==========================================================
@dataclass
class NetworkMessage:
    """
    Core message unit passed through SEED Network.
    """
    id: str
    source: str
    payload: Any
    timestamp: float
    meta: Dict[str, Any] = None

    @staticmethod
    def create(source: str, payload: Any, meta: Dict[str, Any] = None):
        return NetworkMessage(
            id=str(uuid.uuid4()),
            source=source,
            payload=payload,
            timestamp=time.time(),
            meta=meta or {}
        )

# ==========================================================
# =========================== Network ======================
# ==========================================================
class Network:
    """
    SEED AI Core Network Layer
    --------------------------------------------------------
    This class is the authoritative internal communication
    bus for SEED AI systems.
    """

    # ------------------------------------------------------
    # Initialization / State
    # ------------------------------------------------------
    def __init__(self, name: str = "SEED-NET"):
        self.name = name
        self.running = False

        # Thread-safe message queue
        self._queue: queue.Queue[NetworkMessage] = queue.Queue()

        # Registered delivery callbacks
        self._callbacks: List[Callable[[NetworkMessage], None]] = []

        # Optional single legacy callback (compat mode)
        self.on_message_delivered: Optional[Callable[[NetworkMessage], None]] = None

        # Worker thread
        self._thread: Optional[threading.Thread] = None

        # Diagnostics
        self.messages_processed = 0
        self.start_time = None

        logger.info("[%s] Network initialized", self.name)

    # ======================================================
    # ------------------- Lifecycle Control ----------------
    # ======================================================
    def start(self):
        """Start the network polling loop."""
        if self.running:
            logger.warning("[%s] Network already running", self.name)
            return

        self.running = True
        self.start_time = time.time()

        self._thread = threading.Thread(
            target=self._poll_loop,
            name=f"{self.name}-Poller",
            daemon=True
        )
        self._thread.start()

        logger.info("[%s] Network polling started", self.name)

    def stop(self):
        """Stop the network polling loop."""
        self.running = False

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

        logger.info("[%s] Network polling stopped", self.name)

    # ======================================================
    # --------------------- Public API ---------------------
    # ======================================================
    def deliver_message(self, message: NetworkMessage):
        """
        Queue a message for network delivery.
        """
        if not isinstance(message, NetworkMessage):
            raise TypeError("deliver_message expects NetworkMessage")

        self._queue.put(message)
        logger.info("[%s] Message queued: %s", self.name, message.id)

    def send(self, source: str, payload: Any, meta: Dict[str, Any] = None):
        """
        Convenience method to create and send a message.
        """
        msg = NetworkMessage.create(source, payload, meta)
        self.deliver_message(msg)

    def register_callback(self, callback: Callable[[NetworkMessage], None]):
        """
        Register a callback to receive delivered messages.
        """
        if callback not in self._callbacks:
            self._callbacks.append(callback)
            logger.info("[%s] Callback registered: %s", self.name, callback)

    def unregister_callback(self, callback: Callable):
        """
        Remove a previously registered callback.
        """
        if callback in self._callbacks:
            self._callbacks.remove(callback)
            logger.info("[%s] Callback unregistered: %s", self.name, callback)

    # ======================================================
    # -------------------- Internal Loop -------------------
    # ======================================================
    def _poll_loop(self):
        """
        Internal polling loop.
        Safely dispatches messages to callbacks.
        """
        logger.info("[%s] Poll loop active", self.name)

        while self.running:
            try:
                message: NetworkMessage = self._queue.get(timeout=0.5)

                self.messages_processed += 1

                # Legacy single callback support
                if self.on_message_delivered:
                    try:
                        self.on_message_delivered(message)
                    except Exception as e:
                        logger.exception("[%s] Legacy callback error: %s", self.name, e)

                # Multi-callback dispatch
                for callback in list(self._callbacks):
                    try:
                        callback(message)
                    except Exception as e:
                        logger.exception(
                            "[%s] Callback failure (%s): %s",
                            self.name, callback, e
                        )

            except queue.Empty:
                continue
            except Exception as e:
                logger.exception("[%s] Poll loop error: %s", self.name, e)
                time.sleep(0.5)

    # ======================================================
    # ---------------- Diagnostics / Introspection ---------
    # ======================================================
    def status(self) -> Dict[str, Any]:
        """
        Return runtime status snapshot.
        """
        uptime = time.time() - self.start_time if self.start_time else 0.0
        return {
            "name": self.name,
            "running": self.running,
            "messages_processed": self.messages_processed,
            "queue_size": self._queue.qsize(),
            "callbacks": len(self._callbacks),
            "uptime_sec": round(uptime, 2),
        }

# ==========================================================
# ===================== Future Extension Zones =============
# ==========================================================

# ----------------------------------------------------------
# Protocol Adapters (HTTP / SQL / PHP)
# ----------------------------------------------------------
# class HTTPAdapter:
# class SQLAdapter:
# class PHPGateway:

# ----------------------------------------------------------
# IPConfig Manager
# ----------------------------------------------------------
# class IPConfigManager:

# ----------------------------------------------------------
# Internal E-Sim Router
# ----------------------------------------------------------
# class ESimRouter:

# ==========================================================
# ======================= End of File ======================
# ==========================================================
