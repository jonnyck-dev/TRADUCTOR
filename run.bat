@echo off
title "AI Video Dubber & Translator Launcher (Windows)"
echo =======================================================
echo     AI Video Dubber ^& Translator Launcher (Windows)
echo =======================================================
echo.
:: Activate env and install requirements
echo [INFO] Activando entorno virtual de Windows...
call venv\Scripts\activate

echo.
echo =======================================================
echo   Servidor de Doblaje e Inteligencia Artificial listo!
echo   Puedes acceder a la aplicacion web premium en:
echo   👉 http://localhost:8000
echo.
echo   Presiona Ctrl+C en esta ventana para apagar el servidor.
echo =======================================================
echo.

:: Para cambiar el modelo de VibeVoice al de 0.5B (Realtime), descomenta la siguiente linea:
:: set VIBEVOICE_MODEL=VibeVoice-Realtime-0.5B

python backend\main.py
pause
