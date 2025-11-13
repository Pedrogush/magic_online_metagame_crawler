# Installation Guide

This guide provides detailed instructions for installing and setting up MTGO Metagame Tools on Windows.

## Table of Contents

- [System Requirements](#system-requirements)
- [Python Setup](#python-setup)
- [Installing Dependencies](#installing-dependencies)
- [Optional Components](#optional-components)
- [MTGO Bridge Setup](#mtgo-bridge-setup)
- [First Run](#first-run)
- [Troubleshooting](#troubleshooting)
- [Uninstallation](#uninstallation)

## System Requirements

### Required
- **Operating System**: Windows 10 or later (64-bit)
- **Python**: 3.11 or newer
- **RAM**: 4 GB minimum, 8 GB recommended
- **Disk Space**: 500 MB for application + 2-3 GB for card images (optional)
- **Internet Connection**: Required for metagame data and card images

### Optional
- **Magic Online**: Required for collection import and match history features
- **MongoDB**: Optional, for deck persistence (defaults to file-based storage)
- **.NET 9.0 SDK**: Required for MTGO Bridge functionality

## Python Setup

### Step 1: Install Python

1. Download Python 3.11 or newer from [python.org](https://www.python.org/downloads/)
2. Run the installer
3. **Important**: Check "Add Python to PATH" during installation
4. Complete the installation

### Step 2: Verify Python Installation

Open **Command Prompt** or **PowerShell** and run:

```bash
python --version
```

You should see output like: `Python 3.11.x`

If you see an error, Python is not in your PATH. Reinstall and check the PATH option.

## Installing Dependencies

### Step 1: Clone or Download the Repository

**Option A: Using Git**
```bash
git clone https://github.com/Pedrogush/magic_online_metagame_crawler.git
cd magic_online_metagame_crawler
```

**Option B: Download ZIP**
1. Download the ZIP from GitHub
2. Extract to a folder (e.g., `C:\Users\YourName\Documents\magic_online_metagame_crawler`)
3. Open Command Prompt in that folder

### Step 2: Create a Virtual Environment (Recommended)

```bash
# Create virtual environment
python -m venv venv

# Activate it
venv\Scripts\activate
```

Your prompt should now show `(venv)` prefix.

### Step 3: Install Python Dependencies

```bash
pip install -r requirements-dev.txt
```

This will install all required packages including:
- wxPython (GUI framework)
- requests (HTTP client)
- beautifulsoup4 (web scraping)
- pymongo (database, optional)
- Pillow (image processing)
- loguru (logging)
- pytest (testing)

**Installation may take 5-10 minutes** as wxPython is a large package.

### Step 4: Verify Installation

```bash
python -c "import wx; print('wxPython version:', wx.version())"
```

If you see a version number, wxPython is installed correctly.

## Optional Components

### MongoDB (Optional)

MongoDB enables saving decks to a database instead of files.

1. Download MongoDB Community Server from [mongodb.com](https://www.mongodb.com/try/download/community)
2. Install with default settings
3. MongoDB will run on `mongodb://localhost:27017/` by default

**Note**: The application works fine without MongoDB using file-based storage.

### Tesseract OCR (Future Feature)

Currently not required but may be used for future OCR features.

## MTGO Bridge Setup

The MTGO Bridge allows importing your collection and match history from Magic Online.

### Step 1: Install .NET SDK

1. Download [.NET 9.0 SDK](https://dotnet.microsoft.com/download/dotnet/9.0)
2. Run the installer
3. Verify installation:

```powershell
dotnet --version
```

You should see `9.0.x` or later.

### Step 2: Build the MTGO Bridge

```powershell
cd dotnet\MTGOBridge
dotnet restore
dotnet add package MTGOSDK
dotnet build MTGOBridge.csproj
```

### Step 3: Publish the Bridge (Optional)

For a standalone executable:

```powershell
dotnet publish MTGOBridge.csproj -c Release -r win-x64 --self-contained false
```

The executable will be at:
```
dotnet\MTGOBridge\bin\Release\net9.0-windows7.0\win-x64\publish\MTGOBridge.exe
```

### Step 4: Configure Bridge Path

The application will look for the bridge in:
1. Environment variable: `MTGO_BRIDGE_PATH`
2. Default: `dotnet/MTGOBridge/bin/Debug/net9.0-windows7.0/MTGOBridge.exe`

**To set environment variable** (optional):

```powershell
# PowerShell (current session)
$env:MTGO_BRIDGE_PATH = "C:\path\to\MTGOBridge.exe"

# Permanent (requires admin)
[System.Environment]::SetEnvironmentVariable('MTGO_BRIDGE_PATH', 'C:\path\to\MTGOBridge.exe', 'User')
```

For detailed bridge setup, see `dotnet/MTGOBridge/README.md`.

## First Run

### Step 1: Launch the Application

```bash
# From the repository root
python main.py
```

The main window should appear.

### Step 2: Download Card Data (First Time Only)

On first run, the application will download card metadata from Scryfall:

1. This happens automatically when browsing cards
2. Data is cached in `cache/oracle-cards.json` (~30 MB)
3. Updates automatically when stale (every 24 hours)

### Step 3: Download Mana Symbols (Optional)

For proper mana symbol rendering:

```bash
python -m scripts.fetch_mana_assets
```

This downloads SVG mana symbols to `assets/mana_symbols/`.

### Step 4: Test Basic Functionality

1. Click **Tools** → **Metagame Analysis**
2. Select a format (e.g., "Modern")
3. Click "Refresh Data"
4. You should see current metagame archetypes

If this works, your installation is successful!

## Configuration

### Optional: MongoDB Connection

If you installed MongoDB and want to use it:

1. Set environment variable:
   ```powershell
   $env:MONGODB_URI = "mongodb://localhost:27017/"
   ```

2. Or edit your code to point to a remote MongoDB instance

**Note**: Currently MongoDB URI is hardcoded. See GitHub issues for configuration file support.

### Optional: Custom Deck Storage

By default, decks are saved to `decks/` in the repository root.

To change this:
1. Edit `config.json` in the repository root:
   ```json
   {
     "default_deck_save_path": "C:\\Users\\YourName\\Documents\\MTG\\Decks"
   }
   ```

### Optional: Pytest Host Configuration (Developers)

If you're developing and want to run tests on a Windows host via SSH:

1. Copy the example configuration:
   ```bash
   cp pytest_host.conf.example ~/.ssh/pytest_host.conf
   ```

2. Edit `~/.ssh/pytest_host.conf`:
   ```bash
   HOST_USER="your_windows_username"
   HOST_IP="192.168.x.x"
   PYTEST_PATH="C:/path/to/pytest.exe"
   PROJECT_PATH="C:/path/to/project"
   SSH_KEY="${HOME}/.ssh/id_ed25519"
   ```

See [WORKFLOW.md](WORKFLOW.md) for details on the development workflow.

## Upgrading

### Upgrading Python Dependencies

```bash
# Activate virtual environment
venv\Scripts\activate

# Upgrade all packages
pip install --upgrade -r requirements-dev.txt
```

### Upgrading MTGO Bridge

```powershell
cd dotnet\MTGOBridge
dotnet add package MTGOSDK  # Gets latest version
dotnet build
```

### Pulling Latest Code

```bash
git pull origin main
pip install --upgrade -r requirements-dev.txt
```

## Troubleshooting

### Issue: "python: command not found"

**Solution**: Python is not in your PATH.
1. Reinstall Python
2. Check "Add Python to PATH" during installation
3. Or manually add Python to PATH:
   - Search "Environment Variables" in Windows
   - Edit PATH
   - Add `C:\Users\YourName\AppData\Local\Programs\Python\Python311`

### Issue: wxPython installation fails

**Solution**: wxPython requires Microsoft Visual C++ 14.0 or greater.
1. Download [Microsoft C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/)
2. Install "Desktop development with C++"
3. Retry: `pip install wxPython`

### Issue: "Module not found" errors

**Solution**: Dependencies not installed or virtual environment not activated.
```bash
# Activate venv
venv\Scripts\activate

# Reinstall dependencies
pip install -r requirements-dev.txt
```

### Issue: Application window is blank or crashes

**Solution**: wxPython may not be compatible with your display settings.
1. Update graphics drivers
2. Try running with:
   ```bash
   python main.py --no-hardware-acceleration  # (if supported)
   ```
3. Check wxPython compatibility with your Windows version

### Issue: Card images not loading

**Solution**:
1. Check internet connection
2. Run mana symbols download:
   ```bash
   python -m scripts.fetch_mana_assets
   ```
3. Check Scryfall API status: https://scryfall.com/docs/api

### Issue: MTGO Bridge not found

**Solution**:
1. Verify bridge is built:
   ```bash
   dir dotnet\MTGOBridge\bin\Debug\net9.0-windows7.0\
   ```
   You should see `MTGOBridge.exe`

2. Or set explicit path:
   ```powershell
   $env:MTGO_BRIDGE_PATH = "C:\full\path\to\MTGOBridge.exe"
   ```

### Issue: "Connection refused" when saving to MongoDB

**Solution**: MongoDB is not running.
```powershell
# Check if MongoDB service is running
sc query MongoDB

# Start MongoDB service
net start MongoDB
```

### Issue: Collection import fails

**Solution**: MTGO must be running when using the bridge.
1. Launch Magic Online
2. Log in
3. Try collection import again

### Issue: Tests fail with "ModuleNotFoundError"

**Solution**: Install dev dependencies and activate virtual environment.
```bash
venv\Scripts\activate
pip install -r requirements-dev.txt
```

## Uninstallation

### Complete Removal

1. **Delete the repository folder**:
   ```bash
   cd ..
   rmdir /s magic_online_metagame_crawler
   ```

2. **Remove virtual environment** (if created separately):
   ```bash
   rmdir /s venv
   ```

3. **Optional: Remove cache and data**:
   - Cache: `%USERPROFILE%\.cache\mtg_metagame_tools\` (if exists)
   - Decks: Wherever you saved them (default: `decks/` in repository)

4. **Optional: Uninstall MongoDB** (if installed):
   - Use Windows "Add or Remove Programs"
   - Search for "MongoDB"
   - Uninstall

5. **Optional: Uninstall .NET SDK** (if installed only for this app):
   - Use Windows "Add or Remove Programs"
   - Search for ".NET SDK"
   - Uninstall (be careful if other apps use it)

### Partial Removal (Keep Configuration)

If you want to reinstall later but keep your decks and configuration:

1. Delete only the repository folder
2. Keep:
   - `decks/` folder (copy to safe location)
   - `cache/deck_notes.json`
   - `cache/deck_sbguides.json`
   - `config.json`

## Next Steps

After installation:

1. **Read the Usage Section**: See [README.md](README.md#usage) for how to use the application
2. **Explore Features**: Try the different tools (Opponent Spy, Match History, Metagame Analysis)
3. **Import Your Collection**: Use the MTGO Bridge to import your collection (optional)
4. **Join Development**: See [WORKFLOW.md](WORKFLOW.md) if you want to contribute

## Getting Help

- **Issues**: [GitHub Issues](https://github.com/Pedrogush/magic_online_metagame_crawler/issues)
- **Documentation**: Check other `.md` files in the repository
- **Logs**: Check console output for error messages

---

**Last Updated**: November 2025
**Document Version**: 1.0
