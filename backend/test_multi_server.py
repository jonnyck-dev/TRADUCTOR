import sys
import os
import time

sys.path.append("/mnt/g/IA/PROYECTOS/Traductor/backend")
from tts_client import generate_individual_tts, stop_vibevoice_servers

chunks = [
    {"text": "Hola, esto es una prueba del doblaje en paralelo."},
    {"text": "Estamos generando audio con el modelo de VibeVoice."},
    {"text": "Esta es la tercera frase de prueba."},
    {"text": "Y esta es la cuarta frase de prueba."}
]

tts_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "cache", "test_parallel_tts"))
os.makedirs(tts_dir, exist_ok=True)

# Delete existing test files if any
for i in range(len(chunks)):
    p = os.path.join(tts_dir, f"phrase_{i}.mp3")
    if os.path.exists(p):
        os.remove(p)

print("Starting parallel TTS generation test...")
t0 = time.time()
try:
    paths = generate_individual_tts(
        chunks=chunks,
        tts_dir=tts_dir,
        speaker_name="en-Frank_man", # Default wav voice
        vibevoice_model="VibeVoice-Realtime-0.5B",
        vibevoice_cfg=1.3,
        vibevoice_steps=10
    )
    print(f"Generation completed! Paths: {paths}")
    print(f"Time taken: {time.time() - t0:.2f} seconds")
    
    # Check if files exist and are not empty
    for i, p in enumerate(paths):
        if p and os.path.exists(p) and os.path.getsize(p) > 0:
            print(f"File {i} OK: {p} ({os.path.getsize(p)} bytes)")
        else:
            print(f"File {i} FAILED: {p}")
except Exception as e:
    print(f"Test failed with error: {e}")
    import traceback
    traceback.print_exc()
finally:
    # Double check all ports are cleaned up
    stop_vibevoice_servers(processes=None, num_workers=4)
