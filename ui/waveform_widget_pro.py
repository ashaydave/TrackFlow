"""
Professional-Grade Waveform Widget
DJ software style with frequency-based coloring (bass, mids, highs)
"""

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QRect, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QLinearGradient
import numpy as np
import librosa


class WaveformWidgetPro(QWidget):
    """Professional DJ-style waveform with frequency visualization"""

    position_clicked = pyqtSignal(float)  # Emits position (0.0 to 1.0)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.waveform_data = None
        self.frequency_data = None  # Low, mid, high energy
        self.playback_position = 0.0
        self.setMinimumHeight(200)
        self.setMouseTracking(True)

        # Colors - DJ software style
        self.bg_color = QColor(20, 20, 20)
        self.center_line_color = QColor(40, 40, 40)
        self.playhead_color = QColor(255, 255, 255)

        # Frequency-based colors (like Rekordbox)
        self.bass_color = QColor(255, 100, 50)      # Orange/Red for bass
        self.mid_color = QColor(100, 200, 255)      # Blue for mids
        self.high_color = QColor(150, 255, 150)     # Green for highs

    def set_waveform_from_file(self, file_path, duration):
        """Generate professional waveform directly from audio file"""
        try:
            # Load audio with librosa (faster, lower sample rate)
            y, sr = librosa.load(file_path, sr=22050, duration=min(duration, 600))  # Max 10 min for speed

            # Downsample for waveform display (one sample per pixel roughly)
            target_samples = 2000
            if len(y) > target_samples:
                step = len(y) // target_samples
                y = y[::step]

            # Calculate frequency bands using STFT
            # This gives us bass, mid, high energy like DJ software
            hop_length = max(1, len(y) // target_samples)

            # Get spectrogram (adjust n_fft based on signal length)
            n_fft = min(2048, len(y))
            D = np.abs(librosa.stft(y, hop_length=hop_length, n_fft=n_fft))

            # Split into frequency bands
            # Bass: 0-200 Hz, Mids: 200-2000 Hz, Highs: 2000+ Hz
            freq_bins = librosa.fft_frequencies(sr=sr, n_fft=n_fft)

            bass_mask = freq_bins < 200
            mid_mask = (freq_bins >= 200) & (freq_bins < 2000)
            high_mask = freq_bins >= 2000

            # Energy per band
            bass_energy = np.sum(D[bass_mask, :], axis=0)
            mid_energy = np.sum(D[mid_mask, :], axis=0)
            high_energy = np.sum(D[high_mask, :], axis=0)

            # Normalize
            bass_energy = bass_energy / (np.max(bass_energy) + 1e-8)
            mid_energy = mid_energy / (np.max(mid_energy) + 1e-8)
            high_energy = high_energy / (np.max(high_energy) + 1e-8)

            # Store
            self.waveform_data = y
            self.frequency_data = {
                'bass': bass_energy,
                'mid': mid_energy,
                'high': high_energy
            }

            self.update()

        except Exception as e:
            print(f"Error generating waveform: {e}")
            self.waveform_data = None
            self.frequency_data = None
            self.update()

    def set_waveform(self, waveform_data):
        """Set waveform data from pre-computed array"""
        if waveform_data:
            self.waveform_data = np.array(waveform_data)
            # Without frequency data, we'll just show amplitude
            self.frequency_data = None
        else:
            self.waveform_data = None
            self.frequency_data = None
        self.update()

    def set_playback_position(self, position):
        """Set playback position (0.0 to 1.0)"""
        self.playback_position = max(0.0, min(1.0, position))
        self.update()

    def paintEvent(self, event):
        """Draw the professional waveform"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background
        painter.fillRect(self.rect(), self.bg_color)

        if self.waveform_data is None or len(self.waveform_data) == 0:
            # No waveform - show message
            painter.setPen(QColor(100, 100, 100))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                           "Click 'Load Track' to analyze and visualize")
            return

        # Draw center line
        mid_y = self.height() / 2
        painter.setPen(QPen(self.center_line_color, 1))
        painter.drawLine(0, int(mid_y), self.width(), int(mid_y))

        # Draw waveform with frequency colors
        if self.frequency_data:
            self.draw_frequency_waveform(painter)
        else:
            self.draw_simple_waveform(painter)

        # Draw playhead
        if self.playback_position > 0:
            self.draw_playhead(painter)

    def draw_frequency_waveform(self, painter):
        """Draw waveform with frequency-based coloring (professional style)"""
        width = self.width()
        height = self.height()
        mid_y = height / 2

        bass = self.frequency_data['bass']
        mid = self.frequency_data['mid']
        high = self.frequency_data['high']

        num_samples = len(bass)
        samples_per_pixel = max(1, num_samples / width)

        painter.setPen(Qt.PenStyle.NoPen)

        for x in range(width):
            # Get sample index for this pixel
            idx = int(x * samples_per_pixel)
            if idx >= num_samples:
                break

            # Get energy values
            bass_val = bass[idx]
            mid_val = mid[idx]
            high_val = high[idx]

            # Total energy for this sample
            total_energy = (bass_val + mid_val + high_val) / 3.0

            # Bar height based on total energy
            bar_height = total_energy * mid_y * 0.95

            # Draw stacked bars (bass at bottom, then mid, then high)
            y_top = mid_y - bar_height
            y_bottom = mid_y + bar_height

            # Bass (bottom/biggest)
            bass_height = bass_val * bar_height
            painter.setBrush(QBrush(self.bass_color))
            painter.drawRect(x, int(mid_y - bass_height), 1, int(bass_height * 2))

            # Mid (middle layer)
            mid_height = mid_val * bar_height * 0.7
            painter.setBrush(QBrush(self.mid_color))
            painter.drawRect(x, int(mid_y - mid_height), 1, int(mid_height * 2))

            # High (top layer, smallest)
            high_height = high_val * bar_height * 0.4
            painter.setBrush(QBrush(self.high_color))
            painter.drawRect(x, int(mid_y - high_height), 1, int(high_height * 2))

    def draw_simple_waveform(self, painter):
        """Draw simple amplitude waveform (fallback)"""
        width = self.width()
        height = self.height()
        mid_y = height / 2

        num_samples = len(self.waveform_data)
        samples_per_pixel = max(1, num_samples // width)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(self.mid_color))

        for x in range(width):
            start_idx = x * samples_per_pixel
            end_idx = min(start_idx + samples_per_pixel, num_samples)

            if start_idx >= num_samples:
                break

            segment = self.waveform_data[start_idx:end_idx]
            if len(segment) > 0:
                max_val = np.max(np.abs(segment))
                bar_height = max_val * mid_y * 0.9

                painter.drawRect(x, int(mid_y - bar_height), 1, int(bar_height * 2))

    def draw_playhead(self, painter):
        """Draw the playback position indicator"""
        x = int(self.playback_position * self.width())

        # Playhead line
        painter.setPen(QPen(self.playhead_color, 2))
        painter.drawLine(x, 0, x, self.height())

        # Playhead triangle at top
        painter.setBrush(QBrush(self.playhead_color))
        painter.setPen(Qt.PenStyle.NoPen)

        triangle_size = 10
        points = [
            (x, 0),
            (x - triangle_size, triangle_size),
            (x + triangle_size, triangle_size)
        ]

        from PyQt6.QtCore import QPointF
        painter.drawPolygon([QPointF(p[0], p[1]) for p in points])

    def mousePressEvent(self, event):
        """Handle mouse click to seek"""
        if event.button() == Qt.MouseButton.LeftButton:
            position = event.position().x() / self.width()
            position = max(0.0, min(1.0, position))
            self.position_clicked.emit(position)

    def resizeEvent(self, event):
        """Redraw on resize"""
        super().resizeEvent(event)
        self.update()
