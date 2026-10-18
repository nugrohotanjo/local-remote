import socket
import struct
import pickle
import time
import cv2
from tkinter import messagebox
from config import INPUT_PORT, VIDEO_PORT
from history import save_history_entry

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
        messagebox.showerror(
            "Koneksi Gagal",
            f"Tidak dapat terhubung ke {target_ip}:\nPastikan listener di laptop tujuan aktif.\n\nDetail: {e}"
        )
        return

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