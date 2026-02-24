@echo off
REM Activate virtual environment (adjust path if your venv is elsewhere)
call "%~dp0.venv\Scripts\activate"
cd /d "%~dp0"

REM Ensure logs directory exists
if not exist logs mkdir logs

REM Run pipeline (remove --force if you want default cached run)
python main.py --force >> logs\pipeline.log 2>&1

REM Exit with python exit code
exit /b %ERRORLEVEL%
