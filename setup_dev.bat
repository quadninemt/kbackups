@echo off
echo Setting up Development Environment...

REM 1. Check if Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python is not found in your PATH. Please install Python 3.10+ and add it to PATH.
    pause
    exit /b
)

REM 2. Create Virtual Environment
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
) else (
    echo Virtual environment already exists.
)

REM 3. Activate and Install
echo Activating venv and installing dependencies...
call venv\Scripts\activate

REM Upgrade pip inside venv to ensure latest version
python -m pip install --upgrade pip

REM Install requirements
if exist "requirements.txt" (
    pip install -r requirements.txt
    echo.
    echo Dependencies installed successfully!
) else (
    echo Warning: requirements.txt not found.
)

echo.
echo Setup Complete! 
echo To start developing, run: venv\Scripts\activate
echo To build the executable, run: build.bat
pause
