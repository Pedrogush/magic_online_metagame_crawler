#!/usr/bin/env python3
"""wxPython entry point that launches the deck builder directly."""

from __future__ import annotations

import multiprocessing as mp
import time
from collections.abc import Callable

import wx
from loguru import logger

from controllers.app_controller import get_deck_selector_controller
from utils.constants import DARK_ACCENT, DARK_BG, DARK_PANEL, LIGHT_TEXT


def run_splash(ready_event: mp.synchronize.Event) -> None:
    """Run the splash screen in a dedicated process so it never starves."""
    mp.freeze_support()
    splash_app = wx.App(False)
    frame = LoadingFrame()

    def poll_ready(_evt: wx.TimerEvent) -> None:
        if ready_event.is_set():
            frame.set_ready()

    timer = wx.Timer(frame)
    frame.Bind(wx.EVT_TIMER, poll_ready, timer)
    timer.Start(80)
    frame.Show()
    splash_app.MainLoop()


class LoadingFrame(wx.Frame):
    """Lightweight splash with a short progress pulse to avoid blank startup screens."""

    def __init__(self, min_duration: float = 0.8, max_duration: float = 1.8) -> None:
        super().__init__(
            None,
            title="Loading MTGO Deck Builder",
            style=wx.BORDER_NONE | wx.STAY_ON_TOP,
            size=(460, 160),
        )
        self._start = time.monotonic()
        self._min_duration = min_duration
        self._max_duration = max_duration
        self._ready = False
        self._finished = False
        self._on_ready: Callable[[], None] | None = None

        self.SetBackgroundColour(DARK_BG)
        panel = wx.Panel(self)
        panel.SetBackgroundColour(DARK_PANEL)
        outer = wx.BoxSizer(wx.VERTICAL)
        panel.SetSizer(outer)
        frame_sizer = wx.BoxSizer(wx.VERTICAL)
        frame_sizer.Add(panel, 1, wx.EXPAND | wx.ALL, 12)
        self.SetSizer(frame_sizer)

        title = wx.StaticText(panel, label="Loading MTGOTools...")
        title.SetForegroundColour(LIGHT_TEXT)
        title_font = title.GetFont()
        title_font.MakeBold()
        title.SetFont(title_font)
        outer.Add(title, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.TOP | wx.LEFT | wx.RIGHT, 18)
        outer.AddStretchSpacer(1)

        self.gauge = wx.Gauge(panel, range=100, style=wx.GA_HORIZONTAL | wx.GA_SMOOTH)
        self.gauge.SetMinSize((-1, 22))
        self.gauge.SetForegroundColour(DARK_ACCENT)
        self.gauge.SetBackgroundColour(DARK_BG)
        self.gauge.SetValue(5)
        outer.Add(self.gauge, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 18)
        panel.Layout()
        self.Layout()

        self._timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_tick, self._timer)
        self._timer.Start(40)

        self.Centre(wx.BOTH)

    def set_ready(self, on_ready: Callable[[], None] | None = None) -> None:
        """Mark the splash as ready to close once the minimum display time is met."""
        self._ready = True
        self._on_ready = on_ready
        self._maybe_finish()

    def _on_tick(self, _event: wx.TimerEvent) -> None:
        elapsed = time.monotonic() - self._start
        progress = min(100, int((elapsed / self._max_duration) * 100))
        self.gauge.SetValue(progress)
        self._maybe_finish()

    def _maybe_finish(self) -> None:
        if self._finished:
            return
        elapsed = time.monotonic() - self._start
        if (self._ready and elapsed >= self._min_duration) or elapsed >= self._max_duration:
            self._finished = True
            self._timer.Stop()
            callback = self._on_ready
            self.gauge.SetValue(100)
            self.Hide()
            self.Destroy()
            if callback:
                wx.CallAfter(callback)


class MetagameWxApp(wx.App):
    """Bootstrap the redesigned deck builder."""

    def OnInit(self) -> bool:  # noqa: N802 - wx override
        logger.info("Starting MTGO Metagame Deck Builder (wx)")
        self.loading_frame = LoadingFrame()
        # If splash is running out-of-process we only need the readiness signal.
        if getattr(self, "_splash_event", None) is None:
            self.loading_frame.Show()
        wx.CallAfter(self._build_main_window)
        return True

    def _build_main_window(self) -> None:
        controller = get_deck_selector_controller()
        self.controller = controller
        self.SetTopWindow(controller.frame)

        def show_main() -> None:
            controller.frame.Show()
            wx.CallAfter(controller.frame.ensure_card_data_loaded)

        splash_event = getattr(self, "_splash_event", None)
        if splash_event is not None:
            splash_event.set()
            self._join_splash_process()
            show_main()
        elif getattr(self, "loading_frame", None):
            self.loading_frame.set_ready(show_main)
        else:
            show_main()

    def _join_splash_process(self) -> None:
        process = getattr(self, "_splash_process", None)
        if not process:
            return
        try:
            process.join(timeout=1.5)
        except Exception:
            pass

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

    mp.freeze_support()

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

    # Start splash process before heavy work
    splash_event: mp.synchronize.Event | None = None
    splash_process: mp.Process | None = None
    try:
        splash_event = mp.Event()
        splash_process = mp.Process(target=run_splash, args=(splash_event,), daemon=True)
        splash_process.start()
    except Exception as exc:  # pragma: no cover - best effort fallback
        logger.warning(f"Failed to start splash process: {exc}")
        splash_event = None
        splash_process = None

    app = MetagameWxApp(False)
    app._splash_event = splash_event  # type: ignore[attr-defined]
    app._splash_process = splash_process  # type: ignore[attr-defined]

    app.MainLoop()


if __name__ == "__main__":
    main()
