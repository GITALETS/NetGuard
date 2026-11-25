@echo off
title NetGuard Home IP - Servidor de Tesis
echo ========================================================
echo   Iniciando NetGuard Home IP - Sistema Web de Tesis
echo ========================================================
echo.
echo [INFO] El sistema escuchara en la PC y en la red Wi-Fi actual
echo        (Mini-Modem / Router) para que pueda abrirse desde el telefono.
echo [INFO] Si Windows solicita permiso de Firewall para Python,
echo        seleccione "Redes privadas" y haga clic en "Permitir acceso".
echo.
cd /d "%~dp0"
echo Abriendo navegador en http://127.0.0.1:5000...
start http://127.0.0.1:5000
echo Ejecutando servidor Flask (run.py)...
py run.py || python run.py
pause
