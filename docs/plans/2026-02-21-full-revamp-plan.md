# DJ Track Analyzer Full Revamp — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Revamp DJ Track Analyzer with frequency-colored waveform, ≤2s analysis speed, playback bug fix, batch processing with JSON cache, and professional cyberpunk UI.

**Architecture:** Six-file surgical revamp. Keep the working analysis logic skeleton, overhaul speed (librosa duration limit + background waveform thread), fix playback state machine, rewrite waveform renderer (vectorized numpy + frequency coloring), add batch analyzer with thread pool + cache, and rebuild UI layout/styles from scratch.

**Tech Stack:** Python 3.11, PyQt6, librosa, soundfile, mutagen, pygame, numpy, concurrent.futures

**Design doc:** `docs/plans/2026-02-21-full-revamp-design.md`

---

## Implementation Order

```
Task 1 → styles.py (no deps)
Task 2 → audio_analyzer.py (speed fix)
Task 3 → batch_analyzer.py (uses analyzer)
Task 4 → audio_player.py (bug fix, no UI deps)
Task 5 → waveform_dj.py (rewrite, no UI deps)
Task 6 → main_window.py (wires everything)
```

---

## Task 1: Centralized QSS Stylesheet

**Files:**
- Create: `ui/styles.py`

**Step 1: Create the file**

```python
# ui/styles.py
"""
Centralized stylesheet for DJ Track Analyzer.
Cyberpunk / dark DJ software aesthetic.
"""

COLORS = {
    'bg':           '#0a0a0f',
    'panel':        '#0f0f1a',
    'surface':      '#151525',
    'surface2':     '#1a1a2e',
    'accent':       '#0088ff',
    'accent2':      '#00ccff',
    'accent_dim':   '#004488',
    'text':         '#ffffff',
    'text2':        '#8899bb',
    'text3':        '#445566',
    'border':       '#1a2233',
    'hover':        '#1a1a3a',
    'success':      '#00ff88',
    'warning':      '#ffaa00',
    'error':        '#ff4444',
    'waveform_bg':  '#080810',
}

STYLESHEET = """
/* ─── Base ─────────────────────────────────────────────── */
QMainWindow, QWidget {
    background-color: #0a0a0f;
    color: #ffffff;
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 13px;
}

/* ─── Buttons ───────────────────────────────────────────── */
QPushButton {
    background-color: #151525;
    color: #ffffff;
    border: 1px solid #1a2233;
    border-radius: 4px;
    padding: 6px 14px;
    font-size: 12px;
    font-weight: 500;
}
QPushButton:hover {
    background-color: #1a1a3a;
    border-color: #0088ff;
    color: #00ccff;
}
QPushButton:pressed {
    background-color: #004488;
    border-color: #0088ff;
}
QPushButton:disabled {
    color: #445566;
    border-color: #1a2233;
    background-color: #0f0f1a;
}
QPushButton#btn_primary {
    background-color: #0055bb;
    border-color: #0088ff;
    color: #ffffff;
    font-weight: 600;
}
QPushButton#btn_primary:hover {
    background-color: #0066dd;
    border-color: #00ccff;
}
QPushButton#btn_play {
    background-color: #003366;
    border-color: #0088ff;
    font-size: 14px;
    font-weight: 700;
    min-width: 80px;
}
QPushButton#btn_play:hover {
    background-color: #004488;
    border-color: #00ccff;
}

/* ─── Track Table ───────────────────────────────────────── */
QTableWidget {
    background-color: #0a0a0f;
    alternate-background-color: #0d0d18;
    border: 1px solid #1a2233;
    border-radius: 4px;
    gridline-color: #1a2233;
    selection-background-color: #0d2244;
    selection-color: #ffffff;
}
QTableWidget::item {
    padding: 4px 6px;
    border: none;
}
QTableWidget::item:selected {
    background-color: #0d2244;
    color: #00ccff;
}
QHeaderView::section {
    background-color: #0f0f1a;
    color: #8899bb;
    border: none;
    border-bottom: 1px solid #1a2233;
    border-right: 1px solid #1a2233;
    padding: 5px 6px;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1px;
}

/* ─── Search Box ────────────────────────────────────────── */
QLineEdit {
    background-color: #0f0f1a;
    border: 1px solid #1a2233;
    border-radius: 4px;
    color: #ffffff;
    padding: 5px 10px;
    font-size: 12px;
}
QLineEdit:focus {
    border-color: #0088ff;
}
QLineEdit::placeholder {
    color: #445566;
}

/* ─── Sliders ───────────────────────────────────────────── */
QSlider::groove:horizontal {
    background: #1a2233;
    height: 4px;
    border-radius: 2px;
}
QSlider::sub-page:horizontal {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #0055bb, stop:1 #00aaff);
    height: 4px;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #00aaff;
    width: 12px;
    height: 12px;
    margin: -4px 0;
    border-radius: 6px;
    border: 2px solid #0a0a0f;
}
QSlider::handle:horizontal:hover {
    background: #00ccff;
    border-color: #0088ff;
}

/* ─── Progress Bar ──────────────────────────────────────── */
QProgressBar {
    background-color: #1a2233;
    border: none;
    border-radius: 3px;
    height: 6px;
    text-align: center;
    color: transparent;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #0055bb, stop:1 #00ccff);
    border-radius: 3px;
}

/* ─── Scroll Bars ───────────────────────────────────────── */
QScrollBar:vertical {
    background: #0a0a0f;
    width: 8px;
    border: none;
}
QScrollBar::handle:vertical {
    background: #1a2233;
    border-radius: 4px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover {
    background: #0088ff;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

/* ─── Status Bar ────────────────────────────────────────── */
QStatusBar {
    background-color: #0f0f1a;
    color: #8899bb;
    border-top: 1px solid #1a2233;
    font-size: 11px;
    padding: 2px 8px;
}

/* ─── Labels ────────────────────────────────────────────── */
QLabel#track_title {
    font-size: 16px;
    font-weight: 700;
    color: #ffffff;
}
QLabel#track_artist {
    font-size: 12px;
    color: #8899bb;
}
QLabel#info_label {
    font-size: 10px;
    color: #445566;
    text-transform: uppercase;
    letter-spacing: 1px;
}
QLabel#info_value_large {
    font-size: 34px;
    font-weight: 800;
    color: #00aaff;
    font-family: "Consolas", "Courier New", monospace;
}
QLabel#info_value_medium {
    font-size: 26px;
    font-weight: 700;
    color: #ffffff;
    font-family: "Consolas", "Courier New", monospace;
}
QLabel#camelot_value {
    font-size: 26px;
    font-weight: 700;
    color: #00ccff;
    font-family: "Consolas", "Courier New", monospace;
}
QLabel#meta_text {
    font-size: 11px;
    color: #8899bb;
}
QLabel#section_header {
    font-size: 10px;
    font-weight: 700;
    color: #445566;
    text-transform: uppercase;
    letter-spacing: 2px;
}
QLabel#time_display {
    font-size: 13px;
    font-weight: 600;
    color: #8899bb;
    font-family: "Consolas", monospace;
    min-width: 95px;
}

/* ─── Info Cards ────────────────────────────────────────── */
QWidget#info_card {
    background-color: #0f0f1a;
    border: 1px solid #1a2233;
    border-radius: 6px;
}
QWidget#info_card:hover {
    border-color: #0044aa;
}

/* ─── Splitter ──────────────────────────────────────────── */
QSplitter::handle {
    background-color: #1a2233;
    width: 1px;
}

/* ─── Context Menu ──────────────────────────────────────── */
QMenu {
    background-color: #0f0f1a;
    border: 1px solid #1a2233;
    border-radius: 4px;
    padding: 4px;
}
QMenu::item {
    padding: 6px 20px;
    border-radius: 3px;
}
QMenu::item:selected {
    background-color: #1a1a3a;
    color: #00ccff;
}

/* ─── Tooltip ───────────────────────────────────────────── */
QToolTip {
    background-color: #0f0f1a;
    color: #ffffff;
    border: 1px solid #0088ff;
    padding: 4px 8px;
    border-radius: 3px;
    font-size: 11px;
}
"""
```

**Step 2: Verify import works**

```bash
cd "C:\Users\ashay\Documents\Claude\dj-track-analyzer"
conda activate dj-analyzer
python -c "from ui.styles import STYLESHEET, COLORS; print('OK', len(STYLESHEET), 'chars')"
```
Expected: `OK <number> chars`

**Step 3: Commit**

```bash
git add ui/styles.py
git commit -m "feat: add centralized cyberpunk QSS stylesheet"
```

---

## Task 2: Audio Analyzer Speed Overhaul

**Files:**
- Modify: `analyzer/audio_analyzer.py`

**Key insight:** `librosa.load(file, duration=60)` loads only the first 60 seconds. For BPM/key/energy on a 5-min track this is all we need. Full track needed only for waveform (handled separately in background).

**Step 1: Add test for speed**

Create `tests/test_analyzer_speed.py`:

```python
"""Test that analysis completes in under 3 seconds"""
import time
import pytest
from pathlib import Path
from analyzer.audio_analyzer import AudioAnalyzer

SAMPLE_TRACK = r"C:\Users\ashay\Downloads\y2mate.com - LudoWic  MIND PARADE Katana ZERO DLC_320kbps.mp3"

@pytest.mark.skipif(not Path(SAMPLE_TRACK).exists(), reason="Sample track not found")
def test_analysis_speed():
    """Analysis should complete in under 3 seconds"""
    analyzer = AudioAnalyzer()
    start = time.time()
    result = analyzer.analyze_track(SAMPLE_TRACK)
    elapsed = time.time() - start
    assert elapsed < 3.0, f"Analysis took {elapsed:.1f}s (limit: 3s)"
    assert result['bpm'] is not None
    assert result['key']['camelot'] is not None

@pytest.mark.skipif(not Path(SAMPLE_TRACK).exists(), reason="Sample track not found")
def test_analysis_results_unchanged():
    """Core results should still be accurate"""
    analyzer = AudioAnalyzer()
    result = analyzer.analyze_track(SAMPLE_TRACK)
    # These are the known-good values from before
    assert 100 <= result['bpm'] <= 110, f"BPM {result['bpm']} out of expected range"
    assert 'Major' in result['key']['notation'] or 'Minor' in result['key']['notation']
    assert 1 <= result['energy']['level'] <= 10
```

**Step 2: Run test to see current baseline**

```bash
cd "C:\Users\ashay\Documents\Claude\dj-track-analyzer"
conda activate dj-analyzer
python -m pytest tests/test_analyzer_speed.py -v -s
```
Expected: FAIL (too slow, or tests/ dir doesn't exist yet — `mkdir tests && touch tests/__init__.py` first)

```bash
mkdir tests
echo. > tests\__init__.py
```

**Step 3: Rewrite `analyzer/audio_analyzer.py`**

Replace the file entirely:

```python
"""
DJ Track Analyzer - Core Audio Analysis Engine
Optimized for speed: analyzes first 60s only (sufficient for BPM/key/energy).
Waveform data is generated separately by WaveformThread.
"""

import librosa
import numpy as np
from mutagen import File as MutagenFile
from pathlib import Path
import json


class AudioAnalyzer:
    """Fast audio analysis — BPM, key, energy from first 60 seconds."""

    ANALYSIS_DURATION = 60  # seconds — sufficient for electronic music
    SAMPLE_RATE = 22050

    def __init__(self, fast_mode=True):
        self.sample_rate = self.SAMPLE_RATE
        self.fast_mode = fast_mode  # kept for API compat

    def analyze_track(self, file_path):
        """
        Analyze a track. Only loads first 60s for speed.
        Duration and metadata come from mutagen (no audio decode).

        Returns:
            dict with: file_path, filename, bpm, key, energy,
                       metadata, audio_info, duration
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Track not found: {file_path}")

        # --- Fast path: metadata + duration from tags (no audio decode) ---
        metadata = self._extract_metadata(file_path)
        audio_info = self._get_audio_info(file_path)

        # --- Load only first 60s for analysis ---
        y, sr = librosa.load(
            str(file_path),
            sr=self.sample_rate,
            duration=self.ANALYSIS_DURATION,
            mono=True,
        )

        results = {
            'file_path': str(file_path.absolute()),
            'filename': file_path.name,
            'bpm': self._detect_bpm(y, sr),
            'key': self._detect_key(y, sr),
            'energy': self._calculate_energy(y),
            'metadata': metadata,
            'audio_info': audio_info,
            'duration': audio_info.get('duration', len(y) / sr),
        }

        return results

    # ── BPM ──────────────────────────────────────────────────────────────

    def _detect_bpm(self, y, sr):
        try:
            tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
            if isinstance(tempo, np.ndarray):
                bpm = float(tempo.flat[0]) if tempo.size > 0 else None
            else:
                bpm = float(tempo)
            return round(bpm, 1) if bpm else None
        except Exception as e:
            print(f"BPM detection failed: {e}")
            return None

    # ── KEY ──────────────────────────────────────────────────────────────

    def _detect_key(self, y, sr):
        try:
            # Use first 30s for key (chroma stabilizes quickly)
            y_key = y[:sr * 30] if len(y) > sr * 30 else y
            chroma = librosa.feature.chroma_cqt(y=y_key, sr=sr)
            chroma_avg = np.mean(chroma, axis=1)
            key_index = int(np.argmax(chroma_avg))
            is_major = self._is_major_key(chroma_avg)

            return {
                'notation': self._index_to_key(key_index, is_major),
                'camelot': self._to_camelot(key_index, is_major),
                'open_key': self._to_open_key(key_index, is_major),
                'confidence': 'medium',
            }
        except Exception as e:
            print(f"Key detection failed: {e}")
            return {'notation': 'Unknown', 'camelot': 'N/A', 'open_key': 'N/A', 'confidence': 'none'}

    def _is_major_key(self, chroma_avg):
        major_profile = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09,
                                   2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
        minor_profile = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.97,
                                   2.73, 5.17, 3.00, 4.00, 1.94, 3.17])
        chroma_norm = chroma_avg / (np.sum(chroma_avg) + 1e-8)
        scores_maj = [np.dot(np.roll(chroma_norm, -i), major_profile / np.sum(major_profile))
                      for i in range(12)]
        scores_min = [np.dot(np.roll(chroma_norm, -i), minor_profile / np.sum(minor_profile))
                      for i in range(12)]
        return max(scores_maj) >= max(scores_min)

    def _index_to_key(self, key_index, is_major):
        keys = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        return f"{keys[key_index % 12]} {'Major' if is_major else 'Minor'}"

    def _to_camelot(self, key_index, is_major):
        camelot_major = ['8B', '3B', '10B', '5B', '12B', '7B', '2B', '9B', '4B', '11B', '6B', '1B']
        camelot_minor = ['5A', '12A', '7A', '2A', '9A', '4A', '11A', '6A', '1A', '8A', '3A', '10A']
        return (camelot_major if is_major else camelot_minor)[key_index % 12]

    def _to_open_key(self, key_index, is_major):
        open_key_numbers = [1, 8, 3, 10, 5, 12, 7, 2, 9, 4, 11, 6]
        number = open_key_numbers[key_index % 12]
        return f"{number}{'m' if is_major else 'd'}"

    # ── ENERGY ───────────────────────────────────────────────────────────

    def _calculate_energy(self, y):
        try:
            rms = librosa.feature.rms(y=y)[0]
            avg_rms = float(np.mean(rms))
            thresholds = [0.05, 0.08, 0.11, 0.14, 0.17, 0.20, 0.23, 0.26, 0.30]
            energy = next((i + 1 for i, t in enumerate(thresholds) if avg_rms < t), 10)
            descriptions = {1: 'Very Low', 2: 'Low', 3: 'Low-Med', 4: 'Medium', 5: 'Medium',
                            6: 'Med-High', 7: 'High', 8: 'High', 9: 'Very High', 10: 'Peak'}
            return {'level': energy, 'rms': avg_rms, 'description': descriptions[energy]}
        except Exception as e:
            print(f"Energy calculation failed: {e}")
            return {'level': 5, 'rms': 0.0, 'description': 'Unknown'}

    # ── METADATA ─────────────────────────────────────────────────────────

    def _extract_metadata(self, file_path):
        try:
            audio = MutagenFile(str(file_path))
            if audio is None:
                return self._default_metadata()
            return {
                'artist': self._get_tag(audio, ['artist', 'TPE1', '\xa9ART']),
                'title':  self._get_tag(audio, ['title',  'TIT2', '\xa9nam']),
                'album':  self._get_tag(audio, ['album',  'TALB', '\xa9alb']),
                'genre':  self._get_tag(audio, ['genre',  'TCON', '\xa9gen']),
                'year':   self._get_tag(audio, ['date',   'TDRC', '\xa9day']),
                'comment':self._get_tag(audio, ['comment','COMM', '\xa9cmt']),
            }
        except Exception:
            return self._default_metadata()

    def _get_tag(self, audio, tag_names):
        for tag in tag_names:
            if tag in audio:
                value = audio[tag]
                return str(value[0]) if isinstance(value, list) else str(value)
        return ''

    def _default_metadata(self):
        return {'artist': '', 'title': '', 'album': '', 'genre': '', 'year': '', 'comment': ''}

    # ── AUDIO INFO ───────────────────────────────────────────────────────

    def _get_audio_info(self, file_path):
        try:
            audio = MutagenFile(str(file_path))
            if audio is None:
                return self._default_audio_info(file_path)
            bitrate     = getattr(audio.info, 'bitrate', 0) // 1000
            sample_rate = getattr(audio.info, 'sample_rate', 44100)
            channels    = getattr(audio.info, 'channels', 2)
            duration    = getattr(audio.info, 'length', 0.0)
            file_size   = round(file_path.stat().st_size / (1024 * 1024), 2)
            return {
                'format':       file_path.suffix.upper().replace('.', ''),
                'bitrate':      bitrate,
                'sample_rate':  sample_rate,
                'channels':     channels,
                'file_size_mb': file_size,
                'duration':     duration,
            }
        except Exception:
            return self._default_audio_info(file_path)

    def _default_audio_info(self, file_path):
        return {
            'format':       file_path.suffix.upper().replace('.', ''),
            'bitrate':      0,
            'sample_rate':  44100,
            'channels':     2,
            'file_size_mb': round(file_path.stat().st_size / (1024 * 1024), 2),
            'duration':     0.0,
        }

    # ── SAVE ─────────────────────────────────────────────────────────────

    def save_analysis(self, results, output_path=None):
        if output_path is None:
            output_path = Path(results['file_path']).with_suffix('.analysis.json')
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2)
        return output_path
```

**Step 4: Run tests**

```bash
cd "C:\Users\ashay\Documents\Claude\dj-track-analyzer"
conda activate dj-analyzer
python -m pytest tests/test_analyzer_speed.py -v -s
```
Expected: Both tests PASS. Analysis time < 3s.

**Step 5: Verify results match expected values**

```bash
python -c "
from analyzer.audio_analyzer import AudioAnalyzer
import time
a = AudioAnalyzer()
t = time.time()
r = a.analyze_track(r'C:\Users\ashay\Downloads\y2mate.com - LudoWic  MIND PARADE Katana ZERO DLC_320kbps.mp3')
print(f'Time: {time.time()-t:.2f}s')
print(f'BPM: {r[\"bpm\"]}')
print(f'Key: {r[\"key\"][\"notation\"]} / {r[\"key\"][\"camelot\"]}')
print(f'Energy: {r[\"energy\"][\"level\"]}/10')
print(f'Duration: {r[\"duration\"]:.1f}s')
"
```
Expected output: Time < 3s, BPM ~103.4, Key A Major / 11B, Duration 320.x

**Step 6: Commit**

```bash
git add analyzer/audio_analyzer.py tests/
git commit -m "perf: limit analysis to first 60s, get duration from mutagen"
```

---

## Task 3: Batch Analyzer with JSON Cache

**Files:**
- Create: `analyzer/batch_analyzer.py`

**Step 1: Create the file**

```python
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

    def analyze_all(self, file_paths: list[str]) -> None:
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
```

**Step 2: Create data/cache directory**

```bash
mkdir "C:\Users\ashay\Documents\Claude\dj-track-analyzer\data"
mkdir "C:\Users\ashay\Documents\Claude\dj-track-analyzer\data\cache"
echo. > "C:\Users\ashay\Documents\Claude\dj-track-analyzer\data\.gitkeep"
```

**Step 3: Test cache functions**

```python
# tests/test_batch_analyzer.py
import pytest
from pathlib import Path
from analyzer.batch_analyzer import _cache_key, load_cached, save_cached, is_cached, CACHE_DIR

SAMPLE_TRACK = r"C:\Users\ashay\Downloads\y2mate.com - LudoWic  MIND PARADE Katana ZERO DLC_320kbps.mp3"

@pytest.mark.skipif(not Path(SAMPLE_TRACK).exists(), reason="Sample track not found")
def test_cache_roundtrip():
    fp = Path(SAMPLE_TRACK)
    fake_results = {'bpm': 103.4, 'filename': 'test.mp3', 'file_path': str(fp)}

    # Write cache
    save_cached(fp, fake_results)
    assert is_cached(fp)

    # Read it back
    loaded = load_cached(fp)
    assert loaded is not None
    assert loaded['bpm'] == 103.4

    # Clean up
    cache_file = CACHE_DIR / f"{_cache_key(fp)}.json"
    cache_file.unlink()
    assert not is_cached(fp)

def test_missing_file_not_cached(tmp_path):
    fake = tmp_path / "nonexistent.mp3"
    fake.touch()  # create file so stat() works
    assert not is_cached(fake)
    fake.unlink()
```

**Step 4: Run tests**

```bash
conda activate dj-analyzer
python -m pytest tests/test_batch_analyzer.py -v
```
Expected: All tests PASS.

**Step 5: Commit**

```bash
git add analyzer/batch_analyzer.py tests/test_batch_analyzer.py data/.gitkeep
git commit -m "feat: add batch analyzer with thread pool and JSON cache"
```

---

## Task 4: Audio Player Playback Bug Fix

**Files:**
- Modify: `ui/audio_player.py`

**Root cause:** `toggle_playback()` in `main_window.py` calls `resume()` when `current_file` is set, even when audio was never started (state = STOPPED). `resume()` calls `pygame.mixer.music.unpause()` on a track that was never played → silent failure.

**Fix:** Add explicit state tracking. Replace entire file:

**Step 1: Write tests**

```python
# tests/test_audio_player.py
"""Test AudioPlayer state machine"""
import pytest

# Mock pygame before import
import sys
from unittest.mock import MagicMock, patch

# We test the state logic without real audio
def test_initial_state():
    """Player starts in STOPPED state"""
    with patch.dict('sys.modules', {'pygame': MagicMock(), 'pygame.mixer': MagicMock()}):
        import importlib
        import ui.audio_player as ap_module
        importlib.reload(ap_module)
        player = ap_module.AudioPlayer()
        assert player.state == ap_module.PlayerState.STOPPED
        assert not player.is_playing

def test_can_play_after_load(tmp_path):
    """After loading a file, is_ready_to_play is True"""
    with patch.dict('sys.modules', {'pygame': MagicMock(), 'pygame.mixer': MagicMock()}):
        import importlib
        import ui.audio_player as ap_module
        importlib.reload(ap_module)
        player = ap_module.AudioPlayer()
        fake_file = tmp_path / "test.mp3"
        fake_file.write_bytes(b"fake")
        # Patch mixer.music.load to not actually load
        result = player.load(str(fake_file))
        assert result is True
        assert player.current_file == str(fake_file)
```

**Step 2: Run tests (expected to fail — imports need real pygame)**

```bash
conda activate dj-analyzer
python -m pytest tests/test_audio_player.py -v -s 2>&1 | head -30
```

**Step 3: Replace `ui/audio_player.py`**

```python
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
```

**Step 4: Fix `toggle_playback` in main_window.py** (anticipate this — note it for Task 6):

The new correct logic:
```python
def toggle_playback(self):
    if self.audio_player.state == PlayerState.PLAYING:
        self.audio_player.pause()
        self.btn_play.setText("▶ Play")
    elif self.audio_player.state == PlayerState.PAUSED:
        self.audio_player.resume()
        self.btn_play.setText("⏸ Pause")
    else:  # STOPPED
        self.audio_player.play()
        self.btn_play.setText("⏸ Pause")
```

**Step 5: Quick smoke test**

```bash
conda activate dj-analyzer
python -c "
from ui.audio_player import AudioPlayer, PlayerState
from PyQt6.QtWidgets import QApplication; import sys
app = QApplication(sys.argv)
p = AudioPlayer()
assert p.state == PlayerState.STOPPED
assert not p.is_playing
print('State machine OK')
"
```

**Step 6: Commit**

```bash
git add ui/audio_player.py
git commit -m "fix: rewrite audio player with explicit state machine, fix play-on-first-click bug"
```

---

## Task 5: Frequency-Colored Waveform (Complete Rewrite)

**Files:**
- Modify: `ui/waveform_dj.py`

**Design:**
- Two waveforms: `OverviewWaveform` (60px, full track) and `MainWaveform` (130px, shows full track or zoomed window)
- Data: numpy array of shape `(N_BARS, 4)` — columns: amplitude, bass_ratio, mid_ratio, high_ratio
- Color: mix between bass-blue, mid-cyan, high-white based on ratios
- Rendering: pre-compute data in a thread; paint loop draws pre-computed rects (fast — 300 iterations, no data computation in paintEvent)
- `WaveformDJ` is a container widget with both + a thread to generate data

**Step 1: Write the file**

```python
# ui/waveform_dj.py
"""
DJ-Style Frequency-Colored Waveform
====================================
Two widgets stacked vertically:
  - OverviewWaveform: full track overview, 60px, click-to-seek
  - MainWaveform:     main detail view, 130px, click-to-seek

Waveform data is a numpy array (N_BARS, 4):
  col 0: amplitude (0–1, normalized)
  col 1: bass ratio  (0–200 Hz share of total energy)
  col 2: mid ratio   (200–4000 Hz)
  col 3: high ratio  (4000+ Hz)

Color mapping:
  bass  → #0055ff  (deep blue)
  mid   → #00aaff  (sky blue / cyan)
  high  → #ccddff  (near-white blue)
  Mix   = weighted sum by ratio

Rendering: paintEvent uses pre-computed data array (no audio math).
"""

import numpy as np
import librosa
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QRect
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QLinearGradient


# ── Color constants (RGB tuples) ──────────────────────────────────────────────

BASS_COLOR  = (0,   85,  255)   # deep blue
MID_COLOR   = (0,  170,  255)   # sky cyan
HIGH_COLOR  = (180, 220, 255)   # near-white blue
BG_COLOR    = QColor(8, 8, 16)
PLAYED_DIM  = 0.35              # darken played portion to this fraction
PLAYHEAD_COLOR = QColor(255, 255, 255)


def _mix_color(amp, bass, mid, high) -> QColor:
    """Blend bass/mid/high color by energy ratios."""
    total = bass + mid + high + 1e-9
    r = int((BASS_COLOR[0] * bass + MID_COLOR[0] * mid + HIGH_COLOR[0] * high) / total)
    g = int((BASS_COLOR[1] * bass + MID_COLOR[1] * mid + HIGH_COLOR[1] * high) / total)
    b = int((BASS_COLOR[2] * bass + MID_COLOR[2] * mid + HIGH_COLOR[2] * high) / total)
    # Scale brightness by amplitude (makes quiet parts darker naturally)
    brightness = 0.3 + 0.7 * amp
    return QColor(int(r * brightness), int(g * brightness), int(b * brightness))


# ── Data computation (runs in background thread) ──────────────────────────────

class WaveformDataThread(QThread):
    """Computes frequency-colored bar data from an audio file."""

    data_ready = pyqtSignal(np.ndarray)   # shape (N, 4)
    failed     = pyqtSignal(str)

    N_BARS     = 400
    N_FFT      = 512
    SR         = 22050

    def __init__(self, file_path: str):
        super().__init__()
        self.file_path = file_path

    def run(self):
        try:
            # Load full track at low SR for waveform
            y, sr = librosa.load(self.file_path, sr=self.SR, mono=True)
            data = self._compute_bars(y, sr)
            self.data_ready.emit(data)
        except Exception as e:
            self.failed.emit(str(e))

    def _compute_bars(self, y: np.ndarray, sr: int) -> np.ndarray:
        n = self.N_BARS
        spb = max(1, len(y) // n)                    # samples per bar
        fft_n = self.N_FFT
        freqs = np.fft.rfftfreq(fft_n, d=1 / sr)
        bass_mask = freqs < 200
        mid_mask  = (freqs >= 200) & (freqs < 4000)
        high_mask = freqs >= 4000

        bars = np.zeros((n, 4), dtype=np.float32)

        for i in range(n):
            start = i * spb
            chunk = y[start: start + fft_n]
            if len(chunk) < fft_n:
                chunk = np.pad(chunk, (0, fft_n - len(chunk)))

            bars[i, 0] = np.sqrt(np.mean(chunk ** 2))   # RMS amplitude

            spec = np.abs(np.fft.rfft(chunk))
            total = spec.sum() + 1e-9
            bars[i, 1] = spec[bass_mask].sum() / total
            bars[i, 2] = spec[mid_mask].sum()  / total
            bars[i, 3] = spec[high_mask].sum() / total

        # Normalize amplitude to 0–1
        max_amp = bars[:, 0].max() + 1e-9
        bars[:, 0] /= max_amp

        return bars


# ── Base waveform widget ──────────────────────────────────────────────────────

class _BaseWaveform(QWidget):
    """Shared rendering logic for overview and main waveform."""

    position_clicked = pyqtSignal(float)    # 0.0–1.0

    BAR_W = 2   # bar width in pixels
    GAP   = 1   # gap between bars

    def __init__(self, height: int, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(height)
        self.setMaximumHeight(height)
        self.setMouseTracking(True)
        self._data: np.ndarray | None = None      # shape (N, 4)
        self._position: float = 0.0
        self._hover_x: int = -1

    def set_data(self, data: np.ndarray):
        self._data = data
        self.update()

    def set_position(self, pos: float):
        self._position = max(0.0, min(1.0, pos))
        self.update()

    def clear(self):
        self._data = None
        self._position = 0.0
        self.update()

    # ── Paint ─────────────────────────────────────────────────────────────

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)  # crisp bars

        w, h = self.width(), self.height()
        painter.fillRect(0, 0, w, h, BG_COLOR)

        if self._data is None:
            painter.setPen(QColor(50, 60, 80))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Loading waveform…")
            return

        self._draw_bars(painter, w, h)
        self._draw_playhead(painter, w, h)

    def _draw_bars(self, painter: QPainter, w: int, h: int):
        data = self._data
        n = len(data)
        step = self.BAR_W + self.GAP
        n_visible = min(n, w // step)
        half_h = h / 2
        playhead_x = int(self._position * w)

        painter.setPen(Qt.PenStyle.NoPen)

        for i in range(n_visible):
            x = i * step
            bar_idx = int(i * n / n_visible)
            amp, bass, mid, high = data[bar_idx]

            bar_h = max(1, int(amp * half_h * 0.92))
            color = _mix_color(amp, bass, mid, high)

            # Darken played portion
            if x < playhead_x:
                color = QColor(
                    int(color.red()   * PLAYED_DIM),
                    int(color.green() * PLAYED_DIM),
                    int(color.blue()  * PLAYED_DIM),
                )

            painter.setBrush(QBrush(color))
            # Draw mirrored bars (top + bottom from center)
            painter.drawRect(x, int(half_h - bar_h), self.BAR_W, bar_h * 2)

    def _draw_playhead(self, painter: QPainter, w: int, h: int):
        if self._position <= 0.0:
            return
        x = int(self._position * w)
        painter.setPen(QPen(PLAYHEAD_COLOR, 2))
        painter.drawLine(x, 0, x, h)
        # Triangle marker at top
        painter.setBrush(QBrush(PLAYHEAD_COLOR))
        painter.setPen(Qt.PenStyle.NoPen)
        sz = 6
        pts = [
            (x - sz, 0),
            (x + sz, 0),
            (x,      sz * 2),
        ]
        from PyQt6.QtCore import QPointF
        painter.drawPolygon([QPointF(px, py) for px, py in pts])

    # ── Mouse ─────────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._data is not None:
            pos = max(0.0, min(1.0, event.position().x() / self.width()))
            self.position_clicked.emit(pos)

    def mouseMoveEvent(self, event):
        self._hover_x = int(event.position().x())
        self.update()

    def leaveEvent(self, event):
        self._hover_x = -1
        self.update()


# ── Public container widget ───────────────────────────────────────────────────

class WaveformDJ(QWidget):
    """
    Container with OverviewWaveform + MainWaveform stacked vertically.
    Manages WaveformDataThread lifecycle.
    """

    position_clicked = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread: WaveformDataThread | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self.overview = _BaseWaveform(height=50)
        self.main     = _BaseWaveform(height=130)

        layout.addWidget(self.overview)
        layout.addWidget(self.main)

        self.overview.position_clicked.connect(self.position_clicked)
        self.main.position_clicked.connect(self.position_clicked)

    def set_waveform_from_file(self, file_path: str):
        """Start background thread to compute waveform data."""
        # Cancel previous thread if still running
        if self._thread and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(500)

        self.overview.clear()
        self.main.clear()

        self._thread = WaveformDataThread(file_path)
        self._thread.data_ready.connect(self._on_data_ready)
        self._thread.failed.connect(lambda e: print(f"Waveform error: {e}"))
        self._thread.start()

    def _on_data_ready(self, data: np.ndarray):
        self.overview.set_data(data)
        self.main.set_data(data)

    def set_playback_position(self, pos: float):
        self.overview.set_position(pos)
        self.main.set_position(pos)

    def clear(self):
        self.overview.clear()
        self.main.clear()
```

**Step 2: Quick render test**

```bash
conda activate dj-analyzer
python -c "
from PyQt6.QtWidgets import QApplication
import sys, numpy as np
app = QApplication(sys.argv)
from ui.waveform_dj import WaveformDJ
w = WaveformDJ()
w.show()
w.resize(900, 200)
# inject fake data
fake = np.random.rand(400, 4).astype(np.float32)
fake[:, 0] = np.abs(np.sin(np.linspace(0, 20, 400)))
fake[:, 1:] = fake[:, 1:] / fake[:, 1:].sum(axis=1, keepdims=True)
w.overview.set_data(fake)
w.main.set_data(fake)
w.set_playback_position(0.3)
print('Waveform renders OK')
app.exec()
"
```
Expected: Window appears with frequency-colored waveform and playhead at 30%.

**Step 3: Commit**

```bash
git add ui/waveform_dj.py
git commit -m "feat: rewrite waveform with frequency coloring and background data thread"
```

---

## Task 6: Main Window — Full UI Revamp

**Files:**
- Modify: `ui/main_window.py`

This is the largest task. Replace the entire file with the revamped version.

**Step 1: Write the revamped `main_window.py`**

```python
# ui/main_window.py
"""
DJ Track Analyzer — Main Window (Revamped)
Professional cyberpunk DJ software UI.
"""

import os
import sys
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QPushButton, QLabel, QLineEdit, QTableWidget, QTableWidgetItem,
    QFileDialog, QHeaderView, QProgressBar, QStatusBar, QSlider,
    QMenu, QApplication,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QPoint
from PyQt6.QtGui import QFont, QColor, QAction

sys.path.insert(0, str(Path(__file__).parent.parent))
from analyzer.audio_analyzer import AudioAnalyzer
from analyzer.batch_analyzer import BatchAnalyzer, is_cached
from ui.waveform_dj import WaveformDJ
from ui.audio_player import AudioPlayer, PlayerState
from ui.styles import STYLESHEET


# ── Row status colors ─────────────────────────────────────────────────────────

ROW_PENDING   = QColor(30,  30,  45)
ROW_ANALYZING = QColor(10,  30,  70)
ROW_DONE      = QColor(15,  15,  28)

AUDIO_EXTS = {'.mp3', '.wav', '.flac', '.m4a', '.ogg', '.aiff', '.aif'}


# ── Analysis thread (single track) ───────────────────────────────────────────

class AnalysisThread(QThread):
    finished = pyqtSignal(dict)
    error    = pyqtSignal(str)

    def __init__(self, file_path: str):
        super().__init__()
        self.file_path = file_path
        self._analyzer = AudioAnalyzer()

    def run(self):
        try:
            self.finished.emit(self._analyzer.analyze_track(self.file_path))
        except Exception as e:
            self.error.emit(str(e))


# ── Batch worker thread ───────────────────────────────────────────────────────

class BatchThread(QThread):
    """Runs BatchAnalyzer.analyze_all() off the main thread."""

    track_done = pyqtSignal(str, dict, int, int)
    all_done   = pyqtSignal(int, int)
    error      = pyqtSignal(str, str)
    progress   = pyqtSignal(int, int)

    def __init__(self, file_paths: list[str]):
        super().__init__()
        self._paths = file_paths
        self._batch = BatchAnalyzer()
        self._batch.track_done.connect(self.track_done)
        self._batch.all_done.connect(self.all_done)
        self._batch.error.connect(self.error)
        self._batch.progress.connect(self.progress)

    def run(self):
        self._batch.analyze_all(self._paths)

    def cancel(self):
        self._batch.cancel()


# ── Main Window ───────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.current_track: dict | None = None
        self.library_files: list[str] = []        # all file paths in current folder
        self.analysis_thread: AnalysisThread | None = None
        self.batch_thread: BatchThread | None = None
        self._row_map: dict[str, int] = {}        # file_path → table row index

        self.audio_player = AudioPlayer()
        self.audio_player.position_changed.connect(self._on_position_changed)
        self.audio_player.playback_finished.connect(self._on_playback_finished)
        self.audio_player.set_volume(0.7)

        self.setWindowTitle("DJ Track Analyzer")
        self.setMinimumSize(1200, 720)
        self.resize(1400, 820)

        self._init_ui()
        self.setStyleSheet(STYLESHEET)

    # ── UI Construction ───────────────────────────────────────────────────

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        root.addLayout(self._build_toolbar())

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_library_panel())
        splitter.addWidget(self._build_detail_panel())
        splitter.setSizes([340, 1060])
        root.addWidget(splitter)

        sb = QStatusBar()
        self.setStatusBar(sb)
        self._status = sb
        sb.showMessage("Ready — load a track or folder")

    def _build_toolbar(self) -> QHBoxLayout:
        lay = QHBoxLayout()
        lay.setSpacing(6)

        self.btn_load_track = QPushButton("Load Track")
        self.btn_load_folder = QPushButton("Load Folder")
        self.btn_analyze_all = QPushButton("Analyze All")
        self.btn_analyze_all.setObjectName("btn_primary")
        self.btn_analyze_all.setEnabled(False)

        for btn in (self.btn_load_track, self.btn_load_folder, self.btn_analyze_all):
            btn.setFixedHeight(32)
            lay.addWidget(btn)

        self.batch_progress = QProgressBar()
        self.batch_progress.setFixedHeight(8)
        self.batch_progress.setValue(0)
        self.batch_progress.setVisible(False)
        lay.addWidget(self.batch_progress)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search tracks…")
        self.search_box.setFixedHeight(32)
        self.search_box.setMaximumWidth(280)
        lay.addWidget(self.search_box)

        lay.addStretch()

        self.btn_load_track.clicked.connect(self._load_single_track)
        self.btn_load_folder.clicked.connect(self._load_folder)
        self.btn_analyze_all.clicked.connect(self._analyze_all)
        self.search_box.textChanged.connect(self._filter_tracks)

        return lay

    def _build_library_panel(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        hdr = QLabel("TRACK LIBRARY")
        hdr.setObjectName("section_header")
        lay.addWidget(hdr)

        self.track_table = QTableWidget()
        self.track_table.setColumnCount(4)
        self.track_table.setHorizontalHeaderLabels(["Track", "BPM", "Key", "★"])
        self.track_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.track_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.track_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.track_table.setAlternatingRowColors(True)
        self.track_table.verticalHeader().setVisible(False)
        self.track_table.setShowGrid(False)
        self.track_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.track_table.setWordWrap(False)

        hh = self.track_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.track_table.setColumnWidth(1, 58)
        self.track_table.setColumnWidth(2, 64)
        self.track_table.setColumnWidth(3, 28)
        self.track_table.verticalHeader().setDefaultSectionSize(22)

        self.track_table.itemSelectionChanged.connect(self._on_track_selected)
        self.track_table.customContextMenuRequested.connect(self._library_context_menu)

        lay.addWidget(self.track_table)

        self.track_count_label = QLabel("0 tracks")
        self.track_count_label.setObjectName("meta_text")
        lay.addWidget(self.track_count_label)
        return w

    def _build_detail_panel(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 0, 0, 0)
        lay.setSpacing(8)

        # ── Track header ──────────────────────────────────────────────────
        self.lbl_title  = QLabel("No track selected")
        self.lbl_title.setObjectName("track_title")
        self.lbl_artist = QLabel("")
        self.lbl_artist.setObjectName("track_artist")
        lay.addWidget(self.lbl_title)
        lay.addWidget(self.lbl_artist)

        # ── Analysis cards ────────────────────────────────────────────────
        cards_row = QHBoxLayout()
        cards_row.setSpacing(8)

        self.card_bpm     = self._make_card("BPM",     "--",   "info_value_large")
        self.card_key     = self._make_card("Key",     "--",   "info_value_medium")
        self.card_camelot = self._make_card("Camelot", "--",   "camelot_value")
        self.card_energy  = self._make_card("Energy",  "--",   "info_value_medium")

        for card, _ in [self.card_bpm, self.card_key, self.card_camelot, self.card_energy]:
            cards_row.addWidget(card)
        lay.addLayout(cards_row)

        # ── Waveform ──────────────────────────────────────────────────────
        wf_label = QLabel("WAVEFORM")
        wf_label.setObjectName("section_header")
        lay.addWidget(wf_label)

        self.waveform = WaveformDJ()
        self.waveform.position_clicked.connect(self._on_waveform_clicked)
        lay.addWidget(self.waveform)

        # ── Player controls ───────────────────────────────────────────────
        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(8)

        self.btn_play = QPushButton("▶  Play")
        self.btn_play.setObjectName("btn_play")
        self.btn_play.setFixedHeight(36)
        self.btn_play.setFixedWidth(90)
        self.btn_play.setEnabled(False)

        self.btn_stop = QPushButton("⏹")
        self.btn_stop.setFixedSize(36, 36)
        self.btn_stop.setEnabled(False)

        self.btn_skip_back = QPushButton("◀◀")
        self.btn_skip_back.setFixedSize(40, 36)
        self.btn_skip_back.setEnabled(False)
        self.btn_skip_fwd = QPushButton("▶▶")
        self.btn_skip_fwd.setFixedSize(40, 36)
        self.btn_skip_fwd.setEnabled(False)

        for b in (self.btn_play, self.btn_stop, self.btn_skip_back, self.btn_skip_fwd):
            ctrl_row.addWidget(b)

        self.seek_slider = QSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setRange(0, 1000)
        self.seek_slider.setValue(0)
        self.seek_slider.setEnabled(False)
        self._seek_dragging = False
        ctrl_row.addWidget(self.seek_slider, 1)

        self.lbl_time = QLabel("0:00 / 0:00")
        self.lbl_time.setObjectName("time_display")
        ctrl_row.addWidget(self.lbl_time)

        lay.addLayout(ctrl_row)

        # ── Volume row ────────────────────────────────────────────────────
        vol_row = QHBoxLayout()
        vol_row.setSpacing(8)

        vol_lbl = QLabel("VOL")
        vol_lbl.setObjectName("meta_text")
        vol_lbl.setFixedWidth(30)
        vol_row.addWidget(vol_lbl)

        self.vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(70)
        self.vol_slider.setFixedWidth(130)
        vol_row.addWidget(self.vol_slider)

        self.lbl_vol = QLabel("70%")
        self.lbl_vol.setObjectName("meta_text")
        self.lbl_vol.setFixedWidth(35)
        vol_row.addWidget(self.lbl_vol)

        vol_row.addStretch()
        lay.addLayout(vol_row)

        # ── Audio meta row ────────────────────────────────────────────────
        self.lbl_audio_meta = QLabel("")
        self.lbl_audio_meta.setObjectName("meta_text")
        lay.addWidget(self.lbl_audio_meta)

        lay.addStretch()

        # ── Connections ───────────────────────────────────────────────────
        self.btn_play.clicked.connect(self._toggle_playback)
        self.btn_stop.clicked.connect(self._stop_playback)
        self.btn_skip_back.clicked.connect(lambda: self._skip(-10))
        self.btn_skip_fwd.clicked.connect(lambda:  self._skip(+10))
        self.vol_slider.valueChanged.connect(self._on_volume_changed)
        self.seek_slider.sliderPressed.connect(lambda: setattr(self, '_seek_dragging', True))
        self.seek_slider.sliderReleased.connect(self._on_seek_released)

        return w

    # ── Card helper ───────────────────────────────────────────────────────

    def _make_card(self, label_text: str, value_text: str, value_style: str):
        """Returns (card_widget, value_label)."""
        card = QWidget()
        card.setObjectName("info_card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(12, 8, 12, 10)
        lay.setSpacing(2)

        lbl = QLabel(label_text)
        lbl.setObjectName("info_label")
        lay.addWidget(lbl)

        val = QLabel(value_text)
        val.setObjectName(value_style)
        lay.addWidget(val)

        return card, val

    # ── Load / Scan ───────────────────────────────────────────────────────

    def _load_single_track(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Audio File", "",
            "Audio Files (*.mp3 *.wav *.flac *.m4a *.ogg *.aiff);;All Files (*)"
        )
        if path:
            # Add to table if not present
            if path not in self._row_map:
                row = self.track_table.rowCount()
                self.track_table.insertRow(row)
                self._set_row(row, path)
                self._row_map[path] = row
                self.library_files.append(path)
                self.track_count_label.setText(f"{len(self.library_files)} tracks")
            self._start_analysis(path)

    def _load_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Music Folder")
        if not folder:
            return
        files = [
            str(p) for p in sorted(Path(folder).rglob('*'))
            if p.is_file() and p.suffix.lower() in AUDIO_EXTS
        ]
        if not files:
            self._status.showMessage("No audio files found in folder.")
            return

        self.library_files = files
        self._row_map = {}
        self.track_table.setRowCount(0)
        self.track_table.setRowCount(len(files))

        for i, fp in enumerate(files):
            self._set_row(i, fp)
            self._row_map[fp] = i
            # Pre-fill from cache if available
            if is_cached(Path(fp)):
                from analyzer.batch_analyzer import load_cached
                cached = load_cached(Path(fp))
                if cached:
                    self._update_row_from_results(fp, cached)

        self.track_count_label.setText(f"{len(files)} tracks")
        self.btn_analyze_all.setEnabled(True)
        self._status.showMessage(f"Loaded {len(files)} tracks")

    def _set_row(self, row: int, file_path: str):
        name = Path(file_path).stem
        item = QTableWidgetItem(name)
        item.setData(Qt.ItemDataRole.UserRole, file_path)
        item.setToolTip(file_path)
        self.track_table.setItem(row, 0, item)
        self.track_table.setItem(row, 1, QTableWidgetItem("--"))
        self.track_table.setItem(row, 2, QTableWidgetItem("--"))
        self.track_table.setItem(row, 3, QTableWidgetItem("·"))

    # ── Single track analysis ─────────────────────────────────────────────

    def _on_track_selected(self):
        rows = self.track_table.selectedItems()
        if not rows:
            return
        row = rows[0].row()
        fp_item = self.track_table.item(row, 0)
        if fp_item:
            fp = fp_item.data(Qt.ItemDataRole.UserRole)
            if fp:
                self._start_analysis(fp)

    def _start_analysis(self, file_path: str):
        self._status.showMessage(f"Analyzing: {Path(file_path).name}…")
        if row := self._row_map.get(file_path):
            self._highlight_row(row, ROW_ANALYZING)

        self.analysis_thread = AnalysisThread(file_path)
        self.analysis_thread.finished.connect(self._on_analysis_done)
        self.analysis_thread.error.connect(self._on_analysis_error)
        self.analysis_thread.start()

    def _on_analysis_done(self, results: dict):
        self.current_track = results
        fp = results['file_path']

        # Update row
        self._update_row_from_results(fp, results)

        # Update detail panel
        self._display_track(results)

        self._status.showMessage(f"Ready: {results['filename']}")

    def _on_analysis_error(self, msg: str):
        self._status.showMessage(f"Error: {msg}")

    def _update_row_from_results(self, file_path: str, results: dict):
        row = self._row_map.get(file_path)
        if row is None:
            return
        bpm = results.get('bpm')
        key = results.get('key', {})
        self.track_table.setItem(row, 1, QTableWidgetItem(str(bpm) if bpm else "--"))
        self.track_table.setItem(row, 2, QTableWidgetItem(key.get('camelot', '--')))
        self.track_table.setItem(row, 3, QTableWidgetItem("✓"))
        self._highlight_row(row, ROW_DONE)

    def _highlight_row(self, row: int, color: QColor):
        for col in range(self.track_table.columnCount()):
            item = self.track_table.item(row, col)
            if item:
                item.setBackground(color)

    # ── Batch analysis ────────────────────────────────────────────────────

    def _analyze_all(self):
        if not self.library_files:
            return
        if self.batch_thread and self.batch_thread.isRunning():
            self.batch_thread.cancel()
            self.btn_analyze_all.setText("Analyze All")
            self.batch_progress.setVisible(False)
            return

        self.btn_analyze_all.setText("Cancel")
        self.batch_progress.setMaximum(len(self.library_files))
        self.batch_progress.setValue(0)
        self.batch_progress.setVisible(True)

        self.batch_thread = BatchThread(self.library_files)
        self.batch_thread.track_done.connect(self._on_batch_track_done)
        self.batch_thread.all_done.connect(self._on_batch_all_done)
        self.batch_thread.progress.connect(self._on_batch_progress)
        self.batch_thread.start()

    def _on_batch_track_done(self, file_path: str, results: dict, current: int, total: int):
        self._update_row_from_results(file_path, results)

    def _on_batch_progress(self, current: int, total: int):
        self.batch_progress.setValue(current)
        self._status.showMessage(f"Analyzing {current}/{total}…")

    def _on_batch_all_done(self, analyzed: int, cached: int):
        self.btn_analyze_all.setText("Analyze All")
        self.batch_progress.setVisible(False)
        self._status.showMessage(
            f"Done — {analyzed} analyzed, {cached} from cache, {analyzed+cached} total"
        )

    # ── Display track info ────────────────────────────────────────────────

    def _display_track(self, results: dict):
        meta = results.get('metadata', {})
        title  = meta.get('title')  or results['filename']
        artist = meta.get('artist') or "Unknown Artist"
        self.lbl_title.setText(title)
        self.lbl_artist.setText(artist)

        bpm     = results.get('bpm')
        key     = results.get('key', {})
        energy  = results.get('energy', {})
        ai      = results.get('audio_info', {})
        dur_sec = int(results.get('duration', 0))

        # Cards
        _, bpm_val = self.card_bpm
        _, key_val = self.card_key
        _, cam_val = self.card_camelot
        _, ene_val = self.card_energy

        bpm_val.setText(str(bpm) if bpm else "--")
        key_val.setText(key.get('notation', '--'))
        cam_val.setText(key.get('camelot', '--'))
        ene_val.setText(f"{energy.get('level', '--')}/10")

        # Audio meta
        fmt  = ai.get('format', '--')
        br   = ai.get('bitrate', 0)
        sr   = ai.get('sample_rate', 0)
        sz   = ai.get('file_size_mb', 0)
        mm   = dur_sec // 60
        ss   = dur_sec % 60
        self.lbl_audio_meta.setText(
            f"{fmt}  ·  {br} kbps  ·  {sr//1000:.0f}.{(sr%1000)//100}kHz  ·  {sz:.1f} MB  ·  {mm}:{ss:02d}"
        )

        # Seek slider range
        self.seek_slider.setMaximum(max(1, dur_sec * 10))
        self.lbl_time.setText(f"0:00 / {mm}:{ss:02d}")

        # Load audio + waveform
        if self.audio_player.load(results['file_path']):
            self.audio_player.set_duration(results.get('duration', dur_sec))
            self.waveform.set_waveform_from_file(results['file_path'])
            self._enable_controls(True)
        else:
            self._status.showMessage("Error loading audio")

    def _enable_controls(self, enabled: bool):
        for w in (self.btn_play, self.btn_stop, self.btn_skip_back,
                  self.btn_skip_fwd, self.seek_slider):
            w.setEnabled(enabled)

    # ── Playback controls ─────────────────────────────────────────────────

    def _toggle_playback(self):
        state = self.audio_player.state
        if state == PlayerState.PLAYING:
            self.audio_player.pause()
            self.btn_play.setText("▶  Play")
        elif state == PlayerState.PAUSED:
            self.audio_player.resume()
            self.btn_play.setText("⏸  Pause")
        else:  # STOPPED
            self.audio_player.play()
            self.btn_play.setText("⏸  Pause")

    def _stop_playback(self):
        self.audio_player.stop()
        self.btn_play.setText("▶  Play")
        self.waveform.set_playback_position(0.0)
        self.seek_slider.setValue(0)

    def _skip(self, seconds: int):
        if not self.current_track or self.audio_player.duration <= 0:
            return
        cur = self.audio_player.get_position() * self.audio_player.duration
        new_pos = max(0.0, min(cur + seconds, self.audio_player.duration))
        self.audio_player.seek(new_pos / self.audio_player.duration)

    def _on_position_changed(self, pos: float):
        self.waveform.set_playback_position(pos)
        if not self._seek_dragging:
            self.seek_slider.setValue(int(pos * self.seek_slider.maximum()))
        # Update time label
        if self.current_track:
            total_sec = int(self.current_track.get('duration', 0))
            cur_sec   = int(pos * total_sec)
            self.lbl_time.setText(
                f"{cur_sec//60}:{cur_sec%60:02d} / {total_sec//60}:{total_sec%60:02d}"
            )

    def _on_playback_finished(self):
        self.btn_play.setText("▶  Play")
        self.waveform.set_playback_position(0.0)
        self.seek_slider.setValue(0)

    def _on_waveform_clicked(self, pos: float):
        self.audio_player.seek(pos)
        self.waveform.set_playback_position(pos)

    def _on_seek_released(self):
        self._seek_dragging = False
        if self.audio_player.duration > 0:
            pos = self.seek_slider.value() / self.seek_slider.maximum()
            self.audio_player.seek(pos)

    def _on_volume_changed(self, val: int):
        self.audio_player.set_volume(val / 100.0)
        self.lbl_vol.setText(f"{val}%")

    # ── Filter ────────────────────────────────────────────────────────────

    def _filter_tracks(self, text: str):
        for row in range(self.track_table.rowCount()):
            item = self.track_table.item(row, 0)
            match = (text.lower() in item.text().lower()) if item else True
            self.track_table.setRowHidden(row, not match)

    # ── Context menu ──────────────────────────────────────────────────────

    def _library_context_menu(self, pos: QPoint):
        item = self.track_table.itemAt(pos)
        if not item:
            return
        row = item.row()
        fp_item = self.track_table.item(row, 0)
        if not fp_item:
            return
        fp = fp_item.data(Qt.ItemDataRole.UserRole)

        menu = QMenu(self)
        action_analyze = menu.addAction("Re-analyze")
        action_reveal  = menu.addAction("Open in Explorer")

        action = menu.exec(self.track_table.viewport().mapToGlobal(pos))
        if action == action_analyze and fp:
            self._start_analysis(fp)
        elif action == action_reveal and fp:
            os.startfile(str(Path(fp).parent))
```

**Step 2: Update `main.py` to apply stylesheet**

```python
# main.py  — verify it still starts cleanly
```

Check current main.py:

```bash
cat "C:\Users\ashay\Documents\Claude\dj-track-analyzer\main.py"
```

Ensure it does:
```python
app.setStyle("Fusion")
window = MainWindow()
```
No changes needed if MainWindow applies stylesheet internally.

**Step 3: Launch and smoke test**

```bash
conda activate dj-analyzer
cd "C:\Users\ashay\Documents\Claude\dj-track-analyzer"
python main.py
```

Manual test checklist:
- [ ] App launches without errors
- [ ] Dark cyberpunk theme renders correctly
- [ ] Click "Load Track" → select the sample MP3 → analysis < 3s
- [ ] BPM 103.4 / Key A Major / 11B displayed with correct styling
- [ ] Waveform shows frequency-colored bars (not a blob)
- [ ] Click "Play" → audio starts immediately on first click
- [ ] Seek slider and waveform click both seek correctly
- [ ] Skip ±10s buttons work
- [ ] Click "Load Folder" → folder scans, shows tracks
- [ ] Click "Analyze All" → progress bar appears, tracks fill in
- [ ] Re-load same folder → cache hits are instant (< 0.5s per track)
- [ ] Right-click a track → context menu appears

**Step 4: Fix any visual issues found during smoke test**

Common things to tweak after first launch:
- Card widget sizes (adjust padding/font if values get clipped)
- Waveform height (adjust if overview/main look too cramped)
- Column widths in library table

**Step 5: Commit**

```bash
git add ui/main_window.py ui/styles.py
git commit -m "feat: complete UI revamp — cyberpunk theme, freq waveform, batch analysis, seek bar"
```

---

## Task 7: Final Verification Pass

**Step 1: Run all tests**

```bash
conda activate dj-analyzer
cd "C:\Users\ashay\Documents\Claude\dj-track-analyzer"
python -m pytest tests/ -v
```
Expected: All tests pass.

**Step 2: Full end-to-end manual test**

1. Load sample track → verify speed < 3s
2. Verify waveform has visible frequency coloring (blue-ish bars, brighter on drops)
3. Play → pause → resume → stop → play again (each should work correctly)
4. Seek via waveform click + seek slider — both update time display
5. Skip ±10s
6. Load folder with 5+ tracks → Analyze All → verify all complete with ✓ status
7. Reload same folder → all tracks show ✓ instantly from cache

**Step 3: Final commit**

```bash
git add .
git commit -m "chore: final verification pass — revamp complete"
```

---

## Checklist

- [ ] Task 1: `ui/styles.py` — QSS stylesheet ✓
- [ ] Task 2: `analyzer/audio_analyzer.py` — speed (60s limit, mutagen duration) ✓
- [ ] Task 3: `analyzer/batch_analyzer.py` — batch + cache ✓
- [ ] Task 4: `ui/audio_player.py` — state machine bug fix ✓
- [ ] Task 5: `ui/waveform_dj.py` — frequency-colored waveform ✓
- [ ] Task 6: `ui/main_window.py` — full UI revamp ✓
- [ ] Task 7: Final verification ✓
