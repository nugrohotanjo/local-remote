@echo off
setlocal

set APP_NAME=LAN_RemoteDesktop
set MAIN_SCRIPT=remote_app.py

echo ==========================================
echo     BUILDING STANDALONE EXECUTABLE
echo ==========================================

echo [*] Membersihkan cache lama...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist *.spec del /q *.spec

echo [*] Memulai proses kompilasi via launcher 'py'...
py -m PyInstaller --noconfirm --onefile --windowed --name "%APP_NAME%" --hidden-import="cv2" --hidden-import="mss" --hidden-import="pyautogui" --hidden-import="numpy" "%MAIN_SCRIPT%"

echo.
if exist "dist\%APP_NAME%.exe" (
    echo ==========================================
    echo [+] SUKSES! File .exe berhasil dibuat:
    echo     --^> dist\%APP_NAME%.exe
    echo ==========================================
) else (
    echo [-] Build gagal atau file .exe tidak ditemukan.
)

pause