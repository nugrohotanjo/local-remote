import os
import sys
import json
import threading
import subprocess
import urllib.request
from tkinter import messagebox
from config import CURRENT_VERSION, GITHUB_REPO

def check_for_updates():
    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    try:
        req = urllib.request.Request(api_url, headers={"User-Agent": "AutoUpdaterApp"})
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status != 200:
                messagebox.showerror("Error", "Gagal menghubungi server GitHub.")
                return
            data = json.loads(response.read().decode())

        latest_version = data.get("tag_name")
        if not latest_version:
            messagebox.showinfo("Update", "Belum ada rilis versi di GitHub.")
            return

        if latest_version == CURRENT_VERSION:
            messagebox.showinfo("Update", f"Aplikasi sudah versi terbaru ({CURRENT_VERSION}).")
            return

        download_url = None
        for asset in data.get("assets", []):
            if asset.get("name", "").endswith(".exe"):
                download_url = asset.get("browser_download_url")
                break

        if not download_url:
            messagebox.showwarning("Update", f"Versi {latest_version} ditemukan, tetapi file .exe tidak ada di Release.")
            return

        tanya = messagebox.askyesno(
            "Update Ditemukan!",
            f"Versi baru: {latest_version}\nVersi saat ini: {CURRENT_VERSION}\n\nDownload dan pasang sekarang?"
        )
        if tanya:
            threading.Thread(
                target=download_and_replace, 
                args=(download_url, latest_version), 
                daemon=True
            ).start()

    except Exception as e:
        messagebox.showerror("Error", f"Gagal mengecek update:\n{e}")

def download_and_replace(download_url, new_version):
    try:
        if getattr(sys, 'frozen', False):
            current_exe = sys.executable
        else:
            messagebox.showinfo("Info", "Auto-update hanya berjalan saat aplikasi dibuka via .exe.")
            return

        app_dir = os.path.dirname(current_exe)
        clean_tag = new_version.replace(" ", "_")
        new_exe_name = f"LAN_RemoteDesktop_{clean_tag}.exe"
        new_exe_path = os.path.join(app_dir, new_exe_name)
        updater_bat = os.path.join(app_dir, "updater.bat")

        urllib.request.urlretrieve(download_url, new_exe_path)

        bat_script = f"""@echo off
timeout /t 2 /nobreak > nul
if exist "{current_exe}" del /f /q "{current_exe}"
start "" "{new_exe_path}"
del "%~f0"
"""
        with open(updater_bat, "w") as f:
            f.write(bat_script)

        subprocess.Popen(updater_bat, shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
        sys.exit(0)

    except Exception as e:
        messagebox.showerror("Update Gagal", f"Gagal mengunduh atau memasang update:\n{e}")