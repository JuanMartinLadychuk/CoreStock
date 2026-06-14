@echo off
setlocal enabledelayedexpansion
title CoreStack Pro - Build Release
echo ================================================
echo   CoreStack Pro - Generador de ejecutable
echo ================================================
echo.

REM ── 1) Entorno virtual aislado ──────────────────────────────
if not exist venv (
    echo [1/6] Creando entorno virtual...
    python -m venv venv
)
call venv\Scripts\activate.bat

echo [2/6] Instalando dependencias...
python -m pip install --upgrade pip >nul
pip install -r requirements.txt
pip install pyinstaller --upgrade

REM ── 2) Limpiar builds previos ───────────────────────────────
echo [3/6] Limpiando builds anteriores...
if exist build rmdir /s /q build
if exist dist  rmdir /s /q dist

REM ── 3) Compilar ──────────────────────────────────────────────
echo [4/6] Compilando con PyInstaller (esto tarda unos minutos)...
pyinstaller CoreStackPro.spec --noconfirm

if not exist dist\CoreStackPro\CoreStackPro.exe (
    echo.
    echo  ERROR: La compilacion fallo. Revisa el log de arriba.
    echo  Tip: si el error menciona "ModuleNotFoundError" en runtime,
    echo       agrega ese modulo a hiddenimports en CoreStackPro.spec
    pause
    exit /b 1
)

REM ── 4) Carpetas y archivos persistentes ─────────────────────
echo [5/6] Armando carpeta de release...
mkdir dist\CoreStackPro\data 2>nul
mkdir dist\CoreStackPro\logs 2>nul
if exist README_USUARIO.txt copy /Y README_USUARIO.txt dist\CoreStackPro\LEEME.txt >nul

REM ── 5) Comprimir para distribucion ──────────────────────────
echo [6/6] Generando ZIP de distribucion...
set ZIPNAME=CoreStackPro_v0.9.zip
if exist %ZIPNAME% del %ZIPNAME%
powershell -NoProfile -Command "Compress-Archive -Path 'dist\CoreStackPro\*' -DestinationPath '%ZIPNAME%' -Force"

echo.
echo ================================================
echo  LISTO
echo  Carpeta de prueba : dist\CoreStackPro\
echo  ZIP para entregar : %ZIPNAME%
echo ================================================
echo.
echo  Antes de mandarlo al cliente:
echo   1) Copia %ZIPNAME% a una PC SIN Python instalado
echo   2) Descomprimi y ejecuta CoreStackPro.exe
echo   3) Verifica que login, POS y reportes funcionen
echo.
pause
