@echo off
echo ========================================
echo STORYBOOK AI - LAUNCHER
echo ========================================
echo.

REM Check if we have Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ ERROR: Python is not installed or not in PATH
    echo Please install Python 3.10 or later
    pause
    exit /b 1
)

REM Check if we're in the right directory
if not exist "storybookgui.py" (
    echo ❌ ERROR: Not in StoryBookAi project directory
    echo Please run this from: 
    echo C:\Users\Hokeuai\Documents\Textbooks\Artificial Intelligence\StoryBookAi\
    pause
    exit /b 1
)

echo ✅ Found StoryBook AI project
echo.

REM Ask if setup is needed
echo Is this your first time running StoryBook AI?
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
echo STARTING STORYBOOK AI
echo ========================================
echo.

REM Run the application
python storybookgui.py

echo.
echo Application closed.
pause