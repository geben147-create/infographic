# Architecture Patterns: YouTube Scoring & Library System

**Domain:** Append-only scoring pipeline with tiered aggregation
**Researched:** 2026-04-02
**Overall confidence:** HIGH

## Recommended Architecture

### Immutable Data Flow (Core Principle)

```
YouTube Data API v3 ──> RAW_SCORES (append-only table)
                              │
                    ┌─────────┴──────────┐
                    │   SQLite VIEWs      │
                    │  (calculation layer) │
                    └─────────┬──────────┘
                              │
                    VIDEO_SCORE_VIEW (per-video composite score)
                              │
                    CHANNEL_SCORE_VIEW (aggregated channel score)
                              │
                    LIBRARY_GATE_VIEW (pass/fail classification)
                              │
                    LIBRARY_STORAGE (materialized picks)
                              │
                    Google Sheets (dashboard sync)
```

This is a **lambda-lite architecture**: raw data is immutable and append-only, all derived data is computed via SQL views (no denormalized copies), and the only materialized output is the library selection. The key constraint is that every view is deterministic from RAW_SCORES + CONFIG, making the entire system reproducible and auditable.

### Component Boundaries

| Component | Responsibility | Communicates With | Module |
|-----------|---------------|-------------------|--------|
| **Fetcher** | Pull video/channel statistics from YouTube API | YouTube Data API v3 --> RAW_SCORES | `src/scoring/fetcher.py` |
| **Scorer** | Calculate 24 weighted metrics per video | RAW_SCORES --> VIDEO_SCORE_VIEW | `src/scoring/scorer.py` (SQL views) |
| **Aggregator** | Roll up video scores to channel level | VIDEO_SCORE_VIEW --> CHANNEL_SCORE_VIEW | `src/scoring/aggregator.py` (SQL views) |
| **Classifier** | Apply rule-based library gate thresholds | CHANNEL_SCORE_VIEW --> LIBRARY_GATE_VIEW | `src/scoring/classifier.py` (SQL views) |
| **Librarian** | Materialize library picks, manage storage | LIBRARY_GATE_VIEW --> LIBRARY_STORAGE | `src/scoring/librarian.py` |
| **Sheets Sync** | Push dashboard data to Google Sheets | LIBRARY_STORAGE + VIEWs --> Sheets | `src/scoring/sheets_sync.py` |
| **Scheduler** | Orchestrate 40-min fetch/score cycles | APScheduler --> Fetcher --> chain | `src/scoring/scheduler.py` |
| **Config Manager** | Load weights, thresholds, presets from YAML | YAML files --> all scoring components | `src/scoring/config.py` |

### Strict Boundary Rules

1. **Fetcher** never calculates scores -- it only writes raw API responses
2. **Scorer/Aggregator/Classifier** are pure SQL views -- no Python business logic in the calculation path
3. **Librarian** is the only component that writes derived data (materializing library picks)
4. **Sheets Sync** is read-only from SQLite perspective -- it only pushes, never pulls scores back
5. **Config Manager** is the single source of truth for all weights/thresholds -- no magic numbers anywhere

## Data Flow: Detailed

### Phase 1: Raw Data Collection (Fetcher)

```
40-min interval trigger (APScheduler)
    │
    ├─ For each tracked channel:
    │   ├─ channels.list(part=statistics,snippet) --> 1 quota unit
    │   └─ For each video batch (50 IDs per request):
    │       └─ videos.list(part=statistics,snippet) --> 1 quota unit per batch
    │
    └─ INSERT INTO raw_video_scores (append-only, never UPDATE/DELETE)
       INSERT INTO raw_channel_scores (append-only, never UPDATE/DELETE)
```

**Quota budget per cycle** (estimating 5 channels, ~50 videos each):
- Channel stats: 5 calls x 1 unit = 5 units
- Video stats: 5 channels x 1 batch (50 videos) = 5 units
- Total per cycle: ~10 units
- Cycles per day (every 40 min): 36 cycles x 10 units = 360 units/day
- Remaining for video pipeline: 10,000 - 360 = 9,640 units (plenty of headroom)

### Phase 2: Score Calculation (SQL Views -- Zero Python Code)

```sql
-- VIDEO_SCORE_VIEW: Computed entirely in SQLite
-- Uses window functions for delta calculations (views gained since last snapshot)
-- Uses CASE expressions for rule-based tier assignment
-- Weights come from a scoring_config table (loaded from YAML at startup)

CREATE VIEW video_score_view AS
SELECT
    v.video_id,
    v.channel_id,
    v.fetched_at,
    -- Raw metrics (latest snapshot)
    v.view_count,
    v.like_count,
    v.comment_count,
    -- Delta metrics (vs previous snapshot)
    v.view_count - LAG(v.view_count) OVER (
        PARTITION BY v.video_id ORDER BY v.fetched_at
    ) AS views_delta,
    -- Weighted composite score
    (v.view_count * w.weight_views
     + v.like_count * w.weight_likes
     + v.comment_count * w.weight_comments
     + ...) AS composite_score,
    -- Engagement ratio
    CAST(v.like_count AS REAL) / NULLIF(v.view_count, 0) AS engagement_ratio
FROM raw_video_scores v
CROSS JOIN scoring_weights w
WHERE v.fetched_at = (
    SELECT MAX(fetched_at) FROM raw_video_scores
    WHERE video_id = v.video_id
);
```

The critical insight: **SQLite IS the scoring engine.** No Python scoring logic. Views are recalculated on every query, always reflecting the latest weights from the config table. This means changing a weight in YAML and reloading config instantly changes all scores without reprocessing.

### Phase 3: Channel Aggregation (SQL View)

```sql
CREATE VIEW channel_score_view AS
SELECT
    channel_id,
    COUNT(*) AS video_count,
    AVG(composite_score) AS avg_score,
    MAX(composite_score) AS best_score,
    SUM(views_delta) AS total_views_delta,
    AVG(engagement_ratio) AS avg_engagement,
    -- Channel-level metrics from raw_channel_scores
    c.subscriber_count,
    c.total_view_count,
    -- Derived: growth velocity
    c.subscriber_count - LAG(c.subscriber_count) OVER (
        PARTITION BY c.channel_id ORDER BY c.fetched_at
    ) AS subscriber_delta
FROM video_score_view v
JOIN (
    SELECT * FROM raw_channel_scores
    WHERE (channel_id, fetched_at) IN (
        SELECT channel_id, MAX(fetched_at)
        FROM raw_channel_scores
        GROUP BY channel_id
    )
) c ON v.channel_id = c.channel_id
GROUP BY v.channel_id;
```

### Phase 4: Library Classification (SQL View -- Rule-Based Only)

```sql
CREATE VIEW library_gate_view AS
SELECT
    channel_id,
    avg_score,
    avg_engagement,
    subscriber_count,
    CASE
        WHEN avg_score >= t.gold_threshold
             AND avg_engagement >= t.gold_engagement THEN 'gold'
        WHEN avg_score >= t.silver_threshold THEN 'silver'
        WHEN avg_score >= t.bronze_threshold THEN 'bronze'
        ELSE 'unqualified'
    END AS tier,
    CASE
        WHEN avg_score >= t.library_min_score THEN 1
        ELSE 0
    END AS library_eligible
FROM channel_score_view
CROSS JOIN scoring_thresholds t;
```

**No AI classification.** Pure rule-based CASE statements. Thresholds loaded from YAML config into a `scoring_thresholds` table at startup.

### Phase 5: Library Materialization (Only Materialized Step)

```python
# librarian.py -- the ONLY component that writes derived data
def materialize_library():
    """
    SELECT from library_gate_view WHERE library_eligible = 1
    INSERT INTO library_storage (append-only snapshot)
    Each run creates a new snapshot_id -- never overwrites previous selections
    """
```

### Phase 6: Sheets Dashboard Sync

```
library_storage + channel_score_view + video_score_view
    │
    └─ Batch update to Google Sheets (push-only)
       ├─ Tab 1: Channel Scoreboard (channel_score_view)
       ├─ Tab 2: Video Details (video_score_view top N)
       ├─ Tab 3: Library Members (library_storage latest snapshot)
       └─ Tab 4: Score History (time-series from raw_*)
```

## SQLite Schema Design for Time-Series Snapshots

### Core Tables (Append-Only)

```sql
-- Raw video metrics: APPEND-ONLY, never UPDATE/DELETE
CREATE TABLE raw_video_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id TEXT NOT NULL,
    channel_id TEXT NOT NULL,
    fetched_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    -- Snapshot of YouTube statistics at fetch time
    view_count INTEGER NOT NULL DEFAULT 0,
    like_count INTEGER NOT NULL DEFAULT 0,
    comment_count INTEGER NOT NULL DEFAULT 0,
    favorite_count INTEGER NOT NULL DEFAULT 0,
    duration_seconds INTEGER,
    published_at TEXT,
    title TEXT,
    UNIQUE(video_id, fetched_at)
);
CREATE INDEX idx_rvs_video_time ON raw_video_scores(video_id, fetched_at);
CREATE INDEX idx_rvs_channel_time ON raw_video_scores(channel_id, fetched_at);

-- Raw channel metrics: APPEND-ONLY
CREATE TABLE raw_channel_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id TEXT NOT NULL,
    fetched_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    subscriber_count INTEGER NOT NULL DEFAULT 0,
    total_view_count INTEGER NOT NULL DEFAULT 0,
    video_count INTEGER NOT NULL DEFAULT 0,
    channel_title TEXT,
    UNIQUE(channel_id, fetched_at)
);
CREATE INDEX idx_rcs_channel_time ON raw_channel_scores(channel_id, fetched_at);

-- Scoring weights (loaded from YAML, rewritten on config change)
CREATE TABLE scoring_weights (
    id INTEGER PRIMARY KEY CHECK (id = 1),  -- Singleton row
    weight_views REAL NOT NULL DEFAULT 1.0,
    weight_likes REAL NOT NULL DEFAULT 2.0,
    weight_comments REAL NOT NULL DEFAULT 3.0,
    weight_engagement_ratio REAL NOT NULL DEFAULT 5.0,
    weight_views_velocity REAL NOT NULL DEFAULT 2.0,
    weight_subscriber_count REAL NOT NULL DEFAULT 1.0,
    -- ... up to 24 metric weights
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- Classification thresholds (loaded from YAML)
CREATE TABLE scoring_thresholds (
    id INTEGER PRIMARY KEY CHECK (id = 1),  -- Singleton row
    library_min_score REAL NOT NULL DEFAULT 50.0,
    gold_threshold REAL NOT NULL DEFAULT 90.0,
    gold_engagement REAL NOT NULL DEFAULT 0.05,
    silver_threshold REAL NOT NULL DEFAULT 70.0,
    bronze_threshold REAL NOT NULL DEFAULT 50.0,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- Library storage: APPEND-ONLY snapshots
CREATE TABLE library_storage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id TEXT NOT NULL,  -- UUID per materialization run
    channel_id TEXT NOT NULL,
    tier TEXT NOT NULL,  -- gold/silver/bronze
    composite_score REAL NOT NULL,
    selected_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    UNIQUE(snapshot_id, channel_id)
);
CREATE INDEX idx_ls_snapshot ON library_storage(snapshot_id);

-- Tracked channels (input -- which channels to score)
CREATE TABLE tracked_channels (
    channel_id TEXT PRIMARY KEY,
    channel_title TEXT,
    added_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    active INTEGER NOT NULL DEFAULT 1
);

-- Tracked videos (input -- which videos to score per channel)
CREATE TABLE tracked_videos (
    video_id TEXT PRIMARY KEY,
    channel_id TEXT NOT NULL REFERENCES tracked_channels(channel_id),
    video_title TEXT,
    published_at TEXT,
    added_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    active INTEGER NOT NULL DEFAULT 1
);
```

### Design Decisions

| Decision | Rationale |
|----------|-----------|
| TEXT timestamps (ISO 8601) | Human-readable in SQLite CLI, sortable, compatible with existing pipeline |
| UNIQUE(video_id, fetched_at) | Prevents duplicate snapshots from retry/crash-recovery |
| Singleton config tables (id=1) | Weights/thresholds are system-global, not per-channel (yet) |
| Separate raw_video/raw_channel | Different fetch cadences possible, different retention policies |
| No foreign keys on raw tables | Append-only tables should never cascade-delete; tracked_* tables manage lifecycle |
| Same SQLite file as pipeline | Cross-system queries (library_storage joins with content_items) without complexity |

### Retention Strategy

```sql
-- Downsample old data: keep only daily snapshots after 30 days
-- Keep all snapshots for the most recent 30 days (full resolution)
-- This is a periodic maintenance job, not part of the scoring pipeline
DELETE FROM raw_video_scores
WHERE fetched_at < date('now', '-30 days')
AND id NOT IN (
    SELECT MIN(id)
    FROM raw_video_scores
    WHERE fetched_at < date('now', '-30 days')
    GROUP BY video_id, date(fetched_at)
);
```

## Google Sheets Sync Architecture

### Push-Only Pattern (SQLite --> Sheets)

Google Sheets is a **display layer only**. Data flows one direction: SQLite to Sheets. Never pull scores back from Sheets.

```
Sync Trigger (after each scoring cycle or on-demand)
    │
    ├─ Read from SQLite views (batch, single query per tab)
    │
    ├─ Format as 2D arrays for gspread batch_update()
    │
    ├─ gspread.worksheet.batch_update() -- single API call per tab
    │   (combines all cell updates into one request)
    │
    └─ Rate limiting: max 300 requests/60s per project
       Actual usage: ~4 batch_update calls per sync = trivial
```

### Rate Limit Safety

| Constraint | Limit | Our Usage | Safety Margin |
|-----------|-------|-----------|---------------|
| Requests per 60s per project | 300 | ~4 per sync cycle | 75x headroom |
| Requests per 60s per user | 60 | ~4 per sync cycle | 15x headroom |
| Request timeout | 180 seconds | ~2-5 seconds per batch | Safe |
| Cells per batch | ~50,000 | ~500-2,000 | 25x headroom |

### Exponential Backoff for 429s

```python
# sheets_sync.py
import time
from gspread.exceptions import APIError

def sync_with_backoff(worksheet, data, max_retries=3):
    for attempt in range(max_retries):
        try:
            worksheet.batch_update(data)
            return
        except APIError as e:
            if e.response.status_code == 429:
                wait = 2 ** attempt * 10  # 10s, 20s, 40s
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("Sheets sync failed after retries")
```

## Scheduling Architecture (APScheduler)

### Why APScheduler (Not Temporal)

The existing pipeline uses Temporal for long-running, multi-step workflows (script gen --> image gen --> TTS --> assembly). Scoring is fundamentally different: it is a **short batch job** (~5-30 seconds) that runs on a fixed interval. Temporal's durable execution, GPU routing, and human-in-the-loop capabilities are overkill. APScheduler is the right tool because:

1. In-process, zero infrastructure overhead (no Temporal server needed for scoring)
2. SQLite-backed job store (survives restarts)
3. Interval trigger with configurable 40-min cadence
4. Integrates cleanly with the existing FastAPI process via AsyncIOScheduler

### Scheduler Design

```python
# scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.triggers.interval import IntervalTrigger

def create_scorer_scheduler(db_url: str) -> AsyncIOScheduler:
    """Create scoring scheduler with persistent job store."""
    scheduler = AsyncIOScheduler(
        jobstores={
            'default': SQLAlchemyJobStore(url=db_url)
        },
        job_defaults={
            'coalesce': True,       # Merge missed runs into one
            'max_instances': 1,     # Never overlap scoring cycles
            'misfire_grace_time': 600  # 10-min grace for delayed runs
        }
    )
    return scheduler

def register_scoring_jobs(scheduler: AsyncIOScheduler):
    """Register the scoring pipeline job."""
    scheduler.add_job(
        run_scoring_cycle,
        trigger=IntervalTrigger(minutes=40),
        id='scoring_cycle',
        name='YouTube Score Collection & Calculation',
        replace_existing=True,  # Prevent duplicates on restart
    )
```

### Scoring Cycle Flow

```
APScheduler fires every 40 minutes
    │
    ├─ 1. Fetch raw data from YouTube API
    │     (Fetcher: ~5-15 seconds depending on channel count)
    │
    ├─ 2. SQL Views auto-recalculate (zero-cost, on-demand)
    │     (No explicit "scoring step" -- views are always current)
    │
    ├─ 3. Materialize library picks if changed
    │     (Librarian: ~1 second, only writes if gate results differ)
    │
    ├─ 4. Sync to Google Sheets
    │     (Sheets Sync: ~2-5 seconds, batch updates)
    │
    └─ 5. Log cycle completion
          (Duration, quota used, changes detected)
```

Total cycle time: **8-25 seconds**. No GPU, no heavy computation. CPU-only.

## Configuration Management (Weights/Thresholds/Presets)

### YAML-Driven Configuration

```yaml
# config/scoring.yaml
scoring:
  weights:
    views: 1.0
    likes: 2.0
    comments: 3.0
    engagement_ratio: 5.0
    views_velocity_24h: 2.0
    views_velocity_7d: 1.5
    subscriber_count: 1.0
    subscriber_growth_rate: 3.0
    like_to_view_ratio: 4.0
    comment_to_view_ratio: 4.0
    video_age_decay: -0.5      # Negative: older videos score lower
    upload_frequency: 2.0
    avg_view_duration_proxy: 3.0  # Proxy from engagement signals
    thumbnail_ctr_proxy: 2.0     # Proxy: like_velocity as CTR proxy
    # ... up to 24 metrics

  thresholds:
    library_min_score: 50.0
    gold: { min_score: 90.0, min_engagement: 0.05 }
    silver: { min_score: 70.0 }
    bronze: { min_score: 50.0 }

  presets:
    entertainment:
      weights:
        views: 3.0           # Views matter more for entertainment
        engagement_ratio: 2.0
    education:
      weights:
        comments: 5.0        # Comments matter more for education
        like_to_view_ratio: 4.0
    music:
      weights:
        views: 5.0
        views_velocity_24h: 4.0  # Viral velocity matters for music
```

### Config Loading Pattern

```python
# config.py
from pydantic import BaseModel
import yaml

class ScoringWeights(BaseModel, frozen=True):
    views: float = 1.0
    likes: float = 2.0
    comments: float = 3.0
    # ... all 24 weights

class ScoringThresholds(BaseModel, frozen=True):
    library_min_score: float = 50.0
    gold_threshold: float = 90.0
    # ...

class ScoringConfig(BaseModel, frozen=True):
    weights: ScoringWeights
    thresholds: ScoringThresholds

def load_scoring_config(path: str = "config/scoring.yaml") -> ScoringConfig:
    """Load and validate scoring config from YAML."""
    with open(path) as f:
        data = yaml.safe_load(f)
    return ScoringConfig(**data["scoring"])

def sync_config_to_db(config: ScoringConfig, session):
    """Write config to SQLite singleton tables for SQL view consumption."""
    # UPSERT scoring_weights with id=1
    # UPSERT scoring_thresholds with id=1
    # Views automatically pick up new values on next query
```

### Config Change Flow

```
1. Operator edits config/scoring.yaml
2. Config reload endpoint: POST /api/scoring/reload-config
3. Pydantic validates the YAML
4. sync_config_to_db() writes to singleton tables
5. SQL views automatically reflect new weights on next query
6. No re-fetch needed -- existing raw data is re-scored with new weights
```

This is a key architectural advantage: **changing scoring weights does NOT require re-fetching data from YouTube.** The raw data is immutable; the views recalculate instantly.

## Module Boundaries for Future Pipeline Integration

### Integration Points

```
                    ┌────────────────────────────────┐
                    │   Scoring & Library System      │
                    │   (this milestone)              │
                    ├────────────────────────────────┤
                    │ library_storage table           │ <── READ by:
                    │ channel_score_view              │
                    │ video_score_view                │
                    └────────┬───────────────────────┘
                             │
              ┌──────────────┼──────────────────┐
              │              │                  │
              ▼              ▼                  ▼
    ┌─────────────┐ ┌──────────────┐ ┌─────────────────┐
    │ Content      │ │ Playwright   │ │ Frontend         │
    │ Pipeline     │ │ Auto-Deploy  │ │ Dashboard        │
    │ (existing)   │ │ (future)     │ │ (existing)       │
    │              │ │              │ │                  │
    │ Use library  │ │ Use library  │ │ Display scores   │
    │ to pick      │ │ selections   │ │ and library      │
    │ topics from  │ │ for auto-    │ │ status in UI     │
    │ high-scoring │ │ publishing   │ │                  │
    │ channels     │ │ decisions    │ │                  │
    └─────────────┘ └──────────────┘ └─────────────────┘
```

### Contract: What Downstream Consumers Read

```python
# The scoring system exposes these via FastAPI endpoints AND direct SQLite access:

# 1. Library membership (for content pipeline topic selection)
# GET /api/scoring/library/latest
# Returns: [{"channel_id": "...", "tier": "gold", "score": 95.2}, ...]

# 2. Channel scores (for dashboard display)
# GET /api/scoring/channels
# Returns: [{"channel_id": "...", "avg_score": 82.1, "subscriber_count": 50000}, ...]

# 3. Video scores (for dashboard drill-down)
# GET /api/scoring/videos/{channel_id}
# Returns: [{"video_id": "...", "composite_score": 88.5, "views_delta": 1200}, ...]

# 4. Score history (for time-series charts)
# GET /api/scoring/history/{channel_id}?days=30
# Returns: [{"fetched_at": "...", "subscriber_count": ..., "avg_score": ...}, ...]
```

### Isolation Guarantees

The scoring system shares the same SQLite database file as the content pipeline BUT:
1. Uses its own set of tables (clearly named: `raw_video_scores`, `raw_channel_scores`, `scoring_*`, `library_*`, `tracked_*`)
2. Never reads or writes pipeline tables (`pipeline_runs`, `content_items`, `sync_logs`)
3. Content pipeline reads from `library_storage` (read-only) for topic selection -- it never writes scoring data
4. Both systems share `config.py` Settings but scoring adds its own settings fields

## Anti-Patterns to Avoid

### Anti-Pattern 1: Mutable Score Tables
**What:** UPDATE raw_video_scores SET view_count = X WHERE video_id = Y
**Why bad:** Destroys historical data. Cannot calculate deltas. Cannot audit past scoring.
**Instead:** Always INSERT new rows. Use window functions (LAG) for deltas.

### Anti-Pattern 2: Python Scoring Logic
**What:** Loop through videos in Python, calculate weighted scores, write results to a separate table.
**Why bad:** Two sources of truth. Config change requires reprocessing. Materialized scores go stale.
**Instead:** SQL views with CROSS JOIN to config tables. Always fresh. Always consistent.

### Anti-Pattern 3: Sheets as Scoring Input
**What:** Pull metric overrides or manual scores from Google Sheets back into SQLite.
**Why bad:** Race conditions, API quota waste, breaks unidirectional data flow.
**Instead:** Sheets is display-only. All configuration via YAML files committed to git.

### Anti-Pattern 4: Real-Time Streaming for 40-min Intervals
**What:** Using Kafka, Redis Streams, or event sourcing for a 36-times-per-day batch job.
**Why bad:** Massive infrastructure overhead for a job that runs in 10 seconds every 40 minutes.
**Instead:** APScheduler with batch processing. Simple, reliable, zero infrastructure.

### Anti-Pattern 5: Separate Scoring Database
**What:** Creating a second SQLite file for scoring data.
**Why bad:** Cross-database JOINs are painful. Content pipeline needs to read library_storage.
**Instead:** Same database file, different tables. SQLite handles concurrent reads well.

### Anti-Pattern 6: AI/ML for Classification
**What:** Using a trained model to classify channels into tiers.
**Why bad:** Opaque, hard to debug, requires training data that does not exist yet, overkill for threshold-based gating.
**Instead:** Pure SQL CASE statements with configurable thresholds. Transparent, reproducible, instantly tunable.

## Scalability Considerations

| Concern | At 5 channels | At 50 channels | At 500 channels |
|---------|---------------|-----------------|-----------------|
| API quota | 360 units/day | 3,600 units/day | Need quota increase or multiple projects |
| Cycle time | ~10 seconds | ~30 seconds | ~3 minutes, may need parallel batching |
| SQLite size (1 year) | ~50 MB | ~500 MB | ~5 GB, consider partitioning |
| Sheets sync | 4 batch updates | 10 batch updates | Hit rate limits, need pagination |
| View query time | <100ms | <500ms | Consider materialized tables with triggers |

**At 500 channels**: The architecture holds but needs three adaptations: (1) multiple GCP projects for API quota, (2) materialized scoring tables refreshed by triggers instead of pure views, (3) Sheets sync becomes paginated or switches to a different dashboard.

The design deliberately optimizes for the 5-50 channel range, which is the realistic operating scale.

## Suggested Build Order (Dependencies)

```
Phase A: Foundation (no external dependencies)
├── A1: SQLite schema (tables + indexes + views)
├── A2: Pydantic models + YAML config loader
├── A3: Config sync to SQLite singleton tables
└── A4: Unit tests for schema + config

Phase B: Data Collection (depends on A)
├── B1: YouTube API client (fetcher)
├── B2: Tracked channels/videos management
├── B3: APScheduler setup + job registration
└── B4: Integration tests (mock API --> raw tables)

Phase C: Scoring Engine (depends on A, can parallel with B)
├── C1: SQL views (video_score_view)
├── C2: SQL views (channel_score_view)
├── C3: SQL views (library_gate_view)
├── C4: Librarian materialization
└── C5: Tests with fixture data in raw tables

Phase D: Dashboard & Sync (depends on B + C)
├── D1: FastAPI scoring endpoints
├── D2: Sheets sync (push-only, batch_update)
├── D3: Frontend integration (score display)
└── D4: End-to-end test (fetch --> score --> library --> sheets)

Phase E: Integration with Content Pipeline (depends on D)
├── E1: Topic selection from library_storage
├── E2: Playwright auto-deploy hooks (read library)
└── E3: Cross-system integration tests
```

**Key insight for build order:** Phase C (scoring engine) is pure SQL and can be developed and tested with fixture data, completely independent of Phase B (data collection). This allows parallel development and faster iteration on the scoring formula before the API integration is ready.

## Sources

- [YouTube Data API v3 -- Videos: list](https://developers.google.com/youtube/v3/docs/videos/list) -- 1 unit per call, batch up to 50 IDs
- [YouTube API Quota Calculator](https://developers.google.com/youtube/v3/determine_quota_cost) -- 10,000 units/day default
- [YouTube API Quota Tracking 2026](https://www.contentstats.io/blog/youtube-api-quota-tracking) -- Endpoint cost breakdown
- [YouTube Analytics API Metrics](https://developers.google.com/youtube/analytics/metrics) -- RPM, revenue, subscribers
- [YouTube Analytics API Channel Reports](https://developers.google.com/youtube/analytics/channel_reports) -- Channel-level reporting
- [Google Sheets API Usage Limits](https://developers.google.com/workspace/sheets/api/limits) -- 300 req/60s per project
- [gspread 6.x User Guide](https://docs.gspread.org/en/latest/user-guide.html) -- batch_update best practices
- [APScheduler User Guide](https://apscheduler.readthedocs.io/en/3.x/userguide.html) -- SQLAlchemy job store, triggers
- [APScheduler Architecture](https://enqueuezero.com/concrete-architecture/apscheduler.html) -- Component breakdown
- [SQLite Time-Series Best Practices](https://moldstud.com/articles/p-handling-time-series-data-in-sqlite-best-practices) -- Indexing, partitioning
- [High-Performance Time Series on SQLite](https://dev.to/zanzythebar/building-high-performance-time-series-on-sqlite-with-go-uuidv7-sqlc-and-libsql-3ejb) -- Append-only patterns
- [SQLite Temporal Tables](https://www.sqliteforum.com/p/sqlite-and-temporal-tables) -- Snapshot patterns
- [Tracking 100K Videos Without Hitting YouTube API Quota](https://dev.to/siyabuilt/youtubes-api-quota-is-10000-unitsday-heres-how-i-track-100k-videos-without-hitting-it-5d8h) -- Quota optimization
