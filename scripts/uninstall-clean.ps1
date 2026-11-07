<#
.SYNOPSIS
    Cleans or resets NEXORA state, caches, and runtime data.

.DESCRIPTION
    Supports two operating modes:
    - DataOnly: Purges state, logs, tasks, memories, and schedules inside data/. Preserves code, git, and configuration.
    - FactoryReset: Performs full sanitization. Cleans data/, build artifacts (bin/obj), diagnostics, and test caches.

.PARAMETER Mode
    Reset mode: 'DataOnly' or 'FactoryReset'. Default is 'DataOnly'.

.PARAMETER Force
    Skips interactive confirmation prompts.

.EXAMPLE
    .\scripts\uninstall-clean.ps1 -Mode DataOnly
    .\scripts\uninstall-clean.ps1 -Mode FactoryReset -Force
#>

[CmdletBinding()]
param(
    [ValidateSet("DataOnly", "FactoryReset")]
    [string]$Mode = "DataOnly",

    [switch]$Force
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
Set-Location -Path $ProjectRoot

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "               NEXORA System Clean & Reset Tool           " -ForegroundColor Cyan
Write-Host "               Target Mode: $Mode                         " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""

if (-not $Force) {
    Write-Host "[WARNING] This action will permanently delete local state for mode: $Mode." -ForegroundColor Yellow
    $response = Read-Host "Are you sure you wish to proceed? (Type 'YES' to confirm)"
    if ($response -ne "YES") {
        Write-Host "Operation cancelled by operator." -ForegroundColor DarkYellow
        exit 0
    }
}

$DataDir = Join-Path $ProjectRoot "data"

# -------------------------------------------------------------------------
# Mode: DataOnly
# -------------------------------------------------------------------------
Write-Host "[1/2] Purging runtime state in $DataDir..." -ForegroundColor Yellow
if (Test-Path $DataDir) {
    Get-ChildItem -Path $DataDir | ForEach-Object {
        try {
            Remove-Item -Path $_.FullName -Recurse -Force
            Write-Host "      [DELETED] $($_.Name)" -ForegroundColor Green
        } catch {
            Write-Host "      [WARN] Could not delete $($_.FullName): $_" -ForegroundColor DarkYellow
        }
    }
} else {
    Write-Host "      [INFO] Data directory does not exist. Nothing to purge." -ForegroundColor Green
}

# -------------------------------------------------------------------------
# Mode: FactoryReset
# -------------------------------------------------------------------------
if ($Mode -eq "FactoryReset") {
    Write-Host ""
    Write-Host "[2/2] Performing Factory Reset (purging build artifacts, caches, and diagnostics)..." -ForegroundColor Yellow

    # Diagnostics and temporary backups
    $dirsToPurge = @(
        (Join-Path $ProjectRoot "diagnostics"),
        (Join-Path $ProjectRoot ".pytest_cache")
    )

    foreach ($d in $dirsToPurge) {
        if (Test-Path $d) {
            Remove-Item -Path $d -Recurse -Force -ErrorAction SilentlyContinue
            Write-Host "      [PURGED] $d" -ForegroundColor Green
        }
    }

    # Clean __pycache__
    Get-ChildItem -Path $ProjectRoot -Recurse -Filter "__pycache__" -Directory -ErrorAction SilentlyContinue | ForEach-Object {
        Remove-Item -Path $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
    }
    Write-Host "      [PURGED] Python __pycache__ directories." -ForegroundColor Green

    # Clean .NET bin and obj
    $desktopDir = Join-Path $ProjectRoot "desktop"
    if (Test-Path $desktopDir) {
        Get-ChildItem -Path $desktopDir -Recurse -Include "bin", "obj" -Directory -ErrorAction SilentlyContinue | ForEach-Object {
            Remove-Item -Path $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
        }
        Write-Host "      [PURGED] .NET bin and obj build artifacts." -ForegroundColor Green
    }
} else {
    Write-Host ""
    Write-Host "[2/2] Factory reset skipped in DataOnly mode." -ForegroundColor Green
}

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   CLEANUP FINISHED: Mode $Mode Complete                  " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan
