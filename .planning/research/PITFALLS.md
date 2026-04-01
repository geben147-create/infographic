# Domain Pitfalls

**Domain:** Automated YouTube Video Production Pipeline
**Researched:** 2026-04-01

## Critical Pitfalls

Mistakes that cause rewrites or major issues.

### Pitfall 1: 8GB VRAM Contention (OOM Cascades)

**What goes wrong:** Running ComfyUI (SDXL), IndexTTS-2, and Ollama (Qwen3-14B) concurrently on a single RTX 4070 8GB causes out-of-memory crashes. One model loads, pushes another out, the evicted model's task fails, retries, pushes the first model out, creating a cycle.

**Why it happens:** Each model needs 4-8GB VRAM. SDXL needs ~6.5GB. Qwen3-14B quantized needs ~8GB. IndexTTS-2 needs ~4-8GB. They cannot coexist.

**Consequences:** Pipeline hangs, GPU crashes, corrupted outputs, wasted cloud API fallback costs.

**Prevention:**
- Temporal GPU Worker with `max_concurrent_activities=1` -- serialize all GPU tasks
- Explicit model loading/unloading between task types
- Ollama handles model swapping automatically, but ComfyUI and TTS need manual management
- Design workflow to batch same-model tasks (all images first, then all TTS, then script)

**Detection:** Monitor GPU VRAM usage. Alert if >95% for >30 seconds.

### Pitfall 2: Google Sheets as Source of Truth

**What goes wrong:** Pipeline reads/writes Google Sheets during execution. API quota hits (100 requests/100 seconds per user), race conditions between concurrent pipelines, data loss from overwritten cells, no transaction support.

**Why it happens:** Sheets is familiar and visible. Teams default to "just use the spreadsheet."

**Consequences:** Failed pipelines due to quota. Corrupted data from concurrent writes. No audit trail. Cannot replay failed pipeline from consistent state.

**Prevention:**
- Sheets is INPUT layer only. Sync to SQLite on trigger.
- Pipeline operates exclusively on SQLite.
- Write results back to Sheets as final step (notification, not truth).
- Use gspread batch operations to minimize API calls.

**Detection:** API quota errors in logs. Data mismatches between Sheets and actual pipeline output.

### Pitfall 3: YouTube API Quota Exhaustion

**What goes wrong:** Default quota is 10,000 units/day per GCP project. Video upload = 1,600 units. With 5 channels and metadata operations, quota runs out mid-day.

**Why it happens:** All channels share one GCP project. Search/list operations during metadata generation consume units. Retried uploads double-consume.

**Consequences:** Videos generated but cannot be uploaded. Wasted compute. Delayed publishing schedule.

**Prevention:**
- One GCP project per channel (each gets 10,000 units independently)
- Pre-compute all metadata (no search.list calls during upload)
- Upload once, update metadata separately (cheaper operations)
- Request quota increase early (free, but requires justification documentation)
- Implement upload queuing with Temporal: if quota hit, park and retry next day

**Detection:** `quotaExceeded` error from YouTube API. Track daily unit consumption.

### Pitfall 4: n8n Scale Ceiling

**What goes wrong:** Existing n8n workflows become unmaintainable as pipeline complexity grows. 100-node workflows are undebuggable. JSON export diffs are useless for code review. Adding channels means duplicating entire workflows.

**Why it happens:** n8n is excellent for prototyping but was not designed for multi-step ML pipelines with GPU routing.

**Consequences:** Months of accumulated technical debt. Workflow changes become high-risk. No way to test changes before deployment.

**Prevention:**
- Migrate away from n8n for the core pipeline (to Temporal + Python)
- Keep n8n ONLY for simple trigger/notification workflows during transition
- Do not invest in expanding existing n8n workflows

**Detection:** Already happening if you have 50+ node workflows or duplicate workflows per channel.

## Moderate Pitfalls

### Pitfall 5: fal.ai Cost Spiral

**What goes wrong:** Video generation costs accumulate faster than expected. WAN 2.2 at $0.10/sec for 5-second clips = $0.50/clip. 10 clips per video = $5. 5 channels, 1 video/day = $750/month just for video gen.

**Prevention:**
- Use image-based scenes (Ken Burns effect via FFmpeg) for low-motion scenes instead of AI video gen
- Reserve AI video gen for key scenes only (2-3 per video, not all)
- Compare WAN 2.5 ($0.05/sec) vs WAN 2.2 ($0.10/sec) quality -- cheaper option may be sufficient
- Track per-video costs in SQLite, set alerts at thresholds
- Consider WaveSpeedAI or Atlas Cloud as cheaper alternatives (up to 50% less)

### Pitfall 6: TTS Quality Inconsistency in Korean

**What goes wrong:** TTS models trained primarily on English/Chinese produce accented or unnatural Korean. VibeVoice Korean is "experimental." IndexTTS-2 Korean is better but may mispronounce specialized terms (medical, financial).

**Prevention:**
- Test IndexTTS-2 extensively with domain-specific Korean vocabulary before committing
- Build a pronunciation correction dictionary (text preprocessing before TTS)
- Have human QA for first 10-20 videos per niche to calibrate
- Keep MeloTTS as fallback (lightweight, decent Korean)
- Consider cloud TTS APIs (Google Cloud TTS, NAVER Clova) for production quality if open-source falls short

### Pitfall 7: FFmpeg Filter Graph Complexity

**What goes wrong:** Complex crossfade transitions between many clips create enormous filter graphs. FFmpeg silently produces black frames or audio desync when filter graphs have errors.

**Prevention:**
- Convert images to short video clips first (1s each), then concatenate -- much simpler filter graph
- Use the ffmpeg-slideshow-py pattern: images -> tmp clips (parallel) -> concatenate (sequential)
- Always verify output duration matches expected (sum of clips minus transition overlaps)
- Use MoviePy for simple transitions, drop to raw FFmpeg only for advanced needs
- Test with a 3-scene pipeline before scaling to 10+ scenes

### Pitfall 8: ComfyUI Seed Determinism Trap

**What goes wrong:** ComfyUI caches results by seed. If seed is not randomized, you get identical images on retry. If seed IS randomized, you cannot reproduce a good result.

**Prevention:**
- Always generate random seed per image
- Log the seed used in metadata.json alongside the output
- For "retry with different result," increment seed by 1
- For "reproduce exact result," load seed from log

### Pitfall 9: OAuth Token Expiration

**What goes wrong:** YouTube and Google Sheets OAuth tokens expire. Automated pipeline breaks silently at 3 AM. Videos pile up unuploaded.

**Prevention:**
- Store refresh tokens, not access tokens
- Implement automatic token refresh in API worker
- Alert on auth failures immediately (Slack/Telegram notification)
- Test token refresh in CI/CD

## Minor Pitfalls

### Pitfall 10: Temporal Learning Curve

**What goes wrong:** Temporal's deterministic workflow constraints confuse developers. You cannot use random(), datetime.now(), or I/O inside workflows -- only inside activities.

**Prevention:**
- Read Temporal's Python SDK guide before writing first workflow
- Keep workflows thin (just orchestration logic). All I/O in activities.
- Use Temporal's sandbox mode to catch non-determinism errors early

### Pitfall 11: File Cleanup Neglect

**What goes wrong:** Intermediate files (images, audio, video clips) accumulate. Each video produces ~2GB of artifacts. 150 videos/month = 300GB.

**Prevention:**
- Cleanup activity as last step in every workflow
- Keep final.mp4 and metadata.json for 30 days, delete intermediates immediately
- Log file sizes in cost tracking

### Pitfall 12: LLM Script Quality Variance

**What goes wrong:** Qwen3-14B produces inconsistent script quality. Some scripts are excellent, others are generic or factually questionable (health/finance niches = liability risk).

**Prevention:**
- Structured output format (JSON schema enforcement via Pydantic)
- Template-based prompts per niche with few-shot examples
- Fact-check step for health/finance content (Gemini 2.5 Pro as reviewer)
- Human review gate for first 20 videos per niche

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Phase 1: Single pipeline | GPU VRAM contention (#1) | Serialize GPU tasks, max_concurrent=1 |
| Phase 1: Data layer | Sheets as SSOT (#2) | SQLite from day 1, Sheets as input only |
| Phase 2: Multi-channel | YouTube quota (#3) | Separate GCP projects per channel |
| Phase 2: Video gen | Cost spiral (#5) | Mix AI video + Ken Burns, track costs |
| Phase 2: Korean TTS | Quality issues (#6) | Test extensively, fallback to cloud TTS |
| Phase 3: Scale | n8n ceiling (#4) | Should be fully migrated by this phase |
| Phase 3: Batch | File cleanup (#11) | Automated cleanup in workflow |
| All phases | OAuth expiry (#9) | Refresh token logic from day 1 |

## Sources

- [n8n vs Python Limitations](https://zenvanriel.nl/ai-engineer-blog/n8n-vs-python-ai-automation/)
- [Google Sheets API Quotas](https://blog.coupler.io/how-to-use-google-sheets-as-database/)
- [YouTube API Quota System](https://getlate.dev/blog/youtube-api-limits-how-to-calculate-api-usage-cost-and-fix-exceeded-api-quota)
- [YouTube Upload Limits](https://zernio.com/blog/youtube-upload-api)
- [VRAM Requirements Guide](https://www.bacloud.com/en/blog/163/guide-to-gpu-requirements-for-running-ai-models.html)
- [Best GPU for Stable Diffusion 2026](https://offlinecreator.com/blog/best-gpu-for-stable-diffusion-2026)
- [VibeVoice Korean Experimental](https://huggingface.co/microsoft/VibeVoice-Realtime-0.5B)
- [FFmpeg Slideshow Pattern](https://github.com/Twinklebear/ffmpeg-slideshow-py)
- [Temporal Python SDK](https://docs.temporal.io/develop/python)
- [fal.ai Pricing](https://fal.ai/video)
- [Atlas Cloud 50% Cheaper](https://www.atlascloud.ai/blog/case-studies/best-fal-ai-alternative-in-2026-atlas-cloud-deep-dive)
