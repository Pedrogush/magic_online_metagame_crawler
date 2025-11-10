from __future__ import annotations

import sys
import time as time_module
from pathlib import Path

import pytest

if sys.platform != "win32":
    pytest.skip("wxPython UI tests must run on Windows", allow_module_level=True)

import navigators.mtggoldfish as mtggoldfish
import utils.card_images as card_images
import utils.paths as paths
import widgets.deck_selector as deck_selector
import widgets.identify_opponent as identify_opponent
from utils.card_data import CardDataManager
from widgets.deck_selector import MTGDeckSelectionFrame

wx = pytest.importorskip("wx")


SAMPLE_CARDS = [
    {
        "name": "Mountain",
        "name_lower": "mountain",
        "mana_value": 0,
        "color_identity": ["R"],
        "type_line": "Basic Land — Mountain",
        "mana_cost": "",
        "oracle_text": "({T}: Add {R}.)",
        "legalities": {"modern": "Legal"},
    },
    {
        "name": "Island",
        "name_lower": "island",
        "mana_value": 0,
        "color_identity": ["U"],
        "type_line": "Basic Land — Island",
        "mana_cost": "",
        "oracle_text": "({T}: Add {U}.)",
        "legalities": {"modern": "Legal"},
    },
]


def _ensure_dirs(*dirs: Path) -> None:
    for directory in dirs:
        directory.mkdir(parents=True, exist_ok=True)


@pytest.fixture(scope="session", name="wx_app")
def fixture_wx_app() -> wx.App:
    """Create a shared wx App for all UI tests."""
    if wx is None:
        pytest.skip("wxPython is required for UI tests", allow_module_level=True)
    app = wx.App(False)
    yield app
    app.Destroy()


@pytest.fixture(autouse=True)
def ui_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate filesystem paths and make background workers deterministic."""
    root = tmp_path / "mtgo"
    config = root / "config"
    cache = root / "cache"
    decks = root / "decks"
    image_cache = cache / "card_images"
    _ensure_dirs(config, cache, decks, image_cache)

    replacements = {
        "CONFIG_DIR": config,
        "CACHE_DIR": cache,
        "DECKS_DIR": decks,
        "CONFIG_FILE": config / "config.json",
        "DECK_SELECTOR_SETTINGS_FILE": config / "deck_selector_settings.json",
        "DECK_MONITOR_CONFIG_FILE": config / "deck_monitor_config.json",
        "DECK_MONITOR_CACHE_FILE": cache / "deck_monitor_cache.json",
        "ARCHETYPE_CACHE_FILE": cache / "archetype_cache.json",
        "ARCHETYPE_LIST_CACHE_FILE": cache / "archetype_list.json",
        "MTGO_ARTICLES_CACHE_FILE": cache / "mtgo_articles.json",
        "MTGO_DECK_CACHE_FILE": cache / "mtgo_decks.json",
        "DECK_CACHE_FILE": cache / "deck_cache.json",
        "CURR_DECK_FILE": decks / "curr_deck.txt",
    }
    for attr, value in replacements.items():
        monkeypatch.setattr(paths, attr, value, raising=False)

    monkeypatch.setattr(card_images, "IMAGE_CACHE_DIR", image_cache, raising=False)
    monkeypatch.setattr(card_images, "IMAGE_DB_PATH", image_cache / "images.db", raising=False)
    monkeypatch.setattr(
        card_images, "BULK_DATA_CACHE", image_cache / "bulk_data.json", raising=False
    )
    monkeypatch.setattr(
        card_images, "PRINTING_INDEX_CACHE", image_cache / "printings_v1.json", raising=False
    )

    def fake_ensure_latest(self: CardDataManager, force: bool = False) -> None:
        self._cards = SAMPLE_CARDS
        self._cards_by_name = {card["name_lower"]: card for card in SAMPLE_CARDS}

    def fake_get_card(self: CardDataManager, name: str) -> dict[str, object] | None:
        lookup = self._cards_by_name or {}
        return lookup.get(name.lower())

    def fake_search_cards(
        self: CardDataManager, query: str = "", **kwargs
    ) -> list[dict[str, object]]:
        needle = (query or "").strip().lower()
        cards = self._cards or []
        return [card for card in cards if needle in card.get("name_lower", "")]

    monkeypatch.setattr(CardDataManager, "ensure_latest", fake_ensure_latest, raising=False)
    monkeypatch.setattr(CardDataManager, "get_card", fake_get_card, raising=False)
    monkeypatch.setattr(CardDataManager, "search_cards", fake_search_cards, raising=False)

    monkeypatch.setattr(
        deck_selector,
        "CONFIG_FILE",
        replacements["CONFIG_FILE"],
        raising=False,
    )
    monkeypatch.setattr(
        deck_selector,
        "DECK_SELECTOR_SETTINGS_FILE",
        replacements["DECK_SELECTOR_SETTINGS_FILE"],
        raising=False,
    )
    monkeypatch.setattr(
        deck_selector,
        "NOTES_STORE",
        cache / "deck_notes.json",
        raising=False,
    )
    monkeypatch.setattr(
        deck_selector,
        "OUTBOARD_STORE",
        cache / "deck_outboard.json",
        raising=False,
    )
    monkeypatch.setattr(
        deck_selector,
        "GUIDE_STORE",
        cache / "deck_sbguides.json",
        raising=False,
    )
    monkeypatch.setattr(
        deck_selector,
        "LEGACY_NOTES_STORE",
        cache / "deck_notes_wx.json",
        raising=False,
    )
    monkeypatch.setattr(
        deck_selector,
        "LEGACY_OUTBOARD_STORE",
        cache / "deck_outboard_wx.json",
        raising=False,
    )
    monkeypatch.setattr(
        deck_selector,
        "LEGACY_GUIDE_STORE",
        cache / "deck_sbguides_wx.json",
        raising=False,
    )
    monkeypatch.setattr(
        deck_selector,
        "MANA_RENDER_LOG",
        cache / "mana_render.log",
        raising=False,
    )
    monkeypatch.setattr(
        deck_selector,
        "CARD_INSPECTOR_LOG",
        cache / "card_inspector_debug.log",
        raising=False,
    )
    monkeypatch.setattr(
        deck_selector,
        "LEGACY_CONFIG_FILE",
        config / "legacy_config.json",
        raising=False,
    )
    monkeypatch.setattr(
        deck_selector,
        "LEGACY_CURR_DECK_CACHE",
        cache / "curr_deck.txt",
        raising=False,
    )
    monkeypatch.setattr(
        deck_selector,
        "LEGACY_CURR_DECK_ROOT",
        decks / "curr_deck.txt",
        raising=False,
    )

    monkeypatch.setattr(
        identify_opponent,
        "LEGACY_DECK_MONITOR_CONFIG",
        config / "deck_monitor_config.json",
        raising=False,
    )
    monkeypatch.setattr(
        identify_opponent,
        "LEGACY_DECK_MONITOR_CACHE",
        cache / "deck_monitor_cache.json",
        raising=False,
    )
    monkeypatch.setattr(
        identify_opponent,
        "LEGACY_DECK_MONITOR_CACHE_CONFIG",
        config / "deck_monitor_cache.json",
        raising=False,
    )

    for attr, value in {
        "LEGACY_ARCHETYPE_CACHE_FILE": cache / "archetype_cache.json",
        "LEGACY_DECK_CACHE_FILE": cache / "deck_cache.json",
        "LEGACY_ARCHETYPE_CACHE_CONFIG_FILE": config / "archetype_cache.json",
        "LEGACY_DECK_CACHE_CONFIG_FILE": config / "deck_cache.json",
        "LEGACY_CURR_DECK_CACHE_FILE": cache / "curr_deck.txt",
        "LEGACY_CURR_DECK_ROOT_FILE": decks / "curr_deck.txt",
    }.items():
        monkeypatch.setattr(mtggoldfish, attr, value, raising=False)

    monkeypatch.setattr(
        deck_selector._Worker,
        "start",
        lambda self: self._run(),
        raising=False,
    )

    monkeypatch.setattr(
        mtggoldfish,
        "get_archetypes",
        lambda fmt, cache_ttl=3600, allow_stale=True: [
            {"name": "Mono Red Aggro", "href": "mono-red-aggro"},
            {"name": "Azorius Control", "href": "azorius-control"},
        ],
        raising=False,
    )
    monkeypatch.setattr(
        mtggoldfish,
        "get_archetype_decks",
        lambda archetype: [
            {
                "name": archetype,
                "number": "1",
                "player": "TestPilot",
                "event": "Test Event",
                "result": "2-1",
                "date": "2024-10-01",
            },
        ],
        raising=False,
    )

    def fake_download(number: str) -> None:
        (decks / "curr_deck.txt").write_text(
            "4 Mountain\n4 Island\nSideboard\n2 Dispel\n", encoding="utf-8"
        )

    monkeypatch.setattr(mtggoldfish, "download_deck", fake_download, raising=False)

    yield


def pump_ui_events(app: wx.App, *, iterations: int = 5) -> None:
    """Process pending wx events so CallAfter handlers run during tests."""
    for _ in range(iterations):
        pending = getattr(app, "Pending", None)
        if pending:
            while pending():
                app.Dispatch()
        else:
            while wx.Pending():
                app.Dispatch()
        time_module.sleep(0)


@pytest.fixture
def deck_selector_factory(wx_app) -> MTGDeckSelectionFrame:
    def _factory() -> MTGDeckSelectionFrame:
        return MTGDeckSelectionFrame()

    return _factory


def prepare_card_manager(frame: MTGDeckSelectionFrame) -> None:
    manager = CardDataManager()
    manager._cards = SAMPLE_CARDS
    manager._cards_by_name = {card["name_lower"]: card for card in SAMPLE_CARDS}
    frame.card_manager = manager
    frame.card_data_ready = True
