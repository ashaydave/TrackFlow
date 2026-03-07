# TrackFlow — Installation & Setup Guide

For **DJs and music enthusiasts** who want to analyze, organize, and download music.

---

## Quick Start (Windows)

1. **Download** the latest `TrackFlow.exe` from [GitHub Releases](https://github.com/ashaydave/TrackFlow/releases)
2. **Extract** the `TrackFlow` folder anywhere (e.g., `C:\DJ\TrackFlow` or `Downloads`)
3. **Double-click** `TrackFlow.exe` — it will run immediately (no installation needed)
4. **Grant network permission** if Windows Defender asks (TrackFlow downloads from YouTube and Apple Music)

That's it! The app is ready to use.

---

## First Time Setup

When you first open TrackFlow:

1. **Choose your music library folder**
   - Click the **Library** tab
   - Click **Load Folder** and select your DJ music directory
   - TrackFlow will scan it and analyze all tracks (first run takes a few minutes)
   - Analysis results are cached, so subsequent runs are instant

2. **Set download output folder** (optional, for Phase 2 — Downloads tab)
   - Click the **⬇ Downloads** tab
   - Click **Browse** next to "Save to"
   - Choose a folder for downloaded music (can be your library folder, or a staging area)

3. **Subscribe to playlists** (optional)
   - Go to **Downloads → Subscriptions**
   - Add a YouTube playlist URL, an Apple Music playlist URL, or your iTunes library
   - TrackFlow will auto-sync on launch and check for new music

---

## Optional: Install ffmpeg for MP3 Downloads

By default, TrackFlow downloads music as **M4A** (works in all DJ software). If you prefer **MP3 320 kbps**, install ffmpeg:

### Option 1: Using Chocolatey (Recommended)
```bash
choco install ffmpeg
```

### Option 2: Manual Install
1. Download from https://ffmpeg.org/download.html
2. Extract to `C:\ffmpeg\` (or any folder you prefer)
3. Restart TrackFlow

TrackFlow will auto-detect ffmpeg — if found, new downloads will be MP3; otherwise, M4A.

---

## Features at a Glance

### 📊 Track Analysis
- **BPM** detection (beats per minute)
- **Musical key** (Camelot notation, Open Key, relative major/minor)
- **Energy level** (1–10 scale)
- Stored in your library for quick reference

### 🎛️ DJ Controls
- **6 hot cues** (click or press `1`–`6`)
- **A–B seamless loop** with bar-snap presets (½, 1, 2, 4, 8 bars)
- **Waveform zoom** with frequency colors (red = bass, yellow = mids, cyan = highs)
- **Keyboard shortcuts** for seek, loop, cue control

### 🔍 Find Similar Tracks
- Load a track, click **Similar** tab
- TrackFlow finds the 25 most similar tracks in your library
- Based on timbre, pitch, and vibe — not just BPM/key

### ⬇️ Download & Organize
- Paste YouTube URLs and download in the background
- Subscribe to YouTube playlists, Apple Music playlists, or iTunes XML playlists
- Auto-sync on launch — new tracks appear in your queue
- Import downloaded tracks with one click (auto-analyze)

### 🎵 SoulSeek Watcher
- Point TrackFlow at your SoulSeek downloads folder
- Files appear in the watcher automatically as SoulSeek completes them
- Click **Import** to add to your library

---

## Keyboard Shortcuts

| Key | Action |
|---|---|
| `Space` | Play / Pause |
| `←` / `→` | Seek ±5 seconds |
| `Shift+←` / `→` | Seek ±30 seconds |
| `I` | Set loop start (A) |
| `O` | Set loop end (B) |
| `L` | Toggle loop on/off |
| `1`–`6` | Jump to / set hot cue |
| `Shift+1`–`6` | Clear hot cue |
| `Enter` | Play selected track |
| `Delete` | Remove from playlist |

---

## Troubleshooting

### "Antivirus blocked TrackFlow"
**Solution:** TrackFlow is safe. You can:
- Add `dist\TrackFlow\` to your antivirus exclusion list
- Build from source yourself (see below)

### "Downloads fail / Slow speed"
**Solution:**
- Check your internet connection
- YouTube/Apple Music sometimes rate-limit requests
- Try a different playlist or wait a few minutes

### "Can't find my iTunes library"
**Solution:**
- Click **Detect** in the Subscriptions tab — it auto-finds common locations
- Or browse manually: typically at `C:\Users\[YourName]\Music\Music\Music Library.xml` (Apple Music for Windows)

### "Downloaded files are M4A, not MP3"
**Solution:** Install ffmpeg (see "Optional" section above). MP3 output requires ffmpeg.

### "App crashes on startup"
**Solution:**
- If you modified `data/` files manually, delete them — TrackFlow will recreate them on next run
- Report the crash at https://github.com/ashaydave/TrackFlow/issues with the error message

---

## Building from Source (Advanced)

If you want to build the exe yourself or modify TrackFlow:

### Prerequisites
- Python 3.11+
- Conda
- Git

### Steps
```bash
# Clone the repo
git clone https://github.com/ashaydave/TrackFlow.git
cd TrackFlow

# Create conda environment
conda create -n dj-analyzer python=3.11 -y
conda activate dj-analyzer

# Install dependencies
pip install PyQt6 numpy scipy soundfile soxr mutagen pygame yt-dlp watchdog pyinstaller

# Run the app (development)
python main.py

# Build the exe
build.bat
# Output: dist\TrackFlow\TrackFlow.exe
```

---

## Support & Feedback

- **Issues/Bugs:** https://github.com/ashaydave/TrackFlow/issues
- **Feature Requests:** https://github.com/ashaydave/TrackFlow/discussions
- **Built with:** Claude (Anthropic) + Python + PyQt6

---

## What's Next?

- Load your music library and explore the Similar tab
- Try the Downloads tab with a YouTube or Apple Music playlist
- Create custom playlists and export them to your DJ software
- Enjoy seamless looping and hot cues while mixing

Happy DJing! 🎧
