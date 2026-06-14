import json
import os
from translator import translate_chunks

def split_massive_chunks(chunks, max_length=500):
    new_chunks = []
    for chunk in chunks:
        text = chunk["text"]
        if len(text) <= max_length:
            new_chunks.append(chunk)
            continue
            
        # The chunk is massive, split it by periods or just artificially
        sentences = [s.strip() + "." for s in text.split(".") if s.strip()]
        
        start_time = chunk["timestamp"][0]
        end_time = chunk["timestamp"][1]
        total_duration = end_time - start_time
        total_chars = sum(len(s) for s in sentences)
        
        current_time = start_time
        current_sub_text = ""
        current_sub_chars = 0
        
        for sentence in sentences:
            if len(current_sub_text) + len(sentence) > max_length and current_sub_text:
                # Calculate proportional duration for this sub_text
                ratio = len(current_sub_text) / max(total_chars, 1)
                duration = total_duration * ratio
                sub_end = current_time + duration
                
                new_chunks.append({
                    "timestamp": [round(current_time, 2), round(sub_end, 2)],
                    "text": current_sub_text.strip()
                })
                
                current_time = sub_end
                current_sub_text = sentence + " "
            else:
                current_sub_text += sentence + " "
                
        # Add the last remaining piece
        if current_sub_text.strip():
            new_chunks.append({
                "timestamp": [round(current_time, 2), round(end_time, 2)],
                "text": current_sub_text.strip()
            })
            
    return new_chunks

def run():
    task_dir = r"G:\IA\PROYECTOS\Traductor\cache\376e7a92-d91f-44b5-84ae-42363d6421dc"
    english_json = os.path.join(task_dir, "english_whisper.json")
    spanish_json = os.path.join(task_dir, "spanish_translated.json")
    script_txt = os.path.join(task_dir, "script.txt")

    print("Cargando english_whisper.json...")
    with open(english_json, "r", encoding="utf-8") as f:
        orig_data = json.load(f)

    chunks = orig_data.get("chunks", [])
    print(f"Original chunks: {len(chunks)}")
    
    # Split massive chunks
    optimized_chunks = split_massive_chunks(chunks)
    print(f"Chunks optimizados (despues de picar los gigantes): {len(optimized_chunks)}")

    print("Enviando fragmentos optimizados a traducir con qwen3.5:2b...")
    translated_chunks = translate_chunks(optimized_chunks)

    translated_data = {"text": "", "chunks": translated_chunks}

    print("Guardando spanish_translated.json...")
    with open(spanish_json, "w", encoding="utf-8") as f:
        json.dump(translated_data, f, ensure_ascii=False, indent=2)

    print("Generando script.txt con el formato de VibeVoice...")
    with open(script_txt, "w", encoding="utf-8") as f:
        for chunk in translated_chunks:
            text = chunk.get("text", "").strip()
            if text:
                f.write(f"Speaker 1: {text}\n")

    print("¡Exito! La traduccion se ha completado perfectamente.")

if __name__ == "__main__":
    run()
