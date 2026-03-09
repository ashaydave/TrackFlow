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

from pathlib import Path

block_cipher = None

# ── Collect packages that ship native DLLs / data files ────────────────────
# Must run before Analysis so the results can be passed in.
from PyInstaller.utils.hooks import collect_all

def _norm3(items, typecode='DATA'):
    """Normalise to 3-tuples — works with PyInstaller 5.x and 6.x."""
    out = []
    for item in items:
        if len(item) == 3:
            out.append(item)
        elif len(item) == 2:
            out.append((item[0], item[1], typecode))
    return out

_extra_datas    = []
_extra_binaries = []
_extra_hidden   = []

for _pkg in (
    'PyQt6',        # Qt6 platform plugins, DLLs, translations
    'onnxruntime',  # onnxruntime.dll, onnxruntime_providers_shared.dll, etc.
    'soundfile',    # libsndfile-1.dll
    'soxr',         # soxr Cython extension (.pyd)
    'pygame',       # SDL2.dll, SDL2_mixer.dll, etc.
    'mutagen',      # tag-reading for every format
    'yt_dlp',       # all extractors + postprocessors (needed for dynamic imports)
):
    _d, _b, _h = collect_all(_pkg)
    _extra_datas    += _norm3(_d, 'DATA')
    _extra_binaries += _norm3(_b, 'BINARY')
    _extra_hidden   += _h

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
        # scipy — list submodules used; scipy uses lazy imports internally
        'scipy.fft',
        'scipy.fftpack',
        'scipy.signal',
        'scipy.signal.windows',
        'scipy.linalg',
        'scipy.special',
        # numpy internals surfaced at import time in some builds
        'numpy',
        'numpy.core._methods',
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
        'watchdog.observers.winapi',   # Windows native ReadDirectoryChangesW
        'watchdog.events',
        'watchdog.utils',
        'watchdog.utils.dirsnapshot',
        # ── ONNX Runtime (genre detection) ───────────────────────────────
        'onnxruntime',
        'onnxruntime.capi',
        'onnxruntime.capi._pybind_state',
        # ── extras collected from collect_all() calls above ──────────────
        *_extra_hidden,
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Never needed — exclude to keep build lean
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
        'PIL',              # Pillow not used at runtime (only in build.bat)
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
    upx=False,          # UPX can corrupt native DLLs (onnxruntime, SDL2)
    console=False,      # no terminal window
    # Icon: build.bat converts logo_256.png → logo.ico via Pillow before
    # running pyinstaller.  Falls back to no icon if conversion failed.
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
