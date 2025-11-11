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

# Step 1: Check for Inno Setup
Write-Info "Checking for Inno Setup..."
$InnoSetupPath = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
if (-not (Test-Path $InnoSetupPath)) {
    $InnoSetupPath = "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
    if (-not (Test-Path $InnoSetupPath)) {
        Write-Error-Custom "Inno Setup not found. Please install Inno Setup 6 from https://jrsoftware.org/isdl.php"
        exit 1
    }
}
Write-Info "Inno Setup found at: $InnoSetupPath"

# Step 2: Check for PyInstaller
if (-not $SkipPyInstaller) {
    Write-Info "Checking for PyInstaller..."
    $PyInstallerCheck = Get-Command pyinstaller -ErrorAction SilentlyContinue
    if (-not $PyInstallerCheck) {
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
        & pyinstaller $SpecFile --clean --noconfirm
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
    $ExePath = Join-Path $DistDir "magic_online_metagame_crawler\magic_online_metagame_crawler.exe"
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
