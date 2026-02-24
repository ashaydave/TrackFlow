@echo off
echo Building TrackFlow...
call conda activate dj-analyzer
pyinstaller TrackFlow.spec --noconfirm --clean
echo.
echo ============================================
echo Build complete: dist\TrackFlow\TrackFlow.exe
echo ============================================
pause
