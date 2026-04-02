---
phase: 02-content-pipeline
plan: "04"
subsystem: image-video-generation
tags: [comfyui, fal-ai, ffmpeg, ken-burns, temporal-activity, cost-tracking]
dependency_graph:
  requires: [02-01]
  provides: [image-gen-activity, video-gen-activity, cost-tracker]
  affects: [02-05, 02-06]
tech_stack:
  added: [websocket-client, fal-client, ffmpeg-python, httpx]
  patterns: [provider-abstraction, asyncio-to-thread, file-locking, tdd]
key_files:
  created:
    - src/services/comfyui_client.py
    - src/services/fal_client.py
    - src/services/cost_tracker.py
    - src/activities/image_gen.py
    - src/activities/video_gen.py
    - tests/test_image_gen.py
    - tests/test_video_gen.py
  modified: []
decisions:
  - "settings imported at module level in video_gen.py so tests can patch src.activities.video_gen.settings"
  - "CostTracker uses Windows lock-file sentinel (.lock) since msvcrt locking is unreliable with os.O_RDWR + ftruncate"
  - "ComfyUI test emits 'executed' WS message with image info to avoid history endpoint fallback in mock"
  - "ActivityEnvironment.run() is a coroutine — activity tests must be async"
metrics:
  duration_seconds: 592
  completed_date: "2026-04-02"
  tasks_completed: 2
  files_created: 7
---

# Phase 02 Plan 04: Image/Video Generation + Cost Tracking Summary

**One-liner:** ComfyUI WebSocket image provider, fal.ai image/video providers, Ken Burns FFmpeg fallback, and thread-safe cost tracker — all wired as Temporal activities with full TDD coverage.

## What Was Built

### src/services/comfyui_client.py
`ComfyUIProvider(ImageProvider)` — connects to ComfyUI's headless WebSocket API, patches a base SDXL workflow with the user prompt and checkpoint name, waits for the `executing{node=None}` completion signal, then fetches the generated image via `/view`. Uses `asyncio.to_thread()` to wrap the sync WebSocket I/O, and sets `ws.settimeout(120)` per the research requirement.

### src/services/fal_client.py
- `FalImageProvider(ImageProvider)` — calls `fal_client.run_async()` with model + image_size arguments, downloads result URL via httpx, returns bytes.
- `FalVideoProvider(VideoProvider)` — uploads source image via `fal_client.upload_file_async()`, submits generation via `fal_client.submit_async()`, streams progress events, downloads result video to a temp file, and computes cost as `cost_per_second × duration_seconds`. Supports `kling-2.5-turbo` and WAN 2.2/2.5 models.

### src/services/cost_tracker.py
`CostTracker` with `CostEntry` Pydantic model. Reads/writes `cost_log.json` (JSON array). Uses Windows `.lock` sentinel file for mutual exclusion (msvcrt fd-based locking is unreliable with ftruncate). Provides `log()`, `get_run_total()`, `get_run_breakdown()`.

### src/activities/image_gen.py
`generate_scene_image` Temporal activity — loads channel config, parses `image_model` spec, selects `ComfyUIProvider` (local) or `FalImageProvider` (fal), generates bytes, saves to `{run_dir}/images/scene_{NN:02d}.png`.

### src/activities/video_gen.py
`generate_scene_video` Temporal activity — checks `config.vgen_enabled and settings.fal_key` to route to either:
- **fal.ai path**: `FalVideoProvider.generate()` → move temp file → log cost (non-zero)
- **Ken Burns path**: `ken_burns_clip()` via `asyncio.to_thread` → log $0.00 cost

`ken_burns_clip()` uses `ffmpeg-python` with `zoompan` filter at 25fps/1920×1080, with `h264_nvenc` primary and `libx264` software fallback.

## Test Results

```
tests/test_image_gen.py  — 12/12 passed
tests/test_video_gen.py  —  8/8 passed
Total: 20/20 passed, 0 failed
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] ActivityEnvironment.run() returns a coroutine, not a result**
- **Found during:** Task 1, test execution
- **Issue:** Tests called `env.run(...)` and assigned result directly — the return value is a coroutine that needs `await`
- **Fix:** Made all activity tests `async` and used `await env.run(...)`
- **Files modified:** tests/test_image_gen.py

**2. [Rule 1 - Bug] ComfyUI WebSocket test lacked 'executed' message with image info**
- **Found during:** Task 1, test execution
- **Issue:** Production code collects images from `executed` WS events; test mock only sent `executing` events, so `output_images` was empty and the history endpoint fallback was called (which failed with the mock)
- **Fix:** Added an `executed` message with `output.images` list to `_make_ws_messages()` so the image info is captured before the completion signal
- **Files modified:** tests/test_image_gen.py

**3. [Rule 1 - Bug] settings imported locally inside activity function — unpatchable**
- **Found during:** Task 2, test execution
- **Issue:** `from src.config import settings` was inside `generate_scene_video()`, so `patch("src.activities.video_gen.settings")` raised AttributeError
- **Fix:** Moved `from src.config import settings` to module level
- **Files modified:** src/activities/video_gen.py

## Known Stubs

None — all implemented functionality is wired end-to-end with real logic (mocked only in tests).

## Self-Check

Checking created files exist:
- [x] src/services/comfyui_client.py
- [x] src/services/fal_client.py
- [x] src/services/cost_tracker.py
- [x] src/activities/image_gen.py
- [x] src/activities/video_gen.py
- [x] tests/test_image_gen.py
- [x] tests/test_video_gen.py

Checking commits exist:
- [x] 721378c — Task 1: image gen activity + providers + cost tracker
- [x] 7b5c971 — Task 2: video gen activity + Ken Burns fallback

## Self-Check: PASSED
