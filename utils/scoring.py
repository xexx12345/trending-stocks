"""
Scoring utilities - Aggregates data from 4 sources into combined scores
"""

from typing import Dict, List, Optional, Set
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)

DEFAULT_WEIGHTS = {
    'momentum': 0.35,
    'finviz': 0.25,
    'reddit': 0.20,
    'news': 0.20,
}

THEME_BONUS = 5  # Extra points for stocks in hot themes
MULTI_SOURCE_BONUS = 3  # Extra points per additional source beyond 1


def normalize_score(score: float, min_val: float = 0, max_val: float = 100) -> float:
    """Normalize a score to 0-100 range."""
    return max(0, min(100, (score - min_val) / (max_val - min_val) * 100))


def aggregate_scores(
    momentum_data: List[Dict],
    reddit_data: List[Dict],
    news_data: List[Dict],
    weights: Optional[Dict[str, float]] = None,
    theme_tickers: Optional[Set[str]] = None,
    finviz_data: Optional[Dict[str, Dict]] = None,
) -> List[Dict]:
    """
    Aggregate scores from 4 sources into a combined ranking.

    Args:
        momentum_data: List of stocks with momentum scores
        reddit_data: List of stocks with reddit mention data
        news_data: List of stocks with news data
        weights: Dict of source weights (should sum to 1.0)
        theme_tickers: Set of tickers in hot themes (get bonus points)
        finviz_data: Dict of ticker -> {score, signals, change, sector} from Finviz

    Returns:
        List of stocks with combined scores, sorted by score descending
    """
    if weights is None:
        weights = DEFAULT_WEIGHTS

    if theme_tickers is None:
        theme_tickers = set()

    if finviz_data is None:
        finviz_data = {}

    # Create lookup dicts by ticker
    momentum_lookup = {d['ticker']: d for d in momentum_data}
    reddit_lookup = {d['ticker']: d for d in reddit_data}
    news_lookup = {d['ticker']: d for d in news_data}

    # Get all unique tickers across 4 sources
    all_tickers = (
        set(momentum_lookup.keys()) |
        set(reddit_lookup.keys()) |
        set(news_lookup.keys()) |
        set(finviz_data.keys())
    )

    results = []

    for ticker in all_tickers:
        mom = momentum_lookup.get(ticker, {})
        red = reddit_lookup.get(ticker, {})
        news = news_lookup.get(ticker, {})
        fvz = finviz_data.get(ticker, {})

        # Get individual scores (default to 50 if missing from that source)
        mom_score = mom.get('score', 50) if mom else 50
        red_score = red.get('score', 50) if red else 50
        news_score = news.get('score', 50) if news else 50
        fvz_score = fvz.get('score', 50) if fvz else 50

        # Calculate weighted combined score
        combined_score = (
            mom_score * weights.get('momentum', 0) +
            fvz_score * weights.get('finviz', 0) +
            red_score * weights.get('reddit', 0) +
            news_score * weights.get('news', 0)
        )

        # Theme bonus
        in_hot_theme = ticker in theme_tickers
        if in_hot_theme:
            combined_score += THEME_BONUS

        # Count data sources present
        sources = []
        if mom:
            sources.append('momentum')
        if fvz:
            sources.append('finviz')
        if red:
            sources.append('reddit')
        if news:
            sources.append('news')

        # Multi-source bonus
        if len(sources) > 1:
            combined_score += (len(sources) - 1) * MULTI_SOURCE_BONUS

        # Build summary
        summary_parts = []
        if mom and mom.get('change_1m', 0) > 5:
            summary_parts.append(f"+{mom['change_1m']:.0f}% month")
        if fvz and fvz.get('signals'):
            summary_parts.append(f"finviz: {', '.join(fvz['signals'][:2])}")
        if red and red.get('mentions', 0) > 10:
            summary_parts.append(f"{red['mentions']} Reddit mentions")
        if news and news.get('article_count', 0) > 2:
            summary_parts.append(f"{news['article_count']} news articles")
        if in_hot_theme:
            summary_parts.append("hot theme")

        results.append({
            'ticker': ticker,
            'combined_score': round(combined_score, 1),
            'momentum_score': round(mom_score, 1),
            'finviz_score': round(fvz_score, 1),
            'reddit_score': round(red_score, 1),
            'news_score': round(news_score, 1),
            'in_hot_theme': in_hot_theme,
            'sources': sources,
            'summary': '; '.join(summary_parts) if summary_parts else 'Low activity',

            # Include raw data for detailed view
            'momentum_data': mom,
            'finviz_data': fvz,
            'reddit_data': red,
            'news_data': news,
        })

    # Sort by combined score
    results.sort(key=lambda x: x['combined_score'], reverse=True)

    logger.info(f"Aggregated scores for {len(results)} tickers")
    return results


def format_score_indicator(score: float) -> str:
    """Convert score to +/- indicator."""
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


def get_sector_from_momentum(momentum_data: Dict) -> Optional[str]:
    """Extract sector from momentum data if available."""
    return momentum_data.get('sector')


def filter_by_score(results: List[Dict], min_score: float = 50) -> List[Dict]:
    """Filter results by minimum combined score."""
    return [r for r in results if r['combined_score'] >= min_score]


def filter_by_sources(results: List[Dict], min_sources: int = 2) -> List[Dict]:
    """Filter to stocks appearing in multiple sources."""
    return [r for r in results if len(r['sources']) >= min_sources]
