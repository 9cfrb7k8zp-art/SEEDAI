# ==========================================================
# FILE: seed_locking_controller.py
# PATH: SEED_ROOT/seed/core/seed_locking_controller.py
# VERSION: 5.0 (FULL SYSTEM | HANDSHAKE-INTEGRATED | QBIT-HUD-AWARE | SWARM READY)
# UPDATED: 2026-01-01
# ==========================================================
# PURPOSE:
#   Digital Phase-Lock Loop (PLL) for carrier synchronization
#   - Auto integration with Handshake & modem
#   - TrackSystem + HUD overlay support
#   - Qbit emission on lock/unlock events
#   - Multi-PLL swarm coordination for networked devices
# ==========================================================

import time
import math
import logging
import uuid
from threading import Lock

logger = logging.getLogger("SEEDLocking")
logger.setLevel(logging.INFO)

# ==========================================================
# AUTO-INTEGRATION IMPORTS
# ==========================================================
try:
    from seed.core.track_system import TrackSystem
    from seed.core.qbit_dialer import QbitDialer
    from seed.core.handshake_protocol import HandshakePacket
    from seed.core.modem_layer import SignalFrame
except ImportError:
    TrackSystem = None
    QbitDialer = None
    HandshakePacket = None
    SignalFrame = None

# ==========================================================
# PHASE LOCK LOOP CLASS
# ==========================================================
class PhaseLockLoop:
    """
    Digital PLL for carrier synchronization
    Integrated with Handshake, TrackSystem, HUD, and QbitDialer
    Supports multi-PLL swarm coordination
    """

    _swarm_lock = Lock()
    _swarm_instances = []

    def __init__(
        self,
        target_freq: float,
        modem=None,
        handshake_manager=None,
        loop_gain: float = 0.15,
        damping: float = 0.7,
        lock_threshold: float = 0.01,
        channel: str = "PLL",
        skill: str = "PLL_Controller",
        hud_id: str = None,
        qbit_dialer: QbitDialer = None,
    ):
        # PLL parameters
        self.target_freq = target_freq
        self.loop_gain = loop_gain
        self.damping = damping
        self.lock_threshold = lock_threshold

        self.phase = 0.0
        self.freq = target_freq
        self.integrator = 0.0
        self.last_time = time.time()
        self.locked = False

        # SYSTEM INTEGRATION
        self.channel = channel
        self.skill = skill
        self.hud_id = hud_id or f"SS-HUD-{uuid.uuid4().hex[:8]}"
        self.qbit_dialer = qbit_dialer
        self.modem = modem
        self.handshake_manager = handshake_manager

        # Track ID for logging/HUD
        self.track_id = None
        if TrackSystem:
            self.track_id = TrackSystem.begin(
                channel=self.channel,
                skill=self.skill,
                priority="HIGH",
                hud_id=self.hud_id,
            )

        # Register in swarm
        with PhaseLockLoop._swarm_lock:
            PhaseLockLoop._swarm_instances.append(self)

        logger.info(f"[PLL] Initialized | target_freq={self.target_freq} Hz | HUD={self.hud_id}")

    # ======================================================
    # UPDATE LOOP
    # ======================================================
    def update(self, measured_phase: float, measured_freq: float) -> dict:
        now = time.time()
        dt = max(now - self.last_time, 1e-4)
        self.last_time = now

        # Phase error (wrapped)
        phase_error = self._wrap_phase(measured_phase - self.phase)

        # Frequency error
        freq_error = measured_freq - self.freq

        # Loop filter (PI controller)
        self.integrator += phase_error * self.loop_gain * dt
        correction = self.loop_gain * phase_error + self.damping * self.integrator

        # Update internal oscillator
        self.freq += correction + freq_error * 0.05
        self.phase += self.freq * dt
        self.phase = self._wrap_phase(self.phase)

        # Lock detection
        locked_prev = self.locked
        self.locked = abs(phase_error) < self.lock_threshold

        # Emit Qbit / track event on lock change
        if self.locked != locked_prev:
            self._emit_lock_event()

        # TrackSystem logging
        if TrackSystem:
            TrackSystem.emit(
                channel=self.channel,
                state="LOCKED" if self.locked else "UNLOCKED",
                priority="HIGH",
                data={
                    "phase_error": phase_error,
                    "freq": self.freq,
                    "locked": self.locked,
                },
                hud_id=self.hud_id,
            )

        # Auto-align handshake manager if available
        if self.locked and self.handshake_manager:
            self._sync_handshake()

        # Swarm coordination
        self._swarm_sync()

        return {
            "phase_error": phase_error,
            "freq": self.freq,
            "locked": self.locked,
        }

    # ======================================================
    # HANDSHAKE SYNC
    # ======================================================
    def _sync_handshake(self):
        """
        Adjust target frequency in handshake manager to PLL carrier
        """
        if hasattr(self.handshake_manager, "modem") and hasattr(self.handshake_manager.modem, "pll"):
            self.handshake_manager.modem.pll.target_freq = self.freq
            logger.info(f"[PLL] Synced handshake frequency → {self.freq:.4f} Hz")

    # ======================================================
    # QBIT / HUD EMISSION
    # ======================================================
    def _emit_lock_event(self):
        msg_type = "PLL_LOCKED" if self.locked else "PLL_UNLOCKED"
        logger.info(f"[PLL] {msg_type} | freq={self.freq:.4f} Hz | HUD={self.hud_id}")

        if self.qbit_dialer:
            qbit = {
                "qbit_type": msg_type,
                "payload": {
                    "freq": self.freq,
                    "phase": self.phase,
                    "locked": self.locked,
                },
                "track": self.track_id,
                "ts": time.time(),
                "hud_id": self.hud_id,
            }
            try:
                if hasattr(self.qbit_dialer, "submit_qbit"):
                    self.qbit_dialer.submit_qbit(qbit)
                elif hasattr(self.qbit_dialer, "push_data"):
                    self.qbit_dialer.push_data(qbit)
            except Exception as e:
                logger.error(f"[PLL] Qbit emission failed: {e}")

    # ======================================================
    # MULTI-PLL SWARM COORDINATION
    # ======================================================
    def _swarm_sync(self):
        """
        Synchronize phase and frequency across all registered PLLs
        """
        with PhaseLockLoop._swarm_lock:
            swarm_freqs = [pll.freq for pll in PhaseLockLoop._swarm_instances if pll.locked]
            if swarm_freqs:
                avg_freq = sum(swarm_freqs) / len(swarm_freqs)
                self.freq += (avg_freq - self.freq) * 0.1  # soft convergence
                logger.debug(f"[PLL] Swarm sync | avg_freq={avg_freq:.4f} Hz | local={self.freq:.4f} Hz")

    # ======================================================
    # HELPERS
    # ======================================================
    @staticmethod
    def _wrap_phase(phi: float) -> float:
        while phi > math.pi:
            phi -= 2 * math.pi
        while phi < -math.pi:
            phi += 2 * math.pi
        return phi

    # ======================================================
    # SYSTEM TERMINATION
    # ======================================================
    def shutdown(self):
        """Clear track context safely and remove from swarm"""
        with PhaseLockLoop._swarm_lock:
            if self in PhaseLockLoop._swarm_instances:
                PhaseLockLoop._swarm_instances.remove(self)
        if TrackSystem:
            TrackSystem.end()
        logger.info(f"[PLL] Shutdown | HUD={self.hud_id}")
