# -*- mode: python ; coding: utf-8 -*-

import pathlib

from PyInstaller.utils.hooks import Tree

block_cipher = None

project_root = pathlib.Path(__file__).resolve().parents[1]

datas = []
for rel in [
    "vendor/mtgo_format_data",
    "vendor/mtgo_archetype_parser",
    "vendor/mtgosdk",
]:
    src = project_root / rel
    if src.exists():
        datas += Tree(str(src), rel)

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
    ["main.py"],
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
