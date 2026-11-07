@echo off
setlocal enabledelayedexpansion

title NEXORA Backend Server

:: 1. Navigate to Project Root
cd /d "%~dp0"
set "ROOT_DIR=%~dp0"
set "PYTHONPATH=%ROOT_DIR%"

:: 2. Default Configuration
set "HOST=127.0.0.1"
set "PORT=8000"
set "RELOAD=--reload"
set "MODE=dev"

:: 3. Parse CLI Arguments
:parse_args
if "%~1"=="" goto after_args
if /i "%~1"=="--host" (
    set "HOST=%~2"
    shift
    shift
    goto parse_args
)
if /i "%~1"=="-h" (
    set "HOST=%~2"
    shift
    shift
    goto parse_args
)
if /i "%~1"=="--port" (
    set "PORT=%~2"
    shift
    shift
    goto parse_args
)
if /i "%~1"=="-p" (
    set "PORT=%~2"
    shift
    shift
    goto parse_args
)
if /i "%~1"=="--no-reload" (
    set "RELOAD="
    shift
    goto parse_args
)
if /i "%~1"=="--prod" (
    set "MODE=prod"
    set "RELOAD="
    shift
    goto parse_args
)
shift
goto parse_args
:after_args

echo.
echo ======================================================================
echo               NEXORA Backend Server - Local API Engine
echo ======================================================================
echo.

:: 4. Production Standalone Mode Check
if /i "%MODE%"=="prod" (
    if exist "%ROOT_DIR%dist\server\nexora-server.exe" (
        echo [INFO] Launching standalone frozen server: dist\server\nexora-server.exe
        echo [INFO] Host: %HOST% ^| Port: %PORT%
        echo [INFO] API Docs:   http://%HOST%:%PORT%/docs
        echo [INFO] Health URL: http://%HOST%:%PORT%/api/health
        echo.
        "%ROOT_DIR%dist\server\nexora-server.exe" --host %HOST% --port %PORT%
        goto end
    ) else (
        echo [WARN] dist\server\nexora-server.exe not found. Falling back to development runtime...
    )
)

:: 5. Detect Python / uv Runtime
set "RUN_CMD="

where uv >nul 2>&1
if %ERRORLEVEL% equ 0 (
    set "RUN_CMD=uv run uvicorn backend.app.main:app"
) else if exist "%USERPROFILE%\.local\bin\uv.exe" (
    set "RUN_CMD="%USERPROFILE%\.local\bin\uv.exe" run uvicorn backend.app.main:app"
) else if exist "%ROOT_DIR%.venv\Scripts\python.exe" (
    set "RUN_CMD="%ROOT_DIR%.venv\Scripts\python.exe" -m uvicorn backend.app.main:app"
) else if exist "%ROOT_DIR%backend\.venv\Scripts\python.exe" (
    set "RUN_CMD="%ROOT_DIR%backend\.venv\Scripts\python.exe" -m uvicorn backend.app.main:app"
) else (
    where python >nul 2>&1
    if %ERRORLEVEL% equ 0 (
        set "RUN_CMD=python -m uvicorn backend.app.main:app"
    ) else if exist "C:\Python314\python.exe" (
        set "RUN_CMD=C:\Python314\python.exe -m uvicorn backend.app.main:app"
    )
)

if "%RUN_CMD%"=="" (
    echo [ERROR] No suitable Python or uv runtime found!
    echo Please install Python 3.11+ or install uv:
    echo   powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
    echo.
    pause
    exit /b 1
)

:: 6. Launch Server
echo [INFO] Runtime Command: %RUN_CMD%
echo [INFO] Host:           %HOST%
echo [INFO] Port:           %PORT%
if "%RELOAD%"=="" (
    echo [INFO] Auto-reload:    Disabled
) else (
    echo [INFO] Auto-reload:    Enabled
)
echo [INFO] API Endpoint:   http://%HOST%:%PORT%
echo [INFO] Swagger Docs:   http://%HOST%:%PORT%/docs
echo [INFO] Health Probe:   http://%HOST%:%PORT%/api/health
echo.
echo Press Ctrl+C to terminate the server.
echo ======================================================================
echo.

%RUN_CMD% --host %HOST% --port %PORT% %RELOAD%

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Server exited with code %ERRORLEVEL%.
    pause
    exit /b %ERRORLEVEL%
)

:end
