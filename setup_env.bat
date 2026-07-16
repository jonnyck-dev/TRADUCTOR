@echo off
setlocal EnableDelayedExpansion
echo ==========================================================
echo   JANUS Audio Editor / AI Video Dubber
echo   Instalador Portable (Windows)
echo ==========================================================
echo.

set "PROJECT_ROOT=%~dp0"
cd /d "%PROJECT_ROOT%"

:: 0. Download portable ffmpeg if not present
echo.
echo [0/5] Configurando FFmpeg portable...
set "FFMPEG_DIR=backend\bin"
if not exist "%FFMPEG_DIR%" mkdir "%FFMPEG_DIR%"

if not exist "%FFMPEG_DIR%\ffmpeg.exe" (
    echo   - Descargando ffmpeg.exe portable...
    powershell -Command "Invoke-WebRequest -Uri 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip' -OutFile '%TEMP%\ffmpeg.zip'" 2>nul
    if exist "%TEMP%\ffmpeg.zip" (
        powershell -Command "Expand-Archive -Path '%TEMP%\ffmpeg.zip' -DestinationPath '%TEMP%\ffmpeg_extracted' -Force" 2>nul
        for /d %%i in ("%TEMP%\ffmpeg_extracted\*") do (
            if exist "%%i\bin\ffmpeg.exe" (
                copy /y "%%i\bin\ffmpeg.exe" "%FFMPEG_DIR%\ffmpeg.exe" >nul
                echo   [OK] ffmpeg.exe copiado a %FFMPEG_DIR%
            )
        )
        del /q "%TEMP%\ffmpeg.zip" 2>nul
        rmdir /s /q "%TEMP%\ffmpeg_extracted" 2>nul
    ) else (
        echo   [WARNING] No se pudo descargar ffmpeg automaticamente.
        echo   Descargalo de https://ffmpeg.org/download.html
        echo   Coloca ffmpeg.exe en %FFMPEG_DIR%
    )
) else (
    echo   - ffmpeg.exe ya existe. Saltando.
)

:: 1. Main venv + dependencies
echo.
echo [1/5] Creando entorno virtual principal...
python -m venv venv 2>nul || (
    echo [ERROR] No se pudo crear el entorno virtual.
    echo Asegurate de tener Python 3.10+ instalado y en el PATH.
    pause
    exit /b 1
)
call venv\Scripts\activate.bat
python -m pip install --upgrade pip --quiet
pip install -r backend\requirements.txt
echo [OK] Entorno principal listo.

:: 2. Clone external repos if not present
echo.
echo [2/5] Clonando proyectos externos...

:: VibeVoice (community fork)
if not exist "backend\vibevoice\.git" (
    echo   - Clonando VibeVoice...
    git clone https://github.com/vibevoice-community/VibeVoice.git backend\vibevoice --depth 1
) else (
    echo   - VibeVoice ya existe. Saltando clone.
)

:: Demucs (UVR5-UI fork)
if not exist "backend\demucs\.git" (
    echo   - Clonando Demucs/UVR5-UI...
    git clone https://github.com/Eddycrack864/UVR5-UI.git backend\demucs --depth 1
) else (
    echo   - Demucs ya existe. Saltando clone.
)

:: 3. Create subproject venvs
echo.
echo [3/5] Creando entornos virtuales de subproyectos...

:: VoxCPM venv (shared with OmniVoice)
if not exist "backend\VoxCPM\env_voxcpm\Scripts\python.exe" (
    echo   - Creando venv de VoxCPM...
    cd backend\VoxCPM
    python -m venv env_voxcpm
    call env_voxcpm\Scripts\activate.bat
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121 --quiet
    pip install fastapi uvicorn requests pydantic soundfile huggingface_hub accelerate --quiet
    cd ..\..
    echo [OK] VoxCPM configurado.
) else (
    echo   - VoxCPM venv ya existe. Saltando.
)

:: OmniVoice (install in shared VoxCPM env)
if exist "backend\OmniVoice\pyproject.toml" (
    echo   - Instalando OmniVoice en env_voxcpm...
    cd backend\VoxCPM
    call env_voxcpm\Scripts\activate.bat
    pip install -e ..\OmniVoice --quiet
    cd ..\..
    echo [OK] OmniVoice configurado.
) else (
    echo   - [SKIP] OmniVoice no encontrado en backend\OmniVoice
)

:: VibeVoice venv
if not exist "backend\vibevoice\env_vibevoice\Scripts\python.exe" (
    echo   - Creando venv de VibeVoice...
    cd backend\vibevoice
    python -m venv env_vibevoice
    call env_vibevoice\Scripts\activate.bat
    pip install -e . --quiet
    pip install whisperx --quiet
    cd ..\..
    echo [OK] VibeVoice configurado.
) else (
    echo   - VibeVoice venv ya existe. Saltando.
)

:: Demucs venv
if not exist "backend\demucs\env\Scripts\python.exe" (
    echo   - Creando venv de Demucs/UVR5-UI...
    cd backend\demucs
    python -m venv env
    call env\Scripts\activate.bat
    pip install --upgrade pip --quiet
    pip install -r requirements.txt --quiet 2>nul || (
        pip install audio-separator==0.16.5 pydub --quiet
    )
    cd ..\..
    echo [OK] Demucs configurado.
) else (
    echo   - Demucs venv ya existe. Saltando.
)

:: 4. Download models from Hugging Face
echo.
echo [4/5] Descargando modelos desde Hugging Face...

:: VoxCPM models
if not exist "backend\VoxCPM\pretrained_models\VoxCPM-0.5B\pytorch_model.bin" (
    echo   - Descargando VoxCPM models...
    cd backend\VoxCPM
    call env_voxcpm\Scripts\activate.bat
    python -c "from huggingface_hub import snapshot_download; snapshot_download('openbmb/VoxCPM-0.5B', local_dir='pretrained_models/VoxCPM-0.5B')" 2>nul || (
        echo [WARNING] No se pudieron descargar los modelos de VoxCPM automaticamente.
        echo Descargalos manualmente de: https://huggingface.co/openbmb/VoxCPM-0.5B
        echo Colocalos en backend\VoxCPM\pretrained_models\VoxCPM-0.5B\
    )
    cd ..\..
    echo [OK] VoxCPM models.
) else (
    echo   - VoxCPM models ya existen. Saltando.
)

:: VibeVoice models (1.5B + 0.5B)
if not exist "backend\vibevoice\checkpoints\VibeVoice-1.5B\model.safetensors" (
    echo   - Descargando VibeVoice models...
    cd backend\vibevoice
    call env_vibevoice\Scripts\activate.bat
    python -c "from huggingface_hub import snapshot_download; snapshot_download('vibevoice/VibeVoice-1.5B', local_dir='checkpoints/VibeVoice-1.5B')" 2>nul || (
        echo [WARNING] No se pudieron descargar los modelos VibeVoice-1.5B.
        echo Descargalos de: https://huggingface.co/vibevoice/VibeVoice-1.5B
        echo Colocalos en backend\vibevoice\checkpoints\VibeVoice-1.5B\
    )
    python -c "from huggingface_hub import snapshot_download; snapshot_download('microsoft/VibeVoice-Realtime-0.5B', local_dir='checkpoints/VibeVoice-Realtime-0.5B')" 2>nul
    cd ..\..
    echo [OK] VibeVoice models.
) else (
    echo   - VibeVoice models ya existen. Saltando.
)

:: 5. Check Ollama installation
echo.
echo [5/5] Verificando Ollama...
ollama --version >nul 2>&1
if errorlevel 1 (
    echo   [INFO] Ollama no esta instalado en este equipo.
    echo   Se necesita Ollama para la traduccion de los videos.
    echo.
    set /p "install_ollama=   ^> Quieres instalar Ollama ahora? (S/N): "
    if /i "!install_ollama!"=="S" (
        echo.
        echo   - Descargando instalador de Ollama...
        powershell -Command "Invoke-WebRequest -Uri 'https://ollama.com/download/OllamaSetup.exe' -OutFile '%TEMP%\OllamaSetup.exe'" 2>nul
        if exist "%TEMP%\OllamaSetup.exe" (
            echo   - Ejecutando instalador (se abrira una ventana)...
            start /wait "" "%TEMP%\OllamaSetup.exe"
            del /q "%TEMP%\OllamaSetup.exe" 2>nul
            echo   [OK] Ollama instalado. Inicia la aplicacion de Ollama antes de usar el traductor.
        ) else (
            echo   [WARNING] No se pudo descargar el instalador.
            echo   Instala Ollama manualmente desde: https://ollama.com/download
        )
    ) else (
        echo   [SKIP] Instala Ollama manualmente desde https://ollama.com/download
    )
) else (
    echo   [OK] Ollama esta instalado.
)

:: Copy .env from example if not exists
if not exist "backend\.env" (
    if exist ".env.example" (
        copy .env.example backend\.env >nul
        echo [OK] .env creado desde .env.example
    )
)

echo.
echo ==========================================================
echo   Instalacion completada!
echo.
echo   Para iniciar el servidor:
echo     run.bat  (Windows)
echo     run.sh   (WSL/Linux)
echo.
echo   IMPORTANTE: Asegurate de que Ollama este corriendo
echo   antes de usar la aplicacion.
echo.
echo   Servidor web: http://localhost:8000
echo ==========================================================
echo.
pause
