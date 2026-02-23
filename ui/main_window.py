"""
DJ Track Analyzer - Main Window UI
PyQt6-based desktop application for browsing and analyzing DJ tracks.
"""

import os
import sys
import json
import shutil
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QPushButton, QLabel, QLineEdit, QTableWidget, QTableWidgetItem,
    QFileDialog, QHeaderView, QProgressBar, QStatusBar, QSlider,
    QMenu, QApplication, QComboBox, QInputDialog, QAbstractItemView,
    QDialog, QScrollArea,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QPoint
from PyQt6.QtGui import QColor, QAction, QKeyEvent

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
PLAYLISTS_FILE = Path(__file__).parent.parent / 'data' / 'playlists.json'
HOT_CUES_FILE  = Path(__file__).parent.parent / 'data' / 'hot_cues.json'

HOT_CUE_COLORS = [
    QColor(255, 107,   0),   # 1 — Orange
    QColor(  0, 200, 255),   # 2 — Cyan
    QColor(  0, 220, 100),   # 3 — Green
    QColor(255,   0, 136),   # 4 — Pink
    QColor(255, 215,   0),   # 5 — Yellow
    QColor(170,  68, 255),   # 6 — Purple
]

# ── Camelot sort order (1A=0, 1B=1, 2A=2, … 12B=23, unknown=24) ──────────────
_CAMELOT_ORDER: dict = {}
for _i in range(1, 13):
    _CAMELOT_ORDER[f"{_i}A"] = (_i - 1) * 2
    _CAMELOT_ORDER[f"{_i}B"] = (_i - 1) * 2 + 1


def _camelot_sort_key(camelot: str) -> int:
    """Return integer sort key for a Camelot string (1A–12B). Unknown → 24."""
    return _CAMELOT_ORDER.get(camelot, 24)


class DraggableLibraryTable(QTableWidget):
    """Library table that drags the selected track's file path as text/plain MIME."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        self.setDefaultDropAction(Qt.DropAction.CopyAction)

    def mimeData(self, items):
        data = super().mimeData(items)
        if items:
            fp_item = self.item(items[0].row(), 0)
            if fp_item:
                fp = fp_item.data(Qt.ItemDataRole.UserRole)
                if fp:
                    data.setText(str(fp))
        return data


class PlaylistDropTable(QTableWidget):
    """Playlist table that accepts file path drops from DraggableLibraryTable."""

    file_dropped = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DropOnly)

    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasText():
            fp = event.mimeData().text().strip()
            if fp:
                self.file_dropped.emit(fp)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)


class HelpDialog(QDialog):
    """Non-modal help dialog with keyboard shortcuts, waveform legend, and algorithm notes."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("DJ Track Analyzer — Help")
        self.setMinimumSize(480, 520)
        self.setModal(False)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 16, 20, 16)
        outer.setSpacing(8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setSpacing(6)
        lay.setContentsMargins(0, 0, 8, 0)

        def header(text: str) -> None:
            lbl = QLabel(text)
            lbl.setObjectName("section_header")
            lay.addWidget(lbl)

        def shortcut_row(key: str, desc: str) -> None:
            row_w = QWidget()
            row_l = QHBoxLayout(row_w)
            row_l.setContentsMargins(0, 1, 0, 1)
            row_l.setSpacing(8)
            k = QLabel(key)
            k.setObjectName("help_key")
            k.setFixedWidth(148)
            d = QLabel(desc)
            d.setObjectName("meta_text")
            d.setWordWrap(True)
            row_l.addWidget(k)
            row_l.addWidget(d, stretch=1)
            lay.addWidget(row_w)

        def para(text: str) -> None:
            lbl = QLabel(text)
            lbl.setObjectName("meta_text")
            lbl.setWordWrap(True)
            lay.addWidget(lbl)

        def divider() -> None:
            line = QWidget()
            line.setFixedHeight(1)
            line.setStyleSheet("background-color: #1e2a3a;")
            lay.addWidget(line)
            lay.addSpacing(4)

        # ── Section 1: Keyboard Shortcuts ─────────────────────────────
        header("Keyboard Shortcuts")
        lay.addSpacing(2)
        shortcut_row("Space", "Play / Pause")
        shortcut_row("\u2190 / \u2192", "Seek \u22125 s / +5 s")
        shortcut_row("Shift+\u2190 / \u2192", "Seek \u221230 s / +30 s")
        shortcut_row("I", "Set loop in-point (A)")
        shortcut_row("O", "Set loop out-point (B)")
        shortcut_row("L", "Toggle loop on / off")
        shortcut_row("1 \u2013 6", "Jump to hot cue  (sets if empty)")
        shortcut_row("Shift+1 \u2013 6", "Clear hot cue")
        shortcut_row("Enter", "Play selected track (library or playlist)")
        shortcut_row("Delete", "Remove selected track from playlist")
        shortcut_row("F1 / ?", "Open this window")
        lay.addSpacing(4)
        divider()

        # ── Section 2: Waveform Colors ────────────────────────────────
        header("Waveform Colors")
        lay.addSpacing(2)
        shortcut_row("\U0001f534  Red (bass)", "Kicks, subs, low-end  \u2014  0\u2013200 Hz")
        shortcut_row("\U0001f7e0  Amber (mids)", "Melody, vocals, snare  \u2014  200\u20134000 Hz")
        shortcut_row("\U0001f535  Cyan (highs)", "Cymbals, air, hi-hats  \u2014  4000+ Hz")
        para(
            "Bar brightness = amplitude. Quiet sections are darker, loud are brighter. "
            "Bars left of the playhead are dimmed to 35% brightness."
        )
        para(
            "Single waveform (160px): full-track view — "
            "click or drag anywhere to seek."
        )
        lay.addSpacing(4)
        divider()

        # ── Section 3: Energy Score ───────────────────────────────────
        header("Energy Score  (1\u201310)")
        lay.addSpacing(2)
        para(
            "Computed as the root-mean-square (RMS) amplitude across the entire track, "
            "read in 65\u202f536-sample chunks without loading the full file into memory. "
            "The global RMS is mapped to a 1\u201310 scale via fixed thresholds: "
            "1\u202f=\u202fnear-silent / ambient,  10\u202f=\u202fpeak-clipped intensity."
        )
        lay.addSpacing(4)
        divider()

        # ── Section 4: Key Detection ──────────────────────────────────
        header("Key Detection")
        lay.addSpacing(2)
        para(
            "Uses the Krumhansl\u2013Schmuckler pitch-class profile algorithm: "
            "pitch-class distribution is computed from the audio and correlated against "
            "all 24 major/minor key profiles. The best match is the detected key."
        )
        para(
            "Displayed in standard notation (e.g.\u202fF\u266f minor) and "
            "Camelot wheel notation (e.g.\u202f11A) for harmonic mixing. "
            "Adjacent Camelot numbers (+1 / \u22121) and same number in A/B are harmonically compatible."
        )

        lay.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)

        btn_close = QPushButton("Close")
        btn_close.setFixedHeight(32)
        btn_close.clicked.connect(self.close)
        outer.addWidget(btn_close)


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
        self._playlists: list = []   # list of {"name": str, "tracks": [str]}
        self._hot_cues: list = [None] * 6   # each: None or {'position': float (0-1)}
        self._loop_a: float | None = None
        self._loop_b: float | None = None
        self._loop_active: bool = False
        self._help_dialog = None

        self.audio_player = AudioPlayer()
        self.audio_player.position_changed.connect(self._on_position_changed)
        self.audio_player.playback_finished.connect(self._on_playback_finished)
        self.audio_player.set_volume(0.7)

        self.setWindowTitle("DJ Track Analyzer")
        self.setMinimumSize(1200, 720)
        self.resize(1400, 820)

        self._init_ui()
        self.setStyleSheet(STYLESHEET)
        self._load_playlists()

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

        btn_help = QPushButton("?")
        btn_help.setFixedSize(28, 32)
        btn_help.setToolTip("Help / keyboard shortcuts  (F1)")
        btn_help.clicked.connect(self._show_help)
        lay.addWidget(btn_help)

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

        self.track_table = DraggableLibraryTable()
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
        lay.setContentsMargins(10, 0, 4, 0)   # 10px left aligns content with library panel edge
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
        self.waveform.position_dragging.connect(self._on_waveform_dragging)
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

        lay.addWidget(self._build_hot_cue_row())
        lay.addWidget(self._build_loop_row())
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

        lay.addWidget(self._build_playlist_panel())

        return panel

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
        self.playlist_table = PlaylistDropTable()
        self.playlist_table.setColumnCount(3)
        self.playlist_table.setHorizontalHeaderLabels(["Track", "BPM", "Key"])
        self.playlist_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.playlist_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.playlist_table.verticalHeader().setVisible(False)
        self.playlist_table.setShowGrid(False)
        self.playlist_table.setAlternatingRowColors(True)
        self.playlist_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.playlist_table.customContextMenuRequested.connect(self._playlist_context_menu)
        self.playlist_table.file_dropped.connect(
            lambda fp: self._add_to_playlist(
                fp, self.playlist_selector.currentText()
            )
        )
        self.playlist_table.verticalHeader().setDefaultSectionSize(22)

        ph = self.playlist_table.horizontalHeader()
        ph.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        ph.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        ph.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.playlist_table.setColumnWidth(1, 55)
        self.playlist_table.setColumnWidth(2, 55)
        self.playlist_table.setMaximumHeight(180)
        self.playlist_table.setSortingEnabled(True)

        lay.addWidget(self.playlist_table)

        # Wire selector change
        self.playlist_selector.currentIndexChanged.connect(self._on_playlist_changed)

        return panel

    def _build_hot_cue_row(self) -> QWidget:
        """Build the 6-button hot cue row."""
        row_widget = QWidget()
        lay = QHBoxLayout(row_widget)
        lay.setContentsMargins(0, 2, 0, 0)
        lay.setSpacing(4)

        lbl = QLabel("CUE")
        lbl.setObjectName("meta_text")
        lbl.setFixedWidth(30)
        lay.addWidget(lbl)

        self._cue_buttons: list = []
        for i in range(6):
            btn = QPushButton(str(i + 1))
            btn.setFixedSize(44, 26)
            btn.setToolTip(f"Set cue {i + 1}  (key: {i + 1})")
            btn.clicked.connect(lambda checked, idx=i: self._on_cue_clicked(idx))
            btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            btn.customContextMenuRequested.connect(
                lambda pos, idx=i: self._cue_context_menu(idx, pos)
            )
            self._cue_buttons.append(btn)
            lay.addWidget(btn)

        lay.addStretch()
        return row_widget

    def _build_loop_row(self) -> QWidget:
        """Build the A-B loop + bar-snap control row."""
        row_widget = QWidget()
        lay = QHBoxLayout(row_widget)
        lay.setContentsMargins(0, 0, 0, 2)
        lay.setSpacing(4)

        lbl = QLabel("LOOP")
        lbl.setObjectName("meta_text")
        lbl.setFixedWidth(30)
        lay.addWidget(lbl)

        self.btn_loop_a = QPushButton("A")
        self.btn_loop_a.setFixedSize(32, 26)
        self.btn_loop_a.setToolTip("Set loop in-point  (key: I)")
        self.btn_loop_a.clicked.connect(self._set_loop_a)
        lay.addWidget(self.btn_loop_a)

        self.btn_loop_b = QPushButton("B")
        self.btn_loop_b.setFixedSize(32, 26)
        self.btn_loop_b.setToolTip("Set loop out-point  (key: O)")
        self.btn_loop_b.clicked.connect(self._set_loop_b)
        lay.addWidget(self.btn_loop_b)

        self.btn_loop_toggle = QPushButton("\u27f3 LOOP")
        self.btn_loop_toggle.setFixedSize(76, 26)
        self.btn_loop_toggle.setToolTip("Toggle loop on/off  (key: L)")
        self.btn_loop_toggle.setEnabled(False)
        self.btn_loop_toggle.clicked.connect(self._toggle_loop)
        lay.addWidget(self.btn_loop_toggle)

        sep = QLabel("|")
        sep.setObjectName("meta_text")
        sep.setFixedWidth(10)
        lay.addWidget(sep)

        for label, bars in [("\u00bd", 0.5), ("1", 1.0), ("2", 2.0), ("4", 4.0), ("8", 8.0)]:
            btn = QPushButton(label)
            btn.setFixedSize(28, 26)
            btn.setToolTip(f"Snap loop to {label} bar(s) from nearest beat")
            btn.clicked.connect(lambda checked, b=bars: self._snap_loop(b))
            lay.addWidget(btn)

        lay.addStretch()
        return row_widget

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
    # Playlist persistence
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Hot cues
    # ------------------------------------------------------------------

    def _on_cue_clicked(self, idx: int) -> None:
        if not self.current_track:
            return
        if self._hot_cues[idx] is None:
            pos = self.audio_player.get_position()
            self._hot_cues[idx] = {'position': pos}
            self._save_hot_cues()
            self._refresh_cue_buttons()
            self._refresh_waveform_overlays()
            self._status.showMessage(f"Cue {idx + 1} set at {pos:.1%}")
        else:
            self.audio_player.seek(self._hot_cues[idx]['position'])

    def _cue_context_menu(self, idx: int, pos) -> None:
        if self._hot_cues[idx] is None:
            return
        menu = QMenu(self)
        action_clear = menu.addAction(f"Clear cue {idx + 1}")
        btn = self._cue_buttons[idx]
        action = menu.exec(btn.mapToGlobal(pos))
        if action == action_clear:
            self._hot_cues[idx] = None
            self._save_hot_cues()
            self._refresh_cue_buttons()
            self._refresh_waveform_overlays()

    def _refresh_cue_buttons(self) -> None:
        for i, (btn, cue) in enumerate(zip(self._cue_buttons, self._hot_cues)):
            color = HOT_CUE_COLORS[i]
            if cue is None:
                btn.setStyleSheet("")
                btn.setToolTip(f"Set cue {i + 1}  (key: {i + 1})")
            else:
                r, g, b = color.red(), color.green(), color.blue()
                btn.setStyleSheet(
                    f"QPushButton {{"
                    f"  background-color: rgba({r},{g},{b},140);"
                    f"  color: rgb({r},{g},{b});"
                    f"  font-weight: bold;"
                    f"  border: 1px solid rgba({r},{g},{b},180);"
                    f"}}"
                    f"QPushButton:hover {{"
                    f"  background-color: rgba({r},{g},{b},220);"
                    f"}}"
                )
                btn.setToolTip(
                    f"Jump to cue {i + 1}  (key: {i + 1}) · Right-click to clear"
                )

    def _refresh_waveform_overlays(self) -> None:
        """Push current cue + loop state to both waveform panels."""
        cues_data = []
        for i, cue in enumerate(self._hot_cues):
            if cue is not None:
                cues_data.append({
                    'position': cue['position'],
                    'color':    HOT_CUE_COLORS[i],
                })
            else:
                cues_data.append(None)
        # _loop_a/_loop_b/_loop_active added by Task 4; guard with getattr for now
        loop_a      = getattr(self, '_loop_a',      None)
        loop_b      = getattr(self, '_loop_b',      None)
        loop_active = getattr(self, '_loop_active', False)
        self.waveform.update_cues_and_loop(cues_data, loop_a, loop_b, loop_active)

    def _set_loop_a(self) -> None:
        if not self.current_track:
            return
        self._loop_a = self.audio_player.get_position()
        self._loop_active = False
        self._loop_b = None
        self.btn_loop_toggle.setEnabled(False)
        self._refresh_loop_buttons()
        self._refresh_waveform_overlays()

    def _set_loop_b(self) -> None:
        if not self.current_track:
            return
        if self._loop_a is None:
            self._status.showMessage("Set loop A point first  (key: I)")
            return
        pos = self.audio_player.get_position()
        if pos <= self._loop_a:
            self._status.showMessage("Loop B must be after A.")
            return
        self._loop_b = pos
        self.btn_loop_toggle.setEnabled(True)
        self._refresh_loop_buttons()
        self._refresh_waveform_overlays()

    def _toggle_loop(self) -> None:
        if self._loop_a is None or self._loop_b is None:
            return
        self._loop_active = not self._loop_active
        self._refresh_loop_buttons()
        self._refresh_waveform_overlays()

    def _snap_loop(self, bars: float) -> None:
        if not self.current_track:
            return
        bpm = self.current_track.get('bpm')
        if not bpm:
            self._status.showMessage("Analyze track first to get BPM for bar snap.")
            return
        total = self.current_track.get('duration', 0)
        if total <= 0:
            return
        secs_per_bar = 4.0 * 60.0 / float(bpm)
        cur_secs = self.audio_player.get_position() * total
        bar_num = round(cur_secs / secs_per_bar)
        a_secs = bar_num * secs_per_bar
        b_secs = min(a_secs + bars * secs_per_bar, total)
        self._loop_a = a_secs / total
        self._loop_b = b_secs / total
        self._loop_active = True
        self.btn_loop_toggle.setEnabled(True)
        self._refresh_loop_buttons()
        self._refresh_waveform_overlays()
        label = "\u00bd" if bars == 0.5 else str(int(bars))
        self._status.showMessage(
            f"Loop: {label} bar(s) · {a_secs:.2f}s → {b_secs:.2f}s"
        )

    def _refresh_loop_buttons(self) -> None:
        active_style = (
            "QPushButton {"
            "  background-color: rgba(255,185,0,140);"
            "  color: #FFB900;"
            "  font-weight: bold;"
            "  border: 1px solid rgba(255,185,0,180);"
            "}"
        )
        toggle_style = (
            "QPushButton {"
            "  background-color: rgba(0,220,100,160);"
            "  color: #00DC64;"
            "  font-weight: bold;"
            "  border: 1px solid rgba(0,220,100,200);"
            "}"
        )
        self.btn_loop_a.setStyleSheet(active_style if self._loop_a is not None else "")
        self.btn_loop_b.setStyleSheet(active_style if self._loop_b is not None else "")
        self.btn_loop_toggle.setEnabled(
            self._loop_a is not None and self._loop_b is not None
        )
        self.btn_loop_toggle.setStyleSheet(toggle_style if self._loop_active else "")

    def _load_hot_cues(self, file_path: str) -> None:
        """Load saved cues for this track from disk."""
        self._hot_cues = [None] * 6
        try:
            if HOT_CUES_FILE.exists():
                with open(HOT_CUES_FILE) as f:
                    data = json.load(f)
                saved = data.get(file_path, [None] * 6)
                for i, c in enumerate(saved[:6]):
                    if isinstance(c, dict) and 'position' in c:
                        self._hot_cues[i] = {'position': float(c['position'])}
        except Exception as e:
            print(f"Could not load hot cues: {e}")

    def _save_hot_cues(self) -> None:
        """Persist current track's cues to disk."""
        if not self.current_track:
            return
        fp = self.current_track['file_path']
        try:
            HOT_CUES_FILE.parent.mkdir(parents=True, exist_ok=True)
            existing: dict = {}
            if HOT_CUES_FILE.exists():
                with open(HOT_CUES_FILE) as f:
                    existing = json.load(f)
            existing[fp] = self._hot_cues
            with open(HOT_CUES_FILE, 'w') as f:
                json.dump(existing, f, indent=2)
        except Exception as e:
            print(f"Could not save hot cues: {e}")

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

        # Reset cues for the new track
        self._load_hot_cues(results['file_path'])
        self._refresh_cue_buttons()
        self._refresh_waveform_overlays()

        # Reset loop state for new track
        self._loop_a = None
        self._loop_b = None
        self._loop_active = False
        self._refresh_loop_buttons()

        # Load audio + waveform
        # Capture playing state BEFORE load() calls stop() internally
        was_playing = (self.audio_player.state == PlayerState.PLAYING)

        if self.audio_player.load(results['file_path']):
            self.audio_player.set_duration(results.get('duration', dur_sec))
            self.waveform.set_waveform_from_file(results['file_path'])
            self._enable_controls(True)
            if was_playing:
                self.audio_player.play()
                self.btn_play.setText("\u23f8  Pause")
            else:
                self.btn_play.setText("\u25b6  Play")
        else:
            self.btn_play.setText("\u25b6  Play")
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
        # Loop playback
        if (self._loop_active
                and self._loop_a is not None
                and self._loop_b is not None
                and pos >= self._loop_b):
            self.audio_player.seek(self._loop_a)
            return
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

    def _on_waveform_dragging(self, pos: float):
        """Visual-only update during waveform drag — no audio seek."""
        self.waveform.set_playback_position(pos)
        if not self._seek_dragging and self.audio_player.duration > 0:
            self.seek_slider.setValue(int(pos * self.seek_slider.maximum()))

    def _on_seek_released(self):
        self._seek_dragging = False
        if self.audio_player.duration > 0:
            pos = self.seek_slider.value() / self.seek_slider.maximum()
            self.audio_player.seek(pos)

    def _on_volume_changed(self, val: int):
        self.audio_player.set_volume(val / 100.0)
        self.lbl_vol.setText(f"{val}%")

    def _show_help(self) -> None:
        """Open (or raise) the non-modal help dialog."""
        if self._help_dialog is None or not self._help_dialog.isVisible():
            self._help_dialog = HelpDialog(self)
            self._help_dialog.setStyleSheet(self.styleSheet())
        self._help_dialog.show()
        self._help_dialog.raise_()
        self._help_dialog.activateWindow()

    def _clear_cue(self, idx: int) -> None:
        self._hot_cues[idx] = None
        self._save_hot_cues()
        self._refresh_cue_buttons()
        self._refresh_waveform_overlays()

    def _delete_selected_playlist_track(self) -> None:
        rows = self.playlist_table.selectedItems()
        if not rows:
            return
        fp_item = self.playlist_table.item(rows[0].row(), 0)
        if fp_item:
            fp = fp_item.data(Qt.ItemDataRole.UserRole)
            if fp:
                self._remove_from_playlist(fp)

    def _play_selected_track(self, table: QTableWidget) -> None:
        rows = table.selectedItems()
        if not rows:
            return
        fp_item = table.item(rows[0].row(), 0)
        if fp_item:
            fp = fp_item.data(Qt.ItemDataRole.UserRole)
            if fp:
                self._start_analysis(fp)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key  = event.key()
        mods = event.modifiers()
        Mod  = Qt.KeyboardModifier
        Key  = Qt.Key

        # Don't capture Space when a text input (search box) is focused
        focused = QApplication.focusWidget()
        if key == Key.Key_Space and isinstance(focused, QLineEdit):
            super().keyPressEvent(event)
            return

        if key == Key.Key_Space:
            self._toggle_playback()
        elif key == Key.Key_Left:
            self._skip(-30 if mods & Mod.ShiftModifier else -5)
        elif key == Key.Key_Right:
            self._skip(30 if mods & Mod.ShiftModifier else 5)
        elif key == Key.Key_I:
            self._set_loop_a()
        elif key == Key.Key_O:
            self._set_loop_b()
        elif key == Key.Key_L:
            self._toggle_loop()
        elif key == Key.Key_F1:
            self._show_help()
        elif Key.Key_1 <= key <= Key.Key_6:
            idx = key - Key.Key_1
            if mods & Mod.ShiftModifier:
                self._clear_cue(idx)
            else:
                self._on_cue_clicked(idx)
        elif key in (Key.Key_Return, Key.Key_Enter):
            if self.track_table.hasFocus():
                self._play_selected_track(self.track_table)
            elif self.playlist_table.hasFocus():
                self._play_selected_track(self.playlist_table)
        elif key == Key.Key_Delete:
            if self.playlist_table.hasFocus():
                self._delete_selected_playlist_track()
        else:
            super().keyPressEvent(event)

    # ------------------------------------------------------------------
    # Playlist actions
    # ------------------------------------------------------------------

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
        self.playlist_selector.blockSignals(True)
        self.playlist_selector.removeItem(idx)
        self.playlist_selector.blockSignals(False)
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
        self.playlist_table.setSortingEnabled(False)
        self.playlist_table.setRowCount(0)
        idx = self.playlist_selector.currentIndex()
        if idx < 0 or idx >= len(self._playlists):
            self.playlist_table.setSortingEnabled(True)
            return
        pl = self._playlists[idx]
        for fp in pl['tracks']:
            row = self.playlist_table.rowCount()
            self.playlist_table.insertRow(row)
            name_item = QTableWidgetItem(Path(fp).stem)
            name_item.setData(Qt.ItemDataRole.UserRole, fp)
            name_item.setToolTip(fp)
            self.playlist_table.setItem(row, 0, name_item)
            cached = load_cached(Path(fp))
            if cached:
                bpm     = cached.get('bpm')
                camelot = cached.get('key', {}).get('camelot', '--')
                bpm_item = NumericTableWidgetItem(str(bpm) if bpm else "--")
                bpm_item.setData(Qt.ItemDataRole.UserRole, float(bpm) if bpm else 999.0)
                self.playlist_table.setItem(row, 1, bpm_item)
                key_item = NumericTableWidgetItem(camelot)
                key_item.setData(Qt.ItemDataRole.UserRole, _camelot_sort_key(camelot))
                self.playlist_table.setItem(row, 2, key_item)
            else:
                self.playlist_table.setItem(row, 1, QTableWidgetItem("--"))
                self.playlist_table.setItem(row, 2, QTableWidgetItem("--"))
        self.playlist_table.setSortingEnabled(True)

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
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            self._status.showMessage(f"Export failed: could not create folder — {e}")
            return
        copied = skipped = errors = 0
        for track_path in pl['tracks']:
            src = Path(track_path)
            if src.exists():
                try:
                    shutil.copy2(src, out_dir / src.name)
                    copied += 1
                except OSError:
                    errors += 1
            else:
                skipped += 1
        msg = f"Exported {copied} tracks to {out_dir}"
        if skipped:
            msg += f" ({skipped} not found)"
        if errors:
            msg += f" ({errors} copy errors)"
        self._status.showMessage(msg)

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
        menu.addSeparator()

        # "Add to Playlist" submenu
        playlist_menu = menu.addMenu("Add to Playlist")
        playlist_actions: dict = {}
        if self._playlists:
            for pl in self._playlists:
                a = playlist_menu.addAction(pl['name'])
                playlist_actions[a] = pl['name']
        else:
            no_pl = playlist_menu.addAction("No playlists — create one first")
            no_pl.setEnabled(False)

        action = menu.exec(self.track_table.viewport().mapToGlobal(pos))
        if action is None:
            return
        if action == action_analyze and fp:
            self._start_analysis(fp)
        elif action == action_reveal and fp:
            os.startfile(str(Path(fp).parent))
        elif action in playlist_actions and fp:
            self._add_to_playlist(fp, playlist_actions[action])
