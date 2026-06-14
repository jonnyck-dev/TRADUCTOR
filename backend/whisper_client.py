import subprocess
import os
import json

def wsl_to_windows_path(wsl_path: str) -> str:
    if os.name == 'nt':
        return os.path.abspath(wsl_path)
    wsl_path = os.path.abspath(wsl_path)
    try:
        result = subprocess.run(['wslpath', '-w', wsl_path], capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except Exception as e:
        print(f"Error converting path {wsl_path} with wslpath: {e}")
        if wsl_path.startswith('/mnt/'):
            parts = wsl_path.split('/')
            drive = parts[2].upper()
            remaining = '\\'.join(parts[3:])
            return f"{drive}:\\{remaining}"
        return wsl_path

def transcribe_audio(audio_path: str, output_json_path: str, language: str = "English", model_name: str = "openai/whisper-tiny") -> dict:
    """
    Transcribes audio using insanely-fast-whisper.
    Works natively on Windows or via WSL using cmd.exe.
    """
    # Project base directory
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    vibevoice_dir = os.path.join(base_dir, "backend", "vibevoice")
    whisper_dir = os.path.join(base_dir, "backend", "superfastWHISPER")

    if os.name == 'nt':
        win_audio_path = os.path.abspath(audio_path)
        win_output_json_path = os.path.abspath(output_json_path)
        os.makedirs(os.path.dirname(output_json_path), exist_ok=True)
        
        models_path = os.path.join(whisper_dir, "insanely-fast-whisper-main", "models")
        whisper_exe = os.path.join(vibevoice_dir, "env_vibevoice", "Scripts", "insanely-fast-whisper.exe")
        
        # Call the activated env binary directly with local HF_HOME set
        cmd = (
            f'set "PYTHONIOENCODING=utf-8" && '
            f'set "HF_HOME={models_path}" && '
            f'"{whisper_exe}" '
            f'--file-name "{win_audio_path}" --model-name "{model_name}" --language {language} '
            f'--transcript-path "{win_output_json_path}"'
        )
        cwd = None
    else:
        win_audio_path = wsl_to_windows_path(audio_path)
        win_output_json_path = wsl_to_windows_path(output_json_path)
        os.makedirs(os.path.dirname(output_json_path), exist_ok=True)
        cmd = (
            f'cmd.exe /c "set "HF_HOME=C:\\Users\\jpzam\\VibeVoice\\superfastWHISPER\\insanely-fast-whisper-main\\models" && '
            f'C:\\users\\jpzam\\Vibevoice\\env_vibevoice\\Scripts\\activate.bat && '
            f'cd /d C:\\Users\\jpzam\\VibeVoice\\superfastWHISPER\\insanely-fast-whisper-main && '
            f'insanely-fast-whisper.exe --file-name \\"{win_audio_path}\\" --model-name \\"{model_name}\\" --language {language} '
            f'--transcript-path \\"{win_output_json_path}\\"" < /dev/null'
        )
        cwd = "/mnt/c"

    print(f"Executing Whisper command: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd)


    if result.returncode != 0:
        print(f"Whisper stdout: {result.stdout}")
        print(f"Whisper stderr: {result.stderr}")
        raise RuntimeError(f"insanely-fast-whisper failed with exit code {result.returncode}")

    # Read output json
    if not os.path.exists(output_json_path):
        raise FileNotFoundError(f"Whisper completed but transcript JSON not found at: {output_json_path}")

    with open(output_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    return data

