# Phase 2: Content Pipeline - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-02
**Phase:** 02-content-pipeline
**Areas discussed:** 오픈소스 비디오 모델 선정, 모델 스왑 아키텍처, 클라우드 프로바이더, TTS 변경, 전체 모델 스택

---

## 오픈소스 비디오 모델 선정

### 로컬 모델 선택

| Option | Description | Selected |
|--------|-------------|----------|
| Wan 1.3B + CogVideoX | Wan 1.3B 기본 + CogVideoX-5B(양자화) I2V 특화. 둘 다 8GB 동작 | ✓ |
| 클라우드 전용 (fal.ai) | 로컬 설치 없음, fal.ai에서 Wan 2.6+ 사용 | |
| 로컬 + 클라우드 하이브리드 | CogVideoX 로컬 우선 → 실패 시 fal.ai fallback | |
| ComfyUI AnimateDiff | AnimateDiff-Lightning ComfyUI 네이티브 | |

**User's choice:** Wan 1.3B + CogVideoX (Recommended)
**Notes:** 사용자가 별도로 Wan 2.6 (Wan2GP), LTX-Video 2.0도 추가 제시

### 사용자 제시 전체 모델 스택

사용자가 비디오뿐 아니라 전체 카테고리에 대해 상세 추천 리스트 제공:

**비디오:** Wan 2.6 (Wan2GP) + LTX-Video 2.0
**이미지:** SDXL (Juggernaut XL) + FLUX.1-schnell (Q4) + FLUX.1-dev (Q5_K_S)
**TTS:** CosyVoice2-0.5B (primary) + Fish Speech S1-mini (secondary) — IndexTTS-2 한국어 미지원 발견
**LLM:** Qwen3.5-9B (primary) + Qwen3 8B (fallback)

---

## 모델 스왑 아키텍처

| Option | Description | Selected |
|--------|-------------|----------|
| ChannelConfig에 모델명 직접 지정 | channel.yaml에 image_model, tts_engine 등 명시. Enum 관리 | ✓ |
| 모델 레지스트리 패턴 | ModelRegistry 클래스가 프로바이더/엔드포인트/VRAM 관리 | |
| Provider 추상화 레이어 | ImageProvider/VideoProvider 인터페이스 + Strategy 패턴 | |

**User's choice:** ChannelConfig에 모델명 직접 지정
**Notes:** 유료 모델 옆에 비용 메모를 넣고, 사용자가 그 비용 메모를 수정 가능하도록 (model_costs.yaml)

---

## 클라우드 API 프로바이더

| Option | Description | Selected |
|--------|-------------|----------|
| fal.ai + Replicate 우선 | Phase 2에서 2개만 구현, 나머지 Enum 예약 | 부분 |
| 전부 구현 | 7개 프로바이더 모두 Phase 2 | |
| fal.ai만 우선 | 단일 프로바이더, 600+ 모델 커버 | |

**User's choice:** fal.ai + Replicate + kai.ai + Together.ai (4개)
**Notes:** 사용자가 kai.ai와 Together.ai를 추가 요청. 각각 API 클라이언트 + 에러 처리 + 비용 추적 구현

---

## TTS 변경

**User's choice:** 사용자 요구대로 진행
**Notes:** CosyVoice2-0.5B primary + Fish Speech S1-mini secondary. IndexTTS-2 제거 (한국어 공식 미지원). 사용자가 "내가 요구한 대로 해줘"라고 명확히 지시.

---

## 전체 모델 스택 확정

| Option | Description | Selected |
|--------|-------------|----------|
| 맞아, 그대로 진행 | 모든 모델 변경사항 확인 완료 | ✓ |
| 수정 필요 | 일부 변경 | |

**User's choice:** 맞아, 그대로 진행
**Notes:** 없음

---

## Claude's Discretion

- Wan2GP 설치 스크립트 세부사항
- CosyVoice2 배포 모드
- ComfyUI FLUX 워크플로우 구조
- Enum 값 이름
- 모델 간 VRAM 충돌 방지 전략
- kai.ai API 클라이언트 구현 세부

## Deferred Ideas

- Fireworks.ai, krea.ai, WaveSpeedAI — Enum 예약만, Phase 3/v2
- AnimateDiff-Lightning — SD 해상도 제한
- VibeVoice 다중 캐릭터 — v2
- LoRA per channel — v2
