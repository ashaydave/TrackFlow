# ui/waveform_dj.py
"""
DJ-Style Frequency-Colored Waveform
====================================
Two widgets stacked vertically:
  - Overview waveform: full track overview, 50px, click-to-seek
  - Main waveform:     main detail view, 130px, click-to-seek

Waveform data is a numpy array shape (N_BARS, 4):
  col 0: amplitude (0–1, normalized)
  col 1: bass ratio  (0–200 Hz share of total spectral energy)
  col 2: mid ratio   (200–4000 Hz)
  col 3: high ratio  (4000+ Hz)

Color mapping:
  bass  → (0,   85,  255)  deep blue
  mid   → (0,  170,  255)  sky blue / cyan
  high  → (180, 220, 255)  near-white blue
  Mix   = weighted sum by band ratio

Played portion: bars left of playhead rendered at 35% brightness.

Rendering: paintEvent reads pre-computed numpy data (no FFT in paint loop).
Data generation runs in WaveformDataThread (background QThread).
"""

import numpy as np
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QPolygonF
from PyQt6.QtCore import QPointF


# ── Color constants (RGB tuples) ──────────────────────────────────────────────

BASS_COLOR  = np.array([0,   85,  255], dtype=np.float32)
MID_COLOR   = np.array([0,  170,  255], dtype=np.float32)
HIGH_COLOR  = np.array([180, 220, 255], dtype=np.float32)
BG_COLOR    = QColor(8, 8, 16)
PLAYED_DIM  = 0.35   # brightness multiplier for played bars
PLAYHEAD_COLOR = QColor(255, 255, 255)

BAR_W = 2   # bar width in pixels
GAP   = 1   # gap between bars


def _mix_color(amp: float, bass: float, mid: float, high: float) -> QColor:
    """Blend bass/mid/high colors by energy ratios, scaled by amplitude."""
    total = bass + mid + high + 1e-9
    rgb = (BASS_COLOR * bass + MID_COLOR * mid + HIGH_COLOR * high) / total
    # Scale brightness: quiet sections are darker, loud are brighter
    brightness = 0.25 + 0.75 * float(amp)
    r, g, b = (rgb * brightness).clip(0, 255).astype(int)
    return QColor(int(r), int(g), int(b))


# ── Background data computation thread ───────────────────────────────────────

class WaveformDataThread(QThread):
    """
    Reads full audio file, computes frequency-colored bar data.
    Emits data_ready with numpy array shape (N_BARS, 4).
    """

    data_ready = pyqtSignal(object)   # numpy array, shape (N_BARS, 4)
    failed     = pyqtSignal(str)

    N_BARS = 400
    N_FFT  = 512
    SR     = 22050  # load at this sample rate for waveform

    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self._stop = False

    def stop_and_wait(self):
        self._stop = True
        self.quit()
        self.wait(1000)

    def run(self):
        try:
            import soundfile as sf
            import soxr

            # Load full track for waveform (we need the whole file)
            info = sf.info(self.file_path)
            data, sr_native = sf.read(
                self.file_path,
                dtype='float32',
                always_2d=False,
            )
            if self._stop:
                return

            # Mono mix
            if data.ndim == 2:
                data = data.mean(axis=1)

            # Downsample to SR for speed
            if sr_native != self.SR:
                data = soxr.resample(data, sr_native, self.SR, quality='LQ')

            if self._stop:
                return

            bars = self._compute_bars(data, self.SR)
            if not self._stop:
                self.data_ready.emit(bars)

        except Exception as e:
            if not self._stop:
                self.failed.emit(str(e))

    def _compute_bars(self, y: np.ndarray, sr: int) -> np.ndarray:
        """Vectorized frequency-colored bar computation."""
        n = self.N_BARS
        fft_n = self.N_FFT
        spb = max(1, len(y) // n)  # samples per bar

        freqs = np.fft.rfftfreq(fft_n, d=1.0 / sr)
        bass_mask = freqs < 200
        mid_mask  = (freqs >= 200) & (freqs < 4000)
        high_mask = freqs >= 4000

        bars = np.zeros((n, 4), dtype=np.float32)

        for i in range(n):
            if self._stop:
                break
            start = i * spb
            chunk = y[start: start + fft_n]
            if len(chunk) < fft_n:
                chunk = np.pad(chunk, (0, fft_n - len(chunk)))

            # RMS amplitude for this bar
            bars[i, 0] = np.sqrt(np.mean(chunk ** 2))

            # Frequency band ratios via FFT
            spec = np.abs(np.fft.rfft(chunk))
            total = spec.sum() + 1e-9
            bars[i, 1] = spec[bass_mask].sum() / total
            bars[i, 2] = spec[mid_mask].sum()  / total
            bars[i, 3] = spec[high_mask].sum() / total

        # Normalize amplitude to 0–1
        max_amp = bars[:, 0].max() + 1e-9
        bars[:, 0] /= max_amp

        return bars


# ── Shared base waveform widget ───────────────────────────────────────────────

class _BaseWaveform(QWidget):
    """Shared rendering for overview and main waveform panels."""

    position_clicked = pyqtSignal(float)   # 0.0–1.0

    def __init__(self, fixed_height: int, parent=None):
        super().__init__(parent)
        self.setFixedHeight(fixed_height)
        self.setMouseTracking(True)
        self._data: np.ndarray | None = None   # shape (N, 4)
        self._position: float = 0.0

    def set_data(self, data: np.ndarray) -> None:
        self._data = data
        self.update()

    def set_position(self, pos: float) -> None:
        self._position = max(0.0, min(1.0, pos))
        self.update()

    def clear(self) -> None:
        self._data = None
        self._position = 0.0
        self.update()

    # ── Paint ─────────────────────────────────────────────────────────────

    def paintEvent(self, event):
        painter = QPainter(self)
        # No antialiasing — crisp pixel-exact bars
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        w, h = self.width(), self.height()
        painter.fillRect(0, 0, w, h, BG_COLOR)

        if self._data is None:
            painter.setPen(QColor(40, 50, 70))
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                "Loading waveform\u2026"
            )
            return

        self._draw_bars(painter, w, h)
        self._draw_playhead(painter, w, h)

    def _draw_bars(self, painter: QPainter, w: int, h: int) -> None:
        data = self._data
        n = len(data)
        step = BAR_W + GAP                  # 3 pixels per bar slot
        n_visible = min(n, w // step)
        half_h = h / 2.0
        playhead_x = int(self._position * w)

        painter.setPen(Qt.PenStyle.NoPen)

        for i in range(n_visible):
            x = i * step
            bar_idx = int(i * n / n_visible)
            amp, bass, mid, high = (
                float(data[bar_idx, 0]),
                float(data[bar_idx, 1]),
                float(data[bar_idx, 2]),
                float(data[bar_idx, 3]),
            )

            bar_h = max(2, int(amp * half_h * 0.92))
            color = _mix_color(amp, bass, mid, high)

            # Darken played portion
            if x < playhead_x:
                color = QColor(
                    int(color.red()   * PLAYED_DIM),
                    int(color.green() * PLAYED_DIM),
                    int(color.blue()  * PLAYED_DIM),
                )

            painter.setBrush(QBrush(color))
            # Mirrored: draw from center upward and downward
            y_top = int(half_h) - bar_h
            painter.drawRect(x, y_top, BAR_W, bar_h * 2)

    def _draw_playhead(self, painter: QPainter, w: int, h: int) -> None:
        if self._position <= 0.0:
            return
        x = int(self._position * w)

        # White vertical line
        painter.setPen(QPen(PLAYHEAD_COLOR, 2))
        painter.drawLine(x, 0, x, h)

        # Triangle marker at top
        sz = 7
        triangle = QPolygonF([
            QPointF(x - sz, 0),
            QPointF(x + sz, 0),
            QPointF(x,      sz * 2),
        ])
        painter.setBrush(QBrush(PLAYHEAD_COLOR))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon(triangle)

    # ── Mouse ─────────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._data is not None:
            pos = max(0.0, min(1.0, event.position().x() / self.width()))
            self.position_clicked.emit(pos)

    def setCursor(self, cursor):
        if self._data is not None:
            super().setCursor(Qt.CursorShape.PointingHandCursor)


# ── Public container widget ───────────────────────────────────────────────────

class WaveformDJ(QWidget):
    """
    Container widget with overview + main waveform stacked vertically.
    Manages WaveformDataThread lifecycle — only one thread active at a time.

    Usage:
        waveform.set_waveform_from_file(path)   # starts background thread
        waveform.set_playback_position(0.42)    # updates both panels
        waveform.position_clicked -> float       # seek signal
    """

    position_clicked = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread: WaveformDataThread | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self.overview = _BaseWaveform(fixed_height=50)
        self.main     = _BaseWaveform(fixed_height=130)

        layout.addWidget(self.overview)
        layout.addWidget(self.main)

        self.overview.position_clicked.connect(self.position_clicked)
        self.main.position_clicked.connect(self.position_clicked)

    def set_waveform_from_file(self, file_path: str) -> None:
        """Start background thread to compute waveform data."""
        # Stop any running thread first
        if self._thread is not None and self._thread.isRunning():
            self._thread.stop_and_wait()

        self.overview.clear()
        self.main.clear()

        self._thread = WaveformDataThread(file_path)
        self._thread.data_ready.connect(self._on_data_ready)
        self._thread.failed.connect(
            lambda msg: print(f"WaveformDataThread failed: {msg}")
        )
        self._thread.start()

    def _on_data_ready(self, data: np.ndarray) -> None:
        self.overview.set_data(data)
        self.main.set_data(data)

    def set_playback_position(self, pos: float) -> None:
        """Update playhead on both panels (0.0–1.0)."""
        self.overview.set_position(pos)
        self.main.set_position(pos)

    def clear(self) -> None:
        """Clear both panels and stop any running thread."""
        if self._thread is not None and self._thread.isRunning():
            self._thread.stop_and_wait()
        self.overview.clear()
        self.main.clear()
