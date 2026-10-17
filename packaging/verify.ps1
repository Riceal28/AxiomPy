param(
    [string]$Package = ""
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not $Package) {
    $Package = Join-Path $projectRoot "dist\AxiomPy"
}

$exe = Join-Path $Package "AxiomPy.exe"
if (-not (Test-Path -LiteralPath $exe)) {
    throw "AxiomPy.exe not found in $Package"
}

$tools = @("ffmpeg.exe", "ffprobe.exe", "ffplay.exe")
$found = Get-ChildItem -LiteralPath $Package -Recurse -File |
    Where-Object { $tools -contains $_.Name } |
    Select-Object -ExpandProperty FullName

foreach ($name in $tools) {
    if (-not ($found | Where-Object { (Split-Path -Leaf $_) -eq $name })) {
        throw "Bundled tool missing: $name"
    }
}

$process = Start-Process -FilePath $exe -PassThru -WindowStyle Hidden
try {
    Start-Sleep -Seconds 5
    if ($process.HasExited) {
        throw "AxiomPy exited during startup with code $($process.ExitCode)"
    }
    Write-Host "AxiomPy started successfully (PID $($process.Id))"
}
finally {
    if (-not $process.HasExited) {
        Stop-Process -Id $process.Id -Force
    }
}
