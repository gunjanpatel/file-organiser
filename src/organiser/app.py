import os
import queue
import tempfile
import threading
from datetime import datetime
from tkinter import messagebox

from organiser.gui import UI_POLL_MS
from organiser.organiser import organise_files_worker
from organiser.state import AppState


def start_organize(
    source_var,
    dest_var,
    date_opt_var,
    progress_bar,
    status_var,
    log_widget,
    root,
    start_btn,
    cancel_btn,
    browse_widgets,
):
    source_dir = source_var.get()
    dest_dir = dest_var.get()
    date_source = date_opt_var.get()
    if not os.path.isdir(source_dir) or not os.path.isdir(dest_dir):
        messagebox.showerror("Error", "Select valid directories.")
        return
    start_btn.config(state="disabled")
    for w in browse_widgets:
        w.config(state="disabled")
    cancel_btn.config(state="normal")
    log_q = queue.Queue()
    status_q = queue.Queue()
    progress_q = queue.Queue()
    stop_event = threading.Event()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"organize_log_{timestamp}.txt"
    temp_dir = os.path.join(tempfile.gettempdir(), "folder-organiser-logs")
    os.makedirs(temp_dir, exist_ok=True)
    log_path = os.path.join(temp_dir, log_filename)
    worker = threading.Thread(
        target=organise_files_worker,
        args=(
            source_dir,
            dest_dir,
            date_source,
            log_q,
            status_q,
            progress_q,
            stop_event,
            log_path,
        ),
        daemon=True,
    )
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
    progress_bar["value"] = 0
    status_var.set("Starting...")
    log_widget.append(f"Starting organization. Full log: {log_path}")
    worker.start()
    root.after(UI_POLL_MS, flush_queues, root, log_widget, status_var, progress_bar)


def cancel_organize(root):
    state = getattr(root, "_state", None)
    if state and state.stop_event:
        state.stop_event.set()


def flush_queues(root, log_widget, status_var, progress_bar):
    state = getattr(root, "_state", None)
    if not state:
        root.after(UI_POLL_MS, flush_queues, root, log_widget, status_var, progress_bar)
        return
    log_q = state.log_q
    status_q = state.status_q
    progress_q = state.progress_q
    if log_q is not None:
        logs = []
        while True:
            try:
                logs.append(log_q.get_nowait())
            except queue.Empty:
                break
        if logs:
            log_widget.append(logs)
    if status_q is not None:
        latest_status = None
        while True:
            try:
                latest_status = status_q.get_nowait()
            except queue.Empty:
                break
        if latest_status:
            if latest_status == "__WORKER_FINISHED__":
                if state.start_btn:
                    state.start_btn.config(state="normal")
                if state.cancel_btn:
                    state.cancel_btn.config(state="disabled")
                if state.browse_widgets:
                    for w in state.browse_widgets:
                        w.config(state="normal")
                status_var.set("Finished")
                root.after(
                    250, flush_queues, root, log_widget, status_var, progress_bar
                )
                return
            else:
                status_var.set(latest_status)
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
            progress_bar["value"] = percent
            status_var.set(f"{count}/{total} ({percent}%)")
    root.after(UI_POLL_MS, flush_queues, root, log_widget, status_var, progress_bar)
