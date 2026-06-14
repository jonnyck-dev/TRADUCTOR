import os
import json
import requests
import sys

def test_streaming_translation():
    json_path = r"G:\IA\PROYECTOS\Traductor\cache\376e7a92-d91f-44b5-84ae-42363d6421dc\english_whisper.json"
    
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    chunks = data.get("chunks", [])
    # Aislar especificamente el fragmento 3 que es el gigante (indice 2)
    massive_chunk = [chunks[2]]
    
    prompt_system = (
        "You are an expert translator. You will receive a JSON object containing a list of chunks, "
        "where each chunk has a 'timestamp' (list of start and end float times) and 'text' (English text). "
        "Translate the 'text' of each chunk into natural, fluent Spanish. "
        "Keep the exact same number of chunks and the exact same 'timestamp' values. "
        "Return ONLY a JSON object matching the input structure: a JSON object with a single 'chunks' key "
        "containing the array of translated chunks. Do not write markdown, do not write ```json."
    )
    
    prompt_content = {"chunks": massive_chunk}
    
    payload = {
        "model": "qwen3.5:2b", 
        "messages": [
            {"role": "system", "content": prompt_system},
            {"role": "user", "content": json.dumps(prompt_content, ensure_ascii=False)}
        ],
        "stream": True,
        "format": "json"
    }
    
    print("Enviando el fragmento gigante a Ollama (qwen3.5:2b) con streaming activado...")
    print("="*60)
    
    try:
        response = requests.post("http://127.0.0.1:11434/api/chat", json=payload, stream=True)
        response.raise_for_status()
        
        for line in response.iter_lines():
            if line:
                chunk_data = json.loads(line.decode('utf-8'))
                content_piece = chunk_data.get("message", {}).get("content", "")
                # Flush the output so it updates in real time in the log file
                sys.stdout.write(content_piece)
                sys.stdout.flush()
                
    except Exception as e:
        print(f"\n❌ Error durante el streaming: {e}")

if __name__ == "__main__":
    test_streaming_translation()
