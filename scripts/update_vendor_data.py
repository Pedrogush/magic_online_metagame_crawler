#!/usr/bin/env python3
"""Refresh vendored MTGO archetype resources."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENDOR_DIR = ROOT / "vendor"
FORMAT_TARGET = VENDOR_DIR / "mtgo_format_data"
FORMAT_CARD_FILE = "card_colors.json"
PARSER_TARGET = VENDOR_DIR / "mtgo_archetype_parser" / "LICENSE"
METADATA_FILE = VENDOR_DIR / "vendor_sources.json"

SOURCES = {
    "MTGOFormatData": {
        "repo": "https://github.com/Badaro/MTGOFormatData.git",
        "target": FORMAT_TARGET,
    },
    "MTGOArchetypeParser": {
        "repo": "https://github.com/Badaro/MTGOArchetypeParser.git",
        "target": PARSER_TARGET,
    },
}


def run(cmd: list[str], cwd: Path | None = None) -> str:
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=True)
    return result.stdout.strip()


def clone(repo: str, dest: Path) -> Path:
    tempdir = Path(tempfile.mkdtemp(prefix="vendor-src-"))
    run(["git", "clone", "--depth", "1", repo, str(tempdir)])
    return tempdir


def refresh_format_data(tempdir: Path) -> None:
    source_formats = tempdir / "Formats"
    if not source_formats.exists():
        raise RuntimeError(f"Expected Formats directory missing in {tempdir}")

    if FORMAT_TARGET.exists():
        shutil.rmtree(FORMAT_TARGET)
    FORMAT_TARGET.mkdir(parents=True, exist_ok=True)

    shutil.copy(source_formats / FORMAT_CARD_FILE, FORMAT_TARGET / FORMAT_CARD_FILE)
    for entry in source_formats.iterdir():
        if entry.name == FORMAT_CARD_FILE or entry.name.startswith(".git"):
            continue
        target_path = FORMAT_TARGET / entry.name
        if entry.is_dir():
            shutil.copytree(entry, target_path)
        else:
            shutil.copy(entry, target_path)


def refresh_parser_license(tempdir: Path) -> None:
    license_src = tempdir / "LICENSE"
    if not license_src.exists():
        raise RuntimeError("Unable to locate LICENSE in MTGOArchetypeParser repository.")
    PARSER_TARGET.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(license_src, PARSER_TARGET)


def update_metadata(updates: dict[str, str]) -> None:
    metadata: dict[str, dict[str, str]]
    if METADATA_FILE.exists():
        metadata = json.loads(METADATA_FILE.read_text(encoding="utf-8"))
    else:
        metadata = {}
    for key, commit in updates.items():
        entry = metadata.setdefault(key, {})
        entry["repository"] = SOURCES[key]["repo"].removesuffix(".git")
        entry["commit"] = commit
    METADATA_FILE.write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def main() -> int:
    updates: dict[str, str] = {}
    for key, config in SOURCES.items():
        print(f"Updating {key}…", flush=True)
        tempdir = clone(config["repo"], ROOT)
        try:
            commit = run(["git", "rev-parse", "HEAD"], cwd=tempdir)
            updates[key] = commit
            if key == "MTGOFormatData":
                refresh_format_data(tempdir)
            else:
                refresh_parser_license(tempdir)
        finally:
            shutil.rmtree(tempdir, ignore_errors=True)
    update_metadata(updates)
    print("Vendor resources refreshed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
