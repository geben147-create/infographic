# Technology Stack: YouTube Scoring & Hook Library System

**Project:** YouTube Video/Channel Scoring System + Hook Library
**Researched:** 2026-04-02
**Overall Confidence:** HIGH

---

## Context

This stack targets a **data collection and scoring pipeline** — fundamentally different from the video generation pipeline. The system:
1. Calls YouTube Data API v3 to collect video/channel statistics
2. Calculates 24 scoring metrics (VPH, ER, z-scores, HotScore, RPM Proxy, Evergreen Ratio, etc.)
3. Stores append-only data in SQLite via SQLModel
4. Syncs scored results to Google Sheets as the dashboard UI
5. Manages a Hook Library (hooks, titles, thumbnails)

The parent project already uses Python 3.12+, FastAPI, SQLite/SQLModel, and gspread. This scoring system extends that existing stack.

---

## Recommended Stack

### Core Framework (Inherited from Parent Project)

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| **Python** | 3.12+ | Primary language | Already established, statistics ecosystem, type hints | HIGH |
| **FastAPI** | 0.115+ | REST API + scheduled task host | Lifespan events for scheduler init, existing codebase | HIGH |
| **SQLite** | 3.45+ | Primary database | Append-only pattern works perfectly — no row updates needed, just INSERT. ACID, zero-ops | HIGH |
| **SQLModel** | 0.0.37 | ORM | Latest stable (Feb 2026). Pydantic v2 native. For append-only tables, use it for INSERT only — never UPDATE scored snapshots | HIGH |

### YouTube Data API Integration

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| **google-api-python-client** | 2.193+ | YouTube Data API v3 client | Official Google client. Weekly releases. v2.193.0 (Mar 2026). Discovery docs now bundled (no network fetch at init) | HIGH |
| **google-auth** | 2.x | API authentication | Service account auth for API key usage; OAuth2 if channel management needed later | HIGH |

**Critical API Pattern — Batch 50 IDs per call:**
```python
# videos.list costs 1 quota unit regardless of how many IDs (max 50)
# 10,000 daily quota = 500,000 videos/day at 50 per call
request = youtube.videos().list(
    part="snippet,statistics,contentDetails",
    id=",".join(video_ids[:50]),  # HARD LIMIT: 50 IDs max
    fields="items(id,snippet(title,publishedAt,channelId,categoryId),"
           "statistics(viewCount,likeCount,commentCount),"
           "contentDetails(duration))"  # Use fields= to reduce response size
)
```

**Quota Budget for Scoring System:**

| Operation | Cost/call | IDs/call | Daily budget (10K units) |
|-----------|-----------|----------|--------------------------|
| `videos.list` | 1 unit | 50 | 500,000 videos |
| `channels.list` | 1 unit | 50 | 500,000 channels |
| `search.list` | **100 units** | N/A | 100 searches |
| `videos.insert` (upload) | 1,600 units | 1 | 6 uploads |

**Rule: NEVER use `search.list` for data collection.** At 100 units/call, it destroys your quota. Instead, collect video IDs from channel uploads playlists (`playlistItems.list` at 1 unit) or RSS feeds (zero API cost), then batch with `videos.list`.

### Scheduling

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| **APScheduler** | 3.10.4 | Cron-like job scheduling | Stable production release. In-process, no external broker needed. SQLite job store for persistence across restarts | HIGH |

**Why APScheduler 3.x, NOT 4.0:**
- APScheduler 4.0 is **pre-release only** as of April 2026. The maintainer explicitly warns it "may change in backwards incompatible fashion without any migration pathway."
- 3.10.x is battle-tested, supports async via `AsyncIOScheduler`, and has SQLite-backed job stores.
- The scoring system needs simple cron triggers (every 6h, daily), not distributed task queues.

**Why NOT alternatives:**

| Alternative | Why Not |
|-------------|---------|
| `schedule` (PyPI) | No persistence (jobs lost on restart), no async, no job store | 
| Celery Beat | Requires Redis/RabbitMQ broker — massive overkill for cron triggers |
| Temporal schedules | Already in the parent project for video pipeline, but wiring Temporal for simple "fetch YouTube stats every 6h" is over-engineering |
| OS crontab | No visibility, no persistence tracking, no integration with FastAPI |

**APScheduler Configuration Pattern:**
```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

scheduler = AsyncIOScheduler(
    jobstores={"default": SQLAlchemyJobStore(url="sqlite:///data/jobs.db")},
    job_defaults={"coalesce": True, "max_instances": 1},  # Prevent overlap
)
scheduler.add_job(collect_and_score, "cron", hour="*/6", id="score_cycle")
```

### Google Sheets Sync

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| **gspread** | 6.2.1 | Google Sheets read/write | Latest stable (2026). service_account() auth. Batch operations built-in | HIGH |

**Rate Limits (CRITICAL):**
- **300 requests/60s per project** (Google Sheets API v4)
- **60 requests/60s per user**
- No daily limit if you stay within per-minute quotas

**Best Practices for Scoring Dashboard Sync:**

1. **Use `batch_update()` for scored results** — one API call per sheet update, not one per cell:
   ```python
   worksheet.batch_update([
       {"range": "A2:Z50", "values": scored_rows}
   ])
   ```
2. **Use `batch_get()` to read multiple ranges** in a single call
3. **Implement exponential backoff** for 429 errors (gspread does NOT auto-retry by default)
4. **Buffer at 250 req/min** (not 300) to leave headroom
5. **Consider `gspread_asyncio`** (v2.0.1) if sync blocking becomes an issue — provides 1.1s auto-delay between calls

**Anti-pattern: Per-cell updates.**
The existing `sheets_service.py` uses `update_cell()` per field. For the scoring system, this MUST be replaced with batch operations. Writing 50 scored videos x 24 metrics = 1,200 individual cell updates = instant quota death. Use `batch_update()` instead: 1 call.

### Statistical Computation

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| **NumPy** | 2.4.4 | Array math, z-score, normalization | Latest stable (Mar 2026). Vectorized ops handle 10K+ videos in <10ms. Already a transitive dependency | HIGH |
| **statistics** (stdlib) | built-in | Simple mean/stdev for small datasets | Zero dependency. Use for single-metric calculations only | HIGH |

**Why NumPy, NOT SciPy:**
- `scipy.stats.zscore()` is just a thin wrapper around NumPy's mean/std. It adds a 30MB dependency for one function.
- For 24 scoring metrics across hundreds of videos, NumPy's vectorized operations are sufficient and faster than per-row Python loops.
- If you later need distribution fitting or statistical tests, THEN add SciPy. Not before.

**Why NOT scikit-learn StandardScaler:**
- StandardScaler is for ML preprocessing pipelines (fit/transform pattern). Scoring metrics need explicit formulas (VPH = views / hours_since_publish), not generic scaling.
- Overkill dependency (scikit-learn pulls in SciPy + joblib + threadpoolctl).

**Z-Score Implementation (Pure NumPy):**
```python
import numpy as np

def z_scores(values: np.ndarray) -> np.ndarray:
    """Population z-scores. Returns 0 for constant arrays."""
    std = np.std(values)
    if std == 0:
        return np.zeros_like(values)
    return (values - np.mean(values)) / std
```

**Scoring Metrics that Benefit from Vectorized NumPy:**
- VPH (Views Per Hour): `views / hours_since_publish`
- Engagement Rate: `(likes + comments) / views`
- Z-scores across any metric dimension
- HotScore (Reddit-style decay): `log10(max(score, 1)) + sign * seconds / 45000`
- Percentile ranks: `np.searchsorted(np.sort(values), values) / len(values)`

### Testing

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| **pytest** | 8.x | Test framework | De facto standard. 75%+ Python projects use it. Fixtures, parametrize, markers | HIGH |
| **pytest-cov** | 5.x | Coverage reporting | `--cov=src --cov-report=term-missing` — required by project conventions | HIGH |
| **polyfactory** | 3.3.0 | Mock data factories | Generates valid Pydantic/SQLModel instances from type hints. Replaces hand-written fixtures for scored video models | HIGH |
| **time-machine** | 2.x | Time mocking | Testing time-dependent scoring (VPH, HotScore decay) requires freezing time. Superior to `freezegun` (C extension, faster, no side effects) | MEDIUM |
| **respx** | 0.22+ | httpx mock | Mock YouTube API responses without hitting real API. Works with httpx (used by parent project) | MEDIUM |

**Testing Patterns for Scoring Pipeline:**

1. **Deterministic scoring tests**: Use `polyfactory` to generate `VideoSnapshot` models with known values, verify computed scores match expected formulas
2. **Time-dependent tests**: Use `time-machine` to freeze `datetime.utcnow()` for VPH and HotScore calculations
3. **API response mocking**: Use `respx` or `unittest.mock.patch` to simulate YouTube API responses with known statistics
4. **Boundary tests**: Zero views, zero hours (division by zero), negative values, NaN propagation
5. **Snapshot regression**: Store golden scored outputs, compare against future runs to catch formula drift

```python
# Example: Polyfactory for VideoSnapshot
from polyfactory.factories.pydantic_factory import ModelFactory

class VideoSnapshotFactory(ModelFactory):
    __model__ = VideoSnapshot
    view_count = 1000
    like_count = 50
    comment_count = 10
    published_at = datetime(2026, 1, 1)
```

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **Pydantic** | 2.x | Scoring config schemas, API response validation | All scored metric definitions, channel tracking configs |
| **httpx** | 0.27+ | HTTP client (if using raw YouTube API) | Alternative to google-api-python-client for lighter footprint |
| **structlog** | 24.x | Structured logging | Log every scoring cycle: videos processed, scores computed, errors |
| **isodate** | 0.7+ | Parse ISO 8601 durations | YouTube `contentDetails.duration` returns "PT4M13S" format |
| **python-dateutil** | 2.9+ | Date parsing/arithmetic | Parse `publishedAt` timestamps, compute hours since publish |

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Scheduling | APScheduler 3.10 | APScheduler 4.0 | Pre-release, unstable API, "may change without migration pathway" |
| Scheduling | APScheduler 3.10 | Celery Beat | Requires external broker (Redis/RMQ), overkill for cron triggers |
| Scheduling | APScheduler 3.10 | `schedule` | No persistence, no async, jobs lost on restart |
| Stats | NumPy | SciPy | 30MB for one function (zscore). NumPy does everything needed |
| Stats | NumPy | scikit-learn | ML preprocessing tool, not metric computation. Huge transitive deps |
| Stats | NumPy | Pure Python | 100x slower for vectorized operations on 1K+ rows |
| YouTube client | google-api-python-client | youtube-data-api (wrapper) | Extra abstraction layer, less control over fields/parts, 0.0.17 is stale |
| YouTube client | google-api-python-client | httpx raw | Works but lose auto-pagination, discovery schema, error types |
| Sheets | gspread 6.2 | gspread_asyncio | Only add if blocking sync becomes a measured problem |
| ORM | SQLModel 0.0.37 | Raw SQLAlchemy | SQLModel already in codebase, sufficient for append-only INSERTs |
| ORM | SQLModel 0.0.37 | Peewee | Different ORM in same project = cognitive overhead |
| Data factory | polyfactory 3.3 | Faker | Faker generates random strings, not valid model instances |
| Time mock | time-machine | freezegun | freezegun monkey-patches datetime globally, slower, more side effects |

---

## Installation

```bash
# Scoring system dependencies (add to existing project)
pip install google-api-python-client google-auth APScheduler numpy isodate python-dateutil

# Already in project (no action needed):
# fastapi, sqlmodel, gspread, pydantic, structlog, httpx, pytest, pytest-cov

# Dev dependencies for scoring tests
pip install polyfactory time-machine respx
```

---

## Key Integration Points with Parent Project

| Component | How Scoring System Uses It |
|-----------|---------------------------|
| `src/models/` | Add new models: `VideoSnapshot`, `ChannelSnapshot`, `ScoredVideo`, `Hook` |
| `src/services/sheets_service.py` | Extend with batch operations for scored data sync. Replace per-cell updates |
| `src/config.py` | Add YouTube API key, scoring schedule config, tracked channel IDs |
| `src/api/` | Add scoring endpoints: `/api/scores`, `/api/hooks`, `/api/channels/tracked` |
| SQLite database | New tables alongside existing `content_items`, `pipeline_runs` |
| FastAPI lifespan | Initialize APScheduler in app lifespan (alongside existing Temporal workers) |

---

## Sources

- [YouTube Data API v3 — Videos:list](https://developers.google.com/youtube/v3/docs/videos/list)
- [YouTube API Quota Calculator](https://developers.google.com/youtube/v3/determine_quota_cost)
- [YouTube API Quota Management 2026](https://zernio.com/blog/youtube-api-limits-how-to-calculate-api-usage-cost-and-fix-exceeded-api-quota)
- [Track 100K Videos Without Hitting Quota](https://dev.to/siyabuilt/youtubes-api-quota-is-10000-unitsday-heres-how-i-track-100k-videos-without-hitting-it-5d8h)
- [SQLModel Release Notes](https://sqlmodel.tiangolo.com/release-notes/) — v0.0.37 (Feb 2026)
- [SQLModel PyPI](https://pypi.org/project/sqlmodel/)
- [APScheduler PyPI](https://pypi.org/project/APScheduler/) — 3.10.4 stable, 4.0 pre-release
- [APScheduler vs schedule](https://leapcell.io/blog/scheduling-tasks-in-python-apscheduler-versus-schedule)
- [gspread 6.2.1 Documentation](https://docs.gspread.org/)
- [Google Sheets API Usage Limits](https://developers.google.com/workspace/sheets/api/limits)
- [gspread Batch Operations](https://docs.gspread.org/en/latest/user-guide.html)
- [NumPy 2.4.4](https://pypi.org/project/numpy/) — Mar 2026
- [SciPy stats.zscore](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.zscore.html)
- [Z-Score Normalization in Python](https://spotintelligence.com/2025/02/14/z-score-normalization/)
- [google-api-python-client 2.193.0](https://pypi.org/project/google-api-python-client/) — Mar 2026
- [polyfactory 3.3.0](https://pypi.org/project/polyfactory/) — Feb 2026
- [Pytest Best Practices for Data Pipelines](https://www.startdataengineering.com/post/python-datapipeline-integration-test/)
