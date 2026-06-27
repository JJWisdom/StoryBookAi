@echo off
echo ========================================
echo STORYFORGE - LAUNCHER
echo ========================================
echo.

REM Check if we're in the right directory
if not exist "storybookgui.py" (
    echo ERROR: Not in StoryBookAi project directory
    echo Please run this from:
    echo C:\Users\Hokeuai\Documents\Textbooks\Artificial Intelligence\StoryBookAi\
    pause
    exit /b 1
)

REM Activate venv if present, otherwise warn and try system Python
if exist "venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
) else (
    echo WARNING: Virtual environment not found.
    echo Run the following to create it:
    echo   python -m venv venv
    echo   venv\Scripts\activate.bat
    echo   pip install -r requirements.txt
    echo.
    python --version >nul 2>&1
    if errorlevel 1 (
        echo ERROR: Python is not installed or not in PATH
        pause
        exit /b 1
    )
)

REM Ask if setup is needed
echo Is this your first time running StoryForge?
set /p setup="Run setup? (y/n): "

if /i "%setup%"=="y" (
    echo.
    echo Running setup...
    python setup_project.py
    if errorlevel 1 (
        echo Setup failed
        pause
        exit /b 1
    )
)

echo.
echo ========================================
echo STARTING STORYFORGE
echo ========================================
echo.

python storybookgui.py

echo.
echo Application closed.
pause
