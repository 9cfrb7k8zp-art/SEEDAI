# ========================================================================
# File: live_search_hud.py
# Path: seed/systemutils/live_search_hud.py
# V0.1 - Full Live SEED HUD Integration
# Purpose:
#   - Combines SearchEngine + HUDOverlay
#   - Live camera/video feed scanning with object detection and OCR
#   - Interactive HUD with click-to-assign pointers and group visualization
# ========================================================================

import asyncio
from seed.systemutils.search_engine import SearchEngine
from seed.systemutils.hud_overlay import HUDOverlay

async def main_live_search():
    # Initialize SearchEngine with SEED_ROOT path
    search_engine = SearchEngine(root_paths="C:/SEED_ROOT")

    # Initialize HUD overlay window
    hud = HUDOverlay(window_name="SEED Live HUD")

    # Pointer assignment callback
    def pointer_callback(pointer_id, obj):
        print(f"[HUD] Pointer {pointer_id} assigned to object: {obj.get('label', obj.get('text', 'unknown'))}")

    hud.set_pointer_callback(pointer_callback)

    # Frame callback for HUD rendering
    def frame_callback(frame, objects):
        hud.render(frame, objects)

    # Run live stream search (camera 0, keyword optional)
    try:
        results = await search_engine.search_live_stream(
            source=0,              # Use 0 for default camera
            keyword=None,          # Optional keyword for OCR
            detect_objects=True,
            ocr_text=True,
            max_frames=1000,       # Adjust number of frames as needed
            pointer_callback=frame_callback
        )
    finally:
        hud.close()

    # Print summary of results
    print("[LIVE SEARCH COMPLETE]")
    for frame_data in results:
        frame_number = frame_data.get("frame")
        num_objects = len(frame_data.get("objects", []))
        num_groups = len(frame_data.get("groups", {}))
        num_pointers = len(frame_data.get("pointers", {}))
        print(f"Frame {frame_number}: {num_objects} objects, {num_groups} groups, {num_pointers} pointers")

if __name__ == "__main__":
    asyncio.run(main_live_search())
