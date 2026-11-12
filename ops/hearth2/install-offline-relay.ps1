param([string]$SourceRoot = $PSScriptRoot)
$ErrorActionPreference = 'Stop'
if ($env:COMPUTERNAME -ne 'RSLABINSKI-PC') { throw 'Exact approved laptop required' }
if ((Get-TimeZone).Id -ne 'Eastern Standard Time') { throw 'Approved ET timezone required' }
$taskName = 'Hearth-Codex-Offline-Relay'
if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) { throw 'Preserve existing task; installation refused' }
$root = [IO.Path]::GetFullPath((Join-Path $env:LOCALAPPDATA 'Hearth\OfflineRelay'))
$expected = [IO.Path]::GetFullPath((Join-Path $env:LOCALAPPDATA 'Hearth\OfflineRelay'))
if ($root -ne $expected -or (Test-Path -LiteralPath $root)) { throw 'New private target required; preserve existing state' }
$desktop = [Environment]::GetFolderPath('Desktop')
$link = Join-Path $desktop 'Pause Hearth relay.lnk'
if (Test-Path -LiteralPath $link) { throw 'Preserve existing pause shortcut' }
$program = Join-Path $root 'program'
New-Item -ItemType Directory -Path $program -Force | Out-Null
$sid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
& icacls.exe $root /inheritance:r /grant:r "*${sid}:(OI)(CI)F" '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-544:(OI)(CI)F' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Private controller ACL unavailable' }
$files = @('offline_relay.py','offline_relay_state.py','offline_relay_ports.py','offline_relay_windows.py','pause-offline-relay.ps1')
$hashes = @{}
foreach ($name in $files) {
    $source = Join-Path $SourceRoot $name
    if ((Get-Item -LiteralPath $source).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Source link refused' }
    $target = Join-Path $program $name
    Copy-Item -LiteralPath $source -Destination $target
    $hashes[$name] = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant()
    (Get-Item -LiteralPath $target).IsReadOnly = $true
}
$python = (Get-Command python.exe -ErrorAction Stop).Source
$state = Join-Path $root 'relay.sqlite3'
$manifest = @{host=$env:COMPUTERNAME; model=(Get-CimInstance Win32_ComputerSystem).Model; task=$taskName;
    program=$program; state=$state; python=$python; source_hashes=$hashes; installed_disabled=$true;
    live_coordination='unavailable'; included_allowance='unverified'; unattended_launcher='unverified'}
$manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $root 'manifest.json') -Encoding UTF8
& $python -I (Join-Path $program 'offline_relay.py') status --state $state | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Paused state initialization failed' }
$action = New-ScheduledTaskAction -Execute $python -Argument ('-I "'+(Join-Path $program 'offline_relay.py')+'" check --state "'+$state+'"') -WorkingDirectory $program
$triggers = @(7..23 | ForEach-Object { New-ScheduledTaskTrigger -Daily -At ([datetime]::Today.AddHours($_)) })
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 10)
$settings.Enabled = $false
$settings.StartWhenAvailable = $false
$settings.WakeToRun = $false
$principal = New-ScheduledTaskPrincipal -UserId $sid -LogonType Interactive -RunLevel Limited
$definition = New-ScheduledTask -Action $action -Trigger $triggers -Settings $settings -Principal $principal -Description 'Hearth offline relay disabled candidate'
Register-ScheduledTask -TaskName $taskName -TaskPath '\' -InputObject $definition | Out-Null
$readback = Get-ScheduledTask -TaskName $taskName
if ($readback.Settings.Enabled -or [string]$readback.State -ne 'Disabled') { throw 'Disabled registration not verified' }
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($link)
$shortcut.TargetPath = $python
$shortcut.Arguments = '-I "'+(Join-Path $program 'offline_relay.py')+'" pause --state "'+$state+'"'
$shortcut.WorkingDirectory = $program
$shortcut.Description = 'Pause Hearth relay: latch paused, disable exact task and stop verified active work'
$shortcut.WindowStyle = 7
$shortcut.Save()
@{task=$taskName;state=[string]$readback.State;enabled=$readback.Settings.Enabled;root=$root;pause_action=$link;
    last_run=(Get-ScheduledTaskInfo -TaskName $taskName).LastRunTime.ToString('o')} | ConvertTo-Json -Compress
