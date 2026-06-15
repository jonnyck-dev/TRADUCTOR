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
    
    print(f"\n--- Iniciando traducción de {len(chunks)} chunks con {model} (Modo One-Shot) ---")
    
    # Attempt 1: One-Shot translation of all chunks
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": json.dumps({"chunks": chunks}, ensure_ascii=False)}
        ],
        "stream": False,
        "format": "json",
        "options": {
            "num_ctx": 128000,
            "num_predict": 32768
        }
    }
    
    try:
        print("Enviando todos los chunks en un solo query (One-Shot)...")
        # One-shot timeout set to 240 seconds
        response = requests.post(url, json=payload, timeout=240)
        response.raise_for_status()
        result = response.json()
        content = result.get("message", {}).get("content", "").strip()
        
        if "<think>" in content:
            content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
            
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
        translated_chunks = translated_data.get("chunks", [])
        
        if len(translated_chunks) == len(chunks):
            print(f"¡Éxito en traducción One-Shot! Traducidos {len(chunks)} chunks.")
            unload_model(model)
            return translated_chunks
        else:
            print(f"Advertencia: Tamaño de respuesta incorrecto en One-Shot (esperados {len(chunks)}, recibidos {len(translated_chunks)}).")
    except Exception as e:
        print(f"Error en traducción One-Shot: {e}")
        
    # Fallback: Batch translation (groups of 5)
    print("\nFallback: Iniciando traducción en lotes de 5...")
    batch_size = 5
    translated_chunks = []
    
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i+batch_size]
        print(f"Translating batch {i//batch_size + 1}/{(len(chunks) - 1)//batch_size + 1}...")
        
        prompt_content = {"chunks": batch}
        payload_batch = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": json.dumps(prompt_content, ensure_ascii=False)}
            ],
            "stream": False,
            "format": "json",
            "options": {
                "num_ctx": 128000,
                "num_predict": 4096
            }
        }
        
        success = False
        for attempt in range(3):
            try:
                response = requests.post(url, json=payload_batch, timeout=120)
                response.raise_for_status()
                result = response.json()
                content = result.get("message", {}).get("content", "").strip()
                
                if "<think>" in content:
                    content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
                
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
            print(f"Batch {i//batch_size + 1} translation failed. Falling back to individual chunk translation...")
            for chunk in batch:
                single_success = False
                payload_single = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_msg},
                        {"role": "user", "content": json.dumps({"chunks": [chunk]}, ensure_ascii=False)}
                    ],
                    "stream": False,
                    "format": "json",
                    "options": {
                        "num_ctx": 128000,
                        "num_predict": 4096
                    }
                }
                for attempt_single in range(2):
                    try:
                        response = requests.post(url, json=payload_single, timeout=60)
                        response.raise_for_status()
                        result = response.json()
                        content = result.get("message", {}).get("content", "").strip()
                        
                        if "<think>" in content:
                            content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
                            
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
                        if len(batch_translated) == 1:
                            translated_chunks.append(batch_translated[0])
                            single_success = True
                            break
                    except Exception as e:
                        print(f"Error in single chunk translation: {e}")
                if not single_success:
                    print(f"Fallback to keeping original chunk text: {chunk.get('text')}")
                    translated_chunks.append(chunk)
                    
    unload_model(model)
    return translated_chunks

def unload_model(model: str):
    try:
        requests.post(
            "http://127.0.0.1:11434/api/generate",
            json={"model": model, "keep_alive": 0},
            timeout=5
        )
        print(f"Ollama model {model} unloaded from memory successfully.")
    except Exception as e:
        print(f"Failed to unload Ollama model: {e}")


