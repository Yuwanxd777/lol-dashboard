@echo off
rem Update data then push to GitHub Pages. Fully automatic, no prompts.
cd /d "%~dp0"

call update.bat

rem 推送時間戳：公開版頁首「資料時間」顯示這個（本機版仍顯示資料抓取時間）
powershell -NoProfile -Command "Set-Content -Path push_time.js -Value ('window.PUSH_TIME=\"'+(Get-Date -Format 'yyyy-MM-dd HH:mm')+'\";') -Encoding utf8" >> update_log.txt 2>&1

rem 守門：資料檔語法＋headless 開機驗證；失敗就不推送（避免壞資料上線）
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
