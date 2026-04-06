<p align="center">
  <img src="assets/logo.svg" width="120" alt="TrackFlow logo">
</p>

<h1 align="center">TrackFlow</h1>

<p align="center">
  A desktop DJ track analysis, preview, and download tool built with PyQt6.<br>
  Analyze BPM, key, and energy across your library — then preview, loop, cue, find similar tracks,<br>
  organize playlists, and auto-download new music from YouTube, Apple Music, Spotify, Shazam, and SoulSeek.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11-blue?style=flat-square" alt="Python 3.11">
  <img src="https://img.shields.io/badge/framework-PyQt6-green?style=flat-square" alt="PyQt6">
  <img src="https://img.shields.io/badge/built%20with-Claude-cc785c?style=flat-square" alt="Built with Claude">
</p>

---

## Features

### 📊 Analysis Engine
- **BPM detection** via onset-based autocorrelation on a mel spectrogram — analyzes first 60s, pure NumPy/SciPy (no librosa/numba overhead)
- **Musical key detection** using chroma-based Krumhansl–Schmuckler profiles across all 24 major/minor keys, returned in standard, Camelot wheel, and Open Key notation
- **Energy level scoring** (1–10) from full-track RMS via 65 536-sample chunked reads — constant memory usage regardless of file size
- **Genre detection** using Essentia's Discogs-EffNet model (400 Discogs genre/style labels) via ONNX Runtime — no TensorFlow required, works on Windows. Top genres appear in the library table and cache per-track
- Audio metadata extraction (format, bitrate, sample rate, duration, file size)
- Batch analysis with background thread pool and JSON cache (skips already-analyzed tracks)

### 🔍 Track Similarity
- Find the 25 most similar tracks in your library to any loaded track
- **32-dimensional feature vectors**: 20 MFCC coefficients (timbral texture, spectral envelope) + 12 chroma means (pitch-class energy across the 12 semitones)
- **Cosine similarity** — measures the angle between feature vectors, not their magnitude, so loudness differences between tracks don't affect the score. Displayed as 0–100% match
- Results in a dedicated **Similar** tab with BPM, key, and score; double-click to load

### 🌊 Waveform & Visualization
- Frequency-colored filled waveform: **red** = bass (0–200 Hz), **amber** = mids (200–4000 Hz), **cyan** = highs (4000+ Hz)
- **Overview panel** (40px) — full-track minimap, click anywhere to seek
- **Main panel** (120px) — auto-zooms to a ±15s window around the playhead for beat-level precision
- Beat and bar grid overlay synced to detected BPM
- Hot cue tick marks and loop region overlay rendered on both panels
- Click or drag-to-seek (seeks on mouse release, no audio artifacts)

### 🎛️ DJ Controls
- **6 color-coded hot cues** with persistence across sessions (keys `1`–`6`, `Shift+1–6` to clear)
- **Seamless A–B looping** — loop region decoded into RAM and played via `pygame.Sound(loops=-1)`, eliminating the pop/gap found in timer-based approaches
- **Bar-snap loop presets**: ½, 1, 2, 4, 8 bars from nearest beat
- Loop in/out controls (`I` / `O` keys) with live overlay on both waveform panels
- Volume slider, play/pause, and keyboard-driven seeking

### 📚 Library & Playlists
- Load individual tracks or entire folders (recursive scan); **multi-file select** supported
- Sortable columns: track name, BPM, key (Camelot order), energy level
- Low-bitrate flag on tracks below 320 kbps
- Search/filter across library
- Create, delete, and export playlists (copy tracks to folder)
- Multi-select drag-and-drop from library to playlist
- Multi-delete from playlist; sort playlist by BPM or key

### ⬇️ Downloads (Phase 2)

#### YouTube
- Paste any YouTube video or playlist URL into the **Queue** tab
- Downloads as **MP3 320 kbps** when ffmpeg is detected (auto-detected in common install paths); falls back to native m4a if ffmpeg is unavailable
- Per-row progress indicator with format badge; **Import** button appears on completion
- **⏹ Stop** cancels all active and pending queue items at once
- Per-row **✕** button and **✕ Remove Selected** to clear finished or unwanted entries
- Bulk **Import Selected** adds finished tracks to the library and auto-triggers analysis

#### Playlist Subscriptions
Subscribe to YouTube, Apple Music, or Spotify playlists. On every app launch, TrackFlow checks for new additions and queues them automatically.

| Source | How it works |
|---|---|
| **YouTube Playlist** | yt-dlp `extract_flat` fetches the playlist index; new video IDs are downloaded directly |
| **Apple Music URL** | Paste any public `music.apple.com` playlist URL — TrackFlow extracts the anonymous JWT developer token from Apple's web-player JS bundle and calls the Apple Music catalog API to list tracks |
| **iTunes XML** | Parses the `iTunes Music Library.xml` written by Apple Music for Windows (uses Python stdlib `plistlib`) — works for private/personal playlists not accessible via URL |
| **Spotify** | Paste any public `open.spotify.com/playlist/...` URL — TrackFlow scrapes embedded track metadata from the playlist page (no API key needed) |
| **Shazam** | Shazam syncs to Apple Music — enable the Apple Music integration and add the "Shazam Library" playlist via iTunes XML |

For Apple Music, Spotify, and Shazam tracks, TrackFlow searches YouTube using three query variants (`Artist - Title`, `Title Artist`, `Artist Title official audio`) and downloads the best match. Tracks not found on YouTube are shown in a **Not Found** table for manual retry.

Sync state is persisted in `data/sync_state.json` — already-downloaded tracks are never re-queued. Use **🗑 Clear Cache** next to any subscription to reset its sync history (useful when testing or re-downloading a playlist).

#### SoulSeek Watcher
- Point TrackFlow at your SoulSeek "completed downloads" folder
- `watchdog` monitors the folder in real time (catches both new file creation and SoulSeek's `.tmp` → final filename rename-on-completion)
- Each detected audio file appears in the watcher table with an **Import** button

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Space` | Play / Pause |
| `←` / `→` | Seek ±5 seconds |
| `Shift+←` / `→` | Seek ±30 seconds |
| `I` | Set loop in-point (A) |
| `O` | Set loop out-point (B) |
| `L` | Toggle loop on / off |
| `1`–`6` | Jump to hot cue (sets if empty) |
| `Shift+1`–`6` | Clear hot cue |
| `Enter` | Play selected track (library or playlist) |
| `Delete` | Remove selected track(s) from playlist |
| `F1` / `?` | Open help |

---

## Getting Started

### Prerequisites

- Python 3.11+
- Conda (recommended) or pip
- **ffmpeg** (optional) — required for MP3 320 kbps output. TrackFlow auto-detects it from your PATH and common install locations; without it, downloads fall back to m4a.

### Installation

```bash
# Clone the repository
git clone https://github.com/ashaydave/TrackFlow.git
cd TrackFlow

# Create conda environment
conda create -n dj-analyzer python=3.11 -y
conda activate dj-analyzer

# Install dependencies
pip install PyQt6 numpy scipy soundfile soxr mutagen pygame yt-dlp watchdog onnxruntime
```

> **Genre detection** requires `onnxruntime` (included above). The Discogs-EffNet model (~37 MB) downloads automatically on first use. If `onnxruntime` is unavailable the rest of the app works normally — the Genre column simply stays empty.

### Run

```bash
python main.py
```

### Build Executable (Windows)

```bash
build.bat
# Output: dist\TrackFlow\TrackFlow.exe
```

Requires PyInstaller (`pip install pyinstaller`) and the conda environment above. See `build.bat` for details.

---

## Using the Downloads Tab

### YouTube — single track or playlist

1. Click the **⬇ Downloads** tab at the top of the window
2. Set your **Save to** folder (your DJ library folder, or a staging area)
3. Paste a YouTube URL (video or playlist) into the URL bar and click **+ Add**
4. Click **▶ Download All** — progress updates per row; the format badge shows `MP3` or `M4A`
5. When a row shows **✓ Done**, click **⬆ Import** to add it to the library and trigger analysis
6. Use **⏹ Stop** to cancel all downloads at once, or **✕** on individual rows to remove them

### Playlist Subscriptions

1. Go to **⬇ Downloads → Subscriptions**
2. **YouTube:** click **+ Add YouTube Playlist**, paste the playlist URL, give it a label
3. **Apple Music (URL):**
   - Paste a public `music.apple.com` playlist URL into the **Apple Music URL** field and click **+ Subscribe**
   - TrackFlow automatically fetches the track list from the Apple Music catalog API
4. **Spotify:**
   - Paste a public `open.spotify.com/playlist/...` URL into the **Spotify** field and click **+ Add**
   - TrackFlow scrapes the track list from the public page (no API key required)
5. **Apple Music (iTunes XML / Shazam):**
   - Click **Detect** to auto-find your `iTunes Music Library.xml`, or browse manually
   - Click **+ Add Playlist** and type the playlist name exactly as it appears in Apple Music (e.g. `Shazam Library`)
6. Click **🔄 Sync Now** to run a manual check, or simply relaunch the app — sync runs automatically 2 seconds after startup
7. Use **🗑 Clear Cache** next to a subscription to re-sync all tracks (bypasses the already-seen filter)
8. New tracks appear in the Queue tab; click **Import Selected** to bring them into the library

### SoulSeek Watcher

1. Go to **⬇ Downloads → SoulSeek Watcher**
2. Click **Browse** and navigate to your SoulSeek "Finished Downloads" folder
3. Click **▶ Start Watching** — the status indicator turns green
4. As SoulSeek completes downloads, files appear in the table automatically
5. Click **⬆ Import** on any row (or **Import All New**) to add files to the library

---

## Project Structure

```
TrackFlow/
├── main.py                    # Application entry point
├── paths.py                   # Path resolution (dev + frozen exe)
├── build.bat                  # One-click Windows build script
├── TrackFlow.spec             # PyInstaller spec (includes all Phase 2 modules)
├── analyzer/
│   ├── audio_analyzer.py      # BPM / key / energy / MFCC / chroma engine
│   ├── batch_analyzer.py      # Background batch analysis + JSON cache
│   ├── genre_detector.py      # Discogs-EffNet ONNX genre detection (400 styles)
│   └── similarity.py          # 32-dim cosine similarity search
├── downloader/
│   ├── yt_handler.py          # DownloadWorker(QThread) — yt-dlp wrapper,
│   │                          #   ffmpeg auto-detection, MP3/M4A format selection
│   ├── watcher.py             # FolderWatcher(QObject) — watchdog wrapper
│   └── playlist_sync.py       # YouTubePlaylistSource, AppleMusicSource,
│                              #   AppleMusicURLSource, SpotifyPlaylistSource,
│                              #   PlaylistSyncWorker, search_youtube()
├── ui/
│   ├── main_window.py         # Main window, Library tab, all DJ controls
│   ├── downloads_tab.py       # Downloads tab (Queue / Subscriptions / SoulSeek)
│   ├── waveform_dj.py         # Frequency-colored waveform widget
│   ├── audio_player.py        # Pygame player (STOPPED/PLAYING/PAUSED/LOOP_PLAYING)
│   └── styles.py              # Centralized cyberpunk QSS stylesheet
├── assets/
│   ├── logo.svg               # Application logo (vector)
│   ├── logo_32.png            # Toolbar icon
│   └── logo_256.png           # Window / tray icon
├── data/
│   ├── cache/                 # Analysis cache (JSON, keyed by path+mtime+size)
│   ├── hot_cues.json          # Saved hot cue positions per track
│   ├── playlists.json         # Saved playlists
│   ├── sync_state.json        # Last-known playlist state (prevents re-downloads)
│   └── downloads_config.json  # Output folder, watch dir, subscriptions
└── tests/
    ├── test_analyzer_speed.py
    ├── test_batch_analyzer.py
    ├── test_similarity.py
    ├── test_genre.py          # 17 tests — genre cache, model manifest, label cleaning,
    │                          #   format_genres edge cases, onnxruntime availability
    └── test_downloads.py      # FolderWatcher, AppleMusicSource, AppleMusicURLSource,
                               #   sync state, yt_handler imports
```

---

## Built With

This project was built entirely with [Claude](https://claude.ai) by Anthropic — from the analysis engine and UI layout to the waveform rendering, seamless looping, similarity search, and the full playlist-sync and download pipeline.

## License

This project is open source and available under the [MIT License](LICENSE).
