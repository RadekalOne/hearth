param([switch]$SmokeTest)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()
$script:job = $null
$script:action = ''
$script:checked = $false
$form = New-Object System.Windows.Forms.Form
$form.Text = 'Install Hearth (Preview 3)'
$form.ClientSize = New-Object System.Drawing.Size(640, 705)
$form.StartPosition = 'CenterScreen'
$form.FormBorderStyle = 'FixedDialog'
$form.MaximizeBox = $false
$form.Font = New-Object System.Drawing.Font('Segoe UI', 10)

function Label($text, $x, $y, $width, $height) {
    $control = New-Object System.Windows.Forms.Label
    $control.Text = $text
    $control.SetBounds($x, $y, $width, $height)
    $form.Controls.Add($control)
    return $control
}
function Button($text, $x, $y, $width) {
    $control = New-Object System.Windows.Forms.Button
    $control.Text = $text
    $control.SetBounds($x, $y, $width, 36)
    $form.Controls.Add($control)
    return $control
}
function TextBox($x, $y, $secret) {
    $control = New-Object System.Windows.Forms.TextBox
    $control.SetBounds($x, $y, 355, 28)
    $control.UseSystemPasswordChar = $secret
    $form.Controls.Add($control)
    return $control
}
$heading = Label 'Your own place for people and AI agents' 24 20 590 35
$heading.Font = New-Object System.Drawing.Font('Segoe UI', 16, [System.Drawing.FontStyle]::Bold)
$null = Label "Hearth stores chat and memory on this PC. Keep Docker Desktop running while using Hearth. After setup, connect an OpenRouter test agent below." 24 67 590 65
$null = Label '1. Prepare your computer' 24 140 590 25
$null = Label 'Install Node.js (LTS) and Docker Desktop using their normal installers. Open Docker Desktop and wait for it to finish starting. Restart Windows if requested, then reopen this wizard.' 24 168 590 65
$nodeLink = Button 'Get Node.js' 24 235 150
$dockerLink = Button 'Get Docker Desktop' 184 235 180
$check = Button 'Check again' 380 235 210
$nodeLink.Add_Click({ Start-Process 'https://nodejs.org/en/download' })
$dockerLink.Add_Click({ Start-Process 'https://www.docker.com/products/docker-desktop/' })
$null = Label '2. Choose your Hearth login' 24 288 590 25
$null = Label 'Login name' 24 325 160 25
$username = TextBox 200 322 $false
$username.Text = 'admin'
$null = Label 'Password (12+ characters)' 24 368 175 40
$password = TextBox 200 365 $true
$null = Label 'Repeat password' 24 411 170 25
$confirm = TextBox 200 408 $true
$install = Button 'Install Hearth' 24 454 175
$install.Enabled = $false
$progress = New-Object System.Windows.Forms.ProgressBar
$progress.SetBounds(215, 461, 375, 20)
$form.Controls.Add($progress)
$status = Label 'Click Check again to check this computer. No changes are made by the check.' 24 505 590 74
$folder = Label ('Files: ' + (Join-Path $env:LOCALAPPDATA 'Hearth\hub')) 24 574 590 20
$folder.AutoEllipsis = $true
$chat = Button 'Open chat' 24 592 130
$dashboard = Button 'Open dashboard' 164 592 155
$guide = Button 'Setup guide' 329 592 125
$key = Button 'Copy admin key' 464 592 152
$key.Enabled = $false
$agent = Button '3. Connect OpenRouter' 24 646 270
$agent.Add_Click({
    Start-Process powershell.exe -WindowStyle Hidden -ArgumentList ('-NoProfile -ExecutionPolicy Bypass -STA -File "' + (Join-Path $PSScriptRoot 'Connect-OpenRouter.ps1') + '"')
})
$chat.Enabled = $false
$dashboard.Enabled = $false
$chat.Add_Click({ Start-Process 'http://localhost:8009' })
$dashboard.Add_Click({ Start-Process 'http://localhost:8010' })
$guide.Add_Click({ Start-Process (Join-Path $PSScriptRoot '..\..\docs\WINDOWS-INSTALL.md') })
$key.Add_Click({
    try {
        $line = Get-Content -LiteralPath (Join-Path $env:LOCALAPPDATA 'Hearth\hub\.env') | Where-Object { $_ -match '^HEARTH_MEMORY_ADMIN_TOKEN=.+$' } | Select-Object -First 1
        if (-not $line) { throw 'Dashboard key not found. Retry setup or ask for help.' }
        [System.Windows.Forms.Clipboard]::SetText($line.Substring($line.IndexOf('=') + 1))
        $status.Text = 'Admin key copied. Open the dashboard and paste it into the login box. This key grants administrator access; keep it private.'
    } catch { $status.Text = $_.Exception.Message }
})

function Start-Setup($action) {
    try {
        # Refresh PATH so prerequisites installed with this window open are found.
        $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')
        $node = Get-Command node.exe -ErrorAction SilentlyContinue
        if (-not $node) { throw 'Node.js is missing. Click Get Node.js, install the LTS version, then click Check again.' }
        if ($action -eq 'install') {
            if ($password.Text -cne $confirm.Text) { throw 'The passwords do not match. Please type them again.' }
            if ($password.Text.Length -lt 12) { throw 'Choose a password with at least 12 characters.' }
        }
        $payload = @{ action = $action }
        if ($action -eq 'install') { $payload.username = $username.Text; $payload.password = $password.Text }
        $info = New-Object System.Diagnostics.ProcessStartInfo
        $info.FileName = $node.Source
        $info.Arguments = '"' + (Join-Path $PSScriptRoot 'runner.mjs') + '"'
        $info.UseShellExecute = $false
        $info.CreateNoWindow = $true
        $info.RedirectStandardInput = $true
        $info.RedirectStandardOutput = $true
        $info.RedirectStandardError = $true
        $info.StandardOutputEncoding = [System.Text.Encoding]::UTF8
        $info.StandardErrorEncoding = [System.Text.Encoding]::UTF8
        $script:job = New-Object System.Diagnostics.Process
        $script:job.StartInfo = $info
        $null = $script:job.Start()
        $script:output = $script:job.StandardOutput.ReadToEndAsync()
        $script:errors = $script:job.StandardError.ReadToEndAsync()
        # Write UTF-8 directly: Windows PowerShell 5.1 has no StandardInputEncoding.
        $bytes = [System.Text.Encoding]::UTF8.GetBytes(($payload | ConvertTo-Json -Compress))
        $script:job.StandardInput.BaseStream.Write($bytes, 0, $bytes.Length)
        $script:job.StandardInput.BaseStream.Flush()
        $script:job.StandardInput.Close()
        $payload.Clear()
        $script:action = $action
        $check.Enabled = $false
        $install.Enabled = $false
        $username.Enabled = $false
        $password.Enabled = $false
        $confirm.Enabled = $false
        $progress.Style = 'Marquee'
        $status.Text = if ($action -eq 'check') { 'Checking this computer...' } else { 'Installing Hearth. The first download and startup can take several minutes. Please keep this window open.' }
        $timer.Start()
    } catch { $status.Text = $_.Exception.Message }
}
$timer = New-Object System.Windows.Forms.Timer
$timer.Interval = 300
$timer.Add_Tick({
    if (-not $script:job.HasExited -or -not $script:output.IsCompleted -or -not $script:errors.IsCompleted) { return }
    $timer.Stop()
    $progress.Style = 'Blocks'
    $check.Enabled = $true
    $username.Enabled = $true
    $password.Enabled = $true
    $confirm.Enabled = $true
    try {
        $result = $script:output.Result | ConvertFrom-Json
        if (-not $result.message) { throw 'No setup result.' }
        $status.Text = $result.message
        $script:checked = [bool]$result.ok
        $install.Enabled = $script:checked
        if ($script:action -eq 'install' -and $result.ok) {
            $password.Clear()
            $confirm.Clear()
            $install.Enabled = $false
            $chat.Enabled = $true
            $dashboard.Enabled = $true
            $key.Enabled = $true
            $progress.Value = 100
        }
    } catch {
        $status.Text = 'The setup helper could not finish. Install the current Node.js LTS version and reopen this wizard. Your existing Hearth data is kept.'
        $install.Enabled = $false
    } finally {
        $script:job.Dispose()
        $script:job = $null
    }
})
$check.Add_Click({ Start-Setup 'check' })
$install.Add_Click({ Start-Setup 'install' })
$form.Add_FormClosing({
    param($sender, $event)
    if ($script:job) {
        $event.Cancel = $true
        $status.Text = 'Please wait for the current check or installation to finish before closing this window.'
    }
})
try {
    if ($SmokeTest) {
        Start-Setup 'check'
        while ($script:job) { [System.Windows.Forms.Application]::DoEvents(); Start-Sleep -Milliseconds 50 }
        Write-Output $status.Text
    } else { $null = $form.ShowDialog() }
} finally { $timer.Dispose(); $form.Dispose() }
