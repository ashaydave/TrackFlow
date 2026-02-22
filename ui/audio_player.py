"""
Audio Player - Handles audio playback for track preview
"""

import pygame
from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from pathlib import Path
import time


class AudioPlayer(QObject):
    """Audio player with playback controls"""

    position_changed = pyqtSignal(float)  # Emits current position (0.0 to 1.0)
    playback_finished = pyqtSignal()

    def __init__(self):
        super().__init__()

        # Initialize pygame mixer
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)

        self.current_file = None
        self.is_playing = False
        self.duration = 0  # in seconds
        self.start_time = 0  # Track when playback started
        self.pause_position = 0  # Track position when paused

        # Timer to update playback position
        self.position_timer = QTimer()
        self.position_timer.setInterval(50)  # Update every 50ms for smooth playhead
        self.position_timer.timeout.connect(self.update_position)

    def load(self, file_path):
        """Load an audio file"""
        try:
            self.stop()

            # Ensure mixer is initialized
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)

            pygame.mixer.music.load(str(file_path))
            self.current_file = file_path
            self.duration = 0

            # Small delay to ensure file is loaded
            import time
            time.sleep(0.1)

            return True
        except Exception as e:
            print(f"Error loading audio: {e}")
            return False

    def set_duration(self, duration):
        """Set track duration (from analysis results)"""
        self.duration = duration

    def play(self):
        """Start playback from beginning"""
        if self.current_file:
            try:
                pygame.mixer.music.play()
                self.is_playing = True
                self.start_time = time.time()
                self.pause_position = 0
                self.position_timer.start()
            except Exception as e:
                print(f"Error playing: {e}")

    def pause(self):
        """Pause playback"""
        if self.is_playing:
            pygame.mixer.music.pause()
            self.is_playing = False
            # Save current position
            self.pause_position = self.get_position()
            self.position_timer.stop()

    def resume(self):
        """Resume playback"""
        if not self.is_playing and self.current_file:
            pygame.mixer.music.unpause()
            self.is_playing = True
            # Adjust start time to account for pause
            elapsed = self.pause_position * self.duration
            self.start_time = time.time() - elapsed
            self.position_timer.start()

    def stop(self):
        """Stop playback"""
        pygame.mixer.music.stop()
        self.is_playing = False
        self.pause_position = 0
        self.position_timer.stop()
        self.position_changed.emit(0.0)

    def seek(self, position):
        """Seek to position (0.0 to 1.0)"""
        if self.current_file and self.duration > 0:
            time_seconds = position * self.duration
            was_playing = self.is_playing

            try:
                # Stop current playback
                pygame.mixer.music.stop()

                # Restart from new position
                pygame.mixer.music.play(start=time_seconds)
                self.start_time = time.time() - time_seconds
                self.pause_position = position

                if was_playing:
                    self.is_playing = True
                    self.position_timer.start()
                else:
                    pygame.mixer.music.pause()
                    self.is_playing = False

                # Immediately update position
                self.position_changed.emit(position)

            except Exception as e:
                print(f"Error seeking: {e}")

    def get_position(self):
        """Get current playback position (0.0 to 1.0)"""
        if not self.current_file or self.duration == 0:
            return 0.0

        if not self.is_playing:
            return self.pause_position

        try:
            # Calculate position based on elapsed time
            elapsed = time.time() - self.start_time
            position = elapsed / self.duration
            return min(1.0, max(0.0, position))
        except:
            return 0.0

    def update_position(self):
        """Update and emit current position"""
        if self.is_playing:
            # Check if playback finished
            if not pygame.mixer.music.get_busy():
                self.stop()
                self.playback_finished.emit()
                return

            position = self.get_position()
            self.position_changed.emit(position)

    def set_volume(self, volume):
        """Set volume (0.0 to 1.0)"""
        pygame.mixer.music.set_volume(volume)

    def get_volume(self):
        """Get current volume (0.0 to 1.0)"""
        return pygame.mixer.music.get_volume()
