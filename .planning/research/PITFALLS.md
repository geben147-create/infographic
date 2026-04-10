# Domain Pitfalls

**Domain:** YouTube Scoring & Library System (analytics, scoring, video library management)
**Researched:** 2026-04-02
**Confidence:** HIGH (based on official API docs, known SQLite behaviors, and verified statistical edge cases)

## Critical Pitfalls

Mistakes that cause rewrites, data corruption, or silent incorrect scoring.

### Pitfall 1: Snapshot Overwrite Destroys Velocity Calculations

**What goes wrong:** The scoring system fetches YouTube video stats (views, likes, comments) periodically. If each fetch *overwrites* the previous row instead of *appending* a new timestamped snapshot, you permanently lose the ability to calculate velocity metrics (views/day, growth rate, acceleration). A video with 10,000 views tells you nothing without knowing it had 9,500 views yesterday vs. 100 views yesterday.

**Why it happens:** The naive schema uses `UPDATE videos SET views = ? WHERE video_id = ?`. It feels correct -- "just keep it current." Developers don't realize they need the history until after weeks of data have been silently destroyed.

**Consequences:**
- Cannot compute daily view velocity, trending scores, or growth curves
- All historical trend data permanently lost -- no recovery possible
- Scoring degrades to point-in-time snapshots (meaningless for ranking content quality)
- RPM proxy calculations (estimated revenue) become impossible without view deltas

**Prevention:**
- Design append-only `video_snapshots` table from day 1: `(video_id, snapshot_date, views, likes, comments, ...)`
- Separate `videos` table (current state, metadata) from `video_snapshots` (time series)
- Velocity = `(snapshot[t].views - snapshot[t-1].views) / days_between`
- Never UPDATE snapshot rows; only INSERT new ones
- Add unique constraint on `(video_id, snapshot_date)` to prevent duplicate snapshots per day

**Detection:** If your `video_snapshots` table has exactly 1 row per video_id, the design is wrong. Each video should accumulate rows over time.

**Phase relevance:** Must be correct in initial schema design (Phase 1 of scoring milestone). Cannot be retrofitted without data loss.

### Pitfall 2: YouTube Data API Quota Exhaustion from Stats Polling

**What goes wrong:** Fetching video statistics for a library of videos consumes YouTube API quota. With 5 channels producing 1 video/day for 6 months, you have ~900 videos. Polling stats for all 900 videos daily via `videos.list` costs 900 units/day (1 unit per call with `statistics` part). Add `search.list` calls at 100 units each, and you blow through 10,000 units before noon.

**Why it happens:** Developers call `videos.list` one video at a time, or use `search.list` to discover videos (100 units!) instead of maintaining a local video ID registry. Retry loops on transient errors double-consume quota. The quota resets at midnight Pacific Time, not midnight local.

**Consequences:**
- Scoring pipeline halts mid-day, leaving partial data (some videos updated, others stale)
- Partial updates corrupt velocity calculations (stale videos appear to have zero growth)
- Content pipeline video uploads also consume quota from the same project, competing with analytics

**Prevention:**
- **Batch `videos.list` calls**: The API accepts up to 50 video IDs per request. 900 videos = 18 API calls = 18 units (not 900)
- **Never use `search.list` for your own videos**: Maintain a local `videos` table. Use `channels.list` + `playlistItems.list` (1-3 units each) to discover new videos
- **Separate GCP project for analytics**: Isolate scoring quota from upload quota (uploads cost 1,600 units each)
- **Poll frequency by age**: New videos (< 7 days) = daily. Older videos (7-30 days) = weekly. Archive (> 30 days) = monthly
- **Cache API responses**: Store raw API response JSON. If pipeline fails mid-run, resume from cache without re-fetching
- **Track quota consumption**: Log units consumed per API call. Alert at 70% daily usage

**Detection:** `quotaExceeded` error (HTTP 403). Track `units_consumed` counter in your scoring pipeline.

**Phase relevance:** Architecture decision in schema design phase. Batch fetching must be the default pattern from the start.

### Pitfall 3: Z-Score Calculation on Insufficient or Uniform Data

**What goes wrong:** Z-score normalization divides by standard deviation. When all videos in a channel have identical view counts (e.g., a new channel with 5 videos all at ~100 views), standard deviation = 0, producing `NaN` or `Inf` scores. These `NaN` values then propagate through every downstream calculation: composite scores become `NaN`, rankings break, dashboard shows blank cells.

**Why it happens:** Z-score formula is `(x - mean) / std`. When `std = 0`, the result is undefined. Python's behavior varies: `scipy.stats.zscore` returns `NaN` for uniform arrays. Manual `(x - mean) / std` raises `ZeroDivisionError` or produces `inf`. There is a known SciPy bug (issue #12815) where `zscore` returned inconsistent results (`[nan, nan, nan]` vs `[1., 1., 1.]`) for different constant arrays.

**Consequences:**
- Composite scores become `NaN` -- single `NaN` in a weighted sum makes the entire sum `NaN`
- Rankings become empty or incorrect
- Dashboard shows blank or "NaN" text to the operator
- Comparison across channels with different data maturity is meaningless

**Prevention:**
- Guard every z-score calculation: if `std == 0`, return `0.0` for all values (all are at the mean)
- Minimum sample size gate: require N >= 3 videos before computing z-scores. Below threshold, use raw values or percentile ranks instead
- Use `numpy.nan_to_num()` as a safety net after every statistical operation
- Never chain calculations without NaN checks between stages
- Write explicit tests for: empty array, single element, all-identical values, mix of NaN and numbers

**Detection:** `assert not numpy.isnan(score).any()` after every scoring step. Log and alert on NaN production.

**Phase relevance:** Core scoring logic phase. Must be handled in the scoring functions themselves, not as a downstream fix.

### Pitfall 4: Google Sheets API Rate Limits Break Bidirectional Sync

**What goes wrong:** The scoring system writes computed scores back to Google Sheets for human consumption. With 5 channels x ~180 videos each = 900 rows of scores, writing individual cells hits the **60 writes/minute** limit (or 300 writes/100s per project). A full score refresh attempt triggers HTTP 429 errors, partial writes leave the sheet in an inconsistent state (some videos scored, others showing stale data).

**Why it happens:** Using `worksheet.update_cell()` in a loop instead of `worksheet.update()` with batch ranges. The per-user limit (100 requests/100 seconds) is more restrictive than the per-project limit when using a service account (all requests count as one user). Exponential backoff without jitter causes synchronized retry storms.

**Consequences:**
- Partial sheet updates: rows 1-50 have new scores, rows 51-900 have yesterday's scores
- Operator sees inconsistent rankings and makes wrong content decisions
- If sync errors are silently swallowed, no one knows the sheet is stale

**Prevention:**
- **Batch all writes**: Use `worksheet.update('A2:Z901', [[row1], [row2], ...])` -- one API call for the entire sheet
- **Read with `batch_get`**: One call to read all ranges, not per-cell reads
- **Write scores to SQLite first** (source of truth), then batch-push to Sheets as a notification layer
- **Exponential backoff with jitter**: `delay = base * 2^attempt + random(0, 1000ms)`
- **Idempotent writes**: If interrupted, the next run writes the complete current state (not a delta)
- **Timestamp the sync**: Write a "Last Updated" cell in the sheet so the operator knows freshness

**Detection:** HTTP 429 responses in logs. "Last Updated" timestamp older than expected in the sheet.

**Phase relevance:** Sheets sync phase. Batch operations must be the only write pattern.

## Moderate Pitfalls

### Pitfall 5: SQLite Append-Only Table Growth Without Pruning

**What goes wrong:** Daily snapshots for 900 videos = 900 rows/day = 328,500 rows/year. Add hourly snapshots for trending detection and it becomes 7.9M rows/year. Without indexing strategy, queries like "get last 30 days of snapshots for video X" become slow scans. Without pruning, the database file grows unbounded.

**Prevention:**
- **Composite index**: `CREATE INDEX idx_snapshots ON video_snapshots(video_id, snapshot_date DESC)` -- this makes range queries fast
- **INTEGER timestamps** (epoch seconds), not TEXT dates -- 10-100x faster for range queries
- **WAL mode**: `PRAGMA journal_mode=WAL` for concurrent read/write without locking
- **Tiered retention**: Raw daily snapshots for 90 days, then downsample to weekly averages for older data
- **VACUUM periodically**: SQLite does not reclaim space from deleted rows automatically. Schedule `VACUUM` monthly or use `auto_vacuum=INCREMENTAL`
- **Batch inserts in transactions**: 900 INSERTs in one `BEGIN/COMMIT` block, not 900 separate transactions

**Detection:** Query plan shows full table scan (`EXPLAIN QUERY PLAN`). Database file size growing linearly without bound.

**Phase relevance:** Schema design phase (indexes) + operations phase (pruning/vacuuming).

### Pitfall 6: RPM Proxy Accuracy Gives False Confidence

**What goes wrong:** The system estimates revenue using `views * estimated_RPM / 1000`. But RPM varies wildly: $0.50 for gaming Shorts vs $15 for US finance long-form. Not all views are monetized. RPM fluctuates seasonally (Q4 is 2-3x Q1). The operator sees "$500 estimated revenue" and makes business decisions on a number that could be off by 5x.

**Why it happens:** RPM data is not available via YouTube Data API -- only YouTube Studio (not programmatically accessible). Any RPM used in calculations is either a hardcoded estimate or manually entered, both of which drift from reality.

**Prevention:**
- **Label all RPM-derived values as estimates**: Display as "~$500 (estimated)" with a confidence indicator
- **Per-channel RPM configuration**: Allow operator to update RPM per channel from YouTube Studio data
- **RPM decay alert**: If RPM config hasn't been updated in 30 days, show a warning
- **Never use RPM estimates in automated decisions** (e.g., don't auto-prioritize topics based on estimated revenue)
- **Show views-based metrics alongside revenue estimates**: Let the operator see both the reliable metric (views) and the estimate (revenue)

**Detection:** Revenue estimates diverging significantly from YouTube Studio actuals (operator must manually compare).

**Phase relevance:** Scoring model phase. RPM must be a configurable input with freshness tracking, not a hardcoded constant.

### Pitfall 7: Composite Score Weighting Hides Bad Metrics

**What goes wrong:** A composite score like `0.3 * views_zscore + 0.3 * likes_zscore + 0.2 * comments_zscore + 0.2 * velocity_zscore` can mask that a video has zero comments but high views (bot traffic pattern), or high velocity but low absolute numbers (new video with 10 views gaining 5/day appears to "outperform" a video with 100,000 views gaining 100/day).

**Prevention:**
- **Show component scores alongside composite**: Never display only the composite
- **Floor thresholds**: Minimum views (e.g., 100) before a video enters scoring -- otherwise noise dominates
- **Separate absolute and relative metrics**: Don't mix raw counts with rates in the same z-score pool
- **Configurable weights**: Let the operator adjust weights per channel/niche -- a gaming channel cares about engagement ratio differently than a finance channel
- **Document what the score means**: "Score 8.5 means: top 15% in views, top 25% in engagement, above-average growth" -- not just a number

**Detection:** Videos with obviously low quality ranking highly. Sort by composite score and manually review top 10 for sanity.

**Phase relevance:** Scoring algorithm phase.

### Pitfall 8: Timezone Mismatch in Daily Aggregation

**What goes wrong:** YouTube API quota resets at midnight Pacific Time. YouTube Analytics uses Pacific Time for daily reporting. Your server runs in KST (UTC+9). Daily aggregation boundaries don't align, causing:
- A video published at 11 PM KST appears in "yesterday's" YouTube stats
- Velocity calculations show spikes/drops at day boundaries that are actually timezone artifacts
- Comparative analysis between channels in different timezones is misleading

**Prevention:**
- **Store all timestamps in UTC** in SQLite
- **Snapshot timing**: Run daily snapshots at a fixed UTC time (e.g., 08:00 UTC = midnight Pacific = 5 PM KST)
- **Document the snapshot window**: "Stats as of 08:00 UTC daily"
- **Never use `datetime.now()`** -- use `datetime.now(timezone.utc)`
- **YouTube API response timestamps are in ISO 8601 with timezone** -- parse them correctly

**Detection:** View counts decreasing between snapshots (impossible unless timezone mismatch). Day-boundary artifacts in velocity graphs.

**Phase relevance:** Data collection phase. Must be correct from the first snapshot.

## Minor Pitfalls

### Pitfall 9: Testing Scoring Logic with Realistic Data is Hard

**What goes wrong:** Unit tests use synthetic data (5 videos, uniform distributions). Real data has: power-law distributions (1 viral video, 899 normal ones), missing data for new videos, Shorts mixed with long-form, deleted/private videos returning empty stats.

**Prevention:**
- **Create a realistic test fixture**: Export a real snapshot from YouTube API (anonymized) as test data
- **Edge case test matrix**: empty channel, 1 video, all videos same stats, one viral outlier, mix of Shorts and long-form, video deleted mid-scoring, API returning partial data
- **Property-based tests**: Use Hypothesis to generate random valid datasets and verify invariants (scores are finite, rankings are complete, no NaN in output)
- **Regression tests for known bugs**: When a scoring bug is found in production, add its exact data as a test case

**Detection:** Tests pass but production scoring produces NaN or wrong rankings.

**Phase relevance:** Every phase should include targeted test cases.

### Pitfall 10: Shorts vs Long-Form Contamination in Scoring

**What goes wrong:** YouTube Shorts get dramatically different engagement patterns: higher view counts (autoplay), lower watch time, different RPM ($0.01-0.07 vs $2-15). Mixing Shorts and long-form in the same scoring pool makes Shorts appear as top performers by views but worst by revenue.

**Prevention:**
- **Tag videos as Short vs Long-form** (duration < 60s = Short)
- **Separate scoring pools**: Score Shorts against Shorts, long-form against long-form
- **Separate RPM estimates** per format
- **Dashboard filter**: Allow viewing scores filtered by format

**Detection:** Shorts consistently ranking #1 by views but last by estimated revenue.

**Phase relevance:** Data model phase (format tagging) + scoring algorithm phase (separate pools).

### Pitfall 11: Stale Video Metadata After Title/Thumbnail Changes

**What goes wrong:** Operator changes a video title or thumbnail on YouTube Studio to improve CTR. The scoring system still shows the old title/thumbnail from the last metadata fetch, causing confusion about which version of the video is being scored.

**Prevention:**
- **Refresh metadata (title, thumbnail URL) alongside stats** in the same snapshot run
- **Detect title changes**: Compare current title with previous snapshot. Flag changes in the dashboard
- **Track A/B test windows**: If title changed on day X, mark velocity calculations before/after the change

**Detection:** Dashboard shows a title the operator doesn't recognize.

**Phase relevance:** Data collection phase.

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Schema design | Snapshot overwrite (#1) | Append-only video_snapshots table from day 1 |
| Schema design | No format tagging (#10) | Include `is_short` boolean and duration in video model |
| YouTube API integration | Quota exhaustion (#2) | Batch `videos.list` (50 IDs/call), separate GCP project |
| YouTube API integration | Timezone mismatch (#8) | UTC everywhere, snapshot at fixed UTC time |
| Sheets sync | Rate limits (#4) | Batch writes only, idempotent full-state push |
| Scoring algorithm | Z-score NaN (#3) | Guard std=0, minimum sample size, NaN assertions |
| Scoring algorithm | Composite masking (#7) | Show components, configurable weights, floor thresholds |
| Revenue estimation | RPM inaccuracy (#6) | Label as estimate, per-channel config, freshness alerts |
| Data growth | SQLite bloat (#5) | Composite indexes, tiered retention, WAL mode |
| Testing | Synthetic data gaps (#9) | Realistic fixtures, edge case matrix, property tests |
| Metadata sync | Stale titles (#11) | Refresh metadata with stats, detect changes |

## Sources

- [YouTube Data API Quota Calculator](https://developers.google.com/youtube/v3/determine_quota_cost) -- HIGH confidence
- [YouTube API Quota Breakdown (2026)](https://www.contentstats.io/blog/youtube-api-quota-tracking) -- HIGH confidence
- [YouTube API Quota Management (100K videos)](https://dev.to/siyabuilt/youtubes-api-quota-is-10000-unitsday-heres-how-i-track-100k-videos-without-hitting-it-5d8h) -- MEDIUM confidence
- [Google Sheets API Usage Limits](https://developers.google.com/workspace/sheets/api/limits) -- HIGH confidence
- [SciPy zscore inconsistency issue #12815](https://github.com/scipy/scipy/issues/12815) -- HIGH confidence
- [SciPy zscore documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.zscore.html) -- HIGH confidence
- [SQLite Time Series Best Practices](https://moldstud.com/articles/p-handling-time-series-data-in-sqlite-best-practices) -- MEDIUM confidence
- [SQLite DateTime Fast Range Queries](https://copyprogramming.com/howto/how-to-use-time-series-with-sqlite-with-fast-time-range-queries) -- MEDIUM confidence
- [YouTube RPM Explained (vidIQ)](https://vidiq.com/blog/post/youtube-rpm/) -- MEDIUM confidence
- [YouTube Estimated Revenue Accuracy (Quora)](https://www.quora.com/How-accurate-is-Your-Estimated-Revenue-in-YouTube-Analytics) -- LOW confidence
- [Accumulating Snapshot Fact Tables](https://apxml.com/courses/data-modeling-schema-design-analytics/chapter-4-complex-fact-table-patterns/accumulating-snapshot-fact-tables) -- MEDIUM confidence
- [Upsert vs Replace in Data Engineering](https://medium.com/@tzhaonj/data-engineering-upsert-vs-replace-and-how-a-staging-table-can-help-you-find-the-perfect-middle-ea6db324b9ef) -- MEDIUM confidence
