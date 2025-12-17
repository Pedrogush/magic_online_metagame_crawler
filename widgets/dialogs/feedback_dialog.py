"""Dialog for gathering user feedback and exporting diagnostics."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import wx

from services.diagnostics_service import DiagnosticsService
from utils.constants import DARK_BG, DARK_PANEL, LIGHT_TEXT, SUBDUED_TEXT


class FeedbackDialog(wx.Dialog):
    """Collect feedback and produce a diagnostics zip file (no network calls)."""

    def __init__(self, parent: wx.Window, diagnostics_service: DiagnosticsService):
        super().__init__(parent, title="Send Feedback / Export Diagnostics", size=(540, 520))
        self.diagnostics_service = diagnostics_service
        self.SetBackgroundColour(DARK_BG)
        self._build_ui()
        self.CentreOnParent()

    # ------------------------------------------------------------------ UI ------------------------------------------------------------------
    def _build_ui(self) -> None:
        panel = wx.Panel(self)
        panel.SetBackgroundColour(DARK_BG)
        sizer = wx.BoxSizer(wx.VERTICAL)
        panel.SetSizer(sizer)

        intro = wx.StaticText(
            panel,
            label=(
                "Share what happened and export diagnostics to a zip file. "
                "Nothing is uploaded automatically."
            ),
        )
        intro.SetForegroundColour(SUBDUED_TEXT)
        intro.Wrap(500)
        sizer.Add(intro, 0, wx.ALL, 10)

        feedback_label = wx.StaticText(panel, label="Feedback (what were you doing?):")
        feedback_label.SetForegroundColour(LIGHT_TEXT)
        sizer.Add(feedback_label, 0, wx.LEFT | wx.RIGHT, 10)

        self.feedback_text = wx.TextCtrl(
            panel, style=wx.TE_MULTILINE | wx.TE_WORDWRAP, size=(-1, 140)
        )
        self.feedback_text.SetBackgroundColour(DARK_PANEL)
        self.feedback_text.SetForegroundColour(LIGHT_TEXT)
        sizer.Add(self.feedback_text, 0, wx.EXPAND | wx.ALL, 10)

        options_box = wx.StaticBox(panel, label="Include")
        options_box.SetForegroundColour(LIGHT_TEXT)
        options_box.SetBackgroundColour(DARK_BG)
        options_sizer = wx.StaticBoxSizer(options_box, wx.VERTICAL)

        self.include_logs_cb = wx.CheckBox(panel, label="Application logs")
        self.include_logs_cb.SetValue(True)
        self.include_logs_cb.SetForegroundColour(LIGHT_TEXT)
        options_sizer.Add(self.include_logs_cb, 0, wx.ALL, 6)

        self.include_events_cb = wx.CheckBox(panel, label="Usage events (anonymized)")
        self.include_events_cb.SetValue(self.diagnostics_service.event_logging_enabled)
        self.include_events_cb.SetForegroundColour(LIGHT_TEXT)
        options_sizer.Add(self.include_events_cb, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)

        self.enable_events_cb = wx.CheckBox(panel, label="Enable future event logging (opt-in)")
        self.enable_events_cb.SetValue(self.diagnostics_service.event_logging_enabled)
        self.enable_events_cb.SetForegroundColour(LIGHT_TEXT)
        self.enable_events_cb.Bind(wx.EVT_CHECKBOX, self._on_toggle_event_logging)
        options_sizer.Add(self.enable_events_cb, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)

        sizer.Add(options_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)

        destination_row = wx.BoxSizer(wx.HORIZONTAL)
        dest_label = wx.StaticText(panel, label="Save zip to:")
        dest_label.SetForegroundColour(LIGHT_TEXT)
        destination_row.Add(dest_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)

        self.destination_ctrl = wx.TextCtrl(panel, value=str(self._default_destination()))
        self.destination_ctrl.SetBackgroundColour(DARK_PANEL)
        self.destination_ctrl.SetForegroundColour(LIGHT_TEXT)
        destination_row.Add(self.destination_ctrl, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)

        browse_btn = wx.Button(panel, label="Browse…")
        browse_btn.Bind(wx.EVT_BUTTON, self._on_browse)
        destination_row.Add(browse_btn, 0, wx.ALIGN_CENTER_VERTICAL)

        sizer.Add(destination_row, 0, wx.EXPAND | wx.ALL, 10)

        self.status_text = wx.StaticText(panel, label="")
        self.status_text.SetForegroundColour(SUBDUED_TEXT)
        sizer.Add(self.status_text, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        btn_sizer = wx.StdDialogButtonSizer()
        ok_btn = wx.Button(panel, wx.ID_OK, label="Export")
        cancel_btn = wx.Button(panel, wx.ID_CANCEL, label="Cancel")
        btn_sizer.AddButton(ok_btn)
        btn_sizer.AddButton(cancel_btn)
        btn_sizer.Realize()
        sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 10)

        ok_btn.Bind(wx.EVT_BUTTON, self._on_export)

        panel.SetSizerAndFit(sizer)
        self.SetSizerAndFit(sizer)

    # ------------------------------------------------------------------ helpers ------------------------------------------------------------------
    def _default_destination(self) -> Path:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        return self.diagnostics_service.logs_dir / f"mtgo_tools_diagnostics_{ts}.zip"

    def _on_browse(self, _event: wx.CommandEvent) -> None:
        with wx.FileDialog(
            self,
            "Save diagnostics zip",
            wildcard="Zip files (*.zip)|*.zip",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
            defaultFile=Path(self.destination_ctrl.GetValue()).name,
            defaultDir=str(Path(self.destination_ctrl.GetValue()).parent),
        ) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                self.destination_ctrl.SetValue(dlg.GetPath())

    def _on_toggle_event_logging(self, _event: wx.CommandEvent) -> None:
        enabled = self.enable_events_cb.GetValue()
        self.diagnostics_service.set_event_logging_enabled(enabled)
        if enabled:
            self.include_events_cb.SetValue(True)
        self.status_text.SetLabel(
            "Usage events will be recorded locally." if enabled else "Usage event logging disabled."
        )

    def _on_export(self, _event: wx.CommandEvent) -> None:
        destination = Path(self.destination_ctrl.GetValue()).expanduser()
        include_logs = self.include_logs_cb.GetValue()
        include_events = self.include_events_cb.GetValue()
        feedback = self.feedback_text.GetValue()

        try:
            zip_path = self.diagnostics_service.export_diagnostics(
                feedback=feedback,
                include_logs=include_logs,
                include_event_log=include_events,
                destination=destination,
            )
            self.diagnostics_service.log_event(
                "diagnostics_exported",
                metadata={
                    "include_logs": include_logs,
                    "include_events": include_events,
                },
            )
        except Exception as exc:  # pragma: no cover - defensive
            self.status_text.SetLabel(f"Export failed: {exc}")
            wx.MessageBox(
                f"Could not export diagnostics:\n{exc}", "Export Error", wx.OK | wx.ICON_ERROR
            )
            return

        self.status_text.SetLabel(f"Saved diagnostics to {zip_path}")
        wx.MessageBox(
            f"Diagnostics exported to:\n{zip_path}",
            "Diagnostics Exported",
            wx.OK | wx.ICON_INFORMATION,
        )
        self.EndModal(wx.ID_OK)


def show_feedback_dialog(parent: wx.Window, diagnostics_service: DiagnosticsService) -> None:
    dialog = FeedbackDialog(parent, diagnostics_service)
    dialog.ShowModal()
    dialog.Destroy()


__all__ = ["FeedbackDialog", "show_feedback_dialog"]
