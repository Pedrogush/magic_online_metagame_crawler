"""Controllers module - Application-level controllers for coordinating business logic."""

from importlib import import_module
from typing import Any

__all__ = [
    "AppController",
    "get_deck_selector_controller",
    "reset_deck_selector_controller",
]


def __getattr__(name: str) -> Any:
    if name in __all__:
        module = import_module("controllers.app_controller")
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module 'controllers' has no attribute '{name}'")
