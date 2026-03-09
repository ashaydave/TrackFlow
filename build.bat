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

REM ── Step 1: Install / verify dependencies ────
echo [1/4] Checking dependencies...
pip install --quiet PyQt6 numpy scipy soundfile soxr mutagen pygame yt-dlp watchdog pyinstaller onnxruntime Pillow
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] pip install failed. Check your internet connection.
    pause
    exit /b 1
)
echo       Done.
echo.

REM ── Step 2: Convert logo PNG to ICO ──────────
echo [2/4] Converting logo to .ico for Windows taskbar/titlebar...
python -c "from PIL import Image; img=Image.open('assets/logo_256.png'); img.save('assets/logo.ico', sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])" 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo       [WARN] Pillow PNG->ICO conversion failed.
    echo              App will build without a custom icon.
    echo              Install Pillow manually: pip install Pillow
) else (
    echo       logo.ico created at assets/logo.ico
)
echo.

REM ── Step 3: Run PyInstaller ──────────────────
echo [3/4] Building with PyInstaller...
pyinstaller TrackFlow.spec --noconfirm --clean
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Build failed! Check the output above for details.
    echo.
    echo Common causes:
    echo   - Missing package: run pip install ^<package^>
    echo   - onnxruntime DLL not found: pip install onnxruntime
    echo   - PyInstaller too old: pip install --upgrade pyinstaller
    pause
    exit /b 1
)
echo       Done.
echo.

REM ── Step 4: Run test suite ───────────────────
echo [4/4] Running test suite...
python -m pytest tests/ -q --tb=short
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [WARNING] Some tests failed. The exe was still built but may have issues.
    echo           Check test output above before distributing.
) else (
    echo       All tests passed.
)
echo.

REM ── Report build size ────────────────────────
echo ============================================
echo  Build complete!
echo ============================================
echo.
echo  OUTPUT:  dist\TrackFlow\TrackFlow.exe
echo.

REM Show folder size (PowerShell one-liner)
for /f %%A in ('powershell -NoProfile -Command "(Get-ChildItem dist\TrackFlow -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB"') do (
    echo  Dist size: %%A MB
)
echo.
echo  Bundled (always included):
echo    Core:           PyQt6, pygame (SDL2), soundfile (libsndfile), soxr
echo    Analysis:       numpy, scipy — BPM, key, energy, similarity (MFCC+cosine)
echo    Genre:          onnxruntime — Discogs-EffNet ONNX (400 styles)
echo    Downloads:      yt-dlp, watchdog — YouTube, Apple Music, SoulSeek
echo    App modules:    analyzer, ui, downloader, paths
echo.
echo  Downloaded on first run (saved to %%APPDATA%%\TrackFlow\):
echo    models\discogs-effnet-bsdynamic-1.onnx        (~37 MB)
echo    models\genre_discogs400-discogs-effnet-1.json (~0.1 MB)
echo    cache\                 (analysis results, per-track JSON)
echo.
echo  NOT bundled (install separately if needed):
echo    ffmpeg  — required for MP3 320 kbps downloads
echo              Auto-detected from PATH and common install paths.
echo              Without it, downloads fall back to M4A format.
echo.
echo  NOTE: Run the exe from dist\TrackFlow\, not from build\.
echo        Distribute the entire dist\TrackFlow\ folder, not just the .exe.
echo ============================================
echo.
echo Opening output folder...
explorer dist\TrackFlow
pause
