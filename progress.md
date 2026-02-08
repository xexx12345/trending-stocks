# Livermore Trend Quality Implementation Progress

## Goal
Enhance the momentum scanner to capture Jesse Livermore's principle: "buy stocks going up, sell stocks going down" — with emphasis on **not being too late**.

## What Changed
Files: `scanners/momentum.py`, `main.py`

### New Signals Added

| Signal | What It Measures | Points | Status |
|--------|-----------------|--------|--------|
| Trend acceleration | 5d return vs prior 5d return | +/- 8 | DONE |
| Relative strength vs SPY | Stock 1m return minus SPY 1m return | +/- 7 | DONE |
| Volume-direction alignment | Avg volume on up days vs down days | +/- 7 | DONE |
| Breakout detection | Price at 20-day high on >1.5x volume | +8 | DONE |
| Too-late: RSI extreme | RSI > 80 penalty | -4 | DONE |
| Too-late: Extended above MA | Price >12% above MA20 | -4 | DONE |
| Too-late: Consecutive up days | 7+ consecutive up days | -4 | DONE |

### Revised Scoring Budget (base 50, range 0-100)

| Component | Old Points | New Points |
|-----------|-----------|------------|
| Base | 50 | 50 |
| 1m price change | +/- 25 | +/- 20 |
| Volume spike (today) | +15 | +5 |
| RSI | +/- 10 | +/- 8 |
| MA position | +10 | +5 |
| **Trend acceleration** | — | +/- 8 |
| **Relative strength** | — | +/- 7 |
| **Volume alignment** | — | +/- 7 |
| **Breakout** | — | +8 |
| **Too-late penalties** | — | -12 max |

### New Output Fields

| Field | Type | Description |
|-------|------|-------------|
| `acceleration` | float | Recent 5d return minus prior 5d return. Positive = accelerating. |
| `relative_strength` | float | Stock 1m return minus SPY 1m return. Positive = outperforming. |
| `vol_direction_ratio` | float | Avg up-day volume / avg down-day volume. >1 = accumulation. |
| `is_breakout` | bool | Price at 20-day high on >1.5x volume. |
| `consecutive_up_days` | int | Count of consecutive up days at end of period. |
| `pct_above_ma20` | float | How far price is above 20-day MA (%). |
| `too_late_flags` | list | Any of: `rsi_extreme`, `extended_above_ma`, `consecutive_up_days`. |
| `trend_quality` | str | Classification: `strong_early`, `confirmed`, `emerging`, `extended`, `weak`, `bearish`. |

### Trend Quality Classification

| Label | Meaning | Livermore Interpretation |
|-------|---------|------------------------|
| `strong_early` | Score ≥75, accelerating, outperforming market | Ideal entry — leader emerging |
| `confirmed` | Score ≥65, no too-late flags | Good trend, still timely |
| `emerging` | Score ≥55 | Building momentum, watch for confirmation |
| `extended` | Has too-late flags | Probably too late — the move is mature |
| `weak` | Score 40-55 | Not trending meaningfully |
| `bearish` | Score <40 | Going down — sell/avoid (Livermore's other rule) |

### Implementation Steps

- [x] Create progress.md
- [x] Enhance `calculate_momentum_score()` with new signals
- [x] Add `spy_change_1m` parameter, restructure scoring
- [x] Update `scan_momentum()` to extract SPY data and pass through
- [x] Add new fields to output dict
- [x] Enhance `main.py` print_report to show trend quality
- [x] Add new Livermore fields to `top_momentum` in save_json
- [x] Test standalone: `python3 scanners/momentum.py`
- [x] Verify bearish_momentum.py still works (reads same fields)
- [x] Verify scoring.py uses `mom.get('score', 50)` — no changes needed
- [x] Verify save_raw_data saves full momentum dicts — new fields auto-included
- [x] Update progress.md with results

## Test Results (2026-02-07, BASELINE_WATCHLIST only)

**SPY benchmark:** +1.41% (1m)

**Score distribution:** 0-20: 0 | 20-40: 5 | 40-60: 7 | 60-80: 8 | 80-100: 16

**Top 5:**
| Ticker | Score | Quality | 1M | Accel | RelStr | VolDir | Flags |
|--------|-------|---------|-----|-------|--------|--------|-------|
| XLI | 100.0 | strong_early | +13.4% | +3.9 | +12.0 | 1.16 | — |
| XLP | 100.0 | strong_early | +13.7% | +4.6 | +12.3 | 1.27 | rsi_extreme, BRK |
| XLB | 98.0 | strong_early | +19.3% | +6.0 | +17.9 | 1.21 | — |
| GLD | 94.0 | strong_early | +17.6% | +5.2 | +16.2 | 0.82 | — |
| EEM | 92.6 | strong_early | +11.7% | +1.6 | +10.3 | 0.94 | — |

**Bottom 5 (correctly bearish):**
| Ticker | Score | Quality | 1M | Accel | RelStr | VolDir |
|--------|-------|---------|-----|-------|--------|--------|
| KWEB | 35.3 | bearish | -1.8% | -1.6 | -3.2 | 1.12 |
| VXX | 34.6 | bearish | -11.6% | -3.2 | -13.0 | 1.32 |
| QQQ | 34.5 | bearish | -2.3% | -1.8 | -3.8 | 0.82 |
| XLK | 34.2 | bearish | -4.5% | -1.1 | -5.9 | 0.74 |
| ARKK | 23.0 | bearish | -14.7% | +1.3 | -16.1 | 1.07 |

**Key observations:**
- XLK has vol_direction_ratio 0.74 = distribution (more volume on down days) — correctly flagged bearish
- XLP is both breakout AND rsi_extreme — shows breakout but warns it's extended
- Gold miners (GDX/GDXJ) show strong_early but low vol_direction (<0.8) — some caution signal baked in
- ARKK is worst at 23.0 — massive underperformance vs market, correctly identified

## Files Modified
- `scanners/momentum.py` — Livermore-style trend quality signals
- `main.py` — Enhanced print_report + Livermore fields in save_json + all-tickers CSV + uncapped JSON
- `PIPELINE.md` — Documented new output files
- `progress.md` — this file

## "Don't Miss Any Ticker" Changes

### Problem
The old pipeline truncated everything to top 10/20. If 150 tickers were discovered but only 20 made the JSON, you'd miss tickers being hyped across multiple sources.

### Solution: Three outputs, nothing hidden

1. **`output/all_tickers.csv`** (NEW) — Every discovered ticker in one flat spreadsheet.
   - One row per ticker, columns for every source score + Livermore signals
   - Open in Google Sheets / Excel, sort by `num_sources` or `trend_quality`
   - Key columns: `ticker`, `combined_score`, `num_sources`, `sources`, `trend_quality`, `acceleration`, `relative_strength`, `is_breakout`, `too_late_flags`

2. **`output/trending_report.json`** — Now **untruncated**. Previously capped at `[:20]` for combined, `[:10]` for each source. Now includes ALL tickers, ALL sources.

3. **Terminal "ALL DISCOVERED TICKERS"** section — Grouped by source count (descending). Multi-source tickers shown first. Shows trend_quality, breakout flags, too-late warnings.

### CSV Column Reference

| Column | What to sort/filter by |
|--------|----------------------|
| `num_sources` | How many pipelines flagged this ticker (more = higher conviction) |
| `trend_quality` | Filter for `strong_early` = Livermore ideal entries |
| `combined_score` | Overall weighted ranking |
| `acceleration` | Positive = trend speeding up (early) |
| `relative_strength` | Positive = outperforming SPY |
| `is_breakout` | TRUE = 20-day high on volume |
| `too_late_flags` | Non-empty = probably extended |

## Downstream Impact
- `utils/scoring.py` — **No changes needed.** Uses `mom.get('score', 50)` — still works.
- `scanners/bearish_momentum.py` — **No changes needed.** Reads `change_1d/5d/1m`, `rsi`, `volume_ratio`, `above_ma20/ma50` — all still present.
- `config.yaml` — **No changes needed.** Momentum weight still 0.20.
- `save_raw_data()` — **Auto-includes new fields.** Saves full momentum dicts.
- Gemini analysis — **Auto-benefits.** Reads raw momentum.json which now has trend_quality, acceleration, relative_strength, etc.
- Zero extra API calls.
