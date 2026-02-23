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

def test_main_window_imports_cleanly():
    """MainWindow should import without Qt display (headless check)."""
    from ui.main_window import MainWindow, PlayerState
    assert MainWindow is not None
    assert PlayerState is not None

import tempfile, json as _json
from pathlib import Path as _Path

def test_hot_cues_json_roundtrip(tmp_path):
    """Hot cues dict should survive JSON round-trip."""
    cues_file = tmp_path / 'hot_cues.json'
    track_key = '/music/track.mp3'
    cues = [None, {'position': 0.24}, None, {'position': 0.51}, None, None]

    # Save
    cues_file.parent.mkdir(parents=True, exist_ok=True)
    with open(cues_file, 'w') as f:
        _json.dump({track_key: cues}, f)

    # Load
    with open(cues_file) as f:
        loaded = _json.load(f)

    assert loaded[track_key][1] == {'position': 0.24}
    assert loaded[track_key][3] == {'position': 0.51}
    assert loaded[track_key][0] is None

def test_waveform_n_bars_increased():
    """N_BARS must be >= 1200 for smooth filled waveform outline."""
    from ui.waveform_dj import WaveformDataThread
    assert WaveformDataThread.N_BARS >= 1200

def test_waveform_zoom_bounds_clamping():
    """Zoom window must clamp to [0, 1] and handle short tracks."""
    # Simulate the zoom calculation logic from WaveformDJ.set_playback_position
    def compute_zoom(pos, duration, window_secs=30.0):
        if duration <= 0:
            return (0.0, 1.0)
        window_frac = min(1.0, window_secs / duration)
        half = window_frac / 2.0
        start = max(0.0, pos - half)
        end = min(1.0, start + window_frac)
        if end >= 1.0:
            end = 1.0
            start = max(0.0, end - window_frac)
        return (start, end)

    # Middle of a 5-min track: window should be symmetric
    s, e = compute_zoom(0.5, 300.0)
    assert abs((e - s) - 30.0 / 300.0) < 0.001

    # Near start: clamp to 0
    s, e = compute_zoom(0.0, 300.0)
    assert s == 0.0
    assert e == pytest.approx(30.0 / 300.0)

    # Near end: clamp to 1
    s, e = compute_zoom(1.0, 300.0)
    assert e == 1.0

    # Short track < 30s: show full track
    s, e = compute_zoom(0.5, 20.0)
    assert s == 0.0
    assert e == 1.0
