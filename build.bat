@echo off
setlocal

set APP_NAME=LAN_RemoteDesktop
set MAIN_SCRIPT=main.py

set /p NEW_TAG="Masukkan Versi Release Baru (misal v1.0.6): "

echo ==========================================
echo     BUILDING STANDALONE EXECUTABLE
echo ==========================================

taskkill /f /im %APP_NAME%*.exe 2>nul

echo [*] Membersihkan cache lama...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist *.spec del /q *.spec

echo [*] Memulai proses kompilasi via launcher 'py'...
py -m PyInstaller --noconfirm --onefile --windowed --name "%APP_NAME%" --hidden-import="cv2" --hidden-import="mss" --hidden-import="pyautogui" --hidden-import="numpy" "%MAIN_SCRIPT%"

if not exist "dist\%APP_NAME%.exe" (
    echo [-] Build gagal! File exe tidak ditemukan.
    pause
    exit /b 1
)

echo.
echo ==========================================
echo     UPLOADING TO GITHUB RELEASES
echo ==========================================
py upload_release.py %NEW_TAG%

pause