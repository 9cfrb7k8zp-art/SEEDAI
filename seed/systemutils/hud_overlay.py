# ========================================================================
# File: hud_overlay.py
# Path: seed/systemutils/hud_overlay.py
# V0.1 - HUD Overlay Helper for SearchEngine
# Purpose:
#   - Real-time display of live camera/video feed
#   - Highlight objects (squares) and OCR text (circles)
#   - Click-to-assign pointer IDs
#   - Dynamic object grouping visualization
# ========================================================================

import cv2
from typing import List, Dict, Callable, Optional

class HUDOverlay:
    def __init__(self, window_name: str = "SEED HUD"):
        self.window_name = window_name
        self.pointer_next_id = 1
        self.click_assign_callback: Optional[Callable] = None
        self.pointer_assignments: Dict[int, Dict] = {}  # pointer_id -> object

        # Set mouse callback
        cv2.namedWindow(self.window_name)
        cv2.setMouseCallback(self.window_name, self._on_mouse_click)

    def set_pointer_callback(self, callback: Callable):
        """
        Set callback function for pointer assignments.
        Called as callback(pointer_id, object_info)
        """
        self.click_assign_callback = callback

    def _on_mouse_click(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            # Find nearest object under click
            frame_objects = param if param else []
            for obj in frame_objects:
                x1, y1, x2, y2 = obj.get("bbox", (0,0,0,0))
                if x1 <= x <= x2 and y1 <= y <= y2:
                    pointer_id = self.pointer_next_id
                    self.pointer_next_id += 1
                    self.pointer_assignments[pointer_id] = obj
                    obj['pointer'] = pointer_id
                    if self.click_assign_callback:
                        self.click_assign_callback(pointer_id, obj)
                    break

    def render(self, frame, objects: List[Dict]):
        """
        Draw HUD overlays on frame:
        - Squares for object detections
        - Circles for OCR highlights
        - Pointer IDs
        """
        for obj in objects:
            x1, y1, x2, y2 = obj.get("bbox", (0,0,0,0))
            highlight = obj.get("highlight", "square")
            group_id = obj.get("group", None)
            pointer_id = obj.get("pointer", None)

            color = (0, 255, 0)  # default green
            if group_id:
                # Group color: vary by group
                color = ((group_id*50)%255, (group_id*80)%255, (group_id*120)%255)

            if highlight == "square":
                cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), color, 2)
            elif highlight == "circle":
                center = ((int(x1+x2)//2), (int(y1+y2)//2))
                radius = max(int((x2-x1)/2), int((y2-y1)/2))
                cv2.circle(frame, center, radius, color, 2)

            # Draw pointer ID if exists
            if pointer_id:
                cv2.putText(frame, f"P{pointer_id}", (int(x1), int(y1)-5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,0,0), 2)

        cv2.imshow(self.window_name, frame)

    def close(self):
        cv2.destroyWindow(self.window_name)

# ------------------------ Example usage ------------------------
# async def pointer_callback(pointer_id, obj):
#     print(f"Pointer {pointer_id} assigned to object: {obj}")

# hud = HUDOverlay()
# hud.set_pointer_callback(pointer_callback)

# def frame_callback(frame, objects):
#     hud.render(frame, objects)

# await search_engine.search_live_stream(
#     source=0,
#     keyword="target",
#     pointer_callback=frame_callback
# )
# hud.close()
