@echo off
echo ==========================================================
echo   Instalando Entorno Virtual y Dependencias de Windows
echo ==========================================================
echo.

set "PROJECT_ROOT=%~dp0"
cd /d "%PROJECT_ROOT%"

echo [PROCESO] Creando entorno virtual de Python (venv)...
python -m venv venv
if %errorLevel% neq 0 (
    echo [ERROR] No se pudo crear el entorno virtual.
    echo Asegurate de tener Python instalado en Windows y agregado al PATH.
    echo.
    pause
    exit /b 1
)

echo.
echo [PROCESO] Activando entorno e instalando dependencias (requirements.txt)...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r backend\requirements.txt
if %errorLevel% neq 0 (
    echo [ERROR] Hubo un problema al instalar las dependencias de Python.
    echo.
    pause
    exit /b 1
)

echo.
echo ==========================================================
echo   Entorno virtual e instalacion completados con exito!
echo ==========================================================
echo.
pause
