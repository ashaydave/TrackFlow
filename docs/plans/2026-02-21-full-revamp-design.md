# DJ Track Analyzer — Full Revamp Design
**Date:** 2026-02-21
**Author:** Ashay
**Status:** Approved — ready for implementation
**Option:** C (Surgical revamp — fix bugs + UI redesign + speed + batch)

---

## Goals

1. **Speed** — Analysis in ≤2s per track; batch-analyze entire 5-7 GB library
2. **Waveform** — Frequency-colored bars exactly like Rekordbox/VirtualDJ
3. **Bug fixes** — Playback plays on first click, no race conditions
4. **UI** — Professional cyberpunk/dark aesthetic; Rekordbox-grade layout
5. **Batch + Cache** — Analyze all, cache results, instant reload

---

## Layout Design

```
┌─────────────────────────────────────────────────────────────────┐
│  ◈ DJ TRACK ANALYZER   [Load Track] [Load Folder] [Analyze All] │
│                         ░░░░░░░░░░░░░ 0%  [Search............] │
├──────────────┬──────────────────────────────────────────────────┤
│ TRACK LIBRARY│  LudoWic — MIND PARADE                          │
│              │                                                  │
│ ▸ Track   BPM│  ┌───────┐  ┌───────┐  ┌───────┐  ┌─────────┐ │
│   track1 103 │  │ 103.4 │  │A Major│  │  11B  │  │ ●●●●●●●●●│ │
│   track2  -- │  │  BPM  │  │  KEY  │  │CAMELOT│  │  9/10   │ │
│   track3  -- │  └───────┘  └───────┘  └───────┘  └─────────┘ │
│   ...        │                                                  │
│              │  ┌──────────────────────────────────────────┐   │
│              │  │  OVERVIEW WAVEFORM (full track, 60px)    │   │
│              │  └──────────────────────────────────────────┘   │
│              │  ┌──────────────────────────────────────────┐   │
│              │  │  MAIN WAVEFORM (freq-colored, 130px)     │   │
│              │  └──────────────────────────────────────────┘   │
│              │                                                  │
│              │  ▶ Play  ⏹ Stop   ◀◀ -10s   +10s ▶▶           │
│              │  ─────────●──────────────────  2:13 / 5:20      │
│              │  VOL ████████░░  75%                            │
│              │                                                  │
│ 247 tracks   │  MP3  ·  320 kbps  ·  44.1 kHz  ·  5.3 MB      │
└──────────────┴──────────────────────────────────────────────────┘
```

---

## Component Design

### 1. AudioAnalyzer (speed overhaul)

**Current problem:** `librosa.load()` decodes entire file at 22050 Hz — 5-min track = ~6.6M samples, takes 5-10s.

**Fix strategy:**
- Use `soundfile.read()` for raw PCM decoding (2-3× faster than librosa decoder)
- Analyze only first **60 seconds** for BPM — sufficient for electronic music
- Analyze only first **30 seconds** for key — chroma stabilizes quickly
- Metadata via `mutagen` only (no audio load needed) — instant
- Duration via `mutagen` info — no audio load needed
- Energy: RMS on downsampled mono, first 60s only
- Waveform data: generated separately in WaveformThread, not in analyzer

**Target:** ≤2 seconds per track on typical hardware.

**New `analyze_track()` flow:**
```
soundfile.read(file, frames=60*sr, dtype='float32', always_2d=True)
  → mono mix for analysis
  → BPM on mono[:60s]
  → Key on mono[:30s]
  → Energy on mono[:60s]
  → Metadata from mutagen (separate, no audio)
  → Duration from mutagen.info.length
```

### 2. WaveformDJ (complete rewrite)

**Current problem:** Per-pixel Python loop; no frequency coloring; solid blob look.

**New design:**
- **Data:** 3 frequency bands per bar
  - Bass: 0–200 Hz → color `#0055ff` (deep blue)
  - Mid: 200–4000 Hz → color `#00aaff` (cyan/sky)
  - High: 4000+ Hz → color `#aaddff` / `#ffffff` (white-blue)
  - Each bar gets a mixed color based on dominant band
- **Rendering:** Vectorized NumPy, then single `QPainterPath` batch draw — no Python loop
- **Bar spec:** 2px wide, 1px gap = 1 bar per 3 pixels. At 900px width = 300 bars
- **Two waveforms:**
  - **Overview** (60px height): full-track, non-interactive except click-to-seek
  - **Main** (130px height): zoomed 30-second window around playhead, scrolls
- **Playhead:** White vertical line with triangle marker on both waveforms
- **Played portion:** Bars to left of playhead rendered 40% darker

**Waveform data generation (WaveformThread):**
```
soundfile.read(full file) → stereo
STFT per 300 bars → extract bass/mid/high RMS per bar
Normalize each band 0–1
Store as numpy array shape (300, 3)  ← bass, mid, high amplitudes
```

### 3. AudioPlayer (bug fix)

**Current bug:** `toggle_playback()` calls `resume()` whenever `current_file` is set, even on first play. Audio is never started.

**Fix:** Add `_state` enum: `STOPPED | PAUSED | PLAYING`.
- `STOPPED` → call `play()` (starts from beginning)
- `PAUSED` → call `resume()` (continues from pause point)
- `PLAYING` → call `pause()`

Also fix: remove `time.sleep(0.1)` from `load()` — this runs on main thread and freezes UI.

### 4. BatchAnalyzer (new)

**Design:**
- `ThreadPoolExecutor(max_workers=3)` — 3 parallel analysis threads
- JSON cache: `data/cache/{md5_of_filepath}.json` — analyzed once, loaded instantly after
- Cache invalidation: compare file mtime + size
- API:
  ```python
  batch.submit(file_paths)          # queues all
  batch.on_track_done(callback)     # signal per track
  batch.on_all_done(callback)       # signal when complete
  batch.cancel()                    # stop queue
  ```

### 5. MainWindow (UI revamp)

**QSS Theme (cyberpunk dark):**
```
Background:     #0a0a0f  (near-black with blue tint)
Panel:          #0f0f1a
Surface:        #151525
Accent:         #0088ff  (electric blue)
Accent2:        #00ccff  (cyan)
Text primary:   #ffffff
Text secondary: #8899aa
Border:         #1a2233
Hover:          #1a1a3a
```

**Toolbar changes:**
- Add "Analyze All" button with progress bar embedded in toolbar
- Progress bar: thin, accent-colored, shows batch progress
- Status area: shows current operation inline

**Track library changes:**
- Add status column (icon): ✓ cached | ⟳ analyzing | · pending
- Color rows: cached=normal, analyzing=highlighted with accent border, pending=dimmed
- BPM + Key shown in library table after analysis
- Right-click context menu: Re-analyze, Open in Explorer

**Info boxes:**
- Remove box borders; use clean card style with subtle glow on hover
- Energy shown as dot-meter (●●●●●●●○○○) not just "9/10"
- BPM gets larger font (36px), key/camelot slightly smaller (28px)

**Player controls:**
- Add seek bar (position slider) with time display
- Add ±10s skip buttons
- Volume slider styled with gradient fill

---

## File Plan

### Modified files:
- `analyzer/audio_analyzer.py` — speed overhaul (soundfile, segment analysis)
- `ui/waveform_dj.py` — complete rewrite (freq colors, vectorized, two waveforms)
- `ui/audio_player.py` — fix playback state bug, remove sleep
- `ui/main_window.py` — UI revamp, batch controls, new layout

### New files:
- `analyzer/batch_analyzer.py` — BatchAnalyzer with thread pool + JSON cache
- `ui/styles.py` — centralized QSS stylesheet

### Unchanged:
- `main.py` — no changes needed
- `analyzer/__init__.py`, `ui/__init__.py`

---

## Implementation Order

1. `ui/styles.py` — QSS stylesheet (no deps)
2. `analyzer/audio_analyzer.py` — speed fixes (no UI deps)
3. `analyzer/batch_analyzer.py` — batch + cache (depends on analyzer)
4. `ui/audio_player.py` — playback bug fix (no UI deps)
5. `ui/waveform_dj.py` — new waveform (no UI deps beyond PyQt6)
6. `ui/main_window.py` — wire everything together

---

## Success Criteria

- [ ] Single track analysis completes in ≤2 seconds
- [ ] Play button works on first click, every time
- [ ] Waveform shows clearly defined bars with frequency coloring (bass/mid/high)
- [ ] "Analyze All" batch-processes folder with 3 parallel workers
- [ ] Re-loading analyzed folder is instant (cache hit)
- [ ] UI feels like professional DJ software (dark, clean, cyberpunk)
- [ ] No Python loop in waveform paint event
