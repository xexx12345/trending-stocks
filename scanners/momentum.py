"""
Momentum Scanner - Identifies stocks with positive technical momentum
Uses yfinance for free market data
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

# Baseline instruments always scanned for market context.
# Individual stocks are discovered dynamically from other sources.
BASELINE_WATCHLIST = [
    # Broad market
    "SPY", "QQQ", "IWM", "DIA", "VTI",
    # All 11 sector ETFs
    "XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLI", "XLB", "XLRE", "XLU", "XLC",
    # Thematic ETFs
    "SMH", "SOXX", "GLD", "SLV", "GDX", "GDXJ", "XBI", "URA", "XME", "ARKK", "KWEB", "IBB",
    # Bond / vol / commodity proxies
    "TLT", "HYG", "USO", "UNG", "VXX",
    # International
    "EEM", "FXI", "EWZ",
]

# Max tickers per yfinance batch download
YFINANCE_BATCH_LIMIT = 200


def calculate_rsi(prices: pd.Series, period: int = 14) -> float:
    """Calculate RSI for a price series."""
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1] if not rsi.empty else 50.0


def calculate_momentum_score(data: pd.DataFrame,
                              spy_change_1m: float = 0.0) -> Dict:
    """
    Calculate momentum score using Livermore-style trend quality analysis.

    Measures not just "is it going up?" but "is the move early, confirmed,
    and outperforming?" Penalizes exhausted/too-late entries.

    Signals:
    - Core trend: 1m price change (direction and magnitude)
    - Trend acceleration: recent 5d vs prior 5d (catching early moves)
    - Relative strength: outperformance vs SPY (Livermore's "leaders")
    - Volume alignment: accumulation (high vol up days) vs distribution
    - Breakout: 20-day high on above-average volume
    - MA position: above key moving averages
    - RSI sweet spot: momentum without overextension
    - Too-late penalties: RSI >80, extended above MA, consecutive up days
    """
    if data.empty or len(data) < 20:
        return None

    close = data['Close']
    volume = data['Volume']
    price = float(close.iloc[-1])

    # ── Basic price changes ──────────────────────────────────────
    change_1d = ((close.iloc[-1] / close.iloc[-2]) - 1) * 100 if len(close) >= 2 else 0
    change_5d = ((close.iloc[-1] / close.iloc[-6]) - 1) * 100 if len(close) >= 6 else 0
    change_1m = ((close.iloc[-1] / close.iloc[0]) - 1) * 100 if len(close) >= 20 else 0

    # ── Volume basics ────────────────────────────────────────────
    avg_volume = volume.iloc[:-1].mean()
    volume_ratio = volume.iloc[-1] / avg_volume if avg_volume > 0 else 1.0

    # ── RSI ──────────────────────────────────────────────────────
    rsi = calculate_rsi(close)

    # ── Moving averages ──────────────────────────────────────────
    ma_20 = close.rolling(20).mean().iloc[-1]
    ma_50 = close.rolling(50).mean().iloc[-1] if len(close) >= 50 else ma_20
    above_ma20 = close.iloc[-1] > ma_20
    above_ma50 = close.iloc[-1] > ma_50
    pct_above_ma20 = ((close.iloc[-1] - ma_20) / ma_20) * 100 if ma_20 > 0 else 0

    # ── NEW: Trend acceleration ──────────────────────────────────
    # Compare recent 5-day return vs prior 5-day return.
    # Accelerating trend = early entry. Decelerating = late.
    if len(close) >= 11:
        recent_5d = ((close.iloc[-1] / close.iloc[-6]) - 1) * 100
        prior_5d = ((close.iloc[-6] / close.iloc[-11]) - 1) * 100
        acceleration = recent_5d - prior_5d
    else:
        recent_5d = change_5d
        prior_5d = 0
        acceleration = 0

    # ── NEW: Relative strength vs SPY ────────────────────────────
    # Livermore bought leaders — stocks outperforming the market.
    relative_strength = change_1m - spy_change_1m

    # ── NEW: Volume-direction alignment (accumulation/distribution) ──
    # High volume on up days + low volume on down days = smart money buying.
    # The reverse = distribution, trend is hollow.
    daily_returns = close.pct_change()
    up_days = daily_returns > 0
    down_days = daily_returns < 0

    if up_days.sum() > 0 and down_days.sum() > 0:
        avg_up_volume = float(volume[up_days].mean())
        avg_down_volume = float(volume[down_days].mean())
        # Ratio > 1 = accumulation, < 1 = distribution
        vol_direction_ratio = avg_up_volume / avg_down_volume if avg_down_volume > 0 else 1.0
    else:
        avg_up_volume = avg_down_volume = float(avg_volume)
        vol_direction_ratio = 1.0

    # ── NEW: Breakout detection ──────────────────────────────────
    # Price at/near 20-day high on above-average volume = Livermore breakout.
    high_20d = close.iloc[-20:].max() if len(close) >= 20 else close.max()
    is_breakout = (close.iloc[-1] >= high_20d * 0.99) and (volume_ratio > 1.5)

    # ── NEW: Consecutive up days (too-late signal) ───────────────
    consecutive_up = 0
    for i in range(len(daily_returns) - 1, 0, -1):
        if daily_returns.iloc[i] > 0:
            consecutive_up += 1
        else:
            break

    # ════════════════════════════════════════════════════════════════
    # SCORING — Livermore-style composite
    # ════════════════════════════════════════════════════════════════
    score = 50  # Base

    # Core trend: 1m price change (max +/- 20 pts)
    score += min(max(change_1m * 1.5, -20), 20)

    # Trend acceleration (max +/- 8 pts)
    if acceleration > 3:
        score += 8    # Strongly accelerating — early entry
    elif acceleration > 1:
        score += 5
    elif acceleration > 0:
        score += 2
    elif acceleration < -3:
        score -= 8    # Strongly decelerating — late entry
    elif acceleration < -1:
        score -= 5
    elif acceleration < 0:
        score -= 2

    # Relative strength vs SPY (max +/- 7 pts)
    if relative_strength > 8:
        score += 7    # Strong leader
    elif relative_strength > 4:
        score += 5
    elif relative_strength > 1:
        score += 3
    elif relative_strength < -8:
        score -= 7    # Laggard
    elif relative_strength < -4:
        score -= 5
    elif relative_strength < -1:
        score -= 3

    # Volume-direction alignment (max +/- 7 pts)
    if vol_direction_ratio > 1.4:
        score += 7    # Strong accumulation
    elif vol_direction_ratio > 1.15:
        score += 4
    elif vol_direction_ratio < 0.7:
        score -= 7    # Distribution
    elif vol_direction_ratio < 0.85:
        score -= 4

    # Today's volume spike (max +5 pts, reduced from old +15)
    if volume_ratio > 2:
        score += 5
    elif volume_ratio > 1.5:
        score += 3

    # Breakout bonus (+8 pts)
    if is_breakout:
        score += 8

    # RSI — Livermore sweet spot (max +/- 8 pts)
    # 50-65 is ideal: momentum confirmed, not extended
    if 50 <= rsi < 65:
        score += 8    # Sweet spot
    elif 65 <= rsi < 75:
        score += 4    # Getting warm but ok
    elif 40 <= rsi < 50:
        score += 0    # Neutral
    elif 30 <= rsi < 40:
        score -= 4    # Weak
    elif rsi < 30:
        score -= 8    # Broken — not "going up"

    # MA position (max +5 pts)
    if above_ma20:
        score += 3
    if above_ma50:
        score += 2

    # ── TOO-LATE PENALTIES ───────────────────────────────────────
    too_late_flags = []

    # RSI extreme (> 80)
    if rsi > 80:
        score -= 4
        too_late_flags.append('rsi_extreme')

    # Extended above MA20 (> 12%)
    if pct_above_ma20 > 12:
        score -= 4
        too_late_flags.append('extended_above_ma')

    # Too many consecutive up days (7+)
    if consecutive_up >= 7:
        score -= 4
        too_late_flags.append('consecutive_up_days')

    # Clamp 0-100
    score = max(0, min(100, score))

    # ── Classify trend quality ───────────────────────────────────
    if score >= 75 and acceleration > 0 and relative_strength > 0:
        trend_quality = 'strong_early'     # Livermore ideal
    elif score >= 65 and not too_late_flags:
        trend_quality = 'confirmed'        # Good trend, still timely
    elif score >= 55:
        trend_quality = 'emerging'         # Building momentum
    elif too_late_flags:
        trend_quality = 'extended'         # Probably too late
    elif score >= 40:
        trend_quality = 'weak'
    else:
        trend_quality = 'bearish'

    return {
        'change_1d': round(float(change_1d), 2),
        'change_5d': round(float(change_5d), 2),
        'change_1m': round(float(change_1m), 2),
        'volume_ratio': round(float(volume_ratio), 2),
        'rsi': round(float(rsi), 1),
        'above_ma20': bool(above_ma20),
        'above_ma50': bool(above_ma50),
        'score': round(float(score), 1),
        'price': round(float(price), 2),
        # Livermore signals
        'acceleration': round(float(acceleration), 2),
        'relative_strength': round(float(relative_strength), 2),
        'vol_direction_ratio': round(float(vol_direction_ratio), 2),
        'is_breakout': bool(is_breakout),
        'consecutive_up_days': int(consecutive_up),
        'pct_above_ma20': round(float(pct_above_ma20), 2),
        'too_late_flags': too_late_flags,
        'trend_quality': trend_quality,
    }


def scan_momentum(tickers: Optional[List[str]] = None,
                   extra_tickers: Optional[List[str]] = None) -> List[Dict]:
    """
    Scan stocks for momentum signals.

    Args:
        tickers: Discovered pool from Phase 2 (replaces old DEFAULT_TICKERS).
                 If None, only BASELINE_WATCHLIST is scanned.
        extra_tickers: Additional tickers to merge in (e.g. theme tickers).

    Returns list of stocks with momentum data, sorted by score.
    """
    # Always include baseline for market context
    all_tickers = list(BASELINE_WATCHLIST)
    if tickers:
        all_tickers.extend(tickers)
    if extra_tickers:
        all_tickers.extend(extra_tickers)
    all_tickers = list(set(all_tickers))

    results = []
    logger.info(f"Scanning momentum for {len(all_tickers)} tickers...")

    end_date = datetime.now()
    start_date = end_date - timedelta(days=60)  # Need 60 days for 50 MA

    # Batch downloads to stay within yfinance limits
    batches = [all_tickers[i:i + YFINANCE_BATCH_LIMIT]
               for i in range(0, len(all_tickers), YFINANCE_BATCH_LIMIT)]

    # We'll extract SPY's 1m return for relative strength calculation.
    # SPY is in BASELINE_WATCHLIST so it will be in the first batch.
    spy_change_1m = 0.0
    spy_extracted = False

    for batch_idx, batch in enumerate(batches):
        if len(batches) > 1:
            logger.info(f"  Batch {batch_idx + 1}/{len(batches)}: {len(batch)} tickers")

        try:
            data = yf.download(
                batch,
                start=start_date,
                end=end_date,
                progress=False,
                threads=True
            )
        except Exception as e:
            logger.error(f"Failed to download batch {batch_idx + 1}: {e}")
            continue

        # Extract SPY benchmark data from whichever batch contains it
        if not spy_extracted and 'SPY' in batch:
            try:
                if len(batch) == 1:
                    spy_data = data
                else:
                    spy_data = data.xs('SPY', axis=1, level=1) if 'SPY' in data.columns.get_level_values(1) else pd.DataFrame()
                if not spy_data.empty and len(spy_data) >= 20:
                    spy_close = spy_data['Close']
                    spy_change_1m = float(((spy_close.iloc[-1] / spy_close.iloc[0]) - 1) * 100)
                    spy_extracted = True
                    logger.info(f"  SPY benchmark: {spy_change_1m:+.2f}% (1m)")
            except Exception as e:
                logger.debug(f"Could not extract SPY data: {e}")

        for ticker in batch:
            try:
                if len(batch) == 1:
                    ticker_data = data
                else:
                    ticker_data = data.xs(ticker, axis=1, level=1) if ticker in data.columns.get_level_values(1) else pd.DataFrame()

                if ticker_data.empty:
                    continue

                momentum = calculate_momentum_score(ticker_data,
                                                     spy_change_1m=spy_change_1m)
                if momentum:
                    momentum['ticker'] = ticker
                    results.append(momentum)

            except Exception as e:
                logger.debug(f"Error processing {ticker}: {e}")
                continue

    # Sort by score descending
    results.sort(key=lambda x: x['score'], reverse=True)

    logger.info(f"Found {len(results)} stocks with momentum data")
    return results


def format_momentum_indicator(score: float) -> str:
    """Convert score to visual indicator."""
    if score >= 80:
        return "+++"
    elif score >= 65:
        return "++"
    elif score >= 50:
        return "+"
    elif score >= 35:
        return "-"
    else:
        return "--"


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    results = scan_momentum()

    print("\nTOP 15 MOMENTUM STOCKS (Livermore-style)")
    print("-" * 110)
    print(f"{'#':>2} {'Ticker':6} {'Score':>5} {'Quality':12} {'1M':>7} {'Accel':>6} {'RelStr':>6} {'VolDir':>6} {'RSI':>5} {'Flags'}")
    print("-" * 110)
    for i, s in enumerate(results[:15], 1):
        flags = ','.join(s.get('too_late_flags', [])) or '-'
        brk = ' BRK' if s.get('is_breakout') else ''
        print(f"{i:2}. {s['ticker']:6} {s['score']:5.1f} {s['trend_quality']:12} "
              f"{s['change_1m']:+6.2f}% {s['acceleration']:+5.2f} {s['relative_strength']:+5.2f} "
              f"{s['vol_direction_ratio']:5.2f} {s['rsi']:5.1f} {flags}{brk}")

    # Show too-late / extended stocks
    extended = [s for s in results if s.get('too_late_flags')]
    if extended:
        print(f"\n⚠ EXTENDED / TOO-LATE ({len(extended)} stocks):")
        for s in extended[:5]:
            print(f"  {s['ticker']:6} score={s['score']:.0f} flags={','.join(s['too_late_flags'])}")

    # Show breakouts
    breakouts = [s for s in results if s.get('is_breakout')]
    if breakouts:
        print(f"\n★ BREAKOUTS ({len(breakouts)} stocks):")
        for s in breakouts[:5]:
            print(f"  {s['ticker']:6} score={s['score']:.0f} vol={s['volume_ratio']:.1f}x accel={s['acceleration']:+.1f}")
