@echo off
setlocal
cd /d "%~dp0"

set "APP_DIR=%~dp0"
if "%APP_DIR:~-1%"=="\" set "APP_DIR=%APP_DIR:~0,-1%"
set "ICON_FILE=%APP_DIR%\assets\wszm_icon.ico"
set "SHORTCUT_FILE=%APP_DIR%\WSZM.lnk"

if exist "%ICON_FILE%" if not exist "%SHORTCUT_FILE%" (
  powershell -NoProfile -ExecutionPolicy Bypass -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('%SHORTCUT_FILE%'); $s.TargetPath='%~f0'; $s.WorkingDirectory='%APP_DIR%'; $s.IconLocation='%ICON_FILE%,0'; $s.WindowStyle=7; $s.Description='WSZM Urban Safety Suite'; $s.Save()" >nul 2>&1
)

if exist ".venv\Scripts\pythonw.exe" (
  start "" ".venv\Scripts\pythonw.exe" desktop_app.py
) else if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" desktop_app.py
) else (
  python desktop_app.py
)
