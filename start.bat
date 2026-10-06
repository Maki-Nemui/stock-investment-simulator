@echo off
setlocal
cd /d "%~dp0"

rem Use the project environment when available, otherwise use Python on PATH.
set "SIMULATOR_PYTHON=python"
if exist "%~dp0.venv\Scripts\python.exe" set "SIMULATOR_PYTHON=%~dp0.venv\Scripts\python.exe"

"%SIMULATOR_PYTHON%" -c "import streamlit, pandas" >nul 2>&1
if errorlevel 1 (
    echo Python or required packages are missing.
    echo Run: python -m pip install -r requirements.txt
    pause
    exit /b 1
)

echo Starting Stock Portfolio Simulator...
echo Keep this window open while using the app.
echo If the browser does not open, use the Local URL printed below.
"%SIMULATOR_PYTHON%" -m streamlit run main.py --server.headless=false --server.address=localhost --browser.gatherUsageStats=false
if errorlevel 1 (
    echo The app could not start. See the error above.
    pause
)
endlocal

