# analyzer/genre_detector.py
"""
Genre detection using ONNX Runtime + Discogs-EffNet (400 Discogs music styles).

Uses the official Essentia ONNX export of the Discogs-EffNet model, which runs
via onnxruntime — works on Windows, macOS and Linux with no extra dependencies.

Two files are downloaded on first use (~37 MB total):
  discogs-effnet-bsdynamic-1.onnx  — full EffNet model (backbone + genre head)
  genre_discogs400-discogs-effnet-1.json  — class labels

Audio preprocessing replicates Essentia's TensorflowInputMusiCNN exactly:
  - 16 kHz mono
  - 96-band mel spectrogram (Slaney scale, unit_tri normalization,
    512-sample window, 256-sample hop)
  - Essentia log compression: log10(10000 * E + 1) → values ≈ [0, 4]
  - Non-overlapping 128-frame patches → model input [n, 128, 96]
    where axis 1 = time frames, axis 2 = mel bands
  - No per-patch normalization (raw log-compressed values fed to model)

Discogs labels are formatted "Electronic---Deep House"; this module strips
the top-level category so the UI shows "Deep House" instead.
"""

import hashlib
import json
import urllib.request
from pathlib import Path

import numpy as np
from scipy.fft import rfft
from scipy.signal import get_window

from paths import get_cache_dir, get_models_dir


# ---------------------------------------------------------------------------
# Model manifest — ONNX build, Windows-compatible via onnxruntime
# ---------------------------------------------------------------------------

MODELS = {
    "effnet": {
        "url": (
            "https://essentia.upf.edu/models/feature-extractors/"
            "discogs-effnet/discogs-effnet-bsdynamic-1.onnx"
        ),
        "filename": "discogs-effnet-bsdynamic-1.onnx",
        "size_mb": 37,
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
# Mel spectrogram constants  (match Essentia's TensorflowInputMusiCNN exactly)
# ---------------------------------------------------------------------------

_SR     = 16_000   # sample rate (Hz)
_N_FFT  = 512      # FFT window (32 ms at 16 kHz)
_HOP    = 256      # hop size   (16 ms at 16 kHz)
_N_MELS = 96       # mel bands  (Slaney scale, unit_tri normalization)
_FMIN   = 0.0
_FMAX   = 8_000.0  # Nyquist for 16 kHz
_PATCH  = 128      # time-frames per patch → model input [n, 128_time, 96_mel]

# Built once on first call
_MEL_FB: np.ndarray | None = None
_WINDOW: np.ndarray | None = None


def _build_mel_fb() -> np.ndarray:
    """Slaney mel filterbank with unit_tri normalization — [n_mels, n_bins] float32.

    Replicates Essentia MelBands(warpingFormula='slaneyMel', normalization='unit_tri'):
      - Linear mel scale below 1 kHz, logarithmic above
      - Each triangular filter divided by its bandwidth (area normalization)
    """
    # Slaney mel scale constants
    _MIN_LOG_HZ  = 1000.0
    _SP          = 200.0 / 3.0          # linear Hz-per-mel below 1 kHz
    _MIN_LOG_MEL = _MIN_LOG_HZ / _SP
    _LOGSTEP     = np.log(6.4) / 27.0   # log step above 1 kHz

    def hz2mel(hz: np.ndarray) -> np.ndarray:
        hz = np.atleast_1d(np.asarray(hz, float))
        mel = hz / _SP
        mask = hz >= _MIN_LOG_HZ
        mel[mask] = _MIN_LOG_MEL + np.log(hz[mask] / _MIN_LOG_HZ) / _LOGSTEP
        return mel

    def mel2hz(mel: np.ndarray) -> np.ndarray:
        mel = np.atleast_1d(np.asarray(mel, float))
        hz = _SP * mel
        mask = mel >= _MIN_LOG_MEL
        hz[mask] = _MIN_LOG_HZ * np.exp(_LOGSTEP * (mel[mask] - _MIN_LOG_MEL))
        return hz

    freqs   = np.fft.rfftfreq(_N_FFT, d=1.0 / _SR).astype(np.float64)
    mel_pts = np.linspace(hz2mel(_FMIN), hz2mel(_FMAX), _N_MELS + 2)
    hz_pts  = mel2hz(mel_pts)

    fb = np.zeros((_N_MELS, len(freqs)), dtype=np.float32)
    for i in range(_N_MELS):
        lo, mid, hi = hz_pts[i], hz_pts[i + 1], hz_pts[i + 2]
        rise = (freqs - lo) / (mid - lo + 1e-8)
        fall = (hi - freqs) / (hi - mid + 1e-8)
        tri  = np.clip(np.minimum(rise, fall), 0.0, 1.0)
        # unit_tri: divide by triangle area so filters are area-normalised
        tri *= 2.0 / (hi - lo + 1e-8)
        fb[i] = tri.astype(np.float32)
    return fb


def _mel_patches(audio: np.ndarray) -> np.ndarray:
    """
    Convert 16 kHz mono audio to non-overlapping mel spectrogram patches.

    Returns float32 array of shape [n_patches, 128, 96]
    where axis 1 = time frames (128 per patch) and axis 2 = mel bands (96).

    Preprocessing matches Essentia's TensorflowInputMusiCNN exactly:
      - Slaney mel filterbank with unit_tri normalization
      - Power spectrum fed through mel filterbank
      - Essentia log compression: log10(10000 * E + 1) → values ≈ [0, 4]
      - No per-patch z-score (raw log values passed directly to model)
    """
    global _MEL_FB, _WINDOW
    if _MEL_FB is None:
        _MEL_FB = _build_mel_fb()
    if _WINDOW is None:
        _WINDOW = get_window("hann", _N_FFT).astype(np.float32)

    audio = audio.astype(np.float32)

    # Pad so we get at least one full patch
    min_len = _PATCH * _HOP + _N_FFT
    if len(audio) < min_len:
        audio = np.pad(audio, (0, min_len - len(audio)))

    # Strided frame extraction (no Python loop) — same pattern as audio_analyzer.py
    y_pad = np.pad(audio, _N_FFT // 2)
    n_frames = 1 + (len(y_pad) - _N_FFT) // _HOP
    strides = (y_pad.strides[0], y_pad.strides[0] * _HOP)
    framed = np.lib.stride_tricks.as_strided(
        y_pad, shape=(_N_FFT, n_frames), strides=strides
    ).copy()  # [n_fft, n_frames]

    # Power spectrum: [n_bins, n_frames]
    S = np.abs(rfft(framed * _WINDOW.reshape(-1, 1), axis=0)) ** 2

    # Slaney mel spectrogram: [96, n_frames]
    mel = _MEL_FB @ S

    # Essentia log compression: log10(10000 * E + 1) — output range ≈ [0, 4]
    mel_log = np.log10(10_000.0 * mel + 1.0)  # [96, n_frames]

    # Extract non-overlapping patches of 128 time frames
    n_patches = n_frames // _PATCH
    if n_patches == 0:
        # Pad to one full patch
        pad_cols = _PATCH - mel_log.shape[1]
        mel_log = np.pad(mel_log, ((0, 0), (0, pad_cols)))
        n_patches = 1

    mel_trim = mel_log[:, : n_patches * _PATCH]             # [96, n*128]
    patches  = mel_trim.reshape(_N_MELS, n_patches, _PATCH) # [96, n, 128]
    patches  = patches.transpose(1, 2, 0)                   # [n, 128, 96]

    # No per-patch normalisation — Essentia feeds raw log values to the model
    return patches.astype(np.float32)


# ---------------------------------------------------------------------------
# Model download helper
# ---------------------------------------------------------------------------

def ensure_models(status_callback=None) -> dict | None:
    """
    Download ONNX model + labels JSON if not already on disk.

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
            dest.unlink(missing_ok=True)
            return None

    return local_paths


# ---------------------------------------------------------------------------
# Genre cache  (per-track, same scheme as batch_analyzer)
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
    Wraps the Discogs-EffNet ONNX model for music genre classification.

    Produces the same 400 Discogs music-style labels as the Essentia
    TF version, with no platform dependency beyond onnxruntime + numpy.

    Usage::

        model_paths = ensure_models()
        if model_paths:
            d = GenreDetector(model_paths)
            genres = d.detect("/path/to/track.mp3")
            print(d.format_genres(genres))   # "Deep House / Tech House"

    Requires: pip install onnxruntime
    """

    @staticmethod
    def available() -> bool:
        """Return True if onnxruntime is importable."""
        try:
            import onnxruntime  # noqa: F401
            return True
        except Exception as exc:
            print(f"onnxruntime import failed: {type(exc).__name__}: {exc}")
            return False

    def __init__(self, model_paths: dict):
        """
        Load the ONNX session and label list.
        model_paths is the dict returned by ensure_models().
        """
        import onnxruntime as ort

        opts = ort.SessionOptions()
        opts.inter_op_num_threads = 1
        opts.intra_op_num_threads = 2
        opts.log_severity_level = 3   # suppress onnxruntime INFO spam

        self._session = ort.InferenceSession(
            str(model_paths["effnet"]),
            sess_options=opts,
            providers=["CPUExecutionProvider"],
        )

        # Discover input name at runtime (ONNX export may rename nodes)
        self._input_name = self._session.get_inputs()[0].name

        # Pick the output with shape [..., 400] = genre predictions
        # (the model also has an embeddings output of shape [..., 1280])
        self._pred_name = self._session.get_outputs()[0].name
        for out in self._session.get_outputs():
            shape = getattr(out, "shape", None)
            if shape and len(shape) >= 2 and shape[-1] == 400:
                self._pred_name = out.name
                break

        # Load and clean labels: "Electronic---Deep House" → "Deep House"
        with open(model_paths["labels"]) as f:
            meta = json.load(f)
        raw_labels: list[str] = meta.get("classes", [])
        self._labels: list[str] = [
            lbl.split("---")[-1].strip() for lbl in raw_labels
        ]

    def detect(self, file_path: str, top_n: int = 3) -> list[tuple[str, float]]:
        """
        Run genre inference on an audio file.

        Loads up to 30 seconds of audio at 16 kHz, computes mel patches,
        runs the ONNX EffNet model, and returns top_n (genre, score) pairs.
        Raises Exception on failure — caller should catch.
        """
        import soundfile as sf
        import soxr

        info = sf.info(str(file_path))
        max_frames = min(info.frames, 30 * info.samplerate)
        audio, _ = sf.read(
            str(file_path), frames=max_frames, dtype="float32", always_2d=False
        )
        if audio.ndim == 2:
            audio = audio.mean(axis=1)
        if info.samplerate != _SR:
            audio = soxr.resample(audio, info.samplerate, _SR, quality="HQ")

        patches = _mel_patches(audio)   # [n, 128, 96]

        preds = self._session.run(
            [self._pred_name],
            {self._input_name: patches},
        )[0]  # [n, 400]

        avg = np.mean(preds, axis=0)    # [400]
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
        Convert genre list to a display string.

        e.g. [("Deep House", 0.42), ("Tech House", 0.18)] → "Deep House / Tech House"

        Genres below min_score are filtered out.
        """
        filtered = [g for g, s in genres if s >= min_score]
        return " / ".join(filtered[:max_display]) if filtered else ""
