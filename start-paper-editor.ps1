param(
    [ValidateRange(1, 65535)][int]$Port = 8765,
    [switch]$NoBrowser
)
$ErrorActionPreference = 'Stop'
$paperLauncher = Join-Path $PSScriptRoot '最终交付/工作台论文/启动工作台.ps1'
if (-not (Test-Path -LiteralPath $paperLauncher)) {
    Write-Host 'Paper workbench files are missing. Please clone or pull the complete repository.' -ForegroundColor Red
    exit 1
}
& $paperLauncher -Port $Port -NoBrowser:$NoBrowser
exit $LASTEXITCODE
