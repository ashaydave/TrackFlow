# ui/audio_player.py
"""
Audio Player — pygame-based playback with correct state machine.
States: STOPPED → PLAYING → PAUSED → PLAYING (via resume)
        PLAYING/PAUSED → STOPPED (via stop)
"""

import pygame
import time
from enum import Enum, auto
from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from pathlib import Path


class PlayerState(Enum):
    STOPPED = auto()
    PLAYING = auto()
    PAUSED  = auto()


class AudioPlayer(QObject):
    """Pygame-backed audio player with clean state machine."""

    position_changed  = pyqtSignal(float)   # 0.0–1.0
    playback_finished = pyqtSignal()

    def __init__(self):
        super().__init__()
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=1024)

        self.current_file: str | None = None
        self.duration: float = 0.0
        self.state = PlayerState.STOPPED
        self._play_start_time: float = 0.0
        self._paused_at_seconds: float = 0.0

        self._timer = QTimer()
        self._timer.setInterval(50)
        self._timer.timeout.connect(self._tick)

    # ── Properties ───────────────────────────────────────────────────────

    @property
    def is_playing(self) -> bool:
        return self.state == PlayerState.PLAYING

    # ── Public API ───────────────────────────────────────────────────────

    def load(self, file_path: str) -> bool:
        """Load file. Does NOT start playback."""
        try:
            self.stop()
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=1024)
            pygame.mixer.music.load(str(file_path))
            self.current_file = str(file_path)
            self.duration = 0.0
            self._paused_at_seconds = 0.0
            return True
        except Exception as e:
            print(f"AudioPlayer.load error: {e}")
            return False

    def set_duration(self, duration: float) -> None:
        self.duration = duration

    def play(self) -> None:
        """Start from beginning (or from seek position if recently seeked)."""
        if not self.current_file:
            return
        try:
            pygame.mixer.music.play()
            self.state = PlayerState.PLAYING
            self._play_start_time = time.time()
            self._paused_at_seconds = 0.0
            self._timer.start()
        except Exception as e:
            print(f"AudioPlayer.play error: {e}")

    def pause(self) -> None:
        if self.state != PlayerState.PLAYING:
            return
        try:
            self._paused_at_seconds = self._current_seconds()
            pygame.mixer.music.pause()
            self.state = PlayerState.PAUSED
            self._timer.stop()
        except Exception as e:
            print(f"AudioPlayer.pause error: {e}")

    def resume(self) -> None:
        if self.state != PlayerState.PAUSED:
            return
        try:
            pygame.mixer.music.unpause()
            self.state = PlayerState.PLAYING
            # Recalculate start time so position tracking is accurate
            self._play_start_time = time.time() - self._paused_at_seconds
            self._timer.start()
        except Exception as e:
            print(f"AudioPlayer.resume error: {e}")

    def stop(self) -> None:
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass
        self.state = PlayerState.STOPPED
        self._paused_at_seconds = 0.0
        self._timer.stop()
        self.position_changed.emit(0.0)

    def seek(self, position: float) -> None:
        """Seek to normalized position (0.0–1.0)."""
        if not self.current_file or self.duration <= 0:
            return
        target_secs = max(0.0, min(position * self.duration, self.duration))
        was_playing = (self.state == PlayerState.PLAYING)
        try:
            pygame.mixer.music.stop()
            pygame.mixer.music.play(start=target_secs)
            self._play_start_time = time.time() - target_secs
            self._paused_at_seconds = target_secs
            if was_playing:
                self.state = PlayerState.PLAYING
                self._timer.start()
            else:
                pygame.mixer.music.pause()
                self.state = PlayerState.PAUSED
            self.position_changed.emit(position)
        except Exception as e:
            print(f"AudioPlayer.seek error: {e}")

    def set_volume(self, volume: float) -> None:
        """Volume 0.0–1.0."""
        try:
            pygame.mixer.music.set_volume(max(0.0, min(1.0, volume)))
        except Exception:
            pass

    def get_position(self) -> float:
        """Current position as 0.0–1.0."""
        if not self.current_file or self.duration <= 0:
            return 0.0
        secs = self._current_seconds()
        return max(0.0, min(1.0, secs / self.duration))

    # ── Internal ─────────────────────────────────────────────────────────

    def _current_seconds(self) -> float:
        if self.state == PlayerState.PAUSED:
            return self._paused_at_seconds
        if self.state == PlayerState.PLAYING:
            return time.time() - self._play_start_time
        return 0.0

    def _tick(self) -> None:
        if self.state != PlayerState.PLAYING:
            return
        if not pygame.mixer.music.get_busy():
            self.stop()
            self.playback_finished.emit()
            return
        self.position_changed.emit(self.get_position())
