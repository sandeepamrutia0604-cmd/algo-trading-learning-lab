@echo off
cd /d "%~dp0.."
start "" http://127.0.0.1:8000
".venv\Scripts\python.exe" -m uvicorn backend.app.main:app --port 8000
pause
