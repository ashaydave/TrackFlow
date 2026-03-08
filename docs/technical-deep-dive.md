# Building TrackFlow: Deep Technical Dive Into a Desktop DJ Analysis Engine

## What is TrackFlow?

TrackFlow is a desktop DJ track analysis and management tool built with Python. It analyzes BPM, musical key, energy levels, and genre across your entire music library — then helps you find similar tracks, preview with precision looping, and organize playlists. Under the hood, it's a **custom signal processing engine with no heavy ML dependencies** until they're actually needed, built with a philosophy of precision and intentionality.

If you're a software engineer reading this, you'll appreciate the architectural choices. If you're a musician or DJ, you'll understand why they matter for production workflow.

---

## The Signal Processing Engine (No librosa, No Shortcuts)

About a year ago, I was standing at a crossroads: build the audio analysis layer with librosa (the industry-standard music information retrieval library in Python), or write it from scratch using SciPy.

The trade-off looked like this:
- **librosa**: Convenient, well-tested, used by thousands
- **librosa's hidden cost**: ~8 seconds of Numba JIT compilation on first import, adding 8 seconds of cold-start latency to application startup

For a desktop application, that's unacceptable. A user clicks the icon expecting the window in under two seconds, not eight.

So I decided to use **pure SciPy FFT** for spectrograms, **soxr for resampling**, and **NumPy's stride tricks for frame extraction**. The result is an analysis engine that can process a 60-second audio preview in under 100ms — no Numba, no cold-start, no compromise.

### BPM Detection — Autocorrelation on Spectral Flux

The algorithm is deceptively simple: extract a **mel spectrogram** from the first 60 seconds, compute **spectral flux** (frame-to-frame positive energy changes), then apply **autocorrelation** across the 60–200 BPM range.

Here's what happens under the hood:

1. Load first 60 seconds at 22,050 Hz using `soundfile`
2. Compute power spectrogram via `scipy.fft.rfft` with a Hann window
3. Apply mel filterbank (128 triangular filters mapping frequencies to the perceptual mel scale)
4. Convert to dB: `10 × log10(mel_power + 1e-10)`
5. Compute spectral flux: take only positive differences frame-to-frame (negative diffs = silence or reverb decay, not beats)
6. Run autocorrelation on the flux envelope in the lag range corresponding to 60–200 BPM
7. Peak lag → BPM

No onset-detection function approximations. No complex peak-picking heuristics. Just the physics of rhythm: a repeating signal has a strong autocorrelation at its period.

For electronic music (EDM, house, techno), where the beat is metronomic, this works beautifully.

### Musical Key — Krumhansl–Schmuckler Profiles

This is where music psychology meets code. The **Krumhansl–Schmuckler algorithm** is based on decades of listening studies: humans perceive pitch in a 12-note chromatic scale (C, C#, D, D#, E, F, F#, G, G#, A, A#, B), and each of the 24 possible keys (12 major + 12 minor) has a characteristic "tonal profile" — some notes are more central to the key, others are peripheral.

The algorithm:

1. Compute **chroma**: for each STFT bin, determine its pitch class using `midi = 12 × log2(freq / 440Hz) + 69`. Map each bin to one of 12 pitch classes (C through B), averaging energy within each class
2. Normalize the chroma vector to a probability distribution
3. Correlate against all 24 Krumhansl–Schmuckler profiles (predefined vectors learned from music theory and listening studies)
4. Return the key with the highest Pearson correlation
5. Encode in **Camelot wheel notation** (e.g. 6A, 11B) for harmonic mixing

Why Camelot notation? DJs use it to find compatible keys for seamless key-matching transitions. 6A and 7A are adjacent on the wheel — mixing them sounds harmonious because they're a perfect fifth apart in music theory.

The profiles are elegant — for C major: `[6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]` — weighting C (the tonic) highest, then G and F (the fifth and fourth), then others. The algorithm asks: "which profile best explains this song's observed pitch distribution?"

### Energy Scoring — RMS Without Loading the Whole File

Energy is computed as full-track RMS (Root Mean Square amplitude) via chunked reads:

```python
sum_sq = 0.0
n_frames = 0
with sf.SoundFile(file_path) as f:
    for block in f.blocks(blocksize=65536, dtype='float32'):
        mono = block.mean(axis=1) if block.ndim == 2 else block
        sum_sq += float(np.sum(mono ** 2))
        n_frames += len(mono)
avg_rms = np.sqrt(sum_sq / n_frames)
```

This computes full-track RMS — which correlates with perceived loudness — without ever holding the entire audio in memory. The RMS value maps to a 1–10 scale via empirically-tuned thresholds.

---

## The Similarity Engine — Finding Your Next Track

Given any track in your library, TrackFlow returns the **25 most similar tracks** using a **32-dimensional feature vector** and **cosine similarity**.

### 20 MFCC Coefficients: The Texture of Sound

MFCCs (Mel-Frequency Cepstral Coefficients) capture **timbre** — the texture or quality of sound — rather than pitch.

To compute them:
1. Take the mel spectrogram (same as BPM detection)
2. Convert to log scale: `log(mel_power + epsilon)`
3. Apply Discrete Cosine Transform (DCT) across the mel dimension
4. Keep the first 20 coefficients
5. Average across all time frames → single 20-dimensional vector

The result: coefficient 0 captures global loudness envelope, coefficients 1–3 capture broad spectral shape, higher coefficients capture finer timbral details. Two different instruments playing the same notes will have different MFCCs. Two recordings of the same instrument genre will have similar ones.

### 12 Chroma Means: Pitch-Class Energy

The remaining 12 dimensions are the **mean chroma** across the entire track — the same pitch-class energy distribution used for key detection. Two songs in the same key played with similar harmony will have similar chroma distributions.

### Cosine Similarity: Angle, Not Distance

```
cos(θ) = (a · b) / (|a| × |b|)
```

Cosine similarity measures the **angle** between two feature vectors, not their magnitude. This means loudness differences between tracks don't affect the similarity score — only the shape of the feature distribution matters.

The raw cosine value (−1 to +1) maps to a match percentage:

```
similarity% = 100 × (cos(θ) + 1) / 2
```

Feature vectors are cached at analysis time; similarity is computed on-demand across all library tracks and the top 25 results returned.

---

## Genre Detection at Scale — 400 Discogs Categories

Genre detection is the most technically sophisticated part of TrackFlow. It's also where I learned the most painful lesson: **a transposed tensor with the right shape is a silent bug**.

### The Model: Essentia's Discogs-EffNet

I use the **Discogs-EffNet model** from Essentia — the Music Technology Group at Universitat Pompeu Fabra's production-grade audio ML library.

- **EfficientNet backbone**: lightweight CNN, efficient on CPU
- **Trained on 400 Discogs genre/style labels**: Deep House, Minimal, Psych Rock, Jazz, Classical, and 395 more
- **Available as ONNX**: runs via `onnxruntime` — no TensorFlow, no conda headaches, works on Windows
- **~37 MB download**: fetched once on first use, then cached

The model takes 96-band mel spectrogram patches of shape `[n, 128_time, 96_mel]` and outputs 400 probability scores per patch. Scores are averaged across all patches, and the top genres returned.

### The Preprocessing Bug Hunt — Four Mistakes, One Fix

I implemented the preprocessing, fed audio into the model, and got results. No errors. No crashes. Just... wrong answers. Every track — indie folk, tech house, ambient — came back as "Minimal" and "DJ Tool."

I built a **diagnostic probe**: 13 preprocessing variants run across reference tracks, comparing outputs against Essentia's official TensorFlow implementation. Here's what I found:

**Bug 1 — Wrong mel band count**

Using **128 mel bands** (HTK scale, librosa default) instead of **96 bands** (Slaney scale, Essentia default).

The Slaney scale is linear below 1 kHz — where we're most sensitive to pitch differences — and logarithmic above. This provides finer frequency resolution in the perceptually important low-frequency region. The model had never seen 128-band input; it expected 96.

**Bug 2 — Wrong log formula**

Using the standard dB formula: `10 × log10(mel)`. Essentia uses:

```
log10(10000 × E + 1)
```

The standard formula produces −∞ for zero energy. Essentia's formula ensures zero maps to log₁₀(1) = 0 (no singularity), and the ×10000 factor places the full dynamic range in approximately [0, 4]. The model was trained on inputs in [0, 4]; we were feeding values in [−80, 0].

**Bug 3 — Transposed dimensions (the silent killer)**

The model expects patches of shape `[batch, 128_time_frames, 96_mel_bands]`.

We were producing shape `[batch, 128_mel_bands, 96_time_frames]`.

Both have shape `[n, 128, 96]`. No error was thrown. The model silently received time and frequency axes swapped, processed each patch as if it were rotated 90°, and produced garbage predictions.

This was the primary culprit for wrong genres.

**Bug 4 — Per-patch z-score normalization**

Applying zero-mean, unit-variance normalization to each `[128, 96]` patch before inference. This destroys energy information — quiet sections get stretched to look as loud as intense sections. Essentia feeds **raw log-compressed values** directly to the model. No patch normalization whatsoever.

**The fix:**

| Parameter | Wrong | Correct |
|---|---|---|
| Mel bands | 128 (HTK) | **96 (Slaney)** |
| Patch size | 96 frames | **128 frames** |
| Log formula | `10 × log10(mel)` | **`log10(10000×E + 1)`** |
| Layout | `[n, 128_mel, 96_time]` | **`[n, 128_time, 96_mel]`** |
| Normalization | Per-patch z-score | **None** |

**Result:** 365 nonzero genre activations vs 2 before. Predictions went from "Minimal, DJ Tool" to "Indie Rock, Psychedelic Rock, Experimental" for an indie-folk track.

---

## The Waveform Renderer

Each of the 1200 waveform bars is a `[amplitude, bass_ratio, mid_ratio, high_ratio]` vector. Frequency ranges:
- **Red** (0–200 Hz): kicks, subs, bass
- **Amber** (200–4000 Hz): mids, melody, vocals
- **Cyan** (4000+ Hz): highs, cymbals, air

Brightness scales with amplitude. Computed once in a background `QThread`; all paint events just render pre-computed data. No FFT in the paint loop.

Two panels: overview (full track at 50px) and zoom (±15s around playhead at 130px), both showing beat grid, hot cue markers, and loop region overlay.

---

## Seamless Looping — Solving the Click

The naive approach: timer-based detection of the loop out-point, then seek back. This creates an audible gap (~10ms) and a pop from the audio discontinuity.

The solution: **decode the loop region into RAM** as a `pygame.Sound` object, play with `loops=-1` (infinite repetition). Pygame's audio mixer handles the buffer wrap at the hardware level — the last sample is immediately followed by the first, with no gap, no timer event, no pop.

---

## Conclusion

Every decision in TrackFlow was intentional:
- **Pure SciPy** over librosa: 8-second startup penalty eliminated
- **ONNX Runtime** over TensorFlow: Windows-compatible, no conda headaches
- **Cosine similarity** over Euclidean: magnitude-independent, correct for timbre matching
- **Pygame buffer looping** over timer-based seeking: zero-gap, seamless

The most interesting bugs are the silent ones — a transposed tensor with the right shape. The most satisfying optimizations are the invisible ones — 8 seconds removed from startup without sacrificing accuracy.

**Check out TrackFlow on GitHub:** [github.com/ashaydave/TrackFlow](https://github.com/ashaydave/TrackFlow) — MIT license, open source.

Questions about the genre detection bug hunt, the cosine similarity choice, or seamless looping? I'm happy to discuss.

---

*TrackFlow was built entirely with [Claude](https://claude.ai) by Anthropic — from the signal processing engine to the PyQt6 UI.*
