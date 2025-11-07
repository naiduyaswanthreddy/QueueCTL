@echo off
REM Quick test script for QueueCTL

echo ========================================
echo QueueCTL Quick Test
echo ========================================

setlocal ENABLEDELAYEDEXPANSION
set DB_FILE=queuectl_quicktest.db

REM Clean up
if exist %DB_FILE% del %DB_FILE%

echo.
echo [1] Enqueuing test jobs...
REM Use doubled quotes for JSON in Windows CMD and pass --db
python -m queuectl.cli enqueue "{""id"":""job1"",""command"":""echo Hello from Job 1""}" --db %DB_FILE%
python -m queuectl.cli enqueue "{""id"":""job2"",""command"":""timeout /t 2""}" --db %DB_FILE%
python -m queuectl.cli enqueue "{""id"":""job3"",""command"":""echo Job 3 completed""}" --db %DB_FILE%

echo.
echo [2] Checking status...
python -m queuectl.cli status --db %DB_FILE%

echo.
echo [3] Listing pending jobs...
python -m queuectl.cli list --state pending --db %DB_FILE%

echo.
echo [4] Showing configuration...
python -m queuectl.cli config show --db %DB_FILE%

echo.
echo ========================================
echo Test setup complete!
echo.
echo To process jobs, run:
echo   python -m queuectl.cli worker start --count 2 --db %DB_FILE%
endlocal
echo.
echo Press Ctrl+C to stop workers when done.
echo ========================================
