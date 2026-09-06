@echo off
REM Rewind every approval so the Code Council demo is stage-ready again.
REM Reverts clause text and document versions in the vault, sets all proposals
REM back to pending, all tasks back to new, and clears the edit + notification
REM trail. Stop the backend first, or it may hold stale rows in memory.
REM
REM   reset.bat                  full reset, asks for confirmation
REM   reset.bat --dry-run        show what would change, write nothing
REM   reset.bat --yes            no prompt
REM   reset.bat --task CC-2026-0002   rewind the planted demo task only

cd /d "%~dp0"
python scripts\reset_demo.py %*
if errorlevel 1 echo.
pause
