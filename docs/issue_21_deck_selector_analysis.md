# Issue 21 – Deck Selector Mixed Concerns

## Scope & Goal
Issue 21 tracks the effort to confine everything under `widgets/` to UI duties only. `widgets/deck_selector.py` currently acts as both the UI surface and the orchestration layer for application state, persistence, metrics, and remote IO. This document captures the primary “mixed concern” hotspots along with concrete extraction targets so we can migrate the business logic into repositories, services, or helpers under `utils/`.

## Identified Extraction Targets

### 1. Configuration bootstrap and deck save directory (`widgets/deck_selector.py:88-210`)
- Observations: This block reads/migrates JSON config files, ensures directories exist, sets defaults, and exposes `DECK_SAVE_DIR`. None of this is UI-specific.
- Proposal: Move into a dedicated module (e.g., `config/deck_selector_settings.py`). Expose a dataclass or helper that knows how to load, migrate, and validate the deck selector config so the frame only consumes a ready-made settings object.

### 2. Formatting helpers (`widgets/deck_selector.py:126-132`)
- Observations: `format_deck_name` is a pure helper used to present deck rows.
- Proposal: Relocate to `utils/deck_formatter.py` (or `services/deck_service`) to keep formatting logic next to other deck-domain concerns and make it reusable by CLI/tests.

### 3. Background worker abstraction (`widgets/deck_selector.py:135-163`)
- Observations: `_Worker` manages background threads and marshals results back onto the GUI thread. It is a generic UI infrastructure piece that will likely be reused by other widgets.
- Proposal: Promote it to `widgets/background_worker.py` (the file already exists untracked) and import it wherever we need background dispatching.

### 4. Session, preference, and persistence logic (`widgets/deck_selector.py:574-715`)
- Observations: `_restore_session_state`, `_load_window_settings`, `_save_window_settings`, `_serialize_zone_cards`, `_apply_window_preferences`, and `_schedule_settings_save` manage JSON IO, type coercion, and deck state persistence.
- Proposal: Extract a `DeckSelectorStateStore` in `utils` or `services` that handles reading/writing settings, clamping values, and providing typed results. The widget should only call `state_store.load()` / `state_store.save(current_snapshot)`.

### 5. Archetype and MTGGoldfish fetch orchestration (`widgets/deck_selector.py:721-821`, `786-821`)
- Observations: `fetch_archetypes`, `_load_decks_for_archetype`, `_present_archetype_summary`, and `_download_and_display_deck` invoke network helpers, perform retries, build summaries, and juggle deck repository state.
- Proposal: Create a `DeckResearchController` under `services/` that exposes async-friendly methods such as `load_archetypes(format)`, `load_archetype_decks(archetype)`, and `download_deck(number)`, returning DTOs for the widget to render.

### 6. Collection management and MTGO bridge IO (`widgets/deck_selector.py:828-867`)
- Observations: `_load_collection_from_cache` and `_refresh_collection_inventory` include cache validation, status text, and bridge calls.
- Proposal: Move these into the existing `CollectionService` or wrap them with a `CollectionController` that normalizes the return data (filepath, counts, age). The widget should only format the text given a data object.

### 7. Card-image bulk data lifecycle (`widgets/deck_selector.py:868-952`)
- Observations: `_check_and_download_bulk_data`, `_after_bulk_data_check`, `_on_bulk_data_check_failed`, and `_load_bulk_data_into_memory` coordinate download decisions, background jobs, and status messaging.
- Proposal: Introduce a `CardImageDataManager` service that encapsulates the state machine (force cached vs. download) and surfaces simple callbacks (e.g., `ensure_printing_index(force_cached, max_age, on_ready, on_error)`).

### 8. Zone editing and deck text serialization (`widgets/deck_selector.py:948-967`)
- Observations: `_after_zone_change` updates repositories, persists outboard zones, generates deck text, and updates UI state.
- Proposal: Extract zone serialization/mutation into `DeckService` or a helper so the frame merely relays user intent (`zone_service.update(zone, cards)`), subscribes to change events, and refreshes the panels.

### 9. Daily average aggregation (`widgets/deck_selector.py:982-1053`)
- Observations: `_start_daily_average_build` contains filtering, progress dialog orchestration, repeated calls to deck repo/service, and buffer rendering.
- Proposal: Move the aggregation pipeline into `DeckService` (or a new `AverageDeckService`) that takes deck rows + callbacks, returning deck text and statistics. The widget should only own the progress dialog and display the result/error.

### 10. Card data preload (`widgets/deck_selector.py:1055-1084`)
- Observations: `ensure_card_data_loaded` toggles repository flags, kicks background jobs, and displays message boxes on failure.
- Proposal: Provide a `CardDataLoader` helper that exposes `ensure_loaded(on_ready, on_error)`; it should know when data is loading, manage repository state, and surface typed errors.

## Suggested Refactor Flow
1. Extract the pure helpers (`format_deck_name`, `_Worker`) and configuration bootstrap first to unblock other modules.
2. Introduce a controller/service layer (e.g., `DeckSelectorController`) that owns deck/collection/image loading state, while the widget binds UI events to controller callbacks.
3. Move persistence responsibilities into a reusable store class that the widget depends on via composition.
4. Incrementally migrate each group of methods (data loading, collection, bulk image data, daily average) to the new services, replacing direct domain manipulation with service method calls.

Documenting the plan in this file keeps Issue 21 visible and reviewable while we stage the actual refactors over multiple PRs.
