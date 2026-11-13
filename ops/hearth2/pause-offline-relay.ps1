$ErrorActionPreference = 'Stop'
if ([Environment]::MachineName -ne 'RSLABINSKI-PC') { throw 'Exact approved laptop required' }
# Recovery has no dependency on this program directory, the staged manifest or LOCALAPPDATA.
$root=Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'Hearth\OfflineRelay'
& 'C:\Python314\python.exe' -I (Join-Path $root 'recovery\offline_relay_pause.py')
exit $LASTEXITCODE
