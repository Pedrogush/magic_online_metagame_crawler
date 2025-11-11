import wx
from pathlib import Path

MANA_RENDER_LOG = Path("cache") / "mana_render.log"
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

FULL_MANA_SYMBOLS: list[str] = (
    ["W", "U", "B", "R", "G", "C", "S", "X", "Y", "Z", "∞", "½"]
    + [str(i) for i in range(0, 21)]
    + [
        "W/U",
        "W/B",
        "U/B",
        "U/R",
        "B/R",
        "B/G",
        "R/G",
        "R/W",
        "G/W",
        "G/U",
        "C/W",
        "C/U",
        "C/B",
        "C/R",
        "C/G",
        "2/W",
        "2/U",
        "2/B",
        "2/R",
        "2/G",
        "W/P",
        "U/P",
        "B/P",
        "R/P",
        "G/P",
    ]
)

FORMAT_OPTIONS = [
    "Modern",
    "Standard",
    "Pioneer",
    "Legacy",
    "Vintage",
    "Pauper",
    "Commander",
    "Brawl",
    "Historic",
]
