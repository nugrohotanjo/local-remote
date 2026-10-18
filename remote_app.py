import os
import sys
import time
import json
import socket
import struct
import pickle
import threading
import subprocess
import urllib.request
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox
import cv2
import mss
import numpy as np
import pyautogui
import ctypes

# ==========================================
# 0. SISTEM & DISPLAY SCALING FIX
# ==========================================
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

def get_host_cursor_pos():
    pt = POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y

# ==========================================
# KONFIGURASI APLIKASI & GITHUB RELEASES
# ==========================================
CURRENT_VERSION = "v1.0.5"
GITHUB_REPO = "nugrohotanjo/local-remote"

VIDEO_PORT = 9999
INPUT_PORT = 9998
HISTORY_FILE = "remote_history.json"

# ==========================================
# HELPER HISTORY (JSON)
# ==========================================
def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_history_entry(ip_addr):
    history = load_history()
    history[ip_addr] = {
        "last_connected": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    try:
        with open(HISTORY_FILE, "w") as f:
            json.dump(history, f, indent=2)
    except Exception:
        pass

# ==========================================
# 1. HOST / SERVER (Bagian yang di-remote)
# ==========================================
def run_input_server():
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    try:
        server_sock.bind(("0.0.0.0", INPUT_PORT))
        server_sock.listen(5)
    except Exception:
        return

    with mss.mss() as sct:
        monitor = sct.monitors[1]
        screen_w = monitor["width"]
        screen_h = monitor["height"]
        screen_left = monitor["left"]
        screen_top = monitor["top"]

    payload_size = struct.calcsize(">L")

    while True:
        conn, _ = server_sock.accept()
        conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        data = b""
        try:
            while True:
                while len(data) < payload_size:
                    packet = conn.recv(4096)
                    if not packet:
                        break
                    data += packet
                if len(data) < payload_size:
                    break

                packed_msg_size = data[:payload_size]
                data = data[payload_size:]
                msg_size = struct.unpack(">L", packed_msg_size)[0]

                while len(data) < msg_size:
                    packet = conn.recv(4096)
                    if not packet:
                        break
                    data += packet
                if len(data) < msg_size:
                    break

                msg_data = data[:msg_size]
                data = data[msg_size:]

                cmd = pickle.loads(msg_data)
                action = cmd.get("type")

                if action == "move":
                    target_x = screen_left + int(round(cmd["norm_x"] * screen_w))
                    target_y = screen_top + int(round(cmd["norm_y"] * screen_h))
                    ctypes.windll.user32.SetCursorPos(target_x, target_y)
                elif action == "click":
                    target_x = screen_left + int(round(cmd["norm_x"] * screen_w))
                    target_y = screen_top + int(round(cmd["norm_y"] * screen_h))
                    ctypes.windll.user32.SetCursorPos(target_x, target_y)
                    pyautogui.click(button=cmd.get("btn", "left"))
                elif action == "scroll":
                    steps = cmd.get("steps", 0)
                    if steps != 0:
                        pyautogui.scroll(steps)
                elif action == "key":
                    key = cmd.get("key")
                    if key:
                        pyautogui.press(key)
        except Exception:
            pass
        finally:
            conn.close()

def run_video_server():
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    try:
        server_sock.bind(("0.0.0.0", VIDEO_PORT))
        server_sock.listen(5)
    except Exception:
        return

    with mss.mss() as sct:
        monitor = sct.monitors[1]
        # Kualitas dinaikkan ke 88 untuk visual jernih/HD tanpa blur teks
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 88]

        while True:
            conn, _ = server_sock.accept()
            conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            try:
                while True:
                    raw_frame = np.array(sct.grab(monitor))
                    frame = cv2.cvtColor(raw_frame, cv2.COLOR_BGRA2BGR)

                    cur_x, cur_y = get_host_cursor_pos()
                    rel_x = cur_x - monitor["left"]
                    rel_y = cur_y - monitor["top"]
                    if 0 <= rel_x < monitor["width"] and 0 <= rel_y < monitor["height"]:
                        cv2.circle(frame, (rel_x, rel_y), 5, (0, 0, 255), -1)
                        cv2.circle(frame, (rel_x, rel_y), 7, (255, 255, 255), 1)

                    _, encoded_frame = cv2.imencode(".jpg", frame, encode_param)
                    data = pickle.dumps(encoded_frame)
                    size = len(data)
                    conn.sendall(struct.pack(">L", size) + data)
            except Exception:
                pass
            finally:
                conn.close()

# ==========================================
# 2. VIEWER / CLIENT (Bagian yang mengontrol)
# ==========================================
def start_remote_session(target_ip, on_success_callback=None):
    window_name = f"Controlling: {target_ip} (Tekan 'q' untuk keluar)"

    try:
        input_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        input_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        input_sock.settimeout(4.0)
        input_sock.connect((target_ip, INPUT_PORT))
        input_sock.settimeout(None)

        video_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        video_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        video_sock.settimeout(4.0)
        video_sock.connect((target_ip, VIDEO_PORT))
        video_sock.settimeout(None)
    except Exception as e:
        messagebox.showerror("Koneksi Gagal", f"Tidak dapat terhubung ke {target_ip}:\nPastikan listener di laptop sudah aktif.\n\nDetail: {e}")
        return

    # Simpan ke riwayat jika koneksi berhasil
    save_history_entry(target_ip)
    if on_success_callback:
        on_success_callback()

    state = {
        "img_w": 1920,
        "img_h": 1080,
        "last_move": 0.0,
        "window_initialized": False
    }

    def send_command(cmd_dict):
        try:
            data = pickle.dumps(cmd_dict)
            size = len(data)
            input_sock.sendall(struct.pack(">L", size) + data)
        except Exception:
            pass

    def on_mouse(event, x, y, flags, param):
        fw = state["img_w"]
        fh = state["img_h"]

        norm_x = max(0.0, min(1.0, float(x) / float(fw)))
        norm_y = max(0.0, min(1.0, float(y) / float(fh)))

        if event == cv2.EVENT_MOUSEMOVE:
            now = time.time()
            if now - state["last_move"] > 0.016:
                state["last_move"] = now
                send_command({"type": "move", "norm_x": norm_x, "norm_y": norm_y})
        elif event == cv2.EVENT_LBUTTONDOWN:
            send_command({"type": "click", "norm_x": norm_x, "norm_y": norm_y, "btn": "left"})
        elif event == cv2.EVENT_RBUTTONDOWN:
            send_command({"type": "click", "norm_x": norm_x, "norm_y": norm_y, "btn": "right"})
        elif event == cv2.EVENT_MOUSEWHEEL:
            delta = cv2.getMouseWheelDelta(flags)
            steps = 120 if delta > 0 else -120
            send_command({"type": "scroll", "steps": steps})

    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL | cv2.WINDOW_KEEPRATIO)
    cv2.setMouseCallback(window_name, on_mouse)

    data = b""
    payload_size = struct.calcsize(">L")

    try:
        while True:
            while len(data) < payload_size:
                packet = video_sock.recv(4096)
                if not packet:
                    return
                data += packet

            packed_msg_size = data[:payload_size]
            data = data[payload_size:]
            msg_size = struct.unpack(">L", packed_msg_size)[0]

            while len(data) < msg_size:
                packet = video_sock.recv(4096)
                if not packet:
                    return
                data += packet

            frame_data = data[:msg_size]
            data = data[msg_size:]

            encoded_frame = pickle.loads(frame_data)
            frame = cv2.imdecode(encoded_frame, cv2.IMREAD_COLOR)

            h, w, _ = frame.shape
            state["img_w"] = w
            state["img_h"] = h

            # Set ukuran jendela proporsional sesuai aspek rasio monitor asli
            if not state["window_initialized"]:
                target_w = 1280
                target_h = int(1280 * (h / w))
                cv2.resizeWindow(window_name, target_w, target_h)
                state["window_initialized"] = True

            cv2.imshow(window_name, frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key != 255:
                if key == 13:
                    send_command({"type": "key", "key": "enter"})
                elif key == 27:
                    send_command({"type": "key", "key": "esc"})
                elif key == 8:
                    send_command({"type": "key", "key": "backspace"})
                elif 32 <= key <= 126:
                    send_command({"type": "key", "key": chr(key)})
    finally:
        video_sock.close()
        input_sock.close()
        cv2.destroyAllWindows()

# ==========================================
# 3. AUTO-UPDATER VIA GITHUB RELEASES
# ==========================================
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
            messagebox.showinfo("Info", "Auto-update hanya berjalan saat file sudah berupa .exe.")
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

# ==========================================
# 4. GUI UTAMA DENGAN TABEL HISTORY & STATUS
# ==========================================
def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip

def check_ip_port(ip_addr, port=VIDEO_PORT, timeout=0.8):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((ip_addr, port))
        sock.close()
        return True
    except Exception:
        return False

def launch_gui():
    root = tk.Tk()
    root.title(f"LAN Remote Desktop - {CURRENT_VERSION}")
    root.geometry("480x520")
    root.resizable(False, False)

    local_ip = get_local_ip()

    # Header
    header_frame = tk.Frame(root, pady=8)
    header_frame.pack(fill=tk.X)
    tk.Label(header_frame, text="Remote Desktop Dual-Mode", font=("Helvetica", 13, "bold")).pack()
    
    info_sub = tk.Frame(header_frame)
    info_sub.pack(pady=3)
    tk.Label(info_sub, text="IP Komputer Ini: ", font=("Helvetica", 10)).pack(side=tk.LEFT)
    tk.Label(info_sub, text=local_ip, font=("Helvetica", 10, "bold"), fg="#16a34a").pack(side=tk.LEFT)

    tk.Label(header_frame, text="● Siap di-remote di background (Port 9998 & 9999)", fg="#0284c7", font=("Helvetica", 8)).pack()

    # Form Input IP Target
    input_frame = tk.LabelFrame(root, text=" Hubungkan ke Target ", font=("Helvetica", 9, "bold"), padx=10, pady=10)
    input_frame.pack(fill=tk.X, padx=15, pady=5)

    ip_box = tk.Frame(input_frame)
    ip_box.pack(fill=tk.X)
    tk.Label(ip_box, text="Target IP: ").pack(side=tk.LEFT)
    ip_entry = tk.Entry(ip_box, font=("Helvetica", 10))
    ip_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
    ip_entry.insert(0, "192.168.1.")

    def on_connect(target=None):
        t_ip = target if target else ip_entry.get().strip()
        if not t_ip:
            messagebox.showwarning("Peringatan", "Masukkan IP target terlebih dahulu.")
            return
        threading.Thread(
            target=start_remote_session, 
            args=(t_ip, refresh_history_table), 
            daemon=True
        ).start()

    connect_btn = tk.Button(
        input_frame, 
        text="▶ Mulai Remote", 
        command=lambda: on_connect(), 
        bg="#2563eb", 
        fg="white", 
        font=("Helvetica", 10, "bold"), 
        pady=4
    )
    connect_btn.pack(fill=tk.X, pady=(8, 0))

    # Frame History
    history_frame = tk.LabelFrame(root, text=" Riwayat Perangkat Terakhir ", font=("Helvetica", 9, "bold"), padx=10, pady=8)
    history_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=8)

    columns = ("ip", "last_time", "status")
    tree = ttk.Treeview(history_frame, columns=columns, show="headings", height=6)
    tree.heading("ip", text="IP Address")
    tree.heading("last_time", text="Terakhir Remote")
    tree.heading("status", text="Status")

    tree.column("ip", width=120, anchor=tk.CENTER)
    tree.column("last_time", width=180, anchor=tk.CENTER)
    tree.column("status", width=110, anchor=tk.CENTER)
    tree.pack(fill=tk.BOTH, expand=True)

    # Tag warna status
    tree.tag_configure("online", foreground="#16a34a", font=("Helvetica", 9, "bold"))
    tree.tag_configure("offline", foreground="#dc2626")

    def refresh_history_table():
        for item in tree.get_children():
            tree.delete(item)

        history = load_history()
        for ip, data in sorted(history.items(), key=lambda x: x[1].get("last_connected", ""), reverse=True):
            item_id = tree.insert("", tk.END, values=(ip, data.get("last_connected", "-"), "Mengecek..."))

            # Threaded status check per baris IP agar GUI tidak freeze
            def check_worker(i_id, target_ip):
                is_online = check_ip_port(target_ip)
                if root.winfo_exists():
                    root.after(0, lambda: update_status_ui(i_id, is_online))

            threading.Thread(target=check_worker, args=(item_id, ip), daemon=True).start()

    def update_status_ui(item_id, is_online):
        try:
            current_vals = tree.item(item_id, "values")
            if current_vals:
                status_text = "● Siap Remote" if is_online else "○ Offline"
                tag = "online" if is_online else "offline"
                tree.item(item_id, values=(current_vals[0], current_vals[1], status_text), tags=(tag,))
        except Exception:
            pass

    # Klik dua kali baris tabel untuk langsung isi input & connect
    def on_tree_double_click(event):
        selected_item = tree.selection()
        if selected_item:
            clicked_ip = tree.item(selected_item[0], "values")[0]
            ip_entry.delete(0, tk.END)
            ip_entry.insert(0, clicked_ip)
            on_connect(clicked_ip)

    tree.bind("<Double-1>", on_tree_double_click)

    # Tombol aksi riwayat
    btn_box = tk.Frame(history_frame)
    btn_box.pack(fill=tk.X, pady=(6, 0))

    refresh_btn = tk.Button(btn_box, text="🔄 Segarkan Status", command=refresh_history_table, font=("Helvetica", 8))
    refresh_btn.pack(side=tk.LEFT)

    def on_quick_connect():
        selected_item = tree.selection()
        if selected_item:
            clicked_ip = tree.item(selected_item[0], "values")[0]
            on_connect(clicked_ip)
        else:
            messagebox.showinfo("Info", "Pilih salah satu IP dari tabel riwayat di atas terlebih dahulu.")

    quick_btn = tk.Button(btn_box, text="Hubungkan IP Pilihan", command=on_quick_connect, font=("Helvetica", 8, "bold"))
    quick_btn.pack(side=tk.RIGHT)

    # Footer Auto-Update
    footer_frame = tk.Frame(root, pady=6)
    footer_frame.pack(fill=tk.X)
    btn_update = tk.Button(
        footer_frame, 
        text=f"Check Update ({CURRENT_VERSION})", 
        command=lambda: threading.Thread(target=check_for_updates, daemon=True).start(),
        font=("Helvetica", 8)
    )
    btn_update.pack()

    # Load tabel saat startup
    refresh_history_table()
    root.mainloop()

if __name__ == "__main__":
    threading.Thread(target=run_input_server, daemon=True).start()
    threading.Thread(target=run_video_server, daemon=True).start()
    launch_gui()