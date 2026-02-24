<p align="center">
  <img src="assets/logo.svg" width="120" alt="TrackFlow logo">
</p>

<h1 align="center">TrackFlow</h1>

<p align="center">
  A desktop DJ track analysis and preview tool built with PyQt6.
  <br>
  Analyze BPM, musical key, and energy levels across your music library — then preview, loop, cue, find similar tracks, and organize into playlists.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11-blue?style=flat-square" alt="Python 3.11">
  <img src="https://img.shields.io/badge/framework-PyQt6-green?style=flat-square" alt="PyQt6">
  <img src="https://img.shields.io/badge/built%20with-Claude-cc785c?style=flat-square" alt="Built with Claude">
</p>

---

## Features

**Analysis Engine**
- BPM detection via onset-based autocorrelation (first 60s for speed)
- Musical key detection using chroma-based Krumhansl-Schmuckler algorithm with Camelot notation
- Energy level scoring (1–10) from full-track RMS via chunked reads
- Audio metadata extraction (format, bitrate, sample rate, duration, file size)
- Batch analysis with thread pool and JSON cache

**Track Similarity**
- Find the 25 most similar tracks in your library to any loaded track
- 32-dimensional feature vectors: 20 MFCC coefficients (timbre/texture) + 12 chroma means (pitch class)
- Cosine similarity scoring — loudness-independent, 0–100% match score
- Results shown in dedicated Similar tab with BPM, key, and match score
- Requires tracks to be analyzed first; double-click any result to load it

**Waveform & Visualization**
- Frequency-colored filled waveform (red = bass, amber = mid, cyan = high)
- Beat and bar grid overlay synced to detected BPM
- Click or drag-to-seek on waveform (seeks on release, no audio artifacts)
- Playhead tracking during playback

**DJ Controls**
- 6 color-coded hot cues with persistence (keys 1–6, Shift+1–6 to clear)
- **Seamless A–B looping** — loop region decoded into memory and played via `pygame.Sound(loops=-1)`, eliminating the pop/gap found in timer-based approaches
- Bar-snap loop presets: ½, 1, 2, 4, 8 bars from nearest beat
- Loop in/out controls (I / O keys) with visual overlay on waveform
- Play/pause, seek forward/back via keyboard shortcuts

**Library & Playlists**
- Load individual tracks or entire folders
- Sortable columns: track name, BPM, key (Camelot order), energy level
- Low-bitrate flag on tracks below 320 kbps
- Search/filter across library
- Create, delete, and export playlists (copy to folder)
- Multi-select drag-and-drop from library to playlist
- Multi-delete from playlist
- Click any track in library, playlist, or similarity results to load and preview

**Keyboard Shortcuts**
| Key | Action |
|-----|--------|
| `Space` | Play / Pause |
| `←` / `→` | Seek ±5 seconds |
| `Shift+←` / `→` | Seek ±30 seconds |
| `I` | Set loop in-point |
| `O` | Set loop out-point / stop loop (press again to stop) |
| `L` | Toggle loop on / off |
| `1`–`6` | Jump to hot cue (sets if empty) |
| `Shift+1`–`6` | Clear hot cue |
| `Enter` | Play selected track (library or playlist) |
| `Delete` | Remove selected track(s) from playlist |
| `F1` / `?` | Open help |

## Getting Started

### Prerequisites

- Python 3.11+
- Conda (recommended) or pip

### Installation

```bash
# Clone the repository
git clone https://github.com/ashaydave/TrackFlow.git
cd TrackFlow

# Create conda environment
conda create -n trackflow python=3.11 -y
conda activate trackflow

# Install dependencies
pip install PyQt6 numpy scipy soundfile soxr mutagen pygame
```

### Run

```bash
python main.py
```

### Build Executable (Windows)

```bash
build.bat
# Output: dist\TrackFlow\TrackFlow.exe
```

Requires PyInstaller (`pip install pyinstaller`) and the `dj-analyzer` conda environment.

## Project Structure

```
TrackFlow/
├── main.py                  # Application entry point
├── paths.py                 # Centralized path resolution (dev + frozen exe)
├── analyzer/
│   ├── audio_analyzer.py    # Core BPM/key/energy/MFCC/chroma analysis engine
│   ├── batch_analyzer.py    # Thread pool batch analysis + JSON cache
│   └── similarity.py        # 32-dim cosine similarity search
├── ui/
│   ├── main_window.py       # Main application window and all UI logic
│   ├── waveform_dj.py       # Frequency-colored waveform widget
│   ├── audio_player.py      # Pygame-based audio player (STOPPED/PLAYING/PAUSED/LOOP_PLAYING)
│   └── styles.py            # Centralized cyberpunk QSS stylesheet
├── assets/
│   ├── logo.svg             # Application logo (vector)
│   ├── logo_32.png          # Toolbar icon
│   └── logo_256.png         # Window icon
├── data/
│   ├── cache/               # Analysis results cache (JSON, keyed by path+mtime+size)
│   └── hot_cues.json        # Saved hot cue positions
└── tests/
    ├── test_analyzer_speed.py
    ├── test_batch_analyzer.py
    └── test_similarity.py
```

## Built With

This project was built entirely with [Claude](https://claude.ai) by Anthropic — from the analysis engine and UI layout to the waveform rendering, seamless looping, and similarity search.

## License

This project is open source and available under the [MIT License](LICENSE).
