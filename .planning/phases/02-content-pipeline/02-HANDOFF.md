# Phase 2 Handoff — Session 3 → Session 4

## Status
- **Phase 2**: COMPLETE (7/7 plans, 184 tests, 11/11 verified)
- **Branch**: `geben147-create/full_vid-auto_4.2.26_opus`
- **GitHub**: https://github.com/geben147-create/full_vid-auto_4.2.26_opus
- **All code pushed**: Yes

## Next Task for Session 4
**Install & test external dependencies manually:**

### 1. Ollama (LLM)
```powershell
# Check if installed:
ollama --version
# If not:
winget install Ollama.Ollama
# Then:
ollama pull qwen3:14b
# Verify:
curl http://localhost:11434/api/tags
```

### 2. FFmpeg (Video Assembly)
```powershell
# Check:
ffmpeg -version
# If not: download from https://www.gyan.dev/ffmpeg/builds/
# Extract to C:\ffmpeg\, add C:\ffmpeg\bin to PATH
# Verify NVENC:
ffmpeg -encoders 2>&1 | findstr nvenc
```

### 3. ComfyUI (Image Generation)
```powershell
cd C:\
git clone https://github.com/comfyanonymous/ComfyUI.git
cd ComfyUI
pip install -r requirements.txt
# Download SDXL checkpoint to models/checkpoints/
python main.py --listen 0.0.0.0 --port 8188
# Verify: curl http://localhost:8188/system_stats
```

### 4. Temporal Server
```powershell
docker run -d --name temporal -p 7233:7233 -p 8080:8080 temporalio/auto-setup:latest
```

### 5. Start the Pipeline
```powershell
cd C:\WINDOWS\system32
uv run uvicorn src.main:app --reload
# Open http://localhost:8000/docs
```

### 6. Test End-to-End
```powershell
curl -X POST http://localhost:8000/api/pipeline/trigger \
  -H "Content-Type: application/json" \
  -d '{"topic": "한국의 전통 음식 TOP 10", "channel_id": "channel_01"}'
```

## Files Created This Session
- `dashboard.html` — Visual pipeline dashboard
- `SETUP_GUIDE.md` — Manual installation guide
- `.planning/phases/02-content-pipeline/02-VERIFICATION.md` — 11/11 passed

## Known Issues
- `channel_02.yaml` uses `llm_model: together:qwen3-8b` but only `local:*` LLM providers are implemented (NotImplementedError). Cloud LLM deferred.
- TTS requires CosyVoice2 or Kokoro installed locally
- YouTube upload requires OAuth2 setup via `scripts/youtube_auth.py`

## Phase 3 (After manual testing)
`/gsd:plan-phase 3` — Production Operations (quality gate, batch, calendar, cost dashboard)
