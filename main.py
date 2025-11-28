#!/usr/bin/env python3
"""wxPython entry point that launches the deck builder directly."""

from __future__ import annotations

import wx
from loguru import logger

from controllers.app_controller import get_deck_selector_controller
from widgets.splash_frame import LoadingFrame


class MetagameWxApp(wx.App):
    """Bootstrap the redesigned deck builder."""

    def OnInit(self) -> bool:  # noqa: N802 - wx override
        logger.info("Starting MTGO Metagame Deck Builder (wx)")
        self.loading_frame = LoadingFrame()
        self.loading_frame.Show()
        self.loading_frame.Layout()
        self.loading_frame.Refresh()
        self.loading_frame.Update()
        wx.CallAfter(self._build_main_window)
        return True

    def _build_main_window(self) -> None:
        controller = get_deck_selector_controller()
        self.controller = controller
        self.SetTopWindow(controller.frame)

        def show_main() -> None:
            frame = controller.frame
            frame.Freeze()
            frame.Layout()
            frame.SendSizeEvent()
            frame.Thaw()
            frame.Show()
            frame.Refresh()
            frame.Update()
            wx.CallAfter(frame.ensure_card_data_loaded)

        if getattr(self, "loading_frame", None):
            self.loading_frame.set_ready(show_main)
        else:
            show_main()

    def OnExceptionInMainLoop(self) -> bool:  # noqa: N802 - wx override
        """Handle exceptions in the main event loop."""
        import sys
        import traceback

        exc_type, exc_value, exc_traceback = sys.exc_info()
        logger.error("=== UNHANDLED EXCEPTION IN MAIN LOOP ===")
        logger.error(f"Exception type: {exc_type.__name__}")
        logger.error(f"Exception value: {exc_value}")
        logger.error("Traceback:")
        for line in traceback.format_tb(exc_traceback):
            logger.error(line.rstrip())
        logger.error("=== END UNHANDLED EXCEPTION ===")

        # Show error dialog to user
        error_msg = f"An unexpected error occurred:\n\n{exc_type.__name__}: {exc_value}\n\nCheck the log file for details."
        wx.MessageBox(error_msg, "Application Error", wx.OK | wx.ICON_ERROR)

        # Return True to continue running, False to exit
        return True


def main() -> None:
    # Install global exception handler for exceptions outside of wx mainloop
    import sys
    import traceback

    def global_exception_handler(exc_type, exc_value, exc_traceback):
        logger.error("=== UNCAUGHT EXCEPTION (GLOBAL) ===")
        logger.error(f"Exception type: {exc_type.__name__}")
        logger.error(f"Exception value: {exc_value}")
        logger.error("Traceback:")
        for line in traceback.format_tb(exc_traceback):
            logger.error(line.rstrip())
        logger.error("=== END UNCAUGHT EXCEPTION ===")

        # Call default handler
        sys.__excepthook__(exc_type, exc_value, exc_traceback)

    sys.excepthook = global_exception_handler

    app = MetagameWxApp(False)
    app.MainLoop()


if __name__ == "__main__":
    main()
