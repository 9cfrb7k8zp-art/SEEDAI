# ========================================================================
# File: search_engine.py
# Path: seed/systemutils/search_engine.py
# V0.8 - Interactive HUD Live AI + OCR + Object Tracking + Click-Based Grouping
# Purpose:
#   - Full live video stream scanning with object detection & OCR
#   - Click-based pointer assignment and dynamic grouping
#   - Multi-object tracking and real-time reassignment
#   - Async, modular, fully HUD-ready
# ========================================================================

import os
from pathlib import Path
from typing import List, Dict, Union, Optional
import asyncio
import tkinter as tk
try:
    import cv2
except ImportError:
    cv2 = None

try:
    from PIL import Image, ImageDraw, ExifTags
except ImportError:
    Image = None

try:
    import pytesseract
except ImportError:
    pytesseract = None

try:
    import ffmpeg
except ImportError:
    ffmpeg = None

try:
    import torch
    YOLO = None

    def _load_yolo():
        global YOLO
        if YOLO is None:
            from ultralytics import YOLO as _YOLO
            YOLO = _YOLO
        return YOLO

except ImportError as e:
    torch = None
    print("[WARN] Torch not available:", e)

class SearchEngine(tk.Frame):


    FILE_TYPES = {
        "text": [".txt", ".md", ".py", ".log", ".json", ".csv"],
        "image": [".png", ".jpg", ".jpeg", ".bmp", ".gif"],
        "video": [".mp4", ".mov", ".avi", ".mkv"],
    }

    def __init__(self, parent, root_paths=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.root_paths = []
        if isinstance(root_paths, str):
            self.root_paths = [root_paths]
        elif root_paths:
            self.root_paths = root_paths
        self.root_paths = [os.path.abspath(p) for p in self.root_paths]

        # Load YOLO model
        try:
            YOLO_cls = _load_yolo()
            self.object_model = YOLO_cls('yolov8n.pt')
        except Exception as e:
            self.object_model = None
            print("[WARN] YOLO model not loaded:", e)

        # Object tracking and grouping
        self.object_groups: Dict[int, List[Dict]] = {}
        self.next_group_id = 1
        self.pointer_assignments: Dict[int, Dict] = {}  # pointer_id -> object info

    # ------------------------ Async File Search ------------------------
    async def search_files(
        self,
        keyword,
        search_content=False,
        file_types=[],
        detect_objects=False,
        ocr_text=False
    ) -> List[Dict]:
        results = []
        keyword_lower = keyword.lower()
        extensions = self._get_extensions(file_types)

        for root_path in self.root_paths:
            for root, _, files in os.walk(root_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    file_lower = file.lower()

                    if not any(file_lower.endswith(ext) for ext in extensions):
                        continue

                    match_type = None
                    obj_marks = []

                    if keyword_lower in file_lower:
                        match_type = "filename"
                    elif search_content and self._file_contains_keyword(file_path, keyword_lower):
                        match_type = "content"
                    elif Image and file_lower.endswith(tuple(self.FILE_TYPES["image"])) and self._image_contains_keyword(file_path, keyword_lower):
                        match_type = "image_metadata"
                    elif ffmpeg and file_lower.endswith(tuple(self.FILE_TYPES["video"])) and await self._video_contains_keyword(file_path, keyword_lower):
                        match_type = "video_metadata"

                    if detect_objects and self.object_model:
                        if file_lower.endswith(tuple(self.FILE_TYPES["image"])):
                            obj_marks = self._detect_objects_in_image(file_path)
                        elif file_lower.endswith(tuple(self.FILE_TYPES["video"])):
                            obj_marks = await self._detect_objects_in_video(file_path)

                    ocr_results = []
                    if ocr_text and pytesseract:
                        if file_lower.endswith(tuple(self.FILE_TYPES["image"])):
                            ocr_results = self._ocr_image(file_path, keyword_lower)
                        elif file_lower.endswith(tuple(self.FILE_TYPES["video"])):
                            ocr_results = await self._ocr_video(file_path, keyword_lower)

                    if match_type or obj_marks or ocr_results:
                        results.append({
                            "keyword": keyword,
                            "match_type": match_type,
                            "file": file,
                            "path": file_path,
                            "type": self._determine_type(file_path),
                            "objects": obj_marks,
                            "ocr": ocr_results
                        })

                    await asyncio.sleep(0)
        return results



    # ... existing code ...
    async def search(self, *args, **kwargs):
        return await self.search_files(*args, **kwargs)


    # ------------------------ Live Stream with Click-Based HUD ------------------------
    async def search_live_stream(
        self,
        source: Union[int, str],
        keyword=None,
        detect_objects=True,
        ocr_text=True,
        max_frames=500,
        pointer_callback=None
    ) -> List[Dict]:
        if not cv2:
            return []

        results = []
        cap = cv2.VideoCapture(source)
        frame_count = 0
        keyword_lower = keyword.lower() if keyword else None

        while cap.isOpened() and frame_count < max_frames:
            ret, frame = cap.read()
            if not ret:
                break
            frame_count += 1
            frame_results = []

            # Object detection
            if detect_objects and self.object_model:
                objs = self._detect_objects_on_frame(frame)
                self._update_groups(objs)
                for o in objs:
                    o["frame"] = frame_count
                    frame_results.append(o)

            # OCR detection
            if ocr_text and pytesseract:
                ocrs = self._ocr_frame(frame, keyword_lower)
                for o in ocrs:
                    o["frame"] = frame_count
                    frame_results.append(o)

            # Call HUD pointer callback if provided
            if pointer_callback:
                pointer_callback(frame, frame_results)

            if frame_results:
                results.append({
                    "frame": frame_count,
                    "objects": frame_results,
                    "groups": self.object_groups,
                    "pointers": self.pointer_assignments
                })

            await asyncio.sleep(0)

        cap.release()
        return results

    # ------------------------ Pointer Assignment ------------------------
    def assign_pointer(self, pointer_id: int, object_bbox: tuple):
        for group_id, group_objs in self.object_groups.items():
            for obj in group_objs:
                if self._iou(obj['bbox'], object_bbox) > 0.3:
                    self.pointer_assignments[pointer_id] = obj
                    obj['pointer'] = pointer_id
                    return True
        return False

    def remove_pointer(self, pointer_id: int):
        if pointer_id in self.pointer_assignments:
            obj = self.pointer_assignments[pointer_id]
            if 'pointer' in obj:
                del obj['pointer']
            del self.pointer_assignments[pointer_id]

    def _handle_cli_submit(self, event=None):
        command = self.cli_input.get().strip()
        if not command:
            return

        self.cli_output.insert("end", f"> {command}\n")
        self.cli_output.see("end")
        self.cli_input.delete(0, "end")
 
        asyncio.create_task(self._process_command(command))

    async def _process_command(self, command: str):

        # ------------------------------------------------------------------
        # 1️⃣ SEND RAW INPUT TO SEED-AI FIRST (AI INGESTION PRIORITY)
        # ------------------------------------------------------------------
        if hasattr(self.master, "seed_ai"):
            try:
                await self.master.seed_ai.submit(command)
            except Exception as e:
                self.cli_output.insert("end", f"[AI ERROR] {e}\n")


        # ------------------------------------------------------------------
        # 2️⃣ LIVE STREAM SEARCH (IF SOURCE EXISTS)
        # ------------------------------------------------------------------
        live_results = []
        if command.startswith("live:"):
            source = command.replace("live:", "").strip()
            try:
                live_results = await self.search_live_stream(
                    source=source,
                    keyword=command,
                    detect_objects=True,
                    ocr_text=True
                )
                self.cli_output.insert("end", f"[LIVE] {len(live_results)} frames processed\n")
            except Exception as e:
                self.cli_output.insert("end", f"[LIVE ERROR] {e}\n")


        # ------------------------------------------------------------------
        # 3️⃣ FULL FILE SEARCH (OBJECTS + OCR + CONTENT)
        # ------------------------------------------------------------------
        try:
            file_results = await self.search_files(
                keyword=command,
                search_content=True,
                file_types=["text", "image", "video"],
                detect_objects=True,
                ocr_text=True
            )

            for result in file_results:
                self.cli_output.insert(
                     "end",
                     f"[FILE] {result['file']} | {result['type']} | {result['match_type']}\n"
                )

            if not file_results:
                self.cli_output.insert("end", "[FILE] No matches\n")

        except Exception as e:
            self.cli_output.insert("end", f"[SEARCH ERROR] {e}\n")


        # ------------------------------------------------------------------
        # 4️⃣ NETWORK FIRE-AND-FORGET
        # ------------------------------------------------------------------
        if hasattr(self.master, "network_manager"):
            try:
                asyncio.create_task(self.master.network_manager.send(command))
            except Exception as e:
                self.cli_output.insert("end", f"[NET ERROR] {e}\n")


        # ------------------------------------------------------------------
        # 5️⃣ AI FEEDBACK LOOP (RETURN RESULTS BACK INTO SEED-AI)
        # ------------------------------------------------------------------
        if hasattr(self.master, "seed_ai"):
            try:
                summary = {
                    "command": command,
                    "files_found": len(file_results) if 'file_results' in locals() else 0,
                    "live_frames": len(live_results) if 'live_results' in locals() else 0
                }

                await self.master.seed_ai.submit(str(summary))

            except Exception as e:
                self.cli_output.insert("end", f"[AI FEEDBACK ERROR] {e}\n")

        self.cli_output.see("end")

    # ------------------------ Object Grouping ------------------------
    def _update_groups(self, objects: List[Dict]):
        for obj in objects:
            assigned = False
            for group_id, group_objs in self.object_groups.items():
                for gobj in group_objs:
                    if self._iou(obj['bbox'], gobj['bbox']) > 0.3:
                        obj['group'] = group_id
                        self.object_groups[group_id].append(obj)
                        assigned = True
                        break
                if assigned:
                    break
            if not assigned:
                obj['group'] = self.next_group_id
                self.object_groups[self.next_group_id] = [obj]
                self.next_group_id += 1

    def _iou(self, bbox1, bbox2):
        x1 = max(bbox1[0], bbox2[0])
        y1 = max(bbox1[1], bbox2[1])
        x2 = min(bbox1[2], bbox2[2])
        y2 = min(bbox1[3], bbox2[3])
        inter_area = max(0, x2 - x1) * max(0, y2 - y1)
        bbox1_area = (bbox1[2]-bbox1[0])*(bbox1[3]-bbox1[1])
        bbox2_area = (bbox2[2]-bbox2[0])*(bbox2[3]-bbox2[1])
        union_area = bbox1_area + bbox2_area - inter_area
        return inter_area / union_area if union_area != 0 else 0

    # ------------------------ Helpers ------------------------
    def _get_extensions(self, file_types: Optional[List[str]]) -> List[str]:
        extensions = []
        if file_types:
            for t in file_types:
                extensions.extend(self.FILE_TYPES.get(t.lower(), []))
        else:
            for exts in self.FILE_TYPES.values():
                extensions.extend(exts)
        return [ext.lower() for ext in extensions]

    def _file_contains_keyword(self, path: str, keyword_lower: str) -> bool:
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return keyword_lower in f.read().lower()
        except Exception:
            return False

    def _image_contains_keyword(self, path: str, keyword_lower: str) -> bool:
        try:
            img = Image.open(path)
            exif = img.getexif()
            for tag_id, value in exif.items():
                tag_name = ExifTags.TAGS.get(tag_id, tag_id)
                if keyword_lower in str(value).lower() or keyword_lower in str(tag_name).lower():
                    return True
            return False
        except Exception:
            return False

    async def _video_contains_keyword(self, path: str, keyword_lower: str) -> bool:
        if not ffmpeg:
            return False
        try:
            probe = ffmpeg.probe(path)
            for stream in probe.get('streams', []):
                for k, v in stream.items():
                    if keyword_lower in str(v).lower() or keyword_lower in str(k).lower():
                        return True
            for tag, value in probe.get('format', {}).get('tags', {}).items():
                if keyword_lower in str(value).lower() or keyword_lower in str(tag).lower():
                    return True
            return False
        except Exception:
            return False

    def _determine_type(self, path: str) -> str:
        ext = Path(path).suffix.lower()
        for t, exts in self.FILE_TYPES.items():
            if ext in exts:
                return t
        return "unknown"

    # ------------------------ Object Detection ------------------------
    def _detect_objects_in_image(self, path: str) -> List[Dict]:
        if not self.object_model:
            return []
        try:
            results = self.object_model(path)
            objects = []
            for res in results:
                for obj in res.boxes:
                    x1, y1, x2, y2 = obj.xyxy[0].tolist()
                    objects.append({
                        "label": obj.cls.item() if hasattr(obj, 'cls') else 'unknown',
                        "confidence": float(obj.conf[0]) if hasattr(obj, 'conf') else 0.0,
                        "bbox": (x1, y1, x2, y2),
                        "highlight": "square",
                        "group": None
                    })
            return objects
        except Exception:
            return []

    def _detect_objects_on_frame(self, frame) -> List[Dict]:
        if not self.object_model:
            return []
        try:
            results = self.object_model(frame)
            objects = []
            for res in results:
                for obj in res.boxes:
                    x1, y1, x2, y2 = obj.xyxy[0].tolist()
                    objects.append({
                        "label": obj.cls.item() if hasattr(obj, 'cls') else 'unknown',
                        "confidence": float(obj.conf[0]) if hasattr(obj, 'conf') else 0.0,
                        "bbox": (x1, y1, x2, y2),
                        "highlight": "square",
                        "group": None
                    })
            return objects
        except Exception:
            return []

    # ------------------------ OCR ------------------------
    def _ocr_image(self, path: str, keyword_lower: str) -> List[Dict]:
        if not pytesseract or not Image:
            return []
        try:
            img = Image.open(path)
            data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
            results = []
            for i, text in enumerate(data['text']):
                if keyword_lower in text.lower():
                    x, y, w, h = data['left'][i], data['top'][i], data['width'][i], data['height'][i]
                    results.append({
                        "text": text,
                        "bbox": (x, y, x + w, y + h),
                        "highlight": "circle",
                        "group": None
                    })
            return results
        except Exception:
            return []

    def _ocr_frame(self, frame, keyword_lower: str) -> List[Dict]:
        if not pytesseract or not Image:
            return []
        try:
            img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(img_rgb)
            data = pytesseract.image_to_data(pil_img, output_type=pytesseract.Output.DICT)
            results = []
            for i, text in enumerate(data['text']):
                if keyword_lower in text.lower():
                    x, y, w, h = data['left'][i], data['top'][i], data['width'][i], data['height'][i]
                    results.append({
                        "text": text,
                        "bbox": (x, y, x + w, y + h),
                        "highlight": "circle",
                        "group": None
                    })
            return results
        except Exception:
            return []
