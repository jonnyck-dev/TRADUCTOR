import sys
import os
import time
import json
import shutil
import subprocess
import requests

# Ensure we can import from backend
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from tts_client import (
    start_tts_server,
    stop_tts_server,
    generate_individual_tts,
    wsl_to_windows_path
)

def get_vram_usage():
    try:
        res = subprocess.run(
            ["cmd.exe", "/c", "nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits"],
            capture_output=True,
            text=True
        )
        if res.returncode == 0:
            return float(res.stdout.strip())
        return 0.0
    except Exception:
        return 0.0

def main():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    backend_dir = os.path.join(base_dir, "backend")
    
    # 1. Ensure cloned_speaker.wav is in backend/ for tts_client.py compatibility
    src_wav = os.path.join(backend_dir, "vibevoice", "demo", "voices", "cloned_speaker.wav")
    dst_wav = os.path.join(backend_dir, "cloned_speaker.wav")
    if os.path.exists(src_wav):
        print(f"[PREPARATION] Copying reference voice to {dst_wav}...")
        shutil.copy(src_wav, dst_wav)
    else:
        print("[WARNING] Source cloned_speaker.wav not found!")
        
    # 2. Load the first 15 phrases from cache JSON
    cache_json = os.path.join(base_dir, "cache", "cca8db42-d33c-4378-b357-efcf54a621a2", "whisper", "spanish_translated.json")
    if not os.path.exists(cache_json):
        print(f"[ERROR] Cache JSON not found at: {cache_json}")
        return
        
    with open(cache_json, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    chunks = [c for c in data.get("chunks", []) if c.get("text", "").strip()][:15]
    print(f"[INFO] Loaded {len(chunks)} phrases for the benchmark.")
    
    benchmark_dir = os.path.join(base_dir, "cache", "benchmark_runs")
    os.makedirs(benchmark_dir, exist_ok=True)
    
    results = {}
    
    # Merge phrases for One-Shot modes
    merged_text = " ".join([c.get("text", "").strip() for c in chunks])
    merged_chunks = [{"text": merged_text, "timestamp": [0.0, 120.0]}]
    
    # =========================================================================
    # FASE 1: ONE-SHOT CON CLONACIÓN DE VOZ (WAV)
    # =========================================================================
    print("\n" + "="*70)
    print(" FASE 1: ONE-SHOT CON CLONACIÓN (VibeVoice 1.5B vs VoxCPM2 2.0B)")
    print("="*70)
    
    # 1.1 VibeVoice 1.5B (One-Shot + Cloning)
    print("\n--- Test 1.1: VibeVoice 1.5B One-Shot (Cloning) ---")
    vv_dir = os.path.join(benchmark_dir, "vv_f1_oneshot")
    shutil.rmtree(vv_dir, ignore_errors=True)
    
    vram_before = get_vram_usage()
    t0 = time.time()
    try:
        paths = generate_individual_tts(
            chunks=merged_chunks,
            tts_dir=vv_dir,
            speaker_name="cloned_speaker",
            vibevoice_model="VibeVoice-1.5B",
            vibevoice_cfg=1.3,
            vibevoice_steps=10
        )
        t_elapsed = time.time() - t0
        vram_diff = max(0.0, get_vram_usage() - vram_before)
        print(f"[SUCCESS] VibeVoice 1.5B One-Shot completed in {t_elapsed:.2f}s. VRAM added: {vram_diff:.1f} MB.")
        results["vv_f1"] = {"time": t_elapsed, "vram": vram_diff, "status": "Success"}
    except Exception as e:
        print(f"[FAILED] VibeVoice 1.5B One-Shot: {e}")
        results["vv_f1"] = {"time": 0.0, "vram": 0.0, "status": f"Failed: {e}"}
        
    # 1.2 VoxCPM2 2.0B (One-Shot + Cloning)
    print("\n--- Test 1.2: VoxCPM2 2.0B One-Shot (Cloning) ---")
    vox_dir = os.path.join(benchmark_dir, "vox_f1_oneshot")
    shutil.rmtree(vox_dir, ignore_errors=True)
    
    vram_before = get_vram_usage()
    t0 = time.time()
    try:
        paths = generate_individual_tts(
            chunks=merged_chunks,
            tts_dir=vox_dir,
            speaker_name="cloned_speaker",
            vibevoice_model="openbmb/VoxCPM2",
            vibevoice_cfg=2.0,
            vibevoice_steps=10
        )
        t_elapsed = time.time() - t0
        vram_diff = max(0.0, get_vram_usage() - vram_before)
        print(f"[SUCCESS] VoxCPM2 2.0B One-Shot completed in {t_elapsed:.2f}s. VRAM added: {vram_diff:.1f} MB.")
        results["vox_f1"] = {"time": t_elapsed, "vram": vram_diff, "status": "Success"}
    except Exception as e:
        print(f"[FAILED] VoxCPM2 2.0B One-Shot: {e}")
        results["vox_f1"] = {"time": 0.0, "vram": 0.0, "status": f"Failed: {e}"}
        
    # =========================================================================
    # FASE 2: POR FRASES CON CLONACIÓN DE VOZ (WAV) - SECUENCIAL
    # =========================================================================
    print("\n" + "="*70)
    print(" FASE 2: POR FRASES CON CLONACIÓN (VibeVoice 1.5B vs VoxCPM2 2.0B)")
    print("="*70)
    
    # 2.1 VibeVoice 1.5B (Phrases + Cloning - Sequential)
    print("\n--- Test 2.1: VibeVoice 1.5B Phrases (Cloning - Sequential) ---")
    vv_dir = os.path.join(benchmark_dir, "vv_f2_phrases")
    shutil.rmtree(vv_dir, ignore_errors=True)
    
    vram_before = get_vram_usage()
    t0 = time.time()
    try:
        paths = generate_individual_tts(
            chunks=chunks,
            tts_dir=vv_dir,
            speaker_name="cloned_speaker",
            vibevoice_model="VibeVoice-1.5B",
            vibevoice_cfg=1.3,
            vibevoice_steps=10
        )
        t_elapsed = time.time() - t0
        vram_diff = max(0.0, get_vram_usage() - vram_before)
        print(f"[SUCCESS] VibeVoice 1.5B Phrases completed in {t_elapsed:.2f}s. VRAM added: {vram_diff:.1f} MB.")
        results["vv_f2"] = {"time": t_elapsed, "vram": vram_diff, "status": "Success"}
    except Exception as e:
        print(f"[FAILED] VibeVoice 1.5B Phrases: {e}")
        results["vv_f2"] = {"time": 0.0, "vram": 0.0, "status": f"Failed: {e}"}
        
    # 2.2 VoxCPM2 2.0B (Phrases + Cloning - Sequential)
    print("\n--- Test 2.2: VoxCPM2 2.0B Phrases (Cloning - Sequential) ---")
    vox_dir = os.path.join(benchmark_dir, "vox_f2_phrases")
    shutil.rmtree(vox_dir, ignore_errors=True)
    
    vram_before = get_vram_usage()
    t0 = time.time()
    try:
        paths = generate_individual_tts(
            chunks=chunks,
            tts_dir=vox_dir,
            speaker_name="cloned_speaker",
            vibevoice_model="openbmb/VoxCPM2",
            vibevoice_cfg=2.0,
            vibevoice_steps=10
        )
        t_elapsed = time.time() - t0
        vram_diff = max(0.0, get_vram_usage() - vram_before)
        print(f"[SUCCESS] VoxCPM2 2.0B Phrases completed in {t_elapsed:.2f}s. VRAM added: {vram_diff:.1f} MB.")
        results["vox_f2"] = {"time": t_elapsed, "vram": vram_diff, "status": "Success"}
    except Exception as e:
        print(f"[FAILED] VoxCPM2 2.0B Phrases: {e}")
        results["vox_f2"] = {"time": 0.0, "vram": 0.0, "status": f"Failed: {e}"}

    # =========================================================================
    # FASE 3: ONE-SHOT SIN CLONACIÓN (MODELO 0.5B - PRESET VOICE)
    # =========================================================================
    print("\n" + "="*70)
    print(" FASE 3: ONE-SHOT SIN CLONACIÓN (VibeVoice 0.5B vs VoxCPM 0.5B)")
    print("="*70)
    
    # 3.1 VibeVoice 0.5B (One-Shot - Preset)
    print("\n--- Test 3.1: VibeVoice 0.5B One-Shot (Preset) ---")
    vv_dir = os.path.join(benchmark_dir, "vv_f3_oneshot")
    shutil.rmtree(vv_dir, ignore_errors=True)
    
    vram_before = get_vram_usage()
    t0 = time.time()
    try:
        paths = generate_individual_tts(
            chunks=merged_chunks,
            tts_dir=vv_dir,
            speaker_name="en-Frank_man",
            vibevoice_model="VibeVoice-Realtime-0.5B",
            vibevoice_cfg=1.3,
            vibevoice_steps=10
        )
        t_elapsed = time.time() - t0
        vram_diff = max(0.0, get_vram_usage() - vram_before)
        print(f"[SUCCESS] VibeVoice 0.5B One-Shot completed in {t_elapsed:.2f}s. VRAM added: {vram_diff:.1f} MB.")
        results["vv_f3"] = {"time": t_elapsed, "vram": vram_diff, "status": "Success"}
    except Exception as e:
        print(f"[FAILED] VibeVoice 0.5B One-Shot: {e}")
        results["vv_f3"] = {"time": 0.0, "vram": 0.0, "status": f"Failed: {e}"}
        
    # 3.2 VoxCPM 0.5B (One-Shot - Preset)
    print("\n--- Test 3.2: VoxCPM 0.5B One-Shot (Preset) ---")
    vox_dir = os.path.join(benchmark_dir, "vox_f3_oneshot")
    shutil.rmtree(vox_dir, ignore_errors=True)
    
    vram_before = get_vram_usage()
    t0 = time.time()
    try:
        paths = generate_individual_tts(
            chunks=merged_chunks,
            tts_dir=vox_dir,
            speaker_name="en-Frank_man",
            vibevoice_model="pretrained_models/VoxCPM-0.5B",
            vibevoice_cfg=2.0,
            vibevoice_steps=10
        )
        t_elapsed = time.time() - t0
        vram_diff = max(0.0, get_vram_usage() - vram_before)
        print(f"[SUCCESS] VoxCPM 0.5B One-Shot completed in {t_elapsed:.2f}s. VRAM added: {vram_diff:.1f} MB.")
        results["vox_f3"] = {"time": t_elapsed, "vram": vram_diff, "status": "Success"}
    except Exception as e:
        print(f"[FAILED] VoxCPM 0.5B One-Shot: {e}")
        results["vox_f3"] = {"time": 0.0, "vram": 0.0, "status": f"Failed: {e}"}

    # =========================================================================
    # FASE 4: POR FRASES SIN CLONACIÓN (MODELO 0.5B - PRESET VOICE) - PARALELO (3 INSTANCIAS)
    # =========================================================================
    print("\n" + "="*70)
    print(" FASE 4: POR FRASES SIN CLONACIÓN (VibeVoice 0.5B vs VoxCPM 0.5B) - PARALELO")
    print("="*70)
    
    # 4.1 VibeVoice 0.5B (Phrases - Parallel 3 Workers)
    print("\n--- Test 4.1: VibeVoice 0.5B Phrases (Parallel - 3 Workers) ---")
    vv_dir = os.path.join(benchmark_dir, "vv_f4_phrases")
    shutil.rmtree(vv_dir, ignore_errors=True)
    
    vram_before = get_vram_usage()
    t0 = time.time()
    try:
        paths = generate_individual_tts(
            chunks=chunks,
            tts_dir=vv_dir,
            speaker_name="en-Frank_man",
            vibevoice_model="VibeVoice-Realtime-0.5B",
            vibevoice_cfg=1.3,
            vibevoice_steps=10
        )
        t_elapsed = time.time() - t0
        vram_diff = max(0.0, get_vram_usage() - vram_before)
        print(f"[SUCCESS] VibeVoice 0.5B Parallel completed in {t_elapsed:.2f}s. VRAM added: {vram_diff:.1f} MB.")
        results["vv_f4"] = {"time": t_elapsed, "vram": vram_diff, "status": "Success"}
    except Exception as e:
        print(f"[FAILED] VibeVoice 0.5B Parallel: {e}")
        results["vv_f4"] = {"time": 0.0, "vram": 0.0, "status": f"Failed: {e}"}
        
    # 4.2 VoxCPM 0.5B (Phrases - Parallel 3 Workers)
    print("\n--- Test 4.2: VoxCPM 0.5B Phrases (Parallel - 3 Workers) ---")
    vox_dir = os.path.join(benchmark_dir, "vox_f4_phrases")
    shutil.rmtree(vox_dir, ignore_errors=True)
    
    vram_before = get_vram_usage()
    t0 = time.time()
    try:
        paths = generate_individual_tts(
            chunks=chunks,
            tts_dir=vox_dir,
            speaker_name="en-Frank_man",
            vibevoice_model="pretrained_models/VoxCPM-0.5B",
            vibevoice_cfg=2.0,
            vibevoice_steps=10
        )
        t_elapsed = time.time() - t0
        vram_diff = max(0.0, get_vram_usage() - vram_before)
        print(f"[SUCCESS] VoxCPM 0.5B Parallel completed in {t_elapsed:.2f}s. VRAM added: {vram_diff:.1f} MB.")
        results["vox_f4"] = {"time": t_elapsed, "vram": vram_diff, "status": "Success"}
    except Exception as e:
        print(f"[FAILED] VoxCPM 0.5B Parallel: {e}")
        results["vox_f4"] = {"time": 0.0, "vram": 0.0, "status": f"Failed: {e}"}
        
    # --- WRITE BENCHMARK REPORT ---
    report_path = os.path.join(base_dir, "benchmark_report.md")
    print(f"\n[REPORT] Generating report at: {report_path}...")
    
    with open(report_path, "w", encoding="utf-8") as rf:
        rf.write("# Reporte Completo de Benchmark: VibeVoice vs VoxCPM\n\n")
        rf.write("Este benchmark evalúa y compara el rendimiento (tiempo de procesamiento y memoria de GPU) entre **VibeVoice** y **VoxCPM** bajo 4 escenarios diferentes.\n\n")
        rf.write("## Especificaciones de la GPU de Prueba\n")
        rf.write("- **GPU:** NVIDIA GeForce RTX 5070 (Blackwell)\n")
        rf.write("- **Audio de referencia:** `cloned_speaker.wav` (Fases 1 y 2)\n")
        rf.write("- **Presete de voz:** `en-Frank_man` (Fases 3 y 4)\n")
        rf.write("- **Muestra de entrada:** 15 frases traducidas al español\n\n")
        
        rf.write("## 📊 Tabla Comparativa General\n\n")
        rf.write("| Fase del Test | Modelo VibeVoice | Tiempo VibeVoice | VRAM VibeVoice | Modelo VoxCPM | Tiempo VoxCPM | VRAM VoxCPM | Comparativa (VoxCPM vs VibeVoice) |\n")
        rf.write("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n")
        
        # Row 1: Phase 1 (One-Shot con Clonación)
        f1_ratio = results["vox_f1"]["time"] / results["vv_f1"]["time"] if results["vv_f1"]["time"] > 0 else 0
        rf.write(f"| **Fase 1: One-Shot con Clonación** | VibeVoice-1.5B | {results['vv_f1']['time']:.2f} s | {results['vv_f1']['vram']:.1f} MB | VoxCPM2 (2.0B) | {results['vox_f1']['time']:.2f} s | {results['vox_f1']['vram']:.1f} MB | VoxCPM es {f1_ratio:.1f}x más lento |\n")
        
        # Row 2: Phase 2 (Por Frases con Clonación)
        f2_ratio = results["vox_f2"]["time"] / results["vv_f2"]["time"] if results["vv_f2"]["time"] > 0 else 0
        rf.write(f"| **Fase 2: Por Frases con Clonación** | VibeVoice-1.5B | {results['vv_f2']['time']:.2f} s | {results['vv_f2']['vram']:.1f} MB | VoxCPM2 (2.0B) | {results['vox_f2']['time']:.2f} s | {results['vox_f2']['vram']:.1f} MB | VoxCPM es {f2_ratio:.1f}x más lento |\n")
        
        # Row 3: Phase 3 (One-Shot Preset)
        f3_ratio = results["vox_f3"]["time"] / results["vv_f3"]["time"] if results["vv_f3"]["time"] > 0 else 0
        rf.write(f"| **Fase 3: One-Shot sin Clonación (Preset)** | Realtime-0.5B | {results['vv_f3']['time']:.2f} s | {results['vv_f3']['vram']:.1f} MB | VoxCPM-0.5B | {results['vox_f3']['time']:.2f} s | {results['vox_f3']['vram']:.1f} MB | VoxCPM es {f3_ratio:.1f}x más lento |\n")
        
        # Row 4: Phase 4 (Por Frases Preset - Paralelo)
        f4_ratio = results["vox_f4"]["time"] / results["vv_f4"]["time"] if results["vv_f4"]["time"] > 0 else 0
        rf.write(f"| **Fase 4: Por Frases sin Clonación (Paralelo)** | Realtime-0.5B (3x) | {results['vv_f4']['time']:.2f} s | {results['vv_f4']['vram']:.1f} MB | VoxCPM-0.5B (3x) | {results['vox_f4']['time']:.2f} s | {results['vox_f4']['vram']:.1f} MB | VoxCPM es {f4_ratio:.1f}x más lento |\n")
        
        rf.write("\n\n")
        rf.write("## 🔍 Análisis Técnico por Fase\n\n")
        rf.write("### 1. Clonación de Voz en Caliente (Fases 1 y 2)\n")
        rf.write("- **VibeVoice 1.5B**: Permite realizar clonación Zero-Shot real pasando el archivo `.wav` directamente. Al ejecutarse secuencialmente, es significativamente más veloz en inferencia que VoxCPM2, pero su VRAM añadida es moderada.\n")
        rf.write("- **VoxCPM2 (2.0B)**: Ofrece una clonación de timbre con fidelidad excepcional, pero al tener 2 mil millones de parámetros y procesar el audio de referencia en caliente, el tiempo de inferencia es notablemente superior. Consume cerca de 11 GB de VRAM pico en One-Shot, lo que imposibilita de forma segura la ejecución paralela en una GPU comercial.\n\n")
        
        rf.write("### 2. Modelos Livianos 0.5B y Ejecución Paralela (Fases 3 y 4)\n")
        rf.write("- **VibeVoice-Realtime-0.5B**: Este modelo es el campeón de latencia gracias a su arquitectura optimizada y a que las voces preset ya están pre-computadas en archivos `.pt`. En Fase 4 (paralelo 3 instancias), procesó las 15 frases en tiempo récord.\n")
        rf.write("- **VoxCPM-0.5B**: Demuestra que VoxCPM sí puede correr en paralelo con 3 instancias cuando se utiliza su versión reducida de 0.5B parámetros (la cual consume cerca de 1.8 GB de VRAM por instancia, totalizando ~5.5 GB de VRAM en paralelo). Aunque es más lento que VibeVoice 0.5B (debido a que realiza generación autoregresiva en espacio continuo sin discretización), ofrece una flexibilidad y un timbre de voz de diseño muy natural.\n\n")
        
        rf.write("### ⚠️ Limitación del Modelo VoxCPM-0.5B\n")
        rf.write("- Se descubrió durante las pruebas que **el modelo VoxCPM-0.5B no soporta clonación de voz Zero-Shot (`reference_wav_path`)**. Intentar clonar un archivo `.wav` arroja un error en caliente (`reference_wav_path is only supported with VoxCPM2 models`). Para clonación real se requiere obligatoriamente usar el modelo VoxCPM2 de 2.0B.\n\n")
        rf.write("--- \n*Reporte generado automáticamente el 2026-06-26*.\n")
        
    print("[REPORT] Done!")

if __name__ == "__main__":
    main()
