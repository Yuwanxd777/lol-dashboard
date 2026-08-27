@echo off
rem Update data then push to GitHub Pages. Fully automatic, no prompts.
cd /d "%~dp0"

call "%~dp0update.bat"

rem BP sample library self-heal, right after the fresh data lands:
rem   1) label the crops the live detector could not read (uses today's data as truth)
rem   2) drop cross-labelled samples (same frame, two slots showing the same art)
rem Never allowed to block publishing: 10 min cap, exit code ignored, its own log.
rem Everything it touches lives under scripts\bplive (git-ignored), so the push is unaffected.
powershell -NoProfile -Command "$p=Start-Process -FilePath 'python' -ArgumentList 'scripts\bplive\auto_fix.py','--apply' -NoNewWindow -PassThru -RedirectStandardOutput 'scripts\bplive\autofix_log.txt' -RedirectStandardError 'scripts\bplive\autofix_err.txt'; if(-not $p.WaitForExit(600000)){ $p.Kill() }" 2>nul

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
