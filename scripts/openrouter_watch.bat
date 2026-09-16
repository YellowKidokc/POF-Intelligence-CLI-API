@echo off
setlocal
for %%I in ("%~dp0..") do set "ROOT=%%~fI"
if exist "%ROOT%\.venv\Scripts\activate.bat" call "%ROOT%\.venv\Scripts\activate.bat"
python "%ROOT%\cli.py" --openrouter-watch %*
if errorlevel 1 pause
