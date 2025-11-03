"""Match history viewer leveraging MTGOSDK runtime."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

from loguru import logger

import threading

from utils import mtgo_bridge


def _widget_alive(widget: tk.Misc | None) -> bool:
    if widget is None:
        return False
    try:
        return bool(widget.winfo_exists())
    except tk.TclError:
        return False


class MatchHistoryWindow:
    """Simple window displaying recent MTGO matches grouped by event."""

    def __init__(self, master: tk.Misc) -> None:
        self.master = master
        self.window = tk.Toplevel(master)
        self.window.title("MTGO Match History")
        self.window.geometry("720x420")
        self.window.minsize(600, 360)
        self.window.attributes("-topmost", True)

        self.window.protocol("WM_DELETE_WINDOW", self.close)

        self.refresh_button = None
        self.tree: ttk.Treeview | None = None
        self.status_var = tk.StringVar(value="Ready")

        self._build_ui()
        self.refresh_history()

    def _build_ui(self) -> None:
        container = ttk.Frame(self.window, padding=8)
        container.pack(fill="both", expand=True)

        button_bar = ttk.Frame(container)
        button_bar.pack(fill="x", pady=(0, 6))

        self.refresh_button = ttk.Button(button_bar, text="Refresh", command=self.refresh_history)
        self.refresh_button.pack(side="left")

        self.tree = ttk.Treeview(container, columns=("format", "state", "result", "updated"), show="tree headings")
        self.tree.heading("#0", text="Event / Match")
        self.tree.heading("format", text="Format")
        self.tree.heading("state", text="State")
        self.tree.heading("result", text="Result")
        self.tree.heading("updated", text="Updated")
        self.tree.column("#0", width=280, anchor="w")
        self.tree.column("format", width=100, anchor="center")
        self.tree.column("state", width=100, anchor="center")
        self.tree.column("result", width=160, anchor="center")
        self.tree.column("updated", width=140, anchor="center")
        self.tree.pack(fill="both", expand=True)

        status = ttk.Label(container, textvariable=self.status_var, anchor="w")
        status.pack(fill="x", pady=(6, 0))

    def refresh_history(self) -> None:
        if not _widget_alive(self.tree) or not _widget_alive(self.window):
            return

        if _widget_alive(self.refresh_button):
            self.refresh_button.config(state="disabled")
        self.status_var.set("Loading…")
        try:
            self.window.update_idletasks()
        except tk.TclError:
            return

        def worker():
            try:
                ready, error = mtgo_bridge.ensure_runtime_ready()
                if not ready:
                    raise RuntimeError(f"MTGOSDK runtime unavailable: {error or 'see logs'}")
                history = mtgo_bridge.get_match_history()
                logger.debug(f"Match history entries received: {len(history)}")
            except Exception as exc:
                logger.exception("Failed to load match history")
                error_text = str(exc)
                if _widget_alive(self.window):
                    self.window.after(0, lambda: self._handle_history_error(error_text))
                return

            if _widget_alive(self.window):
                self.window.after(0, lambda: self._populate_history(history))

        threading.Thread(target=worker, daemon=True).start()

    def _handle_history_error(self, message: str) -> None:
        if not _widget_alive(self.window):
            return
        self.status_var.set("Failed to load match history")
        if _widget_alive(self.refresh_button):
            self.refresh_button.config(state="normal")
        messagebox.showerror("Match History", f"Unable to load match history:\n{message}")

    def _populate_history(self, history: list[dict]) -> None:
        if not _widget_alive(self.tree):
            return
        self.tree.delete(*self.tree.get_children())

        if not history:
            self.status_var.set("No match data available. Join an event or start a match.")
            if _widget_alive(self.refresh_button):
                self.refresh_button.config(state="normal")
            return

        for event in history:
            event_text = event.get("description") or event.get("type") or event.get("eventId")
            fmt = event.get("format") or "—"
            state = event.get("state") or ("Completed" if event.get("isCompleted") else "Active")
            updated = event.get("lastUpdated") or "—"
            parent_id = self.tree.insert("", "end", text=event_text, values=(fmt, state, "", updated))

            matches = event.get("matches") or []
            if not matches:
                continue

            for match in matches:
                opponent = ", ".join(player.get("name") or "Unknown" for player in match.get("players", []) if player.get("name"))
                match_text = opponent or match.get("id") or "Match"
                if match.get("round"):
                    match_text = f"Round {match['round']}: {match_text}"
                state = match.get("state") or ("Completed" if match.get("isComplete") else "Active")
                result = match.get("result") or "—"
                updated = match.get("lastUpdated") or "—"
                self.tree.insert(parent_id, "end", text=match_text, values=("", state, result, updated))

        for child in self.tree.get_children():
            self.tree.item(child, open=True)
        self.status_var.set("Loaded match history")
        if _widget_alive(self.refresh_button):
            self.refresh_button.config(state="normal")

    def close(self) -> None:
        try:
            self.window.destroy()
        except Exception:
            pass
