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
        "Return the resulting JSON object with the translated 'chunks'."
    )
    
    prompt_content = {"chunks": chunks}
    
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": json.dumps(prompt_content, ensure_ascii=False)}
        ],
        "stream": False,
        "format": "json",
        "options": {
            "num_ctx": 131072,
            "num_predict": -1
        }
    }

    print(f"\n--- Iniciando traduccion en una sola pasada (128K Context) con {model} ---")
    
    try:
        response = requests.post(url, json=payload, timeout=1200)
        response.raise_for_status()
        result = response.json()
        content = result.get("message", {}).get("content", "").strip()
        
        # Eliminar cualquier tag de "thinking" si el modelo los imprime
        if "<think>" in content:
            content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
            
        # Extraer JSON
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

        try:
            translated_data = json.loads(json_str)
            return translated_data.get("chunks", chunks)
        except Exception as e:
            with open("debug_gemma_output.txt", "w", encoding="utf-8") as f:
                f.write(json_str)
            print(f"Failed to translate: {e}")
            return chunks
        
    except Exception as e:
        print(f"API Error: {e}")
        return chunks
