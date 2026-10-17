param(
    [string]$FfmpegBin = "F:\ffmpeg-8.0.1\bin",
    [string]$Python = "D:\python\python.exe"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$dist = Join-Path $projectRoot "dist\AxiomPy"
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
