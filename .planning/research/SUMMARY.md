# Research Summary: YouTube Video Automation Pipeline

**Domain:** Automated multi-channel YouTube video production
**Researched:** 2026-04-01
**Overall confidence:** HIGH

## Executive Summary

The optimal stack for a 2025/2026 YouTube video automation pipeline on an RTX 4070 8GB + cloud hybrid setup is **Python (FastAPI + Temporal)** for orchestration, replacing n8n for the core pipeline. n8n's visual builder is excellent for prototyping but breaks down for GPU-routed, multi-step, multi-channel video production workflows. Temporal's durable execution model, native GPU task routing via Task Queues, and battle-tested video processing track record (Washington Post, Descript) make it the clear choice for this domain.

The image generation stack should center on **SDXL via ComfyUI** for local generation (well within 8GB VRAM), with **FLUX Q4 GGUF** for higher-quality hero images. Video generation must be cloud-based -- 8GB VRAM is insufficient for video gen models, so **WAN 2.2/2.5 via fal.ai** at $0.05-0.10/sec is the cost-effective choice. For Korean TTS, **IndexTTS-2** leads with native Korean support, zero-shot voice cloning, and 150ms streaming latency, while **VibeVoice** offers multi-character capability (up to 4 speakers) with experimental Korean support.

The data architecture should use **SQLite as the source of truth** with Google Sheets as a human-facing input/dashboard layer only. Google Sheets lacks ACID transactions, has API quota limits, and cannot handle concurrent pipeline writes reliably. The sync pattern is: Sheets -> SQLite (on trigger) -> Pipeline execution -> SQLite -> Sheets (results notification).

Cost per video is estimated at $1.25-2.50, driven primarily by cloud video generation. The key cost optimization is mixing AI-generated video clips (for dynamic scenes) with FFmpeg Ken Burns pan/zoom effects on still images (for narration-over scenes), reducing fal.ai API calls by 50-70%.

## Key Findings

**Stack:** Python 3.12 + FastAPI + Temporal + SQLite + ComfyUI + Ollama (Qwen3-14B) + IndexTTS-2 + fal.ai (WAN 2.2) + FFmpeg
**Architecture:** Temporal workflow orchestration with typed worker pools (GPU/CPU/API), ComfyUI headless API for image gen, channel config as immutable data objects
**Critical pitfall:** GPU VRAM contention -- ComfyUI, TTS, and Ollama cannot run concurrently on 8GB. Must serialize GPU tasks with max_concurrent=1.

## Implications for Roadmap

Based on research, suggested phase structure:

1. **Foundation + Single Channel Pipeline** - Build the core: Temporal setup, SQLite data layer, script gen (Ollama), image gen (ComfyUI SDXL), basic TTS (IndexTTS-2 single voice), FFmpeg assembly, YouTube upload.
   - Addresses: Table stakes features, proves end-to-end flow
   - Avoids: VRAM contention (sequential GPU tasks from day 1), Sheets-as-SSOT (SQLite from day 1)

2. **Production Quality + Multi-Channel** - Add video generation (fal.ai WAN), multi-channel config system, thumbnail generation, quality gate (human review), niche-specific LoRAs/prompts.
   - Addresses: Multi-channel support, visual quality upgrade
   - Avoids: YouTube quota issues (separate GCP projects), cost spiral (mixed video + Ken Burns)

3. **Scale + Automation** - Multi-character TTS, batch processing, content calendar, cost tracking dashboard, automated cleanup.
   - Addresses: Differentiator features, operational maturity
   - Avoids: File cleanup neglect, LLM quality variance (fact-check gate)

4. **n8n Migration** - Decommission remaining n8n workflows, move trigger/notification logic to Temporal schedules + FastAPI webhooks.
   - Addresses: Technical debt, single platform
   - Can run in parallel with phases 1-3

**Phase ordering rationale:**
- Phase 1 before 2: Must prove single-channel works before multi-channel config
- Phase 2 before 3: Video generation quality is more valuable than batch quantity
- Phase 4 (n8n migration) is independent -- existing n8n workflows can continue running while new pipeline is built alongside

**Research flags for phases:**
- Phase 1: IndexTTS-2 Korean quality needs hands-on testing before committing (MEDIUM confidence on pronunciation quality for medical/financial terms)
- Phase 2: fal.ai cost optimization needs real-world measurement (cost estimates are theoretical)
- Phase 2: VibeVoice Korean multi-character quality is "experimental" per Microsoft -- may need cloud TTS fallback
- Phase 3: Temporal learning curve is real but one-time (1-2 weeks investment)

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack (orchestration) | HIGH | Multiple 2026 sources confirm Python > n8n for ML pipelines. Temporal video processing case studies are concrete. |
| Stack (image gen) | HIGH | SDXL on 8GB VRAM is well-documented, ComfyUI API is mature. |
| Stack (video gen) | HIGH | fal.ai pricing and WAN model availability confirmed from official source. |
| Stack (TTS) | MEDIUM | IndexTTS-2 Korean claimed, VibeVoice Korean is "experimental." Need hands-on testing. |
| Features | HIGH | Feature landscape based on concrete technical capabilities. |
| Architecture | HIGH | Temporal patterns validated by WashPost/Descript case studies. Worker pool pattern is standard. |
| Pitfalls | HIGH | VRAM contention, API quotas, Sheets limitations are well-documented failure modes. |
| Cost estimates | MEDIUM | Per-video costs theoretical, need real-world measurement. fal.ai pricing from official docs. |

## Gaps to Address

- **IndexTTS-2 Korean pronunciation quality**: Need hands-on testing with domain-specific vocabulary (medical, financial, crypto terms)
- **VibeVoice multi-character Korean**: Experimental status means quality is unknown until tested
- **Temporal operational complexity**: Self-hosted Temporal server requires Docker Compose setup and monitoring
- **ComfyUI SDXL LoRA quality per niche**: Need to identify best community checkpoints/LoRAs for health, stock, crypto visual styles
- **FFmpeg NVENC encoding quality**: Need to verify hardware encoding quality is acceptable for YouTube (vs software encoding)
- **fal.ai reliability/latency in production**: Need to measure actual cold start times and failure rates under sustained load
