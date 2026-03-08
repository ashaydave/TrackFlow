# analyzer/genre_detector.py
"""
Genre detection using Essentia + Discogs-EffNet (400 Discogs music styles).

Models are downloaded on first use from the Essentia model server (~42 MB total):
  - discogs-effnet-bs64-2.pb           (EffNet feature extractor, ~40 MB)
  - genre_discogs400-discogs-effnet-1.pb  (genre classification head, ~1 MB)
  - genre_discogs400-discogs-effnet-1.json  (class labels)

Gracefully disabled if essentia-tensorflow is not installed — GenreDetector.available()
returns False and GenreWorker skips genre analysis without crashing the app.

Discogs labels are formatted as "Electronic---Deep House"; this module strips the
top-level category so the UI shows "Deep House" instead of the raw label.
"""

import hashlib
import json
import urllib.request
from pathlib import Path

from paths import get_cache_dir, get_models_dir


# ---------------------------------------------------------------------------
# Model manifest
# ---------------------------------------------------------------------------

MODELS = {
    "effnet": {
        "url": (
            "https://essentia.upf.edu/models/feature-extractors/"
            "discogs-effnet/discogs-effnet-bs64-2.pb"
        ),
        "filename": "discogs-effnet-bs64-2.pb",
        "size_mb": 40,
    },
    "genre_head": {
        "url": (
            "https://essentia.upf.edu/models/classification-heads/"
            "genre_discogs400/genre_discogs400-discogs-effnet-1.pb"
        ),
        "filename": "genre_discogs400-discogs-effnet-1.pb",
        "size_mb": 1,
    },
    "labels": {
        "url": (
            "https://essentia.upf.edu/models/classification-heads/"
            "genre_discogs400/genre_discogs400-discogs-effnet-1.json"
        ),
        "filename": "genre_discogs400-discogs-effnet-1.json",
        "size_mb": 0.01,
    },
}


# ---------------------------------------------------------------------------
# Model download helper
# ---------------------------------------------------------------------------

def ensure_models(status_callback=None) -> dict | None:
    """
    Download genre models to data/models/ if not already present.

    Returns a dict mapping key → local Path on success, or None on failure.
    status_callback(msg: str) is called with progress messages if provided.
    """
    models_dir = get_models_dir()
    local_paths: dict[str, Path] = {}

    for key, info in MODELS.items():
        dest = models_dir / info["filename"]
        local_paths[key] = dest
        if dest.exists():
            continue

        msg = (
            f"Downloading genre model: {info['filename']} "
            f"(~{info['size_mb']} MB)…"
        )
        if status_callback:
            status_callback(msg)

        try:
            urllib.request.urlretrieve(info["url"], dest)
        except Exception as exc:
            err = f"Genre model download failed ({info['filename']}): {exc}"
            if status_callback:
                status_callback(err)
            # Clean up partial download
            dest.unlink(missing_ok=True)
            return None

    return local_paths


# ---------------------------------------------------------------------------
# Genre cache (per-track, same scheme as batch_analyzer)
# ---------------------------------------------------------------------------

def _genre_cache_key(file_path: Path) -> str:
    """Cache key: MD5 of absolute path + mtime + size, prefixed 'genre_'."""
    stat = file_path.stat()
    key_str = f"{file_path.absolute()}|{stat.st_mtime}|{stat.st_size}"
    return "genre_" + hashlib.md5(key_str.encode()).hexdigest()


def load_genre_cache(file_path: Path) -> str | None:
    """Return cached genre string (e.g. 'Deep House / Tech House') or None."""
    cache_file = get_cache_dir() / f"{_genre_cache_key(file_path)}.json"
    if cache_file.exists():
        try:
            with open(cache_file) as f:
                return json.load(f).get("genres")
        except Exception:
            cache_file.unlink(missing_ok=True)
    return None


def save_genre_cache(file_path: Path, genres_str: str) -> None:
    """Persist genre result so subsequent loads skip inference."""
    cache_file = get_cache_dir() / f"{_genre_cache_key(file_path)}.json"
    with open(cache_file, "w") as f:
        json.dump({"genres": genres_str}, f)


# ---------------------------------------------------------------------------
# GenreDetector
# ---------------------------------------------------------------------------

class GenreDetector:
    """
    Wraps Essentia's Discogs-EffNet pipeline.

    Usage::

        model_paths = ensure_models()
        if model_paths:
            detector = GenreDetector(model_paths)
            genres = detector.detect("/path/to/track.mp3")
            print(detector.format_genres(genres))   # "Deep House / Tech House"

    Requires: pip install essentia-tensorflow
    """

    @staticmethod
    def available() -> bool:
        """Return True if essentia-tensorflow is importable."""
        try:
            import essentia  # noqa: F401
            return True
        except ImportError:
            return False

    def __init__(self, model_paths: dict):
        """
        Initialise. Loads both TensorFlow graphs into memory.
        model_paths is the dict returned by ensure_models().
        """
        import essentia.standard as es
        import numpy as np

        self._es = es
        self._np = np

        self._effnet = es.TensorflowPredictEffnetDiscogs(
            graphFilename=str(model_paths["effnet"]),
            output="PartitionedCall:1",
        )
        self._genre_model = es.TensorflowPredict2D(
            graphFilename=str(model_paths["genre_head"]),
            input="serving_default_model_Placeholder",
            output="PartitionedCall:0",
        )

        # Clean labels: "Electronic---Deep House" → "Deep House"
        with open(model_paths["labels"]) as f:
            meta = json.load(f)
        self._labels: list[str] = [
            lbl.split("---")[-1].strip()
            for lbl in meta.get("classes", [])
        ]

    def detect(self, file_path: str, top_n: int = 3) -> list[tuple[str, float]]:
        """
        Run genre inference on an audio file.

        Loads the audio at 16 kHz mono (required by EffNet), computes embeddings,
        averages frame-level predictions, and returns the top_n genres.

        Returns list of (genre_label, score) sorted by score descending.
        Raises Exception on audio load or inference failure (caller should catch).
        """
        np = self._np
        audio = self._es.MonoLoader(filename=str(file_path), sampleRate=16000)()
        embeddings = self._effnet(audio)
        preds = self._genre_model(embeddings)
        avg = np.mean(preds, axis=0)
        top_idx = np.argsort(avg)[::-1][:top_n]
        return [
            (self._labels[i], float(avg[i]))
            for i in top_idx
            if i < len(self._labels)
        ]

    def format_genres(
        self,
        genres: list[tuple[str, float]],
        min_score: float = 0.05,
        max_display: int = 2,
    ) -> str:
        """
        Convert genre list to display string.

        e.g. [("Deep House", 0.42), ("Tech House", 0.18), ("House", 0.07)]
             → "Deep House / Tech House"

        Genres below min_score are filtered out.
        """
        filtered = [g for g, s in genres if s >= min_score]
        return " / ".join(filtered[:max_display]) if filtered else ""
