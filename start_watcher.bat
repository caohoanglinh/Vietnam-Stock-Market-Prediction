@echo off
title Vnstock GPU Retrain Watcher
color 0A

echo ========================================================
echo   VNSTOCK GPU RETRAIN WATCHER
echo ========================================================
echo.
echo This window will stay open and monitor for retrain signals
echo from your Airflow Docker container.
echo.
echo When the weekly accuracy drops below 50%%, Airflow will
echo drop a flag file, and this script will automatically
echo trigger the pyTorch GPU retraining on your machine.
echo.

python watch_retrain.py

echo.
pause
