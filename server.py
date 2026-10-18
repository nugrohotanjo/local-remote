import socket
import struct
import pickle
import cv2
import mss
import numpy as np
import pyautogui
from config import INPUT_PORT, VIDEO_PORT, JPEG_QUALITY
from utils import get_host_cursor_pos, set_host_cursor_pos

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
                    set_host_cursor_pos(target_x, target_y)
                elif action == "click":
                    target_x = screen_left + int(round(cmd["norm_x"] * screen_w))
                    target_y = screen_top + int(round(cmd["norm_y"] * screen_h))
                    set_host_cursor_pos(target_x, target_y)
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
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY]

        while True:
            conn, _ = server_sock.accept()
            conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            try:
                while True:
                    raw_frame = np.array(sct.grab(monitor))
                    frame = cv2.cvtColor(raw_frame, cv2.COLOR_BGRA2BGR)

                    # Kursor visual host
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