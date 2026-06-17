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
set "LINK_DEMUCS=%PROJECT_ROOT%backend\demucs"

set "TARGET_VIBEVOICE=C:\Users\jpzam\VibeVoice"
set "TARGET_DEMUCS=D:\documentos\descargas\Audio\IA\AUDIO ANALIZER\separacion de audio\UVR5-UI-v1.8.4\UVR5-UI"

:: Eliminar enlaces/directorios existentes si los hay para evitar colision
if exist "%LINK_VIBEVOICE%" (
    echo [INFO] Removiendo enlace existente de vibevoice...
    rmdir "%LINK_VIBEVOICE%"
)
if exist "%LINK_DEMUCS%" (
    echo [INFO] Removiendo enlace existente de demucs...
    rmdir "%LINK_DEMUCS%"
)

echo.
echo [PROCESO] Vinculando VibeVoice a la carpeta del proyecto...
mklink /D "%LINK_VIBEVOICE%" "%TARGET_VIBEVOICE%"

echo.
echo [PROCESO] Vinculando Demucs (UVR5-UI) a la carpeta del proyecto...
mklink /D "%LINK_DEMUCS%" "%TARGET_DEMUCS%"

echo.
echo ==========================================================
echo   Enlaces simbolicos creados con exito!
echo ==========================================================
echo.
pause
