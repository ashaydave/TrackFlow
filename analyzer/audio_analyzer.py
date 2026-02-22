"""
DJ Track Analyzer - Core Audio Analysis Engine
Optimized for speed: analyzes first 60s only (sufficient for BPM/key/energy).
Uses soundfile + soxr for fast MP3 decode, scipy FFT for STFT (avoids librosa
numba cold-start penalty of ~8s). Waveform data is generated separately by
WaveformThread.
"""

import numpy as np
from scipy.fft import rfft, rfftfreq
from scipy.signal import get_window
import soundfile as sf
import soxr
from mutagen import File as MutagenFile
from pathlib import Path
import json


class AudioAnalyzer:
    """Fast audio analysis — BPM, key, energy from first 60 seconds."""

    ANALYSIS_DURATION = 60  # seconds — sufficient for electronic music
    SAMPLE_RATE = 22050
    HOP_LENGTH = 512
    N_FFT = 2048

    def __init__(self, fast_mode=True):
        self.sample_rate = self.SAMPLE_RATE
        self.fast_mode = fast_mode  # kept for API compat
        # Pre-build Hann window and mel filterbank at init (cheap, ~5 ms)
        self._window = get_window('hann', self.N_FFT).astype(np.float32)
        self._mel_fb = self._build_mel_fb(self.SAMPLE_RATE, self.N_FFT)

    # ── PUBLIC ────────────────────────────────────────────────────────────

    def analyze_track(self, file_path):
        """
        Analyze a track. Only loads first 60s for speed.
        Duration and metadata come from mutagen (no audio decode).

        Returns:
            dict with: file_path, filename, bpm, key, energy,
                       metadata, audio_info, duration
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Track not found: {file_path}")

        # --- Fast path: metadata + duration from tags (no audio decode) ---
        metadata = self._extract_metadata(file_path)
        audio_info = self._get_audio_info(file_path)

        # --- Load only first 60s via soundfile + soxr (avoids numba) ---
        y, sr = self._load_audio(file_path)

        # --- STFT once, reuse for BPM, key and energy ---
        S_power, n_frames = self._compute_stft(y)

        results = {
            'file_path': str(file_path.absolute()),
            'filename': file_path.name,
            'bpm': self._detect_bpm(S_power, sr),
            'key': self._detect_key(S_power, n_frames, sr),
            'energy': self._calculate_energy_full(file_path),
            'metadata': metadata,
            'audio_info': audio_info,
            'duration': audio_info.get('duration', len(y) / sr),
        }

        return results

    # ── AUDIO LOAD ────────────────────────────────────────────────────────

    def _load_audio(self, file_path):
        """Load up to ANALYSIS_DURATION seconds using soundfile + soxr.

        soundfile (libsndfile 1.2+) reads MP3 natively in ~0.1 s.
        soxr resamples without numba JIT overhead.
        """
        info = sf.info(str(file_path))
        frames_to_read = min(
            int(info.samplerate * self.ANALYSIS_DURATION),
            info.frames,
        )
        data, sr_native = sf.read(
            str(file_path),
            frames=frames_to_read,
            dtype='float32',
            always_2d=False,
        )
        # Mono mix
        if data.ndim == 2:
            data = data.mean(axis=1)
        # Resample to analysis sample rate if needed
        if sr_native != self.sample_rate:
            data = soxr.resample(data, sr_native, self.sample_rate, quality='HQ')
        return data, self.sample_rate

    # ── STFT ─────────────────────────────────────────────────────────────

    def _compute_stft(self, y):
        """Compute power spectrogram via scipy rfft (no librosa/numba needed)."""
        y_pad = np.pad(y, self.N_FFT // 2)
        n_frames = 1 + (len(y_pad) - self.N_FFT) // self.HOP_LENGTH
        strides = (y_pad.strides[0], y_pad.strides[0] * self.HOP_LENGTH)
        framed = np.lib.stride_tricks.as_strided(
            y_pad,
            shape=(self.N_FFT, n_frames),
            strides=strides,
        ).copy()
        Sc = rfft(framed * self._window.reshape(-1, 1), axis=0)
        S_power = np.abs(Sc) ** 2
        return S_power, n_frames

    # ── BPM ──────────────────────────────────────────────────────────────

    def _detect_bpm(self, S_power, sr):
        """BPM via mel onset flux + autocorrelation (no numba/librosa STFT)."""
        try:
            S_mel = self._mel_fb @ S_power.astype(np.float32)
            S_mel_db = 10 * np.log10(S_mel + 1e-10)
            # Spectral flux: positive differences across time frames
            flux = np.maximum(0, np.diff(S_mel_db, axis=1)).mean(axis=0)
            fps = sr / self.HOP_LENGTH
            env = flux - flux.mean()
            # Autocorrelation in the BPM range 60–200
            corr = np.correlate(env, env, mode='full')
            corr = corr[len(corr) // 2:]
            lag_min = max(1, int(fps * 60 / 200))
            lag_max = min(len(corr) - 1, int(fps * 60 / 60))
            peak_lag = np.argmax(corr[lag_min:lag_max]) + lag_min
            bpm = fps * 60 / peak_lag
            return round(float(bpm), 1)
        except Exception as e:
            print(f"BPM detection failed: {e}")
            return None

    @staticmethod
    def _build_mel_fb(sr, n_fft, n_mels=128):
        """Pure-numpy mel filterbank (no librosa, no numba)."""
        def hz_to_mel(h):
            return 2595 * np.log10(1 + h / 700)

        def mel_to_hz(m):
            return 700 * (10 ** (m / 2595) - 1)

        freqs = rfftfreq(n_fft, d=1.0 / sr)
        mel_pts = np.linspace(hz_to_mel(0), hz_to_mel(sr / 2), n_mels + 2)
        hz_pts = mel_to_hz(mel_pts)
        fb = np.zeros((n_mels, len(freqs)), dtype=np.float32)
        for i in range(n_mels):
            lo, mid, hi = hz_pts[i], hz_pts[i + 1], hz_pts[i + 2]
            rise = (freqs - lo) / (mid - lo + 1e-8)
            fall = (hi - freqs) / (hi - mid + 1e-8)
            fb[i] = np.clip(np.minimum(rise, fall), 0, 1)
        return fb

    # ── KEY ──────────────────────────────────────────────────────────────

    def _detect_key(self, S_power, n_frames, sr):
        """Key detection using chroma from STFT bins + KS profiles."""
        try:
            n_frames_30s = min(int(30 * sr / self.HOP_LENGTH), n_frames)
            S_30 = S_power[:, :n_frames_30s]
            chroma_avg = self._compute_chroma(S_30, sr)
            key_index = int(np.argmax(chroma_avg))
            is_major = self._is_major_key(chroma_avg)
            return {
                'notation': self._index_to_key(key_index, is_major),
                'camelot': self._to_camelot(key_index, is_major),
                'open_key': self._to_open_key(key_index, is_major),
                'confidence': 'medium',
            }
        except Exception as e:
            print(f"Key detection failed: {e}")
            return {
                'notation': 'Unknown',
                'camelot': 'N/A',
                'open_key': 'N/A',
                'confidence': 'none',
            }

    def _compute_chroma(self, S_power, sr):
        """Map STFT power bins to 12 pitch classes (no librosa needed).

        Bins are averaged (not summed) within each pitch class so that
        high-frequency pitch classes — which have more STFT bins — do not
        dominate the result.  This approximates the equal-per-semitone
        energy contribution of a CQT-based chroma.
        """
        freqs_hz = rfftfreq(self.N_FFT, d=1.0 / sr)
        chroma = np.zeros(12, dtype=np.float64)
        counts = np.zeros(12, dtype=np.float64)
        for i, f in enumerate(freqs_hz[1:], 1):
            if 27.5 <= f <= 4186:  # piano-range only
                midi = 12 * np.log2(f / 440.0) + 69
                pc = int(round(midi)) % 12
                chroma[pc] += S_power[i].mean()
                counts[pc] += 1.0
        # Average energy per bin within each pitch class
        chroma /= np.maximum(counts, 1.0)
        return chroma

    def _is_major_key(self, chroma_avg):
        """Krumhansl-Schmuckler major/minor classification."""
        major_profile = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09,
                                   2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
        minor_profile = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.97,
                                   2.73, 5.17, 3.00, 4.00, 1.94, 3.17])
        chroma_norm = chroma_avg / (np.sum(chroma_avg) + 1e-8)
        scores_maj = [
            np.dot(np.roll(chroma_norm, -i), major_profile / np.sum(major_profile))
            for i in range(12)
        ]
        scores_min = [
            np.dot(np.roll(chroma_norm, -i), minor_profile / np.sum(minor_profile))
            for i in range(12)
        ]
        return max(scores_maj) >= max(scores_min)

    def _index_to_key(self, key_index, is_major):
        keys = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        return f"{keys[key_index % 12]} {'Major' if is_major else 'Minor'}"

    def _to_camelot(self, key_index, is_major):
        camelot_major = ['8B', '3B', '10B', '5B', '12B', '7B', '2B', '9B', '4B', '11B', '6B', '1B']
        camelot_minor = ['5A', '12A', '7A', '2A', '9A', '4A', '11A', '6A', '1A', '8A', '3A', '10A']
        return (camelot_major if is_major else camelot_minor)[key_index % 12]

    def _to_open_key(self, key_index, is_major):
        open_key_numbers = [1, 8, 3, 10, 5, 12, 7, 2, 9, 4, 11, 6]
        number = open_key_numbers[key_index % 12]
        return f"{number}{'m' if is_major else 'd'}"

    # ── ENERGY ───────────────────────────────────────────────────────────

    def _calculate_energy_full(self, file_path):
        """Full-track energy RMS via chunked soundfile reads — no large array in memory."""
        CHUNK = 65536
        try:
            sum_sq = 0.0
            n_frames = 0
            with sf.SoundFile(str(file_path)) as f:
                for block in f.blocks(blocksize=CHUNK, dtype='float32'):
                    mono = block.mean(axis=1) if block.ndim == 2 else block
                    sum_sq += float(np.sum(mono ** 2))
                    n_frames += len(mono)
            if n_frames == 0:
                raise ValueError("Empty audio file")
            avg_rms = float(np.sqrt(sum_sq / n_frames))
            thresholds = [0.05, 0.08, 0.11, 0.14, 0.17, 0.20, 0.23, 0.26, 0.30]
            energy = next(
                (i + 1 for i, t in enumerate(thresholds) if avg_rms < t), 10
            )
            descriptions = {
                1: 'Very Low', 2: 'Low', 3: 'Low-Med', 4: 'Medium', 5: 'Medium',
                6: 'Med-High', 7: 'High', 8: 'High', 9: 'Very High', 10: 'Peak',
            }
            return {'level': energy, 'rms': avg_rms, 'description': descriptions[energy]}
        except Exception as e:
            print(f"Full energy calculation failed: {e}")
            return {'level': 5, 'rms': 0.0, 'description': 'Unknown'}

    # ── METADATA ─────────────────────────────────────────────────────────

    def _extract_metadata(self, file_path):
        try:
            audio = MutagenFile(str(file_path))
            if audio is None:
                return self._default_metadata()
            return {
                'artist':  self._get_tag(audio, ['artist',  'TPE1', '\xa9ART']),
                'title':   self._get_tag(audio, ['title',   'TIT2', '\xa9nam']),
                'album':   self._get_tag(audio, ['album',   'TALB', '\xa9alb']),
                'genre':   self._get_tag(audio, ['genre',   'TCON', '\xa9gen']),
                'year':    self._get_tag(audio, ['date',    'TDRC', '\xa9day']),
                'comment': self._get_tag(audio, ['comment', 'COMM', '\xa9cmt']),
            }
        except Exception:
            return self._default_metadata()

    def _get_tag(self, audio, tag_names):
        for tag in tag_names:
            if tag in audio:
                value = audio[tag]
                return str(value[0]) if isinstance(value, list) else str(value)
        return ''

    def _default_metadata(self):
        return {
            'artist': '', 'title': '', 'album': '',
            'genre': '', 'year': '', 'comment': '',
        }

    # ── AUDIO INFO ───────────────────────────────────────────────────────

    def _get_audio_info(self, file_path):
        try:
            audio = MutagenFile(str(file_path))
            if audio is None:
                return self._default_audio_info(file_path)
            bitrate     = getattr(audio.info, 'bitrate',     0) // 1000
            sample_rate = getattr(audio.info, 'sample_rate', 44100)
            channels    = getattr(audio.info, 'channels',    2)
            duration    = getattr(audio.info, 'length',      0.0)
            file_size   = round(file_path.stat().st_size / (1024 * 1024), 2)
            return {
                'format':       file_path.suffix.upper().replace('.', ''),
                'bitrate':      bitrate,
                'sample_rate':  sample_rate,
                'channels':     channels,
                'file_size_mb': file_size,
                'duration':     duration,
            }
        except Exception:
            return self._default_audio_info(file_path)

    def _default_audio_info(self, file_path):
        return {
            'format':       file_path.suffix.upper().replace('.', ''),
            'bitrate':      0,
            'sample_rate':  44100,
            'channels':     2,
            'file_size_mb': round(file_path.stat().st_size / (1024 * 1024), 2),
            'duration':     0.0,
        }

    # ── SAVE ─────────────────────────────────────────────────────────────

    def save_analysis(self, results, output_path=None):
        if output_path is None:
            output_path = Path(results['file_path']).with_suffix('.analysis.json')
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2)
        return output_path
