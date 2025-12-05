# Issue #165 – Extract MTGO decklist parsing into a separate service

This plan outlines how to pull MTGO decklist ingestion/parsing out of the desktop app and expose it
through a small REST API hosted elsewhere. The goal is to replace in-app scraping with a single API
call for MTGO archetype/deck data.

## Current state (in this repo)
- Scraping/parsing: `navigators/mtgo_decklists.py` fetches index/event pages and caches payloads.
- Background ingestion: `services/mtgo_background_service.py` pulls events, classifies decks, writes
  deck text to the local cache, and stores metadata for UI use.
- Aggregation helpers: `utils/metagame_stats.py` updates MTGO deck caches and aggregates decklists.
- UI hooks: `controllers/app_controller.py` kicks off `_start_mtgo_background_fetch`; deck loading
  merges MTGGoldfish + MTGO (`repositories/metagame_repository.py`).
- Scripts/tests: `scripts/fetch_mtgo_*`, `scripts/list_mtgo_events.py`, `test_mtgo_fetch.py`
  exercise the scraping stack.
- Caches/constants: `utils/constants.py` defines MTGO cache paths (`mtgo_decks.json`,
  `mtgo_deck_metadata.json`).

## Target architecture (new repository)
- New repo (e.g., `mtgo-decklists-service`) housing the MTGO ingestion + API stack.
- Tech stack: Python 3.11+, FastAPI (REST), uvicorn, SQLModel/SQLAlchemy on Postgres (or SQLite
  initially), Redis (optional) for request-level caching/rate limiting, dockerized for deploys.
- Modules:
  - `scraper`: existing parsing logic from `navigators/mtgo_decklists.py` (port with minimal deps).
  - `ingestion`: scheduler/worker (APScheduler/Celery/cron) to crawl MTGO index monthly/daily,
    fetch event pages, normalize deck payloads, and classify archetypes (reuse
    `utils/archetype_classifier` logic or bundle a shared wheel).
  - `storage`: ORM models for events, decks, cards, archetypes, and cache snapshots; migration setup
    via Alembic.
  - `api`: FastAPI app exposing read-only endpoints; auth via token/header to gate writes if needed.
  - `clients`: thin HTTP client for consumers (this app + scripts) published as a small pip package.
  - `ops`: Dockerfile/compose, health checks, logging/metrics hooks, deployment manifests.

## API surface (v1 sketch)
- `GET /healthz` – readiness/liveness.
- `GET /events?format=modern&start=2025-12-01&end=2025-12-07&limit=40` – MTGO events with metadata.
- `GET /events/{event_id}/decks` – deck summaries for an event (player/result/archetype ids).
- `GET /decks?archetype=Yawgmoth&format=modern&limit=50` – search/filter deck summaries.
- `GET /decks/{deck_id}` – full deck payload (main/side) plus archetype/result metadata.
- `GET /decks/{deck_id}/text` – text export for direct import into the desktop app.
- `GET /archetypes?format=modern` – archetype list + shares (if computed server-side).
- Responses should include stable ids, publish dates, source tags, and cache timestamps to allow the
  client to reuse local caches. Add ETags/If-None-Match where practical.

## Migration plan for this repo
- Add config for external MTGO API (`MTGO_API_BASE_URL`, optional auth header).
- Introduce a lightweight API client module (`services/mtgo_api_client.py`) to replace direct
  scraping calls.
- Replace `services/mtgo_background_service.py` usage with API-driven fetches; convert background
  task to call the service and write deck text/metadata to local cache if needed.
- Update `repositories/metagame_repository.py` to source MTGO decks via the API client instead of
  local JSON caches; keep MTGGoldfish logic untouched.
- Remove/retire scraping-specific modules (`navigators/mtgo_decklists.py`,
  `utils/metagame_stats.py`, MTGO scripts) after the API client is validated; keep a feature flag to
  fall back to legacy scraping during rollout.
- Adjust UI wiring (`controllers/app_controller.py`) to handle API unavailability gracefully and
  surface status to users.
- Update tests: replace scraper-heavy tests with API client contract tests (with recorded fixtures);
  keep integration smoke tests behind a flag for legacy mode until deprecation.

## New service delivery phases
1) Repo bootstrap: project skeleton, Dockerfile/compose, lint/test CI, base FastAPI app + healthz.
2) Port scraping + normalization: move `mtgo_decklists` logic, add robust caching/retry/backoff.
3) Persistence: define models for events/decks/cards/archetypes, migrations, and seed scripts.
4) Ingestion worker: scheduled crawler to keep data fresh (hourly/daily), with logging + metrics.
5) API implementation: endpoints above, pagination, filtering, simple auth, and ETag support.
6) Client package: Python client with typed responses and basic retry; wire into this app behind
   config flag.
7) Cutover: switch default mode to API, monitor, then delete legacy scraping paths and caches.

## Open questions
- Do we want server-side archetype classification (requires shipping card data + classifier) or keep
  archetype assignment in the desktop app?
- Preferred datastore for production (Postgres vs. managed SQLite) and hosting target (VM, container
  service, etc.)?
- Any rate limits or auth requirements for the public API?
