# TrackFlow — EXE Packaging + Similarity Feature Design
**Date:** 2026-02-23

---

## 1. EXE Packaging

### Goal
Produce a standalone Windows executable that runs without any Python installation or conda environment.

### Tool
PyInstaller with a hand-written `.spec` file for reproducibility.

### Distribution Format
**Single-folder** (`dist/TrackFlow/TrackFlow.exe`), not single-file.
Single-file unpacks to a temp directory on every launch causing slow startup.
Single-folder starts instantly and is easier to debug.

### Data Path Handling
Currently `DATA_DIR`, `CACHE_DIR`, and `HOT_CUES_FILE` are resolved relative to
`__file__`, which points into the PyInstaller temp dir when packaged.

Fix: detect packaged mode and redirect user-writable data to `%APPDATA%\TrackFlow\`:

```python
import sys, os
from pathlib import Path

def _app_data_dir() -> Path:
    if getattr(sys, 'frozen', False):          # running as PyInstaller exe
        base = Path(os.environ.get("APPDATA", Path.home())) / "TrackFlow"
    else:
        base = Path(__file__).parent.parent / "data"
    base.mkdir(parents=True, exist_ok=True)
    return base
```

Apply this to `main_window.py` wherever `DATA_DIR` / `CACHE_DIR` / `HOT_CUES_FILE` are defined.

### Assets Path Handling
Logo and other read-only assets live in `assets/` next to the source.
In packaged mode use `sys._MEIPASS` to find them:

```python
def _assets_dir() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS) / "assets"
    return Path(__file__).parent / "assets"
```

### PyInstaller `.spec` File
File: `TrackFlow.spec` at repo root. Key directives:
- `datas`: include `assets/` folder
- `hiddenimports`: `pygame`, `scipy`, `numpy`, `soundfile`, `soxr`, `mutagen`
- `collect_all`: `PyQt6` (platform plugins, translations, DLLs)
- `icon`: `assets/logo_256.png` (Windows `.ico` auto-converted by PyInstaller if PIL available, else raw PNG)
- `console=False` (no terminal window on launch)
- `name='TrackFlow'`

### Build Script
`build.bat` at repo root — one-command build:
```bat
@echo off
conda activate dj-analyzer
pyinstaller TrackFlow.spec --noconfirm
echo Build complete: dist\TrackFlow\TrackFlow.exe
```

### Estimated Output
~180–220 MB folder. Normal for PyQt6 + numpy/scipy + pygame.

---

## 2. Similarity Feature

### Goal
Given a loaded/selected track, find the most acoustically similar tracks from the
analyzed library and display them in a dedicated "Similar" tab.

### Approach
**MFCC + Chroma cosine similarity** using scipy (already a dependency).

No new package dependencies. ~50 ms extra computation per track during analysis.

### Feature Vector (per track, stored in cache)
| Component | Dims | Source |
|-----------|------|--------|
| MFCC means (coefficients 1–20) | 20 | `scipy.fft` on mel-filterbank, first 60 s |
| Chroma means | 12 | Already computed in `_compute_chroma()`, just not stored |
| **Total** | **32** | |

Stored in cache JSON under key `"features": {"mfcc": [...], "chroma": [...]}`.

### Analysis Changes (`analyzer/audio_analyzer.py`)
- `_detect_key()` already calls `_compute_chroma()` — save the result
- Add `_compute_mfcc(S_power, sr) -> list[float]` using scipy mel filterbank
- Include `"features"` dict in the returned results dict
- `batch_analyzer.py` already caches the full results dict — no changes needed

### Similarity Engine (`analyzer/similarity.py`) — new file
```python
def find_similar(query_fp: str, candidate_fps: list[str],
                 cache_dir: Path, top_n: int = 10) -> list[dict]:
    """
    Returns top_n most similar tracks sorted by cosine similarity descending.
    Each result: {file_path, name, similarity, bpm, key}
    Skips candidates without cached features (not yet analyzed).
    """
```

Algorithm:
1. Load query feature vector from cache
2. Load all candidate feature vectors from cache (skip missing)
3. Stack into matrix, L2-normalise rows
4. Cosine similarity = normalised_matrix @ normalised_query
5. Sort descending, exclude query itself, return top_n

### UI Changes (`ui/main_window.py`)

#### Bottom Panel — "Similar" Tab
Add a `QTabWidget` wrapping the existing playlist panel and a new Similar tab.

Similar tab layout:
```
[ Find Similar ]   "Top 10 matches from analyzed library"
─────────────────────────────────────────────────────
 #   Track Name                    Sim%   BPM    Key
 1   07 - Bahara (Chill Version)   94%    89.1   10B
 2   01 - Phone...                 91%    92.3   9B
 ...
─────────────────────────────────────────────────────
Greyed note if track not analyzed: "Analyze track first"
```

- Results table: 5 columns — Rank, Name, Similarity %, BPM, Key
- Double-click row → load that track into the deck
- Right-click row → "Add to Current Playlist"
- "Find Similar" button disabled until a track is loaded and analyzed

#### Library Context Menu
Add "Find Similar Tracks" to right-click menu on library rows.
Switches to Similar tab and populates it.

#### Trigger points
- "Find Similar" button in Similar tab (uses currently loaded track)
- Library right-click → "Find Similar Tracks" (uses right-clicked track)

### Graceful Degradation
- Tracks without `"features"` in cache (analyzed before this update) are silently skipped
- If fewer than 2 candidates have features, show: "Analyze more tracks to get similarity results"
- Query track itself excluded from results

### Testing
- Unit test: `test_similarity_cosine_correctness` — identical feature vectors → similarity 1.0
- Unit test: `test_similarity_skips_missing_features` — candidates without cache entries skipped
- Unit test: `test_mfcc_shape` — verify 20 coefficients returned
