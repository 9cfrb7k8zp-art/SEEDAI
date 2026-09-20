@echo off
title Oracle Vision Launcher - QOS
cd /d %~dp0

:: Log all .py files in folder
echo Listing Python scripts...
dir *.py > startup_log.txt

:: Run Oracle Vision system
echo Launching oracle_vision.py...
python oracle_vision.py

pause


# Updated at 2025-06-15 10:48:10.558368
# Updated at 2025-06-15 21:03:47.897522