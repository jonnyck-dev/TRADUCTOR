# Plan de Implementación y Arquitectura - Traductor & Doblador de Video con IA

Este proyecto es una aplicación web local que automatiza el proceso de traducción y doblaje de videos usando modelos locales en Windows.

---

## 🚀 Estado de la Implementación (Ya Completado)

1. **Servidor Backend (FastAPI)**: Pipeline orquestado en `backend/main.py` ejecutándose de forma nativa en Windows/WSL.
2. **Transcripción (WhisperX)**: Integración en `backend/whisper_client.py` que provee alineación a nivel de palabra para máxima precisión.
3. **Traducción Robusta (Ollama)**: Traducción segmentada en `backend/translator.py` con fallbacks automáticos batch-by-batch y chunk-by-chunk para evitar oraciones en inglés.
4. **Optimización de TTS (VibeVoice)**:
   - Procesamiento en paralelo limitado a **2 hilos** para proteger la VRAM y evitar congelamientos de la PC.
   - Servidor VibeVoice FastAPI integrado que se levanta y apaga dinámicamente antes y después del TTS para liberar memoria.
   - Slicing automático a un límite de 2 minutos para evitar la degradación y alucinación del modelo.
5. **Botón Detener/Pausar**:
   - Botón interactivo en la UI para detener el proceso en vivo.
   - Endpoint de cancelación `/api/cancel/{task_id}` que limpia los hilos y apaga el servidor TTS de inmediato.
   - Caché in-place que permite retomar exactamente desde la última frase sintetizada al volver a comenzar con la misma caché.
6. **Clonación de Voz Zero-Shot (One-Shot Example)**:
   - Opción *"Voz Clonada"* agregada a la UI.
   - Extracción automática de una muestra limpia de 1 minuto del audio original en inglés buscando el inicio del primer fragmento de voz transcrito por Whisper.
   - Copia dinámica en `backend/vibevoice/demo/voices/cloned_speaker.wav` para su uso automático en VibeVoice.
7. **Separación de Voz e Instrumental (Demucs)**:
   - Integración local de `audio-separator` y el modelo `htdemucs_ft.yaml` utilizando el entorno virtual y checkpoints de `UVR5-UI`.
   - Extracción de `vocals.wav` para una transcripción WhisperX libre de alucinaciones y un sampleado de clonación de voz extremadamente limpio.
   - Reconstrucción automática de la pista de efectos y música de fondo (`no_vocals.wav`) fusionando los canales Bass, Drums y Other con `pydub`.
   - Mezcla final profesional (`dubbed_mixed.wav`) que combina la voz doblada en español con el fondo original con volumen ajustado, preservando la música y efectos especiales en estéreo.
8. **Detección y Advertencia de Modelos Cloud (Ollama)**:
   - Implementación de la función de validación `call_ollama_api` en `translator.py` con una clase de excepción dedicada `OllamaCloudModelError` para aislar fallos de JSONDecodeError.
   - Eliminación de todas las lógicas de fallback y cascadas (traducción por lotes/individuales) en `translator.py` a solicitud del usuario, configurando un modo **One-Shot 100% Exclusivo** para medir con precisión la velocidad de los modelos cloud.
   - Actualización del selector en `index.html` organizando los modelos con `<optgroup>` y añadiendo las opciones reales de tu máquina.
9. **Registro y Visualización de Timers (Optimización)**:
   - Medición precisa de cada fase en el backend (`process_translation_task` en `backend/main.py`) guardando los resultados en `timing_report.json` dentro del directorio de caché de la tarea.
   - Integración visual en el frontend (`index.html`, `app.js`, `style.css`) mediante un panel interactivo con barras de progreso de colores para cada fase y resumen de duración total, permitiendo diagnosticar cuellos de botella con facilidad.

---

## 🎯 Plan de Optimización de Rendimiento y Correcciones Activas

### 1. Generación por Lotes (Batch) de TTS VibeVoice (En Progreso)
- **Problema**: La generación individual de cada frase mediante VibeVoice tarda demasiado (~14 minutos para un video de 20 minutos) debido a los overheads de arranque de síntesis.
- **Solución**:
  - Agrupar frases en bloques contiguos de 5.
  - Generar el audio completo del lote (`batch_{batch_idx}_raw.wav`) en una única llamada al servidor VibeVoice.
  - Ejecutar WhisperX en el audio del lote para obtener los tiempos exactos de inicio y fin de cada palabra en español.
  - Alinear las 5 frases originales con las palabras de WhisperX y segmentar el lote en archivos `phrase_{idx}.mp3` individuales con un pequeño margen de 0.05s.
  - Implementar un fallback proporcional en caso de que WhisperX devuelva timestamps vacíos o incompletos.

### 2. Selección de Modelo, CFG y Steps en la UI (Completado)
- **Control de Parámetros en UI**:
  - Se añade un selector de modelo VibeVoice (`VibeVoice-1.5B` estándar y `VibeVoice-Realtime-0.5B` de streaming).
  - Se implementan controles deslizantes (range sliders) para ajustar en tiempo real el valor de **CFG Scale** (de 1.0 a 3.0) y de **Pasos DDPM / Steps** (de 5 a 50).
- **Integración con Backend**:
  - El frontend (`app.js`) lee y envía los valores elegidos al iniciar el pipeline (`/api/process`).
  - La API de FastAPI (`main.py`) recibe los parámetros y los propaga al cliente de TTS (`generate_individual_tts` en `tts_client.py`).
  - El servidor local de VibeVoice recibe los parámetros en la petición `/api/tts` y los aplica dinámicamente antes de iniciar la generación llamando a `model.set_ddpm_inference_steps(request.ddpm_steps)` e inyectando `cfg_scale=request.cfg_scale` en la generación autoregresiva.

### 3. Visualización y Detalles del Paso Demucs (Completado)
- **Problema**: El paso de separación vocal por Demucs se ejecuta en la GPU en segundo plano pero no tiene visibilidad en la interfaz de usuario, haciendo parecer que el proceso se detiene en "Descargando video".
- **Solución**:
  - Se añade un estado de tarea `"separating"` en el backend (`main.py`) justo antes de llamar a `run_demucs_separation` estableciendo el progreso en 25%.
  - El frontend (`app.js`) maneja este nuevo estado y actualiza el título del diálogo a "Separando Voces (Demucs)", la descripción a "Separando el speaker del fondo usando Demucs offline (Aceleración GPU)..." y el color del indicador.
  - Se añade el paso detallado de separación vocal de Demucs en la sección explicativa "¿Cómo funciona?" de `index.html`.

### 4. Guardado de Chunks Simplificados (english_minimal.json / spanish_minimal.json) (Completado)
- **Problema**: El procesamiento en memoria de la simplificación de chunks de transcripción ("Compress & Merge") es óptimo en velocidad y memoria, pero no deja archivos intermedios legibles en disco para que el usuario analice el texto enviado y devuelto por el LLM.
- **Solución**:
  - Se modifica `translate_chunks` en `translator.py` para aceptar un argumento opcional `save_dir`.
  - Si se proporciona `save_dir`, la función guarda de manera paralela en disco:
    - `english_minimal.json`: los textos e intervalos de tiempo limpios (sin `words`) enviados al modelo.
    - `spanish_minimal.json`: las traducciones en bruto devueltas por Ollama antes de fusionarse con los tiempos a nivel de palabra originales.
  - Se propaga el `whisper_dir` desde `main.py` al llamar a `translate_chunks`.

### 5. Traducción con Preservación de Índices y Auto-Recuperación Focalizada (Completado)
- **Problema**: Al traducir cientos de chunks en un solo bloque (One-Shot), el LLM a veces combina o salta pequeños fragmentos (por ejemplo, devolviendo 312 traducciones para 314 chunks originales). Esto genera una discrepancia de tamaños que hace fallar la sincronización.
- **Solución**:
  - Se añade una clave `"index"` correlativa (0, 1, 2...) a cada chunk enviado en el payload de traducción (`english_minimal.json`).
  - Se actualiza el prompt del sistema para ordenar al LLM que no combine ni omita chunks y que devuelva exactamente los mismos índices.
  - Al recibir la traducción, se parsean los índices recibidos y se mapean en un diccionario.
  - Si faltan índices, el backend identifica cuáles faltan y realiza de manera automática una traducción rápida e individual de esos fragmentos faltantes con Ollama.
  - Se reconstruye la lista ordenada completa a partir de los índices recuperados, garantizando un tamaño final de salida idéntico al de entrada (100% de éxito en la sincronización).

### 6. Verdadero Paralelismo con Múltiples Servidores VibeVoice (Procesos Independientes) (En Progreso)
- **Problema**:
  - Al quitar el `lock` en el endpoint `/api/tts` de un único proceso de VibeVoice, múltiples hilos ejecutan `model.generate()` de manera concurrente en la misma instancia del modelo en GPU. Esto corrompe los KV-caches, estados y masks internos de PyTorch, causando palabras repetidas, silencios, y una alta contención que eleva el tiempo a 2800 segundos.
  - Si se usa un lock en un solo proceso, la generación es secuencial y extremadamente lenta.
- **Solución**:
  - **Múltiples Puertos y Procesos**: Modificar `vibevoice_server.py` para aceptar un parámetro `--port`, añadir el `with lock:` de vuelta a nivel de endpoint, y llamar a `torch.cuda.empty_cache()` para liberar memoria activamente.
  - **Dynamic Workers (VRAM Safe < 10GB)**: En `tts_client.py`, determinar el número de procesos servidores a levantar para no superar los 10 GB de VRAM (incluyendo el sistema operativo y navegador):
    - `0.5B Streaming`: 3 procesos independientes (puertos 8001-8003). Consume ~5.4 GB de VibeVoice + ~2 GB del sistema/pantalla = ~7.4 GB VRAM total.
    - `1.5B Standard`: 1 proceso (puerto 8001). Consume ~4.2 GB de VibeVoice + ~2 GB del sistema/pantalla = ~6.2 GB VRAM total.
  - **Balanceo en Pool de Hilos**: Distribuir las peticiones de síntesis entre los puertos activos de forma balanceada usando un pool de conexiones/puertos disponibles o round-robin.
  - **Parada Limpia**: Asegurar que al finalizar la tarea o cancelarla, se detengan todos los subprocesos en todos los puertos iniciados.

### 7. Formateo Dinámico de Textos según Arquitectura de Modelo (En Progreso)
- **Problema**:
  - En `vibevoice_server.py`, el texto enviado al modelo se formatea anteponiendo `"Speaker 1: "`. 
  - Para el modelo **0.5B Streaming**, esto causa que la voz lea literalmente "Speaker 1" al inicio de algunas frases debido a su menor escala y distinta sensibilidad al formato del prompt.
  - Para el modelo **1.5B Standard**, el formato `"Speaker 1: "` es estrictamente requerido por su arquitectura para alinear correctamente los pesos del locutor.
- **Solución**:
  - Implementar un **formateo dinámico** en `vibevoice_server.py` utilizando la bandera `is_streaming`:
    - Si `is_streaming` es `True` (0.5B): Se remueve el prefijo y se envía texto plano (`f"{request.text}\n"`).
    - Si `is_streaming` es `False` (1.5B): Se mantiene el prefijo `"Speaker 1: {request.text}\n"`.
