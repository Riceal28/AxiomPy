param(
    [string]$FfmpegBin = $env:AXIOM_FFMPEG_BIN,
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$dist = Join-Path $projectRoot "dist\AxiomPy"
$liteDist = Join-Path $projectRoot "dist\AxiomPy-noffmpeg"

if (-not $FfmpegBin) {
    $ffmpeg = Get-Command ffmpeg.exe -ErrorAction SilentlyContinue
    if ($ffmpeg) {
        $FfmpegBin = Split-Path -Parent $ffmpeg.Source
    }
}
if (-not $FfmpegBin) {
    throw "FFmpeg not found. Set AXIOM_FFMPEG_BIN or pass -FfmpegBin."
}
$FfmpegBin = (Resolve-Path -LiteralPath $FfmpegBin).Path
foreach ($name in @("ffmpeg.exe", "ffprobe.exe", "ffplay.exe")) {
    $tool = Join-Path $FfmpegBin $name
    if (-not (Test-Path -LiteralPath $tool)) {
        throw "Missing bundled tool: $tool"
    }
    if ((Get-Item -LiteralPath $tool).Length -lt 1MB) {
        throw ("Refusing to bundle a package-manager shim as $name. " +
               "Pass -FfmpegBin with the directory containing the real FFmpeg binaries.")
    }
    if (Test-Path -LiteralPath ($tool + ".shim")) {
        throw ("Refusing to bundle a Chocolatey shim as $name. " +
               "Pass -FfmpegBin with the real FFmpeg bin directory.")
    }
}

$env:AXIOM_FFMPEG_BIN = $FfmpegBin
$env:PYTHONPATH = Join-Path $projectRoot "src"

Push-Location $projectRoot
try {
    & $Python -m PyInstaller packaging\axiompy.spec --noconfirm --clean
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed with exit code $LASTEXITCODE"
    }

    foreach ($name in @(
        "README.md",
        "README.zh-CN.md",
        "CHANGELOG.md",
        "LICENSE"
    )) {
        Copy-Item -LiteralPath (Join-Path $projectRoot $name) -Destination $dist -Force
    }
    New-Item -ItemType Directory -Path (Join-Path $dist "config") -Force | Out-Null

    # The no-FFmpeg package is the same application without the three bundled
    # tools.  Tool lookup then falls back to Settings or PATH at runtime.
    if (Test-Path -LiteralPath $liteDist) {
        $distRoot = Join-Path $projectRoot "dist"
        if (-not $liteDist.StartsWith($distRoot, [StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to replace a directory outside dist: $liteDist"
        }
        Remove-Item -LiteralPath $liteDist -Recurse -Force
    }
    Copy-Item -LiteralPath $dist -Destination $liteDist -Recurse
    foreach ($name in @("ffmpeg.exe", "ffprobe.exe", "ffplay.exe")) {
        $tools = @(
            Get-ChildItem -LiteralPath $liteDist -Recurse -File -Filter $name
        )
        if (-not $tools) {
            throw "Expected to strip $name from the no-FFmpeg build."
        }
        foreach ($tool in $tools) {
            Remove-Item -LiteralPath $tool.FullName -Force
        }
    }
    $remaining = @(
        Get-ChildItem -LiteralPath $liteDist -Recurse -File |
            Where-Object { @("ffmpeg.exe", "ffprobe.exe", "ffplay.exe") -contains $_.Name }
    )
    if ($remaining) {
        throw "No-FFmpeg build still contains: $($remaining.FullName -join ', ')"
    }

    Write-Host "Portable build (with FFmpeg): $dist"
    Write-Host "Portable build (no FFmpeg): $liteDist"
}
finally {
    Pop-Location
}
