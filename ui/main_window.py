"""
DJ Track Analyzer - Main Window UI
PyQt6-based desktop application for browsing and analyzing DJ tracks
"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QPushButton, QLabel, QLineEdit, QTableWidget, QTableWidgetItem,
    QFileDialog, QHeaderView, QProgressBar, QStatusBar, QSlider
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from pathlib import Path
import sys
import os

# Add parent directory to path to import analyzer
sys.path.insert(0, str(Path(__file__).parent.parent))
from analyzer.audio_analyzer import AudioAnalyzer
from ui.waveform_dj import WaveformDJ
from ui.audio_player import AudioPlayer


class AnalysisThread(QThread):
    """Background thread for analyzing tracks"""
    progress = pyqtSignal(int, int)  # current, total
    finished = pyqtSignal(dict)  # analysis results
    error = pyqtSignal(str)  # error message

    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path
        self.analyzer = AudioAnalyzer()

    def run(self):
        try:
            results = self.analyzer.analyze_track(self.file_path)
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    """Main application window"""

    def __init__(self):
        super().__init__()
        self.current_track = None
        self.current_library_path = None
        self.analyzer = AudioAnalyzer()
        self.audio_player = AudioPlayer()

        # Connect player signals
        self.audio_player.position_changed.connect(self.on_playback_position_changed)
        self.audio_player.playback_finished.connect(self.on_playback_finished)

        # Set default volume
        self.audio_player.set_volume(0.7)

        self.setWindowTitle("DJ Track Analyzer")
        self.setGeometry(100, 100, 1400, 800)

        self.init_ui()

    def init_ui(self):
        """Initialize the user interface"""
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Top toolbar
        toolbar = self.create_toolbar()
        main_layout.addLayout(toolbar)

        # Main content area (splitter with 3 panels)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left panel: Track browser
        left_panel = self.create_track_browser()
        splitter.addWidget(left_panel)

        # Right panel: Track details
        right_panel = self.create_track_details()
        splitter.addWidget(right_panel)

        # Set splitter sizes (30% left, 70% right)
        splitter.setSizes([400, 1000])

        main_layout.addWidget(splitter)

        # Status bar
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("Ready - Load a track or folder to begin")

    def create_toolbar(self):
        """Create top toolbar with actions"""
        toolbar_layout = QHBoxLayout()

        # Load track button
        self.btn_load_track = QPushButton("Load Track")
        self.btn_load_track.setFixedHeight(35)
        self.btn_load_track.clicked.connect(self.load_single_track)
        toolbar_layout.addWidget(self.btn_load_track)

        # Load folder button
        self.btn_load_folder = QPushButton("Load Folder")
        self.btn_load_folder.setFixedHeight(35)
        self.btn_load_folder.clicked.connect(self.load_folder)
        toolbar_layout.addWidget(self.btn_load_folder)

        # Search box
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search tracks...")
        self.search_box.setFixedHeight(35)
        self.search_box.textChanged.connect(self.filter_tracks)
        toolbar_layout.addWidget(self.search_box)

        # Spacer
        toolbar_layout.addStretch()

        return toolbar_layout

    def create_track_browser(self):
        """Create left panel with track list"""
        browser_widget = QWidget()
        browser_layout = QVBoxLayout(browser_widget)
        browser_layout.setContentsMargins(0, 0, 0, 0)

        # Title
        title = QLabel("Track Library")
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title.setFont(title_font)
        browser_layout.addWidget(title)

        # Track table
        self.track_table = QTableWidget()
        self.track_table.setColumnCount(3)
        self.track_table.setHorizontalHeaderLabels(["Track", "BPM", "Key"])

        # Table styling
        header = self.track_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.track_table.setColumnWidth(1, 60)
        self.track_table.setColumnWidth(2, 60)

        self.track_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.track_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.track_table.itemSelectionChanged.connect(self.on_track_selected)

        browser_layout.addWidget(self.track_table)

        # Track count label
        self.track_count_label = QLabel("0 tracks")
        browser_layout.addWidget(self.track_count_label)

        return browser_widget

    def create_track_details(self):
        """Create right panel with track details"""
        details_widget = QWidget()
        details_layout = QVBoxLayout(details_widget)
        details_layout.setContentsMargins(0, 0, 0, 0)

        # Track info section
        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)

        # Track title
        self.lbl_track_title = QLabel("No track selected")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        self.lbl_track_title.setFont(title_font)
        info_layout.addWidget(self.lbl_track_title)

        # Artist
        self.lbl_artist = QLabel("")
        artist_font = QFont()
        artist_font.setPointSize(11)
        self.lbl_artist.setFont(artist_font)
        info_layout.addWidget(self.lbl_artist)

        details_layout.addWidget(info_widget)

        # Analysis info grid
        analysis_widget = QWidget()
        analysis_layout = QHBoxLayout(analysis_widget)

        # BPM
        bpm_widget = self.create_info_box("BPM", "--")
        self.lbl_bpm_value = bpm_widget.findChild(QLabel, "value")
        analysis_layout.addWidget(bpm_widget)

        # Key
        key_widget = self.create_info_box("Key", "--")
        self.lbl_key_value = key_widget.findChild(QLabel, "value")
        analysis_layout.addWidget(key_widget)

        # Camelot
        camelot_widget = self.create_info_box("Camelot", "--")
        self.lbl_camelot_value = camelot_widget.findChild(QLabel, "value")
        analysis_layout.addWidget(camelot_widget)

        # Energy
        energy_widget = self.create_info_box("Energy", "--")
        self.lbl_energy_value = energy_widget.findChild(QLabel, "value")
        analysis_layout.addWidget(energy_widget)

        details_layout.addWidget(analysis_widget)

        # DJ-style waveform widget (like Rekordbox/VirtualDJ)
        self.waveform_widget = WaveformDJ()
        self.waveform_widget.position_clicked.connect(self.on_waveform_clicked)
        details_layout.addWidget(self.waveform_widget)

        # Audio info section
        audio_info_widget = QWidget()
        audio_info_layout = QHBoxLayout(audio_info_widget)

        # Format
        format_widget = self.create_info_box("Format", "--", small=True)
        self.lbl_format_value = format_widget.findChild(QLabel, "value")
        audio_info_layout.addWidget(format_widget)

        # Bitrate
        bitrate_widget = self.create_info_box("Bitrate", "--", small=True)
        self.lbl_bitrate_value = bitrate_widget.findChild(QLabel, "value")
        audio_info_layout.addWidget(bitrate_widget)

        # Sample Rate
        samplerate_widget = self.create_info_box("Sample Rate", "--", small=True)
        self.lbl_samplerate_value = samplerate_widget.findChild(QLabel, "value")
        audio_info_layout.addWidget(samplerate_widget)

        # Duration
        duration_widget = self.create_info_box("Duration", "--", small=True)
        self.lbl_duration_value = duration_widget.findChild(QLabel, "value")
        audio_info_layout.addWidget(duration_widget)

        details_layout.addWidget(audio_info_widget)

        # Player controls
        player_widget = QWidget()
        player_layout = QHBoxLayout(player_widget)
        player_layout.setContentsMargins(0, 10, 0, 0)

        self.btn_play = QPushButton("▶ Play")
        self.btn_play.setFixedHeight(40)
        self.btn_play.setFixedWidth(100)
        self.btn_play.setEnabled(False)
        self.btn_play.clicked.connect(self.toggle_playback)
        player_layout.addWidget(self.btn_play)

        self.btn_stop = QPushButton("⏹ Stop")
        self.btn_stop.setFixedHeight(40)
        self.btn_stop.setFixedWidth(100)
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_playback)
        player_layout.addWidget(self.btn_stop)

        # Volume control
        volume_label = QLabel("Volume:")
        player_layout.addWidget(volume_label)

        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setMinimum(0)
        self.volume_slider.setMaximum(100)
        self.volume_slider.setValue(70)
        self.volume_slider.setFixedWidth(150)
        self.volume_slider.valueChanged.connect(self.on_volume_changed)
        player_layout.addWidget(self.volume_slider)

        self.volume_label = QLabel("70%")
        player_layout.addWidget(self.volume_label)

        player_layout.addStretch()

        details_layout.addWidget(player_widget)

        # Spacer
        details_layout.addStretch()

        return details_widget

    def create_info_box(self, label_text, value_text, small=False):
        """Create an info box widget"""
        widget = QWidget()
        widget.setStyleSheet("background-color: #1e1e1e; border-radius: 5px; padding: 10px;")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)

        label = QLabel(label_text)
        label.setStyleSheet("color: #888; font-size: 10px;")
        layout.addWidget(label)

        value = QLabel(value_text)
        value.setObjectName("value")
        if small:
            value.setStyleSheet("color: white; font-size: 16px; font-weight: bold;")
        else:
            value.setStyleSheet("color: white; font-size: 24px; font-weight: bold;")
        layout.addWidget(value)

        return widget

    def load_single_track(self):
        """Load and analyze a single track"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Audio File",
            "",
            "Audio Files (*.mp3 *.wav *.flac *.m4a *.ogg);;All Files (*)"
        )

        if file_path:
            self.analyze_track(file_path)

    def load_folder(self):
        """Load all tracks from a folder"""
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "Select Music Folder",
            ""
        )

        if folder_path:
            self.current_library_path = folder_path
            self.scan_folder(folder_path)

    def scan_folder(self, folder_path):
        """Scan folder for audio files"""
        self.statusBar.showMessage("Scanning folder...")

        # Find all audio files
        audio_extensions = {'.mp3', '.wav', '.flac', '.m4a', '.ogg'}
        audio_files = []

        for root, dirs, files in os.walk(folder_path):
            for file in files:
                if Path(file).suffix.lower() in audio_extensions:
                    audio_files.append(os.path.join(root, file))

        # Add to table (without analysis for now - analyze on demand)
        self.track_table.setRowCount(len(audio_files))

        for i, file_path in enumerate(audio_files):
            filename = Path(file_path).name

            # Track name
            item = QTableWidgetItem(filename)
            item.setData(Qt.ItemDataRole.UserRole, file_path)  # Store full path
            self.track_table.setItem(i, 0, item)

            # BPM (placeholder)
            self.track_table.setItem(i, 1, QTableWidgetItem("--"))

            # Key (placeholder)
            self.track_table.setItem(i, 2, QTableWidgetItem("--"))

        self.track_count_label.setText(f"{len(audio_files)} tracks")
        self.statusBar.showMessage(f"Loaded {len(audio_files)} tracks from folder")

    def analyze_track(self, file_path):
        """Analyze a track in background thread"""
        self.statusBar.showMessage(f"Analyzing: {Path(file_path).name}...")

        # Create and start analysis thread
        self.analysis_thread = AnalysisThread(file_path)
        self.analysis_thread.finished.connect(self.on_analysis_complete)
        self.analysis_thread.error.connect(self.on_analysis_error)
        self.analysis_thread.start()

    def on_analysis_complete(self, results):
        """Handle completed analysis"""
        self.current_track = results
        self.display_track_info(results)
        self.statusBar.showMessage(f"Analysis complete: {results['filename']}")

    def on_analysis_error(self, error_msg):
        """Handle analysis error"""
        self.statusBar.showMessage(f"Error: {error_msg}")

    def display_track_info(self, results):
        """Display track information in UI"""
        # Track title and artist
        title = results['metadata']['title'] or results['filename']
        artist = results['metadata']['artist'] or "Unknown Artist"

        self.lbl_track_title.setText(title)
        self.lbl_artist.setText(artist)

        # BPM
        bpm = results['bpm']
        self.lbl_bpm_value.setText(str(bpm) if bpm else "--")

        # Key
        key = results['key']['notation']
        self.lbl_key_value.setText(key)

        # Camelot
        camelot = results['key']['camelot']
        self.lbl_camelot_value.setText(camelot)

        # Energy
        energy = results['energy']['level']
        energy_desc = results['energy']['description']
        self.lbl_energy_value.setText(f"{energy}/10")

        # Audio info
        audio_info = results['audio_info']
        self.lbl_format_value.setText(audio_info['format'])
        self.lbl_bitrate_value.setText(f"{audio_info['bitrate']} kbps")
        self.lbl_samplerate_value.setText(f"{audio_info['sample_rate']} Hz")

        # Duration
        duration = int(results['duration'])
        minutes = duration // 60
        seconds = duration % 60
        self.lbl_duration_value.setText(f"{minutes}:{seconds:02d}")

        # Load audio file into player FIRST
        file_path = results['file_path']
        self.statusBar.showMessage("Loading audio...")

        if self.audio_player.load(file_path):
            self.audio_player.set_duration(results['duration'])

            # Generate DJ-style waveform (fast and clean)
            self.statusBar.showMessage("Generating waveform...")
            self.waveform_widget.set_waveform_from_file(file_path)

            # Enable controls
            self.btn_play.setEnabled(True)
            self.btn_stop.setEnabled(True)
            self.btn_play.setText("▶ Play")

            self.statusBar.showMessage(f"Ready: {results['filename']}")
        else:
            self.statusBar.showMessage("Error loading audio file")

    def on_track_selected(self):
        """Handle track selection from table"""
        selected_items = self.track_table.selectedItems()
        if selected_items:
            # Get the file path from first column
            row = selected_items[0].row()
            file_path_item = self.track_table.item(row, 0)
            file_path = file_path_item.data(Qt.ItemDataRole.UserRole)

            if file_path:
                self.analyze_track(file_path)

    def filter_tracks(self, text):
        """Filter tracks based on search text"""
        for row in range(self.track_table.rowCount()):
            item = self.track_table.item(row, 0)
            if item:
                match = text.lower() in item.text().lower()
                self.track_table.setRowHidden(row, not match)

    # Audio Player Controls

    def toggle_playback(self):
        """Toggle play/pause"""
        if self.audio_player.is_playing:
            self.audio_player.pause()
            self.btn_play.setText("▶ Play")
        else:
            self.audio_player.resume() if self.audio_player.current_file else self.audio_player.play()
            self.btn_play.setText("⏸ Pause")

    def stop_playback(self):
        """Stop playback"""
        self.audio_player.stop()
        self.btn_play.setText("▶ Play")
        self.waveform_widget.set_playback_position(0.0)

    def on_playback_position_changed(self, position):
        """Update waveform playhead when position changes"""
        self.waveform_widget.set_playback_position(position)

    def on_playback_finished(self):
        """Handle playback finished"""
        self.btn_play.setText("▶ Play")
        self.waveform_widget.set_playback_position(0.0)

    def on_waveform_clicked(self, position):
        """Handle waveform click to seek"""
        self.audio_player.seek(position)
        self.waveform_widget.set_playback_position(position)

    def on_volume_changed(self, value):
        """Handle volume slider change"""
        volume = value / 100.0
        self.audio_player.set_volume(volume)
        self.volume_label.setText(f"{value}%")


if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    # Set dark theme
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())
