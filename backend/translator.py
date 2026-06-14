import requests
import json
import re

def translate_chunks(chunks: list, model: str = "gemma4:e2b-it-qat") -> list:
    url = "http://127.0.0.1:11434/api/chat"
    system_msg = (
        "You are an expert English to Spanish translator. "
        "You will receive a JSON object with 'chunks' containing English text. "
        "Translate the 'text' of each chunk to natural, fluent Spanish. "
        "Keep the exact 'timestamp' values. "
        "Return the resulting JSON object with the translated 'chunks' and nothing else."
    )
    
    batch_size = 5
    translated_chunks = []
    
    print(f"\n--- Iniciando traducción en lotes de {batch_size} con {model} (Total chunks: {len(chunks)}) ---")
    
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i+batch_size]
        print(f"Translating batch {i//batch_size + 1}/{(len(chunks) - 1)//batch_size + 1}...")
        
        prompt_content = {"chunks": batch}
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": json.dumps(prompt_content, ensure_ascii=False)}
            ],
            "stream": False,
            "format": "json",
            "options": {
                "num_ctx": 32768,
                "num_predict": 4096
            }
        }
        
        # Retry logic
        success = False
        for attempt in range(3):
            try:
                # Use a reasonable timeout (e.g. 180s per batch)
                response = requests.post(url, json=payload, timeout=180)
                response.raise_for_status()
                result = response.json()
                content = result.get("message", {}).get("content", "").strip()
                
                # Clean thinking tags if present
                if "<think>" in content:
                    content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
                
                # Parse JSON
                json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                else:
                    start = content.find('{')
                    end = content.rfind('}')
                    if start != -1 and end != -1:
                        json_str = content[start:end+1]
                    else:
                        json_str = content

                translated_data = json.loads(json_str)
                batch_translated = translated_data.get("chunks", [])
                
                if len(batch_translated) == len(batch):
                    translated_chunks.extend(batch_translated)
                    success = True
                    break
                else:
                    print(f"Warning: Batch size mismatch on attempt {attempt + 1} (expected {len(batch)}, got {len(batch_translated)}). Retrying...")
            except Exception as e:
                print(f"Error in batch translation attempt {attempt + 1}: {e}")
                
        if not success:
            print(f"Failed to translate batch {i//batch_size + 1}. Keeping original English chunks.")
            translated_chunks.extend(batch)
            
    # Unload model from memory immediately to free VRAM for VibeVoice
    try:
        requests.post(
            "http://127.0.0.1:11434/api/generate",
            json={"model": model, "keep_alive": 0},
            timeout=5
        )
        print(f"Ollama model {model} unloaded from memory successfully.")
    except Exception as e:
        print(f"Failed to unload Ollama model: {e}")
            
    return translated_chunks


