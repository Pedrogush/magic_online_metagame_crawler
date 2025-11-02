#!/usr/bin/env python3
"""MTG Deck Builder entry point."""

import tkinter as tk
from loguru import logger

from widgets.deck_selector import MTGDeckSelectionWidget


def main() -> None:
    logger.info("Starting MTG Deck Builder")
    root = tk.Tk()
    app = MTGDeckSelectionWidget(root)
    try:
        app.ensure_card_data_loaded()
    except Exception as exc:  # graceful fallback if preload fails
        logger.warning(f"Unable to preload card data: {exc}")
    root.mainloop()


if __name__ == "__main__":
    main()
