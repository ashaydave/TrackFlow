"""
Downloads Tab — TrackFlow Phase 2
Provides three sub-tabs:
  1. Queue     — YouTube URL / manual download queue with per-row progress
  2. Subscriptions — Watch YouTube playlists and Apple Music / Shazam playlists
  3. SoulSeek  — Filesystem watcher for the SoulSeek download folder
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog, QTabWidget,
    QSplitter, QGroupBox, QInputDialog, QSizePolicy, QProgressBar, QMessageBox,
)
from PyQt6.QtGui import QColor

sys.path.insert(0, str(Path(__file__).parent.parent))
from paths import get_data_dir
from downloader.yt_handler import DownloadWorker, find_ffmpeg
from downloader.watcher import FolderWatcher
from downloader.playlist_sync import (
    YouTubePlaylistSource,
    AppleMusicSource,
    AppleMusicURLSource,
    PlaylistSyncWorker,
    load_sync_state,
    detect_apple_music_xml,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CONFIG_FILE = get_data_dir() / "downloads_config.json"

_STATUS_PENDING     = "Pending"
_STATUS_DOWNLOADING = "Downloading…"
_STATUS_DONE        = "✓ Done"
_STATUS_IMPORTING   = "⬆ Importing…"

_COLOR_DONE    = QColor(0, 200, 80)
_COLOR_ERROR   = QColor(255, 60, 60)
_COLOR_PENDING = QColor(80, 95, 130)
_COLOR_ACTIVE  = QColor(0, 160, 255)


# ---------------------------------------------------------------------------
# DownloadsTab
# ---------------------------------------------------------------------------

class DownloadsTab(QWidget):
    """
    Top-level Downloads tab widget.

    Signals
    -------
    import_requested(file_path)  — tell MainWindow to add this file to the library
    notify(title, body)          — request a desktop notification
    """

    import_requested = pyqtSignal(str)
    notify           = pyqtSignal(str, str)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(self, parent=None):
        super().__init__(parent)

        # Detect ffmpeg once at startup — enables MP3 320 kbps output
        self._ffmpeg_path: str | None = find_ffmpeg()

        # Queue state: list of dicts
        # {url, title, source_label, status, file_path, worker_key}
        self._queue: list[dict] = []
        self._worker: DownloadWorker | None = None
        self._active_url: str | None = None

        # SoulSeek watcher state
        self._watcher = FolderWatcher()
        self._watcher.file_detected.connect(self._on_file_detected)
        self._watcher_items: list[dict] = []  # {file_path, size_mb, imported}

        # Subscription sync worker
        self._sync_worker: PlaylistSyncWorker | None = None

        # Not-found items from subscription sync
        self._not_found: list[dict] = []

        self._config: dict = {}
        self._load_config()

        self._build_ui()

        # Restore watcher if a watch dir was saved
        watch_dir = self._config.get("watch_dir", "")
        if watch_dir and Path(watch_dir).exists():
            self._start_watcher()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._sub_tabs = QTabWidget()
        self._sub_tabs.addTab(self._build_queue_tab(),     "⬇  Queue")
        self._sub_tabs.addTab(self._build_subs_tab(),      "📋  Subscriptions")
        self._sub_tabs.addTab(self._build_soulseek_tab(),  "🎵  SoulSeek Watcher")

        outer.addWidget(self._sub_tabs)

    # ── Queue tab ──────────────────────────────────────────────────────

    def _build_queue_tab(self) -> QWidget:
        page = QWidget()
        lay  = QVBoxLayout(page)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        # Top controls row
        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(6)

        self._url_edit = QLineEdit()
        self._url_edit.setPlaceholderText("Paste a YouTube URL or playlist URL…")
        self._url_edit.returnPressed.connect(self._on_add_url)
        ctrl_row.addWidget(self._url_edit, stretch=1)

        btn_add = QPushButton("+ Add")
        btn_add.setFixedWidth(72)
        btn_add.clicked.connect(self._on_add_url)
        ctrl_row.addWidget(btn_add)

        self.btn_download_all = QPushButton("▶  Download All")
        self.btn_download_all.setFixedWidth(130)
        self.btn_download_all.setObjectName("btn_primary")
        self.btn_download_all.clicked.connect(self._on_download_all)
        ctrl_row.addWidget(self.btn_download_all)

        lay.addLayout(ctrl_row)

        # Output folder row
        folder_row = QHBoxLayout()
        folder_row.setSpacing(6)
        folder_row.addWidget(QLabel("Save to:"))
        self._output_dir_edit = QLineEdit()
        self._output_dir_edit.setPlaceholderText("Choose output folder…")
        self._output_dir_edit.setText(self._config.get("yt_output_dir", ""))
        self._output_dir_edit.textChanged.connect(
            lambda t: self._config.__setitem__("yt_output_dir", t) or self._save_config()
        )
        folder_row.addWidget(self._output_dir_edit, stretch=1)
        btn_browse = QPushButton("Browse")
        btn_browse.setFixedWidth(72)
        btn_browse.clicked.connect(self._browse_output_dir)
        folder_row.addWidget(btn_browse)
        lay.addLayout(folder_row)

        # Format indicator
        if self._ffmpeg_path:
            fmt_text = "🎵  Format: MP3 320 kbps  (ffmpeg detected)"
            fmt_color = "#00cc66"
        else:
            fmt_text = "🎵  Format: m4a (best quality)  — install ffmpeg for MP3 320 kbps"
            fmt_color = "#ffaa00"
        fmt_lbl = QLabel(fmt_text)
        fmt_lbl.setStyleSheet(f"color: {fmt_color}; font-size: 11px; padding: 2px 0;")
        lay.addWidget(fmt_lbl)

        # Queue table
        self._queue_table = QTableWidget(0, 4)
        self._queue_table.setHorizontalHeaderLabels(["Title", "Source", "Status", "Action"])
        hdr = self._queue_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._queue_table.verticalHeader().setDefaultSectionSize(28)
        self._queue_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._queue_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        lay.addWidget(self._queue_table, stretch=1)

        # Bottom action row
        bottom_row = QHBoxLayout()
        btn_import_sel = QPushButton("⬆  Import Selected (Done)")
        btn_import_sel.clicked.connect(self._on_import_selected)
        bottom_row.addWidget(btn_import_sel)
        btn_clear = QPushButton("Clear Done")
        btn_clear.clicked.connect(self._on_clear_done)
        bottom_row.addWidget(btn_clear)
        bottom_row.addStretch()
        lay.addLayout(bottom_row)

        return page

    # ── Subscriptions tab ──────────────────────────────────────────────

    def _build_subs_tab(self) -> QWidget:
        page   = QWidget()
        lay    = QVBoxLayout(page)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)

        # ── YouTube playlists ──────────────────────────────────────────
        yt_group = QGroupBox("YouTube Playlists")
        yt_lay   = QVBoxLayout(yt_group)
        yt_lay.setSpacing(6)

        self._yt_table = QTableWidget(0, 3)
        self._yt_table.setHorizontalHeaderLabels(["Label", "URL", ""])
        self._yt_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents)
        self._yt_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch)
        self._yt_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents)
        self._yt_table.verticalHeader().setDefaultSectionSize(26)
        self._yt_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        yt_lay.addWidget(self._yt_table)

        yt_btn_row = QHBoxLayout()
        btn_add_yt = QPushButton("+ Add YouTube Playlist")
        btn_add_yt.clicked.connect(self._on_add_yt_playlist)
        yt_btn_row.addWidget(btn_add_yt)
        yt_btn_row.addStretch()
        yt_lay.addLayout(yt_btn_row)
        lay.addWidget(yt_group)

        # ── Apple Music / Shazam ───────────────────────────────────────
        am_group = QGroupBox("Apple Music / Shazam")
        am_lay   = QVBoxLayout(am_group)
        am_lay.setSpacing(6)

        xml_row = QHBoxLayout()
        xml_row.addWidget(QLabel("Library XML:"))
        self._xml_edit = QLineEdit()
        self._xml_edit.setPlaceholderText("Path to iTunes Music Library.xml…")
        self._xml_edit.setText(self._config.get("apple_music_xml", ""))
        self._xml_edit.textChanged.connect(
            lambda t: self._config.__setitem__("apple_music_xml", t) or self._save_config()
        )
        xml_row.addWidget(self._xml_edit, stretch=1)
        btn_xml_browse = QPushButton("Browse")
        btn_xml_browse.setFixedWidth(72)
        btn_xml_browse.clicked.connect(self._browse_xml)
        xml_row.addWidget(btn_xml_browse)
        btn_xml_detect = QPushButton("Detect")
        btn_xml_detect.setFixedWidth(72)
        btn_xml_detect.clicked.connect(self._detect_xml)
        xml_row.addWidget(btn_xml_detect)
        am_lay.addLayout(xml_row)

        self._am_table = QTableWidget(0, 2)
        self._am_table.setHorizontalHeaderLabels(["Playlist", ""])
        self._am_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)
        self._am_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents)
        self._am_table.setMaximumHeight(150)
        self._am_table.verticalHeader().setDefaultSectionSize(26)
        self._am_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        am_lay.addWidget(self._am_table)

        am_btn_row = QHBoxLayout()
        btn_add_am = QPushButton("+ Add Playlist (XML)")
        btn_add_am.setToolTip(
            "Add a playlist by name from your iTunes / Apple Music XML library file")
        btn_add_am.clicked.connect(self._on_add_am_playlist)
        am_btn_row.addWidget(btn_add_am)
        btn_add_am_url = QPushButton("+ Add Apple Music URL")
        btn_add_am_url.setToolTip(
            "Subscribe to a public Apple Music playlist via its music.apple.com URL")
        btn_add_am_url.clicked.connect(self._on_add_am_url)
        am_btn_row.addWidget(btn_add_am_url)
        am_btn_row.addStretch()
        am_lay.addLayout(am_btn_row)
        lay.addWidget(am_group)

        # ── Sync controls ──────────────────────────────────────────────
        sync_row = QHBoxLayout()
        self.btn_sync = QPushButton("🔄  Sync All Subscriptions Now")
        self.btn_sync.setObjectName("btn_primary")
        self.btn_sync.clicked.connect(self._on_sync_now)
        sync_row.addWidget(self.btn_sync)
        self._sync_status_lbl = QLabel("")
        self._sync_status_lbl.setObjectName("meta_text")
        sync_row.addWidget(self._sync_status_lbl)
        sync_row.addStretch()
        lay.addLayout(sync_row)

        # ── Not found on YouTube ───────────────────────────────────────
        nf_group = QGroupBox("⚠  Not Found on YouTube")
        nf_lay   = QVBoxLayout(nf_group)
        nf_lay.setSpacing(4)

        self._nf_table = QTableWidget(0, 3)
        self._nf_table.setHorizontalHeaderLabels(["Title", "Artist", "Source"])
        self._nf_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)
        self._nf_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents)
        self._nf_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents)
        self._nf_table.setMaximumHeight(140)
        self._nf_table.verticalHeader().setDefaultSectionSize(26)
        self._nf_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        nf_lay.addWidget(self._nf_table)

        nf_btn_row = QHBoxLayout()
        btn_retry = QPushButton("Retry Selected")
        btn_retry.clicked.connect(self._on_retry_not_found)
        nf_btn_row.addWidget(btn_retry)
        btn_remove_nf = QPushButton("Remove Selected")
        btn_remove_nf.clicked.connect(self._on_remove_not_found)
        nf_btn_row.addWidget(btn_remove_nf)
        nf_btn_row.addStretch()
        nf_lay.addLayout(nf_btn_row)
        lay.addWidget(nf_group)

        lay.addStretch()

        # Populate subscription tables from saved config
        self._refresh_subscription_tables()

        return page

    # ── SoulSeek tab ───────────────────────────────────────────────────

    def _build_soulseek_tab(self) -> QWidget:
        page = QWidget()
        lay  = QVBoxLayout(page)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        # Watch folder row
        watch_row = QHBoxLayout()
        watch_row.addWidget(QLabel("Watch folder:"))
        self._watch_dir_edit = QLineEdit()
        self._watch_dir_edit.setPlaceholderText(
            "Path to SoulSeek completed downloads folder…")
        self._watch_dir_edit.setText(self._config.get("watch_dir", ""))
        watch_row.addWidget(self._watch_dir_edit, stretch=1)
        btn_watch_browse = QPushButton("Browse")
        btn_watch_browse.setFixedWidth(72)
        btn_watch_browse.clicked.connect(self._browse_watch_dir)
        watch_row.addWidget(btn_watch_browse)
        self.btn_watch_toggle = QPushButton("▶  Start Watching")
        self.btn_watch_toggle.setFixedWidth(130)
        self.btn_watch_toggle.clicked.connect(self._toggle_watcher)
        watch_row.addWidget(self.btn_watch_toggle)
        lay.addLayout(watch_row)

        # Status label
        self._watch_status_lbl = QLabel("Not watching.")
        self._watch_status_lbl.setObjectName("meta_text")
        lay.addWidget(self._watch_status_lbl)

        # Detected files table
        self._ss_table = QTableWidget(0, 4)
        self._ss_table.setHorizontalHeaderLabels(["Filename", "Size", "Status", "Action"])
        hdr = self._ss_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._ss_table.verticalHeader().setDefaultSectionSize(28)
        self._ss_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        lay.addWidget(self._ss_table, stretch=1)

        # Bottom row
        bottom_row = QHBoxLayout()
        btn_import_all = QPushButton("⬆  Import All New")
        btn_import_all.clicked.connect(self._on_import_all_new)
        bottom_row.addWidget(btn_import_all)
        bottom_row.addStretch()
        lay.addLayout(bottom_row)

        return page

    # ------------------------------------------------------------------
    # Queue tab — actions
    # ------------------------------------------------------------------

    def _on_add_url(self) -> None:
        url = self._url_edit.text().strip()
        if not url:
            return
        self._url_edit.clear()
        self._add_to_queue(url, source_label="Manual")

    def _add_to_queue(self, url: str, title: str = "", source_label: str = "Manual") -> None:
        """Add a URL to the queue list and insert a row in the table."""
        item = {
            "url":          url,
            "title":        title or url,
            "source_label": source_label,
            "status":       _STATUS_PENDING,
            "file_path":    None,
        }
        self._queue.append(item)
        row = self._queue_table.rowCount()
        self._queue_table.insertRow(row)

        title_item = QTableWidgetItem(item["title"])
        title_item.setToolTip(url)
        title_item.setData(Qt.ItemDataRole.UserRole, len(self._queue) - 1)  # queue index
        self._queue_table.setItem(row, 0, title_item)
        self._queue_table.setItem(row, 1, QTableWidgetItem(source_label))
        status_item = QTableWidgetItem(_STATUS_PENDING)
        status_item.setForeground(_COLOR_PENDING)
        self._queue_table.setItem(row, 2, status_item)
        self._queue_table.setItem(row, 3, QTableWidgetItem(""))

    def _on_download_all(self) -> None:
        self._start_next_download()

    def _start_next_download(self) -> None:
        """Start the next pending download if none is currently running."""
        if self._worker is not None and self._worker.isRunning():
            return

        output_dir = self._output_dir_edit.text().strip()
        if not output_dir:
            return  # no folder configured — silently wait

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Find first pending queue item
        for i, item in enumerate(self._queue):
            if item["status"] == _STATUS_PENDING:
                self._start_download_item(i, output_path)
                return

    def _start_download_item(self, queue_idx: int, output_dir: Path) -> None:
        item = self._queue[queue_idx]
        item["status"] = _STATUS_DOWNLOADING
        self._active_url = item["url"]

        # Update table row
        row = self._row_for_queue_idx(queue_idx)
        if row >= 0:
            status_item = QTableWidgetItem("⬇  0%")
            status_item.setForeground(_COLOR_ACTIVE)
            self._queue_table.setItem(row, 2, status_item)

        worker = DownloadWorker(
            item["url"], output_dir,
            prefer_mp3=True,
            ffmpeg_path=self._ffmpeg_path,
        )
        worker.progress.connect(self._on_dl_progress)
        worker.title_found.connect(self._on_dl_title_found)
        worker.done.connect(self._on_dl_done)
        worker.error.connect(self._on_dl_error)
        self._worker = worker
        worker.start()

    def _on_dl_progress(self, url: str, fraction: float) -> None:
        row = self._row_for_active_url(url)
        if row >= 0:
            pct = int(fraction * 100)
            status_item = QTableWidgetItem(f"⬇  {pct}%")
            status_item.setForeground(_COLOR_ACTIVE)
            self._queue_table.setItem(row, 2, status_item)

    def _on_dl_title_found(self, url: str, title: str) -> None:
        row = self._row_for_active_url(url)
        if row >= 0:
            self._queue_table.item(row, 0).setText(title)
            # Update queue item title
            for item in self._queue:
                if item["url"] == url and item["status"] == _STATUS_DOWNLOADING:
                    item["title"] = title
                    break

    def _on_dl_done(self, url: str, file_path: str) -> None:
        row = self._row_for_active_url(url)
        for item in self._queue:
            if item["url"] == url and item["status"] == _STATUS_DOWNLOADING:
                item["status"] = _STATUS_DONE
                item["file_path"] = file_path
                break

        if row >= 0:
            status_item = QTableWidgetItem(_STATUS_DONE)
            status_item.setForeground(_COLOR_DONE)
            self._queue_table.setItem(row, 2, status_item)

            btn = QPushButton("⬆ Import")
            btn.setFixedHeight(22)
            fp = file_path
            btn.clicked.connect(lambda: self.import_requested.emit(fp))
            self._queue_table.setCellWidget(row, 3, btn)

        title = ""
        for item in self._queue:
            if item.get("file_path") == file_path:
                title = item.get("title", "")
                break
        self.notify.emit("Download complete", title or Path(file_path).stem)

        self._worker = None
        self._active_url = None
        self._start_next_download()

    def _on_dl_error(self, url: str, message: str) -> None:
        row = self._row_for_active_url(url)
        # Make age-restriction errors actionable
        if "Sign in to confirm your age" in message or "age" in message.lower():
            display = "⚠ Age-restricted"
            tooltip = (
                "This video requires age verification.\n"
                "yt-dlp cannot download it without your browser cookies.\n\n"
                "Fix: run once in a terminal:\n"
                "  yt-dlp --cookies-from-browser chrome <url>\n"
                "Or export cookies.txt from your browser and set the path\n"
                "in the cookies field (coming soon)."
            )
        else:
            display = "⚠ Error"
            tooltip = message

        for item in self._queue:
            if item["url"] == url and item["status"] == _STATUS_DOWNLOADING:
                item["status"] = display
                break
        if row >= 0:
            status_item = QTableWidgetItem(display)
            status_item.setForeground(_COLOR_ERROR)
            status_item.setToolTip(tooltip)
            self._queue_table.setItem(row, 2, status_item)

        self._worker = None
        self._active_url = None
        self._start_next_download()

    def _on_import_selected(self) -> None:
        selected_rows = {idx.row() for idx in self._queue_table.selectedIndexes()}
        # If nothing selected, import every done row as a convenience
        import_all = not selected_rows
        for row in range(self._queue_table.rowCount()):
            status_item = self._queue_table.item(row, 2)
            if status_item and status_item.text() == _STATUS_DONE:
                if import_all or row in selected_rows:
                    q_idx = self._queue_idx_for_row(row)
                    if q_idx >= 0 and self._queue[q_idx].get("file_path"):
                        self.import_requested.emit(self._queue[q_idx]["file_path"])

    def _on_clear_done(self) -> None:
        rows_to_remove = [
            r for r in range(self._queue_table.rowCount() - 1, -1, -1)
            if self._queue_table.item(r, 2)
               and self._queue_table.item(r, 2).text() == _STATUS_DONE
        ]
        for r in rows_to_remove:
            self._queue_table.removeRow(r)
        self._queue = [
            item for item in self._queue
            if item["status"] != _STATUS_DONE
        ]

    # ------------------------------------------------------------------
    # Subscriptions tab — actions
    # ------------------------------------------------------------------

    def _on_add_yt_playlist(self) -> None:
        url, ok = QInputDialog.getText(
            self, "Add YouTube Playlist", "Playlist URL:")
        if not ok or not url.strip():
            return
        label, ok2 = QInputDialog.getText(
            self, "Label", "Name for this playlist (shown in queue Source column):")
        if not ok2:
            return
        label = label.strip() or url.strip()
        subs = self._config.setdefault("subscriptions", [])
        subs.append({"type": "youtube", "url": url.strip(), "label": label})
        self._save_config()
        self._refresh_subscription_tables()

    def _on_add_am_playlist(self) -> None:
        if not self._xml_edit.text().strip():
            self._detect_xml()
            if not self._xml_edit.text().strip():
                return
        name, ok = QInputDialog.getText(
            self, "Apple Music Playlist",
            "Playlist name (exactly as in Apple Music, e.g. 'Shazam Library'):")
        if not ok or not name.strip():
            return
        subs = self._config.setdefault("subscriptions", [])
        subs.append({"type": "apple_music", "playlist": name.strip()})
        self._save_config()
        self._refresh_subscription_tables()

    def _on_add_am_url(self) -> None:
        url, ok = QInputDialog.getText(
            self,
            "Add Apple Music Playlist URL",
            "Paste the music.apple.com playlist URL:\n"
            "(e.g. https://music.apple.com/us/playlist/house/pl.u-…)")
        if not ok or not url.strip():
            return
        url = url.strip()
        if "music.apple.com" not in url:
            QMessageBox.warning(
                self, "Invalid URL",
                "Please paste a music.apple.com URL.\n"
                "Example: https://music.apple.com/us/playlist/house/pl.u-…")
            return
        label, ok2 = QInputDialog.getText(
            self, "Label", "Name for this playlist (shown in queue Source column):")
        if not ok2:
            return
        label = label.strip() or url
        subs = self._config.setdefault("subscriptions", [])
        subs.append({"type": "apple_music_url", "url": url, "label": label})
        self._save_config()
        self._refresh_subscription_tables()

    def _on_sync_now(self) -> None:
        if self._sync_worker and self._sync_worker.isRunning():
            return
        sources = self._build_sources()
        if not sources:
            self._sync_status_lbl.setText("No subscriptions configured.")
            return
        self._sync_status_lbl.setText("Syncing…")
        self.btn_sync.setEnabled(False)
        worker = PlaylistSyncWorker(sources, load_sync_state())
        worker.new_track.connect(self._on_sync_new_track)
        worker.track_not_found.connect(self._on_sync_not_found)
        worker.all_done.connect(self._on_sync_all_done)
        self._sync_worker = worker
        worker.start()

    def _on_sync_new_track(self, track: dict) -> None:
        url = track.get("url", "")
        if not url:
            return
        title  = track.get("title", url)
        artist = track.get("artist", "")
        if artist:
            title = f"{artist} — {title}"
        label = track.get("source_label", "Subscription")
        self._add_to_queue(url, title=title, source_label=label)

    def _on_sync_not_found(self, track: dict) -> None:
        self._not_found.append(track)
        row = self._nf_table.rowCount()
        self._nf_table.insertRow(row)
        self._nf_table.setItem(row, 0, QTableWidgetItem(track.get("title", "")))
        self._nf_table.setItem(row, 1, QTableWidgetItem(track.get("artist", "")))
        self._nf_table.setItem(row, 2, QTableWidgetItem(track.get("source_label", "")))

    def _on_sync_all_done(self) -> None:
        self.btn_sync.setEnabled(True)
        found = len([item for item in self._queue
                     if item["source_label"] != "Manual"])
        self._sync_status_lbl.setText(
            f"Sync complete — {found} new track(s) queued."
        )
        self.notify.emit("Playlist sync complete",
                         f"{found} new track(s) added to queue")
        if found > 0:
            self._start_next_download()

    def _on_retry_not_found(self) -> None:
        rows = sorted({idx.row() for idx in self._nf_table.selectedIndexes()},
                      reverse=True)
        for row in rows:
            if row < len(self._not_found):
                track = self._not_found.pop(row)
                self._nf_table.removeRow(row)
                # Re-queue for a fresh sync search
                self._on_sync_new_track(track)

    def _on_remove_not_found(self) -> None:
        rows = sorted({idx.row() for idx in self._nf_table.selectedIndexes()},
                      reverse=True)
        for row in rows:
            if row < len(self._not_found):
                self._not_found.pop(row)
                self._nf_table.removeRow(row)

    def _refresh_subscription_tables(self) -> None:
        """Repopulate both subscription tables from config."""
        self._yt_table.setRowCount(0)
        self._am_table.setRowCount(0)
        for sub in self._config.get("subscriptions", []):
            if sub.get("type") == "youtube":
                self._add_yt_row(sub["url"], sub.get("label", sub["url"]))
            elif sub.get("type") == "apple_music":
                self._add_am_row(sub["playlist"])
            elif sub.get("type") == "apple_music_url":
                self._add_am_row(
                    sub.get("label", sub["url"]),
                    key=sub["url"],
                    sub_type="apple_music_url",
                    tooltip=sub["url"],
                )

    @staticmethod
    def _make_remove_btn() -> QPushButton:
        """Create a visible red ✕ remove button for subscription rows."""
        btn = QPushButton("✕ Remove")
        btn.setFixedHeight(22)
        btn.setStyleSheet(
            "QPushButton { background: #5a1a1a; color: #ff6666; border: 1px solid #882222;"
            " border-radius: 3px; padding: 0 6px; font-size: 11px; }"
            "QPushButton:hover { background: #7a2222; color: #ff9999; border-color: #cc4444; }"
        )
        return btn

    def _add_yt_row(self, url: str, label: str) -> None:
        row = self._yt_table.rowCount()
        self._yt_table.insertRow(row)
        self._yt_table.setItem(row, 0, QTableWidgetItem(label))
        url_item = QTableWidgetItem(url)
        url_item.setToolTip(url)
        self._yt_table.setItem(row, 1, url_item)
        btn_rm = self._make_remove_btn()
        btn_rm.clicked.connect(lambda: self._remove_subscription("youtube", url))
        self._yt_table.setCellWidget(row, 2, btn_rm)

    def _add_am_row(
        self,
        display: str,
        key: str | None = None,
        sub_type: str = "apple_music",
        tooltip: str = "",
    ) -> None:
        """Add a row to the Apple Music table. ``key`` is the removal key (playlist name or URL)."""
        row = self._am_table.rowCount()
        self._am_table.insertRow(row)
        item = QTableWidgetItem(display)
        if tooltip:
            item.setToolTip(tooltip)
        self._am_table.setItem(row, 0, item)
        btn_rm = self._make_remove_btn()
        rm_key = key if key is not None else display
        btn_rm.clicked.connect(
            lambda: self._remove_subscription(sub_type, rm_key))
        self._am_table.setCellWidget(row, 1, btn_rm)

    def _remove_subscription(self, sub_type: str, key: str) -> None:
        subs = self._config.get("subscriptions", [])
        if sub_type == "youtube":
            self._config["subscriptions"] = [
                s for s in subs
                if not (s.get("type") == "youtube" and s.get("url") == key)
            ]
        elif sub_type == "apple_music_url":
            self._config["subscriptions"] = [
                s for s in subs
                if not (s.get("type") == "apple_music_url" and s.get("url") == key)
            ]
        else:
            self._config["subscriptions"] = [
                s for s in subs
                if not (s.get("type") == "apple_music" and s.get("playlist") == key)
            ]
        self._save_config()
        self._refresh_subscription_tables()

    def _build_sources(self) -> list:
        """Build source objects from config subscriptions."""
        sources = []
        xml = self._xml_edit.text().strip()
        for sub in self._config.get("subscriptions", []):
            if sub.get("type") == "youtube":
                src = YouTubePlaylistSource(sub["url"], sub.get("label", sub["url"]))
                sources.append(src)
            elif sub.get("type") == "apple_music" and xml:
                src = AppleMusicSource(xml, sub["playlist"])
                sources.append(src)
            elif sub.get("type") == "apple_music_url":
                src = AppleMusicURLSource(sub["url"], sub.get("label", sub["url"]))
                sources.append(src)
        return sources

    # ------------------------------------------------------------------
    # SoulSeek tab — actions
    # ------------------------------------------------------------------

    def _toggle_watcher(self) -> None:
        if self._watcher.is_watching:
            self._watcher.stop()
            self.btn_watch_toggle.setText("▶  Start Watching")
            self._watch_status_lbl.setText("Stopped.")
        else:
            self._start_watcher()

    def _start_watcher(self) -> None:
        watch_dir = self._watch_dir_edit.text().strip()
        if not watch_dir:
            self._watch_status_lbl.setText("Set a folder to watch first.")
            return
        self._config["watch_dir"] = watch_dir
        self._save_config()
        if self._watcher.start(watch_dir):
            self.btn_watch_toggle.setText("⏹  Stop Watching")
            self._watch_status_lbl.setText(
                f"● Watching: {watch_dir}")
        else:
            self._watch_status_lbl.setText(
                f"⚠  Folder not found: {watch_dir}")

    def _on_file_detected(self, file_path: str) -> None:
        p = Path(file_path)
        try:
            size_mb = p.stat().st_size / (1024 * 1024)
        except OSError:
            size_mb = 0.0

        self._watcher_items.append(
            {"file_path": file_path, "size_mb": size_mb, "imported": False}
        )

        row = self._ss_table.rowCount()
        self._ss_table.insertRow(row)
        self._ss_table.setItem(row, 0, QTableWidgetItem(p.name))
        self._ss_table.setItem(row, 1, QTableWidgetItem(f"{size_mb:.1f} MB"))
        status_item = QTableWidgetItem("New")
        status_item.setForeground(_COLOR_ACTIVE)
        self._ss_table.setItem(row, 2, status_item)

        btn = QPushButton("⬆ Import")
        btn.setFixedHeight(22)
        fp = file_path
        item_idx = len(self._watcher_items) - 1
        btn.clicked.connect(lambda: self._import_watcher_item(item_idx, row))
        self._ss_table.setCellWidget(row, 3, btn)

        # Update status label
        n_new = sum(1 for it in self._watcher_items if not it["imported"])
        self._watch_status_lbl.setText(
            f"● Watching — {n_new} new file(s) detected"
        )

    def _import_watcher_item(self, item_idx: int, row: int) -> None:
        if item_idx >= len(self._watcher_items):
            return
        item = self._watcher_items[item_idx]
        if item["imported"]:
            return
        item["imported"] = True
        status_item = QTableWidgetItem("✓ Imported")
        status_item.setForeground(_COLOR_DONE)
        self._ss_table.setItem(row, 2, status_item)
        self._ss_table.removeCellWidget(row, 3)
        self._ss_table.setItem(row, 3, QTableWidgetItem(""))
        self.import_requested.emit(item["file_path"])

    def _on_import_all_new(self) -> None:
        for idx, item in enumerate(self._watcher_items):
            if not item["imported"]:
                # Find the corresponding table row
                for row in range(self._ss_table.rowCount()):
                    name_item = self._ss_table.item(row, 0)
                    if name_item and name_item.text() == Path(item["file_path"]).name:
                        self._import_watcher_item(idx, row)
                        break

    # ------------------------------------------------------------------
    # Folder browse helpers
    # ------------------------------------------------------------------

    def _browse_output_dir(self) -> None:
        d = QFileDialog.getExistingDirectory(
            self, "Choose Output Folder",
            self._output_dir_edit.text() or str(Path.home()))
        if d:
            self._output_dir_edit.setText(d)

    def _browse_watch_dir(self) -> None:
        d = QFileDialog.getExistingDirectory(
            self, "Choose SoulSeek Folder",
            self._watch_dir_edit.text() or str(Path.home()))
        if d:
            self._watch_dir_edit.setText(d)

    def _browse_xml(self) -> None:
        f, _ = QFileDialog.getOpenFileName(
            self, "Open iTunes Music Library XML",
            self._xml_edit.text() or str(Path.home()),
            "XML Files (*.xml)")
        if f:
            self._xml_edit.setText(f)

    def _detect_xml(self) -> None:
        path = detect_apple_music_xml()
        if path:
            self._xml_edit.setText(path)
        else:
            QMessageBox.information(
                self,
                "iTunes XML Not Found",
                "Could not auto-detect your iTunes Music Library.xml.\n\n"
                "Common locations:\n"
                "  • ~/Music/iTunes/iTunes Music Library.xml\n"
                "  • ~/Music/Music/Music Library.xml\n\n"
                "If you use Apple Music for Windows, open Apple Music,\n"
                "go to Edit → Preferences → Files, and enable\n"
                "\"Keep Music Media folder organised\".\n\n"
                "Then use the Browse button to locate the file manually.\n\n"
                "Tip: For public Apple Music playlists, use\n"
                "\"+ Add Apple Music URL\" instead.",
            )

    # ------------------------------------------------------------------
    # Config persistence
    # ------------------------------------------------------------------

    def _load_config(self) -> None:
        try:
            if CONFIG_FILE.exists():
                with open(CONFIG_FILE) as f:
                    self._config = json.load(f)
        except Exception:
            self._config = {}

    def _save_config(self) -> None:
        try:
            CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(CONFIG_FILE, "w") as f:
                json.dump(self._config, f, indent=2)
        except Exception as exc:
            print(f"[downloads_tab] Could not save config: {exc}")

    # ------------------------------------------------------------------
    # Startup sync (called by MainWindow after 2s delay)
    # ------------------------------------------------------------------

    def run_startup_sync(self) -> None:
        """Trigger a background playlist sync without changing to this tab."""
        sources = self._build_sources()
        if not sources:
            return
        worker = PlaylistSyncWorker(sources, load_sync_state())
        worker.new_track.connect(self._on_sync_new_track)
        worker.track_not_found.connect(self._on_sync_not_found)
        worker.all_done.connect(self._on_sync_all_done)
        self._sync_worker = worker
        worker.start()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _row_for_active_url(self, url: str) -> int:
        """Find the table row for the currently downloading URL."""
        for row in range(self._queue_table.rowCount()):
            title_item = self._queue_table.item(row, 0)
            if title_item and title_item.toolTip() == url:
                return row
        return -1

    def _row_for_queue_idx(self, idx: int) -> int:
        """Find table row by queue index stored in item UserRole."""
        for row in range(self._queue_table.rowCount()):
            title_item = self._queue_table.item(row, 0)
            if title_item and title_item.data(Qt.ItemDataRole.UserRole) == idx:
                return row
        return -1

    def _queue_idx_for_row(self, row: int) -> int:
        title_item = self._queue_table.item(row, 0)
        if title_item:
            val = title_item.data(Qt.ItemDataRole.UserRole)
            if isinstance(val, int):
                return val
        return -1
