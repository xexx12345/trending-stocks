"""
Fundamentals Scanner - Identifies stocks with valuation stress and earnings deterioration.
Uses yfinance .info for fundamental data (free, no API key needed).
"""

import yfinance as yf
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)

# Max tickers per batch
BATCH_SIZE = 50


def _score_ticker(info: dict) -> Dict:
    """Score a single ticker's fundamentals for short conviction."""
    score = 0
    signals = []

    # Forward P/E vs trailing P/E (expansion = slowing growth)
    forward_pe = info.get('forwardPE')
    trailing_pe = info.get('trailingPE')
    if forward_pe and trailing_pe and forward_pe > 0 and trailing_pe > 0:
        if forward_pe > trailing_pe * 1.2:
            score += 15
            signals.append('pe_expansion')
        if forward_pe > 50:
            score += 10
            signals.append('high_forward_pe')

    # P/S ratio extreme (>15 = overvalued)
    ps_ratio = info.get('priceToSalesTrailing12Months')
    if ps_ratio and ps_ratio > 15:
        pts = min((ps_ratio - 15) * 2, 15)
        score += pts
        signals.append('high_ps_ratio')

    # Debt-to-equity ratio (>2.0 = stressed)
    debt_to_equity = info.get('debtToEquity')
    if debt_to_equity and debt_to_equity > 200:  # yfinance reports as percentage
        pts = min((debt_to_equity - 200) / 50, 15)
        score += pts
        signals.append('rising_debt')

    # Negative earnings growth (YoY)
    earnings_growth = info.get('earningsGrowth')
    if earnings_growth is not None and earnings_growth < 0:
        pts = min(abs(earnings_growth) * 50, 20)
        score += pts
        signals.append('negative_earnings_growth')

    # Revenue growth deceleration
    revenue_growth = info.get('revenueGrowth')
    if revenue_growth is not None and revenue_growth < 0.05:
        pts = 10 if revenue_growth < 0 else 5
        score += pts
        signals.append('revenue_deceleration')

    # Negative profit margins
    profit_margin = info.get('profitMargins')
    if profit_margin is not None and profit_margin < 0:
        pts = min(abs(profit_margin) * 30, 15)
        score += pts
        signals.append('negative_margins')

    # Normalize to 0-100
    score = max(0, min(100, score))

    return {
        'score': round(score, 1),
        'signals': signals,
        'forward_pe': round(forward_pe, 2) if forward_pe else None,
        'trailing_pe': round(trailing_pe, 2) if trailing_pe else None,
        'debt_to_equity': round(debt_to_equity / 100, 2) if debt_to_equity else None,
        'earnings_growth': round(earnings_growth, 4) if earnings_growth is not None else None,
        'revenue_growth': round(revenue_growth, 4) if revenue_growth is not None else None,
        'ps_ratio': round(ps_ratio, 2) if ps_ratio else None,
        'profit_margin': round(profit_margin, 4) if profit_margin is not None else None,
    }


def scan_fundamentals(tickers: List[str]) -> List[Dict]:
    """
    Scan tickers for fundamental short signals using yfinance.

    Args:
        tickers: List of ticker symbols to analyze.

    Returns:
        List of dicts sorted by score descending, each containing:
        - ticker, score, signals, forward_pe, debt_to_equity, earnings_growth, summary
    """
    if not tickers:
        return []

    results = []

    for i in range(0, len(tickers), BATCH_SIZE):
        batch = tickers[i:i + BATCH_SIZE]
        if len(tickers) > BATCH_SIZE:
            logger.info(f"  Fundamentals batch {i // BATCH_SIZE + 1}/{(len(tickers) + BATCH_SIZE - 1) // BATCH_SIZE}")

        for ticker in batch:
            try:
                info = yf.Ticker(ticker).info
                if not info or info.get('quoteType') == 'ETF':
                    continue

                scored = _score_ticker(info)
                if scored['score'] < 10:
                    continue

                # Build summary
                summary_parts = []
                if scored.get('forward_pe') and scored['forward_pe'] > 40:
                    summary_parts.append(f"fwd P/E {scored['forward_pe']:.0f}")
                if scored.get('debt_to_equity') and scored['debt_to_equity'] > 2.0:
                    summary_parts.append(f"D/E {scored['debt_to_equity']:.1f}")
                if scored.get('earnings_growth') is not None and scored['earnings_growth'] < 0:
                    summary_parts.append(f"EPS {scored['earnings_growth']:+.0%}")
                if scored.get('revenue_growth') is not None and scored['revenue_growth'] < 0:
                    summary_parts.append(f"rev {scored['revenue_growth']:+.0%}")
                if scored.get('profit_margin') is not None and scored['profit_margin'] < 0:
                    summary_parts.append("negative margins")

                results.append({
                    'ticker': ticker,
                    'score': scored['score'],
                    'signals': scored['signals'],
                    'forward_pe': scored['forward_pe'],
                    'debt_to_equity': scored['debt_to_equity'],
                    'earnings_growth': scored['earnings_growth'],
                    'summary': '; '.join(summary_parts) if summary_parts else 'Mild fundamental stress',
                })

            except Exception as e:
                logger.debug(f"Fundamentals error for {ticker}: {e}")
                continue

    results.sort(key=lambda x: x['score'], reverse=True)
    logger.info(f"Fundamentals: found {len(results)} candidates with stress signals")
    return results
