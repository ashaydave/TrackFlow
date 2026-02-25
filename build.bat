@echo off
echo ============================================
echo  Building TrackFlow...
echo ============================================
echo.

call conda activate dj-analyzer
pyinstaller TrackFlow.spec --noconfirm --clean

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Build failed! Check the output above for details.
    pause
    exit /b 1
)

echo.
echo ============================================
echo  Build successful!
echo ============================================
echo.
echo  OUTPUT:  dist\TrackFlow\TrackFlow.exe
echo.
echo  NOTE: Run the exe from the dist\TrackFlow folder,
echo        NOT from the build folder.
echo ============================================
echo.
echo Opening output folder...
explorer dist\TrackFlow
pause
