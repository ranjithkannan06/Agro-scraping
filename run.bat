@echo off
setlocal enabledelayedexpansion

echo ========================================================================
echo 🌾 FARMER'S HUB (ATHANUR AGRO) - SERVICES LAUNCHER
echo ========================================================================
echo [1] Run in Local Development Mode (Python .venv + Local MongoDB)
echo [2] Run in Production Container Mode (Docker Compose Containers)
echo ========================================================================
set /p "CHOICE=Please select a running mode (1 or 2): "

set "PROJECT_ROOT=%~dp0"
cd /d "%PROJECT_ROOT%"

if "%CHOICE%"=="2" (
    echo ========================================================================
    echo 🐋 STARTING DOCKER CONTAINERIZED SERVICES...
    echo ========================================================================
    
    :: Check if Docker is running
    docker info >nul 2>nul
    if %errorlevel% neq 0 (
        echo [ERROR] Docker Desktop is not running!
        echo Please open Docker Desktop and wait for the engine to start, then try again.
        echo.
        pause
        exit /b 1
    )
    
    echo [INFO] Booting Farmer's Hub services via Docker Compose...
    docker-compose up --build -d
    
    echo [INFO] Waiting 5 seconds for containers to initialize...
    ping 127.0.0.1 -n 6 >nul
    
    echo [INFO] Loading premium dashboard in your browser...
    start "" "%PROJECT_ROOT%web_dashboard\index.html"
    
    echo ========================================================================
    echo ✅ Farmer's Hub is live in Docker. Dashboard opened successfully.
    echo ========================================================================
    pause
    exit /b 0
)

:: ------------------------------------------------------------------------
:: Run Locally (Option 1)
:: ------------------------------------------------------------------------
echo.
echo ========================================================================
echo 💻 STARTING LOCAL HOST SERVICES (Python .venv + Host MongoDB)...
echo ========================================================================

:: 1. Check for python and environment dependencies
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not configured in your system PATH.
    echo Please install Python 3.10+ and try again.
    pause
    exit /b 1
)

:: 2. Activate Python Virtual Environment
if not exist "%PROJECT_ROOT%.venv\Scripts\activate.bat" (
    echo [ERROR] Python virtual environment was not found at .venv\
    echo Please configure it using: python -m venv .venv
    pause
    exit /b 1
)
call "%PROJECT_ROOT%.venv\Scripts\activate.bat"

:: Check if uvicorn is available in the virtual env
where uvicorn >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] uvicorn was not found in your virtual environment.
    echo Please run 'pip install -r requirements.txt' first.
    pause
    exit /b 1
)

:: 3. Check if MongoDB is running on port 27017
echo [INFO] Auditing MongoDB database server...
powershell -Command "Test-NetConnection -ComputerName localhost -Port 27017 -WarningAction SilentlyContinue" | findstr "TcpTestSucceeded : True" >nul
if %errorlevel% equ 0 (
    echo [INFO] MongoDB is already active and running.
) else (
    echo [WARNING] MongoDB is not running on port 27017. Attempting startup...
    net start MongoDB >nul 2>nul
    if !errorlevel! equ 0 (
        echo [INFO] MongoDB service successfully started via Windows Service Manager.
    ) else (
        echo [WARNING] Service Manager start failed or missing Admin privileges.
        echo [INFO] Launching local mongod instance in background...
        if not exist "%PROJECT_ROOT%data\db" mkdir "%PROJECT_ROOT%data\db"
        start "MongoDB Daemon" /min mongod --dbpath "%PROJECT_ROOT%data\db" --port 27017
        ping 127.0.0.1 -n 4 >nul
    )
)

:: 4. Launch FastAPI Backend in a minimized console
echo [INFO] Launching FastAPI Backend (port 8000)...
start "Athanur Backend" /min cmd /k "cd /d %PROJECT_ROOT%backend && uvicorn src.main:app --reload --port 8000"

:: 5. Wait 3 seconds for uvicorn initialization
echo [INFO] Waiting 3 seconds for backend API service to boot...
ping 127.0.0.1 -n 4 >nul

:: 6. Launch Scraper Scheduler in a minimized console
echo [INFO] Launching Scraper Scheduler Service...
start "Athanur Scraper" /min cmd /k "cd /d %PROJECT_ROOT% && python scraper/src/main.py"

:: 7. Wait 2 seconds
ping 127.0.0.1 -n 3 >nul

:: 8. Open Web Dashboard in default browser
echo [INFO] Loading premium dashboard in your browser...
start "" "%PROJECT_ROOT%web_dashboard\index.html"

echo ========================================================================
echo ✅ Athanur Agro is live on Local Host. Dashboard opened successfully.
echo ========================================================================
pause
