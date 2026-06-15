import subprocess
import os
from pydub import AudioSegment
from whisper_client import wsl_to_windows_path

def generate_tts(chunks: list, output_dir: str, speaker_name: str = "en-Frank_man") -> str:
    """
    Generates a single continuous WAV file from translated chunks using VibeVoice TTS.
    Optimized to split the text into batches of max 2 minutes (original duration) to prevent
    VibeVoice from hallucinating/degrading. Generates each batch separately and concatenates
    them using pydub.
    """
    os.makedirs(output_dir, exist_ok=True)
    
    expected_wav = os.path.join(output_dir, "script_generated.wav")
    if os.path.exists(expected_wav) and os.path.getsize(expected_wav) > 0:
        print(f"Skipping VibeVoice generation, using cached: {expected_wav}")
        return expected_wav

    # Group chunks into batches where each batch spans at most 120 seconds of original duration.
    batches = []
    current_batch = []
    batch_start = None
    
    for chunk in chunks:
        ts = chunk.get("timestamp", [0, 0])
        start, end = ts[0], ts[1]
        
        # Skip empty text chunks to avoid unnecessary VibeVoice processing
        if not chunk.get("text", "").strip():
            continue
            
        if batch_start is None:
            batch_start = start
            
        # If adding this chunk makes the batch duration exceed 120 seconds, start a new batch.
        if current_batch and (end - batch_start > 120.0):
            batches.append(current_batch)
            current_batch = [chunk]
            batch_start = start
        else:
            current_batch.append(chunk)
            
    if current_batch:
        batches.append(current_batch)

    if not batches:
        raise ValueError("No text segments to feed to VibeVoice TTS.")
        
    print(f"Split script into {len(batches)} batches of max 2 minutes.")
    
    # Project base directory
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    vibevoice_dir = os.path.join(base_dir, "backend", "vibevoice")
    
    batch_wavs = []
    
    for idx, batch_chunks in enumerate(batches):
        batch_txt_path = os.path.join(output_dir, f"script_batch_{idx}.txt")
        batch_wav_path = os.path.join(output_dir, f"script_batch_{idx}_generated.wav")
        
        # Prepare content
        content_lines = []
        for chunk in batch_chunks:
            text = chunk["text"].strip()
            if text:
                content_lines.append(f"Speaker 1: {text}\n")
        
        content = "".join(content_lines)
        
        # Check if we can reuse the cached WAV for this batch
        reuse_cache = False
        if os.path.exists(batch_txt_path) and os.path.exists(batch_wav_path) and os.path.getsize(batch_wav_path) > 0:
            with open(batch_txt_path, "r", encoding="utf-8") as f:
                existing_content = f.read()
            if existing_content == content:
                reuse_cache = True
                
        if reuse_cache:
            print(f"Skipping VibeVoice generation for batch {idx}, using cached: {batch_wav_path}")
            batch_wavs.append(batch_wav_path)
            continue
            
        # Write batch script file
        with open(batch_txt_path, "w", encoding="utf-8") as f:
            f.write(content)
            
        win_txt_path = wsl_to_windows_path(batch_txt_path)
        win_output_dir = wsl_to_windows_path(output_dir)
        
        if os.name == 'nt':
            python_exe = os.path.join(vibevoice_dir, "env_vibevoice", "Scripts", "python.exe")
            model_path = os.path.join(vibevoice_dir, "checkpoints", "VibeVoice-1.5B")
            
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
                f'python demo/inference_from_file.py --model_path \\"C:\\Users\\jpzam\\VibeVoice\\checkpoints\\VibeVoice-1.5B\\" '
                f'--speaker_names \\"{speaker_name}\\" --device cuda --txt_path \\"{win_txt_path}\\" '
                f'--output_dir \\"{win_output_dir}\\"" < /dev/null'
            )
            cwd = "/mnt/c"
            
        print(f"Executing VibeVoice command for batch {idx}/{len(batches)-1}: {cmd}")
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd)
        
        if result.returncode != 0:
            print(f"VibeVoice stdout: {result.stdout}")
            print(f"VibeVoice stderr: {result.stderr}")
            raise RuntimeError(f"VibeVoice TTS failed on batch {idx} with exit code {result.returncode}")
            
        if not os.path.exists(batch_wav_path):
            raise FileNotFoundError(f"VibeVoice completed but batch output WAV not found at: {batch_wav_path}")
            
        batch_wavs.append(batch_wav_path)

    # Concatenate the audio segments
    print(f"Concatenating {len(batch_wavs)} batches into a single WAV...")
    combined = None
    silence_seg = AudioSegment.silent(duration=100)  # 100ms silence
    
    for wav_path in batch_wavs:
        seg = AudioSegment.from_wav(wav_path)
        if combined is None:
            combined = seg
        else:
            combined = combined + silence_seg + seg
            
    # Save combined audio
    if combined is not None:
        combined.export(expected_wav, format="wav")
    else:
        raise ValueError("No audio segments generated.")
        
    return expected_wav
