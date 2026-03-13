@echo off
title Auto-Clipper
color 0A
echo.
echo  Starting Auto-Clipper...
echo.

:: Check if venv exists
if not exist "venv\Scripts\activate.bat" (
    echo  Not installed yet! Run install.bat first.
    pause
    exit /b 1
)

:: Activate and run
call venv\Scripts\activate.bat

:: Open browser quickly - the web UI shows a loading screen
:: that waits for the backend to fully respond before showing content
start http://localhost:8080

python app.py
