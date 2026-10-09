# Agent KH — one-click Windows installer (PowerShell)
# Right-click -> "Run with PowerShell" (or: powershell -ExecutionPolicy Bypass -File install.ps1)
# Installs to %LOCALAPPDATA%\AgentKH, adds Start Menu shortcut,
# and registers Agent KH to start automatically with Windows.

$ErrorActionPreference = "Stop"
$AppName = "Agent KH"
$InstallDir = Join-Path $env:LOCALAPPDATA "AgentKH"
$SourceDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ExePath = Join-Path $InstallDir "AgentKH.exe"

Write-Host "Installing $AppName ..." -ForegroundColor Cyan

# 1. copy files
if (Test-Path $InstallDir) { Remove-Item $InstallDir -Recurse -Force }
New-Item -ItemType Directory -Path $InstallDir | Out-Null
Copy-Item (Join-Path $SourceDir "*") $InstallDir -Recurse -Force -Exclude "install.ps1","installer.nsi"

# 2. Start Menu shortcut
$Wsh = New-Object -ComObject WScript.Shell
$StartMenu = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
$Shortcut = $Wsh.CreateShortcut((Join-Path $StartMenu "$AppName.lnk"))
$Shortcut.TargetPath = $ExePath
$Shortcut.WorkingDirectory = $InstallDir
$Shortcut.Description = "Agent KH - your personal AI desktop agent"
$Shortcut.Save()

# 3. auto-start with Windows (registry Run key)
$RunKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
Set-ItemProperty -Path $RunKey -Name "AgentKH" -Value "`"$ExePath`""

# 4. optional: Pillow for vision (screenshots)
try {
    & python -m pip install --quiet pillow 2>$null
    Write-Host "Pillow installed (vision enabled)." -ForegroundColor Green
} catch {
    Write-Host "Note: install Pillow for vision:  pip install pillow" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Done! $AppName is installed and will start with Windows." -ForegroundColor Green
Write-Host "Starting now ..."
Start-Process $ExePath -WorkingDirectory $InstallDir
