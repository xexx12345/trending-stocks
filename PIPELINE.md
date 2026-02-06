# Pipeline Architecture

## Flow

```
PHASE 1 — DISCOVER        PHASE 2 — COLLECT     PHASE 3 — ENRICH            PHASE 4 — SCORE LONGS     PHASE 5 — SCORE SHORTS
┌──────────────┐           ┌──────────┐          ┌────────────────┐           ┌──────────────┐          ┌──────────────────┐
│ Reddit       │──┐        │          │          │ Momentum       │──┐        │              │          │                  │
│ News         │──┤        │          │          │ Short Interest │──┤        │  aggregate   │          │ Bearish Momentum │
│ Finviz       │──┤        │  Union   │          │ Options Flow   │──┼───────>│  _scores()   │          │ (reuse Phase 3)  │
│ Themes       │──┤        │  all     │─────────>│ ETF Flows      │──┘        │  12 sources  │          │                  │
│ G.Trends     │──┼───────>│  tickers │          └────────────────┘           │  weighted    │          │ Fundamentals     │
│ Perplexity   │──┤        │          │                                       └──────────────┘          │ (yfinance .info) │
│ Insider      │──┤        └──────────┘                                              │                  │                  │
│ Analyst      │──┤                                                                  │                  │ + 7 existing     │
│ Congress     │──┤                                                                  ▼                  │   source scores  │
│ Institutional│──┘                                                          trending_report.json       │   (inverted)     │
└──────────────┘                                                                     │                  └──────────────────┘
                                                                                     │                          │
                                                                                     ▼                          ▼
                                                                             ┌──────────────────────────────────────────┐
                                                                             │        analyze_with_gemini.sh            │
                                                                             │  Reads all raw data → Gemini CLI         │
                                                                             │  Outputs: analysis_YYYY-MM-DD.html/json  │
                                                                             │                                          │
                                                                             │  Sections: Long Deep Dives, Short Deep   │
                                                                             │  Dives, Pair Trades, Hidden Gems,        │
                                                                             │  Squeeze Watch, Breakout Watch,          │
                                                                             │  Macro Context, Trading Plan             │
                                                                             └──────────────────────────────────────────┘
```

## Running

```bash
# One command — scanner + Gemini analysis
./run_full_analysis.sh

# Options
./run_full_analysis.sh --top 20           # Top 20 results
./run_full_analysis.sh --skip-gemini      # Scanner only, no AI analysis
./run_full_analysis.sh --no-raw           # Don't save raw data files

# Or run steps individually
python3 main.py                           # Step 1: fetch data + score
./analyze_with_gemini.sh                  # Step 2: AI analysis on latest data
```

## Phase Details

### Phase 1 — Discover (10 sources)

| Source | Scanner | What it does | Ticker extraction |
|--------|---------|-------------|-------------------|
| Themes | `scanners/themes.py` | Scans thematic ETF momentum (semis, gold, energy, etc.) | Tickers from hot theme definitions |
| Reddit | `scanners/reddit.py` | Scans 8 subreddits for $TICKER mentions | Blacklist-filtered |
| News | `scanners/news.py` | RSS feeds + yfinance news + web scraping | Blacklist-filtered + company name enrichment |
| Finviz | `scanners/finviz.py` | Gainers, losers, unusual volume, new highs, oversold/overbought | Direct from screener pages |
| Google Trends | `scanners/google_trends.py` | Stock-related query spikes | Ticker extraction from query text |
| Perplexity | `scanners/perplexity_news.py` | AI-powered news discovery | Tickers with catalysts/sentiment |
| Insider Trading | `scanners/insider_trading.py` | SEC Form 4 filings (buys/sells) | Tickers with insider buys |
| Analyst Ratings | `scanners/analyst_ratings.py` | Wall Street upgrades/downgrades | Tickers with score > 60 |
| Congress Trading | `scanners/congress_trading.py` | STOCK Act politician trades | Tickers with congress_buying signal |
| Institutional | `scanners/institutional_holdings.py` | 13F hedge fund positions | Tickers with institutional_accumulation |

### Phase 2 — Collect

Union of all tickers from Phase 1. The `BASELINE_WATCHLIST` (~40 ETFs/proxies) is merged inside the momentum scanner for market context.

### Phase 3 — Enrich (4 passes)

| Pass | Scanner | What it does |
|------|---------|-------------|
| 3a | Momentum | Price change, volume ratio, RSI, MA crossovers on full pool. Batched 200/call. |
| 3b | Short Interest | Short float %, days-to-cover from FinViz. Squeeze risk classification. |
| 3c | Options Activity | Unusual options flow via yfinance. Put/call ratio, volume/OI, bullish/bearish sweeps. |
| 3d | ETF Flows | Sector rotation signals from ETF price/volume. Contributes via bonus, not direct weight. |

### Phase 4 — Score Longs

`aggregate_scores()` in `utils/scoring.py` — combines 12 sources with weighted scoring.

| Source | Weight | What it measures |
|--------|--------|-----------------|
| Momentum | 0.20 | Price action, volume, RSI, MAs |
| Finviz | 0.12 | Signal strength (gainers, new highs, unusual volume) |
| Reddit | 0.10 | Mention count + sentiment |
| News | 0.10 | Article count + sentiment |
| Options Activity | 0.08 | Unusual flow, bullish/bearish sweeps |
| Google Trends | 0.06 | Retail search interest spikes |
| Short Interest | 0.06 | Squeeze setup potential |
| Perplexity | 0.06 | AI-discovered catalysts |
| Analyst Ratings | 0.06 | Upgrades/downgrades |
| Institutional | 0.06 | 13F accumulation/distribution |
| Insider Trading | 0.05 | Form 4 buys/sells |
| Congress Trading | 0.05 | Politician trades |

**Bonuses:**
- Theme bonus: +5 pts for stocks in hot themes
- Multi-source bonus: +3 pts per additional source beyond 1
- ETF flow bonus: +5% of sector flow score

### Phase 5 — Score Shorts

`aggregate_short_scores()` in `utils/scoring.py` — separate function with inverted signal interpretation.

**New scanners (no extra API calls for bearish_momentum):**

| Scanner | File | What it does |
|---------|------|-------------|
| Bearish Momentum | `scanners/bearish_momentum.py` | Reuses Phase 3 momentum data. Scores: negative price change, overbought RSI, below MAs, death cross proxy, high volume on down days. |
| Fundamentals | `scanners/fundamentals.py` | yfinance `.info` calls. Scores: P/E expansion, high P/S, high debt/equity, negative earnings growth, revenue deceleration. |

**Short source weights (9 sources):**

| Source | Weight | Bearish signal |
|--------|--------|---------------|
| Bearish Momentum | 0.25 | Technical breakdown score |
| Fundamentals | 0.15 | Valuation/earnings stress |
| Analyst Downgrades | 0.12 | `action == 'downgrade'` or `'pt_lower'` |
| Bearish Options | 0.12 | `signal == 'bearish_sweep'`, high put/call |
| Insider Selling | 0.10 | `is_buy == False` (cluster sells) |
| Institutional Dist. | 0.08 | `signal == 'institutional_distribution'` |
| Finviz Bearish | 0.08 | top_losers, overbought signals |
| Congress Selling | 0.05 | `signal == 'congress_selling'` |
| Negative News | 0.05 | `sentiment == 'negative'` |

**Short-specific adjustments:**
- Multi-source bonus: +4 pts per bearish source beyond 1
- Squeeze penalty: -15 pts for stocks with >20% short float (crowded trade risk)
- Min score threshold: 40 (configurable in `config.yaml`)

## Gemini AI Analysis

`analyze_with_gemini.sh` reads all raw data from the latest `output/raw/` folder and sends it to Gemini in a single prompt. Produces a unified HTML + JSON report.

**Sections generated:**

| Section | Description |
|---------|-------------|
| Executive Summary | Market regime, bias, confidence, dominant themes |
| Macro Context | VIX, yields, dollar, credit, breadth (from existing data) |
| Sector Analysis | Leading/lagging sectors, rotation signals |
| Long Deep Dives (6) | Full bullish thesis with probability, entry/exit, if-wrong plan |
| Short Deep Dives (4) | Bearish thesis with squeeze risk, cover levels, instrument recommendation |
| Pair Trades (2-3) | Long/short combos from same sector for market-neutral exposure |
| Hidden Gems (4-5) | Under-the-radar small/mid caps not in top 10 |
| Squeeze Watch (3) | High short interest + positive momentum = squeeze candidates |
| Breakout Watch (3-5) | Technical patterns near breakout levels |
| Avoid List (3-5) | Stocks that look risky despite showing up in data |
| Market Risks | Key risks with severity and hedge suggestions |
| Trading Plan | Pre-market focus, key levels, best setups, risk limits |

## Files

| File | Role |
|------|------|
| `main.py` | 5-phase pipeline orchestrator |
| `run_full_analysis.sh` | One-command entry point (scanner + Gemini) |
| `analyze_with_gemini.sh` | Unified Gemini AI analysis (longs + shorts + pairs) |
| `config.yaml` | Weights for long + short pipelines, source config |
| **Scanners** | |
| `scanners/themes.py` | Thematic ETF momentum |
| `scanners/reddit.py` | Reddit mention scanning |
| `scanners/news.py` | News/RSS scanning |
| `scanners/finviz.py` | Finviz screener scraping + scoring |
| `scanners/google_trends.py` | Google Trends retail interest |
| `scanners/short_interest.py` | Short interest / squeeze detection |
| `scanners/momentum.py` | yfinance momentum analysis |
| `scanners/options_activity.py` | Unusual options flow |
| `scanners/perplexity_news.py` | AI-powered news discovery |
| `scanners/insider_trading.py` | SEC Form 4 filings |
| `scanners/analyst_ratings.py` | Upgrades/downgrades |
| `scanners/congress_trading.py` | STOCK Act politician trades |
| `scanners/etf_flows.py` | ETF sector rotation signals |
| `scanners/institutional_holdings.py` | 13F hedge fund positions |
| `scanners/bearish_momentum.py` | Technical breakdown signals (reuses momentum data) |
| `scanners/fundamentals.py` | Valuation stress via yfinance .info |
| **Utils** | |
| `utils/scoring.py` | `aggregate_scores()` (longs) + `aggregate_short_scores()` (shorts) |
| `utils/ticker_blacklist.py` | Shared blacklist filtering |

## Output

| Path | Description |
|------|-------------|
| `output/trending_report.json` | Combined scanner data (longs + shorts) |
| `output/raw/YYYY-MM-DD_HHMMSS/` | Individual scanner JSON files |
| `output/analysis_YYYY-MM-DD.html` | Gemini AI report (opens in browser) |
| `output/analysis_YYYY-MM-DD.json` | Gemini structured JSON output |

## Performance

| Scanner | Est. Time | Notes |
|---------|-----------|-------|
| Themes | ~5s | ETF batch download |
| Reddit | ~10-15s | API rate limited |
| News | ~10-15s | RSS + yfinance |
| Finviz | ~15-20s | Multiple screener pages |
| Google Trends | ~15-20s | 4-5 keywords x 2s delay |
| Perplexity | ~5-10s | Single API call |
| Insider/Analyst/Congress/Institutional | ~10-20s | FinViz + web scraping |
| Momentum | ~30-60s | Depends on discovered ticker count |
| Short Interest | ~25-40s | 0.5s per ticker |
| Options Activity | ~15-25s | yfinance per ticker |
| ETF Flows | ~5s | ETF batch download |
| Bearish Momentum | <1s | Reuses Phase 3 data, no API calls |
| Fundamentals | ~30-60s | yfinance .info per ticker |
| **Scanner Total** | ~3-5min | Full pipeline |
| Gemini Analysis | ~30-60s | Single API call |
| **Total** | ~4-6min | Scanner + Gemini |

## Ticker Filtering

### Blacklist (not whitelist)

Shared blacklist (`utils/ticker_blacklist.py`) blocks common English words, finance jargon, Reddit-isms, and trading verbs.

**Two-tier filtering:**
- `$TICKER` patterns (high confidence): only blocked by `TICKER_BLACKLIST`
- Standalone `TICKER` (lower confidence): also blocked if 1-2 letters unless in `ALLOW_SHORT_TICKERS`

## Ideas / Future Work

- Historical performance tracking (SQLite DB, P&L since recommendation)
- Correlation matrix between top picks
- Earnings calendar integration (yfinance earningsDate)
- Intraday re-scan mode (`--mode intraday`)
- Email/SMS delivery of morning report
- TradingView/thinkorswim watchlist export
- Weight decay: reduce score for tickers only seen once in 7 days
- Multi-day trend context for Gemini (load last 3-5 days of data)
