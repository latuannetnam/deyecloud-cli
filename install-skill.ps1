#Requires -Version 5.1
<#
.SYNOPSIS
    Installs the deye-cloud skill into Claude Code's personal skills directory.

.DESCRIPTION
    Copies the deye-cloud skill (SKILL.md, references/, scripts/) from the
    project directory to ~/.claude/skills/deye-cloud/, suitable for use across
    all Claude Code projects.

    Claude Code skill frontmatter does NOT support 'allowed-tools' or
    'disable-model-invocation' — this script ensures only supported fields
    are written to the installed SKILL.md.

.PARAMETER ProjectPath
    Path to the project root (where skills/deye-cloud/ lives).
    Defaults to the directory containing this script.
    Use this to run the script from any location.

.PARAMETER SkipSync
    Do not copy the corrected SKILL.md back to the project directory.

.EXAMPLE
    .\install-skill.ps1
    .\install-skill.ps1 -SkipSync
    .\install-skill.ps1 -ProjectPath "D:\latuan\Programming\deyecloud-cli"
    .\install-skill.ps1 -ProjectPath "D:\latuan\Programming\deyecloud-cli" -SkipSync
#>

param(
    [string]$ProjectPath = $PSScriptRoot,
    [switch]$SkipSync
)

# ─── Configuration ────────────────────────────────────────────────────────────
$ScriptRoot     = $ProjectPath
$SkillSourceDir = "$ScriptRoot\skills\deye-cloud"
$SkillName      = "deye-cloud"
$ClaudeHome     = "$env:USERPROFILE\.claude"
$SkillTargetDir = "$ClaudeHome\skills\$SkillName"

# Frontmatter written to installed SKILL.md — ONLY supported fields
$Frontmatter = @"
---
name: $SkillName
description: Monitor, configure, and control Deye Hybrid Inverters via the DeyeCloud API. Use when the user asks about solar panels, battery status, inverter settings, energy production, grid export, or any Deye/solar-related topic.
---
"@

# ─── Helpers ──────────────────────────────────────────────────────────────────
function Write-Step($msg) { Write-Host "  $msg" -ForegroundColor Cyan }
function Write-OK($msg)   { Write-Host "  [OK] $msg" -ForegroundColor Green }
function Write-SKIP($msg) { Write-Host "  [SKIP] $msg" -ForegroundColor Yellow }
function Write-ERR($msg)  { Write-Host "  [ERR] $msg" -ForegroundColor Red }

function Install-SkillFile {
    param([string]$Src, [string]$Dst)

    if (-not (Test-Path $Src)) {
        Write-SKIP "Source not found: $Src"
        return $false
    }

    $dstDir = Split-Path $Dst -Parent
    if (-not (Test-Path $dstDir)) {
        New-Item -ItemType Directory -Path $dstDir -Force | Out-Null
    }

    Copy-Item -Path $Src -Destination $Dst -Force
    return $true
}

# ─── Banner ───────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "╔══════════════════════════════════════════════════╗" -ForegroundColor Magenta
Write-Host "║     deye-cloud  —  Claude Code Skill Installer  ║" -ForegroundColor Magenta
Write-Host "╚══════════════════════════════════════════════════╝" -ForegroundColor Magenta
Write-Host ""

# ─── Resolve project path ────────────────────────────────────────────────────
Write-Host "Project : $ProjectPath" -ForegroundColor DarkGray
Write-Host "Skill   : $SkillSourceDir" -ForegroundColor DarkGray

$srcSkillMd  = "$SkillSourceDir\SKILL.md"
$srcScripts  = "$SkillSourceDir\scripts"
$srcRefs     = "$SkillSourceDir\references"

if (-not (Test-Path $srcSkillMd)) {
    Write-ERR "SKILL.md not found at $srcSkillMd"
    exit 1
}
Write-OK "Source validated"

# ─── Validate Claude Code home ───────────────────────────────────────────────
if (-not (Test-Path $ClaudeHome)) {
    Write-ERR "Claude Code home not found at $ClaudeHome. Is Claude Code installed?"
    exit 1
}
Write-OK "Claude Code home : $ClaudeHome"

# ─── Clean & create target ───────────────────────────────────────────────────
Write-Host ""
Write-Host "── Preparing target directory ────────────────────────" -ForegroundColor Magenta

if (Test-Path $SkillTargetDir) {
    Write-Step "Removing existing installation..."
    Remove-Item -Path $SkillTargetDir -Recurse -Force
}
New-Item -ItemType Directory -Path $SkillTargetDir -Force | Out-Null
Write-OK "Target directory ready: $SkillTargetDir"

# ─── Copy supporting folders ─────────────────────────────────────────────────
Write-Host ""
Write-Host "── Copying files ─────────────────────────────────────" -ForegroundColor Magenta

# References
if (Test-Path $srcRefs) {
    $refFiles = Get-ChildItem -Path $srcRefs -Filter "*.md"
    foreach ($f in $refFiles) {
        $dst = "$SkillTargetDir\references\$($f.Name)"
        Install-SkillFile -Src $f.FullName -Dst $dst | Out-Null
        Write-Step "references/$($f.Name)"
    }
    Write-OK "references/ copied"
} else {
    Write-SKIP "No references/ folder found"
}

# Scripts (exclude __pycache__)
if (Test-Path $srcScripts) {
    $scriptFiles = Get-ChildItem -Path $srcScripts -Filter "*.py"
    foreach ($f in $scriptFiles) {
        $dst = "$SkillTargetDir\scripts\$($f.Name)"
        Install-SkillFile -Src $f.FullName -Dst $dst | Out-Null
        Write-Step "scripts/$($f.Name)"
    }
    Write-OK "scripts/ copied (excluded __pycache__)"
} else {
    Write-SKIP "No scripts/ folder found"
}

# ─── Write SKILL.md (with supported frontmatter only) ───────────────────────
Write-Host ""
Write-Host "── Writing SKILL.md ──────────────────────────────────" -ForegroundColor Magenta

$srcContent = Get-Content -Path $srcSkillMd -Raw -Encoding UTF8

# Strip any existing frontmatter block(s) — handles duplicate/multiple blocks
$srcContent = $srcContent -replace '(?s)(^---\n.*?\n---\n)+', ''

# Build final content: our clean frontmatter + stripped body
$finalContent = $Frontmatter + "`n" + $srcContent.TrimStart()

$dstSkillMd = "$SkillTargetDir\SKILL.md"
Set-Content -Path $dstSkillMd -Value $finalContent -Encoding UTF8 -NoNewline
Write-OK "SKILL.md written (frontmatter sanitised)"
Write-Step "Note: allowed-tools / disable-model-invocation removed (unsupported)"

# ─── Sync back to project (optional) ────────────────────────────────────────
Write-Host ""
Write-Host "── Syncing back to project ───────────────────────────" -ForegroundColor Magenta

if ($SkipSync) {
    Write-SKIP "Skipped (use without -SkipSync to enable)"
} else {
    Copy-Item -Path $dstSkillMd -Destination $srcSkillMd -Force
    Write-OK "SKILL.md synced to $srcSkillMd"
}

# ─── Done ───────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "╔══════════════════════════════════════════════════╗" -ForegroundColor Magenta
Write-Host "║  Installation complete!                          ║" -ForegroundColor Green
Write-Host "║                                                  ║" -ForegroundColor Green
Write-Host "║  Start a new Claude Code session, then try:      ║" -ForegroundColor Green
Write-Host "║    /deye-cloud setup                             ║" -ForegroundColor Yellow
Write-Host "║    /deye-cloud status                            ║" -ForegroundColor Yellow
Write-Host "╚══════════════════════════════════════════════════╝" -ForegroundColor Magenta
Write-Host ""
