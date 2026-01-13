import os
import shutil
from datetime import datetime
import threading
import queue
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
from dataclasses import dataclass
from typing import Optional, List
import tempfile

# Maximum number of lines to keep in the on-screen log
MAX_DISPLAY_LOG_LINES = 2000
# How often (ms) the UI polls the queues for updates
UI_POLL_MS = 100

# Date source options
DATE_OPTIONS = [
    'Auto',            # smart default: EXIF for images, else Modified
    'Modified',        # os.path.getmtime
    'Created',         # os.path.getctime
    'Earliest',        # min(created, modified)
    'Latest',          # max(created, modified)
    'EXIF (images)',   # DateTimeOriginal from image EXIF (requires Pillow)
]

# Common image extensions for Auto mode
IMAGE_EXTS = {'.jpg', '.jpeg', '.tiff', '.tif', '.png', '.heic', '.webp'}


@dataclass
class AppState:
    log_q: Optional[queue.Queue] = None
    status_q: Optional[queue.Queue] = None
    progress_q: Optional[queue.Queue] = None
    stop_event: Optional[threading.Event] = None
    worker: Optional[threading.Thread] = None
    start_btn: Optional[tk.Button] = None
    cancel_btn: Optional[tk.Button] = None
    browse_widgets: Optional[List[tk.Widget]] = None


class CollapsibleLog(tk.Frame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.is_collapsed = True
        self.toggle_btn = tk.Button(self, text="Show Log", command=self.toggle)
        self.toggle_btn.pack(fill="x")
        self.log_text = tk.Text(self, height=8, state='disabled')
        # Use a monospace font for readability if available
        try:
            self.log_text.config(font=("Consolas", 10))
        except Exception:
            pass
        self.log_text.pack(fill="both", expand=True)
        self.log_text.pack_forget()

    def toggle(self):
        if self.is_collapsed:
            self.log_text.pack(fill="both", expand=True)
            self.toggle_btn.config(text="Hide Log")
        else:
            self.log_text.pack_forget()
            self.toggle_btn.config(text="Show Log")
        self.is_collapsed = not self.is_collapsed

    # Accept either a single message (str) or an iterable of messages to append in one batch
    def append(self, msgs):
        if isinstance(msgs, str):
            msgs = [msgs]
        self.log_text.config(state='normal')
        # Insert all messages in one operation to reduce redraw work
        for msg in msgs:
            self.log_text.insert(tk.END, msg + '\n')
        # Trim lines if exceeding MAX_DISPLAY_LOG_LINES
        total_lines = int(self.log_text.index('end-1c').split('.')[0])
        if total_lines > MAX_DISPLAY_LOG_LINES:
            excess = total_lines - MAX_DISPLAY_LOG_LINES
            # delete the first `excess` lines
            self.log_text.delete('1.0', f'{excess + 1}.0')
        self.log_text.see(tk.END)
        self.log_text.config(state='disabled')


def _get_exif_datetime_original(path: str) -> Optional[datetime]:
    """Try to read EXIF DateTimeOriginal using Pillow. Return datetime or None on failure."""
    try:
        from PIL import Image, ExifTags
    except Exception:
        return None
    try:
        img = Image.open(path)
        exif = img._getexif()
        if not exif:
            return None
        # find the DateTimeOriginal tag key
        dt_key = None
        for k, v in ExifTags.TAGS.items():
            if v == 'DateTimeOriginal':
                dt_key = k
                break
        if dt_key is None:
            return None
        dt_val = exif.get(dt_key)
        if not dt_val:
            return None
        # EXIF DateTimeOriginal format: 'YYYY:MM:DD HH:MM:SS'
        try:
            return datetime.strptime(dt_val, '%Y:%m:%d %H:%M:%S')
        except Exception:
            return None
    except Exception:
        return None


def get_file_timestamp(path: str, date_source: str, log_q: Optional[queue.Queue] = None) -> float:
    """Return a POSIX timestamp according to the chosen date_source.
    Falls back safely and logs warnings to log_q if provided.
    """
    # Auto mode: for images try EXIF first, else use modified
    if date_source == 'Auto':
        ext = os.path.splitext(path)[1].lower()
        if ext in IMAGE_EXTS:
            exif_dt = _get_exif_datetime_original(path)
            if exif_dt is not None:
                return exif_dt.timestamp()
            # fall through to Modified
        # For non-images or missing EXIF, prefer modified time
        date_source = 'Modified'

    try:
        mtime = os.path.getmtime(path)
    except Exception:
        mtime = None
    try:
        ctime = os.path.getctime(path)
    except Exception:
        ctime = None

    if date_source == 'Modified':
        if mtime is not None:
            return mtime
        # fallback
        if ctime is not None:
            if log_q:
                log_q.put(f"Warning: Modified time unavailable for {path}, using created time")
            return ctime
        raise RuntimeError(f"No timestamp available for {path}")

    if date_source == 'Created':
        if ctime is not None:
            return ctime
        if mtime is not None:
            if log_q:
                log_q.put(f"Warning: Created time unavailable for {path}, using modified time")
            return mtime
        raise RuntimeError(f"No timestamp available for {path}")

    if date_source == 'Earliest':
        candidates = [t for t in (mtime, ctime) if t is not None]
        if candidates:
            return min(candidates)
        raise RuntimeError(f"No timestamp available for {path}")

    if date_source == 'Latest':
        candidates = [t for t in (mtime, ctime) if t is not None]
        if candidates:
            return max(candidates)
        raise RuntimeError(f"No timestamp available for {path}")

    if date_source == 'EXIF (images)':
        # Try EXIF first
        exif_dt = _get_exif_datetime_original(path)
        if exif_dt is not None:
            return exif_dt.timestamp()
        # fallback: use modified time
        if mtime is not None:
            if log_q:
                log_q.put(f"Notice: EXIF not found for {path}, using modified time")
            return mtime
        if ctime is not None:
            if log_q:
                log_q.put(f"Notice: EXIF and modified time not found for {path}, using created time")
            return ctime
        raise RuntimeError(f"No timestamp available for {path}")

    # default fallback
    if mtime is not None:
        return mtime
    if ctime is not None:
        return ctime
    raise RuntimeError(f"No timestamp available for {path}")


def organise_files_worker(source_dir, dest_dir, date_source, log_q, status_q, progress_q, stop_event, log_path):
    """Worker function that runs on a background thread.
    Writes a full log to `log_path` and pushes summary messages into `log_q` for UI display.
    """
    files = [os.path.join(dp, f) for dp, dn, filenames in os.walk(source_dir) for f in filenames if not f.startswith('.')]
    total = len(files)
    # Open the disk log for streaming large runs so we don't keep everything in memory
    try:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        log_file = open(log_path, 'a', encoding='utf-8')
    except Exception:
        # fallback: try current directory
        log_file = open(os.path.basename(log_path), 'a', encoding='utf-8')

    log_file.write(f"Start: {datetime.now().isoformat()}\n")
    log_file.write(f"Date source: {date_source}\n")
    log_file.flush()

    try:
        if total == 0:
            status_q.put("No files found")
            log_q.put("No files found")
            progress_q.put((0, 1))
            return

        for count, file in enumerate(files, 1):
            if stop_event.is_set():
                status_q.put("Cancelled by user")
                log_q.put("Cancelled by user")
                log_file.write(f"Cancelled at {datetime.now().isoformat()} after {count-1} files\n")
                break

            try:
                # Get timestamp according to user's selection
                ts = get_file_timestamp(file, date_source, log_q)
                modified = datetime.fromtimestamp(ts)
                year = modified.strftime("%Y")
                month = modified.strftime("%m-%B")
                target_dir = os.path.join(dest_dir, year, month)
                os.makedirs(target_dir, exist_ok=True)
                dest_path = os.path.join(target_dir, os.path.basename(file))
                shutil.move(file, dest_path)
                msg = f"Moved: {file} -> {dest_path}"
                status_q.put(f"Moving: {count}/{total}")
                log_q.put(msg)
                log_file.write(msg + '\n')
            except Exception as e:
                err = f"Error: {file} ({e})"
                status_q.put(err)
                log_q.put(err)
                log_file.write(err + '\n')

            # push progress as tuple (count, total) — main thread will convert to percent
            progress_q.put((count, total))

        else:
            # Completed normally
            status_q.put(f"✅ Done organizing {total} files.")
            log_q.put(f"✅ Done organizing {total} files.")
            log_file.write(f"Completed: {datetime.now().isoformat()} - {total} files\n")

    finally:
        try:
            log_file.flush()
            log_file.close()
        except Exception:
            pass
        # Always put a sentinel to let UI know worker finished
        status_q.put("__WORKER_FINISHED__")


def start_organize(source_var, dest_var, date_opt_var, progress_bar, status_var, log_widget, root, start_btn, cancel_btn, browse_widgets):
    source_dir = source_var.get()
    dest_dir = dest_var.get()
    date_source = date_opt_var.get()
    if not os.path.isdir(source_dir) or not os.path.isdir(dest_dir):
        messagebox.showerror("Error", "Select valid directories.")
        return

    # Disable controls while running
    start_btn.config(state='disabled')
    for w in browse_widgets:
        w.config(state='disabled')
    cancel_btn.config(state='normal')

    # Queues for thread-safe communication
    log_q = queue.Queue()
    status_q = queue.Queue()
    progress_q = queue.Queue()
    stop_event = threading.Event()

    # Prepare a rotating/per-run log file in the destination
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_filename = f'organize_log_{timestamp}.txt'
    # Store logs in system temp directory under a dedicated subfolder to avoid cluttering destination
    temp_dir = os.path.join(tempfile.gettempdir(), 'folder-organiser-logs')
    os.makedirs(temp_dir, exist_ok=True)
    log_path = os.path.join(temp_dir, log_filename)

    # Start worker thread
    worker = threading.Thread(
        target=organise_files_worker,
        args=(source_dir, dest_dir, date_source, log_q, status_q, progress_q, stop_event, log_path),
        daemon=True,
    )
    # store these in a single AppState on root so cancel/flush functions can access them
    state = AppState(
        log_q=log_q,
        status_q=status_q,
        progress_q=progress_q,
        stop_event=stop_event,
        worker=worker,
        start_btn=start_btn,
        cancel_btn=cancel_btn,
        browse_widgets=browse_widgets,
    )
    root._state = state

    # Initial UI state
    progress_bar['value'] = 0
    status_var.set('Starting...')
    log_widget.append(f"Starting organization. Full log: {log_path}")

    worker.start()

    # Start polling queues on the main thread
    root.after(UI_POLL_MS, flush_queues, root, log_widget, status_var, progress_bar)


def cancel_organize(root):
    # Signal worker to stop
    state = getattr(root, '_state', None)
    if state and state.stop_event:
        state.stop_event.set()


def flush_queues(root, log_widget, status_var, progress_bar):
    """Drain queues and apply batched UI updates on the main thread."""
    state = getattr(root, '_state', None)
    if not state:
        # nothing to do
        root.after(UI_POLL_MS, flush_queues, root, log_widget, status_var, progress_bar)
        return

    log_q = state.log_q
    status_q = state.status_q
    progress_q = state.progress_q

    # Collect logs in a list to append in one batch
    if log_q is not None:
        logs = []
        while True:
            try:
                logs.append(log_q.get_nowait())
            except queue.Empty:
                break
        if logs:
            log_widget.append(logs)

    # Process status messages — show the latest one
    if status_q is not None:
        latest_status = None
        while True:
            try:
                latest_status = status_q.get_nowait()
            except queue.Empty:
                break
        if latest_status:
            if latest_status == "__WORKER_FINISHED__":
                # Worker finished — re-enable UI
                if state.start_btn:
                    state.start_btn.config(state='normal')
                if state.cancel_btn:
                    state.cancel_btn.config(state='disabled')
                if state.browse_widgets:
                    for w in state.browse_widgets:
                        w.config(state='normal')
                status_var.set('Finished')
                # Do one last flush of any remaining queues after short delay
                root.after(250, flush_queues, root, log_widget, status_var, progress_bar)
                return
            else:
                status_var.set(latest_status)

    # Process progress — take the latest tuple and update progress bar
    if progress_q is not None:
        latest = None
        while True:
            try:
                latest = progress_q.get_nowait()
            except queue.Empty:
                break
        if latest is not None:
            count, total = latest
            percent = int((count / total) * 100) if total else 0
            progress_bar['value'] = percent
            status_var.set(f"{count}/{total} ({percent}%)")

    # Keep polling until worker signals finished
    root.after(UI_POLL_MS, flush_queues, root, log_widget, status_var, progress_bar)


def main():
    root = tk.Tk()
    root.title("File Organizer")
    root.geometry("700x450")

    source_var = tk.StringVar()
    dest_var = tk.StringVar()
    status_var = tk.StringVar()

    tk.Label(root, text="Source Directory:").pack(anchor='w', padx=10, pady=(10,0))
    src_frame = tk.Frame(root)
    src_frame.pack(fill="x", padx=10)
    src_entry = tk.Entry(src_frame, textvariable=source_var, width=60)
    src_entry.pack(side="left", fill="x", expand=True)
    src_browse = tk.Button(src_frame, text="Browse", command=lambda: source_var.set(filedialog.askdirectory()))
    src_browse.pack(side="left", padx=5)

    tk.Label(root, text="Destination Directory:").pack(anchor='w', padx=10, pady=(10,0))
    dest_frame = tk.Frame(root)
    dest_frame.pack(fill="x", padx=10)
    dest_entry = tk.Entry(dest_frame, textvariable=dest_var, width=60)
    dest_entry.pack(side="left", fill="x", expand=True)
    dest_browse = tk.Button(dest_frame, text="Browse", command=lambda: dest_var.set(filedialog.askdirectory()))
    dest_browse.pack(side="left", padx=5)

    # Date source selector
    tk.Label(root, text="Date source:").pack(anchor='w', padx=10, pady=(10,0))
    date_opt_var = tk.StringVar(value=DATE_OPTIONS[0])
    date_menu = ttk.Combobox(root, values=DATE_OPTIONS, textvariable=date_opt_var, state='readonly')
    date_menu.pack(fill="x", padx=10)

    progress = ttk.Progressbar(root, length=650)
    progress.pack(pady=15, padx=10)

    tk.Label(root, textvariable=status_var, wraplength=650).pack(padx=10)

    controls_frame = tk.Frame(root)
    controls_frame.pack(pady=5)
    # Create start and cancel buttons; variables referenced in the lambda must exist, so create placeholders first
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

