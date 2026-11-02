@echo off
echo ====================================================
echo Running Indian Legal Chatbot Pytest Suite
echo ====================================================
cd /d "%~dp0..\backend"
call .venv\Scripts\activate.bat
pytest -v
pause
