import wx

from utils.ui_constants import DARK_ALT, DARK_BG, LIGHT_TEXT


class GuideEntryDialog(wx.Dialog):
    def __init__(
        self, parent: wx.Window, archetype_names: list[str], data: dict[str, str] | None = None
    ) -> None:
        super().__init__(parent, title="Sideboard Guide Entry", size=(420, 360))

        main_sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(main_sizer)

        panel = wx.Panel(self)
        panel.SetBackgroundColour(DARK_BG)
        panel_sizer = wx.BoxSizer(wx.VERTICAL)
        panel.SetSizer(panel_sizer)
        main_sizer.Add(panel, 1, wx.EXPAND | wx.ALL, 8)

        archetype_label = wx.StaticText(panel, label="Archetype")
        archetype_label.SetForegroundColour(LIGHT_TEXT)
        panel_sizer.Add(archetype_label, 0, wx.TOP | wx.LEFT, 4)

        initial_choices = sorted({name for name in archetype_names if name})
        self.archetype_ctrl = wx.ComboBox(panel, choices=initial_choices, style=wx.CB_DROPDOWN)
        self.archetype_ctrl.SetBackgroundColour(DARK_ALT)
        self.archetype_ctrl.SetForegroundColour(LIGHT_TEXT)
        if data and data.get("archetype"):
            existing = {
                self.archetype_ctrl.GetString(i) for i in range(self.archetype_ctrl.GetCount())
            }
            if data["archetype"] not in existing:
                self.archetype_ctrl.Append(data["archetype"])
            self.archetype_ctrl.SetValue(data["archetype"])
        panel_sizer.Add(self.archetype_ctrl, 0, wx.EXPAND | wx.ALL, 4)

        self.cards_in_ctrl = wx.TextCtrl(
            panel, value=(data or {}).get("cards_in", ""), style=wx.TE_MULTILINE
        )
        self.cards_in_ctrl.SetBackgroundColour(DARK_ALT)
        self.cards_in_ctrl.SetForegroundColour(LIGHT_TEXT)
        self.cards_in_ctrl.SetHint("Cards to bring in")
        panel_sizer.Add(self.cards_in_ctrl, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 4)

        self.cards_out_ctrl = wx.TextCtrl(
            panel, value=(data or {}).get("cards_out", ""), style=wx.TE_MULTILINE
        )
        self.cards_out_ctrl.SetBackgroundColour(DARK_ALT)
        self.cards_out_ctrl.SetForegroundColour(LIGHT_TEXT)
        self.cards_out_ctrl.SetHint("Cards to take out")
        panel_sizer.Add(self.cards_out_ctrl, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 4)

        self.notes_ctrl = wx.TextCtrl(
            panel, value=(data or {}).get("notes", ""), style=wx.TE_MULTILINE
        )
        self.notes_ctrl.SetBackgroundColour(DARK_ALT)
        self.notes_ctrl.SetForegroundColour(LIGHT_TEXT)
        self.notes_ctrl.SetHint("Notes")
        panel_sizer.Add(self.notes_ctrl, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 4)

        button_sizer = self.CreateSeparatedButtonSizer(wx.OK | wx.CANCEL)
        if button_sizer:
            main_sizer.Add(button_sizer, 0, wx.EXPAND | wx.ALL, 8)

    def get_data(self) -> dict[str, str]:
        return {
            "archetype": self.archetype_ctrl.GetValue().strip(),
            "cards_in": self.cards_in_ctrl.GetValue().strip(),
            "cards_out": self.cards_out_ctrl.GetValue().strip(),
            "notes": self.notes_ctrl.GetValue().strip(),
        }
