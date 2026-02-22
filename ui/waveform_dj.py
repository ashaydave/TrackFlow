"""
DJ-Style Waveform Widget - Exactly like Rekordbox/VirtualDJ
Simple, clean, professional stereo waveform
"""

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush
import numpy as np
import librosa


class WaveformDJ(QWidget):
    """Professional DJ software style waveform - simple and clean"""

    position_clicked = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.waveform_left = None   # Left channel
        self.waveform_right = None  # Right channel
        self.playback_position = 0.0
        self.setMinimumHeight(120)
        self.setMouseTracking(True)

        # Colors - simple like Rekordbox
        self.bg_color = QColor(25, 25, 25)
        self.waveform_color = QColor(0, 150, 255)  # Blue
        self.waveform_dark = QColor(0, 100, 180)   # Darker blue for played portion
        self.center_line_color = QColor(50, 50, 50)
        self.playhead_color = QColor(255, 255, 255)

    def set_waveform_from_file(self, file_path):
        """Generate clean DJ-style waveform from audio file - FAST"""
        try:
            # Load audio - stereo, short duration for speed
            y, sr = librosa.load(file_path, sr=22050, mono=False, duration=None)

            # If mono, duplicate to stereo
            if len(y.shape) == 1:
                y = np.array([y, y])

            # Get left and right channels
            left = y[0]
            right = y[1]

            # Downsample to screen resolution (one sample per 2 pixels)
            target_samples = 1000  # More samples = smoother but slower

            left = self._downsample_max(left, target_samples)
            right = self._downsample_max(right, target_samples)

            self.waveform_left = left
            self.waveform_right = right

            self.update()

        except Exception as e:
            print(f"Waveform error: {e}")
            self.waveform_left = None
            self.waveform_right = None
            self.update()

    def _downsample_max(self, data, target_samples):
        """Downsample by taking max values (preserves peaks like DJ software)"""
        if len(data) <= target_samples:
            return data

        samples_per_bin = len(data) // target_samples
        result = np.zeros(target_samples)

        for i in range(target_samples):
            start = i * samples_per_bin
            end = min(start + samples_per_bin, len(data))
            # Take max absolute value to show peaks (like DJ software)
            result[i] = np.max(np.abs(data[start:end]))

        return result

    def set_playback_position(self, position):
        """Set playback position (0.0 to 1.0)"""
        self.playback_position = max(0.0, min(1.0, position))
        self.update()

    def paintEvent(self, event):
        """Draw the waveform - simple and clean like Rekordbox"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background
        painter.fillRect(self.rect(), self.bg_color)

        if self.waveform_left is None or self.waveform_right is None:
            # Show loading message
            painter.setPen(QColor(100, 100, 100))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                           "Loading waveform...")
            return

        # Draw center line
        mid_y = self.height() / 2
        painter.setPen(QPen(self.center_line_color, 1))
        painter.drawLine(0, int(mid_y), self.width(), int(mid_y))

        # Draw stereo waveform (top = left, bottom = right)
        self.draw_channel(painter, self.waveform_left, is_top=True)
        self.draw_channel(painter, self.waveform_right, is_top=False)

        # Draw playhead
        if self.playback_position > 0:
            self.draw_playhead(painter)

    def draw_channel(self, painter, channel_data, is_top):
        """Draw one channel of the waveform"""
        width = self.width()
        height = self.height()
        mid_y = height / 2
        channel_height = height / 2

        num_samples = len(channel_data)
        playhead_x = int(self.playback_position * width)

        painter.setPen(Qt.PenStyle.NoPen)

        for x in range(width):
            # Get sample for this pixel
            sample_idx = int((x / width) * num_samples)
            if sample_idx >= num_samples:
                break

            amplitude = channel_data[sample_idx]

            # Scale amplitude to fit channel height
            bar_height = amplitude * channel_height * 0.9

            # Choose color based on playback position
            if x < playhead_x:
                color = self.waveform_dark  # Already played
            else:
                color = self.waveform_color  # Not played yet

            painter.setBrush(QBrush(color))

            # Draw bar
            if is_top:
                # Top channel (above center line)
                y = mid_y - bar_height
                painter.drawRect(x, int(y), 2, int(bar_height))
            else:
                # Bottom channel (below center line) - mirrored
                y = mid_y
                painter.drawRect(x, int(y), 2, int(bar_height))

    def draw_playhead(self, painter):
        """Draw playback position indicator"""
        x = int(self.playback_position * self.width())

        # Playhead line
        painter.setPen(QPen(self.playhead_color, 2))
        painter.drawLine(x, 0, x, self.height())

        # Triangle at top
        painter.setBrush(QBrush(self.playhead_color))
        painter.setPen(Qt.PenStyle.NoPen)

        size = 8
        points = [
            (x, 0),
            (x - size, size),
            (x + size, size)
        ]

        from PyQt6.QtCore import QPointF
        painter.drawPolygon([QPointF(p[0], p[1]) for p in points])

    def mousePressEvent(self, event):
        """Click to seek"""
        if event.button() == Qt.MouseButton.LeftButton:
            position = event.position().x() / self.width()
            position = max(0.0, min(1.0, position))
            self.position_clicked.emit(position)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update()
