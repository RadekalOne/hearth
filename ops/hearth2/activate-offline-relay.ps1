param([string]$ClaudeReviewEvent='')
# Explicit local activation of intake/capacity ONLY. No model send authority.
$ErrorActionPreference='Stop'
if(-not $ClaudeReviewEvent.StartsWith('$') -or $ClaudeReviewEvent.Length -gt 200){throw 'Claude review of exact installed evidence is required before enablement'}
if($env:COMPUTERNAME -ne 'RSLABINSKI-PC' -or (Get-TimeZone).Id -ne 'Eastern Standard Time'){throw 'Approved host/timezone required'}
$root=Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'Hearth\OfflineRelay'
$python='C:\Python314\python.exe';$program=Join-Path $root 'program';$state=Join-Path $root 'relay.sqlite3'
$task=Get-ScheduledTask -TaskName 'Hearth-Codex-Offline-Relay' -TaskPath '\' -ErrorAction Stop
$expected='-I "'+(Join-Path $program 'offline_relay.py')+'" check --state "'+$state+'"'
if($task.Settings.Enabled -or [string]$task.State -ne 'Disabled' -or $task.Description -ne 'Hearth offline relay disabled candidate' -or
 @($task.Actions).Count -ne 1 -or $task.Actions[0].Execute -ne $python -or $task.Actions[0].Arguments -ne $expected -or
 $task.Actions[0].WorkingDirectory -ne $program){throw 'Exact disabled owned task required'}
$status=& $python -I (Join-Path $program 'offline_relay.py') status --state $state
if($LASTEXITCODE -ne 0){throw 'Installed source integrity check failed'}
$c=$status|ConvertFrom-Json
if($c.control.paused -ne 1 -or $c.control.enabled -ne 0 -or @($c.jobs|Where-Object {$_.state -in @('claimed','dispatching','active','held')}).Count -ne 0 -or
 @($c.outbox|Where-Object {$_.state -ne 'sent'}).Count -ne 0){throw 'Paused state without active work or unresolved posts required'}
$reviewCheck=@'
import sys,hashlib
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from relay_live import load_configuration,verify_activation_review
from relay_matrix import MatrixClient
root=Path(sys.argv[2]);c=load_configuration(root)
verify_activation_review(MatrixClient.from_env_file(c['matrix_env']),sys.argv[3],hashlib.sha256((root/'manifest.json').read_bytes()).hexdigest())
'@
& $python -I -c $reviewCheck $program $root $ClaudeReviewEvent
if($LASTEXITCODE -ne 0){throw 'Authenticated Claude review of exact installed manifest/mode is not verified'}
$diagnostic=& $python -I (Join-Path $program 'offline_relay.py') diagnose --state $state
if($LASTEXITCODE -ne 0){throw 'Live read-only preflight failed'}
$d=$diagnostic|ConvertFrom-Json
if($d.mode -ne 'intake_capacity_only' -or -not $d.intake_complete -or -not $d.native_complete -or $d.model_turns -ne 0 -or $d.inference_authorized){throw 'Verified intake/capacity-only preflight required'}
# Keep the complete SQLite audit before activation; never remove fixture history.
$backup=Join-Path $root ('pre-activation-'+[DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ')+'.sqlite3')
& $python -I -c 'import sqlite3,sys;s=sqlite3.connect(sys.argv[1]);d=sqlite3.connect(sys.argv[2]);s.backup(d);d.close();s.close()' $state $backup
if($LASTEXITCODE -ne 0){throw 'Pre-activation SQLite backup failed'}
# Enabling the exact task while the latch is still set cannot admit work.
Enable-ScheduledTask -InputObject $task | Out-Null
try {
 & $python -I -c 'import sqlite3,sys,datetime;d=sqlite3.connect(sys.argv[1]);d.execute("BEGIN IMMEDIATE");c=d.execute("SELECT paused,enabled,epoch FROM control WHERE id=1").fetchone();assert c==(1,0,int(sys.argv[2]));assert d.execute("SELECT count(*) FROM jobs WHERE state IN (''claimed'',''dispatching'',''active'',''held'')").fetchone()[0]==0;d.execute("UPDATE control SET paused=0,enabled=1,epoch=epoch+1,status=''enabled_inference_gated'',activation_at=? WHERE id=1",(datetime.datetime.now(datetime.timezone.utc).isoformat(),));d.commit();d.close()' $state $c.control.epoch
 if($LASTEXITCODE -ne 0){throw 'Activation epoch changed or local latch could not be updated'}
} catch {Disable-ScheduledTask -InputObject $task|Out-Null;throw}
$readback=Get-ScheduledTask -TaskName 'Hearth-Codex-Offline-Relay' -TaskPath '\'
if(-not $readback.Settings.Enabled){throw 'Task enable readback failed; inspect local latch'}
@{enabled=$true;mode='intake_capacity_only';model_dispatch='blocked';paid_approval='required';financial_route='unverified';backup=$backup;next_run_is_not_execution_proof=$true}|ConvertTo-Json -Compress
