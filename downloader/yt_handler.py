"""
YouTube download worker using yt-dlp Python API.
Downloads best-quality audio (m4a/webm) without requiring ffmpeg.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

import yt_dlp


def resolve_output_path(info: dict) -> str | None:
    """Extract the final downloaded file path from a yt-dlp info dict."""
    rd = info.get("requested_downloads", [])
    if rd:
        return rd[0].get("filepath")
    # Fallback: older yt-dlp versions store it at top level
    return info.get("filepath") or info.get("_filename")


class DownloadWorker(QThread):
    """
    Downloads a single YouTube URL in a background thread.

    Signals
    -------
    progress(url, fraction)   — 0.0–1.0 download progress
    title_found(url, title)   — fires once the video title is known
    done(url, file_path)      — fires when file is fully written to disk
    error(url, message)       — fires on any exception
    """

    progress    = pyqtSignal(str, float)
    title_found = pyqtSignal(str, str)
    done        = pyqtSignal(str, str)
    error       = pyqtSignal(str, str)

    def __init__(self, url: str, output_dir: Path, parent=None):
        super().__init__(parent)
        self.url = url
        self.output_dir = Path(output_dir)
        self._output_file: str | None = None

    # ------------------------------------------------------------------
    # QThread entry point
    # ------------------------------------------------------------------

    def run(self) -> None:
        ydl_opts = {
            "format": "bestaudio[ext=m4a]/bestaudio",
            "outtmpl": str(self.output_dir / "%(title)s.%(ext)s"),
            "progress_hooks": [self._hook],
            "quiet": True,
            "no_warnings": True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.url, download=True)

            title = info.get("title", "Unknown")
            self.title_found.emit(self.url, title)

            fp = resolve_output_path(info)
            if fp:
                self.done.emit(self.url, fp)
            else:
                # Last-resort glob for the most recently modified audio file
                fp = self._find_recent_audio()
                if fp:
                    self.done.emit(self.url, fp)
                else:
                    self.error.emit(self.url, "Download finished but output file not found.")
        except Exception as exc:
            self.error.emit(self.url, str(exc))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _hook(self, d: dict) -> None:
        if d["status"] == "downloading":
            downloaded = d.get("downloaded_bytes", 0)
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            if total > 0:
                self.progress.emit(self.url, downloaded / total)
        elif d["status"] == "finished":
            self._output_file = d.get("filename")
            self.progress.emit(self.url, 1.0)

    def _find_recent_audio(self) -> str | None:
        """Glob output_dir for the most recently written audio file."""
        audio_exts = {".mp3", ".m4a", ".webm", ".ogg", ".opus", ".wav", ".flac"}
        candidates = [
            p for p in self.output_dir.iterdir()
            if p.suffix.lower() in audio_exts
        ]
        if not candidates:
            return None
        return str(max(candidates, key=lambda p: p.stat().st_mtime))
