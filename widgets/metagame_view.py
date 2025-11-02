"""Metagame statistics view for the deck builder."""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk
from typing import Any, Iterable

from loguru import logger

from utils.metagame_stats import (
    count_decks_by_archetype,
    count_decks_by_event,
    count_decks_by_player,
    load_aggregated_decks,
    update_mtgo_deck_cache,
)


class MetagameStatsView(tk.Frame):
    def __init__(self, master: tk.Misc, **kwargs) -> None:
        super().__init__(master, **kwargs)
        self.configure(background="bisque3")

        self.format_var = tk.StringVar(value="Modern")
        self.days_var = tk.IntVar(value=7)
        self.status_var = tk.StringVar(value="Metagame data has not been loaded yet.")
        self.event_summary_var = tk.StringVar(value="")

        self.deck_tree: ttk.Treeview | None = None
        self.player_tree: ttk.Treeview | None = None

        self._build_ui()

    def _build_ui(self) -> None:
        controls = tk.Frame(self, background="bisque3", padx=8, pady=8)
        controls.grid(row=0, column=0, columnspan=2, sticky="ew")

        tk.Label(controls, text="Format:", background="bisque3", font=("calibri", 11, "bold"))\
            .grid(row=0, column=0, sticky="w")
        format_menu = ttk.Combobox(
            controls,
            textvariable=self.format_var,
            values=[
                "Modern",
                "Pioneer",
                "Legacy",
                "Standard",
                "Pauper",
                "Vintage",
                "Alchemy",
                "Explorer",
            ],
            state="readonly",
            width=12,
        )
        format_menu.grid(row=0, column=1, sticky="w", padx=(4, 12))

        tk.Label(controls, text="Lookback (days):", background="bisque3", font=("calibri", 11, "bold"))\
            .grid(row=0, column=2, sticky="w")
        days_entry = tk.Entry(controls, textvariable=self.days_var, width=5)
        days_entry.grid(row=0, column=3, sticky="w", padx=(4, 12))

        refresh_btn = tk.Button(controls, text="Refresh", command=self.refresh_data, background="bisque2")
        refresh_btn.grid(row=0, column=4, sticky="w")

        status_label = tk.Label(self, textvariable=self.status_var, background="bisque3", anchor="w")
        status_label.grid(row=1, column=0, columnspan=2, sticky="ew", padx=8)
        event_label = tk.Label(self, textvariable=self.event_summary_var, background="bisque3", anchor="w", font=("calibri", 10, "bold"))
        event_label.grid(row=2, column=0, columnspan=2, sticky="ew", padx=8)

        deck_frame = tk.LabelFrame(self, text="Decks", background="bisque3")
        deck_frame.grid(row=3, column=0, sticky="nsew", padx=8, pady=8)
        player_frame = tk.LabelFrame(self, text="Players", background="bisque3")
        player_frame.grid(row=3, column=1, sticky="nsew", padx=8, pady=8)

        self.deck_tree = self._create_tree(deck_frame, columns=("Deck", "Count"), heading="Archetype")
        self.deck_tree.grid(row=0, column=0, sticky="nsew")
        deck_scroll = ttk.Scrollbar(deck_frame, orient="vertical", command=self.deck_tree.yview)
        deck_scroll.grid(row=0, column=1, sticky="ns")
        self.deck_tree.configure(yscrollcommand=deck_scroll.set)

        self.player_tree = self._create_tree(player_frame, columns=("Player", "Count"), heading="Player")
        self.player_tree.grid(row=0, column=0, sticky="nsew")
        player_scroll = ttk.Scrollbar(player_frame, orient="vertical", command=self.player_tree.yview)
        player_scroll.grid(row=0, column=1, sticky="ns")
        self.player_tree.configure(yscrollcommand=player_scroll.set)

        for frame in (deck_frame, player_frame):
            frame.grid_rowconfigure(0, weight=1)
            frame.grid_columnconfigure(0, weight=1)

        self.grid_rowconfigure(3, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self._refresh_in_progress = False

    def _create_tree(self, master: tk.Misc, columns: tuple[str, str], heading: str) -> ttk.Treeview:
        tree = ttk.Treeview(master, columns=columns, show="headings", selectmode="browse", height=12)
        tree.heading(columns[0], text=heading)
        tree.heading(columns[1], text="Count")
        tree.column(columns[0], width=220, anchor="w")
        tree.column(columns[1], width=70, anchor="center")
        return tree

    def _clear_tree(self, tree: ttk.Treeview) -> None:
        if tree is None:
            return
        for row in tree.get_children():
            tree.delete(row)

    def _insert_rows(self, tree: ttk.Treeview, rows: Iterable[tuple[str, int]]) -> None:
        if tree is None:
            return
        for label, count in rows:
            tree.insert("", "end", values=(label, count))

    def refresh_data(self) -> None:
        if self._refresh_in_progress:
            return
        try:
            days = max(1, int(self.days_var.get()))
        except (ValueError, tk.TclError):
            days = 7
            self.days_var.set(days)
        fmt = self.format_var.get()

        self.status_var.set("Refreshing MTGO deck data…")
        self.update_idletasks()
        self._refresh_in_progress = True

        def worker(target_fmt: str, lookback: int):
            decks = None
            error = None
            try:
                decks = update_mtgo_deck_cache(days=lookback, fmt=target_fmt, max_events=20)
            except Exception as exc:  # noqa: BLE001
                logger.error(f"Failed to update MTGO deck cache: {exc}")
                error = str(exc)
                try:
                    decks = load_aggregated_decks()
                except Exception as load_exc:  # noqa: BLE001
                    logger.error(f"Failed to load cached MTGO decks: {load_exc}")
                    error = f"{error}; cache load failed"
                    decks = []

            def finish():
                self._refresh_in_progress = False
                if self.deck_tree is None or self.player_tree is None:
                    if error:
                        self.status_var.set(f"Failed to refresh MTGO data ({error}).")
                    return
                if not decks:
                    self._clear_tree(self.deck_tree)
                    self._clear_tree(self.player_tree)
                    self.event_summary_var.set("")
                    if error:
                        self.status_var.set(f"Failed to refresh MTGO data ({error}).")
                    else:
                        self.status_var.set("No deck data available. Try again later.")
                    return

                rows = _filter_by_format(decks, target_fmt, lookback)
                self._clear_tree(self.deck_tree)
                self._clear_tree(self.player_tree)
                self._insert_rows(self.deck_tree, rows["archetypes"])
                self._insert_rows(self.player_tree, rows["players"])
                archetype_count = len(rows["archetypes"])
                player_count = len(rows["players"])
                if rows["events"]:
                    events_text = ", ".join(f"{label} ({count})" for label, count in rows["events"][:5])
                    self.event_summary_var.set(f"Events: {events_text}")
                else:
                    self.event_summary_var.set("Events: none in range")
                if error:
                    self.status_var.set(
                        f"Showing cached {target_fmt} decks ({archetype_count} archetypes, {player_count} players)."
                    )
                else:
                    self.status_var.set(
                        f"Showing {target_fmt} decks from the last {lookback} day(s): "
                        f"{archetype_count} archetypes, {player_count} players."
                    )

            self.after(0, finish)

        threading.Thread(target=worker, args=(fmt, days), daemon=True).start()


def _filter_by_format(decks: Iterable[dict[str, Any]], fmt: str, days: int) -> dict[str, list[tuple[str, int]]]:
    per_format = count_decks_by_archetype(decks, fmt=fmt, days=days)
    per_player = count_decks_by_player(decks, fmt=fmt, days=days)
    per_event = count_decks_by_event(decks, fmt=fmt, days=days)
    return {"archetypes": per_format, "players": per_player, "events": per_event}


__all__ = ["MetagameStatsView"]
