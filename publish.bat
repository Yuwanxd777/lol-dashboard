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
rem git must never wait for a human (2026-09-22 #208). The scheduled shift runs in a hidden
rem session: if the stored token is ever revoked, git/GCM would pop a credential prompt that
rem nobody can answer and the push would hang forever - no health check, no HEALTH_ALERT.txt,
rem and the task scheduler (IgnoreNew + PT72H) skips up to six shifts. Disable every prompt so
rem a broken credential fails fast with an error line in update_log.txt (the health check reads
rem it and flags a push that did not land). Low-speed abort: a connection stalled below
rem 1000 B/s for 60 s is cut instead of waited on. These are env vars, not -c flags, so the
rem three git lines below stay exactly as publish_gate_flow_test.py expects.
set GIT_TERMINAL_PROMPT=0
set GCM_INTERACTIVE=never
set GIT_HTTP_LOW_SPEED_LIMIT=1000
set GIT_HTTP_LOW_SPEED_TIME=60
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
rem --from-publish: also treat a STALE log as a problem (2026-09-07). update.bat overwrites
rem update_log.txt on its very first line, so if it never ran (call skipped, cd failed, .bat
rem broken) the health check would read the PREVIOUS shift's log - 42 steps all exit 0, gate
rem passed, data counts unchanged because nothing was updated - and report 'no problems'.
rem Manual runs from the improvement loop omit the flag (they run between shifts on purpose).
python scripts\update_health.py --from-publish > update_health_log.txt 2>&1
if errorlevel 1 (
  copy /y update_health_log.txt autopilot\HEALTH_ALERT.txt >nul
) else (
  if exist autopilot\HEALTH_ALERT.txt del autopilot\HEALTH_ALERT.txt
)
rem python has closed the file by now, so folding the verdict into the daily log is safe
type update_health_log.txt >> update_log.txt
rem ---- end of health check block ----

rem per-shift log archive (line 3, 2026-09-21). update.bat overwrites update_log.txt on its
rem very first line, so every shift's log only lives until the next shift starts. On 09-17
rem 22:00 a shift never published; by the time anyone looked (09-21) the log, the console file
rem and the health log had each been overwritten five times and HEALTH_ALERT.txt had been
rem auto-deleted by a later clean shift - the cause is gone for good. Archiving used to be a
rem thing the improvement loop did by hand, so a loop that stops running means no evidence at
rem all. Doing it here means every shift keeps its own copy no matter who is watching.
rem Runs LAST on purpose: the git lines and the health verdict are already in update_log.txt
rem by now, so the archived copy is the whole shift. Archiving halfway through gives you
rem update_log_20260909_2200.txt, which stops at the run_update summary and can never tell
rem you whether that shift published.
rem Advisory only - exit code ignored, it can never block or delay a publish. Its stdout goes
rem to its OWN file: never redirect into update_log.txt (this script READS that file, and
rem cmd's lock on it is exactly what broke the 2026-09-06 run; see CLAUDE.md rule 13).
python scripts\shift_log_archive.py --from-publish > shift_archive_log.txt 2>&1
rem ---- end of shift archive block ----

rem exit code: 0 = pushed, 1 = preflight blocked the push (the health check ran either way)
if "%PUBRC%"=="0" (
  echo publish done. see update_log.txt for details.
) else (
  echo publish aborted by preflight - health check still ran, see autopilot\HEALTH_ALERT.txt
)
exit /b %PUBRC%
