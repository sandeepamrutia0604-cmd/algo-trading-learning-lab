@echo off
rem Starts the app on the demo database (built from simulated stocks), on port 8001.
rem Your real database is not touched. Run once first to build it:  python scripts\demo_setup.py
cd /d "%~dp0.."
if not exist "data\demo.db" (
  echo data\demo.db is missing. Build it first:  python scripts\demo_setup.py
  pause
  exit /b 1
)
set DATABASE_URL=sqlite:///./data/demo.db
start "" http://127.0.0.1:8001
".venv\Scripts\python.exe" -m uvicorn backend.app.main:app --port 8001
pause
