@echo off
cd /d %~dp0

set VOLTAIRE_CORRECTOR=reverso

echo ========================================
echo   Voltaire Helper - Reverso
echo ========================================
echo   Mode Reverso : API web, zero setup.
echo   Gratuit, mais parfois rate-limite (429).
echo   Si ca bloque, attends ~1 minute.
echo.
py -3 voltaire_local_server.py
pause
