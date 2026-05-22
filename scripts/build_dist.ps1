# build_dist.ps1 — Build sdist + wheel for anima-prompt-helper
# Run from anywhere; the script resolves the extension root automatically.
# Does NOT install anything.

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot

Write-Host "=== anima-prompt-helper — build sdist + wheel ===" -ForegroundColor Cyan
Write-Host "Root: $root"

# Verify python -m build is available
$buildCheck = python -m build --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Warning "'python -m build' is not available."
    Write-Warning "Install it first (without --no-deps to get wheel too):"
    Write-Warning "    pip install build"
    exit 1
}
Write-Host "build version: $buildCheck"

# Run build
Push-Location $root
try {
    python -m build --sdist --wheel --outdir dist/
    if ($LASTEXITCODE -ne 0) {
        Write-Error "python -m build failed (exit $LASTEXITCODE)"
        exit 1
    }
} finally {
    Pop-Location
}

# Verify outputs exist and print sizes
$distDir = Join-Path $root "dist"
$tarGz = Get-ChildItem -Path $distDir -Filter "*.tar.gz" -ErrorAction SilentlyContinue
$whl   = Get-ChildItem -Path $distDir -Filter "*.whl"    -ErrorAction SilentlyContinue

$ok = $true
if (-not $tarGz) { Write-Error "No .tar.gz found in dist/"; $ok = $false }
if (-not $whl)   { Write-Error "No .whl found in dist/";    $ok = $false }

if ($ok) {
    Write-Host "`nDist files:" -ForegroundColor Green
    foreach ($f in ($tarGz + $whl)) {
        $kb = [math]::Round($f.Length / 1KB, 1)
        Write-Host ("  {0,-55} {1,8} KB" -f $f.Name, $kb)
    }
    Write-Host "`n[PASS] Build succeeded." -ForegroundColor Green
    exit 0
} else {
    exit 1
}
