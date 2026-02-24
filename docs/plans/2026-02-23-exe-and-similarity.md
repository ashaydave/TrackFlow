# EXE Packaging + Similarity Feature Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Package TrackFlow as a standalone Windows `.exe` and add an MFCC+Chroma similarity search panel that shows the top-10 most similar tracks from the analyzed library.

**Architecture:** A new `paths.py` module centralises all data/asset paths and detects when running as a PyInstaller bundle (`sys.frozen`), redirecting user-writable data to `%APPDATA%\TrackFlow\`. Similarity uses 32-dimensional feature vectors (20 MFCC + 12 chroma) stored in the existing JSON cache and computed via scipy (already a dependency). A "Similar" tab sits alongside the Playlists tab in the bottom panel.

**Tech Stack:** PyInstaller 6.x, scipy.fft.dct (mel filterbank already in codebase), PyQt6 QTabWidget, numpy cosine similarity

**Test command:** `conda run -n dj-analyzer python -m pytest tests/ -v`

---

## Task 1: Centralise paths in `paths.py`

**Why first:** Both exe packaging and similarity feature read/write to `data/`. A single `paths.py` fixes it once for everything.

**Files:**
- Create: `paths.py` (repo root)
- Modify: `analyzer/batch_analyzer.py` (lines 18, 31-32, 44-45, 52-53)
- Modify: `ui/main_window.py` (line 40)
- Modify: `main.py` (icon path block)

**Step 1: Write the failing test**

Add to `tests/test_analyzer_speed.py`:
```python
def test_paths_frozen_detection():
    """paths module must export get_cache_dir() and get_data_dir() callables."""
    import paths
    cache_dir = paths.get_cache_dir()
    data_dir = paths.get_data_dir()
    assets_dir = paths.get_assets_dir()
    assert hasattr(cache_dir, '__truediv__'), "get_cache_dir() must return a Path"
    assert hasattr(data_dir, '__truediv__'), "get_data_dir() must return a Path"
    assert hasattr(assets_dir, '__truediv__'), "get_assets_dir() must return a Path"
    # In dev mode (not frozen) data dir should be under repo root
    assert 'TrackFlow' in str(data_dir) or 'dj-track-analyzer' in str(data_dir)
```

**Step 2: Run test to verify it fails**
```
conda run -n dj-analyzer python -m pytest tests/test_analyzer_speed.py::test_paths_frozen_detection -v
```
Expected: `FAILED` — `ModuleNotFoundError: No module named 'paths'`

**Step 3: Create `paths.py`**
```python
"""
paths.py — Centralised path resolution for TrackFlow.

In dev mode  : data/ and assets/ are relative to this file.
In frozen exe: data/ redirects to %APPDATA%\\TrackFlow\\
               assets/ resolves via sys._MEIPASS (bundle root).
"""
import os
import sys
from pathlib import Path


def _is_frozen() -> bool:
    return getattr(sys, 'frozen', False)


def get_data_dir() -> Path:
    if _is_frozen():
        base = Path(os.environ.get("APPDATA", Path.home())) / "TrackFlow"
    else:
        base = Path(__file__).parent / "data"
    base.mkdir(parents=True, exist_ok=True)
    return base


def get_cache_dir() -> Path:
    d = get_data_dir() / "cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_assets_dir() -> Path:
    if _is_frozen():
        return Path(sys._MEIPASS) / "assets"      # type: ignore[attr-defined]
    return Path(__file__).parent / "assets"
```

**Step 4: Update `analyzer/batch_analyzer.py`**

Replace the module-level constant and all three usages:
```python
# OLD (line 18)
CACHE_DIR = Path(__file__).parent.parent / 'data' / 'cache'

# NEW — add import at top of file, remove the constant
import sys, os
sys.path.insert(0, str(Path(__file__).parent.parent))
from paths import get_cache_dir
```

Replace every `CACHE_DIR` reference:
```python
# load_cached (was lines 31-32):
cache_dir = get_cache_dir()
cache_file = cache_dir / f"{_cache_key(file_path)}.json"

# save_cached (was lines 44-45):
cache_dir = get_cache_dir()
cache_file = cache_dir / f"{_cache_key(file_path)}.json"

# is_cached (was lines 52-53):
cache_dir = get_cache_dir()
return (cache_dir / f"{_cache_key(file_path)}.json").exists()
```

**Step 5: Update `ui/main_window.py` line 40**
```python
# OLD
HOT_CUES_FILE  = Path(__file__).parent.parent / 'data' / 'hot_cues.json'

# NEW — add at top of file imports
import sys as _sys, os as _os
sys.path.insert(0, str(Path(__file__).parent.parent))
from paths import get_data_dir as _get_data_dir
HOT_CUES_FILE = _get_data_dir() / 'hot_cues.json'
```

**Step 6: Update `main.py` icon block**
```python
# OLD
icon_path = Path(__file__).parent / "assets" / "logo_256.png"

# NEW
from paths import get_assets_dir
icon_path = get_assets_dir() / "logo_256.png"
```

**Step 7: Run all tests**
```
conda run -n dj-analyzer python -m pytest tests/ -v
```
Expected: **17 tests pass + 1 new test passes = 18 passed**

**Step 8: Commit**
```bash
git add paths.py analyzer/batch_analyzer.py ui/main_window.py main.py tests/test_analyzer_speed.py
git commit -m "refactor: centralise paths in paths.py with frozen-exe detection"
```

---

## Task 2: Create PyInstaller spec + build script

**Files:**
- Create: `TrackFlow.spec`
- Create: `build.bat`

**Step 1: Install PyInstaller**
```
conda run -n dj-analyzer pip install pyinstaller
```
Expected: `Successfully installed pyinstaller-...`

**Step 2: Write `TrackFlow.spec`**
```python
# TrackFlow.spec
# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[str(Path('.').resolve())],
    binaries=[],
    datas=[
        ('assets', 'assets'),          # logo + icons
    ],
    hiddenimports=[
        'pygame',
        'soundfile',
        'soxr',
        'mutagen',
        'mutagen.mp3',
        'mutagen.flac',
        'mutagen.mp4',
        'scipy.fft',
        'scipy.fftpack',
        'numpy',
        'paths',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'IPython', 'jupyter'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Collect all PyQt6 components (platform plugins, translations, DLLs)
from PyInstaller.utils.hooks import collect_all
qt_datas, qt_binaries, qt_hiddenimports = collect_all('PyQt6')
a.datas    += qt_datas
a.binaries += qt_binaries
a.hiddenimports += qt_hiddenimports

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='TrackFlow',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,                     # no terminal window
    icon='assets\\logo_256.png',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='TrackFlow',
)
```

**Step 3: Write `build.bat`**
```bat
@echo off
echo Building TrackFlow...
conda activate dj-analyzer
pyinstaller TrackFlow.spec --noconfirm --clean
echo.
echo ============================================
echo Build complete: dist\TrackFlow\TrackFlow.exe
echo ============================================
```

**Step 4: Run the build**
```
conda run -n dj-analyzer pyinstaller TrackFlow.spec --noconfirm --clean
```
Expected: `dist\TrackFlow\TrackFlow.exe` created, no errors.
If `collect_all` fails on older PyInstaller, replace the Qt block with:
```python
a.datas += [('assets', 'assets')]
a.hiddenimports += ['PyQt6.QtSvg', 'PyQt6.QtCore', 'PyQt6.QtGui', 'PyQt6.QtWidgets']
```

**Step 5: Smoke-test the exe manually**
Double-click `dist\TrackFlow\TrackFlow.exe`. App should open with title "TrackFlow" and icon.

**Step 6: Commit**
```bash
git add TrackFlow.spec build.bat
git commit -m "feat: PyInstaller spec + build.bat for standalone Windows exe"
```

---

## Task 3: Add MFCC computation to `audio_analyzer.py`

**Files:**
- Modify: `analyzer/audio_analyzer.py`
- Modify: `tests/test_analyzer_speed.py`

**Step 1: Write the failing tests**

Add to `tests/test_analyzer_speed.py`:
```python
@pytest.mark.skipif(not Path(SAMPLE_TRACK).exists(), reason="Sample track not found")
def test_features_in_analysis_result():
    """analyze_track must return a 'features' key with mfcc (20) and chroma (12)."""
    analyzer = AudioAnalyzer()
    result = analyzer.analyze_track(SAMPLE_TRACK)
    assert 'features' in result, "Missing 'features' key"
    feats = result['features']
    assert 'mfcc' in feats,   "Missing mfcc in features"
    assert 'chroma' in feats, "Missing chroma in features"
    assert len(feats['mfcc'])   == 20, f"Expected 20 MFCCs, got {len(feats['mfcc'])}"
    assert len(feats['chroma']) == 12, f"Expected 12 chroma, got {len(feats['chroma'])}"
    # Values must be finite floats
    assert all(isinstance(v, float) for v in feats['mfcc'])
    assert all(isinstance(v, float) for v in feats['chroma'])

def test_mfcc_shape_no_audio():
    """_compute_mfcc must return exactly n_mfcc floats for synthetic input."""
    import numpy as np
    from analyzer.audio_analyzer import AudioAnalyzer
    analyzer = AudioAnalyzer()
    # Synthetic power spectrogram: (N_FFT//2+1, 100 frames)
    n_bins = analyzer.N_FFT // 2 + 1
    S_power = np.abs(np.random.randn(n_bins, 100)) ** 2
    mfcc = analyzer._compute_mfcc(S_power, analyzer.sample_rate, n_mfcc=20)
    assert len(mfcc) == 20
    assert all(isinstance(v, float) for v in mfcc)
```

**Step 2: Run tests to verify they fail**
```
conda run -n dj-analyzer python -m pytest tests/test_analyzer_speed.py::test_features_in_analysis_result tests/test_analyzer_speed.py::test_mfcc_shape_no_audio -v
```
Expected: `FAILED` — `KeyError: 'features'` and `AttributeError: '_compute_mfcc'`

**Step 3: Add `_compute_mfcc` to `AudioAnalyzer`**

In `audio_analyzer.py`, after the `_mel_filterbank` method, add:
```python
def _compute_mfcc(self, S_power, sr, n_mfcc: int = 20) -> list[float]:
    """Compute MFCC means from power spectrogram using scipy DCT.

    Uses the existing mel filterbank (same one used for BPM onset flux).
    Returns n_mfcc floats — the time-averaged MFCC coefficients.
    """
    from scipy.fft import dct as _dct
    n_mels = 64
    fb = self._mel_filterbank(sr, self.N_FFT, n_mels)   # (n_mels, n_bins)
    mel = fb @ S_power                                    # (n_mels, n_frames)
    log_mel = np.log(mel + 1e-9)                          # log compression
    # DCT-II across mel bands → MFCC; keep coefficients 0..n_mfcc-1
    mfcc_matrix = _dct(log_mel, axis=0, norm='ortho')[:n_mfcc, :]
    return mfcc_matrix.mean(axis=1).tolist()
```

**Step 4: Update `_detect_key` to also return chroma**

In `_detect_key`, capture and store `chroma_avg` for reuse.
Change the method signature/body so it returns chroma alongside key info,
OR (simpler) compute chroma separately from `analyze_track`.

Simplest approach — modify `analyze_track` to call `_compute_chroma` once and share the result:

```python
# In analyze_track(), replace:
results = {
    ...
    'key': self._detect_key(S_power, n_frames, sr),
    ...
}

# With:
chroma_avg = self._compute_chroma(S_power[:, :min(int(30 * sr / self.HOP_LENGTH), n_frames)], sr)
results = {
    ...
    'key': self._detect_key_from_chroma(chroma_avg),
    'features': {
        'mfcc':   self._compute_mfcc(S_power, sr),
        'chroma': chroma_avg.tolist(),
    },
    ...
}
```

Add `_detect_key_from_chroma(self, chroma_avg)` — extract the key-detection logic out of `_detect_key`:
```python
def _detect_key_from_chroma(self, chroma_avg) -> dict:
    """Detect key from a pre-computed chroma vector."""
    try:
        key_index = int(np.argmax(chroma_avg))
        is_major = self._is_major_key(chroma_avg)
        return {
            'notation': self._index_to_key(key_index, is_major),
            'camelot':  self._to_camelot(key_index, is_major),
            'open_key': self._to_open_key(key_index, is_major),
            'confidence': 'medium',
        }
    except Exception as e:
        print(f"Key detection failed: {e}")
        return {'notation': 'Unknown', 'camelot': 'N/A',
                'open_key': 'N/A', 'confidence': 'none'}
```

Keep `_detect_key` as a thin wrapper calling `_detect_key_from_chroma` for backwards compatibility.

**Step 5: Run tests**
```
conda run -n dj-analyzer python -m pytest tests/ -v
```
Expected: all previously passing tests still pass + 2 new tests pass.

**Step 6: Commit**
```bash
git add analyzer/audio_analyzer.py tests/test_analyzer_speed.py
git commit -m "feat: add MFCC + chroma feature vectors to analysis results"
```

---

## Task 4: Create `analyzer/similarity.py`

**Files:**
- Create: `analyzer/similarity.py`
- Create: `tests/test_similarity.py`

**Step 1: Write the failing tests**

Create `tests/test_similarity.py`:
```python
"""Tests for MFCC+chroma cosine similarity engine."""
import pytest
import numpy as np
from pathlib import Path
from unittest.mock import patch
from analyzer.similarity import find_similar, _cosine_similarity, _load_feature_vector


def _make_cache(tmp_path, fp, mfcc, chroma, bpm=120.0, camelot='8B'):
    """Helper: write a fake cache JSON for a fake file path."""
    import json, hashlib
    key = hashlib.md5(f"{fp}|1000.0|1000".encode()).hexdigest()
    data = {
        'file_path': fp,
        'filename': Path(fp).name,
        'bpm': bpm,
        'key': {'camelot': camelot, 'notation': 'C Major'},
        'features': {'mfcc': mfcc, 'chroma': chroma},
    }
    cache_file = tmp_path / f"{key}.json"
    cache_file.write_text(json.dumps(data))
    return fp


def test_cosine_similarity_identical():
    """Identical vectors → similarity 1.0."""
    v = [1.0] * 32
    assert abs(_cosine_similarity(v, v) - 1.0) < 1e-6


def test_cosine_similarity_orthogonal():
    """Orthogonal vectors → similarity 0.0."""
    a = [1.0, 0.0]
    b = [0.0, 1.0]
    assert abs(_cosine_similarity(a, b)) < 1e-6


def test_find_similar_excludes_query(tmp_path):
    """Query track must NOT appear in its own results."""
    mfcc = [float(i) for i in range(20)]
    chroma = [float(i) for i in range(12)]
    fp_query = str(tmp_path / "query.mp3")
    fp_other = str(tmp_path / "other.mp3")

    with patch('analyzer.similarity.get_cache_dir', return_value=tmp_path), \
         patch('pathlib.Path.stat') as mock_stat:
        mock_stat.return_value.st_mtime = 1000.0
        mock_stat.return_value.st_size  = 1000
        _make_cache(tmp_path, fp_query, mfcc, chroma)
        _make_cache(tmp_path, fp_other, mfcc, chroma)
        results = find_similar(fp_query, [fp_query, fp_other], tmp_path, top_n=5)

    fps = [r['file_path'] for r in results]
    assert fp_query not in fps, "Query track must not appear in results"
    assert fp_other in fps


def test_find_similar_skips_no_features(tmp_path):
    """Tracks without 'features' in cache are silently skipped."""
    import json, hashlib
    fp_query = str(tmp_path / "query.mp3")
    fp_nofeat = str(tmp_path / "nofeat.mp3")
    mfcc   = [1.0] * 20
    chroma = [1.0] * 12

    with patch('analyzer.similarity.get_cache_dir', return_value=tmp_path), \
         patch('pathlib.Path.stat') as mock_stat:
        mock_stat.return_value.st_mtime = 1000.0
        mock_stat.return_value.st_size  = 1000
        _make_cache(tmp_path, fp_query, mfcc, chroma)
        # Write cache entry WITHOUT features for fp_nofeat
        key = hashlib.md5(f"{fp_nofeat}|1000.0|1000".encode()).hexdigest()
        no_feat_data = {'file_path': fp_nofeat, 'filename': 'nofeat.mp3',
                        'bpm': 120.0, 'key': {'camelot': '8B'}}
        (tmp_path / f"{key}.json").write_text(json.dumps(no_feat_data))
        results = find_similar(fp_query, [fp_query, fp_nofeat], tmp_path, top_n=5)

    assert all(r['file_path'] != fp_nofeat for r in results)


def test_find_similar_returns_sorted(tmp_path):
    """Results must be sorted by similarity descending."""
    mfcc_q = [1.0] * 20 + [0.0] * 0   # length 20
    chroma_q = [1.0] * 12
    # close: same vector
    mfcc_close = [1.0] * 20
    chroma_close = [1.0] * 12
    # far: opposite direction
    mfcc_far = [-1.0] * 20
    chroma_far = [-1.0] * 12

    fp_q     = str(tmp_path / "query.mp3")
    fp_close = str(tmp_path / "close.mp3")
    fp_far   = str(tmp_path / "far.mp3")

    with patch('analyzer.similarity.get_cache_dir', return_value=tmp_path), \
         patch('pathlib.Path.stat') as mock_stat:
        mock_stat.return_value.st_mtime = 1000.0
        mock_stat.return_value.st_size  = 1000
        _make_cache(tmp_path, fp_q,     mfcc_q,     chroma_q)
        _make_cache(tmp_path, fp_close, mfcc_close, chroma_close)
        _make_cache(tmp_path, fp_far,   mfcc_far,   chroma_far)
        results = find_similar(fp_q, [fp_q, fp_close, fp_far], tmp_path, top_n=5)

    assert len(results) == 2
    assert results[0]['file_path'] == fp_close
    assert results[0]['similarity'] > results[1]['similarity']
```

**Step 2: Run tests to verify they fail**
```
conda run -n dj-analyzer python -m pytest tests/test_similarity.py -v
```
Expected: `FAILED` — `ModuleNotFoundError: No module named 'analyzer.similarity'`

**Step 3: Create `analyzer/similarity.py`**
```python
"""
analyzer/similarity.py — MFCC+chroma cosine similarity search.

find_similar(query_fp, candidate_fps, cache_dir, top_n) compares the
32-dim feature vector of the query track against all cached candidates
and returns top_n results sorted by cosine similarity descending.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from paths import get_cache_dir


def _cache_key(file_path: str) -> str:
    """Reproduce the same cache key used by batch_analyzer."""
    p = Path(file_path)
    stat = p.stat()
    key_str = f"{p.absolute()}|{stat.st_mtime}|{stat.st_size}"
    return hashlib.md5(key_str.encode()).hexdigest()


def _load_feature_vector(file_path: str, cache_dir: Path) -> np.ndarray | None:
    """Load 32-dim feature vector from cache, or None if unavailable."""
    try:
        cache_file = cache_dir / f"{_cache_key(file_path)}.json"
        if not cache_file.exists():
            return None
        data = json.loads(cache_file.read_text())
        feats = data.get('features')
        if not feats:
            return None
        mfcc   = feats.get('mfcc', [])
        chroma = feats.get('chroma', [])
        if len(mfcc) != 20 or len(chroma) != 12:
            return None
        return np.array(mfcc + chroma, dtype=np.float32)
    except Exception:
        return None


def _cosine_similarity(a: list | np.ndarray, b: list | np.ndarray) -> float:
    """Cosine similarity between two vectors. Returns float in [-1, 1]."""
    va = np.asarray(a, dtype=np.float32)
    vb = np.asarray(b, dtype=np.float32)
    norm_a = np.linalg.norm(va)
    norm_b = np.linalg.norm(vb)
    if norm_a < 1e-9 or norm_b < 1e-9:
        return 0.0
    return float(np.dot(va, vb) / (norm_a * norm_b))


def find_similar(
    query_fp: str,
    candidate_fps: list[str],
    cache_dir: Path | None = None,
    top_n: int = 10,
) -> list[dict]:
    """
    Return top_n most similar tracks from candidate_fps.

    Each result dict:
        file_path   str
        name        str  (filename stem)
        similarity  float  0.0-1.0
        bpm         float | None
        key         str   Camelot notation | '--'
    """
    if cache_dir is None:
        cache_dir = get_cache_dir()

    query_vec = _load_feature_vector(query_fp, cache_dir)
    if query_vec is None:
        return []

    results = []
    for fp in candidate_fps:
        if fp == query_fp:
            continue
        vec = _load_feature_vector(fp, cache_dir)
        if vec is None:
            continue
        sim = _cosine_similarity(query_vec, vec)
        # Load metadata for display
        try:
            cache_file = cache_dir / f"{_cache_key(fp)}.json"
            meta = json.loads(cache_file.read_text())
        except Exception:
            meta = {}
        results.append({
            'file_path':  fp,
            'name':       Path(fp).stem,
            'similarity': round((sim + 1) / 2, 4),   # map [-1,1] → [0,1]
            'bpm':        meta.get('bpm'),
            'key':        meta.get('key', {}).get('camelot', '--'),
        })

    results.sort(key=lambda r: r['similarity'], reverse=True)
    return results[:top_n]
```

**Step 4: Run tests**
```
conda run -n dj-analyzer python -m pytest tests/test_similarity.py tests/test_analyzer_speed.py -v
```
Expected: all tests pass.

**Step 5: Commit**
```bash
git add analyzer/similarity.py tests/test_similarity.py
git commit -m "feat: add MFCC+chroma cosine similarity engine"
```

---

## Task 5: Add "Similar" tab to the bottom panel UI

**Files:**
- Modify: `ui/main_window.py`

This task wires up the Similar tab alongside the existing Playlists tab. No new tests needed (UI-only).

**Step 1: Locate the playlist panel build method**

Search for `_build_playlist_panel` or similar in `main_window.py`. The playlist QWidget is assembled somewhere around line 640–700. The goal is to wrap the existing playlist widget and the new similar widget inside a `QTabWidget`.

**Step 2: Wrap playlist in a QTabWidget**

Find where `self.playlist_table` and its surrounding layout widget are added to the main layout. Wrap them:

```python
# After building playlist_widget (the QWidget that holds selector + table):
self.bottom_tabs = QTabWidget()
self.bottom_tabs.setObjectName("bottom_tabs")
self.bottom_tabs.addTab(playlist_widget, "Playlists")

# Build similar panel (empty for now)
self.similar_widget = self._build_similar_panel()
self.bottom_tabs.addTab(self.similar_widget, "Similar")

# Replace the direct addWidget(playlist_widget) with:
lay.addWidget(self.bottom_tabs)
```

**Step 3: Build the Similar panel**

Add this method to `MainWindow`:
```python
def _build_similar_panel(self) -> QWidget:
    """Build the 'Similar Tracks' tab content."""
    widget = QWidget()
    lay = QVBoxLayout(widget)
    lay.setContentsMargins(0, 4, 0, 0)
    lay.setSpacing(4)

    # Top bar: button + status label
    top = QHBoxLayout()
    self.btn_find_similar = QPushButton("Find Similar")
    self.btn_find_similar.setFixedHeight(28)
    self.btn_find_similar.setEnabled(False)
    self.btn_find_similar.setToolTip("Find tracks most similar to the currently loaded track")
    self.btn_find_similar.clicked.connect(self._run_find_similar)
    top.addWidget(self.btn_find_similar)

    self.lbl_similar_status = QLabel("Load and analyze a track to find similar ones")
    self.lbl_similar_status.setObjectName("meta_text")
    top.addWidget(self.lbl_similar_status, stretch=1)
    lay.addLayout(top)

    # Results table
    self.similar_table = QTableWidget()
    self.similar_table.setColumnCount(5)
    self.similar_table.setHorizontalHeaderLabels(["#", "Track", "Match", "BPM", "Key"])
    self.similar_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    self.similar_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    self.similar_table.verticalHeader().setVisible(False)
    self.similar_table.setShowGrid(False)
    self.similar_table.setAlternatingRowColors(True)
    self.similar_table.verticalHeader().setDefaultSectionSize(22)
    sh = self.similar_table.horizontalHeader()
    sh.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
    sh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
    sh.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
    sh.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
    sh.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
    self.similar_table.setColumnWidth(0, 28)
    self.similar_table.setColumnWidth(2, 55)
    self.similar_table.setColumnWidth(3, 55)
    self.similar_table.setColumnWidth(4, 45)
    self.similar_table.cellDoubleClicked.connect(self._on_similar_double_clicked)
    lay.addWidget(self.similar_table)
    return widget
```

**Step 4: Style the tab widget**

In `ui/styles.py`, add after existing rules:
```css
QTabWidget::pane { border: none; }
QTabBar::tab {
    background: #1a1a2e;
    color: #aaaaaa;
    padding: 4px 14px;
    border: 1px solid #223355;
    border-bottom: none;
    border-radius: 4px 4px 0 0;
}
QTabBar::tab:selected {
    background: #111830;
    color: #00ccff;
    border-color: #0088ff;
}
```

**Step 5: Smoke test**
```
conda run -n dj-analyzer python -c "from PyQt6.QtWidgets import QApplication; import sys; app = QApplication(sys.argv); from ui.main_window import MainWindow; print('OK')"
```
Expected: `OK`

**Step 6: Commit**
```bash
git add ui/main_window.py ui/styles.py
git commit -m "feat: add Similar tab alongside Playlists in bottom panel"
```

---

## Task 6: Wire "Find Similar" logic + double-click + library context menu

**Files:**
- Modify: `ui/main_window.py`

**Step 1: Enable button when a track is loaded**

In `_display_track()` (called after analysis completes), add:
```python
# Enable Find Similar if the loaded track has features
has_features = bool(self.current_track and
                    self.current_track.get('features'))
self.btn_find_similar.setEnabled(has_features)
self.lbl_similar_status.setText(
    "Click 'Find Similar' to search your library"
    if has_features else "Analyze track first to enable similarity search"
)
```

**Step 2: Implement `_run_find_similar`**

```python
def _run_find_similar(self) -> None:
    """Run cosine similarity search and populate the Similar tab."""
    from analyzer.similarity import find_similar
    from paths import get_cache_dir

    if not self.current_track:
        return

    query_fp = self.current_track['file_path']
    candidates = list(self.library_files)  # all loaded library paths

    self.lbl_similar_status.setText("Searching…")
    QApplication.processEvents()

    results = find_similar(query_fp, candidates,
                           cache_dir=get_cache_dir(), top_n=10)
    self._populate_similar_table(results)

    # Switch to the Similar tab
    self.bottom_tabs.setCurrentWidget(self.similar_widget)

def _populate_similar_table(self, results: list[dict]) -> None:
    """Fill the similar_table with ranked results."""
    self.similar_table.setRowCount(0)
    if not results:
        self.lbl_similar_status.setText(
            "No similar tracks found — analyze more tracks first"
        )
        return

    self.lbl_similar_status.setText(
        f"Top {len(results)} matches from {len(self.library_files)} analyzed tracks"
    )
    for rank, r in enumerate(results, start=1):
        row = self.similar_table.rowCount()
        self.similar_table.insertRow(row)

        rank_item = QTableWidgetItem(str(rank))
        rank_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.similar_table.setItem(row, 0, rank_item)

        name_item = QTableWidgetItem(r['name'])
        name_item.setData(Qt.ItemDataRole.UserRole, r['file_path'])
        name_item.setToolTip(r['file_path'])
        self.similar_table.setItem(row, 1, name_item)

        pct = int(r['similarity'] * 100)
        match_item = QTableWidgetItem(f"{pct}%")
        match_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if pct >= 85:
            match_item.setForeground(QColor("#00ccff"))
        elif pct >= 70:
            match_item.setForeground(QColor("#FFB900"))
        self.similar_table.setItem(row, 2, match_item)

        bpm = r.get('bpm')
        self.similar_table.setItem(row, 3, QTableWidgetItem(str(bpm) if bpm else "--"))
        self.similar_table.setItem(row, 4, QTableWidgetItem(r.get('key', '--')))
```

**Step 3: Implement double-click handler**

```python
def _on_similar_double_clicked(self, row: int, _col: int) -> None:
    """Load the double-clicked similar track into the deck."""
    item = self.similar_table.item(row, 1)
    if item:
        fp = item.data(Qt.ItemDataRole.UserRole)
        if fp:
            self._start_analysis(fp)
```

**Step 4: Add "Find Similar Tracks" to library right-click menu**

In `_library_context_menu()`, add an action after the existing ones:
```python
sim_action = menu.addAction("Find Similar Tracks")
action = menu.exec(self.track_table.viewport().mapToGlobal(pos))
if action == sim_action:
    fp_item = self.track_table.item(row, 0)
    if fp_item:
        fp = fp_item.data(Qt.ItemDataRole.UserRole)
        if fp:
            # Load track first if not already current, then find similar
            self._start_analysis(fp)
            # Switch to Similar tab — actual search fires after analysis
            # completes via _on_analysis_done → _display_track → auto-search
```

For the auto-search after library right-click, set a flag:
```python
self._find_similar_after_load = False   # init in __init__

# In _library_context_menu sim_action handler:
self._find_similar_after_load = True
self._start_analysis(fp)

# In _display_track(), after enabling the button:
if self._find_similar_after_load:
    self._find_similar_after_load = False
    self._run_find_similar()
```

**Step 5: Run all tests**
```
conda run -n dj-analyzer python -m pytest tests/ -v
```
Expected: all tests pass.

**Step 6: Commit**
```bash
git add ui/main_window.py
git commit -m "feat: wire Find Similar button, double-click load, and library context menu"
```

---

## Task 7: Push to GitHub

```bash
git push origin main
```

Expected: all commits pushed, GitHub repo updated.
