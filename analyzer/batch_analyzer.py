# analyzer/batch_analyzer.py
"""
Batch Analyzer — parallel track analysis with JSON result caching.
Uses ThreadPoolExecutor for concurrent analysis (3 workers).
Cache key: MD5 hash of (absolute path + file mtime + file size).
"""

import json
import hashlib
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal

from analyzer.audio_analyzer import AudioAnalyzer
from paths import get_cache_dir

MAX_WORKERS = 3


def _cache_key(file_path: Path) -> str:
    """Stable cache key: md5 of path + mtime + size"""
    stat = file_path.stat()
    key_str = f"{file_path.absolute()}|{stat.st_mtime}|{stat.st_size}"
    return hashlib.md5(key_str.encode()).hexdigest()


def load_cached(file_path: Path) -> dict | None:
    """Return cached analysis result or None if not cached / stale."""
    cache_file = get_cache_dir() / f"{_cache_key(file_path)}.json"
    if cache_file.exists():
        try:
            with open(cache_file) as f:
                return json.load(f)
        except Exception:
            cache_file.unlink(missing_ok=True)
    return None


def save_cached(file_path: Path, results: dict) -> None:
    """Save analysis results to cache."""
    cache_file = get_cache_dir() / f"{_cache_key(file_path)}.json"
    with open(cache_file, 'w') as f:
        json.dump(results, f)


def is_cached(file_path: Path) -> bool:
    """Quick check without reading the file."""
    return (get_cache_dir() / f"{_cache_key(file_path)}.json").exists()


class BatchAnalyzer(QObject):
    """
    Parallel batch analysis with caching.

    Signals:
        track_done(file_path, results, index, total)
        all_done(total_analyzed, total_cached)
        error(file_path, error_message)
        progress(current, total)
    """

    track_done = pyqtSignal(str, dict, int, int)
    all_done   = pyqtSignal(int, int)
    error      = pyqtSignal(str, str)
    progress   = pyqtSignal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cancel_event = threading.Event()

    def analyze_all(self, file_paths: list) -> None:
        """
        Analyze list of file paths. Emits signals as each completes.
        Cache hits are returned immediately without re-analyzing.
        Call from a background QThread.
        """
        self._cancel_event.clear()
        total = len(file_paths)
        completed = 0
        cached_count = 0

        # First pass: emit cached results immediately
        uncached = []
        for i, path_str in enumerate(file_paths):
            if self._cancel_event.is_set():
                break
            fp = Path(path_str)
            cached = load_cached(fp)
            if cached is not None:
                cached_count += 1
                completed += 1
                self.track_done.emit(path_str, cached, completed, total)
                self.progress.emit(completed, total)
            else:
                uncached.append((i, path_str))

        # Second pass: analyze uncached in parallel
        if not uncached or self._cancel_event.is_set():
            self.all_done.emit(total - cached_count, cached_count)
            return

        cancel_event = self._cancel_event  # local ref for thread safety

        def _analyze_one(args):
            idx, path_str = args
            if cancel_event.is_set():
                return 'cancelled', path_str, None
            try:
                # Fresh analyzer per task — thread-safe, no shared state
                analyzer = AudioAnalyzer()
                results = analyzer.analyze_track(path_str)
                save_cached(Path(path_str), results)
                return 'ok', path_str, results
            except Exception as e:
                return 'error', path_str, str(e)

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(_analyze_one, item): item for item in uncached}
            for future in as_completed(futures):
                status, path_str, payload = future.result()
                completed += 1
                if status == 'ok':
                    self.track_done.emit(path_str, payload, completed, total)
                elif status == 'error':
                    self.error.emit(path_str, payload)
                # 'cancelled' — skip silently, no signal needed
                self.progress.emit(completed, total)
                if cancel_event.is_set():
                    break

        self.all_done.emit(total - cached_count, cached_count)

    def cancel(self) -> None:
        self._cancel_event.set()
