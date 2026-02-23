# Waveform Filled Polygon Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace bar-style waveform with a seamless filled-polygon style using fast numpy+QImage rendering, fix choppy playback updates, and add drag-to-seek.

**Architecture:** All changes confined to `ui/waveform_dj.py`. Three independent improvements: (1) more data points for smooth outline, (2) atomic position+zoom update to halve repaint calls, (3) replace Python bar loop with fully vectorised numpy array → QImage blit. No other files touched.

**Tech Stack:** Python 3.11, PyQt6, NumPy (existing)

**Shared context:**
- Project root: `C:\Users\ashay\Documents\Claude\dj-track-analyzer\`
- Conda env: `dj-analyzer`
- Run commands with: `conda run -n dj-analyzer` (NOT `conda activate`)
- Run tests: `conda run -n dj-analyzer python -m pytest tests/ -v`
- Import smoke-test: `conda run -n dj-analyzer python -c "from PyQt6.QtWidgets import QApplication; import sys; app = QApplication(sys.argv); from ui.waveform_dj import WaveformDJ; w = WaveformDJ(); print('OK')"`

---

## Task 1: Increase N_BARS to 1200

**Files:**
- Modify: `ui/waveform_dj.py` — `WaveformDataThread` class only
- Modify: `tests/test_analyzer_speed.py`

### Step 1: Write failing test

Add to `tests/test_analyzer_speed.py`:

```python
def test_waveform_n_bars_increased():
    """N_BARS must be >= 1200 for smooth filled waveform outline."""
    from ui.waveform_dj import WaveformDataThread
    assert WaveformDataThread.N_BARS >= 1200
```

Run:
```bash
conda run -n dj-analyzer python -m pytest tests/test_analyzer_speed.py::test_waveform_n_bars_increased -v
```
Expected: **FAIL** — `400 >= 1200` is False.

### Step 2: Change N_BARS

In `ui/waveform_dj.py`, find:
```python
    N_BARS = 400
```
Change to:
```python
    N_BARS = 1200
```

### Step 3: Run test

```bash
conda run -n dj-analyzer python -m pytest tests/test_analyzer_speed.py::test_waveform_n_bars_increased -v
```
Expected: **PASS**.

### Step 4: Full test suite

```bash
conda run -n dj-analyzer python -m pytest tests/ -v
```
Expected: all tests pass.

### Step 5: Commit

```bash
git -C "C:\Users\ashay\Documents\Claude\dj-track-analyzer" add ui/waveform_dj.py tests/test_analyzer_speed.py
git -C "C:\Users\ashay\Documents\Claude\dj-track-analyzer" commit -m "perf: increase N_BARS 400→1200 for smooth filled waveform"
```

---

## Task 2: Atomic position+zoom update + drag-to-seek

**Files:**
- Modify: `ui/waveform_dj.py` — `_BaseWaveform` and `WaveformDJ` classes

**Why:** `set_playback_position()` currently calls `set_position()` then `set_zoom()` on the main panel — each triggers `self.update()` = 2 full repaints per tick. Combining them into one call halves repaint work. `mouseMoveEvent` is missing so drag never emits `position_clicked`.

### Step 1: Add `set_position_and_zoom()` to `_BaseWaveform`

In `ui/waveform_dj.py`, after the existing `set_zoom()` method, add:

```python
    def set_position_and_zoom(self, pos: float, zoom_start: float, zoom_end: float) -> None:
        """Set position and zoom atomically — triggers only ONE repaint."""
        self._position   = max(0.0, min(1.0, pos))
        self._zoom_start = max(0.0, min(1.0, zoom_start))
        self._zoom_end   = max(self._zoom_start + 0.001, min(1.0, zoom_end))
        self.update()
```

### Step 2: Add `mouseMoveEvent` to `_BaseWaveform`

After `mousePressEvent`, add:

```python
    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton and self._data is not None:
            click_frac = max(0.0, min(1.0, event.position().x() / self.width()))
            zoom_width = self._zoom_end - self._zoom_start
            pos = self._zoom_start + click_frac * zoom_width
            self.position_clicked.emit(max(0.0, min(1.0, pos)))
```

### Step 3: Update `WaveformDJ.set_playback_position()` to use atomic update

Replace the existing method:

```python
    def set_playback_position(self, pos: float) -> None:
        """Update playhead on both panels and recompute zoom for main."""
        self.overview.set_position(pos)          # overview: no zoom, one update
        if self._duration > 0:
            window_frac = min(1.0, 30.0 / self._duration)
            half  = window_frac / 2.0
            start = max(0.0, pos - half)
            end   = min(1.0, start + window_frac)
            if end >= 1.0:
                end   = 1.0
                start = max(0.0, end - window_frac)
            self.main.set_position_and_zoom(pos, start, end)   # ONE repaint
        else:
            self.main.set_position(pos)
```

### Step 4: Import check + full tests

```bash
conda run -n dj-analyzer python -c "from PyQt6.QtWidgets import QApplication; import sys; app = QApplication(sys.argv); from ui.waveform_dj import WaveformDJ; w = WaveformDJ(); print('OK')"
conda run -n dj-analyzer python -m pytest tests/ -v
```
Expected: `OK`, all tests pass.

### Step 5: Commit

```bash
git -C "C:\Users\ashay\Documents\Claude\dj-track-analyzer" add ui/waveform_dj.py
git -C "C:\Users\ashay\Documents\Claude\dj-track-analyzer" commit -m "fix: atomic position+zoom update (1 repaint/tick), add drag-to-seek"
```

---

## Task 3: Replace `_draw_bars` with numpy+QImage filled waveform

**Files:**
- Modify: `ui/waveform_dj.py` — `_BaseWaveform` rendering only

**Why:** A Python loop over ~1200 pixel columns calling `fillRect` 1200 times is slow. Instead: compute all pixel colors in numpy (C speed), build a `QImage` from the array, then one `painter.drawImage()` blit — essentially free from Qt's perspective. The result is also seamless (no gaps between columns).

**Color constants needed** (add at module level, after existing constants):
```python
BG_R, BG_G, BG_B = 8, 8, 16        # must match BG_COLOR = QColor(8, 8, 16)
```

**QImage import needed** — add `QImage` to the QtGui import line:
```python
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QPolygonF, QImage
```

### Step 1: Add `QImage` to imports and `BG_R/G/B` constants

In `ui/waveform_dj.py`:

Find:
```python
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QPolygonF
```
Change to:
```python
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QPolygonF, QImage
```

After `PLAYED_DIM = 0.35`, add:
```python
BG_R, BG_G, BG_B = 8, 8, 16        # RGB components of BG_COLOR
```

### Step 2: Add `_draw_waveform()` to `_BaseWaveform`

Add this method after `_draw_bars()` (keep `_draw_bars` for now — we'll swap the call in Step 3):

```python
    def _draw_waveform(self, painter: QPainter, w: int, h: int) -> None:
        """Filled seamless waveform via vectorised numpy → QImage blit."""
        data = self._data
        n    = len(data)

        # ── Select zoom slice ─────────────────────────────────────────
        bar_start = int(self._zoom_start * n)
        bar_end   = max(bar_start + 1, min(n, int(self._zoom_end * n)))
        n_in_view = bar_end - bar_start

        # ── Map every pixel column → data index ──────────────────────
        col_idx = np.round(
            np.linspace(0, n_in_view - 1, w)
        ).astype(np.int32) + bar_start
        col_idx = np.clip(col_idx, 0, n - 1)

        amps = data[col_idx, 0].astype(np.float32)   # (w,)
        bass = data[col_idx, 1].astype(np.float32)
        mid  = data[col_idx, 2].astype(np.float32)
        high = data[col_idx, 3].astype(np.float32)

        # ── Vectorised colour mixing (same formula as _mix_color) ─────
        total      = bass + mid + high + 1e-9
        brightness = 0.25 + 0.75 * amps              # (w,)

        r_f = (255.0 * bass + 255.0 * mid +   0.0 * high) / total * brightness
        g_f = ( 50.0 * bass + 185.0 * mid + 200.0 * high) / total * brightness
        b_f = (  0.0 * bass +   0.0 * mid + 255.0 * high) / total * brightness

        # ── Dim played columns ────────────────────────────────────────
        zoom_width  = max(1e-9, self._zoom_end - self._zoom_start)
        playhead_x  = int(
            max(0.0, (self._position - self._zoom_start) / zoom_width) * w
        )
        played_mask = np.arange(w) < playhead_x      # (w,) bool
        dim         = np.where(played_mask, PLAYED_DIM, 1.0).astype(np.float32)
        r_u8 = np.clip(r_f * dim, 0, 255).astype(np.uint8)
        g_u8 = np.clip(g_f * dim, 0, 255).astype(np.uint8)
        b_u8 = np.clip(b_f * dim, 0, 255).astype(np.uint8)

        # ── Bar heights ───────────────────────────────────────────────
        half_h     = h // 2
        bar_heights = np.maximum(1, (amps * half_h * 0.92).astype(np.int32))
        y_tops      = np.maximum(0, half_h - bar_heights)   # (w,)
        y_bots      = np.minimum(h, half_h + bar_heights)   # (w,)

        # ── Build RGB888 image array ──────────────────────────────────
        img = np.empty((h, w, 3), dtype=np.uint8)
        img[:, :, 0] = BG_R
        img[:, :, 1] = BG_G
        img[:, :, 2] = BG_B

        # Vectorised fill: for each column, paint rows y_top..y_bot
        # Uses broadcasting: y_grid (h,1) compared to y_tops/y_bots (1,w)
        y_grid = np.arange(h, dtype=np.int32)[:, np.newaxis]   # (h, 1)
        mask   = (y_grid >= y_tops[np.newaxis, :]) & (y_grid < y_bots[np.newaxis, :])
        # mask shape: (h, w)

        img[:, :, 0] = np.where(mask, r_u8[np.newaxis, :], BG_R)
        img[:, :, 1] = np.where(mask, g_u8[np.newaxis, :], BG_G)
        img[:, :, 2] = np.where(mask, b_u8[np.newaxis, :], BG_B)

        # ── Blit to painter ───────────────────────────────────────────
        # img must stay alive until drawImage completes (local var keeps ref)
        qimg = QImage(
            img.data, w, h, w * 3, QImage.Format.Format_RGB888
        )
        painter.drawImage(0, 0, qimg)
```

### Step 3: Swap the `paintEvent` call from `_draw_bars` to `_draw_waveform`

In `paintEvent`, find:
```python
        self._draw_bars(painter, w, h)
```
Change to:
```python
        self._draw_waveform(painter, w, h)
```

### Step 4: Import check + full tests

```bash
conda run -n dj-analyzer python -c "from PyQt6.QtWidgets import QApplication; import sys; app = QApplication(sys.argv); from ui.waveform_dj import WaveformDJ; w = WaveformDJ(); print('OK')"
conda run -n dj-analyzer python -m pytest tests/ -v
```
Expected: `OK`, all tests pass.

### Step 5: Commit

```bash
git -C "C:\Users\ashay\Documents\Claude\dj-track-analyzer" add ui/waveform_dj.py
git -C "C:\Users\ashay\Documents\Claude\dj-track-analyzer" commit -m "feat: filled waveform via numpy+QImage blit, seamless freq-coloured columns"
```

---

## Final Verification

```bash
conda run -n dj-analyzer python -m pytest tests/ -v
```
Expected: all tests pass (12 total including the new N_BARS test).

**Manual checks:**
1. Launch: `conda run -n dj-analyzer python main.py`
2. Load a track → both waveforms show seamless filled style (no gaps between columns)
3. Play → main waveform scrolls smoothly without chop
4. Click anywhere on either waveform → seeks correctly
5. **Drag** across waveform → position follows mouse continuously
6. Zoom: near start of track → main waveform still fills full width
7. Hot cue markers and loop overlays still visible on both panels
