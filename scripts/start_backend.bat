@echo off
echo ====================================================
echo Starting Indian Legal Chatbot FastAPI Backend Server
echo ====================================================
cd /d "%~dp0..\backend"
call .venv\Scripts\activate.bat
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
pause
