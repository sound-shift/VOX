@echo off
setlocal
cd /d "%~dp0"
title VoiceOverXeaven

REM The app files may live on a slow network/SFTP drive (RaiDrive, etc.).
REM Keep the Python environment on the LOCAL disk so setup is fast and reliable.
set "VENV_DIR=%LOCALAPPDATA%\VoiceOverXeaven\.venv"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"

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

if not exist "%VENV_PY%" (
    echo First launch: creating Python environment on this computer...
    echo Location: %VENV_DIR%
    %PYTHON_CMD% -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo ERROR: Could not create the Python environment.
        goto :failed
    )
)

echo Checking dependencies...
"%VENV_PY%" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
    echo ERROR: Could not install the required packages.
    goto :failed
)

echo.
echo Starting VOX...
echo Keep this window open while VOX is running.
echo.
"%VENV_PY%" -m app.main
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
