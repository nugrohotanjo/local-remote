import socket
import ctypes

class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

def enable_dpi_awareness():
    """Mengaktifkan DPI Awareness agar skala koordinat Windows 125%/150% akurat 1:1."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

def get_host_cursor_pos():
    """Mendapatkan posisi kursor mouse host aktual menggunakan Win32 API."""
    pt = POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y

def set_host_cursor_pos(x, y):
    """Memindahkan kursor mouse host secara instan (0 ms latency)."""
    ctypes.windll.user32.SetCursorPos(x, y)

def get_local_ip():
    """Mendeteksi alamat IPv4 lokal komputer."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip

def check_ip_port(ip_addr, port, timeout=0.8):
    """Mengecek apakah port target terbuka (untuk status online)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((ip_addr, port))
        sock.close()
        return True
    except Exception:
        return False