"""Scrape decklists from https://www.mtgo.com/decklists."""

from __future__ import annotations

import json
import re
import threading
import time
import uuid
from collections import Counter, defaultdict
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from curl_cffi import requests
from loguru import logger

from utils.constants import MTGO_DECK_CACHE_FILE

BASE_URL = "https://www.mtgo.com"
DECKLIST_INDEX_URL = "https://www.mtgo.com/decklists/{year}/{month:02d}"
DEFAULT_TIMEOUT = 30
MAX_PARALLEL_WORKERS = 15

# Regex pattern to extract JSON payload from MTGO decklist pages
DETAIL_RE = re.compile(r"window\.MTGO\.decklists\.data\s*=\s*(\{.*?\});", re.DOTALL)

# Global lock to prevent concurrent cache writes (main thread + background preloader)
_cache_write_lock = threading.Lock()


def _load_cache() -> dict[str, Any]:
    if not MTGO_DECK_CACHE_FILE.exists():
        return {}
    try:
        with MTGO_DECK_CACHE_FILE.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except json.JSONDecodeError as exc:
        logger.warning(f"Invalid MTGO deck cache JSON ({MTGO_DECK_CACHE_FILE}): {exc}")
        # Backup corrupted cache and start fresh
        backup_path = MTGO_DECK_CACHE_FILE.with_suffix(".json.corrupt")
        try:
            MTGO_DECK_CACHE_FILE.rename(backup_path)
            logger.info(f"Backed up corrupted cache to {backup_path}")
        except OSError:
            logger.warning(f"Could not backup corrupted cache, deleting it")
            try:
                MTGO_DECK_CACHE_FILE.unlink()
            except OSError:
                pass
        return {}
    except Exception as exc:
        logger.error(f"Unexpected error loading MTGO cache: {exc}")
        return {}


def _save_cache(cache: dict[str, Any]) -> None:
    """
    Save cache with atomic write and thread-safe locking.

    Uses a global lock to prevent concurrent writes from:
    - Main thread parallel workers
    - Background cache preloader service
    """
    import platform

    # Acquire global lock to prevent concurrent saves
    with _cache_write_lock:
        MTGO_DECK_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        # Use unique temp filename
        unique_suffix = f".tmp.{uuid.uuid4().hex}"
        temp_file = MTGO_DECK_CACHE_FILE.with_suffix(unique_suffix)

        try:
            # Write to temp file
            with temp_file.open("w", encoding="utf-8") as fh:
                json.dump(cache, fh, indent=2)

            # On Windows, delete target file first (with retry for file locking)
            if platform.system() == 'Windows' and MTGO_DECK_CACHE_FILE.exists():
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        MTGO_DECK_CACHE_FILE.unlink()
                        break  # Success
                    except OSError as exc:
                        if attempt < max_retries - 1:
                            # File is locked, wait and retry
                            time.sleep(0.1 * (attempt + 1))  # 0.1s, 0.2s, 0.3s
                        else:
                            # Final attempt failed, log but continue
                            logger.debug(f"Could not delete existing cache file after {max_retries} attempts: {exc}")

            # Atomic rename (on Unix) or regular rename (on Windows after deletion)
            temp_file.replace(MTGO_DECK_CACHE_FILE)

        except Exception as exc:
            logger.error(f"Failed to save MTGO cache: {exc}")
            # Clean up temp file if it exists
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except OSError:
                    pass
            raise


def _fetch_html(url: str, stream_optimize: bool = True) -> str:
    """
    Fetch HTML from MTGO.com with optional streaming optimization.

    When stream_optimize=True, stops downloading as soon as the JSON payload
    is found, saving bandwidth since the script tag appears before main content.

    Args:
        url: URL to fetch
        stream_optimize: If True, use streaming to stop early when JSON is found

    Returns:
        HTML content (full page or partial if streaming)
    """
    logger.debug(f"Fetching {url}")

    if not stream_optimize:
        # Original behavior: fetch entire page
        response = requests.get(url, impersonate="chrome", timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        return response.text

    # Streaming optimization: stop when we have the JSON payload
    response = requests.get(url, impersonate="chrome", timeout=DEFAULT_TIMEOUT, stream=True)
    response.raise_for_status()

    # Pattern to find: window.MTGO.decklists.data = {...};
    # We need to find the complete JSON object including the closing };
    accumulated = ""
    chunk_size = 8192  # 8KB chunks
    total_bytes = 0

    try:
        for chunk in response.iter_content(chunk_size=chunk_size):
            if chunk:
                # Decode chunk manually to handle encoding issues
                try:
                    chunk_text = chunk.decode('utf-8', errors='replace')
                except (UnicodeDecodeError, AttributeError):
                    # If chunk is already a string or decode fails
                    chunk_text = str(chunk)

                accumulated += chunk_text
                total_bytes += len(chunk)

                # Check if we have the complete JSON payload
                # Look for the pattern with the closing };
                if "window.MTGO.decklists.data" in accumulated:
                    # Try to match the complete pattern
                    match = DETAIL_RE.search(accumulated)
                    if match:
                        # Found complete JSON! Calculate how much we saved
                        saved_pct = 0
                        if response.headers.get('content-length'):
                            total_size = int(response.headers['content-length'])
                            saved_pct = round((1 - total_bytes / total_size) * 100, 1)

                        logger.debug(
                            f"Stream optimization: stopped after {total_bytes} bytes "
                            f"(saved ~{saved_pct}% bandwidth)"
                        )
                        # Close connection to stop downloading
                        response.close()
                        return accumulated

        # If we got here, we read the entire response without finding JSON
        # This is expected for invalid/404 pages, so log at debug level
        logger.debug("Stream optimization: read entire response without finding JSON pattern")
        return accumulated

    except Exception as exc:
        logger.warning(f"Stream optimization failed: {type(exc).__name__}: {str(exc) or repr(exc)}, falling back to full fetch")
        try:
            response.close()
        except Exception:
            pass
        # Fallback to non-streaming
        response = requests.get(url, impersonate="chrome", timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        return response.text


def _classify_event(title: str) -> tuple[str | None, str | None]:
    title_lower = (title or "").lower()
    fmt = None
    words = title.split()
    if words:
        fmt = words[0].capitalize()
    event_type = "other"
    if "league" in title_lower:
        event_type = "league"
    elif "challenge" in title_lower:
        event_type = "challenge"
    elif "preliminary" in title_lower:
        event_type = "preliminary"
    elif "super qualifier" in title_lower:
        event_type = "super_qualifier"
    elif "qualifier" in title_lower:
        event_type = "qualifier"
    return fmt, event_type


def fetch_decklist_index(year: int, month: int) -> list[dict[str, Any]]:
    """Return decklist entries for the given year/month."""
    cache = _load_cache()
    index_cache = cache.setdefault("index", {})
    key = f"{year}-{month:02d}"
    if key in index_cache:
        return index_cache[key]["entries"]

    url = DECKLIST_INDEX_URL.format(year=year, month=month)
    html = _fetch_html(url)
    soup = BeautifulSoup(html, "lxml")
    entries: list[dict[str, Any]] = []
    for li in soup.select("li.decklists-item"):
        link = li.find("a", class_="decklists-link")
        if not link or not link.get("href"):
            continue
        full_url = urljoin(BASE_URL, link["href"])
        title_el = li.find("h3")
        title = title_el.get_text(strip=True) if title_el else None
        icon = li.find("div", class_="decklists-icon")
        format_hint = None
        if icon:
            for cls in icon.get("class", []):
                if cls != "decklists-icon":
                    format_hint = cls
                    break
        time_el = li.find("time", class_="decklists-date")
        publish_date = time_el.get("datetime") if time_el else None
        fmt, event_type = _classify_event(title or "")
        if format_hint and not fmt:
            fmt = format_hint.replace("-", " ").title()
        entries.append(
            {
                "title": title,
                "format": fmt,
                "event_type": event_type,
                "publish_date": publish_date,
                "url": full_url,
            }
        )

    index_cache[key] = {"entries": entries, "fetched_at": datetime.utcnow().isoformat()}
    _save_cache(cache)
    return entries


def _transform_event_payload(raw_payload: dict[str, Any]) -> dict[str, Any]:
    """
    Transform bloated MTGO payload into slim format.

    Reduces 41,000-line payloads to ~500 lines by extracting only essential data.

    Args:
        raw_payload: Raw payload from MTGO with full card_attributes, etc.

    Returns:
        Slim payload with only essential fields
    """
    # Extract event metadata
    event_id = raw_payload.get("event_id", "")
    description = raw_payload.get("description", "")
    starttime = raw_payload.get("starttime", "")
    format_raw = raw_payload.get("format", "")

    # Normalize format name (CSTANDARD -> Standard, etc.)
    format_name = format_raw.replace("C", "").title() if format_raw else "Unknown"

    # Build loginid maps for winloss and final_rank
    winloss_map: dict[str, dict[str, int]] = {}
    rank_map: dict[str, str] = {}

    # Extract winloss records if present
    for wl in raw_payload.get("winloss", []):
        loginid = wl.get("loginid")
        if loginid:
            winloss_map[loginid] = {
                "wins": int(wl.get("wins", 0)),
                "losses": int(wl.get("losses", 0))
            }

    # Extract final ranks if present
    for rank_entry in raw_payload.get("final_rank", []):
        loginid = rank_entry.get("loginid")
        if loginid:
            rank_map[loginid] = rank_entry.get("rank", "")

    # Process decklists - extract only essential fields
    slim_decks: list[dict[str, Any]] = []
    for deck in raw_payload.get("decklists", []):
        loginid = deck.get("loginid", "")
        player = deck.get("player", "Unknown")

        # Get winloss and rank for this player
        wl_data = winloss_map.get(loginid, {})
        wins = wl_data.get("wins", 0)
        losses = wl_data.get("losses", 0)
        final_rank = rank_map.get(loginid, "")

        # Extract archetype if present
        archetype = deck.get("archetype") or deck.get("deck_name", "")

        # Process mainboard - extract only name, qty
        mainboard: list[dict[str, Any]] = []
        for card in deck.get("main_deck", []):
            qty = int(card.get("qty", 1))
            # card_name can be in card_attributes or directly in card
            attrs = card.get("card_attributes") or {}
            name = attrs.get("card_name") or card.get("card_name", "Unknown")
            mainboard.append({"name": name, "qty": qty})

        # Process sideboard
        sideboard: list[dict[str, Any]] = []
        for card in deck.get("sideboard_deck", []):
            qty = int(card.get("qty", 1))
            attrs = card.get("card_attributes") or {}
            name = attrs.get("card_name") or card.get("card_name", "Unknown")
            sideboard.append({"name": name, "qty": qty})

        slim_decks.append({
            "loginid": loginid,
            "player": player,
            "archetype": archetype,
            "wins": wins,
            "losses": losses,
            "final_rank": final_rank,
            "main_deck": mainboard,
            "sideboard_deck": sideboard,
        })

    # Return slim payload
    return {
        "event_id": event_id,
        "description": description,
        "starttime": starttime,
        "format": format_name,
        "decklists": slim_decks,
    }


def _parse_deck_event(html: str) -> dict[str, Any]:
    """
    Parse MTGO deck event JSON from HTML.

    Args:
        html: HTML content

    Returns:
        Parsed JSON payload

    Raises:
        ValueError: If JSON payload not found (page may be invalid/404)
    """
    match = DETAIL_RE.search(html)
    if not match:
        # Check if this looks like a 404 or error page
        if len(html) < 1000 or "404" in html or "not found" in html.lower():
            raise ValueError("Page appears to be invalid or not found")
        raise ValueError("Could not locate deck JSON payload in page")

    try:
        payload = json.loads(match.group(1))
        return payload
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in deck payload: {exc}") from exc


def fetch_deck_event(url: str, cache: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Return the deck event JSON for a decklist page.

    Transforms bloated payloads into slim format before caching to dramatically
    reduce cache size (41,000 lines → ~500 lines per event).

    Args:
        url: URL to fetch
        cache: Optional cache dict to check/update. If None, loads cache but doesn't save.

    Returns:
        Slim event payload
    """
    # Load cache if not provided
    if cache is None:
        cache = _load_cache()

    deck_cache = cache.setdefault("events", {})
    if url in deck_cache:
        return deck_cache[url]

    html = _fetch_html(url)
    raw_payload = _parse_deck_event(html)
    # Transform to slim format before caching
    slim_payload = _transform_event_payload(raw_payload)
    deck_cache[url] = slim_payload
    # Don't save here - caller is responsible for saving to avoid concurrent writes
    return slim_payload


def iter_deck_events(entries: Iterable[dict[str, Any]]) -> Iterable[dict[str, Any]]:
    for entry in entries:
        try:
            payload = fetch_deck_event(entry["url"])
        except Exception as exc:
            logger.error(f"Failed to fetch deck event {entry['url']}: {exc}")
            continue
        yield entry, payload


def fetch_recent_events_parallel(
    year: int,
    month: int,
    max_events: int | None = None,
    mtg_format: str | None = None
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """
    Fetch recent MTGO events with parallel processing for better performance.

    Args:
        year: Year to fetch
        month: Month to fetch
        max_events: Maximum number of events to fetch
        mtg_format: Optional format filter (e.g., "Modern", "Standard") - filters BEFORE fetching

    Returns:
        List of (entry, payload) tuples for matching events
    """
    all_entries = fetch_decklist_index(year, month)

    # Filter by format BEFORE fetching event details (huge performance improvement)
    if mtg_format:
        format_normalized = mtg_format.lower()
        entries = [
            entry for entry in all_entries
            if (entry.get("format") or "").lower() == format_normalized
        ]
        logger.debug(f"Filtered {len(all_entries)} entries to {len(entries)} for format {mtg_format}")
    else:
        entries = all_entries

    if max_events:
        entries = entries[:max_events]

    results: list[tuple[dict[str, Any], dict[str, Any]]] = []
    if not entries:
        return results

    # Load cache once to check for already-fetched events
    cache = _load_cache()
    deck_cache = cache.setdefault("events", {})

    # Early exit optimization: if first and last entries are cached, check if entire span is cached
    if len(entries) >= 2:
        first_url = entries[0].get("url")
        last_url = entries[-1].get("url")

        if first_url in deck_cache and last_url in deck_cache:
            # Check if ALL entries are cached
            all_cached = all(entry.get("url") in deck_cache for entry in entries)

            if all_cached:
                logger.info(
                    f"All {len(entries)} events already cached (span {first_url[:50]}... to {last_url[:50]}...), "
                    f"skipping fetch"
                )
                # Return cached data without fetching
                for entry in entries:
                    url = entry.get("url")
                    if url and url in deck_cache:
                        results.append((entry, deck_cache[url]))
                return results

    # Track newly fetched events to save at the end (avoid concurrent writes)
    newly_fetched: dict[str, dict[str, Any]] = {}

    # Use ThreadPoolExecutor for parallel fetching
    with ThreadPoolExecutor(max_workers=MAX_PARALLEL_WORKERS) as executor:
        # Submit jobs, passing the shared cache (read-only in workers)
        future_to_entry = {
            executor.submit(fetch_deck_event, entry["url"], cache): entry
            for entry in entries
        }

        for future in as_completed(future_to_entry):
            entry = future_to_entry[future]
            try:
                payload = future.result()
                results.append((entry, payload))
                # Track if this was newly fetched (not from cache)
                if entry["url"] not in deck_cache:
                    newly_fetched[entry["url"]] = payload
            except Exception as exc:
                # Reduce log level for expected failures (404s, invalid pages)
                error_msg = str(exc).lower()
                if "invalid" in error_msg or "not found" in error_msg or "could not locate" in error_msg:
                    logger.debug(f"Skipping invalid/missing deck event {entry['url']}: {exc}")
                else:
                    logger.error(f"Failed to fetch deck event {entry['url']}: {exc}")
                continue

    # Save all newly fetched events at once to avoid concurrent write issues
    if newly_fetched:
        deck_cache.update(newly_fetched)
        _save_cache(cache)
        logger.debug(f"Saved {len(newly_fetched)} newly fetched events to cache")

    return results


def get_archetypes(mtg_format: str, days: int = 30) -> list[dict[str, Any]]:
    """
    Extract archetypes from recent MTGO events for a given format.

    Args:
        mtg_format: The MTG format (e.g., "Modern", "Standard")
        days: Number of days to look back (default: 30)

    Returns:
        List of archetype dictionaries with keys: name, href (archetype name)
    """
    now = datetime.utcnow()
    cutoff = now - timedelta(days=days)

    # Collect unique months to fetch
    months_to_fetch: set[tuple[int, int]] = set()
    current = cutoff
    while current <= now:
        months_to_fetch.add((current.year, current.month))
        # Move to next month
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)

    archetype_counter: Counter[str] = Counter()
    mtg_format_lower = mtg_format.lower()

    for year, month in sorted(months_to_fetch):
        try:
            # Pass format to filter BEFORE fetching event details
            events = fetch_recent_events_parallel(year, month, max_events=50, mtg_format=mtg_format)
        except Exception as exc:
            logger.warning(f"Failed to fetch events for {year}-{month:02d}: {exc}")
            continue

        for entry, payload in events:
            # Format already filtered in fetch_recent_events_parallel
            # No need to filter again here

            # Check publish date
            publish_str = entry.get("publish_date")
            if publish_str:
                try:
                    publish_date = datetime.fromisoformat(publish_str.replace("Z", "+00:00"))
                    if publish_date.replace(tzinfo=None) < cutoff:
                        continue
                except (ValueError, AttributeError):
                    pass

            # Extract archetypes from decklists
            for deck in payload.get("decklists", []):
                archetype = deck.get("archetype") or deck.get("deck_name")
                if archetype and archetype.strip():
                    archetype_counter[archetype.strip()] += 1

    # Convert to format expected by repository
    archetypes = [
        {"name": archetype, "href": archetype.lower().replace(" ", "-").replace("'", "")}
        for archetype, _ in archetype_counter.most_common()
    ]

    logger.info(f"Found {len(archetypes)} archetypes for {mtg_format} from MTGO")
    return archetypes


def get_archetype_decks(
    archetype: str,
    mtg_format: str | None = None,
    days: int = 30,
    max_decks: int = 50
) -> list[dict[str, Any]]:
    """
    Get recent decks for a specific archetype from MTGO events.

    Args:
        archetype: The archetype name or href
        mtg_format: MTG format to filter by (e.g., "Modern", "Standard"). If None, fetches all formats.
        days: Number of days to look back (default: 30)
        max_decks: Maximum number of decks to return (default: 50)

    Returns:
        List of deck dictionaries with keys: date, number, player, event, result, name
    """
    now = datetime.utcnow()
    cutoff = now - timedelta(days=days)

    # Collect unique months to fetch
    months_to_fetch: set[tuple[int, int]] = set()
    current = cutoff
    while current <= now:
        months_to_fetch.add((current.year, current.month))
        # Move to next month
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)

    decks: list[dict[str, Any]] = []
    # Normalize archetype for comparison
    archetype_normalized = archetype.lower().replace("-", " ").replace("_", " ")
    format_normalized = mtg_format.lower() if mtg_format else None

    for year, month in sorted(months_to_fetch, reverse=True):
        if len(decks) >= max_decks:
            break

        try:
            # Pass format to filter BEFORE fetching event details
            events = fetch_recent_events_parallel(year, month, max_events=50, mtg_format=mtg_format)
        except Exception as exc:
            logger.warning(f"Failed to fetch events for {year}-{month:02d}: {exc}")
            continue

        for entry, payload in events:
            if len(decks) >= max_decks:
                break

            # Format already filtered in fetch_recent_events_parallel
            # No need to filter again here

            # Check publish date
            publish_str = entry.get("publish_date")
            publish_date = None
            if publish_str:
                try:
                    publish_date = datetime.fromisoformat(publish_str.replace("Z", "+00:00"))
                    if publish_date.replace(tzinfo=None) < cutoff:
                        continue
                except (ValueError, AttributeError):
                    pass

            # Extract matching decks
            for deck in payload.get("decklists", []):
                if len(decks) >= max_decks:
                    break

                deck_archetype = deck.get("archetype") or deck.get("deck_name") or ""
                deck_archetype_normalized = deck_archetype.lower().replace("-", " ").replace("_", " ")

                if archetype_normalized in deck_archetype_normalized or deck_archetype_normalized in archetype_normalized:
                    # Format date
                    date_str = publish_date.strftime("%Y-%m-%d") if publish_date else entry.get("publish_date", "")

                    # Generate a simple numeric-like identifier for compatibility
                    # Use a hash of the deck to create a unique but simpler ID
                    player = deck.get("player") or deck.get("pilot") or "Unknown"
                    event_url = entry.get("url", "")
                    deck_hash = hash(f"{event_url}#{player}#{deck_archetype}")
                    simple_id = f"mtgo_{abs(deck_hash)}"

                    # Build result string from wins/losses/rank
                    wins = deck.get("wins", 0)
                    losses = deck.get("losses", 0)
                    final_rank = deck.get("final_rank", "")

                    # Format result string
                    if final_rank:
                        result = f"#{final_rank} ({wins}-{losses})"
                    elif wins or losses:
                        result = f"{wins}-{losses}"
                    else:
                        result = ""

                    decks.append({
                        "date": date_str,
                        "number": simple_id,  # Simple identifier for UI
                        "player": player,
                        "event": entry.get("title") or "MTGO Event",
                        "result": result,
                        "name": deck_archetype,
                        "_mtgo_url": event_url,  # Store for deck content fetching
                        "_mtgo_payload": deck,  # Store payload for deck content extraction
                        "_is_mtgo": True,  # Flag to indicate this is from MTGO
                    })

    logger.info(f"Found {len(decks)} decks for archetype '{archetype}' in format '{mtg_format or 'all'}' from MTGO")
    return decks


def fetch_deck_text(deck_number: str) -> str:
    """
    Fetch deck text content from MTGO.

    Note: For MTGO decks, the deck_number might be an event URL or deck ID.
    This function attempts to reconstruct the deck list from cached event data.

    Args:
        deck_number: MTGO deck identifier (could be URL or ID)

    Returns:
        Deck list as text string

    Raises:
        ValueError: If deck cannot be found or parsed
    """
    cache = _load_cache()
    events = cache.get("events", {})

    # Try to find the deck in cached events
    for url, event_payload in events.items():
        for deck in event_payload.get("decklists", []):
            deck_id = deck.get("mtgoId") or deck.get("identifier")
            if str(deck_id) == str(deck_number) or deck_number in url:
                # Convert deck to text format
                return _deck_to_text(deck)

    # If not found in cache, raise error
    raise ValueError(f"Deck {deck_number} not found in MTGO cache. Try fetching recent events first.")


def _deck_to_text(deck: dict[str, Any]) -> str:
    """
    Convert MTGO deck payload to text format.

    Works with both slim and legacy payload formats for backward compatibility.
    """
    lines: list[str] = []

    # Add mainboard
    mainboard = deck.get("main_deck", [])
    for card in mainboard:
        # Slim format: {"name": "Card", "qty": 2}
        # Legacy format: {"qty": 2, "card_attributes": {"card_name": "Card"}}
        if "name" in card:
            # Slim format
            qty = card.get("qty", 1)
            name = card.get("name", "Unknown")
        else:
            # Legacy format
            qty = card.get("qty") or card.get("quantity", 1)
            attrs = card.get("card_attributes") or {}
            name = attrs.get("card_name") or card.get("card_name") or "Unknown"

        lines.append(f"{qty} {name}")

    # Add sideboard
    sideboard = deck.get("sideboard_deck", [])
    if sideboard:
        lines.append("")  # Blank line separator
        for card in sideboard:
            # Slim format: {"name": "Card", "qty": 2}
            # Legacy format: {"qty": 2, "card_attributes": {"card_name": "Card"}}
            if "name" in card:
                # Slim format
                qty = card.get("qty", 1)
                name = card.get("name", "Unknown")
            else:
                # Legacy format
                qty = card.get("qty") or card.get("quantity", 1)
                attrs = card.get("card_attributes") or {}
                name = attrs.get("card_name") or card.get("card_name") or "Unknown"

            lines.append(f"{qty} {name}")

    return "\n".join(lines)


__all__ = [
    "fetch_decklist_index",
    "fetch_deck_event",
    "iter_deck_events",
    "fetch_recent_event_history",
    "fetch_recent_events_parallel",
    "get_archetypes",
    "get_archetype_decks",
    "fetch_deck_text",
]


def fetch_recent_event_history(limit: int = 10) -> list[dict[str, Any]]:
    """Return recent MTGO event results in the history format expected by the UI."""
    now = datetime.utcnow()
    entries = fetch_decklist_index(now.year, now.month)
    history: list[dict[str, Any]] = []
    for entry, payload in iter_deck_events(entries):
        matches: list[dict[str, Any]] = []
        for deck in payload.get("decklists", []):
            player = deck.get("player") or deck.get("pilot")
            standing = deck.get("standing") or deck.get("finish") or deck.get("result")
            record = deck.get("record") or deck.get("points")
            match_id = deck.get("mtgoId") or deck.get("identifier") or deck.get("deckId") or player
            matches.append(
                {
                    "id": str(match_id),
                    "players": [{"name": player, "result": standing}],
                    "state": "Completed",
                    "isComplete": True,
                    "result": standing or record,
                    "lastUpdated": deck.get("eventDate")
                    or deck.get("updatedAt")
                    or entry.get("publish_date"),
                }
            )
        history.append(
            {
                "eventId": entry.get("url"),
                "description": entry.get("title"),
                "format": entry.get("format"),
                "eventType": entry.get("event_type"),
                "isCompleted": True,
                "state": "Completed",
                "lastUpdated": entry.get("publish_date"),
                "matches": matches,
            }
        )
        if len(history) >= limit:
            break
    return history
