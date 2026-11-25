@echo off
echo ========================================================
echo Starting SMS Gateway Stack (FastAPI + React Dashboard)
echo ========================================================
cd /d "%~dp0"
start "SMS Gateway Backend (FastAPI :8072)" cmd /c start_backend.bat
start "SMS Gateway Dashboard (React Vite :5173)" cmd /c start_frontend.bat
echo Both services launched in separate windows!
echo Backend LAN:     http://192.168.1.91:8072  (API Docs: http://192.168.1.91:8072/docs)
echo Backend Public:  http://115.244.240.22:8072
echo Dashboard LAN:   http://192.168.1.91:5173
echo Device WS URL:   ws://115.244.240.22:8072/ws/device?token=rbpssk-sms-gateway-secret-2026
timeout /t 5
