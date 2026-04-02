---
phase: 02-content-pipeline
plan: 01
subsystem: provider-abstraction
tags: [models, provider, channel-config, api-schemas, tdd]
dependency_graph:
  requires: []
  provides:
    - src/models/provider.py (ModelProvider ABC, ProviderType, ModelSpec)
    - src/models/channel_config.py (ChannelConfig frozen model)
    - src/models/script.py (Script, ScriptScene)
    - src/schemas/pipeline.py (API schemas per UI-SPEC)
    - src/services/provider_registry.py (ProviderRegistry singleton)
  affects:
    - all downstream Phase 2 plans that import provider types
tech_stack:
  added:
    - httpx 0.28.1
    - Pillow 12.2.0
    - ffmpeg-python 0.2.0
    - google-api-python-client 2.193.0
    - google-auth-oauthlib
    - pyyaml 6.0.3
    - websocket-client 1.9.0
    - Jinja2 3.1.6
    - rich 14.3.3
    - fal-client 0.13.2
  patterns:
    - Frozen Pydantic model (BaseModel, frozen=True) for ChannelConfig
    - Abstract base classes (ABC) for provider interfaces
    - Module-level singleton + FastAPI Depends() factory for registry
    - Lazy yaml import inside function to avoid missing-module error at class definition time
key_files:
  created:
    - src/models/provider.py
    - src/models/channel_config.py
    - src/models/script.py
    - src/schemas/__init__.py
    - src/schemas/pipeline.py
    - src/services/provider_registry.py
    - tests/test_models_phase2.py
  modified:
    - src/models/__init__.py (re-exports new models)
    - src/config.py (Phase 2 env vars)
    - .env.example (Phase 2 env vars)
    - pyproject.toml (new dependencies)
    - uv.lock
decisions:
  - "Lazy yaml import inside load_channel_config() body instead of module-level: pyyaml not yet installed during Task 1 test run; deferring import avoids ModuleNotFoundError at class definition time"
  - "ModelSpec.parse() splits on first ':' only — model names can contain slashes and colons (e.g. 'fal:fal-ai/wan/image-to-video')"
metrics:
  duration_minutes: 15
  completed_at: "2026-04-02T01:15:31Z"
  tasks_completed: 2
  files_changed: 11
---

# Phase 02 Plan 01: Provider Abstraction + Type Contracts Summary

**One-liner:** Provider ABC layer with ModelSpec parser, frozen ChannelConfig, Script models, and API response schemas — all type contracts for Phase 2 downstream plans.

## What Was Built

All provider abstraction types and pipeline data contracts needed by every downstream Phase 2 plan. No logic — only stable interfaces to code against.

### Files Created

**`src/models/provider.py`**
- `ProviderType` enum: local, fal, replicate, together, fireworks, krea, wavespeed
- `ModelSpec` with `parse("fal:kling-2.5-turbo")` splitting on first `:`
- ABC interfaces: `LLMProvider.generate()`, `ImageProvider.generate()`, `TTSProvider.synthesize()`, `VideoProvider.generate()`

**`src/models/channel_config.py`**
- `ChannelConfig(BaseModel, frozen=True)` with all per-channel settings
- Default models: `video_model="local:wan2gp"`, `tts_model="local:cosyvoice2"`, `llm_model="local:qwen3.5-9b"`
- `load_channel_config(channel_id)` loads from `src/channel_configs/{id}.yaml`

**`src/models/script.py`**
- `ScriptScene`: narration, image_prompt, duration_seconds
- `Script`: title, description, tags, scenes list

**`src/schemas/pipeline.py`**
- `PipelineStatus` enum: running, completed, failed, unknown (per UI-SPEC)
- `PipelineTriggerRequest/Response`, `PipelineStatusResponse`, `CostDetailResponse`, `CostLineItem`
- All field names match UI-SPEC.md exactly

**`src/services/provider_registry.py`**
- `ProviderRegistry` with `register(capability, provider_name, provider)` and `get_provider(capability, model_spec)` 
- Type-specific accessors: `get_llm()`, `get_image()`, `get_tts()`, `get_video()`
- Module-level `registry` singleton + `get_provider_registry()` for FastAPI `Depends()`

## Test Results

```
21 passed in 0.04s
```

All 21 tests pass covering: ModelSpec.parse(), ProviderType values, ChannelConfig frozen/defaults/validate, ScriptScene/Script fields, PipelineStatus enum, PipelineTriggerResponse, PipelineStatusResponse optional fields.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Lazy yaml import to avoid missing-module error**
- **Found during:** Task 1 GREEN phase — test runner failed because `import yaml` at module level raised `ModuleNotFoundError` (pyyaml not yet installed; it's a Task 2 dependency)
- **Issue:** `src/models/channel_config.py` had `import yaml` at module top, causing all `from src.models.*` imports to fail
- **Fix:** Moved `import yaml` inside the `load_channel_config()` function body — yaml is only needed when actually loading a YAML file, not when constructing a `ChannelConfig` instance
- **Files modified:** `src/models/channel_config.py`
- **Commit:** c15940e

## Known Stubs

None. All models are fully specified. `load_channel_config()` requires actual YAML files at runtime but the function itself is complete — missing files raise `FileNotFoundError` (correct behavior).

## Self-Check: PASSED
