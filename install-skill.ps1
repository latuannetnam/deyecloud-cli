#Requires -Version 5.1
<#
.SYNOPSIS
    Thin wrapper around install.py — installs the deye-* skill suite.
.DESCRIPTION
    Delegates to install.py (the cross-platform source of truth). All
    arguments are forwarded, e.g.:
        .\install-skill.ps1
        .\install-skill.ps1 --scope local
        .\install-skill.ps1 --scope global --dry-run
.NOTES
    Requires python (or python3) on PATH.
#>

$ScriptDir = $PSScriptRoot
$InstallPy = Join-Path $ScriptDir "install.py"

if (-not (Test-Path $InstallPy)) {
    Write-Host "[ERR] install.py not found at $InstallPy" -ForegroundColor Red
    exit 1
}

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    $python = Get-Command python3 -ErrorAction SilentlyContinue
}
if (-not $python) {
    Write-Host "[ERR] Python not found on PATH. Install Python 3.8+." -ForegroundColor Red
    exit 1
}

& $python.Source $InstallPy @args
exit $LASTEXITCODE
