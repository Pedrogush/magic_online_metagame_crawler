#!/usr/bin/env python3
"""Clear all caches except card images."""

import shutil
from pathlib import Path

CACHE_DIR = Path("cache")
PRESERVE = {"card_images"}


def clear_caches():
    """Remove all cache files and directories except card images."""
    if not CACHE_DIR.exists():
        print("No cache directory found")
        return

    removed_count = 0
    preserved_count = 0

    for item in CACHE_DIR.iterdir():
        if item.name in PRESERVE:
            preserved_count += 1
            print(f"Preserving: {item}")
            continue

        if item.is_file():
            item.unlink()
            print(f"Removed file: {item}")
            removed_count += 1
        elif item.is_dir():
            shutil.rmtree(item)
            print(f"Removed directory: {item}")
            removed_count += 1

    print(f"\nCleared {removed_count} items, preserved {preserved_count} items")


if __name__ == "__main__":
    clear_caches()
