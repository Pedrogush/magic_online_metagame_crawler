"""High-throughput card image downloader and cache manager.

This module provides functionality to:
1. Download Scryfall bulk data to get all card metadata
2. Fetch card images from Scryfall CDN (no rate limits on image CDN)
3. Maintain a local SQLite database of cached images
4. Support concurrent downloads for high throughput

Architecture:
- Uses Scryfall bulk data JSON for card metadata
- Downloads images from cards.scryfall.io CDN (no rate limits)
- Stores images locally with UUID-based filenames
- SQLite database tracks downloaded images and metadata
- Supports multiple image sizes (small, normal, large, png)
"""

from __future__ import annotations

import json
import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath
from typing import Any

import requests
from loguru import logger

from utils.paths import CACHE_DIR

# Image cache configuration
IMAGE_CACHE_DIR = CACHE_DIR / "card_images"
IMAGE_DB_PATH = IMAGE_CACHE_DIR / "images.db"
BULK_DATA_CACHE = IMAGE_CACHE_DIR / "bulk_data.json"
PRINTING_INDEX_VERSION = 1
PRINTING_INDEX_CACHE = IMAGE_CACHE_DIR / f"printings_v{PRINTING_INDEX_VERSION}.json"

# Image size options (in order of preference for storage)
IMAGE_SIZES = {
    "small": "small",  # 146x204 - thumbnails
    "normal": "normal",  # 488x680 - default
    "large": "large",  # 672x936 - high quality
    "png": "png",  # 745x1040 - highest quality, transparent
}

# Download configuration
BULK_DATA_URL = "https://api.scryfall.com/bulk-data/default-cards"
MAX_WORKERS = 10  # Concurrent download threads
CHUNK_SIZE = 8192  # Download chunk size
REQUEST_TIMEOUT = 30  # Seconds


class CardImageCache:
    """Manages local card image cache with SQLite database."""

    def __init__(self, cache_dir: Path = IMAGE_CACHE_DIR, db_path: Path = IMAGE_DB_PATH):
        self.cache_dir = Path(cache_dir)
        self.db_path = Path(db_path)
        self._ensure_directories()
        self.cache_dir = self.cache_dir.resolve()
        self.db_path = self.db_path.resolve()
        self._path_roots = self._build_path_roots()
        self._init_database()

    def _ensure_directories(self) -> None:
        """Create cache directories if they don't exist."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        for size in IMAGE_SIZES.values():
            (self.cache_dir / size).mkdir(exist_ok=True)

    def _build_path_roots(self) -> list[Path]:
        """Precompute base directories used to resolve relative cache entries."""
        roots: list[Path] = []
        candidates = [
            Path.cwd(),
            self.cache_dir,
            self.cache_dir.parent,
        ]
        # Include grandparent (project root) if available
        try:
            candidates.append(self.cache_dir.parents[1])
        except IndexError:
            pass
        seen = set()
        for entry in candidates:
            resolved = entry.resolve()
            if resolved not in seen:
                seen.add(resolved)
                roots.append(resolved)
        return roots

    def _init_database(self) -> None:
        """Initialize SQLite database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS card_images (
                    uuid TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    set_code TEXT,
                    collector_number TEXT,
                    image_size TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    downloaded_at TEXT NOT NULL,
                    scryfall_uri TEXT,
                    artist TEXT,
                    UNIQUE(uuid, image_size)
                )
            """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_card_name ON card_images(name)
            """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_set_code ON card_images(set_code)
            """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS bulk_data_meta (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    downloaded_at TEXT NOT NULL,
                    total_cards INTEGER NOT NULL,
                    bulk_data_uri TEXT NOT NULL
                )
            """
            )
            conn.commit()

    def _resolve_path(self, stored_path: str) -> Path:
        """Convert stored path strings into usable filesystem Paths.

        Handles Windows-style separators and WSL drive prefixes when running on POSIX.
        """
        raw = stored_path.strip()
        path = Path(raw)
        resolved = self._normalize_path(path)
        if resolved.exists():
            return resolved

        # Normalize backslashes to forward slashes (works on all OSes)
        if "\\" in raw:
            normalized = raw.replace("\\", "/")
            path = Path(normalized)
            normalized_resolved = self._normalize_path(path)
            if normalized_resolved.exists():
                return normalized_resolved

            # Interpret as Windows path and convert to current platform
            try:
                win_path = Path(PureWindowsPath(raw))
                if win_path.exists():
                    return win_path
            except Exception:
                pass

            # Translate Windows drive letters for WSL paths (e.g., C:\ -> /mnt/c/)
            if os.name != "nt" and len(raw) >= 3 and raw[1] == ":" and raw[2] in ("\\", "/"):
                drive = raw[0].lower()
                remainder = raw[3:].replace("\\", "/")
                wsl_path = Path("/mnt") / drive / remainder
                if wsl_path.exists():
                    return wsl_path

        return resolved

    def _normalize_path(self, path: Path) -> Path:
        """Resolve absolute paths or attempt to rebuild relatives under known roots."""
        try:
            if path.is_absolute():
                return path
        except OSError:
            pass

        rel = self._resolve_relative_path(path)
        if rel is not None:
            return rel

        return path

    def _resolve_relative_path(self, relative: Path) -> Path | None:
        """Attempt to resolve a relative cache entry against known roots."""
        for root in self._path_roots:
            candidate = (root / relative).resolve()
            if candidate.exists():
                return candidate
        return None

    def get_image_path(self, card_name: str, size: str = "normal") -> Path | None:
        """Get cached image path for a card name.

        Args:
            card_name: Card name (case-insensitive)
            size: Image size (small, normal, large, png)

        Returns:
            Path to cached image file, or None if not cached
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT file_path FROM card_images WHERE LOWER(name) = LOWER(?) AND image_size = ? LIMIT 1",
                (card_name, size),
            )
            row = cursor.fetchone()
            if row:
                path = self._resolve_path(row[0])
                if path.exists():
                    return path
        return None

    def get_image_by_uuid(self, uuid: str, size: str = "normal") -> Path | None:
        """Get cached image path by Scryfall UUID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT file_path FROM card_images WHERE uuid = ? AND image_size = ?", (uuid, size)
            )
            row = cursor.fetchone()
            if row:
                path = self._resolve_path(row[0])
                if path.exists():
                    return path
        return None

    def add_image(
        self,
        uuid: str,
        name: str,
        set_code: str,
        collector_number: str,
        image_size: str,
        file_path: Path,
        scryfall_uri: str = None,
        artist: str = None,
    ) -> None:
        """Add image record to database."""
        file_path_str = str(Path(file_path).resolve())

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO card_images
                (uuid, name, set_code, collector_number, image_size, file_path,
                 downloaded_at, scryfall_uri, artist)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    uuid,
                    name,
                    set_code,
                    collector_number,
                    image_size,
                    file_path_str,
                    datetime.now(timezone.utc).isoformat(),
                    scryfall_uri,
                    artist,
                ),
            )
            conn.commit()

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        with sqlite3.connect(self.db_path) as conn:
            total = conn.execute("SELECT COUNT(DISTINCT uuid) FROM card_images").fetchone()[0]
            by_size = {}
            for size in IMAGE_SIZES.values():
                count = conn.execute(
                    "SELECT COUNT(*) FROM card_images WHERE image_size = ?", (size,)
                ).fetchone()[0]
                by_size[size] = count

            bulk_meta = conn.execute(
                "SELECT downloaded_at, total_cards FROM bulk_data_meta WHERE id = 1"
            ).fetchone()

        return {
            "unique_cards": total,
            "by_size": by_size,
            "bulk_data_date": bulk_meta[0] if bulk_meta else None,
            "bulk_total_cards": bulk_meta[1] if bulk_meta else None,
        }

    def is_cached(self, uuid: str, size: str = "normal") -> bool:
        """Check if image is already cached."""
        return self.get_image_by_uuid(uuid, size) is not None


class BulkImageDownloader:
    """High-throughput bulk image downloader using Scryfall data."""

    def __init__(self, cache: CardImageCache, max_workers: int = MAX_WORKERS):
        self.cache = cache
        self.max_workers = max_workers
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "MTGOMetagameCrawler/1.0"})

    def download_bulk_metadata(self, force: bool = False) -> tuple[bool, str]:
        """Download Scryfall bulk data JSON.

        Args:
            force: Force re-download even if cached

        Returns:
            (success, message)
        """
        # Check if we have recent bulk data (less than 24 hours old)
        if not force and BULK_DATA_CACHE.exists():
            age = datetime.now().timestamp() - BULK_DATA_CACHE.stat().st_mtime
            if age < 86400:  # 24 hours
                logger.info(f"Using cached bulk data ({age/3600:.1f}h old)")
                return True, "Using cached bulk data"

        try:
            logger.info("Fetching bulk data metadata from Scryfall...")
            resp = self.session.get(BULK_DATA_URL, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            bulk_meta = resp.json()

            download_uri = bulk_meta.get("download_uri")
            if not download_uri:
                return False, "No download URI in bulk data response"

            logger.info(f"Downloading bulk data from {download_uri}")
            logger.info(f"Size: {bulk_meta.get('size', 0) / (1024*1024):.1f} MB")

            # Download with progress
            resp = self.session.get(download_uri, stream=True, timeout=120)
            resp.raise_for_status()

            with BULK_DATA_CACHE.open("wb") as f:
                for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
                    f.write(chunk)

            # Update database metadata (defer card count to avoid parsing 500MB file)
            with sqlite3.connect(self.cache.db_path) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO bulk_data_meta (id, downloaded_at, total_cards, bulk_data_uri)
                    VALUES (1, ?, ?, ?)
                """,
                    (datetime.now(timezone.utc).isoformat(), 0, download_uri),
                )
                conn.commit()

            logger.info("Bulk data downloaded successfully")
            return True, "Bulk data downloaded"

        except Exception as exc:
            logger.exception("Failed to download bulk data")
            return False, f"Error: {exc}"

    def _download_single_image(
        self, card: dict[str, Any], size: str = "normal"
    ) -> tuple[bool, str]:
        """Download a single card image.

        Args:
            card: Card object from bulk data
            size: Image size to download

        Returns:
            (success, message)
        """
        uuid = card.get("id")
        name = card.get("name", "Unknown")

        if not uuid:
            return False, f"No UUID for {name}"

        # Check if already cached
        if self.cache.is_cached(uuid, size):
            return True, f"Already cached: {name}"

        # Get image URI
        image_uris = card.get("image_uris")
        if not image_uris:
            # Check card faces for double-faced cards
            card_faces = card.get("card_faces", [])
            if card_faces and card_faces[0].get("image_uris"):
                image_uris = card_faces[0]["image_uris"]
            else:
                return False, f"No image URIs for {name}"

        image_url = image_uris.get(size)
        if not image_url:
            # Fallback to normal size
            image_url = image_uris.get("normal")
            if not image_url:
                return False, f"No {size} image for {name}"

        try:
            # Download image
            resp = self.session.get(image_url, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()

            # Determine file extension
            ext = "jpg"
            if size == "png":
                ext = "png"

            # Save to cache
            filename = f"{uuid}.{ext}"
            file_path = self.cache.cache_dir / size / filename

            with file_path.open("wb") as f:
                f.write(resp.content)

            # Add to database
            self.cache.add_image(
                uuid=uuid,
                name=name,
                set_code=card.get("set", ""),
                collector_number=card.get("collector_number", ""),
                image_size=size,
                file_path=file_path,
                scryfall_uri=card.get("scryfall_uri"),
                artist=card.get("artist"),
            )

            return True, f"Downloaded: {name}"

        except Exception as exc:
            logger.debug(f"Failed to download {name}: {exc}")
            return False, f"Error: {name} - {exc}"

    def download_all_images(
        self,
        size: str = "normal",
        max_cards: int | None = None,
        progress_callback: callable | None = None,
    ) -> dict[str, Any]:
        """Download all card images from bulk data.

        Args:
            size: Image size to download (small, normal, large, png)
            max_cards: Limit number of cards (for testing)
            progress_callback: Callback function(completed, total, message)

        Returns:
            Statistics dict
        """
        if not BULK_DATA_CACHE.exists():
            return {
                "success": False,
                "error": "Bulk data not downloaded. Call download_bulk_metadata() first.",
            }

        try:
            cards_data = json.loads(BULK_DATA_CACHE.read_text(encoding="utf-8"))
            if max_cards:
                cards_data = cards_data[:max_cards]

            total = len(cards_data)
            completed = 0
            successful = 0
            failed = 0
            skipped = 0

            logger.info(f"Starting bulk download of {total} cards ({size} size)")

            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {
                    executor.submit(self._download_single_image, card, size): card
                    for card in cards_data
                }

                for future in as_completed(futures):
                    completed += 1
                    try:
                        success, message = future.result()
                        if success:
                            if "Already cached" in message:
                                skipped += 1
                            else:
                                successful += 1
                        else:
                            failed += 1
                            logger.debug(message)
                    except Exception as exc:
                        failed += 1
                        logger.debug(f"Exception in download: {exc}")

                    # Progress callback
                    if progress_callback and completed % 100 == 0:
                        progress_callback(
                            completed,
                            total,
                            f"{successful} downloaded, {skipped} cached, {failed} failed",
                        )

            logger.info(
                f"Bulk download complete: {successful} downloaded, {skipped} cached, {failed} failed"
            )

            return {
                "success": True,
                "total": total,
                "downloaded": successful,
                "skipped": skipped,
                "failed": failed,
            }

        except Exception as exc:
            logger.exception("Bulk download failed")
            return {"success": False, "error": str(exc)}


def _load_printing_index_payload() -> dict[str, Any] | None:
    """Load the cached card printings index if available."""
    if not PRINTING_INDEX_CACHE.exists():
        return None
    try:
        with PRINTING_INDEX_CACHE.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)
    except Exception as exc:
        logger.warning(f"Failed to read printings index cache: {exc}")
        return None
    if payload.get("version") != PRINTING_INDEX_VERSION:
        logger.info("Discarding printings index cache due to version mismatch")
        return None
    return payload


def ensure_printing_index_cache(force: bool = False) -> dict[str, Any]:
    """Ensure a compact card printings index exists for fast wx lookups."""
    IMAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    existing = None if force else _load_printing_index_payload()
    bulk_mtime = BULK_DATA_CACHE.stat().st_mtime if BULK_DATA_CACHE.exists() else None

    if existing and (bulk_mtime is None or existing.get("bulk_mtime", 0) >= bulk_mtime):
        return existing

    if bulk_mtime is None:
        raise FileNotFoundError("Bulk data cache not found; cannot build printings index")

    logger.info("Building card printings index from bulk data…")
    with BULK_DATA_CACHE.open("r", encoding="utf-8") as fh:
        cards = json.load(fh)

    by_name: dict[str, list[dict[str, Any]]] = {}
    total_printings = 0
    for card in cards:
        name = (card.get("name") or "").strip()
        uuid = card.get("id")
        if not name or not uuid:
            continue
        key = name.lower()
        entry = {
            "id": uuid,
            "set": (card.get("set") or "").upper(),
            "set_name": card.get("set_name") or "",
            "collector_number": card.get("collector_number") or "",
            "released_at": card.get("released_at") or "",
        }
        by_name.setdefault(key, []).append(entry)
        total_printings += 1

    for entries in by_name.values():
        entries.sort(key=lambda c: c.get("released_at") or "", reverse=True)

    payload = {
        "version": PRINTING_INDEX_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "bulk_mtime": bulk_mtime,
        "unique_names": len(by_name),
        "total_printings": total_printings,
        "data": by_name,
    }

    try:
        with PRINTING_INDEX_CACHE.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, separators=(",", ":"))
        logger.info(
            "Cached card printings index (%s names, %s printings)",
            payload["unique_names"],
            payload["total_printings"],
        )
    except Exception as exc:
        logger.warning(f"Failed to write printings index cache: {exc}")

    return payload


# Singleton instance
_cache_instance: CardImageCache | None = None


def get_cache() -> CardImageCache:
    """Get singleton CardImageCache instance."""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = CardImageCache()
    return _cache_instance


def get_card_image(card_name: str, size: str = "normal") -> Path | None:
    """Get card image from cache.

    Args:
        card_name: Card name (case-insensitive)
        size: Image size (small, normal, large, png)

    Returns:
        Path to image file, or None if not cached
    """
    cache = get_cache()
    return cache.get_image_path(card_name, size)


def download_bulk_images(
    size: str = "normal", max_cards: int | None = None, progress_callback: callable | None = None
) -> dict[str, Any]:
    """High-level function to download all card images.

    Args:
        size: Image size (small, normal, large, png)
        max_cards: Limit download (for testing)
        progress_callback: Progress callback(completed, total, message)

    Returns:
        Statistics dict
    """
    cache = get_cache()
    downloader = BulkImageDownloader(cache)

    # Download metadata first
    success, msg = downloader.download_bulk_metadata()
    if not success:
        return {"success": False, "error": msg}

    # Download images
    return downloader.download_all_images(size, max_cards, progress_callback)


def get_cache_stats() -> dict[str, Any]:
    """Get cache statistics."""
    cache = get_cache()
    return cache.get_cache_stats()


__all__ = [
    "CardImageCache",
    "BulkImageDownloader",
    "PRINTING_INDEX_CACHE",
    "get_cache",
    "get_card_image",
    "download_bulk_images",
    "get_cache_stats",
    "ensure_printing_index_cache",
]
