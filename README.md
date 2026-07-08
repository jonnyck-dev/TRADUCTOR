# JANUS Audio Editor / AI Video Dubber (v4.1)

Aplicación web local para **traducir, doblar y editar** videos desde y hacia **9 idiomas**. Combina transcripción (WhisperX), traducción local (Ollama), síntesis de voz (Edge TTS / VibeVoice / VoxCPM / Windows Native) y edición no-lineal en un estudio interactivo, optimizado para Windows/WSL con GPUs NVIDIA.

---

## Pipeline

```
YouTube / Local → Demucs (separación voz/fondo) → WhisperX (transcripción + timestamps por palabra)
→ Ollama (traducción one-shot) → Sanador IA (limpieza + puntuación) → Sincronización temporal
→ TTS (Edge TTS / VibeVoice / VoxCPM / Windows Native) → Mezcla con fondo → Fusión con video → QA (verificación WhisperX)
```

### Idiomas Soportados

| Idioma | Código | Transcripción | Traducción | Post-procesamiento |
|--------|--------|:---:|:---:|:---:|
| English | `en` | ✅ | ✅ | — |
| Español | `es` | ✅ | ✅ | Enhancement + fonética + sincronización |
| 日本語 | `ja` | ✅ | ✅ | — |
| Português | `pt` | ✅ | ✅ | — |
| Français | `fr` | ✅ | ✅ | — |
| Deutsch | `de` | ✅ | ✅ | — |
| Italiano | `it` | ✅ | ✅ | — |
| 한국어 | `ko` | ✅ | ✅ | — |
| 中文 | `zh` | ✅ | ✅ | — |

---

## Studio Editor Interactivo

Editor no-lineal con timeline horizontal, accesible desde `/studio`:

- **Timeline**: Bloques de colores para Video, Doblaje y Original con ruler de tiempo
- **Inspector**: Textarea editable, selectores de idioma/modelo/voz, reproducción original/doblaje
- **Regeneración por bloque**: Corregí texto y regenerá solo ese MP3 (~5s)
- **Traducción en línea**: Traducí una frase individual a otro idioma directamente desde el inspector
- **Re-transcripción con WhisperX**: Detecta frases perdidas en el gap entre dos bloques
- **Eliminación de frases**: Borrá frases sobrantes con re-indexado automático
- **Ensamblaje final**: Reconstruye el video con las correcciones sin reprocesar todo
- **Herencia paramétrica**: Los selectores del Studio heredan los valores del Home al abrirse
- **Selector de modelo Whisper**: Elegí entre tiny / small / base / medium / large-v2 / large-v3-turbo

---

## Requisitos

- Python 3.10+
- FFmpeg (se descarga automáticamente en el setup)
- Ollama corriendo localmente (puerto `11434`)
- GPU NVIDIA con CUDA (probado en RTX 5070, CUDA 12.8)
- Windows (nativo) o WSL con Ubuntu

---

## Instalación

```bash
# Windows
setup_env.bat

# Linux / WSL
./setup.sh
```

El script de setup automatiza todo: crea entornos virtuales, clona repositorios externos, descarga modelos.

---

## Inicio

```bash
# Windows
run.bat

# WSL / Linux
./run.sh
```

Servidor en **http://localhost:8000** | Studio en **http://localhost:8000/studio**

---

## API Endpoints

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/api/process` | POST | Iniciar procesamiento (URL o caché) |
| `/api/upload` | POST | Subir video local (.mp4) |
| `/api/status/{id}` | GET | Estado y progreso |
| `/api/cancel/{id}` | POST | Cancelar tarea |
| `/api/models` | GET | Listar modelos Ollama |
| `/api/stream/{id}` | GET | Video doblado (Partial Content) |
| `/api/caches` | GET | Listar tareas cacheadas |
| `/api/studio/{id}/data` | GET | Datos del estudio |
| `/api/studio/{id}/meta` | GET | Metadatos (idiomas) del estudio |
| `/api/studio/{id}/translate` | POST | Traducir frase individual |
| `/api/studio/{id}/reprocess` | POST | Regenerar bloque TTS |
| `/api/studio/{id}/retranscribe` | POST | Re-transcribir con WhisperX |
| `/api/studio/{id}/delete/{idx}` | POST | Eliminar frase |
| `/api/studio/{id}/finalize` | POST | Preparar ensamblaje final |
| `/api/studio/{id}/audio/original` | GET | Audio vocal original (slice) |
| `/api/studio/{id}/audio/dubbed/{idx}` | GET | Audio doblado por frase |

---

## Interfaz Web

- Diseño claro con superficies translúcidas y acentos dorados
- Selector de 9 idiomas (origen y destino)
- Selector de modelo WhisperX
- Selector de modelo Ollama con agrupación local/cloud
- Selector de voz y motor TTS
- Simulador de caché local para desarrollo
- Panel de timers con barras de progreso por etapa
- Studio Editor con timeline interactiva

---

## Notas técnicas

- **VRAM**: Los servidores TTS se levantan y destruyen dinámicamente.
- **WSL**: El backend detecta `os.name` y usa `wsl_to_windows_path()` automáticamente.
- **Caché idempotente**: Cada etapa guarda resultados en `cache/{task_id}/`; si se interrumpe, retoma desde el último paso.
- **FFmpeg portable**: El setup descarga FFmpeg automáticamente en `backend/bin/`.
- **CJK Smart Merge**: Los chunks cortos en japonés, chino y coreano se fusionan por caracteres (no por palabras).
- **Modelos de alineación**: Los modelos wav2vec2 para ja/zh/ko se guardan en `backend/whisperx_models/align/` (no dependen de HF cache).
- **Parámetro jerárquico**: Los selectores del Studio heredan los valores del Home al abrirse (papá → hijo).

---

## Planes

| Documento | Propósito |
|-----------|-----------|
| `frontend_landing_separation_plan.md` | Separar frontend del backend e integrarlo en janus-landing (Vercel) |
| `editor/studio_dubber_separation_plan.md` | Separar estado del Studio y del Dubber en frontend y backend |
