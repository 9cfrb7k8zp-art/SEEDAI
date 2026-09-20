import numpy as np
import time
from collections import deque

class QbitIngestEngine:
    """
    Generic Qbit ingest engine for real-time devices.
    Converts input streams into Qbit markers with freq/amp/phase.
    """

    def __init__(self, max_len=200):
        self.max_len = max_len
        self.channels = {}  # {"mic": deque([...]), "camera": deque([...])}
        self.markers = {}   # Qbit markers per channel

    def register_channel(self, name):
        if name not in self.channels:
            self.channels[name] = deque([0.0]*self.max_len, maxlen=self.max_len)
            self.markers[name] = []

    def push_sample(self, channel, value):
        if channel not in self.channels:
            self.register_channel(channel)
        self.channels[channel].append(value)
        # Compute simple Qbit state
        freq = np.abs(value) * 100  # placeholder mapping
        amp = np.abs(value)
        phase = (time.time() % 1) * 360
        self.markers[channel].append({
            "pos": len(self.channels[channel])-1,
            "freq": freq,
            "amp": amp,
            "phase": phase,
            "alpha": 1.0
        })
        # Keep markers limited
        self.markers[channel] = [m for m in self.markers[channel] if m["alpha"] > 0]

    def get_waveform(self, channel):
        return list(self.channels.get(channel, []))

    def get_markers(self, channel):
        return self.markers.get(channel, [])
