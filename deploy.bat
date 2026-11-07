@echo off
setlocal enabledelayedexpansion

title NEXORA Desktop Control Plane - Build and Deploy

echo.
echo ======================================================================
echo           NEXORA Native Desktop Control Plane - Deploy Tool
echo ======================================================================
echo.

:: 1. Detect .NET SDK
set "DOTNET_CMD="

where dotnet >nul 2>&1
if %ERRORLEVEL% equ 0 (
    set "DOTNET_CMD=dotnet"
) else if exist "%LOCALAPPDATA%\Microsoft\dotnet\dotnet.exe" (
    set "DOTNET_CMD=%LOCALAPPDATA%\Microsoft\dotnet\dotnet.exe"
) else if exist "C:\Program Files\dotnet\dotnet.exe" (
    set "DOTNET_CMD=C:\Program Files\dotnet\dotnet.exe"
)

if "%DOTNET_CMD%"=="" (
    echo [ERROR] .NET 8 SDK was not found on your system!
    echo Please install .NET 8 SDK or run:
    echo   powershell -Command "& {Invoke-WebRequest -UseBasicParsing 'https://dot.net/v1/dotnet-install.ps1' -OutFile 'dotnet-install.ps1'; .\dotnet-install.ps1 -Channel 8.0}"
    echo.
    pause
    exit /b 1
)

echo [INFO] Using .NET CLI: "%DOTNET_CMD%"
"%DOTNET_CMD%" --version
echo.

:: 2. Configure Paths and Arguments
set "ROOT_DIR=%~dp0"
set "PROJECT_PATH=%ROOT_DIR%desktop\Nexora.Desktop\Nexora.Desktop.csproj"
set "OUTPUT_DIR=%ROOT_DIR%dist\Nexora"
set "SERVER_OUTPUT_DIR=%OUTPUT_DIR%\server"
set "SELF_CONTAINED=true"
set "AUTO_RUN=0"

:: Parse arguments
:parse_args
if "%~1"=="" goto after_args
if /i "%~1"=="run" set "AUTO_RUN=1"
if /i "%~1"=="--run" set "AUTO_RUN=1"
if /i "%~1"=="-r" set "AUTO_RUN=1"
if /i "%~1"=="--self-contained" set "SELF_CONTAINED=true"
if /i "%~1"=="--framework-dependent" set "SELF_CONTAINED=false"
if /i "%~1"=="--clean" (
    if exist "%OUTPUT_DIR%" (
        echo [INFO] Cleaning previous output directory...
        rmdir /s /q "%OUTPUT_DIR%"
    )
)
shift
goto parse_args
:after_args

echo [INFO] Target Project: %PROJECT_PATH%
echo [INFO] Destination:    %OUTPUT_DIR%
echo [INFO] Self-Contained: %SELF_CONTAINED%
echo.

:: 3. Build the bundled Python backend
echo [BUILD] Freezing backend engine for Windows x64...
echo.

where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python is required to package the NEXORA backend engine.
    exit /b 1
)

python -m PyInstaller --noconfirm --clean --onefile --name nexora-server ^
    --paths "%ROOT_DIR%" ^
    --collect-submodules backend ^
    --distpath "%SERVER_OUTPUT_DIR%" ^
    --workpath "%OUTPUT_DIR%\build-server" ^
    --specpath "%OUTPUT_DIR%\build-server" ^
    "%ROOT_DIR%backend\server_entrypoint.py"

if %ERRORLEVEL% neq 0 (
    echo [ERROR] Backend packaging failed. Run bootstrap to install backend requirements.
    exit /b %ERRORLEVEL%
)

:: 4. Publish desktop executable beside the bundled backend
echo [BUILD] Publishing Release package for Windows x64...
echo.

"%DOTNET_CMD%" publish "%PROJECT_PATH%" ^
    -c Release ^
    -p:Platform=x64 ^
    -r win-x64 ^
    --self-contained %SELF_CONTAINED% ^
    -o "%OUTPUT_DIR%"

if %ERRORLEVEL% neq 0 (
    echo.
    echo ======================================================================
    echo [ERROR] Build failed! Please review compiler messages above.
    echo ======================================================================
    echo.
    exit /b %ERRORLEVEL%
)

:: 5. Create Launcher Script in Output Directory
set "LAUNCHER=%OUTPUT_DIR%\Run-Nexora.bat"
(
    echo @echo off
    echo cd /d "%%~dp0"
    echo start "" "Nexora.Desktop.exe"
) > "%LAUNCHER%"

echo.
echo ======================================================================
echo [SUCCESS] Deploy executable generated successfully!
echo ======================================================================
echo.
echo Executable Location:
echo   %OUTPUT_DIR%\Nexora.Desktop.exe
echo.
echo Launcher Script:
echo   %OUTPUT_DIR%\Run-Nexora.bat
echo.

:: 6. Auto-run or Done
if "%AUTO_RUN%"=="1" (
    echo [RUN] Launching NEXORA Desktop Control Plane...
    start "" "%OUTPUT_DIR%\Nexora.Desktop.exe"
    goto end
)

:end
echo Done.
