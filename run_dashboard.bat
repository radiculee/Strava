@echo off
REM Strava Cycling Dashboard - Local Launcher
echo.
echo Activating virtual environment and starting Streamlit dashboard...
echo.
call \"%~dp0.venv\\Scripts\\activate\"
cd /d \"%~dp0\"

REM Start dashboard on localhost (secure local access only)
echo Dashboard will open at: http://localhost:8501
echo Press Ctrl+C to stop the server
echo.

streamlit run dashboard\\app.py --server.port 8501 --server.address localhost

exit /b %ERRORLEVEL%
