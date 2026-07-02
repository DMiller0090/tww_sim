@echo off
REM Double-click this to open the live-updating ESS efficiency chart.
REM It attaches to a running Dolphin and redraws as you move through the game.
cd /d "%~dp0"
python predict_ess_efficiency.py --live
if errorlevel 1 (
  echo.
  echo --- exited with an error ^(is Dolphin running?^) ---
  pause
)
