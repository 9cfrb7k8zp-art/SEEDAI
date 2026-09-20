# ==========================================================
# FILE: bios_file_tool.py
# PATH: SEED_ROOT/seed/core/bios/bios_file_tool.py
# PURPOSE: BIOS File / Patch Tool (delegates to FileReaderSkill)
# NOTES:
# - TrackID-aware
# - Async safe for first-boot operations
# - Integrates with BuildManager if available
# ==========================================================

import logging
import asyncio
from pathlib import Path

logger = logging.getLogger("BIOS.FileTool")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter("[%(name)s] %(levelname)s: %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

class BIOSFileTool:
    def __init__(self, file_reader_skill=None, build_manager=None):
        self.file_reader = file_reader_skill
        self.build_manager = build_manager

    # -------------------------
    # Read file content
    # -------------------------
    async def read(self, path: str) -> str:
        path_obj = Path(path)
        logger.info(f"[BIOS] Read request: {path_obj}")
        try:
            if self.file_reader:
                # Use FileReaderSkill if available
                await self.file_reader._process_file(str(path_obj))
                return self.file_reader.files.get(str(path_obj), "")
            else:
                return path_obj.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            logger.error(f"[BIOS] Failed to read {path}: {e}")
            return ""

    # -------------------------
    # Write file content
    # -------------------------
    async def write(self, path: str, content: str, track_id=None):
        path_obj = Path(path)
        logger.info(f"[BIOS] Write request: {path_obj} | TrackID={track_id}")
        try:
            if self.file_reader:
                # Update via FileReaderSkill
                self.file_reader.files[str(path_obj)] = content
                await self.file_reader._process_file(str(path_obj), parent_id=track_id)
            else:
                path_obj.write_text(content, encoding="utf-8")
        except Exception as e:
            logger.error(f"[BIOS] Failed to write {path}: {e}")

    # -------------------------
    # Patch a file (delegate to BuildManager if available)
    # -------------------------
    async def patch(self, path: str, new_content: str, track_id=None):
        logger.info(f"[BIOS] Patch request: {path} | TrackID={track_id}")
        try:
            if self.build_manager:
                await self.build_manager.submit_patch(
                    file_path=path,
                    new_content=new_content,
                    track_id=track_id
                )
            else:
                await self.write(path, new_content, track_id)
        except Exception as e:
            logger.error(f"[BIOS] Failed to patch {path}: {e}")
