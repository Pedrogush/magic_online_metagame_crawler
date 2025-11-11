# Build script for creating the MTGO Metagame Deck Builder installer
# This script runs on Windows and creates the installer using Inno Setup
#
# Prerequisites:
# - Inno Setup 6 installed (https://jrsoftware.org/isdl.php)
# - PyInstaller installed (pip install pyinstaller)
# - .NET 9 SDK (optional, if you want to rebuild the bridge)

param(
    [switch]$SkipPyInstaller = $false,
    [switch]$SkipDotNetBuild = $false
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$DistDir = Join-Path $ProjectRoot "dist"
$InstallerDir = Join-Path $DistDir "installer"

function Write-Info {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Green
}

function Write-Warn {
    param([string]$Message)
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Write-Error-Custom {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

function Ensure-GitSync {
    $GitDir = Join-Path $ProjectRoot ".git"
    if (-not (Test-Path $GitDir)) {
        Write-Warn "Git repository not found in project root; skipping git pull."
        return
    }

    Write-Info "Syncing with remote branch..."
    $currentLocation = Get-Location
    Push-Location $ProjectRoot
    try {
        git pull --ff-only
    } catch {
        Write-Warn "Git pull failed: $_"
    } finally {
        Pop-Location
    }
}

# Ensure we are on the latest branch before building
Ensure-GitSync

# Step 0: ensure vendor data directories exist
Write-Info "Updating vendor data..."
Push-Location $ProjectRoot
try {
    $VendorUpdateScript = Join-Path $ProjectRoot "scripts\update_vendor_data.py"
    if (-not (Test-Path $VendorUpdateScript)) {
        Write-Warn "Vendor update script not found; skipping vendor refresh."
    } else {
        $VendorPython = Join-Path $ProjectRoot "env\Scripts\python.exe"
        if (Test-Path $VendorPython) {
            & $VendorPython $VendorUpdateScript
        } else {
            $FallbackPython = Get-Command python -ErrorAction SilentlyContinue
            if ($FallbackPython) {
                & $FallbackPython.Source $VendorUpdateScript
            } else {
                Write-Warn "Python not found; cannot update vendor data."
            }
        }
        if ($LASTEXITCODE -ne 0) {
            Write-Warn "Vendor update script exited with code $LASTEXITCODE"
        }
    }
    foreach ($vendorDir in @("vendor\mtgo_format_data", "vendor\mtgo_archetype_parser", "vendor\mtgosdk")) {
        $fullPath = Join-Path $ProjectRoot $vendorDir
        if (-not (Test-Path $fullPath)) {
            Write-Info "Creating missing vendor directory: $vendorDir"
            New-Item -ItemType Directory -Force -Path $fullPath | Out-Null
        }
    }
} finally {
    Pop-Location
}

# Step 1: Check for Inno Setup
function Get-EnvValue {
    param([string]$Name)

    try {
        $envItem = Get-Item "env:$Name" -ErrorAction Stop
        return $envItem.Value
    } catch {
        return $null
    }
}

Write-Info "Checking for Inno Setup..."
$InnoSetupPath = $env:INNO_SETUP_PATH
if (-not $InnoSetupPath) {
    $ProgramFilesX86 = Get-EnvValue "ProgramFiles(x86)"
    if ($ProgramFilesX86) {
        $candidate = Join-Path $ProgramFilesX86 "Inno Setup 6\ISCC.exe"
        if (Test-Path $candidate) {
            $InnoSetupPath = $candidate
        }
    }
}

if (-not $InnoSetupPath) {
    $ProgramFiles = Get-EnvValue "ProgramFiles"
    if ($ProgramFiles) {
        $candidate = Join-Path $ProgramFiles "Inno Setup 6\ISCC.exe"
        if (Test-Path $candidate) {
            $InnoSetupPath = $candidate
        }
    }
}

if (-not $InnoSetupPath) {
    Write-Error-Custom "Inno Setup not found. Please install Inno Setup 6 from https://jrsoftware.org/isdl.php"
    exit 1
}

Write-Info "Inno Setup found at: $InnoSetupPath"

function Find-PyInstallerPath {
    param([string]$ProjectRoot)

    $explicit = Join-Path $ProjectRoot "env\Scripts\pyinstaller.exe"
    Write-Info "Looking for PyInstaller at explicit path: $explicit"
    if (Test-Path $explicit) {
        Write-Info "PyInstaller found explicitly."
        return $explicit
    }

    $fromEnv = Get-Command pyinstaller -ErrorAction SilentlyContinue
    if ($fromEnv) {
        Write-Info "PyInstaller found via PATH: $($fromEnv.Path)"
        return $fromEnv.Path
    }

    Write-Warn "PyInstaller not found explicitly or via PATH."
    return $null
}

# Step 2: Check for PyInstaller
if (-not $SkipPyInstaller) {
    Write-Info "Checking for PyInstaller..."
    $PyInstallerPath = Find-PyInstallerPath -ProjectRoot $ProjectRoot
    if (-not $PyInstallerPath) {
        Write-Error-Custom "PyInstaller is not installed. Install it with: pip install pyinstaller"
        exit 1
    }

    # Step 3: Build PyInstaller executable
    Write-Info "Building PyInstaller executable..."
    Push-Location $ProjectRoot

    # Check if main.py exists
    if (-not (Test-Path "main.py")) {
        Write-Error-Custom "main.py not found. Please ensure the entry point exists."
        Pop-Location
        exit 1
    }

    # Run PyInstaller with the spec file
    $SpecFile = Join-Path $ProjectRoot "packaging\magic_online_metagame_crawler.spec"
    if (Test-Path $SpecFile) {
        Write-Info "Using existing spec file..."
        & $PyInstallerPath $SpecFile --clean --noconfirm
        if ($LASTEXITCODE -ne 0) {
            Write-Error-Custom "PyInstaller build failed!"
            Pop-Location
            exit 1
        }
    } else {
        Write-Error-Custom "PyInstaller spec file not found at packaging\magic_online_metagame_crawler.spec"
        Pop-Location
        exit 1
    }

    # Verify the executable was created
    $ExePath = Join-Path $DistDir "magic_online_metagame_crawler.exe"
    if (-not (Test-Path $ExePath)) {
        Write-Error-Custom "PyInstaller build failed - executable not found at $ExePath"
        Pop-Location
        exit 1
    }

    Write-Info "PyInstaller build complete!"
    Pop-Location
} else {
    Write-Info "Skipping PyInstaller build (using existing executable)"
}

# Step 4: Check for .NET bridge (optional)
if (-not $SkipDotNetBuild) {
    $BridgePath = Join-Path $ProjectRoot "dotnet\MTGOBridge\bin\Release\net9.0-windows7.0\win-x64\publish\mtgo_bridge.exe"
    if (-not (Test-Path $BridgePath)) {
        Write-Warn ".NET bridge not found at expected location: $BridgePath"
        Write-Warn "Attempting to build the .NET bridge..."

        # Check for dotnet SDK
        $DotNetCheck = Get-Command dotnet -ErrorAction SilentlyContinue
        if ($DotNetCheck) {
            Push-Location (Join-Path $ProjectRoot "dotnet\MTGOBridge")
            Write-Info "Building .NET bridge..."
            & dotnet publish -c Release -r win-x64 --self-contained false
            Pop-Location

            if (-not (Test-Path $BridgePath)) {
                Write-Warn ".NET bridge build completed but executable not found. Installer will be created without it."
            } else {
                Write-Info ".NET bridge build complete!"
            }
        } else {
            Write-Warn ".NET SDK not found. Installer will be created without the bridge."
            Write-Warn "To include the bridge, install .NET 9 SDK and run: dotnet publish -c Release -r win-x64"
        }
    } else {
        Write-Info ".NET bridge found at: $BridgePath"
    }
}

# Step 5: Create installer output directory
Write-Info "Creating installer output directory..."
New-Item -ItemType Directory -Force -Path $InstallerDir | Out-Null

# Step 6: Run Inno Setup Compiler
Write-Info "Running Inno Setup Compiler..."
$IssFile = Join-Path $ScriptDir "installer.iss"

& $InnoSetupPath $IssFile
if ($LASTEXITCODE -ne 0) {
    Write-Error-Custom "Inno Setup compilation failed!"
    exit 1
}

# Step 7: Verify the installer was created
$InstallerFile = Join-Path $InstallerDir "MTGOMetagameBuilder_Setup_v0.2.exe"
if (-not (Test-Path $InstallerFile)) {
    Write-Error-Custom "Installer was not created at expected location: $InstallerFile"
    exit 1
}

# Get installer size
$InstallerSize = (Get-Item $InstallerFile).Length / 1MB
$InstallerSizeFormatted = "{0:N2} MB" -f $InstallerSize

Write-Info "=========================================="
Write-Info "Installer build SUCCESSFUL!"
Write-Info "=========================================="
Write-Info "Installer location: $InstallerFile"
Write-Info "Installer size: $InstallerSizeFormatted"
Write-Info ""
Write-Info "You can now run this installer to install the application."
Write-Info "To test the installer, run: .\test_installer.ps1"
