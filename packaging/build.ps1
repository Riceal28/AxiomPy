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
    if (-not (Test-Path -LiteralPath (Join-Path $FfmpegBin $name))) {
        throw "Missing bundled tool: $(Join-Path $FfmpegBin $name)"
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

    Copy-Item -LiteralPath (Join-Path $projectRoot "README.md") -Destination $dist -Force
    Copy-Item -LiteralPath (Join-Path $projectRoot "LICENSE") -Destination $dist -Force
    New-Item -ItemType Directory -Path (Join-Path $dist "config") -Force | Out-Null
    Write-Host "Portable build: $dist"
}
finally {
    Pop-Location
}
