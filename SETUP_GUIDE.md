# YouTube Pipeline — Manual Setup Guide

## Current Status

| Component | Status | Action |
|-----------|--------|--------|
| Python 3.12+ | OK | - |
| Docker 28.x | OK | - |
| RTX 4070 8GB | OK | nvidia-smi confirmed |
| uv + venv | OK | 184 tests passing |
| Channel Configs | OK | 2 channels verified |
| All Imports | OK | 17 modules loaded |
| Ollama | NOT INSTALLED | Step 1 below |
| FFmpeg | NOT INSTALLED | Step 2 below |
| ComfyUI | NOT INSTALLED | Step 3 below |
| Temporal Server | NOT STARTED | Step 4 below |
| YouTube OAuth | NOT CONFIGURED | Step 5 below |

---

## Step 1: Ollama (LLM - Script Generation)

**URL:** https://ollama.com/download

```powershell
# 1. Download and install from the URL above (Windows installer)

# 2. After install, pull the model:
ollama pull qwen3:14b

# 3. Verify:
ollama run qwen3:14b "Hello, test"

# 4. Check API:
curl http://localhost:11434/api/tags
```

**Expected:** Ollama runs on `localhost:11434`, Qwen3-14B model available.

---

## Step 2: FFmpeg (Video Assembly)

**URL:** https://www.gyan.dev/ffmpeg/builds/

```powershell
# 1. Download "ffmpeg-release-essentials.zip" from the URL above

# 2. Extract to C:\ffmpeg\

# 3. Add to PATH:
#    System Settings > Environment Variables > Path > Add "C:\ffmpeg\bin"

# 4. Restart terminal, verify:
ffmpeg -version
ffmpeg -encoders | findstr nvenc
# Should show: h264_nvenc (NVIDIA NVENC H.264 encoder)
```

**Expected:** `ffmpeg` command available, NVENC encoder listed (RTX 4070).

---

## Step 3: ComfyUI (Image Generation)

**URL:** https://github.com/comfyanonymous/ComfyUI

```powershell
# 1. Clone ComfyUI:
cd C:\
git clone https://github.com/comfyanonymous/ComfyUI.git
cd ComfyUI

# 2. Install dependencies:
pip install -r requirements.txt

# 3. Download SDXL checkpoint:
# Download juggernautXL_v9.safetensors from:
#   https://civitai.com/models/133005/juggernaut-xl
# Place in: C:\ComfyUI\models\checkpoints\

# 4. Start ComfyUI in API mode:
python main.py --listen 0.0.0.0 --port 8188

# 5. Verify API:
curl http://localhost:8188/system_stats
```

**Expected:** ComfyUI API on `localhost:8188`, SDXL checkpoint loaded.

---

## Step 4: Temporal Server (Workflow Orchestration)

```powershell
# Already have Docker. Start Temporal:

docker compose up -d

# Or if no docker-compose.yml exists:
docker run -d --name temporal \
  -p 7233:7233 \
  -p 8080:8080 \
  temporalio/auto-setup:latest

# Verify:
curl http://localhost:7233

# Web UI (mapped to 8081 per project config):
# http://localhost:8080 (or 8081 if remapped)
```

**After Temporal is running, start the FastAPI server:**
```powershell
cd C:\WINDOWS\system32
uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

**Then open:** http://localhost:8000/docs (Swagger UI with all 7 endpoints)

---

## Step 5: YouTube OAuth (Upload)

**URL:** https://console.cloud.google.com/apis/library/youtube.googleapis.com

```powershell
# 1. Go to Google Cloud Console (URL above)
# 2. Enable "YouTube Data API v3"
# 3. Create OAuth 2.0 credentials:
#    - Application type: Desktop app
#    - Download client_secrets.json
#    - Place in project root

# 4. Run the auth script (one-time per channel):
uv run python scripts/youtube_auth.py --channel channel_01
uv run python scripts/youtube_auth.py --channel channel_02

# This opens a browser for OAuth consent.
# Tokens saved to data/yt_token_channel_01.json and _02.json
```

---

## Step 6: TTS Setup

### Option A: CosyVoice2 (Channel 01 default)
```powershell
# Follow: https://github.com/FunAudioLLM/CosyVoice
git clone https://github.com/FunAudioLLM/CosyVoice.git
cd CosyVoice
pip install -e .
```

### Option B: Kokoro (Channel 02 default)
```powershell
# Follow: https://github.com/hexgrad/kokoro
pip install kokoro
```

---

## Quick Verification Checklist

After all steps, run this to verify everything:

```powershell
cd C:\WINDOWS\system32

# 1. Tests still pass:
uv run python -m pytest tests/ -v --tb=short

# 2. Server starts:
uv run uvicorn src.main:app --reload

# 3. Trigger a test pipeline (from another terminal):
curl -X POST http://localhost:8000/api/pipeline/trigger \
  -H "Content-Type: application/json" \
  -d '{"topic": "test video", "channel_id": "channel_01"}'

# 4. Check status:
curl http://localhost:8000/api/pipeline/status/{workflow_id_from_step_3}
```

---

## .env Configuration

Copy and fill in:
```powershell
copy .env.example .env
```

Key variables:
```
TEMPORAL_HOST=localhost:7233
COMFYUI_URL=http://localhost:8188
OLLAMA_URL=http://localhost:11434
FAL_KEY=           # Optional - for cloud video gen (channel_02)
COST_LOG_PATH=data/cost_log.json
```
