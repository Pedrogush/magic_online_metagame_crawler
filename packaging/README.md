# Windows Installer Build

Build on Windows: `.\build_installer.ps1`
Build on Linux: `./build_installer.sh`
Test: `.\test_installer.ps1` or `./test_installer.sh`

This directory contains Inno Setup configuration and build scripts for creating a professional Windows installer. The installer includes license agreement, custom install directory selection, Start Menu and Desktop shortcuts, and bundles all dependencies including the PyInstaller executable, .NET bridge, and vendor data.

Prerequisites: Inno Setup 6, Python 3.11+ with PyInstaller, and optionally .NET 9 SDK (used to publish a self-contained bridge that bundles the .NET runtime). On Linux the build script uses Wine to run Inno Setup and will automatically download it if not present. Output is created at dist/installer/MTGOMetagameBuilder_Setup_v0.2.exe.

To customize edit installer.iss to change version, app name, included files, or shortcuts. For distribution sign the installer and generate checksums. The build and test scripts are CI/CD friendly.

Notes:
- Mana symbol assets are auto-fetched (and bundled) during the build if `assets/mana` is missing.
