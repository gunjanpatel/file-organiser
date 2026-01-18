from dataclasses import dataclass
from typing import Optional, List
import queue
import threading
import tkinter as tk

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
