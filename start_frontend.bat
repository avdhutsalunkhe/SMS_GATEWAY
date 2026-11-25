@echo off
echo Starting SMS Gateway React Dashboard on http://localhost:5173 (LAN: http://192.168.1.91:5173) ...
cd /d "%~dp0\web_dashboard"
call npm run dev -- --host 0.0.0.0 --port 5173
pause
