@echo off
echo ========================================================================
echo 🛑 TERMINATING ALL SERVICES (LOCAL & DOCKER)...
echo ========================================================================

:: 1. Stopping named local CMD windows and uvicorn processes
echo [INFO] Terminating local command windows and servers...
taskkill /f /fi "WINDOWTITLE eq Athanur Backend*" >nul 2>nul
taskkill /f /fi "WINDOWTITLE eq Athanur Scraper*" >nul 2>nul
taskkill /f /fi "WINDOWTITLE eq MongoDB Daemon*" >nul 2>nul
taskkill /f /im uvicorn.exe >nul 2>nul

:: 2. Stopping containerized Docker Compose services
echo [INFO] Auditing Docker Compose services...
docker info >nul 2>nul
if %errorlevel% equ 0 (
    echo [INFO] Stopping active Docker containers...
    cd /d "%~dp0"
    docker-compose down
) else (
    echo [INFO] Docker Desktop is not active. Local termination only.
)

echo ========================================================================
echo ✅ All Farmer's Hub services terminated cleanly.
echo ========================================================================
ping 127.0.0.1 -n 4 >nul
