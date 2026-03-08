@echo off
echo ============================================
echo  TrackFlow Build Script
echo ============================================
echo.

REM ── Activate conda environment ───────────────
call conda activate dj-analyzer
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Could not activate conda environment "dj-analyzer".
    echo         Run: conda create -n dj-analyzer python=3.11 -y
    pause
    exit /b 1
)

REM ── Ensure all dependencies are installed ────
echo [1/3] Checking dependencies...
pip install --quiet PyQt6 numpy scipy soundfile soxr mutagen pygame yt-dlp watchdog pyinstaller
echo       Core deps done.
echo       Installing essentia-tensorflow for genre detection (may take a moment)...
pip install --quiet essentia-tensorflow
if %ERRORLEVEL% NEQ 0 (
    echo [WARNING] essentia-tensorflow failed to install.
    echo           Genre detection will be disabled. The app will still run normally.
)
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] pip install failed. Check your internet connection.
    pause
    exit /b 1
)
echo       Done.
echo.

REM ── Optional: remind about ffmpeg ────────────
echo NOTE: For MP3 320kbps downloads, ffmpeg must be installed separately.
echo       TrackFlow auto-detects ffmpeg from PATH and common install paths.
echo       Without ffmpeg, downloads fall back to M4A format.
echo.

REM ── Run PyInstaller ──────────────────────────
echo [2/3] Building with PyInstaller...
pyinstaller TrackFlow.spec --noconfirm --clean
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Build failed! Check the output above for details.
    pause
    exit /b 1
)
echo       Done.
echo.

REM ── Run tests (optional smoke-check) ─────────
echo [3/3] Running test suite...
python -m pytest tests/ -q --tb=short
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [WARNING] Some tests failed — the exe was still built but may have issues.
    echo           Check test output above before distributing.
) else (
    echo       All tests passed.
)
echo.

echo ============================================
echo  Build complete!
echo ============================================
echo.
echo  OUTPUT:  dist\TrackFlow\TrackFlow.exe
echo.
echo  Includes:
echo    - Phase 1: Analysis, waveform, DJ controls, similarity
echo    - Phase 2: YouTube downloads (MP3/M4A), Apple Music URL
echo              subscriptions, iTunes XML, SoulSeek watcher
echo    - Genre detection: Essentia + Discogs-EffNet (400 styles)
echo              Models downloaded automatically on first use (~42 MB)
echo.
echo  NOTE: Run the exe from dist\TrackFlow\, not from build\.
echo        ffmpeg is NOT bundled — install separately for MP3 output.
echo ============================================
echo.
echo Opening output folder...
explorer dist\TrackFlow
pause
