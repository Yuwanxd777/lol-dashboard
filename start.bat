@echo off
rem Launch the LOL dashboard local server (enables the refresh button to re-fetch).
rem Double-click this file. Keep the window open; close it to stop the server.
cd /d "%~dp0"
python scripts\serve.py
pause
