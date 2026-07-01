# AEGIS Audio Editor / AI Video Dubber (v3.0)

Este proyecto es una aplicación web local para **traducir, doblar y editar** videos de YouTube al español de forma automatizada. Combina transcripción (WhisperX), traducción local (Ollama), síntesis de voz (VibeVoice / VoxCPM) y edición no-lineal en un estudio interactivo, orquestado bajo una arquitectura optimizada para Windows/WSL con GPUs NVIDIA.

---

## Pipeline

```mermaid
graph TD
    A[URL YouTube / Archivo Local] --> B[Descarga: yt-dlp + ffmpeg]
    B --> C[Separación de Voces: Demucs htdemucs_ft]
    C --> D[Vocals.wav]
    C --> E[Fondo Instrumental]
    D --> F[Transcripción: WhisperX + alineación de palabras]
    F --> G[Traducción One-Shot: Ollama + Auto-Corrección JSON]
    G --> H[Sanador IA: eliminación de alucinaciones + puntuación prosódica]
    H --> I[Sincronización temporal: ajuste de español a timestamps originales]
    I --> J[TTS: VibeVoice o VoxCPM]
    J --> K[Sincronización de pistas: Silence Debt Compensation]
    K --> L[Mezcla: voz doblada + fondo instrumental]
    L --> M[Fusión con video: ffmpeg]
    M --> N[QA: verificación WhisperX + accuracy]
```

### Componentes

1. **Separación (Demucs via UVR5-UI)**: Extrae voz y fondo instrumental por separado. Usa el modelo `htdemucs_ft`.

2. **Transcripción (WhisperX)**: Reconocimiento de voz con timestamps a nivel de palabra mediante alineación forzada (wav2vec2).

3. **Traducción (Ollama)**: Traducción one-shot con auto-corrección JSON (hasta 5 reintentos). Soporta cualquier modelo local o cloud.

4. **Sanador IA**: Capa post-traducción que elimina alucinaciones, agrega puntuación prosódica (!, ?) y corrige repeticiones.

5. **Sincronización Temporal**: Ajusta el español traducido a los timestamps originales usando alineación proporcional.

6. **TTS (`VibeVoice` o `VoxCPM`)**: Generación distribuida en servidores paralelos (múltiples puertos) para evitar colisiones de VRAM. Soporta clonación zero-shot de voz.

7. **Mezcla y Fusión**: Combina voz doblada con fondo instrumental a -1dB y ensambla el video final.

---

## Interactive Studio Editor (v3.0)

Editor no-lineal integrado en la web para corrección quirúrgica post-procesamiento:

- **Timeline horizontal**: Bloques de colores para Video, Audio Original (inglés) y Audio Doblado (español).
- **Regeneración por bloque**: Seleccioná un bloque, corregí el texto en el Inspector y regenerá solo ese MP3 (~5s).
- **Auditoría en tiempo real**: Escuchá el canal vocal original aislado vs el doblado.
- **Ensamblaje instantáneo**: Reconstruye el video final con los bloques corregidos sin reprocesar todo.

---

## Requisitos

### Sistema
- Python 3.10+
- FFmpeg (en PATH o ruta personalizada en `audio_processor.py`)
- Ollama corriendo localmente (puerto `11434`)
- GPU NVIDIA con CUDA (probado en RTX 5070, CUDA 12.8)
- Windows (nativo) o WSL con Ubuntu

### Dependencias Python
```
fastapi==0.111.0
uvicorn==0.30.1
yt-dlp>=2026.6.9
pydub==0.25.1
requests==2.32.3
```

---

## Instalación

1. **Clonar**:
   ```bash
   git clone https://github.com/jonnyck-dev/TRADUCTOR.git
   cd TRADUCTOR
   ```

2. **Instalar dependencias**:
   ```cmd
   setup_env.bat
   ```

3. **TTS servers**: Tener clonados VibeVoice y/o VoxCPM accesibles localmente con sus entornos Python activos.

---

## Inicio

### Windows
```cmd
run.bat
```

### WSL / Linux
```bash
./run.sh
```

Servidor en **http://localhost:8000**

---

## API Endpoints

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/api/upload` | POST | Subir video local (.mp4) |
| `/api/process` | POST | Iniciar procesamiento (URL o caché) |
| `/api/cancel/{id}` | POST | Cancelar tarea |
| `/api/status/{id}` | GET | Estado y progreso de tarea |
| `/api/models` | GET | Listar modelos Ollama disponibles |
| `/api/stream/{id}` | GET | Video doblado (HTTP 206 Partial Content) |
| `/api/caches` | GET | Listar tareas cacheadas |
| `/api/studio/{id}/data` | GET | Datos del estudio interactivo |
| `/api/studio/{id}/reprocess` | POST | Regenerar bloque del estudio |
| `/api/studio/{id}/finalize` | POST | Ensamblar video final |

---

## Interfaz Web

- Diseño glassmorphism oscuro con acentos neón
- Reproductor con subtítulos sincronizados (inglés/español)
- Panel de timers con barras de progreso por etapa
- Selector inteligente de modelos Ollama
- Simulador de caché para depuración
- Studio Editor con timeline interactivo

---

## Notas técnicas

- **VRAM**: Los servidores TTS se levantan y destruyen dinámicamente para liberar memoria.
- **WSL**: El backend detecta `os.name` y usa `wsl_to_windows_path()` o rutas nativas según corresponda.
- **Caché idempotente**: Cada etapa guarda resultados en `cache/{task_id}/`; si se interrumpe, retoma desde el último paso completo.
- **FFmpeg**: Ruta hardcodeada `C:\Users\jpzam\Downloads\audioconverter\bin\ffmpeg.exe` en Windows; `ffmpeg` en PATH en WSL/Linux.

---

## Documentación del proyecto

Este repositorio contiene varios archivos `.md` con propósitos específicos. Esta sección es para que una IA (u otro desarrollador) entienda rápidamente qué contiene cada uno y cuándo consultarlos.

| Archivo | Propósito |
|---------|-----------|
| `README.md` | Documentación principal para el usuario: descripción, instalación, uso, API, features. Punto de entrada del proyecto. |
| `implementation_plan.md` | Plan de implementación técnica: estado actual del desarrollo, migraciones pendientes (VoxCPM, uv), correcciones planificadas. Orientado a desarrolladores e IA. |
| `deployment_plan.md` | Plan de despliegue a producción: Docker, portabilidad cloud, variables de entorno, submodules. Para cuando el proyecto se mueva a un servidor. |
| `debugagent.md` | Contexto de debugging para agentes IA: historial de errores resueltos, arquitectura clave, sistema de caché. Consultar cuando se reporte un error en ejecución. |
| `benchmark_report.md` | Reporte de rendimiento comparativo entre VibeVoice y VoxCPM en diferentes escenarios (con/sin clonación, one-shot/frase, paralelo/secuencial). |

### Flujo de consulta recomendado para una IA

1. Leer `README.md` para entender el proyecto, el pipeline y cómo se instala.
2. Leer `implementation_plan.md` para conocer el estado del desarrollo y qué falta implementar.
3. Si hay un error en tiempo de ejecución, leer `debugagent.md` para contexto de debugging.
4. Si se planea desplegar, leer `deployment_plan.md`.
5. Si se necesita comparar motores TTS, leer `benchmark_report.md`.

Los planes de implementación pendientes se encuentran en `implementation_plan.md`, no en este archivo.

---

## Subproyectos

Este repositorio contiene subproyectos con su propia lógica y documentación:

| Subproyecto | Carpeta | Descripción |
|-------------|---------|-------------|
| **AEGIS Studio Editor** | `editor/` | Editor interactivo no-lineal para corrección de videos doblados. Frontend en `frontend_studio/`. |

Cada subproyecto tiene su propio `README.md` con documentación, arquitectura, plan de implementación y bugs conocidos. Consultar la carpeta correspondiente para más detalles.


