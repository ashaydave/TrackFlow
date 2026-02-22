# analyzer/batch_analyzer.py
"""
Batch Analyzer — parallel track analysis with JSON result caching.
Uses ThreadPoolExecutor for concurrent analysis (3 workers).
Cache key: MD5 hash of (absolute path + file mtime + file size).
"""

import json
import hashlib
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal

from analyzer.audio_analyzer import AudioAnalyzer


CACHE_DIR = Path(__file__).parent.parent / 'data' / 'cache'
MAX_WORKERS = 3


def _cache_key(file_path: Path) -> str:
    """Stable cache key: md5 of path + mtime + size"""
    stat = file_path.stat()
    key_str = f"{file_path.absolute()}|{stat.st_mtime}|{stat.st_size}"
    return hashlib.md5(key_str.encode()).hexdigest()


def load_cached(file_path: Path) -> dict | None:
    """Return cached analysis result or None if not cached / stale."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / f"{_cache_key(file_path)}.json"
    if cache_file.exists():
        try:
            with open(cache_file) as f:
                return json.load(f)
        except Exception:
            cache_file.unlink(missing_ok=True)
    return None


def save_cached(file_path: Path, results: dict) -> None:
    """Save analysis results to cache."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / f"{_cache_key(file_path)}.json"
    with open(cache_file, 'w') as f:
        json.dump(results, f)


def is_cached(file_path: Path) -> bool:
    """Quick check without reading the file."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return (CACHE_DIR / f"{_cache_key(file_path)}.json").exists()


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
        self._cancelled = False

    def analyze_all(self, file_paths: list) -> None:
        """
        Analyze list of file paths. Emits signals as each completes.
        Cache hits are returned immediately without re-analyzing.
        Call from a background QThread or use run_in_thread().
        """
        self._cancelled = False
        total = len(file_paths)
        completed = 0
        cached_count = 0
        analyzer_pool = [AudioAnalyzer() for _ in range(MAX_WORKERS)]

        # First pass: emit cached results immediately
        uncached = []
        for i, path_str in enumerate(file_paths):
            if self._cancelled:
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
        if not uncached and not self._cancelled:
            self.all_done.emit(total - cached_count, cached_count)
            return

        def _analyze_one(args):
            idx, path_str = args
            if self._cancelled:
                return None, path_str, None
            try:
                analyzer = analyzer_pool[idx % MAX_WORKERS]
                results = analyzer.analyze_track(path_str)
                save_cached(Path(path_str), results)
                return 'ok', path_str, results
            except Exception as e:
                return 'error', path_str, str(e)

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(_analyze_one, item): item for item in uncached}
            for future in as_completed(futures):
                if self._cancelled:
                    break
                status, path_str, payload = future.result()
                completed += 1
                if status == 'ok':
                    self.track_done.emit(path_str, payload, completed, total)
                elif status == 'error':
                    self.error.emit(path_str, payload)
                self.progress.emit(completed, total)

        if not self._cancelled:
            self.all_done.emit(total - cached_count, cached_count)

    def cancel(self) -> None:
        self._cancelled = True
