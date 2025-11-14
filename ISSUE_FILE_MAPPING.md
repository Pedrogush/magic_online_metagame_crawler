# GitHub Issues - File Mapping
## Issues Without Comments (Ready to Work On)

This document maps each open GitHub issue to the specific files that would need to be modified.

---

### #92 - Card inspector image sizing is inconsistent between different printings

**Description**: Frame size changes which makes arrows shift in place

**Files to Modify**:
- `widgets/panels/card_inspector_panel.py` - Main card inspector implementation
- `widgets/card_image_display.py` - Image display component

**Estimated Complexity**: Low
**Category**: UI/UX

---

### #89 - Card image display looks too abrupt, needs smoothing animations/mouseover

**Description**: Add pop-up card inspector on mouseover and smoothing animations

**Files to Modify**:
- `widgets/panels/card_inspector_panel.py` - Add animation logic
- `widgets/card_image_display.py` - Add mouseover events
- `widgets/panels/card_table_panel.py` - Card list mouseover integration
- `widgets/panels/card_box_panel.py` - Card grid mouseover integration

**Estimated Complexity**: Medium
**Category**: UI/UX Enhancement

---

### #87 - Fix card inspector for double-faced cards

**Description**: Add face aliases to printings index and teach image cache to use // fallbacks

**Files to Modify**:
- `widgets/panels/card_inspector_panel.py` - Handle double-faced card display
- `utils/card_images.py` - Image cache with // fallback logic
- `utils/card_data.py` - Face aliases in printings index
- `services/image_service.py` - Double-faced card resolution

**Estimated Complexity**: Medium
**Category**: Bug Fix

---

### #56 - Cross-check deckbuilder inventory against latest collection export

**Description**: Load cached collection JSON and compare without requiring live bridge

**Files to Modify**:
- `services/collection_service.py` - Add offline collection loading method
- `widgets/panels/deck_builder_panel.py` - Display ownership indicators
- `repositories/card_repository.py` - Collection cache access

**Estimated Complexity**: Medium
**Category**: Feature Enhancement

---

### #55 - Add outboard/sideboard guide section to deckbuilder

**Description**: Extend UI to include matchup planning panel for take-out/take-in lists

**Files to Modify**:
- `widgets/deck_selector.py` - Add new tab/section
- `widgets/panels/sideboard_guide_panel.py` - Extend or create new panel
- `services/store_service.py` - Persist sideboard guides
- `widgets/handlers/sideboard_guide_handlers.py` - Event handling

**Estimated Complexity**: High
**Category**: Feature Enhancement

---

### #54 - Test the challenge alarm workflow

**Description**: Add pytest coverage for challenge alarm timer/alert logic

**Files to Create/Modify**:
- `tests/test_timer_alert.py` - **NEW FILE** - Unit tests for alarm
- `tests/ui/test_timer_alert_ui.py` - **NEW FILE** - UI tests
- `widgets/timer_alert.py` - May need testability refactoring

**Estimated Complexity**: Medium
**Category**: Testing

---

### #52 - Handle waiting for Manatraders bot to take cards

**Description**: Automate detection when bot completes card acquisition

**Files to Modify**:
- `utils/gamelog_parser.py` - Parse trade completion events
- `widgets/identify_opponent.py` - Trade automation logic (if exists here)
- **NEW**: `utils/trade_automation.py` - Create trade automation module

**Estimated Complexity**: High
**Category**: Feature Enhancement (Requires MTGO SDK)

---

### #51 - Automate Manatraders trade acceptance

**Description**: Automatically trigger "take all cards" and confirm trade

**Files to Modify**:
- **Same as #52** - These issues are related
- `utils/gamelog_parser.py` - Detect Manatraders bot
- **NEW**: `utils/trade_automation.py` - Trade automation implementation

**Estimated Complexity**: High
**Category**: Feature Enhancement (Requires MTGO SDK)

---

### #28 - Fix deck download pipeline to return deck text

**Description**: Pipeline passes full dict instead of deck ID, causing navigation to fail

**Files to Modify**:
- `navigators/mtggoldfish.py:288-319` - `download_deck()` function
- `services/deck_service.py:245-287` - `download_daily_deck_average()` method
- `repositories/metagame_repository.py:118-140` - `download_deck_content()` method

**Estimated Complexity**: Medium
**Category**: Bug Fix (Critical from CODEX review)

---

### #27 - Fix metagame archetype dict handling

**Description**: Repository uses nonexistent 'url' key; implement slug-based storage

**Files to Modify**:
- `repositories/metagame_repository.py:92-115` - Cache key handling
- `navigators/mtggoldfish.py:60-134` - Archetype dict structure

**Estimated Complexity**: Medium
**Category**: Bug Fix (Critical from CODEX review)

---

### #21 - [MEDIUM] Extract mixed concerns from deck_selector.py

**Description**: File combines UI, event handlers, state, file I/O, and legacy migration

**Files to Modify**:
- `widgets/deck_selector.py:71-116` - Extract module-level file I/O
- `widgets/deck_selector.py:559-593` - Extract window settings persistence
- **NEW**: `services/window_settings_service.py` - Window preferences service
- **NEW**: `scripts/legacy_migration.py` - One-time migration script

**Estimated Complexity**: High
**Category**: Refactoring (from audit)

---

### #19 - [LOW] Verify path traversal protection in filename sanitization

**Description**: Sanitization needs verification for parent refs, drive letters, null bytes

**Files to Modify**:
- `widgets/deck_selector.py:829-836` - Filename sanitization call site
- `utils/deck.py` - `sanitize_filename()` function (if exists there)
- `tests/test_deck_utils.py` - Add security tests

**Estimated Complexity**: Low
**Category**: Security Hardening

---

### #18 - [LOW] Reduce redundant repository calls

**Description**: Multiple card manager retrievals should consolidate to single parameter

**Files to Modify**:
- `widgets/deck_selector.py:1009-1029` - Redundant card manager calls
- Methods that repeatedly call `card_repo.get_card_manager()`

**Estimated Complexity**: Low
**Category**: Performance Optimization

---

### #14 - [MEDIUM] Extract large complex methods in deck_selector

**Description**: Multiple 48+ line methods mixing UI and business logic

**Files to Modify**:
- `widgets/deck_selector.py:402-428` - `_build_right_panel()`
- `widgets/deck_selector.py:1434-1482` - `_build_daily_average_deck()`
- `widgets/deck_selector.py:813-857` - `on_save_clicked()`
- `widgets/deck_selector.py:1203-1251` - `_handle_zone_add()`

**Extract to**:
- `services/deck_service.py` - Business logic methods
- Smaller private methods in `deck_selector.py`

**Estimated Complexity**: Medium
**Category**: Refactoring (from CLAUDE review)

---

## Summary by Category

### Critical Bugs (Fix First)
- #28 - Fix deck download pipeline
- #27 - Fix metagame archetype dict handling

### Bug Fixes
- #87 - Fix card inspector for double-faced cards
- #92 - Card inspector image sizing

### Feature Enhancements
- #56 - Cross-check deckbuilder inventory
- #55 - Add outboard/sideboard guide
- #52 - Handle Manatraders bot wait
- #51 - Automate Manatraders trade

### Refactoring
- #21 - Extract mixed concerns from deck_selector
- #14 - Extract large complex methods

### Testing
- #54 - Test challenge alarm workflow

### UI/UX
- #89 - Card image display animations

### Performance
- #18 - Reduce redundant repository calls

### Security
- #19 - Verify path traversal protection

---

## Issues WITH Comments (Being Worked On - Skip)

These issues have comments and are likely already claimed:
- #91 - Mana symbols in deckbuilder search (1 comment)
- #90 - Duplicate card entries in mainboard (1 comment)
- #79 - Card inspector double faced cards (1 comment)
- #29 - Normalize archetype cache keys (2 comments)
- #22 - Standardize error handling strategy (1 comment)

---

**Generated**: 2025-11-14
**Source**: GitHub API via WebFetch
**Purpose**: Map issues to files for efficient development workflow
