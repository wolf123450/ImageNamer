@echo off
REM Setup script for ImageNamer on Windows

echo ========================================
echo ImageNamer Setup
echo ========================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8+ from https://www.python.org
    pause
    exit /b 1
)

echo [1/3] Creating virtual environment...
python -m venv .venv
if %errorlevel% neq 0 (
    echo ERROR: Failed to create virtual environment
    pause
    exit /b 1
)

echo [2/3] Installing dependencies...
call .venv\Scripts\activate.bat
pip install -q -r requirements.txt
if %errorlevel% neq 0 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)

echo [3/3] Creating .env file from template...
if exist .env (
    echo .env already exists, skipping
) else (
    copy .env.example .env >nul
    echo .env created from template - please edit it with your settings
)

echo.
echo ========================================
echo Setup complete!
echo ========================================
echo.
echo Next steps:
echo   1. Edit .env file with your settings (Ollama URL, image folder, etc.)
echo   2. Ensure Ollama is running: ollama serve
echo   3. Run: cd src
echo   4. Test: python main.py --help
echo   5. Preview: python main.py --dry-run
echo   6. Process: python main.py
echo.
pause
