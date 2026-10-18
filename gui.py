import threading
import tkinter as tk
from tkinter import ttk, messagebox
from config import CURRENT_VERSION, VIDEO_PORT
from utils import get_local_ip, check_ip_port
from history import load_history
from client import start_remote_session
from updater import check_for_updates

def launch_gui():
    root = tk.Tk()
    root.title(f"LAN Remote Desktop - {CURRENT_VERSION}")
    root.geometry("480x520")
    root.resizable(False, False)

    local_ip = get_local_ip()

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

    tree.tag_configure("online", foreground="#16a34a", font=("Helvetica", 9, "bold"))
    tree.tag_configure("offline", foreground="#dc2626")

    def refresh_history_table():
        for item in tree.get_children():
            tree.delete(item)

        history = load_history()
        for ip, data in sorted(history.items(), key=lambda x: x[1].get("last_connected", ""), reverse=True):
            item_id = tree.insert("", tk.END, values=(ip, data.get("last_connected", "-"), "Mengecek..."))

            def check_worker(i_id, target_ip):
                is_online = check_ip_port(target_ip, VIDEO_PORT)
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

    def on_tree_double_click(event):
        selected_item = tree.selection()
        if selected_item:
            clicked_ip = tree.item(selected_item[0], "values")[0]
            ip_entry.delete(0, tk.END)
            ip_entry.insert(0, clicked_ip)
            on_connect(clicked_ip)

    tree.bind("<Double-1>", on_tree_double_click)

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
            messagebox.showinfo("Info", "Pilih salah satu IP dari tabel riwayat terlebih dahulu.")

    quick_btn = tk.Button(btn_box, text="Hubungkan IP Pilihan", command=on_quick_connect, font=("Helvetica", 8, "bold"))
    quick_btn.pack(side=tk.RIGHT)

    footer_frame = tk.Frame(root, pady=6)
    footer_frame.pack(fill=tk.X)
    btn_update = tk.Button(
        footer_frame, 
        text=f"Check Update ({CURRENT_VERSION})", 
        command=lambda: threading.Thread(target=check_for_updates, daemon=True).start(),
        font=("Helvetica", 8)
    )
    btn_update.pack()

    refresh_history_table()
    root.mainloop()