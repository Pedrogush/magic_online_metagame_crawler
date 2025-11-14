#!/usr/bin/env python3
"""Inspect cached card face images for debugging double-faced downloads."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def find_db(candidate: str | None) -> Path | None:
    """Locate the images.db file."""
    if candidate:
        path = Path(candidate).expanduser()
        return path if path.exists() else None
    default = Path("cache/card_images/images.db")
    if default.exists():
        return default
    return None


def query_faces(db_path: Path, name: str) -> list[tuple]:
    """Return (uuid, name, face_index, image_size, file_path) rows matching name."""
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.execute(
            """
            SELECT uuid, name, face_index, image_size, file_path
            FROM card_images
            WHERE LOWER(name) LIKE LOWER(?)
            ORDER BY uuid, face_index
            """,
            (name,),
        )
        return cursor.fetchall()
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inspect cached card faces (use patterns like '%%Jace%%')."
    )
    parser.add_argument("name", help="Name or SQL LIKE pattern (use % as wildcard)")
    parser.add_argument(
        "--db",
        dest="db",
        help="Optional path to images.db (defaults to cache/card_images/images.db)",
    )
    args = parser.parse_args()

    db_path = find_db(args.db)
    if not db_path:
        raise SystemExit("Image cache database not found. Run the downloader first.")

    rows = query_faces(db_path, args.name)
    if not rows:
        print(f"No cached faces matched pattern {args.name!r}")
        return

    print(f"Found {len(rows)} cached faces in {db_path}:")
    for uuid, name, face_index, size, file_path in rows:
        label = "front/back alias" if face_index == -1 else f"face {face_index}"
        print(f"- {uuid} | {name} | {label} | {size} | {file_path}")


if __name__ == "__main__":
    main()
