"""UI-specific constants shared across widgets."""

import wx

SUBDUED_TEXT = wx.Colour(185, 191, 202)
DARK_BG = wx.Colour(20, 22, 27)
DARK_PANEL = wx.Colour(34, 39, 46)
DARK_ALT = wx.Colour(40, 46, 54)
DARK_ACCENT = wx.Colour(59, 130, 246)
LIGHT_TEXT = wx.Colour(236, 236, 236)

ZONE_TITLES = {
    "main": "Mainboard",
    "side": "Sideboard",
    "out": "Outboard",
}

__all__ = [
    "SUBDUED_TEXT",
    "DARK_BG",
    "DARK_PANEL",
    "DARK_ALT",
    "DARK_ACCENT",
    "LIGHT_TEXT",
    "ZONE_TITLES",
]
