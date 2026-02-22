"""Test that analysis completes in under 3 seconds"""
import time
import pytest
from pathlib import Path
from analyzer.audio_analyzer import AudioAnalyzer

SAMPLE_TRACK = r"C:\Users\ashay\Downloads\y2mate.com - LudoWic  MIND PARADE Katana ZERO DLC_320kbps.mp3"

@pytest.mark.skipif(not Path(SAMPLE_TRACK).exists(), reason="Sample track not found")
def test_analysis_speed():
    """Analysis should complete in under 3 seconds"""
    analyzer = AudioAnalyzer()
    start = time.time()
    result = analyzer.analyze_track(SAMPLE_TRACK)
    elapsed = time.time() - start
    assert elapsed < 3.0, f"Analysis took {elapsed:.1f}s (limit: 3s)"
    assert result['bpm'] is not None
    assert result['key']['camelot'] is not None

@pytest.mark.skipif(not Path(SAMPLE_TRACK).exists(), reason="Sample track not found")
def test_analysis_results_correct():
    """Core results should be accurate"""
    analyzer = AudioAnalyzer()
    result = analyzer.analyze_track(SAMPLE_TRACK)
    assert 100 <= result['bpm'] <= 110, f"BPM {result['bpm']} out of expected range"
    assert 'Major' in result['key']['notation'] or 'Minor' in result['key']['notation']
    assert 1 <= result['energy']['level'] <= 10
    assert result['duration'] > 0
    assert result['audio_info']['bitrate'] > 0
    assert result['audio_info']['format'] == 'MP3'

@pytest.mark.skipif(not Path(SAMPLE_TRACK).exists(), reason="Sample track not found")
def test_return_dict_structure():
    """Return dict must have all required keys"""
    analyzer = AudioAnalyzer()
    result = analyzer.analyze_track(SAMPLE_TRACK)
    required_keys = ['file_path', 'filename', 'bpm', 'key', 'energy', 'metadata', 'audio_info', 'duration']
    for key in required_keys:
        assert key in result, f"Missing key: {key}"
    assert 'notation' in result['key']
    assert 'camelot' in result['key']
    assert 'level' in result['energy']

@pytest.mark.skipif(not Path(SAMPLE_TRACK).exists(), reason="Sample track not found")
def test_full_track_energy_structure():
    """_calculate_energy_full must return correct dict shape and valid level."""
    analyzer = AudioAnalyzer()
    result = analyzer._calculate_energy_full(Path(SAMPLE_TRACK))
    assert isinstance(result, dict)
    assert 'level' in result
    assert 'rms' in result
    assert 'description' in result
    assert 1 <= result['level'] <= 10
    assert result['rms'] > 0
