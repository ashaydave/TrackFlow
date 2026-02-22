# DJ Track Analyzer — Enhancements Design
**Date:** 2026-02-22
**Status:** Approved

---

## Overview

Four enhancements to the revamped DJ Track Analyzer app:

1. **Sortable columns** — click-to-sort BPM, Key, Energy in the track library
2. **Layout alignment fix** — equalize panel margins/padding in the splitter
3. **Waveform color overhaul** — replace blue/cyan/lightblue with red/amber/cyan
4. **Full-track energy RMS** — compute energy over entire track using chunked I/O
5. **Playlist creator** — create named playlists, add tracks, export to folder

---

## Feature 1: Sortable Columns

### Problem
Track library table is not sortable. Sorting by BPM, Key, or Energy requires manual scanning.

### Design

**Column layout change:**
`Track | BPM | Key | Energy | ✓`
— Replace the existing `★` status column with `Energy` (showing `4` not `4/10`), and add a `✓` column back (28px) for analysis status.
— Energy only fills in after analysis; unanalyzed rows show `--`.

**Sort key storage:**
Use `Qt.ItemDataRole.UserRole` to store numeric sort keys on each item:
- BPM item: `UserRole = float(bpm)` — sorts as float, not string
- Key item: `UserRole = int(camelot_sort_key)` — Camelot wheel order: 1A=1, 1B=2, 2A=3, ... 12B=24
- Energy item: `UserRole = int(energy_level)` — 1–10 direct

**Enabling sort:**
Call `self.track_table.setSortingEnabled(True)` after the table is built.
Use a `SortableTableWidgetItem` subclass (overrides `__lt__` to compare `UserRole` values) or use `Qt.ItemDataRole.UserRole` via a custom sort proxy. Simplest approach: `QTableWidgetItem` with `setData(UserRole, numeric_value)` — Qt's default sort compares `UserRole` data when `setSortingEnabled` is True.

**Camelot sort key mapping:**
```
1A→1, 1B→2, 2A→3, 2B→4, 3A→5, 3B→6, 4A→7, 4B→8,
5A→9, 5B→10, 6A→11, 6B→12, 7A→13, 7B→14, 8A→15, 8B→16,
9A→17, 9B→18, 10A→19, 10B→20, 11A→21, 11B→22, 12A→23, 12B→24
```

**Important:** When `setSortingEnabled(True)` is active, `insertRow` / `setItem` calls trigger re-sorts. Must call `setSortingEnabled(False)` before bulk-populating, then re-enable after.

---

## Feature 2: Layout Alignment Fix

### Problem
The detail panel (right of splitter) overlaps the track library panel by a few pixels due to mismatched margins. Both panels currently have `setContentsMargins(0, 0, 0, 0)` but the `section_header` label in the library panel adds implicit top spacing that the detail panel's title label doesn't match.

### Design
Add `lay.setContentsMargins(8, 0, 0, 0)` (left padding only) to the detail panel's `_build_detail_panel` layout so both panels have the same effective left edge inside the splitter. Also ensure the splitter handle width is consistent (`splitter.setHandleWidth(1)`).

---

## Feature 3: Waveform Color Overhaul

### Problem
Bass/mid/high frequency bands are mapped to deep blue / sky cyan / near-white blue — nearly indistinguishable at a glance.

### Design

Replace color constants in `ui/waveform_dj.py`:

| Band | Range | Old Color | New Color | Hex |
|------|-------|-----------|-----------|-----|
| Bass | 0–200 Hz | `(0, 85, 255)` deep blue | `(255, 50, 0)` **red** | `#FF3200` |
| Mid | 200–4kHz | `(0, 170, 255)` cyan | `(255, 185, 0)` **amber** | `#FFB900` |
| High | 4kHz+ | `(180, 220, 255)` light blue | `(0, 200, 255)` **cyan** | `#00C8FF` |

Effect: drops/kicks glow red, melodic/vocal sections glow amber, cymbal/air sections glow cyan. High contrast between all three bands.

No structural changes — only the three `np.array` color constant values change.

---

## Feature 4: Full-Track Energy RMS

### Problem
`_calculate_energy()` in `audio_analyzer.py` computes RMS only on the first 60 seconds (the `y` array from `_load_audio`). A track with a quiet intro followed by heavy drops will be severely underestimated.

### Design

Add a new private method `_calculate_energy_full(file_path)` that:
1. Uses `soundfile.blocks()` to read the file in chunks of 65536 frames
2. Accumulates `sum_sq += np.sum(chunk_mono ** 2)` and `n_frames += len(chunk_mono)` per chunk
3. Computes `rms = sqrt(sum_sq / n_frames)` at the end
4. Memory: only one chunk (~512KB at 44100 Hz stereo float32) in memory at a time

Call this instead of `_calculate_energy(y)` in `analyze_track()`.

**Performance estimate:** A 5-minute MP3 at 44100 Hz stereo = ~26M frames. Reading in 65536-frame chunks = ~400 iterations. Since we're only reading (not decoding to float32 via soxr), this adds ~0.2–0.4s per track on typical hardware — acceptable given analysis was already ~0.6s.

**Signature change in `analyze_track`:**
```python
'energy': self._calculate_energy_full(file_path),  # was _calculate_energy(y)
```

The returned dict shape stays the same: `{'level': int, 'rms': float, 'description': str}`.

**Note:** The existing `_calculate_energy(y)` can be kept (or removed) — it is no longer called from `analyze_track`.

---

## Feature 5: Playlist Creator

### Location
New collapsible section at the bottom of the detail panel, below the audio meta line. Replaces the current `lay.addStretch()` at the end of `_build_detail_panel`.

### Data Model
Persisted to `data/playlists.json`:
```json
{
  "playlists": [
    {
      "name": "Bollywood Set",
      "tracks": ["/absolute/path/to/song1.mp3", "/absolute/path/to/song2.mp3"]
    }
  ]
}
```

Loaded on app startup, saved on every mutation (create, add, remove, delete playlist).

### UI Layout
```
PLAYLISTS                         [+ New]
[ Bollywood Set           ▼ ]  [🗑]  [📁 Export]
────────────────────────────────────────────
Track Name                    BPM   Key
Aye Khuda Mujhako Bata        69.8  9B
Tu Hi Mera                    112.3 5B
────────────────────────────────────────────
(right-click library track → "Add to Playlist")
```

**Widgets:**
- `PLAYLISTS` section header (`section_header` objectName)
- `[+ New]` `QPushButton` — prompts `QInputDialog.getText()` for playlist name → creates entry
- `QComboBox self.playlist_selector` — lists all playlists; switching updates the track list below
- `[🗑]` delete button — removes selected playlist (no file deletion, just removes from JSON)
- `[📁 Export]` button — opens `QFileDialog.getExistingDirectory()` → creates `<PlaylistName>/` subfolder inside chosen dir → `shutil.copy2()` each track file → status bar progress
- `QTableWidget self.playlist_table` — 3 cols: Track (stretch), BPM (55px fixed), Key (55px fixed); no edit triggers; right-click → "Remove from playlist"

**Adding tracks:**
Extend `_library_context_menu()`:
- Add "Add to Playlist ▶" submenu listing all current playlist names
- Each submenu action calls `_add_to_playlist(file_path, playlist_name)`
- If no playlists exist yet, show "Create a playlist first" (disabled action)

**New methods on MainWindow:**
- `_load_playlists()` — called from `__init__`, loads `data/playlists.json`
- `_save_playlists()` — called after any mutation
- `_new_playlist()` — creates new playlist entry
- `_delete_playlist()` — removes current playlist from data
- `_add_to_playlist(file_path, playlist_name)` — appends track if not already present
- `_remove_from_playlist(file_path)` — removes track from current playlist
- `_refresh_playlist_table()` — rebuilds `playlist_table` from current playlist's tracks
- `_export_playlist()` — copies files to chosen destination folder

### Export Behaviour
1. User clicks Export → `QFileDialog.getExistingDirectory()`
2. Create `<dest>/<PlaylistName>/` subfolder (exist_ok=True)
3. For each track: `shutil.copy2(src, dest_subfolder)`
4. Status bar: `"Exported N tracks to <path>"`
5. Tracks that no longer exist on disk are silently skipped with a warning count

---

## Files Changed

| File | Change |
|------|--------|
| `analyzer/audio_analyzer.py` | Add `_calculate_energy_full()`, change `analyze_track()` to use it |
| `ui/waveform_dj.py` | Change 3 color constants (BASS_COLOR, MID_COLOR, HIGH_COLOR) |
| `ui/main_window.py` | Add Energy column, sortable columns, layout fix, playlist panel + logic |
| `data/playlists.json` | New file (created on first playlist creation) |

---

## Tasks

1. **audio_analyzer.py** — Full-track energy RMS via chunked soundfile reads
2. **waveform_dj.py** — Color constant swap (red/amber/cyan)
3. **main_window.py** — Energy column + sortable columns + layout fix
4. **main_window.py** — Playlist creator panel + persistence + export
