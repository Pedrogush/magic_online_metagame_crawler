; Inno Setup Script for MTGO Metagame Deck Builder
; This script creates a Windows installer with license agreement, custom install directory, and shortcuts

#define MyAppName "MTGO Metagame Deck Builder"
#define MyAppVersion "0.2"
#define MyAppPublisher "MTGO Metagame Crawler Contributors"
#define MyAppURL "https://github.com/yourusername/magic_online_metagame_crawler"
#define MyAppExeName "magic_online_metagame_crawler.exe"

[Setup]
; NOTE: The value of AppId uniquely identifies this application. Do not use the same AppId value in installers for other applications.
AppId={{8F9A2D3B-1C4E-5F6A-7B8C-9D0E1F2A3B4C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
; Uncomment the following line to run in non administrative install mode (install for current user only.)
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=../dist/installer
OutputBaseFilename=MTGOMetagameBuilder_Setup_v{#MyAppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; License file
LicenseFile=../LICENSE
; Require Windows 10 or later (matches .NET 9 requirement)
MinVersion=10.0.17763
; Only support x64
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Main executable created by PyInstaller
Source: "../dist/{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
; All other files from PyInstaller bundle
Source: "../dist/*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; .NET Bridge executable + runtime (self-contained publish)
#if DirExists('../dotnet/MTGOBridge/bin/Release/net9.0-windows7.0/win-x64/publish')
Source: "../dotnet/MTGOBridge/bin/Release/net9.0-windows7.0/win-x64/publish/*"; DestDir: "{app}/dotnet/MTGOBridge/bin/Release/net9.0-windows7.0/win-x64/publish"; Flags: ignoreversion recursesubdirs createallsubdirs
#endif
#if DirExists('../dotnet/MTGOBridge/bin/Release/net9.0-windows7.0/publish')
Source: "../dotnet/MTGOBridge/bin/Release/net9.0-windows7.0/publish/*"; DestDir: "{app}/dotnet/MTGOBridge/bin/Release/net9.0-windows7.0/publish"; Flags: ignoreversion recursesubdirs createallsubdirs
#endif
; Vendor data directories (if they exist)
#if DirExists('../vendor/mtgo_format_data')
Source: "../vendor/mtgo_format_data/*"; DestDir: "{app}/vendor/mtgo_format_data"; Flags: ignoreversion recursesubdirs createallsubdirs
#endif
#if DirExists('../vendor/mtgo_archetype_parser')
Source: "../vendor/mtgo_archetype_parser/*"; DestDir: "{app}/vendor/mtgo_archetype_parser"; Flags: ignoreversion recursesubdirs createallsubdirs
#endif
#if DirExists('../vendor/mtgosdk')
Source: "../vendor/mtgosdk/*"; DestDir: "{app}/vendor/mtgosdk"; Flags: ignoreversion recursesubdirs createallsubdirs
#endif
; README and LICENSE
Source: "../README.md"; DestDir: "{app}"; Flags: ignoreversion isreadme
Source: "../LICENSE"; DestDir: "{app}"; Flags: ignoreversion

[Dirs]
Name: "{app}\logs"
Name: "{app}\config"
Name: "{app}\cache"
Name: "{app}\decks"

[Icons]
; Start Menu shortcuts
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{group}\README"; Filename: "{app}\README.md"
; Desktop shortcut (optional, based on task selection)
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; Option to launch the application after installation
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
// Check if the .NET bridge executable exists before trying to include it

// Check if vendor directory exists
function VendorDirExists(DirName: String): Boolean;
var
  VendorPath: String;
begin
  VendorPath := ExpandConstant('{#SourcePath}\..\vendor\' + DirName);
  Result := DirExists(VendorPath);
  if not Result then
    Log('Info: Vendor directory not found: ' + VendorPath);
end;
