<#
.SYNOPSIS
    Runs the NEXORA Pre-Flight Diagnostics Doctor.

.DESCRIPTION
    Validates Python runtime, .NET 8 SDK, Ollama connectivity, Windows Job Objects,
    and SQLite WAL storage permissions.

.PARAMETER Json
    Outputs structured JSON instead of human-readable report.

.EXAMPLE
    .\scripts\doctor.ps1
    .\scripts\doctor.ps1 -Json
#>

param(
    [switch]$Json
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$pythonExe = "python"
if (Test-Path "$repoRoot\.venv\Scripts\python.exe") {
    $pythonExe = "$repoRoot\.venv\Scripts\python.exe"
}

$argsList = @("-m", "backend.app.cli.doctor")
if ($Json) {
    $argsList += "--json"
}

& $pythonExe $argsList
exit $LASTEXITCODE
