# ui/audio_player.py
"""
Audio Player — pygame-based playback with correct state machine.
States: STOPPED → PLAYING → PAUSED → PLAYING (via resume)
        PLAYING/PAUSED → STOPPED (via stop)
        PLAYING → LOOP_PLAYING → PLAYING (via start_loop/stop_loop)
"""

import pygame
import time
from enum import Enum, auto
from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from pathlib import Path


class PlayerState(Enum):
    STOPPED      = auto()
    PLAYING      = auto()
    PAUSED       = auto()
    LOOP_PLAYING = auto()


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
        self._loop_sound: object | None = None        # pygame.mixer.Sound
        self._loop_sound_a_secs: float  = 0.0
        self._loop_sound_dur: float     = 0.0
        self._loop_sound_wall: float    = 0.0

        self._timer = QTimer()
        self._timer.setInterval(50)
        self._timer.timeout.connect(self._tick)

    # ── Properties ───────────────────────────────────────────────────────

    @property
    def is_playing(self) -> bool:
        return self.state in (PlayerState.PLAYING, PlayerState.LOOP_PLAYING)

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
        if self.state == PlayerState.LOOP_PLAYING:
            self._paused_at_seconds = self._current_seconds()
            if self._loop_sound is not None:
                try:
                    self._loop_sound.stop()
                except Exception:
                    pass
                self._loop_sound = None
            try:
                pygame.mixer.music.pause()
            except Exception:
                pass
            self.state = PlayerState.PAUSED
            self._timer.stop()
            return
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
        if self._loop_sound is not None:
            try:
                self._loop_sound.stop()
            except Exception:
                pass
            self._loop_sound = None
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
            v = max(0.0, min(1.0, volume))
            pygame.mixer.music.set_volume(v)
            if self._loop_sound is not None:
                self._loop_sound.set_volume(v)
        except Exception:
            pass

    def start_loop(self, file_path: str, a_secs: float, b_secs: float) -> bool:
        """
        Decode [a_secs, b_secs] of file_path into a pygame.Sound and play
        with loops=-1 for gap-free looping.
        Returns True on success, False if Sound creation fails (caller falls back).
        """
        import numpy as np
        import soundfile as sf
        import soxr

        try:
            info = sf.info(str(file_path))
            sr_native = info.samplerate
            frame_a = int(a_secs * sr_native)
            frame_b = min(int(b_secs * sr_native), info.frames)
            n_frames = max(1, frame_b - frame_a)

            data, _ = sf.read(
                str(file_path),
                start=frame_a,
                frames=n_frames,
                dtype='int16',
                always_2d=True,
            )

            # pygame mixer is initialised at 44100 Hz; resample if source differs
            mixer_sr = 44100
            if sr_native != mixer_sr:
                data_f = data.astype(np.float32) / 32768.0
                left  = soxr.resample(data_f[:, 0], sr_native, mixer_sr, quality='HQ')
                right = soxr.resample(
                    data_f[:, 1] if data_f.shape[1] > 1 else data_f[:, 0],
                    sr_native, mixer_sr, quality='HQ',
                )
                data_f = np.column_stack([left, right])
                data = np.clip(data_f * 32768.0, -32768, 32767).astype(np.int16)

            # Ensure stereo (mixer initialised with channels=2)
            if data.shape[1] == 1:
                data = np.column_stack([data[:, 0], data[:, 0]])

            # Must be C-contiguous for pygame.sndarray
            data = np.ascontiguousarray(data)

            sound = pygame.sndarray.make_sound(data)
            sound.set_volume(pygame.mixer.music.get_volume())

            # Stop existing loop sound; pause the music stream
            if self._loop_sound is not None:
                self._loop_sound.stop()
            pygame.mixer.music.pause()

            self._loop_sound        = sound
            self._loop_sound_a_secs = a_secs
            self._loop_sound_dur    = (frame_b - frame_a) / mixer_sr
            self._loop_sound_wall   = time.time()

            sound.play(loops=-1)

            self.state = PlayerState.LOOP_PLAYING
            self._timer.start()
            return True

        except Exception as e:
            print(f"AudioPlayer.start_loop error: {e}")
            return False

    def stop_loop(self) -> None:
        """Stop the Sound loop and resume music from current logical position."""
        if self._loop_sound is None:
            return
        current_secs = self._current_seconds()
        try:
            self._loop_sound.stop()
        except Exception:
            pass
        self._loop_sound = None

        try:
            pygame.mixer.music.stop()
            pygame.mixer.music.play(start=current_secs)
            self._play_start_time   = time.time() - current_secs
            self._paused_at_seconds = current_secs
            self.state = PlayerState.PLAYING
            self._timer.start()
        except Exception as e:
            print(f"AudioPlayer.stop_loop resume error: {e}")
            self.state = PlayerState.PLAYING

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
        if self.state == PlayerState.LOOP_PLAYING:
            elapsed = time.time() - self._loop_sound_wall
            return self._loop_sound_a_secs + (elapsed % max(self._loop_sound_dur, 1e-9))
        return 0.0

    def _tick(self) -> None:
        if self.state == PlayerState.LOOP_PLAYING:
            self.position_changed.emit(self.get_position())
            return
        if self.state != PlayerState.PLAYING:
            return
        if not pygame.mixer.music.get_busy():
            self.stop()
            self.playback_finished.emit()
            return
        self.position_changed.emit(self.get_position())
