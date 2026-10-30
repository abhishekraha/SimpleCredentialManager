<#
.SYNOPSIS
    Generates Windows Desktop and Start Menu shortcuts (.lnk) for Simple Credential Manager apps:
    1. Simple Credential Manager (Full Workstation Window)
    2. SCM Command Palette (Floating Quick Search)
    3. SCM System Tray (Minimized Tray Daemon)
#>

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..\..")
$DesktopPath = [Environment]::GetFolderPath("Desktop")

$TargetExe = Join-Path $RepoRoot "dist\SimpleCredentialManager-UI.exe"
$UseDist = Test-Path $TargetExe

$WshShell = New-Object -ComObject WScript.Shell

function Create-Shortcut {
    param (
        [string]$ShortcutName,
        [string]$Arguments,
        [string]$Description,
        [string]$Hotkey = ""
    )
    $LnkPath = Join-Path $DesktopPath "$ShortcutName.lnk"
    $Shortcut = $WshShell.CreateShortcut($LnkPath)

    if ($UseDist) {
        $Shortcut.TargetPath = $TargetExe
        $Shortcut.Arguments = $Arguments
    } else {
        $PythonW = Get-Command pythonw -ErrorAction SilentlyContinue
        if ($PythonW) {
            $Shortcut.TargetPath = $PythonW.Source
            $Shortcut.Arguments = "`"$RepoRoot\SimpleCredentialManagerUi.py`" $Arguments"
        } else {
            $Shortcut.TargetPath = "cmd.exe"
            $Shortcut.Arguments = "/c `"$RepoRoot\scripts\launchers\$ShortcutName.bat`""
        }
    }

    $Shortcut.WorkingDirectory = $RepoRoot.Path
    $Shortcut.Description = $Description
    if ($Hotkey) {
        $Shortcut.Hotkey = $Hotkey
    }
    $Shortcut.Save()
    Write-Host "[+] Created Desktop Shortcut: $ShortcutName.lnk" -ForegroundColor Green
}

Write-Host "Creating Simple Credential Manager Desktop Shortcuts..." -ForegroundColor Cyan
Create-Shortcut -ShortcutName "Simple Credential Manager" -Arguments "" -Description "Simple Credential Manager - Workstation Manager"
Create-Shortcut -ShortcutName "SCM Command Palette" -Arguments "--palette" -Description "SCM Floating Command Palette (Quick Search)" -Hotkey "Ctrl+Alt+Space"
Create-Shortcut -ShortcutName "SCM System Tray" -Arguments "--tray" -Description "SCM System Tray Daemon (Background)"

Write-Host ""
Write-Host "Done! Shortcuts placed on your Desktop." -ForegroundColor Green
