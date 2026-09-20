# ==========================================================
# FILE: Render.py
# PATH: SEED_ROOT/seed/systemutils/Render.py
#
# VERSION: 4.0
# BUILD:
#   L3-CONTROL-CONNECTED /
#   HUD-PRESENTATION-SINK /
#   TRACK-AWARE /
#   QBIT-AWARE /
#   PROJECTOR-READY /
#   SINGLE-RUNTIME
#
# ==========================================================
#
# SEED Unified Render Engine
#
# ROLE:
#   Presentation / visualization / render sink.
#
# L3 CONNECTION:
#
#   TrackContext
#        |
#        v
#   TrackIDManager
#        |
#        v
#   TrackSystem
#        |
#        v
#   EventBus
#        |
#        +--------------------+
#        |                    |
#        v                    v
#   QbitDialer             Render
#        |                    |
#        v                    v
#   QbitQueueLoop         HUD / 3D / ART
#        |
#        v
#     Result
#        |
#        v
#     EventBus
#        |
#        v
#   TrackSystem feedback
#
# IMPORTANT:
#
# Render NEVER:
#   - creates Qbits
#   - creates QbitDialer
#   - creates QbitQueueLoop
#   - executes commands
#   - submits commands
#   - controls boot
#   - controls shutdown
#   - overrides Oracle
#   - overrides TrackSystem
#   - controls L3
#
# Render receives L3/system data and presents it.
#
# ==========================================================

from __future__ import annotations

import time
import math
import threading
import logging

from collections import deque
from copy import deepcopy

from typing import (
    Dict,
    Any,
    Optional,
    List,
    Callable,
)

from seed.core.qbit.qbit_encoder import QbitEncoder


# ==========================================================
# LOGGER
# ==========================================================

logger = logging.getLogger(
    "SEED.Render"
)

logger.setLevel(
    logging.INFO
)


# ==========================================================
# CONSTANTS
# ==========================================================

DEFAULT_FPS = 30

EQ_BANDS = 15

PERSIST_HISTORY = 120

MAX_L3_HISTORY = 256

MAX_OUTPUT_HISTORY = 256


BASE_COLORS = {
    "red": (255, 0, 0),
    "blue": (0, 0, 255),
    "yellow": (255, 255, 0),
}


# ==========================================================
# RENDER MODES
# ==========================================================

class RenderMode:

    STATIC = "static"

    DOT_MATRIX = "dot_matrix"

    WAVE = "wave"

    MULTI = "multi"

    ART_3D = "art_3d"


# ==========================================================
# RENDER FRAME
# ==========================================================

class RenderFrame:

    def __init__(
        self,
        *,
        track_id: Optional[str] = None,
        source: Optional[str] = None,
        stage: Optional[str] = None,
        channel: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):

        self.timestamp = time.time()

        self.track_id = track_id

        self.source = source

        self.stage = stage

        self.channel = channel

        self.metadata = dict(
            metadata or {}
        )

        self.layers: List[
            Dict[str, Any]
        ] = []

    def add_layer(
        self,
        layer: Dict[str, Any],
    ) -> None:

        if not isinstance(
            layer,
            dict,
        ):
            return

        self.layers.append(
            layer
        )

    def serialize(
        self,
    ) -> Dict[str, Any]:

        return {
            "timestamp": self.timestamp,

            "track_id": self.track_id,

            "source": self.source,

            "stage": self.stage,

            "channel": self.channel,

            "metadata": deepcopy(
                self.metadata
            ),

            "layers": deepcopy(
                self.layers
            ),
        }


# ==========================================================
# BACKEND REGISTRY
# ==========================================================

class RenderBackendRegistry:

    def __init__(self):

        self.backends: Dict[
            str,
            Callable[
                [Dict[str, Any]],
                None,
            ],
        ] = {}

        self._lock = threading.RLock()

    def register(
        self,
        name: str,
        handler: Callable[
            [Dict[str, Any]],
            None,
        ],
    ) -> None:

        if not callable(handler):
            raise TypeError(
                "Render backend handler must be callable"
            )

        with self._lock:

            self.backends[
                name
            ] = handler

        logger.info(
            "[RenderBackend] Registered: %s",
            name,
        )

    def unregister(
        self,
        name: str,
    ) -> bool:

        with self._lock:

            if name not in self.backends:
                return False

            del self.backends[
                name
            ]

        return True

    def emit(
        self,
        payload: Dict[str, Any],
    ) -> None:

        with self._lock:

            backends = list(
                self.backends.items()
            )

        for name, handler in backends:

            try:

                handler(
                    payload
                )

            except Exception:

                logger.exception(
                    "[RenderBackend] Failure: %s",
                    name,
                )


# ==========================================================
# AUDIO → EQ
# ==========================================================

class AudioEQProcessor:

    def process(
        self,
        samples: List[float],
    ) -> List[float]:

        if not samples:

            return [
                0.0
            ] * EQ_BANDS

        bands = [
            0.0
        ] * EQ_BANDS

        chunk = max(
            1,
            len(samples)
            // EQ_BANDS,
        )

        for i in range(
            EQ_BANDS
        ):

            seg = samples[
                i * chunk:
                (i + 1) * chunk
            ]

            if seg:

                energy = (
                    sum(
                        abs(v)
                        for v in seg
                    )
                    / len(seg)
                )

                bands[i] = min(
                    1.0,
                    energy,
                )

        return bands


# ==========================================================
# VISUAL ENGINES
# ==========================================================

class DotMatrixEngine:

    def generate(
        self,
        eq: List[float],
    ) -> List[
        Dict[str, float]
    ]:

        return [
            {
                "x": i,
                "y": v,
                "intensity": v,
            }

            for i, v in enumerate(eq)
        ]


class WaveEngine:

    def generate(
        self,
        eq: List[float],
        t: float,
    ) -> List[
        Dict[str, float]
    ]:

        return [
            {
                "x": i,
                "y": math.sin(
                    t * 2 + i
                ) * v,
            }

            for i, v in enumerate(eq)
        ]


# ==========================================================
# ART / 3D ENGINE
# ==========================================================

class Art3DEngine:

    def __init__(self):

        self.orientation = {
            "roll": 0.0,
            "pitch": 0.0,
            "yaw": 0.0,
        }

        self.scale = 1.0

        self.camera_distance = 20.0

    def set_orientation(
        self,
        roll: float,
        pitch: float,
        yaw: float,
    ):

        self.orientation[
            "roll"
        ] = float(roll)

        self.orientation[
            "pitch"
        ] = float(pitch)

        self.orientation[
            "yaw"
        ] = float(yaw)

    def transform_point(
        self,
        x: float,
        y: float,
        z: float,
    ):

        r = math.radians(
            self.orientation["roll"]
        )

        p = math.radians(
            self.orientation["pitch"]
        )

        y_ = math.radians(
            self.orientation["yaw"]
        )

        # --------------------------------------------------
        # ROLL
        # --------------------------------------------------

        x1 = x

        y1 = (
            y * math.cos(r)
            - z * math.sin(r)
        )

        z1 = (
            y * math.sin(r)
            + z * math.cos(r)
        )

        # --------------------------------------------------
        # PITCH
        # --------------------------------------------------

        x2 = (
            x1 * math.cos(p)
            + z1 * math.sin(p)
        )

        y2 = y1

        z2 = (
            -x1 * math.sin(p)
            + z1 * math.cos(p)
        )

        # --------------------------------------------------
        # YAW
        # --------------------------------------------------

        x3 = (
            x2 * math.cos(y_)
            - y2 * math.sin(y_)
        )

        y3 = (
            x2 * math.sin(y_)
            + y2 * math.cos(y_)
        )

        z3 = z2

        return (
            x3 * self.scale,
            y3 * self.scale,
            z3 * self.scale,
        )

    def project_to_2d(
        self,
        x: float,
        y: float,
        z: float,
        width: int = 1920,
        height: int = 1080,
    ):

        z += (
            self.camera_distance
            + 0.001
        )

        factor = (
            self.camera_distance
            / z
        )

        screen_x = (
            width / 2
            + x
            * factor
            * width
            / 2
        )

        screen_y = (
            height / 2
            - y
            * factor
            * height
            / 2
        )

        return (
            screen_x,
            screen_y,
        )

    def generate_shapes(
        self,
        eq: List[float],
        t: float,
        projector: bool = True,
    ) -> List[
        Dict[str, float]
    ]:

        points = []

        for i, v in enumerate(eq):

            theta = (
                t
                + i * 0.2
            )

            r = v * 5.0

            x = (
                r
                * math.cos(theta)
            )

            y = (
                r
                * math.sin(theta)
            )

            z = v * 2.0

            tx, ty, tz = (
                self.transform_point(
                    x,
                    y,
                    z,
                )
            )

            if projector:

                sx, sy = (
                    self.project_to_2d(
                        tx,
                        ty,
                        tz,
                    )
                )

            else:

                sx, sy = (
                    tx,
                    ty,
                )

            points.append(
                {
                    "x": tx,
                    "y": ty,
                    "z": tz,
                    "screen_x": sx,
                    "screen_y": sy,
                    "intensity": v,
                }
            )

        return points


# ==========================================================
# EMOTION → COLOR
# ==========================================================

class EmotionColorMapper:

    def apply(
        self,
        colors: Dict[str, tuple],
        state: Dict[str, Any],
    ) -> Dict[str, tuple]:

        mood = state.get(
            "mood",
            "neutral",
        )

        scale = {
            "calm": 0.8,
            "focused": 1.0,
            "alert": 1.2,
            "critical": 1.5,
        }.get(
            mood,
            1.0,
        )

        return {
            k: tuple(
                min(
                    255,
                    int(
                        c * scale
                    ),
                )

                for c in rgb
            )

            for k, rgb in colors.items()
        }


# ==========================================================
# PERSISTENT VISUAL MEMORY
# ==========================================================

class RenderMemory:

    def __init__(self):

        self.history = deque(
            maxlen=PERSIST_HISTORY
        )

        self._lock = threading.RLock()

    def store(
        self,
        frame: Dict[str, Any],
    ):

        with self._lock:

            self.history.append(
                deepcopy(frame)
            )

    def snapshot(
        self,
    ) -> List[
        Dict[str, Any]
    ]:

        with self._lock:

            return deepcopy(
                list(
                    self.history
                )
            )


# ==========================================================
# BACKENDS
# ==========================================================

def gpu_backend_stub(
    payload: Dict[str, Any],
):

    # Presentation backend only.
    return None


def web_backend_stub(
    payload: Dict[str, Any],
):

    # Presentation backend only.
    return None


# ==========================================================
# RENDER ENGINE
# ==========================================================

class Render:

    VERSION = "4.0"

    ROLE = "presentation"

    CONTROL_LAYER = "L3"

    COMMAND_AUTHORITY = "QbitDialer"

    TRANSPORT_AUTHORITY = (
        "QbitQueueLoop"
    )

    # ======================================================
    # INIT
    # ======================================================

    def __init__(
        self,
        fps: int = DEFAULT_FPS,
        event_bus: Optional[Any] = None,
        storage_root=None,
        camera_qbit: Optional[Any] = None,
        output_channel: Optional[
            Callable[
                [Dict[str, Any]],
                None,
            ]
        ] = None,

        # --------------------------------------------------
        # EXISTING SYSTEM REFERENCES
        # --------------------------------------------------

        control_layer=None,
        track_system=None,
        registry=None,
        registry_runtime=None,
        neural_bridge=None,
        oracle=None,
        qbit_dialer=None,
        qbit_queue_loop=None,
        runtime_context=None,
        hud_manager=None,
        hud_view=None,

        # --------------------------------------------------
        # OPTIONAL PRESENTATION CALLBACK
        # --------------------------------------------------

        hud_output: Optional[
            Callable[
                [Dict[str, Any]],
                None,
            ]
        ] = None,
    ):

        # ==================================================
        # EXISTING REFERENCES
        # ==================================================

        self.event_bus = event_bus

        self.storage_root = (
            storage_root
        )

        self.camera_qbit = (
            camera_qbit
        )

        self.control_layer = (
            control_layer
        )

        self.track_system = (
            track_system
        )

        self.registry = (
            registry
        )

        self.registry_runtime = (
            registry_runtime
        )

        self.neural_bridge = (
            neural_bridge
        )

        self.oracle = (
            oracle
        )

        self.qbit_dialer = (
            qbit_dialer
        )

        self.qbit_queue_loop = (
            qbit_queue_loop
        )

        self.runtime_context = (
            runtime_context
        )

        self.hud_manager = (
            hud_manager
        )

        self.hud_view = (
            hud_view
        )

        self.hud_output = (
            hud_output
        )

        # ==================================================
        # RENDER CONFIG
        # ==================================================

        self.fps = max(
            1,
            int(fps),
        )

        self.interval = (
            1.0 / self.fps
        )

        # ==================================================
        # LIFECYCLE
        # ==================================================

        self.running = False

        self.thread: Optional[
            threading.Thread
        ] = None

        self.stop_event = (
            threading.Event()
        )

        self.lock = (
            threading.RLock()
        )

        # ==================================================
        # RENDER STATE
        # ==================================================

        self.render_mode = (
            RenderMode.STATIC
        )

        self.eq_bands = [
            0.0
        ] * EQ_BANDS

        # ==================================================
        # SYSTEM STATE
        # ==================================================

        self.system_status: Dict[
            str,
            Any
        ] = {}

        self.menu_state: Dict[
            str,
            Any
        ] = {}

        self.l3_state: Dict[
            str,
            Any
        ] = {}

        self.qbit_state: Dict[
            str,
            Any
        ] = {}

        self.track_state: Dict[
            str,
            Any
        ] = {}

        self.oracle_state: Dict[
            str,
            Any
        ] = {}

        self.registry_state: Dict[
            str,
            Any
        ] = {}

        # ==================================================
        # DYNAMIC HUD CONTENT
        # ==================================================

        self.hud_content: Any = None

        self.hud_content_type = (
            None
        )

        self.hud_content_metadata: Dict[
            str,
            Any
        ] = {}

        self.output_history = deque(
            maxlen=MAX_OUTPUT_HISTORY
        )

        self.l3_history = deque(
            maxlen=MAX_L3_HISTORY
        )

        # ==================================================
        # BUFFERS
        # ==================================================

        self.audio_buffer = deque(
            maxlen=2048
        )

        self.video_buffer = deque(
            maxlen=4
        )

        # ==================================================
        # ENGINES
        # ==================================================

        self.eq_processor = (
            AudioEQProcessor()
        )

        self.dot_engine = (
            DotMatrixEngine()
        )

        self.wave_engine = (
            WaveEngine()
        )

        self.art_engine = (
            Art3DEngine()
        )

        self.emotion_mapper = (
            EmotionColorMapper()
        )

        self.memory = (
            RenderMemory()
        )

        # ==================================================
        # BACKENDS
        # ==================================================

        self.backends = (
            RenderBackendRegistry()
        )

        # Binary Qbit decoder belongs at the presentation boundary.
        self.qbit_encoder = QbitEncoder(
            track_system=track_system,
            qbit_dialer=qbit_dialer,
            qbit_queue_loop=qbit_queue_loop,
        )

        if output_channel:

            self.backends.register(
                "default",
                output_channel,
            )

        self.backends.register(
            "gpu_stub",
            gpu_backend_stub,
        )

        self.backends.register(
            "web_stub",
            web_backend_stub,
        )

        # ==================================================
        # EVENT BUS
        # ==================================================

        if self.event_bus:

            self._bind_event_bus()

        logger.info(
            "[Render] L3 presentation sink READY | "
            "authority=%s | transport=%s",
            self.COMMAND_AUTHORITY,
            self.TRANSPORT_AUTHORITY,
        )

    # ======================================================
    # EVENT BUS
    # ======================================================

    def _bind_event_bus(
        self,
    ):

        subscriptions = {

            # Existing renderer inputs.
            "audio": self.feed_audio,

            "VOICE_OUTPUT": self.ingest_voice_output,
            "voice.output": self.ingest_voice_output,

            "system_status": (
                self.update_system_status
            ),

            "render_mode": (
                self.set_render_mode
            ),

            # L3 / Track flow.
            "TRACK_PACKET": (
                self.ingest_track_packet
            ),

            "TRACK_QBIT_REQUEST": (
                self.ingest_track_packet
            ),

            # Qbit result / feedback.
            "QBIT_RESULT": (
                self.ingest_qbit_output
            ),

            "QBIT_OUTPUT": (
                self.ingest_qbit_output
            ),

            "QBIT_FEEDBACK": (
                self.ingest_qbit_output
            ),

            # HUD/system output.
            "HUD_OUTPUT": (
                self.ingest_hud_output
            ),

            "hud.output": (
                self.ingest_hud_output
            ),

            "hud.activity": (
                self.ingest_hud_output
            ),

            # Runtime state.
            "L3_STATE": (
                self.update_l3_state
            ),

            "CONTROL_STATE": (
                self.update_l3_state
            ),

            # Registry.
            "REGISTRY_STATE": (
                self.update_registry_state
            ),

            # Oracle is observational.
            "ORACLE_STATE": (
                self.update_oracle_state
            ),

            # Camera.
            "camera": (
                self.feed_video
            ),

            "camera_feed": (
                self.feed_video
            ),
        }

        for event_name, callback in (
            subscriptions.items()
        ):

            try:

                subscribe = getattr(
                    self.event_bus,
                    "subscribe",
                    None,
                )

                if not callable(
                    subscribe
                ):
                    raise RuntimeError(
                        "EventBus missing subscribe()"
                    )

                subscribe(
                    event_name,
                    callback,
                )

                logger.debug(
                    "[Render] EventBus subscribed: %s",
                    event_name,
                )

            except Exception:

                logger.debug(
                    "[Render] EventBus subscription unavailable: %s",
                    event_name,
                    exc_info=True,
                )

        logger.info(
            "[Render] EventBus L3 bindings established"
        )

    # ======================================================
    # L3 STATE
    # ======================================================

    def update_l3_state(
        self,
        state: Optional[
            Dict[str, Any]
        ],
    ):

        if not isinstance(
            state,
            dict,
        ):
            return False

        with self.lock:

            self.l3_state.update(
                deepcopy(state)
            )

            self.l3_history.append(
                {
                    "timestamp": time.time(),
                    "state": deepcopy(state),
                }
            )

        self._publish_hud(
            {
                "type": "l3_state",
                "data": deepcopy(state),
                "track_id": state.get(
                    "track_id"
                ),
                "source": state.get(
                    "source",
                    "L3",
                ),
            }
        )

        return True

    # ======================================================
    # TRACK PACKET
    # ======================================================

    def ingest_track_packet(
        self,
        packet: Optional[
            Dict[str, Any]
        ],
    ):

        if not isinstance(
            packet,
            dict,
        ):
            return False

        track_id = (
            packet.get("track_id")
        )

        metadata = (
            packet.get("metadata")
            or {}
        )

        with self.lock:

            self.track_state = (
                deepcopy(packet)
            )

        # --------------------------------------------------
        # Preserve L3 identity and routing information.
        # --------------------------------------------------

        self.l3_state.update(
            {
                "track_id": track_id,

                "packet_id": packet.get(
                    "packet_id"
                ),

                "sequence": packet.get(
                    "sequence"
                ),

                "channel": packet.get(
                    "channel"
                ),

                "state": packet.get(
                    "state"
                ),

                "stage": packet.get(
                    "stage"
                ),

                "input_type": packet.get(
                    "input_type"
                ),

                "output_type": packet.get(
                    "output_type"
                ),

                "priority": packet.get(
                    "priority"
                ),

                "source": packet.get(
                    "source",
                    "TrackSystem",
                ),

                "flow": deepcopy(
                    packet.get(
                        "flow"
                    )
                    or {}
                ),

                "metadata": deepcopy(
                    metadata
                ),
            }
        )

        self._publish_hud(
            {
                "type": "track",
                "track_id": track_id,
                "source": "TrackSystem",
                "stage": packet.get(
                    "stage"
                ),
                "channel": packet.get(
                    "channel"
                ),
                "data": deepcopy(
                    packet
                ),
            }
        )

        return True

    # ======================================================
    # QBIT OUTPUT
    # ======================================================

    def ingest_qbit_output(
        self,
        payload: Optional[
            Dict[str, Any]
        ],
    ):

        if payload is None:
            return False

        if isinstance(
            payload,
            dict,
        ):

            data = deepcopy(
                payload
            )

            self.qbit_state.update(
                data
            )

            track_id = data.get(
                "track_id"
            )

            source = data.get(
                "source",
                "QbitDialer",
            )

        else:

            data = payload

            track_id = None

            source = (
                "QbitDialer"
            )

        output = {
            "type": "qbit",
            "source": source,
            "track_id": track_id,
            "data": data,
            "timestamp": time.time(),
        }

        self.output_history.append(
            deepcopy(output)
        )

        self._publish_hud(
            output
        )

        return True

    # ======================================================
    # VOICE OVERLAY
    # ======================================================

    def ingest_voice_output(
        self,
        payload: Optional[Dict[str, Any]],
    ):
        if isinstance(payload, dict):
            data = deepcopy(payload)
            text = data.get("text", "")
        else:
            data = {"text": str(payload or "")}
            text = data["text"]
        self.set_hud_content(
            data,
            content_type="voice_overlay",
            metadata={"source": "SEEDVoiceSystem", "voice_text": text},
        )
        self.output_history.append({
            "type": "VOICE_OUTPUT",
            "text": text,
            "timestamp": time.time(),
        })
        return True

    # ======================================================
    # HUD OUTPUT
    # ======================================================

    def ingest_hud_output(
        self,
        payload: Optional[
            Dict[str, Any]
        ],
    ):

        if payload is None:
            return False

        if isinstance(
            payload,
            dict,
        ):

            data = deepcopy(
                payload
            )

            track_id = data.get(
                "track_id"
            )

            source = data.get(
                "source",
                "HUD",
            )

            content_type = data.get(
                "content_type",
                data.get(
                    "type",
                    "output",
                ),
            )

        else:

            data = payload

            track_id = None

            source = "HUD"

            content_type = "output"

        self.set_hud_content(
            data,
            content_type=content_type,
            metadata={
                "source": source,
                "track_id": track_id,
                "timestamp": time.time(),
            },
            track_id=track_id,
            source_id=source,
        )

        return True

    # ======================================================
    # DYNAMIC HUD CONTENT
    # ======================================================

    def set_hud_content(
        self,
        content,
        *,
        content_type=None,
        metadata=None,
        track_id=None,
        source_id=None,
    ):

        metadata = dict(
            metadata or {}
        )

        if track_id is not None:

            metadata[
                "track_id"
            ] = track_id

        if source_id is not None:

            metadata[
                "source_id"
            ] = source_id

        metadata.setdefault(
            "timestamp",
            time.time(),
        )

        with self.lock:

            self.hud_content = (
                deepcopy(content)
            )

            self.hud_content_type = (
                content_type
                or type(content).__name__
            )

            self.hud_content_metadata = (
                deepcopy(metadata)
            )

            self.output_history.append(
                {
                    "type": (
                        self.hud_content_type
                    ),
                    "data": deepcopy(
                        content
                    ),
                    "metadata": deepcopy(
                        metadata
                    ),
                    "timestamp": time.time(),
                }
            )

        # --------------------------------------------------
        # Dynamic HUDView connection.
        #
        # HUDView is presentation-only.
        # --------------------------------------------------

        view = self.hud_view

        if view is not None:

            try:

                setter = getattr(
                    view,
                    "set_content",
                    None,
                )

                if callable(setter):

                    setter(
                        content,
                        content_type=(
                            content_type
                        ),
                        metadata=metadata,
                        track_id=track_id,
                        source_id=source_id,
                    )

            except Exception:

                logger.exception(
                    "[Render] HUDView content update failed"
                )

        self._publish_hud(
            {
                "type": "content",
                "data": deepcopy(
                    content
                ),
                "content_type": (
                    self.hud_content_type
                ),
                "metadata": deepcopy(
                    metadata
                ),
                "track_id": track_id,
                "source": source_id,
            }
        )

        return True

    # ======================================================
    # HUD PRESENTATION OUTPUT
    # ======================================================

    def _publish_hud(
        self,
        payload: Dict[str, Any],
    ):

        if not isinstance(
            payload,
            dict,
        ):
            return False

        payload = deepcopy(
            payload
        )

        payload.setdefault(
            "timestamp",
            time.time(),
        )

        payload.setdefault(
            "render",
            True,
        )

        payload.setdefault(
            "presentation_only",
            True,
        )

        payload.setdefault(
            "command_authority",
            self.COMMAND_AUTHORITY,
        )

        payload.setdefault(
            "transport_authority",
            self.TRANSPORT_AUTHORITY,
        )

        # --------------------------------------------------
        # Direct presentation callback.
        # --------------------------------------------------

        callback = (
            self.hud_output
        )

        if callable(callback):

            try:

                callback(
                    deepcopy(payload)
                )

            except Exception:

                logger.exception(
                    "[Render] HUD output callback failed"
                )

        # --------------------------------------------------
        # Existing HUDManager.
        #
        # We only use presentation-facing methods.
        # No command submission occurs here.
        # --------------------------------------------------

        manager = (
            self.hud_manager
        )

        if manager is not None:

            for method_name in (
                "ingest",
                "publish",
                "update",
                "render",
            ):

                method = getattr(
                    manager,
                    method_name,
                    None,
                )

                if not callable(
                    method
                ):
                    continue

                try:

                    method(
                        payload
                    )

                    break

                except TypeError:

                    try:

                        method(
                            "render",
                            payload,
                        )

                        break

                    except Exception:

                        continue

                except Exception:

                    logger.debug(
                        "[Render] HUDManager "
                        "presentation method failed: %s",
                        method_name,
                        exc_info=True,
                    )

        return True

    # ======================================================
    # EXISTING FEEDS
    # ======================================================

    def feed_audio(
        self,
        samples: List[float],
    ):

        if not samples:
            return

        with self.lock:

            self.audio_buffer.extend(
                samples
            )

    def feed_video(
        self,
        frame: Any,
    ):

        with self.lock:

            self.video_buffer.append(
                frame
            )

    def update_system_status(
        self,
        status: Dict[str, Any],
    ):

        if not isinstance(
            status,
            dict,
        ):
            return

        with self.lock:

            self.system_status.update(
                deepcopy(status)
            )

        self._publish_hud(
            {
                "type": "status",
                "data": deepcopy(
                    status
                ),
                "source": "system",
            }
        )

    def update_registry_state(
        self,
        state: Dict[str, Any],
    ):

        if not isinstance(
            state,
            dict,
        ):
            return False

        with self.lock:

            self.registry_state.update(
                deepcopy(state)
            )

        return True

    def update_oracle_state(
        self,
        state: Dict[str, Any],
    ):

        if not isinstance(
            state,
            dict,
        ):
            return False

        with self.lock:

            self.oracle_state.update(
                deepcopy(state)
            )

        return True

    def update_menu(
        self,
        key: str,
        value: Any,
    ):

        with self.lock:

            self.menu_state[
                key
            ] = deepcopy(value)

    def set_render_mode(
        self,
        mode: str,
    ):

        if mode not in {
            RenderMode.STATIC,
            RenderMode.DOT_MATRIX,
            RenderMode.WAVE,
            RenderMode.MULTI,
            RenderMode.ART_3D,
        }:

            logger.warning(
                "[Render] Unknown render mode: %s",
                mode,
            )

            return False

        with self.lock:

            self.render_mode = mode

        return True

    def set_gyro_orientation(
        self,
        roll: float,
        pitch: float,
        yaw: float,
    ):

        self.art_engine.set_orientation(
            roll,
            pitch,
            yaw,
        )

    # ======================================================
    # L3 SNAPSHOT
    # ======================================================

    def _l3_snapshot(self):

        return {
            "layer": "L3",

            "control_layer": (
                self.control_layer
                is not None
            ),

            "track_system": (
                self.track_system
                is not None
            ),

            "registry": (
                self.registry
                is not None
            ),

            "registry_runtime": (
                self.registry_runtime
                is not None
            ),

            "neural_bridge": (
                self.neural_bridge
                is not None
            ),

            "oracle": (
                self.oracle
                is not None
            ),

            "qbit_dialer": (
                self.qbit_dialer
                is not None
            ),

            "qbit_queue_loop": (
                self.qbit_queue_loop
                is not None
            ),

            "track": deepcopy(
                self.track_state
            ),

            "qbit": deepcopy(
                self.qbit_state
            ),

            "state": deepcopy(
                self.l3_state
            ),

            "registry_state": deepcopy(
                self.registry_state
            ),

            "oracle_state": deepcopy(
                self.oracle_state
            ),
        }

    # ======================================================
    # LIFECYCLE
    # ======================================================

    def start(self):

        if self.running:
            return False

        self.stop_event.clear()

        self.running = True

        self.thread = (
            threading.Thread(
                target=self._loop,
                daemon=True,
                name="SEED-Render",
            )
        )

        self.thread.start()

        logger.info(
            "[Render] Started | "
            "presentation_only=True"
        )

        return True

    def stop(self):

        if not self.running:
            return False

        self.running = False

        self.stop_event.set()

        thread = self.thread

        if (
            thread is not None
            and thread.is_alive()
            and thread
            is not threading.current_thread()
        ):

            thread.join(
                timeout=2.0
            )

        self.thread = None

        logger.info(
            "[Render] Stopped"
        )

        return True

    # ======================================================
    # RENDER LOOP
    #
    # This is ONLY the rendering worker.
    #
    # It does not process commands.
    # ======================================================

    def _loop(self):

        while (
            self.running
            and not self.stop_event.is_set()
        ):

            started = time.time()

            try:

                frame = (
                    self._build_frame()
                )

                payload = (
                    frame.serialize()
                )

                self.memory.store(
                    payload
                )

                self.backends.emit(
                    payload
                )

            except Exception:

                logger.exception(
                    "[Render] Frame error"
                )

            elapsed = (
                time.time()
                - started
            )

            self.stop_event.wait(
                max(
                    0.0,
                    self.interval
                    - elapsed,
                )
            )

    # ======================================================
    # FRAME BUILD
    # ======================================================

    def _build_frame(
        self,
    ) -> RenderFrame:

        with self.lock:

            system_status = deepcopy(
                self.system_status
            )

            menu_state = deepcopy(
                self.menu_state
            )

            render_mode = (
                self.render_mode
            )

            eq_bands = list(
                self.eq_bands
            )

            video = (
                self.video_buffer[-1]
                if self.video_buffer
                else None
            )

            hud_content = deepcopy(
                self.hud_content
            )

            hud_content_type = (
                self.hud_content_type
            )

            hud_metadata = deepcopy(
                self.hud_content_metadata
            )

        # --------------------------------------------------
        # Audio
        # --------------------------------------------------

        with self.lock:

            audio_samples = list(
                self.audio_buffer
            )

        if audio_samples:

            eq_bands = (
                self.eq_processor.process(
                    audio_samples
                )
            )

            with self.lock:

                self.eq_bands = list(
                    eq_bands
                )

        # --------------------------------------------------
        # L3
        # --------------------------------------------------

        l3 = (
            self._l3_snapshot()
        )

        track_id = (
            l3.get("track", {})
            .get("track_id")
        )

        frame = RenderFrame(
            track_id=track_id,
            source="Render",
            stage="PRESENTATION",
            channel=(
                l3.get(
                    "track",
                    {},
                ).get(
                    "channel"
                )
            ),
            metadata={
                "render_version": (
                    self.VERSION
                ),

                "control_layer": "L3",

                "presentation_only": True,

                "command_authority": (
                    self.COMMAND_AUTHORITY
                ),

                "transport_authority": (
                    self.TRANSPORT_AUTHORITY
                ),
            },
        )

        # ==================================================
        # SYSTEM / L3 HUD LAYER
        # ==================================================

        frame.add_layer(
            {
                "type": "hud",

                "system": (
                    system_status
                ),

                "menu": (
                    menu_state
                ),

                "l3": l3,

                "memory_depth": len(
                    self.memory.history
                ),
            }
        )

        # ==================================================
        # DYNAMIC HUD CONTENT
        # ==================================================

        if hud_content is not None:

            frame.add_layer(
                {
                    "type": "content",

                    "content_type": (
                        hud_content_type
                    ),

                    "content": (
                        hud_content
                    ),

                    "metadata": (
                        hud_metadata
                    ),
                }
            )

        # ==================================================
        # VISUAL
        # ==================================================

        colors = (
            self._compute_colors()
        )

        colors = (
            self.emotion_mapper.apply(
                colors,
                system_status,
            )
        )

        visual = {

            "mode": render_mode,

            "colors": colors,

            "eq": list(eq_bands),
        }

        if render_mode in (
            RenderMode.DOT_MATRIX,
            RenderMode.MULTI,
        ):

            visual[
                "dots"
            ] = self.dot_engine.generate(
                eq_bands
            )

        if render_mode in (
            RenderMode.WAVE,
            RenderMode.MULTI,
        ):

            visual[
                "wave"
            ] = self.wave_engine.generate(
                eq_bands,
                time.time(),
            )

        if render_mode == (
            RenderMode.ART_3D
        ):

            visual[
                "art3d"
            ] = (
                self.art_engine.generate_shapes(
                    eq_bands,
                    time.time(),
                    projector=True,
                )
            )

        frame.add_layer(
            {
                "type": "visual",
                **visual,
            }
        )

        # ==================================================
        # CAMERA
        # ==================================================

        if self.camera_qbit:

            try:

                get_frame = getattr(
                    self.camera_qbit,
                    "get_frame",
                    None,
                )

                if callable(
                    get_frame
                ):

                    frame.add_layer(
                        {
                            "type": "camera",

                            "frame": (
                                get_frame()
                            ),

                            "track_id": (
                                track_id
                            ),
                        }
                    )

            except Exception:

                logger.debug(
                    "[Render] Camera Qbit frame unavailable",
                    exc_info=True,
                )

        elif video is not None:

            frame.add_layer(
                {
                    "type": "video",

                    "frame": video,

                    "track_id": track_id,
                }
            )

        # ==================================================
        # L3 LINEAGE LAYER
        # ==================================================

        frame.add_layer(
            {
                "type": "lineage",

                "track_id": track_id,

                "channel": (
                    l3.get(
                        "track",
                        {},
                    ).get(
                        "channel"
                    )
                ),

                "stage": (
                    l3.get(
                        "track",
                        {},
                    ).get(
                        "stage"
                    )
                ),

                "flow": (
                    l3.get(
                        "track",
                        {},
                    ).get(
                        "flow",
                        {},
                    )
                ),
            }
        )

        return frame

    # ======================================================
    # COLOR LOGIC
    # ======================================================

    def _compute_colors(
        self,
    ) -> Dict[str, tuple]:

        with self.lock:

            eq = list(
                self.eq_bands
            )

        intensity = (
            sum(eq)
            / EQ_BANDS
            if eq
            else 0.0
        )

        return {
            k: tuple(
                int(
                    c * intensity
                )

                for c in rgb
            )

            for k, rgb in BASE_COLORS.items()
        }

    # ======================================================
    # BINARY QBIT PRESENTATION BOUNDARY
    # ======================================================

    def decode_binary_qbit(self, payload):
        # Decode bytes only for presentation/inspection.
        return self.qbit_encoder.decode(payload)

    def render_binary_qbit(self, payload):
        # Binary remains transport data; rendering converts it to
        # the existing presentation frame without executing it.
        decoded = self.decode_binary_qbit(payload)
        if not isinstance(decoded, dict):
            return None
        metadata = decoded.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
        frame = RenderFrame(
            track_id=metadata.get("track_id"),
            source=metadata.get("source"),
            stage=metadata.get("stage") or "BINARY_DECODE",
            channel=metadata.get("channel_id") or metadata.get("channel"),
            metadata=metadata,
        )
        frame.metadata["encoding"] = "QBIT-BINARY"
        frame.metadata["intent_hash"] = decoded.get("intent_hash")
        frame.metadata["timestamp"] = decoded.get("timestamp")
        result = frame.serialize()
        self.memory.store(result)
        self.output_history.append(deepcopy(result))
        self.backends.emit(result)
        return result

    # ======================================================
    # SNAPSHOT
    # ======================================================

    def snapshot(self):

        with self.lock:

            return {
                "version": self.VERSION,

                "role": self.ROLE,

                "control_layer": (
                    self.CONTROL_LAYER
                ),

                "running": self.running,

                "fps": self.fps,

                "render_mode": (
                    self.render_mode
                ),

                "system_status": deepcopy(
                    self.system_status
                ),

                "l3": (
                    self._l3_snapshot()
                ),

                "hud_content": deepcopy(
                    self.hud_content
                ),

                "hud_content_type": (
                    self.hud_content_type
                ),

                "hud_content_metadata": (
                    deepcopy(
                        self.hud_content_metadata
                    )
                ),

                "memory_depth": len(
                    self.memory.history
                ),

                "authority": {
                    "presentation_only": True,

                    "can_execute": False,

                    "can_submit_commands": False,

                    "can_submit_qbits": False,

                    "can_control_queue": False,

                    "command_authority": (
                        self.COMMAND_AUTHORITY
                    ),

                    "transport_authority": (
                        self.TRANSPORT_AUTHORITY
                    ),
                },
            }


# ==========================================================
# END OF FILE
# ==========================================================