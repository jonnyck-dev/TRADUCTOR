import os
import uuid
import json
import traceback
import subprocess
from fastapi import FastAPI, BackgroundTasks, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pydub import AudioSegment
import yt_dlp

# Import our modular clients
from whisper_client import transcribe_audio
from translator import translate_chunks
from tts_client import generate_individual_tts, remove_cancelled_task, cancel_task
from audio_processor import sync_individual_phrases, merge_audio_video, run_demucs_separation, mix_voice_and_background
import re
import math

app = FastAPI(title="Video Translator & Dubber API")

# Enable CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
FRONTEND_STUDIO_DIR = os.path.join(BASE_DIR, "frontend_studio")
CACHE_DIR = os.path.join(BASE_DIR, "cache")

os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(FRONTEND_DIR, exist_ok=True)
os.makedirs(FRONTEND_STUDIO_DIR, exist_ok=True)

# In-memory task store
tasks = {}

class ProcessRequest(BaseModel):
    url: str
    model: str = "gemma4:e2b-it-qat"
    speaker: str = "en-Frank_man"
    vibevoice_model: str = "openbmb/VoxCPM2"
    vibevoice_cfg: float = 2.0
    vibevoice_steps: int = 10
    tts_mode: str = "sentence"
    batch_size: int = 15
    sync_size: int = 5

def merge_short_chunks(chunks: list) -> list:
    """
    Merges very short chunks (e.g., duration < 0.8s or <= 2 words) with the next chunk
    to prevent TTS engine failures on monosyllables.
    """
    if not chunks:
        return []
        
    merged = []
    current_chunk = None
    
    for chunk in chunks:
        if current_chunk is None:
            current_chunk = dict(chunk)
            continue
            
        ts = current_chunk.get("timestamp", [0.0, 0.0])
        start, end = ts[0], ts[1]
        duration = end - start
        word_count = len(current_chunk.get("text", "").strip().split())
        
        next_ts = chunk.get("timestamp", [0.0, 0.0])
        gap = next_ts[0] - end
        
        # Merge if it's a single word (monosyllable), extremely short (< 0.4s), OR gap is tiny (< 0.15s)
        # Added a max duration safety of 15.0s to prevent creating infinite chunks if a person speaks extremely fast continuously.
        if duration < 0.4 or word_count <= 1 or (gap < 0.15 and duration < 15.0):
            print(f"Merging chunk: '{current_chunk.get('text', '').strip()}' (Dur: {duration:.2f}s, Gap: {gap:.2f}s) into next chunk.")
            
            # Combine text (Removing trailing punctuation from the first chunk to avoid confusing the translator)
            import re
            current_text = current_chunk.get("text", "").strip()
            # Strip trailing ., ?, ! to make it a continuous fluid sentence
            current_text = re.sub(r'[.?!]+$', '', current_text).strip()
            
            next_text = chunk.get("text", "").strip()
            if current_text and next_text:
                current_chunk["text"] = current_text + " " + next_text
            elif next_text:
                current_chunk["text"] = next_text
                
            # Combine timestamps
            current_chunk["timestamp"] = [start, next_ts[1]]
        else:
            merged.append(current_chunk)
            current_chunk = dict(chunk)
            
    if current_chunk is not None:
        merged.append(current_chunk)
        
    # Run a second pass just in case the last chunk was very short and didn't get merged
    # (Though usually it's fine if the final chunk is short, we won't overcomplicate for now)
    return merged

def preprocess_chunks(chunks: list) -> list:
    """
    Slices any segment/chunk whose duration exceeds 120 seconds into smaller sub-chunks
    to ensure VibeVoice processing and other logic don't degrade.
    """
    new_chunks = []
    for chunk in chunks:
        ts = chunk.get("timestamp", [0.0, 0.0])
        start, end = ts[0], ts[1]
        duration = end - start
        
        # If the duration is less than or equal to 120 seconds, keep it as is
        if duration <= 120.0:
            new_chunks.append(chunk)
            continue
            
        print(f"Preprocessing: splitting long chunk of duration {duration:.2f}s (starts at {start}s)")
        
        # Determine number of parts needed
        num_parts = math.ceil(duration / 120.0)
        part_duration = duration / num_parts
        
        # Split text into sentences/phrases if possible, or fall back to word-based splitting
        text = chunk.get("text", "").strip()
        # Find sentence boundaries: '.', '!', '?', ';'
        sentence_ends = [m.end() for m in re.finditer(r'[.!?;\n]+', text)]
        
        parts_text = []
        if sentence_ends:
            # Try to group sentences to fit within 120s proportionally
            sentences = []
            prev_idx = 0
            for idx in sentence_ends:
                sentences.append(text[prev_idx:idx].strip())
                prev_idx = idx
            if prev_idx < len(text):
                sentences.append(text[prev_idx:].strip())
                
            # Filter empty sentences
            sentences = [s for s in sentences if s]
            
            # Distribute sentences into num_parts
            sents_per_part = math.ceil(len(sentences) / num_parts)
            for i in range(num_parts):
                part_sents = sentences[i * sents_per_part : (i + 1) * sents_per_part]
                parts_text.append(" ".join(part_sents))
        else:
            # Fall back to word-based splitting
            words = text.split()
            if not words:
                new_chunks.append(chunk)
                continue
            words_per_part = math.ceil(len(words) / num_parts)
            for i in range(num_parts):
                part_words = words[i * words_per_part : (i + 1) * words_per_part]
                parts_text.append(" ".join(part_words))
                
        # Re-distribute parts and timestamps
        for i, part_text in enumerate(parts_text):
            if not part_text.strip():
                continue
            part_start = start + i * part_duration
            part_end = start + (i + 1) * part_duration
            
            # Sub-divide the "words" timestamps if they are present in WhisperX output
            part_words_info = []
            if "words" in chunk and chunk["words"]:
                # Filter words that fall into this time window
                for w in chunk["words"]:
                    w_start = w.get("start")
                    if w_start is not None and part_start <= w_start < part_end:
                        part_words_info.append(w)
            
            new_chunks.append({
                "timestamp": [part_start, part_end],
                "text": part_text,
                "words": part_words_info
            })
            
    return new_chunks

def normalize_text(text: str) -> str:
    # Lowercase
    text = text.lower()
    # Remove punctuation (keep only alphanumeric and spaces)
    text = re.sub(r'[^\w\s]', '', text)
    # Normalize whitespace
    text = " ".join(text.split())
    return text

def download_and_extract(url: str, output_dir: str) -> tuple[str, str]:
    downloads_dir = os.path.join(output_dir, "downloads")
    os.makedirs(downloads_dir, exist_ok=True)
    
    video_path = os.path.join(downloads_dir, "video.mp4")
    audio_path = os.path.join(downloads_dir, "audio.wav")
    
    if url.startswith("cache:"):
        cache_id = url.split(":")[1]
        source_dir = os.path.join(CACHE_DIR, cache_id)
        
        # If we are working directly in-place in the cache directory, skip copying
        if os.path.abspath(source_dir) == os.path.abspath(output_dir):
            print(f"Working directly inside cache directory: {source_dir}")
            
            # Check and organize root level files if they exist
            root_video = os.path.join(source_dir, "video.mp4")
            root_audio = os.path.join(source_dir, "audio.wav")
            if os.path.exists(root_video) and not os.path.exists(video_path):
                import shutil
                shutil.move(root_video, video_path)
            if os.path.exists(root_audio) and not os.path.exists(audio_path):
                import shutil
                shutil.move(root_audio, audio_path)
                
            # Organize whisper folder if files are at root level
            whisper_dir = os.path.join(source_dir, "whisper")
            os.makedirs(whisper_dir, exist_ok=True)
            for filename in ["english_whisper.json", "spanish_translated.json", "spanish_whisper.json", "verification_report.json"]:
                root_file = os.path.join(source_dir, filename)
                sub_file = os.path.join(whisper_dir, filename)
                if os.path.exists(root_file) and not os.path.exists(sub_file):
                    try:
                        import shutil
                        shutil.move(root_file, sub_file)
                        print(f"Moved {filename} to whisper/ directory.")
                    except Exception as e:
                        print(f"Failed to move {filename}: {e}")
                        
            if os.path.exists(video_path) and os.path.exists(audio_path):
                return video_path, audio_path
            else:
                raise FileNotFoundError(f"Cached files not found in downloads/ of {source_dir}")
        else:
            # Check new subfolder layout first, then root layout
            cached_video = os.path.join(source_dir, "downloads", "video.mp4")
            if not os.path.exists(cached_video):
                cached_video = os.path.join(source_dir, "video.mp4")
                
            cached_audio = os.path.join(source_dir, "downloads", "audio.wav")
            if not os.path.exists(cached_audio):
                cached_audio = os.path.join(source_dir, "audio.wav")
                
            if os.path.exists(cached_video) and os.path.exists(cached_audio):
                print(f"Skipping download, using cached files from {source_dir}")
                import shutil
                
                # Copy video and audio
                shutil.copy(cached_video, video_path)
                shutil.copy(cached_audio, audio_path)
                
                # Copy cached translations/whisper files if available to skip those phases
                whisper_dir = os.path.join(output_dir, "whisper")
                os.makedirs(whisper_dir, exist_ok=True)
                for filename in ["english_whisper.json", "spanish_translated.json", "spanish_whisper.json", "verification_report.json"]:
                    src = os.path.join(source_dir, "whisper", filename)
                    if not os.path.exists(src):
                        src = os.path.join(source_dir, filename)
                    dst = os.path.join(whisper_dir, filename)
                    if os.path.exists(src) and not os.path.exists(dst):
                        try:
                            shutil.copy(src, dst)
                            print(f"Cached {filename} copied to whisper/ directory.")
                        except Exception as e:
                            print(f"Failed to copy cached {filename}: {e}")
                            
                # Copy tts cache if present
                tts_src_dir = os.path.join(source_dir, "tts")
                tts_dst_dir = os.path.join(output_dir, "tts")
                if os.path.exists(tts_src_dir):
                    os.makedirs(tts_dst_dir, exist_ok=True)
                    for f in os.listdir(tts_src_dir):
                        if f.endswith(".mp3") or f.endswith(".wav"):
                            src = os.path.join(tts_src_dir, f)
                            dst = os.path.join(tts_dst_dir, f)
                            if not os.path.exists(dst):
                                shutil.copy(src, dst)
                                
                return video_path, audio_path
            else:
                raise FileNotFoundError(f"Cached files not found in {source_dir}")

    # Remove existing files if any
    if os.path.exists(video_path):
        try: os.remove(video_path)
        except: pass
    if os.path.exists(audio_path):
        try: os.remove(audio_path)
        except: pass
        
    print(f"Downloading YouTube video: {url}")
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': video_path,
        'merge_output_format': 'mp4',
        'nocheckcertificate': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
        
    if not os.path.exists(video_path):
        raise FileNotFoundError("Video download failed - target MP4 file not found.")
        
    print("Extracting audio from downloaded video...")
    # Extract audio using native Linux ffmpeg (24kHz Mono is best for Whisper & VibeVoice)
    cmd = f'ffmpeg -y -i "{video_path}" -vn -acodec pcm_s16le -ar 24000 -ac 1 "{audio_path}"'
    subprocess.run(cmd, shell=True, check=True, capture_output=True)
    
    if not os.path.exists(audio_path):
        raise FileNotFoundError("Audio extraction failed - target WAV file not found.")
        
    return video_path, audio_path

def prepare_cloned_voice(audio_path: str, whisper_json_path: str):
    """
    Analiza el JSON de whisper para encontrar cuándo empieza el primer fragmento de voz,
    recorta 1 minuto de audio desde ese punto y lo guarda como la voz de referencia
    en backend/vibevoice/demo/voices/cloned_speaker.wav.
    """
    print("Preparando clonación de voz a partir del audio del video...")
    try:
        with open(whisper_json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        chunks = data.get("chunks", [])
        
        # Buscar el segundo de inicio de la primera palabra/frase
        start_sec = 0.0
        for chunk in chunks:
            text = chunk.get("text", "").strip()
            ts = chunk.get("timestamp")
            if text and ts and len(ts) >= 2:
                # Usar nuestra lógica robusta get_flat_timestamp
                from audio_processor import get_flat_timestamp
                flat_ts = get_flat_timestamp(ts)
                start_sec = flat_ts[0]
                print(f"Primera palabra/frase detectada en el segundo: {start_sec}")
                break
                
        # Rutas de destino genéricas
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cloned_wav_path = os.path.join(base_dir, "backend", "cloned_speaker.wav")
        
        # Recortar 1 minuto de audio usando pydub
        print(f"Cargando audio original para recorte: {audio_path}")
        audio = AudioSegment.from_wav(audio_path)
        
        start_ms = int(start_sec * 1000)
        
        # Lógica especial y cimientos para "Editor por Slices"
        is_local_path = os.path.join(os.path.dirname(audio_path), "is_local.txt")
        if os.path.exists(is_local_path):
            if len(audio) <= 15000:
                sample_duration = len(audio) - start_ms
                print(f"[Voice Cloning] Modo Slice detectado (<15s). Usando muestra total de {sample_duration/1000:.2f} segundos.")
            elif len(audio) <= 35000:
                sample_duration = 15000
                print("[Voice Cloning] Video local corto detectado. Extrayendo muestra optimizada de 15 segundos.")
            else:
                sample_duration = 60000
        else:
            sample_duration = 60000
            
        end_ms = start_ms + sample_duration
        end_ms = min(end_ms, len(audio))
        
        print(f"Recortando desde {start_sec:.2f}s hasta {end_ms/1000:.2f}s...")
        sample = audio[start_ms:end_ms]
        sample.export(cloned_wav_path, format="wav")
        print(f"Voz clonada guardada con éxito en: {cloned_wav_path}")
        
        # Copia opcional para compatibilidad con VibeVoice
        vibevoice_voices_dir = os.path.join(base_dir, "backend", "vibevoice", "demo", "voices")
        if os.path.exists(vibevoice_voices_dir):
            try:
                import shutil
                shutil.copy(cloned_wav_path, os.path.join(vibevoice_voices_dir, "cloned_speaker.wav"))
                print("Copiada voz clonada a carpeta de VibeVoice para retrocompatibilidad.")
            except Exception as ce:
                print(f"Failed to copy to VibeVoice folder: {ce}")
    except Exception as e:
        print(f"Error al preparar la voz clonada: {e}")
        traceback.print_exc()

def process_translation_task(task_id: str, url: str, model: str, speaker: str, vibevoice_model: str = None, vibevoice_cfg: float = 2.0, vibevoice_steps: int = 10, tts_mode: str = "sentence", batch_size: int = 15, sync_size: int = 5):
    import time
    start_task_time = time.time()
    step_times = {}
    
    try:
        remove_cancelled_task(task_id)
        output_dir = os.path.join(CACHE_DIR, task_id)
        os.makedirs(output_dir, exist_ok=True)
        
        downloads_dir = os.path.join(output_dir, "downloads")
        whisper_dir = os.path.join(output_dir, "whisper")
        tts_dir = os.path.join(output_dir, "tts")
        audio_sep_dir = os.path.join(output_dir, "audio_separation")
        
        os.makedirs(downloads_dir, exist_ok=True)
        os.makedirs(whisper_dir, exist_ok=True)
        os.makedirs(tts_dir, exist_ok=True)
        os.makedirs(audio_sep_dir, exist_ok=True)
        
        # 1. Download YouTube Video & Extract Audio
        t0 = time.time()
        tasks[task_id]["status"] = "downloading"
        tasks[task_id]["progress"] = 15
        video_path, audio_path = download_and_extract(url, output_dir)
        step_times["1_download_and_extract"] = time.time() - t0
        
        # 1b. Run Demucs separation to get vocals.wav and no_vocals.wav (with fallback)
        t0 = time.time()
        tasks[task_id]["status"] = "separating"
        tasks[task_id]["progress"] = 25
        vocals_wav_path, background_wav_path = run_demucs_separation(audio_path, audio_sep_dir)
        step_times["1b_demucs_separation"] = time.time() - t0
        
        # Calculate original duration
        audio_segment = AudioSegment.from_wav(audio_path)
        duration_sec = audio_segment.duration_seconds
        
        # 2. Transcribe English Audio
        t0 = time.time()
        tasks[task_id]["status"] = "transcribing"
        tasks[task_id]["progress"] = 35
        orig_json_path = os.path.join(whisper_dir, "english_whisper.json")
        if os.path.exists(orig_json_path):
            print(f"Skipping transcription, using cached: {orig_json_path}")
            with open(orig_json_path, 'r', encoding='utf-8') as f:
                orig_data = json.load(f)
        else:
            # Transcribe the clean vocals track to prevent hallucinations caused by background noise
            orig_data = transcribe_audio(vocals_wav_path, orig_json_path, language="English")
        step_times["2_transcription"] = time.time() - t0
            
        # 2b. Preprocess Chunks (split segments exceeding 120s duration, merge short ones)
        orig_chunks = orig_data.get("chunks", [])
        preprocessed_chunks = merge_short_chunks(orig_chunks)
        preprocessed_chunks = preprocess_chunks(preprocessed_chunks)
        
        # 3. Translate JSON to Spanish using Ollama
        t0 = time.time()
        tasks[task_id]["status"] = "translating"
        tasks[task_id]["progress"] = 55
        translated_json_path = os.path.join(whisper_dir, "spanish_1_translated.json")
        enhanced_json_path = os.path.join(whisper_dir, "spanish_2_enhanced.json")
        phonetic_json_path = os.path.join(whisper_dir, "spanish_3_phonetic.json")
        final_json_path = os.path.join(whisper_dir, "spanish_4_final.json")
        
        # Retro-compatibility checks (if old cached files exist)
        cache_to_load = None
        if os.path.exists(final_json_path): cache_to_load = final_json_path
        elif os.path.exists(os.path.join(whisper_dir, "spanish_enhanced.json")): cache_to_load = os.path.join(whisper_dir, "spanish_enhanced.json")
        
        if cache_to_load:
            print(f"Skipping translation pipeline, using fully cached final version: {cache_to_load}")
            with open(cache_to_load, 'r', encoding='utf-8') as f:
                translated_data = json.load(f)
            translated_chunks = translated_data.get("chunks", [])
        else:
            if os.path.exists(translated_json_path):
                print(f"Skipping translation, using cached raw translation: {translated_json_path}")
                with open(translated_json_path, 'r', encoding='utf-8') as f:
                    raw_data = json.load(f)
                raw_translated_chunks = raw_data.get("chunks", [])
            else:
                from translator import translate_chunks
                raw_translated_chunks = translate_chunks(preprocessed_chunks, model=model, save_dir=whisper_dir)
                raw_data = {
                    "text": " ".join([c.get("text", "") for c in raw_translated_chunks]),
                    "chunks": raw_translated_chunks
                }
                with open(translated_json_path, "w", encoding="utf-8") as f:
                    json.dump(raw_data, f, ensure_ascii=False, indent=2)
            
            # 3b. Sanitize and enhance translation for TTS (Anti-Collapse)
            from translator import enhance_translation_for_tts, phonetic_normalization_for_tts, synchronize_translation_for_tts
            
            enhanced_chunks = enhance_translation_for_tts(raw_translated_chunks, model=model)
            with open(enhanced_json_path, "w", encoding="utf-8") as f:
                json.dump({"chunks": enhanced_chunks}, f, ensure_ascii=False, indent=2)
            
            # 3c. Phonetic Normalization (Anti-Gringo Accent)
            phonetic_chunks = phonetic_normalization_for_tts(enhanced_chunks, model=model)
            with open(phonetic_json_path, "w", encoding="utf-8") as f:
                json.dump({"chunks": phonetic_chunks}, f, ensure_ascii=False, indent=2)
            
            # 3d. Math Sync: Ensure words fit in their allotted timestamp
            translated_chunks = synchronize_translation_for_tts(phonetic_chunks, model=model)
            
            translated_data = {
                "text": " ".join([c.get("text", "") for c in translated_chunks]),
                "chunks": translated_chunks
            }
            with open(final_json_path, "w", encoding="utf-8") as f:
                json.dump(translated_data, f, ensure_ascii=False, indent=2)
                
        step_times["3_translation_and_enhancement"] = time.time() - t0
            
        # 4. Generate Spanish TTS (One-shot or Sentence-by-sentence)
        t0 = time.time()
        tasks[task_id]["status"] = "synthesizing"
        tasks[task_id]["progress"] = 75
        
        # Guardián de Estado: Prevenir desincronización por cambios de Batch/Sync Size
        render_state_path = os.path.join(tts_dir, "render_state.json")
        current_state = {
            "tts_mode": tts_mode,
            "batch_size": batch_size,
            "sync_size": sync_size
        }
        if os.path.exists(render_state_path):
            try:
                with open(render_state_path, "r", encoding="utf-8") as f:
                    last_state = json.load(f)
                if last_state.get("batch_size") != batch_size or last_state.get("sync_size") != sync_size or last_state.get("tts_mode") != tts_mode:
                    print(f"[TTS] Alerta: Cambio de configuración detectado {last_state} -> {current_state}. Limpiando caché TTS antigua para evitar desincronización.")
                    import shutil
                    if os.path.exists(tts_dir):
                        for f_name in os.listdir(tts_dir):
                            if f_name.endswith(".mp3") or f_name.endswith(".wav") or f_name.endswith(".json"):
                                try: os.remove(os.path.join(tts_dir, f_name))
                                except: pass
                    sync_dir = os.path.join(output_dir, "sync")
                    if os.path.exists(sync_dir):
                        shutil.rmtree(sync_dir, ignore_errors=True)
            except Exception as e:
                print(f"[TTS] Error leyendo render_state.json: {e}")
                
        with open(render_state_path, "w", encoding="utf-8") as f:
            json.dump(current_state, f)

        if speaker == "cloned_speaker":
            # Extract 1 minute sample from clean vocals wav instead of noisy original audio
            prepare_cloned_voice(vocals_wav_path, orig_json_path)

        from audio_processor import get_flat_timestamp
        if tts_mode == "oneshot":
            print("[TTS] Operating in One-Shot Mode (merging all phrases)...")
            # Merge all Spanish texts into a single string
            merged_text = " ".join([c.get("text", "").strip() for c in translated_chunks if c.get("text", "").strip()])
            
            # Find the start time of the first non-empty phrase
            first_start_time = 0.0
            for chunk in translated_chunks:
                if chunk.get("text", "").strip():
                    ts = get_flat_timestamp(chunk.get("timestamp", [0.0, 0.0]))
                    first_start_time = ts[0]
                    break
            
            # Create a single merged chunk
            tts_chunks = [{"text": merged_text, "timestamp": [first_start_time, duration_sec]}]
        else:
            # Group chunks in batches of `batch_size` in memory (Sentence Mode batching)
            print(f"[TTS] Operating in Sentence Mode (grouping in batches of {batch_size} phrases)...")
            tts_chunks = []
            for i in range(0, len(translated_chunks), batch_size):
                batch = translated_chunks[i:i+batch_size]
                merged_text = " ".join([c.get("text", "").strip() for c in batch if c.get("text", "").strip()])
                if not merged_text:
                    continue
                
                # Get start timestamp of first non-empty chunk in batch
                start_time = None
                for c in batch:
                    if c.get("text", "").strip():
                        ts = get_flat_timestamp(c.get("timestamp", [0.0, 0.0]))
                        start_time = ts[0]
                        break
                if start_time is None:
                    ts = get_flat_timestamp(batch[0].get("timestamp", [0.0, 0.0]))
                    start_time = ts[0]
                    
                # Get end timestamp of last non-empty chunk in batch
                end_time = None
                for c in reversed(batch):
                    if c.get("text", "").strip():
                        ts = get_flat_timestamp(c.get("timestamp", [0.0, 0.0]))
                        end_time = ts[1]
                        break
                if end_time is None:
                    ts = get_flat_timestamp(batch[-1].get("timestamp", [0.0, 0.0]))
                    end_time = ts[1]
                
                tts_chunks.append({
                    "text": merged_text,
                    "timestamp": [start_time, end_time],
                    "original_chunks": batch  # Save reference for slicing later
                })

        mp3_paths = generate_individual_tts(
            tts_chunks, 
            tts_dir, 
            speaker_name=speaker, 
            task_id=task_id,
            vibevoice_model=vibevoice_model,
            vibevoice_cfg=vibevoice_cfg,
            vibevoice_steps=vibevoice_steps
        )
        step_times["4_tts_synthesis"] = time.time() - t0
        
        # If in Sentence Mode, slice into decoupled sync_size blocks using Single-Pass WhisperX (unless sizes match)
        if tts_mode == "sentence":
            if batch_size != sync_size and len(translated_chunks) > sync_size:
                print(f"[TTS] Slicing super-audio into blocks of {sync_size} phrases via Single-Pass WhisperX...")
                from audio_processor import process_super_audio_with_whisperx
                
                sliced_mp3s, final_sync_chunks = process_super_audio_with_whisperx(
                    mp3_paths, translated_chunks, sync_size, tts_dir
                )
                
                tts_chunks_for_sync = final_sync_chunks
                mp3_paths_for_sync = sliced_mp3s
            else:
                if len(translated_chunks) <= sync_size:
                    print(f"[TTS] Bypass Inteligente: El video/slice tiene solo {len(translated_chunks)} frases (<= Sync Size {sync_size}). Omitiendo Single-Pass WhisperX para máxima velocidad.")
                else:
                    print(f"[TTS] Batch Size ({batch_size}) equals Sync Size ({sync_size}). Bypassing WhisperX slicing!")
                tts_chunks_for_sync = tts_chunks
                mp3_paths_for_sync = mp3_paths
        else:
            tts_chunks_for_sync = tts_chunks
            mp3_paths_for_sync = mp3_paths
        
        # --- Phrase-level splitting for Studio Editor ---
        if tts_mode == "sentence" and len(translated_chunks) > 1 and any(
            len(sc.get("original_chunks", [])) > 1 for sc in tts_chunks_for_sync
        ):
            print(f"[TTS] Splitting sync blocks into individual phrases for Studio Editor...")
            from audio_processor import proportional_split
            import shutil
            
            individual_mp3s = []
            individual_chunks = []
            phrase_global_idx = 0
            
            for sync_idx, sync_chunk in enumerate(tts_chunks_for_sync):
                original_phrases = sync_chunk.get("original_chunks", [])
                if not original_phrases:
                    continue
                
                if len(original_phrases) == 1:
                    src_path = mp3_paths_for_sync[sync_idx]
                    ext = os.path.splitext(src_path)[1]
                    dst_path = os.path.join(tts_dir, f"phrase_{phrase_global_idx}{ext}")
                    if os.path.exists(src_path) and os.path.abspath(src_path) != os.path.abspath(dst_path):
                        shutil.copy2(src_path, dst_path)
                    individual_mp3s.append(dst_path if os.path.exists(dst_path) else src_path)
                    individual_chunks.extend(original_phrases)
                    phrase_global_idx += 1
                else:
                    sync_path = mp3_paths_for_sync[sync_idx]
                    phrase_temp_dir = os.path.join(tts_dir, f"phrase_split_{sync_idx}")
                    os.makedirs(phrase_temp_dir, exist_ok=True)
                    try:
                        phrase_paths = proportional_split(sync_path, original_phrases, phrase_temp_dir)
                        for phrase_path in phrase_paths:
                            ext = os.path.splitext(phrase_path)[1]
                            dst_path = os.path.join(tts_dir, f"phrase_{phrase_global_idx}{ext}")
                            if os.path.exists(dst_path):
                                os.remove(dst_path)
                            os.rename(phrase_path, dst_path)
                            individual_mp3s.append(dst_path)
                            phrase_global_idx += 1
                        individual_chunks.extend(original_phrases)
                    finally:
                        shutil.rmtree(phrase_temp_dir, ignore_errors=True)
            
            print(f"[TTS] Split into {len(individual_mp3s)} individual phrase files for Studio Editor.")
            tts_chunks_for_sync = individual_chunks
            mp3_paths_for_sync = individual_mp3s
        
        output_video_path = os.path.join(output_dir, "video_dubbed.mp4")
        verification_report_path = os.path.join(whisper_dir, "verification_report.json")
        timing_report_path = os.path.join(output_dir, "timing_report.json")

        if not os.path.exists(output_video_path) or not os.path.exists(verification_report_path):
            # 5. Overlay, synchronize and speed up chunks (Splicing, stretching and overlaying)
            t0 = time.time()
            tasks[task_id]["status"] = "synchronizing"
            tasks[task_id]["progress"] = 85
            synced_wav_path = os.path.join(output_dir, "dubbed_synced.wav")
            sync_individual_phrases(tts_chunks_for_sync, mp3_paths_for_sync, synced_wav_path, duration_sec)
            step_times["5_synchronization"] = time.time() - t0
            
            # 5b. Mix synced Spanish voice and original background instrumental track
            t0 = time.time()
            mixed_wav_path = os.path.join(output_dir, "dubbed_mixed.wav")
            mix_voice_and_background(synced_wav_path, background_wav_path, mixed_wav_path)
            step_times["5b_audio_mixing"] = time.time() - t0
            
            # 6. Merge dubbed audio and original video track (removing orig audio)
            t0 = time.time()
            tasks[task_id]["status"] = "merging"
            tasks[task_id]["progress"] = 90
            merge_audio_video(video_path, mixed_wav_path, output_video_path)
            step_times["6_video_merging"] = time.time() - t0
            
            # 7. QA Verification: transcribe final dubbed WAV and compare against Spanish translation
            t0 = time.time()
            tasks[task_id]["status"] = "verifying"
            tasks[task_id]["progress"] = 95
            print("Starting QA Verification...")
            
            verification_json_path = os.path.join(whisper_dir, "spanish_whisper_verification.json")
            verification_data = transcribe_audio(synced_wav_path, verification_json_path, language="Spanish")
            
            expected_text = translated_data.get("text", "").strip()
            actual_text = verification_data.get("text", "").strip()
            
            norm_expected = normalize_text(expected_text)
            norm_actual = normalize_text(actual_text)
            
            import difflib
            matcher = difflib.SequenceMatcher(None, norm_expected, norm_actual)
            ratio = matcher.ratio()
            
            passed = bool(ratio >= 0.90)
            verification_report = {
                "accuracy_ratio": ratio,
                "passed": passed,
                "expected_text": expected_text,
                "actual_text": actual_text,
                "normalized_expected": norm_expected,
                "normalized_actual": norm_actual
            }
            
            with open(verification_report_path, "w", encoding="utf-8") as f:
                json.dump(verification_report, f, ensure_ascii=False, indent=2)
                
            print(f"QA Verification completed: Accuracy: {ratio*100:.2f}%. Passed: {passed}")
            step_times["7_qa_verification"] = time.time() - t0
            
            # Calculate total task duration
            total_task_time = time.time() - start_task_time
            step_times["total_duration"] = total_task_time
            
            # Save timing report
            with open(timing_report_path, "w", encoding="utf-8") as f:
                json.dump(step_times, f, ensure_ascii=False, indent=2)
                
        else:
            print("Video and QA report already exist. Skipping sync, merge, and QA steps.")
            
            # Load existing timing report
            if os.path.exists(timing_report_path):
                with open(timing_report_path, "r", encoding="utf-8") as f:
                    step_times = json.load(f)
                    total_task_time = step_times.get("total_duration", 0.0)
            else:
                total_task_time = 0.0
                step_times["total_duration"] = total_task_time
                
            # Load existing QA report
            with open(verification_report_path, "r", encoding="utf-8") as f:
                qa_data = json.load(f)
                ratio = qa_data.get("accuracy_ratio", 1.0)
                passed = qa_data.get("passed", True)
            
        # Print a beautiful summary of timers in the console
        print("\n" + "="*50)
        print("   REPORTE DE TIEMPOS DE EJECUCIÓN (TIMERS)")
        print("="*50)
        for step_name, duration in step_times.items():
            if step_name != "total_duration":
                print(f" - {step_name:<25}: {duration:6.2f} segundos ({duration/total_task_time*100:5.1f}%)")
        print("-"*50)
        print(f" * TOTAL PIPELINE DURATION  : {total_task_time:6.2f} segundos")
        print("="*50 + "\n")
        
        # 8. Finished
        tasks[task_id]["status"] = "completed"
        tasks[task_id]["progress"] = 100
        tasks[task_id]["result"] = {
            "video_url": f"/api/stream/{task_id}?t={int(time.time())}",
            "original_json": orig_data,
            "translated_json": translated_data,
            "timing_report": step_times,
            "verification": {
                "accuracy_ratio": ratio,
                "passed": passed,
                "report_path": f"/cache/{task_id}/whisper/verification_report.json"
            }
        }
        print(f"Task {task_id} completed successfully!")
    except Exception as e:
        print(f"Error processing task {task_id}:")
        traceback.print_exc()
        if "stopped by user" in str(e).lower():
            tasks[task_id]["status"] = "stopped"
            tasks[task_id]["error"] = "Process stopped by user"
        else:
            tasks[task_id]["status"] = "failed"
            tasks[task_id]["error"] = str(e)


@app.post("/api/upload")
async def upload_local_video(file: UploadFile = File(...)):
    import shutil
    import subprocess
    
    task_id = str(uuid.uuid4())
    source_dir = os.path.join(CACHE_DIR, task_id)
    downloads_dir = os.path.join(source_dir, "downloads")
    os.makedirs(downloads_dir, exist_ok=True)
    
    video_path = os.path.join(downloads_dir, "video.mp4")
    
    try:
        with open(video_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        audio_path = os.path.join(downloads_dir, "audio.wav")
        cmd = f'ffmpeg -y -i "{video_path}" -vn -acodec pcm_s16le -ar 24000 -ac 1 "{audio_path}"'
        subprocess.run(cmd, shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Etiqueta secreta para diferenciarlo de YouTube
        with open(os.path.join(downloads_dir, "is_local.txt"), "w") as f:
            f.write("True")
        
        return {"status": "ok", "task_id": task_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/process")
def process_video(request: ProcessRequest, background_tasks: BackgroundTasks):
    if request.url.startswith("cache:"):
        task_id = request.url.split(":")[1]
    else:
        task_id = str(uuid.uuid4())
        
    remove_cancelled_task(task_id)
    tasks[task_id] = {
        "status": "queued",
        "progress": 0,
        "error": None,
        "result": None
    }
    background_tasks.add_task(
        process_translation_task,
        task_id,
        request.url,
        request.model,
        request.speaker,
        request.vibevoice_model,
        request.vibevoice_cfg,
        request.vibevoice_steps,
        request.tts_mode,
        request.batch_size,
        request.sync_size
    )
    return {"task_id": task_id}

@app.post("/api/cancel/{task_id}")
def cancel_task_endpoint(task_id: str):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    tasks[task_id]["status"] = "stopped"
    tasks[task_id]["error"] = "Process stopped by user"
    cancel_task(task_id)
    return {"status": "ok", "message": f"Task {task_id} cancellation requested"}

@app.get("/api/status/{task_id}")
def get_task_status(task_id: str):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    return tasks[task_id]

@app.get("/api/models")
def get_ollama_models():
    import requests
    # 1. Try Ollama local HTTP API
    try:
        response = requests.get("http://127.0.0.1:11434/api/tags", timeout=3)
        if response.status_code == 200:
            data = response.json()
            model_names = [m.get("name") for m in data.get("models", [])]
            return {"status": "ok", "models": model_names}
    except Exception as e:
        print(f"Ollama local API /tags call failed: {e}")
        
    # 2. Try running "ollama list" CLI via subprocess
    try:
        res = subprocess.run(["ollama", "list"], capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=3)
        if res.returncode == 0:
            models = []
            lines = res.stdout.strip().split('\n')
            if len(lines) > 1:
                # Skip header
                for line in lines[1:]:
                    parts = line.split()
                    if parts:
                        models.append(parts[0])
                return {"status": "ok", "models": models}
    except Exception as e:
        print(f"Ollama list execution failed: {e}")
        
    # 3. Static fallback
    return {
        "status": "fallback",
        "models": [
            "gemma4:e2b-it-qat",
            "llama3.2:3b",
            "qwen3.5:2b",
            "deepseek-v4-pro:cloud",
            "deepseek-v4-flash:cloud",
            "nemotron-3-nano:30b-cloud"
        ]
    }

import re
from fastapi import Request
from fastapi.responses import StreamingResponse

@app.get("/api/stream_original/{task_id}")
def stream_original_video(task_id: str, request: Request):
    video_path = os.path.join(CACHE_DIR, task_id, "downloads", "video.mp4")
    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Original video not found")
        
    file_size = os.path.getsize(video_path)
    range_header = request.headers.get("range")
    
    headers = {
        "Accept-Ranges": "bytes",
        "Content-Type": "video/mp4",
        "Access-Control-Expose-Headers": "Content-Range, Accept-Ranges",
        "Cache-Control": "no-cache",
    }
    
    if not range_header:
        headers["Content-Length"] = str(file_size)
        return FileResponse(video_path, headers=headers)
        
    try:
        byte1, byte2 = 0, None
        match = re.search(r'bytes=(\d+)-(\d*)', range_header)
        if match:
            byte1 = int(match.group(1))
            if match.group(2):
                byte2 = int(match.group(2))
    except Exception:
        byte1 = 0
        
    if byte2 is None or byte2 >= file_size:
        byte2 = file_size - 1
        
    length = byte2 - byte1 + 1
    headers["Content-Length"] = str(length)
    headers["Content-Range"] = f"bytes {byte1}-{byte2}/{file_size}"
    
    with open(video_path, "rb") as f:
        f.seek(byte1)
        data = f.read(length)
        
    return StreamingResponse(
        iter([data]), 
        status_code=206, 
        headers=headers, 
        media_type="video/mp4"
    )

@app.get("/api/stream/{task_id}")
def stream_video(task_id: str, request: Request):
    video_path = os.path.join(CACHE_DIR, task_id, "video_dubbed.mp4")
    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Video not found")
        
    file_size = os.path.getsize(video_path)
    range_header = request.headers.get("range")
    
    headers = {
        "Accept-Ranges": "bytes",
        "Content-Type": "video/mp4",
        "Access-Control-Expose-Headers": "Content-Range, Accept-Ranges",
        "Cache-Control": "no-cache",
    }
    
    if not range_header:
        headers["Content-Length"] = str(file_size)
        return FileResponse(video_path, headers=headers)
        
    try:
        byte1, byte2 = 0, None
        match = re.search(r'bytes=(\d+)-(\d*)', range_header)
        if match:
            byte1 = int(match.group(1))
            if match.group(2):
                byte2 = int(match.group(2))
    except Exception:
        byte1 = 0
        
    if byte2 is None or byte2 >= file_size:
        byte2 = file_size - 1
        
    length = byte2 - byte1 + 1
    headers["Content-Length"] = str(length)
    headers["Content-Range"] = f"bytes {byte1}-{byte2}/{file_size}"
    
    def file_iterator():
        with open(video_path, "rb") as f:
            f.seek(byte1)
            remaining = length
            chunk_size = 1024 * 1024
            while remaining > 0:
                chunk = f.read(min(chunk_size, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    return StreamingResponse(file_iterator(), status_code=206, headers=headers)

@app.get("/api/caches")
def list_available_caches():
    valid_caches = []
    if os.path.exists(CACHE_DIR):
        for entry in os.listdir(CACHE_DIR):
            task_dir = os.path.join(CACHE_DIR, entry)
            if os.path.isdir(task_dir) and entry != "benchmark_runs":
                valid_caches.append(entry)
    return {"status": "ok", "caches": valid_caches}


# ==========================================
# PHASE 4: INTERACTIVE STUDIO EDITOR API
# ==========================================
from pydantic import BaseModel
import io

class ReprocessRequest(BaseModel):
    phrase_index: int
    text: str
    speaker: str
    vibevoice_model: str
    vibevoice_cfg: float
    vibevoice_steps: int

def get_latest_script_path(task_id: str):
    whisper_dir = os.path.join(CACHE_DIR, task_id, "whisper")
    for p in ["spanish_4_final.json", "spanish_enhanced.json", "spanish_translated.json"]:
        full_path = os.path.join(whisper_dir, p)
        if os.path.exists(full_path):
            return full_path
    return None

@app.get("/api/studio/{task_id}/data")
def get_studio_data(task_id: str):
    enhanced_json = get_latest_script_path(task_id)
    if not enhanced_json:
        raise HTTPException(status_code=404, detail="Data not ready")
            
    with open(enhanced_json, "r", encoding="utf-8") as f:
        data = json.load(f)
    chunks = data.get("chunks", [])
    
    from audio_processor import get_flat_timestamp
    phrases = []
    for i, chunk in enumerate(chunks):
        ts = get_flat_timestamp(chunk.get("timestamp", [0.0, 0.0]))
        text = chunk.get("text", "").strip()
        if text:
            phrases.append({
                "phrase_index": i,
                "text": text,
                "start_time": ts[0],
                "end_time": ts[1]
            })
    return {"status": "ok", "phrases": phrases}

@app.get("/api/studio/{task_id}/audio/original")
def get_original_audio_slice(task_id: str, start: float, end: float):
    from pydub import AudioSegment
    vocals_path = os.path.join(CACHE_DIR, task_id, "demucs", "htdemucs", "audio", "vocals.wav")
    if not os.path.exists(vocals_path):
        raise HTTPException(status_code=404, detail="Original vocals not found")
        
    audio = AudioSegment.from_file(vocals_path)
    # Add a 200ms padding for context
    slice_audio = audio[max(0, (start - 0.2) * 1000) : (end + 0.2) * 1000]
    
    buf = io.BytesIO()
    slice_audio.export(buf, format="mp3", bitrate="128k")
    buf.seek(0)
    
    headers = {"Cache-Control": "public, max-age=3600"}
    return StreamingResponse(buf, media_type="audio/mpeg", headers=headers)

@app.get("/api/studio/{task_id}/audio/dubbed/{phrase_index}")
def get_dubbed_audio(task_id: str, phrase_index: int):
    path_mp3 = os.path.join(CACHE_DIR, task_id, "tts", f"phrase_{phrase_index}.mp3")
    path_wav = os.path.join(CACHE_DIR, task_id, "tts", f"phrase_{phrase_index}.wav")
    
    headers = {"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"}
    if os.path.exists(path_mp3):
        return FileResponse(path_mp3, headers=headers)
    elif os.path.exists(path_wav):
        return FileResponse(path_wav, headers=headers)
    else:
        raise HTTPException(status_code=404, detail="Dubbed audio not found for this phrase")

@app.post("/api/studio/{task_id}/reprocess")
def reprocess_studio_block(task_id: str, req: ReprocessRequest):
    """Regenerates the TTS for a single phrase and updates the JSON script."""
    tts_dir = os.path.join(CACHE_DIR, task_id, "tts")
    os.makedirs(tts_dir, exist_ok=True)
    
    # 1. Update latest JSON script (single phrase only)
    enhanced_json = get_latest_script_path(task_id)
    if not enhanced_json:
        raise HTTPException(status_code=404, detail="Cache script not found")
        
    with open(enhanced_json, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    if req.phrase_index >= len(data.get("chunks", [])):
        raise HTTPException(status_code=400, detail="Invalid phrase_index out of range")
        
    data["chunks"][req.phrase_index]["text"] = req.text
    with open(enhanced_json, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
                
    # 2. Extract specific vocal slice for voice cloning reference
    from audio_processor import get_flat_timestamp
    import subprocess
    from tts_client import wsl_to_windows_path
    
    phrase_chunk = data["chunks"][req.phrase_index]
    ts = get_flat_timestamp(phrase_chunk.get("timestamp", [0.0, 5.0]))
    start_time = ts[0]
    end_time = ts[1]
            
    vocals_path = os.path.join(CACHE_DIR, task_id, "demucs", "htdemucs", "audio", "vocals.wav")
    ref_wav = os.path.join(tts_dir, f"ref_{req.phrase_index}.wav")
    if os.path.exists(vocals_path):
        cmd = ["ffmpeg", "-y", "-i", vocals_path, "-ss", str(start_time), "-to", str(end_time), "-c", "copy", ref_wav]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
    # 3. Call generate_individual_tts dynamically
    from tts_client import generate_individual_tts
    import shutil
    
    # We create a temporary directory for this single phrase to avoid overwriting others
    temp_tts_dir = os.path.join(CACHE_DIR, task_id, "tts_temp_studio")
    os.makedirs(temp_tts_dir, exist_ok=True)
    
    # If the speaker uses cloning, generate_individual_tts expects the reference wav at ref_{idx}.wav
    temp_ref_wav = os.path.join(temp_tts_dir, "ref_0.wav")
    if os.path.exists(ref_wav):
        shutil.copy2(ref_wav, temp_ref_wav)
        
    dummy_chunks = [{"text": req.text, "timestamp": [start_time, end_time]}]
    
    try:
        generated_paths = generate_individual_tts(
            chunks=dummy_chunks,
            tts_dir=temp_tts_dir,
            speaker_name=req.speaker,
            task_id=task_id,
            vibevoice_model=req.vibevoice_model,
            vibevoice_cfg=req.vibevoice_cfg,
            vibevoice_steps=req.vibevoice_steps
        )
        
        if not generated_paths or not os.path.exists(generated_paths[0]):
            raise HTTPException(status_code=500, detail="TTS generation failed or returned no audio.")
            
        # Move the generated file back to the main tts folder
        output_mp3 = os.path.join(tts_dir, f"phrase_{req.phrase_index}.mp3")
        if os.path.exists(output_mp3):
            os.remove(output_mp3)
        shutil.copy2(generated_paths[0], output_mp3)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Clean up temp dir
        if os.path.exists(temp_tts_dir):
            shutil.rmtree(temp_tts_dir, ignore_errors=True)
            
    return {"status": "ok", "message": f"Phrase {req.phrase_index} regenerated successfully."}

@app.post("/api/studio/{task_id}/finalize")
def finalize_studio_video(task_id: str):
    """Prepares the project for final assembly by clearing the old video outputs."""
    output_video = os.path.join(CACHE_DIR, task_id, "video_dubbed.mp4")
    verification_report = os.path.join(CACHE_DIR, task_id, "whisper", "verification_report.json")
    
    if os.path.exists(output_video):
        os.remove(output_video)
    if os.path.exists(verification_report):
        os.remove(verification_report)
        
    return {"status": "ok", "message": "Listo para ensamblar. Presiona el botón Traducir (Simular) para generar el video final."}

# Mount video cache directory
app.mount("/cache", StaticFiles(directory=CACHE_DIR), name="cache")

# Mount studio frontend
app.mount("/studio", StaticFiles(directory=FRONTEND_STUDIO_DIR, html=True), name="frontend_studio")

# Mount frontend directory last (so / serves index.html)
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
