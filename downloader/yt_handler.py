"""
YouTube download worker using yt-dlp Python API.

Format preference:
  - If ffmpeg is found on the system → downloads as MP3 320 kbps (preferred for DJs)
  - If ffmpeg is not found          → downloads best-quality m4a (no conversion needed)

Use find_ffmpeg() to detect the ffmpeg binary, or pass ffmpeg_path explicitly
to DownloadWorker if you want to override.
"""

from __future__ import annotations

import glob
import shutil
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

import yt_dlp


# ---------------------------------------------------------------------------
# ffmpeg detection
# ---------------------------------------------------------------------------

def find_ffmpeg() -> str | None:
    """
    Locate the ffmpeg executable.
    Checks PATH first, then common Windows install locations.
    Returns the full path string, or None if not found.
    """
    # 1. Standard PATH lookup
    p = shutil.which("ffmpeg")
    if p:
        return p

    # 2. Common Windows locations (Chocolatey, manual installs, bundled apps)
    candidates = [
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\ffmpeg\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe",
        r"C:\ProgramData\chocolatey\bin\ffmpeg.exe",
        r"C:\tools\ffmpeg\bin\ffmpeg.exe",
    ]
    for c in candidates:
        if Path(c).exists():
            return c

    # 3. Broad glob across Program Files (catches bundled installs like
    #    "YouTube Playlist Downloader", "Handbrake", etc.)
    for pattern in [
        r"C:\Program Files*\*\bin\ffmpeg.exe",
        r"C:\Program Files*\*\ffmpeg.exe",
        r"C:\Program Files*\*\*\ffmpeg.exe",
    ]:
        results = glob.glob(pattern)
        if results:
            return results[0]

    return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def resolve_output_path(info: dict) -> str | None:
    """Extract the final downloaded file path from a yt-dlp info dict."""
    rd = info.get("requested_downloads", [])
    if rd:
        return rd[0].get("filepath")
    # Fallback: older yt-dlp versions store it at top level
    return info.get("filepath") or info.get("_filename")


# ---------------------------------------------------------------------------
# Download worker
# ---------------------------------------------------------------------------

class DownloadWorker(QThread):
    """
    Downloads a single YouTube URL in a background thread.

    Parameters
    ----------
    url         : YouTube video or playlist URL
    output_dir  : destination folder
    prefer_mp3  : if True *and* ffmpeg_path is set, convert to MP3 320 kbps
    ffmpeg_path : path to ffmpeg binary (use find_ffmpeg() to detect)

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

    def __init__(
        self,
        url: str,
        output_dir: Path,
        prefer_mp3: bool = True,
        ffmpeg_path: str | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.url         = url
        self.output_dir  = Path(output_dir)
        self._prefer_mp3 = prefer_mp3
        self._ffmpeg     = ffmpeg_path
        self._output_file: str | None = None

    # ------------------------------------------------------------------
    # QThread entry point
    # ------------------------------------------------------------------

    def run(self) -> None:
        ydl_opts = self._build_opts()
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.url, download=True)

            title = info.get("title", "Unknown")
            self.title_found.emit(self.url, title)

            fp = resolve_output_path(info)
            if fp:
                self.done.emit(self.url, fp)
            else:
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

    def _build_opts(self) -> dict:
        base = {
            "outtmpl":        str(self.output_dir / "%(title)s.%(ext)s"),
            "progress_hooks": [self._hook],
            "quiet":          True,
            "no_warnings":    True,
        }
        if self._prefer_mp3 and self._ffmpeg:
            # Convert to MP3 320 kbps — preferred for DJ software compatibility
            base.update({
                "format": "bestaudio/best",
                "postprocessors": [{
                    "key":              "FFmpegExtractAudio",
                    "preferredcodec":   "mp3",
                    "preferredquality": "320",
                }],
                "ffmpeg_location": str(Path(self._ffmpeg).parent),
            })
        else:
            # No ffmpeg: download native best-quality audio (usually m4a/webm)
            base.update({
                "format": "bestaudio[ext=m4a]/bestaudio",
            })
        return base

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
