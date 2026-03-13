"""
TrackFlow - Main Entry Point
Launch the desktop application
"""

import os
import sys

# When frozen (no console window), redirect stdout/stderr to a log file so
# errors are not silently lost.  The log lands next to all other user data.
if getattr(sys, 'frozen', False):
    from pathlib import Path
    _log_dir = Path(os.environ.get("APPDATA", Path.home())) / "TrackFlow"
    _log_dir.mkdir(parents=True, exist_ok=True)
    _log_f = open(_log_dir / "trackflow.log", "w", buffering=1, encoding="utf-8")
    sys.stdout = _log_f
    sys.stderr = _log_f
    print("TrackFlow starting (frozen exe)")

from PyQt6.QtWidgets import QApplication, QSplashScreen
from PyQt6.QtGui import QPalette, QColor, QIcon, QPixmap, QPainter, QFont
from PyQt6.QtCore import Qt


def set_dark_theme(app):
    """Apply dark theme to the application"""
    app.setStyle("Fusion")

    # Dark palette
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.Base, QColor(25, 25, 25))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.Text, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 0, 0))
    palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(0, 0, 0))

    app.setPalette(palette)


def make_splash(logo_path):
    """Create a dark splash screen with the logo and app name."""
    w, h = 400, 280
    pixmap = QPixmap(w, h)
    pixmap.fill(QColor(30, 30, 30))

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Draw logo centered
    logo = QPixmap(str(logo_path))
    if not logo.isNull():
        logo = logo.scaled(96, 96, Qt.AspectRatioMode.KeepAspectRatio,
                           Qt.TransformationMode.SmoothTransformation)
        x = (w - logo.width()) // 2
        painter.drawPixmap(x, 50, logo)

    # App name
    painter.setPen(QColor(255, 255, 255))
    font = QFont("Segoe UI", 22, QFont.Weight.Bold)
    painter.setFont(font)
    painter.drawText(0, 170, w, 40, Qt.AlignmentFlag.AlignCenter, "TrackFlow")

    # Loading text
    painter.setPen(QColor(150, 150, 150))
    font = QFont("Segoe UI", 10)
    painter.setFont(font)
    painter.drawText(0, 210, w, 30, Qt.AlignmentFlag.AlignCenter, "Loading...")

    painter.end()
    return QSplashScreen(pixmap)


def main():
    """Main entry point"""
    app = QApplication(sys.argv)

    # Apply dark theme
    set_dark_theme(app)

    # Set application icon (window title bar + taskbar)
    from paths import get_assets_dir
    icon_path = get_assets_dir() / "logo_256.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    # Show splash screen immediately, before heavy imports
    splash = make_splash(icon_path if icon_path.exists() else "")
    splash.show()
    app.processEvents()

    # Heavy imports happen here
    from ui.main_window import MainWindow

    # Create and show main window
    window = MainWindow()
    window.show()
    splash.finish(window)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
