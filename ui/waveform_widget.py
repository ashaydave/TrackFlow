"""
Waveform Widget - DJ-style waveform visualization
"""

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QRect, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush
import numpy as np


class WaveformWidget(QWidget):
    """Interactive waveform display widget"""

    position_clicked = pyqtSignal(float)  # Emits position (0.0 to 1.0)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.waveform_data = None
        self.playback_position = 0.0  # 0.0 to 1.0
        self.setMinimumHeight(150)
        self.setMouseTracking(True)

        # Colors
        self.bg_color = QColor(30, 30, 30)
        self.waveform_color = QColor(42, 130, 218)  # Blue
        self.center_line_color = QColor(60, 60, 60)
        self.playhead_color = QColor(255, 255, 255)

    def set_waveform(self, waveform_data):
        """Set waveform data (list of float values from -1 to 1)"""
        if waveform_data:
            self.waveform_data = np.array(waveform_data)
        else:
            self.waveform_data = None
        self.update()

    def set_playback_position(self, position):
        """Set playback position (0.0 to 1.0)"""
        self.playback_position = max(0.0, min(1.0, position))
        self.update()

    def paintEvent(self, event):
        """Draw the waveform"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background
        painter.fillRect(self.rect(), self.bg_color)

        if self.waveform_data is None or len(self.waveform_data) == 0:
            # No waveform - show placeholder text
            painter.setPen(QColor(100, 100, 100))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No waveform data")
            return

        # Draw center line
        mid_y = self.height() / 2
        painter.setPen(QPen(self.center_line_color, 1))
        painter.drawLine(0, int(mid_y), self.width(), int(mid_y))

        # Draw waveform
        self.draw_waveform(painter)

        # Draw playhead
        if self.playback_position > 0:
            self.draw_playhead(painter)

    def draw_waveform(self, painter):
        """Draw the waveform bars"""
        width = self.width()
        height = self.height()
        mid_y = height / 2

        # Downsample waveform to fit widget width
        num_samples = len(self.waveform_data)
        samples_per_pixel = max(1, num_samples // width)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(self.waveform_color))

        for x in range(width):
            # Get sample range for this pixel
            start_idx = x * samples_per_pixel
            end_idx = min(start_idx + samples_per_pixel, num_samples)

            if start_idx >= num_samples:
                break

            # Get max and min in this range
            segment = self.waveform_data[start_idx:end_idx]
            if len(segment) > 0:
                max_val = np.max(segment)
                min_val = np.min(segment)

                # Scale to widget height
                top = mid_y - (max_val * mid_y * 0.9)  # 90% of height for headroom
                bottom = mid_y - (min_val * mid_y * 0.9)

                # Draw vertical bar
                bar_height = max(1, abs(bottom - top))
                painter.drawRect(QRect(x, int(top), 1, int(bar_height)))

    def draw_playhead(self, painter):
        """Draw the playback position indicator"""
        x = int(self.playback_position * self.width())

        # Playhead line
        painter.setPen(QPen(self.playhead_color, 2))
        painter.drawLine(x, 0, x, self.height())

        # Playhead triangle at top
        painter.setBrush(QBrush(self.playhead_color))
        painter.setPen(Qt.PenStyle.NoPen)

        triangle_size = 8
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
