"""Scrape decklists from https://www.mtgo.com/decklists."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from datetime import datetime
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from curl_cffi import requests
from loguru import logger

from utils.constants import MTGO_DECK_CACHE_FILE

BASE_URL = "https://www.mtgo.com"
DECKLIST_INDEX_URL = "https://www.mtgo.com/decklists/{year}/{month:02d}"
DEFAULT_TIMEOUT = 30


def _load_cache() -> dict[str, Any]:
    if not MTGO_DECK_CACHE_FILE.exists():
        return {}
    try:
        with MTGO_DECK_CACHE_FILE.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except json.JSONDecodeError as exc:
        logger.warning(f"Invalid MTGO deck cache JSON ({MTGO_DECK_CACHE_FILE}): {exc}")
        return {}


def _save_cache(cache: dict[str, Any]) -> None:
    MTGO_DECK_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with MTGO_DECK_CACHE_FILE.open("w", encoding="utf-8") as fh:
        json.dump(cache, fh, indent=2)


def _fetch_html(url: str) -> str:
    logger.debug(f"Fetching {url}")
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


DETAIL_RE = re.compile(r"window\.MTGO\.decklists\.data\s*=\s*(\{.*?\});", re.DOTALL)


def _parse_deck_event(html: str) -> dict[str, Any]:
    match = DETAIL_RE.search(html)
    if not match:
        raise ValueError("Could not locate deck JSON payload")
    payload = json.loads(match.group(1))
    return payload


def fetch_deck_event(url: str) -> dict[str, Any]:
    """Return the full deck event JSON for a decklist page."""
    cache = _load_cache()
    deck_cache = cache.setdefault("events", {})
    if url in deck_cache:
        return deck_cache[url]

    html = _fetch_html(url)
    payload = _parse_deck_event(html)
    deck_cache[url] = payload
    _save_cache(cache)
    return payload


def iter_deck_events(entries: Iterable[dict[str, Any]]) -> Iterable[dict[str, Any]]:
    for entry in entries:
        try:
            payload = fetch_deck_event(entry["url"])
        except Exception as exc:
            logger.error(f"Failed to fetch deck event {entry['url']}: {exc}")
            continue
        yield entry, payload


__all__ = [
    "fetch_decklist_index",
    "fetch_deck_event",
    "iter_deck_events",
    "fetch_recent_event_history",
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
