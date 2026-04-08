#Requires -Version 5.1
<#
.SYNOPSIS
    Installs all skills from the project's skills/ folder into Claude Code's
    personal skills directory.

.DESCRIPTION
    Iterates over every subdirectory in <ProjectPath>/skills/ and copies
    its SKILL.md, references/, and scripts/ to ~/.claude/skills/<skill-name>/.
    Files are copied as-is — no transformation or rewriting.

    Useful when adding new skills: just drop a new folder under skills/ and
    re-run this script.

.PARAMETER ProjectPath
    Path to the project root (where skills/ lives).
    Defaults to the directory containing this script.

.EXAMPLE
    .\install-skill.ps1
    .\install-skill.ps1 -ProjectPath "D:\latuan\Programming\deyecloud-cli"
#>

param(
    [string]$ProjectPath = $PSScriptRoot
)

# ─── Configuration ────────────────────────────────────────────────────────────
$ScriptRoot = $ProjectPath
$SkillsSourceDir = "$ScriptRoot\skills"
$ClaudeHome = "$env:USERPROFILE\.claude"

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

function Install-Skill {
    param(
        [string]$SkillSourceDir,
        [string]$SkillName
    )

    $SkillTargetDir = "$ClaudeHome\skills\$SkillName"

    Write-Host ""
    Write-Host "  ══ $SkillName ══" -ForegroundColor Magenta

    $srcSkillMd = "$SkillSourceDir\SKILL.md"

    if (-not (Test-Path $srcSkillMd)) {
        Write-ERR "SKILL.md not found at $srcSkillMd"
        return $false
    }

    # ── Clean & create target ─────────────────────────────────────────────────
    if (Test-Path $SkillTargetDir) {
        Write-Step "Removing existing installation..."
        Remove-Item -Path $SkillTargetDir -Recurse -Force
    }
    New-Item -ItemType Directory -Path $SkillTargetDir -Force | Out-Null

    # ── Copy references ───────────────────────────────────────────────────────
    $srcRefs = Join-Path $SkillSourceDir "references"
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

    # ── Copy scripts ─────────────────────────────────────────────────────────
    $srcScripts = Join-Path $SkillSourceDir "scripts"
    if (Test-Path $srcScripts) {
        $scriptFiles = Get-ChildItem -Path $srcScripts -Filter "*.py"
        foreach ($f in $scriptFiles) {
            $dst = "$SkillTargetDir\scripts\$($f.Name)"
            Install-SkillFile -Src $f.FullName -Dst $dst | Out-Null
            Write-Step "scripts/$($f.Name)"
        }
        Write-OK "scripts/ copied"
    } else {
        Write-SKIP "No scripts/ folder found"
    }

    # ── Copy SKILL.md as-is ─────────────────────────────────────────────────
    Install-SkillFile -Src $srcSkillMd -Dst "$SkillTargetDir\SKILL.md" | Out-Null
    Write-Step "SKILL.md"

    return $true
}

# ─── Main ────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "  [== Claude Code Skill Installer (all skills) ==]" -ForegroundColor Magenta
Write-Host ""

Write-Host "Project      : $ProjectPath" -ForegroundColor DarkGray
Write-Host "Source dir   : $SkillsSourceDir" -ForegroundColor DarkGray
Write-Host ""

# ─── Validate source ─────────────────────────────────────────────────────────
if (-not (Test-Path $SkillsSourceDir)) {
    Write-ERR "skills/ directory not found at $SkillsSourceDir"
    exit 1
}

$skillFolders = Get-ChildItem -Path $SkillsSourceDir -Directory
if ($skillFolders.Count -eq 0) {
    Write-ERR "No skill folders found in $SkillsSourceDir"
    exit 1
}

Write-Host "Skills found : $($skillFolders.Name -join ', ')" -ForegroundColor DarkGray

# ─── Validate Claude Code home ───────────────────────────────────────────────
if (-not (Test-Path $ClaudeHome)) {
    Write-ERR "Claude Code home not found at $ClaudeHome. Is Claude Code installed?"
    exit 1
}
Write-OK "Claude Code home : $ClaudeHome"

# ─── Install each skill ──────────────────────────────────────────────────────
$installed = @()
$failed    = @()

foreach ($folder in $skillFolders) {
    $result = Install-Skill -SkillSourceDir $folder.FullName -SkillName $folder.Name
    if ($result) {
        $installed += $folder.Name
    } else {
        $failed += $folder.Name
    }
}

# ─── Done ────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "  [=== Installation Summary ===]" -ForegroundColor Magenta
if ($failed.Count -eq 0) {
    Write-Host "  All skills installed successfully!" -ForegroundColor Green
} else {
    Write-Host "  Installation complete (some skipped)" -ForegroundColor Yellow
}
Write-Host ""
Write-Host "  Installed  : $($installed -join ', ')" -ForegroundColor Green
if ($failed.Count -gt 0) {
    Write-Host "  Skipped    : $($failed -join ', ')" -ForegroundColor Yellow
}
Write-Host ""
Write-Host "  Start a new Claude Code session to use them." -ForegroundColor Green
Write-Host ""