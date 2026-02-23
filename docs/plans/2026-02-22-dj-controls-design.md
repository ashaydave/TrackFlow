# DJ Controls Enhancement — Design Doc
**Date:** 2026-02-22
**Status:** Approved

---

## Overview

Add a DJ controls strip (hot cues + A-B loop) below the waveform, upgrade the waveform to a meaningful overview/zoom pair, fix the song-switching state machine bug, add keyboard shortcuts, drag-and-drop from library to playlist, playlist column sorting, and a help popup.

No EQ (requires full audio backend rewrite — deferred).

---

## Approved Layout (Approach A — Integrated DJ Controls Row)

```
┌─ Detail Panel ─────────────────────────────────────────────────────────┐
│  Track Title                                                            │
│  Artist                                                                 │
│  [BPM]  [Key]  [Camelot]  [Energy]                                     │
│                                                                         │
│  WAVEFORM                                                               │
│  ┌─ Overview (40px) — full track minimap ─────────────────────────────┐│
│  └────────────────────────────────────────────────────────────────────┘│
│  ┌─ Main (120px) — ±15s zoom around playhead, cue/loop overlays ─────┐│
│  └────────────────────────────────────────────────────────────────────┘│
│                                                                         │
│  HOT CUES   [●1] [●2] [●3] [●4] [●5] [●6]        (colored buttons)   │
│  LOOP       [A]  [B]  [⟳ LOOP]  |  [½] [1] [2] [4] [8]              │
│                                                                         │
│  ◀◀  ◀  ▶/⏸  ■  ▶▶  ══════════seek══════════  0:00 / 4:32           │
│  VOL ████░░  70%                                                       │
│  128kbps · 44.1kHz · 8.2 MB · 5:12                                    │
│                                                                         │
│  ┌─ PLAYLISTS ───────────────────────────────────────────────────────┐ │
│  │  [My Set ▾]  [🗑]  [📁 Export]                        [+ New]   │ │
│  │  Track ↕   BPM ↕   Key ↕                                        │ │
│  └───────────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────┘
```

Net height change: zero. Overview 50→40px, Main 130→120px; DJ strip adds ~56px; waveform savings absorb it.

---

## Feature 1 — Song Switching Bug Fix

**Root cause:** `_display_track()` calls `audio_player.load()` which internally calls `stop()`, resetting state to STOPPED, but the Play button text remains "⏸ Pause".

**Fix — new `_load_track(file_path)` method** called from `_on_analysis_done`:
1. Captures `was_playing = (audio_player.state == PLAYING)`
2. Clears loop state + hot cue display, loads saved cues for new track
3. Calls `audio_player.load(file_path)`
4. If `was_playing` → `audio_player.play()`, button text = "⏸ Pause"
5. If not → keep stopped, button text = "▶  Play"

This gives auto-play on track switch (natural DJ auditioning behavior) and always-correct button state.

---

## Feature 2 — Waveform Upgrade

**Files:** `ui/waveform_dj.py`

### Overview panel (40px)
- Full-track compressed minimap — unchanged behavior, just shorter
- Shows hot cue tick marks + loop region overlay
- Click-to-seek anywhere

### Main panel (120px)
- **Zoom window:** renders only the slice of bar data corresponding to ±15 seconds around the current playhead position
- When near track start/end the window clamps to the edge
- Higher effective bar resolution (same 400 bars → displayed ~6× larger)
- Shows hot cue tick marks + loop region overlay

### Overlay layers (both panels)
- **Hot cue markers:** thin colored vertical lines at each cue's normalized position; number badge (1–6) at top in the cue's color
- **Loop region:** semi-transparent fill between A and B normalized positions
  - Amber (`rgba(255,185,0,60)`) when set but inactive
  - Green (`rgba(0,220,100,60)`) when active

### API additions to `WaveformDJ` / `_BaseWaveform`
```python
# On _BaseWaveform:
set_hot_cues(cues: list[dict | None])   # list of 6 items: None or {'position': float, 'color': QColor}
set_loop(a: float | None, b: float | None, active: bool)
set_zoom_center(pos: float, window_secs: float, total_secs: float)  # for main only

# On WaveformDJ (forwards to both panels):
update_cues_and_loop(cues, loop_a, loop_b, loop_active)
```

---

## Feature 3 — Hot Cues

**Files:** `ui/main_window.py`, `data/hot_cues.json`

### State
```python
HOT_CUE_COLORS = [
    QColor(255, 107,   0),   # 1 — Orange
    QColor(  0, 200, 255),   # 2 — Cyan
    QColor(  0, 220, 100),   # 3 — Green
    QColor(255,   0, 136),   # 4 — Pink
    QColor(255, 215,   0),   # 5 — Yellow
    QColor(170,  68, 255),   # 6 — Purple
]

self._hot_cues: list[dict | None] = [None] * 6
# Each set cue: {'position': float (0.0–1.0)}
```

### Persistence
`data/hot_cues.json` — keyed by normalized absolute file path string:
```json
{
  "C:/Music/track.mp3": [null, {"position": 0.24}, null, null, null, null]
}
```

Loaded when a track is displayed (`_load_track`). Saved on every set/clear.

### UI — hot cue row (28px tall)
Six `QPushButton` widgets, each 42px wide × 26px tall:
- **Unset:** dark background, gray number, tooltip "Set cue 1"
- **Set:** cue color background (dimmed), bright cue color number, tooltip "Jump to cue 1 · Right-click to clear"
- **Right-click:** context menu with "Clear cue N"

### Behavior
- **Click unset** → set cue at `audio_player.get_position()` → save → update waveform overlays
- **Click set** → `audio_player.seek(cue['position'])` → update waveform
- **Keys `1`–`6`** → same as click
- **Keys `Shift+1`–`Shift+6`** → clear cue

---

## Feature 4 — A-B Loop + Bar Snap

**Files:** `ui/main_window.py`

### State
```python
self._loop_a: float | None = None   # normalized 0.0–1.0
self._loop_b: float | None = None
self._loop_active: bool = False
```

### UI — loop row (28px tall)
```
[A]  [B]  [⟳ LOOP]    |    [½]  [1]  [2]  [4]  [8]
```
- `[A]` / `[B]`: 36px wide, highlight orange when point is set
- `[⟳ LOOP]`: 64px wide, gray when inactive/incomplete, green when active
- Separator `|`: visual divider
- Bar-snap buttons `[½][1][2][4][8]`: 32px wide each, requires BPM + both A set behavior below

**Bar snap behavior:** Sets A at the nearest beat boundary to current position, then B = A + N × seconds_per_bar, where `seconds_per_bar = 4 × 60 / bpm`. If BPM unknown → status bar message "BPM required for bar snap".

### Loop execution
In `_on_position_changed(pos)`:
```python
if self._loop_active and self._loop_a is not None and self._loop_b is not None:
    if pos >= self._loop_b:
        self.audio_player.seek(self._loop_a)
```
Max 50ms overshoot before snap — inaudible.

### Loop cleared on: new track load, `[A]` sets new point while loop active (resets B and deactivates).

### Keyboard
- `I` → set A point
- `O` → set B point
- `L` → toggle loop (only if both A and B set)

---

## Feature 5 — Keyboard Shortcuts

**Files:** `ui/main_window.py` — `keyPressEvent` override on `MainWindow`

| Key | Action | Guard |
|-----|--------|-------|
| `Space` | Play / Pause | not when text input focused |
| `←` | Seek −5s | track loaded |
| `→` | Seek +5s | track loaded |
| `Shift+←` | Seek −30s | track loaded |
| `Shift+→` | Seek +30s | track loaded |
| `I` | Set loop A | track loaded |
| `O` | Set loop B | track loaded |
| `L` | Toggle loop | A and B both set |
| `1`–`6` | Hot cue jump/set | track loaded |
| `Shift+1`–`Shift+6` | Clear hot cue | — |
| `Delete` | Remove from playlist | playlist_table focused |
| `Enter` | Play selected track | library or playlist focused |
| `F1` | Open Help popup | — |

Space guard: check `focusWidget()` is not `QLineEdit` / `QTextEdit`.

---

## Feature 6 — Drag & Drop (Library → Playlist)

**Files:** `ui/main_window.py`

### Source (`track_table`)
```python
track_table.setDragEnabled(True)
track_table.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
```
Override `startDrag` (or use `mimeData`): encode selected row's `UserRole` file path as `text/plain` MIME data.

### Target (`playlist_table`)
```python
playlist_table.setAcceptDrops(True)
playlist_table.setDragDropMode(QAbstractItemView.DragDropMode.DropOnly)
```
Override `dropEvent`: decode MIME `text/plain` → file path → call `_add_to_playlist(fp, current_playlist_name)`.

No reordering within playlist (out of scope per design decision).

---

## Feature 7 — Playlist Sorting

**Files:** `ui/main_window.py` — `_build_playlist_panel()`

Same pattern as track library:
- `playlist_table.setSortingEnabled(True)`
- BPM column: use `NumericTableWidgetItem` with `UserRole = float(bpm)`
- Key column: use `NumericTableWidgetItem` with `UserRole = _camelot_sort_key(camelot)`
- Track name column: standard `QTableWidgetItem` (alphabetical sort is correct)
- Connect `sortIndicatorChanged` → rebuild playlist display (no `_row_map` needed; playlist table always rebuilds from `_playlists[idx]['tracks']`)

---

## Feature 8 — Help Popup

**Files:** `ui/main_window.py` — new `HelpDialog(QDialog)` class

### Trigger
- `[?]` button appended to toolbar (right side, 28×28)
- `F1` key via `keyPressEvent`

### Content (single scrollable dark dialog, ~480×520px)
Four sections separated by horizontal rules:

**1. Keyboard Shortcuts** — monospace two-column table (key | action)

**2. Waveform Colors**
- 🔴 Red — Bass frequencies (kicks, subs, 0–200 Hz)
- 🟠 Amber — Mid frequencies (melody, vocals, 200–4000 Hz)
- 🔵 Cyan — High frequencies (cymbals, air, 4000+ Hz)
- Bar brightness = amplitude (loud = bright, quiet = dark)
- Played bars dimmed to 35% brightness

**3. Energy Score (1–10)**
Full-track RMS (root mean square amplitude) computed across all audio samples in 65,536-frame chunks. Mapped to 1–10 via fixed thresholds. 1 = ambient/near-silent, 10 = peak-clipped intensity.

**4. Key Detection**
Detected using the Krumhansl-Schmuckler key-finding algorithm (pitch class profile matching). Displayed in standard notation (e.g. F# minor) and Camelot wheel notation (e.g. 11A) for harmonic mixing compatibility.

### Style
Non-modal (`setModal(False)`). Dark theme matching app stylesheet. Single `[Close]` button. Remembers window position.

---

## Files Changed

| File | Type | Change |
|------|------|--------|
| `ui/waveform_dj.py` | Modify | Zoom main waveform, cue/loop overlays, resize panels |
| `ui/main_window.py` | Modify | All new features wired in |
| `ui/styles.py` | Modify | Style rules for cue buttons, loop buttons, help dialog |
| `data/hot_cues.json` | New | Created at runtime, persists hot cue positions |

---

## Out of Scope

- Real-time EQ (requires audio backend rewrite)
- Drag reorder within playlist
- BPM tap tempo
- Waveform zoom via scroll wheel
