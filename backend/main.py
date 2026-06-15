import os
import uuid
import json
import traceback
import subprocess
from fastapi import FastAPI, BackgroundTasks, HTTPException
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
CACHE_DIR = os.path.join(BASE_DIR, "cache")
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(FRONTEND_DIR, exist_ok=True)

# In-memory task store
tasks = {}

class ProcessRequest(BaseModel):
    url: str
    model: str = "gemma4:e2b-it-qat"
    speaker: str = "en-Frank_man"

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
                
        # Rutas de destino
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        voices_dir = os.path.join(base_dir, "backend", "vibevoice", "demo", "voices")
        os.makedirs(voices_dir, exist_ok=True)
        cloned_wav_path = os.path.join(voices_dir, "cloned_speaker.wav")
        
        # Recortar 1 minuto de audio usando pydub
        print(f"Cargando audio original para recorte: {audio_path}")
        audio = AudioSegment.from_wav(audio_path)
        
        start_ms = int(start_sec * 1000)
        end_ms = start_ms + 60000  # 60 segundos
        end_ms = min(end_ms, len(audio))
        
        print(f"Recortando desde {start_sec:.2f}s hasta {end_ms/1000:.2f}s...")
        sample = audio[start_ms:end_ms]
        sample.export(cloned_wav_path, format="wav")
        print(f"Voz clonada guardada con éxito en: {cloned_wav_path}")
    except Exception as e:
        print(f"Error al preparar la voz clonada: {e}")
        traceback.print_exc()

def process_translation_task(task_id: str, url: str, model: str, speaker: str):
    try:
        remove_cancelled_task(task_id)
        output_dir = os.path.join(CACHE_DIR, task_id)
        os.makedirs(output_dir, exist_ok=True)
        
        downloads_dir = os.path.join(output_dir, "downloads")
        whisper_dir = os.path.join(output_dir, "whisper")
        tts_dir = os.path.join(output_dir, "tts")
        
        os.makedirs(downloads_dir, exist_ok=True)
        os.makedirs(whisper_dir, exist_ok=True)
        os.makedirs(tts_dir, exist_ok=True)
        
        # 1. Download YouTube Video & Extract Audio
        tasks[task_id]["status"] = "downloading"
        tasks[task_id]["progress"] = 15
        video_path, audio_path = download_and_extract(url, output_dir)
        
        # 1b. Run Demucs separation to get vocals.wav and no_vocals.wav (with fallback)
        vocals_wav_path, background_wav_path = run_demucs_separation(audio_path, downloads_dir)
        
        # Calculate original duration
        audio_segment = AudioSegment.from_wav(audio_path)
        duration_sec = audio_segment.duration_seconds
        
        # 2. Transcribe English Audio
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
            
        # 2b. Preprocess Chunks (split segments exceeding 120s duration)
        orig_chunks = orig_data.get("chunks", [])
        preprocessed_chunks = preprocess_chunks(orig_chunks)
        
        # 3. Translate JSON to Spanish using Ollama
        tasks[task_id]["status"] = "translating"
        tasks[task_id]["progress"] = 55
        translated_json_path = os.path.join(whisper_dir, "spanish_translated.json")
        if os.path.exists(translated_json_path):
            print(f"Skipping translation, using cached: {translated_json_path}")
            with open(translated_json_path, 'r', encoding='utf-8') as f:
                translated_data = json.load(f)
            translated_chunks = translated_data.get("chunks", [])
        else:
            translated_chunks = translate_chunks(preprocessed_chunks, model=model)
            translated_data = {
                "text": " ".join([c.get("text", "") for c in translated_chunks]),
                "chunks": translated_chunks
            }
            with open(translated_json_path, "w", encoding="utf-8") as f:
                json.dump(translated_data, f, ensure_ascii=False, indent=2)
            
        # 4. Generate individual Spanish TTS MP3s using VibeVoice
        tasks[task_id]["status"] = "synthesizing"
        tasks[task_id]["progress"] = 75
        if speaker == "cloned_speaker":
            # Extract 1 minute sample from clean vocals wav instead of noisy original audio
            prepare_cloned_voice(vocals_wav_path, orig_json_path)
        mp3_paths = generate_individual_tts(translated_chunks, tts_dir, speaker_name=speaker, task_id=task_id)
        
        # 5. Overlay, synchronize and speed up chunks (Splicing, stretching and overlaying)
        tasks[task_id]["status"] = "synchronizing"
        tasks[task_id]["progress"] = 85
        synced_wav_path = os.path.join(output_dir, "dubbed_synced.wav")
        sync_individual_phrases(translated_chunks, mp3_paths, synced_wav_path, duration_sec)
        
        # 5b. Mix synced Spanish voice and original background instrumental track
        mixed_wav_path = os.path.join(output_dir, "dubbed_mixed.wav")
        mix_voice_and_background(synced_wav_path, background_wav_path, mixed_wav_path)
        
        # 6. Merge dubbed audio and original video track (removing orig audio)
        tasks[task_id]["status"] = "merging"
        tasks[task_id]["progress"] = 90
        output_video_path = os.path.join(output_dir, "video_dubbed.mp4")
        merge_audio_video(video_path, mixed_wav_path, output_video_path)
        
        # 7. QA Verification: transcribe final dubbed WAV and compare against Spanish translation
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
        
        verification_report_path = os.path.join(whisper_dir, "verification_report.json")
        with open(verification_report_path, "w", encoding="utf-8") as f:
            json.dump(verification_report, f, ensure_ascii=False, indent=2)
            
        print(f"QA Verification completed: Accuracy: {ratio*100:.2f}%. Passed: {passed}")
        
        # 8. Finished
        tasks[task_id]["status"] = "completed"
        tasks[task_id]["progress"] = 100
        tasks[task_id]["result"] = {
            "video_url": f"/cache/{task_id}/video_dubbed.mp4",
            "original_json": orig_data,
            "translated_json": translated_data,
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
        request.speaker
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

@app.get("/api/caches")
def list_available_caches():
    valid_caches = []
    if not os.path.exists(CACHE_DIR):
        return []
    for entry in os.listdir(CACHE_DIR):
        entry_path = os.path.join(CACHE_DIR, entry)
        if os.path.isdir(entry_path):
            video_exists = os.path.exists(os.path.join(entry_path, "downloads", "video.mp4")) or os.path.exists(os.path.join(entry_path, "video.mp4"))
            audio_exists = os.path.exists(os.path.join(entry_path, "downloads", "audio.wav")) or os.path.exists(os.path.join(entry_path, "downloads", "audio.wav"))
            if video_exists and audio_exists:
                valid_caches.append(entry)
    return valid_caches

# Mount video cache directory
app.mount("/cache", StaticFiles(directory=CACHE_DIR), name="cache")

# Mount frontend directory last (so / serves index.html)
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
