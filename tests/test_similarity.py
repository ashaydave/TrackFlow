"""Tests for MFCC+chroma cosine similarity engine."""
import pytest
import json
import hashlib
import numpy as np
from pathlib import Path
from unittest.mock import patch
from analyzer.similarity import find_similar, _cosine_similarity, _load_feature_vector


def _make_cache(tmp_path, fp, mfcc, chroma, bpm=120.0, camelot='8B'):
    """Write a fake cache JSON for a fake file path using the same key formula."""
    key = hashlib.md5(f"{fp}|1000.0|1000".encode()).hexdigest()
    data = {
        'file_path': fp,
        'filename': Path(fp).name,
        'bpm': bpm,
        'key': {'camelot': camelot, 'notation': 'C Major'},
        'features': {'mfcc': mfcc, 'chroma': chroma},
    }
    (tmp_path / f"{key}.json").write_text(json.dumps(data))


def test_cosine_similarity_identical():
    """Identical vectors → similarity 1.0."""
    v = [1.0] * 32
    assert abs(_cosine_similarity(v, v) - 1.0) < 1e-6


def test_cosine_similarity_orthogonal():
    """Orthogonal vectors → similarity 0.0."""
    a = [1.0, 0.0]
    b = [0.0, 1.0]
    assert abs(_cosine_similarity(a, b)) < 1e-6


def test_find_similar_excludes_query(tmp_path):
    """Query track must NOT appear in its own results."""
    mfcc = [float(i) for i in range(20)]
    chroma = [float(i) for i in range(12)]
    fp_query = str(tmp_path / "query.mp3")
    fp_other = str(tmp_path / "other.mp3")

    with patch('pathlib.Path.stat') as mock_stat:
        mock_stat.return_value.st_mtime = 1000.0
        mock_stat.return_value.st_size  = 1000
        _make_cache(tmp_path, fp_query, mfcc, chroma)
        _make_cache(tmp_path, fp_other, mfcc, chroma)
        results = find_similar(fp_query, [fp_query, fp_other], tmp_path, top_n=5)

    fps = [r['file_path'] for r in results]
    assert fp_query not in fps, "Query track must not appear in results"
    assert fp_other in fps


def test_find_similar_skips_no_features(tmp_path):
    """Tracks without 'features' in cache are silently skipped."""
    fp_query = str(tmp_path / "query.mp3")
    fp_nofeat = str(tmp_path / "nofeat.mp3")
    mfcc   = [1.0] * 20
    chroma = [1.0] * 12

    with patch('pathlib.Path.stat') as mock_stat:
        mock_stat.return_value.st_mtime = 1000.0
        mock_stat.return_value.st_size  = 1000
        _make_cache(tmp_path, fp_query, mfcc, chroma)
        # Write cache WITHOUT features
        key = hashlib.md5(f"{fp_nofeat}|1000.0|1000".encode()).hexdigest()
        no_feat = {'file_path': fp_nofeat, 'filename': 'nofeat.mp3',
                   'bpm': 120.0, 'key': {'camelot': '8B'}}
        (tmp_path / f"{key}.json").write_text(json.dumps(no_feat))
        results = find_similar(fp_query, [fp_query, fp_nofeat], tmp_path, top_n=5)

    assert all(r['file_path'] != fp_nofeat for r in results)


def test_find_similar_returns_sorted(tmp_path):
    """Results must be sorted by similarity descending."""
    mfcc_q      = [1.0] * 20
    chroma_q    = [1.0] * 12
    mfcc_close  = [1.0] * 20   # identical → highest similarity
    chroma_close= [1.0] * 12
    mfcc_far    = [-1.0] * 20  # opposite → lowest similarity
    chroma_far  = [-1.0] * 12

    fp_q     = str(tmp_path / "query.mp3")
    fp_close = str(tmp_path / "close.mp3")
    fp_far   = str(tmp_path / "far.mp3")

    with patch('pathlib.Path.stat') as mock_stat:
        mock_stat.return_value.st_mtime = 1000.0
        mock_stat.return_value.st_size  = 1000
        _make_cache(tmp_path, fp_q,     mfcc_q,     chroma_q)
        _make_cache(tmp_path, fp_close, mfcc_close, chroma_close)
        _make_cache(tmp_path, fp_far,   mfcc_far,   chroma_far)
        results = find_similar(fp_q, [fp_q, fp_close, fp_far], tmp_path, top_n=5)

    assert len(results) == 2
    assert results[0]['file_path'] == fp_close
    assert results[0]['similarity'] > results[1]['similarity']
