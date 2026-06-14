@echo off
echo ==========================================================
echo   Creando Enlaces Simbolicos (Symlinks) en Windows
echo ==========================================================
echo.

:: Verificar permisos de Administrador (requerido para mklink por defecto en Windows)
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERROR] Debes ejecutar este archivo como ADMINISTRADOR.
    echo Por favor, haz clic derecho sobre este archivo y selecciona "Ejecutar como administrador".
    echo.
    pause
    exit /b 1
)

set "PROJECT_ROOT=%~dp0"
set "LINK_VIBEVOICE=%PROJECT_ROOT%backend\vibevoice"
set "LINK_WHISPER=%PROJECT_ROOT%backend\superfastWHISPER"

set "TARGET_VIBEVOICE=C:\Users\jpzam\VibeVoice"
set "TARGET_WHISPER=C:\Users\jpzam\VibeVoice\superfastWHISPER"

:: Eliminar enlaces/directorios existentes si los hay para evitar colision
if exist "%LINK_VIBEVOICE%" (
    echo [INFO] Removiendo enlace existente de vibevoice...
    rmdir "%LINK_VIBEVOICE%"
)
if exist "%LINK_WHISPER%" (
    echo [INFO] Removiendo enlace existente de superfastWHISPER...
    rmdir "%LINK_WHISPER%"
)

echo.
echo [PROCESO] Vinculando VibeVoice a la carpeta del proyecto...
mklink /D "%LINK_VIBEVOICE%" "%TARGET_VIBEVOICE%"

echo.
echo [PROCESO] Vinculando superfastWHISPER a la carpeta del proyecto...
mklink /D "%LINK_WHISPER%" "%TARGET_WHISPER%"

echo.
echo ==========================================================
echo   Enlaces simbolicos creados con exito!
echo ==========================================================
echo.
pause
