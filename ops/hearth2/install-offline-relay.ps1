param([string]$SourceRoot = $PSScriptRoot, [switch]$UpdateDisabled)
$ErrorActionPreference = 'Stop'
if ($env:COMPUTERNAME -ne 'RSLABINSKI-PC') { throw 'Exact approved laptop required' }
if ((Get-TimeZone).Id -ne 'Eastern Standard Time') { throw 'Approved ET timezone required' }
$taskName = 'Hearth-Codex-Offline-Relay'
$python = 'C:\Python314\python.exe'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw 'Approved interpreter unavailable' }
$root = [IO.Path]::GetFullPath((Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'Hearth\OfflineRelay'))
$program = Join-Path $root 'program'
$recovery = Join-Path $root 'recovery'
$state = Join-Path $root 'relay.sqlite3'
$link = Join-Path ([Environment]::GetFolderPath('Desktop')) 'Pause Hearth relay.lnk'
$actionArguments = '-I "'+(Join-Path $program 'offline_relay.py')+'" check --state "'+$state+'"'
foreach($path in @((Split-Path $root),$root,$program,$recovery,$state)) {
    if((Test-Path -LiteralPath $path) -and ((Get-Item -LiteralPath $path).Attributes -band [IO.FileAttributes]::ReparsePoint)){throw 'Installation links refused'}
}
$existing = Get-ScheduledTask -TaskName $taskName -TaskPath '\' -ErrorAction SilentlyContinue
if ($UpdateDisabled) {
    if (-not $existing -or $existing.Settings.Enabled -or [string]$existing.State -ne 'Disabled' -or
        $existing.Description -ne 'Hearth offline relay disabled candidate' -or @($existing.Actions).Count -ne 1 -or
        $existing.Actions[0].Execute -ne $python -or $existing.Actions[0].Arguments -ne $actionArguments -or
        $existing.Actions[0].WorkingDirectory -ne $program) { throw 'Exact owned disabled installation required' }
    & $python -I -c 'import sqlite3,sys;from pathlib import Path;p=Path(sys.argv[1]);d=sqlite3.connect(p.as_uri()+"?mode=ro",uri=True);assert d.execute("SELECT paused,enabled FROM control WHERE id=1").fetchone()==(1,0);assert d.execute("SELECT count(*) FROM jobs WHERE state IN (''claimed'',''dispatching'',''active'',''held'')").fetchone()[0]==0;d.close()' $state
    if ($LASTEXITCODE -ne 0) { throw 'Paused state without active workloads required for refresh' }
    if (-not (Test-Path -LiteralPath $link)) { throw 'Existing pause shortcut required for refresh' }
    $oldShortcut=(New-Object -ComObject WScript.Shell).CreateShortcut($link)
    $legacyArguments='-I "'+(Join-Path $program 'offline_relay.py')+'" pause --state "'+$state+'"'
    $recoveryArguments='-I "'+(Join-Path $recovery 'offline_relay_pause.py')+'"'
    if($oldShortcut.TargetPath -ne $python -or $oldShortcut.Arguments -notin @($legacyArguments,$recoveryArguments)) { throw 'Preserve unrelated pause shortcut' }
    $history=Join-Path $root ('history\'+[DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ'))
    New-Item -ItemType Directory -Path $history | Out-Null
    foreach($dir in @($program,$recovery)) {
        if(Test-Path -LiteralPath $dir){
            $backup=Join-Path $history (Split-Path $dir -Leaf);New-Item -ItemType Directory -Path $backup | Out-Null
            foreach($name in @('offline_relay.py','offline_relay_state.py','offline_relay_ports.py','offline_relay_windows.py','pause-offline-relay.ps1','offline_relay_pause.py')) {
                $item=Join-Path $dir $name
                if(Test-Path -LiteralPath $item){
                    if((Get-Item -LiteralPath $item).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Backup link refused'}
                    Copy-Item -LiteralPath $item -Destination $backup
                }
            }
        }
    }
    Copy-Item -LiteralPath (Join-Path $root 'manifest.json') -Destination $history
    Copy-Item -LiteralPath $link -Destination $history
} else {
    if ($existing -or (Test-Path -LiteralPath $root) -or (Test-Path -LiteralPath $link)) { throw 'Preserve existing task/state/pause shortcut; use explicit disabled refresh only for owned installation' }
    New-Item -ItemType Directory -Path $root | Out-Null
    $sid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    & icacls.exe $root /inheritance:r /grant:r "*${sid}:(OI)(CI)F" '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-544:(OI)(CI)F' | Out-Null
    if($LASTEXITCODE -ne 0){throw 'Private controller ACL unavailable'}
}
foreach($dir in @($root,$program,$recovery)) {
    if(Test-Path -LiteralPath $dir){
        if((Get-Item -LiteralPath $dir).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Installation links refused'}
    } else {New-Item -ItemType Directory -Path $dir | Out-Null}
}
$hashes=@{};$recoveryHashes=@{}
$files=@('offline_relay.py','offline_relay_state.py','offline_relay_ports.py','offline_relay_windows.py','pause-offline-relay.ps1','offline_relay_pause.py')
foreach($name in $files) {
    $source=Join-Path $SourceRoot $name
    if((Get-Item -LiteralPath $source).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Source link refused'}
    $target=Join-Path $(if($name -eq 'offline_relay_pause.py'){$recovery}else{$program}) $name
    if(Test-Path -LiteralPath $target){
        if((Get-Item -LiteralPath $target).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Target link refused'}
        (Get-Item -LiteralPath $target).IsReadOnly=$false
    }
    # Canonical LF bytes match Git blob evidence even with autocrlf checkouts.
    $bytes=[IO.File]::ReadAllText($source).Replace("`r`n","`n")
    [IO.File]::WriteAllText($target,$bytes,(New-Object Text.UTF8Encoding($false)))
    $hash=(Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant()
    if($name -eq 'offline_relay_pause.py'){$recoveryHashes[$name]=$hash}else{$hashes[$name]=$hash}
    (Get-Item -LiteralPath $target).IsReadOnly=$true
}
$manifest=@{host=$env:COMPUTERNAME;model=(Get-CimInstance Win32_ComputerSystem).Model;task=$taskName;
    program=$program;state=$state;python=$python;source_hashes=$hashes;recovery_hashes=$recoveryHashes;installed_disabled=$true;
    live_coordination='unavailable';included_allowance='unverified';unattended_launcher='unverified'}
$manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $root 'manifest.json') -Encoding UTF8
& $python -I (Join-Path $program 'offline_relay.py') status --state $state | Out-Null
if($LASTEXITCODE -ne 0){throw 'Paused state verification failed'}
if(-not $UpdateDisabled) {
    $action=New-ScheduledTaskAction -Execute $python -Argument $actionArguments -WorkingDirectory $program
    $triggers=@(7..23 | ForEach-Object {New-ScheduledTaskTrigger -Daily -At ([datetime]::Today.AddHours($_))})
    $settings=New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 10)
    $settings.Enabled=$false;$settings.StartWhenAvailable=$false;$settings.WakeToRun=$false
    $sid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    $principal=New-ScheduledTaskPrincipal -UserId $sid -LogonType Interactive -RunLevel Limited
    Register-ScheduledTask -TaskName $taskName -TaskPath '\' -InputObject (New-ScheduledTask -Action $action -Trigger $triggers -Settings $settings -Principal $principal -Description 'Hearth offline relay disabled candidate') | Out-Null
}
$readback=Get-ScheduledTask -TaskName $taskName -TaskPath '\'
if($readback.Settings.Enabled -or [string]$readback.State -ne 'Disabled'){throw 'Disabled state not verified'}
$shortcut=(New-Object -ComObject WScript.Shell).CreateShortcut($link)
$shortcut.TargetPath=$python;$shortcut.Arguments='-I "'+(Join-Path $recovery 'offline_relay_pause.py')+'"'
$shortcut.WorkingDirectory=$recovery;$shortcut.Description='Pause Hearth relay: independent latch, recorded workload stop (bounded trial SSH if needed), exact task disable';$shortcut.WindowStyle=7;$shortcut.Save()
@{task=$taskName;state=[string]$readback.State;enabled=$readback.Settings.Enabled;root=$root;pause_action=$link;
    refreshed=[bool]$UpdateDisabled;last_run=(Get-ScheduledTaskInfo -TaskName $taskName -TaskPath '\').LastRunTime.ToString('o')} | ConvertTo-Json -Compress
