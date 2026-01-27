# Pipeline Architecture

## Flow

```
PHASE 1 - DISCOVER          PHASE 2 - COLLECT     PHASE 3 - ENRICH       PHASE 4 - SCORE
┌──────────┐                 ┌──────────┐          ┌──────────┐           ┌──────────┐
│ Reddit   │──┐              │          │          │          │           │          │
│ News     │──┼─────────────>│ Union    │─────────>│ Momentum │──────────>│ Combined │
│ Finviz   │──┤              │ all      │          │ (yfinance│           │ Score    │
│ Themes   │──┘              │ tickers  │          │  batch)  │           │ (4 srcs) │
│          │                 │ + base   │          │          │           │          │
└──────────┘                 └──────────┘          └──────────┘           └──────────┘
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

### Phase 2 — Collect

Union of all tickers from Phase 1. The `BASELINE_WATCHLIST` (~40 ETFs/proxies for market context) is merged inside the momentum scanner.

### Phase 3 — Enrich

Momentum scanner runs on the full discovered pool + baseline watchlist. Batched in groups of 200 for yfinance. Computes price change, volume ratio, RSI, MA crossovers.

### Phase 4 — Score

All 4 sources combined with weighted scoring + bonuses.

## Scoring

### Source Weights

| Source | Weight | What it measures |
|--------|--------|-----------------|
| Momentum | 0.35 | Price action, volume, RSI, MAs |
| Finviz | 0.25 | Signal strength (gainers, new highs, unusual volume, etc.) |
| Reddit | 0.20 | Mention count + sentiment |
| News | 0.20 | Article count + sentiment |

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
| `main.py` | 4-phase pipeline orchestrator |
| `scanners/themes.py` | Thematic ETF momentum |
| `scanners/reddit.py` | Reddit mention scanning |
| `scanners/news.py` | News/RSS scanning |
| `scanners/finviz.py` | Finviz screener scraping + scoring |
| `scanners/momentum.py` | yfinance momentum analysis |
| `utils/scoring.py` | 4-source score aggregation |
| `utils/ticker_blacklist.py` | Shared blacklist filtering |
| `config.yaml` | Weights and source config |

## Ideas / Future Work

- Add earnings calendar as a discovery source
- Weight decay: reduce score for tickers only seen once in 7 days
- Caching layer to avoid re-downloading yfinance data within same session
- SEC filing scanner (13F, insider buys)
- Options flow / unusual options activity
