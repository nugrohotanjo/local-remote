import threading
import pyautogui
from utils import enable_dpi_awareness
from server import run_input_server, run_video_server
from gui import launch_gui

if __name__ == "__main__":
    # Konfigurasi sistem
    pyautogui.FAILSAFE = False
    pyautogui.PAUSE = 0
    enable_dpi_awareness()

    # Jalankan background server listener
    threading.Thread(target=run_input_server, daemon=True).start()
    threading.Thread(target=run_video_server, daemon=True).start()

    # Jalankan antarmuka GUI
    launch_gui()