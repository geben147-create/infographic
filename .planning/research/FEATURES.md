# Feature Landscape: YouTube Scoring & Library System

**Domain:** YouTube video/channel scoring, content classification, hook/thumbnail library
**Researched:** 2026-04-02
**Context:** Complements the existing video production pipeline. Scores videos/channels with 24 metrics, classifies content with keyword rules, stores hooks/thumbnails, tracks Evergreen ratios via daily snapshots, and calculates RPM proxies. All rule-based (no AI judgment).

## Table Stakes

Features the operator expects from any scoring/analytics system. Missing = system generates numbers nobody trusts or acts on.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Per-video composite score** | One number to compare videos at a glance. VidIQ and TubeBuddy both lead with a single score. Without it, 24 raw metrics overwhelm. | Low | Weighted sum of normalized metrics. The weighting formula IS the product. |
| **Score breakdown on hover/click** | A composite score without explanation is a black box nobody trusts. VidIQ shows a 15-point optimization checklist on hover. Users need to see WHY a video scored 73. | Low | Show individual metric contributions to the total. |
| **CTR, watch time, retention as first-class metrics** | These three drive YouTube's algorithm. Every competing tool (VidIQ, TubeBuddy, YouTube Studio) centers them. Ignoring any one means the score is unreliable. | Low | Pull from YouTube Analytics API or manual entry. |
| **Channel-level aggregation** | Operators run 5+ channels. Per-video scores are useless without channel roll-ups (average score, trend, top/bottom performers). | Medium | Aggregate per-channel with date-range filtering. |
| **Keyword-based content classification** | Content needs categories (niche, topic cluster, format type) to filter and compare meaningfully. "How do my finance videos score vs health?" requires classification. | Medium | Rule-based keyword matching against title/description/tags. |
| **Daily snapshot storage** | Scores change over time (views grow, retention stabilizes). Without historical snapshots, you cannot detect trends or track Evergreen behavior. | Medium | Nightly cron captures metric snapshot per video into SQLite. |
| **Sortable/filterable video list** | Operators scan 100+ videos. Must sort by score, date, channel, category. Must filter by classification, date range, score threshold. | Low | Standard table with sort/filter. |
| **Data freshness indicator** | If metrics are stale (last synced 3 days ago), the operator must know. Stale data presented as current erodes trust faster than missing data. | Low | Show "last updated" timestamp per video. |

## Differentiators

Features that make THIS system more useful than VidIQ/TubeBuddy for a multi-channel automation operator.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Evergreen ratio tracking** | The killer feature. Track how video views accumulate over days 1, 7, 30, 90. Evergreen content (tutorials, how-to) keeps gaining views; viral content spikes and dies. The ratio of Day-30 views to Day-1 views reveals content shelf life. No mainstream tool tracks this systematically. | Medium | Requires daily snapshots. Calculate ratio: views(day_N) / views(day_1). Classify as Evergreen (ratio > X), Viral (high day-1, steep decay), Steady, or Dead. |
| **RPM proxy estimation** | Operators cannot see RPM until YPP-qualified. Estimate revenue potential per video using niche-specific CPM benchmarks (finance $4-12, gaming $1-2, tech $4-8) multiplied by estimated monetizable views. Not accurate, but directionally useful for content strategy prioritization. | Low | Lookup table: niche -> CPM range. Formula: estimated_rpm = views * (niche_cpm / 1000) * 0.55. Flag as ESTIMATE, never present as actual revenue. |
| **Hook library with performance correlation** | Store first 30 characters of title + first 10 seconds of transcript as "hook." Correlate hook patterns with CTR and retention. Operators build a swipe file of what works. Creator Hooks Pro charges $29-79/mo for this alone. | Medium | Extract hooks from existing video data. Tag with performance metrics. Search/filter by category, score range. |
| **Thumbnail library with CTR tagging** | Store thumbnail images alongside their CTR. Sort by performance. Group by visual style (face close-up, text-heavy, before/after, etc.) using manual tags. Builds institutional knowledge of what thumbnails work per niche. | Medium | Store thumbnail URL/path + CTR + manual style tags. Gallery view with CTR overlay. |
| **Score trend sparklines** | Show 30-day score trend as a tiny inline chart next to each video/channel. Instantly reveals improving vs declining content. | Low | Requires daily snapshots. Render as SVG sparkline or simple ASCII-art in terminal. |
| **Cross-channel benchmarking** | "My health channel averages 67, my finance channel averages 82." Compare channel performance using the same scoring rubric. Reveals which channels need attention. | Low | Already have per-channel aggregation; this is a comparison view. |
| **Classification-based insights** | "Your evergreen tutorials score 40% higher than your news commentary." Surface patterns by combining classification + scoring. | Low | Group-by classification, show aggregate stats. |
| **Bulk score recalculation** | When the operator tunes scoring weights, recalculate all historical scores instantly. Enables rapid iteration on the scoring formula. | Low | Batch UPDATE in SQLite, re-apply weight formula. Fast because rule-based, no API calls. |

## Anti-Features

Features to explicitly NOT build. Each represents a common over-engineering trap in analytics tools.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **AI-powered scoring / ML models** | The system is explicitly rule-based. ML scoring requires training data you do not have (no YPP revenue data, no years of history). ML also makes scores unexplainable -- the operator cannot tune what they cannot understand. VidIQ/TubeBuddy both use rule-based scoring for exactly this reason. | Use weighted formulas with human-tunable coefficients. Operator adjusts weights via config. |
| **Real-time YouTube API polling** | YouTube Analytics API has strict quotas (10,000 units/day shared with upload). Polling every hour burns quota fast. Real-time data is unnecessary for a scoring system -- scores only meaningfully change daily. | Daily batch sync. Once per day, pull metrics for all videos, store snapshot. |
| **Predictive analytics ("this video will get X views")** | Prediction requires massive datasets and still performs poorly. YouTube's own Creator Studio does not predict. Any prediction you ship will be wrong and will erode trust in the entire system. | Track trends (sparklines), show Evergreen ratios. Let the operator infer, not the system predict. |
| **Competitor channel scraping** | Scraping YouTube violates ToS. Third-party APIs (Social Blade) are unreliable and rate-limited. The system should score YOUR channels, not spy on others. | If competitive data is needed later, use official YouTube Data API (public video stats only). |
| **Custom dashboard builder (drag-and-drop widgets)** | Massive frontend complexity for a single operator. Tools like Grafana exist for this. You will spend months building what Grafana does in hours. | Fixed, opinionated dashboard layout. If the operator wants custom views, export data to Google Sheets or Grafana. |
| **Natural language querying ("show me my best videos this month")** | Requires NLP parsing for minimal gain. The operator has 5 channels, not 500. A dropdown filter is faster than typing a query. | Provide sort/filter dropdowns and date range pickers. |
| **Automated content recommendations** | "You should make more finance tutorials" requires understanding content strategy, audience, competition. The system has no business giving content advice -- it scores, it does not strategize. | Show the data. Let the operator decide. Classification + scoring surface patterns; the human interprets. |
| **Social media integration (Twitter/Instagram metrics)** | Scope creep. Each platform has different APIs, rate limits, and metric definitions. The system is YouTube-focused. | YouTube only. If cross-platform needed, that is a separate system. |
| **Complex user roles / permissions** | Single operator system. Building RBAC for one user is pure over-engineering. | No auth, or simple API key. Local-only access is sufficient. |
| **Email/Slack alert notifications** | For daily-batch scoring, alerts add complexity with minimal value. The operator checks the dashboard once a day when scores update. | Dashboard shows "new scores available" indicator. Operator pulls, system does not push. |

## Feature Dependencies

```
YouTube Analytics API sync  -->  Daily metric snapshots
Daily metric snapshots      -->  Composite scoring
Daily metric snapshots      -->  Evergreen ratio calculation
Daily metric snapshots      -->  Score trend sparklines
Composite scoring           -->  Channel-level aggregation
Composite scoring           -->  Cross-channel benchmarking
Keyword classification      -->  Classification-based insights
Keyword classification      -->  Hook library categorization
Keyword classification      -->  Thumbnail library categorization
Hook extraction             -->  Hook library
Thumbnail storage           -->  Thumbnail library
Scoring weights config      -->  Bulk score recalculation
Niche CPM lookup table      -->  RPM proxy estimation
```

Critical path: API sync -> snapshots -> scoring -> everything else.
Classification is independent of scoring and can be built in parallel.
Libraries (hook/thumbnail) depend on classification for organization but not for storage.

## MVP Recommendation

### Phase A: Score Foundation (build first)

1. **Daily metric snapshot sync** - Pull metrics from YouTube Analytics API, store in SQLite. This is the data foundation everything else depends on.
2. **Composite scoring with breakdown** - 24 metrics, weighted formula, tunable coefficients. Show score + breakdown.
3. **Keyword-based classification** - Rule engine: keyword lists per category, match against title/description/tags. Hierarchical (niche > topic > format).
4. **Sortable/filterable video list** - Dashboard table with score, classification, date, channel columns.

### Phase B: Intelligence Layer (build second)

5. **Evergreen ratio tracking** - Day-1/7/30/90 view ratios. Classify content lifecycle type.
6. **RPM proxy estimation** - Niche CPM lookup + view count formula. Clearly labeled as estimate.
7. **Channel aggregation + cross-channel benchmarks** - Per-channel averages, comparison view.
8. **Score trend sparklines** - 30-day inline trend visualization.

### Phase C: Library System (build third)

9. **Hook library** - Extract, store, tag, correlate with CTR/retention.
10. **Thumbnail library** - Store, tag style, correlate with CTR.
11. **Classification-based insights** - Aggregate patterns by category.
12. **Bulk score recalculation** - Re-score history when weights change.

### Defer

- A/B thumbnail testing integration (needs traffic volume first)
- Any ML/AI-based scoring (rule-based is correct for this scale)
- Competitor analysis (out of scope, ToS risk)
- Cross-platform metrics (scope creep)

## 24 Metrics: Recommended Breakdown

Based on research of VidIQ, TubeBuddy, and YouTube Studio Analytics, here are the 24 metrics organized by category:

### Reach (6 metrics)
1. Impressions
2. Impressions CTR (%)
3. Views (total)
4. Unique viewers
5. Traffic source distribution (search vs suggested vs external)
6. Search ranking position (for target keyword)

### Engagement (6 metrics)
7. Watch time (hours)
8. Average view duration (seconds)
9. Average percentage viewed (%)
10. Likes / dislikes ratio
11. Comments count
12. Shares count

### Retention (4 metrics)
13. Audience retention at 30 seconds (%)
14. Audience retention at 50% of video (%)
15. Relative retention vs similar-length videos (above/below average)
16. Re-watch ratio (segments watched more than once)

### Growth (4 metrics)
17. Subscribers gained from video
18. Subscriber conversion rate (subs gained / views)
19. Views velocity (views per hour in first 48h)
20. Evergreen ratio (day-30 views / day-1 views)

### Revenue Proxy (4 metrics)
21. Estimated RPM (niche CPM * views * 0.55 / 1000)
22. Niche CPM tier (from lookup table)
23. Monetizable view percentage (estimated based on video length > 8min)
24. Revenue trend (RPM proxy over time)

## Scoring Weight Categories

Based on what actually drives YouTube success (per VidIQ and YouTube Creator Academy):

| Category | Suggested Weight | Rationale |
|----------|-----------------|-----------|
| Retention | 30% | YouTube's algorithm weights retention heaviest |
| Engagement | 25% | Signals content quality to algorithm |
| Reach | 20% | Discoverability and CTR |
| Growth | 15% | Subscriber impact and velocity |
| Revenue Proxy | 10% | Directional only, lowest confidence data |

Weights should be operator-configurable. These are starting defaults.

## Keyword Classification: Recommended Approach

Based on content taxonomy best practices (IAB taxonomy, Kontent.ai):

### Structure: 3-level hierarchy
```
Level 1: Niche       (health, finance, tech, gaming, education)
Level 2: Topic       (weight-loss, investing, AI-tools, FPS, math)
Level 3: Format      (tutorial, listicle, news, review, story)
```

### Matching Rules
- **Title match**: Highest priority. Keywords in title are most intentional.
- **Tag match**: Second priority. Creator-assigned classification.
- **Description match**: Third priority. More noise, but catches edge cases.
- **Controlled vocabulary**: Operator defines keyword lists per category. No free-form tagging -- controlled vocabulary prevents "finance" vs "financial" vs "money" fragmentation.
- **Multi-label**: A video can belong to multiple Level 2 topics (e.g., "AI investing tools" = tech + finance).
- **Fallback**: Unmatched videos go to "uncategorized" -- operator reviews and updates rules.

### Maintenance
- Track "uncategorized" count. If > 10% of videos are unclassified, keyword rules need expansion.
- Log which rules fire most/least. Dead rules should be pruned.

## Sources

- [VidIQ Scorecard Features](https://vidiq.com/features/scorecard/)
- [VidIQ vs TubeBuddy Comparison](https://linodash.com/vidiq-vs-tubebuddy/)
- [YouTube Analytics Complete Guide (Improvado)](https://improvado.io/blog/youtube-analytics-guide)
- [YouTube Analytics for Creators (InfluenceFlow)](https://influenceflow.io/resources/youtube-analytics-for-creators-a-complete-guide-to-understanding-your-channel-performance/)
- [Creator Hooks Pro](https://creatorhooks.com/tools/)
- [TitleHooks Packaging Audit](https://titlehooks.com/)
- [OutlierKit Video Analyzer](https://outlierkit.com/blog/best-youtube-video-analyzer-tools)
- [Viewstats by MrBeast](https://www.viewstats.com/info)
- [YouTube RPM Explained (VidIQ)](https://vidiq.com/blog/post/youtube-rpm/)
- [YouTube CPM/RPM Rates 2026 (MilX)](https://milx.app/en/trends/youtube-cpm-rpm-rates-2026-average-niches-countries-more/)
- [Content Taxonomy Best Practices (Kontent.ai)](https://kontent.ai/blog/from-chaos-to-clarity-best-practices-for-content-taxonomy/)
- [Video Metadata Taxonomy (IRIS.TV)](https://blog.iris.tv/en/video-programming-playbook-metadata-taxonomy)
- [Common YouTube Analytics Mistakes (Subscribr)](https://subscribr.ai/p/common-youtube-analytics-mistakes)
- [Evergreen vs Trending Content Strategy (Subscribr)](https://subscribr.ai/p/evergreen-vs-trending-youtube-topics)
- [Evergreen Content for YouTube Growth (TubeBuddy)](https://www.tubebuddy.com/blog/evergreen-youtube-content-strategy/)
