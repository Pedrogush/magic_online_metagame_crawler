#!/usr/bin/env python3
"""Test script to verify MTGO deck metadata caching."""

import json
from datetime import datetime, timedelta

from loguru import logger

try:
    from datetime import UTC
except ImportError:  # pragma: no cover - Python 3.10 fallback
    UTC = UTC

from services.mtgo_background_service import (
    fetch_mtgo_events_for_period,
    load_mtgo_deck_metadata,
    process_mtgo_event,
)
from utils.constants import CACHE_DIR

MTGO_METADATA_CACHE = CACHE_DIR / "mtgo_deck_metadata.json"


def main():
    logger.info("Testing MTGO deck metadata caching...")

    end_date = datetime.now(UTC)
    start_date = end_date - timedelta(days=3)

    logger.info(f"Fetching Modern events from {start_date.date()} to {end_date.date()}")
    events = fetch_mtgo_events_for_period(start_date, end_date, mtg_format="modern")

    if not events:
        logger.warning("No events found in date range")
        return

    logger.info(f"Found {len(events)} events. Processing first event...")

    first_event = events[0]
    logger.info(f"Processing event: {first_event['title']}")

    decks_cached = process_mtgo_event(first_event["url"], mtg_format="modern", delay=0.5)
    logger.info(f"Cached {decks_cached} decks from event")

    if MTGO_METADATA_CACHE.exists():
        logger.info(f"\nMetadata cache file created at: {MTGO_METADATA_CACHE}")

        with MTGO_METADATA_CACHE.open("r", encoding="utf-8") as fh:
            data = json.load(fh)

        logger.info(f"Cache contains {len(data)} archetype entries")

        for key, decks in list(data.items())[:3]:
            logger.info(f"  {key}: {len(decks)} decks")
            if decks:
                sample = decks[0]
                logger.info(
                    f"    Sample: {sample.get('player')} - {sample.get('archetype')} "
                    f"({sample.get('result')}) on {sample.get('date')}"
                )

        logger.info("\nTesting retrieval by archetype...")
        for key in list(data.keys())[:1]:
            parts = key.split(":", 1)
            if len(parts) == 2:
                fmt, archetype = parts
                decks = load_mtgo_deck_metadata(archetype, fmt)
                logger.info(f"Retrieved {len(decks)} decks for {archetype} in {fmt}")

        logger.success("\nTest completed successfully!")
    else:
        logger.error("Metadata cache file was not created")


if __name__ == "__main__":
    main()
