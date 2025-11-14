# Architecture Overview

This document describes the architecture and design patterns used in the MTGO Metagame Tools project.

## Table of Contents

- [Design Philosophy](#design-philosophy)
- [Layered Architecture](#layered-architecture)
- [Module Organization](#module-organization)
- [Design Patterns](#design-patterns)
- [Data Flow](#data-flow)
- [State Management](#state-management)
- [Threading Model](#threading-model)
- [External Dependencies](#external-dependencies)

## Design Philosophy

The project follows these core principles:

1. **Separation of Concerns**: Business logic is separated from UI code
2. **Layered Architecture**: Clear boundaries between presentation, business, and data layers
3. **Testability**: Services and repositories are designed to be easily testable
4. **Singleton Services**: Service and repository instances are shared across the application
5. **Event-Driven UI**: wxPython event system for responsive user interface

## Layered Architecture

The application is organized into four main layers:

```
┌─────────────────────────────────────────────────────────────┐
│                    Presentation Layer                        │
│            (widgets/, main.py)                              │
│   - UI Components (wxPython)                                │
│   - Event Handlers                                          │
│   - View Logic                                              │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                     Service Layer                            │
│                   (services/)                               │
│   - Business Logic                                          │
│   - Workflow Orchestration                                  │
│   - Data Transformation                                     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                   Repository Layer                           │
│                 (repositories/)                             │
│   - Data Access                                             │
│   - Caching                                                 │
│   - File I/O                                                │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│              External Services & Data Sources                │
│         (navigators/, utils/, dotnet/MTGOBridge)           │
│   - MTGGoldfish API                                         │
│   - Scryfall API                                            │
│   - MTGO Bridge                                             │
│   - Local File System                                       │
└─────────────────────────────────────────────────────────────┘
```

### Layer Responsibilities

#### Presentation Layer (`widgets/`, `main.py`)
- **Purpose**: User interface and interaction
- **Key Components**:
  - `main.py`: Application entry point
  - `deck_selector.py`: Main application window
  - `panels/`: Reusable UI panels (deck builder, stats, sideboard guide, etc.)
  - `dialogs/`: Modal dialogs
  - `buttons/`: Custom button widgets
- **Responsibilities**:
  - Render UI components
  - Handle user events
  - Delegate business logic to services
  - Display data returned from services
- **Anti-patterns to avoid**:
  - ❌ Direct database/file access
  - ❌ Business logic in event handlers
  - ❌ Direct API calls to external services

#### Service Layer (`services/`)
- **Purpose**: Business logic and workflow orchestration
- **Components**:
  - `deck_service.py`: Deck analysis, validation, and manipulation
  - `collection_service.py`: Collection management and ownership analysis
  - `search_service.py`: Card search and filtering logic
  - `image_service.py`: Card image management and downloads
- **Responsibilities**:
  - Implement business rules
  - Coordinate between repositories
  - Transform data for presentation
  - Validation and error handling
- **Pattern**: Singleton instances accessed via `get_*_service()` functions

#### Repository Layer (`repositories/`)
- **Purpose**: Data access and persistence
- **Components**:
  - `deck_repository.py`: Deck file I/O and MongoDB operations
  - `card_repository.py`: Card data and image management
  - `metagame_repository.py`: Cached metagame data access
- **Responsibilities**:
  - Abstract data storage mechanisms
  - Implement caching strategies
  - Handle file I/O operations
  - Manage data freshness and TTL
- **Pattern**: Singleton instances accessed via `get_*_repository()` functions

#### External Services (`navigators/`, `utils/`)
- **Purpose**: Integration with external systems and utilities
- **Components**:
  - `navigators/mtggoldfish.py`: Web scraping for metagame data
  - `navigators/mtgo_decklists.py`: Official MTGO decklist parsing
  - `utils/gamelog_parser.py`: Match history extraction
  - `utils/card_data.py`: Scryfall API integration
  - `dotnet/MTGOBridge/`: .NET bridge for MTGO integration
- **Responsibilities**:
  - HTTP requests to external APIs
  - Web scraping and HTML parsing
  - MTGO SDK integration
  - File format parsing

## Module Organization

### Directory Structure

```
magic_online_metagame_crawler/
│
├── main.py                          # Application entry point
│
├── widgets/                         # Presentation Layer
│   ├── deck_selector.py              # Main window (~1000 lines - God Class antipattern)
│   ├── identify_opponent.py          # Opponent tracking widget
│   ├── match_history.py              # Match history viewer
│   ├── metagame_analysis.py          # Meta statistics viewer
│   ├── timer_alert.py                # Challenge timer alerts
│   ├── card_image_display.py         # Card image viewer
│   │
│   ├── panels/                       # Reusable panel components
│   │   ├── deck_builder_panel.py     # Card search and deck building
│   │   ├── deck_stats_panel.py       # Mana curve and statistics
│   │   ├── deck_research_panel.py    # Archetype browser
│   │   ├── sideboard_guide_panel.py  # Sideboard guide management
│   │   ├── deck_notes_panel.py       # Deck notes editor
│   │   ├── card_inspector_panel.py   # Card image viewer
│   │   ├── card_table_panel.py       # Card list display
│   │   └── card_box_panel.py         # Card grid display
│   │
│   ├── dialogs/                      # Modal dialogs
│   │   └── image_download_dialog.py  # Bulk image download
│   │
│   ├── handlers/                     # Event handler classes
│   │   ├── deck_selector_handlers.py # Main window event handlers
│   │   ├── card_table_panel_handler.py # Card table events
│   │   └── sideboard_guide_handlers.py # Sideboard guide events
│   │
│   └── buttons/                      # Custom buttons
│       ├── deck_action_buttons.py    # Deck operation buttons
│       └── mana_button.py            # Mana symbol buttons
│
├── services/                        # Service Layer
│   ├── deck_service.py               # Deck business logic
│   ├── collection_service.py         # Collection management
│   ├── search_service.py             # Card search logic
│   └── image_service.py              # Image management
│
├── repositories/                    # Repository Layer
│   ├── deck_repository.py            # Deck persistence
│   ├── card_repository.py            # Card data access
│   └── metagame_repository.py        # Cached metagame data
│
├── navigators/                      # External API Integration
│   ├── mtggoldfish.py                # MTGGoldfish scraper
│   └── mtgo_decklists.py             # MTGO.com parser
│
├── utils/                           # Utility Modules
│   ├── card_data.py                  # Card metadata manager
│   ├── gamelog_parser.py             # Match log parser
│   ├── archetype_classifier.py       # Deck archetype detection
│   ├── mana_icon_factory.py          # Mana symbol rendering
│   ├── card_images.py                # Card image utilities
│   ├── search_filters.py             # Search filter functions
│   ├── deck.py                       # Deck parsing utilities
│   ├── metagame_stats.py             # Meta statistics
│   ├── constants.py                  # Application constants
│   └── paths.py                      # Path management
│
├── dotnet/MTGOBridge/               # .NET MTGO Integration
│   ├── Program.cs                    # Bridge implementation
│   └── MTGOBridge.csproj             # .NET project file
│
├── tests/                           # Test Suite
│   ├── conftest.py                   # Pytest configuration
│   ├── test_helpers.py               # Test utilities
│   ├── test_*.py                     # Unit tests
│   └── ui/                           # UI tests
│       ├── conftest.py               # UI test fixtures
│       └── test_deck_selector.py     # Widget tests
│
└── scripts/                         # Utility Scripts
    ├── dump_collection.py            # Collection export
    ├── monitor_currency.py           # Currency monitoring
    ├── fetch_mana_assets.py          # Asset download
    └── update_vendor_data.py         # Vendor data update
```

## Design Patterns

### 1. Singleton Pattern (Services & Repositories)

All services and repositories use the singleton pattern to ensure single instances across the application:

```python
# services/deck_service.py
_deck_service: DeckService | None = None

def get_deck_service() -> DeckService:
    global _deck_service
    if _deck_service is None:
        _deck_service = DeckService()
    return _deck_service
```

**Benefits**:
- Shared state across application
- Single source of truth for cached data
- Easy to reset in tests

**Testing**: Tests use `reset_all_globals()` fixture to clear singletons between tests.

### 2. Repository Pattern

Data access is abstracted through repository classes:

```python
class DeckRepository:
    def save_to_file(self, deck_text: str, filename: str) -> Path:
        """Save deck to file system"""

    def load_from_file(self, filepath: Path) -> str:
        """Load deck from file system"""

    def save_to_db(self, deck_name: str, deck_text: str):
        """Save deck to MongoDB"""
```

**Benefits**:
- Abstract storage mechanism
- Easy to mock in tests
- Centralized caching logic

### 3. Service Pattern

Business logic is encapsulated in service classes:

```python
class DeckService:
    def analyze_deck(self, deck_text: str) -> dict:
        """Analyze deck and return statistics"""

    def validate_deck_format(self, deck_text: str, format: str) -> tuple[bool, str]:
        """Validate deck for format legality"""
```

**Benefits**:
- Reusable business logic
- Testable without UI
- Clear separation from presentation

### 4. Event-Driven Architecture (UI)

wxPython widgets communicate via events and callbacks:

```python
class DeckBuilderPanel(wx.Panel):
    def __init__(self, parent, on_search_callback=None):
        self.on_search = on_search_callback

    def _on_search_button(self, event):
        if self.on_search:
            self.on_search()  # Notify parent
```

**Benefits**:
- Loose coupling between widgets
- Parent controls workflow
- Easy to test panels in isolation

### 5. Panel Composition

The main window (`deck_selector.py`) is composed of reusable panels:

```python
class MTGDeckSelectionFrame(wx.Frame):
    def __init__(self, parent):
        # Compose panels
        self.research_panel = DeckResearchPanel(notebook, ...)
        self.builder_panel = DeckBuilderPanel(notebook, ...)
        self.stats_panel = DeckStatsPanel(notebook, ...)
        self.guide_panel = SideboardGuidePanel(notebook, ...)
        self.notes_panel = DeckNotesPanel(notebook, ...)
```

**Benefits**:
- Reusable components
- Easier testing
- Better organization

### 6. Lazy Loading

Card data and images are loaded on demand:

```python
class CardDataManager:
    def __init__(self):
        self._cards = None  # Not loaded yet

    def get_all_cards(self) -> list[dict]:
        if self._cards is None:
            self._load_from_scryfall()  # Load on first access
        return self._cards
```

**Benefits**:
- Faster startup time
- Reduced memory usage
- Load only what's needed

## Data Flow

### Example: Loading a Deck

```
User clicks "Load Deck"
         ↓
[deck_selector.py]
  _on_load_deck()
         ↓
[deck_repository.py]
  load_from_file(path) → deck_text
         ↓
[deck_service.py]
  analyze_deck(deck_text) → stats
         ↓
[deck_selector.py]
  _on_deck_content_ready(deck_text, stats)
  ├→ Update card lists
  ├→ Update stats panel
  └→ Refresh UI
```

### Example: Searching Cards

```
User enters search query
         ↓
[deck_builder_panel.py]
  _on_search_button()
         ↓
[deck_selector.py]
  _on_builder_search()
         ↓
[search_service.py]
  search_with_builder_filters(filters, cards)
  ├→ Apply name filter
  ├→ Apply color filter
  ├→ Apply mana value filter
  └→ Return filtered results
         ↓
[deck_selector.py]
  Update search results table
```

### Example: Importing Collection

```
User clicks "Refresh from Bridge"
         ↓
[deck_selector.py]
  _refresh_collection_inventory(force=True)
         ↓
[collection_service.py]
  refresh_from_bridge_async()
  ├→ Run bridge.exe in subprocess
  ├→ Parse JSON output
  ├→ Save to cache file
  └→ Return collection data
         ↓
[deck_selector.py]
  Update collection status
  Update card ownership indicators
```

## State Management

### Application State

State is managed at multiple levels:

1. **Singleton Services**: Shared state like card data, collection
2. **Widget State**: Local UI state (selected deck, search filters)
3. **File-Based Persistence**: Deck notes, sideboard guides, settings
4. **Database**: Saved decks (MongoDB, optional)

### Global Singletons

```python
# These maintain state across the application:
- CardDataManager: Card metadata from Scryfall
- CollectionService: User's MTGO collection
- DeckService: Current deck being edited
- MetagameRepository: Cached metagame data
```

### Resetting State (Testing)

Tests use fixtures to reset global state:

```python
# tests/conftest.py
@pytest.fixture(autouse=True)
def reset_global_state():
    reset_all_services()
    reset_all_repositories()
```

## Threading Model

### Main Thread (UI Thread)
- All wxPython UI operations run on main thread
- Event handlers execute on main thread

### Background Workers
Used for long-running operations to keep UI responsive:

```python
def _download_deck_async(self, deck_number: int):
    def worker():
        deck_text = download_deck(deck_number)  # Slow I/O
        wx.CallAfter(self._on_deck_ready, deck_text)  # Back to UI thread

    threading.Thread(target=worker, daemon=True).start()
```

**Operations using background threads**:
- Deck downloads from MTGGoldfish
- Metagame data fetching
- Image downloads
- Collection imports from MTGO Bridge
- Match history parsing

**Pattern**: `wx.CallAfter()` to marshal results back to UI thread

## External Dependencies

### Python Libraries

| Library | Purpose | Layer |
|---------|---------|-------|
| wxPython | GUI framework | Presentation |
| requests | HTTP client | Navigators |
| beautifulsoup4 | HTML parsing | Navigators |
| pymongo | MongoDB client | Repository |
| Pillow | Image processing | Utils |
| loguru | Logging | All layers |
| pytest | Testing | Tests |

### External Services

| Service | Purpose | Used By |
|---------|---------|---------|
| MTGGoldfish | Metagame data | `navigators/mtggoldfish.py` |
| Scryfall API | Card metadata | `utils/card_data.py` |
| MTGO Bridge | Collection data | `services/collection_service.py` |

### Data Files

| File | Purpose | Location |
|------|---------|----------|
| Card bulk data | Scryfall card JSON | `cache/oracle-cards.json` |
| Collection export | MTGO collection | `cache/collection.json` |
| Deck files | Saved decks | `decks/*.txt` |
| Notes | Deck notes | `cache/deck_notes.json` |
| Sideboard guides | Boarding plans | `cache/deck_sbguides.json` |

## Known Technical Debt

**For comprehensive analysis, see**: `docs/reviews/CODEBASE_AUDIT_2025-11-14.md`

### Critical Issues (Fix Immediately)

1. **Service with UI Dependencies**: `services/collection_service.py`
   - **Problem**: Imports wxPython, returns wx.Colour objects, violates layering
   - **Impact**: Cannot test service without UI, cannot reuse in non-UI contexts
   - **Plan**: Extract color logic to presentation layer

2. **Undefined Method Bug**: `widgets/handlers/deck_selector_handlers.py:84, 102`
   - **Problem**: Calls `self._build_deck_text()` which doesn't exist
   - **Impact**: Production bug - AttributeError when copying/saving decks
   - **Plan**: Replace with `self.deck_service.build_deck_text_from_zones()`

3. **Duplicate Functions**: Two `analyze_deck()` with different logic
   - **Problem**: `utils/deck.py:73` vs `services/deck_service.py:95` - conflicting implementations
   - **Impact**: Data correctness issues, developer confusion
   - **Plan**: Consolidate to single implementation

### High Priority Issues

4. **God Class**: `deck_selector.py` (~1000 lines)
   - **Problem**: Too many responsibilities (UI, state, I/O, threading)
   - **Plan**: Extract into focused controllers

5. **UI/Business Logic Mixing**: Widgets contain business logic
   - **Problem**: Hard to test, tight coupling
   - **Locations**: Event handlers, panels with direct file I/O
   - **Plan**: Extract to services

6. **Test Coverage**: ~15-18% overall
   - **Problem**: Low confidence in refactoring, bugs reach production
   - **Gap**: ~2,500 lines of untested critical logic
   - **Plan**: Target 65-70% coverage (see `docs/TEST_COVERAGE_GAPS.md`)

### Medium Priority Issues

7. **Code Duplication**:
   - Cache management duplicated across 2 modules (~130 lines)
   - Singleton boilerplate across 5 services (~100 lines)
   - Locking pattern repeated 8+ times
   - **Plan**: Create shared `CacheManager`, singleton decorator

8. **Dead/Unused Code**:
   - `utils/mtgo_bridge.py`: Stub functions, redundant wrappers
   - `utils/paths_constants.py`: Could merge into `paths.py`
   - Test code in production modules
   - **Plan**: Remove dead code, consolidate modules

### Refactoring Opportunities

- Extract `MetagameService` from `metagame_analysis.py`
- Extract `MatchHistoryService` from `match_history.py`
- Extract `OpponentTrackingService` from `identify_opponent.py`
- Standardize service access patterns (choose one: DI vs. service locator)
- Standardize error handling strategy
- Add thread safety to loading flags

### Documentation References

Detailed analysis available in:
- **`docs/reviews/CODEBASE_AUDIT_2025-11-14.md`**: Comprehensive audit with priorities
- **`docs/TEST_COVERAGE_GAPS.md`**: Detailed test coverage analysis and roadmap
- **`docs/reviews/CLAUDE_REVIEW_2025-11-13.md`**: Refactoring review
- **`docs/reviews/CODEX_REVIEW_2025-11-13.md`**: Branch-specific issues

## Future Architecture Improvements

### Planned Enhancements

1. **Dependency Injection**: Replace singleton pattern with DI container
2. **Event Bus**: Centralized event system for widget communication
3. **State Management**: Introduce proper state management (Redux-like)
4. **Async/Await**: Replace threading with asyncio for I/O operations
5. **Plugin System**: Allow extending functionality via plugins

### Migration Path

The architecture is designed to support incremental improvements:
- Services can be refactored without changing UI
- Repositories can change storage mechanism transparently
- Panels can be redesigned independently

---

**Last Updated**: November 14, 2025
**Document Version**: 1.1
**Changelog**:
- v1.1 (2025-11-14): Updated technical debt section, added handler modules, fixed line counts
- v1.0 (2025-11-13): Initial version
