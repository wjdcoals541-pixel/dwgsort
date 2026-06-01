@echo off
setlocal

set "APP_DIR=%~dp0"
set "VENV_PYTHON=%APP_DIR%\.venv\Scripts\python.exe"

if not exist "%APP_DIR%\cad_converter_qt.py" (
    echo DWGSort 4.0 app entry point was not found.
    echo Expected: "%APP_DIR%\cad_converter_qt.py"
    pause
    exit /b 1
)

cd /d "%APP_DIR%"

if exist "%VENV_PYTHON%" (
    "%VENV_PYTHON%" cad_converter_qt.py
) else (
    python cad_converter_qt.py
)

pause
