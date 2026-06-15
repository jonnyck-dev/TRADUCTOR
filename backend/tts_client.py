import subprocess
import os
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

def start_vibevoice_server() -> subprocess.Popen:
    import time
    import requests
    from whisper_client import wsl_to_windows_path
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    vibevoice_dir = os.path.join(base_dir, "backend", "vibevoice")
    win_vibevoice_dir = wsl_to_windows_path(vibevoice_dir)
    
    if os.name == 'nt':
        python_exe = os.path.join(vibevoice_dir, "env_vibevoice", "Scripts", "python.exe")
        cmd = f'"{python_exe}" vibevoice_server.py'
        cwd = vibevoice_dir
    else:
        python_exe = os.path.join(vibevoice_dir, "env_vibevoice", "Scripts", "python.exe")
        win_python_exe = wsl_to_windows_path(python_exe)
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
    import requests
    print("Stopping VibeVoice server...")
    try:
        resp = requests.post("http://127.0.0.1:8001/shutdown", timeout=2.0)
        print("Shutdown request response:", resp.json())
    except Exception as e:
        print(f"Failed to call shutdown endpoint: {e}")
        if process:
            try:
                process.terminate()
                process.wait(timeout=2)
                print("Subprocess terminated.")
            except Exception as pe:
                print(f"Failed to terminate subprocess: {pe}")

def generate_individual_tts(chunks: list, tts_dir: str, speaker_name: str = "en-Frank_man", task_id: str = None) -> list:
    """
    Generates individual MP3 files for each translated chunk using VibeVoice TTS.
    Parallelized to use multiple threads, speeding up the process on powerful GPUs.
    Returns a list of absolute paths to the generated MP3 files.
    """
    os.makedirs(tts_dir, exist_ok=True)
    
    # Project base directory
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    vibevoice_dir = os.path.join(base_dir, "backend", "vibevoice")
    
    # Pre-allocate mp3_paths list with Nones
    mp3_paths = [None] * len(chunks)
    
    # ponytail: server URL and use_server flag determined at function scope
    server_url = "http://127.0.0.1:8001/api/tts"
    use_server = False
    
    # We will use a thread pool to run generation in parallel.
    # We use max_workers=2 to limit the resource load and prevent freezing the user's PC.
    from concurrent.futures import ThreadPoolExecutor
    
    def process_chunk(idx, chunk):
        if task_id and task_id in cancelled_tasks:
            raise RuntimeError(f"Task {task_id} stopped by user.")
            
        text = chunk.get("text", "").strip()
        mp3_path = os.path.join(tts_dir, f"phrase_{idx}.mp3")
        
        if not text:
            return idx, None
            
        # Check cache
        if os.path.exists(mp3_path) and os.path.getsize(mp3_path) > 0:
            print(f"Skipping VibeVoice generation for phrase {idx}, using cached MP3: {mp3_path}")
            return idx, mp3_path
            
        # ponytail: read use_server from parent scope instead of pinging per-chunk
        local_use_server = use_server
            
        generated_wav = os.path.join(tts_dir, f"phrase_{idx}_generated.wav")
        phrase_txt_path = os.path.join(tts_dir, f"phrase_{idx}.txt")
        
        if task_id and task_id in cancelled_tasks:
            raise RuntimeError(f"Task {task_id} stopped by user.")
            
        if speaker_name == "windows_native":
            # ponytail: use PowerShell native Speech Synthesizer for instant robotic TTS
            print(f"Using Windows native Speech Synthesizer for phrase {idx}/{len(chunks)-1}")
            try:
                clean_text = text.replace('"', "'").replace("\n", " ").strip()
                ps_text = clean_text.replace("'", "''")
                win_output_wav = wsl_to_windows_path(generated_wav)
                ps_cmd = f"Add-Type -AssemblyName System.Speech; $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; $synth.SetOutputToWaveFile('{win_output_wav}'); $synth.Speak('{ps_text}'); $synth.Dispose()"
                result = subprocess.run(
                    ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
                    stdin=subprocess.DEVNULL,
                    capture_output=True,
                    text=True
                )
                if result.returncode != 0:
                    raise RuntimeError(f"Windows Native TTS command failed: {result.stderr}")
            except Exception as e:
                print(f"Error in Windows Native TTS for phrase {idx}: {e}")
                raise e
        else:
            if local_use_server:
                print(f"Using persistent VibeVoice server for phrase {idx}/{len(chunks)-1}")
                try:
                    import requests
                    win_output_wav = wsl_to_windows_path(generated_wav)
                    payload = {
                        "text": text,
                        "speaker": speaker_name,
                        "output_path": win_output_wav
                    }
                    response = requests.post(server_url, json=payload, timeout=60)
                    if response.status_code != 200:
                        raise RuntimeError(f"Server TTS failed: {response.text}")
                except Exception as e:
                    print(f"Server TTS call failed for phrase {idx}, falling back to subprocess: {e}")
                    local_use_server = False
                    
            if not local_use_server:
                if task_id and task_id in cancelled_tasks:
                    raise RuntimeError(f"Task {task_id} stopped by user.")
                    
                # Write phrase script file
                with open(phrase_txt_path, "w", encoding="utf-8") as f:
                    f.write(f"Speaker 1: {text}\n")
                    
                win_txt_path = wsl_to_windows_path(phrase_txt_path)
                win_output_dir = wsl_to_windows_path(tts_dir)
                
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
                    win_vibevoice_dir = wsl_to_windows_path(vibevoice_dir)
                    python_exe = os.path.join(vibevoice_dir, "env_vibevoice", "Scripts", "python.exe")
                    win_python_exe = wsl_to_windows_path(python_exe)
                    cmd = (
                        f'cmd.exe /c "cd /d {win_vibevoice_dir} && '
                        f'"{win_python_exe}" demo/inference_from_file.py --model_path \\"{win_vibevoice_dir}\\checkpoints\\VibeVoice-1.5B\\" '
                        f'--speaker_names \\"{speaker_name}\\" --device cuda --txt_path \\"{win_txt_path}\\" '
                        f'--output_dir \\"{win_output_dir}\\"" < /dev/null'
                    )
                    cwd = "/mnt/c"
                    
                print(f"Executing VibeVoice command for phrase {idx}/{len(chunks)-1}: {cmd}")
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd)
                
                if result.returncode != 0:
                    print(f"VibeVoice stdout: {result.stdout}")
                    print(f"VibeVoice stderr: {result.stderr}")
                    raise RuntimeError(f"VibeVoice TTS failed on phrase {idx} with exit code {result.returncode}")
            
        if task_id and task_id in cancelled_tasks:
            raise RuntimeError(f"Task {task_id} stopped by user.")
            
        # Convert WAV to MP3 using pydub
        try:
            audio_segment = AudioSegment.from_wav(generated_wav)
            audio_segment.export(mp3_path, format="mp3")
            print(f"Successfully generated and cached: {mp3_path}")
        except Exception as e:
            print(f"Failed to convert WAV to MP3 for phrase {idx}: {e}")
            if os.path.exists(mp3_path):
                try: os.remove(mp3_path)
                except: pass
            raise e
        finally:
            # Clean up intermediate files (.txt and .wav)
            if os.path.exists(phrase_txt_path):
                try: os.remove(phrase_txt_path)
                except: pass
            if os.path.exists(generated_wav):
                try: os.remove(generated_wav)
                except: pass
                
        return idx, mp3_path

    # Check if there are any chunks that actually need generation
    needs_generation = False
    for idx, chunk in enumerate(chunks):
        text = chunk.get("text", "").strip()
        mp3_path = os.path.join(tts_dir, f"phrase_{idx}.mp3")
        if text and not (os.path.exists(mp3_path) and os.path.getsize(mp3_path) > 0):
            needs_generation = True
            break

    server_process = None
    # ponytail: do not start VibeVoice server if we are using native Windows TTS
    if needs_generation and speaker_name != "windows_native":
        server_process = start_vibevoice_server()
        try:
            import requests
            resp = requests.get("http://127.0.0.1:8001/openapi.json", timeout=1.0)
            if resp.status_code == 200:
                use_server = True
        except Exception:
            pass

    try:
        # Run tasks with ThreadPoolExecutor
        print(f"Starting parallel VibeVoice generation with 2 workers for {len(chunks)} chunks...")
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(process_chunk, i, chunk) for i, chunk in enumerate(chunks)]
            for fut in futures:
                try:
                    idx, mp3_path = fut.result()
                    mp3_paths[idx] = mp3_path
                except Exception as e:
                    print(f"Error in parallel VibeVoice chunk execution: {e}")
                    # Cancel any pending futures to prevent more threads starting
                    for f in futures:
                        f.cancel()
                    raise e
    finally:
        if server_process:
            stop_vibevoice_server(server_process)
                
    return mp3_paths

def generate_tts(chunks: list, output_dir: str, speaker_name: str = "en-Frank_man") -> str:
    """
    Deprecated: Backward compatible function. Replaced by generate_individual_tts + sync_individual_phrases.
    Concatenates individual phrases to simulate the old output behavior if needed.
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

