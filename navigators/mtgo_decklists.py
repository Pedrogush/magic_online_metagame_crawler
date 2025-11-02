"""Scrape decklists from https://www.mtgo.com/decklists."""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Dict, Iterable, List, Tuple
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from curl_cffi import requests
from loguru import logger

from utils.paths import MTGO_DECK_CACHE_FILE

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


def _classify_event(title: str) -> Tuple[str | None, str | None]:
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


def fetch_decklist_index(year: int, month: int) -> List[Dict[str, Any]]:
    """Return decklist entries for the given year/month."""
    cache = _load_cache()
    index_cache = cache.setdefault("index", {})
    key = f"{year}-{month:02d}"
    if key in index_cache:
        return index_cache[key]["entries"]

    url = DECKLIST_INDEX_URL.format(year=year, month=month)
    html = _fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")
    entries: List[Dict[str, Any]] = []
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


def _parse_deck_event(html: str) -> Dict[str, Any]:
    match = DETAIL_RE.search(html)
    if not match:
        raise ValueError("Could not locate deck JSON payload")
    payload = json.loads(match.group(1))
    return payload


def fetch_deck_event(url: str) -> Dict[str, Any]:
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


def iter_deck_events(entries: Iterable[Dict[str, Any]]) -> Iterable[Dict[str, Any]]:
    for entry in entries:
        try:
            payload = fetch_deck_event(entry["url"])
        except Exception as exc:
            logger.error(f"Failed to fetch deck event {entry['url']}: {exc}")
            continue
        yield entry, payload


__all__ = ["fetch_decklist_index", "fetch_deck_event", "iter_deck_events"]
