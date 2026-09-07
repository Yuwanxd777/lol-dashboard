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
rem PUBRC carries the preflight verdict all the way to the end of this file. A failed gate
rem must STILL reach the health check below: otherwise the worst kind of run (broken data,
rem nothing pushed) is the only one that leaves no autopilot\HEALTH_ALERT.txt behind, and the
rem improvement loop reads "no alert file" as "the last shift was fine". Set GIT and PUBRC
rem BEFORE the if-block: a variable set inside a parenthesised block still expands to its
rem old value inside that same block (cmd expands the whole block when it parses it).
set GIT="C:\Program Files\Git\cmd\git.exe"
set PUBRC=0
python scripts\preflight_check.py >> update_log.txt 2>&1
if errorlevel 1 (
  echo PREFLIGHT FAILED - push skipped. see update_log.txt >> update_log.txt
  echo publish aborted by preflight. see update_log.txt for details.
  set PUBRC=1
)

rem the block above has closed, so %PUBRC% below expands to the value it just set
if "%PUBRC%"=="0" (
  %GIT% add -A >> update_log.txt 2>&1
  %GIT% commit -m "data update %date% %time%" >> update_log.txt 2>&1
  %GIT% push >> update_log.txt 2>&1
)

rem data health check (line 3, 2026-09-07). Runs AFTER the push on purpose: it reads
rem update_log.txt for the run_update timings, the preflight verdict and the push line,
rem so all of that has to be in the log already.
rem Advisory only - the exit code is deliberately NOT propagated. It can never block,
rem delay or undo a publish; by this point the push has already happened (or was skipped
rem by the gate above, which is exactly the case that needs the alert file the most).
rem Its stdout goes to its OWN file. Never redirect into update_log.txt / update_console.txt:
rem other programs open those, and cmd's lock is what made run_update.py die with
rem PermissionError on 2026-09-06 (the 10:00 update silently did nothing and still pushed).
rem exit 1 = something is off (shrunk data / non-zero step / lint errors / no run at all):
rem leave a latch file for the improvement loop and the panel; a clean run clears it.
python scripts\update_health.py > update_health_log.txt 2>&1
if errorlevel 1 (
  copy /y update_health_log.txt autopilot\HEALTH_ALERT.txt >nul
) else (
  if exist autopilot\HEALTH_ALERT.txt del autopilot\HEALTH_ALERT.txt
)
rem python has closed the file by now, so folding the verdict into the daily log is safe
type update_health_log.txt >> update_log.txt
rem ---- end of health check block ----

rem exit code: 0 = pushed, 1 = preflight blocked the push (the health check ran either way)
if "%PUBRC%"=="0" (
  echo publish done. see update_log.txt for details.
) else (
  echo publish aborted by preflight - health check still ran, see autopilot\HEALTH_ALERT.txt
)
exit /b %PUBRC%
