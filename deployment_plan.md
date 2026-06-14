# Deployment Plan - Cloud & GitHub Portability

This document outlines the architectural changes needed to make the YouTube Video Translator & Dubbing application self-contained, portable, and deployable on any local machine or cloud server (Linux/Windows) with GPU/CPU support.

---

## User Review Required

> [!IMPORTANT]
> **Submodule Integration**: VibeVoice code and its model checkpoints need to be packaged within the project repo.
> * We will include VibeVoice as a git submodule under `backend/vibevoice/`.
> * Large model checkpoints (`VibeVoice-1.5B`, `VibeVoice-Realtime-0.5B`) should **not** be checked into GitHub due to size limitations. Instead, they will be downloaded dynamically at build/startup time using Hugging Face CLI or python script.

> [!IMPORTANT]
> **GPU / CUDA Dependencies**: Running deep learning models in production requires PyTorch with CUDA support.
> * For local development, standard `pip install` works.
> * For production cloud servers, we must use **Docker** with the `nvidia-container-toolkit` enabled to pass the host GPU to the container.

---

## Open Questions

> [!WARNING]
> 1. **Docker Deployment vs. Shell Setup**: Would you prefer the default production setup to be Docker-based (which packages PyTorch, FFmpeg, Whisper, and VibeVoice automatically in a single container) or a manual script-based setup for Linux/Windows servers?
>    * *We recommend Docker*, as it completely eliminates issues with Python versions, OS-level library mismatches, and GPU driver configurations.
> 2. **Hugging Face Model Access**: VibeVoice models are downloaded from Hugging Face. When deploying to a cloud server, do we want to pull them automatically at boot, or should we include a utility script to pre-download them?

---

## Proposed Changes

To achieve full portability, we will restructure the project to make all dependencies local and configurable via environment variables. For local development on Windows, instead of duplicating massive files, we will use Windows Directory Symbolic Links (`mklink /d`) to link the existing external repositories (VibeVoice, Whisper models) directly into the project workspace:

```
G:\IA\PROYECTOS\Traductor\
├── .env.example             # Configuration template
├── Dockerfile               # Packaging FastAPI + PyTorch + FFmpeg (Future Linux/Cloud)
├── docker-compose.yml       # Composing Backend + Ollama + NVIDIA GPU access
├── setup_symlinks.bat       # Script to link VibeVoice and Whisper folders natively
├── backend/
│   ├── .env                 # Local environment config
│   ├── main.py              # Dynamic path configuration (BASE_DIR)
│   ├── requirements.txt     # Updated with PyTorch, insanely-fast-whisper, etc.
│   ├── whisper_client.py    # Native Windows execution
│   ├── tts_client.py        # Native Windows execution
│   └── vibevoice/           # Linked via mklink /d to C:\Users\jpzam\VibeVoice
└── frontend/
```

### 1. Environment Configuration (`.env`)
We will introduce a `.env` file loaded via `python-dotenv`. All paths will be configurable:
```env
# Server Config
PORT=8000
HOST=0.0.0.0

# Ollama API Endpoint (can point to localhost, cloud VPS, or remote server)
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=gemma4:e2b-it-qat

# Whisper Configuration
# If local, runs native python insanely-fast-whisper. If remote, can point to a Whisper API
WHISPER_MODE=local 

# VibeVoice Configurations
VIBEVOICE_CODE_DIR=backend/vibevoice
VIBEVOICE_MODEL_PATH=backend/vibevoice/checkpoints/VibeVoice-1.5B
VIBEVOICE_DEVICE=cuda  # cuda, cpu, mps

# System Executables
FFMPEG_PATH=ffmpeg  # uses system path by default, can be custom path
```

### 2. Native Whisper Client Integration
Currently, `whisper_client.py` calls the Windows `.exe` via `cmd.exe`. 
For portability, we will update it to run the local Python package `insanely-fast-whisper` directly if not in legacy local-only mode:
```python
import sys
import subprocess
import os

def transcribe_audio(audio_path: str, output_json_path: str, language: str = "English") -> dict:
    # If WHISPER_MODE is local, run native CLI
    if os.getenv("WHISPER_MODE", "local") == "local":
        cmd = f"insanely-fast-whisper --file-name {audio_path} --language {language} --flash True --transcript-path {output_json_path}"
        subprocess.run(cmd, shell=True, check=True)
    # Else fallback to legacy Windows cmd.exe interop mode
```

### 3. Native VibeVoice Integration
Instead of calling a Windows script via command prompt, we will import VibeVoice natively inside the FastAPI python server.
* This keeps the VibeVoice model **loaded in RAM/VRAM** continuously.
* Generating a segment takes milliseconds instead of seconds (no startup overhead).
* Subprocessing is completely avoided.

### 4. Dockerization
We will add a `Dockerfile` that uses `nvidia/cuda` as the base image, installs Python, FFmpeg, installs our dependencies (including PyTorch and insanely-fast-whisper), and downloads the VibeVoice model weights:
```dockerfile
FROM nvidia/cuda:12.1.1-runtime-ubuntu22.04

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3-pip python3-dev ffmpeg git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy and install dependencies
COPY backend/requirements.txt .
RUN pip3 install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
RUN pip3 install --no-cache-dir -r requirements.txt

# Download VibeVoice model checkpoints
RUN python3 -c "from huggingface_hub import snapshot_download; snapshot_download(repo_id='microsoft/VibeVoice-1.5b', local_dir='backend/vibevoice/checkpoints/VibeVoice-1.5B')"

COPY . .

EXPOSE 8000
CMD ["python3", "backend/main.py"]
```

---

## Roadmap & Pending Tasks

> [!NOTE]
> **Current Phase**: We are currently in **Phase 1: Local Verification (Windows Native)**. The priority is to verify the entire system running directly on Windows Host. Future support for standalone Linux servers or Docker is deferred to Phase 2.

### Phase 1: Local Verification (Current)
- [ ] **Launch Application**: Start the local FastAPI server natively on Windows using `python backend/main.py` (or through the Windows venv).
- [ ] **Download Video**: Input a YouTube URL and verify the video is successfully saved to `G:\IA\PROYECTOS\Traductor\cache\{task_id}\video.mp4` and audio extracted to `audio.wav`.
- [ ] **Whisper Transcription**: Verify `whisper_client.py` transcribes the English audio via local Windows `insanely-fast-whisper.exe` (pointing HF_HOME to the linked models directory) and outputs `english_whisper.json`.
- [ ] **Ollama Translation**: Verify `translator.py` translates the JSON chunks into Spanish using `gemma4:e2b-it-qat` and outputs `spanish_translated.json`.
- [ ] **TTS Dubbing**: Verify `tts_client.py` generates the continuous Spanish WAV file via local Windows VibeVoice (either linked or absolute path).
- [ ] **TTS Transcription**: Verify `insanely-fast-whisper` transcribes the generated Spanish WAV to `spanish_whisper.json`.
- [ ] **Synchronization & Merging**: Verify `audio_processor.py` successfully aligns timestamps, time-stretches segments using Windows `ffmpeg.exe`, overlays them, and merges the audio back into the video.
- [ ] **Frontend Player**: Verify that the browser player can stream the cached dubbed video and highlight synced subtitles.

### Phase 2: Portability & Deployment Setup
- [ ] **Environment Setup**: Add `.env.example` and load configs via `python-dotenv`.
- [ ] **Submodule VibeVoice**: Add the VibeVoice code repository as a submodule under `backend/vibevoice`.
- [ ] **Hugging Face Downloader**: Write a python script to automatically download VibeVoice checkpoints at build time.
- [ ] **Refactor Whisper & TTS Clients**: Update clients to run local Python package calls natively (for standalone Linux/Windows servers) instead of relying on WSL-Windows shell interop.
- [ ] **Docker Packaging**: Finalize the `Dockerfile` and `docker-compose.yml` to compose the app and Ollama service with GPU passthrough.
- [ ] **Verify Cloud Deploy**: Test running the container on a cloud VPS (e.g. AWS or RunPod).

