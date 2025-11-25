# Architecture (Updated)

This document reflects the current refactored codebase (controller-driven UI, consolidated constants, radar and sideboard guide features).

## High-Level Shape

- **Entry**: `main.py` → `controllers/app_controller.AppController` → `widgets/app_frame.AppFrame` (UI).
- **Presentation**: `widgets/` (frame + panels) with event-handler mixins under `widgets/handlers/`.
- **Business Logic**: `services/` (deck, collection, image, search, radar, state, deck_research).
- **Persistence/State**: `repositories/` (deck, card, metagame), stores on disk (notes/outboard/guide), Mongo optional.
- **Utilities**: `utils/` (constants.py, card_images, card_data, deck utilities, search filters, background worker, deck_text_cache, mana icons, etc.).
- **External**: `navigators/` (mtggoldfish, mtgo_decklists), `dotnet/MTGOBridge/`.

## Current Directory Map

```
controllers/
  app_controller.py        # Owns services/repos, creates AppFrame, runs initial loads
widgets/
  app_frame.py             # Thin frame; uses handler mixins
  handlers/
    app_event_handlers.py
    card_table_panel_handler.py
    sideboard_guide_handlers.py
  panels/
    deck_builder_panel.py  # Radar-aware search UI
    deck_research_panel.py
    deck_stats_panel.py
    sideboard_guide_panel.py
    card_inspector_panel.py
    radar_panel.py
    deck_notes_panel.py
    card_table_panel.py
    card_box_panel.py
  dialogs/
    guide_entry_dialog.py
    image_download_dialog.py
  buttons/ (toolbar, deck actions, mana)
  identify_opponent.py, match_history.py, metagame_analysis.py, timer_alert.py
services/
  deck_service.py, deck_research_service.py, collection_service.py,
  search_service.py, image_service.py, radar_service.py, state_service.py
repositories/
  deck_repository.py (decklist hash), card_repository.py, metagame_repository.py
utils/
  constants.py (all paths/constants), card_images.py, card_data.py,
  deck.py, search_filters.py, mana_icon_factory.py, background_worker.py,
  deck_text_cache.py, etc.
navigators/
  mtggoldfish.py, mtgo_decklists.py
 dotnet/MTGOBridge/        # External bridge
 tests/                    # Unit + UI (UI builds AppFrame via controller)
```

## Key Flows (Controller-Centric)

- **Startup**: main.py → AppController() → AppFrame; controller.run_initial_loads triggers archetypes fetch, collection cache load, bulk image check; callbacks marshal via wx.CallAfter.
- **Bulk Images**: controller.check_and_download_bulk_data → image_service.check/download → controller.load_bulk_data_into_memory → AppFrame _on_bulk_data_loaded → card inspector gets printings.
- **Collection**: AppFrame toolbar → controller.refresh_collection_from_bridge → collection_service.refresh_from_bridge_async → UI updates status + ownership tables.
- **Deck Download**: AppFrame delegates to controller.download_and_display_deck → navigators.mtggoldfish.download_deck/read_curr_deck_file → AppFrame updates tables/stats.
- **Sideboard Guide**: Stored by decklist hash (guide_store/outboard_store). CSV import/export supported; guide_entry_dialog takes main/side cards; Save & Continue supported.
- **Radar**: DeckBuilderPanel opens RadarDialog (widgets/panels/radar_panel.py) → radar_service.calculate_radar → results can export as decklist or feed builder filters.
- **Deck Builder**: search_service.search_with_builder_filters, optional radar filters; results table drives card inspector.

## Constants & Paths

All paths/constants live in `utils/constants.py` (CONFIG_DIR, CACHE_DIR, DECKS_DIR, settings files, cache files, UI colors, formats, service thresholds). Legacy `paths.py`, `service_config.py`, `game_constants.py`, `ui_constants.py` are removed.

## Technical Debt / Risks

- **Docs Drift**: Keep this file in sync when adding/removing modules (controllers, services, handler mixins).
- **Single-Threaded UI**: Background threads marshal via wx.CallAfter; no asyncio. Long tasks still at risk if callbacks misused.
- **Singletons**: Services/repos are global; tests reset via controller resets, but concurrency/user state should be monitored.
- **Partial Migrations**: Some UI code still does light business logic; continue moving logic into services/controller.
- **Platform Assumptions**: UI tests gated to Windows/wx display; MTGOBridge is Windows-only.

## Update Checklist (when changing architecture)
- Update directory map above.
- Note new services or removed modules.
- Refresh key flows if controller/wiring changes.
- Verify constants live in `utils/constants.py` and nowhere else.

_Last updated: refactor-separate-ui-business-logic branch._
