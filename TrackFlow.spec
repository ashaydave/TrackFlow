# TrackFlow.spec
# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[str(Path('.').resolve())],
    binaries=[],
    datas=[
        ('assets', 'assets'),
    ],
    hiddenimports=[
        # Core audio / analysis
        'pygame',
        'pygame.mixer',
        'soundfile',
        'soxr',
        'mutagen',
        'mutagen.mp3',
        'mutagen.flac',
        'mutagen.mp4',
        'scipy.fft',
        'scipy.fftpack',
        'numpy',
        # App modules — Phase 1
        'paths',
        'analyzer',
        'analyzer.audio_analyzer',
        'analyzer.batch_analyzer',
        'analyzer.similarity',
        'ui',
        'ui.main_window',
        'ui.waveform_dj',
        'ui.audio_player',
        'ui.styles',
        # App modules — Phase 2 (Downloads)
        'downloader',
        'downloader.yt_handler',
        'downloader.watcher',
        'downloader.playlist_sync',
        'ui.downloads_tab',
        # yt-dlp (YouTube downloads + Apple Music search)
        'yt_dlp',
        'yt_dlp.extractor',
        'yt_dlp.extractor.youtube',
        'yt_dlp.postprocessor',
        'yt_dlp.postprocessor.ffmpeg',
        # watchdog (SoulSeek folder watcher)
        'watchdog',
        'watchdog.observers',
        'watchdog.observers.polling',
        'watchdog.events',
        'watchdog.utils',
        'watchdog.utils.dirsnapshot',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'IPython', 'jupyter'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Collect all PyQt6 components (platform plugins, translations, DLLs)
from PyInstaller.utils.hooks import collect_all
qt_datas, qt_binaries, qt_hiddenimports = collect_all('PyQt6')

# Normalize to 3-tuples in case collect_all returns 2-tuples (PyInstaller 6.x compatibility)
def _norm3(items, typecode='DATA'):
    result = []
    for item in items:
        if len(item) == 3:
            result.append(item)
        elif len(item) == 2:
            result.append((item[0], item[1], typecode))
    return result

a.datas    += _norm3(qt_datas, 'DATA')
a.binaries += _norm3(qt_binaries, 'BINARY')
a.hiddenimports += qt_hiddenimports

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
    upx=False,
    console=False,
    icon='assets\logo_256.png',
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
