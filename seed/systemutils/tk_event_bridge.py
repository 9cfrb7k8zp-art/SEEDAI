# File: tk_event_bridge.py
# Path: seed/systemutils/tk_event_bridge.py
#
#         root    : tk.Tk instance (main thread only)
#        handler : callable(event_name, payload)
#        poll_ms : how often to poll queue
#
# ======================================================================

import queue
import logging

logger = logging.getLogger("TkEventBridge")

class TkEventBridge:

    def __init__(self, root, handler, poll_ms=50):
        self.root = root
        self.handler = handler
        self.poll_ms = poll_ms
        self.queue = queue.Queue()
        self._running = False

    def start(self):
        if self.root is None:
            print("[TkEventBridge] Start deferred (no root)")
            return
        self._poll()

    def stop(self):
        self._running = False

    def emit(self, event_name, payload=None):

        self.queue.put((event_name, payload))


    def _poll(self):
        if not self._running:
            return
        try:
            while True:
                event_name, payload = self.queue.get_nowait()
                try:
                    self.handler(event_name, payload)
                except Exception as e:
                    logger.exception(f"TkEvent handler error: {e}")
        except queue.Empty:
            pass

        if self.root is None:
            print("[TkEventBridge] Poll skipped (root detached)")
            return
        self.root.after(self.poll_ms, self._poll)

