import requests
import json
import re

class OllamaCloudModelError(Exception):
    """Exception raised when an Ollama cloud model is not found or has subscription issues."""
    pass

def call_ollama_api(url: str, payload: dict, timeout: float) -> dict:
    try:
        response = requests.post(url, json=payload, timeout=timeout)
        if response.status_code != 200:
            try:
                err_data = response.json()
                err_msg = err_data.get("error", response.text)
            except:
                err_msg = response.text
            raise OllamaCloudModelError(f"error modelo cloud: {err_msg}")
        return response.json()
    except requests.exceptions.RequestException as e:
        if hasattr(e, 'response') and e.response is not None:
            try:
                err_data = e.response.json()
                err_msg = err_data.get("error", e.response.text)
            except:
                err_msg = e.response.text
            raise OllamaCloudModelError(f"error modelo cloud: {err_msg}")
        raise e

def translate_chunks(chunks: list, model: str = "gemma4:e2b-it-qat") -> list:
    url = "http://127.0.0.1:11434/api/chat"
    system_msg = (
        "You are an expert English to Spanish translator. "
        "You will receive a JSON object with 'chunks' containing English text. "
        "Translate the 'text' of each chunk to natural, fluent Spanish. "
        "Keep the exact 'timestamp' values. "
        "Return the resulting JSON object with the translated 'chunks' and nothing else."
    )
    
    print(f"\n--- Iniciando traducción de {len(chunks)} chunks con {model} (Modo One-Shot Exclusivo) ---")
    
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
        # One-shot timeout set to 300 seconds (5 minutes)
        result = call_ollama_api(url, payload, timeout=300)
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
            raise ValueError(
                f"Error en traducción One-Shot: Discrepancia en cantidad de segmentos. "
                f"Se enviaron {len(chunks)} y se recibieron {len(translated_chunks)}."
            )
    except OllamaCloudModelError as ve:
        raise ve
    except Exception as e:
        print(f"Error crítico en traducción One-Shot: {e}")
        raise e

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



