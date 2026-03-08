"""
Tests for analyzer/genre_detector.py

These tests cover:
- Module import / availability check (no network required)
- ensure_models() return structure and partial-failure handling
- Genre cache roundtrip (load_genre_cache / save_genre_cache)
- GenreDetector.format_genres() label formatting logic
- Label cleaning: "Electronic---Deep House" → "Deep House"
- GenreDetector.available() reflects essentia import state
- paths.get_models_dir() creates and returns correct directory
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# paths.get_models_dir()
# ---------------------------------------------------------------------------

def test_get_models_dir_creates_directory(tmp_path, monkeypatch):
    """get_models_dir() must create the directory if it doesn't exist."""
    import paths
    monkeypatch.setattr(paths, "get_data_dir", lambda: tmp_path)
    from paths import get_models_dir
    # Monkeypatching the module-level function after import requires re-import
    # so we test via calling the real function with patched data dir
    d = tmp_path / "models"
    assert not d.exists()
    # Call the real implementation (it uses get_data_dir internally)
    # Just verify we can import and call it without error
    result = get_models_dir()
    assert result.exists()
    assert result.is_dir()


# ---------------------------------------------------------------------------
# ensure_models()
# ---------------------------------------------------------------------------

def test_ensure_models_skips_existing_files(tmp_path, monkeypatch):
    """ensure_models() should not re-download if all files already exist."""
    import analyzer.genre_detector as gd
    monkeypatch.setattr(gd, "get_models_dir", lambda: tmp_path)

    # Pre-create fake model files
    for info in gd.MODELS.values():
        (tmp_path / info["filename"]).write_bytes(b"fake-model-data")

    downloaded = []
    with patch("urllib.request.urlretrieve", side_effect=lambda u, d: downloaded.append(u)):
        result = gd.ensure_models()

    assert result is not None
    assert downloaded == [], "Should not download anything if files already exist"
    for key in gd.MODELS:
        assert key in result
        assert result[key].exists()


def test_ensure_models_returns_none_on_download_failure(tmp_path, monkeypatch):
    """ensure_models() returns None when a download fails."""
    import analyzer.genre_detector as gd
    monkeypatch.setattr(gd, "get_models_dir", lambda: tmp_path)

    messages = []
    with patch("urllib.request.urlretrieve", side_effect=OSError("network error")):
        result = gd.ensure_models(status_callback=messages.append)

    assert result is None
    assert any("failed" in m.lower() for m in messages)


def test_ensure_models_calls_status_callback(tmp_path, monkeypatch):
    """ensure_models() should emit progress messages via callback."""
    import analyzer.genre_detector as gd
    monkeypatch.setattr(gd, "get_models_dir", lambda: tmp_path)

    messages = []

    def fake_download(url, dest):
        Path(dest).write_bytes(b"fake")

    with patch("urllib.request.urlretrieve", side_effect=fake_download):
        result = gd.ensure_models(status_callback=messages.append)

    assert result is not None
    # At least one message per model that needed downloading
    assert len(messages) >= len(gd.MODELS)


# ---------------------------------------------------------------------------
# Genre cache (load_genre_cache / save_genre_cache)
# ---------------------------------------------------------------------------

def test_genre_cache_roundtrip(tmp_path, monkeypatch):
    """Save and load a genre result for a fake file."""
    import analyzer.genre_detector as gd
    monkeypatch.setattr(gd, "get_cache_dir", lambda: tmp_path)

    # Create a real temp file so stat() works
    audio_file = tmp_path / "track.mp3"
    audio_file.write_bytes(b"\x00" * 1024)

    genres_str = "Deep House / Tech House"
    gd.save_genre_cache(audio_file, genres_str)

    loaded = gd.load_genre_cache(audio_file)
    assert loaded == genres_str


def test_genre_cache_returns_none_for_uncached(tmp_path, monkeypatch):
    """load_genre_cache returns None if the file has no cache entry."""
    import analyzer.genre_detector as gd
    monkeypatch.setattr(gd, "get_cache_dir", lambda: tmp_path)

    audio_file = tmp_path / "track.mp3"
    audio_file.write_bytes(b"\x00" * 512)

    assert gd.load_genre_cache(audio_file) is None


def test_genre_cache_handles_corrupt_json(tmp_path, monkeypatch):
    """load_genre_cache returns None and removes corrupt cache file."""
    import analyzer.genre_detector as gd
    monkeypatch.setattr(gd, "get_cache_dir", lambda: tmp_path)

    audio_file = tmp_path / "track.mp3"
    audio_file.write_bytes(b"\x00" * 512)

    # Write corrupt cache
    from analyzer.genre_detector import _genre_cache_key
    cache_file = tmp_path / f"{_genre_cache_key(audio_file)}.json"
    cache_file.write_text("{not valid json")

    result = gd.load_genre_cache(audio_file)
    assert result is None
    assert not cache_file.exists(), "Corrupt cache file should be removed"


def test_genre_cache_key_changes_on_file_modification(tmp_path):
    """Different file contents should produce different cache keys."""
    from analyzer.genre_detector import _genre_cache_key
    import time

    f = tmp_path / "track.mp3"
    f.write_bytes(b"\x00" * 512)
    key1 = _genre_cache_key(f)

    # Modify file (change mtime and/or size)
    time.sleep(0.01)
    f.write_bytes(b"\x00" * 1024)
    key2 = _genre_cache_key(f)

    assert key1 != key2


# ---------------------------------------------------------------------------
# GenreDetector.available()
# ---------------------------------------------------------------------------

def test_available_returns_false_when_essentia_missing():
    """available() should return False if essentia is not installed."""
    import builtins
    real_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == "essentia":
            raise ImportError("No module named 'essentia'")
        return real_import(name, *args, **kwargs)

    from analyzer.genre_detector import GenreDetector
    with patch("builtins.__import__", side_effect=mock_import):
        result = GenreDetector.available()

    assert result is False


def test_available_returns_true_when_essentia_present():
    """available() returns True when essentia imports successfully."""
    from analyzer.genre_detector import GenreDetector

    mock_essentia = MagicMock()
    with patch.dict("sys.modules", {"essentia": mock_essentia}):
        result = GenreDetector.available()

    assert result is True


# ---------------------------------------------------------------------------
# GenreDetector.format_genres()
# ---------------------------------------------------------------------------

def test_format_genres_top_two():
    """format_genres returns top 2 genres above threshold as 'A / B'."""
    from analyzer.genre_detector import GenreDetector

    # Instantiate without loading real models
    detector = object.__new__(GenreDetector)
    detector._labels = ["Deep House", "Tech House", "House", "Minimal Techno"]

    genres = [("Deep House", 0.42), ("Tech House", 0.18), ("House", 0.07)]
    result = detector.format_genres(genres)
    assert result == "Deep House / Tech House"


def test_format_genres_filters_below_threshold():
    """Genres below min_score are excluded."""
    from analyzer.genre_detector import GenreDetector

    detector = object.__new__(GenreDetector)
    detector._labels = ["Deep House", "Ambient", "House"]

    genres = [("Deep House", 0.5), ("Ambient", 0.02), ("House", 0.01)]
    result = detector.format_genres(genres, min_score=0.05)
    assert result == "Deep House"


def test_format_genres_empty_list():
    """format_genres returns empty string for empty input."""
    from analyzer.genre_detector import GenreDetector

    detector = object.__new__(GenreDetector)
    detector._labels = []

    assert detector.format_genres([]) == ""


def test_format_genres_all_below_threshold():
    """format_genres returns empty string when all scores are below threshold."""
    from analyzer.genre_detector import GenreDetector

    detector = object.__new__(GenreDetector)
    detector._labels = ["Deep House"]

    genres = [("Deep House", 0.01)]
    assert detector.format_genres(genres, min_score=0.05) == ""


# ---------------------------------------------------------------------------
# Label cleaning (Discogs format)
# ---------------------------------------------------------------------------

def test_label_cleaning_logic():
    """Verify 'Electronic---Deep House' → 'Deep House' cleaning."""
    raw_labels = [
        "Electronic---Deep House",
        "Electronic---Tech House",
        "Pop---Synth-pop",
        "Jazz",            # no separator
        "Rock---Alternative Rock",
    ]
    cleaned = [lbl.split("---")[-1].strip() for lbl in raw_labels]
    assert cleaned == [
        "Deep House",
        "Tech House",
        "Synth-pop",
        "Jazz",
        "Alternative Rock",
    ]


# ---------------------------------------------------------------------------
# MODELS manifest sanity check
# ---------------------------------------------------------------------------

def test_models_manifest_has_required_keys():
    """MODELS dict has the three required keys with expected fields."""
    from analyzer.genre_detector import MODELS

    assert set(MODELS.keys()) == {"effnet", "genre_head", "labels"}
    for key, info in MODELS.items():
        assert "url" in info, f"Missing 'url' in MODELS['{key}']"
        assert "filename" in info, f"Missing 'filename' in MODELS['{key}']"
        assert info["url"].startswith("https://"), f"URL should be HTTPS: {info['url']}"
        assert info["filename"].endswith((".pb", ".json")), (
            f"Unexpected file extension: {info['filename']}"
        )


def test_models_effnet_is_largest():
    """The EffNet backbone should be the largest model (~40 MB)."""
    from analyzer.genre_detector import MODELS

    effnet_size = MODELS["effnet"]["size_mb"]
    assert effnet_size >= 30, f"EffNet expected ~40 MB, got {effnet_size}"
    assert effnet_size > MODELS["genre_head"]["size_mb"]
