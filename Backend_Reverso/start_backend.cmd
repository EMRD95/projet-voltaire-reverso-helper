@echo off
cd /d %~dp0

rem Config koboldcpp (optionnel): crée koboldcpp_config.cmd avec :
rem   set VOLTAIRE_KOBOLDCPP_BASE_URL=http://127.0.0.1:5001
rem   set VOLTAIRE_KOBOLDCPP_MODEL=mon-modele
rem   set VOLTAIRE_KOBOLDCPP_API_KEY=*** ce backend en mode local

rem Choisis le correcteur : koboldcpp (défaut) ou reverso
if "%VOLTAIRE_CORRECTOR%"=="" set VOLTAIRE_CORRECTOR=koboldcpp

if exist koboldcpp_config.cmd call koboldcpp_config.cmd

if "%VOLTAIRE_KOBOLDCPP_BASE_URL%"=="" set VOLTAIRE_KOBOLDCPP_BASE_URL=http://127.0.0.1:5001

echo ========================================
echo   Voltaire Helper
echo   Corrector: %VOLTAIRE_CORRECTOR%
echo ========================================
if "%VOLTAIRE_CORRECTOR%"=="koboldcpp" (
    echo   koboldcpp: %VOLTAIRE_KOBOLDCPP_BASE_URL%
    echo   Modele   : %VOLTAIRE_KOBOLDCPP_MODEL%
    echo.
    echo   Lance koboldcpp avec --api, charge ton modele, puis lance ce script.
) else (
    echo   Mode Reverso : pas de backend local necessaire.
)
echo.
py -3 voltaire_local_server.py
pause
