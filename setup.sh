#!/bin/bash
set -e

echo "=========================================================="
echo "  AEGIS Audio Editor / AI Video Dubber"
echo "  Portable Setup (Linux/WSL)"
echo "=========================================================="
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 0. Download portable ffmpeg if not present
echo ""
echo "[0/5] Setting up portable FFmpeg..."
FFMPEG_DIR="backend/bin"
mkdir -p "$FFMPEG_DIR"

if [ ! -f "$FFMPEG_DIR/ffmpeg" ] && [ ! -f "$FFMPEG_DIR/ffmpeg.exe" ]; then
    echo "  - Downloading ffmpeg..."
    if command -v wget &> /dev/null; then
        wget -q "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz" -O /tmp/ffmpeg.tar.xz 2>/dev/null
        if [ -f /tmp/ffmpeg.tar.xz ]; then
            mkdir -p /tmp/ffmpeg_extracted
            tar -xf /tmp/ffmpeg.tar.xz -C /tmp/ffmpeg_extracted 2>/dev/null
            FFMPEG_BIN=$(find /tmp/ffmpeg_extracted -name ffmpeg -type f 2>/dev/null | head -1)
            if [ -n "$FFMPEG_BIN" ]; then
                cp "$FFMPEG_BIN" "$FFMPEG_DIR/ffmpeg"
                chmod +x "$FFMPEG_DIR/ffmpeg"
                echo "  [OK] ffmpeg copied to $FFMPEG_DIR"
            fi
            rm -rf /tmp/ffmpeg.tar.xz /tmp/ffmpeg_extracted
        fi
    elif command -v curl &> /dev/null; then
        curl -sL "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz" -o /tmp/ffmpeg.tar.xz
        if [ -f /tmp/ffmpeg.tar.xz ]; then
            mkdir -p /tmp/ffmpeg_extracted
            tar -xf /tmp/ffmpeg.tar.xz -C /tmp/ffmpeg_extracted 2>/dev/null
            FFMPEG_BIN=$(find /tmp/ffmpeg_extracted -name ffmpeg -type f 2>/dev/null | head -1)
            if [ -n "$FFMPEG_BIN" ]; then
                cp "$FFMPEG_BIN" "$FFMPEG_DIR/ffmpeg"
                chmod +x "$FFMPEG_DIR/ffmpeg"
                echo "  [OK] ffmpeg copied to $FFMPEG_DIR"
            fi
            rm -rf /tmp/ffmpeg.tar.xz /tmp/ffmpeg_extracted
        fi
    fi
    
    if [ ! -f "$FFMPEG_DIR/ffmpeg" ]; then
        echo "  [WARNING] Could not auto-download ffmpeg."
        echo "  Install ffmpeg via your package manager (apt install ffmpeg)"
        echo "  or download from https://ffmpeg.org/download.html"
    fi
else
    echo "  - ffmpeg already exists. Skipping."
fi

# 1. Main venv + dependencies
echo ""
echo "[1/5] Creating main virtual environment..."
python3 -m venv venv 2>/dev/null || python -m venv venv
source venv/bin/activate
pip install --upgrade pip --quiet
pip install -r backend/requirements.txt
echo "[OK] Main environment ready."

# 2. Clone external repos if not present
echo ""
echo "[2/5] Cloning external projects..."

# VibeVoice (community fork)
if [ ! -d "backend/vibevoice/.git" ]; then
    echo "  - Cloning VibeVoice..."
    git clone https://github.com/vibevoice-community/VibeVoice.git backend/vibevoice --depth 1
else
    echo "  - VibeVoice already exists. Skipping."
fi

# Demucs (UVR5-UI fork)
if [ ! -d "backend/demucs/.git" ]; then
    echo "  - Cloning Demucs/UVR5-UI..."
    git clone https://github.com/Eddycrack864/UVR5-UI.git backend/demucs --depth 1
else
    echo "  - Demucs already exists. Skipping."
fi

# 3. Create subproject venvs
echo ""
echo "[3/5] Creating subproject venvs..."

# VoxCPM venv
if [ ! -f "backend/VoxCPM/env_voxcpm/bin/python" ]; then
    echo "  - Creating VoxCPM venv..."
    cd backend/VoxCPM
    python3 -m venv env_voxcpm 2>/dev/null || python -m venv env_voxcpm
    source env_voxcpm/bin/activate
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121 --quiet 2>/dev/null || \
        pip install torch torchvision torchaudio --quiet
    pip install fastapi uvicorn requests pydantic soundfile huggingface_hub --quiet
    deactivate
    cd ../..
    echo "[OK] VoxCPM configured."
else
    echo "  - VoxCPM venv already exists. Skipping."
fi

# VibeVoice venv
if [ ! -f "backend/vibevoice/env_vibevoice/bin/python" ]; then
    echo "  - Creating VibeVoice venv..."
    cd backend/vibevoice
    python3 -m venv env_vibevoice 2>/dev/null || python -m venv env_vibevoice
    source env_vibevoice/bin/activate
    pip install -e . --quiet
    pip install whisperx --quiet
    deactivate
    cd ../..
    echo "[OK] VibeVoice configured."
else
    echo "  - VibeVoice venv already exists. Skipping."
fi

# Demucs venv
if [ ! -f "backend/demucs/env/bin/python" ]; then
    echo "  - Creating Demucs/UVR5-UI venv..."
    cd backend/demucs
    python3 -m venv env 2>/dev/null || python -m venv env
    source env/bin/activate
    pip install --upgrade pip --quiet
    pip install -r requirements.txt --quiet 2>/dev/null || \
        pip install audio-separator==0.16.5 pydub --quiet
    deactivate
    cd ../..
    echo "[OK] Demucs configured."
else
    echo "  - Demucs venv already exists. Skipping."
fi

# 4. Download models from Hugging Face
echo ""
echo "[4/5] Downloading models from Hugging Face..."

# VoxCPM models
if [ ! -f "backend/VoxCPM/pretrained_models/VoxCPM-0.5B/pytorch_model.bin" ]; then
    echo "  - Downloading VoxCPM models..."
    cd backend/VoxCPM
    source env_voxcpm/bin/activate
    python -c "from huggingface_hub import snapshot_download; snapshot_download('openbmb/VoxCPM-0.5B', local_dir='pretrained_models/VoxCPM-0.5B')" 2>/dev/null || \
        echo "[WARNING] Could not auto-download VoxCPM models. Get them from https://huggingface.co/openbmb/VoxCPM-0.5B"
    deactivate
    cd ../..
    echo "[OK] VoxCPM models."
else
    echo "  - VoxCPM models already exist. Skipping."
fi

# VibeVoice models (1.5B + 0.5B)
if [ ! -d "backend/vibevoice/checkpoints/VibeVoice-1.5B/config.json" ]; then
    echo "  - Downloading VibeVoice models..."
    cd backend/vibevoice
    source env_vibevoice/bin/activate
    python -c "from huggingface_hub import snapshot_download; snapshot_download('vibevoice/VibeVoice-1.5B', local_dir='checkpoints/VibeVoice-1.5B')" 2>/dev/null || \
        echo "[WARNING] Could not auto-download VibeVoice-1.5B. Get it from https://huggingface.co/vibevoice/VibeVoice-1.5B"
    python -c "from huggingface_hub import snapshot_download; snapshot_download('microsoft/VibeVoice-Realtime-0.5B', local_dir='checkpoints/VibeVoice-Realtime-0.5B')" 2>/dev/null
    deactivate
    cd ../..
    echo "[OK] VibeVoice models."
else
    echo "  - VibeVoice models already exist. Skipping."
fi

# 5. Check Ollama installation
echo ""
echo "[5/5] Checking Ollama..."
if command -v ollama &> /dev/null; then
    echo "  [OK] Ollama is installed."
else
    echo "  [INFO] Ollama is not installed on this system."
    echo "  Ollama is required for video translation."
    echo ""
    read -p "  > Install Ollama now? (y/n): " install_ollama
    if [ "$install_ollama" = "y" ] || [ "$install_ollama" = "Y" ]; then
        echo "  - Installing Ollama via official script..."
        curl -fsSL https://ollama.com/install.sh | sh 2>/dev/null || \
        echo "  [WARNING] Auto-install failed. Install manually from https://ollama.com/download"
        echo "  [OK] Ollama installed. Start the service with: ollama serve"
    else
        echo "  [SKIP] Install Ollama manually from https://ollama.com/download"
    fi
fi

# Copy .env from example if not exists
if [ ! -f "backend/.env" ] && [ -f ".env.example" ]; then
    cp .env.example backend/.env
    echo "[OK] .env created from .env.example"
fi

echo ""
echo "=========================================================="
echo "  Installation complete!"
echo ""
echo "  To start the server:"
echo "    ./run.sh"
echo ""
echo "  IMPORTANT: Make sure Ollama is running before using"
echo "  the application (run: ollama serve)"
echo ""
echo "  Web server: http://localhost:8000"
echo "=========================================================="
