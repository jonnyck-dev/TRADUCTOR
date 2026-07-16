# JANUS Dubber / JANUS Editor (v4.2)

Aplicación web local para **traducir, doblar y editar** videos desde y hacia **9 idiomas**. Combina transcripción (WhisperX), traducción local (Ollama), síntesis de voz (OmniVoice / Edge TTS / VibeVoice / VoxCPM / Windows Native) y edición no-lineal en un estudio interactivo, optimizado para Windows/WSL con GPUs NVIDIA.

---

## Pipeline

```
YouTube / Local → Demucs (separación voz/fondo) → WhisperX (transcripción + timestamps por palabra)
→ Ollama (traducción one-shot) → IAs de Post-Procesamiento (opcionales) → Sincronización temporal
→ TTS (OmniVoice / Edge TTS / VibeVoice / VoxCPM / Windows Native) → Mezcla con fondo → Fusión con video → QA (verificación WhisperX)
```

### IAs de Post-Procesamiento (controlables por checkbox)

| IA | Función | Default |
|---|---|---|
| **Sanador IA** | Limpia repeticiones, corrige errores de traducción, agrega puntuación emocional | ✅ On |
| **Fonética IA** | Convierte números y acrónimos a pronunciación española (necesaria para VoxCPM/VibeVoice, auto-off para OmniVoice/Edge) | ✅ On |
| **Reductor IA** | Acorta frases que exceden el tiempo disponible del video | ✅ On |

### OmniVoice — Voice Cloning (600+ idiomas)

```
Cloned Speaker (10s inglés) → Puente VoxCPM2 (1 frase, ~53s one-time)
  → ref_es_bridge.wav (español con la voz clonada)
  → OmniVoice genera todas las frases en español nativo (~6x tiempo real)
```

Parámetros recomendados: CFG=2.0, Steps=16 (se auto-configuran al seleccionar OmniVoice).

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

## Motores TTS

| Motor | Tipo | Parámetros | Voz Clonada | Notas |
|-------|------|------------|-------------|-------|
| **OmniVoice** | Local (GPU) | 0.6B | ✅ | 600+ idiomas, RTF 0.025, 3 workers paralelos |
| **VoxCPM2** | Local (GPU) | 2.0B | ✅ | Alta fidelidad, 1 worker |
| **VibeVoice 1.5B** | Local (GPU) | 1.5B | ❌ | Standard, 1 worker |
| **VibeVoice 0.5B** | Local (GPU) | 0.5B | ❌ | Streaming, 3 workers paralelos |
| **Edge TTS** | Online | — | ❌ | Sin GPU, 300+ voces neurales Microsoft |
| **Windows Native** | Local | — | ❌ | Velocidad inmediata, sin GPU |

---

## Notas técnicas

- **VRAM**: Los servidores TTS se levantan y destruyen dinámicamente. OmniVoice y VoxCPM2 comparten el mismo entorno virtual.
- **WSL**: El backend detecta `os.name` y usa `wsl_to_windows_path()` automáticamente.
- **Caché idempotente**: Cada etapa guarda resultados en `cache/{task_id}/`; si se interrumpe, retoma desde el último paso. El bridge VoxCPM2 → OmniVoice se cachea como `ref_es_bridge.wav`.
- **FFmpeg portable**: El setup descarga FFmpeg automáticamente en `backend/bin/`.
- **CJK Smart Merge**: Los chunks cortos en japonés, chino y coreano se fusionan por caracteres (no por palabras).
- **Modelos de alineación**: Los modelos wav2vec2 para ja/zh/ko se guardan en `backend/whisperx_models/align/` (no dependen de HF cache).
- **Parámetro jerárquico**: Los selectores del Studio heredan los valores del Home al abrirse (papá → hijo).
- **Auto-configuración TTS**: Al seleccionar OmniVoice → CFG=2.0, Steps=16. VoxCPM2 → CFG=2.0, Steps=10. Fonética IA se desactiva automáticamente para OmniVoice y Edge TTS.
- **Documentación interna**: Los archivos de planificación, bugs y arquitectura están en `documentacion/` (no trackeados en git).

---
