import wx

from utils.constants import DARK_ALT, DARK_BG, LIGHT_TEXT


class GuideEntryDialog(wx.Dialog):
    def __init__(
        self, parent: wx.Window, archetype_names: list[str], data: dict[str, str] | None = None
    ) -> None:
        super().__init__(parent, title="Sideboard Guide Entry", size=(650, 500))

        main_sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(main_sizer)

        panel = wx.Panel(self)
        panel.SetBackgroundColour(DARK_BG)
        panel_sizer = wx.BoxSizer(wx.VERTICAL)
        panel.SetSizer(panel_sizer)
        main_sizer.Add(panel, 1, wx.EXPAND | wx.ALL, 8)

        # Archetype
        archetype_label = wx.StaticText(panel, label="Archetype/Matchup")
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

        # Play scenario section
        play_label = wx.StaticText(panel, label="On the Play")
        play_label.SetForegroundColour(LIGHT_TEXT)
        play_label.SetFont(play_label.GetFont().Bold())
        panel_sizer.Add(play_label, 0, wx.TOP | wx.LEFT, 8)

        play_sizer = wx.BoxSizer(wx.HORIZONTAL)
        panel_sizer.Add(play_sizer, 1, wx.EXPAND | wx.ALL, 4)

        self.play_out_ctrl = wx.TextCtrl(
            panel, value=(data or {}).get("play_out", ""), style=wx.TE_MULTILINE
        )
        self.play_out_ctrl.SetBackgroundColour(DARK_ALT)
        self.play_out_ctrl.SetForegroundColour(LIGHT_TEXT)
        self.play_out_ctrl.SetHint("Cards out (e.g., 2x Lightning Bolt)")
        play_sizer.Add(self.play_out_ctrl, 1, wx.EXPAND | wx.RIGHT, 4)

        self.play_in_ctrl = wx.TextCtrl(
            panel, value=(data or {}).get("play_in", ""), style=wx.TE_MULTILINE
        )
        self.play_in_ctrl.SetBackgroundColour(DARK_ALT)
        self.play_in_ctrl.SetForegroundColour(LIGHT_TEXT)
        self.play_in_ctrl.SetHint("Cards in (e.g., 2x Surgical Extraction)")
        play_sizer.Add(self.play_in_ctrl, 1, wx.EXPAND)

        # Draw scenario section
        draw_label = wx.StaticText(panel, label="On the Draw")
        draw_label.SetForegroundColour(LIGHT_TEXT)
        draw_label.SetFont(draw_label.GetFont().Bold())
        panel_sizer.Add(draw_label, 0, wx.TOP | wx.LEFT, 8)

        draw_sizer = wx.BoxSizer(wx.HORIZONTAL)
        panel_sizer.Add(draw_sizer, 1, wx.EXPAND | wx.ALL, 4)

        self.draw_out_ctrl = wx.TextCtrl(
            panel, value=(data or {}).get("draw_out", ""), style=wx.TE_MULTILINE
        )
        self.draw_out_ctrl.SetBackgroundColour(DARK_ALT)
        self.draw_out_ctrl.SetForegroundColour(LIGHT_TEXT)
        self.draw_out_ctrl.SetHint("Cards out (e.g., 1x Mountain)")
        draw_sizer.Add(self.draw_out_ctrl, 1, wx.EXPAND | wx.RIGHT, 4)

        self.draw_in_ctrl = wx.TextCtrl(
            panel, value=(data or {}).get("draw_in", ""), style=wx.TE_MULTILINE
        )
        self.draw_in_ctrl.SetBackgroundColour(DARK_ALT)
        self.draw_in_ctrl.SetForegroundColour(LIGHT_TEXT)
        self.draw_in_ctrl.SetHint("Cards in (e.g., 1x Containment Priest)")
        draw_sizer.Add(self.draw_in_ctrl, 1, wx.EXPAND)

        # Notes section
        notes_label = wx.StaticText(panel, label="Notes (Optional)")
        notes_label.SetForegroundColour(LIGHT_TEXT)
        panel_sizer.Add(notes_label, 0, wx.TOP | wx.LEFT, 8)

        self.notes_ctrl = wx.TextCtrl(
            panel, value=(data or {}).get("notes", ""), style=wx.TE_MULTILINE
        )
        self.notes_ctrl.SetBackgroundColour(DARK_ALT)
        self.notes_ctrl.SetForegroundColour(LIGHT_TEXT)
        self.notes_ctrl.SetHint("Strategy notes for this matchup")
        panel_sizer.Add(self.notes_ctrl, 1, wx.EXPAND | wx.ALL, 4)

        button_sizer = self.CreateSeparatedButtonSizer(wx.OK | wx.CANCEL)
        if button_sizer:
            main_sizer.Add(button_sizer, 0, wx.EXPAND | wx.ALL, 8)

    def get_data(self) -> dict[str, str]:
        return {
            "archetype": self.archetype_ctrl.GetValue().strip(),
            "play_out": self.play_out_ctrl.GetValue().strip(),
            "play_in": self.play_in_ctrl.GetValue().strip(),
            "draw_out": self.draw_out_ctrl.GetValue().strip(),
            "draw_in": self.draw_in_ctrl.GetValue().strip(),
            "notes": self.notes_ctrl.GetValue().strip(),
        }
