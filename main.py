#!/usr/bin/env python3
"""
MTG Metagame Analysis Tools - Main Launcher

Launches the opponent tracking widget and/or deck research browser.
"""
import tkinter as tk
from tkinter import ttk
import sys
import threading
from loguru import logger


class LauncherWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("MTG Metagame Tools Launcher")
        self.root.geometry("400x300")
        self.root.configure(bg="#f0e6d2")

        # Header
        header = tk.Label(
            self.root,
            text="MTG Metagame Analysis Tools",
            font=("Arial", 16, "bold"),
            bg="#f0e6d2",
            fg="#2c3e50"
        )
        header.pack(pady=20)

        subtitle = tk.Label(
            self.root,
            text="Select a tool to launch:",
            font=("Arial", 11),
            bg="#f0e6d2",
            fg="#34495e"
        )
        subtitle.pack(pady=5)

        # Button frame
        button_frame = tk.Frame(self.root, bg="#f0e6d2")
        button_frame.pack(pady=20, expand=True)

        # Opponent Tracker button
        self.tracker_btn = tk.Button(
            button_frame,
            text="🎯 Opponent Deck Tracker",
            command=self.launch_opponent_tracker,
            font=("Arial", 12, "bold"),
            bg="#3498db",
            fg="white",
            activebackground="#2980b9",
            relief="raised",
            bd=3,
            padx=20,
            pady=15,
            cursor="hand2"
        )
        self.tracker_btn.pack(pady=10, fill="x")

        # Deck Browser button
        self.browser_btn = tk.Button(
            button_frame,
            text="📚 Deck Research Browser",
            command=self.launch_deck_browser,
            font=("Arial", 12, "bold"),
            bg="#2ecc71",
            fg="white",
            activebackground="#27ae60",
            relief="raised",
            bd=3,
            padx=20,
            pady=15,
            cursor="hand2"
        )
        self.browser_btn.pack(pady=10, fill="x")

        # Launch Both button
        self.both_btn = tk.Button(
            button_frame,
            text="🚀 Launch Both",
            command=self.launch_both,
            font=("Arial", 12, "bold"),
            bg="#9b59b6",
            fg="white",
            activebackground="#8e44ad",
            relief="raised",
            bd=3,
            padx=20,
            pady=15,
            cursor="hand2"
        )
        self.both_btn.pack(pady=10, fill="x")

        # Info text
        info = tk.Label(
            self.root,
            text="Press ESC to close this launcher",
            font=("Arial", 9, "italic"),
            bg="#f0e6d2",
            fg="#7f8c8d"
        )
        info.pack(side="bottom", pady=10)

        # Bind ESC to close
        self.root.bind("<Escape>", lambda e: self.root.quit())

        # Center window on screen
        self.center_window()

        # Preload MTGJSON card data in background
        self.preload_card_data()

    def center_window(self):
        """Center the launcher window on screen"""
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')

    def launch_opponent_tracker(self):
        """Launch the opponent deck tracking widget"""
        logger.info("Launching Opponent Deck Tracker...")
        try:
            from widgets.identify_opponent import MTGOpponentDeckSpy
            tracker = MTGOpponentDeckSpy()
            logger.info("Opponent Deck Tracker launched successfully")
            # Don't close launcher - let user launch more tools if needed
        except Exception as e:
            logger.error(f"Failed to launch Opponent Tracker: {e}")
            self.show_error("Opponent Tracker", str(e))

    def launch_deck_browser(self):
        """Launch the deck research browser"""
        logger.info("Launching Deck Research Browser...")
        # Disable button temporarily to prevent double-clicks
        self.browser_btn.config(state="disabled", text="⏳ Opening...")

        def launch():
            try:
                from widgets.deck_selector import MTGDeckSelectionWidget
                browser_root = tk.Toplevel()
                browser_root.title("MTG Deck Research Browser")
                browser = MTGDeckSelectionWidget(browser_root)
                logger.info("Deck Research Browser launched successfully")
                # Re-enable button after short delay
                self.root.after(1000, lambda: self.browser_btn.config(
                    state="normal",
                    text="📚 Deck Research Browser"
                ))
            except Exception as e:
                logger.error(f"Failed to launch Deck Browser: {e}")
                self.browser_btn.config(state="normal", text="📚 Deck Research Browser")
                self.show_error("Deck Browser", str(e))

        # Launch in next event loop to allow UI to update
        self.root.after(50, launch)

    def preload_card_data(self):
        """Warm up card database for the integrated deck builder features"""

        def worker():
            try:
                from utils.card_data import CardDataManager

                manager = CardDataManager()
                manager.ensure_latest()
                logger.info("MTGJSON card data cache ready")
            except Exception as exc:
                logger.warning(f"Unable to preload card data: {exc}")

        threading.Thread(target=worker, daemon=True).start()

    def launch_both(self):
        """Launch both widgets"""
        logger.info("Launching all tools...")
        self.launch_opponent_tracker()
        self.launch_deck_browser()

    def show_error(self, tool_name, error_msg):
        """Show error dialog"""
        error_window = tk.Toplevel(self.root)
        error_window.title(f"Error Launching {tool_name}")
        error_window.geometry("400x150")
        error_window.configure(bg="#e74c3c")

        tk.Label(
            error_window,
            text=f"Failed to launch {tool_name}",
            font=("Arial", 12, "bold"),
            bg="#e74c3c",
            fg="white"
        ).pack(pady=10)

        tk.Label(
            error_window,
            text=str(error_msg)[:100],
            font=("Arial", 9),
            bg="#e74c3c",
            fg="white",
            wraplength=350
        ).pack(pady=5)

        tk.Button(
            error_window,
            text="Close",
            command=error_window.destroy,
            bg="white",
            fg="#e74c3c"
        ).pack(pady=10)

    def run(self):
        """Start the launcher"""
        logger.info("MTG Metagame Tools Launcher started")
        self.root.mainloop()


def main():
    """Main entry point"""
    logger.info("=" * 60)
    logger.info("MTG Metagame Analysis Tools")
    logger.info("=" * 60)

    launcher = LauncherWindow()
    launcher.run()


if __name__ == "__main__":
    main()
