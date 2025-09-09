@echo off
echo Starting University Confession Bot...
echo.

REM Change to the bot directory
cd /d "C:\Users\sende\Desktop\boot"

REM Run the bot
python bot.py

REM Keep window open if there's an error
if errorlevel 1 (
    echo.
    echo Bot exited with an error. Press any key to close...
    pause >nul
)
