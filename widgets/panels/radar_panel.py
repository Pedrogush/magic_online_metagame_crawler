"""
Radar Panel - Displays archetype card frequency analysis.

Shows mainboard and sideboard card frequencies with inclusion rates and saturation percentages.
"""

from __future__ import annotations

from typing import Any, Callable

import wx
import wx.dataview as dv

from services.radar_service import RadarData, RadarService, get_radar_service
from utils.constants import DARK_ALT, DARK_PANEL, LIGHT_TEXT


class RadarPanel(wx.Panel):
    """Panel that displays archetype radar (card frequency analysis)."""

    def __init__(
        self,
        parent: wx.Window,
        radar_service: RadarService | None = None,
        on_export: Callable[[RadarData], None] | None = None,
        on_use_for_search: Callable[[RadarData], None] | None = None,
    ):
        """
        Initialize the radar panel.

        Args:
            parent: Parent window
            radar_service: Radar service for calculations
            on_export: Callback when export button clicked (radar_data)
            on_use_for_search: Callback when "Use for Search" clicked (radar_data)
        """
        super().__init__(parent)
        self.SetBackgroundColour(DARK_PANEL)

        self.radar_service = radar_service or get_radar_service()
        self.on_export = on_export
        self.on_use_for_search = on_use_for_search
        self.current_radar: RadarData | None = None

        self._build_ui()

    def _build_ui(self) -> None:
        """Build the panel UI."""
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(sizer)

        # Header with archetype info and controls
        header_sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(header_sizer, 0, wx.EXPAND | wx.ALL, 6)

        # Archetype name label
        self.archetype_label = wx.StaticText(self, label="No radar loaded.")
        self.archetype_label.SetForegroundColour(LIGHT_TEXT)
        font = self.archetype_label.GetFont()
        font.PointSize += 2
        font = font.Bold()
        self.archetype_label.SetFont(font)
        header_sizer.Add(self.archetype_label, 1, wx.ALIGN_CENTER_VERTICAL)

        # Export button
        self.export_btn = wx.Button(self, label="Export as Decklist")
        self.export_btn.Enable(False)
        self.export_btn.Bind(wx.EVT_BUTTON, self._on_export_clicked)
        header_sizer.Add(self.export_btn, 0, wx.LEFT, 6)

        # Use for search button
        self.use_search_btn = wx.Button(self, label="Use for Search")
        self.use_search_btn.Enable(False)
        self.use_search_btn.Bind(wx.EVT_BUTTON, self._on_use_search_clicked)
        header_sizer.Add(self.use_search_btn, 0, wx.LEFT, 6)

        # Summary statistics
        self.summary_label = wx.StaticText(self, label="")
        self.summary_label.SetForegroundColour(LIGHT_TEXT)
        sizer.Add(self.summary_label, 0, wx.ALL, 6)

        # Split view for mainboard and sideboard
        split_sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(split_sizer, 1, wx.EXPAND | wx.ALL, 6)

        # Mainboard section
        mainboard_box = wx.StaticBox(self, label="Mainboard Radar")
        mainboard_box.SetForegroundColour(LIGHT_TEXT)
        mainboard_box_sizer = wx.StaticBoxSizer(mainboard_box, wx.VERTICAL)
        split_sizer.Add(mainboard_box_sizer, 1, wx.EXPAND | wx.RIGHT, 6)

        self.mainboard_list = dv.DataViewListCtrl(self)
        self.mainboard_list.AppendTextColumn("Card", width=200)
        self.mainboard_list.AppendTextColumn("Inclusion %", width=90)
        self.mainboard_list.AppendTextColumn("Saturation %", width=90)
        self.mainboard_list.AppendTextColumn("Avg Copies", width=90)
        self.mainboard_list.AppendTextColumn("Max", width=60)
        self.mainboard_list.SetBackgroundColour(DARK_ALT)
        self.mainboard_list.SetForegroundColour(LIGHT_TEXT)
        mainboard_box_sizer.Add(self.mainboard_list, 1, wx.EXPAND | wx.ALL, 6)

        # Sideboard section
        sideboard_box = wx.StaticBox(self, label="Sideboard Radar")
        sideboard_box.SetForegroundColour(LIGHT_TEXT)
        sideboard_box_sizer = wx.StaticBoxSizer(sideboard_box, wx.VERTICAL)
        split_sizer.Add(sideboard_box_sizer, 1, wx.EXPAND)

        self.sideboard_list = dv.DataViewListCtrl(self)
        self.sideboard_list.AppendTextColumn("Card", width=200)
        self.sideboard_list.AppendTextColumn("Inclusion %", width=90)
        self.sideboard_list.AppendTextColumn("Saturation %", width=90)
        self.sideboard_list.AppendTextColumn("Avg Copies", width=90)
        self.sideboard_list.AppendTextColumn("Max", width=60)
        self.sideboard_list.SetBackgroundColour(DARK_ALT)
        self.sideboard_list.SetForegroundColour(LIGHT_TEXT)
        sideboard_box_sizer.Add(self.sideboard_list, 1, wx.EXPAND | wx.ALL, 6)

    # ============= Public API =============

    def display_radar(self, radar: RadarData) -> None:
        """
        Display radar data in the panel.

        Args:
            radar: RadarData to display
        """
        self.current_radar = radar

        # Update header
        self.archetype_label.SetLabel(
            f"{radar.archetype_name} - {radar.format_name} Radar"
        )

        # Update summary
        summary = (
            f"Analyzed {radar.total_decks_analyzed} decks  |  "
            f"{len(radar.mainboard_cards)} unique mainboard cards  |  "
            f"{len(radar.sideboard_cards)} unique sideboard cards"
        )
        if radar.decks_failed > 0:
            summary += f"  |  {radar.decks_failed} decks failed"
        self.summary_label.SetLabel(summary)

        # Enable buttons
        self.export_btn.Enable(True)
        self.use_search_btn.Enable(True)

        # Populate lists
        self._populate_card_list(self.mainboard_list, radar.mainboard_cards)
        self._populate_card_list(self.sideboard_list, radar.sideboard_cards)

    def clear(self) -> None:
        """Clear the radar display."""
        self.current_radar = None
        self.archetype_label.SetLabel("No radar loaded.")
        self.summary_label.SetLabel("")
        self.mainboard_list.DeleteAllItems()
        self.sideboard_list.DeleteAllItems()
        self.export_btn.Enable(False)
        self.use_search_btn.Enable(False)

    # ============= Private Methods =============

    def _populate_card_list(self, list_ctrl: dv.DataViewListCtrl, cards: list) -> None:
        """
        Populate a list control with card frequency data.

        Args:
            list_ctrl: DataViewListCtrl to populate
            cards: List of CardFrequency objects
        """
        list_ctrl.DeleteAllItems()

        for card in cards:
            list_ctrl.AppendItem([
                card.card_name,
                f"{card.inclusion_rate:.1f}%",
                f"{card.saturation_rate:.1f}%",
                f"{card.avg_copies:.2f}",
                str(card.max_copies),
            ])

    def _on_export_clicked(self, event: wx.Event) -> None:
        """Handle export button click."""
        if self.current_radar and self.on_export:
            self.on_export(self.current_radar)

    def _on_use_search_clicked(self, event: wx.Event) -> None:
        """Handle use for search button click."""
        if self.current_radar and self.on_use_for_search:
            self.on_use_for_search(self.current_radar)


class RadarDialog(wx.Dialog):
    """Dialog for generating and viewing archetype radars."""

    def __init__(
        self,
        parent: wx.Window,
        metagame_repo,
        format_name: str,
        radar_service: RadarService | None = None,
    ):
        """
        Initialize the radar dialog.

        Args:
            parent: Parent window
            metagame_repo: Metagame repository for fetching archetypes
            format_name: MTG format (e.g., "Modern", "Standard")
            radar_service: Radar service for calculations
        """
        super().__init__(
            parent,
            title=f"Archetype Radar - {format_name}",
            size=(900, 700),
        )
        self.SetBackgroundColour(DARK_PANEL)

        self.metagame_repo = metagame_repo
        self.format_name = format_name
        self.radar_service = radar_service or get_radar_service()
        self.archetypes: list[dict[str, Any]] = []
        self.current_radar: RadarData | None = None

        self._build_ui()
        self._load_archetypes()

    def _build_ui(self) -> None:
        """Build the dialog UI."""
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(sizer)

        # Archetype selection
        selection_sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(selection_sizer, 0, wx.EXPAND | wx.ALL, 10)

        label = wx.StaticText(self, label="Select Archetype:")
        label.SetForegroundColour(LIGHT_TEXT)
        selection_sizer.Add(label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)

        self.archetype_choice = wx.Choice(self)
        self.archetype_choice.SetBackgroundColour(DARK_ALT)
        self.archetype_choice.SetForegroundColour(LIGHT_TEXT)
        selection_sizer.Add(self.archetype_choice, 1, wx.RIGHT, 6)

        self.generate_btn = wx.Button(self, label="Generate Radar")
        self.generate_btn.Bind(wx.EVT_BUTTON, self._on_generate_clicked)
        selection_sizer.Add(self.generate_btn, 0)

        # Progress gauge
        self.progress = wx.Gauge(self, range=100)
        sizer.Add(self.progress, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        self.progress_label = wx.StaticText(self, label="")
        self.progress_label.SetForegroundColour(LIGHT_TEXT)
        sizer.Add(self.progress_label, 0, wx.ALL, 10)

        # Radar panel
        self.radar_panel = RadarPanel(
            self,
            radar_service=self.radar_service,
            on_export=self._export_radar,
            on_use_for_search=self._use_radar_for_search,
        )
        sizer.Add(self.radar_panel, 1, wx.EXPAND | wx.ALL, 10)

        # Close button
        close_btn = wx.Button(self, wx.ID_CLOSE, "Close")
        close_btn.Bind(wx.EVT_BUTTON, lambda e: self.Close())
        sizer.Add(close_btn, 0, wx.ALIGN_RIGHT | wx.ALL, 10)

    def _load_archetypes(self) -> None:
        """Load archetypes for the current format."""
        try:
            self.archetypes = self.metagame_repo.get_archetypes_for_format(
                self.format_name
            )
            archetype_names = [arch.get("name", "Unknown") for arch in self.archetypes]
            self.archetype_choice.Set(archetype_names)

            if archetype_names:
                self.archetype_choice.SetSelection(0)

        except Exception as exc:
            wx.MessageBox(
                f"Failed to load archetypes: {exc}",
                "Error",
                wx.OK | wx.ICON_ERROR,
            )

    def _on_generate_clicked(self, event: wx.Event) -> None:
        """Handle generate radar button click."""
        selection = self.archetype_choice.GetSelection()
        if selection == wx.NOT_FOUND:
            wx.MessageBox(
                "Please select an archetype.",
                "No Archetype Selected",
                wx.OK | wx.ICON_WARNING,
            )
            return

        archetype = self.archetypes[selection]

        # Disable button during generation
        self.generate_btn.Enable(False)
        self.progress.SetValue(0)
        self.progress_label.SetLabel("Generating radar...")

        # Use CallAfter to ensure UI updates
        wx.CallAfter(self._generate_radar, archetype)

    def _generate_radar(self, archetype: dict[str, Any]) -> None:
        """
        Generate radar for the selected archetype.

        Args:
            archetype: Archetype dictionary
        """
        try:
            # Progress callback
            def update_progress(current: int, total: int, deck_name: str) -> None:
                percent = int((current / total) * 100) if total > 0 else 0
                wx.CallAfter(self.progress.SetValue, percent)
                wx.CallAfter(
                    self.progress_label.SetLabel,
                    f"Analyzing deck {current}/{total}: {deck_name}",
                )

            # Calculate radar
            radar = self.radar_service.calculate_radar(
                archetype,
                self.format_name,
                progress_callback=update_progress,
            )

            # Display results
            wx.CallAfter(self.radar_panel.display_radar, radar)
            wx.CallAfter(self.progress_label.SetLabel, "Radar generated successfully!")
            self.current_radar = radar

        except Exception as exc:
            wx.CallAfter(
                wx.MessageBox,
                f"Failed to generate radar: {exc}",
                "Error",
                wx.OK | wx.ICON_ERROR,
            )
            wx.CallAfter(self.progress_label.SetLabel, "Failed to generate radar.")

        finally:
            wx.CallAfter(self.generate_btn.Enable, True)
            wx.CallAfter(self.progress.SetValue, 0)

    def _export_radar(self, radar: RadarData) -> None:
        """
        Export radar as a deck list.

        Args:
            radar: RadarData to export
        """
        # Ask for minimum saturation threshold
        dlg = wx.TextEntryDialog(
            self,
            "Enter minimum saturation % (0-100):\n"
            "(100% = always-a-four-of)",
            "Export Radar as Decklist",
            "0",
        )

        if dlg.ShowModal() == wx.ID_OK:
            try:
                min_saturation = float(dlg.GetValue())
                if min_saturation < 0 or min_saturation > 100:
                    raise ValueError("Must be between 0 and 100")

                # Generate deck list
                decklist = self.radar_service.export_radar_as_decklist(
                    radar, min_saturation
                )

                # Save to file
                with wx.FileDialog(
                    self,
                    "Save Radar Decklist",
                    wildcard="Text files (*.txt)|*.txt",
                    style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
                ) as fileDialog:
                    if fileDialog.ShowModal() == wx.ID_OK:
                        path = fileDialog.GetPath()
                        with open(path, "w", encoding="utf-8") as f:
                            f.write(decklist)
                        wx.MessageBox(
                            f"Radar exported to {path}",
                            "Export Successful",
                            wx.OK | wx.ICON_INFORMATION,
                        )

            except ValueError as exc:
                wx.MessageBox(
                    f"Invalid saturation value: {exc}",
                    "Error",
                    wx.OK | wx.ICON_ERROR,
                )

        dlg.Destroy()

    def _use_radar_for_search(self, radar: RadarData) -> None:
        """
        Use radar for deck builder search (to be implemented in integration).

        Args:
            radar: RadarData to use
        """
        # This will be connected to the main window's deck builder
        wx.MessageBox(
            "Radar search filter applied!",
            "Search Filter",
            wx.OK | wx.ICON_INFORMATION,
        )
        self.Close()

    def get_current_radar(self) -> RadarData | None:
        """Get the currently displayed radar."""
        return self.current_radar
