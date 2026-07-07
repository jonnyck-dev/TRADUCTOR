#!/usr/bin/env python3
"""
Test de diagnóstico: replica el prompt EXACTO de translator.py
para ver qué devuelve Ollama al traducir japonés → español.
"""

import requests
import json
import sys
import os
from datetime import datetime

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_OUTPUT_FILE = os.path.join(OUTPUT_DIR, "test_raw_output.txt")
REPORT_FILE = os.path.join(OUTPUT_DIR, "test_report.txt")

# Texto japonés REAL del caché (Attack on Titan dialogue)
JAPANESE_TEXT = "お前さ、疲れてんだよなあ、ベルトルトこうなってもおかしくないくらい大変だったんだろう?ああ、ライナーは疲れているんだだいたいな、お前が人類を殺しまくった鎧の巨人なら"

# Prompt EXACTO de translator.py (línea 66-72)
source_language = "Japanese"
target_language = "Spanish"

system_msg = (
    f"You are an expert {source_language} to {target_language} translator. "
    f"You will receive a JSON object with 'chunks' containing {source_language} text. "
    f"Translate the 'text' of each chunk to natural, fluent {target_language}. "
    "Keep the exact 'timestamp' and 'index' values. Do not omit, combine, or split chunks. "
    "Return the resulting JSON object with the translated 'chunks' and nothing else."
)

# Input EXACTO que se envía al LLM
test_chunks = {
    "chunks": [
        {
            "index": 0,
            "text": JAPANESE_TEXT,
            "timestamp": [2.45, 19.122]
        }
    ]
}

# Payload EXACTO de translator.py (línea 95-108)
payload = {
    "model": "gemma4:e2b-it-qat",
    "messages": [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": json.dumps(test_chunks, ensure_ascii=False)}
    ],
    "stream": False,
    "format": "json",
    "options": {
        "num_ctx": 128000,
        "num_predict": 32768,
        "temperature": 0.0
    }
}

def fix_json_quotes(json_str: str) -> str:
    """Copia exacta de translator.py"""
    import re
    json_str = re.sub(r'\}\s*\{', '},\n{', json_str)
    json_str = re.sub(r'\]\s*\{', '],\n{', json_str)
    
    def replace_quote(match):
        prefix = match.group(1)
        content = match.group(2)
        suffix = match.group(3)
        temp = content.replace('\\"', '___ESCAPED_QUOTE___')
        temp = temp.replace('"', '\\"')
        escaped_content = temp.replace('___ESCAPED_QUOTE___', '\\"')
        if "timestamp" in suffix and "," not in suffix:
            suffix = '", "timestamp"'
        return prefix + escaped_content + suffix
    
    pattern = r'("text"\s*:\s*")(.*?)((?<!\\)"\s*,?\s*(?<!\\)"timestamp"|\s*\})'
    return re.sub(pattern, replace_quote, json_str, flags=re.DOTALL)

def main():
    print("=" * 80)
    print("TEST DE TRADUCCIÓN: japonés → español con gemma4:e2b-it-qat")
    print("=" * 80)
    print(f"\nTexto japonés de entrada ({len(JAPANESE_TEXT)} caracteres):")
    print(JAPANESE_TEXT)
    print("\n" + "=" * 80)
    print("Enviando prompt a Ollama...")
    print(f"Modelo: {payload['model']}")
    print(f"num_predict: {payload['options']['num_predict']}")
    print(f"format: {payload['format']}")
    print("=" * 80)
    
    try:
        response = requests.post(
            "http://127.0.0.1:11434/api/chat",
            json=payload,
            timeout=900
        )
        response.raise_for_status()
        
        result = response.json()
        raw_content = result.get("message", {}).get("content", "").strip()
        
        print(f"\nRespuesta cruda recibida ({len(raw_content)} caracteres):")
        print("-" * 80)
        print(raw_content[:2000])  # Primeros 2000 chars
        if len(raw_content) > 2000:
            print(f"\n... [{len(raw_content) - 2000} caracteres más] ...")
        print("-" * 80)
        
        # Guardar respuesta cruda
        with open(RAW_OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write(raw_content)
        print(f"\nRespuesta cruda guardada en: {RAW_OUTPUT_FILE}")
        
        # Limpiar think tags (como hace translator.py)
        import re
        content = raw_content
        if "<think>" in content:
            think_match = re.search(r'<think>(.*?)</think>', content, flags=re.DOTALL)
            if think_match:
                print(f"\n[INFO] Detectado <think> tag ({len(think_match.group(1))} caracteres)")
                content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
        
        # Limpiar markdown code blocks
        if content.startswith("```"):
            content = re.sub(r'^```(?:json)?\s*', '', content)
        if content.endswith("```"):
            content = re.sub(r'\s*```$', '', content)
        
        # Extraer JSON
        start = content.find('{')
        end = content.rfind('}')
        if start != -1 and end != -1:
            json_str = content[start:end+1]
        else:
            json_str = content
        
        print(f"\nJSON extraído ({len(json_str)} caracteres):")
        print(json_str[:1000])
        
        # Intentar parsear PRIMERO (antes de cualquier reparación)
        print("\n" + "=" * 80)
        print("Intentando parsear JSON crudo (sin reparación)...")
        print("=" * 80)
        
        try:
            data = json.loads(json_str, strict=False)
            print("\n✅ ÉXITO: JSON parseado sin necesidad de reparación")
        except json.JSONDecodeError as e:
            print(f"\n❌ JSON crudo inválido: {e}")
            print("\nAplicando fix_json_quotes...")
            json_str = fix_json_quotes(json_str)
            print(f"\nDespués de fix_json_quotes:")
            print(json_str[:1000])
            
            print("\nIntentando parsear de nuevo...")
            try:
                data = json.loads(json_str, strict=False)
                print("\n✅ ÉXITO: JSON parseado después de reparación")
            except json.JSONDecodeError as e2:
                print(f"\n❌ FALLO: {e2}")
                print(f"\nPosición del error: línea {e2.lineno}, columna {e2.colno}, char {e2.pos}")
                
                # Mostrar contexto alrededor del error
                error_pos = e2.pos
                context_start = max(0, error_pos - 50)
                context_end = min(len(json_str), error_pos + 50)
                context = json_str[context_start:context_end]
                
                print(f"\nContexto alrededor del error (pos {context_start}-{context_end}):")
                print("-" * 80)
                print(context)
                print("-" * 80)
                print(f"{' ' * (error_pos - context_start)}↑ ERROR AQUÍ")
                
                # Mostrar el carácter exacto
                if error_pos < len(json_str):
                    char_at_error = json_str[error_pos]
                    print(f"\nCarácter en posición {error_pos}: '{char_at_error}' (U+{ord(char_at_error):04X})")
                
                # Guardar reporte detallado
                report = {
                    "timestamp": datetime.now().isoformat(),
                    "model": payload['model'],
                    "input_text": JAPANESE_TEXT,
                    "raw_response": raw_content,
                    "json_extracted": json_str,
                    "error": str(e2),
                    "error_position": e2.pos,
                    "context": context
                }
                with open(REPORT_FILE, "w", encoding="utf-8") as f:
                    json.dump(report, f, ensure_ascii=False, indent=2)
                print(f"\nReporte detallado guardado en: {REPORT_FILE}")
                sys.exit(1)
        
        # Si llegamos aquí, el JSON fue parseado exitosamente
        print(f"\nChunks traducidos: {len(data.get('chunks', []))}")
        for chunk in data.get('chunks', []):
            print(f"  Index {chunk.get('index')}: {chunk.get('text', '')[:100]}...")
        
        # Verificar si hay traducción real
        translated_text = data.get('chunks', [{}])[0].get('text', '')
        if translated_text == JAPANESE_TEXT:
            print("\n⚠️  ADVERTENCIA: El texto NO fue traducido (sigue en japonés)")
        elif not translated_text:
            print("\n⚠️  ADVERTENCIA: El texto traducido está vacío")
        else:
            print(f"\n✅ Traducción exitosa: {translated_text[:150]}...")
            
    except requests.exceptions.RequestException as e:
        print(f"\n❌ ERROR DE CONEXIÓN: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
