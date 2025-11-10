#!/usr/bin/env python3
"""wxPython entry point that launches the deck builder directly."""

from __future__ import annotations

import wx
from loguru import logger

from widgets.deck_selector import MTGDeckSelectionFrame


class MetagameWxApp(wx.App):
    """Bootstrap the redesigned deck builder."""

    def OnInit(self) -> bool:  # noqa: N802 - wx override
        logger.info("Starting MTGO Metagame Deck Builder (wx)")
        frame = MTGDeckSelectionFrame(None)
        frame.Show()
        self.SetTopWindow(frame)
        wx.CallAfter(frame.ensure_card_data_loaded)
        return True


def main() -> None:
    app = MetagameWxApp(False)
    app.MainLoop()


if __name__ == "__main__":
    main()
