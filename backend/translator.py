import requests
import json
import re
import os

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

def fix_json_quotes(json_str: str) -> str:
    """
    Finds "text": "value" pairs in the JSON string, programmatically escapes 
    any internal unescaped double quotes, and repairs missing commas between fields or objects.
    """
    # 1. Fix missing commas between chunk objects: } { -> },{
    json_str = re.sub(r'\}\s*\{', '},\n{', json_str)
    
    # 2. Fix missing commas between array elements if bracket closed: ] { -> ],{
    json_str = re.sub(r'\]\s*\{', '],\n{', json_str)
    
    def replace_quote(match):
        prefix = match.group(1)
        content = match.group(2)
        suffix = match.group(3)
        
        # Escape double quotes inside content, preserving already escaped quotes
        temp = content.replace('\\"', '___ESCAPED_QUOTE___')
        temp = temp.replace('"', '\\"')
        escaped_content = temp.replace('___ESCAPED_QUOTE___', '\\"')
        
        # Reconstruct suffix to ensure there is a comma before "timestamp"
        # If suffix doesn't contain a comma but has "timestamp", insert it!
        if "timestamp" in suffix and "," not in suffix:
            suffix = '", "timestamp"'
            
        return prefix + escaped_content + suffix
        
    # Matches "text": "content" followed optionally by a comma, then "timestamp", or followed by object close
    # Using negative lookbehind (?<!\\) to ensure ending quote is not an escaped quote
    pattern = r'("text"\s*:\s*")(.*?)((?<!\\)"\s*,?\s*(?<!\\)"timestamp"|\s*\})'
    return re.sub(pattern, replace_quote, json_str, flags=re.DOTALL)

def translate_chunks(chunks: list, model: str = "gemma4:e2b-it-qat", save_dir: str = None) -> list:
    url = "http://127.0.0.1:11434/api/chat"
    system_msg = (
        "You are an expert English to Spanish translator. "
        "You will receive a JSON object with 'chunks' containing English text. "
        "Translate the 'text' of each chunk to natural, fluent Spanish. "
        "Keep the exact 'timestamp' and 'index' values. Do not omit, combine, or split chunks. "
        "Return the resulting JSON object with the translated 'chunks' and nothing else."
    )
    
    print(f"\n--- Iniciando traducción de {len(chunks)} chunks con {model} (Modo One-Shot Exclusivo + Optimizados) ---")
    
    # Compress chunks: extract text, timestamp, and index
    minimal_chunks = []
    for idx, c in enumerate(chunks):
        minimal_chunks.append({
            "index": idx,
            "text": c.get("text", ""),
            "timestamp": c.get("timestamp", [0.0, 0.0])
        })
        
    if save_dir:
        try:
            os.makedirs(save_dir, exist_ok=True)
            min_input_path = os.path.join(save_dir, "english_minimal.json")
            with open(min_input_path, "w", encoding="utf-8") as f:
                json.dump({"chunks": minimal_chunks}, f, ensure_ascii=False, indent=2)
            print(f"Saved simplified English input to disk: {min_input_path}")
        except Exception as se:
            print(f"Warning: Failed to save english_minimal.json: {se}")
        
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": json.dumps({"chunks": minimal_chunks}, ensure_ascii=False)}
        ],
        "stream": False,
        "format": "json",
        "options": {
            "num_ctx": 128000,
            "num_predict": 32768,
            "temperature": 0.0
        }
    }
    
    try:
        print("Enviando chunks minimalistas en un solo query (One-Shot)...")
        # One-shot timeout set to 900 seconds (15 minutes)
        result = call_ollama_api(url, payload, timeout=900)
        content = result.get("message", {}).get("content", "").strip()
        
        # Clean think tags
        if "<think>" in content:
            content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
            
        # Clean markdown code block wraps if present
        clean_content = content
        if clean_content.startswith("```"):
            clean_content = re.sub(r'^```(?:json)?\s*', '', clean_content)
        if clean_content.endswith("```"):
            clean_content = re.sub(r'\s*```$', '', clean_content)
            
        start = clean_content.find('{')
        end = clean_content.rfind('}')
        if start != -1 and end != -1:
            json_str = clean_content[start:end+1]
        else:
            json_str = clean_content

        # Escape internal double quotes in text fields
        json_str = fix_json_quotes(json_str)

        translated_minimal_chunks = []
        max_attempts = 5
        current_attempt = 1
        last_error = None
        
        while current_attempt <= max_attempts:
            try:
                translated_data = json.loads(json_str, strict=False)
                translated_minimal_chunks = translated_data.get("chunks", [])
                break
            except json.JSONDecodeError as jde:
                last_error = jde
                print(f"Advertencia: Intento {current_attempt}/{max_attempts} falló con JSONDecodeError: {jde}. Solicitando auto-corrección al LLM...")
                
                if current_attempt == max_attempts:
                    break
                    
                correction_prompt = (
                    f"The following JSON text contains a syntax error: {jde}.\n"
                    f"Please fix ONLY the syntax errors (such as missing commas, unescaped quotes, or unmatched brackets) "
                    f"and return the valid corrected JSON object containing the 'chunks' key.\n"
                    f"Do not change the translations. Return ONLY the raw corrected JSON and nothing else.\n\n"
                    f"MALFORMED JSON:\n{json_str}"
                )
                payload_correction = {
                    "model": model,
                    "messages": [
                        {"role": "user", "content": correction_prompt}
                    ],
                    "stream": False,
                    "format": "json",
                    "options": {
                        "num_ctx": 128000,
                        "num_predict": 32768,
                        "temperature": 0.0
                    }
                }
                try:
                    corr_result = call_ollama_api(url, payload_correction, timeout=180)
                    corr_content = corr_result.get("message", {}).get("content", "").strip()
                    
                    # Clean think tags and markdown
                    if "<think>" in corr_content:
                        corr_content = re.sub(r'<think>.*?</think>', '', corr_content, flags=re.DOTALL).strip()
                    
                    clean_corr = corr_content
                    if clean_corr.startswith("```"):
                        clean_corr = re.sub(r'^```(?:json)?\s*', '', clean_corr)
                    if clean_corr.endswith("```"):
                        clean_corr = re.sub(r'\s*```$', '', clean_corr)
                    
                    start_corr = clean_corr.find('{')
                    end_corr = clean_corr.rfind('}')
                    if start_corr != -1 and end_corr != -1:
                        json_str = clean_corr[start_corr:end_corr+1]
                    else:
                        json_str = clean_corr
                        
                    # Also fix unescaped double quotes on LLM-corrected JSON string
                    json_str = fix_json_quotes(json_str)
                except Exception as e_corr:
                    print(f"Error al enviar consulta de corrección en intento {current_attempt}: {e_corr}")
                    raise jde
                    
                current_attempt += 1
                
        if not translated_minimal_chunks and last_error:
            print(f"Fallo crítico: No se pudo auto-corregir el JSON de traducción tras {max_attempts} intentos.")
            raise last_error
            
        if save_dir and translated_minimal_chunks:
            try:
                min_output_path = os.path.join(save_dir, "spanish_minimal.json")
                with open(min_output_path, "w", encoding="utf-8") as f:
                    json.dump({"chunks": translated_minimal_chunks}, f, ensure_ascii=False, indent=2)
                print(f"Saved raw translated Spanish output to disk: {min_output_path}")
            except Exception as se:
                print(f"Warning: Failed to save spanish_minimal.json: {se}")
        
        # Map translated chunks by index with positioning fallback
        translated_by_index = {}
        for i, c in enumerate(translated_minimal_chunks):
            idx = c.get("index")
            if idx is None:
                idx = i
            try:
                idx = int(idx)
            except:
                idx = i
            translated_by_index[idx] = c
            
        # Find any missing indices
        missing_indices = [idx for idx in range(len(chunks)) if idx not in translated_by_index]
        
        if missing_indices:
            print(f"Discrepancia detectada: Faltan {len(missing_indices)} segmentos por traducir. Iniciando auto-recuperación individual...")
            for idx in missing_indices:
                orig_chunk = chunks[idx]
                orig_text = orig_chunk.get("text", "").strip()
                if not orig_text:
                    translated_by_index[idx] = {
                        "index": idx,
                        "text": "",
                        "timestamp": orig_chunk.get("timestamp", [0.0, 0.0])
                    }
                    continue
                    
                # Direct single-phrase translation prompt
                chunk_prompt = f"Translate the following English sentence to natural, fluent Spanish. Return ONLY the translated Spanish text and nothing else:\n\n{orig_text}"
                single_payload = {
                    "model": model,
                    "messages": [
                        {"role": "user", "content": chunk_prompt}
                    ],
                    "stream": False,
                    "options": {
                        "temperature": 0.0
                    }
                }
                try:
                    single_res = call_ollama_api(url, single_payload, timeout=60)
                    translated_text = single_res.get("message", {}).get("content", "").strip()
                    if "<think>" in translated_text:
                        translated_text = re.sub(r'<think>.*?</think>', '', translated_text, flags=re.DOTALL).strip()
                    if translated_text.startswith('"') and translated_text.endswith('"'):
                        translated_text = translated_text[1:-1].strip()
                        
                    translated_by_index[idx] = {
                        "index": idx,
                        "text": translated_text,
                        "timestamp": orig_chunk.get("timestamp", [0.0, 0.0])
                    }
                    print(f"-> Recuperado índice {idx}: '{orig_text}' -> '{translated_text}'")
                except Exception as se_err:
                    print(f"Error recuperando índice {idx}: {se_err}. Usando texto original en inglés.")
                    translated_by_index[idx] = {
                        "index": idx,
                        "text": orig_text,
                        "timestamp": orig_chunk.get("timestamp", [0.0, 0.0])
                    }
                    
        # Reconstruct the complete ordered translated chunks list
        reconstructed_chunks = []
        for idx in range(len(chunks)):
            reconstructed_chunks.append(translated_by_index[idx])
            
        # Merge the translated Spanish texts back into the original full chunk structures
        merged_chunks = []
        for orig, trans in zip(chunks, reconstructed_chunks):
            new_chunk = dict(orig)
            new_chunk["orig_text"] = orig.get("text")
            new_chunk["text"] = trans.get("text", orig.get("text"))
            merged_chunks.append(new_chunk)
            
        print(f"¡Éxito en traducción One-Shot! Traducidos y alineados {len(chunks)} chunks.")
        unload_model(model)
        return merged_chunks
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



def enhance_translation_for_tts(chunks: list, model: str) -> list:
    """
    Second AI Pass: Cleans hallucinations, removes repetition loops, 
    and adds strong grammatical punctuation for TTS emotion.
    Enforces strict array length and index matching to prevent sync collapse.
    """
    import json
    import re
    print("\n[Sanador IA] Iniciando segunda pasada de limpieza y emoción para el TTS...")
    
    minimal_chunks = [{"index": i, "text": c.get("text", "")} for i, c in enumerate(chunks)]
    json_input = json.dumps({"chunks": minimal_chunks}, ensure_ascii=False)
    
    prompt = (
        "You are a highly aggressive script cleaner for an AI Voice Actor. "
        "Your PRIMARY directive is to completely eradicate AI stuttering, hallucinated words, and translation loops.\n\n"
        "CRITICAL RULES:\n"
        "1. ANNIHILATE REPETITIONS: If you see words or phrases repeating unnaturally ('ir a ir a', 'que que que', 'el el', 'bueno bueno bueno'), cut them out mercilessly. Leave only ONE instance of the phrase so it sounds like a normal human speaking.\n"
        "2. Fix broken, disjointed, or nonsensical Spanish sentences caused by poor AI translation.\n"
        "3. ADD intense grammatical punctuation (!, ?, ..., commas) to inject emotion into the TTS reading.\n"
        "4. REMOVE any emojis, asterisks (*), or sound effect labels (like [risa]). Only keep spoken words.\n"
        "5. CRITICAL: You MUST return EXACTLY the same number of chunks, keeping the exact same 'index' IDs.\n"
        "6. Return ONLY a valid JSON object in the format: {\"chunks\": [{\"index\": 0, \"text\": \"...\"}, ...]}\n\n"
        f"ORIGINAL SCRIPT:\n{json_input}"
    )
    
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "format": "json",
        "options": {
            "num_predict": 32768,
            "temperature": 0.3
        }
    }
    
    try:
        url = "http://127.0.0.1:11434/api/chat"
        res = call_ollama_api(url, payload, timeout=300)
        content = res.get("message", {}).get("content", "").strip()
        
        if "<think>" in content:
            content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
            
        start_idx = content.find('{')
        end_idx = content.rfind('}')
        if start_idx != -1 and end_idx != -1:
            content = content[start_idx:end_idx+1]
            
        data = json.loads(content)
        sanitized_chunks = data.get("chunks", [])
        
        # Security Check: Enforce structural integrity
        if len(sanitized_chunks) != len(chunks):
            print(f"[Sanador IA] ALERTA: La IA modificó la cantidad de segmentos ({len(sanitized_chunks)} vs {len(chunks)}). Abortando limpieza para proteger la sincronización.")
            return chunks
            
        # Map back safely by index
        sanitized_by_index = {c.get("index"): c.get("text", "") for c in sanitized_chunks}
        
        enhanced_chunks = []
        for i, orig_chunk in enumerate(chunks):
            new_chunk = dict(orig_chunk)
            # If the index is missing or text is empty, fallback to original
            new_text = sanitized_by_index.get(i)
            if new_text is None or new_text.strip() == "":
                new_text = orig_chunk.get("text", "")
            new_chunk["text"] = new_text
            enhanced_chunks.append(new_chunk)
            
        print("[Sanador IA] Limpieza exitosa. Guion optimizado para VibeVoice.")
        return enhanced_chunks
        
    except Exception as e:
        print(f"[Sanador IA] Falló la conexión o el formato ({e}). Usando traducción original.")
        return chunks
