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
if "%ROOT_DIR:~-1%"=="\" set "ROOT_DIR=%ROOT_DIR:~0,-1%"
cd /d "%ROOT_DIR%"

set "PROJECT_PATH=%ROOT_DIR%\desktop\Nexora.Desktop\Nexora.Desktop.csproj"
set "OUTPUT_DIR=%ROOT_DIR%\dist\Nexora"
set "SERVER_OUTPUT_DIR=%OUTPUT_DIR%\server"
set "RESOURCES_DIR=%ROOT_DIR%\desktop\Nexora.Desktop\Resources"
set "SELF_CONTAINED=true"
set "AUTO_RUN=0"
set "SKIP_BACKEND=0"

:: Terminate any running instances to prevent file write locks
taskkill /f /im Nexora.exe >nul 2>&1
taskkill /f /im Nexora.Desktop.exe >nul 2>&1
taskkill /f /im nexora-server.exe >nul 2>&1

:: Parse arguments
:parse_args
if "%~1"=="" goto after_args
if /i "%~1"=="run" set "AUTO_RUN=1"
if /i "%~1"=="--run" set "AUTO_RUN=1"
if /i "%~1"=="-r" set "AUTO_RUN=1"
if /i "%~1"=="--self-contained" set "SELF_CONTAINED=true"
if /i "%~1"=="--framework-dependent" set "SELF_CONTAINED=false"
if /i "%~1"=="--skip-backend" set "SKIP_BACKEND=1"
if /i "%~1"=="--skip-freeze" set "SKIP_BACKEND=1"
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
if not exist "%RESOURCES_DIR%" mkdir "%RESOURCES_DIR%"
if not exist "%SERVER_OUTPUT_DIR%" mkdir "%SERVER_OUTPUT_DIR%"
if not exist "%ROOT_DIR%\dist\server" mkdir "%ROOT_DIR%\dist\server"

if "%SKIP_BACKEND%"=="1" (
    if exist "%RESOURCES_DIR%\nexora-server.exe" (
        echo [INFO] Skipping backend freeze: using existing %RESOURCES_DIR%\nexora-server.exe
        goto skip_freeze
    )
)

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
    --collect-submodules uvicorn ^
    --collect-submodules fastapi ^
    --collect-submodules starlette ^
    --collect-submodules pydantic ^
    --collect-submodules pydantic_settings ^
    --add-data "%ROOT_DIR%\data\model_profiles.json;data" ^
    --distpath "%ROOT_DIR%\dist\server" ^
    --workpath "%OUTPUT_DIR%\build-server" ^
    --specpath "%OUTPUT_DIR%\build-server" ^
    "%ROOT_DIR%\backend\server_entrypoint.py"

if %ERRORLEVEL% neq 0 (
    echo [ERROR] Backend packaging failed. Run bootstrap to install backend requirements.
    exit /b %ERRORLEVEL%
)

copy /y "%ROOT_DIR%\dist\server\nexora-server.exe" "%RESOURCES_DIR%\nexora-server.exe" >nul
copy /y "%ROOT_DIR%\dist\server\nexora-server.exe" "%SERVER_OUTPUT_DIR%\nexora-server.exe" >nul

:skip_freeze

:: 4. Publish standalone desktop executable
echo.
echo [BUILD] Publishing Release package for Windows x64...
echo.

:: Remove any obsolete Nexora.Desktop.exe to avoid naming ambiguity
if exist "%OUTPUT_DIR%\Nexora.Desktop.exe" del /f /q "%OUTPUT_DIR%\Nexora.Desktop.exe" >nul 2>&1

"%DOTNET_CMD%" publish "%PROJECT_PATH%" ^
    -c Release ^
    -p:Platform=x64 ^
    -r win-x64 ^
    -p:PublishSingleFile=true ^
    -p:SelfContained=%SELF_CONTAINED% ^
    -p:IncludeNativeLibrariesForSelfExtract=true ^
    -o "%OUTPUT_DIR%"

if %ERRORLEVEL% neq 0 (
    echo.
    echo ======================================================================
    echo [ERROR] Build failed! Please review compiler messages above.
    echo ======================================================================
    echo.
    exit /b %ERRORLEVEL%
)

if not exist "%ROOT_DIR%\dist\standalone" mkdir "%ROOT_DIR%\dist\standalone"
if exist "%OUTPUT_DIR%\Nexora.exe" (
    copy /y "%OUTPUT_DIR%\Nexora.exe" "%ROOT_DIR%\dist\standalone\Nexora.exe" >nul
)

:: 5. Create Launcher Script in Output Directory
set "LAUNCHER=%OUTPUT_DIR%\Run-Nexora.bat"
echo @echo off> "%LAUNCHER%"
echo cd /d "%%~dp0">> "%LAUNCHER%"
echo start "" "Nexora.exe">> "%LAUNCHER%"

echo.
echo ======================================================================
echo [SUCCESS] Deploy executable generated successfully!
echo ======================================================================
echo.
echo Standalone Single-File Executable:
echo   %OUTPUT_DIR%\Nexora.exe
echo.
echo Standalone Distribution Folder:
echo   %ROOT_DIR%\dist\standalone\Nexora.exe
echo.
echo Launcher Script:
echo   %OUTPUT_DIR%\Run-Nexora.bat
echo.

:: 6. Auto-run or Done
if "%AUTO_RUN%"=="1" (
    echo [RUN] Launching NEXORA Desktop Control Plane...
    start "" "%OUTPUT_DIR%\Nexora.exe"
    goto end
)

:end
echo Done.
