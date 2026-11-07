<#
.SYNOPSIS
    Creates an atomic, consistent backup archive of NEXORA state and data.

.DESCRIPTION
    1. Flushes and truncates SQLite Write-Ahead Logs (WAL) for memory and scheduler databases.
    2. Packages tasks, memory, schedules, MCP configurations, skills, and model profiles into a ZIP archive.
    3. Excludes ephemeral logs and quarantine folders.
    4. Computes and generates a SHA-256 checksum file alongside the archive.

.PARAMETER BackupPath
    Custom destination path for the backup ZIP. If omitted, saves to backups/nexora-backup-TIMESTAMP.zip.

.EXAMPLE
    .\scripts\backup.ps1
    .\scripts\backup.ps1 -BackupPath "D:\Backups\nexora-pre-upgrade.zip"
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [string]$BackupPath
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
Set-Location -Path $ProjectRoot

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "               NEXORA Atomic Backup Utility               " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""

$DataDir = Join-Path $ProjectRoot "data"
$BackupsDir = Join-Path $ProjectRoot "backups"
if (-not (Test-Path $BackupsDir)) {
    New-Item -ItemType Directory -Path $BackupsDir -Force | Out-Null
}

$Timestamp = (Get-Date).ToUniversalTime().ToString("yyyyMMdd_HHmmss")
if (-not $BackupPath) {
    $BackupPath = Join-Path $BackupsDir "nexora-backup-$Timestamp.zip"
} else {
    $BackupDir = Split-Path -Parent $BackupPath
    if ($BackupDir -and -not (Test-Path $BackupDir)) {
        New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
    }
}

$ChecksumPath = "$BackupPath.sha256"

# -------------------------------------------------------------------------
# Step 1: Flushes & Checkpoints SQLite WAL Databases
# -------------------------------------------------------------------------
Write-Host "[1/4] Checkpointing SQLite WAL logs (atomic truncate)..." -ForegroundColor Yellow
$checkpointScript = @"
import sqlite3
from pathlib import Path

db_targets = [
    Path('data/memory/nexora_memory.db'),
    Path('data/scheduler/nexora_scheduler.db'),
]

for db in db_targets:
    if db.exists():
        conn = sqlite3.connect(str(db))
        try:
            conn.execute('PRAGMA wal_checkpoint(TRUNCATE);')
            print(f'Checkpointed: {db}')
        finally:
            conn.close()
"@

try {
    python -c $checkpointScript
    Write-Host "      [OK] SQLite WAL logs truncated successfully." -ForegroundColor Green
} catch {
    Write-Host "      [WARN] SQLite checkpoint threw warning: $_" -ForegroundColor DarkYellow
}

Write-Host ""

# -------------------------------------------------------------------------
# Step 2: Assemble Backup Payload Staging
# -------------------------------------------------------------------------
Write-Host "[2/4] Assembling state data into archive..." -ForegroundColor Yellow
$stagingDir = Join-Path $env:TEMP "nexora_backup_staging_$Timestamp"
if (Test-Path $stagingDir) { Remove-Item -Path $stagingDir -Recurse -Force }
New-Item -ItemType Directory -Path $stagingDir -Force | Out-Null

$itemsToInclude = @(
    "memory",
    "scheduler",
    "tasks",
    "skills",
    "mcp",
    "model_profiles.json",
    "workspace"
)

$copiedCount = 0
foreach ($item in $itemsToInclude) {
    $srcPath = Join-Path $DataDir $item
    if (Test-Path $srcPath) {
        $destPath = Join-Path $stagingDir $item
        if ((Get-Item $srcPath).PSIsContainer) {
            Copy-Item -Path $srcPath -Destination $destPath -Recurse -Force
        } else {
            Copy-Item -Path $srcPath -Destination $destPath -Force
        }
        $copiedCount++
    }
}

# Write backup metadata manifest
$manifest = @{
    backup_timestamp_utc = (Get-Date).ToUniversalTime().ToString("o")
    version = "1.0.0"
    machine = $env:COMPUTERNAME
    user = $env:USERNAME
    items_backed_up = $copiedCount
} | ConvertTo-Json -Depth 3

Set-Content -Path (Join-Path $stagingDir "backup_manifest.json") -Value $manifest -Encoding utf8

# -------------------------------------------------------------------------
# Step 3: Compress to ZIP Archive
# -------------------------------------------------------------------------
Write-Host "[3/4] Compressing to $BackupPath..." -ForegroundColor Yellow
if (Test-Path $BackupPath) {
    Remove-Item -Path $BackupPath -Force
}

Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory($stagingDir, $BackupPath)
Remove-Item -Path $stagingDir -Recurse -Force

$zipFileInfo = Get-Item $BackupPath
$sizeKb = [math]::Round($zipFileInfo.Length / 1024, 2)
Write-Host "      [OK] Archive created ($sizeKb KB)." -ForegroundColor Green
Write-Host ""

# -------------------------------------------------------------------------
# Step 4: Compute SHA-256 Checksum
# -------------------------------------------------------------------------
Write-Host "[4/4] Computing SHA-256 checksum..." -ForegroundColor Yellow
$hashResult = Get-FileHash -Path $BackupPath -Algorithm SHA256
$hashString = "$($hashResult.Hash)  $([System.IO.Path]::GetFileName($BackupPath))"
Set-Content -Path $ChecksumPath -Value $hashString -Encoding utf8

Write-Host "      [OK] SHA-256: $($hashResult.Hash)" -ForegroundColor Green
Write-Host "      [OK] Saved checksum file to: $ChecksumPath" -ForegroundColor Green
Write-Host ""

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   BACKUP COMPLETED SUCCESSFULLY                          " -ForegroundColor Green
Write-Host "   Destination: $BackupPath                               " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan
