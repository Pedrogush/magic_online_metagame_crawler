from __future__ import annotations

import wx

from utils.constants import DARK_BG, DARK_PANEL, LIGHT_TEXT, SUBDUED_TEXT
from widgets.help_content import HELP_TEXT


def show_help_dialog(parent: wx.Window | None) -> None:
    """Display the help/about dialog with feature guide and contact details."""
    dialog = wx.Dialog(parent, title="Help & About", size=(720, 640))
    dialog.SetBackgroundColour(DARK_BG)

    sizer = wx.BoxSizer(wx.VERTICAL)
    dialog.SetSizer(sizer)

    intro = wx.StaticText(dialog, label="How to use MTGO Deck Research & Builder")
    intro.SetForegroundColour(LIGHT_TEXT)
    intro_font = intro.GetFont()
    intro_font.PointSize += 1
    intro_font = intro_font.Bold()
    intro.SetFont(intro_font)
    sizer.Add(intro, 0, wx.ALL, 10)

    help_body = wx.TextCtrl(
        dialog,
        value=HELP_TEXT,
        style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_WORDWRAP | wx.NO_BORDER,
    )
    help_body.SetBackgroundColour(DARK_PANEL)
    help_body.SetForegroundColour(LIGHT_TEXT)
    sizer.Add(help_body, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

    note = wx.StaticText(
        dialog,
        label="Tip: Hover any button to see a quick description.",
    )
    note.SetForegroundColour(SUBDUED_TEXT)
    sizer.Add(note, 0, wx.ALL, 10)

    btn_row = wx.BoxSizer(wx.HORIZONTAL)
    sizer.Add(btn_row, 0, wx.ALIGN_RIGHT | wx.ALL, 10)

    close_btn = wx.Button(dialog, wx.ID_CLOSE, label="Close")
    close_btn.Bind(wx.EVT_BUTTON, lambda _evt: dialog.EndModal(wx.ID_CLOSE))
    btn_row.Add(close_btn, 0)

    dialog.ShowModal()
    dialog.Destroy()


__all__ = ["show_help_dialog"]
