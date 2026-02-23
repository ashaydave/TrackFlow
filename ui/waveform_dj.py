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
  bass  → (255,  50,   0)  red    — kicks/subs
  mid   → (255, 185,   0)  amber  — melody/vocals
  high  → (  0, 200, 255)  cyan   — cymbals/air
  Mix   = weighted sum by band ratio

Played portion: bars left of playhead rendered at 35% brightness.

Rendering: paintEvent reads pre-computed numpy data (no FFT in paint loop).
Data generation runs in WaveformDataThread (background QThread).
"""

import numpy as np
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QPolygonF, QImage
from PyQt6.QtCore import QPointF


# ── Color constants (RGB tuples) ──────────────────────────────────────────────

BASS_COLOR  = np.array([255,  50,   0], dtype=np.float32)   # red   — kicks/subs
MID_COLOR   = np.array([255, 185,   0], dtype=np.float32)   # amber — melody/vocals
HIGH_COLOR  = np.array([  0, 200, 255], dtype=np.float32)   # cyan  — cymbals/air
BG_COLOR    = QColor(8, 8, 16)
PLAYED_DIM  = 0.35   # brightness multiplier for played bars
PLAYHEAD_COLOR = QColor(255, 255, 255)
BG_R, BG_G, BG_B = 8, 8, 16        # RGB components of BG_COLOR

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

    N_BARS = 1200
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

    position_clicked  = pyqtSignal(float)   # 0.0–1.0  — press or release (seeks audio)
    position_dragging = pyqtSignal(float)   # 0.0–1.0  — move while held (visual only)

    def __init__(self, fixed_height: int, parent=None):
        super().__init__(parent)
        self.setFixedHeight(fixed_height)
        self.setMouseTracking(True)
        self._data: np.ndarray | None = None   # shape (N, 4)
        self._position: float = 0.0
        self._zoom_start: float = 0.0
        self._zoom_end: float = 1.0
        self._hot_cues: list = [None] * 6   # each: None or {'position': float, 'color': QColor}
        self._loop_a: float | None = None
        self._loop_b: float | None = None
        self._loop_active: bool = False
        self._beat_grid: tuple | None = None   # (bpm: float, duration: float)

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

    def set_zoom(self, start: float, end: float) -> None:
        """Set visible fraction of track (0.0–1.0). Full track: 0.0, 1.0."""
        self._zoom_start = max(0.0, min(1.0, start))
        self._zoom_end = max(self._zoom_start + 0.001, min(1.0, end))
        self.update()

    def set_position_and_zoom(self, pos: float, zoom_start: float, zoom_end: float) -> None:
        """Set position and zoom atomically — triggers only ONE repaint."""
        self._position   = max(0.0, min(1.0, pos))
        self._zoom_start = max(0.0, min(1.0, zoom_start))
        self._zoom_end   = max(self._zoom_start + 0.001, min(1.0, zoom_end))
        self.update()

    def set_hot_cues(self, cues: list) -> None:
        """cues: list of 6 items, each None or {'position': float, 'color': QColor}."""
        self._hot_cues = cues
        self.update()

    def set_loop(self, a, b, active: bool) -> None:
        self._loop_a = a
        self._loop_b = b
        self._loop_active = active
        self.update()

    def set_beat_grid(self, bpm: float | None, duration: float) -> None:
        """Set BPM + duration so beat/bar lines can be painted on the waveform."""
        if bpm and bpm > 0 and duration > 0:
            self._beat_grid = (float(bpm), float(duration))
        else:
            self._beat_grid = None
        self.update()

    def _draw_beat_grid(self, painter: QPainter, w: int, h: int) -> None:
        """Draw semi-transparent beat (thin) and bar (full-height) tick marks."""
        if self._beat_grid is None:
            return
        bpm, duration = self._beat_grid
        secs_per_beat = 60.0 / bpm
        beat = 0
        t = 0.0
        while t < duration:
            x = int((t / duration) * w)
            is_bar = (beat % 4 == 0)
            alpha  = 55 if is_bar else 20
            ht     = h  if is_bar else h // 2
            y_top  = (h - ht) // 2
            painter.setPen(QPen(QColor(255, 255, 255, alpha), 1))
            painter.drawLine(x, y_top, x, y_top + ht)
            beat += 1
            t    += secs_per_beat

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

        self._draw_waveform(painter, w, h)
        self._draw_beat_grid(painter, w, h)
        self._draw_loop_region(painter, w, h)
        self._draw_cue_markers(painter, w, h)
        self._draw_playhead(painter, w, h)

    def _draw_bars(self, painter: QPainter, w: int, h: int) -> None:
        data = self._data
        n = len(data)

        # Zoom: select which bars are visible
        bar_start = int(self._zoom_start * n)
        bar_end   = int(self._zoom_end   * n)
        bar_end   = max(bar_start + 1, min(n, bar_end))
        n_in_view = bar_end - bar_start

        step = BAR_W + GAP
        n_visible = w // step   # always fill widget; bars repeat when zoomed in far
        if n_visible < 1:
            return

        half_h = h / 2.0
        zoom_width = max(1e-9, self._zoom_end - self._zoom_start)
        playhead_x = int(
            max(0.0, (self._position - self._zoom_start) / zoom_width) * w
        )

        painter.setPen(Qt.PenStyle.NoPen)

        for i in range(n_visible):
            x = i * step
            bar_idx = bar_start + int(i * n_in_view / n_visible)
            bar_idx = min(n - 1, bar_idx)
            amp, bass, mid, high = (
                float(data[bar_idx, 0]),
                float(data[bar_idx, 1]),
                float(data[bar_idx, 2]),
                float(data[bar_idx, 3]),
            )

            bar_h = max(2, int(amp * half_h * 0.92))
            color = _mix_color(amp, bass, mid, high)

            if x < playhead_x:
                color = QColor(
                    int(color.red()   * PLAYED_DIM),
                    int(color.green() * PLAYED_DIM),
                    int(color.blue()  * PLAYED_DIM),
                )

            painter.setBrush(QBrush(color))
            y_top = int(half_h) - bar_h
            painter.drawRect(x, y_top, BAR_W, bar_h * 2)

    def _draw_waveform(self, painter: QPainter, w: int, h: int) -> None:
        """Filled seamless waveform via vectorised numpy → QImage blit (full track)."""
        data = self._data
        n    = len(data)

        # ── Map every pixel column → data index (full track, no zoom) ─
        col_idx = np.round(np.linspace(0, n - 1, w)).astype(np.int32)
        col_idx = np.clip(col_idx, 0, n - 1)

        amps = data[col_idx, 0].astype(np.float32)   # (w,)
        bass = data[col_idx, 1].astype(np.float32)
        mid  = data[col_idx, 2].astype(np.float32)
        high = data[col_idx, 3].astype(np.float32)

        # ── Vectorised colour mixing ───────────────────────────────────
        total      = bass + mid + high + 1e-9
        brightness = 0.25 + 0.75 * amps

        r_f = (255.0 * bass + 255.0 * mid +   0.0 * high) / total * brightness
        g_f = ( 50.0 * bass + 185.0 * mid + 200.0 * high) / total * brightness
        b_f = (  0.0 * bass +   0.0 * mid + 255.0 * high) / total * brightness

        # ── Dim played columns ────────────────────────────────────────
        playhead_x  = int(self._position * w)
        played_mask = np.arange(w) < playhead_x
        dim         = np.where(played_mask, PLAYED_DIM, 1.0).astype(np.float32)
        r_u8 = np.clip(r_f * dim, 0, 255).astype(np.uint8)
        g_u8 = np.clip(g_f * dim, 0, 255).astype(np.uint8)
        b_u8 = np.clip(b_f * dim, 0, 255).astype(np.uint8)

        # ── Bar heights ───────────────────────────────────────────────
        half_h      = h // 2
        bar_heights = np.maximum(1, (amps * half_h * 0.92).astype(np.int32))
        y_tops      = np.maximum(0, half_h - bar_heights)
        y_bots      = np.minimum(h, half_h + bar_heights)

        # ── Build RGB888 image array ──────────────────────────────────
        img    = np.empty((h, w, 3), dtype=np.uint8)
        y_grid = np.arange(h, dtype=np.int32)[:, np.newaxis]          # (h, 1)
        mask   = (y_grid >= y_tops[np.newaxis, :]) & (y_grid < y_bots[np.newaxis, :])

        img[:, :, 0] = np.where(mask, r_u8[np.newaxis, :], BG_R)
        img[:, :, 1] = np.where(mask, g_u8[np.newaxis, :], BG_G)
        img[:, :, 2] = np.where(mask, b_u8[np.newaxis, :], BG_B)

        # ── Blit (img kept alive as local var) ────────────────────────
        qimg = QImage(img.data, w, h, w * 3, QImage.Format.Format_RGB888)
        painter.drawImage(0, 0, qimg)

    def _draw_loop_region(self, painter: QPainter, w: int, h: int) -> None:
        """Draw semi-transparent loop region between A and B points."""
        if self._loop_a is None and self._loop_b is None:
            return
        zoom_width = max(1e-9, self._zoom_end - self._zoom_start)

        a_norm = self._loop_a if self._loop_a is not None else self._loop_b
        b_norm = self._loop_b if self._loop_b is not None else self._loop_a

        a_x = int(max(0.0, (a_norm - self._zoom_start) / zoom_width) * w)
        b_x = int(max(0.0, (b_norm - self._zoom_start) / zoom_width) * w)
        a_x = max(0, min(w, a_x))
        b_x = max(0, min(w, b_x))
        if a_x > b_x:
            a_x, b_x = b_x, a_x

        if b_x - a_x >= 1:
            fill = QColor(0, 220, 100, 50) if self._loop_active else QColor(255, 185, 0, 40)
            painter.fillRect(a_x, 0, b_x - a_x, h, fill)

        line_color = (QColor(0, 220, 100, 200) if self._loop_active
                      else QColor(255, 185, 0, 200))
        painter.setPen(QPen(line_color, 1))
        if self._loop_a is not None:
            painter.drawLine(a_x, 0, a_x, h)
        if self._loop_b is not None:
            painter.drawLine(b_x, 0, b_x, h)

    def _draw_cue_markers(self, painter: QPainter, w: int, h: int) -> None:
        """Draw colored tick marks for set hot cues."""
        zoom_width = max(1e-9, self._zoom_end - self._zoom_start)
        for i, cue in enumerate(self._hot_cues):
            if cue is None:
                continue
            pos = cue['position']
            if not (self._zoom_start - 0.001 <= pos <= self._zoom_end + 0.001):
                continue
            x = int((pos - self._zoom_start) / zoom_width * w)
            x = max(0, min(w - 1, x))
            color = cue['color']

            painter.setPen(QPen(color, 2))
            painter.drawLine(x, 0, x, h)

            badge = 13
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(x - badge // 2, 0, badge, badge)

            painter.setPen(QPen(QColor(0, 0, 0)))
            font = painter.font()
            font.setPointSize(7)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(
                x - badge // 2, 0, badge, badge,
                Qt.AlignmentFlag.AlignCenter,
                str(i + 1),
            )

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
            click_frac = max(0.0, min(1.0, event.position().x() / self.width()))
            zoom_width = self._zoom_end - self._zoom_start
            pos = self._zoom_start + click_frac * zoom_width
            pos = max(0.0, min(1.0, pos))
            self.position_clicked.emit(pos)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton and self._data is not None:
            pos = max(0.0, min(1.0, event.position().x() / self.width()))
            self.position_dragging.emit(pos)   # visual update only — no audio seek

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._data is not None:
            pos = max(0.0, min(1.0, event.position().x() / self.width()))
            self.position_clicked.emit(pos)    # seek audio on release

    def setCursor(self, cursor):
        if self._data is not None:
            super().setCursor(Qt.CursorShape.PointingHandCursor)


# ── Public container widget ───────────────────────────────────────────────────

class WaveformDJ(QWidget):
    """
    Single full-track waveform widget.
    Manages WaveformDataThread lifecycle — only one thread active at a time.

    Signals:
        position_clicked(float)  — emitted on press or drag-release (seek audio)
        position_dragging(float) — emitted during drag (visual update only)
    """

    position_clicked  = pyqtSignal(float)
    position_dragging = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread: WaveformDataThread | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.main = _BaseWaveform(fixed_height=160)
        layout.addWidget(self.main)

        self.main.position_clicked.connect(self.position_clicked)
        self.main.position_dragging.connect(self.position_dragging)

    def set_waveform_from_file(self, file_path: str) -> None:
        """Start background thread to compute waveform data."""
        if self._thread is not None and self._thread.isRunning():
            self._thread.stop_and_wait()
        self.main.clear()
        self._thread = WaveformDataThread(file_path)
        self._thread.data_ready.connect(self._on_data_ready)
        self._thread.failed.connect(
            lambda msg: print(f"WaveformDataThread failed: {msg}")
        )
        self._thread.start()

    def _on_data_ready(self, data: np.ndarray) -> None:
        self.main.set_data(data)

    def set_playback_position(self, pos: float) -> None:
        """Update playhead position (0.0–1.0)."""
        self.main.set_position(pos)

    def clear(self) -> None:
        """Clear waveform and stop any running thread."""
        if self._thread is not None and self._thread.isRunning():
            self._thread.stop_and_wait()
        self.main.clear()

    def update_cues_and_loop(
        self,
        cues: list,
        loop_a,
        loop_b,
        loop_active: bool,
    ) -> None:
        """Push hot cue + loop state to waveform panel."""
        self.main.set_hot_cues(cues)
        self.main.set_loop(loop_a, loop_b, loop_active)

    def set_beat_grid(self, bpm: float | None, duration: float) -> None:
        """Forward BPM/duration to the base waveform for beat-grid painting."""
        self.main.set_beat_grid(bpm, duration)
