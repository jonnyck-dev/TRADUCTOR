# Bugs conocidos del Studio Editor

## [BUG-001] Desync entre bloques del Studio y archivos de audio

**Severidad**: Alta
**Estado**: FIXED — Split por frase individual implementado
**Archivos afectados**: `backend/main.py`, `frontend_studio/app.js`

### Descripción (obsoleto)
El Studio agrupa chunks por `batch_size` para mostrar bloques en la timeline, pero el endpoint `/dubbed/{batch_index}` busca archivos generados con otro `batch_size`.

**Solución aplicada**: Split post-sync por frase individual (`proportional_split()` en `audio_processor.py`). Ahora `phrase_{i}.wav` = 1 frase. El Studio trabaja a nivel de `phrase_index`.

---

## [BUG-002] `batch_index` en reprocess no coincide con slicing de super-audio

**Severidad**: Alta
**Estado**: FIXED — Reprocess ahora usa `phrase_index` directamente
**Archivos afectados**: `backend/main.py`

### Descripción (obsoleto)
El endpoint `/reprocess` usaba `batch_index * batch_size` para calcular el rango de chunks, causando desajuste tras el re-slicing por sync_size.

**Solución aplicada**: `/reprocess` recibe `phrase_index` y actualiza un único chunk `data["chunks"][req.phrase_index]`.

---

## [BUG-003] Botón "Volver al Inicio" cierra la ventana en modo standalone

**Severidad**: Baja
**Estado**: Confirmado
**Archivos afectados**: `frontend_studio/app.js`

### Descripción
`openHomeView()` ejecuta `window.close()`. En modo standalone, si el navegador no permite `window.close()` (porque no se abrió con `window.open()`), no pasa nada y el usuario queda atrapado.
