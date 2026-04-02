# Frontend Pages Specification

> 백엔드 API 13개 엔드포인트, 3개 DB 테이블, 2개 워크플로, 12개 액티비티 기반

---

## Page Map (7 pages)

```
/                    → Dashboard (Overview)
/pipelines           → Pipeline Runs List
/pipelines/:id       → Pipeline Detail (Single Run)
/trigger             → New Pipeline (Trigger Form)
/costs               → Cost Analytics
/channels            → Channel Management
/settings            → System Settings & Health
```

---

## Page 1: Dashboard (Overview)

**목적**: 한눈에 전체 상태 파악 — Stripe Dashboard 메인 화면 참고

### UI 구성요소

| 영역 | 컴포넌트 | 데이터 |
|------|----------|--------|
| 상단 스탯 카드 4개 | StatCard | Total Runs, Running Now, Ready to Upload, 30일 비용 |
| 최근 파이프라인 5개 | Mini Table | 최근 5개 run (workflow_id, channel, status, time) |
| 비용 추이 차트 | Line/Bar Chart | 일별/주별 비용 트렌드 |
| 시스템 상태 | Health Bar | Temporal, SQLite, Disk 상태 |
| 빠른 실행 | CTA Button | "New Video" → /trigger 이동 |

### 연결 API

| API | Method | 용도 | 폴링 |
|-----|--------|------|------|
| `GET /api/dashboard/runs?limit=5` | GET | 최근 5개 run | 30초 |
| `GET /api/dashboard/costs?days=30` | GET | 30일 비용 집계 | 30초 |
| `GET /health` | GET | 시스템 상태 | 30초 |

### UX 유의사항

- Empty State: 첫 방문 시 "Create your first video" CTA + 일러스트
- 스탯 카드: 숫자가 바뀔 때 count-up 애니메이션
- Running 상태 run이 있으면 pulse 애니메이션으로 주의 끌기
- 에러 시 toast notification (빨간 배너 아님)
- Skeleton loading: 데이터 로드 전 회색 블록 표시

---

## Page 2: Pipeline Runs List (/pipelines)

**목적**: 전체 파이프라인 실행 이력 — Stripe Payments 목록 참고

### UI 구성요소

| 영역 | 컴포넌트 | 데이터 |
|------|----------|--------|
| 필터 바 | Select + Search | 채널 필터, 상태 필터, 검색 |
| 데이터 테이블 | Full Table | workflow_id, channel, status, cost, started, completed, actions |
| 페이지네이션 | Prev/Next + Page Info | offset/limit 기반 |
| 벌크 액션 | Checkbox + Action Bar | 선택된 run 일괄 삭제/재시작 (향후) |

### 테이블 컬럼 상세

| 컬럼 | 타입 | 정렬 | 포맷 |
|------|------|------|------|
| Workflow | mono text | - | 앞 16자 + tooltip 전체 |
| Channel | text | O | channel_id |
| Topic | text | - | 말줄임 30자 (향후 API 추가 필요) |
| Status | badge | O | 6가지 상태별 색상 뱃지 |
| Cost | number | O | $0.00 / -- (null) |
| Started | relative time | O | "3m ago", "2h ago", "Apr 2" |
| Actions | buttons | - | 상태별 다른 버튼 표시 |

### 상태별 Actions 버튼 매핑

| Status | 가능한 Actions |
|--------|---------------|
| `running` | View Progress → /pipelines/:id |
| `waiting_approval` | Approve / Reject 버튼 |
| `ready_to_upload` | Download Video, Download Thumb |
| `completed` | Download Video, View on YouTube (링크) |
| `failed` | View Error, Retry 버튼 |
| `unknown` | View Details |

### 연결 API

| API | Method | 용도 |
|-----|--------|------|
| `GET /api/dashboard/runs?limit=20&offset=0&channel_id=` | GET | 페이지별 run 목록 |
| `POST /api/pipeline/{id}/approve` | POST | 승인/거절 (waiting_approval일 때) |
| `DELETE /api/pipeline/{id}` | DELETE | 실행 취소 (running일 때) |
| `GET /api/pipeline/{id}/download` | GET | 비디오 다운로드 |
| `GET /api/pipeline/{id}/thumbnail` | GET | 썸네일 다운로드 |

### UX 유의사항

- 테이블 행 클릭 → /pipelines/:id 상세 페이지 이동
- running 행은 배경색 미세하게 다르게 (attention)
- failed 행은 왼쪽 border-left: 3px solid red
- 빈 상태: "No pipelines yet. Start your first video →"
- 필터 변경 시 URL query param 반영 (?channel=channel_01&status=running)
- 모바일: 카드 레이아웃으로 전환 (테이블 X)

---

## Page 3: Pipeline Detail (/pipelines/:id)

**목적**: 단일 파이프라인의 전체 진행 과정 — CapCut 프로젝트 뷰 참고

### UI 구성요소

| 영역 | 컴포넌트 | 데이터 |
|------|----------|--------|
| 헤더 | Title + Status Badge | workflow_id, status, channel_id |
| 진행 스테퍼 | Step Progress Bar | 8단계 파이프라인 진행률 |
| 비디오 프리뷰 | Video Player | 완성된 영상 재생 (ready_to_upload/completed) |
| 썸네일 프리뷰 | Image | 생성된 썸네일 이미지 |
| 스크립트 뷰 | Accordion/Tab | 생성된 스크립트 (title, description, scenes) |
| 씬 갤러리 | Image Grid | 7개 씬 이미지 그리드 |
| 비용 상세 | Cost Table | service별 비용 breakdown |
| 액션 바 | Sticky Bottom Bar | Download Video / Download Thumb / Approve / Reject |
| 에러 패널 | Error Card | failed 시 에러 메시지 + 스택트레이스 |
| 메타데이터 | Key-Value List | started_at, completed_at, duration, channel_id |

### 파이프라인 8단계 스테퍼

```
1. Setup Dirs    → 2. Script Gen   → 3. Image Gen (×N)
→ 4. TTS (×N)   → 5. Video Gen (×N) → 6. Thumbnail
→ 7. Assembly   → 8. Quality Gate (optional)
```

각 단계: ● 완료(green) / ◐ 진행중(blue+spin) / ○ 대기(gray) / ✕ 실패(red)

### 연결 API

| API | Method | 용도 | 폴링 |
|-----|--------|------|------|
| `GET /api/pipeline/status/{id}` | GET | 상태 + 진행률 | 3초 (running일 때) |
| `GET /api/pipeline/cost/{id}` | GET | 비용 breakdown | status 변경 시 |
| `GET /api/pipeline/{id}/video` | GET | 비디오 스트리밍 프리뷰 | - |
| `GET /api/pipeline/{id}/download` | GET | 비디오 다운로드 | - |
| `GET /api/pipeline/{id}/thumbnail` | GET | 썸네일 다운로드 | - |
| `POST /api/pipeline/{id}/approve` | POST | 승인/거절 | - |
| `DELETE /api/pipeline/{id}` | DELETE | 취소 | - |

### UX 유의사항

- running 상태: 3초마다 폴링, 스테퍼 실시간 업데이트
- waiting_approval: Approve/Reject 버튼 강조 (primary/danger)
- ready_to_upload: Download 버튼 크게, "Upload to YouTube Studio" 외부 링크
- 비디오 프리뷰: 브라우저 내장 `<video>` 플레이어 사용
- 씬 이미지: Lightbox로 클릭 시 확대
- 비용: $0.00이면 "All local — no API costs" 메시지
- 에러: 전체 에러 메시지 + "Retry" 버튼
- 뒤로가기: /pipelines 목록으로 breadcrumb

---

## Page 4: New Pipeline — Trigger (/trigger)

**목적**: 새 비디오 파이프라인 시작 — Canva "Create a design" 참고

### UI 구성요소

| 영역 | 컴포넌트 | 데이터 |
|------|----------|--------|
| 토픽 입력 | Text Input (large) | topic (필수) |
| 채널 선택 | Radio Card Group | channel_01, channel_02 (YAML에서 로드) |
| 채널 프리뷰 | Info Card | 선택된 채널의 모델, 언어, vgen 설정 표시 |
| 예상 비용 | Cost Estimate | vgen_enabled면 ~$2.50, 아니면 $0.00 |
| 고급 옵션 | Collapsible Section | quality_gate 토글 |
| 실행 버튼 | Primary CTA | "Generate Video" |
| 최근 토픽 | Suggestion Chips | 이전에 사용한 토픽 (향후) |

### 채널 카드 표시 정보

```
┌─────────────────────────────────┐
│  ● channel_01                   │
│  General / Korean               │
│  LLM: Qwen3:14b (local)        │
│  Image: SDXL Juggernaut        │
│  TTS: Kokoro                   │
│  Video: Ken Burns (local)       │
│  Cost: ~$0.00/video             │
└─────────────────────────────────┘
```

### 연결 API

| API | Method | 용도 |
|-----|--------|------|
| `POST /api/pipeline/trigger` | POST | 파이프라인 시작 |

### Request Body
```json
{
  "topic": "2026 AI Trends",
  "channel_id": "channel_01"
}
```

### 성공 후 흐름
1. API 응답 수신 (workflow_id)
2. Toast: "Pipeline started!"
3. 자동 redirect → /pipelines/{workflow_id} (상세 페이지)

### UX 유의사항

- 토픽 입력: placeholder "e.g., 2026년 AI 트렌드 Top 5"
- 입력 없이 제출 → inline validation "토픽을 입력하세요"
- 채널 미선택 → inline validation "채널을 선택하세요"
- 실행 버튼: 클릭 후 loading spinner + disabled (중복 방지)
- 비용 경고: vgen_enabled 채널 선택 시 "Estimated cost: ~$2.50 (fal.ai)" 노란 배너
- 키보드: Enter로 제출 가능

---

## Page 5: Cost Analytics (/costs)

**목적**: 비용 분석 + 트렌드 — Stripe Billing 대시보드 참고

### UI 구성요소

| 영역 | 컴포넌트 | 데이터 |
|------|----------|--------|
| 기간 선택 | Segmented Control | 7일 / 30일 / 90일 / 전체 |
| 총 비용 카드 | Large Stat | 기간 내 총 비용 |
| 채널별 비용 바 | Horizontal Bars | 채널별 비용 비교 (Stripe 스타일) |
| 비용 트렌드 | Line Chart | 일별 비용 추이 |
| 서비스별 비용 | Donut Chart | fal.ai / Gemini / local(0) 비율 |
| 상세 테이블 | Table | 개별 run의 비용 breakdown |
| 비용 예측 | Projection Card | 현재 추세 기반 월간 예상 비용 |

### 연결 API

| API | Method | 용도 |
|-----|--------|------|
| `GET /api/dashboard/costs?days=7` | GET | 7일 비용 |
| `GET /api/dashboard/costs?days=30` | GET | 30일 비용 |
| `GET /api/dashboard/costs?days=90` | GET | 90일 비용 |
| `GET /api/dashboard/runs?limit=100` | GET | run별 비용 (테이블) |
| `GET /api/pipeline/cost/{id}` | GET | 개별 run 비용 상세 |

### 향후 필요 API (현재 미구현)

| API | 용도 |
|-----|------|
| `GET /api/dashboard/costs/daily?days=30` | 일별 비용 시계열 데이터 |
| `GET /api/dashboard/costs/by-service?days=30` | 서비스별 비용 집계 |

### UX 유의사항

- 비용 $0.00 주로 → "Mostly local processing — minimal cloud costs" 메시지
- 차트: Chart.js 또는 Recharts 사용
- 숫자 포맷: $1,234.56 (천단위 콤마)
- 기간 변경 시 차트 + 카드 동시 업데이트 (트랜지션)
- 빈 상태: "No cost data yet. Run your first pipeline →"

---

## Page 6: Channel Management (/channels)

**목적**: 채널별 설정 확인 + 관리 — Notion Database 뷰 참고

### UI 구성요소

| 영역 | 컴포넌트 | 데이터 |
|------|----------|--------|
| 채널 카드 그리드 | Card Grid | 채널별 설정 카드 |
| 채널 상세 | Side Panel / Modal | 선택한 채널의 전체 설정 |
| 모델 뱃지 | Badge Row | LLM, Image, TTS, Video 모델명 |
| 실행 통계 | Mini Stats | 채널별 총 run 수, 성공률, 평균 비용 |
| YouTube 연결 | Status Indicator | OAuth 토큰 유효 여부 |
| 빠른 실행 | CTA | "Generate for this channel" → /trigger?channel=X |

### 채널 카드 상세

```
┌─────────────────────────────────────────┐
│  channel_01 — General                   │
│  🌐 Korean                              │
│                                         │
│  LLM      Qwen3:14b (local)            │
│  Image    SDXL Juggernaut (local)       │
│  TTS      Kokoro (local)               │
│  Video    Ken Burns (local)             │
│                                         │
│  ☐ Video Gen (fal.ai)    ☑ Quality Gate │
│                                         │
│  Runs: 15  |  Success: 93%  |  Avg: $0  │
│                                         │
│  [Generate Video]  [Edit Config]        │
└─────────────────────────────────────────┘
```

### 연결 API

| API | Method | 용도 |
|-----|--------|------|
| `GET /api/dashboard/runs?channel_id=X` | GET | 채널별 run 통계 |
| `GET /api/dashboard/costs?channel_id=X` | GET | 채널별 비용 |

### 향후 필요 API (현재 미구현)

| API | 용도 |
|-----|------|
| `GET /api/channels` | 전체 채널 목록 + 설정 |
| `PUT /api/channels/{id}` | 채널 설정 수정 |
| `POST /api/channels` | 새 채널 추가 |
| `GET /api/channels/{id}/youtube-status` | YouTube OAuth 상태 |

### UX 유의사항

- 현재: YAML 파일 기반이므로 읽기 전용 표시
- 향후: API 추가 시 인라인 편집 가능
- 채널 추가: "Add Channel" → YAML 템플릿 다운로드 안내
- YouTube 연결: 토큰 만료 시 "Reconnect YouTube" 버튼
- local 모델은 green 뱃지, cloud 모델은 blue 뱃지 + 비용 표시

---

## Page 7: System Settings & Health (/settings)

**목적**: 시스템 상태 + 설정 — Notion Settings 참고

### UI 구성요소

| 영역 | 컴포넌트 | 데이터 |
|------|----------|--------|
| Health 대시보드 | 3-column Grid | Temporal, SQLite, Disk |
| 워커 상태 | Worker Cards | GPU(1), CPU(4), API(8) 워커 |
| Temporal UI 링크 | External Link | http://localhost:8081 |
| Google Sheets 동기화 | Sync Panel | 마지막 동기화 시각, 수동 동기화 버튼 |
| 알림 로그 | Alert Table | data/alerts.jsonl 최근 항목 |
| 시스템 정보 | Info Grid | FFmpeg 버전, Ollama 모델, ComfyUI 상태 |
| 배치 실행 | Batch Panel | JSON 입력 → 일괄 파이프라인 실행 |
| 스케줄 관리 | Schedule Panel | 예약된 영상 목록 |
| YouTube Auth | Auth Panel | 채널별 OAuth 상태 |

### Health 카드 상세

```
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  ● Temporal  │  │  ● SQLite    │  │  ● Disk      │
│  Connected   │  │  Healthy     │  │  49.0 GB     │
│              │  │              │  │  free         │
│  Uptime: 7h  │  │  3 tables    │  │  ████░░ 65%  │
│  Workflows: 5│  │  156 rows    │  │              │
└──────────────┘  └──────────────┘  └──────────────┘
```

### 연결 API

| API | Method | 용도 |
|-----|--------|------|
| `GET /health` | GET | 시스템 상태 |
| `POST /api/sync/sheets` | POST | 수동 Sheets 동기화 |
| `GET /api/sync/status/{id}` | GET | 동기화 상태 |

### 향후 필요 API (현재 미구현)

| API | 용도 |
|-----|------|
| `GET /api/system/workers` | 워커 상태 (실행 중/중단) |
| `GET /api/system/info` | FFmpeg, Ollama, ComfyUI 버전 |
| `GET /api/system/alerts?limit=20` | 최근 알림 목록 |
| `GET /api/schedules` | 예약 목록 |
| `DELETE /api/schedules/{id}` | 예약 취소 |
| `POST /api/batch/run` | 배치 실행 (현재 CLI만) |

### UX 유의사항

- Health: 5초마다 폴링, 상태 변경 시 dot 색상 전환 애니메이션
- Disk: progress bar로 시각화, 10GB 미만 시 빨간색 경고
- Sheets 동기화: 버튼 클릭 → spinner → 결과 toast
- 알림 로그: 최신순, severity별 색상 (critical=red, warning=yellow, info=blue)
- Temporal UI: 새 탭으로 열기 (target="_blank")

---

## Sidebar Navigation 구조

```
┌─────────────────────┐
│  ▶ Studio           │  ← 로고
│                     │
│  ■ Dashboard        │  ← /
│  ▷ Pipelines        │  ← /pipelines
│  $ Costs            │  ← /costs
│  ◎ Channels         │  ← /channels
│                     │
│  ─────────────────  │  ← Divider
│                     │
│  ⚙ Settings         │  ← /settings
│                     │
│  ─────────────────  │
│  ● All operational  │  ← Health status
│  Updated 7:30 PM    │
└─────────────────────┘
```

---

## 공통 컴포넌트 (Shared)

| 컴포넌트 | 사용 페이지 | 설명 |
|----------|-----------|------|
| `Sidebar` | 전체 | 네비게이션 + health 상태 |
| `StatCard` | Dashboard, Costs | 아이콘 + 숫자 + 라벨 |
| `StatusBadge` | Pipelines, Detail | 6가지 상태별 색상 뱃지 |
| `DataTable` | Pipelines, Costs, Settings | 정렬 + 필터 + 페이지네이션 |
| `Toast` | 전체 | 성공/에러/경고 알림 |
| `Skeleton` | 전체 | 로딩 중 placeholder |
| `EmptyState` | 전체 | 데이터 없을 때 일러스트 + CTA |
| `Modal` | Detail, Settings | 확인 다이얼로그, 상세 보기 |
| `CostBar` | Dashboard, Costs | 수평 비용 바 차트 |
| `StepProgress` | Detail | 8단계 파이프라인 스테퍼 |
| `VideoPlayer` | Detail | `<video>` 래퍼 |
| `ImageLightbox` | Detail | 이미지 클릭 확대 |
| `ChannelCard` | Trigger, Channels | 채널 설정 카드 |
| `SearchInput` | Pipelines | 검색 + 디바운스 |
| `SegmentedControl` | Costs | 기간 선택 (7d/30d/90d) |

---

## API 연결 총 정리

### 현재 사용 가능한 API (13개)

| # | Endpoint | 사용 페이지 |
|---|----------|-----------|
| 1 | `GET /health` | Dashboard, Settings |
| 2 | `GET /api/dashboard/runs` | Dashboard, Pipelines |
| 3 | `GET /api/dashboard/costs` | Dashboard, Costs |
| 4 | `POST /api/pipeline/trigger` | Trigger |
| 5 | `GET /api/pipeline/status/{id}` | Detail |
| 6 | `GET /api/pipeline/cost/{id}` | Detail, Costs |
| 7 | `POST /api/pipeline/{id}/approve` | Detail, Pipelines |
| 8 | `GET /api/pipeline/{id}/download` | Detail, Pipelines |
| 9 | `GET /api/pipeline/{id}/thumbnail` | Detail, Pipelines |
| 10 | `GET /api/pipeline/{id}/video` | Detail |
| 11 | `DELETE /api/pipeline/{id}` | Detail, Pipelines |
| 12 | `POST /api/sync/sheets` | Settings |
| 13 | `GET /api/sync/status/{id}` | Settings |

### 향후 추가 필요 API (10개)

| # | Endpoint | 사용 페이지 | 우선순위 |
|---|----------|-----------|---------|
| 1 | `GET /api/channels` | Channels, Trigger | HIGH |
| 2 | `GET /api/channels/{id}` | Channels | HIGH |
| 3 | `PUT /api/channels/{id}` | Channels | MEDIUM |
| 4 | `GET /api/dashboard/costs/daily` | Costs | HIGH |
| 5 | `GET /api/dashboard/costs/by-service` | Costs | MEDIUM |
| 6 | `GET /api/system/workers` | Settings | MEDIUM |
| 7 | `GET /api/system/info` | Settings | LOW |
| 8 | `GET /api/system/alerts` | Settings | MEDIUM |
| 9 | `GET /api/schedules` | Settings | LOW |
| 10 | `POST /api/batch/run` | Settings | LOW |

---

## 기술 스택 선택지

### Option A: Vanilla (현재)
- HTML + CSS + JS
- 장점: 빌드 없음, 가장 가벼움, GitHub Pages 즉시 배포
- 단점: 라우팅 직접 구현, 컴포넌트 재사용 어려움, 상태 관리 복잡

### Option B: React + shadcn/ui (추천)
- Vite + React + Tailwind + shadcn/ui
- 장점: 최고 품질 UI 컴포넌트, 커뮤니티 거대, Stripe 미학 구현 용이
- 단점: 빌드 필요, 번들 크기

### Option C: Vue + Nuxt
- 장점: SPA + SSR, 학습 곡선 낮음
- 단점: shadcn/ui 미지원 (radix-vue 대안)

### Option D: Astro + Islands
- 장점: 정적 우선, 부분 하이드레이션
- 단점: 동적 대시보드에는 과소 (주로 콘텐츠 사이트용)

### 추천: Option B (React + shadcn/ui)
- shadcn-admin 레퍼런스 직접 활용 가능
- Stripe 스타일 구현에 최적
- Netlify/Vercel 즉시 배포
