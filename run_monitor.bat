@echo off
rem Roda o monitor de precos e guarda a saida em monitor.log
cd /d "%~dp0"
echo ===== %date% %time% ===== >> monitor.log
py scraper.py >> monitor.log 2>&1
