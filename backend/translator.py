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

def repair_json_robust(json_str: str) -> str:
    """
    Reparación programática agresiva: extrae cada chunk individualmente con regex
    y reconstruye el JSON desde cero. Último recurso antes de llamar al LLM.
    """
    chunks = []
    # Match each chunk object individually: {"index": N, "text": "...", "timestamp": [...]}
    chunk_pattern = re.compile(
        r'\{\s*"index"\s*:\s*(\d+)\s*,\s*"text"\s*:\s*"((?:[^"\\]|\\.)*)"\s*,?\s*"timestamp"\s*:\s*(\[[^\]]*\])\s*\}',
        re.DOTALL
    )
    for m in chunk_pattern.finditer(json_str):
        idx = int(m.group(1))
        text = m.group(2)
        ts_raw = m.group(3)
        try:
            ts = json.loads(ts_raw)
        except:
            ts = [0.0, 0.0]
        chunks.append({"index": idx, "text": text, "timestamp": ts})
    
    # Fallback: try looser pattern where text might have unescaped quotes
    if not chunks:
        loose_pattern = re.compile(
            r'"index"\s*:\s*(\d+)\s*,\s*"text"\s*:\s*"(.+?)"\s*,\s*"timestamp"\s*:\s*(\[[^\]]*\])',
            re.DOTALL
        )
        for m in loose_pattern.finditer(json_str):
            idx = int(m.group(1))
            text = m.group(2).replace('"', '\\"')
            ts_raw = m.group(3)
            try:
                ts = json.loads(ts_raw)
            except:
                ts = [0.0, 0.0]
            chunks.append({"index": idx, "text": text, "timestamp": ts})
    
    if chunks:
        return json.dumps({"chunks": chunks}, ensure_ascii=False)
    return json_str

def translate_chunks(chunks: list, model: str = "gemma4:e2b-it-qat", save_dir: str = None, source_language: str = "English", target_language: str = "Spanish") -> list:
    url = "http://127.0.0.1:11434/api/chat"
    system_msg = (
        f"You are an expert {source_language} to {target_language} translator. "
        f"You will receive a JSON object with 'chunks' containing {source_language} text. "
        f"Translate the 'text' of each chunk to natural, fluent {target_language}. "
        "Keep the exact 'timestamp' and 'index' values. Do not omit, combine, or split chunks. "
        "CRITICAL: All double quotes inside 'text' values MUST be escaped as \\\". "
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
            min_input_path = os.path.join(save_dir, f"{source_language.lower()}_minimal.json")
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

        translated_minimal_chunks = []
        max_attempts = 5
        current_attempt = 1
        last_error = None
        
        # Try parsing raw JSON first (before any repair)
        try:
            translated_data = json.loads(json_str, strict=False)
            translated_minimal_chunks = translated_data.get("chunks", [])
            print("JSON parseado exitosamente sin reparación.")
        except json.JSONDecodeError as jde:
            print(f"JSON crudo inválido: {jde}. Aplicando reparación programática...")
            json_str = fix_json_quotes(json_str)
            json_str = repair_json_robust(json_str)
        
        # If still not parsed, enter correction loop
        if not translated_minimal_chunks:
            while current_attempt <= max_attempts:
                try:
                    translated_data = json.loads(json_str, strict=False)
                    translated_minimal_chunks = translated_data.get("chunks", [])
                    break
                except json.JSONDecodeError as jde:
                    last_error = jde
                    print(f"Advertencia: Intento {current_attempt}/{max_attempts} falló con JSONDecodeError: {jde}.")
                    
                    if current_attempt == max_attempts:
                        break
                    
                    # Apply repair functions before asking LLM
                    json_str = fix_json_quotes(json_str)
                    json_str = repair_json_robust(json_str)
                    
                    print(f"Solicitando auto-corrección al LLM...")
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
                    except Exception as e_corr:
                        print(f"Error al enviar consulta de corrección en intento {current_attempt}: {e_corr}")
                        raise jde
                        
                    current_attempt += 1
                
        if not translated_minimal_chunks and last_error:
            print(f"Fallo crítico: No se pudo auto-corregir el JSON de traducción tras {max_attempts} intentos.")
            print(f"Usando texto original como fallback para {len(chunks)} chunks.")
            translated_minimal_chunks = []
            for idx, c in enumerate(chunks):
                translated_minimal_chunks.append({
                    "index": idx,
                    "text": c.get("text", ""),
                    "timestamp": c.get("timestamp", [0.0, 0.0])
                })
            
        if save_dir and translated_minimal_chunks:
            try:
                min_output_path = os.path.join(save_dir, f"{target_language.lower()}_minimal.json")
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
                chunk_prompt = f"Translate the following {source_language} sentence to natural, fluent {target_language}. Return ONLY the translated {target_language} text and nothing else:\n\n{orig_text}"
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



def safe_parse_ollama_json(content: str, model: str, max_retries: int = 3) -> dict:
    """
    Clean Ollama response, apply aggressive JSON repair, and auto-correct via LLM if needed.
    Mirrors the battle-tested logic in translate_chunks.
    """
    content = content.strip()
    if "<think>" in content:
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
    if content.startswith("```"):
        content = re.sub(r'^```(?:json)?\s*', '', content)
    if content.endswith("```"):
        content = re.sub(r'\s*```$', '', content)

    start = content.find('{')
    if start == -1:
        start = content.find('[')
    end = content.rfind('}')
    if end == -1 or content.rfind(']') > end:
        end = content.rfind(']')
    if start != -1 and end != -1:
        content = content[start:end+1]

    for attempt in range(max_retries + 1):
        try:
            return json.loads(content, strict=False)
        except json.JSONDecodeError as jde:
            content = fix_json_quotes(content)
            content = repair_json_robust(content)
            try:
                return json.loads(content, strict=False)
            except json.JSONDecodeError:
                pass

            if attempt >= max_retries:
                raise jde

            print(f"  [safe-parse] JSON roto, pidiendo autocorrección al LLM (intento {attempt+1}/{max_retries})...")
            correction_prompt = (
                f"The following JSON text contains a syntax error: {jde}.\n"
                f"Please fix ONLY the syntax errors (missing commas, unescaped quotes, unmatched brackets) "
                f"and return the valid corrected JSON. Do NOT change values or structure. Return ONLY the raw corrected JSON.\n\n"
                f"MALFORMED JSON:\n{content}"
            )
            corr_payload = {
                "model": model,
                "messages": [{"role": "user", "content": correction_prompt}],
                "stream": False,
                "format": "json",
                "options": {"num_ctx": 128000, "num_predict": 32768, "temperature": 0.0}
            }
            try:
                corr_res = call_ollama_api("http://127.0.0.1:11434/api/chat", corr_payload, timeout=180)
                content = corr_res.get("message", {}).get("content", "").strip()
                if "<think>" in content:
                    content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
                if content.startswith("```"):
                    content = re.sub(r'^```(?:json)?\s*', '', content)
                if content.endswith("```"):
                    content = re.sub(r'\s*```$', '', content)
                s = content.find('{')
                if s == -1: s = content.find('[')
                e = content.rfind('}')
                if e == -1 or content.rfind(']') > e: e = content.rfind(']')
                if s != -1 and e != -1:
                    content = content[s:e+1]
            except Exception:
                pass

    raise ValueError(f"safe_parse_ollama_json: unable to parse JSON after {max_retries} retries")


def enhance_translation_for_tts(chunks: list, model: str) -> list:
    print("\n[Sanador IA] Iniciando segunda pasada de limpieza y emoción para el TTS...")
    
    minimal_chunks = [{"index": i, "text": c.get("text", "")} for i, c in enumerate(chunks)]
    json_input = json.dumps({"chunks": minimal_chunks}, ensure_ascii=False)
    
    system_msg = (
        "You are a script cleaner for a Spanish Text-to-Speech engine. "
        "Remove AI stuttering, repeated words, and translation artifacts from the Spanish text. "
        "Add punctuation (!, ?, ...) for natural TTS emotion. Remove emojis and sound effect labels. "
        "CRITICAL: Return EXACTLY the same number of chunks with the same index IDs. "
        "Return ONLY a valid JSON object: {\"chunks\": [{\"index\": 0, \"text\": \"...\"}, ...]}"
    )
    
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": json_input}
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
        url = "http://127.0.0.1:11434/api/chat"
        res = call_ollama_api(url, payload, timeout=300)
        content = res.get("message", {}).get("content", "").strip()
        data = safe_parse_ollama_json(content, model)
        sanitized_chunks = data.get("chunks", [])
        
        sanitized_by_index = {c.get("index"): c.get("text", "") for c in sanitized_chunks}
        
        enhanced_chunks = []
        for i, orig_chunk in enumerate(chunks):
            new_chunk = dict(orig_chunk)
            new_text = sanitized_by_index.get(i)
            if new_text is None or new_text.strip() == "":
                new_text = orig_chunk.get("text", "")
            new_chunk["text"] = new_text
            enhanced_chunks.append(new_chunk)
            
        print("[Sanador IA] Limpieza exitosa. Guion optimizado para TTS.")
        return enhanced_chunks
        
    except Exception as e:
        print(f"[Sanador IA] Falló ({e}). Usando traducción original.")
        return chunks

def synchronize_translation_for_tts(chunks: list, model: str) -> list:
    import math
    print("\n[Sanador IA] Paso 3: Sincronización Matemática de Tiempos...")
    import re
    chunks_to_sync = []
    
    for idx, chunk in enumerate(chunks):
        ts = chunk.get("timestamp", [0.0, 0.0])
        if isinstance(ts, (list, tuple)) and len(ts) == 2:
            duration = ts[1] - ts[0]
        else:
            duration = 2.0
            
        orig_text = chunk.get("orig_text", "")
        orig_words = len(orig_text.split()) if orig_text else int(duration * 2.5)
        
        # Max words is the max between duration * 2.5 and original_words * 1.25
        max_words = int(max(math.ceil(duration * 2.5), math.ceil(orig_words * 1.25)))
        
        # PHYSICAL LIMIT CAP: A TTS engine cannot realistically speak more than 3.5 words per second without artifacting.
        # If the original speaker spoke insanely fast, we must still enforce a hard cap for the Spanish TTS.
        absolute_max = int(math.ceil(duration * 3.5))
        if max_words > absolute_max:
            max_words = absolute_max
        
        current_text = chunk.get("text", "")
        current_words = len(current_text.split())
        
        # If it exceeds the limit with a small buffer, mark for reduction
        if current_words > max_words + 1:
            chunks_to_sync.append({
                "index": idx,
                "text": current_text,
                "duration_sec": round(duration, 2),
                "current_words": current_words,
                "target_max_words": max_words
            })
            
    if not chunks_to_sync:
        print("[Sanador IA] Todas las frases están dentro del límite de tiempo. No se requiere sincronización.")
        return chunks
        
    print(f"[Sanador IA] {len(chunks_to_sync)} frases exceden el límite. Llamando a IA Sincronizadora...")
    
    json_input = json.dumps(chunks_to_sync, ensure_ascii=False)
    
    system_msg = (
        "You are an audio dubbing synchronizer. The following Spanish phrases are too long for their video time slots. "
        "Paraphrase each phrase to fit within its target_max_words without losing core meaning. "
        "Output in Spanish. Keep punctuation. CRITICAL: Return EXACTLY the same number of items with the same index IDs. "
        "Return ONLY a valid JSON array: [{\"index\": 0, \"text\": \"...\"}, ...]"
    )
    
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": json_input}
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
        url = "http://127.0.0.1:11434/api/chat"
        res = call_ollama_api(url, payload, timeout=300)
        content = res.get("message", {}).get("content", "").strip()
        
        sync_data = safe_parse_ollama_json(content, model)
        
        synced_chunks = {}
        for item in (sync_data if isinstance(sync_data, list) else sync_data.get("chunks", sync_data.get("data", []))):
            idx = item.get("index")
            txt = item.get("text")
            if idx is not None and txt:
                synced_chunks[idx] = txt
        
        for i, chunk in enumerate(chunks):
            if i in synced_chunks:
                chunks[i]["text"] = synced_chunks[i]
                print(f"  [Sinc] Frase {i} ajustada al límite de tiempo.")

        return chunks
    except Exception as e:
        print(f"[Sanador IA] Falló la sincronización: {e}. Usando texto largo original.")
        return chunks

def phonetic_normalization_for_tts(chunks: list, model: str, save_dir: str = None, target_language: str = "spanish") -> list:
    print("\n[Sanador IA] Paso Extra: Normalización Fonética (Anti-Acento Inglés)...")
    import re
    chunks_to_phoneticize = []
    
    for idx, chunk in enumerate(chunks):
        text = chunk.get("text", "")
        if re.search(r'\d', text) or re.search(r'\b[A-Z]{2,}\b', text):
            chunks_to_phoneticize.append({
                "index": idx,
                "text": text
            })
            
    if chunks_to_phoneticize:
        print(f"[Sanador IA] Se detectaron {len(chunks_to_phoneticize)} frases con números o acrónimos. Llamando a IA Fonética...")
        json_input = json.dumps(chunks_to_phoneticize, ensure_ascii=False)
        
        system_msg = (
            "You are a phonetic transcriber for a Spanish Text-to-Speech engine. "
            "Convert numbers to spelled-out Spanish words and acronyms to phonetic Spanish syllables. "
            "CRITICAL: Return EXACTLY the same number of items with the same index IDs. "
            "Return ONLY a valid JSON array: [{\"index\": 0, \"text\": \"...\"}, ...]"
        )
        
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": json_input}
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
            url = "http://127.0.0.1:11434/api/chat"
            res = call_ollama_api(url, payload, timeout=300)
            content = res.get("message", {}).get("content", "").strip()
            
            phone_data = safe_parse_ollama_json(content, model)
            
            if isinstance(phone_data, list):
                for p_item in phone_data:
                    idx = p_item.get("index")
                    new_text = p_item.get("text")
                    if idx is not None and new_text and 0 <= idx < len(chunks):
                        chunks[idx]["text"] = new_text
                        print(f"  [Fonética] Bloque {idx} normalizado: {new_text}")
            else:
                phone_items = phone_data.get("chunks", phone_data.get("data", []))
                if isinstance(phone_items, list):
                    for p_item in phone_items:
                        idx = p_item.get("index")
                        new_text = p_item.get("text")
                        if idx is not None and new_text and 0 <= idx < len(chunks):
                            chunks[idx]["text"] = new_text
                            print(f"  [Fonética] Bloque {idx} normalizado: {new_text}")
                else:
                    print("[Sanador IA] Error: La IA Fonética no devolvió una lista JSON válida.")
        except Exception as e:
            print(f"[Sanador IA] Falló la normalización fonética: {e}. Se usará texto original.")
    else:
        print("[Sanador IA] No se encontraron números ni acrónimos. Omitiendo pase de IA Fonética.")
        
    if save_dir:
        out_path = os.path.join(save_dir, f"{target_language.lower()}_phonetic.json")
        try:
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump({"chunks": chunks}, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[Warning] No se pudo guardar spanish_phonetic.json: {e}")
            
    return chunks
