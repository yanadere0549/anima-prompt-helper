#Requires -Version 5.1
<#
.SYNOPSIS
    Local CI runner for anima-prompt-helper. Mirrors .github/workflows/ci.yml.

.PARAMETER SkipBenchmarks
    Skip benchmark scripts (step 6). Useful for quick pre-push checks.

.EXAMPLE
    pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/run_all_checks.ps1
    pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/run_all_checks.ps1 -SkipBenchmarks
#>
[CmdletBinding()]
param(
    [switch]$SkipBenchmarks
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

function Write-Step { param([string]$Msg)
    Write-Host "`n=== $Msg ===" -ForegroundColor Cyan
}

function Write-Pass { param([string]$Msg)
    Write-Host "[PASS] $Msg" -ForegroundColor Green
}

function Write-Fail { param([string]$Msg)
    Write-Host "[FAIL] $Msg" -ForegroundColor Red
}

function Write-Info { param([string]$Msg)
    Write-Host "       $Msg" -ForegroundColor Yellow
}

# ---------------------------------------------------------------------------
# Resolve root and Python
# ---------------------------------------------------------------------------

$ScriptDir  = $PSScriptRoot
$ExtRoot    = (Resolve-Path (Join-Path $ScriptDir "..")).Path

$PythonExe = $null
# Resolve all python/python3 executables on PATH (may be >1 on Windows).
# Prefer the first one that has pytest installed; fall back to any that run.
$AllPythons = @()
foreach ($name in @("python3", "python")) {
    try {
        $found = Get-Command $name -All -ErrorAction SilentlyContinue
        if ($found) { $AllPythons += $found | Select-Object -ExpandProperty Source }
    } catch { }
}
$AllPythons = $AllPythons | Select-Object -Unique

foreach ($py in $AllPythons) {
    try {
        $ver = & $py --version 2>&1
        if ($LASTEXITCODE -ne 0) { continue }
        & $py -c "import pytest" 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            $PythonExe = $py
            break
        }
        if (-not $PythonExe) { $PythonExe = $py }   # fallback
    } catch { }
}
if (-not $PythonExe) {
    Write-Fail "Python not found. Install Python 3.10+ and ensure it is on PATH."
    exit 1
}

# ---------------------------------------------------------------------------
# Stopwatch + per-step tracking
# ---------------------------------------------------------------------------

$Stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
$StepResults = New-Object 'System.Collections.Generic.List[hashtable]'

function Record-Step {
    param([string]$Name, [bool]$Passed, [string]$Detail = "")
    $StepResults.Add(@{ Name = $Name; Passed = $Passed; Detail = $Detail })
}

# ---------------------------------------------------------------------------
# HEADER
# ---------------------------------------------------------------------------

Write-Host ""
Write-Host "############################################################" -ForegroundColor Cyan
Write-Host "#   anima-prompt-helper  --  local CI runner               #" -ForegroundColor Cyan
Write-Host "############################################################" -ForegroundColor Cyan
Write-Host "Root   : $ExtRoot"
Write-Host "Python : $(&$PythonExe --version 2>&1)"
Write-Host "Date   : $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
if ($SkipBenchmarks) {
    Write-Info "Benchmarks : SKIPPED (-SkipBenchmarks)"
}

# ---------------------------------------------------------------------------
# STEP 1 - py_compile (fail-fast)
# ---------------------------------------------------------------------------

Write-Step "Step 1 - Syntax check (py_compile)"

$PyFiles = Get-ChildItem -Path $ExtRoot -Recurse -Filter "*.py" |
    Where-Object { $_.FullName -notmatch '[\\/]\.venv[\\/]' } |
    Where-Object { $_.FullName -notmatch '[\\/]\.git[\\/]' } |
    Where-Object { $_.FullName -notmatch '[\\/]node_modules[\\/]' } |
    Where-Object { $_.FullName -notmatch '[\\/]__pycache__[\\/]' }

Write-Host "       Found $($PyFiles.Count) .py files"

$CompileError = $false
foreach ($f in $PyFiles) {
    & $PythonExe -m py_compile $f.FullName 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "Compile error: $($f.FullName)"
        $CompileError = $true
    }
}

if ($CompileError) {
    Write-Fail "py_compile failed. Fix syntax errors before proceeding."
    Record-Step "py_compile" $false "Syntax errors found"
    # Print summary so far then exit
    $Stopwatch.Stop()
    Write-Host "`n[SUMMARY] ABORTED after step 1 (total $([int]$Stopwatch.Elapsed.TotalSeconds)s)" -ForegroundColor Red
    exit 1
}

Write-Pass "All $($PyFiles.Count) Python files compile cleanly."
Record-Step "py_compile" $true "$($PyFiles.Count) files"

# ---------------------------------------------------------------------------
# STEP 2 - pytest
# ---------------------------------------------------------------------------

Write-Step "Step 2 - pytest"

$TestsDir = Join-Path $ExtRoot "tests"
Push-Location $ExtRoot
try {
    & $PythonExe -m pytest $TestsDir -v --tb=short
    $PytestCode = $LASTEXITCODE
} finally {
    Pop-Location
}

if ($PytestCode -eq 0) {
    Write-Pass "pytest passed (exit $PytestCode)."
    Record-Step "pytest" $true
} else {
    Write-Fail "pytest failed (exit $PytestCode)."
    Record-Step "pytest" $false "exit $PytestCode"
}

# ---------------------------------------------------------------------------
# STEP 3 - data integrity check
# ---------------------------------------------------------------------------

Write-Step "Step 3 - Data integrity check"

$IntegrityScript = Join-Path $ScriptDir "check_data_integrity.py"
Push-Location $ExtRoot
try {
    $IntegrityOutput = & $PythonExe $IntegrityScript 2>&1
    $IntegrityCode = $LASTEXITCODE
} finally {
    Pop-Location
}

$IntegrityOutput | ForEach-Object { Write-Host "       $_" }
if ($IntegrityCode -eq 0) {
    Write-Pass "check_data_integrity.py passed."
    Record-Step "data_integrity" $true
} else {
    Write-Fail "check_data_integrity.py failed (exit $IntegrityCode)."
    Record-Step "data_integrity" $false "exit $IntegrityCode"
}

# ---------------------------------------------------------------------------
# STEP 4 - JSON validation (data/, i18n/, templates/)
# ---------------------------------------------------------------------------

Write-Step "Step 4 - JSON file validation"

$JsonDirs = @(
    (Join-Path $ExtRoot "data"),
    (Join-Path $ExtRoot "i18n"),
    (Join-Path $ExtRoot "templates")
)

$JsonFiles  = @()
$JsonFailed = @()

foreach ($dir in $JsonDirs) {
    if (Test-Path $dir) {
        $JsonFiles += Get-ChildItem -Path $dir -Recurse -Filter "*.json"
    }
}

Write-Host "       Checking $($JsonFiles.Count) JSON file(s)..."

foreach ($jf in $JsonFiles) {
    $relPath = $jf.FullName.Substring($ExtRoot.Length).TrimStart('\').TrimStart('/')
    $result = & $PythonExe -c "import json,sys; json.load(open(r'$($jf.FullName)',encoding='utf-8'))" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "  JSON parse error: $relPath"
        Write-Host "         $result" -ForegroundColor Red
        $JsonFailed += $relPath
    } else {
        Write-Host "       OK  $relPath"
    }
}

# Workflow node-ID validation (mirrors ci.yml inline script)
$WorkflowValidatePy = @"
import json, sys, pathlib, re

workflow_files = list(pathlib.Path(r'$ExtRoot').rglob('data/anima_workflow_*.json'))
if not workflow_files:
    print('No workflow JSON files found -- skipping node-id validation')
    sys.exit(0)

errors = []
for wf_path in workflow_files:
    try:
        data = json.loads(wf_path.read_text(encoding='utf-8'))
    except json.JSONDecodeError as exc:
        errors.append(f'{wf_path}: JSON parse error: {exc}')
        continue
    nodes = data.get('nodes', [])
    node_ids = {n['id'] for n in nodes if 'id' in n}
    links = data.get('links', [])
    for link in links:
        if len(link) < 5:
            continue
        src_node_id = link[1]
        dst_node_id = link[3]
        if src_node_id not in node_ids:
            errors.append(f'{wf_path}: link {link[0]} references missing src node {src_node_id}')
        if dst_node_id not in node_ids:
            errors.append(f'{wf_path}: link {link[0]} references missing dst node {dst_node_id}')

if errors:
    for e in errors:
        print(f'ERROR: {e}', file=sys.stderr)
    sys.exit(1)
print(f'OK: validated {len(workflow_files)} workflow file(s)')
"@

$WfOutput = & $PythonExe -c $WorkflowValidatePy 2>&1
$WfCode   = $LASTEXITCODE
$WfOutput | ForEach-Object { Write-Host "       $_" }

if ($JsonFailed.Count -eq 0 -and $WfCode -eq 0) {
    Write-Pass "All $($JsonFiles.Count) JSON file(s) valid."
    Record-Step "json_validation" $true "$($JsonFiles.Count) files"
} else {
    if ($JsonFailed.Count -gt 0) {
        Write-Fail "JSON parse errors in: $($JsonFailed -join ', ')"
    }
    if ($WfCode -ne 0) {
        Write-Fail "Workflow node-ID validation failed."
    }
    Record-Step "json_validation" $false "failures: $($JsonFailed.Count)"
}

# ---------------------------------------------------------------------------
# STEP 5 - Benchmarks (optional)
# ---------------------------------------------------------------------------

if ($SkipBenchmarks) {
    Write-Step "Step 5 - Benchmarks (SKIPPED)"
    Write-Info "Pass -SkipBenchmarks to skip. Remove flag to run."
    Record-Step "benchmarks" $true "skipped"
} else {
    Write-Step "Step 5 - Benchmarks"

    $BenchScripts = Get-ChildItem -Path $ScriptDir -Filter "benchmark_*.py" | Sort-Object Name
    Write-Host "       Found $($BenchScripts.Count) benchmark script(s)."

    $BenchFailed = $false

    foreach ($bs in $BenchScripts) {
        Write-Host "`n  --- $($bs.Name) ---" -ForegroundColor Yellow
        Push-Location $ExtRoot
        try {
            $BenchLines = & $PythonExe $bs.FullName 2>&1
            $BenchCode  = $LASTEXITCODE
        } finally {
            Pop-Location
        }

        # Print last 6 lines
        $BenchTail = $BenchLines | Select-Object -Last 6
        $BenchTail | ForEach-Object { Write-Host "       $_" }

        if ($BenchCode -ne 0) {
            Write-Fail "$($bs.Name) exited $BenchCode"
            $BenchFailed = $true
        } else {
            Write-Pass "$($bs.Name) completed."
        }
    }

    if (-not $BenchFailed) {
        Record-Step "benchmarks" $true "$($BenchScripts.Count) scripts"
    } else {
        Record-Step "benchmarks" $false "one or more benchmarks failed"
    }
}

# ---------------------------------------------------------------------------
# FINAL SUMMARY
# ---------------------------------------------------------------------------

$Stopwatch.Stop()
$TotalSec = [math]::Round($Stopwatch.Elapsed.TotalSeconds, 1)

$AllPassed = (@($StepResults | Where-Object { -not $_.Passed })).Count -eq 0

Write-Host ""
Write-Host "############################################################" -ForegroundColor Cyan
Write-Host "#                       SUMMARY                           #" -ForegroundColor Cyan
Write-Host "############################################################" -ForegroundColor Cyan
Write-Host "  Total time : ${TotalSec}s"
Write-Host ""

$i = 1
foreach ($sr in $StepResults) {
    if ($sr.Passed) {
        $statusColor = "Green"; $statusText = "PASS"
    } else {
        $statusColor = "Red"; $statusText = "FAIL"
    }
    $detail = if ($sr.Detail) { "  ($($sr.Detail))" } else { "" }
    Write-Host ("  Step {0}: [{1}] {2}{3}" -f $i, $statusText, $sr.Name, $detail) -ForegroundColor $statusColor
    $i++
}

Write-Host ""
if ($AllPassed) {
    Write-Host "  RESULT: ALL CHECKS PASSED" -ForegroundColor Green
    exit 0
} else {
    Write-Host "  RESULT: ONE OR MORE CHECKS FAILED" -ForegroundColor Red
    exit 1
}
