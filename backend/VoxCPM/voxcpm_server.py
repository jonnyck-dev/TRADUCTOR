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

# Ensure we can import from src/
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

parser = argparse.ArgumentParser()
parser.add_argument("--model_path", type=str, default="openbmb/VoxCPM2", help="Path to the VoxCPM model checkpoint")
parser.add_argument("--port", type=int, default=8001, help="Port to run the VoxCPM server on")
args, unknown = parser.parse_known_args()

app = FastAPI(title="VoxCPM TTS Model Server")

model = None
lock = threading.Lock()

class TTSRequest(BaseModel):
    text: str
    speaker: str
    output_path: str
    cfg_value: float = 2.0
    inference_timesteps: int = 10
    reference_wav_path: Optional[str] = None
    normalize: bool = False

@app.on_event("startup")
def load_model():
    global model
    print("Initializing VoxCPM TTS Server...")
    print(f"Loading model from: {args.model_path}")
    
    # Import voxcpm inside the load context
    from voxcpm import VoxCPM
    
    # Load model on CUDA, using float16/bfloat16 if supported
    try:
        model = VoxCPM.from_pretrained(
            args.model_path,
            load_denoiser=False
        )
        print("VoxCPM model loaded successfully and ready!")
    except Exception as e:
        print(f"Failed to load VoxCPM model: {e}")
        traceback.print_exc()
        raise e

@app.post("/api/tts")
def generate_tts(request: TTSRequest):
    global model
    if model is None:
        raise HTTPException(status_code=503, detail="Model not initialized")
        
    try:
        with lock:
            print(f"Processing VoxCPM TTS request: speaker='{request.speaker}', text='{request.text[:50]}...', normalize={request.normalize}")
            
            # Map old VibeVoice generic voices to VoxCPM2 prompt descriptions
            speaker_mapping = {
                "en-Frank_man": "(A middle-aged man, deep and steady voice) ",
                "en-Carter_man": "(A young man, warm and clear voice) ",
                "en-Davis_man": "(An older man, mature and serious voice) ",
                "en-Grace_woman": "(A young woman, gentle and sweet voice) ",
                "en-Emma_woman": "(A middle-aged woman, friendly and professional voice) "
            }
            
            ref_path = request.reference_wav_path
            text_to_generate = request.text
            
            # Determine if we use cloning or voice design
            if request.speaker == "cloned_speaker" and ref_path:
                print(f"Using cloning mode with reference WAV: {ref_path}")
            elif request.speaker in speaker_mapping:
                # Prepend the description for voice design
                desc = speaker_mapping[request.speaker]
                text_to_generate = f"{desc}{request.text}"
                ref_path = None
                print(f"Using voice design mode with description: {desc.strip()}")
            elif request.speaker.startswith("("):
                # Description already passed in UI
                ref_path = None
                print(f"Using custom voice design: {request.speaker}")
            else:
                # Fallback to cloning if speaker looks like a path and no ref_path was explicitly passed
                if os.path.exists(request.speaker):
                    ref_path = request.speaker
                    print(f"Using speaker path as reference: {ref_path}")
                else:
                    ref_path = None
                    print("Using default voice design mode")
            
            # Generate speech
            if ref_path:
                wav = model.generate(
                    text=text_to_generate,
                    reference_wav_path=ref_path,
                    cfg_value=request.cfg_value,
                    inference_timesteps=request.inference_timesteps,
                    normalize=request.normalize
                )
            else:
                wav = model.generate(
                    text=text_to_generate,
                    cfg_value=request.cfg_value,
                    inference_timesteps=request.inference_timesteps,
                    normalize=request.normalize
                )
                
            # Ensure target directory exists
            output_dir = os.path.dirname(request.output_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
                
            # Save audio using soundfile
            sf.write(request.output_path, wav, model.tts_model.sample_rate)
            print(f"Saved generated audio to: {request.output_path}")
            
            return {"status": "success", "file": request.output_path}
            
    except Exception as e:
        print(f"Error in VoxCPM TTS generation:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        try:
            torch.cuda.empty_cache()
        except:
            pass

@app.post("/shutdown")
def shutdown():
    print("Received shutdown request. Terminating VoxCPM server...")
    def stop_server():
        import time
        time.sleep(0.5)
        os.kill(os.getpid(), signal.SIGINT)
    
    threading.Thread(target=stop_server).start()
    return {"status": "shutting_down"}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=args.port)
