"""Card inspector panel - displays card details, images, and printings."""

from __future__ import annotations

from typing import Any, Callable

import wx
from loguru import logger

from utils.card_images import BULK_DATA_CACHE, BulkImageDownloader, ensure_printing_index_cache, get_cache, get_card_image
from widgets.card_image_display import CardImageDisplay


class CardInspectorPanel(wx.Panel):
    """Panel for inspecting card details with image and printing navigation."""

    def __init__(
        self,
        parent: wx.Window,
        mana_icon_factory: Any,
        bg_color: wx.Colour,
        panel_color: wx.Colour,
        text_color: wx.Colour,
        subdued_color: wx.Colour,
    ):
        """Initialize card inspector panel.

        Args:
            parent: Parent window
            mana_icon_factory: Factory for rendering mana symbols
            bg_color: Background color
            panel_color: Panel background color
            text_color: Primary text color
            subdued_color: Subdued text color
        """
        super().__init__(parent)
        self.SetBackgroundColour(panel_color)

        self.mana_icons = mana_icon_factory
        self.bg_color = bg_color
        self.panel_color = panel_color
        self.text_color = text_color
        self.subdued_color = subdued_color

        # State
        self.current_card_name: str | None = None
        self.printings: list[dict[str, Any]] = []
        self.current_printing_index: int = 0
        self.bulk_data_by_name: dict[str, list[dict[str, Any]]] | None = None
        self.image_cache = get_cache()
        self.image_downloader: BulkImageDownloader | None = None
        self.printing_index_loading: bool = False

        self._build_ui()

    def _build_ui(self) -> None:
        """Build the UI components."""
        main_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.SetSizer(main_sizer)

        # Image column
        image_column_panel = wx.Panel(self)
        image_column_panel.SetBackgroundColour(self.panel_color)
        image_column = wx.BoxSizer(wx.VERTICAL)
        image_column_panel.SetSizer(image_column)
        main_sizer.Add(image_column_panel, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 12)

        # Card image display
        self.card_image_display = CardImageDisplay(image_column_panel, width=260, height=360)
        image_column.Add(self.card_image_display, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.ALL, 4)

        # Navigation panel
        self.nav_panel = wx.Panel(image_column_panel)
        self.nav_panel.SetBackgroundColour(self.panel_color)
        nav_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.nav_panel.SetSizer(nav_sizer)

        try:
            nav_btn_size = self.FromDIP(wx.Size(38, 30))
        except AttributeError:
            nav_btn_size = wx.Size(38, 30)

        self.prev_btn = wx.Button(self.nav_panel, label="◀", size=nav_btn_size)
        self.prev_btn.Bind(wx.EVT_BUTTON, lambda _: self._on_prev_printing())
        nav_sizer.Add(self.prev_btn, 0, wx.RIGHT, 4)

        self.printing_label = wx.StaticText(self.nav_panel, label="")
        self.printing_label.SetForegroundColour(self.subdued_color)
        nav_sizer.Add(self.printing_label, 1, wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_CENTER)

        self.next_btn = wx.Button(self.nav_panel, label="▶", size=nav_btn_size)
        self.next_btn.Bind(wx.EVT_BUTTON, lambda _: self._on_next_printing())
        nav_sizer.Add(self.next_btn, 0, wx.LEFT, 4)

        image_column.Add(self.nav_panel, 0, wx.EXPAND | wx.TOP, 6)
        self.nav_panel.Hide()

        # Details column
        details_panel = wx.Panel(self)
        details_panel.SetBackgroundColour(self.panel_color)
        details_sizer = wx.BoxSizer(wx.VERTICAL)
        details_panel.SetSizer(details_sizer)
        main_sizer.Add(details_panel, 1, wx.EXPAND)

        # Card name
        self.name_label = wx.StaticText(details_panel, label="Select a card to inspect.")
        name_font = self.name_label.GetFont()
        name_font.SetPointSize(name_font.GetPointSize() + 2)
        name_font.MakeBold()
        self.name_label.SetFont(name_font)
        self.name_label.SetForegroundColour(self.text_color)
        details_sizer.Add(self.name_label, 0, wx.BOTTOM, 4)

        # Mana cost container
        self.cost_container = wx.Panel(details_panel)
        self.cost_container.SetBackgroundColour(self.panel_color)
        self.cost_container.SetMinSize((-1, 36))
        self.cost_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.cost_container.SetSizer(self.cost_sizer)
        details_sizer.Add(self.cost_container, 0, wx.EXPAND | wx.BOTTOM, 4)

        # Type line
        self.type_label = wx.StaticText(details_panel, label="")
        self.type_label.SetForegroundColour(self.subdued_color)
        details_sizer.Add(self.type_label, 0, wx.BOTTOM, 4)

        # Stats (P/T or loyalty)
        self.stats_label = wx.StaticText(details_panel, label="")
        self.stats_label.SetForegroundColour(self.text_color)
        details_sizer.Add(self.stats_label, 0, wx.BOTTOM, 4)

        # Oracle text
        self.text_ctrl = wx.TextCtrl(
            details_panel,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_WORDWRAP | wx.NO_BORDER,
        )
        self.text_ctrl.SetBackgroundColour(self.panel_color)
        self.text_ctrl.SetForegroundColour(self.text_color)
        self.text_ctrl.SetMinSize((-1, 120))
        details_sizer.Add(self.text_ctrl, 1, wx.EXPAND | wx.TOP, 4)

        self.reset()

    def reset(self) -> None:
        """Reset inspector to default state."""
        self.current_card_name = None
        self.printings = []
        self.current_printing_index = 0

        self.name_label.SetLabel("Select a card to inspect.")
        self.type_label.SetLabel("")
        self.stats_label.SetLabel("")
        self.text_ctrl.SetValue("")

        # Clear mana cost
        self.cost_sizer.Clear(True)
        self.cost_container.Layout()

        self.card_image_display.clear()
        self.nav_panel.Hide()
        self.Layout()

    def update_card(
        self,
        card: dict[str, Any],
        get_metadata_func: Callable[[str], dict[str, Any] | None],
    ) -> None:
        """Update inspector with card details.

        Args:
            card: Card dictionary with name and quantity
            get_metadata_func: Function to get full card metadata
        """
        name = card.get("name", "")
        if not name:
            self.reset()
            return

        metadata = get_metadata_func(name)
        if not metadata:
            self.reset()
            return

        # Update basic info
        self.name_label.SetLabel(name)
        self.type_label.SetLabel(metadata.get("type_line", ""))

        # Stats
        stats_parts: list[str] = []
        if "power" in metadata and "toughness" in metadata:
            stats_parts.append(f"{metadata['power']}/{metadata['toughness']}")
        if "loyalty" in metadata:
            stats_parts.append(f"Loyalty: {metadata['loyalty']}")
        self.stats_label.SetLabel(" • ".join(stats_parts) if stats_parts else "")

        # Oracle text
        oracle_text = metadata.get("oracle_text", "")
        self.text_ctrl.SetValue(oracle_text)

        # Mana cost
        self._render_mana_cost(metadata.get("mana_cost", ""))

        # Load image and printings
        self.current_card_name = name
        self._load_card_image_and_printings(name)

        self.Layout()

    def _render_mana_cost(self, mana_cost: str) -> None:
        """Render mana cost symbols.

        Args:
            mana_cost: Mana cost string
        """
        self.cost_sizer.Clear(True)
        if mana_cost:
            cost_panel = self.mana_icons.render(self.cost_container, mana_cost)
            self.cost_sizer.Add(cost_panel, 0, wx.ALIGN_CENTER_VERTICAL)
        self.cost_container.Layout()

    def _load_card_image_and_printings(self, card_name: str) -> None:
        """Load card image and available printings.

        Args:
            card_name: Card name
        """
        # Load printings from bulk data
        if self.bulk_data_by_name is None:
            self._ensure_bulk_data_loaded()
            if self.bulk_data_by_name is None:
                self._load_single_card_image(card_name)
                return

        self.printings = self.bulk_data_by_name.get(card_name, [])

        if not self.printings:
            logger.debug(f"No printings found for {card_name}")
            self._load_single_card_image(card_name)
            return

        # Start with first printing
        self.current_printing_index = 0
        self._load_current_printing_image()

        # Show navigation if multiple printings
        if len(self.printings) > 1:
            self.printing_label.SetLabel(f"1 / {len(self.printings)}")
            self.nav_panel.Show()
        else:
            self.nav_panel.Hide()

        self.Layout()

    def _ensure_bulk_data_loaded(self) -> None:
        """Ensure bulk card data is loaded."""
        if self.bulk_data_by_name is not None or self.printing_index_loading:
            return

        self.printing_index_loading = True

        def on_success():
            if BULK_DATA_CACHE.exists():
                self.bulk_data_by_name = ensure_printing_index_cache()
                logger.info("Loaded bulk data for printings")
            self.printing_index_loading = False

        def on_error(exc: Exception):
            logger.warning(f"Failed to load bulk data: {exc}")
            self.printing_index_loading = False

        # Trigger async load (would need threading in real implementation)
        try:
            if BULK_DATA_CACHE.exists():
                self.bulk_data_by_name = ensure_printing_index_cache()
        except Exception as exc:
            logger.warning(f"Failed to load bulk data: {exc}")

    def _load_single_card_image(self, card_name: str) -> None:
        """Load image for card without printing data.

        Args:
            card_name: Card name
        """
        try:
            image_path = get_card_image(card_name, self.image_cache)
            if image_path and image_path.exists():
                self.card_image_display.load_image(image_path)
            else:
                self.card_image_display.clear()
        except Exception as exc:
            logger.warning(f"Failed to load image for {card_name}: {exc}")
            self.card_image_display.clear()

    def _load_current_printing_image(self) -> None:
        """Load image for current printing."""
        if not self.printings or self.current_printing_index >= len(self.printings):
            return

        printing = self.printings[self.current_printing_index]
        scryfallid = printing.get("identifiers", {}).get("scryfallId", "")

        if not scryfallid:
            logger.warning("No scryfall ID for printing")
            self.card_image_display.clear()
            return

        try:
            image_path = self.image_cache.get(scryfallid)
            if image_path and image_path.exists():
                self.card_image_display.load_image(image_path)
            else:
                self.card_image_display.clear()
        except Exception as exc:
            logger.warning(f"Failed to load printing image: {exc}")
            self.card_image_display.clear()

    def _on_prev_printing(self) -> None:
        """Navigate to previous printing."""
        if not self.printings:
            return

        self.current_printing_index = (self.current_printing_index - 1) % len(self.printings)
        self.printing_label.SetLabel(
            f"{self.current_printing_index + 1} / {len(self.printings)}"
        )
        self._load_current_printing_image()

    def _on_next_printing(self) -> None:
        """Navigate to next printing."""
        if not self.printings:
            return

        self.current_printing_index = (self.current_printing_index + 1) % len(self.printings)
        self.printing_label.SetLabel(
            f"{self.current_printing_index + 1} / {len(self.printings)}"
        )
        self._load_current_printing_image()
