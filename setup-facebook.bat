@echo off
rem Stores the Facebook page token in GitHub Secrets, using values from ..\.env. Nothing secret is printed.
cd /d "%~dp0"
python setup_from_env.py
echo.
if errorlevel 1 (echo  FAILED. Copy the ERROR line above to Claude, without any token or secret.) else (echo  DONE.)
pause
