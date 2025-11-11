#!/usr/bin/env python3
"""Benchmark the card metadata caches to understand their load times."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

from loguru import logger

from utils.card_images import BULK_DATA_CACHE, PRINTING_INDEX_CACHE


def _format_duration(seconds: float) -> str:
    if seconds < 1:
        return f"{seconds * 1000:.1f} ms"
    return f"{seconds:.2f} s"


def _benchmark(path: Path, iterations: int, label: str) -> None:
    if not path.exists():
        logger.warning(f"{label} cache not found at {path}")
        return

    size_mb = path.stat().st_size / (1024 * 1024)
    logger.info(f"{label} cache size: {size_mb:.1f} MB")

    durations: list[float] = []
    for iteration in range(iterations):
        start = time.perf_counter()
        try:
            with path.open("rb") as fh:
                json.load(fh)
        except json.JSONDecodeError as exc:
            logger.error(f"Failed to parse {label} cache: {exc}")
            return
        elapsed = time.perf_counter() - start
        durations.append(elapsed)
        logger.info(f"{label} iteration {iteration + 1}: {_format_duration(elapsed)}")

    summary = {
        "min": durations and _format_duration(min(durations)),
        "max": durations and _format_duration(max(durations)),
        "avg": durations and _format_duration(statistics.mean(durations)),
    }
    logger.info(
        "{label} summary: min={min}, max={max}, avg={avg}",
        label=label,
        **summary,  # type: ignore[arg-type]
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Measure how long it takes to load the card metadata caches into memory."
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=1,
        help="How many times to load each cache (default: 1).",
    )
    parser.add_argument(
        "--skip-bulk",
        action="store_true",
        help="Skip measuring the full bulk_data.json cache.",
    )
    parser.add_argument(
        "--skip-printings",
        action="store_true",
        help="Skip measuring the compact printings index cache.",
    )

    args = parser.parse_args()

    if args.iterations < 1:
        parser.error("--iterations must be at least 1")

    if args.skip_bulk and args.skip_printings:
        parser.error("Cannot skip both caches; nothing to benchmark.")

    if not args.skip_printings:
        _benchmark(PRINTING_INDEX_CACHE, args.iterations, "Printings index")

    if not args.skip_bulk:
        _benchmark(BULK_DATA_CACHE, args.iterations, "Bulk data")

    return 0


if __name__ == "__main__":
    sys.exit(main())
