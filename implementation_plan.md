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
   - Actualización del selector en `index.html` organizando los modelos con `<optgroup>` y añadiendo las opciones reales de tu máquina.
9. **Registro y Visualización de Timers (Optimización)**:
   - Medición precisa de cada fase en el backend (`process_translation_task` en `backend/main.py`) guardando los resultados en `timing_report.json` dentro del directorio de caché de la tarea.
   - Integración visual en el frontend (`index.html`, `app.js`, `style.css`) mediante un panel interactivo con barras de progreso de colores para cada fase y resumen de duración total, permitiendo diagnosticar cuellos de botella con facilidad.
10. **Interfaz Adaptativa y Renderizado Nativo (UI/UX)**:
   - Uso de la propiedad CSS `color-scheme: dark;` a nivel de raíz (`:root`) para delegar el renderizado de componentes base al navegador.
   - Esto obliga a Chrome/Edge a utilizar versiones con diseño oscuro de controles nativos como `<select>` (menús desplegables) y scrollbars sin requerir hacks de CSS.
   - Soluciona de forma limpia problemas de ilegibilidad y permite una fácil transición futura a modos claros dinámicos (`color-scheme: light dark;`).

---

## 🎯 Plan de Migración a VoxCPM2 y Correcciones Activas

### 1. Creación de Entorno Virtual y Conservación de VibeVoice (Pendiente)
- **Conservar Vínculo Simbólico**: **NO se eliminará ni se romperá** el enlace simbólico `backend/vibevoice` para preservar la compatibilidad con el código anterior y proteger los archivos locales del host.
- **Arquitectura Pluggable (TTS Modular)**: Diseñaremos el sistema de forma que se pueda alternar entre **VoxCPM2** y **VibeVoice** dinámicamente mediante la configuración del frontend o una variable del backend (`tts_engine`).
- **Crear Entorno Virtual para VoxCPM**: Crear un entorno de Windows dedicado en `backend/VoxCPM/env_voxcpm` para aislar sus dependencias de 2B parámetros:
  ```cmd
  cd /d G:\IA\PROYECTOS\Traductor\backend\VoxCPM
  python -m venv env_voxcpm
  ```
- **Instalar Dependencias en env_voxcpm**:
  - Activar el entorno virtual e instalar PyTorch con soporte CUDA:
    ```cmd
    env_voxcpm\Scripts\activate
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
    ```
  - Instalar el paquete `voxcpm` en modo editable y librerías auxiliares:
    ```cmd
    pip install -e .
    pip install fastapi uvicorn requests pydantic soundfile
    ```

### 2. Creación del Servidor FastAPI de VoxCPM (`backend/voxcpm_server.py`) (Pendiente)
- **Problema**: Necesitamos un backend persistente para cargar el modelo VoxCPM2 en VRAM y responder consultas rápidamente sin el overhead de re-inicialización en cada frase.
- **Solución**:
  - Crear [backend/VoxCPM/voxcpm_server.py](file:///mnt/g/IA/PROYECTOS/Traductor/backend/VoxCPM/voxcpm_server.py) exponiendo un endpoint `/api/tts` y un endpoint `/shutdown`.
  - El servidor cargará `openbmb/VoxCPM2` con soporte CUDA, `load_denoiser=False` y en `torch.bfloat16` para optimizar memoria.
  - Implementar un mutex de concurrencia (`with lock:`) para proteger la generación del modelo, asegurando la seguridad de hilos en PyTorch a nivel de proceso único.
  - Liberar la memoria de la GPU tras cada generación mediante `torch.cuda.empty_cache()` para mantener el consumo general bajo el límite estricto de **10 GB de VRAM**.
  - Este servidor coexistirá con `vibevoice_server.py`, permitiendo levantar el correspondiente según el motor seleccionado.

### 3. Refactorización del Cliente TTS (`backend/tts_client.py`) (Pendiente)
- **Problema**: El cliente actual está configurado específicamente para comunicarse con el servidor y parámetros de VibeVoice, e inicia múltiples servidores paralelos. Además, el acoplamiento a nombres como `vibevoice_` genera confusión al migrar de modelo.
- **Solución**:
  - **Generalizar Nomenclatura**: Renombrar funciones y variables obsoletas de VibeVoice a términos genéricos de TTS para desacoplar el código:
    - `start_vibevoice_servers` -> `start_tts_server`
    - `stop_vibevoice_servers` -> `stop_tts_server`
    - `vibevoice_model` -> `tts_model`
    - `vibevoice_cfg` -> `tts_cfg`
    - `vibevoice_steps` -> `tts_steps`
  - Modificar las funciones para iniciar/detener **únicamente 1 servidor** de `voxcpm_server.py` en el puerto `8001` (para realizar pruebas de rendimiento base y medir velocidad sin saturar la VRAM).
  - Configurar el cliente para realizar llamadas secuenciales al servidor (con un pool de tamaño 1) para evaluar el rendimiento inicial. Si Joan decide que requiere mayor velocidad, escalaremos posteriormente a 2-3 instancias paralelas.
  - Mapear los parámetros de la petición hacia VoxCPM2:
    - `tts_cfg` -> `cfg_value` (VoxCPM2 acepta de 1.0 a 3.0, recomendado: 2.0).
    - `tts_steps` -> `inference_timesteps` (Recomendado: 10 o 15).
  - Configurar la clonación Zero-Shot: si se selecciona `cloned_speaker`, pasar la ruta de `cloned_speaker.wav` directamente a `reference_wav_path` en `model.generate()`.
  - *Nota*: Por simplicidad y YAGNI, usaremos el modo **Controllable Voice Cloning** básico pasándole solo `reference_wav_path` para lograr una clonación de timbre de alta fidelidad sin la sobre-ingeniería de transcribir la muestra de voz en inglés.

### 4. Actualización del Frontend (UI y Controladores) (Pendiente)
- **Problema**: El selector de modelos de síntesis y las etiquetas de la interfaz siguen mostrando VibeVoice y enviando parámetros específicos del modelo anterior.
- **Solución**:
  - Actualizar [frontend/index.html](file:///mnt/g/IA/PROYECTOS/Traductor/frontend/index.html) para renombrar los títulos a **VoxCPM2** y remover los modelos obsoletos de VibeVoice.
  - Actualizar los range sliders y selectores de la interfaz para enviar variables genéricas (`tts_model`, `tts_cfg`, `tts_steps`) al backend.
  - Adaptar [frontend/app.js](file:///mnt/g/IA/PROYECTOS/Traductor/frontend/app.js) para mapear estas nuevas variables al pipeline `/api/process`.

### 5. Migración de Infraestructura (Gestor de Paquetes Moderno) (Pendiente)
- **Problema**: El proyecto utiliza actualmente `venv` y `pip` tradicionales, lo que causa demoras significativas (5-10 minutos) al instalar entornos pesados para modelos de audio y aumenta el riesgo de "Dependency Hell" (conflictos entre versiones de PyTorch, CUDA y librerías).
- **Solución**:
  - **Migrar a `uv` (Astral)**: Reemplazar todas las creaciones de entorno virtual y comandos de instalación en los archivos `.bat` para usar el gestor ultrarrápido en Rust (`uv venv` y `uv pip install`).
  - Esto nos permitirá usar el caché global mediante hardlinks, reduciendo la instalación de librerías masivas como PyTorch a simples segundos, resolviendo cualquier conflicto de dependencias al instante y mejorando drásticamente los tiempos de actualización del proyecto.

---

## Optimizaciones pendientes

### 1. Servidor TTS persistente
- **Contexto**: Actualmente el servidor TTS (VibeVoice/VoxCPM) se inicia y destruye por cada tarea para liberar VRAM.
- **Cuándo implementar**: Cuando el proyecto se despliegue en un servidor dedicado o se entregue al usuario final.
- **Objetivo**: Mantener el servidor TTS vivo entre tareas para evitar la recarga del modelo (~30s) en cada procesamiento.

### 2. Entorno mínimo por motor
- **Contexto**: Cada entorno Python (VibeVoice, Demucs, etc.) tiene paquetes no usados que ocupan espacio (~2 GB innecesarios).
- **Objetivo**: Crear `requirements_tts_minimal.txt` eliminando gradio, whisperx, pyannote, datasets, optuna, pytorch_lightning, etc. Reducir tiempo de importación y espacio en disco.

### 3. Fusión de shards del modelo
- **Contexto**: El checkpoint de VibeVoice-1.5B tiene 3 archivos `.safetensors` (~1.8 GB c/u) que se cargan secuencialmente.
- **Objetivo**: Fusionarlos en un solo `model.safetensors` para reducir overhead de carga (~1-2s más rápido).
- **Nota**: Requiere respaldar los shards originales antes de ejecutar. Se modifica el proyecto VibeVoice, no el Traductor.

### 4. Optimización de Arquitectura de Separación (Demucs Puro)
- **Problema**: Actualmente se usa el entorno pesado `audio-separator` (basado en UVR5) que acarrea "Cold Starts" lentos (10-20s) debido al exceso de librerías innecesarias (Gradio, PyQt, etc.) y la abstracción pesada al cargar el modelo `htdemucs_ft`.
- **Solución (Fase Local)**:
  - Eliminar por completo el entorno UVR5/`audio-separator`.
  - Instalar el paquete oficial de Meta (`demucs` puro, sin GUI) usando `uv` en un entorno virtual limpio (`venv_demucs`).
  - Mantener la arquitectura de carga/descarga bajo demanda (arrancar subproceso, procesar, destruir) para no acaparar memoria VRAM que necesitan VoxCPM2 y Ollama, pero el tiempo de carga caerá drásticamente por no tener "grasa".
- **Solución (Fase Servidor/Nube - A Futuro)**:
  - Crear un microservicio residente `demucs_server.py` que mantenga los tensores del modelo precargados en la VRAM de la GPU permanentemente.
  - Esto reducirá la latencia de inicio de separación a **0 milisegundos**, siendo el estándar de la industria para despliegues escalables donde la VRAM no es un cuello de botella compartido.
