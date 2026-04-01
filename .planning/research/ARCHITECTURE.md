# Architecture Patterns

**Domain:** Automated YouTube Video Production Pipeline
**Researched:** 2026-04-01

## Recommended Architecture

### High-Level: Temporal Workflow Orchestration + Worker Pool

```
                    +-------------------+
                    |  Google Sheets    |  (Human data entry)
                    +--------+----------+
                             |
                             v
                    +-------------------+
                    |  FastAPI Gateway   |  (API + Sheets sync + triggers)
                    +--------+----------+
                             |
                             v
                    +-------------------+
                    |  Temporal Server   |  (Workflow orchestration)
                    +--------+----------+
                             |
              +--------------+--------------+
              |              |              |
              v              v              v
     +--------+----+ +------+------+ +-----+-------+
     | CPU Workers  | | GPU Workers | | API Workers  |
     | (FFmpeg,     | | (ComfyUI,  | | (fal.ai,    |
     |  metadata,   | |  TTS,      | |  YouTube,   |
     |  Sheets sync)| |  Ollama)   | |  Gemini)    |
     +-------------+ +------------+ +-------------+
              |              |              |
              v              v              v
     +-------------------------------------------+
     |              SQLite Database               |
     |  (Pipeline state, video metadata, costs)   |
     +-------------------------------------------+
```

### Component Boundaries

| Component | Responsibility | Communicates With | Deployment |
|-----------|---------------|-------------------|------------|
| **FastAPI Gateway** | HTTP API, Sheets sync trigger, status dashboard | Temporal Client, SQLite | Docker container |
| **Temporal Server** | Workflow scheduling, state persistence, retry logic | Workers via Task Queues | Docker container |
| **CPU Workers** | FFmpeg assembly, metadata generation, file management | Temporal, SQLite, filesystem | Host process |
| **GPU Workers** | ComfyUI (image gen), IndexTTS-2 (TTS), Ollama (LLM) | Temporal, local GPU, filesystem | Host process (GPU access) |
| **API Workers** | fal.ai calls, YouTube upload, Gemini API, Sheets API | Temporal, external APIs | Docker container |
| **SQLite** | Persistent state, video records, cost tracking | All workers via SQLModel | File on host |
| **ComfyUI** | Image generation engine | GPU Workers via HTTP API | Docker or host process |
| **Ollama** | LLM inference server | GPU Workers via OpenAI-compatible API | Host process |

### Data Flow: Single Video Production

```
1. TRIGGER
   Google Sheets -> FastAPI (sync) -> Temporal (start workflow)
   OR
   FastAPI API call -> Temporal (start workflow)
   OR
   Temporal Schedule (cron) -> Temporal (start workflow)

2. SCRIPT GENERATION (GPU Worker - Ollama)
   Channel config + topic -> Qwen3-14B -> structured script JSON
   {title, description, scenes: [{narration, image_prompt, duration}], tags}

3. PARALLEL GENERATION (GPU + API Workers)
   3a. Images: script.scenes -> ComfyUI SDXL -> scene images (local GPU)
   3b. TTS: script.scenes[].narration -> IndexTTS-2 -> audio clips (local GPU)
   3c. Video clips: scene images -> fal.ai WAN 2.2 -> video clips (cloud API)
   3d. Thumbnail: script.title -> ComfyUI SDXL -> thumbnail + Pillow text overlay

4. ASSEMBLY (CPU Worker - FFmpeg)
   video clips + images + audio + transitions -> FFmpeg -> final MP4
   - NVENC hardware encoding on RTX 4070
   - Crossfade transitions between scenes
   - Audio mixing (TTS + background music)

5. QUALITY GATE (optional)
   Assembled video -> notification -> human approval signal
   OR auto-approve if confidence > threshold

6. PUBLISH (API Worker)
   Final MP4 + metadata -> YouTube Data API v3 -> published video
   Update SQLite with YouTube video ID, publish timestamp

7. CLEANUP
   Remove intermediate files, log costs, update Sheets status
```

## Patterns to Follow

### Pattern 1: Temporal Activity-per-Service

**What:** Each external service call (ComfyUI, fal.ai, YouTube, Ollama) is a separate Temporal Activity with its own retry policy and timeout.

**When:** Always. Every I/O operation is an Activity.

**Why:** If fal.ai times out mid-video-generation, Temporal retries just that activity, not the entire pipeline. GPU workers don't re-generate already-completed images.

**Example:**
```python
@workflow.defn
class ProduceVideoWorkflow:
    @workflow.run
    async def run(self, params: VideoParams) -> VideoResult:
        # Step 1: Generate script (GPU worker queue)
        script = await workflow.execute_activity(
            generate_script,
            params.topic,
            task_queue="gpu-worker",
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )

        # Step 2: Parallel generation
        images, audio, video_clips, thumbnail = await asyncio.gather(
            workflow.execute_activity(
                generate_images, script.scenes,
                task_queue="gpu-worker",
                start_to_close_timeout=timedelta(minutes=10),
            ),
            workflow.execute_activity(
                generate_tts, script.scenes,
                task_queue="gpu-worker",
                start_to_close_timeout=timedelta(minutes=10),
            ),
            workflow.execute_activity(
                generate_video_clips, script.scenes,
                task_queue="api-worker",
                start_to_close_timeout=timedelta(minutes=15),
            ),
            workflow.execute_activity(
                generate_thumbnail, script,
                task_queue="gpu-worker",
                start_to_close_timeout=timedelta(minutes=3),
            ),
        )

        # Step 3: Assemble (CPU worker queue)
        final_video = await workflow.execute_activity(
            assemble_video,
            AssemblyInput(images, audio, video_clips, thumbnail),
            task_queue="cpu-worker",
            start_to_close_timeout=timedelta(minutes=10),
        )

        # Step 4: Publish (API worker queue)
        result = await workflow.execute_activity(
            upload_to_youtube,
            UploadInput(final_video, script.metadata),
            task_queue="api-worker",
            start_to_close_timeout=timedelta(minutes=30),
        )

        return result
```

### Pattern 2: Channel Config as Immutable Data

**What:** Each YouTube channel is a frozen config object that defines style, voice, prompts, LoRAs, and publish settings.

**When:** Multi-channel operations.

**Example:**
```python
from pydantic import BaseModel

class ChannelConfig(BaseModel, frozen=True):
    channel_id: str
    channel_name: str
    niche: str  # "health", "stock", "crypto"
    language: str  # "ko", "en"
    sdxl_checkpoint: str  # "juggernautXL_v10.safetensors"
    sdxl_lora: str | None  # Niche-specific LoRA
    tts_voice_ref: str  # Reference audio path for IndexTTS-2
    tts_characters: list[str]  # Multi-character voice refs
    prompt_template: str  # Jinja2 template for script generation
    thumbnail_style: str  # "bold_text", "face_reaction", etc.
    youtube_category_id: int
    default_tags: list[str]
    publish_schedule: str  # cron expression
```

### Pattern 3: Intermediate File Convention

**What:** All pipeline artifacts follow a predictable path convention based on workflow run ID.

**When:** Always. Enables cleanup, debugging, and resume.

**Example:**
```
/data/pipeline/{workflow_run_id}/
  script.json           # Generated script
  images/
    scene_001.png
    scene_002.png
  video_clips/
    scene_001.mp4
    scene_002.mp4
  audio/
    scene_001.wav
    scene_002.wav
    background.mp3
  thumbnail.png
  final.mp4             # Assembled video
  metadata.json         # YouTube metadata
  cost_log.json         # API cost tracking
```

### Pattern 4: ComfyUI as Headless Service

**What:** Run ComfyUI in headless mode, submit workflows via REST API, poll for completion via WebSocket.

**When:** All image generation.

**Example:**
```python
import httpx
import json

async def generate_image_via_comfyui(
    prompt: str,
    checkpoint: str,
    lora: str | None,
    output_path: str,
) -> str:
    workflow = load_workflow_template("sdxl_base.json")
    workflow = set_node_value(workflow, "prompt_node", "text", prompt)
    workflow = set_node_value(workflow, "checkpoint_node", "ckpt_name", checkpoint)
    if lora:
        workflow = set_node_value(workflow, "lora_node", "lora_name", lora)
    # Randomize seed for unique output
    workflow = set_node_value(workflow, "sampler_node", "seed", random.randint(0, 2**32))

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "http://localhost:8188/prompt",
            json={"prompt": workflow}
        )
        prompt_id = resp.json()["prompt_id"]

    # Poll for completion (or use WebSocket)
    result = await wait_for_completion(prompt_id)
    # Download output image
    await download_output(prompt_id, output_path)
    return output_path
```

## Anti-Patterns to Avoid

### Anti-Pattern 1: Google Sheets as Source of Truth

**What:** Using Sheets API for reads/writes during pipeline execution.
**Why bad:** API quotas, no transactions, race conditions between concurrent pipelines, no relational integrity.
**Instead:** Sync Sheets to SQLite on trigger. Pipeline reads/writes only to SQLite. Sync results back to Sheets after completion.

### Anti-Pattern 2: Monolithic Pipeline Script

**What:** One giant Python script that runs the entire pipeline sequentially.
**Why bad:** If it fails at step 7 of 10, you restart from scratch. No parallelism. No retry granularity.
**Instead:** Temporal workflow with individual Activities. Each step is independently retryable and parallelizable.

### Anti-Pattern 3: GPU Worker Contention

**What:** Running ComfyUI, IndexTTS, and Ollama simultaneously on 8GB VRAM.
**Why bad:** OOM crashes. Models fight for VRAM. Unpredictable failures.
**Instead:** Sequential GPU task execution. Temporal Task Queue with maxConcurrentActivities=1 for GPU workers. Load/unload models between tasks, or use Ollama's built-in model management.

### Anti-Pattern 4: Hardcoded Channel Config in Workflow

**What:** Channel-specific prompts, styles, voices embedded in workflow code.
**Why bad:** Adding a channel = modifying code. 5 channels = 5 workflow copies.
**Instead:** Channel config objects loaded from database/config files. Single workflow parameterized by channel_id.

### Anti-Pattern 5: Storing Videos in Database

**What:** Saving video binary data in SQLite or any database.
**Why bad:** Database bloat, slow queries, backup nightmare.
**Instead:** Videos on filesystem with predictable paths. Database stores only metadata and file paths.

## Scalability Considerations

| Concern | Current (1-2 videos/day) | Medium (5-10 videos/day) | High (20+ videos/day) |
|---------|--------------------------|--------------------------|----------------------|
| GPU VRAM | Sequential tasks, model swap | Add second GPU or cloud burst to fal.ai for images too | Full cloud migration for generation |
| Storage | Local SSD, ~2GB/video | Add NAS or S3-compatible storage | Cloud storage (S3/R2) |
| Temporal | Docker single node | Same (handles thousands of workflows) | Temporal Cloud or cluster |
| Database | SQLite | SQLite (still fine) | Migrate to PostgreSQL |
| YouTube quota | 6 uploads/day/project | Multiple GCP projects (1 per channel) | Quota increase request |
| Cost | ~$1.25-2.50/video | Same per video, ~$375-750/mo | Negotiate fal.ai volume pricing |

## Sources

- [Temporal Python SDK Workflows](https://docs.temporal.io/develop/python)
- [Temporal Task Queue Routing](https://docs.temporal.io/task-routing)
- [Temporal Video Processing at WashPost](https://temporal.io/blog/temporal-supercharges-video-processing-at-the-washington-post)
- [ComfyUI API Usage](https://deepwiki.com/Comfy-Org/ComfyUI/7-api-and-programmatic-usage)
- [ComfyUI Headless Hosting](https://9elements.com/blog/hosting-a-comfyui-workflow-via-api/)
- [Google Sheets as Database Limitations](https://blog.coupler.io/how-to-use-google-sheets-as-database/)
