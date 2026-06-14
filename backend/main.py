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
from tts_client import generate_tts
from audio_processor import align_transcripts, create_synchronized_audio, merge_audio_video

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

def download_and_extract(url: str, output_dir: str) -> tuple[str, str]:
    if url.startswith("cache:"):
        cache_id = url.split(":")[1]
        source_dir = os.path.join(CACHE_DIR, cache_id)
        cached_video = os.path.join(source_dir, "video.mp4")
        cached_audio = os.path.join(source_dir, "audio.wav")
        if os.path.exists(cached_video) and os.path.exists(cached_audio):
            print(f"Skipping download, using cached files from {source_dir}")
            # Copy cached translations if available to skip those phases
            import shutil
            for filename in ["english_whisper.json", "spanish_translated.json"]:
                src = os.path.join(source_dir, filename)
                dst = os.path.join(output_dir, filename)
                if os.path.exists(src) and not os.path.exists(dst):
                    try:
                        shutil.copy(src, dst)
                        print(f"Cached {filename} copied to new task directory.")
                    except Exception as e:
                        print(f"Failed to copy cached {filename}: {e}")
            return cached_video, cached_audio
        else:
            raise FileNotFoundError(f"Cached files not found in {source_dir}")

    video_path = os.path.join(output_dir, "video.mp4")
    audio_path = os.path.join(output_dir, "audio.wav")
    
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

def process_translation_task(task_id: str, url: str, model: str, speaker: str):
    try:
        output_dir = os.path.join(CACHE_DIR, task_id)
        os.makedirs(output_dir, exist_ok=True)
        
        # 1. Download YouTube Video & Extract Audio
        tasks[task_id]["status"] = "downloading"
        tasks[task_id]["progress"] = 15
        video_path, audio_path = download_and_extract(url, output_dir)
        
        # Calculate original duration
        audio_segment = AudioSegment.from_wav(audio_path)
        duration_sec = audio_segment.duration_seconds
        
        # 2. Transcribe English Audio
        tasks[task_id]["status"] = "transcribing"
        tasks[task_id]["progress"] = 35
        orig_json_path = os.path.join(output_dir, "english_whisper.json")
        if os.path.exists(orig_json_path):
            print(f"Skipping transcription, using cached: {orig_json_path}")
            with open(orig_json_path, 'r', encoding='utf-8') as f:
                orig_data = json.load(f)
        else:
            orig_data = transcribe_audio(audio_path, orig_json_path, language="English")
        
        # 3. Translate JSON to Spanish using Ollama
        tasks[task_id]["status"] = "translating"
        tasks[task_id]["progress"] = 55
        translated_json_path = os.path.join(output_dir, "spanish_translated.json")
        if os.path.exists(translated_json_path):
            print(f"Skipping translation, using cached: {translated_json_path}")
            with open(translated_json_path, 'r', encoding='utf-8') as f:
                translated_data = json.load(f)
            translated_chunks = translated_data.get("chunks", [])
        else:
            translated_chunks = translate_chunks(orig_data.get("chunks", []), model=model)
            translated_data = {
                "text": " ".join([c.get("text", "") for c in translated_chunks]),
                "chunks": translated_chunks
            }
            with open(translated_json_path, "w", encoding="utf-8") as f:
                json.dump(translated_data, f, ensure_ascii=False, indent=2)
            
        # 4. Generate continuous Spanish TTS using VibeVoice
        tasks[task_id]["status"] = "synthesizing"
        tasks[task_id]["progress"] = 75
        dubbed_wav_path = generate_tts(translated_chunks, output_dir, speaker_name=speaker)
        
        # Get dubbed WAV duration
        dub_segment = AudioSegment.from_wav(dubbed_wav_path)
        dub_duration_sec = dub_segment.duration_seconds
        
        # 5. Transcribe dubbed WAV for audio timestamps
        tasks[task_id]["status"] = "transcribing_dub"
        tasks[task_id]["progress"] = 85
        dub_json_path = os.path.join(output_dir, "spanish_whisper.json")
        dub_data = transcribe_audio(dubbed_wav_path, dub_json_path, language="Spanish")
        
        # 6. Splicing, stretching and overlaying
        tasks[task_id]["status"] = "synchronizing"
        tasks[task_id]["progress"] = 90
        alignment = align_transcripts(translated_chunks, dub_data.get("chunks", []), dub_duration_sec)
        
        synced_wav_path = os.path.join(output_dir, "dubbed_synced.wav")
        create_synchronized_audio(alignment, dubbed_wav_path, synced_wav_path, duration_sec)
        
        # 7. Merge dubbed audio and original video track (removing orig audio)
        tasks[task_id]["status"] = "merging"
        tasks[task_id]["progress"] = 95
        output_video_path = os.path.join(output_dir, "video_dubbed.mp4")
        merge_audio_video(video_path, synced_wav_path, output_video_path)
        
        # 8. Finished
        tasks[task_id]["status"] = "completed"
        tasks[task_id]["progress"] = 100
        tasks[task_id]["result"] = {
            "video_url": f"/cache/{task_id}/video_dubbed.mp4",
            "original_json": orig_data,
            "translated_json": translated_data
        }
        print(f"Task {task_id} completed successfully!")
        
    except Exception as e:
        print(f"Error processing task {task_id}:")
        traceback.print_exc()
        tasks[task_id]["status"] = "failed"
        tasks[task_id]["error"] = str(e)

@app.post("/api/process")
def process_video(request: ProcessRequest, background_tasks: BackgroundTasks):
    task_id = str(uuid.uuid4())
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
            video_exists = os.path.exists(os.path.join(entry_path, "video.mp4"))
            audio_exists = os.path.exists(os.path.join(entry_path, "audio.wav"))
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
