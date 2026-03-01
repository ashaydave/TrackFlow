"""
SoulSeek folder watcher using watchdog.
Emits a Qt signal whenever a new audio file appears in the watched directory.
Handles both direct creation (on_created) and rename-on-completion
(on_moved) — SoulSeek typically saves as .tmp and renames when finished.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer


AUDIO_EXTS = {".mp3", ".wav", ".flac", ".m4a", ".ogg", ".aiff", ".aif", ".opus", ".webm"}


class _AudioHandler(FileSystemEventHandler):
    """Watchdog event handler that forwards audio-file events to a callback."""

    def __init__(self, callback):
        super().__init__()
        self._cb = callback

    def on_created(self, event) -> None:
        if not event.is_directory:
            path = Path(event.src_path)
            if path.suffix.lower() in AUDIO_EXTS:
                self._cb(str(path))

    def on_moved(self, event) -> None:
        """Catches SoulSeek's .tmp → final-filename rename on download completion."""
        if not event.is_directory:
            path = Path(event.dest_path)
            if path.suffix.lower() in AUDIO_EXTS:
                self._cb(str(path))


class FolderWatcher(QObject):
    """
    Watches a directory tree for new audio files and emits file_detected.

    Usage
    -----
    watcher = FolderWatcher()
    watcher.file_detected.connect(my_slot)
    watcher.start(r"C:\\Users\\me\\SoulSeek\\complete")
    # ... later ...
    watcher.stop()
    """

    file_detected = pyqtSignal(str)   # absolute path of the detected audio file

    def __init__(self, parent=None):
        super().__init__(parent)
        self._observer: Observer | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self, folder_path: str) -> bool:
        """
        Begin watching *folder_path* (recursively).
        Stops any existing watch first.
        Returns False if the folder does not exist.
        """
        self.stop()
        path = Path(folder_path)
        if not path.exists():
            return False

        handler = _AudioHandler(lambda fp: self.file_detected.emit(fp))
        self._observer = Observer()
        self._observer.schedule(handler, str(path), recursive=True)
        self._observer.start()
        return True

    def stop(self) -> None:
        """Stop watching and join the observer thread."""
        if self._observer is not None:
            self._observer.stop()
            self._observer.join()
            self._observer = None

    @property
    def is_watching(self) -> bool:
        return self._observer is not None and self._observer.is_alive()
