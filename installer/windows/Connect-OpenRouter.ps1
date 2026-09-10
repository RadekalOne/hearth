param([switch]$SmokeTest, [string]$RenderPath)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()
$script:job = $null
$script:tested = $false
$script:roomUrl = $null
$form = New-Object System.Windows.Forms.Form
$form.Text = 'Hearth - Connect OpenRouter'
$form.ClientSize = New-Object System.Drawing.Size(650, 710)
$form.StartPosition = 'CenterScreen'
$form.FormBorderStyle = 'FixedDialog'
$form.MaximizeBox = $false
$form.Font = New-Object System.Drawing.Font('Segoe UI', 10)
function Label($text, $x, $y, $width, $height) {
    $c = New-Object System.Windows.Forms.Label
    $c.Text = $text; $c.SetBounds($x, $y, $width, $height); $form.Controls.Add($c); return $c
}
function Button($text, $x, $y, $width) {
    $c = New-Object System.Windows.Forms.Button
    $c.Text = $text; $c.SetBounds($x, $y, $width, 36); $form.Controls.Add($c); return $c
}
function Field($y, $secret) {
    $c = New-Object System.Windows.Forms.TextBox
    $c.SetBounds(185, $y, 430, 28); $c.UseSystemPasswordChar = $secret; $form.Controls.Add($c); return $c
}
$heading = Label 'Try your first OpenRouter agent' 24 20 600 34
$heading.Font = New-Object System.Drawing.Font('Segoe UI', 17, [System.Drawing.FontStyle]::Bold)
$null = Label 'Install Hearth first. This preview adds one agent to a private test room. Each reply uses only the message you send; shared memory and computer tools are not enabled.' 24 68 600 65
$null = Label '1. Get a key with a small spending limit' 24 142 600 26
$null = Label 'Create an OpenRouter API key with a limit of $5 or less. Add credit if needed. Test reply sends one short request and may use credit. Keep your key private.' 24 173 600 52
$getKey = Button 'Open OpenRouter keys' 24 231 230
$getKey.Add_Click({ Start-Process 'https://openrouter.ai/settings/keys' })
$null = Label 'API key' 24 285 150 25
$apiKey = Field 282 $true
$null = Label '2. Choose your agent' 24 325 600 25
$null = Label 'Agent name' 24 361 150 25
$name = Field 358 $false
$name.Text = 'helper'
$null = Label 'Model' 24 403 145 25
$model = New-Object System.Windows.Forms.ComboBox
$model.SetBounds(185, 400, 430, 28)
$model.DropDownStyle = 'DropDown'
$model.AutoCompleteMode = 'SuggestAppend'
$model.AutoCompleteSource = 'ListItems'
$form.Controls.Add($model)
$load = Button 'Load models' 24 440 145
$null = Label 'Choose from the list, or paste a provider/model ID. Private routing may not be available for every model.' 185 440 430 46
$consent = New-Object System.Windows.Forms.CheckBox
$consent.Text = 'Send messages I direct at this agent to OpenRouter and its model provider. Use private routing; stop if unavailable.'
$consent.SetBounds(24, 493, 600, 48)
$form.Controls.Add($consent)
$test = Button 'Test reply' 24 550 135
$connect = Button 'Start agent' 172 550 135
$connect.Enabled = $false
$stop = Button 'Stop agent' 320 550 135
$open = Button 'Open test room' 468 550 157
$open.Enabled = $false
$status = Label 'Load models, enter your key, then click Test reply.' 24 605 600 72
$progress = New-Object System.Windows.Forms.ProgressBar
$progress.SetBounds(24, 684, 600, 10)
$form.Controls.Add($progress)
$inputs = @($apiKey, $name, $model, $consent, $load, $test, $connect, $stop)
function Reset-Test { $script:tested = $false; $connect.Enabled = $false }
$apiKey.Add_TextChanged({ Reset-Test })
$name.Add_TextChanged({ Reset-Test })
$model.Add_TextChanged({ Reset-Test })
$consent.Add_CheckedChanged({ Reset-Test })
function Start-Action($action) {
    try {
        $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')
        $node = Get-Command node.exe -ErrorAction SilentlyContinue
        if (-not $node) { throw 'Install Node.js using Install Hearth, then reopen this window.' }
        if ($action -in @('test', 'connect') -and -not $consent.Checked) { throw 'Check the message-sharing box before testing or starting your agent.' }
        if ($action -eq 'connect' -and -not $script:tested) { throw 'Use Test reply with these settings first.' }
        $payload = @{ action = $action }
        if ($action -in @('test', 'connect')) {
            $payload.name = $name.Text.Trim()
            $payload.model = $model.Text.Trim()
            $payload.key = $apiKey.Text.Trim()
            $payload.consent = $consent.Checked
        }
        $info = New-Object System.Diagnostics.ProcessStartInfo
        $info.FileName = $node.Source
        $info.Arguments = '"' + (Join-Path $PSScriptRoot 'openrouter.mjs') + '"'
        $info.UseShellExecute = $false; $info.CreateNoWindow = $true
        $info.RedirectStandardInput = $true; $info.RedirectStandardOutput = $true; $info.RedirectStandardError = $true
        $info.StandardOutputEncoding = [Text.Encoding]::UTF8
        $info.StandardErrorEncoding = [Text.Encoding]::UTF8
        $script:job = New-Object System.Diagnostics.Process
        $script:job.StartInfo = $info
        $null = $script:job.Start()
        $script:output = $script:job.StandardOutput.ReadToEndAsync()
        $script:errors = $script:job.StandardError.ReadToEndAsync()
        $bytes = [Text.Encoding]::UTF8.GetBytes(($payload | ConvertTo-Json -Compress))
        $script:job.StandardInput.BaseStream.Write($bytes, 0, $bytes.Length)
        $script:job.StandardInput.BaseStream.Flush(); $script:job.StandardInput.Close()
        $payload.Clear(); [Array]::Clear($bytes, 0, $bytes.Length)
        $script:action = $action
        foreach ($control in $inputs) { $control.Enabled = $false }
        $progress.Style = 'Marquee'
        $status.Text = switch ($action) {
            'models' { 'Loading the current OpenRouter model list...' }
            'test' { 'Checking your key limit and requesting one short test reply...' }
            'connect' { 'Creating your private test room and starting the agent. The first download can take a few minutes...' }
            'stop' { 'Stopping the agent...' }
        }
        $timer.Start()
    } catch { $status.Text = $_.Exception.Message }
}
$timer = New-Object System.Windows.Forms.Timer
$timer.Interval = 250
$timer.Add_Tick({
    if (-not $script:job.HasExited -or -not $script:output.IsCompleted -or -not $script:errors.IsCompleted) { return }
    $timer.Stop(); $progress.Style = 'Blocks'
    foreach ($control in $inputs) { $control.Enabled = $true }
    try {
        $result = $script:output.Result | ConvertFrom-Json
        if (-not $result.message) { throw 'No result from helper.' }
        $status.Text = $result.message
        if ($script:action -eq 'models' -and $result.ok) {
            $previous = $model.Text
            $model.Items.Clear()
            foreach ($item in $result.models) { $null = $model.Items.Add($item.id) }
            $model.Text = $previous
        }
        if ($script:action -eq 'test') { $script:tested = [bool]$result.ok }
        if ($script:action -eq 'connect' -and $result.ok) {
            $script:roomUrl = $result.roomUrl
            $open.Enabled = $true
            $apiKey.Clear()
        }
        if ($script:action -eq 'stop' -and $result.ok) { $script:tested = $false }
    } catch { $status.Text = 'The helper did not finish. Reopen this window and retry. Do not share your API key when asking for help.' }
    finally {
        $connect.Enabled = $script:tested
        $script:job.Dispose(); $script:job = $null
    }
})
$load.Add_Click({ Start-Action 'models' })
$test.Add_Click({ Start-Action 'test' })
$connect.Add_Click({ Start-Action 'connect' })
$stop.Add_Click({ Start-Action 'stop' })
$open.Add_Click({ if ($script:roomUrl) { Start-Process $script:roomUrl } })
$form.Add_FormClosing({ param($sender, $event)
    if ($script:job) { $event.Cancel = $true; $status.Text = 'Please wait for the current action to finish before closing this window.' }
})
try {
    if ($RenderPath) {
        $form.Show(); [Windows.Forms.Application]::DoEvents()
        $bitmap = New-Object Drawing.Bitmap($form.Width, $form.Height)
        $form.DrawToBitmap($bitmap, (New-Object Drawing.Rectangle(0, 0, $form.Width, $form.Height)))
        $bitmap.Save($RenderPath); $bitmap.Dispose(); $form.Hide()
    } elseif ($SmokeTest) { Write-Output ('OpenRouter wizard initialized: ' + $form.Controls.Count + ' controls; start disabled=' + (-not $connect.Enabled)) }
    else { $null = $form.ShowDialog() }
} finally { $timer.Dispose(); $form.Dispose() }
