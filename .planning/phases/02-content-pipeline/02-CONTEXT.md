# Phase 2: Content Pipeline - Context

**Gathered:** 2026-04-02
**Status:** Ready for planning

<domain>
## Phase Boundary

A single topic input produces a complete YouTube video with title, description, tags, and thumbnail — uploaded automatically — for any configured channel. All AI models (LLM, image, video, TTS) are swappable via ChannelConfig with Enum-managed model lists and per-model cost annotations.

**In scope:** Script generation, image generation, video generation (local + cloud), TTS, FFmpeg assembly, YouTube upload, thumbnail generation, multi-channel config, multi-provider cloud API support, model swapping architecture.

**Not in scope:** Quality gate (Phase 3), batch processing (Phase 3), content calendar (Phase 3), cost dashboard UI (Phase 3), multi-character voice acting (v2).

</domain>

<decisions>
## Implementation Decisions

### Model Stack (Updated from tech spec)

- **D-20:** LLM (Script Generation):
  - Primary: **Qwen3.5-9B** via Ollama (~7GB VRAM Q4, 54-58 t/s)
  - Fallback: **Qwen3 8B** via Ollama (~5-6GB VRAM Q4)
  - Cloud fallback: Gemini 2.5 Pro API (adds cost)
  - 기존 스펙의 Qwen3-14B에서 변경 — 더 작고 빠르며 한국어 동등

- **D-21:** Image Generation:
  - **SDXL (Juggernaut XL)** — 6GB VRAM, 5-15s/image, ComfyUI 네이티브 (기존 스펙 유지)
  - **FLUX.1-schnell (Q4 GGUF)** — ~6GB VRAM, 15-20s/image, 빠른 생성 (신규)
  - **FLUX.1-dev (Q5_K_S GGUF)** — ~7-8GB VRAM, 45-60s/image, 최고 품질 (신규)
  - ChannelConfig `image_model` 필드에서 선택. 모두 ComfyUI 워크플로우로 실행

- **D-22:** Video Generation (Local):
  - **Wan 2.6** via Wan2GP — ~8GB VRAM (양자화), 480p, Apache 2.0, 최신 오픈소스 (기존 WAN 2.2에서 업그레이드)
  - **CogVideoX-5B** (양자화) — ~8GB VRAM, I2V 특화, 6초 클립 (신규)
  - **LTX-Video 2.0** — ~8GB (2B 모델), 빠른 생성, 4K 지원 (신규)
  - Ken Burns fallback 유지 (로컬 모델 + 클라우드 모두 없을 때)

- **D-23:** TTS (Korean):
  - Primary: **CosyVoice2-0.5B** — ~2GB VRAM, 한국어 공식 지원, Apache 2.0, 150ms 스트리밍
  - Secondary: **Fish Speech S1-mini** — ~2GB VRAM, TTS Arena 1위, 음성 복제, CC BY-NC-SA
  - **IndexTTS-2 제거** — 한국어 공식 미지원 (중국어/영어/일본어만)
  - **MeloTTS 유지** — 경량 한국어 fallback으로 남겨둠

- **D-24:** Cloud API Providers (Phase 2 구현 범위):
  - **fal.ai** — 비디오/이미지 primary (600+ 모델, 단일 API 키)
  - **Replicate** — 비디오 fallback (HunyuanVideo, CogVideoX 클라우드 버전)
  - **kai.ai** — 추가 프로바이더
  - **Together.ai** — LLM 클라우드 fallback
  - 각 프로바이더별: API 클라이언트 + 에러 처리 + 비용 추적 구현
  - Enum 예약만: Fireworks.ai, krea.ai, WaveSpeedAI (Phase 3 또는 v2에서 구현)

### Model Swapping Architecture

- **D-25:** ChannelConfig에 모델명 직접 지정 방식:
  ```yaml
  # channel_01.yaml 예시
  channel_id: "tech_kr"
  image_model: "sdxl-juggernaut"    # Enum: sdxl-juggernaut, flux-schnell, flux-dev
  video_model: "wan2.6"             # Enum: wan2.6, cogvideox-5b, ltx-video-2
  tts_engine: "cosyvoice2"          # Enum: cosyvoice2, fish-speech, melotts
  llm_model: "qwen3.5-9b"          # Enum: qwen3.5-9b, qwen3-8b
  video_provider: "local"           # Enum: local, fal.ai, replicate, kai.ai, together.ai
  ```

- **D-26:** 지원 모델 목록은 Python Enum으로 관리. 각 Enum 값에 비용 메모 포함:
  ```python
  class VideoModel(str, Enum):
      WAN_2_6 = "wan2.6"           # local, $0/clip
      COGVIDEOX_5B = "cogvideox-5b" # local, $0/clip
      LTX_VIDEO_2 = "ltx-video-2"  # local, $0/clip
  ```
  비용 정보는 별도 `model_costs.yaml` 파일에서 관리 — 사용자가 직접 수정 가능

- **D-27:** 유료 모델 비용은 `model_costs.yaml`에 기록하고 사용자가 수정 가능:
  ```yaml
  # model_costs.yaml
  fal.ai:
    wan-i2v-480p: 0.20    # $/clip
    wan-i2v-720p: 0.40
    flux-schnell: 0.005   # $/image
  replicate:
    hunyuan-video: 1.27   # $/video
  ```

### Claude's Discretion

- Wan2GP 설치 스크립트 세부사항 (clone + setup 단계)
- CosyVoice2 배포 모드 (subprocess vs direct Python import)
- ComfyUI 워크플로우 JSON 구조 (FLUX용 별도 워크플로우 필요 여부)
- 정확한 Enum 값 이름 (위는 예시)
- 모델 간 VRAM 충돌 방지를 위한 언로드 전략
- kai.ai API 클라이언트 구현 세부사항 (API 문서 확인 필요)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Tech Spec
- `CLAUDE.md` (project root) — Full technology stack, architecture decisions, local vs cloud split. **Note: LLM/TTS/Image/Video 모델 정보는 이 CONTEXT.md가 최신 — CLAUDE.md와 충돌 시 CONTEXT.md 우선**

### Requirements
- `.planning/REQUIREMENTS.md` — PIPE-01~06, VGEN-01~03, CHAN-01~02
- `.planning/ROADMAP.md` — Phase 2 success criteria (5 conditions)
- `.planning/PROJECT.md` — Core value, non-goals, key decisions

### Phase 1 Context (carry forward)
- `.planning/phases/01-infrastructure/01-CONTEXT.md` — D-01 through D-19 locked decisions (project layout, Temporal, SQLite, worker pools, file layout)

### Phase 2 Research
- `.planning/phases/02-content-pipeline/02-RESEARCH.md` — Architecture patterns, anti-patterns, common pitfalls, environment availability. **Note: TTS/LLM/Video 모델 추천은 이 CONTEXT.md로 대체됨**

### External Docs (use context7 or web search)
- Wan2GP GitHub (`deepbeepmeep/Wan2GP`) — RTX 4070 8GB에서 Wan 2.6 실행 가이드
- CosyVoice2 GitHub — Python API, 한국어 설정
- Fish Speech GitHub — S1-mini 설치 및 API
- CogVideoX GitHub — 양자화 모델 실행 가이드
- LTX-Video GitHub — 2B 모델 설치
- fal-client Python SDK — `submit_async()`, `iter_events()`, `upload_file_async()`
- Replicate Python SDK — `replicate.run()`, `replicate.predictions.create()`
- kai.ai API docs — 확인 필요
- Together.ai Python SDK — LLM inference API

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/config.py` — Pydantic Settings. Phase 2에서 OLLAMA_URL, COMFYUI_URL, FAL_KEY, REPLICATE_API_TOKEN, KAI_API_KEY, TOGETHER_API_KEY 등 추가 필요
- `src/activities/pipeline.py` — `setup_pipeline_dirs()` 재사용 (아티팩트 디렉토리 생성)
- `src/activities/cleanup.py` — `cleanup_intermediate_files()` 재사용
- `src/workflows/pipeline_validation.py` — Phase 1 검증용, Phase 2 ContentPipelineWorkflow의 참조 패턴
- `src/services/db_service.py` — pipeline_runs 상태 업데이트에 재사용
- `src/workers/` — gpu_worker, cpu_worker, api_worker 3개 워커 프로세스에 새 Activity 등록

### Established Patterns
- Temporal Activity: `@activity.defn` + Pydantic BaseModel input/output + task_queue 라우팅
- Worker 분리: GPU maxConcurrent=1, CPU maxConcurrent=4, API maxConcurrent=8
- Config: Pydantic Settings from `.env`
- DB: SQLModel + Alembic migrations
- File paths only in Activity results (binary 데이터 반환 금지)

### Integration Points
- `src/workflows/content_pipeline.py` (신규) — 메인 워크플로우, PipelineValidationWorkflow 패턴 따름
- `src/models/channel_config.py` (신규) — ChannelConfig frozen model, YAML 로드
- `src/channel_configs/` (신규) — 채널별 YAML 설정 파일
- `model_costs.yaml` (신규) — 프로바이더/모델별 비용 정보, 사용자 수정 가능

</code_context>

<specifics>
## Specific Ideas

- **IndexTTS-2 한국어 미지원 발견** — 기존 스펙에서 primary TTS였으나 중국어/영어/일본어만 공식 지원. CosyVoice2-0.5B로 교체 (한국어 공식 지원, Apache 2.0, 150ms 스트리밍)
- **Qwen3-14B → Qwen3.5-9B 다운사이징** — 더 작고 빠르며 한국어 품질 동등. VRAM 여유 확보
- **WAN 2.2 → Wan 2.6 업그레이드** — Wan2GP 프로젝트로 8GB VRAM 최적화 실행 가능
- **FLUX 모델 추가** — ComfyUI에서 GGUF 양자화 FLUX 워크플로우 지원, 이미지 품질 옵션 확대
- **model_costs.yaml 사용자 수정 가능** — 유료 모델 옆에 비용 메모, 사용자가 직접 업데이트
- **4개 클라우드 프로바이더** — fal.ai(primary) + Replicate + kai.ai + Together.ai, 각각 API 클라이언트 + 에러 처리 + 비용 추적

</specifics>

<deferred>
## Deferred Ideas

- **Fireworks.ai 프로바이더** — Phase 3 또는 v2에서 추가 (Enum 예약만)
- **krea.ai 프로바이더** — Phase 3 또는 v2에서 추가 (크리에이티브 이미지 도구, UI 중심)
- **WaveSpeedAI 프로바이더** — Phase 3 또는 v2에서 추가 (Wan 최적화 추론)
- **AnimateDiff-Lightning** — ComfyUI 네이티브 비디오 생성, SD 해상도 제한으로 Phase 2에서는 제외
- **VibeVoice 다중 캐릭터 TTS** — v2 (Microsoft, 한국어 실험적)
- **LoRA per channel** — v2 (기본 파이프라인 안정화 후)

</deferred>

---

*Phase: 02-content-pipeline*
*Context gathered: 2026-04-02*
