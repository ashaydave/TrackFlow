# TrackFlow.spec
# -*- mode: python ; coding: utf-8 -*-
#
# Build with:  pyinstaller TrackFlow.spec --noconfirm --clean
# Or via:      build.bat   (handles deps, icon conversion, and test run)
#
# Output layout: dist/TrackFlow/
#   TrackFlow.exe             — main executable
#   onnxruntime*.dll          — genre detection (ONNX Runtime)
#   libsndfile-1.dll          — audio decode (soundfile)
#   SDL2*.dll                 — audio playback (pygame)
#   PyQt6/                    — UI framework
#   assets/                   — logos, icons (bundled at _MEIPASS)
#
# NOT bundled (downloaded / stored at runtime in %APPDATA%\TrackFlow\):
#   models/discogs-effnet-bsdynamic-1.onnx     (~37 MB, genre detection)
#   models/genre_discogs400-discogs-effnet-1.json
#   cache/                                     (analysis results)
#   playlists.json, hot_cues.json, sync_state.json

import sys
from pathlib import Path

block_cipher = None

# ── Collect packages that ship native DLLs / data files ────────────────────
# collect_all() returns plain 2-tuples (src, dest) for datas and binaries.
# Do NOT convert to 3-tuples — PyInstaller 6.x Analysis() only accepts
# 2-tuples in the binaries list and will raise ValueError otherwise.
from PyInstaller.utils.hooks import collect_all

_extra_datas    = []
_extra_binaries = []
_extra_hidden   = []

for _pkg in (
    'PyQt6',        # Qt6 platform plugins, DLLs, translations
    'onnxruntime',  # onnxruntime.dll, onnxruntime_providers_shared.dll, etc.
    'soxr',         # soxr Cython extension (.pyd)
    'pygame',       # SDL2.dll, SDL2_mixer.dll, etc.
    'mutagen',      # tag-reading for every audio format
    'yt_dlp',       # all extractors + postprocessors (dynamic imports)
):
    _d, _b, _h = collect_all(_pkg)
    _extra_datas    += _d   # 2-tuples — safe to extend directly
    _extra_binaries += _b   # 2-tuples — do NOT wrap in _norm3()
    _extra_hidden   += _h

# soundfile: the DLL (libsndfile_x64.dll on modern pip installs) lives in a
# _soundfile_data/ directory adjacent to site-packages, NOT inside the soundfile
# package itself.  soundfile.py loads it via ctypes relative to __file__:
#   dirname(soundfile.__file__) + '/_soundfile_data/libsndfile_x64.dll'
# When frozen, __file__ resolves inside _MEIPASS, so the whole _soundfile_data/
# directory must be copied there — use datas (not binaries) to preserve the
# relative path.
_sf_data = Path(sys.prefix) / 'Lib' / 'site-packages' / '_soundfile_data'
if _sf_data.exists():
    _extra_datas.append((str(_sf_data), '_soundfile_data'))
else:
    # Fallback for older installs that name the DLL libsndfile-1.dll
    for _sf_dll in (
        Path(sys.prefix) / 'Library' / 'bin' / 'libsndfile-1.dll',   # conda (Windows)
        Path(sys.prefix) / 'Library' / 'bin' / 'libsndfile_x64.dll', # conda alt name
        Path(sys.prefix) / 'DLLs'   / 'libsndfile-1.dll',
    ):
        if _sf_dll.exists():
            _extra_binaries.append((str(_sf_dll), '.'))
            break
    else:
        print("WARNING: libsndfile DLL not found — audio loading may fail in the built exe.")
        print("         Try: pip install soundfile  (bundles the DLL automatically)")

# ── Main analysis ───────────────────────────────────────────────────────────
a = Analysis(
    ['main.py'],
    pathex=[str(Path('.').resolve())],
    binaries=_extra_binaries,
    datas=[
        ('assets', 'assets'),   # logos / icons  →  _MEIPASS/assets/
        *_extra_datas,
    ],
    hiddenimports=[
        # ── Core audio / DSP ────────────────────────────────────────────
        'pygame',
        'pygame.mixer',
        'soundfile',
        'soxr',
        # mutagen — one entry per container format to avoid lazy-import misses
        'mutagen',
        'mutagen.mp3',
        'mutagen.flac',
        'mutagen.mp4',
        'mutagen.ogg',
        'mutagen.wave',
        'mutagen.aiff',
        'mutagen.id3',
        'mutagen._tags',
        # scipy — list the submodules actually used
        'scipy.fft',
        'scipy.fftpack',
        'scipy.signal',
        'scipy.signal.windows',
        'scipy.linalg',
        'scipy.special',
        # numpy internals surfaced at import time in some builds
        'numpy',
        'numpy.lib.format',
        # ── App modules — Phase 1 ────────────────────────────────────────
        'paths',
        'analyzer',
        'analyzer.audio_analyzer',
        'analyzer.batch_analyzer',
        'analyzer.similarity',
        'analyzer.genre_detector',
        'ui',
        'ui.main_window',
        'ui.waveform_dj',
        'ui.audio_player',
        'ui.styles',
        # ── App modules — Phase 2 (Downloads) ───────────────────────────
        'downloader',
        'downloader.yt_handler',
        'downloader.watcher',
        'downloader.playlist_sync',
        'ui.downloads_tab',
        # ── yt-dlp ───────────────────────────────────────────────────────
        'yt_dlp',
        'yt_dlp.extractor',
        'yt_dlp.extractor.youtube',
        'yt_dlp.extractor.soundcloud',
        'yt_dlp.postprocessor',
        'yt_dlp.postprocessor.ffmpeg',
        'yt_dlp.networking',
        'yt_dlp.networking.common',
        # ── watchdog ─────────────────────────────────────────────────────
        'watchdog',
        'watchdog.observers',
        'watchdog.observers.polling',
        'watchdog.observers.winapi',    # Windows native ReadDirectoryChangesW
        'watchdog.events',
        'watchdog.utils',
        'watchdog.utils.dirsnapshot',
        # ── ONNX Runtime (genre detection) ───────────────────────────────
        'onnxruntime',
        'onnxruntime.capi',
        'onnxruntime.capi._pybind_state',
        # ── extras from collect_all() calls above ─────────────────────────
        *_extra_hidden,
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['rthook_onnxruntime.py'],
    excludes=[
        # Exclude heavy packages that are never used at runtime
        'tkinter',
        'matplotlib',
        'IPython',
        'jupyter',
        'tensorflow',       # genre detection uses ONNX Runtime, not TF
        'torch',
        'torchvision',
        'torchaudio',
        'sklearn',
        'pandas',
        'PIL',              # Pillow only used in build.bat for icon conversion
        # onnxruntime.quantization needs the 'onnx' package which we don't install.
        # We only use ORT for inference, not quantization — safe to exclude entirely.
        'onnxruntime.quantization',
        'onnxruntime.tools',
        'onnx',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='TrackFlow',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,          # UPX can corrupt onnxruntime + SDL2 DLLs — keep off
    console=False,      # no terminal window
    # build.bat converts logo_256.png -> logo.ico before running pyinstaller.
    # Falls back to no icon if the conversion step was skipped.
    icon='assets/logo.ico' if Path('assets/logo.ico').exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='TrackFlow',
)
