@echo off
setlocal
cd /d "%~dp0"
title VoiceOverXeaven

echo.
echo ========================================
echo   VoiceOverXeaven launcher
echo ========================================
echo.

where py >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=py -3"
) else (
    where python >nul 2>&1
    if errorlevel 1 (
        echo ERROR: Python was not found.
        echo Install Python 3.10 or newer from https://www.python.org/downloads/
        echo During installation, enable "Add Python to PATH".
        goto :failed
    )
    set "PYTHON_CMD=python"
)

if not exist ".venv\Scripts\python.exe" (
    echo First launch: creating Python environment...
    %PYTHON_CMD% -m venv ".venv"
    if errorlevel 1 (
        echo ERROR: Could not create the Python environment.
        goto :failed
    )
)

echo Checking dependencies...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
    echo ERROR: Could not install the required packages.
    goto :failed
)

echo.
echo Starting VOX...
echo Keep this window open while VOX is running.
echo.
".venv\Scripts\python.exe" -m app.main
if errorlevel 1 (
    echo.
    echo ERROR: VOX stopped with an error. The details are shown above.
    goto :failed
)

endlocal
exit /b 0

:failed
echo.
echo Send a screenshot of this window if you need help.
pause
endlocal
exit /b 1