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
