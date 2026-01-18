import tkinter as tk
from tkinter import filedialog, ttk

from organiser.app import start_organize, cancel_organize
from organiser.gui import CollapsibleLog

DATE_OPTIONS = [
    'Auto',
    'Modified',
    'Created',
    'Earliest',
    'Latest',
    'EXIF (images)',
]

def main():
    root = tk.Tk()
    root.title("File Organizer")
    root.geometry("700x450")
    source_var = tk.StringVar()
    dest_var = tk.StringVar()
    status_var = tk.StringVar()
    tk.Label(root, text="Source Directory:").pack(anchor='w', padx=10, pady=(10, 0))
    src_frame = tk.Frame(root)
    src_frame.pack(fill="x", padx=10)
    src_entry = tk.Entry(src_frame, textvariable=source_var, width=60)
    src_entry.pack(side="left", fill="x", expand=True)
    src_browse = tk.Button(src_frame, text="Browse", command=lambda: source_var.set(filedialog.askdirectory()))
    src_browse.pack(side="left", padx=5)
    tk.Label(root, text="Destination Directory:").pack(anchor='w', padx=10, pady=(10, 0))
    dest_frame = tk.Frame(root)
    dest_frame.pack(fill="x", padx=10)
    dest_entry = tk.Entry(dest_frame, textvariable=dest_var, width=60)
    dest_entry.pack(side="left", fill="x", expand=True)
    dest_browse = tk.Button(dest_frame, text="Browse", command=lambda: dest_var.set(filedialog.askdirectory()))
    dest_browse.pack(side="left", padx=5)
    tk.Label(root, text="Date source:").pack(anchor='w', padx=10, pady=(10, 0))
    date_opt_var = tk.StringVar(value=DATE_OPTIONS[0])
    date_menu = ttk.Combobox(root, values=DATE_OPTIONS, textvariable=date_opt_var, state='readonly')
    date_menu.pack(fill="x", padx=10)
    progress = ttk.Progressbar(root, length=650)
    progress.pack(pady=15, padx=10)
    tk.Label(root, textvariable=status_var, wraplength=650).pack(padx=10)
    controls_frame = tk.Frame(root)
    controls_frame.pack(pady=5)
    start_btn = tk.Button(controls_frame, text="Start")
    cancel_btn = tk.Button(controls_frame, text="Cancel", state='disabled')
    start_btn.config(command=lambda: start_organize(source_var, dest_var, date_opt_var, progress, status_var, log_widget, root, start_btn, cancel_btn, [src_browse, dest_browse]))
    start_btn.pack(side="left", padx=5)
    cancel_btn.config(command=lambda: cancel_organize(root))
    cancel_btn.pack(side="left", padx=5)
    log_widget = CollapsibleLog(root)
    log_widget.pack(fill="both", expand=True, padx=10, pady=5)
    root.mainloop()

if __name__ == "__main__":
    main()
