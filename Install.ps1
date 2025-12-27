# Get the full path of your GUI script in the current folder
$ScriptPath = Join-Path -Path $PSScriptRoot -ChildPath "organiser-gui.ps1"

$IconPath = Join-Path -Path $PSScriptRoot -ChildPath "logo.ico"

# Define where the shortcut goes
$ShortcutPath = "$([Environment]::GetFolderPath('Desktop'))\Photo Organiser.lnk"

# Create the shortcut object
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)

# This is the "Magic" command that makes it run smoothly
$Shortcut.TargetPath = "powershell.exe"
$Shortcut.Arguments = "-ExecutionPolicy Bypass -WindowStyle Hidden -File ""$ScriptPath"""

# Optional: Give it a nice icon (e.g., a Windows icon)
$Shortcut.IconLocation = $IconPath

$Shortcut.Save()

Write-Host "Shortcut created on your Desktop!" -ForegroundColor Green