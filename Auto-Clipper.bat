@echo off
title Auto-Clipper
color 0A

:: ============================================================
::  Auto-Clipper - Double-click to install & run
::  Works on Windows. Just double-click this file.
:: ============================================================

echo.
echo  ========================================
echo    Auto-Clipper
echo  ========================================
echo.

:: ---------- Already installed? Just launch ----------
if exist "venv\Scripts\python.exe" (
    echo  Starting Auto-Clipper...
    echo.
    call venv\Scripts\activate.bat
    echo  Opening browser...
    timeout /t 2 /nobreak >nul
    start http://localhost:8080
    python app.py
    exit /b 0
)

:: ---------- First time: install everything ----------
echo  First time setup - this takes a few minutes.
echo.

:: 1. Check Python
echo [1/4] Checking for Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  Python is NOT installed.
    echo.
    echo  Opening the Python download page now...
    echo  IMPORTANT: Check the box "Add python.exe to PATH"
    echo             at the BOTTOM of the installer!
    echo.
    start https://www.python.org/downloads/
    echo  After installing Python, double-click Auto-Clipper.bat again.
    echo.
    pause
    exit /b 1
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do echo  Found Python %%v

:: 2. FFmpeg
echo.
echo [2/4] Checking for FFmpeg...
ffmpeg -version >nul 2>&1
if %errorlevel% neq 0 (
    echo  FFmpeg not found. Downloading automatically...
    echo  This may take a minute...

    powershell -Command "& { $ProgressPreference = 'SilentlyContinue'; try { Invoke-WebRequest -Uri 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip' -OutFile '%TEMP%\ffmpeg.zip' -UseBasicParsing } catch { Write-Host 'Download failed'; exit 1 } }"

    if %errorlevel% neq 0 (
        echo.
        echo  Auto-download failed. Install FFmpeg manually:
        echo  https://github.com/BtbN/FFmpeg-Builds/releases
        echo.
        pause
        exit /b 1
    )

    echo  Extracting...
    powershell -Command "Expand-Archive -Path '%TEMP%\ffmpeg.zip' -DestinationPath '%LOCALAPPDATA%\ffmpeg' -Force"

    for /d %%d in ("%LOCALAPPDATA%\ffmpeg\ffmpeg-*") do set FFMPEG_BIN=%%d\bin

    if not defined FFMPEG_BIN (
        echo  Could not find FFmpeg after extraction.
        pause
        exit /b 1
    )

    powershell -Command "[Environment]::SetEnvironmentVariable('Path', [Environment]::GetEnvironmentVariable('Path', 'User') + ';%FFMPEG_BIN%', 'User')"
    set "PATH=%PATH%;%FFMPEG_BIN%"
    del "%TEMP%\ffmpeg.zip" 2>nul
    echo  FFmpeg installed!
) else (
    echo  Found FFmpeg
)

:: 3. Virtual environment
echo.
echo [3/4] Setting up Python environment...
python -m venv venv
if %errorlevel% neq 0 (
    echo  Failed to create Python environment.
    pause
    exit /b 1
)
echo  OK

:: 4. Dependencies
echo.
echo [4/4] Installing dependencies...
call venv\Scripts\activate.bat
pip install -r requirements.txt --quiet
if %errorlevel% neq 0 (
    echo  Failed to install dependencies.
    pause
    exit /b 1
)
echo  OK

:: ---------- Done! Launch ----------
echo.
echo  ========================================
echo    Installation complete! Starting app...
echo  ========================================
echo.
echo  Next time just double-click Auto-Clipper.bat again.
echo.

timeout /t 2 /nobreak >nul
start http://localhost:8080

python app.py
