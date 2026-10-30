@echo off
title NetGuard Home IP - Servidor de Tesis
echo ========================================================
echo   Iniciando NetGuard Home IP - Sistema Web de Tesis
echo ========================================================
echo.
cd /d "%~dp0"
echo Abriendo navegador en http://127.0.0.1:5000...
start http://127.0.0.1:5000
echo Ejecutando servidor Flask (run.py)...
py run.py || python run.py
pause

