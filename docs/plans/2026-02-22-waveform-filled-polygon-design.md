# Waveform Redesign — Filled Polygon Style

**Date:** 2026-02-22
**Status:** Approved
**Scope:** `ui/waveform_dj.py` only

---

## Goal

Replace the current bar/histogram waveform with a clean, seamless filled-polygon style matching professional DJ software (red=bass, amber=mid, cyan=high, mirrored shape). Fix choppy playback updates and add drag-to-seek support.

---

## Issues Being Fixed

### 1. Choppy playback scroll
`set_playback_position()` calls `set_position()` then `set_zoom()` separately — each calls `self.update()`, causing 2 full repaints per position tick. Fix: add `set_position_and_zoom(pos, zoom_start, zoom_end)` on `_BaseWaveform` that sets both atomically and calls `update()` once.

### 2. Can't drag playhead
`mousePressEvent` emits `position_clicked` on click, but `mouseMoveEvent` is missing. Fix: add `mouseMoveEvent` that emits `position_clicked` whenever the left button is held, enabling drag-to-seek.

### 3. Bar-style waveform looks blocky
Replace 2px+gap bars with 1px seamless filled columns. Use numpy vectorised rendering (build full `QImage` via array ops, then one `painter.drawImage()` call) for both speed and visual quality.

---

## Design

### Data layer (`WaveformDataThread`)
- `N_BARS`: 400 → **1200** (3× resolution for smooth shape outline)
- Data format unchanged: `(N, 4)` float32 `[amp, bass, mid, high]`
- Background thread unchanged — user sees no delay

### Rendering (`_BaseWaveform._draw_bars` → `_draw_waveform`)

**Algorithm (numpy fast path):**
1. Select in-view slice `data[bar_start:bar_end]` using zoom fractions
2. For each pixel column `x` in `[0, w)`:
   - Map → bar index via linear interp (vectorised with `np.interp`)
   - Compute `amp`, color channel weights
   - Compute `bar_h = max(1, int(amp * half_h * 0.92))`
   - Dim played columns (left of playhead) by ×0.35
3. Build `QImage(w, h, Format_RGB32)` via `np.frombuffer` + fill column strips
4. One `painter.drawImage(0, 0, qimage)` call

**Why QImage:** builds entire frame in numpy (C speed), then one GPU-accelerated blit — avoids 1200 individual `fillRect` Python calls.

### Atomic position+zoom update
Add to `_BaseWaveform`:
```python
def set_position_and_zoom(self, pos: float, zoom_start: float, zoom_end: float) -> None:
    self._position = max(0.0, min(1.0, pos))
    self._zoom_start = max(0.0, min(1.0, zoom_start))
    self._zoom_end   = max(self._zoom_start + 0.001, min(1.0, zoom_end))
    self.update()  # ONE repaint
```

Update `WaveformDJ.set_playback_position()` to call this for `main`, and plain `set_position()` for `overview` (no zoom needed there).

### Drag-to-seek
Add to `_BaseWaveform`:
```python
def mouseMoveEvent(self, event):
    if event.buttons() & Qt.MouseButton.LeftButton and self._data is not None:
        click_frac = max(0.0, min(1.0, event.position().x() / self.width()))
        zoom_width = self._zoom_end - self._zoom_start
        pos = self._zoom_start + click_frac * zoom_width
        self.position_clicked.emit(max(0.0, min(1.0, pos)))
```

---

## What Stays the Same
- `_draw_loop_region`, `_draw_cue_markers`, `_draw_playhead` — unchanged
- `WaveformDJ` public API — unchanged
- `main_window.py` — unchanged
- All other files — unchanged

---

## Tests
- Update `test_waveform_zoom_bounds_clamping` — logic unchanged, still passes
- Add `test_waveform_n_bars_increased` — assert `WaveformDataThread.N_BARS >= 1200`
