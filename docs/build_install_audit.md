# Build and Installer Audit

Last reviewed on Linux host (building Windows installer with Wine + Inno Setup).

## Build flow
- `packaging/build_installer.ps1` (Windows) refreshes vendored data (`scripts/update_vendor_data.py`, `scripts/update_mtgosdk_vendor.py`), optionally builds the .NET bridge, then runs PyInstaller via `packaging/magic_online_metagame_crawler.spec` and invokes Inno Setup (`installer.iss`).
- `packaging/build_installer.sh` (Linux) runs PyInstaller and Inno Setup under Wine but does **not** refresh vendor data or attempt a bridge build; it relies on those artifacts already existing in `vendor/` and `dotnet/MTGOBridge/bin/.../publish/`.
- PyInstaller bundles the `main.py` entrypoint; `magic_online_metagame_crawler.spec` only adds vendor data folders (`vendor/mtgo_format_data`, `vendor/mtgo_archetype_parser`, `vendor/mtgosdk`) plus `mtgo_bridge.exe` if it exists at the published path.

## Installer contents (`packaging/installer.iss`)
- Installs the entire PyInstaller `dist` output and the full bridge publish directory (including the bundled .NET runtime) from `dotnet/MTGOBridge/bin/Release/net9.0-windows7.0/.../publish/` when present.
- Copies vendor datasets into `{app}/vendor/...` only if those directories already exist at build time.
- .NET runtime now ships via self-contained bridge publish (see Windows build script); no external runtime install required when the bridge is built.

## Python packaging gaps (`setup.py`)
- Packages list is limited to `widgets`, `navigators`, and `utils`, omitting `controllers`, `services`, `repositories`, and other modules used at runtime.
- `install_requires` is incomplete relative to actual usage/`requirements-dev.txt` (missing at least `wxPython`, `requests`, `defusedxml`, `pygetwindow`, `matplotlib`, `lxml`, etc.).
- Result: installing via `pip` with `setup.py` would not pull all runtime dependencies or package all modules needed by the app.

## Vendor/SDK coverage
- Vendor data inclusion depends on the `vendor/` folder being pre-populated; Windows build script tries to fetch it, Linux script does not.
- The MTGO bridge binary is included if published; the MTGOSDK NuGet contents are vendored via `scripts/update_mtgosdk_vendor.py` but only copied when the `vendor/mtgosdk` folder exists.
