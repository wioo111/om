param(
    [ValidateRange(1, 65535)][int]$Port = 8765,
    [switch]$NoBrowser
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$OutputEncoding = [Console]::OutputEncoding
$env:PYTHONUTF8 = '1'
$launchRoot = $PSScriptRoot
$bootstrap = Join-Path $launchRoot 'paper_editor/bootstrap.py'
$pythonCandidates = @()
$venvPython = Join-Path $launchRoot '.venv/Scripts/python.exe'
if (Test-Path -LiteralPath $venvPython) { $pythonCandidates += ,@($venvPython) }
foreach ($pythonName in @('py', 'python', 'python3')) {
    $pythonCommand = Get-Command $pythonName -ErrorAction SilentlyContinue
    if ($pythonCommand -and $pythonCommand.Source -notmatch '[\\/]WindowsApps[\\/]') {
        if ($pythonName -eq 'py') { $pythonCandidates += ,@($pythonCommand.Source, '-3') }
        else { $pythonCandidates += ,@($pythonCommand.Source) }
    }
}
$chosenPython = $null
foreach ($candidate in $pythonCandidates) {
    $pythonExe = $candidate[0]
    $pythonPrefix = @($candidate | Select-Object -Skip 1)
    try {
        & $pythonExe @pythonPrefix -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 3)" 2>$null
        if ($LASTEXITCODE -eq 0) { $chosenPython = $candidate; break }
    } catch { }
}
if (-not $chosenPython) {
    Write-Host '需要先安装 Python 3.10 或更高版本，并选择 Add Python to PATH。' -ForegroundColor Red
    Write-Host '下载地址：https://www.python.org/downloads/；无需管理员权限、Node.js 或预装 Python 包。'
    exit 1
}
$pythonExe = $chosenPython[0]
$pythonPrefix = @($chosenPython | Select-Object -Skip 1)
$bootstrapArguments = @($bootstrap, '--port', [string]$Port)
if ($NoBrowser) { $bootstrapArguments += '--no-browser' }
& $pythonExe @pythonPrefix @bootstrapArguments
exit $LASTEXITCODE
