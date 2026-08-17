@echo off
setlocal

set "APP_DIR=%~dp0"
set "VENV_PYTHON=%APP_DIR%\.venv\Scripts\python.exe"
set "REQUIREMENTS=%APP_DIR%\requirements.txt"

if not exist "%APP_DIR%\cad_converter_qt.py" (
    echo DWGSort 4.0 app entry point was not found.
    echo Expected: "%APP_DIR%\cad_converter_qt.py"
    pause
    exit /b 1
)

cd /d "%APP_DIR%"

if exist "%VENV_PYTHON%" (
    "%VENV_PYTHON%" --version >nul 2>&1
    if errorlevel 1 (
        echo Existing .venv is broken. Recreating it...
        rmdir /s /q "%APP_DIR%\.venv"
    )
)

if not exist "%VENV_PYTHON%" (
    echo Preparing DWGSort 4.0 Python environment...
    py -3.12 -m venv "%APP_DIR%\.venv" >nul 2>&1
    if errorlevel 1 (
        py -3 -m venv "%APP_DIR%\.venv" >nul 2>&1
    )
    if errorlevel 1 (
        python -m venv "%APP_DIR%\.venv"
    )
    if errorlevel 1 (
        echo Failed to create .venv. Please install Python 3.12 or newer.
        pause
        exit /b 1
    )
)

"%VENV_PYTHON%" -c "import PySide6, pandas, matplotlib, openpyxl, xlrd, fitz, ezdxf" >nul 2>&1
if errorlevel 1 (
    if not exist "%REQUIREMENTS%" (
        echo requirements.txt was not found.
        pause
        exit /b 1
    )
    echo Installing DWGSort 4.0 dependencies...
    "%VENV_PYTHON%" -m pip install -r "%REQUIREMENTS%"
    if errorlevel 1 (
        echo Failed to install dependencies.
        pause
        exit /b 1
    )
)

"%VENV_PYTHON%" cad_converter_qt.py

pause
