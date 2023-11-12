@echo off
rem prevent commands from showing in console

rem https://stackoverflow.com/questions/4340350/how-to-check-if-a-file-exists-from-inside-a-batch-file
if exist "%userprofile%\Start Menu\Programs\Startup\mousebattery.bat" (
    rem file exists
    del "%userprofile%\Start Menu\Programs\Startup\mousebattery.bat"
    echo Mouse battery automatic launch on Windows startup was disabled.
) else (
    rem file doesn't exist
    echo Mouse battery already does not launch automatically on Windows startup.
)

echo If mouse battery still launches on Windows startup, go to %userprofile%\Start Menu\Programs\Startup and delete mousebattery.bat manually.

pause