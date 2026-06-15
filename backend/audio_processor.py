import os
import subprocess
from pydub import AudioSegment

def get_ffmpeg_cmd() -> str:
    if os.name == 'nt':
        return r'"C:\Users\jpzam\Downloads\audioconverter\bin\ffmpeg.exe"'
    return 'ffmpeg'

def get_flat_timestamp(timestamp) -> list:
    """
    Ensures the timestamp is a flat list of [start, end] floats.
    Handles nested list structures defensively.
    """
    if not timestamp:
        return [0.0, 0.0]
    
    # If it's a list/tuple
    if isinstance(timestamp, (list, tuple)):
        # If the first element is also a list/tuple (nested)
        if len(timestamp) > 0 and isinstance(timestamp[0], (list, tuple)):
            # Find the first valid float start
            start = 0.0
            for item in timestamp:
                if isinstance(item, (list, tuple)) and len(item) > 0:
                    start = item[0]
                    break
                elif isinstance(item, (int, float)):
                    start = item
                    break
            
            # Find the last valid float end
            end = 0.0
            for item in reversed(timestamp):
                if isinstance(item, (list, tuple)) and len(item) > 1:
                    end = item[1]
                    break
                elif isinstance(item, (int, float)):
                    end = item
                    break
            return [float(start), float(end)]
        
        # If it's a flat list of floats/ints
        if len(timestamp) >= 2:
            try:
                return [float(timestamp[0]), float(timestamp[1])]
            except (ValueError, TypeError):
                pass
                
    return [0.0, 0.0]

def stretch_audio_segment(input_wav: str, output_wav: str, factor: float):
    """
    Time-stretches a WAV file using ffmpeg's high-quality atempo filter.
    factor > 1.0 speeds it up (shortens duration).
    factor < 1.0 slows it down (lengthens duration).
    """
    if factor < 0.5:
        filter_str = "atempo=0.5"
    elif factor > 2.0:
        # Chain two atempo filters to achieve speedup > 2.0 (clamped at 4.0)
        clamped_factor = min(factor, 4.0)
        filter_str = f"atempo=2.0,atempo={clamped_factor / 2.0}"
    else:
        filter_str = f"atempo={factor}"
        
    ffmpeg = get_ffmpeg_cmd()
    cmd = f'{ffmpeg} -y -i "{input_wav}" -filter:a "{filter_str}" -vn "{output_wav}"'
    subprocess.run(cmd, shell=True, capture_output=True)

def get_word_list(chunks: list) -> list:
    """
    Flattens chunk segment text into a list of words with estimated or actual timestamps.
    """
    words = []
    for chunk in chunks:
        # Check if we have actual word-level timestamps from WhisperX
        if "words" in chunk and chunk["words"]:
            use_real_words = True
            for w_info in chunk["words"]:
                if not isinstance(w_info, dict) or "start" not in w_info or "end" not in w_info:
                    use_real_words = False
                    break
            if use_real_words:
                for w_info in chunk["words"]:
                    w_text = w_info.get("word", "")
                    w_norm = "".join(c for c in w_text.lower() if c.isalnum())
                    w_start = w_info.get("start")
                    w_end = w_info.get("end")
                    if w_start is not None and w_end is not None and w_norm:
                        words.append({
                            "word": w_norm,
                            "start": w_start,
                            "end": w_end
                        })
                continue

        # Fallback: estimate word timestamps linearly based on segment duration
        ts = get_flat_timestamp(chunk.get("timestamp"))
        text = chunk.get("text", "")
        if not ts or len(ts) < 2 or not text:
            continue
        t_start, t_end = ts[0], ts[1]
        chunk_words = text.strip().split()
        if not chunk_words:
            continue
        
        duration = t_end - t_start
        word_dur = duration / len(chunk_words)
        
        for idx, w in enumerate(chunk_words):
            w_norm = "".join(c for c in w.lower() if c.isalnum())
            if w_norm:
                words.append({
                    "word": w_norm,
                    "start": t_start + idx * word_dur,
                    "end": t_start + (idx + 1) * word_dur
                })
    return words

def align_transcripts(original_chunks: list, dubbed_chunks: list, total_dub_duration: float) -> list:
    """
    Aligns translated segments with continuous dubbed audio using word-level alignment.
    Falls back to proportional mapping if word alignment fails.
    """
    alignment = []
    
    original_words = get_word_list(original_chunks)
    dubbed_words = get_word_list(dubbed_chunks)
    
    # If either list is empty, use proportional mapping fallback
    if not original_words or not dubbed_words:
        print("Alignment: Word lists empty. Using proportional mapping fallback.")
        return get_proportional_alignment(original_chunks, total_dub_duration)
        
    # Sequential matching pointer
    dub_ptr = 0
    
    # Calculate total original duration for fallback ratio
    total_orig_duration = 0.0
    if original_chunks:
        total_orig_duration = get_flat_timestamp(original_chunks[-1].get("timestamp", [0, 0]))[1]
    if total_orig_duration == 0:
        total_orig_duration = 1.0
        
    for chunk in original_chunks:
        ts = get_flat_timestamp(chunk.get("timestamp"))
        text = chunk.get("text", "")
        if not ts or len(ts) < 2:
            continue
        orig_start, orig_end = ts[0], ts[1]
        
        if not text.strip():
            # Silent chunk
            alignment.append({
                "orig_start": orig_start,
                "orig_end": orig_end,
                "dub_start": 0.0,
                "dub_end": 0.0,
                "text": text,
                "is_silent": True
            })
            continue
            
        chunk_words = [c for c in ("".join(char for char in w.lower() if char.isalnum()) for w in text.strip().split()) if c]
        if not chunk_words:
            alignment.append({
                "orig_start": orig_start,
                "orig_end": orig_end,
                "dub_start": 0.0,
                "dub_end": 0.0,
                "text": text,
                "is_silent": True
            })
            continue
            
        # Match words in dubbed audio
        # We look for the start and end of this block of words in dubbed_words
        match_start_time = None
        match_end_time = None
        
        if dub_ptr >= len(dubbed_words):
            # Proportional mapping fallback when we run out of dubbed words
            ratio = total_dub_duration / total_orig_duration
            match_start_time = orig_start * ratio
            match_end_time = orig_end * ratio
        else:
            # Simple sliding window search for the best word block match
            best_dub_start_idx = dub_ptr
            # We scan a small window forward to find the first matching word
            for offset in range(min(10, len(dubbed_words) - dub_ptr)):
                candidate_idx = dub_ptr + offset
                if dubbed_words[candidate_idx]["word"] == chunk_words[0]:
                    best_dub_start_idx = candidate_idx
                    break
                    
            if best_dub_start_idx >= len(dubbed_words):
                best_dub_start_idx = len(dubbed_words) - 1
                
            # Set start timestamp
            match_start_time = dubbed_words[best_dub_start_idx]["start"]
            
            # Advance pointer to end of this segment
            target_end_idx = min(best_dub_start_idx + len(chunk_words) - 1, len(dubbed_words) - 1)
            match_end_time = dubbed_words[target_end_idx]["end"]
            
            # Update the pointer for next iterations
            dub_ptr = target_end_idx + 1
        
        alignment.append({
            "orig_start": orig_start,
            "orig_end": orig_end,
            "dub_start": match_start_time,
            "dub_end": match_end_time,
            "text": text,
            "is_silent": False
        })
        
    return alignment

def get_proportional_alignment(original_chunks: list, total_dub_duration: float) -> list:
    if not original_chunks:
        return []
    # Calculate original duration
    last_chunk = original_chunks[-1]
    total_orig_duration = get_flat_timestamp(last_chunk.get("timestamp", [0, 0]))[1]
    if total_orig_duration == 0:
        total_orig_duration = 1.0
        
    ratio = total_dub_duration / total_orig_duration
    
    alignment = []
    for chunk in original_chunks:
        ts = get_flat_timestamp(chunk.get("timestamp"))
        text = chunk.get("text", "")
        if not ts or len(ts) < 2:
            continue
        orig_start, orig_end = ts[0], ts[1]
        
        alignment.append({
            "orig_start": orig_start,
            "orig_end": orig_end,
            "dub_start": orig_start * ratio,
            "dub_end": orig_end * ratio,
            "text": text,
            "is_silent": not text.strip()
        })
    return alignment

def create_synchronized_audio(alignment: list, dubbed_wav_path: str, output_wav_path: str, total_duration_sec: float) -> str:
    """
    Slices segments from the continuous VibeVoice WAV file, stretches them,
    and overlays them onto a silent background track at the correct timestamps.
    """
    dub_audio = AudioSegment.from_wav(dubbed_wav_path)
    
    # Create a silent audio track of the original duration
    total_duration_ms = int(total_duration_sec * 1000)
    synchronized_audio = AudioSegment.silent(duration=total_duration_ms, frame_rate=24000)
    
    # Directory to store temp segments
    temp_dir = os.path.join(os.path.dirname(output_wav_path), "temp_segments")
    os.makedirs(temp_dir, exist_ok=True)
    
    for idx, item in enumerate(alignment):
        if item.get("is_silent", False):
            continue
            
        orig_start_ms = int(item["orig_start"] * 1000)
        orig_end_ms = int(item["orig_end"] * 1000)
        orig_duration_ms = orig_end_ms - orig_start_ms
        
        dub_start_ms = int(item["dub_start"] * 1000)
        dub_end_ms = int(item["dub_end"] * 1000)
        dub_duration_ms = dub_end_ms - dub_start_ms
        
        if dub_duration_ms <= 0 or orig_duration_ms <= 0:
            continue
            
        # Slice the segment from the dubbed audio file
        segment_audio = dub_audio[dub_start_ms:dub_end_ms]
        
        temp_input = os.path.join(temp_dir, f"seg_{idx}_in.wav")
        temp_output = os.path.join(temp_dir, f"seg_{idx}_out.wav")
        
        segment_audio.export(temp_input, format="wav")
        
        # Calculate speed factor
        # If we need it to fit in orig_duration_ms, we adjust playback rate
        factor = dub_duration_ms / orig_duration_ms
        
        try:
            stretch_audio_segment(temp_input, temp_output, factor)
            if os.path.exists(temp_output):
                stretched_segment = AudioSegment.from_wav(temp_output)
            else:
                stretched_segment = segment_audio
        except Exception as e:
            print(f"Stretching failed for segment {idx}: {e}")
            stretched_segment = segment_audio
            
        # Clean up temp files
        if os.path.exists(temp_input):
            os.remove(temp_input)
        if os.path.exists(temp_output):
            os.remove(temp_output)
            
        # Overlay onto the synchronized track
        synchronized_audio = synchronized_audio.overlay(stretched_segment, position=orig_start_ms)
        
    # Clean up temp directory
    try:
        os.rmdir(temp_dir)
    except Exception:
        pass
        
    synchronized_audio.export(output_wav_path, format="wav")
    return output_wav_path

def merge_audio_video(video_path: str, audio_path: str, output_video_path: str) -> str:
    """
    Merges the dubbed audio track back into the video file, muting the original audio.
    """
    ffmpeg = get_ffmpeg_cmd()
    cmd = (
        f'{ffmpeg} -y -i "{video_path}" -i "{audio_path}" '
        f'-c:v copy -map 0:v:0 -map 1:a:0 -c:a aac -shortest "{output_video_path}"'
    )
    print(f"Merging video and audio: {cmd}")
    subprocess.run(cmd, shell=True, capture_output=True)
    return output_video_path

def sync_individual_phrases(chunks: list, mp3_paths: list, output_wav_path: str, total_duration_sec: float) -> str:
    """
    Overlays individual phrase MP3 files onto a silent audio track at their original start times.
    Uses a Silence Debt Compensation algorithm to dynamically absorb overlaps into future silent moments,
    preventing aggressive slowdowns and extreme speedups.
    """
    total_duration_ms = int(total_duration_sec * 1000)
    # 24kHz Mono is best for Whisper & VibeVoice
    synchronized_audio = AudioSegment.silent(duration=total_duration_ms, frame_rate=24000)
    
    temp_dir = os.path.join(os.path.dirname(output_wav_path), "temp_sync_segments")
    os.makedirs(temp_dir, exist_ok=True)
    
    silence_debt = 0.0  # seconds
    
    for idx, (chunk, mp3_path) in enumerate(zip(chunks, mp3_paths)):
        if not mp3_path or not os.path.exists(mp3_path):
            continue
            
        ts = get_flat_timestamp(chunk.get("timestamp", [0.0, 0.0]))
        orig_start = ts[0]
        orig_end = ts[1]
        orig_duration = orig_end - orig_start
        
        # Calculate target start time (taking silence debt into account)
        target_start = orig_start + silence_debt
        target_start_ms = int(target_start * 1000)
        
        # Determine the next non-silent segment's original start time
        next_orig_start = total_duration_sec
        for j in range(idx + 1, len(chunks)):
            if chunks[j].get("text", "").strip() and mp3_paths[j] is not None:
                next_ts = get_flat_timestamp(chunks[j].get("timestamp", [0.0, 0.0]))
                next_orig_start = next_ts[0]
                break
                
        # Load the generated TTS audio
        try:
            audio_segment = AudioSegment.from_file(mp3_path)
            dub_duration = audio_segment.duration_seconds
        except Exception as e:
            print(f"Error loading MP3 for chunk {idx}: {e}")
            continue
            
        # 1. Calculate ideal speed factor to fit its original segment duration
        if orig_duration > 0:
            ideal_factor = dub_duration / orig_duration
        else:
            ideal_factor = 1.0
            
        # 2. Adjust maximum allowed speed depending on accumulated silence debt.
        # If the debt is high, we allow slightly more acceleration to catch up.
        max_speed = 1.3
        if silence_debt > 2.0:
            max_speed = 1.5
        elif silence_debt > 4.0:
            max_speed = 1.8
            
        # We clamp the speed factor to avoid extreme slowmotion (min 0.9) and extreme speedup (max_speed)
        factor = max(0.9, min(ideal_factor, max_speed))
        
        # Calculate effective duration after stretching
        effective_duration = dub_duration / factor
        effective_end = target_start + effective_duration
        
        # 3. Calculate new silence debt based on overlap with next segment
        if effective_end > next_orig_start:
            # We invaded the next segment's timeline. Accumulate the debt.
            new_silence_debt = effective_end - next_orig_start
        else:
            # Silence future segment absorbed the debt. Reset debt.
            new_silence_debt = 0.0
            
        silence_debt = new_silence_debt
        
        # Apply time stretching if factor is not 1.0 (with a small margin)
        if abs(factor - 1.0) > 0.02:
            temp_input = os.path.join(temp_dir, f"seg_{idx}_in.wav")
            temp_output = os.path.join(temp_dir, f"seg_{idx}_out.wav")
            
            try:
                audio_segment.export(temp_input, format="wav")
                stretch_audio_segment(temp_input, temp_output, factor)
                if os.path.exists(temp_output):
                    stretched_segment = AudioSegment.from_wav(temp_output)
                    print(f"Chunk {idx} (orig {orig_start:.2f}s-{orig_end:.2f}s, tts {dub_duration:.2f}s) "
                          f"stretched by {factor:.2f}x. Placement: {target_start:.2f}s-{effective_end:.2f}s. Silence debt: {silence_debt:.2f}s")
                else:
                    stretched_segment = audio_segment
            except Exception as e:
                print(f"Stretching failed for chunk {idx}: {e}")
                stretched_segment = audio_segment
            finally:
                if os.path.exists(temp_input):
                    try: os.remove(temp_input)
                    except: pass
                if os.path.exists(temp_output):
                    try: os.remove(temp_output)
                    except: pass
        else:
            stretched_segment = audio_segment
            print(f"Chunk {idx} (orig {orig_start:.2f}s-{orig_end:.2f}s, tts {dub_duration:.2f}s) "
                  f"kept at 1.0x. Placement: {target_start:.2f}s-{effective_end:.2f}s. Silence debt: {silence_debt:.2f}s")
            
        # Overlay onto the synchronized track
        synchronized_audio = synchronized_audio.overlay(stretched_segment, position=target_start_ms)
        
    # Clean up temp directory
    try:
        if os.path.exists(temp_dir):
            for f in os.listdir(temp_dir):
                os.remove(os.path.join(temp_dir, f))
            os.rmdir(temp_dir)
    except Exception as e:
        print(f"Failed to clean up temp dir {temp_dir}: {e}")
        
    synchronized_audio.export(output_wav_path, format="wav")
    return output_wav_path

def run_demucs_separation(audio_path: str, output_dir: str) -> tuple[str, str]:
    """
    Runs Demucs separation on the given audio file using the UVR5-UI python environment.
    If UVR5-UI is not found or fails, falls back to returning (audio_path, None).
    """
    import os
    import subprocess
    import shutil
    import ast
    from whisper_client import wsl_to_windows_path
    
    # Path to UVR5-UI
    uvr5_dir = "/mnt/d/documentos/descargas/Audio/IA/AUDIO ANALIZER/separacion de audio/UVR5-UI-v1.8.4/UVR5-UI"
    python_exe = os.path.join(uvr5_dir, "env", "Scripts", "python.exe")
    model_dir = os.path.join(uvr5_dir, "models")
    
    # Check if UVR5-UI is available
    if not os.path.exists(python_exe) or not os.path.exists(model_dir):
        print(f"Demucs warning: UVR5-UI python or models not found at {uvr5_dir}. Skipping separation.")
        return audio_path, None
        
    vocals_dst = os.path.join(output_dir, "vocals.wav")
    no_vocals_dst = os.path.join(output_dir, "no_vocals.wav")
    
    # If already separated and cached, return cached paths
    if os.path.exists(vocals_dst) and os.path.exists(no_vocals_dst):
        print("Demucs: Using cached separated vocals and background tracks.")
        return vocals_dst, no_vocals_dst
        
    print(f"Demucs: Starting separation for {audio_path}...")
    try:
        # Convert paths to Windows format
        win_input_wav = wsl_to_windows_path(audio_path)
        win_output_dir = wsl_to_windows_path(output_dir)
        win_model_dir = wsl_to_windows_path(model_dir)
        
        # Prepare python script to execute inside Windows
        win_python_code = (
            "from audio_separator.separator import Separator; "
            "import os; "
            "from pydub import AudioSegment; "
            f"sep = Separator(model_file_dir=r'{win_model_dir}', output_dir=r'{win_output_dir}'); "
            "sep.load_model('htdemucs_ft.yaml'); "
            f"output_files = sep.separate(r'{win_input_wav}'); "
            "print('SUCCESS_FILES:', output_files)"
        )
        
        # Determine how to run based on OS name
        args = [python_exe, "-c", win_python_code]
        cwd = uvr5_dir
            
        res = subprocess.run(args, capture_output=True, text=True, errors="replace", cwd=cwd)
        if res.returncode != 0:
            print("Demucs execution failed:")
            print("STDOUT:", res.stdout)
            print("STDERR:", res.stderr)
            raise RuntimeError(f"Demucs returned non-zero code {res.returncode}")
            
        # Parse STDOUT to find generated files
        stdout_lines = res.stdout.split('\n')
        success_line = [line for line in stdout_lines if "SUCCESS_FILES:" in line]
        if not success_line:
            raise RuntimeError("Demucs execution completed but did not output SUCCESS_FILES.")
            
        # Parse the list from string
        generated_files_str = success_line[0].split("SUCCESS_FILES:")[1].strip()
        generated_files = ast.literal_eval(generated_files_str)
        
        # Find vocals file
        vocals_files = [f for f in generated_files if "(Vocals)" in f]
        if not vocals_files:
            raise RuntimeError("Vocals stem not found in generated files.")
        vocals_file = vocals_files[0]
        
        # Find non-vocals files
        non_vocals_files = [f for f in generated_files if "(Vocals)" not in f]
        
        # Reconstruct background track (Instrumental)
        print("Demucs: Reconstructing background track from non-vocals stems...")
        from pydub import AudioSegment
        mixed = None
        for f in non_vocals_files:
            path = os.path.join(output_dir, f)
            audio = AudioSegment.from_wav(path)
            if mixed is None:
                mixed = audio
            else:
                mixed = mixed.overlay(audio)
                
        # Export mixed and rename vocals
        mixed.export(no_vocals_dst, format="wav")
        shutil.copy(os.path.join(output_dir, vocals_file), vocals_dst)
        
        # Clean up all intermediate generated stems
        print("Demucs: Cleaning up intermediate stem files...")
        for f in generated_files:
            path = os.path.join(output_dir, f)
            if os.path.exists(path):
                try: os.remove(path)
                except: pass
                
        print("Demucs: Audio separation completed successfully!")
        return vocals_dst, no_vocals_dst
        
    except Exception as e:
        print(f"Demucs Error: {e}. Falling back to original audio.")
        # If anything failed, return original audio and None for background
        return audio_path, None

def mix_voice_and_background(vocals_path: str, background_path: str, output_path: str) -> str:
    """
    Mixes the dubbed voice with the instrumental/background audio track.
    Reduces the background track's volume slightly to ensure voice clarity.
    """
    import os
    import shutil
    from pydub import AudioSegment
    if not background_path or not os.path.exists(background_path):
        # If no background track is available, just copy vocals to output
        shutil.copy(vocals_path, output_path)
        return output_path
        
    print(f"Mixing dubbed voice ({vocals_path}) and background track ({background_path})...")
    vocals = AudioSegment.from_wav(vocals_path)
    background = AudioSegment.from_wav(background_path)
    
    # We decrease the background volume by 3dB to make sure vocals are clear
    background_adjusted = background - 3
    
    # Overlay vocals on background. This preserves the sample rate/stereo of the background.
    mixed = background_adjusted.overlay(vocals)
    mixed.export(output_path, format="wav")
    print(f"Professional dubbed audio mixed and saved to: {output_path}")
    return output_path
