$ErrorActionPreference = 'Stop'
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$stage = Join-Path ([IO.Path]::GetTempPath()) ('hearth-setup-' + [guid]::NewGuid().ToString('N'))
$null = New-Item -ItemType Directory -Path $stage
# Include current edits through an explicit public-file list for preview builds.
$files = @('Install Hearth.cmd', 'installer/windows/Install-Hearth.ps1', 'installer/windows/runner.mjs',
    'Connect OpenRouter.cmd', 'installer/windows/Connect-OpenRouter.ps1', 'installer/windows/openrouter.mjs',
    'integrations/openrouter/agent.mjs', 'integrations/openrouter/compose.yml',
    '.env.example', 'docker-compose.yml', 'docker-compose.expose.yml', 'docker-compose.expose-memory.yml',
    'LICENSE', 'README.md', 'PROJECT.md', 'mcp/matrix/index.mjs', 'mcp/matrix/package.json',
    'mcp/matrix/package-lock.json', 'mcp/memory/app.py', 'mcp/memory/Dockerfile', 'mcp/memory/requirements.txt')
$files += Get-ChildItem (Join-Path $repo 'cli') -File -Filter '*.mjs' | ForEach-Object { 'cli/' + $_.Name }
$files += Get-ChildItem (Join-Path $repo 'docs') -File -Filter '*.md' | ForEach-Object { 'docs/' + $_.Name }
$files += @('config/element-config.json', 'config/element-nginx.conf.template', 'config/gitignore.template')
$files += @('mcp/memory/static/index.html', 'mcp/memory/static/app.js', 'mcp/memory/static/app.css')
foreach ($relative in $files) {
    $destination = Join-Path $stage $relative
    $null = New-Item -ItemType Directory -Force -Path (Split-Path $destination)
    Copy-Item -LiteralPath (Join-Path $repo $relative) -Destination $destination
}
$out = Join-Path $repo 'dist'
$null = New-Item -ItemType Directory -Force -Path $out
$zip = Join-Path $out 'Hearth-Windows-Setup-preview.zip'
Compress-Archive -Path (Join-Path $stage '*') -DestinationPath $zip -Force
Write-Output $zip
