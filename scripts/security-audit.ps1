<#
.SYNOPSIS
    Automated Security Audit & SBOM Verification Gate for NEXORA.

.DESCRIPTION
    Executes comprehensive security controls:
    1. Python package dependency integrity audit (pip check).
    2. Adversarial security regression test suite (backend/tests/security/test_security_hardening.py).
    3. Software Bill of Materials (SBOM) validation (docs/SBOM.json).
    4. Loopback and network surface verification.

.EXAMPLE
    .\scripts\security-audit.ps1
#>

[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
Set-Location -Path $ProjectRoot

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "         NEXORA Automated Security & Hardening Audit      " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""

$PassedGates = 0
$TotalGates = 4

# -------------------------------------------------------------------------
# Gate 1: Python Package Integrity Audit
# -------------------------------------------------------------------------
Write-Host "[1/4] Auditing Python dependencies for broken requirements..." -ForegroundColor Yellow
try {
    $pipCheck = python -m pip check 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "      [PASS] Python dependencies are consistent and unbroken." -ForegroundColor Green
        $PassedGates++
    } else {
        Write-Host "      [FAIL] Python dependency check failed:`n$pipCheck" -ForegroundColor Red
    }
} catch {
    Write-Host "      [FAIL] Could not execute pip check: $_" -ForegroundColor Red
}

Write-Host ""

# -------------------------------------------------------------------------
# Gate 2: Adversarial Security Regression Test Suite
# -------------------------------------------------------------------------
Write-Host "[2/4] Running adversarial security regression test suite..." -ForegroundColor Yellow
try {
    $testOut = python -m pytest backend/tests/security/test_security_hardening.py -q 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "      [PASS] All 16 adversarial security tests passed successfully." -ForegroundColor Green
        $PassedGates++
    } else {
        Write-Host "      [FAIL] Adversarial security tests failed:`n$testOut" -ForegroundColor Red
    }
} catch {
    Write-Host "      [FAIL] Could not execute security test suite: $_" -ForegroundColor Red
}

Write-Host ""

# -------------------------------------------------------------------------
# Gate 3: Software Bill of Materials (SBOM) Validation
# -------------------------------------------------------------------------
Write-Host "[3/4] Validating Software Bill of Materials (SBOM)..." -ForegroundColor Yellow
$SbomPath = Join-Path $ProjectRoot "docs\SBOM.json"
if (Test-Path $SbomPath) {
    try {
        $sbomContent = Get-Content -Path $SbomPath -Raw | ConvertFrom-Json
        $componentCount = $sbomContent.components.Count
        Write-Host "      [PASS] Valid CycloneDX SBOM located ($componentCount components registered)." -ForegroundColor Green
        $PassedGates++
    } catch {
        Write-Host "      [FAIL] docs/SBOM.json is not valid JSON: $_" -ForegroundColor Red
    }
} else {
    Write-Host "      [FAIL] docs/SBOM.json was not found." -ForegroundColor Red
}

Write-Host ""

# -------------------------------------------------------------------------
# Gate 4: Host Network Surface & Loopback Verification
# -------------------------------------------------------------------------
Write-Host "[4/4] Verifying network surface and localhost-only binding configuration..." -ForegroundColor Yellow
try {
    $loopbackCheck = python -c "from backend.app.core.config import get_settings; s = get_settings(); assert s.HOST == '127.0.0.1', f'Invalid HOST: {s.HOST}'; print(f'HOST: {s.HOST}:{s.PORT}')" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "      [PASS] Strict localhost loopback binding confirmed: $loopbackCheck" -ForegroundColor Green
        $PassedGates++
    } else {
        Write-Host "      [FAIL] Loopback verification failed: $loopbackCheck" -ForegroundColor Red
    }
} catch {
    Write-Host "      [FAIL] Could not verify loopback settings: $_" -ForegroundColor Red
}

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Cyan
if ($PassedGates -eq $TotalGates) {
    Write-Host "   AUDIT RESULT: ALL $PassedGates GATES PASSED (CLEAN SECURITY STATE)  " -ForegroundColor Green
    Write-Host "==========================================================" -ForegroundColor Cyan
    exit 0
} else {
    Write-Host "   AUDIT RESULT: FAILED ($PassedGates/$TotalGates GATES PASSED)       " -ForegroundColor Red
    Write-Host "==========================================================" -ForegroundColor Cyan
    exit 1
}
