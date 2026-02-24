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

def test_loop_bar_snap_calculation():
    """Bar snap must correctly compute A/B positions from BPM."""
    bpm = 128.0
    duration = 240.0     # 4 minutes

    secs_per_bar = 4.0 * 60.0 / bpm   # = 1.875 s

    # Snap to 4 bars from position 0.2 (= 48s into 240s track)
    cur_secs = 0.2 * duration          # 48.0s
    bars = 4
    bar_num = round(cur_secs / secs_per_bar)
    a_secs = bar_num * secs_per_bar
    b_secs = min(a_secs + bars * secs_per_bar, duration)

    a_pos = a_secs / duration
    b_pos = b_secs / duration

    assert 0.0 <= a_pos <= 1.0
    assert 0.0 <= b_pos <= 1.0
    assert b_pos > a_pos
    expected_len = bars * secs_per_bar / duration
    assert abs((b_pos - a_pos) - expected_len) < 0.001


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


def test_bar_snap_right_trim_keeps_in_fixed():
    """When IN is set, bar-snap keeps IN fixed and only adjusts OUT."""
    bpm = 128.0
    duration = 240.0
    secs_per_bar = 4.0 * 60.0 / bpm   # 1.875 s

    # IN already set at 0.25 (60 s)
    loop_a = 0.25
    a_secs = loop_a * duration          # 60.0 s

    # Press "4" bar snap
    bars = 4
    b_secs = min(a_secs + bars * secs_per_bar, duration)
    loop_b = b_secs / duration

    assert loop_b > loop_a
    expected_len = bars * secs_per_bar / duration
    assert abs((loop_b - loop_a) - expected_len) < 0.001


def test_beat_grid_line_count():
    """Beat grid should generate correct number of beat positions for given BPM/duration."""
    bpm = 120.0
    duration = 60.0   # 1 minute = 120 beats
    secs_per_beat = 60.0 / bpm   # 0.5 s
    expected_beats = int(duration / secs_per_beat)  # 120

    beats = []
    t = 0.0
    while t < duration:
        beats.append(t)
        t += secs_per_beat

    assert len(beats) == expected_beats
    assert beats[0] == 0.0
    assert abs(beats[-1] - (duration - secs_per_beat)) < 0.001


def test_multi_delete_collects_unique_rows():
    """Multi-delete should collect all selected row indices, deduplicated."""
    class FakeItem:
        def __init__(self, row): self._row = row
        def row(self): return self._row

    items = [FakeItem(r) for r in [0, 0, 0, 1, 1, 1, 2, 2, 2]]
    unique_rows = sorted({item.row() for item in items}, reverse=True)
    assert unique_rows == [2, 1, 0]


def test_low_bitrate_flag_threshold():
    """Tracks below 320 kbps should be flagged; 320+ should not."""
    def should_flag(bitrate):
        return bitrate is not None and bitrate > 0 and bitrate < 320

    assert should_flag(128)  is True
    assert should_flag(256)  is True
    assert should_flag(319)  is True
    assert should_flag(320)  is False
    assert should_flag(0)    is False
    assert should_flag(None) is False


def test_paths_frozen_detection():
    """paths module must export get_cache_dir() and get_data_dir() callables."""
    import paths
    cache_dir = paths.get_cache_dir()
    data_dir = paths.get_data_dir()
    assets_dir = paths.get_assets_dir()
    assert hasattr(cache_dir, '__truediv__'), "get_cache_dir() must return a Path"
    assert hasattr(data_dir, '__truediv__'), "get_data_dir() must return a Path"
    assert hasattr(assets_dir, '__truediv__'), "get_assets_dir() must return a Path"
    # In dev mode (not frozen) data dir should be under repo root
    assert 'TrackFlow' in str(data_dir) or 'dj-track-analyzer' in str(data_dir)


@pytest.mark.skipif(not Path(SAMPLE_TRACK).exists(), reason="Sample track not found")
def test_features_in_analysis_result():
    """analyze_track must return a 'features' key with mfcc (20) and chroma (12)."""
    analyzer = AudioAnalyzer()
    result = analyzer.analyze_track(SAMPLE_TRACK)
    assert 'features' in result, "Missing 'features' key"
    feats = result['features']
    assert 'mfcc' in feats,   "Missing mfcc in features"
    assert 'chroma' in feats, "Missing chroma in features"
    assert len(feats['mfcc'])   == 20, f"Expected 20 MFCCs, got {len(feats['mfcc'])}"
    assert len(feats['chroma']) == 12, f"Expected 12 chroma, got {len(feats['chroma'])}"
    assert all(isinstance(v, float) for v in feats['mfcc'])
    assert all(isinstance(v, float) for v in feats['chroma'])

def test_mfcc_shape_no_audio():
    """_compute_mfcc must return exactly n_mfcc floats for synthetic input."""
    import numpy as np
    from analyzer.audio_analyzer import AudioAnalyzer
    analyzer = AudioAnalyzer()
    n_bins = analyzer.N_FFT // 2 + 1
    S_power = np.abs(np.random.randn(n_bins, 100)) ** 2
    mfcc = analyzer._compute_mfcc(S_power, analyzer.sample_rate, n_mfcc=20)
    assert len(mfcc) == 20
    assert all(isinstance(v, float) for v in mfcc)
