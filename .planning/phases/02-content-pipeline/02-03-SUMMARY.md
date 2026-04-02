---
phase: 02-content-pipeline
plan: "03"
subsystem: ai-providers
tags: [ollama, llm, tts, cosyvoice, kokoro, temporal, jinja2, httpx]

requires:
  - phase: 02-01
    provides: LLMProvider/TTSProvider ABCs, ModelSpec, ProviderType enums
  - phase: 02-02
    provides: ChannelConfig, load_channel_config, Jinja2 templates

provides:
  - OllamaProvider implementing LLMProvider ABC (src/services/ollama_client.py)
  - generate_script Temporal activity (src/activities/script_gen.py)
  - CosyVoiceTTSProvider and KokoroTTSProvider (src/services/tts_client.py)
  - generate_tts_audio Temporal activity (src/activities/tts.py)

affects: [02-04, 02-05, 02-06, 02-07, pipeline-workflow]

tech-stack:
  added: []
  patterns:
    - "Module-level async helper functions (_synthesize_cosyvoice, _synthesize_kokoro) allow tests to patch at the right seam without mocking class methods"
    - "asyncio.to_thread() wraps sync ML inference to keep Temporal worker event loop unblocked"
    - "Lazy importlib.import_module() for heavy ML deps (CosyVoice2, Kokoro) — raises ApplicationError on missing install"
    - "OllamaProvider._strip_fences() handles both json and plain ``` fences from LLM responses"

key-files:
  created:
    - src/services/ollama_client.py
    - src/activities/script_gen.py
    - src/services/tts_client.py
    - src/activities/tts.py
    - tests/test_script_gen.py
    - tests/test_tts.py
  modified: []

key-decisions:
  - "Module-level _synthesize_cosyvoice/_synthesize_kokoro helpers (not class methods) to enable direct patch target in tests without complex class-level mock setup"
  - "get_tts_provider() factory function parses model_spec and returns correct provider — decouples activity from provider instantiation"
  - "NotImplementedError for non-local LLM providers in generate_script — cloud LLM deferred to Plan 07"
  - "ApplicationError (non_retryable=True) on missing TTS install — Temporal will not retry missing-library failures"

patterns-established:
  - "TDD Red-Green: failing tests committed first, then implementation to pass"
  - "Activity pattern: load config → select provider → call provider → save artifact → return output model"
  - "Provider pattern: ABC in models/provider.py, implementation in services/, factory function for selection"

requirements-completed: [PIPE-01, PIPE-03]

duration: 9min
completed: 2026-04-02
---

# Phase 02 Plan 03: Script Generation and TTS Activities Summary

**Ollama LLM provider and TTS activities (CosyVoice2/Kokoro) wired through provider ABC, generating Script JSON and WAV files with full mock test coverage**

## Performance

- **Duration:** 9 min
- **Started:** 2026-04-02T01:23:14Z
- **Completed:** 2026-04-02T01:32:10Z
- **Tasks:** 2
- **Files created:** 6

## Accomplishments

- OllamaProvider sends structured JSON schema requests to /api/generate and strips markdown fences from LLM response before Script.model_validate_json()
- generate_script activity loads channel config, renders Jinja2 template with topic, calls Ollama, validates Script, saves script.json to run_dir
- CosyVoiceTTSProvider and KokoroTTSProvider use asyncio.to_thread() for sync-to-async bridging and raise ApplicationError (non_retryable) when not installed
- generate_tts_audio activity selects provider from channel config, saves scene_NN.wav, calculates duration from WAV header via wave module
- 21 total tests passing (9 script gen + 12 TTS)

## Task Commits

Each task was committed atomically:

1. **RED: test_script_gen.py (failing)** - `22cbbed` (test)
2. **GREEN: OllamaProvider + generate_script activity** - `0b139ea` (feat)
3. **RED: test_tts.py (failing)** - `19c90f2` (test)
4. **GREEN: TTS providers + generate_tts_audio activity** - `ceea2fb` (feat)

_Note: TDD tasks have two commits each (test RED then feat GREEN)_

## Files Created

- `src/services/ollama_client.py` - OllamaProvider implementing LLMProvider ABC
- `src/activities/script_gen.py` - generate_script Temporal activity with ScriptGenInput/Output
- `src/services/tts_client.py` - CosyVoiceTTSProvider, KokoroTTSProvider, get_tts_provider factory
- `src/activities/tts.py` - generate_tts_audio Temporal activity with TTSInput/Output
- `tests/test_script_gen.py` - 9 tests covering OllamaProvider and generate_script
- `tests/test_tts.py` - 12 tests covering TTS providers and generate_tts_audio

## Decisions Made

- Module-level `_synthesize_cosyvoice` / `_synthesize_kokoro` async helpers allow tests to patch at a clean seam rather than requiring complex class method mocking
- `NotImplementedError` raised for non-local LLM providers in `generate_script` — cloud LLM support deferred to Plan 07
- `ApplicationError(non_retryable=True)` on missing ML library install — Temporal should not retry a missing-library failure
- `get_tts_provider(model_spec)` factory decouples the activity from provider instantiation details

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed mock_post signature in test_topic_injected_into_rendered_prompt**
- **Found during:** Task 1 GREEN verification
- **Issue:** Mock function `async def mock_post(url, **kwargs)` received self as first arg when patching `httpx.AsyncClient.post` (instance method)
- **Fix:** Changed to `async def mock_post(self_or_url, url_or_nothing=None, **kwargs)` to handle method binding correctly
- **Files modified:** tests/test_script_gen.py
- **Verification:** Test passed after fix
- **Committed in:** 0b139ea (Task 1 feat commit)

---

**Total deviations:** 1 auto-fixed (1 bug in test mock)
**Impact on plan:** Minor test mock correction. No scope creep.

## Issues Encountered

- Worktree has its own `.venv` without dev dependencies (pytest-asyncio). Tests must be run via `cd /c/WINDOWS/system32 && uv run pytest .claude/worktrees/agent-a5e4a3e4/tests/...` to pick up the main system32 venv that has all packages.

## Known Stubs

None. All provider synthesize methods with lazy imports are intentional production patterns (not stubs) — CosyVoice2 and Kokoro are genuinely not installed in this environment and are expected to raise ApplicationError.

## Next Phase Readiness

- generate_script and generate_tts_audio activities are ready to be registered in the Temporal workflow
- Both activities use the provider ABC — new providers can be added by implementing the ABC and updating get_tts_provider()
- Plan 04 (image generation) follows the same provider pattern established here

## Self-Check: PASSED

All 6 source/test files confirmed on disk. All 4 task commits (22cbbed, 0b139ea, 19c90f2, ceea2fb) confirmed in git log. Final verification: 21/21 tests passing.

---
*Phase: 02-content-pipeline*
*Completed: 2026-04-02*
