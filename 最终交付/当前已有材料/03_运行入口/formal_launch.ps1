param([Parameter(Mandatory=$true)][ValidateSet(3,4)][int]$Problem, [switch]$Check, [ValidateSet('RouteProbeP4','FastP4')][string]$P4Strategy = 'RouteProbeP4')
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
$pythonCandidates = @()
if ($env:JAMMERS_PYTHON) { $pythonCandidates += $env:JAMMERS_PYTHON }
$pythonCandidates += (Join-Path $repoRoot '.venv/Scripts/python.exe')
$pythonCandidates += (Join-Path $env:USERPROFILE '.cache/cumcm-q12-venv/Scripts/python.exe')
$pythonCommand = Get-Command python.exe -ErrorAction SilentlyContinue
if ($pythonCommand) { $pythonCandidates += $pythonCommand.Source }
$selectedPython = $pythonCandidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
if (-not $selectedPython) {
    Write-Host 'Python not found. Set JAMMERS_PYTHON to your project Python executable.'
    exit 1
}
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUNBUFFERED = '1'
$env:PYTHONUTF8 = '1'
$launchArgs = @((Join-Path $PSScriptRoot 'formal_launch.py'), '--problem', [string]$Problem)
if ($Problem -eq 4) { $launchArgs += @('--p4-strategy', $P4Strategy) }
if ($Check) { $launchArgs += '--check' }
& $selectedPython @launchArgs
exit $LASTEXITCODE
