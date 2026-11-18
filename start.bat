@echo off
setlocal enabledelayedexpansion
title SentryGrid - Emergency Response System

cd /d "%~dp0"

echo ====================================================================
echo   SentryGrid - Real-Time Disaster Alert and Emergency Response
echo   CSA4310: Internet Programming Capstone Project
echo ====================================================================
echo.

:: 1. Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not found in your PATH.
    echo Please install Python 3.9+ and make sure to check "Add Python to PATH".
    echo Download from: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('python --version') do set PYTHON_VER=%%i
echo [*] Detected: !PYTHON_VER!

:: 2. Check for Virtual Environment
if exist venv\Scripts\activate.bat (
    echo [*] Activating virtual environment (venv)...
    call venv\Scripts\activate.bat
) else if exist ..\venv\Scripts\activate.bat (
    echo [*] Activating virtual environment (..\venv)...
    call ..\venv\Scripts\activate.bat
)

:: 3. Check for .env file
if not exist .env (
    if exist .env.example (
        echo [*] Creating .env from .env.example...
        copy .env.example .env >nul
    )
)

:: 4. Verify/Install Requirements
echo [*] Checking dependencies...
python -c "import flask, mysql.connector, dotenv, werkzeug" >nul 2>&1
if errorlevel 1 (
    echo [*] Installing required packages from requirements.txt...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [WARNING] Some dependencies failed to install. Continuing anyway...
    )
) else (
    echo [OK] All required dependencies are installed.
)

:: 5. Menu options
echo.
echo Select an option:
echo   [1] Start Application Server (Default)
echo   [2] Initialize/Reset Database (runs init_db.py) and Start
echo   [3] Run System Automated Tests
echo.
choice /c 123 /m "Enter choice (1, 2, or 3) [auto-selects 1 in 5s]: " /t 5 /d 1
set USER_CHOICE=!errorlevel!

if "!USER_CHOICE!"=="2" (
    echo.
    echo [*] Initializing SentryGrid database...
    python init_db.py
    echo.
) else if "!USER_CHOICE!"=="3" (
    echo.
    echo [*] Running automated tests...
    python test_all_features.py
    echo.
    echo Press any key to start the server...
    pause >nul
)

:: 6. Launch browser in background after short delay
start "" /b cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:5000"

:: 7. Start Flask Server
echo.
echo ====================================================================
echo   Server is running at: http://localhost:5000
echo   Default Accounts:
echo     - Admin:     admin / admin123
echo     - Responder: responder1 / resp123
echo     - Citizen:   citizen1 / citizen123
echo.
echo   Press Ctrl+C to stop the server.
echo ====================================================================
echo.

python app.py

pause
