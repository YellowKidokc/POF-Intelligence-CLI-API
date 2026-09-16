@echo off
setlocal
for %%I in ("%~dp0..\..\..") do set "ROOT=%%~fI"
if exist "%ROOT%\.venv\Scripts\activate.bat" call "%ROOT%\.venv\Scripts\activate.bat"
set /p STATION_NAME="New station name: "
python "%ROOT%\cli.py" --station-new "%STATION_NAME%" --from "%~dp0.."
if errorlevel 1 pause
