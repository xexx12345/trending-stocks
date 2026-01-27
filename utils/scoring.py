"""
Scoring utilities - Aggregates data from multiple sources into combined scores
"""

from typing import Dict, List, Optional
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)

DEFAULT_WEIGHTS = {
    'momentum': 0.4,
    'reddit': 0.3,
    'news': 0.3
}


def normalize_score(score: float, min_val: float = 0, max_val: float = 100) -> float:
    """Normalize a score to 0-100 range."""
    return max(0, min(100, (score - min_val) / (max_val - min_val) * 100))


def aggregate_scores(
    momentum_data: List[Dict],
    reddit_data: List[Dict],
    news_data: List[Dict],
    weights: Optional[Dict[str, float]] = None
) -> List[Dict]:
    """
    Aggregate scores from multiple sources into a combined ranking.

    Args:
        momentum_data: List of stocks with momentum scores
        reddit_data: List of stocks with reddit mention data
        news_data: List of stocks with news data
        weights: Dict of source weights (must sum to 1.0)

    Returns:
        List of stocks with combined scores, sorted by score descending
    """
    if weights is None:
        weights = DEFAULT_WEIGHTS

    # Create lookup dicts by ticker
    momentum_lookup = {d['ticker']: d for d in momentum_data}
    reddit_lookup = {d['ticker']: d for d in reddit_data}
    news_lookup = {d['ticker']: d for d in news_data}

    # Get all unique tickers
    all_tickers = set(momentum_lookup.keys()) | set(reddit_lookup.keys()) | set(news_lookup.keys())

    results = []

    for ticker in all_tickers:
        mom = momentum_lookup.get(ticker, {})
        red = reddit_lookup.get(ticker, {})
        news = news_lookup.get(ticker, {})

        # Get individual scores (default to 50 if missing)
        mom_score = mom.get('score', 50) if mom else 50
        red_score = red.get('score', 50) if red else 50
        news_score = news.get('score', 50) if news else 50

        # Calculate weighted combined score
        combined_score = (
            mom_score * weights.get('momentum', 0) +
            red_score * weights.get('reddit', 0) +
            news_score * weights.get('news', 0)
        )

        # Build summary
        summary_parts = []
        if mom and mom.get('change_1m', 0) > 5:
            summary_parts.append(f"+{mom['change_1m']:.0f}% month")
        if red and red.get('mentions', 0) > 10:
            summary_parts.append(f"{red['mentions']} Reddit mentions")
        if news and news.get('article_count', 0) > 2:
            summary_parts.append(f"{news['article_count']} news articles")

        # Determine data sources present
        sources = []
        if mom:
            sources.append('momentum')
        if red:
            sources.append('reddit')
        if news:
            sources.append('news')

        results.append({
            'ticker': ticker,
            'combined_score': round(combined_score, 1),
            'momentum_score': round(mom_score, 1),
            'reddit_score': round(red_score, 1),
            'news_score': round(news_score, 1),
            'sources': sources,
            'summary': '; '.join(summary_parts) if summary_parts else 'Low activity',

            # Include raw data for detailed view
            'momentum_data': mom,
            'reddit_data': red,
            'news_data': news
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
