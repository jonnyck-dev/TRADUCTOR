import json
import os
from translator import translate_chunks
from tts_client import generate_tts

task_dir = r"G:\IA\PROYECTOS\Traductor\cache\376e7a92-d91f-44b5-84ae-42363d6421dc"
english_json = os.path.join(task_dir, "english_whisper.json")
spanish_json = os.path.join(task_dir, "spanish_translated.json")
script_txt = os.path.join(task_dir, "script.txt")

print("Cargando english_whisper.json...")
with open(english_json, "r", encoding="utf-8") as f:
    orig_data = json.load(f)

chunks = orig_data.get("chunks", [])

print(f"Traduciendo {len(chunks)} fragmentos en una sola pasada usando gemma4:e2b-it-qat...")
# translate_chunks ya usa qwen3.5:2b por defecto gracias a nuestra edicion previa
translated_chunks = translate_chunks(chunks)

translated_data = {"text": "", "chunks": translated_chunks}

print("Guardando spanish_translated.json...")
with open(spanish_json, "w", encoding="utf-8") as f:
    json.dump(translated_data, f, ensure_ascii=False, indent=2)

print("Generando script.txt con el formato de VibeVoice...")
with open(script_txt, "w", encoding="utf-8") as f:
    for chunk in translated_chunks:
        text = chunk["text"].strip()
        if text:
            f.write(f"Speaker 1: {text}\n")

print("¡Traduccion y script.txt generados con exito!")
