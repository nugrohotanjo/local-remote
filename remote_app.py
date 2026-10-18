import socket
import struct
import pickle
import threading
import tkinter as tk
from tkinter import messagebox
import cv2
import mss
import numpy as np
import pyautogui

pyautogui.FAILSAFE = False

VIDEO_PORT = 9999
INPUT_PORT = 9998

# ==========================================
# 1. HOST / SERVER (Bagian yang di-remote)
# ==========================================
def run_input_server():
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server_sock.bind(("0.0.0.0", INPUT_PORT))
        server_sock.listen(5)
    except Exception as e:
        print(f"[!] Gagal bind Input Server: {e}")
        return

    with mss.mss() as sct:
        monitor = sct.monitors[1]
        screen_w = monitor["width"]
        screen_h = monitor["height"]

    payload_size = struct.calcsize(">L")

    while True:
        conn, _ = server_sock.accept()
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
                    target_x = int(cmd["norm_x"] * screen_w)
                    target_y = int(cmd["norm_y"] * screen_h)
                    pyautogui.moveTo(target_x, target_y)
                elif action == "click":
                    target_x = int(cmd["norm_x"] * screen_w)
                    target_y = int(cmd["norm_y"] * screen_h)
                    pyautogui.click(target_x, target_y, button=cmd.get("btn", "left"))
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
    try:
        server_sock.bind(("0.0.0.0", VIDEO_PORT))
        server_sock.listen(5)
    except Exception as e:
        print(f"[!] Gagal bind Video Server: {e}")
        return

    with mss.mss() as sct:
        monitor = sct.monitors[1]
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 65]

        while True:
            conn, _ = server_sock.accept()
            try:
                while True:
                    raw_frame = np.array(sct.grab(monitor))
                    frame = cv2.cvtColor(raw_frame, cv2.COLOR_BGRA2BGR)
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
def start_remote_session(target_ip):
    win_w, win_h = 1280, 720
    window_name = f"Controlling: {target_ip} (Tekan 'q' untuk keluar)"

    try:
        input_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        input_sock.connect((target_ip, INPUT_PORT))

        video_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        video_sock.connect((target_ip, VIDEO_PORT))
    except Exception as e:
        messagebox.showerror("Koneksi Gagal", f"Tidak dapat terhubung ke {target_ip}:\n{e}")
        return

    def send_command(cmd_dict):
        try:
            data = pickle.dumps(cmd_dict)
            size = len(data)
            input_sock.sendall(struct.pack(">L", size) + data)
        except Exception:
            pass

    def on_mouse(event, x, y, flags, param):
        norm_x = max(0.0, min(1.0, x / win_w))
        norm_y = max(0.0, min(1.0, y / win_h))

        if event == cv2.EVENT_LBUTTONDOWN:
            send_command({"type": "click", "norm_x": norm_x, "norm_y": norm_y, "btn": "left"})
        elif event == cv2.EVENT_RBUTTONDOWN:
            send_command({"type": "click", "norm_x": norm_x, "norm_y": norm_y, "btn": "right"})
        elif event == cv2.EVENT_MOUSEMOVE and (flags & cv2.EVENT_FLAG_LBUTTON):
            send_command({"type": "move", "norm_x": norm_x, "norm_y": norm_y})

    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, win_w, win_h)
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
# 3. GUI CONTROLLER (Tkinter)
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

def launch_gui():
    root = tk.Tk()
    root.title("Python Remote Desktop (LAN)")
    root.geometry("380x230")
    root.resizable(False, False)

    local_ip = get_local_ip()

    tk.Label(root, text="Remote Desktop Dual-Mode", font=("Helvetica", 14, "bold")).pack(pady=10)

    # Info IP perangkat ini
    info_frame = tk.Frame(root)
    info_frame.pack(pady=5)
    tk.Label(info_frame, text="IP Perangkat Ini:", font=("Helvetica", 10)).pack(side=tk.LEFT)
    ip_label = tk.Label(info_frame, text=f" {local_ip} ", font=("Helvetica", 10, "bold"), fg="blue")
    ip_label.pack(side=tk.LEFT)

    status_label = tk.Label(root, text="Status: Listener Aktif (Siap di-remote)", fg="green", font=("Helvetica", 9))
    status_label.pack(pady=2)

    # Input target IP
    connect_frame = tk.Frame(root)
    connect_frame.pack(pady=15)
    tk.Label(connect_frame, text="Target IP: ").pack(side=tk.LEFT)
    ip_entry = tk.Entry(connect_frame, width=18, font=("Helvetica", 10))
    ip_entry.pack(side=tk.LEFT, padx=5)
    ip_entry.insert(0, "192.168.1.")

    def on_connect_btn():
        target = ip_entry.get().strip()
        if not target:
            messagebox.showwarning("Peringatan", "Masukkan IP target terlebih dahulu.")
            return
        threading.Thread(target=start_remote_session, args=(target,), daemon=True).start()

    connect_btn = tk.Button(root, text="Hubungkan / Remote", command=on_connect_btn, bg="#2563eb", fg="white", font=("Helvetica", 10, "bold"), padx=10, pady=5)
    connect_btn.pack(pady=5)

    root.mainloop()

if __name__ == "__main__":
    # Jalankan listener server di background
    threading.Thread(target=run_input_server, daemon=True).start()
    threading.Thread(target=run_video_server, daemon=True).start()

    # Jalankan GUI
    launch_gui()