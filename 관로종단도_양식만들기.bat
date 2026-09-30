@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" profile_template_app.py
) else (
  python profile_template_app.py
)
if errorlevel 1 pause
