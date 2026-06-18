@echo off
cd /d %~dp0

rem Config koboldcpp (optionnel): crée koboldcpp_config.cmd avec :
rem   set VOLTAIRE_KOBOLDCPP_BASE_URL=http://127.0.0.1:5001
rem   set VOLTAIRE_KOBOLDCPP_MODEL=mon-modele

set VOLTAIRE_CORRECTOR=koboldcpp

if exist koboldcpp_config.cmd call koboldcpp_config.cmd

if "%VOLTAIRE_KOBOLDCPP_BASE_URL%"=="" set VOLTAIRE_KOBOLDCPP_BASE_URL=http://127.0.0.1:5001

echo ========================================
echo   Voltaire Helper - koboldcpp
echo ========================================
echo   koboldcpp: %VOLTAIRE_KOBOLDCPP_BASE_URL%
echo   Modele   : %VOLTAIRE_KOBOLDCPP_MODEL%
echo.
if "%VOLTAIRE_KOBOLDCPP_MODEL%"=="" (
    echo   ⚠  VOLTAIRE_KOBOLDCPP_MODEL non defini !
    echo   Modele recommande : gemma-4-E2B-it-UD-Q4_K_XL.gguf
    echo   (tourne sur un PC portable, ~3 Go RAM)
    echo   Cree koboldcpp_config.cmd ou definis la variable.
    echo.
)
echo   Lance koboldcpp avec --api avant ce script.
echo.
py -3 voltaire_local_server.py
pause
