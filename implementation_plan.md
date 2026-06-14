# Implementation Plan - Video Translator & Dubbing Web App

This project consists of a local-running web application that downloads YouTube videos, transcribes them using the Windows-native `insanely-fast-whisper`, translates the transcription using a local Ollama model, and generates a synchronized Spanish dubbed audio track using Microsoft VibeVoice TTS. All operations are run natively under Windows.

---

## User Review Required

> [!IMPORTANT]
> **Windows Native Execution**: Since Whisper and VibeVoice are installed on the Windows host (`C:\Users\jpzam\...`), the FastAPI server runs natively under Windows. All media files are saved inside the local `cache/` folder in the project root.

> [!IMPORTANT]
> **Audio Synchronization Pipeline**: We have two potential methods to generate and synchronize the Spanish dubbing. Please review the options below and let us know your preference.

### Splicing & Sync Options:
* **Option A: Batch Generation + Second Whisper Pass (Recommended)**
  1. Generate the entire Spanish audio in **one run** of VibeVoice by writing a script file containing all segments (`Speaker 1: hola...\nSpeaker 1: bienvenido...`). This only runs the VibeVoice python script once, avoiding startup loading overhead.
  2. Run `insanely-fast-whisper.exe` on the generated Spanish audio file to get a JSON with the exact timestamps of when the Spanish words were actually spoken.
  3. Run a Python matching script (or Ollama 2B model) to align the original English segments with the Spanish segments.
  4. Use `ffmpeg`/`pydub` to slice the Spanish audio at the detected timestamps, speed-up/slow-down each segment to match the original duration, and stitch them back into a single synchronized track.
  
* **Option B: Persistent Windows TTS API Server + Segment-by-Segment**
  1. Create a tiny Python server (using FastAPI/Flask) running on the Windows Python environment that loads VibeVoice *once* on startup and keeps it in memory.
  2. For each translation segment, the backend calls the Windows TTS API to generate a WAV file for that specific sentence.
  3. The backend stretches/squeezes each WAV segment to match the original duration and overlays it at the original start time.
  4. *Pros*: Trivial alignment, no second Whisper pass.
  5. *Cons*: Requires running a separate background Python server in Windows command prompt in addition to the main server.

---

## Open Questions

> [!WARNING]
> 1. **Default Ollama Model**: Which model would you prefer to use for translating the JSON transcription by default? We saw `qwen3.5:4b` and `gemma4:12b-it-qat` are available on your machine. We recommend `qwen3.5:4b` as it is fast and highly competent.
> 2. **Audio Merging vs. Browser Overlay**: Would you prefer the backend to generate a final video file with the dubbed audio embedded (meaning the browser just plays a single video), or should the browser play the video muted and play the dubbed audio segments dynamically?
>    * *We recommend merging on the server via `ffmpeg`*, as it is much more robust and avoids browser audio sync drifts.

---

## Proposed Changes

The project will be created inside `G:\IA\PROYECTOS\Traductor`.

```
G:\IA\PROYECTOS\Traductor\
├── backend/
│   ├── main.py              # FastAPI server
│   ├── requirements.txt     # Python backend dependencies (yt-dlp, pydub, etc.)
│   ├── whisper_client.py    # Wrapper to call insanely-fast-whisper
│   ├── translator.py        # Ollama JSON translation logic
│   ├── tts_client.py        # Wrapper to call VibeVoice TTS
│   └── audio_processor.py   # Audio alignment, stretching, and merging logic
└── frontend/
    ├── index.html           # Premium UI Structure
    ├── style.css            # Dark mode, neon accents, glassmorphic styles
    └── app.js               # Visualizing video, polling status, and controlling player
```

### Backend

#### [NEW] [main.py](file:///home/clawbot/PROYECTO/IA/Traductor/backend/main.py)
* Initialize a FastAPI application.
* Endpoints:
  * `POST /api/process`: Accepts a YouTube URL.
    1. Downloads video/audio using `yt-dlp` to a shared folder.
    2. Invokes Whisper to transcribe the English audio.
    3. Invokes Ollama to translate the transcription JSON to Spanish.
    4. Invokes VibeVoice TTS to generate Spanish dubbing.
    5. Runs the audio synchronization pipeline to align the Spanish audio with the video.
    6. Combines the synchronized audio and video using `ffmpeg`.
  * `GET /api/status/{task_id}`: Polls the progress of the translation/dubbing task.
  * Serve static files (frontend) and media files (cached videos and audios).

#### [NEW] [requirements.txt](file:///home/clawbot/PROYECTO/IA/Traductor/backend/requirements.txt)
* Core libraries: `fastapi`, `uvicorn`, `yt-dlp`, `pydub`, `requests`.

#### [NEW] [whisper_client.py](file:///home/clawbot/PROYECTO/IA/Traductor/backend/whisper_client.py)
* Logic to translate WSL paths to Windows paths (`wslpath -w`).
* Invokes `cmd.exe /c` with the insanely-fast-whisper activation environment and arguments.

#### [NEW] [translator.py](file:///home/clawbot/PROYECTO/IA/Traductor/backend/translator.py)
* Calls the local Ollama API (`http://127.0.0.1:11434/api/generate` or `/api/chat`).
* Prompts the LLM (e.g. `qwen3.5:4b`) to translate the text in the JSON transcript segment-by-segment, keeping the exact same structure (timestamps, speakers, ids) and returning valid JSON.

#### [NEW] [tts_client.py](file:///home/clawbot/PROYECTO/IA/Traductor/backend/tts_client.py)
* Invokes VibeVoice TTS script using `cmd.exe /c`.
* Supports selecting different speakers (e.g., Frank, Carter, etc.).

#### [NEW] [audio_processor.py](file:///home/clawbot/PROYECTO/IA/Traductor/backend/audio_processor.py)
* Uses `pydub` to slice, adjust speed (time-stretch), and merge the audio segments.
* Slices the dubbed Spanish track at the timestamps indicated by the second Whisper pass.
* Stretches each segment to fit the original segment duration.
* Overlays them on top of a silent background at the correct original timestamps.
* Merges the synchronized dubbed audio track back into the video file using `ffmpeg`.

### Frontend

#### [NEW] [index.html](file:///home/clawbot/PROYECTO/IA/Traductor/frontend/index.html)
* High-end UI structure with a main player viewport and a sidebar.
* Input field for YouTube URL, with a prominent "Translate & Dub" action button.
* Side control panel:
  * Select translation model, target speaker, and toggle options.
* Sidebar with scrolling, interactive subtitles highlighting the current sentence synced with the player.

#### [NEW] [style.css](file:///home/clawbot/PROYECTO/IA/Traductor/frontend/style.css)
* Custom modern styling (dark mode background, neon teal/purple glow, glassmorphic panels, and smooth transitions).

#### [NEW] [app.js](file:///home/clawbot/PROYECTO/IA/Traductor/frontend/app.js)
* Handle video playback, custom events for subtitle highlighting, and AJAX requests to the backend.

---

## Verification Plan

### Automated Tests
- Test Whisper invocation: Run Python script that calls Whisper on a test audio file and outputs JSON.
- Test Ollama translation: Send a dummy JSON to Ollama and verify it translates correctly while keeping JSON syntax.
- Test VibeVoice invocation: Run VibeVoice with a dummy text file and check for a generated `.wav` file.
- Run FastAPI app and verify endpoints.

### Manual Verification
- Paste a YouTube URL in the browser, check download speed, verify transcription, watch the generated dubbed video, and listen to the audio sync.
