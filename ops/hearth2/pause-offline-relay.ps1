$ErrorActionPreference = 'Stop'
if ($env:COMPUTERNAME -ne 'RSLABINSKI-PC') { throw 'Exact approved laptop required' }
$root = Join-Path $env:LOCALAPPDATA 'Hearth\OfflineRelay'
$manifest = Get-Content -LiteralPath (Join-Path $root 'manifest.json') -Raw | ConvertFrom-Json
if ($manifest.host -ne $env:COMPUTERNAME -or $manifest.task -ne 'Hearth-Codex-Offline-Relay') { throw 'Controller binding mismatch' }
& $manifest.python -I (Join-Path $root 'program\offline_relay.py') pause --state (Join-Path $root 'relay.sqlite3')
exit $LASTEXITCODE
