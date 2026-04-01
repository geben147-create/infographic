# YouTube Video Automation Pipeline

## What This Is

RTX 4070 8GB + 클라우드 하이브리드 환경에서 동작하는 다채널 YouTube 영상 자동 제작 파이프라인. 토픽/키워드 입력만으로 스크립트 생성, AI 이미지/영상 생성, 한국어 TTS, FFmpeg 조립, YouTube 업로드까지 전 과정을 자동화한다.

## Core Value

**토픽 하나로 완성된 YouTube 영상을 자동 생성하고 업로드하는 것.** 단일 채널에서 end-to-end 파이프라인이 동작해야 나머지 모든 기능(다채널, 배치, 품질 게이트)이 의미를 갖는다.

## Requirements

### Validated

- ✓ **ORCH-01~03**: Temporal 워크플로우 오케스트레이션 + typed worker pools (GPU/CPU/API) + durable retry — Validated in Phase 1: Infrastructure
- ✓ **DATA-01~03**: Google Sheets → SQLite 동기화 + 파이프라인 상태 SQLite 전용 관리 + 결과 역동기화 — Validated in Phase 1: Infrastructure
- ✓ **FILE-01~02**: data/pipeline/{run_id}/ 디렉토리 구조 + cleanup activity — Validated in Phase 1: Infrastructure

### Active

- [ ] Qwen3-14B(Ollama) 기반 스크립트 자동 생성
- [ ] ComfyUI SDXL 기반 장면별 이미지 생성
- [ ] fal.ai WAN 2.2 기반 AI 영상 클립 생성
- [ ] IndexTTS-2 한국어 TTS 음성 생성
- [ ] FFmpeg 영상 조립 (이미지 + 영상 + 오디오 + 전환효과)
- [ ] YouTube Data API v3 자동 업로드
- [ ] 다채널 지원 (채널별 Config 프로필)
- [ ] Google Sheets → SQLite 데이터 동기화
- [ ] 썸네일 자동 생성 (SDXL + 텍스트 오버레이)
- [ ] 품질 게이트 (업로드 전 사람 검토)
- [ ] 파이프라인 상태 대시보드
- [ ] 배치 처리 (일주일치 콘텐츠 야간 생성)
- [ ] 콘텐츠 캘린더 예약 발행
- [ ] 다중 캐릭터 음성 연기

### Out of Scope

- 실시간 영상 편집 UI — ComfyUI GUI로 수동 편집 가능
- 자체 영상 호스팅 — YouTube가 플랫폼
- SNS 크로스 포스팅 — 스코프 크립, 각 플랫폼 퀄크
- 자체 LLM 학습 — 8GB VRAM 부족, Ollama로 충분
- 자체 비디오 생성 모델 학습 — 24GB+ 필요, fal.ai 사용
- 복잡한 사용자 인증 — 단일 운영자, SaaS 아님
- 모바일 앱 — CLI + 웹 대시보드로 충분
- 라이브 스트리밍 — 사전 녹화 콘텐츠에 집중

## Context

- **하드웨어:** RTX 4070 8GB, GPU VRAM 8GB 제약 → ComfyUI/TTS/Ollama 동시 실행 불가, 순차 실행 필수
- **스택:** Python 3.12 + FastAPI + Temporal + SQLite + ComfyUI + Ollama + IndexTTS-2 + fal.ai + FFmpeg
- **아키텍처:** Temporal 워크플로우 오케스트레이션, typed worker pools (GPU/CPU/API)
- **비용:** 영상당 $1.25-2.50 예상 (주로 fal.ai 클라우드 비디오 생성)
- **최적화:** AI 영상 + FFmpeg Ken Burns 효과 혼합으로 fal.ai 비용 50-70% 절감
- **데이터:** Google Sheets는 입력 UI만, SQLite가 진짜 SSOT
- **TTS 리스크:** IndexTTS-2 한국어 발음 품질 (의료/금융 용어) 실제 테스트 필요

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Temporal > n8n | n8n은 프로토타이핑 좋지만 GPU 라우팅/멀티스텝 영상 파이프라인에서 한계 | Pending |
| SQLite > Sheets as SSOT | Sheets는 ACID 없음, API 쿼터, 동시 쓰기 불안정 | Pending |
| fal.ai for video gen | 8GB VRAM으로 로컬 비디오 생성 불가, fal.ai $0.05-0.10/sec | Pending |
| SDXL via ComfyUI | 8GB VRAM에 충분, 헤드리스 API 성숙 | Pending |
| Qwen3-14B via Ollama | 로컬 LLM, 무료, Gemini fallback | Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-02 after Phase 1: Infrastructure completion*
