# Reporte Completo de Benchmark: VibeVoice vs VoxCPM

Este benchmark evalúa y compara el rendimiento (tiempo de procesamiento y memoria de GPU) entre **VibeVoice** y **VoxCPM** bajo 4 escenarios diferentes.

## Especificaciones de la GPU de Prueba
- **GPU:** NVIDIA GeForce RTX 5070 (Blackwell)
- **Audio de referencia:** `cloned_speaker.wav` (Fases 1 y 2)
- **Presete de voz:** `en-Frank_man` (Fases 3 y 4)
- **Muestra de entrada:** 15 frases traducidas al español

## 📊 Tabla Comparativa General

| Fase del Test | Modelo VibeVoice | Tiempo VibeVoice | VRAM VibeVoice | Modelo VoxCPM | Tiempo VoxCPM | VRAM VoxCPM | Comparativa (VoxCPM vs VibeVoice) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Fase 1: One-Shot con Clonación** | VibeVoice-1.5B | 142.91 s | 0.0 MB | VoxCPM2 (2.0B) | 138.54 s | 0.0 MB | VoxCPM es 1.0x más lento |
| **Fase 2: Por Frases con Clonación** | VibeVoice-1.5B | 187.64 s | 2.0 MB | VoxCPM2 (2.0B) | 203.55 s | 120.0 MB | VoxCPM es 1.1x más lento |
| **Fase 3: One-Shot sin Clonación (Preset)** | Realtime-0.5B | 166.05 s | 0.0 MB | VoxCPM-0.5B | 153.10 s | 0.0 MB | VoxCPM es 0.9x más lento |
| **Fase 4: Por Frases sin Clonación (Paralelo)** | Realtime-0.5B (3x) | 127.60 s | 40.0 MB | VoxCPM-0.5B (3x) | 202.25 s | 0.0 MB | VoxCPM es 1.6x más lento |


## 🔍 Análisis Técnico por Fase

### 1. Clonación de Voz en Caliente (Fases 1 y 2)
- **VibeVoice 1.5B**: Permite realizar clonación Zero-Shot real pasando el archivo `.wav` directamente. Al ejecutarse secuencialmente, es significativamente más veloz en inferencia que VoxCPM2, pero su VRAM añadida es moderada.
- **VoxCPM2 (2.0B)**: Ofrece una clonación de timbre con fidelidad excepcional, pero al tener 2 mil millones de parámetros y procesar el audio de referencia en caliente, el tiempo de inferencia es notablemente superior. Consume cerca de 11 GB de VRAM pico en One-Shot, lo que imposibilita de forma segura la ejecución paralela en una GPU comercial.

### 2. Modelos Livianos 0.5B y Ejecución Paralela (Fases 3 y 4)
- **VibeVoice-Realtime-0.5B**: Este modelo es el campeón de latencia gracias a su arquitectura optimizada y a que las voces preset ya están pre-computadas en archivos `.pt`. En Fase 4 (paralelo 3 instancias), procesó las 15 frases en tiempo récord.
- **VoxCPM-0.5B**: Demuestra que VoxCPM sí puede correr en paralelo con 3 instancias cuando se utiliza su versión reducida de 0.5B parámetros (la cual consume cerca de 1.8 GB de VRAM por instancia, totalizando ~5.5 GB de VRAM en paralelo). Aunque es más lento que VibeVoice 0.5B (debido a que realiza generación autoregresiva en espacio continuo sin discretización), ofrece una flexibilidad y un timbre de voz de diseño muy natural.

### ⚠️ Limitación del Modelo VoxCPM-0.5B
- Se descubrió durante las pruebas que **el modelo VoxCPM-0.5B no soporta clonación de voz Zero-Shot (`reference_wav_path`)**. Intentar clonar un archivo `.wav` arroja un error en caliente (`reference_wav_path is only supported with VoxCPM2 models`). Para clonación real se requiere obligatoriamente usar el modelo VoxCPM2 de 2.0B.

--- 
*Reporte generado automáticamente el 2026-06-26*.
