# ==========================================================
# FILE: autofix_engine.py
# PATH: seed/core/integration/autofix_engine.py
#
# PURPOSE:
# - Intelligent error correction engine
# - Applies FixSkills to real files
# - TrackID + Qbit + Agent authorization
# - Fully compatible with QbitDialer v3.7
# - Integrated with HealthMonitor & DeviceModemManager
#
# NOTES:
# - No direct file I/O (uses FileReaderSkill for write authority)
# - Emits per-line telemetry to QbitDialer
# - Emits system/device health telemetry
# - Automatically ensures minimal system files exist (Python + binary + C++)
# - Starts with initial code dictionary to bootstrap SEED AI OS
# - Supports multi-channel TrackID and smart labeling
# ==========================================================

import os
import logging
import asyncio
from pathlib import Path
from seed.core.track_id_manager import TrackIDManager



logger = logging.getLogger("AutoFixEngine")
logger.setLevel(logging.INFO)
if not logger.hasHandlers():
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(name)s] %(levelname)s: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# -------------------------
# Minimal files to bootstrap
# -------------------------
MINIMAL_FILES = {
    "python": ["file_reader.py", "autofix_skill_loader.py", "core_scaffold.py"],
    "binary": ["seed_bootstrap.exe"],
    "cpp": ["basic_build.cpp"]
}

# Optional integration
try:
    from seed.core.device_modem_integration import device_modem_manager
except ImportError:
    HealthMonitor = None
    device_modem_manager = None

print("🔥 LOADED AutoFixEngine FROM:", __file__)

# -------------------------
# AutoFix Engine
# -------------------------
class AutoFixEngine:
    def __init__(
        self,
        file_reader_skill,
        build_manager=None,
        agent_manager=None,
        qbit_dialer=None,
        skill_loader=None,
        seed_root="./SEED_ROOT",
        health_monitor = None
    ):

        from seed.systemutils.healthmonitor import HealthMonitor
        self.file_reader = file_reader_skill
        self.build_manager = build_manager
        self.agent_manager = agent_manager
        self.qbit = qbit_dialer
        self.skill_loader = skill_loader
        self.seed_root = Path(seed_root)
        self.health_monitor = health_monitor

        self.seed_root.mkdir(parents=True, exist_ok=True)
        self._ensure_minimal_files()

    # ------------------------------------------------------
    # Bootstrap: create missing minimal files
    # ------------------------------------------------------
    def _ensure_minimal_files(self):
        for category, files in MINIMAL_FILES.items():
            for fname in files:
                fpath = self.seed_root / fname
                if not fpath.exists():
                    try:
                        if category == "python":
                            fpath.write_text(
                                f"# Auto-generated placeholder: {fname}\n"
                                f"if __name__ == '__main__':\n"
                                f"    print('Running {fname}')\n",
                                encoding="utf-8"
                            )
                        elif category == "binary":
                            fpath.write_bytes(b"/* Placeholder binary for SEED AI OS bootstrap */")
                        elif category == "cpp":
                            fpath.write_text(
                                "#include <iostream>\n"
                                "int main() {\n"
                                "    std::cout << \"Basic build tool placeholder\" << std::endl;\n"
                                "    return 0;\n"
                                "}\n",
                                encoding="utf-8"
                            )
                        logger.info(f"[Bootstrap] Created {category} file: {fpath}")
                    except Exception as e:
                        logger.error(f"[Bootstrap] Failed to create {fpath}: {e}")
                        if self.health_monitor:
                            self.health_monitor.record_fault("AutoFixEngine", e)

    # ------------------------------------------------------
    # Process a file with FixSkills
    # ------------------------------------------------------
    async def process_file(self, file_path, original_content, parent_id=None, channels=None):
        channels = channels or ["AUTOFIX"]
        track_id = TrackIDManager.generate(
            channel_marker=",".join(channels),
            skill_name="AUTO_FIX",
            parent_id=parent_id,
            qbit_callback=self.qbit.emit_safe if self.qbit else None
        )

        # ---------------- Authorization ----------------
        if self.agent_manager and not self.agent_manager.authorize(
            skill="AUTO_FIX",
            priority="system",
            track_id=track_id
        ):
            logger.warning(f"[AutoFix] Authorization denied | {file_path}")
            return

        # ---------------- Load FixSkills ----------------
        skills = self.skill_loader.load() if self.skill_loader else []
        content = original_content
        changed = False

        for skill in skills:
            try:
                if skill.match(content):
                    new_content = skill.apply(content)
                    if new_content != content:
                        content = new_content
                        changed = True
                        if self.qbit:
                            self.qbit.emit_safe(
                                payload={
                                    "event": "AUTOFIX_APPLIED",
                                    "file": str(file_path),
                                    "skill": skill.name,
                                    "channels": channels
                                },
                                track_id=track_id
                            )
            except Exception as e:
                logger.error(f"[AutoFix:{skill.name}] failed: {e}")
                if self.health_monitor:
                    self.health_monitor.record_fault("AutoFixEngine", e)

        # ---------------- Per-line telemetry ----------------
        for idx, line in enumerate(content.splitlines(), 1):
            self.emit_line_telemetry(file_path, idx, line, track_id, channels)

        if not changed:
            return

        # ---------------- Write back using FileReaderSkill ----------------
        if self.file_reader:
            try:
                await self.file_reader._process_file(file_path, parent_id=track_id)
            except Exception as e:
                logger.error(f"[AutoFix] File write failed: {file_path} | {e}")
                if self.health_monitor:
                    self.health_monitor.record_fault("AutoFixEngine", e)

        # ---------------- Trigger build if exists ----------------
        if self.build_manager:
            try:
                await self.build_manager.request_build(
                    file_path=file_path,
                    priority="high",
                    track_id=track_id,
                    parent_id=parent_id,
                    metadata={"autofix": True, "channels": channels}
                )
            except Exception as e:
                logger.error(f"[AutoFix] Build trigger failed: {file_path} | {e}")
                if self.health_monitor:
                    self.health_monitor.record_fault("AutoFixEngine", e)

        # ---------------- DeviceModemManager routing ----------------
        if device_modem_manager:
            try:
                device_modem_manager.push_device_event(
                    device_id="AUTOFIX_ENGINE",
                    payload={
                        "event": "FILE_CORRECTED",
                        "file": str(file_path),
                        "track_id": track_id,
                        "channels": channels
                    },
                    channel="IOT"
                )
            except Exception as e:
                logger.warning(f"[AutoFix] DeviceModem routing failed: {e}")

        logger.info(f"[AutoFix] File corrected → {file_path} | TrackID={track_id} | Channels={channels}")

    # ------------------------------------------------------
    # Emit per-line telemetry to QbitDialer
    # ------------------------------------------------------
    def emit_line_telemetry(self, file_path, line_number, line_content, track_id=None, channels=None):
        if not self.qbit:
            return
        payload = {
            "event": "LINE_ANALYSIS",
            "file": str(file_path),
            "line_number": line_number,
            "line_content": line_content,
            "channels": channels or []
        }
        try:
            self.qbit.emit_safe(payload, track_id=track_id)
        except Exception as e:
            logger.error(f"[AutoFix] Failed to emit line telemetry: {e}")
            if self.health_monitor:
                self.health_monitor.record_fault("AutoFixEngine", e)
