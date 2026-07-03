# Debug Agent Context: AI Video Dubber & Translator

Hola. Eres el Agente de Debugging especializado en este proyecto. Tu objetivo principal es ayudar a Joan a corregir errores en tiempo de ejecución a medida que realiza las pruebas en Windows Nativo.

---

## 1. Arquitectura del Proyecto

El proyecto es una aplicación web local de traducción y doblaje automático de video. Funciona mediante un backend en **FastAPI (Python)** y un frontend sencillo con **HTML/CSS/JS (Vanilla)**.

### Estructura de Archivos Clave:
- [backend/main.py](backend/main.py): Orquestador principal, expone la API, maneja las colas en segundo plano, la descarga de YouTube (`yt-dlp`), extracción de audio, sincronización y unión final.
- [backend/whisper_client.py](backend/whisper_client.py): Cliente de transcripción. Invoca `insanely-fast-whisper` ejecutando el entorno de Windows nativo con `HF_HOME` apuntando al caché local de modelos Hugging Face para evitar descargas masivas de red.
- [backend/translator.py](backend/translator.py): Cliente de traducción usando **Ollama** localmente.
- [backend/tts_client.py](backend/tts_client.py): Generador de audio usando **VibeVoice** (TTS). Llama de forma nativa al script local de VibeVoice en Windows.
- [backend/audio_processor.py](backend/audio_processor.py): Alineación de subtítulos, estiramiento/acortamiento de audio con `pydub`, y multiplexado final del video sin audio original con el audio doblado usando `ffmpeg` de Windows.
- [frontend/index.html](frontend/index.html), [frontend/style.css](frontend/style.css), [frontend/app.js](frontend/app.js): Interfaz de usuario.

---

## 2. Sistema de Caché y Modo Desarrollo

Todos los archivos temporales se guardan localmente bajo `cache/<task_id>/`.

**Modo Simular con Caché (Dev Mode)**:
- Para agilizar las pruebas y evitar baneos de YouTube, agregamos un checkbox en la interfaz: **"Modo Desarrollo: Simular con Caché Local"**.
- Al activarse, lista carpetas del caché que ya contienen `video.mp4` y `audio.wav` (consultando el endpoint `/api/caches`).
- Al enviar la tarea, manda la ruta del caché formateada como `cache:<id>`. El backend salta la descarga de YouTube y usa directamente los archivos guardados.

---

## 3. Estado de Depuración (Debug State) y Errores Resueltos

1. **Error de ruta de Hugging Face (`HF_HOME`) [RESUELTO]**: 
   - El script `whisper_client.py` construía el comando con `set HF_HOME=... &&`. Al usar `&&` en Windows CMD, el espacio anterior al operador `&&` se guardaba dentro de la variable (quedando como `models \hub`), lo que provocaba `WinError 3` (Ruta no encontrada) al cargar Whisper.
   - **Solución**: Envolvimos la asignación en comillas: `set "HF_HOME=C:\..." &&`.
2. **Advertencia de TorchCodec**:
   - `Could not load libtorchcodec_core8.dll`. Esta advertencia se puede ignorar; `insanely-fast-whisper` volverá a decodificar con ffmpeg estándar de forma segura.

---

## 4. Tus Tareas como Agente de Debugging

Joan interactuará directamente contigo enviándote los errores o fallos que arroje la consola al ejecutar el programa (Whisper, Ollama, VibeVoice o la mezcla final).
Deberás:
1. Analizar el trace de error detenidamente.
2. Identificar el archivo responsable ([backend/main.py](backend/main.py), [backend/whisper_client.py](backend/whisper_client.py), etc.).
3. Modificar el código adecuadamente usando tus herramientas.
4. Responder a Joan indicándole qué arreglaste y cómo debe proceder.
