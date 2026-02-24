<p align="center">
  <img src="assets/logo.svg" width="120" alt="TrackFlow logo">
</p>

<h1 align="center">TrackFlow</h1>

<p align="center">
  A desktop DJ track analysis and preview tool built with PyQt6.
  <br>
  Analyze BPM, musical key, and energy levels across your music library — then preview, loop, and organize tracks into playlists.
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

**Waveform & Visualization**
- Frequency-colored filled waveform (red = bass, amber = mid, cyan = high)
- Beat and bar grid overlay synced to detected BPM
- Drag-to-seek on waveform
- Playhead tracking during playback

**DJ Controls**
- 6 color-coded hot cues with persistence (keys 1–6, Shift+1–6 to set)
- A–B loop with bar-snap presets (½, 1, 2, 4, 8 bars)
- Loop in/out controls with visual overlay on waveform
- Play/pause, seek forward/back via keyboard shortcuts

**Library & Playlists**
- Load individual tracks or entire folders
- Sortable columns: track name, BPM, key (Camelot order), energy level
- Low-bitrate flag on tracks below 320 kbps
- Search/filter across library
- Create, delete, and export playlists (M3U)
- Multi-select drag-and-drop from library to playlist
- Multi-delete from playlist
- Click any track in library or playlist to load and preview it

**Keyboard Shortcuts**
| Key | Action |
|-----|--------|
| `Space` | Play / Pause |
| `←` `→` | Seek ±5 seconds |
| `I` | Set loop in-point |
| `O` | Set loop out-point / stop loop |
| `1`–`6` | Jump to hot cue |
| `Shift+1`–`6` | Set hot cue |
| `Enter` | Add selected library track to playlist |
| `Delete` | Remove selected playlist track(s) |
| `F1` | Open help |

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

## Project Structure

```
TrackFlow/
├── main.py                  # Application entry point
├── analyzer/
│   ├── audio_analyzer.py    # Core BPM/key/energy analysis engine
│   └── batch_analyzer.py    # Thread pool batch analysis + JSON cache
├── ui/
│   ├── main_window.py       # Main application window and all UI logic
│   ├── waveform_dj.py       # Frequency-colored waveform widget
│   ├── audio_player.py      # Pygame-based audio player with state machine
│   └── styles.py            # Centralized cyberpunk QSS stylesheet
├── assets/
│   └── logo.svg             # Application logo
├── data/
│   ├── cache/               # Analysis results cache (JSON)
│   └── hot_cues.json        # Saved hot cue positions
└── tests/
    ├── test_analyzer_speed.py
    └── test_batch_analyzer.py
```

## Built With

This project was built entirely with [Claude](https://claude.ai) by Anthropic — from the analysis engine and UI layout to the waveform rendering and keyboard shortcuts.

## License

This project is open source and available under the [MIT License](LICENSE).
