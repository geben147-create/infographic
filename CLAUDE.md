<!-- GSD:project-start source:PROJECT.md -->
## Project

**YouTube Video Automation Pipeline**

RTX 4070 Laptop GPU (4GB VRAM) + 클라우드 하이브리드 환경에서 동작하는 다채널 YouTube 영상 자동 제작 파이프라인. 토픽/키워드 입력만으로 스크립트 생성, AI 이미지/영상 생성, 한국어 TTS, FFmpeg 조립, YouTube 업로드까지 전 과정을 자동화한다.

**Core Value:** **토픽 하나로 완성된 YouTube 영상을 자동 생성하고 업로드하는 것.** 단일 채널에서 end-to-end 파이프라인이 동작해야 나머지 모든 기능(다채널, 배치, 품질 게이트)이 의미를 갖는다.
<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->
## Technology Stack

## Orchestration Decision: n8n vs Python vs Hybrid
### Comparison Matrix
| Criterion | n8n | Python (FastAPI + Temporal) | Hybrid (n8n + Python services) |
|-----------|-----|---------------------------|-------------------------------|
| **Dev speed (initial)** | Fast (visual, drag-drop) | Slower (code everything) | Medium |
| **Dev speed (at scale)** | Slow (100-node JSON nightmare) | Fast (refactor, test, reuse) | Medium |
| **GPU task routing** | None native | Temporal: native Task Queue routing | Python handles GPU |
| **Error handling** | Basic retry per node | Temporal: durable execution, auto-resume | Split responsibility |
| **Git versioning** | One giant JSON blob | Normal code files, proper diffs | Mixed |
| **Cost control** | Poor (token waste in visual builders) | Excellent (prune before model calls) | Good |
| **Video processing** | Must shell out to external | Native FFmpeg/subprocess integration | Python handles heavy |
| **Multi-channel mgmt** | Painful at 5+ channels | Config-driven, loop over channels | Mixed |
| **Team collaboration** | Difficult (JSON merge conflicts) | Standard code review workflow | Split |
| **Debugging** | Visual but shallow | Full stack traces, breakpoints | Split |
| **Community/ecosystem** | Growing but shallow for ML | Massive Python ML ecosystem | Both |
### Recommendation: Python-first with FastAPI + Temporal
## Recommended Stack
### Core Framework
| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| **Python** | 3.12+ | Primary language | ML/AI ecosystem, ComfyUI native, FFmpeg wrappers | HIGH |
| **FastAPI** | 0.115+ | REST API layer | Async, fast, OpenAPI docs, Depends() DI | HIGH |
| **Temporal** | Python SDK 1.16+ | Workflow orchestration | Durable execution, GPU task routing, auto-retry, state persistence. Used by WashPost for video processing. | HIGH |
| **Redis** | 7.x | Cache + message broker | Temporal worker coordination, result caching | HIGH |
### AI / Generation Models
| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| **Qwen3-14B** (local via Ollama) | Latest | Script generation | Best value for creative writing, Korean support, zero API cost | HIGH |
| **Gemini 2.5 Pro** (cloud API) | Latest | Complex script generation, fact-checking | Longer context, better reasoning for complex topics | MEDIUM |
| **ComfyUI** | Latest | Image generation orchestration | Headless API mode, exports workflow as JSON, massive node ecosystem | HIGH |
| **SDXL** (local) | SDXL 1.0 + community checkpoints | Image generation (primary) | Runs well on 4GB VRAM (Laptop GPU), massive LoRA ecosystem, 5-10s per image | HIGH |
| **FLUX Q4 GGUF** (local) | FLUX.1-dev quantized | Image generation (high quality) | 90% of full quality via Q4 quantization, borderline on 4GB VRAM — use with caution | MEDIUM |
| **fal.ai** | API | Cloud image/video generation fallback | 600+ models, single API key, $0.05-0.40/sec video, fast cold starts (5-10s) | HIGH |
| **WAN 2.2/2.5** via fal.ai | Latest | Video generation (image-to-video) | $0.05-0.10/sec, LoRA support, high motion diversity | HIGH |
| **IndexTTS-2** | Latest | Korean TTS (primary) | Zero-shot, Korean native, 150ms streaming latency, 30-50% fewer pronunciation errors vs v1 | HIGH |
| **VibeVoice** (Microsoft) | Realtime-0.5B | Multi-character TTS (4 speakers) | Up to 4 distinct speakers, 90min synthesis, experimental Korean support | MEDIUM |
| **MeloTTS** | Latest | Korean TTS (lightweight fallback) | Lightweight, Korean support, good for batch processing | MEDIUM |
### Media Processing
| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| **FFmpeg** | 7.x | Video assembly, transitions, encoding | Industry standard, hardware-accelerated encoding (NVENC on RTX 4070) | HIGH |
| **ffmpeg-python** | 0.2.0 | FFmpeg Python wrapper | Direct filter graph control, complex chains for slideshows/transitions | HIGH |
| **MoviePy** | 2.x | High-level video editing | Pythonic API for crossfades, text overlays, compositing. v2 is current. | MEDIUM |
| **Pillow** | 10.x | Image manipulation | Thumbnail generation, text overlay, image preprocessing | HIGH |
### Data Layer
| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| **SQLite** (via SQLModel) | 3.45+ | Primary database | Zero-ops, ACID, file-based, sufficient for single-server pipeline | HIGH |
| **Google Sheets** | API v4 | Human-facing data entry/dashboard | Keep as INPUT layer only, not source of truth. Familiar to content team. | HIGH |
| **SQLModel** | 0.0.16+ | ORM | Pydantic + SQLAlchemy, type-safe, FastAPI-native | HIGH |
### Infrastructure
| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| **Docker** | 24+ | Containerization | Isolate ComfyUI, Temporal, workers | HIGH |
| **Ollama** | Latest | Local LLM serving | OpenAI-compatible API, easy model management, runs Qwen3 locally | HIGH |
| **YouTube Data API v3** | v3 | Video upload automation | 6 uploads/day per project (1,600 units each, 10,000 daily quota). Use multiple GCP projects for 5+ channels. | HIGH |
### Supporting Libraries
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **Pydantic** | 2.x | Data validation | All API schemas, config objects |
| **gspread** | 6.x | Google Sheets Python client | Sync Sheets data to SQLite |
| **google-api-python-client** | 2.x | YouTube upload | OAuth2 + videos.insert |
| **httpx** | 0.27+ | Async HTTP client | Calling fal.ai, ComfyUI API |
| **Jinja2** | 3.x | Template engine | Script templates per channel/niche |
| **structlog** | 24.x | Structured logging | Pipeline observability |
| **rich** | 13.x | CLI output | Development/debugging |
## Alternatives Considered
| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Orchestration | Temporal | Celery + Redis | No durable execution, no native GPU routing, manual state management |
| Orchestration | Temporal | n8n | Poor for GPU workloads, JSON versioning nightmare, token waste, no multi-channel config |
| Orchestration | Temporal | Dramatiq | Python-only, single-core (GIL), no built-in monitoring, no workflow state |
| Image Gen | SDXL (local) | FLUX full (local) | Needs 12GB+ VRAM at full precision, too slow at Q4 for batch |
| Image Gen | SDXL (local) | PixArt-Sigma | Good quality/size ratio but smaller ecosystem, fewer LoRAs |
| Video Gen | WAN via fal.ai | Sora 2 | $0.30-0.50/sec vs $0.05-0.10/sec, cost prohibitive at scale |
| Video Gen | WAN via fal.ai | Local WAN 2.2 | 4GB VRAM (Laptop GPU) insufficient for video gen models, cloud is correct choice |
| TTS | IndexTTS-2 | CosyVoice 3 | IndexTTS-2 has better Korean support and lower latency |
| TTS | IndexTTS-2 | Kokoro | Only 82M params, English-focused, weaker Korean |
| Database | SQLite | PostgreSQL | Overkill for single-server pipeline, adds ops overhead |
| Database | SQLite + Sheets | Google Sheets as SSOT | API quotas, no relations, no ACID, change tracking gaps |
| LLM | Qwen3-14B local | GPT-4o API | Cost ($0/mo local vs $$$ API), Korean creative writing quality comparable |
| LLM | Qwen3-14B local | Qwen3-235B cloud | 14B is sufficient for script gen, 235B is overkill |
| FFmpeg wrapper | ffmpeg-python | subprocess raw | ffmpeg-python provides composable filter graphs, less error-prone |
| FFmpeg wrapper | ffmpeg-python | ffmpeg-generator | Less mature, smaller community |
## Architecture: Local vs Cloud Split
### Local (RTX 4070 Laptop GPU, 4GB VRAM)
- **Image generation**: SDXL via ComfyUI (5-10s/image)
- **FLUX Q4**: For hero images needing higher quality (45-60s/image)
- **LLM inference**: Qwen3-14B via Ollama (script generation)
- **TTS**: IndexTTS-2 / VibeVoice (Korean multi-character)
- **FFmpeg**: Video assembly, transitions, encoding (NVENC acceleration)
### Cloud APIs
- **fal.ai**: Video generation (WAN 2.2/2.5), overflow image generation
- **Gemini 2.5 Pro**: Complex content research, fact-checking
- **YouTube Data API**: Video upload, metadata
- **Google Sheets API**: Data input sync
### Cost Estimate (per video)
| Step | Local/Cloud | Estimated Cost |
|------|-------------|---------------|
| Script (Qwen3 local) | Local | $0.00 |
| Images x10 (SDXL local) | Local | $0.00 |
| Video clips x5 (WAN 2.2 via fal.ai, 5s each) | Cloud | ~$1.25-2.50 |
| TTS (IndexTTS-2 local) | Local | $0.00 |
| FFmpeg assembly | Local | $0.00 |
| Thumbnail (SDXL local) | Local | $0.00 |
| YouTube upload | Cloud | $0.00 (API) |
| **Total per video** | | **~$1.25-2.50** |
| **Monthly (1 video/day, 5 channels)** | | **~$190-380/mo** |
## Installation
# Core framework
# Temporal
# Google APIs
# Media processing
# AI/ML
# Dev dependencies
# System dependencies (via system package manager or Docker)
# FFmpeg 7.x with NVENC support
# Ollama (for local LLM serving)
# ComfyUI (for image generation)
# Docker + Docker Compose (for Temporal server)
# Temporal server (Docker)
## Sources
- [n8n vs Python: Which keeps AI projects reliable](https://zenvanriel.nl/ai-engineer-blog/n8n-vs-python-ai-automation/)
- [Why Custom Python is the Automation Endgame](https://negibamaxim.eu/en/blog/zapier-make-n8n-vs-custom-python-code)
- [Build AI Research Agent: n8n vs Python 2026](https://www.searchcans.com/blog/build-ai-research-agent-n8n-vs-python-2026/)
- [Best Local Image Generation Models 2026](https://awesomeagents.ai/guides/best-local-image-generation-models-2026/)
- [FLUX 2 vs SDXL Comparison 2026](https://apatero.com/blog/flux-2-vs-stable-diffusion-xl-comparison-2026)
- [Best GPU for Stable Diffusion 2026](https://offlinecreator.com/blog/best-gpu-for-stable-diffusion-2026)
- [fal.ai Video Generation](https://fal.ai/video)
- [WaveSpeedAI vs fal.ai](https://wavespeed.ai/blog/posts/fal-ai-review-2026/)
- [Temporal: Video Processing at Washington Post](https://temporal.io/blog/temporal-supercharges-video-processing-at-the-washington-post)
- [Orchestrating AI Tasks: Celery vs Temporal](https://dasroot.net/posts/2026/02/orchestrating-ai-tasks-celery-temporal/)
- [Celery to Temporal Migration](https://dev.to/wintrover/from-celeryredis-to-temporal-a-journey-toward-idempotency-and-reliable-workflows-k1i)
- [IndexTTS-2 GitHub](https://github.com/diodiogod/TTS-Audio-Suite)
- [VibeVoice Microsoft](https://github.com/microsoft/VibeVoice)
- [Best Open Source TTS Models 2026](https://bentoml.com/blog/exploring-the-world-of-open-source-text-to-speech-models)
- [Best Open Source LLM for Creative Writing 2026](https://www.siliconflow.com/articles/en/best-open-source-llm-for-creative-writing-ideation)
- [Qwen3 GitHub](https://github.com/QwenLM/Qwen3)
- [YouTube Upload API Quotas 2026](https://zernio.com/blog/youtube-upload-api)
- [YouTube API Quota Guide](https://getlate.dev/blog/youtube-api-limits-how-to-calculate-api-usage-cost-and-fix-exceeded-api-quota)
- [ComfyUI API Programmatic Usage](https://deepwiki.com/Comfy-Org/ComfyUI/7-api-and-programmatic-usage)
- [Google Sheets as Database Limitations](https://blog.coupler.io/how-to-use-google-sheets-as-database/)
- [SQLite Renaissance 2026](https://dev.to/pockit_tools/the-sqlite-renaissance-why-the-worlds-most-deployed-database-is-taking-over-production-in-2026-3jcc)
- [FFmpeg Python Guide](https://www.gumlet.com/learn/ffmpeg-python/)
- [MoviePy v2](https://pypi.org/project/moviepy/)
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd:quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd:debug` for investigation and bug fixing
- `/gsd:execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd:profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
