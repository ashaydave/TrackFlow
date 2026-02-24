"""
analyzer/similarity.py — MFCC+chroma cosine similarity search.

find_similar(query_fp, candidate_fps, cache_dir, top_n) compares the
32-dim feature vector of the query track against all cached candidates
and returns top_n results sorted by cosine similarity descending.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from paths import get_cache_dir


def _cache_key(file_path: str) -> str:
    """Reproduce the same cache key used by batch_analyzer."""
    p = Path(file_path)
    stat = p.stat()
    key_str = f"{p.absolute()}|{stat.st_mtime}|{stat.st_size}"
    return hashlib.md5(key_str.encode()).hexdigest()


def _load_feature_vector(file_path: str, cache_dir: Path) -> np.ndarray | None:
    """Load 32-dim feature vector from cache, or None if unavailable."""
    try:
        cache_file = cache_dir / f"{_cache_key(file_path)}.json"
        if not cache_file.exists():
            return None
        data = json.loads(cache_file.read_text())
        feats = data.get('features')
        if not feats:
            return None
        mfcc   = feats.get('mfcc', [])
        chroma = feats.get('chroma', [])
        if len(mfcc) != 20 or len(chroma) != 12:
            return None
        return np.array(mfcc + chroma, dtype=np.float32)
    except Exception:
        return None


def _cosine_similarity(a: list | np.ndarray, b: list | np.ndarray) -> float:
    """Cosine similarity between two vectors. Returns float in [-1, 1]."""
    va = np.asarray(a, dtype=np.float32)
    vb = np.asarray(b, dtype=np.float32)
    norm_a = float(np.linalg.norm(va))
    norm_b = float(np.linalg.norm(vb))
    if norm_a < 1e-9 or norm_b < 1e-9:
        return 0.0
    return float(np.dot(va, vb) / (norm_a * norm_b))


def find_similar(
    query_fp: str,
    candidate_fps: list[str],
    cache_dir: Path | None = None,
    top_n: int = 25,
) -> list[dict]:
    """
    Return top_n most similar tracks from candidate_fps.

    Each result dict has keys:
        file_path   str
        name        str   (filename stem)
        similarity  float (0.0–1.0, mapped from cosine [-1,1])
        bpm         float | None
        key         str   (Camelot notation or '--')
    """
    if cache_dir is None:
        cache_dir = get_cache_dir()

    query_vec = _load_feature_vector(query_fp, cache_dir)
    if query_vec is None:
        return []

    results = []
    for fp in candidate_fps:
        if fp == query_fp:
            continue
        vec = _load_feature_vector(fp, cache_dir)
        if vec is None:
            continue
        sim = _cosine_similarity(query_vec, vec)
        try:
            cache_file = cache_dir / f"{_cache_key(fp)}.json"
            meta = json.loads(cache_file.read_text())
        except Exception:
            meta = {}
        results.append({
            'file_path':  fp,
            'name':       Path(fp).stem,
            'similarity': round((sim + 1.0) / 2.0, 4),  # map [-1,1] → [0,1]
            'bpm':        meta.get('bpm'),
            'key':        meta.get('key', {}).get('camelot', '--'),
        })

    results.sort(key=lambda r: r['similarity'], reverse=True)
    return results[:top_n]
