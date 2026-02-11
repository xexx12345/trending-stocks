# Improvements & Feature Roadmap

Prioritized by expected impact on signal quality.

---

## Tier 1 — Highest Impact (Signal Quality)

### 1. Backtest Tracker — "Did Yesterday's Picks Work?"

Right now you get a list every morning and never close the loop. Add a `track_performance.py` that:

- Loads previous `trending_report.json` files (by date)
- Fetches next-day / next-week returns for each pick via yfinance
- Computes hit rate, avg return, and Sharpe by source and by combined score tier
- Outputs a `performance_history.json` and summary table

**Why it matters:** You have 12 sources with hand-tuned weights. Without backtesting, you're guessing which sources actually predict moves. This lets you tune weights empirically instead of by gut.

### 2. Earnings & Event Calendar Filter

A stock can score 90 and still gap down 20% on an earnings miss. Add an earnings-aware layer:

- Pull upcoming earnings dates from yfinance `.calendar` or a free API (earningswhispers RSS)
- Flag any pick reporting within 3 trading days
- Add an `earnings_flag` field: `reporting_soon`, `just_reported`, `clear`
- Optionally auto-demote `reporting_soon` tickers by a configurable penalty (e.g. -10 from combined score)
- Surface this prominently in the report and Gemini prompt

**Why it matters:** Earnings are the single biggest binary event for any stock. Ignoring them is a blind spot that can override every other signal.

### 3. Multi-Day Trend Tracking

One morning's scan is a snapshot. What you really want is: "This ticker has been rising in mentions AND score for 3 consecutive days." Add:

- A lightweight `history.db` (SQLite) or rolling JSON that stores daily scores per ticker
- New fields: `days_trending` (consecutive days in top 30), `score_delta` (today vs yesterday), `mention_trend` (rising/falling/new)
- Filter: tickers trending for 2-3 days = "confirmed momentum"; day-1 only = "early signal"

**Why it matters:** Distinguishes real trends from one-day noise. A stock that Reddit loved for one afternoon is different from one that's been building buzz for a week.

### 4. Source Independence Score

Several sources overlap significantly (momentum + finviz + bearish_momentum all read price data; reddit + news + perplexity all read sentiment). When 3 correlated sources agree, it's less meaningful than when 3 independent sources agree.

- Tag each source as `technical`, `sentiment`, or `fundamental`
- Compute a `signal_diversity` score: how many independent *categories* confirm the signal, not just how many raw sources
- Weight the multi-source bonus by diversity, not raw count

**Why it matters:** Prevents the illusion of confirmation from redundant signals.

---

## Tier 2 — High Impact (Missing Signals)

### 5. Macro Regime Detector

The market regime determines whether longs or shorts are the right playbook. Build a lightweight regime classifier from data you already download:

- SPY trend (from momentum baseline): bull/bear/chop
- VIX level (add ^VIX to baseline watchlist): low-vol / elevated / crisis
- TLT trend (already in baseline): risk-on vs flight-to-safety
- Breadth: % of baseline watchlist above MA50

Output a `market_regime` field: `risk_on`, `cautious`, `risk_off`, `crisis`. Use it to:
- Auto-adjust long vs short emphasis
- Add regime context to the Gemini prompt
- Filter: in `risk_off`, demote speculative longs; in `risk_on`, demote shorts

**Why it matters:** Stock-picking in a bear market is swimming upstream. Regime awareness prevents fighting the tape.

### 6. Dark Pool / Block Trade Signals

Large institutional trades often route through dark pools before showing up in price. Add:

- FINRA ADF short volume data (free, daily CSV from `shortsqueeze.com` or FINRA's own files)
- Compute dark pool short volume ratio per ticker
- Significant deviation from 30-day average = signal

**Why it matters:** Dark pool activity is one of the few leading indicators of institutional intent that retail can access for free.

### 7. Economic Calendar Awareness

Like earnings but for macro events. Fed meetings, CPI, NFP, and GDP releases move the entire market.

- Scrape the economic calendar from `tradingeconomics.com` or `investing.com` RSS
- Flag days with high-impact events
- Add to report header and Gemini prompt: "Today is Fed day — expect volatility after 2pm ET"

**Why it matters:** Macro events can override all stock-level signals. Being aware prevents getting blindsided.

### 8. Relative Strength Ranking (IBD-Style)

You already compute `relative_strength` vs SPY. Extend it:

- Rank all discovered tickers by RS percentile (1-99)
- Track RS ranking over time (is it improving or deteriorating?)
- IBD-style composite: 40% 3-month, 20% 6-month, 20% 9-month, 20% 12-month (use yfinance 1y data)
- Surface RS percentile prominently in output

**Why it matters:** Relative strength is one of the most empirically validated factors in equity returns. Your current implementation is basic — this would make it rigorous.

---

## Tier 3 — Medium Impact (Execution & UX)

### 9. Pre-Market Gap Scanner

Run a lightweight 6:30 AM scan that only checks pre-market movers:

- Use yfinance pre-market data or Finviz pre-market screener
- Cross-reference against yesterday's picks: "NVDA was #3 yesterday, gapping up 2% pre-market — thesis confirming"
- Flag unexpected gaps on positions you might hold

**Why it matters:** Pre-market action often determines the day's direction. Running the full pipeline at 6 AM misses this.

### 10. Implement the Caching Layer

`config.yaml` defines `cache.enabled: true` and `cache.ttl_minutes: 60` but there's no caching code. Add:

- Simple file-based or SQLite cache keyed by `(scanner_name, date, params_hash)`
- Honor TTL from config
- Skip API calls when cache is fresh
- `--no-cache` CLI flag to force refresh

**Why it matters:** Lets you re-run the pipeline (e.g. after tweaking weights) without hammering APIs and waiting 5+ minutes. Also enables intraday re-scans.

### 11. Parallel Scanner Execution

Scanners are currently sequential. Many are independent (reddit, news, finviz, google_trends, perplexity). Use `concurrent.futures.ThreadPoolExecutor`:

- Group Phase 1 scanners into parallel batches (respect rate limits with per-domain semaphores)
- Phase 3 enrichment can also parallelize (momentum is one batch download, but short_interest and options are per-ticker)

**Why it matters:** Pipeline currently takes 3-5 minutes. Parallelization could cut it to under 2.

### 12. Conviction Tiers Instead of Raw Scores

Raw scores (0-100) are hard to act on. Add human-readable tiers:

| Tier | Criteria | Action |
|------|----------|--------|
| **Strong Buy** | Score > 80, 5+ sources, no too_late flags, trend_quality = strong_early | Full position |
| **Buy** | Score > 70, 3+ sources | Half position |
| **Watch** | Score > 60, rising mentions | Add to watchlist, wait for pullback |
| **Fade** | Score < 50 with deteriorating RS | Avoid or short |

Surface these tiers in the terminal report and JSON output.

### 13. Alert System

After the main scan, check for high-conviction triggers and send a notification:

- New ticker entering top 5 that wasn't there yesterday
- Existing pick with score increasing 10+ points day-over-day
- Insider cluster buy on a ticker already in top 20
- Short squeeze risk on a rising ticker

Delivery: simple macOS notification (`osascript`), or write to a `alerts.json` that a separate watcher could pick up.

---

## Tier 4 — Nice to Have

### 14. Web Dashboard

Generate a static HTML dashboard (no server needed) alongside the JSON:

- Sortable table of all picks with sparkline charts
- Score heatmap by source (which sources agree/disagree)
- Historical score chart per ticker (requires Tier 1 #3)
- Sector rotation map
- Already have the Gemini HTML report — this would be a data-focused complement

### 15. Sector Rotation Model

Go beyond raw ETF flows. Implement a simple rotation model:

- Track sector ETF relative strength over 1w/1m/3m
- Detect rotation patterns: early-cycle (tech→industrials), late-cycle (staples→utilities)
- Output: "Rotation favoring: [sectors]. Fading: [sectors]."
- Use this to boost/penalize tickers in rotating sectors

### 16. Options Flow Quality Filter

Current options scanner just checks volume/OI ratio and put/call ratio. Improve with:

- Filter for near-term expiry only (next 2 weeks) — these are more directional
- Weight by dollar value of premium, not just contract count
- Detect repeat unusual activity (same strike/expiry hit multiple days)

### 17. Smarter Ticker Extraction

The current regex + blacklist approach misses context. Improvements:

- Use the Perplexity/Gemini output to validate extracted tickers (cross-reference)
- Add company name → ticker reverse lookup to news scanner (partially exists but only 150 companies)
- Consider a lightweight NER model for more accurate extraction from Reddit posts

---

## Quick Wins (< 1 hour each)

- [ ] Add `^VIX` to the baseline watchlist in `momentum.py` — free macro signal
- [ ] Add `HYG` (high yield bonds) to baseline — credit stress indicator
- [ ] Surface `trend_quality` more prominently in terminal output (currently buried)
- [ ] Add `--longs-only` and `--shorts-only` CLI flags to skip irrelevant phases
- [ ] Fix the `cache` config — either implement it or remove the dead config to avoid confusion
- [ ] Add retry logic with exponential backoff to HTTP-dependent scanners (finviz, insider, congress)
- [ ] Save a `daily_digest.txt` one-pager alongside the JSON for quick mobile reading
