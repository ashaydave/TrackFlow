# TrackFlow — Session Summary

> Last updated: 2026-02-28
> Use this file to give a new Claude session full context on the project.

---

## Project Overview

**TrackFlow** is a desktop DJ tool built with Python / PyQt6, located at:
`C:\Users\ashay\Documents\Claude\dj-track-analyzer`

- **Conda env**: `dj-analyzer` (Python 3.11)
- **Run**: `conda activate dj-analyzer && python main.py`
- **Tests**: `conda run -n dj-analyzer python -m pytest tests/ -v` → **50 tests, all passing**
- **Build**: `build.bat` → `dist\TrackFlow\TrackFlow.exe` (PyInstaller, Windows only)
- **GitHub**: `https://github.com/ashaydave/TrackFlow.git` (branch: `main`)

---

## What Has Been Built

### Phase 1 — Intelligent Track Analysis (complete)
- BPM detection, musical key (Camelot + Open Key), energy scoring
- 32-dim cosine similarity search (MFCC + chroma)
- Frequency-colored waveform (red/amber/cyan for bass/mids/highs) with overview + main panels
- Beat/bar grid overlay, hot cues (6, color-coded, persistent), A–B seamless loop
- Library management, multi-playlist support, search/filter
- Cyberpunk QSS dark theme

### Phase 2 — Downloads Tab (complete)
Full downloads system across three sub-tabs:

| Sub-tab | Features |
|---|---|
| **Queue** | Add YouTube URLs; yt-dlp download worker; MP3 320kbps (auto-detected ffmpeg) or M4A fallback; per-row progress + format badge; ⏹ Stop All; ✕ per-row remove; ✕ Remove Selected; ⬆ Import to library |
| **Subscriptions** | YouTube playlist subscriptions; Apple Music URL subscriptions (public playlists via catalog API); iTunes XML subscriptions (for private/Shazam playlists); sync on launch + manual Sync Now; 🗑 Clear Cache per subscription; ⚠ amber error feedback |
| **SoulSeek Watcher** | watchdog monitors a folder in real-time; detects new audio files and tmp→final renames; Import / Import All New buttons |

---

## Current File Map

```
TrackFlow/
├── main.py
├── paths.py
├── build.bat
├── TrackFlow.spec             ← PyInstaller (includes all Phase 2 modules)
├── analyzer/
│   ├── audio_analyzer.py
│   ├── batch_analyzer.py
│   └── similarity.py
├── downloader/
│   ├── yt_handler.py          ← DownloadWorker, find_ffmpeg()
│   ├── watcher.py             ← FolderWatcher (watchdog)
│   └── playlist_sync.py       ← YouTubePlaylistSource, AppleMusicSource,
│                                 AppleMusicURLSource, PlaylistSyncWorker
├── ui/
│   ├── main_window.py
│   ├── downloads_tab.py       ← All Downloads tab UI + logic
│   ├── waveform_dj.py
│   ├── audio_player.py
│   └── styles.py
├── assets/ (logo files)
├── data/  (runtime-generated, gitignored)
│   ├── cache/
│   ├── hot_cues.json
│   ├── playlists.json
│   ├── sync_state.json        ← Cleared by "🗑 Clear Cache" button
│   └── downloads_config.json
└── tests/
    ├── test_analyzer_speed.py  (25 tests)
    ├── test_batch_analyzer.py
    ├── test_similarity.py       (5 tests)
    └── test_downloads.py        (25 tests)
```

---

## Key Technical Details

### Apple Music URL Support (`downloader/playlist_sync.py` → `AppleMusicURLSource`)

**How it works (as of 2026-02-28):**

Apple embeds an anonymous JWT developer token in their main web-player JS bundle. This token is valid for ~6 months and is sufficient to call the public Apple Music catalog API for any public playlist.

1. `_get_apple_token()` fetches `https://music.apple.com/`
2. Finds `<script src="/assets/index~HASH.js">` (skips legacy/polyfill variants)
3. Fetches the bundle, extracts the JWT with regex
4. Token is cached at class level for the session (only paid once)
5. `_try_apple_api()` calls `amp-api.music.apple.com/v1/catalog/{storefront}/playlists/{id}/tracks` with `Authorization: Bearer {token}`, paginating up to 10 pages (100 tracks/page)

**Fallback chain in `get_tracks()`:**
1. `_try_apple_api()` — primary (catalog API with JWT from JS bundle)
2. `_try_page_scrape()` — checks JSON-LD, `serialized-server-data`, `__NEXT_DATA__`
3. yt-dlp — last resort (always fails for music.apple.com, but harmless)
4. Sets `self.last_error` and emits `source_error` signal if all fail

**What caused the original failure:** The code was only searching the HTML page for the JWT. Apple moved the token to the JS bundle (`index~*.js`). The fix was to parse the `<script src>` tags from the HTML and fetch the bundle.

**URL format handled:** `https://music.apple.com/{storefront}/playlist/{name}/{id}`
e.g. `https://music.apple.com/us/playlist/house/pl.u-xlyNEpPTJWmpxYd`

### ffmpeg Detection (`downloader/yt_handler.py` → `find_ffmpeg()`)
- `shutil.which("ffmpeg")` first (handles PATH installs)
- Glob search across common Windows paths including:
  - `C:\Program Files (x86)\YouTube Playlist Downloader\ffmpeg.exe`
  - `C:\ffmpeg\bin\ffmpeg.exe` and similar
- Returns path string or `None`; stored as `self._ffmpeg_path` in `DownloadsTab`
- If found: `FFmpegExtractAudio` postprocessor → MP3 320kbps
- If not found: native m4a (no postprocessor)

### Sync State (`data/sync_state.json`)
```json
{
  "apple_music_url::https://music.apple.com/...": ["track_id_1", "track_id_2", ...],
  "https://youtube.com/playlist?list=...": ["yt_video_id_1", ...]
}
```
- Loaded at sync start, checked per-track, saved after sync
- "🗑 Clear Cache" button in Subscriptions tab calls `save_sync_state({})` (clears ALL sources)

### Queue Index Pattern
Queue rows use a stored `q_idx` (dict with `row` key) so remove-by-index works even after rows are removed. The `lambda` captures by value: `lambda _checked=False, idx=q_idx: self._remove_queue_item_by_idx(idx)`

### PlaylistSyncWorker Signals
```python
new_track       = pyqtSignal(dict)   # {title, artist, url, source_id, source_label}
track_not_found = pyqtSignal(dict)   # {title, artist, source_id, source_label}
source_done     = pyqtSignal(str, int)  # source_id, new_track_count
source_error    = pyqtSignal(str, str)  # source_id, error_message
all_done        = pyqtSignal()
```

### Multi-file Import Fix (`ui/main_window.py`)
`_load_single_track` was changed to use `QFileDialog.getOpenFileNames` (plural) and loops over all selected paths.

---

## Bugs Fixed in the Last Two Sessions

| Bug | Fix |
|---|---|
| `AttributeError: 'QTableWidget' object has no attribute 'isRowSelected'` | Replaced with `{idx.row() for idx in self._queue_table.selectedIndexes()}` |
| Can only select one file at a time | `getOpenFileName` → `getOpenFileNames` in `_load_single_track` |
| Downloads as m4a, not MP3 | Added `find_ffmpeg()` + `FFmpegExtractAudio` postprocessor in `DownloadWorker` |
| ✕ Remove buttons invisible (dark bg) | Restyled to red "✕ Remove" buttons |
| Apple Music URL: "Unsupported URL" (yt-dlp) | Implemented 3-stage approach; primary: catalog API with JWT token |
| JWT token not found (HTML only, not bundle) | Fixed `_get_apple_token()` to fetch and search `index~*.js` JS bundle |
| Import button clipped as "Imr" | Fixed Action column to `QHeaderView.ResizeMode.Fixed` at 90px; import button `setFixedSize(88, 22)` |
| Stop only cancels active download | `_on_stop_download` now marks ALL pending rows as "✕ Cancelled" too |
| No way to remove tracks from queue | Added per-row ✕ button + "✕ Remove Selected" bottom button |
| Sync cache blocks re-testing | Added "🗑 Clear Cache" button calling `save_sync_state({})` |
| Sync error shown only in terminal | Added `source_error` signal → amber `⚠ label: message` in status label |

---

## Known Limitations / Future Work

- **Apple Music JWT expiry**: The token Apple embeds in their bundle is valid for ~6 months. If it expires and the Apple Music bundle structure changes, `_get_apple_token()` may need updating. The class-level cache (`_cached_token`) can be manually cleared between sessions.
- **SoulSeek**: TrackFlow watches a folder but does not control SoulSeek directly — it relies on the user running SoulSeek separately.
- **Windows only**: The build system and some paths (ffmpeg detection, iTunes XML paths) are Windows-specific.
- **No cloud sync**: Library, playlists, hot cues, and sync state are stored locally in `data/`.
- **Tracks not found on YouTube**: When Apple Music tracks can't be matched on YouTube, they go to a "Not Found" table. There's no automatic retry or alternative source.

---

## Possible Next Features

- Show waveform thumbnail in library/playlist rows
- BPM tap-tempo override
- Export analysis data to CSV / Rekordbox XML
- Beatgrid editing
- Rate / tag tracks (star rating, custom tags)
- Auto-match BPM between two loaded tracks (DJ pitch adjustment)
- Support for Spotify URL subscriptions (would need Spotify API credentials)
- macOS build support

---

## How to Continue in a New Session

1. Open Claude Code in `C:\Users\ashay\Documents\Claude\dj-track-analyzer`
2. Share this file: `.claude/session-summary.md`
3. Run `conda run -n dj-analyzer python -m pytest tests/ -v` to confirm baseline (should be 50 passing)
4. Check `git log --oneline -5` to see recent commits
5. Pick up from "Possible Next Features" above or address any new bugs
