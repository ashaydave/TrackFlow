# DJ Track Analyzer Enhancements — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Add sortable columns, fix panel alignment, overhaul waveform colors to red/amber/cyan, compute energy over the full track, and add a playlist creator with copy-to-folder export.

**Architecture:** All changes are surgical edits to 2–3 files. Tasks 1–2 are independent of each other and of tasks 3–5. Tasks 3, 4, 5 all touch `main_window.py` and must be done sequentially (3→4→5) to avoid merge conflicts. Tasks can be executed in order: 1, 2, then 3, 4, 5.

**Tech Stack:** Python 3.11, PyQt6, soundfile (chunked block reader for energy), numpy, shutil (for playlist export)

---

## Shared Context

### Project root
`C:\Users\ashay\Documents\Claude\dj-track-analyzer\`

### Conda environment
`conda activate dj-analyzer`

### Run tests
```bash
cd "C:\Users\ashay\Documents\Claude\dj-track-analyzer"
conda activate dj-analyzer && python -m pytest tests/ -v
```

### Sample track used in existing speed tests
`C:\Users\ashay\Downloads\y2mate.com - LudoWic  MIND PARADE Katana ZERO DLC_320kbps.mp3`
(tests are `@pytest.mark.skipif` if absent — that's fine)

---

## Task 1: Full-Track Energy RMS — `analyzer/audio_analyzer.py`

**Files:**
- Modify: `analyzer/audio_analyzer.py` (lines 59–68, 237–252)
- Modify: `tests/test_analyzer_speed.py` (add one test)

**What & Why:**
Replace `_calculate_energy(y)` (which only sees the first 60s) with `_calculate_energy_full(file_path)` that reads the entire file in 65536-frame chunks using `soundfile.blocks()`. Accumulate sum-of-squares per chunk → compute global RMS at the end. Never more than ~512KB in memory at once.

---

### Step 1: Write failing test

Add to `tests/test_analyzer_speed.py`:

```python
SAMPLE_TRACK = r"C:\Users\ashay\Downloads\y2mate.com - LudoWic  MIND PARADE Katana ZERO DLC_320kbps.mp3"

@pytest.mark.skipif(not Path(SAMPLE_TRACK).exists(), reason="Sample track not found")
def test_full_track_energy_structure():
    """_calculate_energy_full must return correct dict shape and valid level."""
    analyzer = AudioAnalyzer()
    result = analyzer._calculate_energy_full(Path(SAMPLE_TRACK))
    assert isinstance(result, dict)
    assert 'level' in result
    assert 'rms' in result
    assert 'description' in result
    assert 1 <= result['level'] <= 10
    assert result['rms'] > 0
```

### Step 2: Run to verify it fails
```bash
conda activate dj-analyzer && cd "C:\Users\ashay\Documents\Claude\dj-track-analyzer" && python -m pytest tests/test_analyzer_speed.py::test_full_track_energy_structure -v
```
Expected: `FAIL` — `AttributeError: 'AudioAnalyzer' object has no attribute '_calculate_energy_full'`

### Step 3: Add `_calculate_energy_full` to `audio_analyzer.py`

In `analyzer/audio_analyzer.py`, in the `# ── ENERGY` section (after line 252), add this new method:

```python
def _calculate_energy_full(self, file_path):
    """Full-track energy RMS via chunked soundfile reads — no large array in memory."""
    CHUNK = 65536
    try:
        sum_sq = 0.0
        n_frames = 0
        with sf.SoundFile(str(file_path)) as f:
            for block in f.blocks(blocksize=CHUNK, dtype='float32'):
                mono = block.mean(axis=1) if block.ndim == 2 else block
                sum_sq += float(np.sum(mono ** 2))
                n_frames += len(mono)
        if n_frames == 0:
            raise ValueError("Empty audio file")
        avg_rms = float(np.sqrt(sum_sq / n_frames))
        thresholds = [0.05, 0.08, 0.11, 0.14, 0.17, 0.20, 0.23, 0.26, 0.30]
        energy = next(
            (i + 1 for i, t in enumerate(thresholds) if avg_rms < t), 10
        )
        descriptions = {
            1: 'Very Low', 2: 'Low', 3: 'Low-Med', 4: 'Medium', 5: 'Medium',
            6: 'Med-High', 7: 'High', 8: 'High', 9: 'Very High', 10: 'Peak',
        }
        return {'level': energy, 'rms': avg_rms, 'description': descriptions[energy]}
    except Exception as e:
        print(f"Full energy calculation failed: {e}")
        return {'level': 5, 'rms': 0.0, 'description': 'Unknown'}
```

### Step 4: Wire it in `analyze_track()`

In `analyze_track()` (around line 64), change:
```python
# BEFORE:
'energy': self._calculate_energy(y),
# AFTER:
'energy': self._calculate_energy_full(file_path),
```

### Step 5: Run tests
```bash
conda activate dj-analyzer && cd "C:\Users\ashay\Documents\Claude\dj-track-analyzer" && python -m pytest tests/test_analyzer_speed.py -v
```
Expected: ALL PASS (speed test should still pass; full-track read adds ~0.2–0.4s but limit is 3s)

### Step 6: Commit
```bash
cd "C:\Users\ashay\Documents\Claude\dj-track-analyzer"
git add analyzer/audio_analyzer.py tests/test_analyzer_speed.py
git commit -m "feat: compute energy RMS over full track via chunked soundfile reads"
```

---

## Task 2: Waveform Color Overhaul — `ui/waveform_dj.py`

**Files:**
- Modify: `ui/waveform_dj.py` (lines 36–38 only)

**What & Why:**
Replace blue/cyan/near-white with red/amber/cyan so bass, mid, and high bands are visually distinct.

---

### Step 1: Edit the 3 color constants

In `ui/waveform_dj.py`, replace lines 36–38:

```python
# BEFORE:
BASS_COLOR  = np.array([0,   85,  255], dtype=np.float32)
MID_COLOR   = np.array([0,  170,  255], dtype=np.float32)
HIGH_COLOR  = np.array([180, 220, 255], dtype=np.float32)

# AFTER:
BASS_COLOR  = np.array([255,  50,   0], dtype=np.float32)   # red   — kicks/subs
MID_COLOR   = np.array([255, 185,   0], dtype=np.float32)   # amber — melody/vocals
HIGH_COLOR  = np.array([  0, 200, 255], dtype=np.float32)   # cyan  — cymbals/air
```

### Step 2: Import check
```bash
conda activate dj-analyzer && cd "C:\Users\ashay\Documents\Claude\dj-track-analyzer" && python -c "from PyQt6.QtWidgets import QApplication; import sys; app = QApplication(sys.argv); from ui.waveform_dj import WaveformDJ; print('OK')"
```
Expected: `OK`

### Step 3: Commit
```bash
cd "C:\Users\ashay\Documents\Claude\dj-track-analyzer"
git add ui/waveform_dj.py
git commit -m "feat: waveform colors red/amber/cyan (bass/mid/high) for clear band contrast"
```

---

## Task 3: Sortable Columns + Energy Column — `ui/main_window.py`

**Files:**
- Modify: `ui/main_window.py`

**What & Why:**
Add a 5th column for Energy (numeric, 1–10). Store numeric sort keys in `Qt.ItemDataRole.UserRole` via a `NumericTableWidgetItem` subclass so Qt sorts by number not string. Add a helper to map Camelot strings to sort integers. Wrap bulk inserts in `setSortingEnabled(False/True)`. Rebuild `_row_map` when the user sorts.

**Important notes on Qt sorting:**
- `setSortingEnabled(True)` causes Qt to re-sort the table after every `setItem()` call — this shuffles row positions and breaks `_row_map`. Must disable during inserts, re-enable after.
- When the user clicks a column header to sort, `_row_map` (file_path → row index) becomes stale. Fix: connect `sortIndicatorChanged` to `_rebuild_row_map()`.
- `QTableWidgetItem.__lt__` compares text by default. `NumericTableWidgetItem` overrides `__lt__` to compare `UserRole` numeric values.

---

### Step 1: Add `NumericTableWidgetItem` and `_CAMELOT_ORDER` at module level

After the `AUDIO_EXTS` constant (around line 35), add:

```python
# ── Camelot sort order (1A=0, 1B=1, 2A=2, … 12B=23, unknown=24) ──────────────
_CAMELOT_ORDER: dict = {}
for _i in range(1, 13):
    _CAMELOT_ORDER[f"{_i}A"] = (_i - 1) * 2
    _CAMELOT_ORDER[f"{_i}B"] = (_i - 1) * 2 + 1


def _camelot_sort_key(camelot: str) -> int:
    """Return integer sort key for a Camelot string (1A–12B). Unknown → 24."""
    return _CAMELOT_ORDER.get(camelot, 24)


class NumericTableWidgetItem(QTableWidgetItem):
    """QTableWidgetItem whose sort order is its UserRole numeric value."""
    def __lt__(self, other: QTableWidgetItem) -> bool:
        self_val  = self.data(Qt.ItemDataRole.UserRole)
        other_val = other.data(Qt.ItemDataRole.UserRole)
        if self_val is None:
            return True
        if other_val is None:
            return False
        try:
            return float(self_val) < float(other_val)
        except (TypeError, ValueError):
            return self.text() < other.text()
```

### Step 2: Update `_build_library_panel()` — 5 columns + sorting

Replace the column setup block inside `_build_library_panel()`:

```python
# BEFORE (4 columns):
self.track_table.setColumnCount(4)
self.track_table.setHorizontalHeaderLabels(["Track", "BPM", "Key", "\u2605"])
...
hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
self.track_table.setColumnWidth(1, 58)
self.track_table.setColumnWidth(2, 64)
self.track_table.setColumnWidth(3, 28)

# AFTER (5 columns):
self.track_table.setColumnCount(5)
self.track_table.setHorizontalHeaderLabels(["Track", "BPM", "Key", "Nrg", "\u2713"])
...
hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
hdr.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
self.track_table.setColumnWidth(1, 58)
self.track_table.setColumnWidth(2, 64)
self.track_table.setColumnWidth(3, 42)
self.track_table.setColumnWidth(4, 22)
```

After the `itemSelectionChanged` and `customContextMenuRequested` connections, add:
```python
self.track_table.setSortingEnabled(True)
self.track_table.horizontalHeader().sortIndicatorChanged.connect(
    lambda *_: self._rebuild_row_map()
)
```

### Step 3: Add `_rebuild_row_map()` method

Add this method anywhere in the class (good place: right after `_highlight_row`):

```python
def _rebuild_row_map(self) -> None:
    """Rebuild _row_map after table sort — keeps file_path→row_index accurate."""
    self._row_map = {}
    for row in range(self.track_table.rowCount()):
        item = self.track_table.item(row, 0)
        if item:
            fp = item.data(Qt.ItemDataRole.UserRole)
            if fp:
                self._row_map[fp] = row
```

### Step 4: Update `_set_row()` — add Energy col, update ✓ col

```python
def _set_row(self, row: int, file_path: str):
    name = Path(file_path).stem
    item = QTableWidgetItem(name)
    item.setData(Qt.ItemDataRole.UserRole, file_path)
    item.setToolTip(file_path)
    self.track_table.setItem(row, 0, item)
    self.track_table.setItem(row, 1, QTableWidgetItem("--"))
    self.track_table.setItem(row, 2, QTableWidgetItem("--"))
    self.track_table.setItem(row, 3, QTableWidgetItem("--"))   # Energy
    self.track_table.setItem(row, 4, QTableWidgetItem("\u00b7"))  # ·  (pending)
```

### Step 5: Update `_update_row_from_results()` — fill Energy + use NumericTableWidgetItem

```python
def _update_row_from_results(self, file_path: str, results: dict):
    row = self._row_map.get(file_path)
    if row is None:
        return
    bpm    = results.get('bpm')
    key    = results.get('key', {})
    energy = results.get('energy', {})
    camelot = key.get('camelot', '--')
    energy_level = energy.get('level')

    # BPM — numeric sort
    bpm_item = NumericTableWidgetItem(str(bpm) if bpm else "--")
    bpm_item.setData(Qt.ItemDataRole.UserRole, float(bpm) if bpm else 999.0)
    self.track_table.setItem(row, 1, bpm_item)

    # Key — Camelot sort order
    key_item = NumericTableWidgetItem(camelot)
    key_item.setData(Qt.ItemDataRole.UserRole, _camelot_sort_key(camelot))
    self.track_table.setItem(row, 2, key_item)

    # Energy — numeric sort
    nrg_item = NumericTableWidgetItem(str(energy_level) if energy_level else "--")
    nrg_item.setData(Qt.ItemDataRole.UserRole, int(energy_level) if energy_level else 0)
    self.track_table.setItem(row, 3, nrg_item)

    # Status ✓
    self.track_table.setItem(row, 4, QTableWidgetItem("\u2713"))
    self._highlight_row(row, ROW_DONE)
```

### Step 6: Update `_highlight_row()` — now 5 columns

Update the range to `self.track_table.columnCount()` (it already does this — verify no hardcoded `4`).
It currently says `for col in range(self.track_table.columnCount())` — good, no change needed.

### Step 7: Disable sorting during bulk inserts in `_load_folder()`

Wrap the row-insertion loop:
```python
# BEFORE:
self.track_table.setRowCount(0)
self.track_table.setRowCount(len(files))
for i, fp in enumerate(files):
    self._set_row(i, fp)
    ...

# AFTER:
self.track_table.setSortingEnabled(False)
self.track_table.setRowCount(0)
self.track_table.setRowCount(len(files))
for i, fp in enumerate(files):
    self._set_row(i, fp)
    self._row_map[fp] = i
    if is_cached(Path(fp)):
        cached = load_cached(Path(fp))
        if cached:
            self._update_row_from_results(fp, cached)
self.track_table.setSortingEnabled(True)
```

### Step 8: Disable sorting during single-track insert in `_load_single_track()`

```python
# Wrap the insertRow block:
self.track_table.setSortingEnabled(False)
row = self.track_table.rowCount()
self.track_table.insertRow(row)
self._set_row(row, path)
self._row_map[path] = row
self.library_files.append(path)
self.track_count_label.setText(f"{len(self.library_files)} tracks")
self.track_table.setSortingEnabled(True)
```

### Step 9: Import check
```bash
conda activate dj-analyzer && cd "C:\Users\ashay\Documents\Claude\dj-track-analyzer" && python -c "from PyQt6.QtWidgets import QApplication; import sys; app = QApplication(sys.argv); from ui.main_window import MainWindow; print('OK')"
```

### Step 10: Commit
```bash
cd "C:\Users\ashay\Documents\Claude\dj-track-analyzer"
git add ui/main_window.py
git commit -m "feat: sortable BPM/Key/Energy columns with correct numeric sort order"
```

---

## Task 4: Layout Alignment Fix — `ui/main_window.py`

**Files:**
- Modify: `ui/main_window.py`

**What & Why:**
The detail panel (right side of splitter) has no left margin, so its content starts immediately at the splitter handle — making it look like it's overlapping the library. Adding left padding and tightening the splitter handle width fixes the visual gap.

---

### Step 1: Fix detail panel left margin

In `_build_detail_panel()`, change:
```python
# BEFORE:
lay.setContentsMargins(0, 0, 0, 0)

# AFTER:
lay.setContentsMargins(10, 0, 4, 0)
```

### Step 2: Set splitter handle width

In `_init_ui()`, after `splitter = QSplitter(Qt.Orientation.Horizontal)`, add:
```python
splitter.setHandleWidth(1)
```

### Step 3: Import check
```bash
conda activate dj-analyzer && cd "C:\Users\ashay\Documents\Claude\dj-track-analyzer" && python -c "from PyQt6.QtWidgets import QApplication; import sys; app = QApplication(sys.argv); from ui.main_window import MainWindow; print('OK')"
```

### Step 4: Commit
```bash
cd "C:\Users\ashay\Documents\Claude\dj-track-analyzer"
git add ui/main_window.py
git commit -m "fix: add left margin to detail panel, tighten splitter handle"
```

---

## Task 5: Playlist Creator — `ui/main_window.py`

**Files:**
- Modify: `ui/main_window.py`

**What & Why:**
Add a playlist section below the audio meta line. Playlists are named collections of track paths stored in `data/playlists.json`. The user adds tracks via right-click context menu, switches playlists via dropdown, and exports by copying files to a chosen folder.

---

### Step 1: Add imports at the top of `main_window.py`

Add to the existing import block:
```python
import json
import shutil
from PyQt6.QtWidgets import (
    ...,   # existing
    QComboBox, QInputDialog,
)
```

(Add `QComboBox` and `QInputDialog` to the existing `from PyQt6.QtWidgets import (...)` block.)

### Step 2: Add `PLAYLISTS_FILE` constant (module level, after `AUDIO_EXTS`)

```python
PLAYLISTS_FILE = Path(__file__).parent.parent / 'data' / 'playlists.json'
```

### Step 3: Add playlist state to `__init__`

After `self._seek_dragging = False`, add:
```python
self._playlists: list = []   # list of {"name": str, "tracks": [str]}
```

After `self._init_ui()` and `self.setStyleSheet(STYLESHEET)`, add:
```python
self._load_playlists()
```

### Step 4: Add `_load_playlists()` and `_save_playlists()`

```python
def _load_playlists(self) -> None:
    """Load playlists from JSON on startup."""
    try:
        if PLAYLISTS_FILE.exists():
            with open(PLAYLISTS_FILE) as f:
                data = json.load(f)
            self._playlists = data.get('playlists', [])
    except Exception as e:
        print(f"Could not load playlists: {e}")
        self._playlists = []
    # Populate the selector
    self.playlist_selector.blockSignals(True)
    self.playlist_selector.clear()
    for pl in self._playlists:
        self.playlist_selector.addItem(pl['name'])
    self.playlist_selector.blockSignals(False)
    self._refresh_playlist_table()

def _save_playlists(self) -> None:
    """Persist playlists to JSON."""
    try:
        PLAYLISTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(PLAYLISTS_FILE, 'w') as f:
            json.dump({'playlists': self._playlists}, f, indent=2)
    except Exception as e:
        print(f"Could not save playlists: {e}")
```

### Step 5: Add `_build_playlist_panel()` method

```python
def _build_playlist_panel(self) -> QWidget:
    panel = QWidget()
    lay = QVBoxLayout(panel)
    lay.setContentsMargins(0, 4, 0, 0)
    lay.setSpacing(4)

    # Header row
    header_row = QHBoxLayout()
    header_lbl = QLabel("PLAYLISTS")
    header_lbl.setObjectName("section_header")
    header_row.addWidget(header_lbl)
    header_row.addStretch()
    btn_new = QPushButton("+ New")
    btn_new.setFixedHeight(24)
    btn_new.clicked.connect(self._new_playlist)
    header_row.addWidget(btn_new)
    lay.addLayout(header_row)

    # Selector + action row
    ctrl_row = QHBoxLayout()
    self.playlist_selector = QComboBox()
    self.playlist_selector.setMinimumWidth(160)
    ctrl_row.addWidget(self.playlist_selector, stretch=1)

    btn_delete = QPushButton("\U0001f5d1")   # 🗑
    btn_delete.setFixedSize(28, 28)
    btn_delete.setToolTip("Delete playlist")
    btn_delete.clicked.connect(self._delete_playlist)
    ctrl_row.addWidget(btn_delete)

    btn_export = QPushButton("\U0001f4c1 Export")   # 📁
    btn_export.setFixedHeight(28)
    btn_export.setToolTip("Copy all tracks to a folder")
    btn_export.clicked.connect(self._export_playlist)
    ctrl_row.addWidget(btn_export)

    lay.addLayout(ctrl_row)

    # Playlist track table
    self.playlist_table = QTableWidget()
    self.playlist_table.setColumnCount(3)
    self.playlist_table.setHorizontalHeaderLabels(["Track", "BPM", "Key"])
    self.playlist_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    self.playlist_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    self.playlist_table.verticalHeader().setVisible(False)
    self.playlist_table.setShowGrid(False)
    self.playlist_table.setAlternatingRowColors(True)
    self.playlist_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    self.playlist_table.customContextMenuRequested.connect(self._playlist_context_menu)
    self.playlist_table.verticalHeader().setDefaultSectionSize(22)

    ph = self.playlist_table.horizontalHeader()
    ph.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
    ph.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
    ph.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
    self.playlist_table.setColumnWidth(1, 55)
    self.playlist_table.setColumnWidth(2, 55)
    self.playlist_table.setMaximumHeight(180)

    lay.addWidget(self.playlist_table)

    # Wire selector change
    self.playlist_selector.currentIndexChanged.connect(self._on_playlist_changed)

    return panel
```

### Step 6: Wire `_build_playlist_panel()` into `_build_detail_panel()`

In `_build_detail_panel()`, replace the final `lay.addStretch()` with:
```python
lay.addWidget(self._build_playlist_panel())
```

### Step 7: Add all playlist methods

```python
def _new_playlist(self) -> None:
    name, ok = QInputDialog.getText(self, "New Playlist", "Playlist name:")
    if not ok or not name.strip():
        return
    name = name.strip()
    if any(p['name'] == name for p in self._playlists):
        self._status.showMessage(f"Playlist '{name}' already exists.")
        return
    self._playlists.append({'name': name, 'tracks': []})
    self._save_playlists()
    self.playlist_selector.addItem(name)
    self.playlist_selector.setCurrentText(name)
    self._status.showMessage(f"Created playlist: {name}")

def _delete_playlist(self) -> None:
    idx = self.playlist_selector.currentIndex()
    if idx < 0:
        return
    name = self._playlists[idx]['name']
    self._playlists.pop(idx)
    self._save_playlists()
    self.playlist_selector.removeItem(idx)
    self._refresh_playlist_table()
    self._status.showMessage(f"Deleted playlist: {name}")

def _add_to_playlist(self, file_path: str, playlist_name: str) -> None:
    for pl in self._playlists:
        if pl['name'] == playlist_name:
            if file_path not in pl['tracks']:
                pl['tracks'].append(file_path)
                self._save_playlists()
                if self.playlist_selector.currentText() == playlist_name:
                    self._refresh_playlist_table()
                self._status.showMessage(
                    f"Added '{Path(file_path).stem}' to {playlist_name}"
                )
            else:
                self._status.showMessage("Track already in playlist.")
            return

def _remove_from_playlist(self, file_path: str) -> None:
    idx = self.playlist_selector.currentIndex()
    if idx < 0:
        return
    pl = self._playlists[idx]
    if file_path in pl['tracks']:
        pl['tracks'].remove(file_path)
        self._save_playlists()
        self._refresh_playlist_table()

def _on_playlist_changed(self, index: int) -> None:
    self._refresh_playlist_table()

def _refresh_playlist_table(self) -> None:
    self.playlist_table.setRowCount(0)
    idx = self.playlist_selector.currentIndex()
    if idx < 0 or idx >= len(self._playlists):
        return
    pl = self._playlists[idx]
    from analyzer.batch_analyzer import load_cached
    for fp in pl['tracks']:
        row = self.playlist_table.rowCount()
        self.playlist_table.insertRow(row)
        name_item = QTableWidgetItem(Path(fp).stem)
        name_item.setData(Qt.ItemDataRole.UserRole, fp)
        name_item.setToolTip(fp)
        self.playlist_table.setItem(row, 0, name_item)
        # Fill BPM/Key from cache if available
        cached = load_cached(Path(fp))
        if cached:
            bpm = cached.get('bpm')
            camelot = cached.get('key', {}).get('camelot', '--')
            self.playlist_table.setItem(row, 1, QTableWidgetItem(str(bpm) if bpm else "--"))
            self.playlist_table.setItem(row, 2, QTableWidgetItem(camelot))
        else:
            self.playlist_table.setItem(row, 1, QTableWidgetItem("--"))
            self.playlist_table.setItem(row, 2, QTableWidgetItem("--"))

def _playlist_context_menu(self, pos: QPoint) -> None:
    item = self.playlist_table.itemAt(pos)
    if not item:
        return
    row = item.row()
    fp_item = self.playlist_table.item(row, 0)
    if not fp_item:
        return
    fp = fp_item.data(Qt.ItemDataRole.UserRole)
    menu = QMenu(self)
    action_remove = menu.addAction("Remove from playlist")
    action = menu.exec(self.playlist_table.viewport().mapToGlobal(pos))
    if action == action_remove and fp:
        self._remove_from_playlist(fp)

def _export_playlist(self) -> None:
    idx = self.playlist_selector.currentIndex()
    if idx < 0:
        return
    pl = self._playlists[idx]
    if not pl['tracks']:
        self._status.showMessage("Playlist is empty — nothing to export.")
        return
    dest = QFileDialog.getExistingDirectory(self, "Select Export Destination")
    if not dest:
        return
    out_dir = Path(dest) / pl['name']
    out_dir.mkdir(parents=True, exist_ok=True)
    copied = skipped = 0
    for track_path in pl['tracks']:
        src = Path(track_path)
        if src.exists():
            shutil.copy2(src, out_dir / src.name)
            copied += 1
        else:
            skipped += 1
    msg = f"Exported {copied} tracks to {out_dir}"
    if skipped:
        msg += f" ({skipped} files not found on disk)"
    self._status.showMessage(msg)
```

### Step 8: Update `_library_context_menu()` — add "Add to Playlist" submenu

Replace the existing `_library_context_menu` with:

```python
def _library_context_menu(self, pos: QPoint):
    item = self.track_table.itemAt(pos)
    if not item:
        return
    row = item.row()
    fp_item = self.track_table.item(row, 0)
    if not fp_item:
        return
    fp = fp_item.data(Qt.ItemDataRole.UserRole)

    menu = QMenu(self)
    action_analyze = menu.addAction("Re-analyze")
    action_reveal  = menu.addAction("Open in Explorer")
    menu.addSeparator()

    # "Add to Playlist" submenu
    playlist_menu = menu.addMenu("Add to Playlist")
    if self._playlists:
        for pl in self._playlists:
            a = playlist_menu.addAction(pl['name'])
            a.setData(pl['name'])
    else:
        no_pl = playlist_menu.addAction("No playlists — create one first")
        no_pl.setEnabled(False)

    action = menu.exec(self.track_table.viewport().mapToGlobal(pos))
    if action == action_analyze and fp:
        self._start_analysis(fp)
    elif action == action_reveal and fp:
        os.startfile(str(Path(fp).parent))
    elif action and action.data() and fp:
        # "Add to Playlist" submenu action
        self._add_to_playlist(fp, action.data())
```

### Step 9: Import check
```bash
conda activate dj-analyzer && cd "C:\Users\ashay\Documents\Claude\dj-track-analyzer" && python -c "from PyQt6.QtWidgets import QApplication; import sys; app = QApplication(sys.argv); from ui.main_window import MainWindow; print('OK')"
```

### Step 10: Run all tests
```bash
conda activate dj-analyzer && cd "C:\Users\ashay\Documents\Claude\dj-track-analyzer" && python -m pytest tests/ -v
```
Expected: all pass / known skips

### Step 11: Commit
```bash
cd "C:\Users\ashay\Documents\Claude\dj-track-analyzer"
git add ui/main_window.py data/
git commit -m "feat: playlist creator — create/delete/export playlists, add via context menu"
```

---

## Final Verification

After all 5 tasks:

```bash
conda activate dj-analyzer && cd "C:\Users\ashay\Documents\Claude\dj-track-analyzer" && python -m pytest tests/ -v
```

Manual smoke test:
1. Launch: `python main.py`
2. Load folder → verify 5-column table with Track/BPM/Key/Nrg/✓
3. Click BPM header → verify numeric sort (99.4 < 143.6, not string sort)
4. Click Key header → verify Camelot order (1A before 2A before 12B)
5. Run "Analyze All" → verify Nrg column fills in as each track completes
6. Click Energy header → verify ascending/descending numeric sort
7. Waveform: load a track with heavy bass drop → verify bars glow red at drop
8. Create a playlist → add 3 tracks via right-click → verify they appear
9. Export playlist → verify files are copied to `<dest>/<PlaylistName>/`
10. Restart app → verify playlists are still there (JSON persistence)

```bash
git log --oneline -8
```
