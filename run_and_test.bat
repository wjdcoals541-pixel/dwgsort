@echo off
setlocal enabledelayedexpansion

echo.
echo ============================================================
echo STEP 1: Test imports
echo ============================================================
cd /d "%~dp0"
call .venv\Scripts\python.exe test_imports.py
if errorlevel 1 (
    echo.
    echo Import test failed. Attempting to install missing packages...
    echo.
    call .venv\Scripts\pip.exe install PySide6 PyQt-Fluent-Widgets pandas openpyxl matplotlib
    if errorlevel 1 (
        echo.
        echo Package installation failed!
        pause
        exit /b 1
    )
)

echo.
echo ============================================================
echo STEP 2: Running CAD Converter App
echo ============================================================
echo.
call .venv\Scripts\python.exe cad_converter_qt.py

echo.
echo App closed. Check above for any errors.
pause
