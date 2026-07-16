import os
import sys
import torch
import traceback
import threading
import signal
import argparse
from typing import Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import soundfile as sf

parser = argparse.ArgumentParser()
parser.add_argument("--model_path", type=str, default="k2-fsa/OmniVoice", help="HuggingFace model ID or local path")
parser.add_argument("--port", type=int, default=8001, help="Port to run the OmniVoice server on")
args, unknown = parser.parse_known_args()

app = FastAPI(title="OmniVoice TTS Server")

model = None
lock = threading.Lock()

LANGUAGE_CODE_MAP = {
    "spanish": "es", "english": "en", "japanese": "ja", "portuguese": "pt",
    "french": "fr", "german": "de", "italian": "it", "korean": "ko", "chinese": "zh",
}

class TTSRequest(BaseModel):
    text: str
    speaker: str
    output_path: str
    reference_wav_path: Optional[str] = None
    ref_text: Optional[str] = None
    target_language: str = "Spanish"
    num_step: int = 16
    guidance_scale: float = 2.0

@app.on_event("startup")
def load_model():
    global model
    print("Initializing OmniVoice TTS Server...")
    print(f"Loading model from: {args.model_path}")

    from omnivoice import OmniVoice

    try:
        model = OmniVoice.from_pretrained(
            args.model_path,
            device_map="cuda:0" if torch.cuda.is_available() else "cpu",
            dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
            load_asr=False,
        )
        print("OmniVoice model loaded successfully and ready!")
    except Exception as e:
        print(f"Failed to load OmniVoice model: {e}")
        traceback.print_exc()
        raise e

@app.post("/api/tts")
def generate_tts(request: TTSRequest):
    global model
    if model is None:
        raise HTTPException(status_code=503, detail="Model not initialized")

    try:
        with lock:
            print(f"Processing OmniVoice TTS request: speaker='{request.speaker}', text='{request.text[:50]}...'")

            ref_path = request.reference_wav_path
            text_to_generate = request.text

            lang_code = LANGUAGE_CODE_MAP.get(request.target_language.lower(), request.target_language.lower())

            if request.speaker == "cloned_speaker" and ref_path and os.path.exists(ref_path):
                print(f"Using voice cloning mode with reference WAV: {ref_path}")
                ref_text = request.ref_text or " "
                audio = model.generate(
                    text=text_to_generate,
                    ref_audio=ref_path,
                    ref_text=ref_text,
                    language=lang_code,
                    num_step=request.num_step,
                    guidance_scale=request.guidance_scale,
                )
            else:
                instruct = request.speaker
                print(f"Using voice design mode with instruct: {instruct}")
                audio = model.generate(
                    text=text_to_generate,
                    instruct=instruct,
                    language=lang_code,
                    num_step=request.num_step,
                    guidance_scale=request.guidance_scale,
                )

            output_dir = os.path.dirname(request.output_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)

            sf.write(request.output_path, audio[0], 24000)
            print(f"Saved generated audio to: {request.output_path}")

            return {"status": "success", "file": request.output_path}

    except Exception as e:
        print(f"Error in OmniVoice TTS generation:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        try:
            torch.cuda.empty_cache()
        except:
            pass

@app.post("/shutdown")
def shutdown():
    print("Received shutdown request. Terminating OmniVoice server...")
    def stop_server():
        import time
        time.sleep(0.5)
        os.kill(os.getpid(), signal.SIGINT)

    threading.Thread(target=stop_server).start()
    return {"status": "shutting_down"}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=args.port)
