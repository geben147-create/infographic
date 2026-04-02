# Phase 2: Content Pipeline — Research

**Researched:** 2026-04-02
**Domain:** Ollama/Qwen3 script gen, ComfyUI SDXL, IndexTTS-2/MeloTTS, ffmpeg-python, fal.ai WAN i2v, YouTube Data API v3, Pillow thumbnail, Temporal activity patterns
**Confidence:** HIGH (stack verified against pip registry, official docs, and GitHub)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

No CONTEXT.md exists for Phase 2 yet — constraints below are inherited from CLAUDE.md and Phase 1 locked decisions that Phase 2 must respect.

### Locked Decisions (from Phase 1 — carry forward)

- **D-01:** Source code under `src/` with feature-module structure: `workflows/`, `activities/`, `models/`, `workers/`, `services/`, `api/`, `main.py`, `config.py`
- **D-02:** Temporal server via Docker Compose using `temporalio/auto-setup` image.
- **D-03:** Temporal connection config in `src/config.py` via Pydantic Settings. Local default: `localhost:7233`.
- **D-04:** SQLModel tables: `content_items`, `pipeline_runs`, `sync_log`. Alembic migrations for new columns.
- **D-05:** SQLModel + Alembic. `DATABASE_URL` env var (default: `data/pipeline.db`).
- **D-06:** Three Task Queues: `gpu-queue` (maxConcurrent=1), `cpu-queue` (maxConcurrent=4), `api-queue` (maxConcurrent=8).
- **D-07:** Activities registered via `@activity.defn` + worker registration — not by convention.
- **D-13:** Artifact directory: `data/pipeline/{workflow_run_id}/` with subdirs `scripts/`, `images/`, `audio/`, `video/`, `thumbnails/`, `final/`.
- **D-14:** Cleanup deletes `scripts/`, `images/`, `audio/`, `video/`, `thumbnails/` after final MP4 confirmed. Never deletes `data/pipeline.db` or `data/cost_log.json`.
- **D-15:** `data/` is gitignored.
- **D-16:** `uv` for dependency management. `pyproject.toml` only.
- **D-18:** `.env` file for secrets. `.env.example` in git. `.env` gitignored.
- **D-19:** `pytest tests/ -v --cov=src --cov-report=term-missing`.

### Stack Decisions (from CLAUDE.md)

- **Script gen:** Qwen3-14B via Ollama (local, `ollama pull qwen3:14b`)
- **Image gen:** SDXL via ComfyUI headless API (local, `localhost:8188`)
- **TTS:** IndexTTS-2 (primary, Korean native); MeloTTS (lightweight fallback)
- **Video assembly:** ffmpeg-python 0.2.0 + system FFmpeg with NVENC
- **Video gen (optional):** fal.ai WAN i2v model — `fal-ai/wan-i2v`; toggle via channel config; Ken Burns fallback
- **YouTube upload:** google-api-python-client + OAuth2
- **Thumbnail:** SDXL + Pillow text overlay
- **Multi-channel config:** Pydantic frozen model, channel_id parameter routing
- **Cost tracking:** real-time display + `data/cost_log.json`

### Claude's Discretion (Phase 2)

- Exact Pydantic model fields for ChannelConfig (beyond what requirements name)
- Whether to use Ollama `/api/generate` or `/api/chat` for script generation
- Exact ffmpeg filter chains for Ken Burns and transitions
- IndexTTS-2 deployment mode (subprocess call vs gradio_client vs direct Python import)
- Exact script JSON schema field names (beyond: title, description, narration, image_prompt, duration, tags)
- Number of plans to split Phase 2 into

### Deferred Ideas (OUT OF SCOPE for Phase 2)

- Quality gate human-in-the-loop — Phase 3, OPS-01/OPS-02
- Batch processing mode — Phase 3, OPS-03
- Content calendar / scheduled workflows — Phase 3, OPS-04
- Cost tracking dashboard — Phase 3, OPS-05/OPS-06
- VibeVoice multi-character TTS — v2
- LoRA per channel — v2 (after pipeline stabilization)
- A/B thumbnail testing — v2
- Trend topic discovery — v2
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PIPE-01 | Topic → Qwen3-14B → structured script JSON (title, description, per-scene narration+image_prompt+duration, tags) | Ollama `/api/generate` with JSON schema format param; Jinja2 prompt templates per channel |
| PIPE-02 | Each scene → ComfyUI SDXL image (headless API) | ComfyUI WebSocket + `/prompt` POST + `/history` poll + `/view` download; workflow JSON per channel checkpoint |
| PIPE-03 | Each scene narration → IndexTTS-2 Korean TTS audio file | `indextts.infer_v2.IndexTTS2.infer()` Python API; reference audio per channel voice; MeloTTS fallback |
| PIPE-04 | FFmpeg assembles image+audio+transitions → final MP4 (NVENC) | ffmpeg-python 0.2.0; zoompan for Ken Burns; concat demuxer for assembly; `-c:v h264_nvenc` |
| PIPE-05 | YouTube Data API v3 auto-upload with metadata | google-api-python-client; resumable upload via `videos.insert()`; OAuth2 credentials per channel |
| PIPE-06 | SDXL thumbnail + Pillow text overlay → attached to YouTube upload | `thumbnails.set()` API; Pillow 12.x `ImageDraw` + `ImageFont`; max 2MB JPEG/PNG |
| VGEN-01 | fal.ai WAN i2v generates scene video clips when API key set; Ken Burns fallback when absent | `fal_client.run_async("fal-ai/wan-i2v", ...)` + `submit_async()` for cost events; zoompan fallback |
| VGEN-02 | Per-video cost shown real-time + written to cost_log.json | fal_client `InProgress`/`Completed` events; `data/cost_log.json` append per pipeline run |
| VGEN-03 | Channel config can toggle video gen on/off | `ChannelConfig.vgen_enabled: bool = False` field; activity checks config before calling fal.ai |
| CHAN-01 | Channel config profiles (niche, checkpoint, LoRA, TTS voice, prompt templates, thumbnail style, tags, schedule) as Pydantic frozen model | `class ChannelConfig(BaseModel, frozen=True)` with all listed fields; loaded from YAML/JSON per channel_id |
| CHAN-02 | Single workflow code handles all channels via channel_id parameter | `ContentPipelineWorkflow.run(params: PipelineParams)` where `PipelineParams.channel_id` drives all config lookups |
</phase_requirements>

---

## Summary

Phase 2 converts the Phase 1 skeleton into a functioning end-to-end content production system. A single `ContentPipelineWorkflow` Temporal workflow accepts a topic and channel_id, then chains 8–10 Temporal Activities across the three existing task queues. GPU activities (script gen, image gen, TTS) run serially on the gpu-queue; media assembly and cost logging run on cpu-queue; YouTube upload runs on api-queue.

The most complex integration is ComfyUI: it requires either a WebSocket client (preferred for event-driven completion) or HTTP polling against `/history/{prompt_id}`. The ComfyUI workflow JSON is channel-specific (different SDXL checkpoints per channel), so it must be loaded from a per-channel template file and patched at runtime with the scene's image prompt. IndexTTS-2 provides the primary Korean TTS path via a direct Python import (`indextts.infer_v2.IndexTTS2`), but it is a large model (4.7GB weights) that requires a separate clone and setup step. MeloTTS is a clean fallback for Korean (`TTS(language='KR')`).

The fal.ai integration is gated: when `FAL_KEY` env var is set AND `channel.vgen_enabled=True`, scenes use `fal-ai/wan-i2v` image-to-video ($0.20–0.40/video depending on resolution); otherwise, ffmpeg-python zoompan produces Ken Burns clips from the SDXL still. Cost tracking appends to `data/cost_log.json` with per-run totals.

**Primary recommendation:** Implement the pipeline as a single `ContentPipelineWorkflow` with one Activity per pipeline stage. Use channel YAML config files loaded at workflow start. Use ComfyUI WebSocket (not polling) for image generation to detect failures promptly. Use the `fal_client.submit_async()` event stream for real-time cost tracking. Do not run IndexTTS-2 and ComfyUI simultaneously — both compete for RTX 4070 VRAM, and gpu-queue maxConcurrent=1 already serializes them.

---

## Standard Stack

### Core (all Phase 2 additions to pyproject.toml)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `fal-client` | 0.13.2 | fal.ai WAN i2v video generation | Official Python client; async event stream for cost tracking |
| `httpx` | 0.28.1 | Async HTTP client for Ollama + ComfyUI APIs | Already in ecosystem; native asyncio; replaces requests |
| `Pillow` | 12.2.0 | Thumbnail image manipulation, text overlay | Industry standard; `ImageDraw`, `ImageFont`, JPEG export |
| `ffmpeg-python` | 0.2.0 | FFmpeg Python wrapper (filter graphs) | Composable filter chains; zoompan, concat, NVENC encoding |
| `moviepy` | 2.2.1 | High-level video editing for crossfades | v2 is current API; simpler crossfade compositing than raw ffmpeg-python |
| `google-api-python-client` | 2.193.0 | YouTube Data API v3 upload + thumbnails.set | Official Google client; handles resumable uploads, OAuth2 |
| `google-auth-oauthlib` | latest | OAuth2 flow for YouTube | Required companion to google-api-python-client for user OAuth |
| `Jinja2` | 3.1.6 | Prompt templates per channel/niche | Already in CLAUDE.md stack; `Environment(loader=FileSystemLoader(...))` |
| `pyyaml` | 6.x | Load channel config YAML files | Clean human-editable config format; Pydantic model_validate() |
| `websocket-client` | 1.x | ComfyUI WebSocket connection | Required for ComfyUI ws:// event stream |

### Supporting (system dependencies — not pip)

| Dependency | How to Install | Notes |
|------------|---------------|-------|
| FFmpeg 7.x with NVENC | `winget install Gyan.FFmpeg` or `choco install ffmpeg` | Must have `h264_nvenc` encoder; verify with `ffmpeg -encoders \| grep nvenc` |
| Ollama | `winget install Ollama.Ollama` | Exposes OpenAI-compatible API at `http://localhost:11434` |
| ComfyUI | `git clone https://github.com/comfyanonymous/ComfyUI` + `pip install -r requirements.txt` | Runs at `http://localhost:8188`; headless mode `--listen 0.0.0.0` |
| IndexTTS-2 | `git clone https://github.com/index-tts/index-tts` + `uv sync` + `hf download IndexTeam/IndexTTS-2 --local-dir=checkpoints` | 4.7GB weights; separate repo install |
| Qwen3:14b model | `ollama pull qwen3:14b` (9.3GB) | After Ollama is running |

**Installation (pip additions):**
```bash
uv add fal-client httpx Pillow ffmpeg-python moviepy google-api-python-client google-auth-oauthlib pyyaml websocket-client
```

**Version verification (confirmed against PyPI registry 2026-04-02):**
- fal-client: 0.13.2 (latest)
- httpx: 0.28.1 (latest)
- Pillow: 12.2.0 (latest)
- ffmpeg-python: 0.2.0 (latest — unmaintained but stable)
- moviepy: 2.2.1 (latest)
- google-api-python-client: 2.193.0 (latest)
- Jinja2: 3.1.6 (latest)

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| ComfyUI WebSocket | HTTP polling `/history` | WebSocket detects failures immediately; polling adds 1–5s delay and busy loop |
| ffmpeg-python | subprocess raw | ffmpeg-python composable graphs are cleaner for multi-filter chains; fallback to subprocess only if ffmpeg-python bugs out |
| moviepy | ffmpeg crossfade filters directly | moviepy 2.x crossfade is simpler Python; can be removed if NVENC pipeline is preferred end-to-end |
| MeloTTS | CosyVoice | MeloTTS has confirmed Korean `TTS(language='KR')` API; CosyVoice 3 less clear on programmatic Korean access |
| fal-client | httpx direct | fal-client handles auth, queue events, retries; use direct httpx only if fal-client breaks |

---

## Architecture Patterns

### Recommended Project Structure (Phase 2 additions)

```
src/
├── activities/
│   ├── script_gen.py       # PIPE-01: Ollama Qwen3 → script JSON
│   ├── image_gen.py        # PIPE-02: ComfyUI SDXL per scene
│   ├── tts.py              # PIPE-03: IndexTTS-2 / MeloTTS per scene
│   ├── video_assembly.py   # PIPE-04: ffmpeg-python MP4 assembly
│   ├── video_gen.py        # VGEN-01/02: fal.ai WAN i2v + cost tracking
│   ├── thumbnail.py        # PIPE-06: SDXL thumbnail + Pillow text overlay
│   ├── youtube_upload.py   # PIPE-05: YouTube API upload + thumbnail attach
│   ├── pipeline.py         # (existing — setup_pipeline_dirs)
│   ├── cleanup.py          # (existing — cleanup_intermediate_files)
│   └── sheets.py           # (existing)
├── workflows/
│   ├── content_pipeline.py # ContentPipelineWorkflow (new main workflow)
│   └── pipeline_validation.py  # (existing)
├── services/
│   ├── comfyui_client.py   # ComfyUI WebSocket + HTTP client wrapper
│   ├── ollama_client.py    # Ollama /api/generate wrapper
│   ├── cost_tracker.py     # cost_log.json read/write
│   ├── db_service.py       # (existing)
│   └── sheets_service.py   # (existing)
├── channel_configs/
│   ├── channel_01.yaml     # Example channel config
│   └── channel_02.yaml     # Second channel for CHAN-02 test
├── models/
│   ├── channel_config.py   # ChannelConfig Pydantic frozen model (CHAN-01)
│   ├── script.py           # ScriptScene, Script Pydantic models
│   └── ...                 # (existing)
├── prompt_templates/
│   ├── script_default.j2   # Default Jinja2 script gen prompt
│   └── script_finance.j2   # Example channel-specific prompt
└── config.py               # (add OLLAMA_URL, COMFYUI_URL, FAL_KEY, YT_* env vars)

data/
├── pipeline.db
├── cost_log.json           # Appended per run (VGEN-02)
└── pipeline/{run_id}/
    ├── scripts/            # script.json
    ├── images/             # scene_01.png, scene_02.png, ...
    ├── audio/              # scene_01.wav, scene_02.wav, ...
    ├── video/              # scene_01.mp4 (ken burns or WAN clip)
    ├── thumbnails/         # thumbnail.png
    └── final/              # final_video.mp4
```

### Pattern 1: ContentPipelineWorkflow Activity Chain

**What:** A single `@workflow.defn` class chains activities sequentially. Each activity is idempotent (checks if output file already exists before re-generating). The workflow carries `run_dir: str` so every activity knows its artifact path.

**When to use:** Any multi-step GPU pipeline with per-scene loops.

```python
# Source: Temporal Python SDK pattern (Activity-per-Service)
@workflow.defn
class ContentPipelineWorkflow:
    @workflow.run
    async def run(self, params: PipelineParams) -> PipelineResult:
        # Step 1: Setup dirs (cpu-queue) — reuse from Phase 1
        run_dir = await workflow.execute_activity(
            "setup_pipeline_dirs",
            SetupDirsInput(workflow_run_id=params.run_id),
            task_queue="cpu-queue",
            start_to_close_timeout=timedelta(seconds=30),
        )

        # Step 2: Generate script (gpu-queue — Ollama uses GPU)
        script = await workflow.execute_activity(
            "generate_script",
            ScriptGenInput(topic=params.topic, channel_id=params.channel_id,
                           run_dir=run_dir.base_path),
            task_queue="gpu-queue",
            start_to_close_timeout=timedelta(minutes=5),
        )

        # Step 3: Per-scene image + TTS (gpu-queue, sequential due to maxConcurrent=1)
        for i, scene in enumerate(script.scenes):
            await workflow.execute_activity(
                "generate_scene_image",
                ImageGenInput(scene_index=i, prompt=scene.image_prompt,
                              channel_id=params.channel_id, run_dir=run_dir.base_path),
                task_queue="gpu-queue",
                start_to_close_timeout=timedelta(minutes=3),
            )
            await workflow.execute_activity(
                "generate_tts_audio",
                TTSInput(scene_index=i, text=scene.narration,
                         channel_id=params.channel_id, run_dir=run_dir.base_path),
                task_queue="gpu-queue",
                start_to_close_timeout=timedelta(minutes=5),
            )

        # Step 4: Video clips (gpu-queue: Ken Burns or fal.ai)
        for i, scene in enumerate(script.scenes):
            await workflow.execute_activity(
                "generate_scene_video",
                VideoGenInput(scene_index=i, channel_id=params.channel_id,
                              run_dir=run_dir.base_path,
                              image_path=f"{run_dir.base_path}/images/scene_{i:02d}.png"),
                task_queue="gpu-queue",  # fal.ai calls go via api-queue variant
                start_to_close_timeout=timedelta(minutes=10),
            )

        # Step 5: Thumbnail (gpu-queue)
        await workflow.execute_activity(
            "generate_thumbnail",
            ThumbnailInput(title=script.title, channel_id=params.channel_id,
                           run_dir=run_dir.base_path),
            task_queue="gpu-queue",
            start_to_close_timeout=timedelta(minutes=3),
        )

        # Step 6: Assemble MP4 (cpu-queue)
        await workflow.execute_activity(
            "assemble_video",
            AssemblyInput(scene_count=len(script.scenes), run_dir=run_dir.base_path),
            task_queue="cpu-queue",
            start_to_close_timeout=timedelta(minutes=10),
        )

        # Step 7: YouTube upload (api-queue)
        result = await workflow.execute_activity(
            "upload_to_youtube",
            UploadInput(script=script, channel_id=params.channel_id,
                        run_dir=run_dir.base_path),
            task_queue="api-queue",
            start_to_close_timeout=timedelta(minutes=15),
        )

        # Step 8: Cleanup (cpu-queue) — reuse from Phase 1
        await workflow.execute_activity(
            "cleanup_intermediate_files",
            CleanupInput(workflow_run_id=params.run_id),
            task_queue="cpu-queue",
            start_to_close_timeout=timedelta(seconds=30),
        )
        return result
```

### Pattern 2: ChannelConfig Pydantic Frozen Model (CHAN-01)

**What:** A frozen Pydantic model loaded from YAML at workflow start. Passed as serialized dict through Temporal (frozen models cannot be mutated accidentally).

```python
# Source: Pydantic v2 docs — frozen=True prevents mutation
class ChannelConfig(BaseModel, frozen=True):
    channel_id: str
    niche: str
    language: str = "ko"
    sdxl_checkpoint: str = "sd_xl_base_1.0.safetensors"
    lora: str | None = None
    tts_voice_reference: str = "voices/default_ko.wav"  # path to reference wav
    tts_engine: str = "indextts2"  # or "melotts"
    prompt_template: str = "script_default.j2"
    thumbnail_style: str = "default"
    tags: list[str] = []
    vgen_enabled: bool = False
    youtube_credentials_path: str = ""  # path to OAuth2 json

def load_channel_config(channel_id: str) -> ChannelConfig:
    path = Path(f"src/channel_configs/{channel_id}.yaml")
    data = yaml.safe_load(path.read_text())
    return ChannelConfig.model_validate(data)
```

### Pattern 3: Ollama Script Generation with Structured Output

**What:** Call Ollama's `/api/generate` with a JSON schema `format` param to get deterministic script JSON.

```python
# Source: Ollama REST API docs — format=JSON schema object
async def generate_script(topic: str, template: str) -> Script:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "qwen3:14b",
                "prompt": template,  # Jinja2-rendered, includes topic
                "stream": False,
                "format": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                        "tags": {"type": "array", "items": {"type": "string"}},
                        "scenes": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "narration": {"type": "string"},
                                    "image_prompt": {"type": "string"},
                                    "duration_seconds": {"type": "number"}
                                },
                                "required": ["narration", "image_prompt", "duration_seconds"]
                            }
                        }
                    },
                    "required": ["title", "description", "tags", "scenes"]
                }
            },
            timeout=300.0,  # Qwen3-14B can take 60-120s for first token
        )
    raw = response.json()["response"]
    return Script.model_validate_json(raw)
```

### Pattern 4: ComfyUI Image Generation via WebSocket

**What:** Submit workflow JSON to `/prompt`, then listen on WebSocket until `executing` event with `node=None` signals completion, then fetch image via `/view`.

```python
# Source: ComfyUI websockets_api_example.py
import uuid, json, websocket, httpx

def generate_image_comfyui(
    prompt_workflow: dict,  # pre-loaded SDXL workflow JSON, patched with image_prompt
    server: str = "localhost:8188",
) -> bytes:
    client_id = str(uuid.uuid4())
    ws = websocket.WebSocket()
    ws.connect(f"ws://{server}/ws?clientId={client_id}")

    # Submit prompt
    resp = httpx.post(f"http://{server}/prompt",
                      json={"prompt": prompt_workflow, "client_id": client_id})
    prompt_id = resp.json()["prompt_id"]

    # Wait for completion via WebSocket
    while True:
        msg = json.loads(ws.recv())
        if msg["type"] == "executing":
            if msg["data"]["node"] is None and msg["data"]["prompt_id"] == prompt_id:
                break

    # Retrieve output image
    history = httpx.get(f"http://{server}/history/{prompt_id}").json()
    outputs = history[prompt_id]["outputs"]
    for node_id, node_output in outputs.items():
        if "images" in node_output:
            img = node_output["images"][0]
            image_bytes = httpx.get(
                f"http://{server}/view",
                params={"filename": img["filename"], "subfolder": img["subfolder"],
                        "type": img["type"]}
            ).content
            return image_bytes
    raise RuntimeError("No image output found in ComfyUI history")
```

### Pattern 5: fal.ai WAN i2v with Real-Time Cost Events (VGEN-01/02)

**What:** Use `fal_client.submit_async()` event stream to track generation progress and extract cost from `Completed` event.

```python
# Source: fal-client GitHub README
import fal_client, asyncio

async def generate_video_clip(image_url: str, prompt: str) -> tuple[str, float]:
    """Returns (video_url, cost_usd)"""
    handle = await fal_client.submit_async(
        "fal-ai/wan-i2v",
        arguments={
            "image_url": image_url,
            "prompt": prompt,
            "resolution": "480p",   # $0.20 vs $0.40 for 720p
            "num_frames": 81,
        }
    )
    cost = 0.0
    async for event in handle.iter_events(with_logs=True):
        if isinstance(event, fal_client.Queued):
            print(f"Queue position: {event.position}")
        elif isinstance(event, fal_client.Completed):
            # fal Completed event contains billing info in some models
            pass
    result = await handle.get()
    video_url = result["video"]["url"]
    # WAN i2v at 480p = $0.20 fixed, 720p = $0.40
    cost = 0.20 if "480p" in str(arguments) else 0.40
    return video_url, cost
```

### Pattern 6: Ken Burns Fallback (VGEN-01 off path)

**What:** When fal.ai is disabled or key is absent, create a video clip from a still image using FFmpeg zoompan filter.

```python
# Source: FFmpeg zoompan filter documentation
import ffmpeg

def ken_burns_clip(image_path: str, output_path: str,
                   duration_seconds: float = 5.0) -> None:
    """Create a slow zoom video clip from a still image."""
    fps = 25
    total_frames = int(duration_seconds * fps)
    (
        ffmpeg
        .input(image_path, loop=1, t=duration_seconds)
        .filter("zoompan",
                z="min(zoom+0.0015,1.5)",
                d=total_frames,
                x="iw/2-(iw/zoom/2)",
                y="ih/2-(ih/zoom/2)",
                s="1920x1080")
        .output(output_path, vcodec="h264_nvenc", r=fps,
                pix_fmt="yuv420p", t=duration_seconds)
        .overwrite_output()
        .run()
    )
```

### Pattern 7: YouTube Upload + Thumbnail (PIPE-05/06)

**What:** Resumable multipart upload via `videos.insert()`, then `thumbnails.set()` as a separate call.

```python
# Source: YouTube Data API v3 guide
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials

def upload_video(credentials_path: str, video_path: str, script: Script) -> str:
    creds = Credentials.from_authorized_user_file(credentials_path)
    youtube = build("youtube", "v3", credentials=creds)

    body = {
        "snippet": {
            "title": script.title,
            "description": script.description,
            "tags": script.tags,
            "categoryId": "22",  # People & Blogs
        },
        "status": {"privacyStatus": "private"},  # safe default
    }
    media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    while response is None:
        _, response = request.next_chunk()
    return response["id"]

def set_thumbnail(youtube, video_id: str, thumbnail_path: str) -> None:
    media = MediaFileUpload(thumbnail_path, mimetype="image/jpeg")
    youtube.thumbnails().set(videoId=video_id, media_body=media).execute()
```

### Pattern 8: Pillow Thumbnail Generation (PIPE-06)

**What:** Load SDXL-generated image, overlay title text, save as JPEG.

```python
# Source: Pillow docs — ImageDraw + ImageFont
from PIL import Image, ImageDraw, ImageFont

def add_text_overlay(image_path: str, title: str, output_path: str) -> None:
    img = Image.open(image_path).convert("RGB")
    img = img.resize((1280, 720))  # YouTube recommended thumbnail size
    draw = ImageDraw.Draw(img)
    # Use a bundled TTF — do not rely on system fonts
    font = ImageFont.truetype("assets/fonts/NotoSansKR-Bold.ttf", size=72)
    # Shadow for readability
    draw.text((22, 22), title, font=font, fill=(0, 0, 0))
    draw.text((20, 20), title, font=font, fill=(255, 255, 255))
    img.save(output_path, "JPEG", quality=90)
    # Verify < 2MB (YouTube thumbnails.set limit)
    assert Path(output_path).stat().st_size < 2 * 1024 * 1024
```

### Anti-Patterns to Avoid

- **Parallel GPU activities:** Never `asyncio.gather()` on gpu-queue activities. The `maxConcurrent=1` enforces serialization, but gathering creates redundant Temporal workflow history bloat. Loop sequentially.
- **Storing large blobs in Temporal activity results:** Do not return image bytes from activities. Return file paths only. Temporal serializes activity results into workflow history — large payloads cause memory issues.
- **Calling ComfyUI synchronously inside an async activity:** ComfyUI WebSocket is synchronous (`websocket-client`). Wrap the synchronous call in `asyncio.to_thread()` to avoid blocking the Temporal activity event loop.
- **Hardcoding channel-specific logic in workflow code:** All channel variation must come from `ChannelConfig`. Never `if channel_id == "channel_01":` in workflow or activity code.
- **Mutating ChannelConfig:** The model is `frozen=True`. Create a new config if needed (but there is no reason to mutate it).
- **Running IndexTTS-2 and ComfyUI in the same process:** Both load large GPU models. Keep TTS and image gen as separate activity invocations. The gpu-queue serializes them naturally.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| YouTube resumable upload | Custom multipart HTTP | `googleapiclient.http.MediaFileUpload` | Handles chunk retry, exponential backoff, 403/500 edge cases |
| fal.ai queue polling | `while True: check_status()` | `fal_client.submit_async()` + `iter_events()` | SDK handles auth, retries, websocket reconnect |
| ComfyUI completion detection | HTTP polling loop | WebSocket `ws.recv()` until `node=None` | Polling adds 1–5s latency; WebSocket is event-driven |
| JSON schema validation for scripts | Manual dict parsing | Pydantic `model_validate_json()` | Schema enforcement + typed access at zero cost |
| Structured Ollama output | String parsing + regex | Ollama `format` parameter with JSON schema | Model constrained to valid JSON; no hallucinated fields |
| Korean font rendering for thumbnails | PIL default font | `ImageFont.truetype("NotoSansKR-Bold.ttf")` | PIL default bitmap font cannot render Korean glyphs |
| OAuth2 token refresh | Manual `requests.post()` | `google-auth` library + `Credentials.refresh()` | Handles token expiry, refresh flow, multiple auth backends |
| Cost log writes | Direct `json.dump()` race conditions | Dedicated `CostTracker` service with file locking | Concurrent pipeline runs can corrupt JSON if written naively |

**Key insight:** The YouTube upload pipeline has ~15 documented edge cases (quota exceeded, partial upload recovery, thumbnail size limits, OAuth token expiry). Always use the official client library.

---

## Common Pitfalls

### Pitfall 1: Ollama JSON Format Constraint Not Enough

**What goes wrong:** Even with `format=json_schema`, Qwen3 sometimes wraps the JSON in markdown code fences (` ```json\n{...}\n``` `), especially for creative prompts.

**Why it happens:** RLHF training causes the model to add formatting even when instructed not to. The `format` parameter reduces but does not eliminate this.

**How to avoid:** Strip markdown fences before `model_validate_json()`. Add system prompt instruction: `"Respond ONLY with valid JSON. No markdown, no explanation, no code fences."` Use `response.strip().lstrip("```json").rstrip("```").strip()`.

**Warning signs:** `json.JSONDecodeError` in `generate_script` activity logs.

### Pitfall 2: ComfyUI WebSocket Disconnect on Long Generations

**What goes wrong:** SDXL generation takes 5–10 seconds. If ComfyUI is under load, the WebSocket connection may time out before completion.

**Why it happens:** The `websocket-client` library has a default timeout. Long-running workflows (FLUX Q4 = 45–60s) exceed default keep-alive.

**How to avoid:** Set `ws.settimeout(120)` before connecting. Wrap the recv loop in a try/except for `websocket.WebSocketTimeoutException` and fall back to HTTP polling on `/history/{prompt_id}`.

### Pitfall 3: fal.ai Upload Requirement for Local Images

**What goes wrong:** `fal-ai/wan-i2v` expects `image_url` to be a publicly reachable URL. Passing a local file path causes a 422 error.

**Why it happens:** The fal.ai service fetches the image from the provided URL server-side.

**How to avoid:** Upload the SDXL image to fal.ai CDN first: `image_url = await fal_client.upload_file_async(local_image_path)`. This returns a temporary CDN URL valid for 24h.

**Warning signs:** `422 Unprocessable Entity` from fal.ai with message "failed to fetch image".

### Pitfall 4: NVENC Not Available in ffmpeg Build

**What goes wrong:** `ffmpeg -c:v h264_nvenc` fails with "Encoder h264_nvenc not found" despite RTX 4070 being present.

**Why it happens:** The system FFmpeg may be built without NVIDIA SDK support (common with package manager installs on Windows).

**How to avoid:** Download Gyan's full-build FFmpeg from `https://www.gyan.dev/ffmpeg/builds/` which includes NVENC. Verify: `ffmpeg -encoders | grep nvenc`. Fallback: use `-c:v libx264` (CPU) if NVENC unavailable.

**Warning signs:** ffmpeg exits with error code 1 and "encoder" in stderr.

### Pitfall 5: IndexTTS-2 Korean Support Gap

**What goes wrong:** IndexTTS-2 (official repo: `index-tts/index-tts`) documentation focuses on Chinese and English. Korean support is not explicitly confirmed in the README.

**Why it happens:** IndexTTS-2 is developed by Bilibili (Chinese company); Korean is a secondary target.

**How to avoid:** Test Korean TTS quality early in Plan 1 of Phase 2 before building the full pipeline around it. Have MeloTTS (`TTS(language='KR')`) configured as the fallback. MeloTTS Korean support is confirmed.

**Warning signs:** Garbled/accented Korean output, pronunciation errors on domain-specific vocabulary.

### Pitfall 6: YouTube quota exhaustion (10,000 units/day)

**What goes wrong:** `videos.insert()` costs ~1,600 quota units. `thumbnails.set()` costs ~50 units. With 5 channels × 2 videos = ~8,250 units/day, headroom is tight.

**Why it happens:** YouTube Data API v3 has a hard 10,000 unit/day limit per GCP project.

**How to avoid:** Use one GCP project per channel (each gets 10,000 units). Track quota usage in SQLite. The CLAUDE.md stack notes "Use multiple GCP projects for 5+ channels."

**Warning signs:** `quotaExceeded` error in YouTube API response.

### Pitfall 7: Temporal Activity Results Used as File Contents

**What goes wrong:** Returning image bytes (PNG = 1–4MB) from a Temporal activity causes workflow history to balloon, slowing the Temporal server.

**Why it happens:** Temporal serializes all activity return values into workflow history using the configured data converter.

**How to avoid:** Activities return only file paths (strings). The actual binary files live on disk under `data/pipeline/{run_id}/`. Pass paths between activities, not contents.

### Pitfall 8: ChannelConfig Loading Inside Workflow Code

**What goes wrong:** `Path("src/channel_configs/channel_01.yaml").read_text()` inside a `@workflow.defn` method causes a Temporal determinism violation error.

**Why it happens:** Temporal replays workflow history during recovery; file system access is non-deterministic (file could change).

**How to avoid:** Load `ChannelConfig` inside the first Activity (e.g., `setup_pipeline_dirs` or a new `load_channel_config` activity on cpu-queue), serialize it to JSON, and pass it as a string through the workflow. Activities can access the filesystem freely.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Docker | Temporal server | Yes | 28.0.1 (Desktop-Linux context) | — |
| Ollama (service) | PIPE-01 script gen | Not reachable | — (not found in PATH or localhost:11434) | Manual start: `ollama serve` |
| Ollama qwen3:14b model | PIPE-01 | Not verified | — | Pull required: `ollama pull qwen3:14b` |
| ComfyUI (service) | PIPE-02 image gen | Not reachable | — (localhost:8188 not responding) | Manual start: `python main.py --listen` |
| FFmpeg | PIPE-04 video assembly | Not found in PATH | — | Install via winget/choco; verify NVENC |
| IndexTTS-2 (repo+weights) | PIPE-03 TTS | Not installed | — | Clone + pip install + HF download (4.7GB) |
| fal-client (pip) | VGEN-01/02 | Not installed | 0.13.2 available | `uv add fal-client` |
| httpx (pip) | PIPE-01, PIPE-02 API | Not installed | 0.28.1 available | `uv add httpx` |
| Pillow (pip) | PIPE-06 thumbnail | Not installed | 12.2.0 available | `uv add Pillow` |
| ffmpeg-python (pip) | PIPE-04 | Not installed | 0.2.0 available | `uv add ffmpeg-python` |
| google-api-python-client (pip) | PIPE-05 upload | Not installed | 2.193.0 available | `uv add google-api-python-client` |
| moviepy (pip) | PIPE-04 transitions | Not installed | 2.2.1 available | `uv add moviepy` |
| Jinja2 (pip) | PIPE-01 templates | Not installed | 3.1.6 available | `uv add Jinja2` |
| Korean font (NotoSansKR) | PIPE-06 thumbnail | Unknown | — | Download from Google Fonts; bundle in `assets/fonts/` |
| FAL_KEY (env var) | VGEN-01 | Unknown | — | Feature gated — pipeline works without it (Ken Burns fallback) |
| YouTube OAuth2 credentials | PIPE-05 | Unknown | — | Must be configured per channel; feature blocked without it |

**Missing dependencies with no fallback (block execution):**
- FFmpeg with NVENC — required for PIPE-04; libx264 works as non-NVENC fallback but must be decided
- IndexTTS-2 weights (4.7GB HuggingFace download) — no fast alternative; MeloTTS is the code fallback
- YouTube OAuth2 credentials — PIPE-05 cannot function without them; requires GCP project setup

**Missing dependencies with fallback (degraded-but-functional):**
- Ollama + qwen3:14b — can fall back to Gemini 2.5 Pro API for script gen (adds API cost)
- fal.ai API key — Ken Burns effect used instead of AI video clips
- IndexTTS-2 — MeloTTS `TTS(language='KR')` is a confirmed working Korean TTS fallback

**Plan 1 of Phase 2 must include a Wave 0 task to install all pip dependencies and verify all service connections before any content generation code is written.**

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Ollama `format="json"` string | Ollama `format=json_schema_object` | Ollama 0.5+ | Schema-constrained output, far fewer hallucinated fields |
| ComfyUI HTTP-only polling | ComfyUI WebSocket + HTTP fallback | ComfyUI 0.2+ | Event-driven completion; no busy loop |
| fal-client synchronous `run()` | `submit_async()` + `iter_events()` | fal-client 0.5+ | Real-time progress + cost events |
| MoviePy 1.x | MoviePy 2.x | 2024 | Breaking API changes — `VideoFileClip`, not `VideoFileClip.set_audio()` |
| Pillow `ImageFont.truetype` from system | Bundle TTF in `assets/fonts/` | Best practice | System fonts differ across machines; Korean glyphs absent on many Windows installs |
| YouTube upload with `apiclient` | `googleapiclient` (same library, renamed) | 2020 | `apiclient` was deprecated; use `googleapiclient.discovery.build` |

**Deprecated/outdated:**
- `fal.run()` (synchronous): Still works but blocks; use `fal_client.run_async()` for async activities
- MoviePy 1.x: `clip.set_audio()` → `clip.with_audio()` in 2.x; entire API surface changed
- ComfyUI `extra_pnginfo` for metadata: Still present but workflow should use standard `KSampler` + `VAEDecode` nodes without custom metadata nodes for portability

---

## Open Questions

1. **IndexTTS-2 Korean quality for domain vocabulary**
   - What we know: Official docs focus on Chinese/English; Korean not explicitly documented
   - What's unclear: Whether Korean domain-specific words (medical, financial, crypto niches) are mispronounced
   - Recommendation: Test with 10 Korean sentences early in Plan 1; if quality is poor, switch to MeloTTS as primary and accept lower voice quality

2. **ComfyUI SDXL workflow JSON format for Phase 2**
   - What we know: ComfyUI uses `KSampler`, `CLIPTextEncode`, `VAEDecode` node types; workflow exported as JSON from GUI
   - What's unclear: Exact node IDs and structure for the specific checkpoint the user plans to use
   - Recommendation: Load a workflow JSON exported from ComfyUI GUI as a template file; patch only the `CLIPTextEncode` positive prompt node at runtime. Do not hard-code node IDs — use a helper that finds the node by class name.

3. **fal.ai WAN i2v actual pricing vs estimate**
   - What we know: $0.20/clip at 480p, $0.40/clip at 720p (confirmed from fal.ai model page)
   - What's unclear: Whether billing events in `fal_client.Completed` include a `billing` field we can parse automatically vs. tracking fixed costs
   - Recommendation: Track cost as a fixed lookup (`{"480p": 0.20, "720p": 0.40}`) in cost_tracker.py for now; update if fal.ai adds a billing field to response

4. **YouTube OAuth2 flow for automated (headless) upload**
   - What we know: `videos.insert()` requires YouTube upload scope; OAuth2 not service accounts
   - What's unclear: Whether the operator has already completed the OAuth2 consent flow and saved refresh tokens, or if this needs to be set up from scratch
   - Recommendation: Plan 1 should include a one-time OAuth2 setup script (`scripts/youtube_auth.py`) that outputs `data/yt_token_{channel_id}.json` — these tokens auto-refresh at upload time

5. **VRAM contention: Ollama + ComfyUI on RTX 4070 8GB**
   - What we know: SDXL uses ~5-6GB VRAM; Qwen3-14B uses ~8-9GB VRAM (quantized via Ollama)
   - What's unclear: Whether Ollama offloads VRAM after script generation before ComfyUI loads
   - Recommendation: Script gen activity must complete (Ollama finishes, VRAM released) before image gen starts. Temporal gpu-queue serialization handles this. Add a `time.sleep(2)` or Ollama `/api/tags` ping between activities to confirm model is unloaded if VRAM OOM errors appear in testing.

---

## Project Constraints (from CLAUDE.md)

The following project-specific constraints from CLAUDE.md apply to all Phase 2 implementation:

- **Absolute:** No `# type: ignore` or `# noqa` to suppress errors — fix root causes
- **Absolute:** No features from REQUIREMENTS.md "Out of Scope" section (real-time editing UI, SNS cross-posting, live streaming)
- **Absolute:** No secrets hardcoded — all API keys and credentials via `.env` / Pydantic Settings
- **Absolute:** Tests must not be modified to pass — fix implementation instead
- **Absolute:** Plan items processed one at a time — no simultaneous multi-plan execution
- **Mandatory:** TDD — write tests before implementation for each activity
- **Mandatory:** After each plan completes, update `plan.md` with `[✅]` and HALT
- **Mandatory:** New errors found → log in `LessonsLearned.md`
- **Mandatory:** Read files before editing
- **Architecture:** FastAPI `Depends()` for service injection in API routes
- **Architecture:** Router (`api/`) handles HTTP only; business logic in `services/`
- **Architecture:** No direct DB queries in routers — go through service layer
- **Architecture:** Pydantic `models/` ≠ API `schemas/`; keep separate
- **Naming:** `snake_case` files, `PascalCase` classes, `snake_case` functions, `UPPER_SNAKE_CASE` constants
- **Testing:** `pytest tests/ -v --cov=src --cov-report=term-missing` — no other test runner
- **Build:** `uv sync`, `uvicorn src.main:app --reload`, `ruff check .`, `mypy src/`
- **Git:** One plan = one commit; format `feat: description`

---

## Sources

### Primary (HIGH confidence)

- fal-client GitHub README (`fal-ai/fal`) — `run()`, `run_async()`, `submit_async()`, `iter_events()`, `upload_file()` patterns verified
- ComfyUI `script_examples/websockets_api_example.py` — WebSocket + `/prompt` + `/history` + `/view` patterns verified
- Ollama REST API docs (`ollama/ollama/blob/main/docs/api.md`) — `/api/generate` with `format=json_schema` verified
- fal.ai `fal-ai/wan-i2v` model page — input schema, response schema, pricing ($0.20/480p, $0.40/720p) verified
- YouTube Data API v3 docs — `videos.insert()`, `thumbnails.set()`, quota costs verified
- MeloTTS `docs/install.md` — `TTS(language='KR')` Korean support verified
- IndexTTS-2 GitHub (`index-tts/index-tts`) — `IndexTTS2.infer()` Python API verified; Korean support NOT confirmed
- Ollama model library — `qwen3:14b` (9.3GB, 40K ctx) confirmed
- PyPI registry — all pip package versions confirmed as of 2026-04-02
- FFmpeg zoompan filter documentation — `zoompan` filter parameters for Ken Burns effect verified

### Secondary (MEDIUM confidence)

- Pillow `ImageDraw` + `ImageFont` patterns — well-documented, no recent API changes; Korean font requirement inferred from known PIL limitation
- YouTube quota cost table — verified from multiple secondary sources; 1,600 units for `videos.insert()`, 50 for `thumbnails.set()`
- VRAM estimates (Qwen3-14B ~8-9GB, SDXL ~5-6GB) — inferred from model size + common knowledge; actual measured values may differ

### Tertiary (LOW confidence — needs validation)

- IndexTTS-2 Korean language quality — not confirmed in official docs; requires hands-on testing
- fal.ai `Completed` event billing field presence — not verified in SDK docs; assumed to require fixed-cost lookup
- Ollama VRAM release timing after inference — timing behavior assumed; requires empirical testing on RTX 4070

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all versions verified against PyPI registry 2026-04-02
- Architecture patterns: HIGH — based on official SDK examples and Phase 1 established patterns
- Pitfalls: MEDIUM — most inferred from library behavior and docs; IndexTTS-2 Korean and NVENC are empirically unverified
- Environment availability: HIGH — all checks run against actual machine state

**Research date:** 2026-04-02
**Valid until:** 2026-05-02 (stable stack; fal.ai pricing may change sooner — check before billing-critical work)
