@echo off
cd /d %~dp0

set VOLTAIRE_CORRECTOR=deepseek

rem Configuration dans deepseek_config.cmd :
rem   set VOLTAIRE_DEEPSEEK_API_KEY=sk-...
rem   set VOLTAIRE_DEEPSEEK_MODEL=deepseek-v4-flash
rem   set VOLTAIRE_DEEPSEEK_USE_INSTRUCTIONS=1

if exist deepseek_config.cmd call deepseek_config.cmd

if "%VOLTAIRE_DEEPSEEK_API_KEY%"=="" (
    echo ========================================
    echo   ⚠  VOLTAIRE_DEEPSEEK_API_KEY non definie !
    echo   Cree une cle sur https://platform.deepseek.com/api_keys
    echo   puis mets-la dans deepseek_config.cmd :
    echo     set VOLTAIRE_DEEPSEEK_API_KEY=sk-...
    echo ========================================
    pause
    exit /b 1
)

echo ========================================
echo   Voltaire Helper - DeepSeek
echo ========================================
echo   Model: %VOLTAIRE_DEEPSEEK_MODEL%
echo   instructions.txt: %VOLTAIRE_DEEPSEEK_USE_INSTRUCTIONS%
echo.
py -3 voltaire_local_server.py
pause
