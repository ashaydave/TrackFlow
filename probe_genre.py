# -*- coding: utf-8 -*-
"""
Genre probe — Phase 2 (old normalization variants) + Phase 3 (correct Essentia pipeline).

Phase 3 implements the EXACT Essentia TensorflowInputMusiCNN preprocessing:
  - 96 Slaney mel bands with unit_tri normalization
  - Power spectrum
  - log10(10000 * E + 1)  [NOT 10*log10, NOT z-score]
  - 128-frame patches  ->  model input [n, 128_time, 96_mel]
"""
import sys, json
import numpy as np
from pathlib import Path

MODEL    = Path("data/models/discogs-effnet-bsdynamic-1.onnx")
LABELS_F = Path("data/models/genre_discogs400-discogs-effnet-1.json")

if not MODEL.exists():
    print("Model not downloaded yet."); sys.exit(0)

import onnxruntime as ort
sess = ort.InferenceSession(str(MODEL), providers=["CPUExecutionProvider"])
input_name = sess.get_inputs()[0].name
pred_name  = sess.get_outputs()[0].name
for o in sess.get_outputs():
    if o.shape and o.shape[-1] == 400: pred_name = o.name; break

with open(LABELS_F) as f:
    meta = json.load(f)
labels = [l.split("---")[-1].strip() for l in meta.get("classes", [])]

# Search for test audio — include Shazam folder on Desktop
TEST = None
search_dirs = [
    Path("downloads"),
    Path("."),
    Path.home() / "Desktop" / "Shazam",
    Path.home() / "Downloads",
]
for d in search_dirs:
    if not d.exists():
        continue
    hits = sorted(
        list(d.glob("*.mp3")) + list(d.glob("*.flac")) + list(d.glob("*.wav")),
        key=lambda p: p.stat().st_mtime, reverse=True
    )
    if hits:
        TEST = hits[0]
        print(f"Searching in: {d}")
        break

if not TEST:
    print("No test audio file found."); sys.exit(0)

print(f"Track: {TEST.name}")

import soundfile as sf, soxr
from scipy.fft import rfft
from scipy.signal import get_window

SR, N_FFT, HOP = 16000, 512, 256
window_hann = get_window("hann", N_FFT).astype(np.float32)

info = sf.info(str(TEST))
audio, _ = sf.read(str(TEST), frames=min(info.frames, 30*info.samplerate), dtype="float32", always_2d=False)
if audio.ndim == 2: audio = audio.mean(axis=1)
if info.samplerate != SR: audio = soxr.resample(audio, info.samplerate, SR, quality="HQ")

# ── Shared helpers ────────────────────────────────────────────────────────────

def get_framed(audio_arr, n_fft, hop):
    y_pad = np.pad(audio_arr, n_fft//2)
    n = 1 + (len(y_pad) - n_fft) // hop
    st = (y_pad.strides[0], y_pad.strides[0]*hop)
    return np.lib.stride_tricks.as_strided(y_pad, (n_fft, n), st).copy()

def run(patches, tag):
    pv = patches.flatten()
    preds = sess.run([pred_name], {input_name: patches})[0]
    avg = np.mean(preds, axis=0)
    top = np.argsort(avg)[::-1][:5]
    nz  = np.sum(avg > 1e-4)
    print(f"\n  [{tag}]")
    print(f"   patches shape: {patches.shape}   input range [{pv.min():.3f}, {pv.max():.3f}]  mean={pv.mean():.3f}")
    print(f"   preds range [{avg.min():.4f}, {avg.max():.4f}]  sum={avg.sum():.3f}  nonzero={nz}")
    for i in top:
        if i < len(labels): print(f"    {avg[i]:.4f}  {labels[i]}")

# ═══════════════════════════════════════════════════════════════════════════════
# Phase 2  (old variants — N_MELS=128, PATCH=96, Slaney+utri, MAG 10log10)
# ═══════════════════════════════════════════════════════════════════════════════
N_MELS_OLD, PATCH_OLD = 128, 96

def slaney_utri_fb_128():
    MIN_LOG_HZ, SP = 1000.0, 200/3
    MIN_LOG_MEL = MIN_LOG_HZ/SP
    LOGSTEP = np.log(6.4)/27
    def hz2mel(hz):
        hz = np.atleast_1d(np.asarray(hz, float)); mel = hz/SP
        lm = hz>=MIN_LOG_HZ; mel[lm]=MIN_LOG_MEL+np.log(hz[lm]/MIN_LOG_HZ)/LOGSTEP
        return mel
    def mel2hz(mel):
        mel = np.atleast_1d(np.asarray(mel, float)); hz = SP*mel
        lm = mel>=MIN_LOG_MEL; hz[lm]=MIN_LOG_HZ*np.exp(LOGSTEP*(mel[lm]-MIN_LOG_MEL))
        return hz
    freqs = np.fft.rfftfreq(N_FFT, 1./SR)
    pts = np.linspace(hz2mel(0), hz2mel(8000), N_MELS_OLD+2); hz = mel2hz(pts)
    fb = np.zeros((N_MELS_OLD, len(freqs)), np.float32)
    for i in range(N_MELS_OLD):
        lo,mid,hi = hz[i],hz[i+1],hz[i+2]
        fb[i] = np.clip(np.minimum((freqs-lo)/(mid-lo+1e-8),(hi-freqs)/(hi-mid+1e-8)),0,1)
        fb[i] *= 2./(hi-lo+1e-8)
    return fb

fb128 = slaney_utri_fb_128()
framed = get_framed(audio, N_FFT, HOP)
fft_mag = np.abs(rfft(framed * window_hann.reshape(-1,1), axis=0))
mel_db = 10.*np.log10(np.maximum(fb128 @ fft_mag, 1e-7))   # [128, n_frames]
print(f"\n-- Phase 2 base (N_MELS=128, PATCH=96, Slaney+utri, MAG 10log10) --")
print(f"   mel_db: range=[{mel_db.min():.1f}, {mel_db.max():.1f}]  mean={mel_db.mean():.1f}  std={mel_db.std():.1f}")

def to_patches_old(spec):
    n_p = spec.shape[1]//PATCH_OLD
    if n_p == 0: n_p=1; spec=np.pad(spec,((0,0),(0,PATCH_OLD-spec.shape[1])))
    return spec[:,:n_p*PATCH_OLD].reshape(N_MELS_OLD,n_p,PATCH_OLD).transpose(1,0,2).astype(np.float32)

# 1–7: select a few key variants from Phase 2
m7 = np.clip(mel_db - mel_db.max(), -80, 0)
m7 = (m7 + 80.) / 80.
run(to_patches_old(mel_db.copy()), "P2-baseline: Slaney 128 MAG 10log10 (no norm)")
run(to_patches_old(m7),           "P2-max-norm [0,1]: best old result (281 nonzero)")

# ═══════════════════════════════════════════════════════════════════════════════
# Phase 3  CORRECT Essentia preprocessing (N_MELS=96, PATCH=128)
# ═══════════════════════════════════════════════════════════════════════════════
N_MELS_NEW, PATCH_NEW = 96, 128

def slaney_utri_fb_96():
    """Slaney mel scale, unit_tri normalization, 96 bands (Essentia default)."""
    MIN_LOG_HZ = 1000.0
    SP = 200.0 / 3.0
    MIN_LOG_MEL = MIN_LOG_HZ / SP
    LOGSTEP = np.log(6.4) / 27.0
    def hz2mel(hz):
        hz = np.atleast_1d(np.asarray(hz, float)); mel = hz / SP
        mask = hz >= MIN_LOG_HZ
        mel[mask] = MIN_LOG_MEL + np.log(hz[mask] / MIN_LOG_HZ) / LOGSTEP
        return mel
    def mel2hz(mel):
        mel = np.atleast_1d(np.asarray(mel, float)); hz = SP * mel
        mask = mel >= MIN_LOG_MEL
        hz[mask] = MIN_LOG_HZ * np.exp(LOGSTEP * (mel[mask] - MIN_LOG_MEL))
        return hz
    freqs   = np.fft.rfftfreq(N_FFT, 1.0/SR)
    mel_pts = np.linspace(hz2mel(0), hz2mel(8000), N_MELS_NEW+2)
    hz_pts  = mel2hz(mel_pts)
    fb = np.zeros((N_MELS_NEW, len(freqs)), np.float32)
    for i in range(N_MELS_NEW):
        lo, mid, hi = hz_pts[i], hz_pts[i+1], hz_pts[i+2]
        tri = np.clip(np.minimum((freqs-lo)/(mid-lo+1e-8),(hi-freqs)/(hi-mid+1e-8)),0,1)
        tri *= 2.0 / (hi - lo + 1e-8)
        fb[i] = tri.astype(np.float32)
    return fb

fb96 = slaney_utri_fb_96()

# Power spectrum
S = fft_mag ** 2    # fft_mag already computed above (magnitude); square for power

# Slaney mel with power
mel96 = fb96 @ S                               # [96, n_frames]

# Essentia log compression: log10(10000 * E + 1)
mel_log96 = np.log10(10_000.0 * mel96 + 1.0)  # [96, n_frames], range ~[0, 4]

print(f"\n-- Phase 3: CORRECT Essentia preprocessing (N_MELS=96, PATCH=128) --")
print(f"   mel_log96: range=[{mel_log96.min():.3f}, {mel_log96.max():.3f}]  mean={mel_log96.mean():.3f}  std={mel_log96.std():.3f}")

def to_patches_new(spec):
    """spec: [96, n_frames] -> [n, 128_time, 96_mel]"""
    n_p = spec.shape[1] // PATCH_NEW
    if n_p == 0:
        n_p = 1
        spec = np.pad(spec, ((0,0),(0, PATCH_NEW - spec.shape[1])))
    trim = spec[:, :n_p*PATCH_NEW]                            # [96, n*128]
    patches = trim.reshape(N_MELS_NEW, n_p, PATCH_NEW)        # [96, n, 128]
    return patches.transpose(1, 2, 0).astype(np.float32)      # [n, 128, 96]

run(to_patches_new(mel_log96), "P3-CORRECT: Slaney 96 POWER log10(10000E+1) no-zscore")

# P3 variant: also try with z-score for comparison
patches_p3 = to_patches_new(mel_log96)
mu  = patches_p3.mean(axis=(1,2), keepdims=True)
sg  = patches_p3.std(axis=(1,2),  keepdims=True) + 1e-8
run((patches_p3 - mu) / sg, "P3+zscore: Slaney 96 POWER log10(10000E+1) +zscore")
