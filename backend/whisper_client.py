import subprocess
import os
import json

def wsl_to_windows_path(wsl_path: str) -> str:
    if wsl_path.startswith('/mnt/'):
        parts = wsl_path.split('/')
        drive = parts[2].upper()
        remaining = '\\'.join(parts[3:])
        return f"{drive}:\\{remaining}"
    if os.name == 'nt':
        return os.path.abspath(wsl_path)
    wsl_path = os.path.abspath(wsl_path)
    try:
        result = subprocess.run(['wslpath', '-w', wsl_path], capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except Exception as e:
        print(f"Error converting path {wsl_path} with wslpath: {e}")
        return wsl_path

def transcribe_audio(audio_path: str, output_json_path: str, language: str = "English", model_name: str = "openai/whisper-tiny") -> dict:
    """
    Transcribes audio using WhisperX to get high-precision segment and word-level timestamps.
    Works natively on Windows or via WSL using cmd.exe.
    """
    # Project base directory
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    vibevoice_dir = os.path.join(base_dir, "backend", "vibevoice")

    # Map model name for WhisperX CLI
    model_arg = model_name
    model_lower = model_name.lower()
    if "whisper-tiny" in model_lower or model_lower == "tiny":
        model_arg = "tiny"
    elif "whisper-small" in model_lower or model_lower == "small":
        model_arg = "small"
    elif "whisper-medium" in model_lower or model_lower == "medium":
        model_arg = "medium"
    elif "whisper-base" in model_lower or model_lower == "base":
        model_arg = "base"
    elif "whisper-large" in model_lower or "large" in model_lower:
        model_arg = "large-v2"

    # Map language name to code
    lang_code = "en" if language.lower() in ["english", "en"] else "es" if language.lower() in ["spanish", "es"] else language

    if os.name == 'nt':
        whisperx_exe = os.path.join(vibevoice_dir, "env_vibevoice", "Scripts", "whisperx.exe")
        win_audio_path = os.path.abspath(audio_path)
        win_output_dir = os.path.abspath(os.path.dirname(output_json_path))
        os.makedirs(os.path.dirname(output_json_path), exist_ok=True)
        
        cmd = (
            f'"{whisperx_exe}" '
            f'"{win_audio_path}" --model {model_arg} --language {lang_code} '
            f'--output_dir "{win_output_dir}" --output_format json --device cuda --compute_type float16'
        )
        cwd = None
    else:
        win_audio_path = wsl_to_windows_path(audio_path)
        win_output_dir = wsl_to_windows_path(os.path.dirname(output_json_path))
        os.makedirs(os.path.dirname(output_json_path), exist_ok=True)
        
        win_vibevoice_dir = wsl_to_windows_path(vibevoice_dir)
        activate_bat = os.path.join(vibevoice_dir, "env_vibevoice", "Scripts", "activate.bat")
        win_activate = wsl_to_windows_path(activate_bat)
        
        cmd = (
            f'cmd.exe /c "set VIRTUAL_ENV=&\"{win_activate}\"&& '
            f'whisperx \\"{win_audio_path}\\" --model {model_arg} --language {lang_code} '
            f'--output_dir \\"{win_output_dir}\\" --output_format json --device cuda --compute_type float16" < /dev/null'
        )
        cwd = "/mnt/c"

    print(f"Executing WhisperX command: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd)

    if result.returncode != 0:
        print(f"WhisperX stdout: {result.stdout}")
        print(f"WhisperX stderr: {result.stderr}")
        raise RuntimeError(f"WhisperX transcription failed with exit code {result.returncode}")

    # Read output json
    audio_filename = os.path.basename(audio_path)
    audio_name_no_ext, _ = os.path.splitext(audio_filename)
    generated_json = os.path.join(os.path.dirname(output_json_path), f"{audio_name_no_ext}.json")

    if not os.path.exists(generated_json):
        # Scan output directory for any json matching the file name just in case
        json_dir = os.path.dirname(output_json_path)
        if os.path.exists(json_dir):
            matching_files = [f for f in os.listdir(json_dir) if f.endswith(".json") and audio_name_no_ext in f]
            if matching_files:
                generated_json = os.path.join(json_dir, matching_files[0])
            else:
                raise FileNotFoundError(f"WhisperX completed but transcript JSON not found at: {generated_json}")
        else:
            raise FileNotFoundError(f"WhisperX completed but output dir does not exist: {json_dir}")

    with open(generated_json, 'r', encoding='utf-8') as f:
        wx_data = json.load(f)

    # Format WhisperX output to match expected backend format
    chunks = []
    for seg in wx_data.get("segments", []):
        chunk_words = []
        for w in seg.get("words", []):
            if "start" in w and "end" in w:
                chunk_words.append({
                    "word": w.get("word", ""),
                    "start": w.get("start"),
                    "end": w.get("end")
                })
        chunks.append({
            "timestamp": [seg.get("start", 0.0), seg.get("end", 0.0)],
            "text": seg.get("text", "").strip(),
            "words": chunk_words
        })

    formatted_data = {
        "text": " ".join([seg.get("text", "").strip() for seg in wx_data.get("segments", [])]),
        "chunks": chunks
    }

    # Write formatted json to target output_json_path
    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(formatted_data, f, ensure_ascii=False, indent=2)

    # Clean up the intermediate json if it was named differently
    if generated_json != output_json_path and os.path.exists(generated_json):
        try:
            os.remove(generated_json)
        except Exception as e:
            print(f"Non-fatal error removing temporary WhisperX file {generated_json}: {e}")

    return formatted_data

