@echo off
title Compilador Nexus Fetch para Linux (via WSL)
echo ========================================================
echo       🔻 NEXUS FETCH - BUILD PIPELINE (LINUX NATIVO)
echo ========================================================
echo.
echo Executando compilacao dentro do Ubuntu no WSL...
echo.

wsl -d Ubuntu -- bash -c "cd /mnt/c/Users/Luiz/Documents/GitHub/NexusFetch && ./build_linux.sh"

echo.
pause
