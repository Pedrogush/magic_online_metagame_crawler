# -*- mode: python ; coding: utf-8 -*-

import os
import pathlib
import sys

block_cipher = None

def _spec_path() -> pathlib.Path:
    if "__file__" in globals():
        return pathlib.Path(__file__).resolve()
    if sys.argv:
        return pathlib.Path(sys.argv[0]).resolve()
    return pathlib.Path(".").resolve()

project_root = _spec_path().parents[1]

def tree(src: pathlib.Path, dest: str) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    if not src.exists():
        return result
    for root, _dirs, files in os.walk(src):
        for file in files:
            path = pathlib.Path(root) / file
            rel = path.relative_to(src)
            target_dir = pathlib.Path(dest) / rel.parent
            result.append((str(path), str(target_dir)))
    return result

datas = []
for rel in [
    "vendor/mtgo_format_data",
    "vendor/mtgo_archetype_parser",
    "vendor/mtgosdk",
]:
    src = project_root / rel
    if src.exists():
        datas += tree(src, rel)

binaries = []
bridge_candidates = [
    project_root
    / "dotnet"
    / "MTGOBridge"
    / "bin"
    / "Release"
    / "net9.0-windows7.0"
    / "win-x64"
    / "publish"
    / "mtgo_bridge.exe",
    project_root
    / "dotnet"
    / "MTGOBridge"
    / "bin"
    / "Release"
    / "net9.0-windows7.0"
    / "publish"
    / "mtgo_bridge.exe",
]
for candidate in bridge_candidates:
    if candidate.exists():
        binaries.append((str(candidate), "mtgo_bridge.exe"))
        break

a = Analysis(
    ["main_wx.py"],
    pathex=[str(project_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="magic_online_metagame_crawler",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
