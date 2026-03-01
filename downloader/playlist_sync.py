"""
Playlist sync: detects new tracks in subscribed YouTube playlists and
Apple Music / iTunes XML playlists, and queues them for download.

Sources
-------
- YouTubePlaylistSource  — uses yt-dlp extract_flat to list a playlist
- AppleMusicSource       — parses Apple Music for Windows / iTunes XML via stdlib plistlib

For Apple Music / Shazam tracks (no YouTube URL), search_youtube() tries
3 query variants and returns the first match.

State persistence
-----------------
Sync state is stored in get_data_dir() / 'sync_state.json' as:
  { source_id: [id_or_title, ...] }
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

import yt_dlp

sys.path.insert(0, str(Path(__file__).parent.parent))
from paths import get_data_dir


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SYNC_STATE_FILE = get_data_dir() / "sync_state.json"


# ---------------------------------------------------------------------------
# YouTube search helper
# ---------------------------------------------------------------------------

def search_youtube(title: str, artist: str = "") -> str | None:
    """
    Try up to 3 query variants and return the first matching YouTube URL.
    Returns None if all queries fail or no results are found.
    """
    queries = [
        f"{artist} - {title}" if artist else title,
        f"{title} {artist}".strip(),
        f"{artist} {title} official audio".strip(),
    ]
    opts = {
        "quiet": True,
        "extract_flat": True,
        "no_warnings": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        for q in queries:
            try:
                info = ydl.extract_info(f"ytsearch1:{q}", download=False)
                entries = (info or {}).get("entries", [])
                if entries:
                    return entries[0].get("url") or entries[0].get("webpage_url")
            except Exception:
                continue
    return None


# ---------------------------------------------------------------------------
# Playlist sources
# ---------------------------------------------------------------------------

class YouTubePlaylistSource:
    """
    Fetches the current track list of a YouTube playlist without downloading.

    Parameters
    ----------
    source_id : str
        The playlist URL (used as the unique key in sync_state).
    label : str
        Human-readable name shown in the UI.
    """

    def __init__(self, source_id: str, label: str = ""):
        self.source_id = source_id
        self.label = label or source_id

    def get_tracks(self) -> list[dict]:
        """
        Returns list of dicts: {id, title, url}.
        Returns [] on any error (network, private playlist, etc.).
        """
        opts = {
            "quiet": True,
            "extract_flat": True,
            "no_warnings": True,
        }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(self.source_id, download=False)
            return [
                {
                    "id": e.get("id", ""),
                    "title": e.get("title", ""),
                    "url": e.get("url") or e.get("webpage_url", ""),
                }
                for e in (info.get("entries") or [])
                if e
            ]
        except Exception:
            return []


class AppleMusicSource:
    """
    Reads a named playlist from an Apple Music for Windows / iTunes XML library file.
    Uses Python's stdlib plistlib — no extra dependencies.

    Parameters
    ----------
    xml_path : str
        Path to the iTunes Music Library.xml file.
    playlist_name : str
        Exact playlist name to watch (e.g. "Shazam Library").
    """

    def __init__(self, xml_path: str, playlist_name: str):
        self.xml_path = xml_path
        self.playlist_name = playlist_name
        self.source_id = f"apple_music::{playlist_name}"

    def get_tracks(self) -> list[dict]:
        """
        Returns list of dicts: {id, title, artist}.
        Returns [] if the XML doesn't exist or the playlist isn't found.
        """
        import plistlib

        xml = Path(self.xml_path)
        if not xml.exists():
            return []

        try:
            with open(xml, "rb") as f:
                data = plistlib.load(f)
        except Exception:
            return []

        track_map = data.get("Tracks", {})
        for pl in data.get("Playlists", []):
            if pl.get("Name") == self.playlist_name:
                result = []
                for item in pl.get("Playlist Items", []):
                    tid = str(item.get("Track ID", ""))
                    t = track_map.get(tid, {})
                    result.append({
                        "id": tid,
                        "title": t.get("Name", ""),
                        "artist": t.get("Artist", ""),
                    })
                return result
        return []


class AppleMusicURLSource:
    """
    Fetches the track list from a public Apple Music playlist URL.

    Parses JSON-LD structured data (MusicPlaylist schema) embedded in the
    page — works for any public playlist without authentication.
    For each track found, PlaylistSyncWorker will call search_youtube()
    to locate a matching YouTube video.

    Parameters
    ----------
    url   : Full https://music.apple.com/… playlist URL
    label : Human-readable name shown in the Queue source column
    """

    def __init__(self, url: str, label: str = ""):
        self.url = url
        self.label = label or "Apple Music"
        self.source_id = f"apple_music_url::{url}"

    def get_tracks(self) -> list[dict]:
        """
        Returns list of dicts: {id, title, artist}.
        Returns [] on any network or parsing error.
        """
        import html as _html  # noqa: F401 (unused but kept for reference)
        import json
        import re
        import urllib.request

        try:
            req = urllib.request.Request(
                self.url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                    "Accept-Language": "en-US,en;q=0.9",
                },
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                page = resp.read().decode("utf-8", errors="replace")
        except Exception:
            return []

        # Apple Music embeds MusicPlaylist schema as JSON-LD in <script> tags
        for raw in re.findall(
            r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            page,
            re.DOTALL,
        ):
            try:
                data = json.loads(raw)
                if data.get("@type") == "MusicPlaylist":
                    return self._parse_ld(data)
            except Exception:
                continue
        return []

    @staticmethod
    def _parse_ld(data: dict) -> list[dict]:
        tracks = []
        for item in data.get("track", []):
            name = item.get("name", "").strip()
            if not name:
                continue
            by_artist = item.get("byArtist", {})
            if isinstance(by_artist, dict):
                artist = by_artist.get("name", "")
            elif isinstance(by_artist, list) and by_artist:
                artist = by_artist[0].get("name", "")
            else:
                artist = ""
            tracks.append({
                "id":     f"{name}::{artist}",
                "title":  name,
                "artist": artist,
            })
        return tracks


def detect_apple_music_xml() -> str | None:
    """
    Auto-detect the Apple Music / iTunes library XML on Windows.
    Checks the two common locations and returns the first that exists.
    """
    home = Path.home()
    candidates = [
        home / "Music" / "iTunes" / "iTunes Music Library.xml",
        home / "Music" / "Music" / "Music Library.xml",
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    return None


# ---------------------------------------------------------------------------
# Sync state helpers
# ---------------------------------------------------------------------------

def load_sync_state() -> dict:
    """Load known-track-IDs from disk. Returns {} on any error."""
    try:
        if SYNC_STATE_FILE.exists():
            with open(SYNC_STATE_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def save_sync_state(state: dict) -> None:
    """Persist known-track-IDs to disk."""
    try:
        SYNC_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(SYNC_STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
    except Exception as exc:
        print(f"[playlist_sync] Could not save sync state: {exc}")


# ---------------------------------------------------------------------------
# Sync worker (QThread)
# ---------------------------------------------------------------------------

class PlaylistSyncWorker(QThread):
    """
    Checks all subscribed playlist sources for new tracks.
    For YouTube sources: emits new_track directly (URL already known).
    For Apple Music sources: calls search_youtube() and emits new_track if found,
    or track_not_found if all 3 queries fail.

    After finishing, updates sync_state on disk.

    Signals
    -------
    new_track(dict)          — {title, artist?, url, source_id, source_label}
    track_not_found(dict)    — {title, artist, source_id, source_label}
    source_done(str, int)    — source_id, count of new tracks found
    all_done()
    """

    new_track       = pyqtSignal(dict)
    track_not_found = pyqtSignal(dict)
    source_done     = pyqtSignal(str, int)
    all_done        = pyqtSignal()

    def __init__(
        self,
        sources: list,          # list of YouTubePlaylistSource | AppleMusicSource
        known_state: dict,      # from load_sync_state()
        parent=None,
    ):
        super().__init__(parent)
        self._sources = sources
        self._known = known_state
        self._new_state: dict = {k: list(v) for k, v in known_state.items()}

    def run(self) -> None:
        for source in self._sources:
            tracks = source.get_tracks()
            known_ids = self._known_ids_for(source.source_id)
            new_count = 0

            for t in tracks:
                tid = t.get("id") or t.get("title")
                if not tid or tid in known_ids:
                    continue

                # Track is new — record it immediately so re-runs don't duplicate
                self._new_state.setdefault(source.source_id, [])
                self._new_state[source.source_id].append(tid)

                if "url" not in t or not t["url"]:
                    # Apple Music track — search YouTube
                    url = search_youtube(t.get("title", ""), t.get("artist", ""))
                    if url:
                        t["url"] = url
                        t["source_id"] = source.source_id
                        t["source_label"] = getattr(source, "label", source.source_id)
                        self.new_track.emit(dict(t))
                        new_count += 1
                    else:
                        t["source_id"] = source.source_id
                        t["source_label"] = getattr(source, "label", source.source_id)
                        self.track_not_found.emit(dict(t))
                else:
                    t["source_id"] = source.source_id
                    t["source_label"] = getattr(source, "label", source.source_id)
                    self.new_track.emit(dict(t))
                    new_count += 1

            self.source_done.emit(source.source_id, new_count)

        save_sync_state(self._new_state)
        self.all_done.emit()

    # ------------------------------------------------------------------

    def _known_ids_for(self, source_id: str) -> set:
        raw = self._known.get(source_id, [])
        result = set()
        for item in raw:
            if isinstance(item, str):
                result.add(item)
            elif isinstance(item, dict):
                result.add(item.get("id") or item.get("title", ""))
        return result
