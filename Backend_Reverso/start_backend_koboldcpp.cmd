@echo off
cd /d %~dp0

set VOLTAIRE_CORRECTOR=koboldcpp

if exist koboldcpp_config.cmd call koboldcpp_config.cmd

if "%VOLTAIRE_KOBOLDCPP_BASE_URL%"=="" set VOLTAIRE_KOBOLDCPP_BASE_URL=http://127.0.0.1:5001

echo ========================================
echo   Voltaire Helper - koboldcpp
echo ========================================
echo   koboldcpp: %VOLTAIRE_KOBOLDCPP_BASE_URL%
echo   Modele   : auto-detecte via l'API koboldcpp
echo.
echo   Lance koboldcpp avec --api avant ce script.
echo.
py -3 voltaire_local_server.py
pause
