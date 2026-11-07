<#
.SYNOPSIS
    Tiered Test Runner for NEXORA Backend and Desktop Host.

.DESCRIPTION
    Runs the complete hermetic test gate:
    1. Python Backend Test Suite (300+ tests including security hardening).
    2. Desktop .NET Unit Tests (49 xUnit tests).
    3. WinUI 3 Desktop Build Verification (x64).
    4. [Optional] Live local Ollama smoke suite if -IncludeLive is specified.

.PARAMETER IncludeLive
    Opt-in switch to execute live local Ollama connectivity and model smoke tests.

.EXAMPLE
    .\scripts\run-all-tests.ps1
    .\scripts\run-all-tests.ps1 -IncludeLive
#>

[CmdletBinding()]
param(
    [switch]$IncludeLive
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
Set-Location -Path $ProjectRoot

$stopwatch = [System.Diagnostics.Stopwatch]::StartNew()

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "              NEXORA Automated Test Runner                " -ForegroundColor Cyan
if ($IncludeLive) {
    Write-Host "         Mode: Hermetic Gate + Live Smoke (-IncludeLive)  " -ForegroundColor Magenta
} else {
    Write-Host "         Mode: Offline Hermetic Gate (<= 60s Target)      " -ForegroundColor Green
}
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""

# Resolve dotnet executable
$DotnetCmd = "dotnet"
$customDotnet = "$env:LOCALAPPDATA\Microsoft\dotnet\dotnet.exe"
if (Test-Path $customDotnet) {
    $DotnetCmd = $customDotnet
}

$FailedSteps = @()

# -------------------------------------------------------------------------
# Step 1: Python Backend Test Suite
# -------------------------------------------------------------------------
Write-Host "[1/3] Running Python Backend Test Suite..." -ForegroundColor Yellow
if ($IncludeLive) {
    $env:NEXORA_RUN_LIVE_TESTS = "1"
} else {
    $env:NEXORA_RUN_LIVE_TESTS = "0"
}

try {
    python -m pytest backend/tests -v
    if ($LASTEXITCODE -ne 0) {
        $FailedSteps += "Python Backend Tests"
    } else {
        Write-Host "      [PASS] Python Backend Tests passed." -ForegroundColor Green
    }
} catch {
    $FailedSteps += "Python Backend Tests ($($_))"
}

Write-Host ""

# -------------------------------------------------------------------------
# Step 2: Desktop .NET Unit Tests
# -------------------------------------------------------------------------
Write-Host "[2/3] Running Desktop .NET Unit Tests..." -ForegroundColor Yellow
$DesktopTestsProject = Join-Path $ProjectRoot "desktop\Nexora.Desktop.Tests\Nexora.Desktop.Tests.csproj"

try {
    & $DotnetCmd test $DesktopTestsProject --verbosity normal --no-restore
    if ($LASTEXITCODE -ne 0) {
        # Retry with restore if needed
        & $DotnetCmd test $DesktopTestsProject --verbosity normal
        if ($LASTEXITCODE -ne 0) {
            $FailedSteps += "Desktop .NET Unit Tests"
        } else {
            Write-Host "      [PASS] Desktop .NET Unit Tests passed." -ForegroundColor Green
        }
    } else {
        Write-Host "      [PASS] Desktop .NET Unit Tests passed." -ForegroundColor Green
    }
} catch {
    $FailedSteps += "Desktop .NET Unit Tests ($($_))"
}

Write-Host ""

# -------------------------------------------------------------------------
# Step 3: WinUI 3 Desktop Build Gate
# -------------------------------------------------------------------------
Write-Host "[3/3] Building WinUI 3 Desktop Application (x64 Debug)..." -ForegroundColor Yellow
$DesktopAppProject = Join-Path $ProjectRoot "desktop\Nexora.Desktop\Nexora.Desktop.csproj"

try {
    & $DotnetCmd build $DesktopAppProject -c Debug -p:Platform=x64 --verbosity minimal
    if ($LASTEXITCODE -ne 0) {
        $FailedSteps += "WinUI 3 Desktop Build"
    } else {
        Write-Host "      [PASS] WinUI 3 Desktop Application built successfully." -ForegroundColor Green
    }
} catch {
    $FailedSteps += "WinUI 3 Desktop Build ($($_))"
}

Write-Host ""

# -------------------------------------------------------------------------
# Final Summary
# -------------------------------------------------------------------------
$stopwatch.Stop()
$elapsedSec = [math]::Round($stopwatch.Elapsed.TotalSeconds, 2)

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "                     TEST RUN SUMMARY                     " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "Total Execution Time: $elapsedSec seconds"

if ($FailedSteps.Count -eq 0) {
    Write-Host "STATUS: ALL TEST GATES PASSED (HERMETIC INTEGRITY CONFIRMED)" -ForegroundColor Green
    Write-Host "==========================================================" -ForegroundColor Cyan
    exit 0
} else {
    Write-Host "STATUS: FAILED" -ForegroundColor Red
    Write-Host "Failed Steps: $($FailedSteps -join ', ')" -ForegroundColor Red
    Write-Host "==========================================================" -ForegroundColor Cyan
    exit 1
}
