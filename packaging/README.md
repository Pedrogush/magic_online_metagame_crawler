# Windows Installer Build Guide

This directory contains scripts and configuration for building a professional Windows installer for the MTGO Metagame Deck Builder using Inno Setup.

## Features

The installer includes:
- **License Agreement**: Displays the MIT License before installation
- **Custom Install Directory**: Users can choose where to install the application
- **Shortcuts**: Creates Start Menu shortcuts and optional Desktop/Quick Launch shortcuts
- **Bundled Dependencies**: Includes all necessary files:
  - PyInstaller-built Python executable
  - .NET Bridge executable (mtgo_bridge.exe)
  - Vendor data directories (card data, archetypes, etc.)
  - README and LICENSE files
- **Professional Wizard**: Modern Windows installer UI
- **Uninstaller**: Automatic uninstall support via Windows Programs & Features

## Prerequisites

### For Building on Windows

1. **Inno Setup 6** (or later)
   - Download from: https://jrsoftware.org/isdl.php
   - Install with default options

2. **Python 3.11+** with PyInstaller
   ```powershell
   pip install pyinstaller
   ```

3. **.NET 9 SDK** (optional, for rebuilding the bridge)
   - Download from: https://dotnet.microsoft.com/download/dotnet/9.0

### For Building on Linux

1. **Wine** (to run Inno Setup)
   ```bash
   # Ubuntu/Debian
   sudo apt-get install wine wine64

   # Arch
   sudo pacman -S wine

   # Fedora
   sudo dnf install wine
   ```

2. **Python 3.11+** with PyInstaller
   ```bash
   pip install pyinstaller
   ```

3. **Inno Setup** (automatically downloaded by build script)
   - The build script will download and install Inno Setup in Wine if not present

## Building the Installer

### On Windows

1. Navigate to the packaging directory:
   ```powershell
   cd packaging
   ```

2. Run the build script:
   ```powershell
   .\build_installer.ps1
   ```

   **Options:**
   ```powershell
   # Skip PyInstaller build (use existing executable)
   .\build_installer.ps1 -SkipPyInstaller

   # Skip .NET bridge build (use existing bridge)
   .\build_installer.ps1 -SkipDotNetBuild

   # Skip both
   .\build_installer.ps1 -SkipPyInstaller -SkipDotNetBuild
   ```

3. The installer will be created at:
   ```
   dist/installer/MTGOMetagameBuilder_Setup_v0.2.exe
   ```

### On Linux

1. Navigate to the packaging directory:
   ```bash
   cd packaging
   ```

2. Run the build script:
   ```bash
   ./build_installer.sh
   ```

   The script will:
   - Check for Wine and install Inno Setup if needed
   - Build the PyInstaller executable
   - Run Inno Setup via Wine
   - Create the installer in `dist/installer/`

3. The installer will be created at:
   ```
   dist/installer/MTGOMetagameBuilder_Setup_v0.2.exe
   ```

## Testing the Installer

After building, you should test that the installer was created correctly.

### On Windows

```powershell
.\test_installer.ps1
```

### On Linux

```bash
./test_installer.sh
```

The test script verifies:
- ✅ Installer file exists and is a valid PE executable
- ✅ File size is reasonable (not corrupted, not too small/large)
- ✅ Contains Inno Setup signature
- ✅ Contains application metadata (name, version, license)
- ✅ File integrity (can be read, not corrupted)
- ✅ Contains references to required components

### Manual Testing

To fully test the installer, you should:

1. **Run the installer on a Windows machine:**
   - Double-click the installer or run as administrator
   - Follow the installation wizard
   - Verify the license agreement is displayed
   - Test custom installation directory selection
   - Check that shortcuts are created correctly

2. **Test the installed application:**
   - Launch from Start Menu shortcut
   - Launch from Desktop shortcut (if created)
   - Verify all features work correctly
   - Check that the .NET bridge is accessible

3. **Test uninstallation:**
   - Go to Windows Settings → Apps → Installed apps
   - Find "MTGO Metagame Deck Builder"
   - Click Uninstall
   - Verify all files and shortcuts are removed

## File Structure

```
packaging/
├── README.md                           # This file
├── installer.iss                       # Inno Setup configuration
├── build_installer.sh                  # Linux build script
├── build_installer.ps1                 # Windows build script
├── test_installer.sh                   # Linux test script
├── test_installer.ps1                  # Windows test script
└── magic_online_metagame_crawler.spec  # PyInstaller spec file
```

## Customizing the Installer

### Changing the Version

Edit `installer.iss` and update the version:

```pascal
#define MyAppVersion "0.3"  // Change this
```

Also update in `pyproject.toml` and `setup.py`.

### Changing the Application Name

Edit `installer.iss`:

```pascal
#define MyAppName "Your App Name"
```

### Adding More Files

Edit the `[Files]` section in `installer.iss`:

```pascal
Source: "path/to/your/file"; DestDir: "{app}"; Flags: ignoreversion
```

### Customizing Shortcuts

Edit the `[Icons]` section in `installer.iss`:

```pascal
Name: "{group}\Your Shortcut"; Filename: "{app}\your.exe"
```

### Adding a Custom Icon

1. Add your icon file (`.ico`) to the project
2. Update `installer.iss`:

```pascal
[Setup]
SetupIconFile=path\to\your\icon.ico

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\your_icon.ico"
```

## Troubleshooting

### "Inno Setup not found"

- **Windows**: Install Inno Setup from https://jrsoftware.org/isdl.php
- **Linux**: The script will try to auto-install. If it fails, manually install Wine and Inno Setup

### "PyInstaller build failed"

1. Check that `main.py` exists in the project root
2. Verify the spec file path is correct
3. Check for missing dependencies: `pip install -r requirements.txt`

### ".NET bridge not found"

The installer will still build without the bridge, but you'll see a warning. To include it:

```bash
cd dotnet/MTGOBridge
dotnet publish -c Release -r win-x64 --self-contained false
```

### "Installer size is suspiciously small"

This usually means required files weren't included. Check:
- PyInstaller `dist/` directory exists and has files
- .NET bridge was built successfully
- Vendor data directories exist

### Linux: "Wine errors when running Inno Setup"

Try:
```bash
# Initialize Wine
winecfg

# Clear Wine cache
rm -rf ~/.wine
winetricks
```

## Advanced Usage

### Building for Distribution

Before distributing the installer:

1. **Update the version** in all files (`pyproject.toml`, `setup.py`, `installer.iss`)
2. **Add digital signature** (optional, requires code signing certificate):
   ```pascal
   [Setup]
   SignTool=signtool
   ```
3. **Test on clean Windows installation**
4. **Generate checksums** for distribution:
   ```bash
   sha256sum MTGOMetagameBuilder_Setup_v0.2.exe > checksums.txt
   ```

### Automated Builds (CI/CD)

The build scripts are designed to be CI/CD friendly. Example GitHub Actions workflow:

```yaml
name: Build Installer

on:
  push:
    tags:
      - 'v*'

jobs:
  build:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install pyinstaller
      - name: Build installer
        run: cd packaging && .\build_installer.ps1
      - name: Test installer
        run: cd packaging && .\test_installer.ps1
      - name: Upload artifact
        uses: actions/upload-artifact@v3
        with:
          name: installer
          path: dist/installer/*.exe
```

## Support

For issues with:
- **Inno Setup**: See https://jrsoftware.org/ishelp/
- **PyInstaller**: See https://pyinstaller.org/en/stable/
- **This project**: Open an issue on GitHub

## License

This installer configuration is part of the MTGO Metagame Deck Builder project and is licensed under the MIT License. See the LICENSE file in the project root for details.
