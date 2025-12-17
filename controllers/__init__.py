"""Controllers module - Application-level controllers for coordinating business logic."""

try:  # wxPython may be missing in headless environments
    from controllers.app_controller import (
        AppController,
        get_deck_selector_controller,
        reset_deck_selector_controller,
    )
except Exception:  # pragma: no cover - UI controller unavailable without wx
    AppController = None

    def get_deck_selector_controller():
        raise RuntimeError("AppController is unavailable (wxPython not installed)")

    def reset_deck_selector_controller():
        return None


__all__ = ["AppController", "get_deck_selector_controller", "reset_deck_selector_controller"]
