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
   - Actualización del selector en `index.html` organizando los modelos con `<optgroup>` y añadiendo las opciones reales de tu máquina (`deepseek-v4-pro:cloud`, `deepseek-v4-flash:cloud`, `nemotron-3-nano:30b-cloud`, `qwen3.5:cloud`, `gemma4:31b-cloud`).
9. **Registro y Visualización de Timers (Optimización)**:
   - Medición precisa de cada fase en el backend (`process_translation_task` en `backend/main.py`) guardando los resultados en `timing_report.json` dentro del directorio de caché de la tarea.
   - Integración visual en el frontend (`index.html`, `app.js`, `style.css`) mediante un panel interactivo con barras de progreso de colores para cada fase y resumen de duración total, permitiendo diagnosticar cuellos de botella con facilidad.

---

## 🎯 Próximas Mejoras & Futuras Implementaciones

### 1. Resolución del Problema de Pronunciación de Números en VibeVoice
* **Observación**: VibeVoice tiende a pronunciar todos los números en inglés (por ejemplo, diciendo "three hundred" en lugar de "trescientos") aun cuando el texto se encuentra en español.
* **Propuesta**: Implementar un preprocesador de texto en el backend que convierta todos los números a su representación en palabras en español (ej: `300` -> `trescientos`, `43%` -> `cuarenta y tres por ciento`) antes de enviarlo a la API de VibeVoice.

### 2. Sincronización Avanzada: Sistema de Compensación por Deuda de Silencio (Silence Debt)
* **Observación**: Algunas frases se escuchan extremadamente lentas (slowmotion, ej: *"como siempre, gracias por vernos"*) o demasiado rápidas al intentar encajar con la línea de tiempo original.
* **Propuesta de Arquitectura (Silence Debt Compensation)**:
  - En lugar de estirar o encoger de forma agresiva cada frase de manera aislada (generando slowmotion o aceleraciones molestas), el pipeline mantendrá una **cuenta acumulada de silencio** (deuda de silencio).
  - Si una frase es más larga que su espacio original, en lugar de acelerarla al máximo, puede "tomar prestado" tiempo del silencio del futuro (el espacio libre entre la frase actual y la siguiente).
  - La "deuda" se iría pagando retrasando ligeramente el inicio de las frases siguientes o recortando silencios futuros innecesarios, ajustando dinámicamente el timeline hasta balancear la sincronización natural sin alterar la velocidad inteligible de la voz.

### 4. Optimizaciones de Traducción y Gestión de Caché (Fase de Optimización Activa)
* **Reducción de Temperatura (Ollama)**: Configurar la temperatura de traducción a `0.0` para que el modelo sea determinista y siga fielmente el formato JSON solicitado.
* **Auto-Corrección Inteligente de JSON Iterativa (LLM)**: Capturar errores `JSONDecodeError` y realizar un bucle de corrección interactivo con el LLM de hasta **5 intentos**, enviándole la traza del error de sintaxis y el JSON malformado para que devuelva el fragmento corregido, garantizando que el One-Shot se rescate en caso de errores de puntuación o comillas.
* **Corrección Programática de Comas y Comillas**:
  - Implementar un preprocesador regex `fix_json_quotes` en [translator.py](file:///mnt/g/IA/PROYECTOS/Traductor/backend/translator.py) para escapar comillas dobles internas en strings de texto.
  - Reparar programáticamente la falta de comas `,` entre las propiedades `"text"` y `"timestamp"`, y entre los objetos `{}` y corchetes `[]` del array de chunks en el JSON, previniendo errores de delimitador sin necesidad de reintentos con la IA.
* **Carga Dinámica de Modelos (Ollama list)**:
  - Crear un endpoint backend `/api/models` que consulte la API local de Ollama (`/api/tags`) o ejecute `ollama list` para obtener los modelos reales instalados.
  - **Diagnóstico y Corrección de Bloqueo (Completado)**: Se diagnosticó que al lanzar el servidor backend desde el entorno WSL hacia el host de Windows mediante `cmd.exe /c "run.bat"`, la falta de redirección de entrada estándar (`< /dev/null`) causaba que el proceso de Windows se suspendiera esperando entrada (stdin), impidiendo que levantara el servidor en el puerto 8000. Además, de forma preventiva, se configuró `stdin=subprocess.DEVNULL` en la llamada a `subprocess.run(["ollama", "list"])` en `main.py` para asegurar que las llamadas internas al CLI de Ollama nunca se congelen.
  - Actualizar el dropdown del frontend (`select-model`) para agrupar dinámicamente los modelos en locales y cloud según su etiqueta, eliminando nombres hardcodeados.
* **Compresión y Fusión de Chunks (Extract & Merge)**:
  - En lugar de enviar la estructura completa de WhisperX (que contiene arrays de palabras detalladas con sus timestamps individuales), el backend extraerá un JSON minimalista que contenga únicamente `"text"` y `"timestamp"` para cada frase.
  - Esto ahorra un ~70% de tokens de contexto, acelera la traducción en Ollama y elimina errores de sintaxis causados por el volumen de datos.
  - Una vez traducido, el backend fusionará la traducción en español de vuelta al JSON completo original de WhisperX segmentado, sobreescribiendo el campo `"text"` y preservando intactos los arrays `"words"`.
* **Subdirectorio de Separación de Audio en Caché**:
  - Crear la carpeta dedicada `audio_separation` en el directorio de caché de cada tarea para almacenar los stems de Demucs (`vocals.wav`, `no_vocals.wav`, etc.), manteniendo el espacio ordenado junto a `downloads`, `whisper` y `tts`.
