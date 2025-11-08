import json
import threading
import time
from collections import Counter
import re
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import wx
import wx.dataview as dv
from loguru import logger

from navigators.mtggoldfish import get_archetypes, get_archetype_decks, download_deck
from utils.card_data import CardDataManager
from utils.card_images import (
    get_card_image,
    get_cache,
    BulkImageDownloader,
    IMAGE_CACHE_DIR,
    BULK_DATA_CACHE,
    ensure_printing_index_cache,
)
from utils.deck import add_dicts, analyze_deck, deck_to_dictionary
from utils.dbq import save_deck_to_db
from utils.paths import (
    CACHE_DIR,
    CONFIG_FILE,
    CURR_DECK_FILE,
    DECK_SELECTOR_SETTINGS_FILE,
    DECKS_DIR,
)
from widgets.card_image_display import CardImageDisplay
from widgets.identify_opponent_wx import MTGOpponentDeckSpyWx
from widgets.match_history_wx import MatchHistoryFrame
from widgets.timer_alert_wx import TimerAlertFrame

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

LEGACY_CONFIG_FILE = Path("config.json")
LEGACY_CURR_DECK_CACHE = Path("cache") / "curr_deck.txt"
LEGACY_CURR_DECK_ROOT = Path("curr_deck.txt")

NOTES_STORE = CACHE_DIR / "deck_notes_wx.json"
OUTBOARD_STORE = CACHE_DIR / "deck_outboard_wx.json"
GUIDE_STORE = CACHE_DIR / "deck_sbguides_wx.json"
MANA_RENDER_LOG = Path("cache") / "mana_render.log"
CARD_INSPECTOR_LOG = CACHE_DIR / "card_inspector_debug.log"


def _log_mana_event(*parts: str) -> None:  # pragma: no cover - debug helper
    try:
        MANA_RENDER_LOG.parent.mkdir(parents=True, exist_ok=True)
        with MANA_RENDER_LOG.open("a", encoding="utf-8") as fh:
            fh.write(" | ".join(parts) + "\n")
    except OSError:
        pass


def _log_card_inspector(*parts: str) -> None:  # pragma: no cover - debug helper
    try:
        CARD_INSPECTOR_LOG.parent.mkdir(parents=True, exist_ok=True)
        with CARD_INSPECTOR_LOG.open("a", encoding="utf-8") as fh:
            stamp = time.strftime("%Y-%m-%d %H:%M:%S")
            fh.write(f"{stamp} | " + " | ".join(parts) + "\n")
    except OSError:
        pass

CONFIG: Dict[str, Any] = {}
if CONFIG_FILE.exists():
    try:
        with CONFIG_FILE.open("r", encoding="utf-8") as _cfg_file:
            CONFIG = json.load(_cfg_file)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive logging
        logger.warning(f"Invalid {CONFIG_FILE} ({exc}); using default deck save path")
        CONFIG = {}
elif LEGACY_CONFIG_FILE.exists():
    try:
        with LEGACY_CONFIG_FILE.open("r", encoding="utf-8") as _cfg_file:
            CONFIG = json.load(_cfg_file)
        logger.warning("Loaded legacy config.json from project root; migrating to config/ directory")
        try:
            with CONFIG_FILE.open("w", encoding="utf-8") as fh:
                json.dump(CONFIG, fh, indent=4)
        except OSError as exc:
            logger.warning(f"Failed to write migrated config.json: {exc}")
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive logging
        logger.warning(f"Invalid legacy config.json ({exc}); using default deck save path")
        CONFIG = {}
else:
    logger.debug(f"{CONFIG_FILE} not found; using default deck save path")

default_deck_dir = Path(CONFIG.get("deck_selector_save_path") or DECKS_DIR)
DECK_SAVE_DIR = default_deck_dir.expanduser()
try:
    DECK_SAVE_DIR.mkdir(parents=True, exist_ok=True)
except OSError as exc:  # pragma: no cover - defensive logging
    logger.warning(f"Unable to create deck save directory '{DECK_SAVE_DIR}': {exc}")
CONFIG.setdefault("deck_selector_save_path", str(DECK_SAVE_DIR))

DARK_BG = wx.Colour(20, 22, 27)
DARK_PANEL = wx.Colour(34, 39, 46)
DARK_ALT = wx.Colour(40, 46, 54)
DARK_ACCENT = wx.Colour(59, 130, 246)
LIGHT_TEXT = wx.Colour(236, 236, 236)
SUBDUED_TEXT = wx.Colour(185, 191, 202)

ZONE_TITLES = {
    "main": "Mainboard",
    "side": "Sideboard",
    "out": "Outboard",
}

FULL_MANA_SYMBOLS: List[str] = (
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


def format_deck_name(deck: Dict[str, Any]) -> str:
    """Compose a compact deck line for list display."""
    date = deck.get("date", "")
    player = deck.get("player", "")
    event = deck.get("event", "")
    result = deck.get("result", "")
    return f"{date} | {player} — {event} [{result}]".strip()


class _Worker:
    """Helper for dispatching background work and returning results on the UI thread."""

    def __init__(
        self,
        func: Callable,
        *args,
        on_success: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
    ) -> None:
        self.func = func
        self.args = args
        self.on_success = on_success
        self.on_error = on_error

    def start(self) -> None:
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self) -> None:
        try:
            result = self.func(*self.args)
        except Exception as exc:  # pragma: no cover - UI side effects
            logger.exception(f"Background task failed: {exc}")
            if self.on_error:
                wx.CallAfter(self.on_error, exc)
            return
        if self.on_success:
            wx.CallAfter(self.on_success, result)


class ManaIconFactory:
    FALLBACK_COLORS = {
        "w": (253, 251, 206),
        "u": (188, 218, 247),
        "b": (128, 115, 128),
        "r": (241, 155, 121),
        "g": (159, 203, 166),
        "c": (208, 198, 187),
        "multicolor": (246, 223, 138),
    }
    _FONT_LOADED = False
    _FONT_NAME = "Mana"

    def __init__(self) -> None:
        self._cache: Dict[str, wx.Bitmap] = {}
        self._glyph_map, self._color_map = self._load_css_resources()
        self._ensure_font_loaded()

    def render(self, parent: wx.Window, mana_cost: str) -> wx.Window:
        panel = wx.Panel(parent)
        panel.SetBackgroundColour(parent.GetBackgroundColour())
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        panel.SetSizer(sizer)
        tokens = self._tokenize(mana_cost)
        if not tokens:
            label = wx.StaticText(panel, label="—")
            label.SetForegroundColour(SUBDUED_TEXT)
            sizer.Add(label)
            return panel
        for idx, token in enumerate(tokens):
            bmp = self._get_bitmap(token)
            icon = wx.StaticBitmap(panel, bitmap=bmp)
            margin = 1 if idx < len(tokens) - 1 else 0
            sizer.Add(icon, 0, wx.RIGHT, margin)
        panel.SetMinSize((max(28, len(tokens) * 28), 32))
        return panel

    def bitmap_for_symbol(self, symbol: str) -> wx.Bitmap:
        token = symbol.strip()
        if token.startswith("{") and token.endswith("}"):
            token = token[1:-1]
        return self._get_bitmap(token or "")

    def _tokenize(self, cost: str) -> List[str]:
        tokens: List[str] = []
        if not cost:
            return tokens
        parts = cost.replace("}", "").split("{")
        for part in parts:
            token = part.strip()
            if not token:
                continue
            tokens.append(token)
        return tokens

    def _get_bitmap(self, symbol: str) -> wx.Bitmap:
        if symbol in self._cache:
            return self._cache[symbol]
        key = self._normalize_symbol(symbol)
        components = self._hybrid_components(key)
        second_color: Optional[tuple[int, int, int]] = None
        glyph = self._glyph_map.get(key or "") if not components else ""
        _log_mana_event("_get_bitmap", f"symbol={symbol}", f"key={key}", f"glyph={'yes' if glyph else 'no'}", f"components={components}")
        scale = 3
        size = 26 * scale
        bmp = wx.Bitmap(size, size)
        dc = wx.MemoryDC(bmp)
        dc.SetBackground(wx.Brush(DARK_ALT))
        dc.Clear()

        cx = cy = size // 2
        radius = (size // 2) - scale
        gctx = wx.GraphicsContext.Create(dc)
        shadow_colour = wx.Colour(0, 0, 0, 80)
        gctx.SetPen(wx.Pen(wx.Colour(0, 0, 0, 0)))
        gctx.SetBrush(wx.Brush(shadow_colour))
        gctx.DrawEllipse(cx - radius + scale, cy - radius + scale, radius * 2, radius * 2)

        text_font = self._build_render_font(scale)
        text_color = wx.Colour(20, 20, 20)
        if components:
            second_color = self._draw_hybrid_circle(gctx, cx, cy, radius, components)
        else:
            fill_color = self._color_for_key(key or "")
            gctx.SetPen(wx.Pen(wx.Colour(25, 25, 25, 140), 2))
            gctx.SetBrush(wx.Brush(wx.Colour(*fill_color)))
            gctx.DrawEllipse(cx - radius, cy - radius, radius * 2, radius * 2)
            glyph_to_draw = glyph or self._glyph_fallback(key)
            if glyph_to_draw:
                gctx.SetFont(text_font, text_color)
                tw, th = gctx.GetTextExtent(glyph_to_draw)
                gctx.DrawText(glyph_to_draw, cx - tw / 2, cy - th / 2)

        dc.SelectObject(wx.NullBitmap)

        if components and second_color:
            bmp = self._apply_hybrid_overlay(bmp, cx, cy, radius, second_color)
            dc = wx.MemoryDC(bmp)
            gctx = wx.GraphicsContext.Create(dc)
            self._draw_hybrid_glyph(gctx, cx, cy, radius, components, text_font, text_color)
            dc.SelectObject(wx.NullBitmap)
        img = bmp.ConvertToImage()
        img = img.Blur(1)
        img = img.Scale(26, 26, wx.IMAGE_QUALITY_HIGH)
        final = wx.Bitmap(img)
        self._cache[symbol] = final
        return final

    def _build_render_font(self, scale: int) -> wx.Font:
        if self._FONT_LOADED:
            return wx.Font(13 * scale, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL, False, self._FONT_NAME)
        font = wx.Font(wx.FontInfo(13 * scale).Family(wx.FONTFAMILY_SWISS))
        font.MakeBold()
        return font

    def _draw_component(
        self,
        gctx: wx.GraphicsContext,
        cx: int,
        cy: int,
        radius: int,
        key: Optional[str],
        font: wx.Font,
        text_color: wx.Colour,
        outline: bool = True,
    ) -> None:
        color = self._color_for_key(key or "")
        pen_color = wx.Colour(25, 25, 25, 160) if outline else wx.Colour(0, 0, 0, 0)
        width = 2 if outline else 0
        gctx.SetPen(wx.Pen(pen_color, width))
        gctx.SetBrush(wx.Brush(wx.Colour(*color)))
        gctx.DrawEllipse(cx - radius, cy - radius, radius * 2, radius * 2)
        glyph = self._glyph_fallback(key)
        if glyph:
            gctx.SetFont(font, text_color)
            tw, th = gctx.GetTextExtent(glyph)
            gctx.DrawText(glyph, cx - tw / 2, cy - th / 2)

    def _draw_hybrid_circle(
        self,
        gctx: wx.GraphicsContext,
        cx: int,
        cy: int,
        radius: int,
        components: List[str],
    ) -> tuple[int, int, int]:
        rect = (cx - radius, cy - radius, radius * 2, radius * 2)
        base = self._color_for_key(components[0])
        second = self._color_for_key(components[1])
        gctx.SetPen(wx.Pen(wx.Colour(25, 25, 25, 200), 2))
        gctx.SetBrush(wx.Brush(wx.Colour(*base)))
        gctx.DrawEllipse(*rect)
        gctx.StrokeLine(cx - radius, cy + radius, cx + radius, cy - radius)
        return second

    def _draw_hybrid_glyph(
        self,
        gctx: wx.GraphicsContext,
        cx: int,
        cy: int,
        radius: int,
        components: List[str],
        font: wx.Font,
        text_color: wx.Colour,
    ) -> None:
        offsets = [(-radius * 0.3, -radius * 0.3), (radius * 0.3, radius * 0.3)]
        glyph_font = self._scaled_font(font, 0.52)
        for idx, component in enumerate(components):
            glyph = self._glyph_fallback(component)
            if not glyph:
                continue
            gctx.SetFont(glyph_font, text_color)
            dx, dy = offsets[idx] if idx < len(offsets) else (0, 0)
            tw, th = gctx.GetTextExtent(glyph)
            gctx.DrawText(glyph, cx - tw / 2 + dx, cy - th / 2 + dy)
        # Restore original font to avoid surprising callers.
        gctx.SetFont(font, text_color)

    def _apply_hybrid_overlay(
        self,
        bmp: wx.Bitmap,
        cx: int,
        cy: int,
        radius: int,
        color: tuple[int, int, int],
    ) -> wx.Bitmap:
        img = bmp.ConvertToImage()
        width, height = img.GetWidth(), img.GetHeight()
        limit = max(1, radius - 1)
        limit_sq = limit * limit
        cr, cg, cb = color
        for x in range(width):
            dx = x - cx
            for y in range(height):
                dy = y - cy
                if dx * dx + dy * dy > limit_sq:
                    continue
                if dx + dy >= 0:
                    img.SetRGB(x, y, cr, cg, cb)
        return wx.Bitmap(img)

    def _scaled_font(self, font: wx.Font, factor: float) -> wx.Font:
        size = max(6, int(font.GetPointSize() * factor))
        try:
            return wx.Font(
                size,
                font.GetFamily(),
                font.GetStyle(),
                font.GetWeight(),
                font.GetUnderlined(),
                font.GetFaceName(),
            )
        except Exception:
            return font

    def _glyph_fallback(self, key: Optional[str]) -> str:
        if not key:
            return ""
        glyph = self._glyph_map.get(key)
        if glyph:
            _log_mana_event("_glyph_fallback", f"key={key}", "source=direct")
            return glyph
        compact = key.replace("/", "")
        glyph = self._glyph_map.get(compact)
        if glyph:
            _log_mana_event("_glyph_fallback", f"key={key}", f"source=compact({compact})")
            return glyph
        if len(key) > 1:
            tail = key[-1]
            glyph = self._glyph_map.get(tail)
            if glyph:
                _log_mana_event("_glyph_fallback", f"key={key}", f"source=tail({tail})")
                return glyph
        fallback = key.upper()
        _log_mana_event("_glyph_fallback", f"key={key}", f"source=default({fallback})")
        return fallback

    def _color_for_key(self, key: Optional[str]) -> tuple[int, int, int]:
        if not key:
            return self.FALLBACK_COLORS["multicolor"]
        if key in self._color_map:
            return self._color_map[key]
        if key.isdigit() or key in {"x", "y", "z"}:
            return self._color_map.get("c", self.FALLBACK_COLORS["c"])
        if "-" in key:
            for part in key.split("-"):
                if part in self._color_map:
                    return self._color_map[part]
        if key[0] in self._color_map:
            return self._color_map[key[0]]
        if len(key) >= 2 and key[0].isdigit() and key[1] in self._color_map:
            return self._color_map[key[1]]
        return self.FALLBACK_COLORS["multicolor"]

    def _normalize_symbol(self, symbol: str) -> Optional[str]:
        token = symbol.strip().lower().replace("{", "").replace("}", "")
        if not token:
            return None
        token = token.replace("½", "half")
        if "/" in token:
            parts = [part for part in token.split("/") if part]
            if all(part.isdigit() for part in parts if part):
                token = "-".join(filter(None, parts))
            else:
                token = "".join(parts)
        aliases = {
            "∞": "infinity",
            "1/2": "1-2",
            "half": "1-2",
            "snow": "s",
        }
        return aliases.get(token, token)

    def _hybrid_components(self, key: Optional[str]) -> Optional[List[str]]:
        if not key or len(key) < 2:
            return None
        base = set("wubrg")
        first, second = key[0], key[1]
        if first in base.union({"c"}) and second in base:
            _log_mana_event("_hybrid_components", f"key={key}", "match=two-color")
            return [first, second]
        if first == "2" and second in base:
            _log_mana_event("_hybrid_components", f"key={key}", "match=two-hybrid")
            return ["c", second]
        _log_mana_event("_hybrid_components", f"key={key}", "match=none")
        return None

    def _ensure_font_loaded(self) -> None:
        if ManaIconFactory._FONT_LOADED:
            return
        font_path = Path(__file__).resolve().parents[1] / "assets" / "mana" / "fonts" / "mana.ttf"
        if not font_path.exists():
            logger.debug("Mana font not found at %s; using fallback glyphs", font_path)
            return
        try:
            wx.Font.AddPrivateFont(str(font_path))
            ManaIconFactory._FONT_LOADED = True
        except Exception as exc:  # pragma: no cover
            logger.debug(f"Unable to load mana font: {exc}")

    def _load_css_resources(self) -> tuple[Dict[str, str], Dict[str, tuple[int, int, int]]]:
        glyphs: Dict[str, str] = {}
        colors: Dict[str, tuple[int, int, int]] = {}
        css_path = Path(__file__).resolve().parents[1] / "assets" / "mana" / "css" / "mana.min.css"
        if not css_path.exists():
            return glyphs, {k: tuple(v) for k, v in self.FALLBACK_COLORS.items()}
        css_text = css_path.read_text(encoding="utf-8")
        color_re = re.compile(r"--ms-mana-([a-z0-9-]+):\s*#([0-9a-fA-F]{6})")
        for match in color_re.finditer(css_text):
            key = match.group(1).lower()
            hex_value = match.group(2)
            colors[key] = tuple(int(hex_value[i : i + 2], 16) for i in (0, 2, 4))
        for block in css_text.split("}"):
            if "content" not in block or "::" not in block:
                continue
            parts = block.split("{", 1)
            if len(parts) != 2:
                continue
            selectors, body = parts
            content_match = re.search(r'content:\s*"([^"]+)"', body)
            if not content_match:
                continue
            glyph_char = content_match.group(1)
            for raw_selector in selectors.split(","):
                raw_selector = raw_selector.strip()
                if not raw_selector.startswith(".ms-"):
                    continue
                cls = raw_selector.split("::", 1)[0].replace(".ms-", "").lower()
                if cls:
                    glyphs[cls] = glyph_char
        for base, rgb in self.FALLBACK_COLORS.items():
            colors.setdefault(base, rgb)
        return glyphs, colors
class CardCardPanel(wx.Panel):
    def __init__(
        self,
        parent: wx.Window,
        zone: str,
        card: Dict[str, Any],
        icon_factory: ManaIconFactory,
        get_metadata: Callable[[str], Optional[Dict[str, Any]]],
        owned_status: Callable[[str, int], tuple[str, wx.Colour]],
        on_delta: Callable[[str, str, int], None],
        on_remove: Callable[[str, str], None],
        on_select: Callable[[str, Dict[str, Any], "CardCardPanel"], None],
    ) -> None:
        super().__init__(parent)
        self.zone = zone
        self.card = card
        self._get_metadata = get_metadata
        self._owned_status = owned_status
        self._on_delta = on_delta
        self._on_remove = on_remove
        self._on_select = on_select
        self._active = False

        self.SetBackgroundColour(DARK_ALT)
        row = wx.BoxSizer(wx.HORIZONTAL)
        self.SetSizer(row)
        self.SetMinSize((-1, 34))

        base_font = wx.Font(11, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)

        self.qty_label = wx.StaticText(self, label=str(card["qty"]))
        self.qty_label.SetForegroundColour(LIGHT_TEXT)
        self.qty_label.SetFont(base_font)
        row.Add(self.qty_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)

        meta = get_metadata(card["name"]) or {}
        mana_cost = meta.get("mana_cost", "")

        owned_text, owned_colour = owned_status(card["name"], card["qty"])
        self.name_label = wx.StaticText(self, label=card["name"], style=wx.ST_NO_AUTORESIZE)
        self.name_label.SetForegroundColour(owned_colour)
        self.name_label.SetFont(base_font)
        self.name_label.Wrap(110)
        row.Add(self.name_label, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)

        mana_panel = icon_factory.render(self, mana_cost)
        row.Add(mana_panel, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)

        self.button_panel = wx.Panel(self)
        self.button_panel.SetBackgroundColour(DARK_ALT)
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.button_panel.SetSizer(btn_sizer)
        add_btn = wx.Button(self.button_panel, label="+", size=(24, 24))
        add_btn.Bind(wx.EVT_BUTTON, lambda _evt: self._on_delta(zone, card["name"], 1))
        btn_sizer.Add(add_btn, 0)
        sub_btn = wx.Button(self.button_panel, label="−", size=(24, 24))
        sub_btn.Bind(wx.EVT_BUTTON, lambda _evt: self._on_delta(zone, card["name"], -1))
        btn_sizer.Add(sub_btn, 0, wx.LEFT, 2)
        rem_btn = wx.Button(self.button_panel, label="×", size=(24, 24))
        rem_btn.Bind(wx.EVT_BUTTON, lambda _evt: self._on_remove(zone, card["name"]))
        btn_sizer.Add(rem_btn, 0, wx.LEFT, 2)
        row.Add(self.button_panel, 0, wx.ALIGN_CENTER_VERTICAL)
        self.button_panel.Hide()

        self._bind_click_targets([self, self.qty_label, self.name_label, mana_panel])

    def update_quantity(self, qty: int, owned_text: str, owned_colour: wx.Colour) -> None:
        self.qty_label.SetLabel(str(qty))
        self.name_label.SetForegroundColour(owned_colour)
        self.Layout()

    def set_active(self, active: bool) -> None:
        if self._active == active:
            return
        self._active = active
        self.button_panel.Show(active)
        self.button_panel.Enable(active)
        self.button_panel.SetBackgroundColour(DARK_ACCENT if active else DARK_ALT)
        self.SetBackgroundColour(DARK_ACCENT if active else DARK_ALT)
        self.Refresh()
        self.Layout()

    def _bind_click_targets(self, targets: List[wx.Window]) -> None:
        for target in targets:
            target.Bind(wx.EVT_LEFT_DOWN, self._handle_click)
            for child in target.GetChildren():
                child.Bind(wx.EVT_LEFT_DOWN, self._handle_click)

    def _handle_click(self, _event: wx.MouseEvent) -> None:
        self._on_select(self.zone, self.card, self)


class CardTablePanel(wx.Panel):
    def __init__(
        self,
        parent: wx.Window,
        zone: str,
        icon_factory: ManaIconFactory,
        get_metadata: Callable[[str], Optional[Dict[str, Any]]],
        owned_status: Callable[[str, int], tuple[str, wx.Colour]],
        on_delta: Callable[[str, str, int], None],
        on_remove: Callable[[str, str], None],
        on_add: Callable[[str], None],
        on_select: Callable[[str, Optional[Dict[str, Any]]], None],
    ) -> None:
        super().__init__(parent)
        self.zone = zone
        self.icon_factory = icon_factory
        self._get_metadata = get_metadata
        self._owned_status = owned_status
        self._on_delta = on_delta
        self._on_remove = on_remove
        self._on_add = on_add
        self._on_select = on_select
        self.cards: List[Dict[str, Any]] = []
        self.card_widgets: List[CardCardPanel] = []
        self.active_panel: Optional[CardCardPanel] = None
        self.selected_name: Optional[str] = None

        self.SetBackgroundColour(DARK_PANEL)
        outer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(outer)

        header = wx.BoxSizer(wx.HORIZONTAL)
        self.count_label = wx.StaticText(self, label="0 cards")
        self.count_label.SetForegroundColour(SUBDUED_TEXT)
        header.Add(self.count_label, 0, wx.ALIGN_CENTER_VERTICAL)
        header.AddStretchSpacer(1)
        add_btn = wx.Button(self, label="Add Card")
        add_btn.Bind(wx.EVT_BUTTON, lambda _evt: self._on_add(self.zone))
        header.Add(add_btn, 0)
        outer.Add(header, 0, wx.EXPAND | wx.BOTTOM, 4)

        self.scroller = wx.ScrolledWindow(self, style=wx.VSCROLL)
        self.scroller.SetBackgroundColour(DARK_PANEL)
        self.scroller.SetScrollRate(5, 5)
        self.grid_sizer = wx.GridSizer(0, 4, 8, 8)
        self.scroller.SetSizer(self.grid_sizer)
        outer.Add(self.scroller, 1, wx.EXPAND)

    def set_cards(self, cards: List[Dict[str, Any]]) -> None:
        self.cards = cards
        self._rebuild_grid()

    def _rebuild_grid(self) -> None:
        self.grid_sizer.Clear(delete_windows=True)
        self.card_widgets = []
        self.active_panel = None
        total = sum(card["qty"] for card in self.cards)
        self.count_label.SetLabel(f"{total} card{'s' if total != 1 else ''}")
        for card in self.cards:
            cell = CardCardPanel(
                self.scroller,
                self.zone,
                card,
                self.icon_factory,
                self._get_metadata,
                self._owned_status,
                self._on_delta,
                self._on_remove,
                self._handle_card_click,
            )
            self.grid_sizer.Add(cell, 0, wx.EXPAND)
            self.card_widgets.append(cell)
        remainder = len(self.cards) % 4
        if remainder:
            for _ in range(4 - remainder):
                spacer = wx.Panel(self.scroller)
                spacer.SetBackgroundColour(DARK_PANEL)
                self.grid_sizer.Add(spacer, 0, wx.EXPAND)
        self.grid_sizer.Layout()
        self.scroller.Layout()
        self.scroller.FitInside()
        self._restore_selection()

    def _handle_card_click(self, zone: str, card: Dict[str, Any], panel: CardCardPanel) -> None:
        if self.active_panel is panel:
            return
        if self.active_panel:
            self.active_panel.set_active(False)
        self.active_panel = panel
        self.selected_name = card["name"]
        panel.set_active(True)
        self._notify_selection(card)

    def _restore_selection(self) -> None:
        if not self.selected_name:
            self._notify_selection(None)
            return
        for widget in self.card_widgets:
            if widget.card["name"].lower() == self.selected_name.lower():
                self.active_panel = widget
                widget.set_active(True)
                self._notify_selection(widget.card)
                return
        previously_had_selection = self.selected_name is not None
        self.selected_name = None
        if previously_had_selection:
            self._notify_selection(None)

    def clear_selection(self) -> None:
        if self.active_panel:
            self.active_panel.set_active(False)
        self.active_panel = None
        self.selected_name = None
        self._notify_selection(None)

    def collapse_active(self) -> None:
        if self.active_panel:
            self.active_panel.set_active(False)
        self.active_panel = None
        self.selected_name = None

    def _notify_selection(self, card: Optional[Dict[str, Any]]) -> None:
        if self._on_select:
            self._on_select(self.zone, card)


class GuideEntryDialog(wx.Dialog):
    def __init__(self, parent: wx.Window, archetype_names: List[str], data: Optional[Dict[str, str]] = None) -> None:
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
            existing = {self.archetype_ctrl.GetString(i) for i in range(self.archetype_ctrl.GetCount())}
            if data["archetype"] not in existing:
                self.archetype_ctrl.Append(data["archetype"])
            self.archetype_ctrl.SetValue(data["archetype"])
        panel_sizer.Add(self.archetype_ctrl, 0, wx.EXPAND | wx.ALL, 4)

        self.cards_in_ctrl = wx.TextCtrl(panel, value=(data or {}).get("cards_in", ""), style=wx.TE_MULTILINE)
        self.cards_in_ctrl.SetBackgroundColour(DARK_ALT)
        self.cards_in_ctrl.SetForegroundColour(LIGHT_TEXT)
        self.cards_in_ctrl.SetHint("Cards to bring in")
        panel_sizer.Add(self.cards_in_ctrl, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 4)

        self.cards_out_ctrl = wx.TextCtrl(panel, value=(data or {}).get("cards_out", ""), style=wx.TE_MULTILINE)
        self.cards_out_ctrl.SetBackgroundColour(DARK_ALT)
        self.cards_out_ctrl.SetForegroundColour(LIGHT_TEXT)
        self.cards_out_ctrl.SetHint("Cards to take out")
        panel_sizer.Add(self.cards_out_ctrl, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 4)

        self.notes_ctrl = wx.TextCtrl(panel, value=(data or {}).get("notes", ""), style=wx.TE_MULTILINE)
        self.notes_ctrl.SetBackgroundColour(DARK_ALT)
        self.notes_ctrl.SetForegroundColour(LIGHT_TEXT)
        self.notes_ctrl.SetHint("Notes")
        panel_sizer.Add(self.notes_ctrl, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 4)

        button_sizer = self.CreateSeparatedButtonSizer(wx.OK | wx.CANCEL)
        if button_sizer:
            main_sizer.Add(button_sizer, 0, wx.EXPAND | wx.ALL, 8)

    def get_data(self) -> Dict[str, str]:
        return {
            "archetype": self.archetype_ctrl.GetValue().strip(),
            "cards_in": self.cards_in_ctrl.GetValue().strip(),
            "cards_out": self.cards_out_ctrl.GetValue().strip(),
            "notes": self.notes_ctrl.GetValue().strip(),
        }


class ManaKeyboardFrame(wx.Frame):
    def __init__(
        self,
        parent: wx.Window,
        create_button: Callable[[wx.Window, str, Callable[[str], None]], wx.Button],
        on_symbol: Callable[[str], None],
    ) -> None:
        super().__init__(
            parent,
            title="Mana Keyboard",
            size=(620, 330),
            style=wx.CAPTION | wx.CLOSE_BOX | wx.FRAME_TOOL_WINDOW | wx.STAY_ON_TOP,
        )
        panel = wx.Panel(self)
        panel.SetBackgroundColour(DARK_BG)
        root = wx.BoxSizer(wx.VERTICAL)
        panel.SetSizer(root)

        info = wx.StaticText(panel, label="Click a symbol to type it anywhere")
        info.SetForegroundColour(LIGHT_TEXT)
        root.Add(info, 0, wx.ALIGN_CENTER | wx.ALL, 8)

        wrap = wx.WrapSizer(wx.HORIZONTAL)
        for token in FULL_MANA_SYMBOLS:
            btn = create_button(panel, token, on_symbol)
            wrap.Add(btn, 0, wx.ALL, 4)
        root.Add(wrap, 1, wx.ALIGN_CENTER_HORIZONTAL | wx.ALL, 10)
        self.CentreOnParent()


class MTGDeckSelectionFrame(wx.Frame):
    """wxPython-based metagame research + deck builder UI."""

    def __init__(self, parent: Optional[wx.Window] = None):
        super().__init__(parent, title="MTGO Deck Research & Builder", size=(1380, 860))

        self.settings = self._load_window_settings()
        self.current_format = self.settings.get("format", "Modern")
        if self.current_format not in FORMAT_OPTIONS:
            self.current_format = "Modern"

        self.archetypes: List[Dict[str, Any]] = []
        self.filtered_archetypes: List[Dict[str, Any]] = []
        self.decks: List[Dict[str, Any]] = []
        self.current_deck: Optional[Dict[str, Any]] = None
        self.current_deck_text: str = ""
        self.zone_cards: Dict[str, List[Dict[str, Any]]] = {"main": [], "side": [], "out": []}
        self.collection_inventory: Dict[str, int] = {}
        self.collection_path: Optional[Path] = None
        self.card_manager: Optional[CardDataManager] = None
        self.card_data_loading = False
        self.card_data_ready = False

        self.deck_notes_store = self._load_store(NOTES_STORE)
        self.outboard_store = self._load_store(OUTBOARD_STORE)
        self.guide_store = self._load_store(GUIDE_STORE)

        self.sideboard_guide_entries: List[Dict[str, str]] = []
        self.sideboard_exclusions: List[str] = []
        self.active_inspector_zone: Optional[str] = None
        self.left_mode = "builder" if self.settings.get("left_mode") == "builder" else "research"
        self.builder_results_cache: List[Dict[str, Any]] = []
        self.builder_inputs: Dict[str, wx.TextCtrl] = {}
        self.builder_results_ctrl: Optional[wx.ListCtrl] = None
        self.builder_status_label: Optional[wx.StaticText] = None
        self.builder_mana_exact_cb: Optional[wx.CheckBox] = None
        self.builder_mv_comparator: Optional[wx.Choice] = None
        self.builder_mv_value: Optional[wx.TextCtrl] = None
        self.builder_format_checks: List[wx.CheckBox] = []
        self.builder_color_checks: Dict[str, wx.CheckBox] = {}
        self.builder_color_mode_choice: Optional[wx.Choice] = None
        self.left_stack: Optional[wx.Simplebook] = None
        self.research_panel: Optional[wx.Panel] = None
        self.builder_panel: Optional[wx.Panel] = None

        self.deck_buffer: Dict[str, float] = {}
        self.decks_added: int = 0
        self.loading_archetypes = False
        self.loading_decks = False
        self.loading_daily_average = False

        self._save_timer: Optional[wx.Timer] = None
        self.mana_icons = ManaIconFactory()
        self.tracker_window: Optional[MTGOpponentDeckSpyWx] = None
        self.timer_window: Optional[TimerAlertFrame] = None
        self.history_window: Optional[MatchHistoryFrame] = None
        self.mana_keyboard_window: Optional[ManaKeyboardFrame] = None

        self._build_ui()
        self._apply_window_preferences()
        self.SetMinSize((1260, 760))
        self.Centre(wx.BOTH)

        self.Bind(wx.EVT_CLOSE, self.on_close)
        self.Bind(wx.EVT_SIZE, self.on_window_change)
        self.Bind(wx.EVT_MOVE, self.on_window_change)

        wx.CallAfter(self._run_initial_loads)

    # ------------------------------------------------------------------ UI ------------------------------------------------------------------
    def _build_ui(self) -> None:
        self.SetBackgroundColour(DARK_BG)

        self.status_bar = self.CreateStatusBar()
        self.status_bar.SetBackgroundColour(DARK_PANEL)
        self.status_bar.SetForegroundColour(LIGHT_TEXT)
        self._set_status("Ready")

        root_panel = wx.Panel(self)
        root_panel.SetBackgroundColour(DARK_BG)
        root_sizer = wx.BoxSizer(wx.HORIZONTAL)
        root_panel.SetSizer(root_sizer)

        left_panel = wx.Panel(root_panel)
        left_panel.SetBackgroundColour(DARK_PANEL)
        left_sizer = wx.BoxSizer(wx.VERTICAL)
        left_panel.SetSizer(left_sizer)
        root_sizer.Add(left_panel, 0, wx.EXPAND | wx.ALL, 10)

        self.left_stack = wx.Simplebook(left_panel)
        self.left_stack.SetBackgroundColour(DARK_PANEL)
        left_sizer.Add(self.left_stack, 1, wx.EXPAND)

        self._create_research_panel()
        self._create_builder_panel()
        self._show_left_panel(self.left_mode, force=True)

        right_panel = wx.Panel(root_panel)
        right_panel.SetBackgroundColour(DARK_BG)
        right_sizer = wx.BoxSizer(wx.VERTICAL)
        right_panel.SetSizer(right_sizer)
        root_sizer.Add(right_panel, 1, wx.EXPAND | wx.ALL, 10)

        toolbar = wx.BoxSizer(wx.HORIZONTAL)
        right_sizer.Add(toolbar, 0, wx.EXPAND | wx.BOTTOM, 6)
        tracker_btn = wx.Button(right_panel, label="Opponent Tracker")
        tracker_btn.Bind(wx.EVT_BUTTON, lambda _evt: self.open_opponent_tracker())
        toolbar.Add(tracker_btn, 0, wx.RIGHT, 6)
        timer_btn = wx.Button(right_panel, label="Timer Alert")
        timer_btn.Bind(wx.EVT_BUTTON, lambda _evt: self.open_timer_alert())
        toolbar.Add(timer_btn, 0, wx.RIGHT, 6)
        history_btn = wx.Button(right_panel, label="Match History")
        history_btn.Bind(wx.EVT_BUTTON, lambda _evt: self.open_match_history())
        toolbar.Add(history_btn, 0, wx.RIGHT, 6)
        reload_collection_btn = wx.Button(right_panel, label="Load Collection")
        reload_collection_btn.Bind(wx.EVT_BUTTON, lambda _evt: self._refresh_collection_inventory(force=True))
        toolbar.Add(reload_collection_btn, 0, wx.RIGHT, 6)
        download_images_btn = wx.Button(right_panel, label="Download Card Images")
        download_images_btn.Bind(wx.EVT_BUTTON, lambda _evt: self._show_image_download_dialog())
        toolbar.Add(download_images_btn, 0)
        toolbar.AddStretchSpacer(1)

        upper_split = wx.BoxSizer(wx.HORIZONTAL)
        right_sizer.Add(upper_split, 1, wx.EXPAND | wx.BOTTOM, 10)

        summary_column = wx.BoxSizer(wx.VERTICAL)
        upper_split.Add(summary_column, 1, wx.EXPAND | wx.RIGHT, 10)

        summary_box = wx.StaticBox(right_panel, label="Archetype Summary")
        summary_box.SetForegroundColour(LIGHT_TEXT)
        summary_box.SetBackgroundColour(DARK_PANEL)
        summary_sizer = wx.StaticBoxSizer(summary_box, wx.VERTICAL)
        summary_column.Add(summary_sizer, 0, wx.EXPAND | wx.BOTTOM, 10)

        self.summary_text = wx.TextCtrl(
            summary_box,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_WORDWRAP | wx.NO_BORDER,
        )
        self._stylize_textctrl(self.summary_text, multiline=True)
        self.summary_text.SetMinSize((-1, 110))
        summary_sizer.Add(self.summary_text, 1, wx.EXPAND | wx.ALL, 6)

        deck_box = wx.StaticBox(right_panel, label="Deck Results")
        deck_box.SetForegroundColour(LIGHT_TEXT)
        deck_box.SetBackgroundColour(DARK_PANEL)
        deck_sizer = wx.StaticBoxSizer(deck_box, wx.VERTICAL)
        summary_column.Add(deck_sizer, 1, wx.EXPAND)

        inspector_box = wx.StaticBox(right_panel, label="Card Inspector")
        inspector_box.SetForegroundColour(LIGHT_TEXT)
        inspector_box.SetBackgroundColour(DARK_PANEL)
        inspector_sizer = wx.StaticBoxSizer(inspector_box, wx.VERTICAL)
        upper_split.Add(inspector_sizer, 2, wx.EXPAND)

        inspector_content = wx.BoxSizer(wx.HORIZONTAL)
        inspector_sizer.Add(inspector_content, 1, wx.EXPAND | wx.ALL, 6)

        image_column_panel = wx.Panel(inspector_box)
        image_column_panel.SetBackgroundColour(DARK_PANEL)
        image_column = wx.BoxSizer(wx.VERTICAL)
        image_column_panel.SetSizer(image_column)
        inspector_content.Add(image_column_panel, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 12)

        # Create the card image display widget (clean implementation)
        self.card_image_display = CardImageDisplay(image_column_panel, width=260, height=360)
        image_column.Add(self.card_image_display, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.ALL, 4)

        self.inspector_nav_panel = wx.Panel(image_column_panel)
        self.inspector_nav_panel.SetBackgroundColour(DARK_PANEL)
        nav_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.inspector_nav_panel.SetSizer(nav_sizer)

        try:
            nav_btn_size = self.FromDIP(wx.Size(38, 30))
        except AttributeError:
            nav_btn_size = wx.Size(38, 30)

        self.inspector_prev_btn = wx.Button(self.inspector_nav_panel, label="◀", size=nav_btn_size)
        self._stylize_button(self.inspector_prev_btn)
        self.inspector_prev_btn.Bind(wx.EVT_BUTTON, lambda _evt: self._on_prev_printing())
        nav_sizer.Add(self.inspector_prev_btn, 0, wx.RIGHT, 4)

        self.inspector_printing_label = wx.StaticText(self.inspector_nav_panel, label="")
        self.inspector_printing_label.SetForegroundColour(SUBDUED_TEXT)
        nav_sizer.Add(self.inspector_printing_label, 1, wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_CENTER)

        self.inspector_next_btn = wx.Button(self.inspector_nav_panel, label="▶", size=nav_btn_size)
        self._stylize_button(self.inspector_next_btn)
        self.inspector_next_btn.Bind(wx.EVT_BUTTON, lambda _evt: self._on_next_printing())
        nav_sizer.Add(self.inspector_next_btn, 0, wx.LEFT, 4)

        image_column.Add(self.inspector_nav_panel, 0, wx.EXPAND | wx.TOP, 6)
        self.inspector_nav_panel.Hide()  # Hidden by default

        inspector_details_panel = wx.Panel(inspector_box)
        inspector_details_panel.SetBackgroundColour(DARK_PANEL)
        inspector_details = wx.BoxSizer(wx.VERTICAL)
        inspector_details_panel.SetSizer(inspector_details)
        inspector_content.Add(inspector_details_panel, 1, wx.EXPAND)

        self.inspector_name = wx.StaticText(inspector_details_panel, label="Select a card to inspect.")
        name_font = self.inspector_name.GetFont()
        name_font.SetPointSize(name_font.GetPointSize() + 2)
        name_font.MakeBold()
        self.inspector_name.SetFont(name_font)
        self.inspector_name.SetForegroundColour(LIGHT_TEXT)
        inspector_details.Add(self.inspector_name, 0, wx.BOTTOM, 4)

        self.inspector_cost_container = wx.Panel(inspector_details_panel)
        self.inspector_cost_container.SetBackgroundColour(DARK_PANEL)
        self.inspector_cost_container.SetMinSize((-1, 36))
        self.inspector_cost_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.inspector_cost_container.SetSizer(self.inspector_cost_sizer)
        inspector_details.Add(self.inspector_cost_container, 0, wx.EXPAND | wx.BOTTOM, 4)

        self.inspector_type = wx.StaticText(inspector_details_panel, label="")
        self.inspector_type.SetForegroundColour(SUBDUED_TEXT)
        inspector_details.Add(self.inspector_type, 0, wx.BOTTOM, 4)

        self.inspector_stats = wx.StaticText(inspector_details_panel, label="")
        self.inspector_stats.SetForegroundColour(LIGHT_TEXT)
        inspector_details.Add(self.inspector_stats, 0, wx.BOTTOM, 4)

        self.inspector_text = wx.TextCtrl(
            inspector_details_panel,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_WORDWRAP | wx.NO_BORDER,
        )
        self._stylize_textctrl(self.inspector_text, multiline=True)
        self.inspector_text.SetMinSize((-1, 120))
        inspector_details.Add(self.inspector_text, 1, wx.EXPAND | wx.TOP, 4)

        # State for managing printings
        self.inspector_printings: List[Dict[str, Any]] = []
        self.inspector_current_printing: int = 0
        self.inspector_current_card_name: Optional[str] = None
        self.image_cache = get_cache()
        self.image_downloader: Optional[BulkImageDownloader] = None

        # Bulk data cache - loaded once in memory for fast lookups
        self.bulk_data_by_name: Optional[Dict[str, List[Dict[str, Any]]]] = None
        self.printing_index_loading: bool = False

        self._reset_card_inspector()

        self.deck_list = wx.ListBox(deck_box, style=wx.LB_SINGLE)
        self._stylize_listbox(self.deck_list)
        self.deck_list.Bind(wx.EVT_LISTBOX, self.on_deck_selected)
        deck_sizer.Add(self.deck_list, 1, wx.EXPAND | wx.ALL, 6)

        button_row = wx.BoxSizer(wx.HORIZONTAL)
        deck_sizer.Add(button_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)

        self.load_button = wx.Button(deck_box, label="Load Deck")
        self._stylize_button(self.load_button)
        self.load_button.Disable()
        self.load_button.Bind(wx.EVT_BUTTON, self.on_load_deck_clicked)
        button_row.Add(self.load_button, 0, wx.RIGHT, 6)

        self.daily_average_button = wx.Button(deck_box, label="Today's Average")
        self._stylize_button(self.daily_average_button)
        self.daily_average_button.Disable()
        self.daily_average_button.Bind(wx.EVT_BUTTON, self.on_daily_average_clicked)
        button_row.Add(self.daily_average_button, 0, wx.RIGHT, 6)

        self.copy_button = wx.Button(deck_box, label="Copy")
        self._stylize_button(self.copy_button)
        self.copy_button.Disable()
        self.copy_button.Bind(wx.EVT_BUTTON, self.on_copy_clicked)
        button_row.Add(self.copy_button, 0, wx.RIGHT, 6)

        self.save_button = wx.Button(deck_box, label="Save Deck")
        self._stylize_button(self.save_button)
        self.save_button.Disable()
        self.save_button.Bind(wx.EVT_BUTTON, self.on_save_clicked)
        button_row.Add(self.save_button, 0)

        detail_box = wx.StaticBox(right_panel, label="Deck Workspace")
        detail_box.SetForegroundColour(LIGHT_TEXT)
        detail_box.SetBackgroundColour(DARK_PANEL)
        detail_sizer = wx.StaticBoxSizer(detail_box, wx.VERTICAL)
        right_sizer.Add(detail_sizer, 1, wx.EXPAND)

        self.deck_tabs = wx.Notebook(detail_box)
        detail_sizer.Add(self.deck_tabs, 1, wx.EXPAND | wx.ALL, 6)

        self.deck_tables_page = wx.Panel(self.deck_tabs)
        self.deck_tabs.AddPage(self.deck_tables_page, "Deck Tables")
        tables_sizer = wx.BoxSizer(wx.VERTICAL)
        self.deck_tables_page.SetSizer(tables_sizer)

        self.zone_notebook = wx.Notebook(self.deck_tables_page)
        tables_sizer.Add(self.zone_notebook, 1, wx.EXPAND | wx.BOTTOM, 6)

        self.main_table = CardTablePanel(
            self.zone_notebook,
            "main",
            self.mana_icons,
            self._get_card_metadata,
            self._owned_status,
            self._handle_zone_delta,
            self._handle_zone_remove,
            self._handle_zone_add,
            self._handle_card_focus,
        )
        self.zone_notebook.AddPage(self.main_table, "Mainboard")

        self.side_table = CardTablePanel(
            self.zone_notebook,
            "side",
            self.mana_icons,
            self._get_card_metadata,
            self._owned_status,
            self._handle_zone_delta,
            self._handle_zone_remove,
            self._handle_zone_add,
            self._handle_card_focus,
        )
        self.zone_notebook.AddPage(self.side_table, "Sideboard")

        self.out_table = CardTablePanel(
            self.zone_notebook,
            "out",
            self.mana_icons,
            self._get_card_metadata,
            lambda name, qty: ("Out", wx.Colour(255, 255, 255)),
            self._handle_zone_delta,
            self._handle_zone_remove,
            self._handle_zone_add,
            self._handle_card_focus,
        )
        self.zone_notebook.AddPage(self.out_table, "Outboard")

        self.collection_status_label = wx.StaticText(self.deck_tables_page, label="Collection inventory not loaded.")
        self.collection_status_label.SetForegroundColour(SUBDUED_TEXT)
        tables_sizer.Add(self.collection_status_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 4)

        self.stats_page = wx.Panel(self.deck_tabs)
        self.deck_tabs.AddPage(self.stats_page, "Stats")
        stats_sizer = wx.BoxSizer(wx.VERTICAL)
        self.stats_page.SetSizer(stats_sizer)

        self.stats_summary = wx.StaticText(self.stats_page, label="No deck loaded.")
        self.stats_summary.SetForegroundColour(LIGHT_TEXT)
        stats_sizer.Add(self.stats_summary, 0, wx.ALL, 6)

        stats_split = wx.BoxSizer(wx.HORIZONTAL)
        stats_sizer.Add(stats_split, 1, wx.EXPAND | wx.ALL, 6)

        self.curve_list = dv.DataViewListCtrl(self.stats_page)
        self.curve_list.AppendTextColumn("CMC", width=80)
        self.curve_list.AppendTextColumn("Count", width=80)
        self.curve_list.SetBackgroundColour(DARK_ALT)
        self.curve_list.SetForegroundColour(LIGHT_TEXT)
        stats_split.Add(self.curve_list, 0, wx.RIGHT, 12)

        self.color_list = dv.DataViewListCtrl(self.stats_page)
        self.color_list.AppendTextColumn("Color", width=120)
        self.color_list.AppendTextColumn("Share", width=100)
        self.color_list.SetBackgroundColour(DARK_ALT)
        self.color_list.SetForegroundColour(LIGHT_TEXT)
        stats_split.Add(self.color_list, 0)

        self.guide_page = wx.Panel(self.deck_tabs)
        self.deck_tabs.AddPage(self.guide_page, "Sideboard Guide")
        guide_sizer = wx.BoxSizer(wx.VERTICAL)
        self.guide_page.SetSizer(guide_sizer)

        self.guide_view = dv.DataViewListCtrl(self.guide_page, style=dv.DV_ROW_LINES)
        self.guide_view.AppendTextColumn("Archetype", width=200)
        self.guide_view.AppendTextColumn("Cards In", width=200)
        self.guide_view.AppendTextColumn("Cards Out", width=200)
        self.guide_view.AppendTextColumn("Notes", width=220)
        self.guide_view.SetBackgroundColour(DARK_ALT)
        self.guide_view.SetForegroundColour(LIGHT_TEXT)
        guide_sizer.Add(self.guide_view, 1, wx.EXPAND | wx.ALL, 6)

        guide_buttons = wx.BoxSizer(wx.HORIZONTAL)
        guide_sizer.Add(guide_buttons, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)
        add_guide_btn = wx.Button(self.guide_page, label="Add Entry")
        add_guide_btn.Bind(wx.EVT_BUTTON, lambda _evt: self._on_add_guide_entry())
        guide_buttons.Add(add_guide_btn, 0, wx.RIGHT, 6)
        edit_guide_btn = wx.Button(self.guide_page, label="Edit Entry")
        edit_guide_btn.Bind(wx.EVT_BUTTON, lambda _evt: self._on_edit_guide_entry())
        guide_buttons.Add(edit_guide_btn, 0, wx.RIGHT, 6)
        remove_guide_btn = wx.Button(self.guide_page, label="Remove Entry")
        remove_guide_btn.Bind(wx.EVT_BUTTON, lambda _evt: self._on_remove_guide_entry())
        guide_buttons.Add(remove_guide_btn, 0, wx.RIGHT, 6)
        exclusions_btn = wx.Button(self.guide_page, label="Exclude Archetypes")
        exclusions_btn.Bind(wx.EVT_BUTTON, lambda _evt: self._on_edit_exclusions())
        guide_buttons.Add(exclusions_btn, 0)
        guide_buttons.AddStretchSpacer(1)

        self.guide_exclusions_label = wx.StaticText(self.guide_page, label="Exclusions: —")
        self.guide_exclusions_label.SetForegroundColour(SUBDUED_TEXT)
        guide_sizer.Add(self.guide_exclusions_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)

        self.notes_page = wx.Panel(self.deck_tabs)
        self.deck_tabs.AddPage(self.notes_page, "Deck Notes")
        notes_sizer = wx.BoxSizer(wx.VERTICAL)
        self.notes_page.SetSizer(notes_sizer)

        self.deck_notes_text = wx.TextCtrl(self.notes_page, style=wx.TE_MULTILINE)
        self._stylize_textctrl(self.deck_notes_text, multiline=True)
        notes_sizer.Add(self.deck_notes_text, 1, wx.EXPAND | wx.ALL, 6)

        notes_buttons = wx.BoxSizer(wx.HORIZONTAL)
        notes_sizer.Add(notes_buttons, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)
        save_notes_btn = wx.Button(self.notes_page, label="Save Notes")
        save_notes_btn.Bind(wx.EVT_BUTTON, lambda _evt: self._save_current_notes())
        notes_buttons.Add(save_notes_btn, 0, wx.RIGHT, 6)
        notes_buttons.AddStretchSpacer(1)

    # ------------------------------------------------------------------ Left panel helpers -------------------------------------------------
    def _create_research_panel(self) -> None:
        if not self.left_stack:
            return
        panel = wx.Panel(self.left_stack)
        panel.SetBackgroundColour(DARK_PANEL)
        sizer = wx.BoxSizer(wx.VERTICAL)
        panel.SetSizer(sizer)

        format_label = wx.StaticText(panel, label="Format")
        self._stylize_label(format_label)
        sizer.Add(format_label, 0, wx.TOP | wx.LEFT | wx.RIGHT, 6)

        self.format_choice = wx.Choice(panel, choices=FORMAT_OPTIONS)
        self.format_choice.SetStringSelection(self.current_format)
        self._stylize_choice(self.format_choice)
        self.format_choice.Bind(wx.EVT_CHOICE, self.on_format_changed)
        sizer.Add(self.format_choice, 0, wx.EXPAND | wx.ALL, 6)

        self.search_ctrl = wx.SearchCtrl(panel, style=wx.TE_PROCESS_ENTER)
        self.search_ctrl.ShowSearchButton(True)
        self.search_ctrl.SetHint("Search archetypes…")
        self.search_ctrl.Bind(wx.EVT_TEXT, self.on_archetype_filter)
        self._stylize_textctrl(self.search_ctrl)
        sizer.Add(self.search_ctrl, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)

        self.archetype_list = wx.ListBox(panel, style=wx.LB_SINGLE)
        self._stylize_listbox(self.archetype_list)
        self.archetype_list.Bind(wx.EVT_LISTBOX, self.on_archetype_selected)
        sizer.Add(self.archetype_list, 1, wx.EXPAND | wx.ALL, 6)

        refresh_button = wx.Button(panel, label="Reload Archetypes")
        self._stylize_button(refresh_button)
        refresh_button.Bind(wx.EVT_BUTTON, lambda evt: self.fetch_archetypes(force=True))
        sizer.Add(refresh_button, 0, wx.EXPAND | wx.ALL, 6)

        self.left_stack.AddPage(panel, "Research")
        self.research_panel = panel

    def _create_builder_panel(self) -> None:
        if not self.left_stack:
            return
        panel = wx.Panel(self.left_stack)
        panel.SetBackgroundColour(DARK_PANEL)
        sizer = wx.BoxSizer(wx.VERTICAL)
        panel.SetSizer(sizer)

        back_btn = wx.Button(panel, label="Deck Research")
        self._stylize_button(back_btn)
        back_btn.Bind(wx.EVT_BUTTON, lambda _evt: self._show_left_panel("research"))
        sizer.Add(back_btn, 0, wx.EXPAND | wx.ALL, 6)

        info = wx.StaticText(panel, label="Deck Builder: search MTG cards by property.")
        self._stylize_label(info, subtle=True)
        sizer.Add(info, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)

        field_specs = [
            ("name", "Card Name", "e.g. Ragavan"),
            ("type", "Type Line", "Artifact Creature"),
            ("mana", "Mana Cost", "Curly braces like {1}{G} or shorthand (e.g. GGG)"),
            ("text", "Oracle Text", "Keywords or abilities"),
        ]
        for key, label_text, hint in field_specs:
            lbl = wx.StaticText(panel, label=label_text)
            self._stylize_label(lbl, subtle=True)
            sizer.Add(lbl, 0, wx.LEFT | wx.RIGHT, 6)
            ctrl = wx.TextCtrl(panel)
            self._stylize_textctrl(ctrl)
            ctrl.SetHint(hint)
            sizer.Add(ctrl, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)
            self.builder_inputs[key] = ctrl
            if key == "mana":
                match_row = wx.BoxSizer(wx.HORIZONTAL)
                match_label = wx.StaticText(panel, label="Match")
                self._stylize_label(match_label, subtle=True)
                match_row.Add(match_label, 0, wx.RIGHT, 6)
                exact_cb = wx.CheckBox(panel, label="Exact symbols")
                exact_cb.SetForegroundColour(LIGHT_TEXT)
                exact_cb.SetBackgroundColour(DARK_PANEL)
                match_row.Add(exact_cb, 0)
                self.builder_mana_exact_cb = exact_cb
                match_row.AddStretchSpacer(1)
                sizer.Add(match_row, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)

                keyboard_row = wx.BoxSizer(wx.HORIZONTAL)
                keyboard_row.AddStretchSpacer(1)
                for token in ["W", "U", "B", "R", "G", "C", "X"]:
                    btn = self._create_mana_button(panel, token, self._append_mana_symbol)
                    keyboard_row.Add(btn, 0, wx.ALL, 2)
                all_btn = wx.Button(panel, label="All", size=(52, 28))
                self._stylize_button(all_btn)
                all_btn.Bind(wx.EVT_BUTTON, lambda _evt: self._open_full_mana_keyboard())
                keyboard_row.Add(all_btn, 0, wx.ALL, 2)
                keyboard_row.AddStretchSpacer(1)
                sizer.Add(keyboard_row, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.LEFT | wx.RIGHT | wx.BOTTOM, 4)

        mv_row = wx.BoxSizer(wx.HORIZONTAL)
        mv_label = wx.StaticText(panel, label="Mana Value Filter")
        self._stylize_label(mv_label, subtle=True)
        mv_row.Add(mv_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        mv_choice = wx.Choice(panel, choices=["Any", "<", "≤", "=", "≥", ">"])
        mv_choice.SetSelection(0)
        self._stylize_choice(mv_choice)
        self.builder_mv_comparator = mv_choice
        mv_row.Add(mv_choice, 0, wx.RIGHT, 6)
        mv_value = wx.TextCtrl(panel)
        self._stylize_textctrl(mv_value)
        mv_value.SetHint("e.g. 3")
        self.builder_mv_value = mv_value
        mv_row.Add(mv_value, 1)
        sizer.Add(mv_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)

        formats_label = wx.StaticText(panel, label="Formats")
        self._stylize_label(formats_label, subtle=True)
        sizer.Add(formats_label, 0, wx.LEFT | wx.RIGHT, 6)
        formats_grid = wx.FlexGridSizer(0, 2, 4, 8)
        for fmt in FORMAT_OPTIONS:
            cb = wx.CheckBox(panel, label=fmt)
            cb.SetForegroundColour(LIGHT_TEXT)
            cb.SetBackgroundColour(DARK_PANEL)
            formats_grid.Add(cb, 0, wx.RIGHT, 6)
            self.builder_format_checks.append(cb)
        sizer.Add(formats_grid, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)

        color_label = wx.StaticText(panel, label="Color Identity Filter")
        self._stylize_label(color_label, subtle=True)
        sizer.Add(color_label, 0, wx.LEFT | wx.RIGHT, 6)

        color_mode = wx.Choice(panel, choices=["Any", "At least", "Exactly", "Not these"])
        color_mode.SetSelection(0)
        self._stylize_choice(color_mode)
        self.builder_color_mode_choice = color_mode
        sizer.Add(color_mode, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)

        colors_row = wx.BoxSizer(wx.HORIZONTAL)
        for code, label in [
            ("W", "White"),
            ("U", "Blue"),
            ("B", "Black"),
            ("R", "Red"),
            ("G", "Green"),
            ("C", "Colorless"),
        ]:
            cb = wx.CheckBox(panel, label=label)
            cb.SetForegroundColour(LIGHT_TEXT)
            cb.SetBackgroundColour(DARK_PANEL)
            colors_row.Add(cb, 0, wx.RIGHT, 6)
            self.builder_color_checks[code] = cb
        sizer.Add(colors_row, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)

        controls = wx.BoxSizer(wx.HORIZONTAL)
        search_btn = wx.Button(panel, label="Search Cards")
        self._stylize_button(search_btn)
        search_btn.Bind(wx.EVT_BUTTON, self.on_builder_search)
        controls.Add(search_btn, 0, wx.RIGHT, 6)
        clear_btn = wx.Button(panel, label="Clear Filters")
        self._stylize_button(clear_btn)
        clear_btn.Bind(wx.EVT_BUTTON, self.on_builder_clear)
        controls.Add(clear_btn, 0)
        controls.AddStretchSpacer(1)
        sizer.Add(controls, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)

        results = wx.ListCtrl(panel, style=wx.LC_REPORT | wx.BORDER_NONE)
        results.InsertColumn(0, "Name", width=220)
        results.InsertColumn(1, "Mana", width=110)
        self._stylize_listctrl(results)
        results.Bind(wx.EVT_LIST_ITEM_SELECTED, self.on_builder_result_selected)
        sizer.Add(results, 1, wx.EXPAND | wx.ALL, 6)
        self.builder_results_ctrl = results

        status = wx.StaticText(panel, label="Search for cards to populate this list.")
        status.SetForegroundColour(SUBDUED_TEXT)
        sizer.Add(status, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)
        self.builder_status_label = status

        self.left_stack.AddPage(panel, "Builder")
        self.builder_panel = panel

    def _show_left_panel(self, mode: str, force: bool = False) -> None:
        target = "builder" if mode == "builder" else "research"
        if self.left_stack:
            index = 1 if target == "builder" else 0
            if force or self.left_stack.GetSelection() != index:
                self.left_stack.ChangeSelection(index)
        if target == "builder":
            self.ensure_card_data_loaded()
        if force or self.left_mode != target:
            self.left_mode = target
            self._schedule_settings_save()

    def _get_mana_font(self, size: int = 14) -> wx.Font:
        if ManaIconFactory._FONT_LOADED:
            return wx.Font(size, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL, False, ManaIconFactory._FONT_NAME)
        font = self.GetFont()
        font.SetPointSize(size)
        font.MakeBold()
        return font

    def _create_mana_button(self, parent: wx.Window, token: str, handler: Callable[[str], None]) -> wx.Button:
        bmp: Optional[wx.Bitmap] = None
        try:
            bmp = self.mana_icons.bitmap_for_symbol(token)
        except Exception:
            bmp = None
        if bmp:
            btn: wx.Button = wx.BitmapButton(parent, bitmap=bmp, size=(bmp.GetWidth() + 10, bmp.GetHeight() + 10), style=wx.BU_EXACTFIT)
        else:
            btn = wx.Button(parent, label=token, size=(44, 28))
            btn.SetFont(self._get_mana_font(15))
        btn.SetBackgroundColour(DARK_ALT)
        btn.SetForegroundColour(LIGHT_TEXT)
        btn.SetToolTip(token)
        btn.Bind(wx.EVT_BUTTON, lambda _evt, sym=token: handler(sym))
        return btn

    def _open_full_mana_keyboard(self) -> None:
        if self.mana_keyboard_window and self.mana_keyboard_window.IsShown():
            self.mana_keyboard_window.Raise()
            return
        frame = ManaKeyboardFrame(self, self._create_mana_button, self._type_global_mana_symbol)
        frame.Bind(wx.EVT_CLOSE, self._on_mana_keyboard_closed)
        frame.Show()
        self.mana_keyboard_window = frame

    def _on_mana_keyboard_closed(self, event: wx.CloseEvent) -> None:
        self.mana_keyboard_window = None
        event.Skip()

    def _restore_session_state(self) -> None:
        saved_mode = self.settings.get("left_mode")
        if saved_mode in {"research", "builder"}:
            self.left_mode = saved_mode
            self._show_left_panel(self.left_mode, force=True)
        saved_zones = self.settings.get("saved_zone_cards") or {}
        changed = False
        for zone in ("main", "side", "out"):
            entries = saved_zones.get(zone, [])
            if not isinstance(entries, list):
                continue
            sanitized: List[Dict[str, Any]] = []
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                name = entry.get("name")
                qty = entry.get("qty", 0)
                if not name:
                    continue
                try:
                    qty_int = max(0, int(qty))
                except (TypeError, ValueError):
                    continue
                if qty_int <= 0:
                    continue
                sanitized.append({"name": name, "qty": qty_int})
            if sanitized:
                self.zone_cards[zone] = sanitized
                changed = True
        if changed:
            self.main_table.set_cards(self.zone_cards["main"])
            self.side_table.set_cards(self.zone_cards["side"])
            self.out_table.set_cards(self.zone_cards["out"])
        saved_text = self.settings.get("saved_deck_text", "")
        if saved_text:
            self.current_deck_text = saved_text
            self._update_stats(saved_text)
            self.copy_button.Enable(True)
            self.save_button.Enable(True)
        saved_deck = self.settings.get("saved_deck_info")
        if isinstance(saved_deck, dict):
            self.current_deck = saved_deck

    def _run_initial_loads(self) -> None:
        self._restore_session_state()
        self.fetch_archetypes()
        self._load_collection_from_cache()  # Fast cache-only load on startup
        self._check_and_download_bulk_data()  # Download card image bulk data if needed

    # ------------------------------------------------------------------ Styling helpers ------------------------------------------------------
    def _stylize_label(self, label: wx.StaticText, subtle: bool = False) -> None:
        label.SetForegroundColour(SUBDUED_TEXT if subtle else LIGHT_TEXT)
        label.SetBackgroundColour(DARK_PANEL if subtle else DARK_BG)
        font = label.GetFont()
        if not subtle:
            font.MakeBold()
        label.SetFont(font)

    def _stylize_textctrl(self, ctrl: wx.TextCtrl, multiline: bool = False) -> None:
        ctrl.SetBackgroundColour(DARK_ALT)
        ctrl.SetForegroundColour(LIGHT_TEXT)
        font = ctrl.GetFont()
        if multiline:
            font.SetPointSize(font.GetPointSize() + 1)
        ctrl.SetFont(font)

    def _stylize_choice(self, ctrl: wx.Choice) -> None:
        ctrl.SetBackgroundColour(DARK_ALT)
        ctrl.SetForegroundColour(LIGHT_TEXT)

    def _stylize_listbox(self, ctrl: wx.ListBox) -> None:
        ctrl.SetBackgroundColour(DARK_ALT)
        ctrl.SetForegroundColour(LIGHT_TEXT)
        if hasattr(ctrl, "SetSelectionBackground"):
            ctrl.SetSelectionBackground(DARK_ACCENT)
            ctrl.SetSelectionForeground(wx.Colour(15, 17, 22))

    def _stylize_listctrl(self, ctrl: wx.ListCtrl) -> None:
        ctrl.SetBackgroundColour(DARK_ALT)
        ctrl.SetTextColour(LIGHT_TEXT)
        if hasattr(ctrl, "SetHighlightColour"):
            ctrl.SetHighlightColour(DARK_ACCENT)
        if hasattr(ctrl, "SetSelectionBackground"):
            ctrl.SetSelectionBackground(DARK_ACCENT)
        if hasattr(ctrl, "SetSelectionForeground"):
            ctrl.SetSelectionForeground(wx.Colour(10, 12, 16))

    def _stylize_button(self, button: wx.Button) -> None:
        button.SetBackgroundColour(DARK_ACCENT)
        button.SetForegroundColour(wx.Colour(12, 14, 18))
        font = button.GetFont()
        font.MakeBold()
        button.SetFont(font)

    def _set_status(self, message: str) -> None:
        if self.status_bar:
            self.status_bar.SetStatusText(message)
        logger.info(message)

    # ------------------------------------------------------------------ Window persistence ---------------------------------------------------
    def _load_window_settings(self) -> Dict[str, Any]:
        if not DECK_SELECTOR_SETTINGS_FILE.exists():
            return {}
        try:
            with DECK_SELECTOR_SETTINGS_FILE.open("r", encoding="utf-8") as fh:
                return json.load(fh)
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive logging
            logger.warning(f"Failed to load deck selector settings: {exc}")
            return {}

    def _save_window_settings(self) -> None:
        data = dict(self.settings)
        pos = self.GetPosition()
        size = self.GetSize()
        data.update(
            {
                "format": self.current_format,
                "window_size": [size.width, size.height],
                "screen_pos": [pos.x, pos.y],
                "left_mode": self.left_mode,
                "saved_deck_text": self.current_deck_text,
                "saved_zone_cards": self._serialize_zone_cards(),
            }
        )
        if self.current_deck:
            data["saved_deck_info"] = self.current_deck
        elif "saved_deck_info" in data:
            data.pop("saved_deck_info")
        try:
            with DECK_SELECTOR_SETTINGS_FILE.open("w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)
        except OSError as exc:  # pragma: no cover - defensive logging
            logger.warning(f"Unable to persist deck selector settings: {exc}")
        self.settings = data

    def _serialize_zone_cards(self) -> Dict[str, List[Dict[str, Any]]]:
        serialized: Dict[str, List[Dict[str, Any]]] = {}
        for zone, cards in self.zone_cards.items():
            cleaned: List[Dict[str, Any]] = []
            for entry in cards:
                name = entry.get("name")
                qty = entry.get("qty", 0)
                if not name:
                    continue
                try:
                    qty_int = max(0, int(qty))
                except (TypeError, ValueError):
                    qty_int = 0
                if qty_int <= 0:
                    continue
                cleaned.append({"name": name, "qty": qty_int})
            serialized[zone] = cleaned
        return serialized

    def _apply_window_preferences(self) -> None:
        size = self.settings.get("window_size")
        if isinstance(size, list) and len(size) == 2:
            try:
                self.SetSize(wx.Size(int(size[0]), int(size[1])))
            except (TypeError, ValueError):
                logger.debug("Ignoring invalid saved window size")
        pos = self.settings.get("screen_pos")
        if isinstance(pos, list) and len(pos) == 2:
            try:
                self.SetPosition(wx.Point(int(pos[0]), int(pos[1])))
            except (TypeError, ValueError):
                logger.debug("Ignoring invalid saved window position")

    def _schedule_settings_save(self) -> None:
        if self._save_timer is None:
            self._save_timer = wx.Timer(self)
            self.Bind(wx.EVT_TIMER, self._flush_pending_settings, self._save_timer)
        if self._save_timer.IsRunning():
            self._save_timer.Stop()
        self._save_timer.StartOnce(600)

    def on_window_change(self, event: wx.Event) -> None:
        self._schedule_settings_save()
        event.Skip()

    def _flush_pending_settings(self, _event: wx.TimerEvent) -> None:
        self._save_window_settings()

    # ------------------------------------------------------------------ Event handlers -------------------------------------------------------
    def on_format_changed(self, _event: wx.CommandEvent) -> None:
        self.current_format = self.format_choice.GetStringSelection()
        self.fetch_archetypes(force=True)

    def on_archetype_filter(self, _event: wx.CommandEvent) -> None:
        query = self.search_ctrl.GetValue().strip().lower()
        if not query:
            self.filtered_archetypes = list(self.archetypes)
        else:
            self.filtered_archetypes = [entry for entry in self.archetypes if query in entry.get("name", "").lower()]
        self._populate_archetype_list()

    def on_archetype_selected(self, _event: wx.CommandEvent) -> None:
        if self.loading_archetypes or self.loading_decks:
            return
        idx = self.archetype_list.GetSelection()
        if idx == wx.NOT_FOUND:
            return
        archetype = self.filtered_archetypes[idx]
        self._load_decks_for_archetype(archetype)

    def on_builder_search(self, _event: wx.CommandEvent) -> None:
        if not self.card_manager:
            if not self.card_data_loading:
                self.ensure_card_data_loaded()
            wx.MessageBox(
                "Card database is still loading. Please try again in a moment.",
                "Card Search",
                wx.OK | wx.ICON_INFORMATION,
            )
            return
        filters = {key: ctrl.GetValue().strip() for key, ctrl in self.builder_inputs.items()}
        mana_query = self._normalize_mana_query(filters.get("mana", ""))
        mana_mode = "exact" if (self.builder_mana_exact_cb and self.builder_mana_exact_cb.IsChecked()) else "contains"
        mv_cmp = self.builder_mv_comparator.GetStringSelection() if self.builder_mv_comparator else "Any"
        mv_value = None
        if self.builder_mv_value:
            text = self.builder_mv_value.GetValue().strip()
            if text:
                try:
                    mv_value = float(text)
                except ValueError:
                    wx.MessageBox("Mana value must be numeric.", "Card Search", wx.OK | wx.ICON_WARNING)
                    return
        selected_formats = [cb.GetLabel().lower() for cb in self.builder_format_checks if cb.IsChecked()]
        color_mode = self.builder_color_mode_choice.GetStringSelection() if self.builder_color_mode_choice else "Any"
        selected_colors = [code for code, cb in self.builder_color_checks.items() if cb.IsChecked()]
        query = filters.get("name") or filters.get("text") or ""
        results = self.card_manager.search_cards(query=query, format_filter=None)
        filtered: List[Dict[str, Any]] = []
        for card in results:
            name_lower = card.get("name_lower", "")
            if filters.get("name") and filters["name"].lower() not in name_lower:
                continue
            type_line = (card.get("type_line") or "").lower()
            if filters.get("type") and filters["type"].lower() not in type_line:
                continue
            mana_cost = (card.get("mana_cost") or "").upper()
            if mana_query and not self._matches_mana_cost(mana_cost, mana_query, mana_mode):
                continue
            oracle_text = (card.get("oracle_text") or "").lower()
            if filters.get("text") and filters["text"].lower() not in oracle_text:
                continue
            if selected_formats:
                legalities = card.get("legalities", {}) or {}
                if not all(legalities.get(fmt) == "Legal" for fmt in selected_formats):
                    continue
            if mv_value is not None and mv_cmp != "Any":
                if not self._matches_mana_value(card.get("mana_value"), mv_value, mv_cmp):
                    continue
            if selected_colors and color_mode != "Any":
                if not self._matches_color_filter(card.get("color_identity") or [], selected_colors, color_mode):
                    continue
            filtered.append(card)
            if len(filtered) >= 300:
                break
        self.builder_results_cache = filtered
        self._populate_builder_results()

    def on_builder_clear(self, _event: wx.CommandEvent) -> None:
        for ctrl in self.builder_inputs.values():
            ctrl.ChangeValue("")
        self.builder_results_cache = []
        self._populate_builder_results()
        if self.builder_status_label:
            self.builder_status_label.SetLabel("Filters cleared.")
        if self.builder_mana_exact_cb:
            self.builder_mana_exact_cb.SetValue(False)
        if self.builder_mv_comparator:
            self.builder_mv_comparator.SetSelection(0)
        if self.builder_mv_value:
            self.builder_mv_value.ChangeValue("")
        for cb in self.builder_format_checks:
            cb.SetValue(False)
        if self.builder_color_mode_choice:
            self.builder_color_mode_choice.SetSelection(0)
        for cb in self.builder_color_checks.values():
            cb.SetValue(False)

    def on_builder_result_selected(self, event: wx.ListEvent) -> None:
        idx = event.GetIndex()
        if idx < 0 or idx >= len(self.builder_results_cache):
            return
        meta = self.builder_results_cache[idx]
        faux_card = {"name": meta.get("name", "Unknown"), "qty": 1}
        self._update_card_inspector(None, faux_card, meta)

    def _populate_builder_results(self) -> None:
        if not self.builder_results_ctrl:
            return
        self.builder_results_ctrl.DeleteAllItems()
        for idx, card in enumerate(self.builder_results_cache):
            name = card.get("name", "Unknown")
            mana = card.get("mana_cost") or "—"
            item_index = self.builder_results_ctrl.InsertItem(idx, name)
            self.builder_results_ctrl.SetItem(item_index, 1, mana)
        if self.builder_status_label:
            count = len(self.builder_results_cache)
            self.builder_status_label.SetLabel(f"Showing {count} card{'s' if count != 1 else ''}.")

    def _normalize_mana_query(self, raw: str) -> str:
        text = (raw or "").strip()
        if not text:
            return ""
        if "{" in text and "}" in text:
            return text
        upper_text = text.upper()
        tokens: List[str] = []
        i = 0
        length = len(upper_text)
        while i < length:
            ch = upper_text[i]
            if ch.isspace() or ch in {',', ';'}:
                i += 1
                continue
            if ch.isdigit():
                num = ch
                i += 1
                while i < length and upper_text[i].isdigit():
                    num += upper_text[i]
                    i += 1
                tokens.append(num)
                continue
            if ch == '{':
                end = upper_text.find('}', i + 1)
                if end != -1:
                    tokens.append(upper_text[i + 1 : end])
                    i = end + 1
                    continue
                i += 1
                continue
            if ch in {"/", "}"}:
                i += 1
                continue
            if ch.isalpha() or ch in {"∞", "½"}:
                token = ch
                i += 1
                while i < length and (upper_text[i].isalpha() or upper_text[i] in {"/", "½"}):
                    token += upper_text[i]
                    i += 1
                if "/" in token:
                    tokens.append(token)
                elif len(token) > 1:
                    tokens.extend(token)
                else:
                    tokens.append(token)
                continue
            i += 1
        return "".join(f"{{{tok}}}" for tok in tokens if tok)

    def _tokenize_mana_symbols(self, cost: str) -> List[str]:
        tokens: List[str] = []
        if not cost:
            return tokens
        for part in cost.replace("}", "").split("{"):
            token = part.strip().upper()
            if token:
                tokens.append(token)
        return tokens

    def _matches_mana_cost(self, card_cost: str, query: str, mode: str) -> bool:
        query_tokens = self._tokenize_mana_symbols(query)
        if not query_tokens:
            return True
        card_tokens = self._tokenize_mana_symbols(card_cost)
        card_counts = Counter(card_tokens)
        query_counts = Counter(query_tokens)
        if mode == "exact":
            return card_counts == query_counts
        for symbol, needed in query_counts.items():
            if card_counts.get(symbol, 0) < needed:
                return False
        return True

    def _matches_mana_value(self, card_value: Any, target: float, comparator: str) -> bool:
        try:
            value = float(card_value)
        except (TypeError, ValueError):
            return False
        if comparator == "<":
            return value < target
        if comparator == "≤":
            return value <= target
        if comparator == "=":
            return value == target
        if comparator == "≥":
            return value >= target
        if comparator == ">":
            return value > target
        return True

    def _matches_color_filter(self, card_colors: List[str], selected: List[str], mode: str) -> bool:
        if not selected or mode == "Any":
            return True
        selected_set = {c.upper() for c in selected}
        card_set = {c.upper() for c in card_colors if c}
        if not card_set:
            card_set = {"C"}
        if mode == "At least":
            return selected_set.issubset(card_set)
        if mode == "Exactly":
            return card_set == selected_set
        if mode == "Not these":
            return selected_set.isdisjoint(card_set)
        return True

    def _append_mana_symbol(self, token: str) -> None:
        ctrl = self.builder_inputs.get("mana")
        if not ctrl:
            return
        symbol = token.strip().upper()
        if not symbol:
            return
        text = symbol if symbol.startswith("{") else f"{{{symbol}}}"
        ctrl.ChangeValue(ctrl.GetValue() + text)
        ctrl.SetFocus()

    def _type_global_mana_symbol(self, token: str) -> None:
        text = self._normalize_mana_query(token)
        if not text:
            return
        simulator = wx.UIActionSimulator()
        for ch in text:
            simulator.Char(ord(ch))

    def on_deck_selected(self, _event: wx.CommandEvent) -> None:
        if self.loading_decks:
            return
        idx = self.deck_list.GetSelection()
        if idx == wx.NOT_FOUND:
            return
        deck = self.decks[idx]
        self.current_deck = deck
        self.load_button.Enable()
        self.copy_button.Enable(self._has_deck_loaded())
        self.save_button.Enable(self._has_deck_loaded())
        self._set_status(f"Selected deck {format_deck_name(deck)}")
        self._show_left_panel("builder")
        self._schedule_settings_save()

    def on_load_deck_clicked(self, _event: wx.CommandEvent) -> None:
        if not self.current_deck or self.loading_decks:
            return
        self._download_and_display_deck(self.current_deck)

    def on_daily_average_clicked(self, _event: wx.CommandEvent) -> None:
        if self.loading_daily_average or not self.decks:
            return
        self._build_daily_average_deck()

    def on_copy_clicked(self, _event: wx.CommandEvent) -> None:
        deck_content = self._build_deck_text().strip()
        if not deck_content:
            wx.MessageBox("No deck to copy.", "Copy Deck", wx.OK | wx.ICON_INFORMATION)
            return
        if wx.TheClipboard.Open():
            try:
                wx.TheClipboard.SetData(wx.TextDataObject(deck_content))
            finally:
                wx.TheClipboard.Close()
            self._set_status("Deck copied to clipboard.")
        else:  # pragma: no cover
            wx.MessageBox("Could not access clipboard.", "Copy Deck", wx.OK | wx.ICON_WARNING)

    def on_save_clicked(self, _event: wx.CommandEvent) -> None:
        deck_content = self._build_deck_text().strip()
        if not deck_content:
            wx.MessageBox("Load a deck first.", "Save Deck", wx.OK | wx.ICON_INFORMATION)
            return
        default_name = "saved_deck"
        if self.current_deck:
            default_name = format_deck_name(self.current_deck).replace(" | ", "_")
        dlg = wx.TextEntryDialog(self, "Deck name:", "Save Deck", default_name=default_name)
        if dlg.ShowModal() != wx.ID_OK:
            dlg.Destroy()
            return
        deck_name = dlg.GetValue().strip() or default_name
        dlg.Destroy()

        safe_name = "".join(ch if ch not in '\\/:*?"<>|' else "_" for ch in deck_name).strip()
        if not safe_name:
            safe_name = "saved_deck"
        file_path = DECK_SAVE_DIR / f"{safe_name}.txt"
        try:
            with file_path.open("w", encoding="utf-8") as fh:
                fh.write(deck_content)
        except OSError as exc:  # pragma: no cover
            wx.MessageBox(f"Failed to write deck file:\n{exc}", "Save Deck", wx.OK | wx.ICON_ERROR)
            return

        try:
            deck_id = save_deck_to_db(
                deck_name=deck_name,
                deck_content=deck_content,
                format_type=self.current_format,
                archetype=self.current_deck.get("name") if self.current_deck else None,
                player=self.current_deck.get("player") if self.current_deck else None,
                source="mtggoldfish" if self.current_deck else "manual",
                metadata=(self.current_deck or {}),
            )
            logger.info(f"Deck saved to database: {deck_name} (ID: {deck_id})")
        except Exception as exc:  # pragma: no cover
            logger.warning(f"Deck saved to file but not database: {exc}")
            deck_id = None

        message = f"Deck saved to {file_path}"
        if deck_id:
            message += f"\nDatabase ID: {deck_id}"
        wx.MessageBox(message, "Deck Saved", wx.OK | wx.ICON_INFORMATION)
        self._set_status("Deck saved successfully.")

    # ------------------------------------------------------------------ Data loading ---------------------------------------------------------
    def fetch_archetypes(self, force: bool = False) -> None:
        if self.loading_archetypes:
            return
        self.loading_archetypes = True
        self._set_status(f"Loading archetypes for {self.current_format}…")
        self.archetype_list.Clear()
        self.archetype_list.Append("Loading…")
        self.archetype_list.Disable()
        self.decks.clear()
        self.deck_list.Clear()
        self._clear_deck_display()
        self.daily_average_button.Disable()
        self.load_button.Disable()
        self.copy_button.Disable()
        self.save_button.Disable()

        def loader(fmt: str):
            return get_archetypes(fmt.lower(), allow_stale=not force)

        _Worker(loader, self.current_format, on_success=self._on_archetypes_loaded, on_error=self._on_archetypes_error).start()

    def _clear_deck_display(self) -> None:
        self.current_deck = None
        self.summary_text.ChangeValue("Select an archetype to view decks.")
        self.zone_cards = {"main": [], "side": [], "out": []}
        self.main_table.set_cards([])
        self.side_table.set_cards([])
        self.out_table.set_cards(self.zone_cards["out"])
        self.current_deck_text = ""
        self._update_stats("")
        self.deck_notes_text.ChangeValue("")
        self.guide_view.DeleteAllItems()
        self.guide_exclusions_label.SetLabel("Exclusions: —")

    def _on_archetypes_loaded(self, items: List[Dict[str, Any]]) -> None:
        self.loading_archetypes = False
        self.archetypes = sorted(items, key=lambda entry: entry.get("name", "").lower())
        self.filtered_archetypes = list(self.archetypes)
        self._populate_archetype_list()
        self.archetype_list.Enable()
        count = len(self.archetypes)
        self._set_status(f"Loaded {count} archetypes for {self.current_format}.")
        self.summary_text.ChangeValue(f"Select an archetype to view decks.\nLoaded {count} archetypes.")

    def _on_archetypes_error(self, error: Exception) -> None:
        self.loading_archetypes = False
        self.archetype_list.Clear()
        self.archetype_list.Append("Failed to load archetypes.")
        self._set_status(f"Error: {error}")
        wx.MessageBox(f"Unable to load archetypes:\n{error}", "Archetype Error", wx.OK | wx.ICON_ERROR)

    def _populate_archetype_list(self) -> None:
        self.archetype_list.Clear()
        if not self.filtered_archetypes:
            self.archetype_list.Append("No archetypes found.")
            self.archetype_list.Disable()
            return
        for item in self.filtered_archetypes:
            self.archetype_list.Append(item.get("name", "Unknown"))
        self.archetype_list.Enable()

    def _load_decks_for_archetype(self, archetype: Dict[str, Any]) -> None:
        if self.loading_decks:
            return
        self.loading_decks = True
        name = archetype.get("name", "Unknown")
        href = archetype.get("href")
        self._set_status(f"Loading decks for {name}…")
        self.deck_list.Clear()
        self.deck_list.Append("Loading…")
        self.deck_list.Disable()
        self.summary_text.ChangeValue(f"{name}\n\nFetching deck results…")

        def loader(identifier: str):
            return get_archetype_decks(identifier)

        _Worker(loader, href, on_success=lambda decks: self._on_decks_loaded(name, decks), on_error=self._on_decks_error).start()

    def _on_decks_loaded(self, archetype_name: str, decks: List[Dict[str, Any]]) -> None:
        self.loading_decks = False
        self.decks = decks
        self.deck_list.Clear()
        if not decks:
            self.deck_list.Append("No decks found.")
            self.deck_list.Disable()
            self._set_status(f"No decks for {archetype_name}.")
            self.summary_text.ChangeValue(f"{archetype_name}\n\nNo deck data available.")
            return
        for deck in decks:
            self.deck_list.Append(format_deck_name(deck))
        self.deck_list.Enable()
        self.daily_average_button.Enable()
        self._present_archetype_summary(archetype_name, decks)
        self._set_status(f"Loaded {len(decks)} decks for {archetype_name}. Select one to inspect.")

    def _on_decks_error(self, error: Exception) -> None:
        self.loading_decks = False
        self.deck_list.Clear()
        self.deck_list.Append("Failed to load decks.")
        self._set_status(f"Error loading decks: {error}")
        wx.MessageBox(f"Failed to load deck lists:\n{error}", "Deck Error", wx.OK | wx.ICON_ERROR)

    def _present_archetype_summary(self, archetype_name: str, decks: List[Dict[str, Any]]) -> None:
        by_date: Dict[str, int] = {}
        for deck in decks:
            date = deck.get("date", "").lower()
            by_date[date] = by_date.get(date, 0) + 1
        latest_dates = sorted(by_date.items(), reverse=True)[:7]
        lines = [archetype_name, "", f"Total decks loaded: {len(decks)}", ""]
        if latest_dates:
            lines.append("Recent activity:")
            for day, count in latest_dates:
                lines.append(f"  {day}: {count} deck(s)")
        else:
            lines.append("No recent deck activity.")
        self.summary_text.ChangeValue("\n".join(lines))

    def _download_and_display_deck(self, deck: Dict[str, Any]) -> None:
        deck_number = deck.get("number")
        if not deck_number:
            wx.MessageBox("Deck identifier missing.", "Deck Error", wx.OK | wx.ICON_ERROR)
            return
        self._set_status("Downloading deck…")
        self.load_button.Disable()
        self.copy_button.Disable()
        self.save_button.Disable()

        def worker(number: str):
            download_deck(number)
            return self._read_curr_deck_file()

        def on_success(content: str):
            self._on_deck_content_ready(content, source="mtggoldfish")
            self.load_button.Enable()

        _Worker(worker, deck_number, on_success=on_success, on_error=self._on_deck_download_error).start()

    def _on_deck_download_error(self, error: Exception) -> None:
        self.load_button.Enable()
        self._set_status(f"Deck download failed: {error}")
        wx.MessageBox(f"Failed to download deck:\n{error}", "Deck Download", wx.OK | wx.ICON_ERROR)

    def _on_deck_content_ready(self, deck_text: str, source: str = "manual") -> None:
        self.current_deck_text = deck_text
        stats = analyze_deck(deck_text)
        self.zone_cards["main"] = [{"name": name, "qty": qty} for name, qty in stats["mainboard_cards"]]
        self.zone_cards["side"] = [{"name": name, "qty": qty} for name, qty in stats["sideboard_cards"]]
        self.zone_cards["out"] = self._load_outboard_for_current()
        self.main_table.set_cards(self.zone_cards["main"])
        self.side_table.set_cards(self.zone_cards["side"])
        self.out_table.set_cards(self.zone_cards["out"])
        self._update_stats(deck_text)
        self.copy_button.Enable(True)
        self.save_button.Enable(True)
        self._load_notes_for_current()
        self._load_guide_for_current()
        self._set_status(f"Deck ready ({source}).")
        self._show_left_panel("builder")
        self._schedule_settings_save()

    def _has_deck_loaded(self) -> bool:
        return bool(self.zone_cards["main"] or self.zone_cards["side"])

    # ------------------------------------------------------------------ Collection + card data -----------------------------------------------
    def ensure_card_data_loaded(self) -> None:
        if self.card_data_ready or self.card_data_loading:
            return
        self.card_data_loading = True

        def worker() -> None:
            try:
                manager = CardDataManager()
                manager.ensure_latest()
            except Exception as exc:
                logger.warning(f"Card data preload failed: {exc}")
                wx.CallAfter(self._on_card_data_failed, exc)
                return
            wx.CallAfter(self._on_card_data_ready, manager)

        threading.Thread(target=worker, daemon=True).start()

    def _on_card_data_ready(self, manager: CardDataManager) -> None:
        self.card_manager = manager
        self.card_data_ready = True
        self.card_data_loading = False
        self._set_status("Card database loaded.")
        self._update_stats(self.current_deck_text)

    def _on_card_data_failed(self, error: Exception) -> None:
        self.card_data_ready = False
        self.card_data_loading = False
        self.card_manager = None
        logger.warning(f"Card data unavailable: {error}")

    def _load_collection_from_cache(self) -> bool:
        """Load collection from cached file without calling bridge. Returns True if loaded."""
        files = sorted(DECK_SAVE_DIR.glob("collection_full_trade_*.json"))
        if not files:
            self.collection_inventory = {}
            self.collection_status_label.SetLabel("No collection found. Click 'Refresh Collection' to fetch from MTGO.")
            return False

        latest = files[-1]
        try:
            data = json.loads(latest.read_text(encoding="utf-8"))
            mapping = {entry.get("name", "").lower(): int(entry.get("quantity", 0)) for entry in data if isinstance(entry, dict)}
            self.collection_inventory = mapping
            self.collection_path = latest

            # Show file age in status
            from datetime import datetime
            file_age_seconds = (datetime.now().timestamp() - latest.stat().st_mtime)
            age_hours = int(file_age_seconds / 3600)
            age_str = f"{age_hours}h ago" if age_hours > 0 else "recent"

            self.collection_status_label.SetLabel(f"Collection: {latest.name} ({len(mapping)} entries, {age_str})")
            self.main_table.set_cards(self.zone_cards["main"])
            self.side_table.set_cards(self.zone_cards["side"])
            logger.info(f"Loaded collection from cache: {len(mapping)} unique cards")
            return True
        except Exception as exc:
            logger.warning(f"Failed to load cached collection {latest}: {exc}")
            self.collection_inventory = {}
            self.collection_status_label.SetLabel(f"Collection cache load failed: {exc}")
            return False

    def _refresh_collection_inventory(self, force: bool = False) -> None:
        """Fetch collection from MTGO Bridge and export to JSON."""
        from datetime import datetime
        from utils import mtgo_bridge

        # Check if we already have a recent collection export (unless forced)
        if not force:
            files = sorted(DECK_SAVE_DIR.glob("collection_full_trade_*.json"))
            if files:
                latest = files[-1]
                # Check if file is less than 1 hour old
                try:
                    file_age_seconds = (datetime.now().timestamp() - latest.stat().st_mtime)
                    if file_age_seconds < 3600:  # Less than 1 hour
                        # Load from cache
                        if self._load_collection_from_cache():
                            return
                except Exception as exc:
                    logger.warning(f"Failed to check collection file age: {exc}")

        # Fetch fresh collection from MTGO Bridge
        self.collection_status_label.SetLabel("Fetching collection from MTGO...")
        logger.info("Fetching collection from MTGO Bridge")

        def worker():
            try:
                # Call the bridge to get collection
                collection_data = mtgo_bridge.get_collection_snapshot(timeout=60.0)

                if not collection_data:
                    wx.CallAfter(self._on_collection_fetch_failed, "Bridge returned empty collection")
                    return

                # Export to JSON file with timestamp
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"collection_full_trade_{timestamp}.json"
                filepath = DECK_SAVE_DIR / filename

                # Convert collection data to list format expected by the UI
                # The bridge returns: {"cards": [{"name": "...", "quantity": ...}, ...]}
                cards = collection_data.get("cards", [])
                if not cards:
                    wx.CallAfter(self._on_collection_fetch_failed, "No cards in collection data")
                    return

                # Write to file
                try:
                    with filepath.open("w", encoding="utf-8") as f:
                        json.dump(cards, f, indent=2)
                    logger.info(f"Exported collection to {filepath} ({len(cards)} cards)")
                except Exception as exc:
                    wx.CallAfter(self._on_collection_fetch_failed, f"Failed to write file: {exc}")
                    return

                # Load the newly created file
                wx.CallAfter(self._on_collection_fetched, filepath, cards)

            except FileNotFoundError as exc:
                wx.CallAfter(self._on_collection_fetch_failed, "MTGO Bridge not found. Build the bridge executable.")
                logger.error(f"Bridge not found: {exc}")
            except Exception as exc:
                wx.CallAfter(self._on_collection_fetch_failed, str(exc))
                logger.exception("Failed to fetch collection from bridge")

        threading.Thread(target=worker, daemon=True).start()

    def _on_collection_fetched(self, filepath: Path, cards: list) -> None:
        """Handle successful collection fetch."""
        try:
            mapping = {entry.get("name", "").lower(): int(entry.get("quantity", 0)) for entry in cards if isinstance(entry, dict)}
            self.collection_inventory = mapping
            self.collection_path = filepath
            self.collection_status_label.SetLabel(f"Collection: {filepath.name} ({len(mapping)} entries)")
            self.main_table.set_cards(self.zone_cards["main"])
            self.side_table.set_cards(self.zone_cards["side"])
            logger.info(f"Collection loaded: {len(mapping)} unique cards")
        except Exception as exc:
            logger.exception(f"Failed to process collection data: {exc}")
            self.collection_status_label.SetLabel(f"Collection load failed: {exc}")

    def _on_collection_fetch_failed(self, error_msg: str) -> None:
        """Handle collection fetch failure."""
        self.collection_inventory = {}
        self.collection_status_label.SetLabel(f"Collection fetch failed: {error_msg}")
        logger.warning(f"Collection fetch failed: {error_msg}")

    def _check_and_download_bulk_data(self) -> None:
        """Check if bulk data exists, and download/load in background if needed."""
        from datetime import datetime

        needs_download = False

        if BULK_DATA_CACHE.exists():
            # Check age - if older than 24 hours, download in background
            try:
                age_seconds = datetime.now().timestamp() - BULK_DATA_CACHE.stat().st_mtime
                if age_seconds < 86400:  # Less than 24 hours
                    logger.info(f"Bulk data cache is recent ({age_seconds/3600:.1f}h old)")
                    # Still need to load into memory
                    self._load_bulk_data_into_memory()
                    return
                else:
                    logger.info(f"Bulk data cache is stale ({age_seconds/3600:.1f}h old), updating...")
                    needs_download = True
            except Exception as exc:
                logger.warning(f"Failed to check bulk data age: {exc}")
                return
        else:
            needs_download = True

        if needs_download:
            # Attempt to use any cached printings index while we refresh metadata
            if not self.bulk_data_by_name:
                self._load_bulk_data_into_memory()

            logger.info("Bulk data not found or stale, downloading in background...")
            self._set_status("Downloading card image database...")

            def worker():
                try:
                    if self.image_downloader is None:
                        self.image_downloader = BulkImageDownloader(self.image_cache)

                    success, msg = self.image_downloader.download_bulk_metadata(force=True)

                    if success:
                        wx.CallAfter(self._on_bulk_data_downloaded, msg)
                    else:
                        wx.CallAfter(self._on_bulk_data_failed, msg)

                except Exception as exc:
                    wx.CallAfter(self._on_bulk_data_failed, str(exc))
                    logger.exception("Failed to download bulk data")

            threading.Thread(target=worker, daemon=True).start()

    def _load_bulk_data_into_memory(self, force: bool = False) -> None:
        """Load the compact card printings index in the background."""
        if self.printing_index_loading and not force:
            return
        if self.bulk_data_by_name and not force:
            return
        self.printing_index_loading = True
        self._set_status("Preparing card printings cache…")

        def worker() -> None:
            try:
                payload = ensure_printing_index_cache(force=force)
                data = payload.get("data", {})
                stats = {
                    "unique_names": payload.get("unique_names", len(data)),
                    "total_printings": payload.get("total_printings", sum(len(v) for v in data.values())),
                }
                wx.CallAfter(self._on_bulk_data_loaded, data, stats)
            except Exception as exc:
                wx.CallAfter(self._on_bulk_data_load_failed, str(exc))
                logger.exception("Failed to prepare card printings index")

        threading.Thread(target=worker, daemon=True).start()

    def _on_bulk_data_loaded(self, by_name: Dict[str, List[Dict[str, Any]]], stats: Dict[str, Any]) -> None:
        """Handle successful printings index load."""
        self.printing_index_loading = False
        self.bulk_data_by_name = by_name
        self._set_status("Ready")
        logger.info(
            "Printings index ready: %s names / %s printings",
            stats.get("unique_names"),
            stats.get("total_printings"),
        )

    def _on_bulk_data_load_failed(self, error_msg: str) -> None:
        """Handle printings index loading failure."""
        self.printing_index_loading = False
        self._set_status("Ready")
        logger.warning(f"Card printings index load failed: {error_msg}")

    def _on_bulk_data_downloaded(self, msg: str) -> None:
        """Handle successful bulk data download."""
        self._set_status("Card image database downloaded, indexing printings…")
        logger.info(f"Bulk data downloaded: {msg}")
        # Now rebuild the printings index
        self._load_bulk_data_into_memory(force=True)

    def _on_bulk_data_failed(self, error_msg: str) -> None:
        """Handle bulk data download failure."""
        self._set_status("Ready")
        logger.warning(f"Bulk data download failed: {error_msg}")

    def _show_image_download_dialog(self) -> None:
        """Show dialog for downloading card images with quality selection."""
        dialog = wx.Dialog(self, title="Download Card Images", size=(450, 320))
        dialog.SetBackgroundColour(DARK_BG)

        panel = wx.Panel(dialog)
        panel.SetBackgroundColour(DARK_BG)
        sizer = wx.BoxSizer(wx.VERTICAL)
        panel.SetSizer(sizer)

        # Title
        title = wx.StaticText(panel, label="Download Card Images from Scryfall")
        title.SetForegroundColour(LIGHT_TEXT)
        title_font = title.GetFont()
        title_font.PointSize += 2
        title_font = title_font.Bold()
        title.SetFont(title_font)
        sizer.Add(title, 0, wx.ALL, 10)

        # Image quality selection
        quality_label = wx.StaticText(panel, label="Image Quality:")
        quality_label.SetForegroundColour(LIGHT_TEXT)
        sizer.Add(quality_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)

        quality_choice = wx.Choice(panel, choices=[
            "Small (146x204, ~100KB/card, ~8GB total)",
            "Normal (488x680, ~300KB/card, ~25GB total)",
            "Large (672x936, ~500KB/card, ~40GB total)",
            "PNG (745x1040, ~700KB/card, ~55GB total)"
        ])
        quality_choice.SetSelection(1)  # Default to Normal
        sizer.Add(quality_choice, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # Download amount selection
        amount_label = wx.StaticText(panel, label="Download Amount:")
        amount_label.SetForegroundColour(LIGHT_TEXT)
        sizer.Add(amount_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)

        amount_choice = wx.Choice(panel, choices=[
            "Test mode (first 100 cards)",
            "First 1,000 cards",
            "First 5,000 cards",
            "First 10,000 cards",
            "All cards (~80,000+)"
        ])
        amount_choice.SetSelection(0)  # Default to Test mode
        sizer.Add(amount_choice, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # Info text
        info_text = wx.StaticText(panel, label=(
            "Note: Images are downloaded from Scryfall's CDN (no rate limits).\n"
            "This may take 30-60 minutes for all cards depending on your connection.\n"
            "You can use the app while downloading."
        ))
        info_text.SetForegroundColour(SUBDUED_TEXT)
        info_text.Wrap(420)
        sizer.Add(info_text, 0, wx.ALL, 10)

        # Buttons
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        button_sizer.AddStretchSpacer(1)

        cancel_btn = wx.Button(panel, wx.ID_CANCEL, label="Cancel")
        button_sizer.Add(cancel_btn, 0, wx.RIGHT, 6)

        download_btn = wx.Button(panel, wx.ID_OK, label="Download")
        download_btn.SetDefault()
        button_sizer.Add(download_btn, 0)

        sizer.Add(button_sizer, 0, wx.EXPAND | wx.ALL, 10)

        panel.SetSizerAndFit(sizer)
        dialog.SetClientSize(panel.GetBestSize())
        dialog.Centre()

        if dialog.ShowModal() == wx.ID_OK:
            # Get selected quality
            quality_map = {0: "small", 1: "normal", 2: "large", 3: "png"}
            quality = quality_map[quality_choice.GetSelection()]

            # Get selected amount
            amount_map = {0: 100, 1: 1000, 2: 5000, 3: 10000, 4: None}
            max_cards = amount_map[amount_choice.GetSelection()]

            # Start download
            self._start_image_download(quality, max_cards)

        dialog.Destroy()

    def _start_image_download(self, size: str, max_cards: Optional[int]) -> None:
        """Start downloading card images with progress dialog."""
        # Create progress dialog
        max_value = max_cards if max_cards else 80000
        progress_dialog = wx.ProgressDialog(
            "Downloading Card Images",
            "Preparing download...",
            maximum=max_value,
            parent=self,
            style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE | wx.PD_CAN_ABORT | wx.PD_ELAPSED_TIME | wx.PD_REMAINING_TIME
        )

        # Track cancellation
        download_cancelled = [False]

        def progress_callback(completed: int, total: int, message: str):
            """Update progress dialog from worker thread."""
            wx.CallAfter(self._update_download_progress, progress_dialog, completed, total, message, download_cancelled)

        def worker():
            """Background download worker."""
            try:
                if self.image_downloader is None:
                    self.image_downloader = BulkImageDownloader(self.image_cache)

                # Ensure bulk data is downloaded
                if not BULK_DATA_CACHE.exists():
                    wx.CallAfter(progress_dialog.Update, 0, "Downloading bulk metadata first...")
                    success, msg = self.image_downloader.download_bulk_metadata(force=False)
                    if not success:
                        wx.CallAfter(self._on_image_download_failed, progress_dialog, f"Failed to download metadata: {msg}")
                        return

                # Download images
                result = self.image_downloader.download_all_images(
                    size=size,
                    max_cards=max_cards,
                    progress_callback=progress_callback
                )

                # Check if cancelled
                if download_cancelled[0]:
                    wx.CallAfter(self._on_image_download_cancelled, progress_dialog)
                elif result.get("success"):
                    wx.CallAfter(self._on_image_download_complete, progress_dialog, result)
                else:
                    wx.CallAfter(self._on_image_download_failed, progress_dialog, result.get("error", "Unknown error"))

            except Exception as exc:
                logger.exception("Image download failed")
                wx.CallAfter(self._on_image_download_failed, progress_dialog, str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _update_download_progress(self, dialog: wx.ProgressDialog, completed: int, total: int, message: str, cancelled_flag: list):
        """Update progress dialog (called from main thread via wx.CallAfter)."""
        if not dialog:
            return

        try:
            # Check if dialog still exists
            _ = dialog.GetTitle()
        except RuntimeError:
            # Dialog was destroyed
            cancelled_flag[0] = True
            return

        # Update progress
        continue_download, skip = dialog.Update(completed, message)
        if not continue_download:
            # User clicked cancel
            cancelled_flag[0] = True
            dialog.Destroy()

    def _on_image_download_complete(self, dialog: wx.ProgressDialog, result: Dict[str, Any]):
        """Handle successful image download."""
        try:
            dialog.Destroy()
        except RuntimeError:
            pass

        msg = (
            f"Download complete!\n\n"
            f"Total processed: {result.get('total', 0)}\n"
            f"Downloaded: {result.get('downloaded', 0)}\n"
            f"Already cached: {result.get('skipped', 0)}\n"
            f"Failed: {result.get('failed', 0)}"
        )
        wx.MessageBox(msg, "Download Complete", wx.OK | wx.ICON_INFORMATION)
        self._set_status("Card image download complete")

    def _on_image_download_failed(self, dialog: wx.ProgressDialog, error_msg: str):
        """Handle image download failure."""
        try:
            dialog.Destroy()
        except RuntimeError:
            pass

        wx.MessageBox(f"Download failed: {error_msg}", "Download Error", wx.OK | wx.ICON_ERROR)
        self._set_status("Ready")

    def _on_image_download_cancelled(self, dialog: wx.ProgressDialog):
        """Handle image download cancellation."""
        try:
            dialog.Destroy()
        except RuntimeError:
            pass

        self._set_status("Card image download cancelled")

    def _get_card_metadata(self, name: str) -> Optional[Dict[str, Any]]:
        if not self.card_manager:
            return None
        return self.card_manager.get_card(name)

    def _owned_status(self, name: str, required: int) -> tuple[str, wx.Colour]:
        if not self.collection_inventory:
            return ("Owned —", SUBDUED_TEXT)
        have = self.collection_inventory.get(name.lower(), 0)
        if have >= required:
            return (f"Owned {have}/{required}", wx.Colour(120, 200, 120))
        if have > 0:
            return (f"Owned {have}/{required}", wx.Colour(230, 200, 90))
        return ("Owned 0", wx.Colour(230, 120, 120))

    # ------------------------------------------------------------------ Zone editing ---------------------------------------------------------
    def _handle_zone_delta(self, zone: str, name: str, delta: int) -> None:
        cards = self.zone_cards.get(zone, [])
        for entry in cards:
            if entry["name"].lower() == name.lower():
                entry["qty"] = max(0, entry["qty"] + delta)
                if entry["qty"] == 0:
                    cards.remove(entry)
                break
        else:
            if delta > 0:
                cards.append({"name": name, "qty": delta})
        cards.sort(key=lambda item: item["name"].lower())
        self.zone_cards[zone] = cards
        self._after_zone_change(zone)

    def _handle_zone_remove(self, zone: str, name: str) -> None:
        cards = self.zone_cards.get(zone, [])
        self.zone_cards[zone] = [entry for entry in cards if entry["name"].lower() != name.lower()]
        self._after_zone_change(zone)

    def _handle_zone_add(self, zone: str) -> None:
        if zone == "out":
            main_cards = [entry["name"] for entry in self.zone_cards.get("main", [])]
            existing = {entry["name"].lower() for entry in self.zone_cards.get("out", [])}
            candidates = [name for name in main_cards if name.lower() not in existing]
            if not candidates:
                wx.MessageBox("All mainboard cards are already in the outboard list.", "Outboard", wx.OK | wx.ICON_INFORMATION)
                return
            dlg = wx.SingleChoiceDialog(self, "Select a mainboard card eligible for sideboarding.", "Outboard", candidates)
            if dlg.ShowModal() != wx.ID_OK:
                dlg.Destroy()
                return
            selection = dlg.GetStringSelection()
            dlg.Destroy()
            qty = next((entry["qty"] for entry in self.zone_cards["main"] if entry["name"] == selection), 1)
            self.zone_cards.setdefault("out", []).append({"name": selection, "qty": qty})
            self.zone_cards["out"].sort(key=lambda item: item["name"].lower())
            self._after_zone_change("out")
            return

        dlg = wx.TextEntryDialog(self, f"Add card to {ZONE_TITLES.get(zone, zone)} (format: 'Qty Card Name')", "Add Card")
        if dlg.ShowModal() != wx.ID_OK:
            dlg.Destroy()
            return
        value = dlg.GetValue().strip()
        dlg.Destroy()
        if not value:
            return
        parts = value.split(" ", 1)
        try:
            qty = int(parts[0]) if len(parts) > 1 else 1
        except ValueError:
            qty = 1
        name = parts[1].strip() if len(parts) > 1 else value
        if not name:
            return
        self.zone_cards.setdefault(zone, []).append({"name": name, "qty": max(1, qty)})
        self.zone_cards[zone].sort(key=lambda item: item["name"].lower())
        self._after_zone_change(zone)

    def _after_zone_change(self, zone: str) -> None:
        if zone == "main":
            self.main_table.set_cards(self.zone_cards["main"])
        elif zone == "side":
            self.side_table.set_cards(self.zone_cards["side"])
        else:
            self.out_table.set_cards(self.zone_cards["out"])
            self._persist_outboard_for_current()
        self.current_deck_text = self._build_deck_text()
        self._update_stats(self.current_deck_text)
        self.copy_button.Enable(self._has_deck_loaded())
        self.save_button.Enable(self._has_deck_loaded())
        self._schedule_settings_save()

    # ------------------------------------------------------------------ Card inspector -----------------------------------------------------
    def _handle_card_focus(self, zone: str, card: Optional[Dict[str, Any]]) -> None:
        if card is None:
            if self.active_inspector_zone == zone:
                self._reset_card_inspector()
            return
        self._collapse_other_zone_tables(zone)
        self._update_card_inspector(zone, card)

    def _collapse_other_zone_tables(self, active_zone: str) -> None:
        tables = {
            "main": self.main_table,
            "side": self.side_table,
            "out": self.out_table,
        }
        for zone, table in tables.items():
            if zone == active_zone:
                continue
            table.collapse_active()

    def _reset_card_inspector(self) -> None:
        self.active_inspector_zone = None
        self.inspector_name.SetLabel("Select a card to inspect.")
        self.inspector_type.SetLabel("")
        self.inspector_stats.SetLabel("")
        self.inspector_text.ChangeValue("")
        self._render_inspector_cost("")
        # Show placeholder with new widget
        self.card_image_display.show_placeholder("Select a card")
        self.inspector_nav_panel.Hide()
        self.inspector_printings = []
        self.inspector_current_printing = 0
        self.inspector_current_card_name = None
        _log_card_inspector("reset")

    def _update_card_inspector(self, zone: Optional[str], card: Dict[str, Any], meta: Optional[Dict[str, Any]] = None) -> None:
        self.active_inspector_zone = zone
        zone_title = ZONE_TITLES.get(zone, zone.title()) if zone else "Card Search"
        header = f"{card['name']}  ×{card['qty']}  ({zone_title})"
        self.inspector_name.SetLabel(header)
        meta = meta or self._get_card_metadata(card["name"]) or {}
        mana_cost = meta.get("mana_cost") or ""
        self._render_inspector_cost(mana_cost)
        type_line = meta.get("type_line") or "Type data unavailable."
        self.inspector_type.SetLabel(type_line)
        stats_bits: List[str] = []
        if meta.get("mana_value") is not None:
            stats_bits.append(f"MV {meta['mana_value']}")
        if meta.get("power") or meta.get("toughness"):
            stats_bits.append(f"P/T {meta.get('power', '?')}/{meta.get('toughness', '?')}")
        if meta.get("loyalty"):
            stats_bits.append(f"Loyalty {meta['loyalty']}")
        colors = meta.get("color_identity") or []
        stats_bits.append(f"Colors: {'/'.join(colors) if colors else 'Colorless'}")
        stats_bits.append(f"Zone: {zone_title}")
        self.inspector_stats.SetLabel("  |  ".join(stats_bits))
        oracle_text = meta.get("oracle_text") or "No rules text available."
        self.inspector_text.ChangeValue(oracle_text)

        # Load card image and printings
        self._load_card_image_and_printings(card["name"])

    def _render_inspector_cost(self, mana_cost: str) -> None:
        self.inspector_cost_sizer.Clear(delete_windows=True)
        if mana_cost:
            panel = self.mana_icons.render(self.inspector_cost_container, mana_cost)
            panel.SetMinSize((max(32, panel.GetBestSize().width), 32))
        else:
            panel = wx.StaticText(self.inspector_cost_container, label="—")
            panel.SetForegroundColour(SUBDUED_TEXT)
        self.inspector_cost_sizer.Add(panel, 0)
        self.inspector_cost_container.Layout()

    def _load_card_image_and_printings(self, card_name: str) -> None:
        """Load card image and populate printings list (uses in-memory cache)."""
        self.inspector_current_card_name = card_name
        self.inspector_printings = []
        self.inspector_current_printing = 0
        _log_card_inspector("load_card", card_name, f"bulk_loaded={bool(self.bulk_data_by_name)}")

        # Query in-memory bulk data for all printings of this card (non-blocking)
        if self.bulk_data_by_name:
            # Fast O(1) lookup from pre-indexed dictionary
            printings = self.bulk_data_by_name.get(card_name.lower(), [])
            self.inspector_printings = printings
            _log_card_inspector("printings_found", card_name, f"count={len(printings)}")
        elif BULK_DATA_CACHE.exists():
            # Fallback: bulk data not loaded yet, show placeholder
            logger.debug(f"Bulk data not loaded yet for {card_name}, showing placeholder")
            _log_card_inspector("bulk_missing_in_memory", card_name)

        # Try to load an image
        self._load_current_printing_image()

    def _load_current_printing_image(self) -> None:
        """Load and display the current printing's image."""
        if not self.inspector_printings:
            # No printings found, try to load any cached image for this card name
            image_path = get_card_image(self.inspector_current_card_name, "normal")
            exists = image_path.exists() if image_path else False
            _log_card_inspector(
                "fallback_by_name",
                self.inspector_current_card_name or "<unknown>",
                f"path={image_path}",
                f"exists={exists}",
            )
            if image_path:
                self.card_image_display.show_image(image_path)
                self.inspector_nav_panel.Hide()
            else:
                # No image available, show placeholder
                self.card_image_display.show_placeholder("Not cached")
                self.inspector_nav_panel.Hide()
            return

        # Get current printing
        printing = self.inspector_printings[self.inspector_current_printing]
        uuid = printing.get("id")
        _log_card_inspector(
            "printing_selected",
            self.inspector_current_card_name or "<unknown>",
            f"index={self.inspector_current_printing}",
            f"uuid={uuid}",
        )

        # Try to load from cache
        image_path = self.image_cache.get_image_by_uuid(uuid, "normal")
        _log_card_inspector(
            "uuid_lookup",
            self.inspector_current_card_name or "<unknown>",
            f"uuid={uuid}",
            f"path={image_path}",
        )

        if image_path:
            self.card_image_display.show_image(image_path)
        else:
            # Image not cached, show placeholder
            self.card_image_display.show_placeholder("Not cached")

        # Update navigation controls
        if len(self.inspector_printings) > 1:
            set_code = printing.get("set", "").upper()
            set_name = printing.get("set_name", "")
            printing_info = f"{self.inspector_current_printing + 1} of {len(self.inspector_printings)}"
            if set_code:
                printing_info += f" - {set_code}"
            if set_name:
                printing_info += f" ({set_name})"
            self.inspector_printing_label.SetLabel(printing_info)
            self.inspector_prev_btn.Enable(self.inspector_current_printing > 0)
            self.inspector_next_btn.Enable(self.inspector_current_printing < len(self.inspector_printings) - 1)
            self.inspector_nav_panel.Show()
        else:
            self.inspector_nav_panel.Hide()

    def _on_prev_printing(self) -> None:
        """Navigate to previous printing."""
        if self.inspector_current_printing > 0:
            self.inspector_current_printing -= 1
            self._load_current_printing_image()

    def _on_next_printing(self) -> None:
        """Navigate to next printing."""
        if self.inspector_current_printing < len(self.inspector_printings) - 1:
            self.inspector_current_printing += 1
            self._load_current_printing_image()

    # ------------------------------------------------------------------ Stats + notes --------------------------------------------------------
    def _update_stats(self, deck_text: str) -> None:
        if not deck_text.strip():
            self.stats_summary.SetLabel("No deck loaded.")
            self.curve_list.DeleteAllItems()
            self.color_list.DeleteAllItems()
            return
        stats = analyze_deck(deck_text)
        summary = (
            f"Mainboard: {stats['mainboard_count']} cards ({stats['unique_mainboard']} unique)  |  "
            f"Sideboard: {stats['sideboard_count']} cards ({stats['unique_sideboard']} unique)  |  "
            f"Estimated lands: {stats['estimated_lands']}"
        )
        self.stats_summary.SetLabel(summary)
        self._render_curve()
        self._render_color_concentration()

    def _render_curve(self) -> None:
        self.curve_list.DeleteAllItems()
        if not self.card_manager:
            return
        counts: Counter[str] = Counter()
        for entry in self.zone_cards.get("main", []):
            meta = self.card_manager.get_card(entry["name"])
            mana_value = meta.get("mana_value") if meta else None
            bucket: str
            if isinstance(mana_value, (int, float)):
                value = int(mana_value)
                bucket = "7+" if value >= 7 else str(value)
            else:
                bucket = "X"
            counts[bucket] += entry["qty"]
        def curve_key(bucket: str) -> int:
            if bucket == "X":
                return 99
            if bucket.endswith("+") and bucket[:-1].isdigit():
                return int(bucket[:-1]) + 10
            if bucket.isdigit():
                return int(bucket)
            return 98

        for bucket in sorted(counts.keys(), key=curve_key):
            self.curve_list.AppendItem([bucket, str(counts[bucket])])

    def _render_color_concentration(self) -> None:
        self.color_list.DeleteAllItems()
        if not self.card_manager:
            return
        totals: Counter[str] = Counter()
        for entry in self.zone_cards.get("main", []):
            meta = self.card_manager.get_card(entry["name"])
            identity = meta.get("color_identity") if meta else []
            if not identity:
                totals["Colorless"] += entry["qty"]
            else:
                for color in identity:
                    totals[color.upper()] += entry["qty"]
        grand_total = sum(totals.values())
        if not grand_total:
            return
        for color, count in sorted(totals.items(), key=lambda item: item[0]):
            pct = (count / grand_total) * 100
            label = f"{pct:.1f}% ({count})"
            self.color_list.AppendItem([color, label])

    def _load_notes_for_current(self) -> None:
        key = self._current_deck_key()
        note = self.deck_notes_store.get(key, "")
        self.deck_notes_text.ChangeValue(note)

    def _save_current_notes(self) -> None:
        key = self._current_deck_key()
        self.deck_notes_store[key] = self.deck_notes_text.GetValue()
        self._save_store(NOTES_STORE, self.deck_notes_store)
        self._set_status("Deck notes saved.")

    # ------------------------------------------------------------------ Outboard + guide persistence -----------------------------------------
    def _persist_outboard_for_current(self) -> None:
        key = self._current_deck_key()
        self.outboard_store[key] = self.zone_cards.get("out", [])
        self._save_store(OUTBOARD_STORE, self.outboard_store)

    def _load_outboard_for_current(self) -> List[Dict[str, Any]]:
        key = self._current_deck_key()
        data = self.outboard_store.get(key, [])
        cleaned: List[Dict[str, Any]] = []
        for entry in data:
            name = entry.get("name")
            qty = int(entry.get("qty", 0))
            if name and qty > 0:
                cleaned.append({"name": name, "qty": qty})
        return cleaned

    def _load_guide_for_current(self) -> None:
        key = self._current_deck_key()
        payload = self.guide_store.get(key) or {}
        self.sideboard_guide_entries = payload.get("entries", [])
        self.sideboard_exclusions = payload.get("exclusions", [])
        self._refresh_guide_view()

    def _persist_guide_for_current(self) -> None:
        key = self._current_deck_key()
        self.guide_store[key] = {
            "entries": self.sideboard_guide_entries,
            "exclusions": self.sideboard_exclusions,
        }
        self._save_store(GUIDE_STORE, self.guide_store)

    def _refresh_guide_view(self) -> None:
        self.guide_view.DeleteAllItems()
        for entry in self.sideboard_guide_entries:
            if entry.get("archetype") in self.sideboard_exclusions:
                continue
            self.guide_view.AppendItem(
                [
                    entry.get("archetype", ""),
                    entry.get("cards_in", ""),
                    entry.get("cards_out", ""),
                    entry.get("notes", ""),
                ]
            )
        if self.sideboard_exclusions:
            text = ", ".join(self.sideboard_exclusions)
        else:
            text = "—"
        self.guide_exclusions_label.SetLabel(f"Exclusions: {text}")

    def _on_add_guide_entry(self) -> None:
        names = [item.get("name", "") for item in self.archetypes]
        dlg = GuideEntryDialog(self, names)
        if dlg.ShowModal() == wx.ID_OK:
            data = dlg.get_data()
            if data.get("archetype"):
                self.sideboard_guide_entries.append(data)
                self._persist_guide_for_current()
                self._refresh_guide_view()
        dlg.Destroy()

    def _on_edit_guide_entry(self) -> None:
        item = self.guide_view.GetSelection()
        if not item.IsOk():
            wx.MessageBox("Select an entry to edit.", "Sideboard Guide", wx.OK | wx.ICON_INFORMATION)
            return
        index = self.guide_view.ItemToRow(item)
        data = self.sideboard_guide_entries[index]
        names = [item.get("name", "") for item in self.archetypes]
        dlg = GuideEntryDialog(self, names, data=data)
        if dlg.ShowModal() == wx.ID_OK:
            updated = dlg.get_data()
            if updated.get("archetype"):
                self.sideboard_guide_entries[index] = updated
                self._persist_guide_for_current()
                self._refresh_guide_view()
        dlg.Destroy()

    def _on_remove_guide_entry(self) -> None:
        item = self.guide_view.GetSelection()
        if not item.IsOk():
            wx.MessageBox("Select an entry to remove.", "Sideboard Guide", wx.OK | wx.ICON_INFORMATION)
            return
        index = self.guide_view.ItemToRow(item)
        del self.sideboard_guide_entries[index]
        self._persist_guide_for_current()
        self._refresh_guide_view()

    def _on_edit_exclusions(self) -> None:
        archetype_names = [item.get("name", "") for item in self.archetypes]
        dlg = wx.MultiChoiceDialog(
            self,
            "Select archetypes to exclude from the printed guide.",
            "Sideboard Guide",
            archetype_names,
        )
        selected_indices = [archetype_names.index(name) for name in self.sideboard_exclusions if name in archetype_names]
        dlg.SetSelections(selected_indices)
        if dlg.ShowModal() == wx.ID_OK:
            selections = dlg.GetSelections()
            self.sideboard_exclusions = [archetype_names[idx] for idx in selections]
            self._persist_guide_for_current()
            self._refresh_guide_view()
        dlg.Destroy()

    # ------------------------------------------------------------------ Guide / notes helpers ------------------------------------------------
    def _load_store(self, path: Path) -> Dict[str, Any]:
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON at {path}; ignoring store")
            return {}

    def _save_store(self, path: Path, data: Dict[str, Any]) -> None:
        try:
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except OSError as exc:
            logger.warning(f"Failed to write {path}: {exc}")

    # ------------------------------------------------------------------ Daily average --------------------------------------------------------
    def _build_daily_average_deck(self) -> None:
        today = time.strftime("%Y-%m-%d").lower()
        todays_decks = [deck for deck in self.decks if today in deck.get("date", "").lower()]

        if not todays_decks:
            wx.MessageBox("No decks from today found for this archetype.", "Daily Average", wx.OK | wx.ICON_INFORMATION)
            return

        self.loading_daily_average = True
        self.daily_average_button.Disable()
        self._set_status("Building daily average deck…")
        progress_dialog = wx.ProgressDialog(
            "Daily Average",
            "Downloading decks…",
            maximum=len(todays_decks),
            parent=self,
            style=wx.PD_APP_MODAL | wx.PD_ELAPSED_TIME,
        )

        def worker(rows: List[Dict[str, Any]]):
            buffer: Dict[str, float] = {}
            for index, deck in enumerate(rows, start=1):
                download_deck(deck["number"])
                deck_content = self._read_curr_deck_file()
                buffer = add_dicts(buffer, deck_to_dictionary(deck_content))
                wx.CallAfter(progress_dialog.Update, index, f"Processed {index}/{len(rows)} decks…")
            return buffer

        def on_success(buffer: Dict[str, float]):
            progress_dialog.Destroy()
            self.loading_daily_average = False
            self.daily_average_button.Enable()
            deck_text = self._render_average_deck(buffer, len(todays_decks))
            self._on_deck_content_ready(deck_text, source="average")

        def on_error(error: Exception):
            progress_dialog.Destroy()
            self.loading_daily_average = False
            self.daily_average_button.Enable()
            wx.MessageBox(f"Failed to build daily average:\n{error}", "Daily Average", wx.OK | wx.ICON_ERROR)
            self._set_status(f"Daily average failed: {error}")

        _Worker(worker, todays_decks, on_success=on_success, on_error=on_error).start()

    def _render_average_deck(self, buffer: Dict[str, float], decks_added: int) -> str:
        if not buffer or decks_added <= 0:
            return ""
        lines: List[str] = []
        sideboard_lines: List[str] = []
        for card, total in sorted(buffer.items(), key=lambda kv: (kv[0].startswith("Sideboard"), kv[0])):
            display_name = card.replace("Sideboard ", "")
            average = float(total) / decks_added
            value = f"{average:.2f}" if not average.is_integer() else str(int(average))
            output = f"{value} {display_name}"
            if card.lower().startswith("sideboard"):
                sideboard_lines.append(output)
            else:
                lines.append(output)
        if sideboard_lines:
            lines.append("")
            lines.extend(sideboard_lines)
        return "\n".join(lines)

    def _read_curr_deck_file(self) -> str:
        candidates = [CURR_DECK_FILE, LEGACY_CURR_DECK_CACHE, LEGACY_CURR_DECK_ROOT]
        for candidate in candidates:
            if candidate.exists():
                with candidate.open("r", encoding="utf-8") as fh:
                    contents = fh.read()
                if candidate != CURR_DECK_FILE:
                    try:
                        CURR_DECK_FILE.parent.mkdir(parents=True, exist_ok=True)
                        with CURR_DECK_FILE.open("w", encoding="utf-8") as target:
                            target.write(contents)
                        try:
                            candidate.unlink()
                        except OSError:
                            logger.debug(f"Unable to remove legacy deck file {candidate}")
                    except OSError as exc:  # pragma: no cover
                        logger.debug(f"Failed to migrate curr_deck.txt from {candidate}: {exc}")
                return contents
        raise FileNotFoundError("Current deck file not found")

    # ------------------------------------------------------------------ Helpers --------------------------------------------------------------
    def _build_deck_text(self) -> str:
        if not self.zone_cards["main"] and not self.zone_cards["side"]:
            return ""
        lines: List[str] = []
        for entry in self.zone_cards["main"]:
            lines.append(f"{entry['qty']} {entry['name']}")
        if self.zone_cards["side"]:
            lines.append("")
            lines.append("Sideboard")
            for entry in self.zone_cards["side"]:
                lines.append(f"{entry['qty']} {entry['name']}")
        return "\n".join(lines).strip()

    def _current_deck_key(self) -> str:
        if self.current_deck:
            return self.current_deck.get("href") or self.current_deck.get("name", "manual").lower()
        return "manual"

    def _widget_exists(self, window: Optional[wx.Window]) -> bool:
        if window is None:
            return False
        try:
            return bool(window.IsShown())
        except wx.PyDeadObjectError:
            return False

    def open_opponent_tracker(self) -> None:
        if self._widget_exists(self.tracker_window):
            self.tracker_window.Raise()
            return
        try:
            self.tracker_window = MTGOpponentDeckSpyWx(self)
            self.tracker_window.Bind(wx.EVT_CLOSE, lambda evt: self._handle_child_close(evt, "tracker_window"))
            self.tracker_window.Show()
        except Exception as exc:
            logger.error(f"Failed to launch opponent tracker: {exc}")
            wx.MessageBox(f"Unable to launch opponent tracker:\n{exc}", "Opponent Tracker", wx.OK | wx.ICON_ERROR)

    def open_timer_alert(self) -> None:
        if self._widget_exists(self.timer_window):
            self.timer_window.Raise()
            return
        try:
            self.timer_window = TimerAlertFrame(self)
            self.timer_window.Bind(wx.EVT_CLOSE, lambda evt: self._handle_child_close(evt, "timer_window"))
            self.timer_window.Show()
        except Exception as exc:
            logger.error(f"Failed to open timer alert: {exc}")
            wx.MessageBox(f"Unable to open timer alert:\n{exc}", "Timer Alert", wx.OK | wx.ICON_ERROR)

    def open_match_history(self) -> None:
        if self._widget_exists(self.history_window):
            self.history_window.Raise()
            return
        try:
            self.history_window = MatchHistoryFrame(self)
            self.history_window.Bind(wx.EVT_CLOSE, lambda evt: self._handle_child_close(evt, "history_window"))
            self.history_window.Show()
        except Exception as exc:
            logger.error(f"Failed to open match history: {exc}")
            wx.MessageBox(f"Unable to open match history:\n{exc}", "Match History", wx.OK | wx.ICON_ERROR)

    def _handle_child_close(self, event: wx.CloseEvent, attr: str) -> None:
        setattr(self, attr, None)
        event.Skip()

    # ------------------------------------------------------------------ Lifecycle ------------------------------------------------------------
    def on_close(self, event: wx.CloseEvent) -> None:
        if self._save_timer and self._save_timer.IsRunning():
            self._save_timer.Stop()
        self._save_window_settings()
        for attr in ("tracker_window", "timer_window", "history_window"):
            window = getattr(self, attr)
            if self._widget_exists(window):
                window.Destroy()
                setattr(self, attr, None)
        if self.mana_keyboard_window and self.mana_keyboard_window.IsShown():
            self.mana_keyboard_window.Destroy()
            self.mana_keyboard_window = None
        event.Skip()


def launch_wx_app() -> None:
    app = wx.App(False)
    frame = MTGDeckSelectionFrame()
    frame.Show()
    app.MainLoop()


__all__ = ["MTGDeckSelectionFrame", "launch_wx_app"]
