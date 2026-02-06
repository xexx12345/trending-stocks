"""
Bearish Momentum Scanner - Identifies stocks with technical breakdown signals.
Reuses existing momentum data from Phase 3 (no extra API calls).
"""

from typing import Dict, List
import logging

logger = logging.getLogger(__name__)


def scan_bearish_momentum(momentum_data: List[Dict]) -> List[Dict]:
    """
    Analyze existing momentum data for bearish technical signals.

    Args:
        momentum_data: The existing results['momentum'] list from Phase 3.

    Returns:
        List of dicts sorted by bearish score descending, each containing:
        - ticker, score (0-100), signals, change_1m, rsi, summary
    """
    results = []

    for stock in momentum_data:
        ticker = stock.get('ticker', '')
        change_1d = stock.get('change_1d', 0)
        change_5d = stock.get('change_5d', 0)
        change_1m = stock.get('change_1m', 0)
        rsi = stock.get('rsi', 50)
        volume_ratio = stock.get('volume_ratio', 1.0)
        above_ma20 = stock.get('above_ma20', True)
        above_ma50 = stock.get('above_ma50', True)

        score = 0
        signals = []

        # Negative 1M price change (bigger drop = higher short score, max 30 pts)
        if change_1m < 0:
            pts = min(abs(change_1m) * 1.5, 30)
            score += pts
            signals.append('declining')

        # RSI > 70: overbought fade candidate (max 20 pts)
        if rsi > 70:
            pts = min((rsi - 70) * 1.5, 20)
            score += pts
            signals.append('overbought')
        elif rsi > 80:
            score += 5  # extra for extreme overbought
            signals.append('extreme_overbought')

        # Price below MA20 (10 pts)
        if not above_ma20:
            score += 10
            signals.append('below_ma20')

        # Price below MA50 (10 pts)
        if not above_ma50:
            score += 10
            signals.append('below_ma50')

        # Death cross proxy: below MA50 + negative 5D trend (10 pts)
        if not above_ma50 and change_5d < 0:
            score += 10
            signals.append('death_cross_proxy')

        # High volume on down days (volume_ratio > 1.5 + negative 1D) (15 pts)
        if volume_ratio > 1.5 and change_1d < 0:
            pts = min((volume_ratio - 1.0) * 5, 15)
            score += pts
            signals.append('high_vol_decline')

        # Below both MAs bonus (5 pts)
        if not above_ma20 and not above_ma50:
            score += 5
            signals.append('breakdown')

        # Normalize to 0-100
        score = max(0, min(100, score))

        if score < 10:
            continue

        # Build summary
        summary_parts = []
        if rsi > 70:
            summary_parts.append(f"RSI {rsi:.0f}")
        if change_1m < -5:
            summary_parts.append(f"{change_1m:+.1f}% 1M")
        if not above_ma50:
            summary_parts.append("below MA50")
        if volume_ratio > 1.5 and change_1d < 0:
            summary_parts.append(f"vol {volume_ratio:.1f}x on down day")

        results.append({
            'ticker': ticker,
            'score': round(score, 1),
            'signals': signals,
            'change_1m': round(change_1m, 2),
            'rsi': round(rsi, 1),
            'summary': '; '.join(summary_parts) if summary_parts else 'Mild bearish signals',
        })

    results.sort(key=lambda x: x['score'], reverse=True)
    logger.info(f"Bearish momentum: found {len(results)} candidates")
    return results
