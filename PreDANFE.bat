@echo off
rem Pré-DANFE do SysPDV - lista as NF-e não transmitidas e gera o PDF.
cd /d "%~dp0predanfe"
set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not exist "%PY%" set "PY=python"
"%PY%" predanfe.py %*
echo.
pause
