<#
.SYNOPSIS
    Exports a sanitized diagnostics and troubleshooting support bundle.

.DESCRIPTION
    Collects system specifications, diagnostics report, component inventory, and recent
    scrubbed logs into a timestamped ZIP bundle. All secrets, tokens, API keys,
    quarantine files, and user prompts are strictly redacted.

.PARAMETER OutFile
    Optional target path for the generated diagnostics ZIP bundle.

.EXAMPLE
    .\scripts\export-diagnostics.ps1
    .\scripts\export-diagnostics.ps1 -OutFile "C:\temp\nexora-diag.zip"
#>

param(
    [string]$OutFile
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$pythonExe = "python"
if (Test-Path "$repoRoot\.venv\Scripts\python.exe") {
    $pythonExe = "$repoRoot\.venv\Scripts\python.exe"
}

$argsList = @("-m", "backend.app.cli.doctor", "--export")
if ($OutFile) {
    $argsList += @("--out", $OutFile)
}

& $pythonExe $argsList
exit $LASTEXITCODE
