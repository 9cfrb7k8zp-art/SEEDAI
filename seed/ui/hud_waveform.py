# ==========================================================
# FILE: hud_waveform.py
# ==========================================================

import time
import threading
from collections import deque
from typing import Dict, Any

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation


class HUDWaveformRenderer:

    def __init__(
        self,
        event_bus,
        buffer_size=512,
        fps=30
    ):
        self.event_bus = event_bus
        self.buffer_size = buffer_size
        self.fps = fps

        # Rolling buffers
        self.amp_buffer = deque(maxlen=buffer_size)
        self.freq_buffer = deque(maxlen=buffer_size)
        self.time_buffer = deque(maxlen=buffer_size)

        self._lock = threading.Lock()
        self._running = False

        # Subscribe to FAT stream
        self.event_bus.subscribe("HUD_FAT_EVENT", self._on_fat_event)

    # --------------------------------------------------
    # FAT ingest
    # --------------------------------------------------
    def _on_fat_event(self, entry: Dict[str, Any]):
        if entry.get("source") != "audio":
            return

        data = entry.get("data", {})
        amp = float(data.get("amp", 0.0))
        freq = float(data.get("freq", 0.0))
        ts = entry.get("timestamp", time.time())

        with self._lock:
            self.amp_buffer.append(amp)
            self.freq_buffer.append(freq)
            self.time_buffer.append(ts)

    # --------------------------------------------------
    # HUD render
    # --------------------------------------------------
    def start(self):
        if self._running:
            return

        self._running = True
        thread = threading.Thread(target=self._run_plot, daemon=True)
        thread.start()

    def stop(self):
        self._running = False

    def _run_plot(self):
        plt.style.use("dark_background")

        fig, (ax_wave, ax_freq) = plt.subplots(
            2, 1, figsize=(10, 6)
        )

        wave_line, = ax_wave.plot([], [], lw=1)
        freq_bar = ax_freq.bar([0], [0], width=0.5)

        ax_wave.set_ylim(-0.01, 0.01)
        ax_wave.set_title("Audio Amplitude (Waveform)")
        ax_wave.set_xlabel("Samples")
        ax_wave.set_ylabel("Amplitude")

        ax_freq.set_ylim(0, 5000)
        ax_freq.set_title("Dominant Frequency (Hz)")
        ax_freq.set_xticks([])

        def update(_):
            if not self._running:
                return wave_line,

            with self._lock:
                amps = np.array(self.amp_buffer)
                freqs = np.array(self.freq_buffer)

            if len(amps) == 0:
                return wave_line,

            x = np.arange(len(amps))
            wave_line.set_data(x, amps)
            ax_wave.set_xlim(0, len(amps))

            if len(freqs) > 0:
                freq_bar[0].set_height(freqs[-1])

            return wave_line, freq_bar

        ani = animation.FuncAnimation(
            fig,
            update,
            interval=1000 / self.fps,
            blit=False
        )

        plt.tight_layout()
        plt.show()
