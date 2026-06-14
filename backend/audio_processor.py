import os
import subprocess
from pydub import AudioSegment

def get_ffmpeg_cmd() -> str:
    if os.name == 'nt':
        return r'"C:\Users\jpzam\Downloads\audioconverter\bin\ffmpeg.exe"'
    return 'ffmpeg'

def stretch_audio_segment(input_wav: str, output_wav: str, factor: float):
    """
    Time-stretches a WAV file using ffmpeg's high-quality atempo filter.
    factor > 1.0 speeds it up (shortens duration).
    factor < 1.0 slows it down (lengthens duration).
    """
    # Clamp factor to avoid extreme distortion (ffmpeg atempo supports 0.5 to 2.0)
    # If factor is outside this range, we chain filters or clamp it.
    if factor < 0.5:
        filter_str = "atempo=0.5"
    elif factor > 2.0:
        filter_str = "atempo=2.0"
    else:
        filter_str = f"atempo={factor}"
        
    ffmpeg = get_ffmpeg_cmd()
    cmd = f'{ffmpeg} -y -i "{input_wav}" -filter:a "{filter_str}" -vn "{output_wav}"'
    subprocess.run(cmd, shell=True, capture_output=True)

def get_word_list(chunks: list) -> list:
    """
    Flattens chunk segment text into a list of words with estimated timestamps.
    """
    words = []
    for chunk in chunks:
        ts = chunk.get("timestamp")
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
            # Normalize word text (lowercase, alphanumeric only)
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
    
    for chunk in original_chunks:
        ts = chunk.get("timestamp")
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
        
        # Simple sliding window search for the best word block match
        best_dub_start_idx = dub_ptr
        # We scan a small window forward to find the first matching word
        for offset in range(min(10, len(dubbed_words) - dub_ptr)):
            candidate_idx = dub_ptr + offset
            if dubbed_words[candidate_idx]["word"] == chunk_words[0]:
                best_dub_start_idx = candidate_idx
                break
                
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
    total_orig_duration = last_chunk.get("timestamp", [0, 0])[1]
    if total_orig_duration == 0:
        total_orig_duration = 1.0
        
    ratio = total_dub_duration / total_orig_duration
    
    alignment = []
    for chunk in original_chunks:
        ts = chunk.get("timestamp")
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
