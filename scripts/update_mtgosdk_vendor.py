#!/usr/bin/env python3
"""Download and extract MTGOSDK NuGet packages into vendor/mtgosdk."""

from __future__ import annotations

import argparse
import json
import shutil
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENDOR_ROOT = ROOT / "vendor" / "mtgosdk"

PACKAGES = ["MTGOSDK", "MTGOSDK.Win32"]


def fetch_latest_version(package: str) -> str:
    index_url = f"https://api.nuget.org/v3-flatcontainer/{package.lower()}/index.json"
    with urllib.request.urlopen(index_url) as resp:
        data = json.load(resp)
    versions = data.get("versions")
    if not versions:
        raise RuntimeError(f"No versions found for {package}")
    return versions[-1]


def download_package(package: str, version: str, target: Path) -> Path:
    target.mkdir(parents=True, exist_ok=True)
    filename = target / f"{package}.{version}.nupkg"
    download_url = (
        f"https://api.nuget.org/v3-flatcontainer/{package.lower()}/{version}/{package.lower()}.{version}.nupkg"
    )
    with urllib.request.urlopen(download_url) as resp, open(filename, "wb") as fh:
        shutil.copyfileobj(resp, fh)
    return filename


def extract_package(nupkg: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(nupkg) as zf:
        zf.extractall(destination)


def copy_license_files(source_root: Path) -> None:
    for name in ("LICENSE", "NOTICE"):
        src = source_root / name
        if src.exists():
            shutil.copy(src, VENDOR_ROOT / name)
            return
    # fallback: download from upstream repo
    urllib.request.urlretrieve(
        "https://raw.githubusercontent.com/videre-project/MTGOSDK/main/LICENSE",
        VENDOR_ROOT / "LICENSE",
    )
    urllib.request.urlretrieve(
        "https://raw.githubusercontent.com/videre-project/MTGOSDK/main/NOTICE",
        VENDOR_ROOT / "NOTICE",
    )


def update_sources_json(version: str, commit: str | None) -> None:
    sources_path = ROOT / "vendor" / "vendor_sources.json"
    if sources_path.exists():
        data = json.loads(sources_path.read_text(encoding="utf-8"))
    else:
        data = {}
    for package in PACKAGES:
        entry = data.setdefault(package, {})
        entry["repository"] = "https://github.com/videre-project/MTGOSDK"
        entry["version"] = version
        if commit:
            entry["commit"] = commit
    sources_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def resolve_commit(nuspec_path: Path) -> str | None:
    try:
        import xml.etree.ElementTree as ET
    except ImportError:
        return None
    root = ET.parse(nuspec_path).getroot()
    namespace = {"ns": root.tag.split("}")[0].strip("{")}
    repo = root.find("ns:metadata/ns:repository", namespace)
    if repo is None:
        return None
    return repo.attrib.get("commit")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", help="Specific MTGOSDK version (defaults to latest)")
    args = parser.parse_args()

    version = args.version or fetch_latest_version(PACKAGES[0])
    VENDOR_ROOT.mkdir(parents=True, exist_ok=True)

    commit_hash: str | None = None
    for package in PACKAGES:
        print(f"Fetching {package} {version}…")
        nupkg = download_package(package, version, VENDOR_ROOT)
        extract_dir = VENDOR_ROOT / package
        extract_package(nupkg, extract_dir)
        nuspec = next(extract_dir.glob("*.nuspec"), None)
        if nuspec is not None and commit_hash is None:
            commit_hash = resolve_commit(nuspec)

    copy_license_files(VENDOR_ROOT / PACKAGES[0])
    update_sources_json(version, commit_hash)
    print("MTGOSDK vendor refresh complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
