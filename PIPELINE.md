# Pipeline Architecture

## Flow

```
PHASE 1 - DISCOVER          PHASE 2 - COLLECT     PHASE 3 - ENRICH         PHASE 4 - SCORE
┌──────────┐                 ┌──────────┐          ┌──────────┐             ┌──────────┐
│ Reddit   │──┐              │          │          │          │             │          │
│ News     │──┤              │          │          │ Momentum │──┐          │          │
│ Finviz   │──┼─────────────>│ Union    │─────────>│          │  ├─────────>│ Combined │
│ Themes   │──┤              │ all      │          │ Short    │──┘          │ Score    │
│ G.Trends │──┘              │ tickers  │          │ Interest │             │ (6 srcs) │
└──────────┘                 └──────────┘          └──────────┘             └──────────┘
```

**Key inversion**: Momentum runs LAST on discovered tickers, not first on a hardcoded list.

## Phase Details

### Phase 1 — Discover

| Source | What it does | Ticker extraction |
|--------|-------------|-------------------|
| **Themes** | Scans thematic ETF momentum (semis, gold, energy, etc.) | Returns tickers from hot theme definitions |
| **Reddit** | Scans subreddits for $TICKER and standalone mentions | Blacklist-filtered (no whitelist) |
| **News** | RSS feeds + yfinance news + web scraping | Blacklist-filtered + company name enrichment |
| **Finviz** | Top gainers, losers, unusual volume, new highs, oversold/overbought, industry movers | Direct from screener pages |
| **Google Trends** | Searches for stock-related queries, extracts trending tickers | Ticker extraction from query text |

### Phase 2 — Collect

Union of all tickers from Phase 1. The `BASELINE_WATCHLIST` (~40 ETFs/proxies for market context) is merged inside the momentum scanner.

### Phase 3 — Enrich

Two enrichment passes:

1. **Momentum scanner** runs on the full discovered pool + baseline watchlist. Batched in groups of 200 for yfinance. Computes price change, volume ratio, RSI, MA crossovers.

2. **Short interest scanner** runs on all discovered tickers. Fetches short float % and days-to-cover from FinViz to identify squeeze candidates.

### Phase 4 — Score

All 6 sources combined with weighted scoring + bonuses.

## Scoring

### Source Weights

| Source | Weight | What it measures |
|--------|--------|-----------------|
| Momentum | 0.30 | Price action, volume, RSI, MAs |
| Finviz | 0.20 | Signal strength (gainers, new highs, unusual volume, etc.) |
| Reddit | 0.15 | Mention count + sentiment |
| News | 0.15 | Article count + sentiment |
| Google Trends | 0.10 | Retail search interest spikes |
| Short Interest | 0.10 | Squeeze setup potential |

### Bonuses

- **Theme bonus**: +5 points for stocks in hot themes
- **Multi-source bonus**: +3 points per additional source beyond 1

### Finviz Signal Weights

| Signal | Base Score |
|--------|-----------|
| Top gainers | 80 |
| New highs | 75 |
| Industry movers | 65 |
| Unusual volume | 60 |
| Overbought | 55 |
| Oversold | 40 |
| Top losers | 20 |

Multi-signal bonus: +5 per additional signal type (capped at +15).

### Google Trends Scoring

| Factor | Points |
|--------|--------|
| Base score | Average of max and avg trend value (0-100) |
| Breakout bonus | +20 for 300%+ surge queries |
| Multi-mention bonus | +5 per additional mention (capped at +15) |

Detects retail interest spikes before they hit mainstream news. "Breakout" queries (300%+ increase) indicate explosive interest.

### Short Interest Scoring

| Factor | Points |
|--------|--------|
| Short Float % | short_float × 2 (e.g., 15% = 30 pts) |
| Days-to-cover >5 | +10 |
| Days-to-cover >10 | +20 |
| Cap | 100 max |

**Squeeze Risk Levels:**
- **High**: >20% short float OR >10 days to cover
- **Medium**: >10% short float OR >5 days to cover
- **Low**: Everything else

High short interest + high days-to-cover = potential squeeze setup.

## Ticker Filtering

### Blacklist (not whitelist)

The old approach used hardcoded whitelists (~200 tickers). The new approach uses a shared blacklist (`utils/ticker_blacklist.py`) that blocks common English words, finance jargon, Reddit-isms, and trading verbs.

**Two-tier filtering:**
- `$TICKER` patterns (high confidence): only blocked by `TICKER_BLACKLIST`
- Standalone `TICKER` (lower confidence): also blocked if 1-2 letters unless in `ALLOW_SHORT_TICKERS`

**Tickers that are also words** (GOLD, LOW, ALL, NOW): blacklisted for standalone — caught via `$` prefix or company-name matching instead.

## Files

| File | Role |
|------|------|
| `main.py` | 6-phase pipeline orchestrator |
| `scanners/themes.py` | Thematic ETF momentum |
| `scanners/reddit.py` | Reddit mention scanning |
| `scanners/news.py` | News/RSS scanning |
| `scanners/finviz.py` | Finviz screener scraping + scoring |
| `scanners/google_trends.py` | Google Trends retail interest detection |
| `scanners/short_interest.py` | Short interest / squeeze detection |
| `scanners/momentum.py` | yfinance momentum analysis |
| `utils/scoring.py` | 6-source score aggregation |
| `utils/ticker_blacklist.py` | Shared blacklist filtering |
| `config.yaml` | Weights and source config |

## Performance

| Scanner | Est. Time | Notes |
|---------|-----------|-------|
| Themes | ~5s | ETF batch download |
| Reddit | ~10-15s | API rate limited |
| News | ~10-15s | RSS + yfinance |
| Finviz | ~15-20s | Multiple screener pages |
| Google Trends | ~15-20s | 4-5 keywords × 2s delay |
| Momentum | ~30-60s | Depends on discovered ticker count |
| Short Interest | ~25-40s | 0.5s per ticker |
| **Total** | ~2-2.5min | Full pipeline |

## Ideas / Future Work

- Add earnings calendar as a discovery source
- Weight decay: reduce score for tickers only seen once in 7 days
- Caching layer to avoid re-downloading yfinance data within same session
- SEC filing scanner (13F, insider buys)
- Options flow / unusual options activity
