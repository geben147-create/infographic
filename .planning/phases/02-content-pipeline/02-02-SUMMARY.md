---
phase: 02-content-pipeline
plan: 02
subsystem: config
tags: [yaml, jinja2, channel-config, youtube-oauth, fonts, pyyaml, httpx, google-auth-oauthlib]

# Dependency graph
requires:
  - phase: 02-content-pipeline
    provides: Phase 2 research and architecture patterns (CHAN-01, CHAN-02)

provides:
  - Two channel YAML configs (channel_01: general/local stack, channel_02: finance/fal.ai stack)
  - Jinja2 prompt templates for LLM script generation (default + finance variants)
  - YouTube OAuth2 one-time setup script (per-channel token generation)
  - Font download helper (NotoSansKR-Bold.ttf for Korean thumbnail text overlay)
  - Asset directory structure (assets/fonts/, voices/) tracked in git

affects: [02-content-pipeline, activities/script_gen, activities/youtube_upload, activities/thumbnail]

# Tech tracking
tech-stack:
  added: [pyyaml==6.0.3, jinja2==3.1.6, httpx==0.28.1, google-auth-oauthlib (already installed via google-auth)]
  patterns:
    - "Channel configs as YAML files in src/channel_configs/ — one file per channel_id"
    - "Jinja2 FileSystemLoader from src/prompt_templates/ for channel-specific script prompts"
    - "OAuth2 token files in data/yt_token_{channel_id}.json — gitignored data dir"

key-files:
  created:
    - src/channel_configs/channel_01.yaml
    - src/channel_configs/channel_02.yaml
    - src/prompt_templates/script_default.j2
    - src/prompt_templates/script_finance.j2
    - scripts/youtube_auth.py
    - scripts/download_font.py
    - assets/fonts/.gitkeep
    - voices/.gitkeep
  modified:
    - pyproject.toml (added pyyaml, jinja2, httpx)
    - uv.lock

key-decisions:
  - "channel_01 uses all-local stack (cosyvoice2 TTS, local:wan2gp video, qwen3.5-9b LLM, vgen_enabled=false)"
  - "channel_02 uses fal.ai stack (kokoro TTS, fal:kling-2.5-turbo video, together:qwen3-8b LLM, vgen_enabled=true)"
  - "Prompt templates include explicit JSON-only instruction to mitigate Qwen3 markdown-wrapping pitfall"
  - "Font download uses httpx (follow_redirects=True) for GitHub raw content redirect chain"
  - "YouTube auth script checks for existing valid tokens before running OAuth flow (idempotent)"

patterns-established:
  - "Pattern 1: Channel YAML + Pydantic frozen model = multi-channel without code branching"
  - "Pattern 2: Jinja2 templates for LLM prompts enable per-channel prompt variation without code changes"
  - "Pattern 3: Setup scripts (scripts/) for one-time human-action steps (auth, assets)"

requirements-completed: [CHAN-01, CHAN-02]

# Metrics
duration: 5min
completed: 2026-04-02
---

# Phase 02 Plan 02: Channel Configs and Setup Scripts Summary

**Two channel YAML configs (general vs finance niche), Jinja2 script prompt templates with JSON-only instruction, YouTube OAuth2 setup script, and NotoSansKR font download helper**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-04-02T01:09:02Z
- **Completed:** 2026-04-02T01:14:01Z
- **Tasks:** 2
- **Files modified:** 10

## Accomplishments

- Created channel_01.yaml (general niche, fully local stack: cosyvoice2/qwen3.5-9b/sdxl, vgen_enabled=false) and channel_02.yaml (finance niche, fal.ai stack: kokoro/kling-2.5-turbo/flux-kontext, vgen_enabled=true)
- Created Jinja2 prompt templates: script_default.j2 (general Korean content) and script_finance.j2 (investment/market analysis focus with professional tone)
- Created scripts/youtube_auth.py with InstalledAppFlow OAuth2 flow, token expiry check/refresh, and idempotent re-run behavior
- Created scripts/download_font.py that fetches NotoSansKR variable font via httpx with file size verification (>1MB guard)
- Established assets/fonts/ and voices/ directory structure tracked in git via .gitkeep files

## Task Commits

1. **Task 1: Channel config YAML files + Jinja2 prompt templates** - `06895ac` (feat)
2. **Task 2: YouTube OAuth2 setup script + Font download script + Asset dirs** - `f313cec` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `src/channel_configs/channel_01.yaml` - General niche channel: local SDXL/cosyvoice2/qwen3.5-9b, vgen_enabled=false
- `src/channel_configs/channel_02.yaml` - Finance niche channel: fal.ai kling/flux-kontext, kokoro TTS, vgen_enabled=true
- `src/prompt_templates/script_default.j2` - Default Jinja2 LLM prompt: Korean script JSON with topic/niche/tags injection
- `src/prompt_templates/script_finance.j2` - Finance variant prompt: investment/market analysis focus, professional tone
- `scripts/youtube_auth.py` - One-time OAuth2 setup: InstalledAppFlow, per-channel token save, expiry refresh
- `scripts/download_font.py` - NotoSansKR download via httpx, 1MB file size guard, idempotent
- `assets/fonts/.gitkeep` - Tracks font directory in git
- `voices/.gitkeep` - Tracks TTS reference audio directory in git
- `pyproject.toml` - Added pyyaml, jinja2, httpx dependencies

## Decisions Made

- channel_01 is the "safe" local-only channel (no fal.ai cost) — good for testing without spending money
- channel_02 demonstrates the full cloud path with vgen_enabled=true to test CHAN-02 multi-channel requirement
- Prompt templates include "Respond ONLY with valid JSON. No markdown, no explanation, no code fences." to address the documented Qwen3 markdown-wrapping pitfall from 02-RESEARCH.md
- Font download uses httpx with follow_redirects=True because GitHub raw content URLs issue a 302 redirect to a CDN

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Windows cp949 default encoding causes UnicodeDecodeError when reading UTF-8 YAML files with Korean characters using default `Path.read_text()`. The Jinja2 FileSystemLoader handles this correctly. Callers loading YAML must use `encoding="utf-8"` explicitly. This is a known Windows Python behavior (not a bug in the files). The ChannelConfig loader (to be built in plan 02-01 or similar) must pass encoding="utf-8" to yaml.safe_load.

## User Setup Required

None for this plan. However, downstream steps require:
- YouTube OAuth2: run `uv run python scripts/youtube_auth.py --channel-id channel_01 --client-secrets client_secrets.json` once per channel after obtaining GCP OAuth2 credentials
- Font download: run `uv run python scripts/download_font.py` once before thumbnail generation

## Next Phase Readiness

- Channel configs ready for ChannelConfig Pydantic model to load via `yaml.safe_load(path.read_text(encoding="utf-8"))`
- Prompt templates ready for Jinja2 rendering in script_gen activity
- OAuth2 script ready for human-action step before upload activities
- Asset directories tracked and ready for font/audio files

## Self-Check: PASSED

All 8 created files confirmed present on disk. Both task commits (06895ac, f313cec) verified in git log.

---
*Phase: 02-content-pipeline*
*Completed: 2026-04-02*
