# Plan de Implementación — Split por Frase Individual

## Objetivo

Hacer que el Studio Editor trabaje a nivel de **frase individual** en vez de grupos de N frases. Cada bloque en la timeline = 1 frase, cada audio = 1 frase, cada regeneración = 1 frase.

## Estado: COMPLETADO

| Paso | Cambio | Archivo | Estado |
|------|--------|---------|--------|
| 1 | Split por frase individual post-sync | `backend/main.py` + `audio_processor.py` | ✅ |
| 2 | `/data` devuelve `phrases` en vez de `batches` | `backend/main.py` | ✅ |
| 3 | `/dubbed/{phrase_index}` busca por frase | `backend/main.py` | ✅ |
| 4 | `/reprocess` regenera 1 frase via `phrase_index` | `backend/main.py` | ✅ |
| 5 | Frontend adaptado a `phrase_index` | `frontend_studio/app.js` | ✅ |
| 6 | Verificación con video completo | — | ⬜ Pendiente |

## Cambios realizados

### 1. Pipeline TTS
Después de `process_super_audio_with_whisperx()`, se agregó una tercera pasada que divide cada bloque de `sync_size` en frases individuales usando `proportional_split()` sobre el audio sincronizado. Los archivos se guardan como `phrase_{global_idx}.wav` en `tts/`. Se reemplazan `tts_chunks_for_sync` y `mp3_paths_for_sync` con las listas individuales.

### 2. Endpoint /data
Ya no acepta `?batch_size=`. Devuelve `{ status, phrases: [{ phrase_index, text, start_time, end_time }] }` iterando `data["chunks"]` directamente.

### 3. Endpoint /dubbed/{phrase_index}
Busca `tts/phrase_{phrase_index}.wav` o `.mp3` directamente (sin multiplicar por batch_size).

### 4. Endpoint /reprocess
Recibe `phrase_index` en vez de `batch_index`. Actualiza `data["chunks"][req.phrase_index]["text"]`. Recorta vocal de referencia para UNA sola frase usando sus timestamps exactos.

### 5. Frontend
- `loadStudioData()` sin `batch_size`, lee `data.phrases`
- `renderTimeline()` itera `phrases`, renderiza 1 bloque por frase
- `selectStudioBlock(phrase)` muestra "Frase #N"
- Reproductores y regeneración usan `phrase_index`

## Riesgos (vigentes)

| Riesgo | Mitigación |
|--------|------------|
| Más archivos en disco (~46 WAVs de 1-2s) | Espacio despreciable (~50 MB total) |
| WhisperX puede fallar en frases muy cortas | `proportional_split()` como fallback |
| Ruido de click en bordes de slice | Usar 10ms fade in/out (ya implementado) |
| Regeneración de 1 frase puede no encajar temporalmente | Mantener el timestamp original de la frase |

## V4.0: Multi-Language Support (Completado)

### Cambios realizados

| # | Cambio | Archivo |
|---|--------|---------|
| 1 | Guardar `task_meta.json` en cache | `backend/main.py` |
| 2 | Endpoint `/api/studio/{id}/meta` | `backend/main.py` |
| 3 | `get_studio_data()` devuelve `source_language` + `target_language` | `backend/main.py` |
| 4 | `get_latest_script_path()` auto-detecta idioma desde meta | `backend/main.py` |
| 5 | Labels dinámicos en Studio UI | `frontend_studio/index.html` |
| 6 | `eng/esp` → `source/target` en datos de subtítulos | `frontend_studio/app.js` |
| 7 | CSS classes `.text-eng/.text-esp` → `.text-source/.text-target` | `frontend_studio/style.css` |
| 8 | Botones "Inglés/Español" → "Original/Doblaje" dinámicos | `frontend_studio/index.html` |
| 9 | Track labels y success messages dinámicos | `frontend_studio/app.js` |

## V4.1: Traducción Individual en Inspector (Completado)

### Problema
Cuando el usuario retranscribe una frase con WhisperX, obtiene el texto en idioma original pero no hay forma de traducirlo al idioma destino. El botón "Regenerate Audio" solo genera TTS con el texto actual del textarea, sin pasar por el pipeline de traducción.

### Solución aplicada
Sistema jerárquico de parámetros (Papá → Hijo) + botón "Traducir con IA" en el Inspector.

| # | Cambio | Archivo |
|---|--------|---------|
| 1 | Agregar `select-studio-target-lang` (Idioma Destino) en Inspector | `frontend/index.html` |
| 2 | Agregar `select-studio-model` (Modelo Ollama) en Inspector | `frontend/index.html` |
| 3 | Agregar botón `btn-studio-translate` (Traducir con IA) en Inspector | `frontend/index.html` |
| 4 | Función `loadStudioModels()` para cargar modelos Ollama en Inspector | `frontend/app.js` |
| 5 | Herencia de parámetros: Inspector hereda valores del "papá" al abrir | `frontend/app.js` |
| 6 | Event listener `btnStudioTranslate` → llama endpoint `/translate` | `frontend/app.js` |
| 7 | Modelo `TranslateRequest` y endpoint `POST /api/studio/{id}/translate` | `backend/main.py` |
| 8 | Pipeline completo: translate → enhance → phonetic → sync para 1 frase | `backend/main.py` |

### Arquitectura Jerárquica de Parámetros

```
PAPÁ (Home View - Parámetros Iniciales)
├── Modelo de Traducción (select-model)
├── Idioma Original (select-source-lang)
├── Idioma Destino (select-target-lang)
├── Modelo TTS (select-tts-model)
├── Voz (select-speaker)
├── CFG, Steps, Batch, Sync
│
└── HIJO (Inspector del Studio - Sobrescribe localmente)
    ├── Idioma Original (select-studio-source-lang) ← hereda del papá
    ├── Idioma Destino (select-studio-target-lang) ← hereda del papá
    ├── Modelo Ollama (select-studio-model) ← hereda del papá
    ├── Modelo TTS (select-studio-tts-model) ← hereda del papá
    ├── Voz (select-studio-speaker) ← hereda del papá
    │
    └── REGLA: Cambiar el HIJO NO afecta al PAPÁ ni a otros HIJOS
```

### Flujo de Traducción Individual

```
1. Usuario selecciona frase en timeline
2. (Opcional) Retranscribe con WhisperX → texto en idioma original
3. Usuario hace clic en "Traducir con IA"
4. Frontend envía POST /api/studio/{id}/translate
   { phrase_index, source_language, target_language, model }
5. Backend ejecuta pipeline completo para UNA frase:
   a. translate_chunks() → Ollama one-shot
   b. enhance_translation_for_tts() → Sanador IA (si target=spanish)
   c. phonetic_normalization_for_tts() → Fonética (si target=spanish)
   d. synchronize_translation_for_tts() → Reductor IA (si target=spanish)
6. Backend actualiza JSON script con texto traducido
7. Frontend actualiza textarea y timeline
8. Usuario puede regenerar TTS con el texto traducido
```

### Flujo

```
1. Main Dubber completa tarea → guarda task_meta.json {source_language, target_language}
2. Usuario abre Studio Editor
3. Frontend llama GET /api/studio/{id}/meta → obtiene idiomas
4. Frontend llama GET /api/studio/{id}/data → obtiene phrases + idiomas
5. UI se actualiza con nombres de idioma reales (ej: "Japonés" / "Español")
6. Backward compat: sin task_meta.json → defaults English/Spanish
```

### task_meta.json (cache)
```json
{
  "source_language": "Japanese",
  "target_language": "Spanish",
  "created_at": "...",
  "model": "gemma4:e2b-it-qat",
  "tts_model": "openbmb/VoxCPM2",
  "speaker": "cloned_speaker"
}
```
