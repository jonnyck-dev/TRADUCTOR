import subprocess
import os
import time
import requests
import queue
from concurrent.futures import ThreadPoolExecutor
from pydub import AudioSegment
from whisper_client import wsl_to_windows_path

cancelled_tasks = set()

def cancel_task(task_id: str):
    if task_id:
        cancelled_tasks.add(task_id)
        print(f"Added task {task_id} to cancelled_tasks set in tts_client")

def remove_cancelled_task(task_id: str):
    if task_id in cancelled_tasks:
        cancelled_tasks.remove(task_id)
        print(f"Removed task {task_id} from cancelled_tasks set in tts_client")

def start_tts_server(model_name_or_path: str = None, port: int = 8001, engine: str = "voxcpm") -> subprocess.Popen:
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    if engine == "vibevoice":
        code_dir = os.path.join(base_dir, "backend", "vibevoice")
        server_script = "vibevoice_server.py"
        venv_name = "env_vibevoice"
        model_arg = f" --model_path checkpoints\\{model_name_or_path}" if model_name_or_path else ""
    else:  # voxcpm
        code_dir = os.path.join(base_dir, "backend", "VoxCPM")
        server_script = "voxcpm_server.py"
        venv_name = "env_voxcpm"
        if model_name_or_path:
            model_arg = f" --model_path {model_name_or_path}"
        else:
            model_arg = " --model_path openbmb/VoxCPM2"
            
    win_code_dir = wsl_to_windows_path(code_dir)
    port_arg = f" --port {port}"
    python_exe = os.path.join(code_dir, venv_name, "Scripts", "python.exe")
    
    if os.name == 'nt':
        cmd = f'"{python_exe}" {server_script}{model_arg}{port_arg}'
        cwd = code_dir
    else:
        win_python_exe = wsl_to_windows_path(python_exe)
        cmd = f'cmd.exe /c "cd /d {win_code_dir} && "{win_python_exe}" {server_script}{model_arg}{port_arg}" < /dev/null'
        cwd = "/mnt/c"
        
    print(f"Starting {engine.upper()} TTS server dynamically on port {port} with command: {cmd}")
    process = subprocess.Popen(cmd, shell=True, cwd=cwd)
    
    print(f"Waiting for {engine.upper()} TTS server to start and load model...")
    ready_ports = set()
    start_time = time.time()
    
    while time.time() - start_time < 120:  # Allow up to 120s for 2B model loading
        try:
            resp = requests.get(f"http://127.0.0.1:{port}/openapi.json", timeout=1.0)
            if resp.status_code == 200:
                print(f"{engine.upper()} TTS server on port {port} is ready! (took {time.time() - start_time:.2f}s)")
                ready_ports.add(port)
                break
        except Exception:
            pass
        time.sleep(2.0)
        
    if port not in ready_ports:
        print(f"Warning: {engine.upper()} TTS server on port {port} did not respond in time.")
        
    return process

def stop_tts_server(process=None, port: int = 8001):
    print(f"Stopping TTS server on port {port}...")
    try:
        resp = requests.post(f"http://127.0.0.1:{port}/shutdown", timeout=2.0)
        print(f"Shutdown request response for port {port}:", resp.json())
    except Exception as e:
        print(f"Failed to call shutdown endpoint on port {port}: {e}")
        
    # Force kill any process listening on port to prevent VRAM leaks
    if os.name == 'nt':
        try:
            res = subprocess.run("netstat -ano", capture_output=True, text=True, shell=True)
            for line in res.stdout.splitlines():
                if f":{port}" in line and "LISTENING" in line:
                    parts = line.strip().split()
                    if len(parts) >= 5:
                        pid = parts[-1]
                        print(f"Force-killing TTS server process PID {pid} on port {port}...")
                        subprocess.run(f"taskkill /f /pid {pid}", shell=True, capture_output=True)
        except Exception as ke:
            print(f"Error force-killing process on port {port}: {ke}")
    else:
        try:
            res = subprocess.run(f"lsof -t -i:{port}", capture_output=True, text=True, shell=True)
            pid = res.stdout.strip()
            if pid:
                print(f"Force-killing TTS server process PID {pid} on port {port}...")
                subprocess.run(f"kill -9 {pid}", shell=True)
        except Exception as ke:
            print(f"Error force-killing process on port {port}: {ke}")

    if process:
        try:
            process.terminate()
            process.wait(timeout=2)
            print("Subprocess terminated.")
        except Exception as pe:
            print(f"Failed to terminate subprocess: {pe}")

# --- Legacy Compatibility Wrappers ---
def start_vibevoice_servers(model_name_or_path: str = None, num_workers: int = 1) -> list:
    return [start_tts_server(model_name_or_path, port=8001, engine="vibevoice")]

def stop_vibevoice_servers(processes=None, num_workers=1):
    stop_tts_server(processes[0] if processes else None, port=8001)

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
                
        start_time = None
        end_time = None
        
        if whisperx_words and 0 <= first_match_idx < len(whisperx_words):
            start_time = whisperx_words[first_match_idx].get("start")
        if whisperx_words and 0 <= last_match_idx < len(whisperx_words):
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

def generate_individual_tts(chunks: list, tts_dir: str, speaker_name: str = "en-Frank_man", task_id: str = None, tts_model: str = None, tts_cfg: float = 1.3, tts_steps: int = 10) -> list:
    """
    Generates individual MP3 files for each translated chunk using TTS (VoxCPM or VibeVoice).
    Returns a list of absolute paths to the generated MP3 files.
    """
    os.makedirs(tts_dir, exist_ok=True)
    mp3_paths = [os.path.join(tts_dir, f"phrase_{i}.mp3") for i in range(len(chunks))]
    
    # 1. Handle Windows native TTS (individual execution, since it's already fast)
    if speaker_name == "windows_native":
        for idx, chunk in enumerate(chunks):
            if task_id and task_id in cancelled_tasks:
                raise RuntimeError(f"Task {task_id} stopped by user.")
            text = chunk.get("text", "").strip()
            mp3_path = mp3_paths[idx]
            if not text:
                continue
            if os.path.exists(mp3_path) and os.path.getsize(mp3_path) > 0:
                continue
            
            print(f"Using Windows native Speech Synthesizer for phrase {idx}/{len(chunks)-1}")
            generated_wav = os.path.join(tts_dir, f"phrase_{idx}_generated.wav")
            try:
                clean_text = text.replace('"', "'").replace("\n", " ").strip()
                ps_text = clean_text.replace("'", "''")
                win_output_wav = wsl_to_windows_path(generated_wav)
                ps_cmd = (
                    "Add-Type -AssemblyName System.Speech; "
                    "$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                    "$voice = $synth.GetInstalledVoices() | ForEach-Object { $_.VoiceInfo } | Where-Object { $_.Culture.Name -like 'es-*' } | Select-Object -First 1; "
                    "if ($voice) { $synth.SelectVoice($voice.Name) }; "
                    f"$synth.SetOutputToWaveFile('{win_output_wav}'); "
                    f"$synth.Speak('{ps_text}'); "
                    "$synth.Dispose()"
                )
                result = subprocess.run(
                    ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
                    stdin=subprocess.DEVNULL,
                    capture_output=True,
                    text=True
                )
                if result.returncode != 0:
                    raise RuntimeError(f"Windows Native TTS command failed: {result.stderr}")
                
                # Convert to MP3
                audio_segment = AudioSegment.from_wav(generated_wav)
                audio_segment.export(mp3_path, format="mp3")
            except Exception as e:
                print(f"Error in Windows Native TTS for phrase {idx}: {e}")
                raise e
            finally:
                if os.path.exists(generated_wav):
                    try: os.remove(generated_wav)
                    except: pass
        return mp3_paths

    # 2. Determine TTS Engine (VoxCPM or VibeVoice)
    model_name = tts_model or "openbmb/VoxCPM2"
    engine = "vibevoice"
    if "vox" in model_name.lower() or "cpm" in model_name.lower() or "openbmb" in model_name.lower():
        engine = "voxcpm"
        
    # Filter chunks that actually need generation
    chunks_to_generate = []
    for idx, chunk in enumerate(chunks):
        text = chunk.get("text", "").strip()
        mp3_path = mp3_paths[idx]
        if text and not (os.path.exists(mp3_path) and os.path.getsize(mp3_path) > 0):
            chunks_to_generate.append((idx, chunk))
            
    needs_generation = len(chunks_to_generate) > 0
    server_processes = []
    use_server = False
    
    # Determine parallel workers:
    # VoxCPM always uses 1 instance for base testing (single-threaded).
    # VibeVoice 0.5B uses 3 workers, VibeVoice 1.5B uses 1 worker.
    if engine == "voxcpm":
        num_workers = 3 if "0.5b" in model_name.lower() else 1
    else:
        num_workers = 3 if "0.5b" in model_name.lower() else 1
        
    print(f"Using {num_workers} parallel {engine.upper()} server instances for model: {model_name}")
    
    if needs_generation:
        # Start persistent server instances
        ports = [8001 + i for i in range(num_workers)]
        for port in ports:
            p = start_tts_server(model_name, port=port, engine=engine)
            server_processes.append(p)
            
        # Verify the primary server is alive
        try:
            resp = requests.get("http://127.0.0.1:8001/openapi.json", timeout=1.0)
            if resp.status_code == 200:
                use_server = True
        except Exception:
            pass
            
    if needs_generation and not use_server:
        raise RuntimeError(f"{engine.upper()} persistent servers did not start successfully. Aborting pipeline.")
        
    try:
        # Setup workers queue
        port_queue = queue.Queue()
        for i in range(num_workers):
            port_queue.put(8001 + i)
            
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # Resolve the generic cloned_speaker WAV path on Windows
        cloned_wav_path = os.path.join(base_dir, "backend", "cloned_speaker.wav")
        win_cloned_wav_path = wsl_to_windows_path(cloned_wav_path)
            
        def process_single_chunk(item):
            idx, chunk = item
            if task_id and task_id in cancelled_tasks:
                raise RuntimeError(f"Task {task_id} stopped by user.")
                
            text = chunk.get("text", "").strip()
            mp3_path = mp3_paths[idx]
            
            temp_wav = os.path.join(tts_dir, f"phrase_{idx}_raw.wav")
            win_temp_wav = wsl_to_windows_path(temp_wav)
            
            port = port_queue.get()
            server_url = f"http://127.0.0.1:{port}/api/tts"
            
            print(f"Generating {engine.upper()} TTS on port {port} for phrase {idx}/{len(chunks)-1}: '{text[:40]}...'")
            
            try:
                max_retries = 3
                for attempt in range(max_retries):
                    if task_id and task_id in cancelled_tasks:
                        raise RuntimeError(f"Task {task_id} stopped by user.")
                    try:
                        # Construct payload based on engine
                        if engine == "voxcpm":
                            payload = {
                                "text": text,
                                "speaker": speaker_name,
                                "output_path": win_temp_wav,
                                "cfg_value": tts_cfg,
                                "inference_timesteps": tts_steps,
                                "reference_wav_path": win_cloned_wav_path if speaker_name == "cloned_speaker" else None,
                                "normalize": False
                            }
                        else:  # vibevoice
                            payload = {
                                "text": text,
                                "speaker": speaker_name,
                                "output_path": win_temp_wav,
                                "cfg_scale": tts_cfg,
                                "ddpm_steps": tts_steps
                            }
                        
                        response = requests.post(server_url, json=payload, timeout=None)
                        if response.status_code == 200:
                            break
                        else:
                            raise RuntimeError(f"Server on port {port} returned status code {response.status_code}: {response.text}")
                    except Exception as e:
                        if attempt == max_retries - 1:
                            raise e
                        print(f"Server TTS call on port {port} failed (attempt {attempt+1}/{max_retries}). Retrying... Error: {e}")
                        time.sleep(2.0)
                        
                if not os.path.exists(temp_wav):
                    raise FileNotFoundError(f"Generated raw WAV file not found at: {temp_wav}")
                    
                # Convert WAV to MP3 using pydub
                try:
                    audio_segment = AudioSegment.from_wav(temp_wav)
                    audio_segment.export(mp3_path, format="mp3")
                    print(f"Successfully generated and saved phrase {idx} MP3: {mp3_path}")
                except Exception as e:
                    print(f"Error converting phrase {idx} WAV to MP3: {e}")
                    raise e
                finally:
                    if os.path.exists(temp_wav):
                        try: os.remove(temp_wav)
                        except: pass
            finally:
                port_queue.put(port)
                    
        # Process chunks (either sequentially for voxcpm/single worker, or in parallel for multiple workers)
        if chunks_to_generate:
            print(f"\nStarting TTS generation for {len(chunks_to_generate)} phrases...")
            with ThreadPoolExecutor(max_workers=num_workers) as executor:
                list(executor.map(process_single_chunk, chunks_to_generate))
                
    finally:
        if server_processes:
            for i, p in enumerate(server_processes):
                stop_tts_server(p, port=8001 + i)
            
    return [os.path.join(tts_dir, f"phrase_{i}.mp3") if chunks[i].get("text", "").strip() else None for i in range(len(chunks))]

def generate_tts(chunks: list, output_dir: str, speaker_name: str = "en-Frank_man") -> str:
    """
    Deprecated: Backward compatible function.
    """
    tts_dir = os.path.join(output_dir, "tts")
    mp3_paths = generate_individual_tts(chunks, tts_dir, speaker_name)
    
    combined = None
    silence_seg = AudioSegment.silent(duration=100, frame_rate=24000)
    
    for mp3_path in mp3_paths:
        if mp3_path and os.path.exists(mp3_path):
            seg = AudioSegment.from_file(mp3_path)
            if combined is None:
                combined = seg
            else:
                combined = combined + silence_seg + seg
                
    expected_wav = os.path.join(output_dir, "script_generated.wav")
    if combined is not None:
        combined.export(expected_wav, format="wav")
    else:
        raise ValueError("No audio segments generated.")
        
    return expected_wav
