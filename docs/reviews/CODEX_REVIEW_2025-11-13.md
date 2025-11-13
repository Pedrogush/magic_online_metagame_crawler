# CODEX Branch Review Report: refactor-deck-selector-architecture-011CV2pbBY7A3j4q2Mfx55c4

## Overview
- Conducted a full code review of the current branch with an emphasis on the new deck selector architecture.
- Focused on correctness of metagame fetching, deck aggregation, collection handling, and UI/domain helpers exposed in `services/` and `repositories/`.
- Documented the most pressing issues below so the branch stays mergeable and the deck builder experience remains reliable.

## Key Findings
1. **Archetype dictionary mismatch prevents deck fetching** (`repositories/metagame_repository.py:92-115`, `navigators/mtggoldfish.py:60-134`) – The repository expects a `url` but stores/requests `href`, so decks are always cached under `""` and `get_archetype_decks` is invoked with the full dict instead of the slug (resulting in 404s), meaning the UI never loads archetype decks.
2. **Deck download flow never returns any deck text** (`repositories/metagame_repository.py:118-140`, `services/deck_service.py:245-287`, `navigators/mtggoldfish.py:288-319`) – Deck dicts contain a `number`, not a `url`, but `download_deck_content` blindly passes the dict to `download_deck`, so `deck_content` is always `None`. Averaging and downloads thus silently fail.
3. **Cache key normalization is inconsistent** (`repositories/metagame_repository.py:56-78` vs `navigators/mtggoldfish.py:60-97`) – The navigator lowercases format names before persisting cache entries, but the repository reads/writes using the human-facing case. Every cache lookup misses and triggers network IO even when the cached file is valid.
4. **Stale-cache fallback never fires** (`repositories/metagame_repository.py:144-179`) – `_load_cached_archetypes` resets `max_age=None` to the default TTL, so callers attempting to bypass expiration after a fetch failure always discard the cache, leaving users without any data when MTGGoldfish is unreachable.
5. **Deck averaging loses fractional counts** (`services/deck_service.py:39-88`) – Quantities are cast to `int(float(...))` immediately, dropping fractional values from tournament averages before aggregation, which skews results.
6. **Land estimation ignores counts** (`services/deck_service.py:153-161`) – `estimated_lands` counts only distinct land names instead of summing card quantities, so even decks with 23 Islands report one land.
7. **Collection loading is a stub** (`repositories/card_repository.py:237-252`) – `load_collection_from_file` always returns an empty list, breaking `CollectionService.load_collection` and making cached inventories no-ops.
8. **Card ownership lookups are case-sensitive while caches store lowercase** (`services/collection_service.py:117-136`, `306-330`) – When loading from cache, all card names are lowercased, but `owns_card`/`get_owned_count` query using the case from the deck list, so ownership indicators never trigger for cached collections.
9. **Deck file serializer allows blank filenames** (`repositories/deck_repository.py:266-296`) – `save_deck_to_file` writes `".txt"` when the deck name is empty or whitespace, which is invalid on some platforms and easily overwritten; should reuse `utils.deck.sanitize_filename` with a fallback like `saved_deck`.

## Suggested Next Steps
1. Wire the repository to use the slug/number fields that the navigator actually provides and return deck text from `download_deck_content`, then heal the averaging UI.
2. Normalize cache keys (lowercase at both ends) and honor `max_age=None` so stale data is usable when live fetches fail.
3. Preserve fractional card counts during parsing and aggregate land totals correctly to avoid misleading statistics.
4. Implement real collection file parsing, keep ownership lookups in sync with the normalized cache, and harden `save_deck_to_file` against empty names.

## Testing / Validation
- Not run (static review). Please rerun unit/UI tests after applying the fixes above before merging.
