# 🎬 AI Video Dubber & Translator (Premium)

Este proyecto es una aplicación web local de nivel premium diseñada para **traducir y doblar videos de YouTube** al español de forma automatizada. Combina modelos avanzados de transcripción, traducción local/nube y síntesis de voz, todo orquestado bajo un flujo optimizado que protege el uso de VRAM y CPU en sistemas Windows/WSL con tarjetas gráficas NVIDIA (probado en RTX 5070 con CUDA 12.8).

---

## 🧠 Arquitectura y Flujo del Pipeline

El doblador de voz opera en un pipeline secuencial optimizado que mide y expone los tiempos de ejecución de cada fase en la interfaz:

```mermaid
graph TD
    A[URL YouTube] --> B[Descarga de Medios via yt-dlp]
    B --> C[Separación de Voces con Demucs htdemucs_ft]
    C --> D[Vocals.wav]
    C --> E[No_vocals.wav instrumental]
    D --> F[Transcripción WhisperX con alineación de palabras]
    F --> G[Traducción One-Shot con Ollama + Auto-Corrección JSON]
    G --> H[Clonación Zero-Shot de Voz original]
    H --> I[Generación de TTS con VibeVoice en lotes de 2 min]
    I --> J[Sincronización de audio y video vía ffmpeg]
    J --> K[Mezcla de Voces y Fondo estéreo]
    K --> L[Video Doblado y Sincronizado]
```

### Componentes Clave:

1. **Separación de Audio (Demucs)**:
   - Extrae la voz limpia (`vocals.wav`) para evitar alucinaciones en la transcripción.
   - Extrae el fondo instrumental, música y efectos (`no_vocals.wav`) mediante la mezcla estéreo de Bass, Drums y Other a -3dB.
2. **Transcripción (WhisperX)**:
   - Provee transcripción ultra precisa con marcas de tiempo a nivel de palabra mediante alineación forzada (wav2vec2).
3. **Traducción Inteligente (Ollama)**:
   - Ejecución en **modo One-Shot exclusivo** optimizando el contexto enviando solo textos y marcas básicas de tiempo (reduciendo ~70% de tokens redundantes).
   - **Corrección regex integrada (`fix_json_quotes`)**: Repara comillas dobles internas y comas omitidas antes del parser.
   - **Auto-corrección iterativa (hasta 5 intentos)**: Captura fallos de sintaxis JSON y le pide a la IA que se corrija pasándole la traza del error.
4. **Síntesis y Doblaje (VibeVoice) - v2.0**:
   - **Clonación de Voz Zero-Shot**: Extrae automáticamente una muestra de 1 minuto de la voz original del video y la usa para sintetizar el español.
   - **Arquitectura Desacoplada de Sincronización (NUEVO)**: 
     - Permite generar audio en lotes grandes (ej. 15 frases por `Batch Size`) para velocidad máxima, mientras usa una granularidad diferente para alinear el video (ej. 5 frases por `Sync Size`).
     - **WhisperX de Pasada Única**: Concatena todos los lotes de audio inyectando 1.5s de silencio y ejecuta la alineación forzada una sola vez sobre un "Super-Audio" para ahorrar VRAM y tiempo.
     - **Slicing Acústico Seguro**: Rebana el audio global aplicando 300ms de margen dinámico de padding y 25ms de Cross-Fade en los bordes para eliminar cualquier *clic* de corte.
     - **Bypass Inteligente**: Si el `Batch Size` y `Sync Size` coinciden, el sistema detecta que el recorte es innecesario, apagando WhisperX por completo para un procesamiento ultra veloz.
   - **Gestión de Ciclo de Vida**: Levanta el servidor TTS de forma dinámica antes de generar y lo apaga (`/shutdown`) de inmediato para liberar memoria gráfica. Ejecuta en **2 hilos** paralelos para proteger la estabilidad de la PC.

---

## 🛠️ Requisitos e Instalación

### Requisitos Previos (Windows Host)
- Python 3.10 o superior.
- **FFmpeg** instalado y en el PATH (o mapeado en tu ruta personalizada).
- **Ollama** instalado y corriendo localmente (puerto `11434`).
- Carpeta de **VibeVoice** clonada localmente.

### Configuración del Entorno

1. **Clonar el repositorio**:
   ```bash
   git clone https://github.com/jonnyck-dev/TRADUCTOR.git
   cd TRADUCTOR
   ```

2. **Crear enlaces simbólicos (Ejecutar como Administrador en Windows)**:
   Abre una terminal cmd de Windows con permisos de Administrador y ejecuta:
   ```cmd
   setup_symlinks.bat
   ```
   *Esto vinculará las dependencias de `VibeVoice` y `Demucs` (UVR5-UI) al backend del proyecto.*

3. **Configurar Entorno Virtual e Instalar dependencias**:
   Ejecuta el asistente:
   ```cmd
   setup_env.bat
   ```

---

## 🚀 Cómo Iniciar el Proyecto

### En Windows
Simplemente haz doble clic en `run.bat` o ejecútalo desde cmd:
```cmd
run.bat
```

### En WSL / Linux
Ejecuta el script de inicio:
```bash
./run.sh
```

El servidor web premium estará disponible en: **👉 [http://localhost:8000](http://localhost:8000)**

---

## 🎨 Interfaz Premium

La UI cuenta con un diseño glassmorphic moderno y oscuro que ofrece:
- **Selector Dinámico de Modelos de Traducción**: Ejecuta `ollama list` y llama a la API `/api/tags` en tiempo real para listar y agrupar tus modelos locales y modelos cloud (como DeepSeek, Qwen o Nemotron).
- **Panel Visual de Timers**: Muestra barras de progreso y tiempos detallados de cada etapa del pipeline (Descarga, Demucs, WhisperX, Traducción, TTS y Fusión final) tras terminar el doblaje.
- **Visor de Subtítulos (Click-to-Seek)**: Muestra la transcripción en inglés y traducción en español sincronizada. Al hacer clic sobre cualquier frase, el reproductor de video nativo saltará automáticamente al segundo exacto de inicio. (Incluye un botón <i class="fa-solid fa-eye"></i> para ocultar/mostrar la caja y mantener la interfaz limpia).
- **Restricciones Inteligentes de Procesamiento**: La UI vincula dinámicamente el `Sync Size` al `Batch Size`, evitando configuraciones ilógicas y previniendo que el servidor entre en bucles de recorte redundantes.
- **Simulador de Caché (Idempotente por Fases)**: Permite depurar y reproducir flujos de prueba sin consumir llamadas de red o GPU redundantes.
  - *Bug Fix (v2.0)*: El backend ahora verifica la existencia del archivo `video_dubbed.mp4` y el reporte QA; si ambos existen, el sistema omite instantáneamente la sincronización, mezcla, renderizado de FFmpeg y QA, reduciendo el tiempo de recarga de 150 segundos a 0.001 segundos.
  - *Midpoint Slicing (v2.1)*: El recorte de audio usa cálculo de punto medio (Zero-Overlap) y fades de 10ms, eliminando por completo el efecto de "disco rayado" o tartamudeo en las uniones fonéticas.
  - *Mix de Audio Profesional (v2.1)*: La música de fondo se reduce a -1dB (en lugar de -3dB) para proteger y resaltar el diseño de sonido original del creador.
  - *Optimización Web-Streaming (v2.1)*: 
    - La compilación final mediante FFmpeg incluye la bandera `-movflags +faststart` para mover el `moov atom` al inicio del MP4.
    - Se implementó un motor de streaming personalizado en FastAPI (`/api/stream`) que inyecta manualmente cabeceras HTTP 206 Partial Content (Accept-Ranges). Esto permite que navegadores basados en Chromium (Chrome, Brave) puedan adelantar la barra de navegación (seek-bar) libremente sin reiniciar la carga del video.
