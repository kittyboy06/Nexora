# NEXORA Standalone Executable Packaging Automation Script
# Builds both Python backend engine and WinUI 3 desktop into a single self-contained Nexora.exe

[CmdletBinding()]
param(
    [switch]$SkipBackendFreeze,
    [string]$Configuration = "Release"
)

$ErrorActionPreference = "Stop"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "       NEXORA - Standalone Executable Packaging Build       " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

$repoRoot = (Get-Item $PSScriptRoot).Parent.FullName
Set-Location $repoRoot

# 1. Resolve .NET SDK
$dotnetCmd = "dotnet"
if (-not (Get-Command "dotnet" -ErrorAction SilentlyContinue)) {
    $dotnetCandidates = @(
        "$env:LOCALAPPDATA\Microsoft\dotnet\dotnet.exe",
        "C:\Program Files\dotnet\dotnet.exe"
    )
    foreach ($cand in $dotnetCandidates) {
        if (Test-Path $cand) {
            $dotnetCmd = $cand
            break
        }
    }
}
Write-Host "[1/4] Checking prerequisites..." -ForegroundColor Yellow
Write-Host "  .NET CLI: $dotnetCmd"

# 2. Frozen Backend Server Build
$resourcesDir = Join-Path $repoRoot "desktop\Nexora.Desktop\Resources"
$distServerDir = Join-Path $repoRoot "dist\server"
New-Item -ItemType Directory -Force -Path $resourcesDir, $distServerDir | Out-Null

$serverExe = Join-Path $resourcesDir "nexora-server.exe"

if (-not $SkipBackendFreeze) {
    Write-Host "[2/4] Freezing Python backend into single-file executable..." -ForegroundColor Yellow
    python -m PyInstaller --noconfirm --clean --onefile `
        --name nexora-server `
        --paths . `
        --collect-submodules backend `
        --collect-submodules uvicorn `
        --collect-submodules fastapi `
        --collect-submodules starlette `
        --collect-submodules pydantic `
        --collect-submodules pydantic_settings `
        --add-data "data/model_profiles.json;data" `
        --distpath $distServerDir `
        backend/server_entrypoint.py

    Copy-Item (Join-Path $distServerDir "nexora-server.exe") $serverExe -Force
    Write-Host "  Frozen backend built: $serverExe ($([math]::Round((Get-Item $serverExe).Length / 1MB, 2)) MB)" -ForegroundColor Green
} else {
    Write-Host "[2/4] Skipping backend freeze (using existing $serverExe)..." -ForegroundColor Yellow
}

if (-not (Test-Path $serverExe)) {
    Write-Error "Backend server executable not found at $serverExe. Aborting build."
}

# 3. Publish Single-File Standalone Executable
Write-Host "[3/4] Publishing standalone WinUI 3 Desktop single-file binary..." -ForegroundColor Yellow
$desktopProj = Join-Path $repoRoot "desktop\Nexora.Desktop\Nexora.Desktop.csproj"
$distStandalone = Join-Path $repoRoot "dist\standalone"

& $dotnetCmd publish $desktopProj `
    -c $Configuration `
    -p:Platform=x64 `
    -r win-x64 `
    -p:PublishSingleFile=true `
    -p:SelfContained=true `
    -p:IncludeNativeLibrariesForSelfExtract=true `
    -o $distStandalone

$finalExe = Join-Path $distStandalone "Nexora.exe"
if (-not (Test-Path $finalExe)) {
    # If named Nexora.Desktop.exe, copy to Nexora.exe
    $desktopExe = Join-Path $distStandalone "Nexora.Desktop.exe"
    if (Test-Path $desktopExe) {
        Copy-Item $desktopExe $finalExe -Force
    }
}

# 4. Final Validation & Output Summary
Write-Host "[4/4] Finalizing and computing binary verification..." -ForegroundColor Yellow
if (Test-Path $finalExe) {
    $item = Get-Item $finalExe
    $hash = (Get-FileHash $finalExe -Algorithm SHA256).Hash
    $sizeMb = [math]::Round($item.Length / 1MB, 2)

    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host "  BUILD SUCCESSFUL - STANDALONE EXECUTABLE READY" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host "  Output Binary : $($item.FullName)" -ForegroundColor White
    Write-Host "  File Size     : $sizeMb MB" -ForegroundColor White
    Write-Host "  SHA256 Hash   : $hash" -ForegroundColor White
    Write-Host ""
    Write-Host "  This binary is 100% self-contained and requires no external" -ForegroundColor Cyan
    Write-Host "  Python, .NET runtime, or web server dependencies." -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor Green
} else {
    Write-Error "Failed to produce final executable at $finalExe"
}
