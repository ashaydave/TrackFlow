# ui/styles.py
"""
Centralized stylesheet for DJ Track Analyzer.
Cyberpunk / dark DJ software aesthetic.
"""

COLORS = {
    'bg':           '#0a0a0f',
    'panel':        '#0f0f1a',
    'surface':      '#151525',
    'surface2':     '#1a1a2e',
    'accent':       '#0088ff',
    'accent2':      '#00ccff',
    'accent_dim':   '#004488',
    'text':         '#ffffff',
    'text2':        '#8899bb',
    'text3':        '#445566',
    'border':       '#1a2233',
    'hover':        '#1a1a3a',
    'success':      '#00ff88',
    'warning':      '#ffaa00',
    'error':        '#ff4444',
    'waveform_bg':  '#080810',
}

STYLESHEET = """
/* ─── Base ─────────────────────────────────────────────── */
QMainWindow, QWidget {
    background-color: #0a0a0f;
    color: #ffffff;
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 13px;
}

/* ─── Buttons ───────────────────────────────────────────── */
QPushButton {
    background-color: #151525;
    color: #ffffff;
    border: 1px solid #1a2233;
    border-radius: 4px;
    padding: 6px 14px;
    font-size: 12px;
    font-weight: 500;
}
QPushButton:hover {
    background-color: #1a1a3a;
    border-color: #0088ff;
    color: #00ccff;
}
QPushButton:pressed {
    background-color: #004488;
    border-color: #0088ff;
}
QPushButton:disabled {
    color: #445566;
    border-color: #1a2233;
    background-color: #0f0f1a;
}
QPushButton#btn_primary {
    background-color: #0055bb;
    border-color: #0088ff;
    color: #ffffff;
    font-weight: 600;
}
QPushButton#btn_primary:hover {
    background-color: #0066dd;
    border-color: #00ccff;
}
QPushButton#btn_play {
    background-color: #003366;
    border-color: #0088ff;
    font-size: 14px;
    font-weight: 700;
    min-width: 80px;
}
QPushButton#btn_play:hover {
    background-color: #004488;
    border-color: #00ccff;
}

/* ─── Track Table ───────────────────────────────────────── */
QTableWidget {
    background-color: #0a0a0f;
    alternate-background-color: #0d0d18;
    border: 1px solid #1a2233;
    border-radius: 4px;
    gridline-color: #1a2233;
    selection-background-color: #0d2244;
    selection-color: #ffffff;
}
QTableWidget::item {
    padding: 4px 6px;
    border: none;
}
QTableWidget::item:selected {
    background-color: #0d2244;
    color: #00ccff;
}
QHeaderView::section {
    background-color: #0f0f1a;
    color: #8899bb;
    border: none;
    border-bottom: 1px solid #1a2233;
    border-right: 1px solid #1a2233;
    padding: 5px 6px;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1px;
}

/* ─── Search Box ────────────────────────────────────────── */
QLineEdit {
    background-color: #0f0f1a;
    border: 1px solid #1a2233;
    border-radius: 4px;
    color: #ffffff;
    padding: 5px 10px;
    font-size: 12px;
}
QLineEdit:focus {
    border-color: #0088ff;
}
QLineEdit::placeholder {
    color: #445566;
}

/* ─── Sliders ───────────────────────────────────────────── */
QSlider::groove:horizontal {
    background: #1a2233;
    height: 4px;
    border-radius: 2px;
}
QSlider::sub-page:horizontal {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #0055bb, stop:1 #00aaff);
    height: 4px;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #00aaff;
    width: 12px;
    height: 12px;
    margin: -4px 0;
    border-radius: 6px;
    border: 2px solid #0a0a0f;
}
QSlider::handle:horizontal:hover {
    background: #00ccff;
    border-color: #0088ff;
}

/* ─── Progress Bar ──────────────────────────────────────── */
QProgressBar {
    background-color: #1a2233;
    border: none;
    border-radius: 3px;
    height: 6px;
    text-align: center;
    color: transparent;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #0055bb, stop:1 #00ccff);
    border-radius: 3px;
}

/* ─── Scroll Bars ───────────────────────────────────────── */
QScrollBar:vertical {
    background: #0a0a0f;
    width: 8px;
    border: none;
}
QScrollBar::handle:vertical {
    background: #1a2233;
    border-radius: 4px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover {
    background: #0088ff;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

/* ─── Status Bar ────────────────────────────────────────── */
QStatusBar {
    background-color: #0f0f1a;
    color: #8899bb;
    border-top: 1px solid #1a2233;
    font-size: 11px;
    padding: 2px 8px;
}

/* ─── Labels ────────────────────────────────────────────── */
QLabel#track_title {
    font-size: 16px;
    font-weight: 700;
    color: #ffffff;
}
QLabel#track_artist {
    font-size: 12px;
    color: #8899bb;
}
QLabel#info_label {
    font-size: 10px;
    color: #445566;
    text-transform: uppercase;
    letter-spacing: 1px;
}
QLabel#info_value_large {
    font-size: 34px;
    font-weight: 800;
    color: #00aaff;
    font-family: "Consolas", "Courier New", monospace;
}
QLabel#info_value_medium {
    font-size: 26px;
    font-weight: 700;
    color: #ffffff;
    font-family: "Consolas", "Courier New", monospace;
}
QLabel#camelot_value {
    font-size: 26px;
    font-weight: 700;
    color: #00ccff;
    font-family: "Consolas", "Courier New", monospace;
}
QLabel#meta_text {
    font-size: 11px;
    color: #8899bb;
}
QLabel#section_header {
    font-size: 10px;
    font-weight: 700;
    color: #445566;
    text-transform: uppercase;
    letter-spacing: 2px;
}
QLabel#time_display {
    font-size: 13px;
    font-weight: 600;
    color: #8899bb;
    font-family: "Consolas", monospace;
    min-width: 95px;
}

/* ─── Info Cards ────────────────────────────────────────── */
QWidget#info_card {
    background-color: #0f0f1a;
    border: 1px solid #1a2233;
    border-radius: 6px;
}
QWidget#info_card:hover {
    border-color: #0044aa;
}

/* ─── Splitter ──────────────────────────────────────────── */
QSplitter::handle {
    background-color: #1a2233;
    width: 1px;
}

/* ─── Context Menu ──────────────────────────────────────── */
QMenu {
    background-color: #0f0f1a;
    border: 1px solid #1a2233;
    border-radius: 4px;
    padding: 4px;
}
QMenu::item {
    padding: 6px 20px;
    border-radius: 3px;
}
QMenu::item:selected {
    background-color: #1a1a3a;
    color: #00ccff;
}

/* ─── Tooltip ───────────────────────────────────────────── */
QToolTip {
    background-color: #0f0f1a;
    color: #ffffff;
    border: 1px solid #0088ff;
    padding: 4px 8px;
    border-radius: 3px;
    font-size: 11px;
}
"""
