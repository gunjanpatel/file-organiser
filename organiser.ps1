param (
    [string]$SourceDir,
    [string]$DestDir
)

# Check for missing arguments
if (-not $SourceDir -or -not $DestDir) {
    Write-Host "❌ Usage: .\organize.ps1 <source_directory> <destination_directory>" -ForegroundColor Red
    exit 1
}

# Check if source exists
if (-not (Test-Path -Path $SourceDir -PathType Container)) {
    Write-Host "❌ Source directory does not exist: $SourceDir" -ForegroundColor Red
    exit 1
}

# Create destination if it doesn't existAdd-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

# --- Create the Main Window ---
$Form = New-Object System.Windows.Forms.Form
$Form.Text = "File Organizer Tool"
$Form.Size = New-Object System.Drawing.Size(450, 300)
$Form.StartPosition = "CenterScreen"
$Form.FormBorderStyle = "FixedDialog"
$Form.MaximizeBox = $false

# --- Labels and Inputs ---
$LabelSrc = New-Object System.Windows.Forms.Label
$LabelSrc.Text = "Source Folder:"
$LabelSrc.Location = New-Object System.Drawing.Point(20, 20)
$LabelSrc.AutoSize = $true
$Form.Controls.Add($LabelSrc)

$TxtSrc = New-Object System.Windows.Forms.TextBox
$TxtSrc.Location = New-Object System.Drawing.Point(20, 45)
$TxtSrc.Size = New-Object System.Drawing.Size(300, 20)
$Form.Controls.Add($TxtSrc)

$BtnSrc = New-Object System.Windows.Forms.Button
$BtnSrc.Text = "Browse"
$BtnSrc.Location = New-Object System.Drawing.Point(330, 43)
$Form.Controls.Add($BtnSrc)

$LabelDest = New-Object System.Windows.Forms.Label
$LabelDest.Text = "Destination Folder:"
$LabelDest.Location = New-Object System.Drawing.Point(20, 85)
$LabelDest.AutoSize = $true
$Form.Controls.Add($LabelDest)

$TxtDest = New-Object System.Windows.Forms.TextBox
$TxtDest.Location = New-Object System.Drawing.Point(20, 110)
$TxtDest.Size = New-Object System.Drawing.Size(300, 20)
$Form.Controls.Add($TxtDest)

$BtnDest = New-Object System.Windows.Forms.Button
$BtnDest.Text = "Browse"
$BtnDest.Location = New-Object System.Drawing.Point(330, 108)
$Form.Controls.Add($BtnDest)

# --- Progress Bar ---
$ProgressBar = New-Object System.Windows.Forms.ProgressBar
$ProgressBar.Location = New-Object System.Drawing.Point(20, 210)
$ProgressBar.Size = New-Object System.Drawing.Size(390, 23)
$ProgressBar.Style = "Continuous"
$Form.Controls.Add($ProgressBar)

$StatusLabel = New-Object System.Windows.Forms.Label
$StatusLabel.Text = "Ready"
$StatusLabel.Location = New-Object System.Drawing.Point(20, 190)
$StatusLabel.AutoSize = $true
$Form.Controls.Add($StatusLabel)

# --- Logic for Buttons ---
$FolderBrowser = New-Object System.Windows.Forms.FolderBrowserDialog

$BtnSrc.Add_Click({
    if ($FolderBrowser.ShowDialog() -eq "OK") { $TxtSrc.Text = $FolderBrowser.SelectedPath }
})

$BtnDest.Add_Click({
    if ($FolderBrowser.ShowDialog() -eq "OK") { $TxtDest.Text = $FolderBrowser.SelectedPath }
})

# --- Main Logic Execution ---
$BtnRun = New-Object System.Windows.Forms.Button
$BtnRun.Text = "Start Organizing"
$BtnRun.Location = New-Object System.Drawing.Point(150, 150)
$BtnRun.Size = New-Object System.Drawing.Size(120, 30)
$BtnRun.BackColor = [System.Drawing.Color]::LightGreen
$Form.Controls.Add($BtnRun)

$BtnRun.Add_Click({
    $Src = $TxtSrc.Text
    $Dest = $TxtDest.Text

    if (-not (Test-Path $Src) -or -not (Test-Path $Dest)) {
        [System.Windows.Forms.MessageBox]::Show("Please select valid folders.", "Error")
        return
    }

    $Files = Get-ChildItem -Path $Src -File -Recurse | Where-Object { -not $_.Name.StartsWith(".") }
    $Total = $Files.Count

    if ($Total -eq 0) {
        [System.Windows.Forms.MessageBox]::Show("No files found to organize.")
        return
    }

    $ProgressBar.Maximum = $Total
    $ProgressBar.Value = 0

    foreach ($File in $Files) {
        $StatusLabel.Text = "Moving: $($File.Name)"
        $Form.Refresh() # Forces UI to update

        $Created = $File.CreationTime
        $TargetFolder = Join-Path $Dest -ChildPath ($Created.ToString("yyyy") + "\" + $Created.ToString("MM-MMMM"))

        if (-not (Test-Path $TargetFolder)) {
            New-Item -ItemType Directory -Path $TargetFolder -Force | Out-Null
        }

        Move-Item -Path $File.FullName -Destination $TargetFolder -Force
        $ProgressBar.Value++
    }

    $StatusLabel.Text = "Finished!"
    [System.Windows.Forms.MessageBox]::Show("Successfully organized $Total files!", "Done")
})

$Form.ShowDialog()
if (-not (Test-Path -Path $DestDir)) {
    New-Item -ItemType Directory -Path $DestDir -Force | Out-Null
}

# Get all files (excluding hidden files starting with '.')
$Files = Get-ChildItem -Path $SourceDir -File -Recurse | Where-Object { -not $_.Name.StartsWith(".") }
$Total = $Files.Count
$Count = 0

if ($Total -eq 0) {
    Write-Host "ℹ️ No files found to organize."
    exit
}

foreach ($File in $Files) {
    $Count++

    # Get Creation Date
    $Created = $File.CreationTime
    $Year = $Created.ToString("yyyy")
    $Month = $Created.ToString("MM-MMMM") # Example: 05-May

    # Define and create target path
    $TargetFolder = Join-Path $DestDir -ChildPath "$Year\$Month"
    if (-not (Test-Path $TargetFolder)) {
        New-Item -ItemType Directory -Path $TargetFolder -Force | Out-Null
    }

    # Move file
    Move-Item -Path $File.FullName -Destination $TargetFolder -Force

    # Progress Bar (Native PowerShell style)
    $Percent = ($Count / $Total) * 100
    Write-Progress -Activity "Organizing Files" -Status "Moving $($File.Name)" -PercentComplete $Percent
}

Write-Host "`n✅ Done organizing $Total files." -ForegroundColor Green