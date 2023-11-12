@echo off
rem prevent commands from showing in console

rem install all required libraries
pip install -r mouse_battery_hwinfo_requirements.txt

rem create autoexec.bat file in windows startup directory that starts mouse_battery_hwinfo.py
echo start "" pythonw %cd%\mouse_battery_hwinfo.py > "%userprofile%\Start Menu\Programs\Startup\mousebattery.bat"

rem notify user that script will now launch on windows startup
echo Mouse battery will now launch automatically on Windows startup.

rem wait for input then exit console
pause