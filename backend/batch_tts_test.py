import os
import json
import time
import requests
import subprocess
from pydub import AudioSegment

# Setup paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_DIR = os.path.join(BASE_DIR, "backend")
VIBEVOICE_DIR = os.path.join(PROJECT_DIR, "vibevoice")

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

def start_vibevoice_server() -> subprocess.Popen:
    if os.name == 'nt':
        python_exe = os.path.join(VIBEVOICE_DIR, "env_vibevoice", "Scripts", "python.exe")
        cmd = f'"{python_exe}" vibevoice_server.py'
        cwd = VIBEVOICE_DIR
    else:
        python_exe = os.path.join(VIBEVOICE_DIR, "env_vibevoice", "Scripts", "python.exe")
        win_python_exe = wsl_to_windows_path(python_exe)
        win_vibevoice_dir = wsl_to_windows_path(VIBEVOICE_DIR)
        cmd = f'cmd.exe /c "cd /d {win_vibevoice_dir} && "{win_python_exe}" vibevoice_server.py" < /dev/null'
        cwd = "/mnt/c"
        
    print(f"Starting VibeVoice server dynamically with command: {cmd}")
    process = subprocess.Popen(cmd, shell=True, cwd=cwd)
    
    print("Waiting for VibeVoice server to start and load model...")
    server_ready = False
    start_time = time.time()
    while time.time() - start_time < 60:
        try:
            resp = requests.get("http://127.0.0.1:8001/openapi.json", timeout=1.0)
            if resp.status_code == 200:
                print(f"VibeVoice server is ready! (took {time.time() - start_time:.2f}s)")
                server_ready = True
                break
        except Exception:
            pass
        time.sleep(1.0)
        
    if not server_ready:
        print("Warning: VibeVoice server did not respond within 60 seconds.")
    return process

def stop_vibevoice_server(process=None):
    print("Stopping VibeVoice server...")
    try:
        resp = requests.post("http://127.0.0.1:8001/shutdown", timeout=2.0)
        print("Shutdown request response:", resp.json())
    except Exception as e:
        print(f"Failed to call shutdown endpoint: {e}")
        
    if os.name == 'nt':
        try:
            res = subprocess.run("netstat -ano", capture_output=True, text=True, shell=True)
            for line in res.stdout.splitlines():
                if ":8001" in line and "LISTENING" in line:
                    parts = line.strip().split()
                    if len(parts) >= 5:
                        pid = parts[-1]
                        print(f"Force-killing VibeVoice server process PID {pid} on port 8001...")
                        subprocess.run(f"taskkill /f /pid {pid}", shell=True, capture_output=True)
        except Exception as ke:
            print(f"Error force-killing VibeVoice process on port 8001: {ke}")
    else:
        try:
            res = subprocess.run("lsof -t -i:8001", capture_output=True, text=True, shell=True)
            pid = res.stdout.strip()
            if pid:
                print(f"Force-killing VibeVoice server process PID {pid} on port 8001...")
                subprocess.run(f"kill -9 {pid}", shell=True)
        except Exception as ke:
            print(f"Error force-killing VibeVoice process on port 8001: {ke}")

    if process:
        try:
            process.terminate()
            process.wait(timeout=2)
            print("Subprocess terminated.")
        except Exception as pe:
            print(f"Failed to terminate subprocess: {pe}")

def run_whisperx_on_file(audio_path: str, output_json_path: str) -> dict:
    if os.name == 'nt':
        whisperx_exe = os.path.join(VIBEVOICE_DIR, "env_vibevoice", "Scripts", "whisperx.exe")
        win_audio_path = os.path.abspath(audio_path)
        win_output_dir = os.path.abspath(os.path.dirname(output_json_path))
        os.makedirs(os.path.dirname(output_json_path), exist_ok=True)
        cmd = (
            f'"{whisperx_exe}" "{win_audio_path}" --model tiny --language es '
            f'--output_dir "{win_output_dir}" --output_format json --device cuda --compute_type float16'
        )
        cwd = None
    else:
        win_audio_path = wsl_to_windows_path(audio_path)
        win_output_dir = wsl_to_windows_path(os.path.dirname(output_json_path))
        os.makedirs(os.path.dirname(output_json_path), exist_ok=True)
        cmd = (
            f'cmd.exe /c "C:\\users\\jpzam\\Vibevoice\\env_vibevoice\\Scripts\\activate.bat && '
            f'whisperx \\"{win_audio_path}\\" --model tiny --language es '
            f'--output_dir \\"{win_output_dir}\\" --output_format json --device cuda --compute_type float16" < /dev/null'
        )
        cwd = "/mnt/c"

    print(f"Running WhisperX: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd)
    if result.returncode != 0:
        raise RuntimeError(f"WhisperX failed: {result.stderr}")
        
    audio_filename = os.path.basename(audio_path)
    audio_name_no_ext, _ = os.path.splitext(audio_filename)
    generated_json = os.path.join(os.path.dirname(output_json_path), f"{audio_name_no_ext}.json")
    
    with open(generated_json, 'r', encoding='utf-8') as f:
        wx_data = json.load(f)
        
    # Clean up intermediate file
    if generated_json != output_json_path and os.path.exists(generated_json):
        try: os.remove(generated_json)
        except: pass
        
    return wx_data

def align_words_to_chunks(chunk_texts, whisperx_words, total_duration):
    import re
    def normalize(text):
        return [w for w in re.sub(r'[^\w\s]', '', text.lower()).split() if w]
        
    chunk_word_lists = [normalize(t) for t in chunk_texts]
    results = []
    current_idx = 0
    
    for c_idx, c_words in enumerate(chunk_word_lists):
        if not c_words:
            results.append((0.0, 0.0))
            continue
            
        first_match_idx = None
        for i in range(current_idx, len(whisperx_words)):
            if whisperx_words[i].get("word", "").lower() == c_words[0]:
                first_match_idx = i
                break
                
        if first_match_idx is None:
            for i in range(current_idx, len(whisperx_words)):
                if whisperx_words[i].get("word", "").lower() in c_words:
                    first_match_idx = i
                    break
                    
        if first_match_idx is None:
            first_match_idx = current_idx
            
        last_match_idx = first_match_idx
        for i in range(first_match_idx, min(first_match_idx + len(c_words) + 5, len(whisperx_words))):
            w = whisperx_words[i].get("word", "").lower()
            if w in c_words:
                last_match_idx = i
                
        start_time = whisperx_words[first_match_idx].get("start")
        end_time = whisperx_words[last_match_idx].get("end")
        
        if start_time is None:
            start_time = (c_idx / len(chunk_texts)) * total_duration
        if end_time is None:
            end_time = ((c_idx + 1) / len(chunk_texts)) * total_duration
            
        if start_time > end_time:
            start_time, end_time = end_time, start_time
            
        results.append((start_time, end_time))
        current_idx = max(last_match_idx + 1, current_idx + 1)
        
    return results

def process_batch(batch_idx, batch_chunks, tts_dir, speaker_name="en-Frank_man"):
    print(f"\n--- Processing Batch {batch_idx} (phrases {batch_chunks[0][0]}-{batch_chunks[-1][0]}) ---")
    
    # 1. Check if all phrase MP3s already exist
    all_cached = True
    for idx, chunk in batch_chunks:
        mp3_path = os.path.join(tts_dir, f"phrase_{idx}.mp3")
        if not (os.path.exists(mp3_path) and os.path.getsize(mp3_path) > 0):
            all_cached = False
            break
            
    if all_cached:
        print(f"Batch {batch_idx} already cached completely. Skipping.")
        return
        
    # 2. Concatenate text
    prompt_text = " ".join([chunk.get("text", "").strip() for idx, chunk in batch_chunks])
    print(f"Prompt text: '{prompt_text}'")
    
    # Paths
    batch_raw_wav = os.path.join(tts_dir, f"batch_{batch_idx}_raw.wav")
    batch_json_path = os.path.join(tts_dir, f"batch_{batch_idx}_whisper.json")
    win_batch_raw_wav = wsl_to_windows_path(batch_raw_wav)
    
    # 3. Call server
    server_url = "http://127.0.0.1:8001/api/tts"
    max_retries = 3
    for attempt in range(max_retries):
        try:
            payload = {
                "text": prompt_text,
                "speaker": speaker_name,
                "output_path": win_batch_raw_wav
            }
            response = requests.post(server_url, json=payload, timeout=180.0)
            if response.status_code == 200:
                print(f"Successfully generated batch raw WAV: {batch_raw_wav}")
                break
            else:
                raise RuntimeError(f"Server returned status code {response.status_code}: {response.text}")
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            print(f"Server TTS call failed (attempt {attempt+1}/{max_retries}). Retrying... Error: {e}")
            time.sleep(2.0)
            
    if not os.path.exists(batch_raw_wav):
        raise FileNotFoundError(f"Generated raw WAV file not found at: {batch_raw_wav}")
        
    # Load audio to get duration
    batch_audio = AudioSegment.from_wav(batch_raw_wav)
    total_duration = batch_audio.duration_seconds
    print(f"Batch raw audio duration: {total_duration:.2f}s")
    
    # 4. Run WhisperX on raw WAV
    print(f"Running WhisperX on batch raw audio...")
    wx_data = run_whisperx_on_file(batch_raw_wav, batch_json_path)
    
    # Extract words list
    whisperx_words = []
    for seg in wx_data.get("segments", []):
        for w in seg.get("words", []):
            if "start" in w and "end" in w:
                whisperx_words.append(w)
                
    # 5. Align
    chunk_texts = [chunk.get("text", "").strip() for idx, chunk in batch_chunks]
    alignments = align_words_to_chunks(chunk_texts, whisperx_words, total_duration)
    
    # 6. Slice and save
    for (idx, chunk), (start_time, end_time) in zip(batch_chunks, alignments):
        mp3_path = os.path.join(tts_dir, f"phrase_{idx}.mp3")
        
        # Slicing timestamps with small padding (0.05s) to avoid cut phonemes
        start_padded = max(0.0, start_time - 0.05)
        end_padded = min(total_duration, end_time + 0.05)
        
        start_ms = int(start_padded * 1000)
        end_ms = int(end_padded * 1000)
        
        print(f"Slicing phrase {idx}: {start_padded:.2f}s - {end_padded:.2f}s (duration {(end_padded-start_padded):.2f}s)")
        
        phrase_audio = batch_audio[start_ms:end_ms]
        
        # Export
        phrase_audio.export(mp3_path, format="mp3")
        print(f"Successfully generated sliced MP3: {mp3_path}")
        
    # Clean up temp batch files
    if os.path.exists(batch_raw_wav):
        os.remove(batch_raw_wav)
    if os.path.exists(batch_json_path):
        os.remove(batch_json_path)

def test_batch_synthesis():
    task_id = "f61c78a0-24e0-4fee-a5fb-ce1c3296fbf6"
    task_dir = os.path.join(BASE_DIR, "cache", task_id)
    spanish_json = os.path.join(task_dir, "whisper", "spanish_translated.json")
    tts_dir = os.path.join(task_dir, "tts")
    
    print(f"Reading translations from {spanish_json}...")
    with open(spanish_json, "r", encoding="utf-8") as f:
        spanish_data = json.load(f)
        
    chunks = spanish_data.get("chunks", [])
    print(f"Total chunks to synthesize: {len(chunks)}")
    
    # Pair each chunk with its original 0-indexed index
    chunks_with_idx = list(enumerate(chunks))
    
    # Group in batches of 5
    batch_size = 5
    batches = [chunks_with_idx[i:i+batch_size] for i in range(0, len(chunks_with_idx), batch_size)]
    print(f"Total batches to process: {len(batches)}")
    
    # Check if VibeVoice server is running
    server_ready = False
    try:
        resp = requests.get("http://127.0.0.1:8001/openapi.json", timeout=1.0)
        if resp.status_code == 200:
            server_ready = True
    except Exception:
        pass
        
    server_process = None
    if not server_ready:
        server_process = start_vibevoice_server()
        
    try:
        # Process each batch sequentially
        for b_idx, batch in enumerate(batches):
            process_batch(b_idx, batch, tts_dir, speaker_name="en-Frank_man")
    finally:
        if server_process:
            stop_vibevoice_server(server_process)

if __name__ == "__main__":
    test_batch_synthesis()
