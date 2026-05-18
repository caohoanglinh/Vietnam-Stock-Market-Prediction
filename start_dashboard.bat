@echo off
setlocal

cd /d "%~dp0"

powershell -NoProfile -Command "try { $resp = Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/static/ -TimeoutSec 2; if ($resp.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }"
if %errorlevel%==0 (
    start "" "http://127.0.0.1:8000/static/"
    exit /b 0
)

start "VNStock Dashboard" powershell -NoLogo -NoExit -ExecutionPolicy Bypass -File "%~dp0web\run_dashboard.ps1"
timeout /t 4 /nobreak >nul
start "" "http://127.0.0.1:8000/static/"
