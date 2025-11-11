#!/usr/bin/env python3
"""Fetch the mana symbol assets from andrewgioia/mana when missing."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def _run_git_clone(url: str, target: Path, depth: int = 1) -> None:
    cmd = [
        "git",
        "clone",
        url,
        str(target),
        "--depth",
        str(depth),
    ]
    subprocess.check_call(cmd)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-fetch assets even if the assets/mana directory already exists.",
    )
    parser.add_argument(
        "--repo",
        default="https://github.com/andrewgioia/mana.git",
        help="Git repository to clone (default: %(default)s)",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    assets_dir = project_root / "assets"
    target_dir = assets_dir / "mana"

    if target_dir.exists():
        if not args.force:
            print(f"Mana assets already present at {target_dir}")
            return 0
        print(f"Removing existing directory {target_dir} (force requested)")
        shutil.rmtree(target_dir)

    assets_dir.mkdir(parents=True, exist_ok=True)

    try:
        print(f"Cloning {args.repo} into {target_dir}…")
        _run_git_clone(args.repo, target_dir)
    except subprocess.CalledProcessError as exc:
        print(f"Failed to clone mana assets: {exc}", file=sys.stderr)
        if target_dir.exists():
            shutil.rmtree(target_dir)
        return exc.returncode or 1

    print("Mana assets downloaded successfully.")
    print("You may keep the repository as-is or prune unused files if desired.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
