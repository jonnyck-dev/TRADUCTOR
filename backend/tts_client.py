import subprocess
import os
from whisper_client import wsl_to_windows_path

def generate_tts(chunks: list, output_dir: str, speaker_name: str = "en-Frank_man") -> str:
    """
    Generates a single continuous WAV file from translated chunks using VibeVoice TTS.
    Writes a structured text script, runs VibeVoice on Windows via WSL, and returns
    the path to the generated WAV file.
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # Write the script in VibeVoice multi-speaker format
    txt_path = os.path.join(output_dir, "script.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        for idx, chunk in enumerate(chunks):
            text = chunk["text"].strip()
            # If text is empty, skip or write a placeholder (though skip is better)
            if text:
                f.write(f"Speaker 1: {text}\n")
    
    # Check if we wrote any text
    if not os.path.exists(txt_path) or os.path.getsize(txt_path) == 0:
        raise ValueError("No text segments to feed to VibeVoice TTS.")
        
    win_txt_path = wsl_to_windows_path(txt_path)
    win_output_dir = wsl_to_windows_path(output_dir)
    
    # Project base directory
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    vibevoice_dir = os.path.join(base_dir, "backend", "vibevoice")

    # Command to run VibeVoice inference
    if os.name == 'nt':
        python_exe = os.path.join(vibevoice_dir, "env_vibevoice", "Scripts", "python.exe")
        model_path = os.path.join(vibevoice_dir, "checkpoints", "VibeVoice-Realtime-0.5B")
        
        cmd = (
            f'"{python_exe}" '
            f'demo/inference_from_file.py --model_path "{model_path}" '
            f'--speaker_names "{speaker_name}" --device cuda --txt_path "{win_txt_path}" '
            f'--output_dir "{win_output_dir}"'
        )
        cwd = vibevoice_dir
    else:
        cmd = (
            f'cmd.exe /c "C:\\users\\jpzam\\Vibevoice\\env_vibevoice\\Scripts\\activate.bat && '
            f'cd /d C:\\Users\\jpzam\\VibeVoice && '
            f'python demo/inference_from_file.py --model_path \\"C:\\Users\\jpzam\\VibeVoice\\checkpoints\\VibeVoice-Realtime-0.5B\\" '
            f'--speaker_names \\"{speaker_name}\\" --device cuda --txt_path \\"{win_txt_path}\\" '
            f'--output_dir \\"{win_output_dir}\\"" < /dev/null'
        )
        cwd = "/mnt/c"
    
    print(f"Executing VibeVoice command: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd)
    
    if result.returncode != 0:
        print(f"VibeVoice stdout: {result.stdout}")
        print(f"VibeVoice stderr: {result.stderr}")
        raise RuntimeError(f"VibeVoice TTS failed with exit code {result.returncode}")
        
    # Expected output path: output_dir/script_generated.wav
    expected_wav = os.path.join(output_dir, "script_generated.wav")
    if not os.path.exists(expected_wav):
        # Scan output directory for any generated wav file
        wav_files = [f for f in os.listdir(output_dir) if f.endswith(".wav")]
        if wav_files:
            expected_wav = os.path.join(output_dir, wav_files[0])
        else:
            raise FileNotFoundError(f"VibeVoice completed but output WAV not found in: {output_dir}")
            
    return expected_wav
