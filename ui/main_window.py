"""
DJ Track Analyzer - Main Window UI
PyQt6-based desktop application for browsing and analyzing DJ tracks.
"""

import os
import sys
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QPushButton, QLabel, QLineEdit, QTableWidget, QTableWidgetItem,
    QFileDialog, QHeaderView, QProgressBar, QStatusBar, QSlider,
    QMenu, QApplication,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QPoint
from PyQt6.QtGui import QColor, QAction

sys.path.insert(0, str(Path(__file__).parent.parent))
from analyzer.audio_analyzer import AudioAnalyzer
from analyzer.batch_analyzer import BatchAnalyzer, is_cached, load_cached
from ui.waveform_dj import WaveformDJ
from ui.audio_player import AudioPlayer, PlayerState
from ui.styles import STYLESHEET


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ROW_PENDING   = QColor(30,  30,  45)
ROW_ANALYZING = QColor(10,  30,  70)
ROW_DONE      = QColor(15,  15,  28)

AUDIO_EXTS = {'.mp3', '.wav', '.flac', '.m4a', '.ogg', '.aiff', '.aif'}

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


# ---------------------------------------------------------------------------
# Background threads
# ---------------------------------------------------------------------------

class AnalysisThread(QThread):
    """Single-track analysis thread."""
    finished = pyqtSignal(dict)
    error    = pyqtSignal(str)

    def __init__(self, file_path: str):
        super().__init__()
        self.file_path = file_path
        self._analyzer = AudioAnalyzer()

    def run(self):
        try:
            self.finished.emit(self._analyzer.analyze_track(self.file_path))
        except Exception as e:
            self.error.emit(str(e))


class BatchThread(QThread):
    """Wraps BatchAnalyzer and runs it off the main thread."""
    track_done = pyqtSignal(str, dict, int, int)
    all_done   = pyqtSignal(int, int)
    error      = pyqtSignal(str, str)
    progress   = pyqtSignal(int, int)

    def __init__(self, file_paths: list):
        super().__init__()
        self._paths = file_paths
        self._batch = BatchAnalyzer()
        # Forward all signals
        self._batch.track_done.connect(self.track_done)
        self._batch.all_done.connect(self.all_done)
        self._batch.error.connect(self.error)
        self._batch.progress.connect(self.progress)

    def run(self):
        self._batch.analyze_all(self._paths)

    def cancel(self):
        self._batch.cancel()


# ---------------------------------------------------------------------------
# Main Window
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.current_track: dict | None = None
        self.library_files: list = []
        self.analysis_thread: AnalysisThread | None = None
        self.batch_thread: BatchThread | None = None
        self._row_map: dict = {}   # file_path (str) -> table row index (int)
        self._seek_dragging = False

        self.audio_player = AudioPlayer()
        self.audio_player.position_changed.connect(self._on_position_changed)
        self.audio_player.playback_finished.connect(self._on_playback_finished)
        self.audio_player.set_volume(0.7)

        self.setWindowTitle("DJ Track Analyzer")
        self.setMinimumSize(1200, 720)
        self.resize(1400, 820)

        self._init_ui()
        self.setStyleSheet(STYLESHEET)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        root.addLayout(self._build_toolbar())

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        splitter.addWidget(self._build_library_panel())
        splitter.addWidget(self._build_detail_panel())
        splitter.setSizes([340, 1060])

        root.addWidget(splitter)

        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status.showMessage("Ready — load a track or folder to begin")

    def _build_toolbar(self) -> QHBoxLayout:
        lay = QHBoxLayout()

        self.btn_load_track = QPushButton("Load Track")
        self.btn_load_track.setFixedHeight(32)
        lay.addWidget(self.btn_load_track)

        self.btn_load_folder = QPushButton("Load Folder")
        self.btn_load_folder.setFixedHeight(32)
        lay.addWidget(self.btn_load_folder)

        self.btn_analyze_all = QPushButton("Analyze All")
        self.btn_analyze_all.setObjectName("btn_primary")
        self.btn_analyze_all.setFixedHeight(32)
        self.btn_analyze_all.setEnabled(False)
        lay.addWidget(self.btn_analyze_all)

        self.batch_progress = QProgressBar()
        self.batch_progress.setFixedHeight(8)
        self.batch_progress.setVisible(False)
        lay.addWidget(self.batch_progress)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search tracks\u2026")
        self.search_box.setFixedHeight(32)
        self.search_box.setMaximumWidth(280)
        lay.addWidget(self.search_box)

        lay.addStretch()

        # Connections
        self.btn_load_track.clicked.connect(self._load_single_track)
        self.btn_load_folder.clicked.connect(self._load_folder)
        self.btn_analyze_all.clicked.connect(self._analyze_all)
        self.search_box.textChanged.connect(self._filter_tracks)

        return lay

    def _build_library_panel(self) -> QWidget:
        panel = QWidget()
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        header = QLabel("TRACK LIBRARY")
        header.setObjectName("section_header")
        lay.addWidget(header)

        self.track_table = QTableWidget()
        self.track_table.setColumnCount(5)
        self.track_table.setHorizontalHeaderLabels(["Track", "BPM", "Key", "Nrg", "\u2713"])
        self.track_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.track_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.track_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.track_table.setAlternatingRowColors(True)
        self.track_table.verticalHeader().setVisible(False)
        self.track_table.setShowGrid(False)
        self.track_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        hdr = self.track_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.track_table.setColumnWidth(1, 58)
        self.track_table.setColumnWidth(2, 64)
        self.track_table.setColumnWidth(3, 42)
        self.track_table.setColumnWidth(4, 22)

        self.track_table.verticalHeader().setDefaultSectionSize(22)

        self.track_table.itemSelectionChanged.connect(self._on_track_selected)
        self.track_table.customContextMenuRequested.connect(self._library_context_menu)
        self.track_table.setSortingEnabled(True)
        self.track_table.horizontalHeader().sortIndicatorChanged.connect(
            lambda *_: self._rebuild_row_map()
        )

        lay.addWidget(self.track_table)

        self.track_count_label = QLabel("0 tracks")
        self.track_count_label.setObjectName("meta_text")
        lay.addWidget(self.track_count_label)

        return panel

    def _build_detail_panel(self) -> QWidget:
        panel = QWidget()
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(10, 0, 4, 0)
        lay.setSpacing(6)

        # Track header
        self.lbl_title = QLabel("No track selected")
        self.lbl_title.setObjectName("track_title")
        lay.addWidget(self.lbl_title)

        self.lbl_artist = QLabel("")
        self.lbl_artist.setObjectName("track_artist")
        lay.addWidget(self.lbl_artist)

        # Info cards row
        cards_row = QHBoxLayout()
        cards_row.setSpacing(8)

        self.card_bpm     = self._make_card("BPM",     "--", "info_value_large")
        self.card_key     = self._make_card("Key",     "--", "info_value_medium")
        self.card_camelot = self._make_card("Camelot", "--", "camelot_value")
        self.card_energy  = self._make_card("Energy",  "--", "info_value_medium")

        cards_row.addWidget(self.card_bpm[0])
        cards_row.addWidget(self.card_key[0])
        cards_row.addWidget(self.card_camelot[0])
        cards_row.addWidget(self.card_energy[0])

        lay.addLayout(cards_row)

        # Waveform section
        waveform_header = QLabel("WAVEFORM")
        waveform_header.setObjectName("section_header")
        lay.addWidget(waveform_header)

        self.waveform = WaveformDJ()
        self.waveform.position_clicked.connect(self._on_waveform_clicked)
        lay.addWidget(self.waveform)

        # Player controls row
        controls_row = QHBoxLayout()
        controls_row.setSpacing(8)

        self.btn_play = QPushButton("\u25b6  Play")
        self.btn_play.setObjectName("btn_play")
        self.btn_play.setFixedHeight(36)
        self.btn_play.setFixedWidth(90)
        self.btn_play.setEnabled(False)
        controls_row.addWidget(self.btn_play)

        self.btn_stop = QPushButton("\u23f9")
        self.btn_stop.setFixedSize(36, 36)
        self.btn_stop.setEnabled(False)
        controls_row.addWidget(self.btn_stop)

        self.btn_skip_back = QPushButton("\u25c4\u25c4")
        self.btn_skip_back.setFixedSize(40, 36)
        self.btn_skip_back.setEnabled(False)
        controls_row.addWidget(self.btn_skip_back)

        self.btn_skip_fwd = QPushButton("\u25ba\u25ba")
        self.btn_skip_fwd.setFixedSize(40, 36)
        self.btn_skip_fwd.setEnabled(False)
        controls_row.addWidget(self.btn_skip_fwd)

        self.seek_slider = QSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setRange(0, 1000)
        self.seek_slider.setEnabled(False)
        controls_row.addWidget(self.seek_slider, stretch=1)

        self.lbl_time = QLabel("0:00 / 0:00")
        self.lbl_time.setObjectName("time_display")
        controls_row.addWidget(self.lbl_time)

        lay.addLayout(controls_row)

        # Connect player controls
        self.btn_play.clicked.connect(self._toggle_playback)
        self.btn_stop.clicked.connect(self._stop_playback)
        self.btn_skip_back.clicked.connect(lambda: self._skip(-10))
        self.btn_skip_fwd.clicked.connect(lambda: self._skip(+10))
        self.seek_slider.sliderPressed.connect(lambda: setattr(self, '_seek_dragging', True))
        self.seek_slider.sliderReleased.connect(self._on_seek_released)

        # Volume row
        vol_row = QHBoxLayout()

        vol_label = QLabel("VOL")
        vol_label.setObjectName("meta_text")
        vol_label.setFixedWidth(30)
        vol_row.addWidget(vol_label)

        self.vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(70)
        self.vol_slider.setFixedWidth(130)
        vol_row.addWidget(self.vol_slider)

        self.lbl_vol = QLabel("70%")
        self.lbl_vol.setObjectName("meta_text")
        self.lbl_vol.setFixedWidth(35)
        vol_row.addWidget(self.lbl_vol)

        vol_row.addStretch()

        lay.addLayout(vol_row)

        self.vol_slider.valueChanged.connect(self._on_volume_changed)

        # Audio meta line
        self.lbl_audio_meta = QLabel("")
        self.lbl_audio_meta.setObjectName("meta_text")
        lay.addWidget(self.lbl_audio_meta)

        lay.addStretch()

        return panel

    def _make_card(self, label_text: str, value_text: str, value_style: str) -> tuple:
        """Return (card_widget, value_label)."""
        card = QWidget()
        card.setObjectName("info_card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(12, 8, 12, 10)
        lay.setSpacing(2)

        lbl = QLabel(label_text)
        lbl.setObjectName("info_label")
        lay.addWidget(lbl)

        val = QLabel(value_text)
        val.setObjectName(value_style)
        lay.addWidget(val)

        return card, val

    # ------------------------------------------------------------------
    # Track loading
    # ------------------------------------------------------------------

    def _load_single_track(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Audio File", "",
            "Audio Files (*.mp3 *.wav *.flac *.m4a *.ogg *.aiff);;All Files (*)"
        )
        if path:
            if path not in self._row_map:
                self.track_table.setSortingEnabled(False)
                try:
                    row = self.track_table.rowCount()
                    self.track_table.insertRow(row)
                    self._set_row(row, path)
                    self._row_map[path] = row
                    self.library_files.append(path)
                    self.track_count_label.setText(f"{len(self.library_files)} tracks")
                finally:
                    self.track_table.setSortingEnabled(True)
                    self._rebuild_row_map()   # resort may have moved every row
            self._start_analysis(path)

    def _load_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Music Folder")
        if not folder:
            return
        files = [
            str(p) for p in sorted(Path(folder).rglob('*'))
            if p.is_file() and p.suffix.lower() in AUDIO_EXTS
        ]
        if not files:
            self._status.showMessage("No audio files found in folder.")
            return

        self.library_files = files
        self._row_map = {}
        self.track_table.setSortingEnabled(False)
        try:
            self.track_table.setRowCount(0)
            self.track_table.setRowCount(len(files))
            for i, fp in enumerate(files):
                self._set_row(i, fp)
                self._row_map[fp] = i
                if is_cached(Path(fp)):
                    cached = load_cached(Path(fp))
                    if cached:
                        self._update_row_from_results(fp, cached)
        finally:
            self.track_table.setSortingEnabled(True)
        self.track_count_label.setText(f"{len(files)} tracks")
        self.btn_analyze_all.setEnabled(True)
        self._status.showMessage(f"Loaded {len(files)} tracks")

    def _set_row(self, row: int, file_path: str):
        name = Path(file_path).stem
        item = QTableWidgetItem(name)
        item.setData(Qt.ItemDataRole.UserRole, file_path)
        item.setToolTip(file_path)
        self.track_table.setItem(row, 0, item)
        self.track_table.setItem(row, 1, QTableWidgetItem("--"))
        self.track_table.setItem(row, 2, QTableWidgetItem("--"))
        self.track_table.setItem(row, 3, QTableWidgetItem("--"))   # Energy
        self.track_table.setItem(row, 4, QTableWidgetItem("\u00b7"))  # · (pending)

    # ------------------------------------------------------------------
    # Track selection & analysis
    # ------------------------------------------------------------------

    def _on_track_selected(self):
        rows = self.track_table.selectedItems()
        if not rows:
            return
        row = rows[0].row()
        fp_item = self.track_table.item(row, 0)
        if fp_item:
            fp = fp_item.data(Qt.ItemDataRole.UserRole)
            if fp:
                self._start_analysis(fp)

    def _start_analysis(self, file_path: str):
        self._status.showMessage(f"Analyzing: {Path(file_path).name}\u2026")
        row = self._row_map.get(file_path)
        if row is not None:
            self._highlight_row(row, ROW_ANALYZING)

        # Disconnect previous thread to prevent stale results
        if self.analysis_thread is not None:
            try:
                self.analysis_thread.finished.disconnect()
                self.analysis_thread.error.disconnect()
            except RuntimeError:
                pass  # already disconnected

        self.analysis_thread = AnalysisThread(file_path)
        self.analysis_thread.finished.connect(self._on_analysis_done)
        self.analysis_thread.error.connect(self._on_analysis_error)
        self.analysis_thread.start()

    def _on_analysis_done(self, results: dict):
        self.current_track = results
        fp = results['file_path']
        self._update_row_from_results(fp, results)
        self._display_track(results)
        self._status.showMessage(f"Ready: {results['filename']}")

    def _on_analysis_error(self, msg: str):
        self._status.showMessage(f"Error: {msg}")

    def _update_row_from_results(self, file_path: str, results: dict):
        row = self._row_map.get(file_path)
        if row is None:
            return
        bpm          = results.get('bpm')
        key          = results.get('key', {})
        energy       = results.get('energy', {})
        camelot      = key.get('camelot', '--')
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

    def _highlight_row(self, row: int, color: QColor):
        for col in range(self.track_table.columnCount()):
            item = self.track_table.item(row, col)
            if item:
                item.setBackground(color)

    def _rebuild_row_map(self) -> None:
        """Rebuild _row_map after table sort — keeps file_path→row_index accurate."""
        self._row_map = {}
        for row in range(self.track_table.rowCount()):
            item = self.track_table.item(row, 0)
            if item:
                fp = item.data(Qt.ItemDataRole.UserRole)
                if fp:
                    self._row_map[fp] = row

    # ------------------------------------------------------------------
    # Batch analysis
    # ------------------------------------------------------------------

    def _analyze_all(self):
        if not self.library_files:
            return
        if self.batch_thread and self.batch_thread.isRunning():
            self.batch_thread.cancel()
            self.btn_analyze_all.setText("Analyze All")
            self.batch_progress.setVisible(False)
            return

        self.btn_analyze_all.setText("Cancel")
        self.batch_progress.setMaximum(len(self.library_files))
        self.batch_progress.setValue(0)
        self.batch_progress.setVisible(True)

        self.batch_thread = BatchThread(self.library_files)
        self.batch_thread.track_done.connect(self._on_batch_track_done)
        self.batch_thread.all_done.connect(self._on_batch_all_done)
        self.batch_thread.progress.connect(self._on_batch_progress)
        self.batch_thread.start()

    def _on_batch_track_done(self, file_path: str, results: dict, current: int, total: int):
        self._update_row_from_results(file_path, results)

    def _on_batch_progress(self, current: int, total: int):
        self.batch_progress.setValue(current)
        self._status.showMessage(f"Analyzing {current}/{total}\u2026")

    def _on_batch_all_done(self, analyzed: int, cached: int):
        self.btn_analyze_all.setText("Analyze All")
        self.batch_progress.setVisible(False)
        self._status.showMessage(
            f"Done \u2014 {analyzed} analyzed, {cached} from cache, {analyzed + cached} total"
        )

    # ------------------------------------------------------------------
    # Detail panel display
    # ------------------------------------------------------------------

    def _display_track(self, results: dict):
        meta   = results.get('metadata', {})
        title  = meta.get('title')  or results['filename']
        artist = meta.get('artist') or "Unknown Artist"
        self.lbl_title.setText(title)
        self.lbl_artist.setText(artist)

        bpm    = results.get('bpm')
        key    = results.get('key', {})
        energy = results.get('energy', {})
        ai     = results.get('audio_info', {})
        dur_sec = int(results.get('duration', 0))

        # Unpack cards
        _, bpm_val = self.card_bpm
        _, key_val = self.card_key
        _, cam_val = self.card_camelot
        _, ene_val = self.card_energy

        bpm_val.setText(str(bpm) if bpm else "--")
        key_val.setText(key.get('notation', '--'))
        cam_val.setText(key.get('camelot', '--'))
        ene_val.setText(f"{energy.get('level', '--')}/10")

        # Audio meta line
        fmt = ai.get('format', '--')
        br  = ai.get('bitrate', 0)
        sr  = ai.get('sample_rate', 0)
        sz  = ai.get('file_size_mb', 0)
        mm  = dur_sec // 60
        ss  = dur_sec % 60
        self.lbl_audio_meta.setText(
            f"{fmt}  \u00b7  {br} kbps  \u00b7  {sr // 1000}.{(sr % 1000) // 100}kHz"
            f"  \u00b7  {sz:.1f} MB  \u00b7  {mm}:{ss:02d}"
        )

        # Seek slider
        self.seek_slider.setMaximum(max(1, dur_sec * 10))
        self.lbl_time.setText(f"0:00 / {mm}:{ss:02d}")

        # Load audio + waveform
        if self.audio_player.load(results['file_path']):
            self.audio_player.set_duration(results.get('duration', dur_sec))
            self.waveform.set_waveform_from_file(results['file_path'])
            self._enable_controls(True)
        else:
            self._enable_controls(False)
            self._status.showMessage("Error loading audio")

    def _enable_controls(self, enabled: bool):
        for w in (self.btn_play, self.btn_stop, self.btn_skip_back,
                  self.btn_skip_fwd, self.seek_slider):
            w.setEnabled(enabled)

    # ------------------------------------------------------------------
    # Playback controls
    # ------------------------------------------------------------------

    def _toggle_playback(self):
        state = self.audio_player.state
        if state == PlayerState.PLAYING:
            self.audio_player.pause()
            self.btn_play.setText("\u25b6  Play")
        elif state == PlayerState.PAUSED:
            self.audio_player.resume()
            self.btn_play.setText("\u23f8  Pause")
        else:  # STOPPED
            self.audio_player.play()
            self.btn_play.setText("\u23f8  Pause")

    def _stop_playback(self):
        self.audio_player.stop()
        self.btn_play.setText("\u25b6  Play")
        self.waveform.set_playback_position(0.0)
        self.seek_slider.setValue(0)

    def _skip(self, seconds: float):
        if not self.current_track or self.audio_player.duration <= 0:
            return
        cur = self.audio_player.get_position() * self.audio_player.duration
        new_pos = max(0.0, min(cur + seconds, self.audio_player.duration))
        self.audio_player.seek(new_pos / self.audio_player.duration)

    def _on_position_changed(self, pos: float):
        self.waveform.set_playback_position(pos)
        if not self._seek_dragging:
            self.seek_slider.setValue(int(pos * self.seek_slider.maximum()))
        if self.current_track:
            total_sec = int(self.current_track.get('duration', 0))
            cur_sec   = int(pos * total_sec)
            self.lbl_time.setText(
                f"{cur_sec // 60}:{cur_sec % 60:02d} / "
                f"{total_sec // 60}:{total_sec % 60:02d}"
            )

    def _on_playback_finished(self):
        self.btn_play.setText("\u25b6  Play")
        self.waveform.set_playback_position(0.0)
        self.seek_slider.setValue(0)

    def _on_waveform_clicked(self, pos: float):
        self.audio_player.seek(pos)
        self.waveform.set_playback_position(pos)

    def _on_seek_released(self):
        self._seek_dragging = False
        if self.audio_player.duration > 0:
            pos = self.seek_slider.value() / self.seek_slider.maximum()
            self.audio_player.seek(pos)

    def _on_volume_changed(self, val: int):
        self.audio_player.set_volume(val / 100.0)
        self.lbl_vol.setText(f"{val}%")

    # ------------------------------------------------------------------
    # Search / filter
    # ------------------------------------------------------------------

    def _filter_tracks(self, text: str):
        for row in range(self.track_table.rowCount()):
            item = self.track_table.item(row, 0)
            match = (text.lower() in item.text().lower()) if item else True
            self.track_table.setRowHidden(row, not match)

    # ------------------------------------------------------------------
    # Context menu
    # ------------------------------------------------------------------

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

        action = menu.exec(self.track_table.viewport().mapToGlobal(pos))
        if action == action_analyze and fp:
            self._start_analysis(fp)
        elif action == action_reveal and fp:
            os.startfile(str(Path(fp).parent))
