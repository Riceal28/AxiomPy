param(
    [string]$FfmpegBin = $env:AXIOM_FFMPEG_BIN,
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$dist = Join-Path $projectRoot "dist\AxiomPy"

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
    Write-Host "Portable build: $dist"
}
finally {
    Pop-Location
}
