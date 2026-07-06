# Arquitectura del Studio Editor

## Layout (frontend_studio/index.html)

```
┌─────────────────────────────────────────────────┐
│  JANUS AUDIO EDITOR v4.1    [← Volver al Inicio] │
├──────────────────────┬──────────────────────────┤
│                      │  INSPECTOR               │
│   VIDEO PLAYER       │  ┌────────────────────┐  │
│                      │  │ Bloque #3           │  │
│                      │  │ [12:30 - 12:45]     │  │
│                      │  ├────────────────────┤  │
│                      │  │ TRANSCRIPT (Español)│  │
│                      │  │ [textarea editable] │  │
│                      │  ├────────────────────┤  │
│                      │  │ [🔊 Inglés][▶ Español]│  │
│                      │  │ [🔄 Regenerar Audio] │  │
│                      │  └────────────────────┘  │
├──────────────────────┴──────────────────────────┤
│  TIMELINE                     [🎬 Ensamblar]     │
│  ┌────┬────────────────────────────────────────┐ │
│  │ V1 │  ████████████████████████████████████  │ │
│  │ A1 │  ██░░██░░░░██░░░░██░░██░░░░██░░░░░░  │ │
│  │ A2 │  ████░░████░░░░████░░████░░░░████░░░░  │ │
│  └────┴────────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘
```

## Endpoints del backend (main.py)

### GET /api/studio/{task_id}/data
- Lee `spanish_enhanced.json` o `spanish_translated.json`
- Devuelve chunks individuales (1 frase = 1 bloque)
- Devuelve `{ status, phrases: [{ phrase_index, text, start_time, end_time }] }`

### GET /api/studio/{task_id}/audio/original?start=X&end=Y
- Recorta `vocals.wav` desde start a end + padding 200ms
- Devuelve MP3 stream

### GET /api/studio/{task_id}/audio/dubbed/{phrase_index}
- Busca `tts/phrase_{phrase_index}.wav` o `.mp3`
- Devuelve el archivo (con cache-busting)

### POST /api/studio/{task_id}/reprocess
- Recibe `{ phrase_index, text, speaker, tts_model, tts_cfg, tts_steps }`
- Actualiza `spanish_enhanced.json` → `data["chunks"][req.phrase_index]["text"]`
- Recorta vocal de referencia de `vocals.wav`
- Llama al TTS server
- Guarda nuevo `phrase_{phrase_index}.wav`

### POST /api/studio/{task_id}/translate
- Recibe `{ phrase_index, source_language, target_language, model }`
- Lee el chunk actual del JSON script
- Ejecuta pipeline completo de traducción para UNA frase:
  - `translate_chunks()` → Ollama one-shot
  - `enhance_translation_for_tts()` → Sanador IA (si target=spanish)
  - `phonetic_normalization_for_tts()` → Fonética (si target=spanish)
  - `synchronize_translation_for_tts()` → Reductor IA (si target=spanish)
- Salva `orig_text` (texto original) y `text` (traducido) en el chunk
- Devuelve `{ status, phrase_index, translated_text, original_text }`

### POST /api/studio/{task_id}/finalize
- Limpia outputs anteriores
- Mensaje al usuario para re-ensamblar con caché

## Flujo de datos actual (CON BUG)

```
translated_chunks (46 frases individuales)
        │
        ▼
Agrupar por batch_size=15 → 4 grupos
        │
        ▼
TTS → phrase_0.mp3 (15 frases), phrase_1.mp3 (15), etc.
        │
        ▼
process_super_audio_with_whisperx()
  → super-audio + WhisperX
  → slicing por sync_size=5 → sync_slice_0.wav a sync_slice_9.wav
        │
        ▼
sync_individual_phrases(sync_slice_X.wav) → sincronización final
        │
        ▼
Studio: /data agrupa por batch_size=5 → 10 bloques
Studio: /dubbed/{index} busca phrase_{index}.mp3 ❌
```

## El bug fundamental

| Componente | Granularidad | Archivo |
|------------|-------------|---------|
| TTS genera | batch_size=15 | `phrase_0.mp3` (15 frases) |
| Sync-slice produce | sync_size=5 | `sync_slice_0.wav` (5 frases) |
| Studio /data devuelve | batch_size=5 | 10 bloques de 5 frases |
| Studio /dubbed busca | 1 bloque | `phrase_0.mp3` ❌ |

**Problema**: `batch_size` (TTS) y `sync_size` (post-slicing) pueden ser diferentes, y el endpoint `/dubbed` siempre apunta a `phrase_{index}.mp3` que fue generado con `batch_size`. Si `batch_size=15` y `sync_size=5`, `phrase_1.mp3` contiene frases 15-29 pero el bloque 1 del Studio debería contener frases 5-9.

Además, cada bloque del Studio contiene **5 frases** en un solo archivo de audio. El usuario no puede editar frase por frase.

## Flujo deseado (post-implementación)

```
translated_chunks (46 frases individuales)
        │
        ▼
TTS → super-audio → WhisperX → split por sync_size → split por frase individual
        │
        ▼
phrase_0.wav (frase 0), phrase_1.wav (frase 1), ..., phrase_45.wav (frase 45)
        │
        ▼
Studio: /data devuelve chunks individuales
Studio: /dubbed/{i} busca phrase_{i}.wav ✓
Studio: reprocess regenera UNA frase
        │
        ▼
Sincronización final con sync_individual_phrases() por frase individual
```
