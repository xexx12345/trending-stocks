"""
Options Activity Scanner - Detect unusual options flow via yfinance.

Scans option chains for:
- High Volume/OI ratio (unusual activity)
- Put/Call ratio anomalies (sentiment indicator)
- Premium spikes (large bets being placed)
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import yfinance as yf

logger = logging.getLogger(__name__)

# Default minimum thresholds for detection
MIN_VOLUME_OI_RATIO = 1.5  # Volume/OI > 1.5 is interesting
HIGH_VOLUME_OI_RATIO = 3.0  # Volume/OI > 3 is very unusual


def _get_nearest_expiry(ticker: yf.Ticker) -> Optional[str]:
    """Get the nearest options expiration date."""
    try:
        expirations = ticker.options
        if not expirations:
            return None
        # Get the nearest expiry (first one)
        return expirations[0]
    except Exception:
        return None


def _calculate_options_score(
    volume_oi_ratio: float,
    put_call_ratio: float,
    call_volume: int,
    put_volume: int,
) -> float:
    """
    Calculate options activity score (0-100).

    Scoring logic:
    - Base: 50
    - Volume/OI ratio: >5 = +25, >3 = +15, >2 = +10
    - Put/Call anomaly: <0.5 or >1.5 = +15, <0.6 or >1.2 = +10
    """
    score = 50.0

    # Volume/OI ratio scoring
    if volume_oi_ratio > 5:
        score += 25
    elif volume_oi_ratio > 3:
        score += 15
    elif volume_oi_ratio > 2:
        score += 10

    # Put/Call ratio anomaly scoring
    if put_call_ratio < 0.5 or put_call_ratio > 1.5:
        score += 15
    elif put_call_ratio < 0.6 or put_call_ratio > 1.2:
        score += 10

    # Volume bonus for high absolute volumes
    total_volume = call_volume + put_volume
    if total_volume > 100000:
        score += 10
    elif total_volume > 50000:
        score += 5

    return min(100.0, score)


def _determine_signal(put_call_ratio: float, volume_oi_ratio: float) -> str:
    """
    Determine the type of options signal.

    Returns: bullish_sweep, bearish_sweep, straddle, or neutral
    """
    if put_call_ratio < 0.5 and volume_oi_ratio > 2:
        return 'bullish_sweep'
    elif put_call_ratio > 1.5 and volume_oi_ratio > 2:
        return 'bearish_sweep'
    elif 0.8 <= put_call_ratio <= 1.2 and volume_oi_ratio > 3:
        return 'straddle'
    else:
        return 'neutral'


def fetch_options_activity(ticker_symbol: str) -> Optional[Dict]:
    """
    Fetch options activity data for a single ticker.

    Args:
        ticker_symbol: Stock ticker symbol

    Returns:
        Dict with options activity metrics, or None if failed/no data
    """
    try:
        ticker = yf.Ticker(ticker_symbol)
        expiry = _get_nearest_expiry(ticker)

        if not expiry:
            return None

        # Get options chain for nearest expiry
        chain = ticker.option_chain(expiry)
        calls = chain.calls
        puts = chain.puts

        if calls.empty and puts.empty:
            return None

        # Calculate aggregate metrics
        call_volume = int(calls['volume'].sum()) if 'volume' in calls.columns else 0
        call_oi = int(calls['openInterest'].sum()) if 'openInterest' in calls.columns else 0
        put_volume = int(puts['volume'].sum()) if 'volume' in puts.columns else 0
        put_oi = int(puts['openInterest'].sum()) if 'openInterest' in puts.columns else 0

        total_volume = call_volume + put_volume
        total_oi = call_oi + put_oi

        if total_oi == 0:
            return None

        # Calculate ratios
        volume_oi_ratio = total_volume / total_oi if total_oi > 0 else 0
        put_call_ratio = put_volume / call_volume if call_volume > 0 else 1.0

        # Skip if no unusual activity
        if volume_oi_ratio < MIN_VOLUME_OI_RATIO and 0.7 <= put_call_ratio <= 1.3:
            return None

        # Calculate score
        score = _calculate_options_score(
            volume_oi_ratio, put_call_ratio, call_volume, put_volume
        )

        # Determine signal type
        signal = _determine_signal(put_call_ratio, volume_oi_ratio)

        return {
            'ticker': ticker_symbol,
            'score': round(score, 1),
            'volume_oi_ratio': round(volume_oi_ratio, 2),
            'put_call_ratio': round(put_call_ratio, 2),
            'call_volume': call_volume,
            'put_volume': put_volume,
            'call_oi': call_oi,
            'put_oi': put_oi,
            'expiry': expiry,
            'signal': signal,
        }

    except Exception as e:
        logger.debug(f"Failed to fetch options for {ticker_symbol}: {e}")
        return None


def scan_options_activity(
    tickers: List[str],
    min_score: float = 50.0,
) -> List[Dict]:
    """
    Scan multiple tickers for unusual options activity.

    Args:
        tickers: List of ticker symbols to analyze
        min_score: Minimum score threshold to include in results

    Returns:
        List of dicts with ticker, score, and options metrics
    """
    if not tickers:
        return []

    results = []
    processed = 0
    total = len(tickers)

    logger.info(f"Scanning options activity for {total} tickers...")

    for ticker in tickers:
        try:
            data = fetch_options_activity(ticker)

            if data and data['score'] >= min_score:
                results.append(data)

            processed += 1

            # Progress logging every 25 tickers
            if processed % 25 == 0:
                logger.debug(f"Options scan progress: {processed}/{total}")

        except Exception as e:
            logger.debug(f"Error processing options for {ticker}: {e}")
            continue

    # Sort by score descending
    results.sort(key=lambda x: x['score'], reverse=True)

    logger.info(f"Options scan found {len(results)} tickers with unusual activity")
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("\nOPTIONS ACTIVITY SCAN")
    print("-" * 60)

    # Test with some popular optionable stocks
    test_tickers = ['NVDA', 'TSLA', 'AAPL', 'AMD', 'SPY', 'QQQ', 'META', 'AMZN', 'GOOGL', 'MSFT']

    results = scan_options_activity(test_tickers, min_score=0)

    if results:
        print(f"\nOptions Activity Data:\n")
        print(f"{'Ticker':<8} {'Score':<8} {'V/OI':<8} {'P/C':<8} {'CallVol':<10} {'PutVol':<10} {'Signal'}")
        print("-" * 70)
        for r in results:
            print(f"{r['ticker']:<8} {r['score']:<8.1f} {r['volume_oi_ratio']:<8.2f} "
                  f"{r['put_call_ratio']:<8.2f} {r['call_volume']:<10} {r['put_volume']:<10} {r['signal']}")
    else:
        print("No unusual options activity found")
