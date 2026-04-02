# Requirements

**Project:** YouTube Video Automation Pipeline
**Version:** v1
**Last updated:** 2026-04-01

## v1 Requirements

### Core Pipeline (PIPE)

- [x] **PIPE-01**: 토픽/키워드 입력 시 Qwen3-14B(Ollama)가 구조화된 스크립트(제목, 설명, 장면별 내레이션+이미지 프롬프트+길이, 태그) JSON을 생성한다
- [x] **PIPE-02**: 스크립트의 각 장면에 대해 ComfyUI SDXL이 이미지를 생성한다 (헤드리스 API)
- [x] **PIPE-03**: 스크립트의 각 장면 내레이션에 대해 IndexTTS-2가 한국어 TTS 오디오를 생성한다
- [x] **PIPE-04**: FFmpeg가 이미지+오디오+전환효과를 조립하여 최종 MP4를 생성한다 (NVENC 하드웨어 인코딩)
- [x] **PIPE-05**: YouTube Data API v3를 통해 메타데이터(제목, 설명, 태그, 카테고리)와 함께 자동 업로드한다
- [x] **PIPE-06**: 썸네일을 SDXL + Pillow 텍스트 오버레이로 자동 생성하여 업로드 시 첨부한다

### Video Generation — Optional (VGEN)

- [x] **VGEN-01**: fal.ai WAN 2.2 API 키가 설정된 경우 장면별 AI 영상 클립을 생성한다 (API 키 없으면 이미지+Ken Burns로 대체)
- [x] **VGEN-02**: 영상 생성 시 영상당 비용($/초)을 실시간 표시하고 cost_log.json에 기록한다
- [x] **VGEN-03**: 채널 Config에서 영상 생성 on/off를 토글할 수 있다

### Multi-Channel (CHAN)

- [x] **CHAN-01**: 채널별 Config 프로필(니치, 언어, 체크포인트, LoRA, TTS 음성, 프롬프트 템플릿, 썸네일 스타일, 태그, 발행 스케줄)을 Pydantic frozen model로 관리한다
- [x] **CHAN-02**: 단일 워크플로우가 channel_id 파라미터로 모든 채널을 처리한다 (채널별 코드 복사 금지)

### Data Layer (DATA)

- [x] **DATA-01**: Google Sheets에서 콘텐츠 입력 데이터를 SQLite로 동기화한다 (Sheets는 UI만, SQLite가 SSOT)
- [x] **DATA-02**: 파이프라인 실행 중 모든 상태/메타데이터는 SQLite에만 읽기/쓰기한다
- [x] **DATA-03**: 파이프라인 완료 후 결과를 Sheets에 역동기화한다 (YouTube URL, 상태)

### Orchestration (ORCH)

- [x] **ORCH-01**: Temporal 워크플로우가 전체 파이프라인을 오케스트레이션한다 (Activity-per-Service 패턴)
- [x] **ORCH-02**: GPU/CPU/API 워커 풀을 Temporal Task Queue로 분리한다 (GPU maxConcurrent=1)
- [x] **ORCH-03**: 실패 시 Temporal의 durable execution으로 해당 Activity만 재시도한다

### Quality & Operations (OPS)

- [ ] **OPS-01**: 품질 게이트 — 업로드 전 사람이 미리보기하고 승인/거부할 수 있다 (Temporal human-in-the-loop signal)
- [ ] **OPS-02**: 품질 게이트는 Config에서 on/off 토글 가능하다 (자동 승인 모드)
- [x] **OPS-03**: 배치 처리 모드 — 여러 영상을 큐에 넣어 야간 일괄 생성할 수 있다
- [x] **OPS-04**: 콘텐츠 캘린더 — Temporal scheduled workflows로 예약 발행한다
- [x] **OPS-05**: 영상별 API 비용을 추적하고 대시보드에 표시한다 (fal.ai, Gemini 등 유료 API 호출당 비용)
- [ ] **OPS-06**: 파이프라인 상태 대시보드 — Temporal Web UI + FastAPI 커스텀 엔드포인트

### File Management (FILE)

- [x] **FILE-01**: 파이프라인 아티팩트는 `/data/pipeline/{workflow_run_id}/` 구조를 따른다
- [x] **FILE-02**: 파이프라인 완료 후 중간 파일을 정리하는 cleanup Activity가 있다

## v2 Requirements (Deferred)

- 다중 캐릭터 음성 연기 (VibeVoice/IndexTTS-2 multi-voice) — IndexTTS-2 한국어 품질 검증 후
- 니치별 스타일 프리셋 (LoRA per channel) — 기본 파이프라인 안정화 후
- A/B 썸네일 테스트 — 트래픽 데이터 필요
- 트렌드 토픽 자동 발견 — 수동 토픽 입력으로 충분
- 영상 성과 분석 (YouTube Analytics 피드백 루프) — 수개월 데이터 필요
- SEO 최적화 메타데이터 고도화 — 기본 메타데이터 생성은 v1에 포함

## Out of Scope

- 실시간 영상 편집 UI — ComfyUI GUI로 수동 편집
- 자체 영상 호스팅 — YouTube가 플랫폼
- SNS 크로스 포스팅 — 각 플랫폼 quirks, 스코프 크립
- 자체 LLM/비디오 모델 학습 — VRAM 부족, 외부 서비스 사용
- 복잡한 인증 시스템 — 단일 운영자
- 모바일 앱 — CLI + 웹 대시보드
- 라이브 스트리밍 — 사전 녹화 콘텐츠

## Traceability

| REQ-ID | Phase | Status |
|--------|-------|--------|
| ORCH-01 | Phase 1 | Complete |
| ORCH-02 | Phase 1 | Complete |
| ORCH-03 | Phase 1 | Complete |
| DATA-01 | Phase 1 | Complete |
| DATA-02 | Phase 1 | Complete |
| DATA-03 | Phase 1 | Complete |
| FILE-01 | Phase 1 | Complete |
| FILE-02 | Phase 1 | Complete |
| PIPE-01 | Phase 2 | Complete |
| PIPE-02 | Phase 2 | Complete |
| PIPE-03 | Phase 2 | Complete |
| PIPE-04 | Phase 2 | Complete |
| PIPE-05 | Phase 2 | Complete |
| PIPE-06 | Phase 2 | Complete |
| VGEN-01 | Phase 2 | Complete |
| VGEN-02 | Phase 2 | Complete |
| VGEN-03 | Phase 2 | Complete |
| CHAN-01 | Phase 2 | Complete |
| CHAN-02 | Phase 2 | Complete |
| OPS-01 | Phase 3 | Pending |
| OPS-02 | Phase 3 | Pending |
| OPS-03 | Phase 3 | Complete |
| OPS-04 | Phase 3 | Complete |
| OPS-05 | Phase 3 | Complete |
| OPS-06 | Phase 3 | Pending |

---
*Generated: 2026-04-01*
