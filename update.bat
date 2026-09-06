@echo off
rem LOL dashboard data update (local only; publish.bat pushes to GitHub)
rem
rem 2026-09-05: the step list moved into scripts\run_update.py so independent steps can run
rem in parallel (they are network-bound; running them one by one just adds up the waiting).
rem That file also prints per-step timing, which this .bat never did.
rem
rem   python scripts\run_update.py --dry-run     show the plan, run nothing
rem   python scripts\run_update.py --jobs 1      fully sequential (old behaviour)
rem   python scripts\run_update.py --only a,b    run only those steps (for testing)
rem
rem Two steps in the old sequential list had been silently dead since 2026-08-22:
rem the path strings had been written by a tool that expanded \t and \b, so
rem "scripts\trim_data_cols.py" held a TAB and "scripts\build_font_subset.py" a BACKSPACE.
rem Keep this file pure ASCII and never let an editor re-escape these paths.

cd /d "%~dp0"

set LOG=update_log.txt
echo ==== %date% %time% ==== > "%LOG%"

rem 2026-09-06: capture run_update.py's own stdout/stderr too. The 2026-09-05 22:00 run
rem crashed after stage 2 and fell back to sequential (94 min instead of ~20), but the
rem traceback went to the hidden console and was lost. Now it lands in the log.
python scripts\run_update.py --jobs 4 >> "%LOG%" 2>&1
if errorlevel 1 (
  echo run_update.py failed - falling back to sequential >> "%LOG%"
  python scripts\run_update.py --jobs 1 >> "%LOG%" 2>&1
)

type "%LOG%"
