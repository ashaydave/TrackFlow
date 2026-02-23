# UX Polish — Design Doc
**Date:** 2026-02-22
**Scope:** 8 fixes/features identified from screenshot review

---

## 1. Toolbar `?` button clipped

**Problem:** `addStretch()` is placed *after* `btn_help`. The search box has an expanding
size policy (QLineEdit default), so at narrow window widths it shoves `?` past the right
edge of the visible area.

**Fix:** Move `addStretch()` to *before* `search_box`. Remove the trailing stretch.
Layout becomes: `[Load Track] [Load Folder] [Analyze All] [progress] <stretch> [search] [?]`.
Search and `?` are now pinned to the right edge and always fully visible.

---

## 2. Loop row overflow — remove `⟳ LOOP` button

**Problem:** `IN(44) + OUT(44) + ⟳LOOP(76) + sep + 5×bar-snap(34)` ≈ 340 px plus spacing
overflows the available width.

**Fix:** Remove `btn_loop_toggle` from `_build_loop_row()`. The button is redundant now
that OUT auto-starts the loop and a second press stops it. The `L` key shortcut still calls
`_toggle_loop()`. Remove `btn_loop_toggle` references from `_refresh_loop_buttons()` and
`__init__`.

---

## 3. Bar-snap trims OUT (right edge), keeps IN fixed

**Current behaviour:** `_snap_loop(bars)` always recalculates both IN and OUT from the
current playhead position, ignoring any existing IN point.

**New behaviour:**
- If `_loop_a` is already set → keep it fixed; set `_loop_b = _loop_a + bars * secs_per_bar`
  (clamped to track end). Auto-start loop.
- If `_loop_a` is not set → snap both from current playhead position as before.

This lets users set IN manually and then click a bar-snap to size the loop from the right.

---

## 4. Beat/bar grid on waveform

**Feature:** Draw subtle vertical tick lines at each bar boundary (every 4 beats) on the
waveform, so the user can see phrase structure at a glance.

**Implementation:**
- Add `set_beat_grid(bpm: float | None, duration: float)` to `_BaseWaveform`.
- In `paintEvent`, call `_draw_beat_grid(painter, w, h)` between `_draw_waveform` and
  `_draw_loop_region`.
- Beat grid draws semi-transparent white lines (`rgba(255,255,255,30)`) at every beat
  position, and slightly brighter (`rgba(255,255,255,60)`) at bar (every 4th beat) positions.
- Line height: beats at 40% of waveform height (centred), bars at full height.
- `MainWindow._display_track()` calls `self.waveform.set_beat_grid(bpm, duration)` after
  analysis. Clears grid when no track loaded.

---

## 5. Keyboard shortcuts — replace `keyPressEvent` with `QShortcut`

**Problem:** `keyPressEvent` on `MainWindow` only fires when the window itself has focus.
Child widgets (QTableWidget, QSlider, QComboBox) consume key events without propagating them
upward, so Space / arrows / Enter / Delete don't work when a table is focused.

**Fix:** Replace `keyPressEvent` with `QShortcut` objects using
`Qt.ShortcutContext.WindowShortcut` (the default), which fires when any widget *within*
the window has focus.

Shortcuts to register:
| Key | Action |
|-----|--------|
| Space | `_toggle_playback()` (skipped if QLineEdit focused) |
| Left | `_skip(-5)` |
| Shift+Left | `_skip(-30)` |
| Right | `_skip(5)` |
| Shift+Right | `_skip(30)` |
| I | `_set_loop_a()` |
| O | `_set_loop_b()` |
| L | `_toggle_loop()` |
| F1 | `_show_help()` |
| Return / Enter | load selected track (library or playlist) |
| Delete | delete selected playlist tracks |
| 1–6 | hot cue |
| Shift+1–6 | clear cue |

---

## 6. Multi-delete from playlist

**Problem:** `_delete_selected_playlist_track()` reads only `rows[0]`.

**Fix:** Collect all unique selected row indices from `selectedItems()`. Sort descending
(so removing a higher row doesn't shift lower row indices). Call `_remove_from_playlist(fp)`
for each.

---

## 7. Multi-drag from library to playlist

**Problem:** `DraggableLibraryTable.mimeData()` only encodes the first selected item's path.

**Fix:** In `mimeData()`, iterate over all selected rows, collect their `UserRole` file
paths, join with `"\n"`. In `PlaylistDropTable.dropEvent()`, split the text on `"\n"` and
emit `file_dropped` for each non-empty path.

---

## 8. Low-bitrate flag (< 320 kbps) in library

**Feature:** Mark tracks below 320 kbps with a visible but unobtrusive indicator.

**Implementation:** When populating the library table (in `_rebuild_row_map` /
`_populate_track_row`), check the track's `bitrate` field. If `bitrate < 320` (or missing):
- Prepend `⚑ ` to the display text of the track-name cell (col 0).
- Set the cell's foreground color to `QColor("#FF8C00")` (orange).
- Set tooltip: `"Low bitrate: {bitrate} kbps (< 320)"`.

No new column needed; the existing track name cell carries the signal.

---

## Files affected

| File | Changes |
|------|---------|
| `ui/main_window.py` | Items 1–3, 5–8 |
| `ui/waveform_dj.py` | Item 4 (beat grid) |
| `tests/test_analyzer_speed.py` | New tests for bar-snap right-trim, multi-delete, beat-grid |
