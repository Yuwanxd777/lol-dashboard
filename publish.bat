@echo off
rem Update data then push to GitHub Pages. Fully automatic, no prompts.
cd /d "%~dp0"

call update.bat

rem push timestamp: public site header shows this as data time (local build shows fetch time)
powershell -NoProfile -Command "Set-Content -Path push_time.js -Value ('window.PUSH_TIME=\"'+(Get-Date -Format 'yyyy-MM-dd HH:mm')+'\";') -Encoding utf8" >> update_log.txt 2>&1

rem gate: data-file syntax + headless boot check; on failure skip push (never ship broken data)
python scripts\preflight_check.py >> update_log.txt 2>&1
if errorlevel 1 (
  echo PREFLIGHT FAILED - push skipped. see update_log.txt >> update_log.txt
  echo publish aborted by preflight. see update_log.txt for details.
  exit /b 1
)

set GIT="C:\Program Files\Git\cmd\git.exe"
%GIT% add -A >> update_log.txt 2>&1
%GIT% commit -m "data update %date% %time%" >> update_log.txt 2>&1
%GIT% push >> update_log.txt 2>&1
echo publish done. see update_log.txt for details.
