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
    $tool = $found | Where-Object { (Split-Path -Leaf $_) -eq $name } |
        Select-Object -First 1
    if (-not $tool) {
        throw "Bundled tool missing: $name"
    }
    if ((Get-Item -LiteralPath $tool).Length -lt 1MB) {
        throw "Bundled tool is a shim, not a real executable: $tool"
    }
    & $tool -version *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "Bundled tool failed to start: $tool (exit $LASTEXITCODE)"
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
