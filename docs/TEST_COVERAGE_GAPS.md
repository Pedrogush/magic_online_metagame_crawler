# Test Coverage Gaps Analysis
## MTGO Metagame Tools - Detailed Testing Guide

### Overview

Current test coverage: **15-18%** (2,719 test lines covering 15,247 production lines)
Target coverage: **65-70%**
Gap: **~2,500 lines of untested business logic** across 16 modules

This document provides a comprehensive breakdown of testing gaps and priorities.

---

## Critical Priority Modules (Test Immediately)

### 1. card_data.py (283 LOC) - CRITICAL

**What it does**:
- Downloads Scryfall bulk card data (JSON)
- Extracts ZIP files
- Caches card metadata
- Provides card lookup by name
- Lazy loads on first access

**Why critical**:
- Core functionality - entire app depends on card data
- Network I/O with failure modes
- File system operations (ZIP extraction)
- Caching logic with TTL

**Untested Functions**:
```python
CardDataManager.__init__()
CardDataManager._download_cards()
CardDataManager._load_from_cache()
CardDataManager.get_all_cards()
CardDataManager.get_card_by_name()
CardDataManager.refresh_data()
```

**Test Scenarios Needed**:
- ✓ Successful download and extraction
- ✓ Network failure handling
- ✓ Corrupt ZIP file handling
- ✓ Cache hit vs. cache miss
- ✓ TTL expiration
- ✓ Concurrent access
- ✓ Card lookup by exact name
- ✓ Card lookup by case-insensitive name
- ✓ Missing card handling

**Estimated Test LOC**: 150-200 lines

---

### 2. card_images.py (707 LOC) - CRITICAL

**What it does**:
- SQLite cache for card images
- Concurrent downloads from Scryfall
- Image URL resolution
- Progress tracking
- Cache management

**Why critical**:
- Data integrity (SQLite corruption risk)
- Concurrent I/O operations
- Large files (disk space management)
- User-facing feature (missing images break UI)

**Untested Functions**:
```python
CardImageCache.__init__()
CardImageCache.get_image_path()
CardImageCache.download_images_bulk()
CardImageCache._download_single_image()
CardImageCache.get_missing_images()
CardImageCache.clear_cache()
_get_image_url()
```

**Test Scenarios Needed**:
- ✓ Database initialization and migration
- ✓ Concurrent downloads (10+ threads)
- ✓ Download failure retry logic
- ✓ Partial download recovery
- ✓ Disk full handling
- ✓ Cache hit performance
- ✓ Image URL resolution for double-faced cards
- ✓ Progress callback accuracy
- ✓ Cancel operation mid-download

**Estimated Test LOC**: 200-250 lines

---

### 3. mtggoldfish.py (338 LOC) - CRITICAL

**What it does**:
- Web scraping MTGGoldfish for metagame data
- HTML parsing with BeautifulSoup
- Archetype listing by format
- Deck download by number
- Caching with TTL
- Data aggregation

**Why critical**:
- External dependency (website changes break functionality)
- Complex HTML parsing (fragile)
- Network I/O failures
- Data accuracy for metagame analysis

**Untested Functions**:
```python
list_archetypes()
get_archetype_decks()
download_deck()
download_daily_deck_average()
_parse_archetype_table()
_extract_deck_metadata()
_cache_archetypes()
```

**Test Scenarios Needed**:
- ✓ HTML parsing with current format
- ✓ HTML changes detection (version checking)
- ✓ Network timeout handling
- ✓ 404 handling for missing decks
- ✓ Invalid format handling
- ✓ Rate limiting respect
- ✓ Cache staleness handling
- ✓ Deck number extraction
- ✓ Archetype URL parsing
- ✓ Deck aggregation accuracy

**Estimated Test LOC**: 150-200 lines
**Test Data**: Capture HTML snapshots for regression testing

---

### 4. store_service.py (59 LOC) - CRITICAL

**What it does**:
- JSON file persistence
- Deck notes storage
- Sideboard guides storage
- Atomic writes

**Why critical**:
- Data loss risk
- File corruption risk
- No database backup

**Untested Functions**:
```python
StoreService.save_notes()
StoreService.load_notes()
StoreService.save_sideboard_guide()
StoreService.load_sideboard_guide()
StoreService.delete_note()
StoreService.delete_guide()
```

**Test Scenarios Needed**:
- ✓ Save and load round-trip
- ✓ File corruption handling
- ✓ Concurrent writes
- ✓ Disk full handling
- ✓ Unicode characters
- ✓ Large data (>1MB notes)
- ✓ Missing file handling
- ✓ Invalid JSON handling

**Estimated Test LOC**: 80-100 lines

---

### 5. metagame.py (67 LOC) - CRITICAL

**What it does**:
- MTGGoldfish web scraping
- Latest deck fetching by player name
- Fallback logic

**Why critical**:
- External dependency
- User-facing opponent tracking feature
- HTML parsing fragility

**Untested Functions**:
```python
get_latest_deck()
_parse_player_decks()
```

**Test Scenarios Needed**:
- ✓ Valid player name
- ✓ Invalid player name
- ✓ Player with no recent decks
- ✓ Network failure
- ✓ HTML format changes

**Estimated Test LOC**: 50-70 lines

---

## High Priority Modules

### 6. mtgo_decklists.py (194 LOC) - HIGH

**What it does**:
- Parses MTGO.com official decklists
- Extracts deck from HTML
- Date parsing
- Player name extraction

**Untested Functions**:
```python
get_deck_from_mtgo_decklists()
_parse_deck_html()
_extract_event_info()
```

**Test Scenarios**: HTML parsing, date formats, encoding issues

**Estimated Test LOC**: 80-100 lines

---

### 7. mana_icon_factory.py (436 LOC) - HIGH

**What it does**:
- Renders mana symbols using wxPython
- Image composition
- Caching rendered symbols
- Color gradients

**Untested Functions**: All rendering functions

**Test Scenarios**: Symbol rendering accuracy, cache behavior, color blending

**Estimated Test LOC**: 100-120 lines (requires wxPython test harness)

---

### 8. mtgo_bridge.py (147 LOC) - HIGH

**What it does**:
- Subprocess execution of .NET bridge
- JSON parsing of collection/history
- Error handling for MTGO not running

**Untested Functions**:
```python
export_collection()
export_match_history()
parse_bridge_output()
check_bridge_available()
```

**Test Scenarios**: Bridge executable not found, MTGO not running, malformed JSON, timeout

**Estimated Test LOC**: 80-100 lines

---

### 9. archetype_classifier.py (127 LOC) - HIGH

**What it does**:
- Classifies decks by archetype
- Card signature matching
- Format detection

**Untested Functions**:
```python
classify_deck()
_match_archetype()
_calculate_similarity()
```

**Test Scenarios**: Known archetypes, unknown decks, edge cases

**Estimated Test LOC**: 100-120 lines

---

## Medium Priority Modules (Partial Coverage)

### 10. deck_service.py (432 LOC) - MEDIUM

**Current Tests**: Basic tests exist
**Gaps**:
- Deck averaging logic not tested
- Format validation not tested
- Deck aggregation accuracy not tested

**Additional Test Scenarios Needed**:
- ✓ Average 5 decks with varying card counts
- ✓ Fractional card handling
- ✓ Format legality checking (Modern, Legacy, Standard)
- ✓ Deck validation edge cases

**Estimated Additional Test LOC**: 100-150 lines

---

### 11. collection_service.py (650 LOC) - MEDIUM

**Current Tests**: Minimal tests
**Gaps**:
- Async collection refresh not tested
- Ownership analysis not tested
- Missing cards calculation not tested

**Additional Test Scenarios Needed**:
- ✓ Load collection from bridge
- ✓ Async refresh with callbacks
- ✓ Deck ownership analysis accuracy
- ✓ Missing cards report
- ✓ Collection caching

**Estimated Additional Test LOC**: 150-200 lines

---

### 12. search_service.py (406 LOC) - MEDIUM

**Current Tests**: None
**Gaps**: All search and filter logic untested

**Test Scenarios Needed**:
- ✓ Name search (exact, partial, regex)
- ✓ Color filter (exact, contains, identity)
- ✓ Mana value filter (=, <, >, range)
- ✓ Type filter (creature, instant, etc.)
- ✓ Rarity filter
- ✓ Combined filters
- ✓ Empty results
- ✓ Performance with 30,000+ cards

**Estimated Test LOC**: 150-200 lines

---

## Testing Infrastructure Needs

### Test Fixtures Required

1. **Card Data Fixture** (`tests/fixtures/card_data.json`)
   - Sample of 50-100 cards
   - Covers all card types
   - Includes edge cases (double-faced, split cards)

2. **HTML Snapshots** (`tests/fixtures/html/`)
   - MTGGoldfish archetype page
   - MTGGoldfish deck page
   - MTGO decklists page

3. **Mock Services**
   - Mock HTTP responses
   - Mock file system
   - Mock SQLite database

4. **Test Helpers**
   - `create_test_deck()` - Generate valid deck text
   - `mock_collection()` - Mock collection data
   - `mock_card_db()` - Mock card database

### Test Organization

```
tests/
├── unit/
│   ├── services/
│   │   ├── test_deck_service.py
│   │   ├── test_collection_service.py
│   │   ├── test_search_service.py
│   │   └── test_store_service.py
│   ├── repositories/
│   │   ├── test_deck_repository.py
│   │   ├── test_card_repository.py
│   │   └── test_metagame_repository.py
│   ├── utils/
│   │   ├── test_card_data.py ← NEW
│   │   ├── test_card_images.py ← NEW
│   │   ├── test_archetype_classifier.py ← NEW
│   │   └── test_deck_parsing.py
│   └── navigators/
│       ├── test_mtggoldfish.py ← NEW
│       └── test_mtgo_decklists.py ← NEW
├── integration/
│   ├── test_deck_workflow.py ← NEW
│   ├── test_collection_workflow.py ← NEW
│   └── test_metagame_workflow.py ← NEW
├── ui/
│   ├── test_deck_selector.py (FIX EXISTING)
│   ├── test_panels.py ← NEW
│   └── test_handlers.py ← NEW
└── fixtures/
    ├── card_data.json ← NEW
    ├── html/ ← NEW
    └── decks/ ← NEW
```

---

## Test Coverage Roadmap

### Phase 1: Critical Modules (Sprint 1)
**Goal**: 40% coverage
**Modules**:
- ✓ card_data.py
- ✓ card_images.py
- ✓ store_service.py

**Estimated Effort**: 400-500 test lines
**Risk Reduction**: 60% (covers most critical data loss scenarios)

### Phase 2: External Dependencies (Sprint 2)
**Goal**: 55% coverage
**Modules**:
- ✓ mtggoldfish.py
- ✓ metagame.py
- ✓ mtgo_bridge.py
- ✓ mtgo_decklists.py

**Estimated Effort**: 350-450 test lines
**Risk Reduction**: 80% (covers most external failure modes)

### Phase 3: Service Layer Completion (Sprint 3)
**Goal**: 65% coverage
**Modules**:
- ✓ deck_service.py (complete)
- ✓ collection_service.py (complete)
- ✓ search_service.py (complete)

**Estimated Effort**: 400-550 test lines
**Risk Reduction**: 90%

### Phase 4: Integration & UI (Sprint 4)
**Goal**: 70% coverage
**Modules**:
- ✓ Integration tests for workflows
- ✓ Fix existing UI tests
- ✓ Add handler tests

**Estimated Effort**: 300-400 test lines
**Risk Reduction**: 95%

---

## Testing Best Practices

### 1. Use Pytest Fixtures
```python
@pytest.fixture
def card_manager():
    """Provide card manager with test data."""
    manager = CardDataManager()
    manager._cards = load_test_card_data()
    return manager
```

### 2. Mock External Dependencies
```python
@patch('requests.get')
def test_download_deck(mock_get):
    mock_get.return_value.text = SAMPLE_DECK_HTML
    deck = download_deck(12345)
    assert "Lightning Bolt" in deck
```

### 3. Test Error Paths
```python
def test_download_deck_network_failure():
    with patch('requests.get', side_effect=RequestException):
        deck = download_deck(12345)
        assert deck is None  # or raises exception
```

### 4. Use Parameterized Tests
```python
@pytest.mark.parametrize("format,expected", [
    ("Modern", True),
    ("Legacy", True),
    ("Standard", False),
])
def test_deck_legality(format, expected):
    assert is_legal(BURN_DECK, format) == expected
```

### 5. Test Data Isolation
```python
@pytest.fixture(autouse=True)
def reset_global_state():
    """Reset singletons between tests."""
    reset_all_services()
    reset_all_repositories()
    yield
```

---

## Success Metrics

| Metric | Current | Phase 1 | Phase 2 | Phase 3 | Target |
|--------|---------|---------|---------|---------|--------|
| Coverage % | 15-18% | 40% | 55% | 65% | 70% |
| Test Lines | 2,719 | 3,200 | 3,600 | 4,000 | 4,500 |
| Critical Modules | 0/5 | 3/5 | 5/5 | 5/5 | 5/5 |
| Integration Tests | 0 | 0 | 0 | 3 | 5 |
| Broken Tests | 1 | 0 | 0 | 0 | 0 |

---

## Conclusion

Increasing test coverage from 15-18% to 65-70% requires adding approximately **1,800-2,000 lines of tests** across four phases. The critical modules (Phase 1) should be prioritized immediately to reduce data loss and corruption risks.

Focus on:
1. **Data integrity** (card_data, card_images, store_service)
2. **External dependencies** (web scraping, bridge integration)
3. **Business logic** (service layer completion)
4. **User workflows** (integration tests)

With this systematic approach, the codebase will have sufficient test coverage to support confident refactoring and parallel development.

---

**Document Version**: 1.0
**Last Updated**: November 14, 2025
**Related Documents**:
- CODEBASE_AUDIT_2025-11-14.md (comprehensive audit)
- ARCHITECTURE.md (architecture overview)
- tests/TESTING_GUIDE.md (pytest setup)
