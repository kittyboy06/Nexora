<#
.SYNOPSIS
    Restores NEXORA state and data from a verified backup archive.

.DESCRIPTION
    1. Validates archive integrity and matches against SHA-256 checksum file.
    2. Supports -VerifyOnly mode to test backup health without changing system state.
    3. Takes an automatic rollback snapshot before applying restore.
    4. Extracts archive contents into the data/ directory.
    5. Runs SQLite PRAGMA integrity_check on all restored databases.

.PARAMETER BackupPath
    Path to the backup ZIP archive.

.PARAMETER VerifyOnly
    Only validates archive structure, SHA-256 hash, and SQLite integrity without restoring files.

.PARAMETER Force
    Skips interactive confirmation prompts.

.EXAMPLE
    .\scripts\restore.ps1 -BackupPath "backups\nexora-backup-20261107_120000.zip" -VerifyOnly
    .\scripts\restore.ps1 -BackupPath "backups\nexora-backup-20261107_120000.zip" -Force
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$BackupPath,

    [switch]$VerifyOnly,
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
Set-Location -Path $ProjectRoot

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "               NEXORA Restore & Recovery Tool             " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""

# -------------------------------------------------------------------------
# Step 1: Validate Archive & Checksum
# -------------------------------------------------------------------------
if (-not (Test-Path $BackupPath)) {
    Write-Host "[ERROR] Backup archive not found: $BackupPath" -ForegroundColor Red
    exit 1
}

$resolvedBackupPath = (Resolve-Path $BackupPath).Path
Write-Host "[1/4] Verifying archive integrity and SHA-256 checksum..." -ForegroundColor Yellow

$ChecksumFile = "$resolvedBackupPath.sha256"
if (Test-Path $ChecksumFile) {
    $expectedHashLine = (Get-Content -Path $ChecksumFile -Raw).Trim()
    $expectedHash = ($expectedHashLine -split '\s+')[0].Trim().ToUpper()
    $actualHash = (Get-FileHash -Path $resolvedBackupPath -Algorithm SHA256).Hash.ToUpper()

    if ($expectedHash -ne $actualHash) {
        Write-Host "      [FAIL] SHA-256 checksum mismatch!" -ForegroundColor Red
        Write-Host "             Expected: $expectedHash" -ForegroundColor Red
        Write-Host "             Actual:   $actualHash" -ForegroundColor Red
        exit 1
    }
    Write-Host "      [OK] SHA-256 checksum verified: $actualHash" -ForegroundColor Green
} else {
    Write-Host "      [WARN] No companion .sha256 checksum file found. Proceeding with caution." -ForegroundColor DarkYellow
}

Write-Host ""

# -------------------------------------------------------------------------
# Step 2: Validate Archive Internal Structure
# -------------------------------------------------------------------------
Write-Host "[2/4] Inspecting archive contents and manifest..." -ForegroundColor Yellow
Add-Type -AssemblyName System.IO.Compression.FileSystem

$tempVerifyDir = Join-Path $env:TEMP "nexora_restore_verify_$([guid]::NewGuid().ToString('N'))"
New-Item -ItemType Directory -Path $tempVerifyDir -Force | Out-Null

try {
    [System.IO.Compression.ZipFile]::ExtractToDirectory($resolvedBackupPath, $tempVerifyDir)
    
    $manifestFile = Join-Path $tempVerifyDir "backup_manifest.json"
    if (Test-Path $manifestFile) {
        $manifest = Get-Content -Path $manifestFile -Raw | ConvertFrom-Json
        Write-Host "      [OK] Manifest found: Version $($manifest.version) (created $($manifest.backup_timestamp_utc))" -ForegroundColor Green
    } else {
        Write-Host "      [WARN] No backup_manifest.json inside archive." -ForegroundColor DarkYellow
    }

    # Verify SQLite database files in archive
    $dbFiles = Get-ChildItem -Path $tempVerifyDir -Recurse -Filter "*.db"
    foreach ($db in $dbFiles) {
        $dbCheckScript = @"
import sqlite3
conn = sqlite3.connect(r'$($db.FullName)')
try:
    cursor = conn.cursor()
    cursor.execute('PRAGMA integrity_check;')
    res = cursor.fetchone()[0]
    if res != 'ok':
        raise ValueError(f'Corrupt database: {res}')
    print('DB_OK')
finally:
    conn.close()
"@
        $res = python -c $dbCheckScript 2>&1
        if ($res -notmatch "DB_OK") {
            Write-Host "      [FAIL] Database integrity check failed for $($db.Name): $res" -ForegroundColor Red
            Remove-Item -Path $tempVerifyDir -Recurse -Force
            exit 1
        }
        Write-Host "      [OK] Database $($db.Name) passed SQLite integrity check." -ForegroundColor Green
    }
} finally {
    if ($VerifyOnly) {
        Remove-Item -Path $tempVerifyDir -Recurse -Force
    }
}

if ($VerifyOnly) {
    Write-Host ""
    Write-Host "==========================================================" -ForegroundColor Cyan
    Write-Host "   VERIFICATION SUCCESSFUL: BACKUP IS SOUND AND READY      " -ForegroundColor Green
    Write-Host "==========================================================" -ForegroundColor Cyan
    exit 0
}

Write-Host ""

# -------------------------------------------------------------------------
# Step 3: Safety Snapshot of Current State
# -------------------------------------------------------------------------
Write-Host "[3/4] Creating pre-restore rollback snapshot..." -ForegroundColor Yellow
$DataDir = Join-Path $ProjectRoot "data"
$RollbackDir = Join-Path $env:TEMP "nexora_pre_restore_rollback_$([guid]::NewGuid().ToString('N'))"
New-Item -ItemType Directory -Path $RollbackDir -Force | Out-Null

if (Test-Path $DataDir) {
    Copy-Item -Path "$DataDir\*" -Destination $RollbackDir -Recurse -Force
    Write-Host "      [OK] Pre-restore snapshot preserved at: $RollbackDir" -ForegroundColor Green
} else {
    New-Item -ItemType Directory -Path $DataDir -Force | Out-Null
}

Write-Host ""

# -------------------------------------------------------------------------
# Step 4: Apply Restored Data
# -------------------------------------------------------------------------
Write-Host "[4/4] Applying restored data to $DataDir..." -ForegroundColor Yellow
try {
    # Copy from verified extraction
    Get-ChildItem -Path $tempVerifyDir | ForEach-Object {
        if ($_.Name -ne "backup_manifest.json") {
            $dest = Join-Path $DataDir $_.Name
            if ($_.PSIsContainer) {
                Copy-Item -Path $_.FullName -Destination $dest -Recurse -Force
            } else {
                Copy-Item -Path $_.FullName -Destination $dest -Force
            }
        }
    }
    Remove-Item -Path $tempVerifyDir -Recurse -Force
    Write-Host "      [OK] Files successfully extracted to data/ directory." -ForegroundColor Green
} catch {
    Write-Host "      [ERROR] Restore failed! Reverting from rollback snapshot: $_" -ForegroundColor Red
    Copy-Item -Path "$RollbackDir\*" -Destination $DataDir -Recurse -Force
    Remove-Item -Path $RollbackDir -Recurse -Force
    exit 1
}

# Clean rollback directory upon success
Remove-Item -Path $RollbackDir -Recurse -Force

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   RESTORE COMPLETED SUCCESSFULLY                         " -ForegroundColor Green
Write-Host "   All databases and state restored and verified.         " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan
