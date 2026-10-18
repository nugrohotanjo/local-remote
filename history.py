import os
import json
from datetime import datetime
from config import HISTORY_FILE

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