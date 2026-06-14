# AI Video Dubber & Translator (Windows Native)

Este proyecto es una aplicación web local y automatizable diseñada para descargar videos de YouTube, transcribir el audio en inglés con `insanely-fast-whisper`, traducirlo al español usando un modelo local en **Ollama**, doblar la voz usando **VibeVoice** (TTS), sincronizar los tiempos de voz de forma inteligente y unir todo de nuevo en un archivo de video final mediante `ffmpeg`.

---

## 🚀 Instalación Rápida (Windows)

1. **Crear Enlaces Simbólicos**: Haz clic derecho sobre `setup_symlinks.bat` y selecciona **Ejecutar como administrador**. (Esto vinculará las carpetas externas de VibeVoice y Whisper).
2. **Instalar Dependencias**: Haz doble clic sobre `setup_env.bat` para crear el entorno virtual de Python (`venv`) e instalar todas las dependencias necesarias de forma automática.
3. **Arrancar el Servidor**: Haz doble clic sobre `run.bat` para iniciar el backend de FastAPI. Estará disponible en [http://localhost:8000](http://localhost:8000).

---

## 💻 Automatización por Terminal (CLI)

Puedes automatizar todo el proceso sin necesidad de abrir la interfaz gráfica del navegador. Aquí tienes los comandos detallados para integrarlos en scripts de terminal:

### 1. Iniciar el Servidor en Segundo Plano (Windows CMD)
Para arrancar el servidor desde una terminal:
```cmd
venv\Scripts\activate.bat
python backend\main.py
```

### 2. Enviar una Tarea de Doblaje (POST /api/process)
Envía una solicitud HTTP POST al servidor con la URL del video de YouTube, el modelo de traducción de Ollama y la voz de VibeVoice elegida.

#### Usando un Video de YouTube normal:
```bash
curl -X POST http://localhost:8000/api/process ^
  -H "Content-Type: application/json" ^
  -d "{\"url\":\"https://www.youtube.com/watch?v=DTUNF9weRls\",\"model\":\"gemma4:e2b-it-qat\",\"speaker\":\"en-Frank_man\"}"
```

#### Usando un Video ya guardado en la Caché (Modo Desarrollo/Pruebas rápidas):
```bash
curl -X POST http://localhost:8000/api/process ^
  -H "Content-Type: application/json" ^
  -d "{\"url\":\"cache:011d02e8-4393-4eba-bfa9-84e881352c07\",\"model\":\"gemma4:e2b-it-qat\",\"speaker\":\"en-Frank_man\"}"
```

> **Respuesta esperada (JSON)**:
> ```json
> {"task_id": "9e5e74e4-aa40-4824-bd8b-89f333596407"}
> ```

---

### 3. Consultar el Estado del Proceso (GET /api/status/{task_id})
Puedes consultar el progreso de la tarea mediante peticiones GET periódicas (por ejemplo, cada 3 segundos):

```bash
curl -s http://localhost:8000/api/status/9e5e74e4-aa40-4824-bd8b-89f333596407
```

#### Respuestas posibles de Estado (`status`):
- `queued`: En cola, esperando recursos.
- `downloading`: Descargando video de YouTube.
- `transcribing`: Transcribiendo inglés con Whisper.
- `translating`: Traduciendo con Ollama.
- `synthesizing`: Generando TTS en español con VibeVoice.
- `transcribing_dub`: Transcribiendo el audio doblado para alinear tiempos.
- `synchronizing`: Estirando y sincronizando el audio por segmentos.
- `merging`: Mezclando el video original con el nuevo audio en Ffmpeg.
- `completed`: Proceso finalizado con éxito.
- `failed`: Error durante el proceso (el error se detalla en el campo `error`).

> **Respuesta en progreso (JSON)**:
> ```json
> {
>   "status": "translating",
>   "progress": 55,
>   "error": null,
>   "result": null
> }
> ```

---

### 4. Obtener el Video Doblado Final
Una vez que el estado cambie a `"completed"`, el JSON de estado te devolverá la URL del video final en la clave `result.video_url`. Puedes descargarlo o reproducirlo directamente desde:

`http://localhost:8000/cache/{task_id}/video_dubbed.mp4`

Ejemplo de descarga con cURL:
```bash
curl -o video_doblado.mp4 http://localhost:8000/cache/9e5e74e4-aa40-4824-bd8b-89f333596407/video_dubbed.mp4
```
