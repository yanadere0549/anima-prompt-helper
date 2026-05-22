#Requires -Version 5.1
<#
.SYNOPSIS
    Installs anima-prompt-helper workflow templates into the ComfyUI workflow picker.

.DESCRIPTION
    Copies templates/*.json from the extension directory into
    <ComfyUI>/user/default/workflows/, naming each file with the prefix
    "anima-prompt-helper - " so they are visually grouped in the picker.

.PARAMETER Force
    Overwrite existing files in the target directory.

.PARAMETER DryRun
    Print what would be copied without writing any files.

.PARAMETER Quiet
    Suppress per-file messages; print only the final summary.

.EXAMPLE
    pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/install_templates.ps1
    pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/install_templates.ps1 -Force
    pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/install_templates.ps1 -DryRun
#>
[CmdletBinding()]
param(
    [switch]$Force,
    [switch]$DryRun,
    [switch]$Quiet
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# ---------------------------------------------------------------------------
# Path detection
# scripts/ -> extension root -> ComfyUI root
# ---------------------------------------------------------------------------

$ScriptDir   = $PSScriptRoot
$ExtRoot     = (Resolve-Path (Join-Path $ScriptDir "..")).Path
$ComfyRoot   = (Resolve-Path (Join-Path $ExtRoot "../..")).Path
$TargetDir   = Join-Path $ComfyRoot "user\default\workflows"
$TemplateDir = Join-Path $ExtRoot "templates"
$Prefix      = "anima-prompt-helper - "

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

function Write-Msg {
    param([string]$Text, [string]$Color = "White")
    if (-not $Quiet) {
        Write-Host $Text -ForegroundColor $Color
    }
}

# ---------------------------------------------------------------------------
# Validate template directory
# ---------------------------------------------------------------------------

if (-not (Test-Path $TemplateDir)) {
    Write-Host "[ERROR] Templates directory not found: $TemplateDir" -ForegroundColor Red
    exit 1
}

$Templates = @(Get-ChildItem -Path $TemplateDir -Filter "*.json" -File)
if ($Templates.Count -eq 0) {
    Write-Host "[WARN] No .json files found in: $TemplateDir" -ForegroundColor Yellow
    exit 0
}

# ---------------------------------------------------------------------------
# Create target directory (unless dry-run)
# ---------------------------------------------------------------------------

if ($DryRun) {
    Write-Msg "[DRY RUN] Target directory: $TargetDir" "Cyan"
} else {
    if (-not (Test-Path $TargetDir)) {
        New-Item -ItemType Directory -Path $TargetDir -Force | Out-Null
        Write-Msg "Created directory: $TargetDir" "Yellow"
    }
}

# ---------------------------------------------------------------------------
# Process each template
# ---------------------------------------------------------------------------

$Copied  = 0
$Skipped = 0

foreach ($tmpl in $Templates) {
    $destName = "${Prefix}$($tmpl.Name)"
    $destPath = Join-Path $TargetDir $destName

    if ($DryRun) {
        Write-Host "  would copy: $($tmpl.Name) -> $destName" -ForegroundColor Cyan
        $Copied++
        continue
    }

    if (Test-Path $destPath) {
        if ($Force) {
            Copy-Item -Path $tmpl.FullName -Destination $destPath -Force
            Write-Msg "  overwrite : $destName" "Yellow"
            $Copied++
        } else {
            Write-Msg "  skip      : $destName (already exists; use -Force to overwrite)" "DarkGray"
            $Skipped++
        }
    } else {
        Copy-Item -Path $tmpl.FullName -Destination $destPath
        Write-Msg "  copy      : $destName" "Green"
        $Copied++
    }
}

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

if ($DryRun) {
    Write-Host ""
    Write-Host "Dry-run summary: would copy $Copied template(s)." -ForegroundColor Cyan
} else {
    Write-Host ""
    Write-Host "Done. Copied: $Copied  Skipped: $Skipped" -ForegroundColor Green
}

exit 0
