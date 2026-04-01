# Feature Landscape

**Domain:** Automated YouTube Video Production Pipeline
**Researched:** 2026-04-01

## Table Stakes

Features users (channel operators) expect. Missing = pipeline feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Script generation from topic/keyword | Core value: automated content | Medium | Qwen3-14B local + Gemini fallback |
| AI image generation per scene | Visual content backbone | Medium | SDXL via ComfyUI, batched |
| AI video clip generation | Modern YouTube expectation | High | WAN 2.2 via fal.ai (cloud, not local) |
| Korean TTS with natural prosody | Korean channels = Korean audio | Medium | IndexTTS-2 primary |
| FFmpeg video assembly | Combine images + video + audio | Medium | Transitions, timing, encoding |
| Thumbnail generation | Every video needs one | Low | SDXL + text overlay via Pillow |
| YouTube upload with metadata | Automation endpoint | Low | Data API v3, OAuth2 |
| Multi-channel support | 5+ channels stated | Medium | Config-driven channel profiles |
| Google Sheets data input | Content team familiarity | Low | Sync to SQLite, not SSOT |
| Pipeline status dashboard | Know what's running/failed | Medium | Temporal Web UI + custom FastAPI endpoints |
| Retry on failure | Cloud APIs fail, GPUs OOM | Medium | Temporal durable execution handles this natively |

## Differentiators

Features that elevate from "automation tool" to "production system."

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Multi-character voice acting | Dialogue-based scripts with distinct voices | High | VibeVoice (4 speakers) or IndexTTS-2 voice cloning |
| Niche-specific style presets | Health vs crypto vs stock = different visual identity | Medium | LoRA per channel, prompt templates |
| A/B thumbnail testing | Auto-generate 2-3 thumbnails, pick best CTR | Medium | Generate variants, YouTube API for swap |
| Content calendar scheduling | Plan weeks ahead, auto-publish | Low | Temporal scheduled workflows |
| Quality gate (human review) | Preview before publish | Low | Temporal human-in-the-loop signal pattern |
| SEO-optimized metadata | Title, description, tags from AI | Low | Qwen3 generates, templates per niche |
| Trend-aware topic generation | Auto-discover trending topics per niche | Medium | Web search API + LLM filtering |
| Cost tracking per video | Know exactly what each video costs | Low | Log fal.ai API costs per workflow |
| Batch processing mode | Generate week of content overnight | Medium | Temporal batch workflows, queue management |
| Video performance analytics | Track which styles/topics perform best | High | YouTube Analytics API, feedback loop |

## Anti-Features

Features to explicitly NOT build.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Real-time video editing UI | Massive scope, not the product | Use ComfyUI GUI for manual edits when needed |
| Custom video player/hosting | YouTube IS the platform | Upload to YouTube, embed from there |
| Social media cross-posting | Scope creep, each platform has quirks | Future milestone if needed, not MVP |
| In-house LLM training | 8GB VRAM insufficient, huge cost | Use Qwen3-14B via Ollama, fine-tune LoRAs at most |
| In-house video gen model training | Requires 24GB+ VRAM minimum | Use fal.ai cloud APIs |
| Complex user auth system | Single operator, not SaaS | Simple API key or local-only access |
| Mobile app | No user-facing product | CLI + Web dashboard sufficient |
| Live streaming automation | Completely different domain | Stay with pre-recorded content |

## Feature Dependencies

```
Google Sheets sync → SQLite data layer (Sheets feeds DB)
Script generation → requires channel profile config
Image generation → requires script (scene breakdown)
Video generation → requires images (image-to-video)
TTS generation → requires script (text to speak)
FFmpeg assembly → requires images + video clips + TTS audio
Thumbnail generation → requires script (topic context) + image gen
YouTube upload → requires assembled video + thumbnail + metadata
Multi-channel → requires config system (channel profiles)
Quality gate → requires assembled video (preview before publish)
Batch processing → requires all single-video pipeline steps working
A/B thumbnails → requires thumbnail gen + YouTube API
```

## MVP Recommendation

### Phase 1: Single-Channel Pipeline (Prioritize)

1. **Script generation** - Qwen3-14B via Ollama, single channel
2. **Image generation** - SDXL via ComfyUI headless API
3. **TTS** - IndexTTS-2, single voice
4. **FFmpeg assembly** - Images + audio, basic transitions
5. **YouTube upload** - Automated with metadata

### Phase 2: Production Quality

6. **Video clip generation** - WAN 2.2 via fal.ai
7. **Multi-channel config** - Channel profiles, style presets
8. **Thumbnail generation** - SDXL + text overlay
9. **Quality gate** - Human preview before publish

### Phase 3: Scale

10. **Multi-character TTS** - VibeVoice or IndexTTS-2 multi-voice
11. **Batch processing** - Week-ahead content generation
12. **Content calendar** - Scheduled publishing

### Defer Indefinitely

- A/B thumbnail testing (needs traffic data first)
- Video performance analytics (needs months of data)
- Trend-aware topic generation (nice-to-have, manual topics work)

## Sources

- [fal.ai Video Generation Pricing](https://fal.ai/video)
- [YouTube Upload API Quotas](https://zernio.com/blog/youtube-upload-api)
- [ComfyUI Headless API](https://deepwiki.com/Comfy-Org/ComfyUI/7-api-and-programmatic-usage)
- [Temporal Human-in-the-Loop Patterns](https://docs.temporal.io/develop/python)
- [IndexTTS-2 Korean Support](https://github.com/diodiogod/TTS-Audio-Suite)
