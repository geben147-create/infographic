---
phase: 02-content-pipeline
plan: 05
subsystem: media
tags: [ffmpeg, ffmpeg-python, pillow, nvenc, libx264, temporal, thumbnail, video-assembly]

requires:
  - phase: 02-content-pipeline/02-03
    provides: TTS activity producing per-scene WAV audio files
  - phase: 02-content-pipeline/02-04
    provides: image_gen and video_gen activities producing per-scene MP4 clips

provides:
  - assemble_video Temporal activity: concat scene clips + audio → final MP4 (h264_nvenc + libx264 fallback)
  - generate_thumbnail Temporal activity: 1280x720 JPEG with Korean text overlay under 2MB
  - build_concat_file() helper: writes FFmpeg concat demuxer text file
  - merge_audio_video() helper: merges silent video clip with WAV audio track

affects: [02-06, 02-07, pipeline-workflow]

tech-stack:
  added: []
  patterns:
    - "ffmpeg._run.Error imported directly so except clause survives full ffmpeg module mock in tests"
    - "asyncio.to_thread() for all blocking FFmpeg/Pillow CPU operations in async Temporal activities"
    - "Two-attempt NVENC→libx264 pattern: try h264_nvenc, catch FfmpegError with encoder/nvenc in stderr, retry libx264"
    - "Pillow font fallback: ImageFont.truetype → load_default with structlog warning on FileNotFoundError"

key-files:
  created:
    - src/activities/video_assembly.py
    - src/activities/thumbnail.py
    - tests/test_video_assembly.py
    - tests/test_thumbnail.py
  modified: []

key-decisions:
  - "Import ffmpeg._run.Error directly (not ffmpeg.Error via module alias) so the except clause survives full ffmpeg module patching in tests"
  - "Thumbnail text positioned at bottom-left (20, 580) with 2px drop shadow — large enough for YouTube click-through visibility"
  - "JPEG quality=90 primary, auto-reduced to 75 if file exceeds 2MB YouTube limit"

patterns-established:
  - "FfmpegError import pattern: from ffmpeg._run import Error as FfmpegError avoids mock breakage"
  - "All blocking media operations wrapped in asyncio.to_thread() helper functions"

requirements-completed: [PIPE-04, PIPE-06]

duration: 6min
completed: 2026-04-02
---

# Phase 02 Plan 05: Video Assembly & Thumbnail Summary

**FFmpeg concat-demuxer assembly of scene clips into final MP4 (h264_nvenc/libx264 fallback) plus Pillow-based 1280x720 Korean thumbnail with drop-shadow text overlay, both as Temporal activities**

## Performance

- **Duration:** 6 min
- **Started:** 2026-04-02T01:38:21Z
- **Completed:** 2026-04-02T01:44:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- `assemble_video` Temporal activity: verifies all scene video/audio files exist, merges each pair with ffmpeg, builds concat demuxer file, encodes final MP4 with h264_nvenc (libx264 fallback on encoder error)
- `generate_thumbnail` Temporal activity: loads first scene image (or solid dark background), resizes to 1280x720, draws Korean title with 2px drop shadow, saves JPEG under 2MB YouTube limit
- 17 tests passing across both activities (TDD: all tests written before implementation)

## Task Commits

1. **Task 1: FFmpeg video assembly activity** - `5cdf7ac` (feat)
2. **Task 2: Thumbnail generation activity** - `dffceb0` (feat)

## Files Created/Modified

- `src/activities/video_assembly.py` - assemble_video Temporal activity, build_concat_file(), merge_audio_video()
- `src/activities/thumbnail.py` - generate_thumbnail Temporal activity, _build_thumbnail(), _load_font()
- `tests/test_video_assembly.py` - 9 tests: concat file format, merge helper, NVENC fallback, missing files error, output path
- `tests/test_thumbnail.py` - 8 tests: resize, output path, 2MB limit, fallback background, text overlay, font fallback

## Decisions Made

- **FfmpegError import pattern**: `from ffmpeg._run import Error as FfmpegError` rather than `except ffmpeg.Error` — when `ffmpeg` is fully patched in tests, `ffmpeg.Error` becomes a MagicMock (not a BaseException subclass), which causes `TypeError: catching classes that do not inherit from BaseException`. Importing the real class at module load time before patching avoids this.
- **JPEG quality strategy**: quality=90 primary, auto-resave at quality=75 if file exceeds 2MB. Keeps thumbnails high quality in practice (1280x720 JPEG at q=90 is ~200-400KB) while guaranteeing YouTube compliance.
- **Text position**: bottom-left (x=20, y=580) with 2px shadow offset. Avoids YouTube UI chrome that overlays top/bottom-right corners.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed TypeError in NVENC fallback when ffmpeg module is fully mocked**
- **Found during:** Task 1 (GREEN phase, first test run)
- **Issue:** `except ffmpeg.Error` in `_run_concat()` raised `TypeError: catching classes that do not inherit from BaseException` when the `ffmpeg` module was patched wholesale in tests (MagicMock replaces `ffmpeg.Error`)
- **Fix:** Added `from ffmpeg._run import Error as FfmpegError` at module import time; updated except clause to `except FfmpegError`. Real class captured before any patching occurs.
- **Files modified:** `src/activities/video_assembly.py`
- **Verification:** `test_assemble_video_nvenc_fallback` passes; fallback path confirmed (libx264 in call_log_codecs)
- **Committed in:** `5cdf7ac` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — bug in mock interaction)
**Impact on plan:** Fix was necessary for test correctness and real runtime reliability. No scope creep.

## Issues Encountered

- None beyond the FfmpegError mock interaction documented above.

## User Setup Required

None - no external service configuration required. Both activities use local FFmpeg and Pillow (already in project dependencies).

## Next Phase Readiness

- `assemble_video` and `generate_thumbnail` are ready to be wired into the main pipeline workflow
- Both activities accept `run_dir` from the pipeline directory setup (02-01)
- Font file at `assets/fonts/NotoSansKR-Bold.ttf` should be added to the repo for proper Korean text rendering (optional — Pillow default font is used as fallback)
- Wave 3 complete: plan 02-05 done

---
*Phase: 02-content-pipeline*
*Completed: 2026-04-02*

## Self-Check: PASSED

- FOUND: src/activities/video_assembly.py
- FOUND: src/activities/thumbnail.py
- FOUND: tests/test_video_assembly.py
- FOUND: tests/test_thumbnail.py
- FOUND: .planning/phases/02-content-pipeline/02-05-SUMMARY.md
- FOUND commit: 5cdf7ac (video assembly)
- FOUND commit: dffceb0 (thumbnail)
- Tests: 17/17 passed
