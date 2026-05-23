@echo off
title All Web Apps
echo.
echo =============================================
echo   ALL WEB APPS LAUNCHER
echo =============================================
echo.

:: Get WSL2 IP address
for /f %%i in ('%SystemRoot%\System32\wsl.exe -d Ubuntu hostname -I') do set WSL_IP=%%i

echo  WSL2 IP: %WSL_IP%
echo.

:: Setup port forwarding: Windows localhost -> WSL2 for all 3 apps
echo  Setting up port forwarding...
netsh interface portproxy delete v4tov4 listenport=5000 listenaddress=127.0.0.1 >nul 2>&1
netsh interface portproxy delete v4tov4 listenport=5010 listenaddress=127.0.0.1 >nul 2>&1
netsh interface portproxy delete v4tov4 listenport=5055 listenaddress=127.0.0.1 >nul 2>&1
netsh interface portproxy add v4tov4 listenport=5000 listenaddress=127.0.0.1 connectport=5000 connectaddress=%WSL_IP% >nul 2>&1
netsh interface portproxy add v4tov4 listenport=5010 listenaddress=127.0.0.1 connectport=5010 connectaddress=%WSL_IP% >nul 2>&1
netsh interface portproxy add v4tov4 listenport=5055 listenaddress=127.0.0.1 connectport=5055 connectaddress=%WSL_IP% >nul 2>&1
echo  Port forwarding set: localhost:5000/5010/5055 -> WSL2
echo.

:: Start all apps via WSL in background
echo  Starting apps in WSL...
start /B "" %SystemRoot%\System32\wsl.exe -d Ubuntu -- /bin/bash /mnt/c/Users/U939/OneDrive/Desktop/Sandbox/start_all.sh

:: Wait then open browser
echo  Waiting for apps to start...
timeout /t 10 /nobreak > nul

echo  Opening browser...
start http://localhost:5000
start http://localhost:5010
start http://localhost:5055

echo.
echo =============================================
echo  Line App     http://localhost:5000
echo  Excel Dash   http://localhost:5010
echo  SoftTech AI  http://localhost:5055
echo.
echo  Close the WSL window to stop all apps.
echo =============================================
echo.
pause
