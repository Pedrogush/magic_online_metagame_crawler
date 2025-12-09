# Codebase Review (MTGO Deck Builder)

## Context
- MTGO scraping is currently stubbed and will move to an external, continuously-running service; the app should consume that data instead of scraping locally.
- All previous documentation was removed in favor of this focused review and action plan.

## Actionable Work Items

### 1) Decompose `AppController` into testable components
- Extract settings/session persistence into a dedicated manager (load/save/restore window + deck state).
- Extract deck/archetype orchestration into a service that accepts injected repos/services instead of globals.
- Introduce constructor injection (or a lightweight factory) so unit tests can provide mocks; remove singleton globals where practical.
- Update `AppFrame` wiring to use the new components; keep UI logic thin.
- Add unit tests for the extracted components (settings serialization, deck/archetype workflows) without wx.

### 2) Fix background thread lifecycle and cancellation
- Replace ad-hoc daemon `BackgroundWorker` loops with a managed executor that accepts a stop event.
- Wire executor start/stop to frame lifecycle (init/close); ensure MTGO status polling and other loops exit cleanly.
- Add cancellation/timeouts to bridge status checks so offline/unsupported platforms do not spam logs.
- Add tests that simulate stop signals and assert threads/flags are cleared.

### 3) Prepare for external MTGO data service integration
- Remove or disable in-app MTGO scraping/background fetch code paths; guard with a clear feature flag and UI messaging.
- Define a data-provider interface (e.g., `MTGODataSource`) that can read from the future external service or local cache.
- Add configuration/env plumbing for the service endpoint plus error handling and offline fallback.
- Write unit tests that stub the provider and verify deck/archetype merging logic remains correct.

### 4) Clean up image/bulk data service surface
- Remove unused APIs (`ensure_data_ready`, `load_bulk_data_direct`, etc.) and align controller calls to the minimal surface.
- Add explicit state flags + logging for load vs download, and ensure locks prevent concurrent downloads.
- Cover `ImageService` with tests for cache-exists checks, forced refresh, and error handling.

### 5) Harden metagame/deck repository cache behavior
- Add tests for cache expiry/fallback in `MetagameRepository` (archetypes + decks) including corrupt JSON recovery.
- Add source-filter tests to ensure MTGO/Goldfish merging order and sorting are deterministic.
- Normalize date parsing in one helper with coverage for both `YYYY-MM-DD` and `MM/DD/YYYY` inputs.

### 6) Add user feedback/diagnostics loop
- Add a lightweight “Send feedback / export diagnostics” entry in the UI that packages logs + a short form.
- Implement opt-in, anonymized event logging (feature use, background job outcomes) persisted locally.
- Provide an export-to-file flow that users can share; add unit tests for log packaging (no network).

## Notes
- Each item is sized to fit in a small PR; issues should be opened per item so they can be tracked and parallelized.
