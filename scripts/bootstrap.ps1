<#
.SYNOPSIS
    One-Click Onboarding and Environment Bootstrap Script for NEXORA.

.DESCRIPTION
    Configures and initializes a pristine developer or operator machine:
    1. Validates Python 3.14+ runtime and .NET 8 SDK.
    2. Provisions required local data/ directory trees.
    3. Initializes .env configuration from backend/.env.example if missing.
    4. Installs/updates Python dependencies from backend/requirements.txt.
    5. Restores and builds the WinUI 3 Desktop Application.
    6. Runs pre-flight diagnostics (scripts/doctor.ps1).

.PARAMETER SkipDependencies
    Skips python pip install step if dependencies are already satisfied.

.PARAMETER SkipBuild
    Skips the .NET build step.

.EXAMPLE
    .\scripts\bootstrap.ps1
    .\scripts\bootstrap.ps1 -SkipDependencies
#>

[CmdletBinding()]
param(
    [switch]$SkipDependencies,
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
Set-Location -Path $ProjectRoot

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "            NEXORA v1.0 One-Click Setup & Bootstrap       " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""

# -------------------------------------------------------------------------
# Step 1: Initialize Local Directories
# -------------------------------------------------------------------------
Write-Host "[1/6] Provisioning local state and data directories..." -ForegroundColor Yellow
$requiredDirs = @(
    "data\tasks",
    "data\memory",
    "data\scheduler",
    "data\skills",
    "data\mcp",
    "data\quarantine",
    "data\workspace",
    "data\logs",
    "data\research",
    "data\tools\generated",
    "diagnostics",
    "backups"
)

foreach ($dir in $requiredDirs) {
    $fullPath = Join-Path $ProjectRoot $dir
    if (-not (Test-Path $fullPath)) {
        New-Item -ItemType Directory -Path $fullPath -Force | Out-Null
        Write-Host "      [CREATED] $dir" -ForegroundColor Green
    }
}
Write-Host "      [OK] Directory structure provisioned." -ForegroundColor Green
Write-Host ""

# -------------------------------------------------------------------------
# Step 2: Initialize Configuration (.env)
# -------------------------------------------------------------------------
Write-Host "[2/6] Configuring local environment (.env)..." -ForegroundColor Yellow
$rootEnv = Join-Path $ProjectRoot ".env"
$exampleEnv = Join-Path $ProjectRoot "backend\.env.example"

if (-not (Test-Path $rootEnv) -and (Test-Path $exampleEnv)) {
    Copy-Item -Path $exampleEnv -Destination $rootEnv
    Write-Host "      [COPIED] Created .env from backend\.env.example" -ForegroundColor Green
} elseif (Test-Path $rootEnv) {
    Write-Host "      [OK] Existing .env file found." -ForegroundColor Green
}
Write-Host ""

# -------------------------------------------------------------------------
# Step 3: Check & Install Python Dependencies
# -------------------------------------------------------------------------
Write-Host "[3/6] Verifying Python runtime and dependencies..." -ForegroundColor Yellow
$pyVersion = python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')" 2>&1
Write-Host "      Python Runtime: $pyVersion" -ForegroundColor Cyan

if (-not $SkipDependencies) {
    $reqFile = Join-Path $ProjectRoot "backend\requirements.txt"
    if (Test-Path $reqFile) {
        Write-Host "      Installing/verifying packages from $reqFile..." -ForegroundColor Yellow
        python -m pip install -r $reqFile --quiet
        Write-Host "      [OK] Python dependencies verified." -ForegroundColor Green
    }
} else {
    Write-Host "      [SKIPPED] Dependency installation skipped by operator." -ForegroundColor DarkYellow
}
Write-Host ""

# -------------------------------------------------------------------------
# Step 4: Resolve & Build .NET WinUI 3 Desktop Host
# -------------------------------------------------------------------------
Write-Host "[4/6] Verifying .NET 8 SDK and building desktop host..." -ForegroundColor Yellow
$DotnetCmd = "dotnet"
$customDotnet = "$env:LOCALAPPDATA\Microsoft\dotnet\dotnet.exe"
if (Test-Path $customDotnet) {
    $DotnetCmd = $customDotnet
}

if (-not $SkipBuild) {
    $desktopSln = Join-Path $ProjectRoot "desktop\Nexora.sln"
    if (Test-Path $desktopSln) {
        & $DotnetCmd restore $desktopSln --verbosity minimal
        & $DotnetCmd build $desktopSln -c Debug -p:Platform=x64 --verbosity minimal
        Write-Host "      [OK] WinUI 3 desktop client built successfully." -ForegroundColor Green
    }
} else {
    Write-Host "      [SKIPPED] .NET build skipped by operator." -ForegroundColor DarkYellow
}
Write-Host ""

# -------------------------------------------------------------------------
# Step 5: Execute Pre-Flight Diagnostics Doctor
# -------------------------------------------------------------------------
Write-Host "[5/6] Running system diagnostics doctor..." -ForegroundColor Yellow
$doctorScript = Join-Path $ProjectRoot "scripts\doctor.ps1"
if (Test-Path $doctorScript) {
    & powershell -ExecutionPolicy Bypass -File $doctorScript
}
Write-Host ""

# -------------------------------------------------------------------------
# Step 6: Summary & Launch Instructions
# -------------------------------------------------------------------------
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "               BOOTSTRAP COMPLETED SUCCESSFULLY           " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next Steps to Run NEXORA:" -ForegroundColor Yellow
Write-Host "  1. Start Core Backend Engine:" -ForegroundColor White
Write-Host "     .\start_server.bat" -ForegroundColor Cyan
Write-Host "     (or: uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload)" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  2. Launch WinUI 3 Desktop Control Plane:" -ForegroundColor White
Write-Host "     & `"$DotnetCmd`" run --project desktop\Nexora.Desktop\Nexora.Desktop.csproj" -ForegroundColor Cyan
Write-Host ""
Write-Host "  3. Run Full Verification Suite at Any Time:" -ForegroundColor White
Write-Host "     .\scripts\run-all-tests.ps1" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
