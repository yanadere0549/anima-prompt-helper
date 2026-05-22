# zip_release.ps1 — Build a local release zip matching the GitHub Actions release.yml output.
# Output: dist/anima-prompt-helper-v<version>.zip (version read from pyproject.toml)
# Does NOT install anything.

$ErrorActionPreference = "Stop"

$root    = Split-Path -Parent $PSScriptRoot

# Read version from pyproject.toml ([project] table -> version = "x.y.z")
$pyproject = Get-Content -Path (Join-Path $root "pyproject.toml") -Encoding UTF8
$versionLine = $pyproject | Where-Object { $_ -match '^\s*version\s*=\s*"([^"]+)"' } | Select-Object -First 1
if (-not $versionLine -or -not ($versionLine -match '^\s*version\s*=\s*"([^"]+)"')) {
    throw "Failed to read version from pyproject.toml"
}
$version = "v$($Matches[1])"
$zipName = "anima-prompt-helper-$version.zip"
$distDir = Join-Path $root "dist"
$zipPath = Join-Path $distDir $zipName

Write-Host "=== anima-prompt-helper — zip release ===" -ForegroundColor Cyan
Write-Host "Root   : $root"
Write-Host "Output : $zipPath"

# Ensure dist/ exists
if (-not (Test-Path $distDir)) {
    New-Item -ItemType Directory -Path $distDir | Out-Null
}

# Remove stale zip if present
if (Test-Path $zipPath) {
    Remove-Item $zipPath -Force
}

# Collect files to include (mirror release.yml excludes)
$excludePatterns = @(
    "\.git[/\\]",
    "__pycache__[/\\]",
    "\.pyc$",
    "\.github[/\\]",
    "\.venv[^/\\]*[/\\]",
    "node_modules[/\\]",
    "data[/\\]anima_workflow_",
    "\.egg-info[/\\]",
    "[/\\]dist[/\\]",
    "[/\\]build[/\\]",
    "\.pytest_cache[/\\]"
)

$allFiles = Get-ChildItem -Path $root -Recurse -File | Where-Object {
    $rel = $_.FullName.Substring($root.Length + 1)
    $include = $true
    foreach ($pat in $excludePatterns) {
        if ($rel -match $pat) { $include = $false; break }
    }
    $include
}

Write-Host "Collecting $($allFiles.Count) files..."

# Build zip using Compress-Archive (requires temp staging for relative paths)
$tempDir = Join-Path ([System.IO.Path]::GetTempPath()) "anima_zip_$([System.Guid]::NewGuid().ToString('N'))"
New-Item -ItemType Directory -Path $tempDir | Out-Null

try {
    foreach ($f in $allFiles) {
        $rel = $f.FullName.Substring($root.Length + 1)
        $dest = Join-Path $tempDir $rel
        $destParent = Split-Path $dest -Parent
        if (-not (Test-Path $destParent)) {
            New-Item -ItemType Directory -Path $destParent | Out-Null
        }
        Copy-Item $f.FullName $dest
    }

    Compress-Archive -Path (Join-Path $tempDir "*") -DestinationPath $zipPath -CompressionLevel Optimal
} finally {
    Remove-Item $tempDir -Recurse -Force -ErrorAction SilentlyContinue
}

# Report
$zipItem = Get-Item $zipPath
$kb = [math]::Round($zipItem.Length / 1KB, 1)
Write-Host "`nCreated: $zipPath" -ForegroundColor Green
Write-Host "Size   : $kb KB"
Write-Host "[PASS] zip_release succeeded." -ForegroundColor Green
exit 0
