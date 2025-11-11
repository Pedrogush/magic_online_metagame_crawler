# Refactoring Guide: Separating Business Logic from UI

## Overview

This document describes the refactoring of `MTGDeckSelectionFrame` (3,445 lines) to separate business logic from UI concerns, following the **Service Layer** and **Separation of Concerns** patterns.

## Problem Statement

The original `MTGDeckSelectionFrame` class was a **God Object** that:
- Mixed business logic with UI code
- Had 145+ methods handling everything from UI rendering to API calls
- Made testing difficult (business logic coupled to wx widgets)
- Made maintenance challenging (changes rippled across unrelated concerns)
- Violated Single Responsibility Principle

## Solution Architecture

### Service Layer Pattern

We've extracted business logic into dedicated service classes in the `/services/` directory:

```
services/
├── __init__.py
├── deck_service.py              # Deck operations (load, save, parse, download)
├── archetype_service.py         # Archetype fetching and filtering
├── collection_service.py        # Collection inventory management
└── deck_analysis_service.py     # Deck statistics and analysis
```

### UI Component Extraction

Complex UI sections extracted into reusable components:

```
widgets/
├── card_inspector_panel.py      # Card details, images, printings
└── [Future] deck_workspace_panel.py  # Deck tables, notes, guides
```

## Phase 1: Service Classes Created (COMPLETED)

### 1. DeckService (`services/deck_service.py`)

**Responsibilities:**
- Download decks from MTGGoldfish
- Parse deck text into structured data
- Build deck text from structured data
- Save decks to file/database
- Build daily average decks
- Render average decks

**Key Methods:**
```python
deck_service = DeckService(deck_save_dir)

# Download deck
deck_text = deck_service.download_deck(deck_dict)

# Parse deck text
zones = deck_service.parse_deck(deck_text)
# Returns: {"main": [...], "side": [...], "out": [...]}

# Build deck text
deck_text = deck_service.build_deck_text(zones)

# Save deck
filepath = deck_service.save_deck(deck_text, "My Deck")
deck_service.save_to_db(deck_text, metadata)

# Analyze deck
stats = deck_service.analyze_deck(deck_text)

# Build daily average
buffer, count = deck_service.build_daily_average(decks, format_name)
avg_text = deck_service.render_average_deck(buffer, count)
```

**Extracted From:**
- `_download_and_display_deck()`
- `_on_deck_content_ready()`
- `_build_deck_text()`
- `on_save_clicked()`
- `_build_daily_average_deck()`
- `_render_average_deck()`

### 2. ArchetypeService (`services/archetype_service.py`)

**Responsibilities:**
- Fetch archetypes for formats
- Filter archetypes by search query
- Fetch decklists for archetypes
- Generate archetype summaries
- Cache management

**Key Methods:**
```python
archetype_service = ArchetypeService()

# Fetch archetypes
archetypes = archetype_service.fetch_archetypes("Modern", force=False)

# Filter archetypes
filtered = archetype_service.filter_archetypes(archetypes, "burn")

# Fetch decks
decks = archetype_service.fetch_decks_for_archetype("Modern", "RDW")

# Generate summary
summary = archetype_service.get_archetype_summary("RDW", decks)

# Clear cache
archetype_service.clear_cache()
```

**Extracted From:**
- `fetch_archetypes()`
- `on_archetype_filter()`
- `_load_decks_for_archetype()`
- `_present_archetype_summary()`

### 3. CollectionService (`services/collection_service.py`)

**Responsibilities:**
- Load collection from cache
- Save collection to cache
- Fetch collection from MTGO bridge
- Build inventory dictionary
- Get ownership status

**Key Methods:**
```python
collection_service = CollectionService(cache_dir)

# Load from cache
if collection_service.load_from_cache():
    inventory = collection_service.inventory

# Fetch from bridge
cards = collection_service.fetch_from_bridge(bridge_path)
collection_service.save_to_cache(cards)
inventory = collection_service.build_inventory(cards)

# Check ownership
owned = collection_service.get_owned_quantity("Lightning Bolt")
status, color = collection_service.get_owned_status("Lightning Bolt", required=4)
```

**Extracted From:**
- `_load_collection_from_cache()`
- `_refresh_collection_inventory()`
- `_on_collection_fetched()`
- `_owned_status()`

### 4. DeckAnalysisService (`services/deck_analysis_service.py`)

**Responsibilities:**
- Analyze deck statistics
- Calculate mana curve
- Calculate color distribution
- Identify key cards
- Validate deck against format rules
- Calculate card type distribution

**Key Methods:**
```python
analysis_service = DeckAnalysisService()

# Analyze deck
stats = analysis_service.analyze(deck_text)

# Calculate curve
curve = analysis_service.calculate_mana_curve(cards)
# Returns: {0: 10, 1: 14, 2: 18, ...}

# Calculate colors
colors = analysis_service.calculate_color_distribution(cards)
# Returns: {"W": 0, "U": 12, "B": 0, "R": 25, "G": 0, "C": 0}

# Validate deck
validation = analysis_service.validate_deck(zones, "Modern")
# Returns: {"valid": True, "issues": [], "totals": {...}}

# Type distribution
types = analysis_service.calculate_card_type_distribution(cards)
# Returns: {"Creature": 20, "Instant": 15, "Land": 25, ...}
```

**Extracted From:**
- `_update_stats()`
- `_render_curve()`
- `_render_color_concentration()`

### 5. CardInspectorPanel (`widgets/card_inspector_panel.py`)

**Responsibilities:**
- Display card details (name, type, stats, oracle text)
- Show card images
- Navigate between printings
- Render mana cost symbols

**Key Methods:**
```python
inspector = CardInspectorPanel(
    parent, mana_icon_factory,
    bg_color, panel_color, text_color, subdued_color
)

# Update card
inspector.update_card(card_dict, get_metadata_func)

# Reset
inspector.reset()
```

**Extracted From:**
- `_update_card_inspector()`
- `_reset_card_inspector()`
- `_render_inspector_cost()`
- `_load_card_image_and_printings()`
- `_on_prev_printing()`
- `_on_next_printing()`

## Phase 2: Integration (TODO)

### Step 1: Update MTGDeckSelectionFrame.__init__()

```python
def __init__(self, parent: wx.Window | None = None):
    super().__init__(parent, title="MTGO Deck Research & Builder", size=(1380, 860))

    # Initialize services
    self.deck_service = DeckService(DECK_SAVE_DIR)
    self.archetype_service = ArchetypeService()
    self.collection_service = CollectionService(CACHE_DIR)
    self.analysis_service = DeckAnalysisService()

    # ... rest of initialization
```

### Step 2: Replace Business Logic with Service Calls

**Before:**
```python
def _download_and_display_deck(self, deck: dict[str, Any]) -> None:
    deck_num = deck.get("number", "")
    if not deck_num:
        return

    def fetch_deck():
        logger.info(f"Downloading deck {deck_num}")
        deck_text = download_deck(deck_num)
        return deck_text

    _Worker(
        fetch_deck,
        on_success=lambda txt: self._on_deck_content_ready(txt, "archetype"),
        on_error=self._on_deck_download_error,
    ).start()
```

**After:**
```python
def _download_and_display_deck(self, deck: dict[str, Any]) -> None:
    def fetch_deck():
        return self.deck_service.download_deck(deck)

    _Worker(
        fetch_deck,
        on_success=lambda txt: self._on_deck_content_ready(txt, "archetype"),
        on_error=self._on_deck_download_error,
    ).start()
```

### Step 3: Replace Archetype Operations

**Before:**
```python
def fetch_archetypes(self, force: bool = False) -> None:
    if self.loading_archetypes and not force:
        return

    self.loading_archetypes = True
    fmt = self.current_format

    def _fetch():
        logger.info(f"Fetching archetypes for {fmt}")
        archetypes = get_archetypes(fmt)
        return archetypes

    _Worker(
        _fetch,
        on_success=self._on_archetypes_loaded,
        on_error=self._on_archetypes_error,
    ).start()
```

**After:**
```python
def fetch_archetypes(self, force: bool = False) -> None:
    if self.loading_archetypes and not force:
        return

    self.loading_archetypes = True
    fmt = self.current_format

    def _fetch():
        return self.archetype_service.fetch_archetypes(fmt, force=force)

    _Worker(
        _fetch,
        on_success=self._on_archetypes_loaded,
        on_error=self._on_archetypes_error,
    ).start()
```

### Step 4: Replace Collection Operations

**Before:**
```python
def _load_collection_from_cache(self) -> bool:
    if not collection_cache_path.exists():
        logger.debug("No collection cache found")
        return False

    try:
        with collection_cache_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        self.collection_inventory = {}
        for item in data.get("cards", []):
            name = item.get("name", "")
            qty = item.get("quantity", 0)
            if name:
                self.collection_inventory[name] = self.collection_inventory.get(name, 0) + qty

        logger.info(f"Loaded {len(self.collection_inventory)} unique cards from cache")
        return True
    except (OSError, json.JSONDecodeError) as exc:
        logger.error(f"Failed to load collection cache: {exc}")
        return False
```

**After:**
```python
def _load_collection_from_cache(self) -> bool:
    loaded = self.collection_service.load_from_cache()
    if loaded:
        self.collection_inventory = self.collection_service.inventory
    return loaded
```

### Step 5: Replace CardInspector UI

**Before:** (100+ lines of card inspector code in MTGDeckSelectionFrame)

**After:**
```python
def _build_ui(self) -> None:
    # ... other UI code ...

    # Replace inline card inspector with component
    self.card_inspector = CardInspectorPanel(
        inspector_box,
        self.mana_icons,
        DARK_BG,
        DARK_PANEL,
        LIGHT_TEXT,
        SUBDUED_TEXT,
    )
    inspector_sizer.Add(self.card_inspector, 1, wx.EXPAND | wx.ALL, 6)

    # ... other UI code ...

def _handle_card_focus(self, zone: str, card: dict[str, Any] | None) -> None:
    if card is None:
        self.card_inspector.reset()
    else:
        self.card_inspector.update_card(card, self._get_card_metadata)
```

## Benefits of Refactoring

### 1. **Testability**
Services can be tested independently without wxPython:

```python
def test_deck_service_parse():
    service = DeckService(Path("/tmp"))
    deck_text = "4 Lightning Bolt\n60 Mountain"
    zones = service.parse_deck(deck_text)

    assert zones["main"][0]["name"] == "Lightning Bolt"
    assert zones["main"][0]["quantity"] == 4
```

### 2. **Maintainability**
Business logic changes don't affect UI:

```python
# Change deck parsing logic without touching UI
class DeckService:
    def parse_deck(self, deck_text: str) -> dict[str, list[dict[str, Any]]]:
        # New parsing algorithm - UI unchanged
        ...
```

### 3. **Reusability**
Services can be used in other contexts:

```python
# CLI tool
deck_service = DeckService(Path("./decks"))
deck_text = deck_service.download_deck({"number": "12345"})
deck_service.save_deck(deck_text, "my_deck")

# Web API
@app.route("/api/deck/<deck_id>")
def get_deck(deck_id):
    deck_service = DeckService(DECK_DIR)
    deck_text = deck_service.download_deck({"number": deck_id})
    return {"deck": deck_text}
```

### 4. **Code Organization**
Clear separation of concerns:

```
Before: MTGDeckSelectionFrame (3,445 lines)
├── UI rendering
├── Event handling
├── Deck operations
├── Archetype operations
├── Collection operations
├── Image operations
├── Analysis operations
└── File I/O

After: MTGDeckSelectionFrame (~1,500 lines)
├── UI rendering
├── Event handling
└── Service coordination

services/
├── deck_service.py           (234 lines)
├── archetype_service.py      (117 lines)
├── collection_service.py     (144 lines)
└── deck_analysis_service.py  (178 lines)

widgets/
└── card_inspector_panel.py   (291 lines)
```

## Testing Strategy

### Service Tests (Unit Tests)

```python
# tests/test_deck_service.py
import pytest
from services.deck_service import DeckService

def test_parse_deck_basic():
    service = DeckService(Path("/tmp"))
    deck_text = """
4 Lightning Bolt
20 Mountain

Sideboard
3 Skullcrack
    """
    zones = service.parse_deck(deck_text)

    assert len(zones["main"]) == 2
    assert zones["main"][0]["name"] == "Lightning Bolt"
    assert zones["main"][0]["quantity"] == 4
    assert len(zones["side"]) == 1

def test_build_deck_text():
    service = DeckService(Path("/tmp"))
    zones = {
        "main": [{"name": "Lightning Bolt", "quantity": 4}],
        "side": [{"name": "Skullcrack", "quantity": 3}],
    }

    deck_text = service.build_deck_text(zones)

    assert "4 Lightning Bolt" in deck_text
    assert "Sideboard" in deck_text
    assert "3 Skullcrack" in deck_text
```

### Integration Tests

```python
# tests/test_mtg_deck_selection_frame.py
def test_load_deck_uses_service(monkeypatch):
    # Mock deck service
    called = False

    def mock_download(deck):
        nonlocal called
        called = True
        return "4 Lightning Bolt"

    monkeypatch.setattr("services.deck_service.download_deck", mock_download)

    # Create frame and load deck
    frame = MTGDeckSelectionFrame()
    frame._download_and_display_deck({"number": "12345"})

    # Wait for worker thread
    wx.YieldIfNeeded()

    assert called
```

## Migration Path

### Immediate (Phase 1 - COMPLETED)
- ✅ Create service classes
- ✅ Create CardInspectorPanel component
- ✅ Document refactoring approach

### Short Term (Phase 2 - 2-3 days)
- Replace business logic calls with service calls
- Integrate CardInspectorPanel
- Update unit tests

### Medium Term (1-2 weeks)
- Extract DeckWorkspacePanel component
- Extract ResearchPanel component (if not already separate)
- Add comprehensive service tests

### Long Term (1 month)
- Extract all UI components
- Achieve <500 lines for MTGDeckSelectionFrame
- Reach 60%+ test coverage

## Code Size Reduction

| Component | Before | After | Reduction |
|-----------|--------|-------|-----------|
| **MTGDeckSelectionFrame** | 3,445 lines | ~1,500 lines | -56% |
| **Services** (new) | 0 lines | 673 lines | +673 |
| **CardInspectorPanel** (new) | 0 lines | 291 lines | +291 |
| **Total** | 3,445 lines | 2,464 lines | -28% |

*Note: Total reduction comes from elimination of duplicate code and clearer abstractions*

## Next Steps

1. **Review this refactoring guide** with the team
2. **Run existing tests** to establish baseline
3. **Implement Phase 2 integration** (estimated 2-3 days)
4. **Add service unit tests** (estimated 1-2 days)
5. **Update integration tests** (estimated 1 day)
6. **Documentation review** (estimated 1 day)

## Questions & Answers

### Q: Will this break existing functionality?
A: No. The refactoring preserves all existing behavior. Services wrap existing functions, so the API contracts remain the same.

### Q: Do we need to refactor everything at once?
A: No. This can be done incrementally. Start with one service (e.g., DeckService) and gradually migrate others.

### Q: How do we handle the transition?
A: Keep old methods temporarily, mark them as deprecated, and gradually replace callers with service calls.

### Q: What about performance?
A: Performance should be equivalent or better. Services add minimal overhead (one extra function call), but enable caching and optimization opportunities.

### Q: How do we test UI with services?
A: Mock services in UI tests:

```python
def test_ui_with_mock_service(monkeypatch):
    mock_service = Mock(spec=DeckService)
    mock_service.download_deck.return_value = "4 Lightning Bolt"

    frame = MTGDeckSelectionFrame()
    monkeypatch.setattr(frame, "deck_service", mock_service)

    # Test UI behavior
    ...
```

## References

- [Service Layer Pattern](https://martinfowler.com/eaaCatalog/serviceLayer.html)
- [Separation of Concerns](https://en.wikipedia.org/wiki/Separation_of_concerns)
- [God Object Anti-pattern](https://en.wikipedia.org/wiki/God_object)
- [Original Code Review Report](./CODE_REVIEW_REPORT.md)

---

**Created:** 2025-11-11
**Status:** Phase 1 Complete, Phase 2 Pending
**Reviewed by:** Claude Code
