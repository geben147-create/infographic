# Dashboard UI/UX Design Reference

> Comprehensive design system reference for building a production-quality dashboard.
> Modeled after Stripe's design philosophy: sophistication, trust, clarity, and density.

---

## 1. Stripe's Design Philosophy

| Principle | Description |
|-----------|-------------|
| **Sophistication & Trust** | Cool tones, layered depth, financial gravitas. Multiple shadow layers create realistic depth. |
| **Obsessive polish** | Stripe spends 20x more time on details than typical teams. Even typing animations use randomized delays for realism. |
| **Constraint-driven consistency** | Custom styling is intentionally limited. Color choices are restricted to maintain accessibility and platform cohesion. |
| **Token-based system** | All styling uses design tokens (colors, spacing, typography) rather than arbitrary values. |
| **Science-driven color** | Colors built in CIELAB perceptually uniform color space. Scale numbers differing by 500+ guarantee AA contrast (4.5:1). |
| **Progressive disclosure** | Overview first (charts, KPIs), then drill-down (tables, detail views). Search spans all entity types. |

### Stripe's Core Color Tokens

| Token | Value | Usage |
|-------|-------|-------|
| `colorPrimary` | `#0570de` | Primary actions, links |
| `colorBackground` | `#ffffff` | Page background |
| `colorText` | `#30313d` | Body text |
| `colorDanger` | `#df1b41` | Errors, destructive actions |
| `borderRadius` | `4px` | Subtle, not rounded |
| `spacingUnit` | `2px` | Base unit (multiples of 2) |
| `fontFamily` | `Ideal Sans, system-ui, sans-serif` | Clean, neutral typeface |

---

## 2. Layout Patterns

### Scanning Patterns

| Pattern | When to Use | Key Rule |
|---------|-------------|----------|
| **F-pattern** | Text-heavy dashboards, data tables | Most important content in top-left. Users scan top row fully, then left edge downward. |
| **Z-pattern** | Landing pages, sparse layouts | Eye moves: top-left -> top-right -> bottom-left -> bottom-right. Place CTA at terminal point. |

### Sidebar vs. Top Navigation

| Aspect | Sidebar (Recommended for Dashboards) | Top Nav |
|--------|---------------------------------------|---------|
| Best for | Complex hierarchy, 5-15+ sections | Simple sites, 3-5 sections |
| Expanded width | 240-300px | Full width, 48-64px height |
| Collapsed width | 48-64px (icon only) | N/A |
| Mobile behavior | Hidden by default below 768px; use bottom tab bar (max 5 items) or slide-over drawer | Hamburger menu |

### Dashboard Layout Structure

```
+--sidebar--+------------------main-content------------------+
|  logo     |  breadcrumb / page title                       |
|  nav      |  +--stat-card--+--stat-card--+--stat-card--+   |
|  items    |  +--chart-wide-----------+--chart-small----+   |
|  (5-7     |  +--data-table-full-width------------------+   |
|   max)    |                                                 |
+-----------+-------------------------------------------------+
```

### Layout Rules

| Rule | Value |
|------|-------|
| Max visible stat cards in initial view | 5-6 |
| Content max-width | 1200-1440px |
| Sidebar takes | ~15% of viewport when expanded |
| Main content area | Remaining 85% |
| Mobile breakpoint | 768px (hide sidebar) |
| Tablet breakpoint | 1024px (collapse sidebar) |

---

## 3. Color System

### 60-30-10 Rule

| Proportion | Role | Example |
|------------|------|---------|
| **60%** | Dominant / background | White (`#ffffff`) or light gray (`#f6f8fa`) |
| **30%** | Secondary / surfaces | Card backgrounds, sidebar, borders |
| **10%** | Accent / interactive | Primary blue, CTAs, active states |

### Semantic Color Palette

| Purpose | Color | Hex Range | Usage |
|---------|-------|-----------|-------|
| **Primary** | Blue | `#0570de` | Links, primary buttons, active states |
| **Success** | Green | `#30b566` | Completed, healthy, positive trends |
| **Warning** | Amber/Yellow | `#f5a623` | Caution, pending, degraded |
| **Danger** | Red | `#df1b41` | Errors, failures, destructive actions |
| **Info** | Light blue | `#5bc0de` | Informational, neutral alerts |
| **Neutral** | Gray scale | `#6b7280` | Secondary text, borders, disabled |

### Accessibility Contrast Requirements

| Element | Minimum Ratio | Standard |
|---------|---------------|----------|
| Normal text (< 18px) | 4.5:1 | WCAG AA |
| Large text (>= 18px or 14px bold) | 3:1 | WCAG AA |
| UI components & graphics | 3:1 | WCAG 2.1 AA |
| Focus indicators | 3:1 | WCAG 2.2 AA |

### Color Rules

- NEVER use color as the sole indicator. Always pair with icon, text label, or pattern/texture.
- Test with grayscale filter to verify information is still conveyed.
- Each status color must work on both light and dark backgrounds.
- For charts: use colorblind-safe palettes (avoid red/green only pairs).

---

## 4. Typography System

### Modular Type Scale (1.25 ratio, base 16px)

| Token | Size | Weight | Line Height | Use Case |
|-------|------|--------|-------------|----------|
| `display` | 32px | 700 | 40px | Page titles, hero numbers |
| `h1` | 28px | 700 | 36px | Section headers |
| `h2` | 24px | 600 | 32px | Card titles |
| `h3` | 20px | 600 | 28px | Sub-section headers |
| `body-lg` | 18px | 400 | 28px | Emphasized body text |
| `body` | 16px | 400 | 24px | Default body text |
| `body-sm` | 14px | 400 | 20px | Secondary text, table cells |
| `caption` | 12px | 400 | 16px | Labels, timestamps, helper text |
| `overline` | 11px | 600 | 16px | Category labels (uppercase + letter-spacing) |

### Typography Rules

| Rule | Value |
|------|-------|
| Line heights | Always multiples of 4px (fits 8px grid) |
| Max line length | 60-80 characters for readability |
| Font pairing | One sans-serif family. Use weight/size for hierarchy, not multiple fonts. |
| Metric numbers | Use tabular (monospace) figures for data alignment in tables |
| Number formatting | Thousands separator, 2 decimal places for currency, abbreviated for large numbers (1.2K, 3.4M) |

---

## 5. Spacing System (8px Grid)

### Spacing Scale

| Token | Value | Usage |
|-------|-------|-------|
| `space-0.5` | 4px | Icon-to-text gap, tight internal padding |
| `space-1` | 8px | Minimum padding, related element gap |
| `space-2` | 16px | Standard padding, card internal spacing |
| `space-3` | 24px | Section separation within a card |
| `space-4` | 32px | Card-to-card gap, section spacing |
| `space-6` | 48px | Major section separation |
| `space-8` | 64px | Page-level vertical spacing |

### Spacing Rules

| Rule | Guideline |
|------|-----------|
| **Internal < External** | Padding inside a card must be less than margin between cards. |
| **Consistent gaps** | Use the same gap value for all cards in a row. |
| **Touch targets** | Minimum 44x44px (WCAG 2.2 AA) for clickable elements. |
| **Button spacing** | 16px between side-by-side buttons; 8px for stacked buttons. |
| **Button internal** | Minimum 16px padding from label to button edge. |
| **Icon spacing** | 8px between icon and adjacent text. |

---

## 6. Component Design Guidelines

### 6.1 Stat/Metric Cards

```
+--card (padding: 24px)---------------------------+
|  LABEL (caption, gray, uppercase)               |
|  $12,450.00 (display, bold)                     |
|  [up-arrow] +12.5% vs last month (body-sm)      |
+------------------------------------------------+
```

| Rule | Guideline |
|------|-----------|
| Max per row | 3-4 on desktop, 2 on tablet, 1 on mobile |
| Trend indicator | Arrow icon + percentage + comparison period |
| Trend colors | Green for positive, red for negative, gray for neutral |
| Number format | Tabular figures, right-aligned within card if in a row |
| Click behavior | Card click navigates to detail view (entire card is clickable) |
| Loading state | Skeleton with shimmer matching exact layout |

### 6.2 Data Tables

| Rule | Guideline |
|------|-----------|
| **Column alignment** | Text: left-aligned. Numbers: right-aligned. Status: center-aligned. |
| **Row height** | Default: 48px. Compact: 36px. Comfortable: 56px. |
| **Zebra striping** | Optional. If used, alternate row color should be subtle (2-3% darker). |
| **Hover state** | Subtle background change on row hover. |
| **Sort indicators** | Arrow icon on sortable column headers. Active sort bold + highlighted. |
| **Pagination** | Show total count, page size selector (10/25/50/100), page navigation. |
| **Filtering** | Persistent filter bar above table. Active filters shown as removable chips. |
| **Empty state** | Illustration + message + CTA. Never just "No data." |
| **Sticky header** | Table header stays visible on scroll. |
| **Column resize** | Allow drag-to-resize on desktop for data-dense tables. |
| **Row actions** | Visible action buttons (not hidden behind hover). Max 2-3 inline actions; overflow into "..." menu. |
| **Selection** | Checkbox column on left. Bulk action bar appears on selection. |
| **Responsive** | Priority columns stay visible; low-priority columns hide or move to expandable row detail. |

### 6.3 Cards (General)

| Aspect | Guideline |
|--------|-----------|
| **Border vs Shadow** | Use subtle border (`1px solid #e5e7eb`) for flat design or box-shadow for elevated feel. Not both. |
| **Shadow scale** | `sm`: 1px blur (default cards). `md`: 4px blur (hover/active). `lg`: 10px blur (modals/dropdowns). |
| **Border radius** | 8px for cards, 4px for inputs/buttons, 12px for modals. Consistent per category. |
| **Padding** | 16px minimum. 24px recommended for standard cards. |
| **Hierarchy** | Title -> value/content -> supporting text -> actions. Top-to-bottom. |
| **Max cards per view** | 5-6 in initial viewport. Scroll for more. |

### 6.4 Status Indicators

| Pattern | When to Use | Design |
|---------|-------------|--------|
| **Dot** (8px circle) | Inline status next to text | Color + text label always |
| **Badge/Chip** | Status in tables, lists | Colored background (10% opacity) + colored text + optional icon |
| **Progress bar** | Completion percentage | Filled bar + percentage text |
| **Sparkline** | Trend in compact space | Tiny inline line chart (no axes) |
| **Icon + text** | Prominent status display | Semantic icon + label |

Status Badge Color Map:

| Status | Background | Text | Icon |
|--------|-----------|------|------|
| Active / Running | `blue-50` | `blue-700` | Spinning circle |
| Completed / Success | `green-50` | `green-700` | Checkmark |
| Warning / Degraded | `amber-50` | `amber-700` | Triangle alert |
| Error / Failed | `red-50` | `red-700` | X circle |
| Pending / Queued | `gray-50` | `gray-600` | Clock |
| Draft | `gray-50` | `gray-500` | Pencil |

### 6.5 Buttons

| Level | Style | When to Use |
|-------|-------|-------------|
| **Primary** | Solid background, white text | Main action per section. MAX ONE per visible area. |
| **Secondary** | Border only, colored text | Secondary actions alongside primary |
| **Ghost/Tertiary** | No border, no background, colored text | Low-priority actions, toolbar actions |
| **Danger (primary)** | Red solid background | Required destructive step (delete account) |
| **Danger (ghost)** | Red text, no background | Optional destructive action (remove item) |
| **Disabled** | 40% opacity, no pointer | Action unavailable. Always show tooltip explaining why. |

Button sizing:

| Size | Height | Padding (h) | Font Size | Use Case |
|------|--------|-------------|-----------|----------|
| `sm` | 32px | 12px | 13px | Inline, table rows |
| `md` | 40px | 16px | 14px | Default, forms |
| `lg` | 48px | 20px | 16px | Hero actions, CTAs |

### 6.6 Forms & Inputs

| Rule | Guideline |
|------|-----------|
| Label position | Above the input (not floating, not inline) |
| Required indicator | Asterisk (*) after label text |
| Helper text | Below input, gray, 12px. Disappears on error and replaced by error message. |
| Error state | Red border + red error message below + error icon inside input |
| Input height | 40px default, 48px for prominent forms |
| Spacing between fields | 24px vertical gap |
| Button placement | Primary action right-aligned, secondary left of primary |
| Validation timing | On blur for individual fields, on submit for the form |

### 6.7 Sidebar Navigation

| Rule | Guideline |
|------|-----------|
| Item count | 5-7 primary items max at top level |
| Icon + label | Always pair. Icon-only acceptable in collapsed state with tooltip. |
| Icon size | 20-24px |
| Active state | Filled icon variant + highlighted background + left border accent |
| Hover state | Subtle background color change |
| Nested items | Disclosure arrow, indent children 24px |
| Collapse toggle | Persistent chevron at top or bottom. Save preference to localStorage. |
| Collapse animation | 200-300ms ease transition |
| Section dividers | Thin line + optional section label between groups |
| Footer area | Settings, help, user profile at bottom |

---

## 7. Data Visualization

### Chart Type Selection

| Goal | Chart Type | Rules |
|------|-----------|-------|
| Compare categories | **Bar chart** | Sort by value (not alphabetical). Horizontal if many categories or long labels. |
| Trend over time | **Line chart** | X-axis = time (left to right, no gaps). Max 3-5 lines before it gets cluttered. |
| Part-to-whole (static) | **Pie/Donut chart** | Max 5 slices. Must sum to meaningful 100%. |
| Part-to-whole (over time) | **Stacked area chart** | Max 3-5 categories. |
| Correlation | **Scatter plot** | Two numeric axes. Add trend line if useful. |
| Distribution | **Histogram** | Equal bin widths. |
| Single KPI progress | **Gauge / Progress bar** | Show target line/value for context. |
| Trend in compact space | **Sparkline** | No axes, no labels. Just the shape. |

### Chart Design Rules

| Rule | Guideline |
|------|-----------|
| Always show context | Comparison line, target, or previous period |
| Remove chartjunk | No 3D effects, no decorative gridlines, no gradient fills |
| Label directly | Label lines/bars directly instead of using a separate legend when possible |
| Tooltip on hover | Show exact value + date + comparison on hover |
| Responsive | Charts must resize. Reduce data points on mobile if needed. |
| Animation | Animate on first render only (300-500ms ease-out). No animation on data refresh. |
| Y-axis | Start at 0 for bar charts. Line charts can start at a contextual minimum. |
| Grid lines | Light horizontal only. No vertical grid lines unless scatter plot. |
| Colors | Max 5-7 colors per chart. Use sequential palette for continuous data, categorical for discrete. |

---

## 8. State Design

### 8.1 Empty States

| Scenario | Content Formula |
|----------|----------------|
| **First use** | Illustration + "You have no [items] yet" + "Create your first [item]" CTA |
| **No search results** | "No results for [query]" + suggestions or "Clear filters" link |
| **Filtered to zero** | "No [items] match these filters" + "Clear all filters" link |
| **Error loading** | Error icon + "Failed to load [items]" + "Try again" button |
| **Multiple empty widgets** | Use text-only empty states (no illustrations) to avoid repetitive clutter |

Rules:
- Every empty state must have an actionable CTA.
- Size variants: extra-small (inside cards), small (inside tables/modals), large (full page).
- Never display a raw "null", "undefined", or completely blank area.

### 8.2 Loading States

| Pattern | When to Use | Duration |
|---------|-------------|----------|
| **Skeleton screen** | Initial page/section load | Any duration. Preferred over spinner. |
| **Skeleton + shimmer** | Content loading | 300-700ms shimmer cycle |
| **Inline spinner** | Button action in progress | < 5 seconds expected |
| **Progress bar** | Upload, long process with known duration | > 5 seconds |
| **Optimistic update** | Toggle, like, bookmark, status change | Instant (rollback on error) |

Skeleton screen rules:
- Match the exact layout of the content being loaded (same heights, widths, positions).
- Use neutral gray rectangles with subtle pulse animation.
- Show skeleton for minimum 200ms to avoid flash.
- Never show both skeleton and spinner simultaneously.

### 8.3 Error States

| Type | When to Use | Design |
|------|-------------|--------|
| **Inline** | Field validation errors | Red text below the field, red border |
| **Banner** | Page-level warnings/errors | Full-width colored bar at top of content area. Dismissible. |
| **Toast** | Transient notifications | Bottom-right. Auto-dismiss after 5s. Manual dismiss for errors. |
| **Modal/Dialog** | Destructive confirmation, critical errors | Centered overlay. Requires explicit action. |
| **Empty state** | Failed data fetch | In the content area where data would appear |

Toast rules:
- Success: auto-dismiss 3-5 seconds.
- Error: persist until manually dismissed.
- Max 3 toasts visible at once; queue the rest.
- Stack from bottom, newest on top.
- Position: bottom-right for desktop, bottom-center for mobile.

---

## 9. Pipeline-Specific UX (YouTube Automation)

### 9.1 Pipeline Status Tracking

| Element | Design |
|---------|--------|
| **Pipeline row in table** | Topic name + channel + status badge + progress bar + timestamp + actions |
| **Status flow** | `queued` -> `scripting` -> `generating_media` -> `assembling` -> `ready_to_upload` -> `uploaded` |
| **Progress indicator** | Stepped progress bar showing current phase (6 steps). Completed steps are green, current is blue with animation, future is gray. |
| **Time estimate** | Show elapsed time and estimated remaining time per phase. |
| **Error in pipeline** | Red badge on failed step. Expandable row shows error message + "Retry" button on the failed step. |
| **Log viewer** | Expandable section per pipeline showing timestamped log entries. Scrollable, monospace font, auto-scroll to bottom. |

### 9.2 Cost/Billing Display

| Rule | Guideline |
|------|-----------|
| Format | Always show currency symbol + 2 decimal places ($1.25) |
| Breakdown | Show cost per component (video gen, TTS, API calls) |
| Comparison | Show vs. budget/target with color coding |
| Trend | Daily/weekly cost line chart with running total |
| Alerts | Yellow badge when approaching budget threshold (80%), red at 100% |

### 9.3 File Download Flow

| Step | UX |
|------|-----|
| Trigger | Button with download icon + file type label |
| In progress | Button becomes disabled + inline spinner + "Preparing..." |
| Ready | Browser native download starts. Toast: "Download started" |
| Error | Toast with error + "Try again" link |
| Large files | Show file size before download. Progress bar during download. |

### 9.4 Health/Monitoring Display

| Component | Indicator |
|-----------|-----------|
| API endpoints | Green/yellow/red dot + response time (ms) |
| GPU utilization | Percentage bar + temperature |
| Queue depth | Number badge. Yellow if > threshold. |
| Service uptime | Percentage + last incident time |
| Layout | Grid of small health cards. Click for detail panel. |

### 9.5 Real-Time Data Updates

| Method | When to Use | UX Treatment |
|--------|-------------|--------------|
| **Polling** (10-30s) | Pipeline status, queue depth | Fade transition on value change. "Last updated" timestamp visible. |
| **WebSocket** | Live logs, active pipeline progress | Streaming append. Auto-scroll if user is at bottom. |
| **Optimistic UI** | User-triggered actions (retry, cancel) | Instant UI update. Rollback + error toast on failure. |
| **Manual refresh** | Expensive queries, reports | "Refresh" button with last-updated timestamp. |

Animation on data change:
- Number change: brief highlight flash (200ms yellow background fade).
- Status change: smooth badge color transition (300ms).
- New table row: slide-in from top (200ms).
- Removed row: fade-out (200ms), then collapse space (200ms).

---

## 10. Accessibility Essentials (WCAG 2.1 AA)

### Contrast Ratios (Non-Negotiable)

| Element | Minimum |
|---------|---------|
| Normal text | 4.5:1 |
| Large text (18px+ or 14px bold) | 3:1 |
| UI components, icons, borders | 3:1 |
| Focus indicators | 3:1 vs unfocused state |

### Focus Indicators

| Rule | Implementation |
|------|----------------|
| Visible focus ring | 2px solid outline with 3:1 contrast. Never `outline: none` without replacement. |
| Focus not obscured | Focused element must not be hidden behind sticky headers, modals, etc. |
| Focus order | Matches visual reading order (left-to-right, top-to-bottom). |
| Skip links | "Skip to main content" link as first focusable element. |

### Keyboard Navigation

| Rule | Implementation |
|------|----------------|
| All features keyboard-accessible | No mouse-only interactions. |
| No keyboard traps | Tab/Shift+Tab must always move focus. Escape closes modals/dropdowns. |
| Arrow keys | Navigate within composite widgets (tabs, menus, data grids). |
| Enter/Space | Activate buttons/links. Space for checkboxes/toggles. |
| Custom shortcuts | Must be disableable or remappable. |

### Screen Reader Support

| Element | Requirement |
|---------|-------------|
| Images | `alt` text (decorative images: `alt=""`) |
| Icons | `aria-label` or visually hidden text |
| Dynamic content | `aria-live` regions for toasts, status updates |
| Tables | Proper `<th>` with `scope`. Caption or `aria-label` on table. |
| Charts | Text alternative summarizing the data trend |
| Modals | `aria-modal="true"`, focus trap, return focus on close |
| Loading states | `aria-busy="true"` on loading containers |

### Motion & Animation

| Rule | Implementation |
|------|----------------|
| `prefers-reduced-motion` | Respect OS setting. Disable non-essential animation. |
| Essential motion | Keep functional transitions (page load) but make instant. |
| Auto-playing content | Provide pause/stop controls. |
| Flash content | Nothing flashes more than 3 times per second. |

---

## 11. Performance UX

| Technique | Implementation | Perceived Speed Gain |
|-----------|---------------|---------------------|
| **Skeleton screens** | Gray placeholders matching content layout + shimmer | Feels 20% faster than spinners |
| **Optimistic updates** | Update UI immediately, rollback on error | Feels instant |
| **Above-the-fold priority** | Render visible content first, lazy-load below fold | First paint < 1s |
| **Predictive prefetch** | On hover over nav link, prefetch that route's data | Next page feels instant |
| **Image lazy loading** | `loading="lazy"` on images below fold | Reduces initial payload |
| **Virtual scrolling** | Render only visible table rows (for 100+ row tables) | Smooth scroll at any data size |
| **Stale-while-revalidate** | Show cached data immediately, fetch fresh in background | No loading state for repeat visits |
| **Chunked responses** | Stream table data, render rows as they arrive | Progressive content appearance |

### Response Time Thresholds

| Duration | User Perception | Required UX |
|----------|----------------|-------------|
| < 100ms | Instant | No feedback needed |
| 100-300ms | Slight delay | Subtle cursor change or button state |
| 300ms-1s | Noticeable | Spinner or skeleton |
| 1-5s | Slow | Skeleton + progress indication |
| 5-10s | Very slow | Progress bar with estimate |
| > 10s | Unacceptable for interactive | Background task + notification on complete |

---

## 12. Common Mistakes (Anti-Patterns)

| Anti-Pattern | Problem | Fix |
|--------------|---------|-----|
| **Information overload** | Everything looks equally important | Max 5-6 cards in view. Clear hierarchy. Progressive disclosure. |
| **Color-only status** | Colorblind users lose information | Always pair color with icon + text label. |
| **Generic empty states** | "No data" without guidance | Contextual message + actionable CTA per scenario. |
| **Hide-and-hover actions** | Users must mouse-explore to find actions | Make row actions always visible (2-3 max, overflow to menu). |
| **Spinner for everything** | User anxiety, no progress sense | Skeleton screens for content load. Progress bars for long tasks. |
| **Wrong chart type** | Pie chart with 12 slices, 3D bar charts | Follow chart selection guide. Max 5 slices for pie. No 3D ever. |
| **No data context** | Numbers without comparison/target | Always show vs. target, vs. previous period, or trend direction. |
| **Inconsistent visual language** | Mixed chart styles, varying card sizes | One design system. Token-based consistency. |
| **One-size-fits-all dashboard** | Different roles see same view | Role-based views or customizable widget layout. |
| **Ignoring F-pattern** | Critical data in wrong position | Most important KPIs in top-left quadrant. |
| **Excessive whitespace** | Wasted screen, forces scrolling for key data | Balance density with breathability. Data dashboards need density. |
| **Trend-chasing** | Neumorphism, glassmorphism over clarity | Clarity beats aesthetics. Stripe is flat + subtle shadow, not trendy. |
| **Floating labels** | Accessibility issues, disappear on focus | Labels always above input field. |
| **Auto-dismissing error toasts** | User misses error message | Error toasts persist until dismissed. Only success auto-dismisses. |
| **No loading minimum** | Skeleton flashes for 50ms | Minimum 200ms display time for any loading state. |
| **Disabled without explanation** | Grayed button with no context | Tooltip on disabled elements explaining why. |

---

## 13. Responsive Breakpoints

| Breakpoint | Width | Layout Changes |
|------------|-------|---------------|
| **Mobile** | < 768px | Single column. Sidebar hidden (bottom tab or drawer). Cards stack. Tables become card lists or horizontal scroll. |
| **Tablet** | 768-1024px | Sidebar collapsed (icon-only). 2-column card grid. Tables may hide low-priority columns. |
| **Desktop** | 1024-1440px | Sidebar expanded. 3-4 column card grid. Full table display. |
| **Wide** | > 1440px | Content max-width 1440px, centered. Extra space becomes margin. |

### Mobile-Specific Rules

- Touch targets: minimum 44x44px.
- No hover-dependent interactions (no tooltips as primary info delivery).
- Bottom sheet for filters/actions instead of dropdowns.
- Swipe gestures for table row actions (optional, with visible fallback).
- Reduce chart complexity (fewer data points, simpler chart types).

---

## 14. Design Token Summary (Quick Reference)

```
/* Colors */
--color-bg-primary:    #ffffff;
--color-bg-secondary:  #f6f8fa;
--color-bg-tertiary:   #f0f2f5;
--color-text-primary:  #1a1a2e;
--color-text-secondary:#6b7280;
--color-text-tertiary: #9ca3af;
--color-border:        #e5e7eb;
--color-accent:        #0570de;
--color-success:       #30b566;
--color-warning:       #f5a623;
--color-danger:        #df1b41;

/* Typography */
--font-family:         'Inter', system-ui, sans-serif;
--font-size-xs:        11px;
--font-size-sm:        12px;
--font-size-base:      14px;
--font-size-md:        16px;
--font-size-lg:        18px;
--font-size-xl:        20px;
--font-size-2xl:       24px;
--font-size-3xl:       28px;
--font-size-4xl:       32px;

/* Spacing (8px grid) */
--space-0:    0px;
--space-0.5:  4px;
--space-1:    8px;
--space-1.5:  12px;
--space-2:    16px;
--space-3:    24px;
--space-4:    32px;
--space-6:    48px;
--space-8:    64px;

/* Shadows */
--shadow-sm:  0 1px 2px rgba(0,0,0,0.05);
--shadow-md:  0 4px 6px rgba(0,0,0,0.07);
--shadow-lg:  0 10px 15px rgba(0,0,0,0.1);

/* Border Radius */
--radius-sm:  4px;   /* buttons, inputs */
--radius-md:  8px;   /* cards */
--radius-lg:  12px;  /* modals, dialogs */
--radius-full: 9999px; /* pills, avatars */

/* Transitions */
--transition-fast:   150ms ease;
--transition-base:   200ms ease;
--transition-slow:   300ms ease;

/* Breakpoints */
--bp-mobile:  768px;
--bp-tablet:  1024px;
--bp-desktop: 1440px;

/* Z-Index Scale */
--z-dropdown:  1000;
--z-sticky:    1020;
--z-fixed:     1030;
--z-modal-bg:  1040;
--z-modal:     1050;
--z-popover:   1060;
--z-tooltip:   1070;
--z-toast:     1080;
```

---

## Sources

- [Stripe - Designing Accessible Color Systems](https://stripe.com/blog/accessible-color-systems)
- [Stripe Docs - Design Your App](https://docs.stripe.com/stripe-apps/design)
- [Stripe Docs - Style Your App](https://docs.stripe.com/stripe-apps/style)
- [Stripe Docs - Build a UI](https://docs.stripe.com/stripe-apps/build-ui)
- [Stripe Elements Appearance API](https://docs.stripe.com/elements/appearance-api)
- [Eleken - Make It Like Stripe](https://www.eleken.co/blog-posts/making-it-like-stripe)
- [Smashing Magazine - UX Strategies for Real-Time Dashboards](https://www.smashingmagazine.com/2025/09/ux-strategies-real-time-dashboards/)
- [UXPin - Dashboard Design Principles](https://www.uxpin.com/studio/blog/dashboard-design-principles/)
- [Pencil & Paper - Dashboard UX Patterns](https://www.pencilandpaper.io/articles/ux-pattern-analysis-data-dashboards)
- [NN/g - Skeleton Screens 101](https://www.nngroup.com/articles/skeleton-screens/)
- [Simon Hearne - Optimistic UI Patterns](https://simonhearne.com/2021/optimistic-ui-patterns/)
- [Carbon Design System - Button Usage](https://carbondesignsystem.com/components/button/usage/)
- [Carbon Design System - Empty States](https://carbondesignsystem.com/patterns/empty-states-pattern/)
- [PatternFly - Button Design Guidelines](https://www.patternfly.org/components/button/design-guidelines/)
- [Cieden - Spacing Best Practices (8pt Grid)](https://cieden.com/book/sub-atomic/spacing/spacing-best-practices)
- [DesignSystems.com - Space, Grids and Layouts](https://www.designsystems.com/space-grids-and-layouts/)
- [EightShapes - Buttons in Design Systems](https://medium.com/eightshapes-llc/buttons-in-design-systems-eac3acf7e23)
- [AlfDesignGroup - Sidebar Design for Web Apps](https://www.alfdesigngroup.com/post/improve-your-sidebar-design-for-web-apps)
- [UX Planet - Best UX Practices for Designing a Sidebar](https://uxplanet.org/best-ux-practices-for-designing-a-sidebar-9174ee0ecaa2)
- [EazyBI - Data Visualization Chart Types](https://eazybi.com/blog/data-visualization-and-chart-types)
- [Datawrapper - Chart Types Guide](https://www.datawrapper.de/blog/chart-types-guide)
- [Eleken - Empty State UX Examples](https://www.eleken.co/blog-posts/empty-state-ux)
- [Raw.Studio - Dashboard Design Disasters](https://raw.studio/blog/dashboard-design-disasters-6-ux-mistakes-you-cant-afford-to-make/)
- [Databox - Bad Dashboard Examples](https://databox.com/bad-dashboard-examples)
- [WebAIM - WCAG 2 Checklist](https://webaim.org/standards/wcag/checklist)
- [BrowserStack - WCAG Compliance Checklist](https://www.browserstack.com/guide/wcag-compliance-checklist)
- [DesignRush - Dashboard Design Principles](https://www.designrush.com/agency/ui-ux-design/dashboard/trends/dashboard-design-principles)
