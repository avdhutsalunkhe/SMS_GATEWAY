@echo off
echo Starting SMS Gateway Backend on http://0.0.0.0:8072 (LAN: http://192.168.1.91:8072) ...
cd /d "%~dp0"
call .\.venv\Scripts\activate.bat
set PYTHONPATH=.
python -m uvicorn main:app --host 0.0.0.0 --port 8072
pause
