"""Tests for batch_analyzer cache functions"""
import pytest
from pathlib import Path
from analyzer.batch_analyzer import _cache_key, load_cached, save_cached, is_cached, CACHE_DIR

SAMPLE_TRACK = r"C:\Users\ashay\Downloads\y2mate.com - LudoWic  MIND PARADE Katana ZERO DLC_320kbps.mp3"

@pytest.mark.skipif(not Path(SAMPLE_TRACK).exists(), reason="Sample track not found")
def test_cache_roundtrip():
    """Cache write → read roundtrip works correctly"""
    fp = Path(SAMPLE_TRACK)
    fake_results = {'bpm': 103.4, 'filename': 'test.mp3', 'file_path': str(fp)}

    save_cached(fp, fake_results)
    assert is_cached(fp)

    loaded = load_cached(fp)
    assert loaded is not None
    assert loaded['bpm'] == 103.4

    # Clean up
    cache_file = CACHE_DIR / f"{_cache_key(fp)}.json"
    cache_file.unlink(missing_ok=True)
    assert not is_cached(fp)

def test_missing_file_not_cached(tmp_path):
    """Newly created empty file is not cached"""
    fake = tmp_path / "nonexistent.mp3"
    fake.touch()
    assert not is_cached(fake)

def test_cache_key_stability():
    """Same file always produces same cache key"""
    import tempfile, os
    with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
        f.write(b'fake')
        path = Path(f.name)
    try:
        key1 = _cache_key(path)
        key2 = _cache_key(path)
        assert key1 == key2
        assert len(key1) == 32  # MD5 hex length
    finally:
        os.unlink(path)

def test_load_cached_handles_corrupt_json(tmp_path):
    """load_cached returns None and removes corrupt cache file"""
    fp = tmp_path / "song.mp3"
    fp.touch()
    # Write corrupt JSON to cache location
    from analyzer.batch_analyzer import CACHE_DIR, _cache_key
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / f"{_cache_key(fp)}.json"
    cache_file.write_text("{{INVALID JSON")
    result = load_cached(fp)
    assert result is None
    assert not cache_file.exists()  # should be cleaned up
