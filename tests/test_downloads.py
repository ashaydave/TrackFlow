"""
Tests for the Downloads tab components.
All tests are offline (no network calls) — real YouTube/Apple Music access
is exercised manually during the smoke-test checklist.
"""

import json
import plistlib
import sys
import time
from pathlib import Path

import pytest

# Make sure project root is on the path
sys.path.insert(0, str(Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# Import checks
# ---------------------------------------------------------------------------

def test_downloader_imports_cleanly():
    """All downloader submodules must import without raising."""
    from downloader.yt_handler import DownloadWorker, resolve_output_path
    from downloader.watcher import FolderWatcher
    from downloader.playlist_sync import (
        YouTubePlaylistSource,
        AppleMusicSource,
        PlaylistSyncWorker,
        search_youtube,
        detect_apple_music_xml,
        load_sync_state,
        save_sync_state,
    )
    assert DownloadWorker is not None
    assert FolderWatcher is not None
    assert YouTubePlaylistSource is not None
    assert AppleMusicSource is not None


# ---------------------------------------------------------------------------
# yt_handler — resolve_output_path (pure function, no network)
# ---------------------------------------------------------------------------

def test_resolve_output_path_happy():
    from downloader.yt_handler import resolve_output_path
    info = {"requested_downloads": [{"filepath": "/tmp/track.m4a"}]}
    assert resolve_output_path(info) == "/tmp/track.m4a"


def test_resolve_output_path_empty_requested():
    from downloader.yt_handler import resolve_output_path
    assert resolve_output_path({"requested_downloads": []}) is None


def test_resolve_output_path_missing_key():
    from downloader.yt_handler import resolve_output_path
    assert resolve_output_path({}) is None


def test_resolve_output_path_fallback_filepath():
    """Older yt-dlp stores path directly in info['filepath']."""
    from downloader.yt_handler import resolve_output_path
    info = {"filepath": "/music/track.webm"}
    assert resolve_output_path(info) == "/music/track.webm"


# ---------------------------------------------------------------------------
# watcher — FolderWatcher (real filesystem events, no network)
# ---------------------------------------------------------------------------

def _make_direct_watcher(detected: list):
    """
    Create a FolderWatcher whose signal is connected with DirectConnection.
    DirectConnection delivers signals across threads without an event loop,
    which is required in pytest (no app.exec() running).
    """
    from downloader.watcher import FolderWatcher
    from PyQt6.QtCore import Qt
    watcher = FolderWatcher()
    watcher.file_detected.connect(detected.append, Qt.ConnectionType.DirectConnection)
    return watcher


def test_folder_watcher_detects_mp3(tmp_path):
    """FolderWatcher must emit file_detected when an mp3 is created."""
    detected = []
    watcher = _make_direct_watcher(detected)
    assert watcher.start(str(tmp_path))
    (tmp_path / "test.mp3").write_bytes(b"fake mp3 data")
    time.sleep(0.6)   # watchdog is async; give it time
    watcher.stop()
    assert any("test.mp3" in p for p in detected), \
        f"Expected test.mp3 in detected files, got: {detected}"


def test_folder_watcher_detects_flac(tmp_path):
    """FolderWatcher must emit for .flac files."""
    detected = []
    watcher = _make_direct_watcher(detected)
    watcher.start(str(tmp_path))
    (tmp_path / "track.flac").write_bytes(b"fake")
    time.sleep(0.6)
    watcher.stop()
    assert any("track.flac" in p for p in detected)


def test_folder_watcher_detects_renamed_file(tmp_path):
    """
    Simulate SoulSeek completion: file saved as .tmp then renamed to .flac.
    FolderWatcher must catch the on_moved event.
    """
    detected = []
    watcher = _make_direct_watcher(detected)
    watcher.start(str(tmp_path))
    tmp_file = tmp_path / "downloading.tmp"
    tmp_file.write_bytes(b"data")
    time.sleep(0.2)
    tmp_file.rename(tmp_path / "track.flac")
    time.sleep(0.6)
    watcher.stop()
    assert any("track.flac" in p for p in detected), \
        f"Expected track.flac via rename, got: {detected}"


def test_folder_watcher_ignores_non_audio(tmp_path):
    """FolderWatcher must NOT emit for .txt or .jpg files."""
    detected = []
    watcher = _make_direct_watcher(detected)
    watcher.start(str(tmp_path))
    (tmp_path / "readme.txt").write_bytes(b"text")
    (tmp_path / "cover.jpg").write_bytes(b"img")
    time.sleep(0.6)
    watcher.stop()
    assert detected == [], f"Expected no detections, got: {detected}"


def test_folder_watcher_returns_false_for_missing_dir(tmp_path):
    """start() must return False if the folder doesn't exist."""
    from downloader.watcher import FolderWatcher
    watcher = FolderWatcher()
    result = watcher.start(str(tmp_path / "nonexistent"))
    assert result is False


def test_folder_watcher_is_watching_property(tmp_path):
    """is_watching should reflect the actual observer state."""
    from downloader.watcher import FolderWatcher
    watcher = FolderWatcher()
    assert not watcher.is_watching
    watcher.start(str(tmp_path))
    assert watcher.is_watching
    watcher.stop()
    assert not watcher.is_watching


# ---------------------------------------------------------------------------
# playlist_sync — AppleMusicSource (plist parsing, no network)
# ---------------------------------------------------------------------------

def _write_itunes_xml(path: Path, tracks: dict, playlists: list) -> None:
    """Write a minimal iTunes-compatible plist XML for testing."""
    data = {"Tracks": tracks, "Playlists": playlists}
    with open(path, "wb") as f:
        plistlib.dump(data, f)


def test_apple_music_source_parses_shazam_playlist(tmp_path):
    """AppleMusicSource must correctly extract tracks from a named playlist."""
    xml_path = tmp_path / "library.xml"
    _write_itunes_xml(
        xml_path,
        tracks={
            "100": {"Track ID": 100, "Name": "Xtal",     "Artist": "Aphex Twin"},
            "101": {"Track ID": 101, "Name": "Archangel", "Artist": "Burial"},
        },
        playlists=[
            {
                "Name": "Shazam Library",
                "Playlist Items": [{"Track ID": 100}, {"Track ID": 101}],
            }
        ],
    )
    from downloader.playlist_sync import AppleMusicSource
    src = AppleMusicSource(str(xml_path), "Shazam Library")
    tracks = src.get_tracks()
    assert len(tracks) == 2
    assert tracks[0]["title"]  == "Xtal"
    assert tracks[0]["artist"] == "Aphex Twin"
    assert tracks[1]["title"]  == "Archangel"
    assert tracks[1]["artist"] == "Burial"


def test_apple_music_source_unknown_playlist(tmp_path):
    """AppleMusicSource returns [] when the playlist name isn't found."""
    xml_path = tmp_path / "library.xml"
    _write_itunes_xml(xml_path, tracks={}, playlists=[])
    from downloader.playlist_sync import AppleMusicSource
    src = AppleMusicSource(str(xml_path), "Nonexistent Playlist")
    assert src.get_tracks() == []


def test_apple_music_source_missing_xml():
    """AppleMusicSource returns [] gracefully when the XML file is absent."""
    from downloader.playlist_sync import AppleMusicSource
    src = AppleMusicSource("/nonexistent/path/library.xml", "Shazam Library")
    assert src.get_tracks() == []


def test_apple_music_source_id():
    """source_id must be stable and formatted as 'apple_music::<playlist>'."""
    from downloader.playlist_sync import AppleMusicSource
    src = AppleMusicSource("/tmp/lib.xml", "My Playlist")
    assert src.source_id == "apple_music::My Playlist"


# ---------------------------------------------------------------------------
# playlist_sync — sync state persistence
# ---------------------------------------------------------------------------

def test_sync_state_roundtrip(tmp_path, monkeypatch):
    """save_sync_state / load_sync_state must persist and restore correctly."""
    import downloader.playlist_sync as ps
    monkeypatch.setattr(ps, "SYNC_STATE_FILE", tmp_path / "sync_state.json")

    state = {
        "PLxyz": ["id1", "id2"],
        "apple_music::Shazam Library": [{"id": "100", "title": "Xtal", "artist": "Aphex Twin"}],
    }
    ps.save_sync_state(state)
    loaded = ps.load_sync_state()
    assert loaded["PLxyz"] == ["id1", "id2"]
    assert loaded["apple_music::Shazam Library"][0]["title"] == "Xtal"


def test_load_sync_state_missing_file(tmp_path, monkeypatch):
    """load_sync_state must return {} when the file doesn't exist."""
    import downloader.playlist_sync as ps
    monkeypatch.setattr(ps, "SYNC_STATE_FILE", tmp_path / "does_not_exist.json")
    assert ps.load_sync_state() == {}


# ---------------------------------------------------------------------------
# downloads_tab — config roundtrip (no Qt display required)
# ---------------------------------------------------------------------------

def test_downloads_config_roundtrip(tmp_path):
    """Config dict must survive a JSON write/read cycle."""
    config = {
        "yt_output_dir":  r"C:\Music\DJ Library",
        "watch_dir":      r"C:\SoulSeek\complete",
        "apple_music_xml": r"C:\Users\me\Music\iTunes\iTunes Music Library.xml",
        "subscriptions": [
            {"type": "youtube",     "url": "https://yt.be/list=XYZ", "label": "Techno"},
            {"type": "apple_music", "playlist": "Shazam Library"},
        ],
    }
    cfg_file = tmp_path / "downloads_config.json"
    with open(cfg_file, "w") as f:
        json.dump(config, f, indent=2)
    with open(cfg_file) as f:
        loaded = json.load(f)

    assert loaded["yt_output_dir"] == r"C:\Music\DJ Library"
    assert loaded["subscriptions"][0]["label"] == "Techno"
    assert loaded["subscriptions"][1]["playlist"] == "Shazam Library"


# ---------------------------------------------------------------------------
# MainWindow — import smoke (headless, no display needed for import)
# ---------------------------------------------------------------------------

def test_main_window_imports_with_downloads_tab():
    """MainWindow must import cleanly after the Downloads tab integration."""
    from ui.main_window import MainWindow
    assert MainWindow is not None
