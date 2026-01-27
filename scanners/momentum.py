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


def calculate_momentum_score(data: pd.DataFrame) -> Dict:
    """
    Calculate momentum score for a stock based on:
    - Price change (1d, 5d, 1m)
    - Volume vs average
    - RSI
    - MA crossovers
    """
    if data.empty or len(data) < 20:
        return None

    close = data['Close']
    volume = data['Volume']

    # Price changes
    change_1d = ((close.iloc[-1] / close.iloc[-2]) - 1) * 100 if len(close) >= 2 else 0
    change_5d = ((close.iloc[-1] / close.iloc[-6]) - 1) * 100 if len(close) >= 6 else 0
    change_1m = ((close.iloc[-1] / close.iloc[0]) - 1) * 100 if len(close) >= 20 else 0

    # Volume spike
    avg_volume = volume.iloc[:-1].mean()
    volume_ratio = volume.iloc[-1] / avg_volume if avg_volume > 0 else 1.0

    # RSI
    rsi = calculate_rsi(close)

    # Moving averages
    ma_20 = close.rolling(20).mean().iloc[-1]
    ma_50 = close.rolling(50).mean().iloc[-1] if len(close) >= 50 else ma_20

    above_ma20 = close.iloc[-1] > ma_20
    above_ma50 = close.iloc[-1] > ma_50

    # Calculate composite score (0-100)
    score = 50  # Base score

    # Price momentum contribution (max +/- 25 points)
    score += min(max(change_1m * 2, -25), 25)

    # Volume contribution (max +15 points)
    if volume_ratio > 2:
        score += 15
    elif volume_ratio > 1.5:
        score += 10
    elif volume_ratio > 1.2:
        score += 5

    # RSI contribution (max +/- 10 points)
    if 50 < rsi < 70:
        score += 10  # Bullish momentum
    elif rsi >= 70:
        score += 5   # Overbought, less weight
    elif rsi < 30:
        score -= 10  # Oversold

    # MA position contribution (max +10 points)
    if above_ma20:
        score += 5
    if above_ma50:
        score += 5

    # Normalize to 0-100
    score = max(0, min(100, score))

    return {
        'change_1d': round(change_1d, 2),
        'change_5d': round(change_5d, 2),
        'change_1m': round(change_1m, 2),
        'volume_ratio': round(volume_ratio, 2),
        'rsi': round(rsi, 1),
        'above_ma20': above_ma20,
        'above_ma50': above_ma50,
        'score': round(score, 1),
        'price': round(close.iloc[-1], 2)
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

        for ticker in batch:
            try:
                if len(batch) == 1:
                    ticker_data = data
                else:
                    ticker_data = data.xs(ticker, axis=1, level=1) if ticker in data.columns.get_level_values(1) else pd.DataFrame()

                if ticker_data.empty:
                    continue

                momentum = calculate_momentum_score(ticker_data)
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

    print("\nTOP 10 MOMENTUM STOCKS")
    print("-" * 60)
    for i, stock in enumerate(results[:10], 1):
        print(f"{i}. {stock['ticker']:6} | Score: {stock['score']:5.1f} | "
              f"1D: {stock['change_1d']:+6.2f}% | 1M: {stock['change_1m']:+6.2f}% | "
              f"Vol: {stock['volume_ratio']:.1f}x")
