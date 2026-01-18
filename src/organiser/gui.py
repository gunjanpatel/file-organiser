import tkinter as tk

MAX_DISPLAY_LOG_LINES = 2000
UI_POLL_MS = 100

class CollapsibleLog(tk.Frame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.is_collapsed = True
        self.toggle_btn = tk.Button(self, text="Show Log", command=self.toggle)
        self.toggle_btn.pack(fill="x")
        self.log_text = tk.Text(self, height=8, state='disabled')
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

    def append(self, msgs):
        if isinstance(msgs, str):
            msgs = [msgs]
        self.log_text.config(state='normal')
        for msg in msgs:
            self.log_text.insert(tk.END, msg + '\n')
        total_lines = int(self.log_text.index('end-1c').split('.')[0])
        if total_lines > MAX_DISPLAY_LOG_LINES:
            excess = total_lines - MAX_DISPLAY_LOG_LINES
            self.log_text.delete('1.0', f'{excess + 1}.0')
        self.log_text.see(tk.END)
        self.log_text.config(state='disabled')
