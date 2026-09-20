# ==========================================================
# FILE: file_reader.py
# PATH: SEED_ROOT/seed/skills/file_reader.py
# VERSION: 0.8.0 (TrackID + Driver Build + HUD + Smart Labeling + Multi-Channel)
# UPDATED: 2025-12-30
# ==========================================================

import os
import time
import asyncio
import uuid
from copy import deepcopy
from seed.skills.skill_base import SkillBase
import logging
import contextlib

# Optional dependencies
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
except ImportError:
    Observer = None
    FileSystemEventHandler = None

try:
    import pandas as pd
except ImportError:
    pd = None

try:
    from PyPDF2 import PdfReader
except ImportError:
    PdfReader = None

try:
    from PIL import Image
except ImportError:
    Image = None

try:
    import wave
except ImportError:
    wave = None

try:
    import mutagen
except ImportError:
    mutagen = None

# Supported extensions
TEXT_EXTENSIONS = [".txt", ".md", ".log", ".json", ".py"]
CSV_EXTENSIONS = [".csv", ".xlsx"]
PDF_EXTENSIONS = [".pdf"]
IMAGE_EXTENSIONS = [".png", ".jpg", ".jpeg", ".bmp", ".gif"]
AUDIO_EXTENSIONS = [".wav", ".mp3", ".flac"]

logger = logging.getLogger("FileReaderSkill")
logger.setLevel(logging.INFO)

# --------------------------------------------------
# TrackID generator for files/events
# --------------------------------------------------
def gen_track_id(prefix="FILE", parent_id=None):
    tid = f"{prefix}-{str(uuid.uuid4())[:8]}"
    return {"track_id": tid, "parent_id": parent_id}

# --------------------------------------------------
# FileReader Skill with Driver Build + Smart Labeling
# --------------------------------------------------
class FileReaderSkill(SkillBase):
    def __init__(self, name="file_reader", throttle_interval=0.5,
                 actuator_engine=None, sparkplug=None,
                 watch_dirs=None, build_manager=None):
        super().__init__(name=name, throttle_interval=throttle_interval,
                         actuator_engine=actuator_engine, sparkplug=sparkplug)
        self.watch_dirs = watch_dirs or ["./SEED_ROOT/inbox"]
        self._file_mtimes = {}
        self.priority_map = {}
        self.build_manager = build_manager
        self.loop = asyncio.get_event_loop()
        self._observer = None
        self._queue_task = None
        self._start_watcher()

    # --------------------------------------------------
    # Start real-time watcher
    # --------------------------------------------------
    def _start_watcher(self):
        if not Observer or not FileSystemEventHandler:
            self.logger.warning(f"[{self.name}] watchdog not installed, using polling fallback")
            self._queue_task = self.loop.create_task(self._polling_loop())
            return

        class Handler(FileSystemEventHandler):
            def __init__(self, skill):
                self.skill = skill

            def on_created(self, event):
                if not event.is_directory:
                    asyncio.run_coroutine_threadsafe(self.skill._process_file(event.src_path), self.skill.loop)

            def on_modified(self, event):
                if not event.is_directory:
                    asyncio.run_coroutine_threadsafe(self.skill._process_file(event.src_path), self.skill.loop)

        self._observer = Observer()
        handler = Handler(self)
        for d in self.watch_dirs:
            if os.path.exists(d):
                self._observer.schedule(handler, path=d, recursive=False)
        self._observer.start()
        self.logger.info(f"[{self.name}] Real-time directory watcher started")

    # --------------------------------------------------
    # Polling fallback loop
    # --------------------------------------------------
    async def _polling_loop(self):
        while True:
            for dir_path in self.watch_dirs:
                if not os.path.exists(dir_path):
                    continue
                for filename in os.listdir(dir_path):
                    file_path = os.path.join(dir_path, filename)
                    if os.path.isfile(file_path) and self._should_process(file_path):
                        await self._process_file(file_path)
            await asyncio.sleep(1.0)

    # --------------------------------------------------
    # Check if file should be processed
    # --------------------------------------------------
    def _should_process(self, file_path):
        try:
            mtime = os.path.getmtime(file_path)
        except Exception:
            return False
        if file_path not in self._file_mtimes or self._file_mtimes[file_path] != mtime:
            self._file_mtimes[file_path] = mtime
            return True
        return False

    # --------------------------------------------------
    # Process file and generate TrackID-aware payload
    # --------------------------------------------------
    async def _process_file(self, file_path, parent_id=None):
        ids = gen_track_id("FILE", parent_id)
        track_id, parent_id = ids["track_id"], ids["parent_id"]

        payload = {
            "track_id": track_id,
            "parent_id": parent_id,
            "skill": self.name,
            "file_path": file_path,
            "status": "success",
            "metadata": {},
            "data": {},
            "priority": "medium",
            "request_driver_build": False,
            "timestamp": time.time()
        }

        try:
            ext = os.path.splitext(file_path)[1].lower()
            payload["metadata"]["extension"] = ext

            # ----------------- Text -----------------
            if ext in TEXT_EXTENSIONS:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                payload["metadata"].update({
                    "length": len(content),
                    "lines": content.count("\n") + 1
                })
                payload["data"]["text"] = content[:5000]

            # ----------------- CSV / Excel -----------------
            elif ext in CSV_EXTENSIONS and pd:
                df = pd.read_csv(file_path) if ext == ".csv" else pd.read_excel(file_path)
                payload["metadata"]["rows"] = len(df)
                payload["metadata"]["columns"] = len(df.columns)
                payload["data"]["csv_head"] = df.head(5).to_dict(orient="records")

            # ----------------- PDF -----------------
            elif ext in PDF_EXTENSIONS and PdfReader:
                reader = PdfReader(file_path)
                payload["metadata"]["pages"] = len(reader.pages)
                text_content = ""
                for page in reader.pages:
                    text_content += page.extract_text() or ""
                payload["data"]["text"] = text_content[:5000]

            # ----------------- Images -----------------
            elif ext in IMAGE_EXTENSIONS and Image:
                img = Image.open(file_path)
                payload["metadata"].update({
                    "width": img.width,
                    "height": img.height,
                    "mode": img.mode,
                    "format": img.format
                })
                payload["data"]["image_info"] = f"{img.width}x{img.height} {img.mode}"

            # ----------------- Audio -----------------
            elif ext in AUDIO_EXTENSIONS:
                if ext == ".wav" and wave:
                    with contextlib.closing(wave.open(file_path, 'r')) as wf:
                        payload["metadata"].update({
                            "channels": wf.getnchannels(),
                            "framerate": wf.getframerate(),
                            "frames": wf.getnframes(),
                            "duration": wf.getnframes() / wf.getframerate()
                        })
                        payload["data"]["note"] = "Audio WAV metadata extracted"
                elif mutagen:
                    audio = mutagen.File(file_path)
                    if audio:
                        payload["metadata"]["duration"] = getattr(audio.info, "length", 0)
                        payload["metadata"]["bitrate"] = getattr(audio.info, "bitrate", 0)
                        payload["data"]["note"] = f"{ext.upper()} metadata extracted"

            else:
                payload["status"] = "unsupported_type"
                payload["data"]["note"] = "File type not yet supported"

            # ----------------- Priority / Driver Build -----------------
            fname_lower = os.path.basename(file_path).lower()
            if "driver" in fname_lower or "build" in fname_lower:
                payload["request_driver_build"] = True
                payload["priority"] = "high"
            elif ext in [".json", ".csv", ".xlsx", ".pdf"]:
                payload["priority"] = "medium"
            elif ext in IMAGE_EXTENSIONS + AUDIO_EXTENSIONS:
                payload["priority"] = "medium"
            else:
                payload["priority"] = "low"

            self.priority_map[file_path] = payload["priority"]

            # ----------------- Queue / Execute -----------------
            payload["track_id"] = track_id
            self.enqueue_event(payload)

            # ----------------- Trigger Driver Build & Write for Manager -----------------
            if self.build_manager:
                try:
                    await self.build_manager.request_build(
                        file_path,
                        priority=payload["priority"],
                        track_id=track_id,
                        parent_id=parent_id,
                        metadata=deepcopy(payload["metadata"])
                    )
                    self.logger.info(f"[{self.name}] Build requested for: {file_path} | TrackID={track_id}")
                except Exception as e:
                    self.logger.warning(f"[{self.name}] Failed to request build: {e} | TrackID={track_id}")

        except Exception as e:
            payload["status"] = "error"
            payload["error"] = str(e)
            self.enqueue_event(payload)

    # --------------------------------------------------
    # Skill execution / SparkPlug output
    # --------------------------------------------------
    async def execute(self, payload):
        track_id = payload.get("track_id") or gen_track_id("EXEC")["track_id"]
        self.logger.info(f"[{self.name}] Processing: {payload.get('file_path')} (priority={payload.get('priority')}) | TrackID={track_id}")
        await self.execute_chain(payload)
        self.push_sparkplug_event("file_reader_output", payload)

    # --------------------------------------------------
    # Cleanup observer on shutdown
    # --------------------------------------------------
    def stop(self):
        if self._observer:
            self._observer.stop()
            self._observer.join()
        if self._queue_task:
            self._queue_task.cancel()
        self.logger.info(f"[{self.name}] FileReader stopped cleanly")
