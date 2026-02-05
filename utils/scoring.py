"""
Scoring utilities - Aggregates data from 9 sources into combined scores
"""

from typing import Dict, List, Optional, Set
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)

DEFAULT_WEIGHTS = {
    'momentum': 0.25,
    'finviz': 0.15,
    'reddit': 0.12,
    'news': 0.12,
    'google_trends': 0.08,
    'short_interest': 0.08,
    'options_activity': 0.08,
    'perplexity': 0.07,
    'insider_trading': 0.05,
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
    google_trends_data: Optional[List[Dict]] = None,
    short_interest_data: Optional[List[Dict]] = None,
    options_data: Optional[List[Dict]] = None,
    perplexity_data: Optional[List[Dict]] = None,
    insider_data: Optional[List[Dict]] = None,
) -> List[Dict]:
    """
    Aggregate scores from 9 sources into a combined ranking.

    Args:
        momentum_data: List of stocks with momentum scores
        reddit_data: List of stocks with reddit mention data
        news_data: List of stocks with news data
        weights: Dict of source weights (should sum to 1.0)
        theme_tickers: Set of tickers in hot themes (get bonus points)
        finviz_data: Dict of ticker -> {score, signals, change, sector} from Finviz
        google_trends_data: List of dicts with ticker, score, trend_value, is_breakout
        short_interest_data: List of dicts with ticker, score, short_float, short_ratio, squeeze_risk
        options_data: List of dicts with ticker, score, volume_oi_ratio, put_call_ratio, signal
        perplexity_data: List of dicts with ticker, score, mention_count, sentiment, has_catalyst
        insider_data: List of dicts with ticker, score, is_buy, transaction_value, role

    Returns:
        List of stocks with combined scores, sorted by score descending
    """
    if weights is None:
        weights = DEFAULT_WEIGHTS

    if theme_tickers is None:
        theme_tickers = set()

    if finviz_data is None:
        finviz_data = {}

    if google_trends_data is None:
        google_trends_data = []

    if short_interest_data is None:
        short_interest_data = []

    if options_data is None:
        options_data = []

    if perplexity_data is None:
        perplexity_data = []

    if insider_data is None:
        insider_data = []

    # Create lookup dicts by ticker
    momentum_lookup = {d['ticker']: d for d in momentum_data}
    reddit_lookup = {d['ticker']: d for d in reddit_data}
    news_lookup = {d['ticker']: d for d in news_data}
    trends_lookup = {d['ticker']: d for d in google_trends_data}
    short_lookup = {d['ticker']: d for d in short_interest_data}
    options_lookup = {d['ticker']: d for d in options_data}
    perplexity_lookup = {d['ticker']: d for d in perplexity_data}
    insider_lookup = {d['ticker']: d for d in insider_data}

    # Get all unique tickers across 9 sources
    all_tickers = (
        set(momentum_lookup.keys()) |
        set(reddit_lookup.keys()) |
        set(news_lookup.keys()) |
        set(finviz_data.keys()) |
        set(trends_lookup.keys()) |
        set(short_lookup.keys()) |
        set(options_lookup.keys()) |
        set(perplexity_lookup.keys()) |
        set(insider_lookup.keys())
    )

    results = []

    for ticker in all_tickers:
        mom = momentum_lookup.get(ticker, {})
        red = reddit_lookup.get(ticker, {})
        news = news_lookup.get(ticker, {})
        fvz = finviz_data.get(ticker, {})
        trends = trends_lookup.get(ticker, {})
        short = short_lookup.get(ticker, {})
        opts = options_lookup.get(ticker, {})
        perp = perplexity_lookup.get(ticker, {})
        insd = insider_lookup.get(ticker, {})

        # Get individual scores (default to 50 if missing from that source)
        mom_score = mom.get('score', 50) if mom else 50
        red_score = red.get('score', 50) if red else 50
        news_score = news.get('score', 50) if news else 50
        fvz_score = fvz.get('score', 50) if fvz else 50
        trends_score = trends.get('score', 50) if trends else 50
        short_score = short.get('score', 50) if short else 50
        opts_score = opts.get('score', 50) if opts else 50
        perp_score = perp.get('score', 50) if perp else 50
        insd_score = insd.get('score', 50) if insd else 50

        # Calculate weighted combined score
        combined_score = (
            mom_score * weights.get('momentum', 0) +
            fvz_score * weights.get('finviz', 0) +
            red_score * weights.get('reddit', 0) +
            news_score * weights.get('news', 0) +
            trends_score * weights.get('google_trends', 0) +
            short_score * weights.get('short_interest', 0) +
            opts_score * weights.get('options_activity', 0) +
            perp_score * weights.get('perplexity', 0) +
            insd_score * weights.get('insider_trading', 0)
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
        if trends:
            sources.append('google_trends')
        if short:
            sources.append('short_interest')
        if opts:
            sources.append('options')
        if perp:
            sources.append('perplexity')
        if insd:
            sources.append('insider')

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
        if trends and trends.get('is_breakout'):
            summary_parts.append("Google breakout")
        elif trends and trends.get('trend_value', 0) > 50:
            summary_parts.append(f"trending ({trends['trend_value']})")
        if short and short.get('squeeze_risk') == 'high':
            sf = short.get('short_float', 0)
            summary_parts.append(f"squeeze risk ({sf:.0f}% short)")
        if opts and opts.get('signal') in ('bullish_sweep', 'bearish_sweep'):
            summary_parts.append(f"options: {opts['signal']}")
        if perp and perp.get('has_catalyst'):
            summary_parts.append("AI catalyst")
        if insd and insd.get('is_buy') and insd.get('transaction_value', 0) > 100000:
            summary_parts.append(f"insider buy ${insd['transaction_value']:,.0f}")
        if in_hot_theme:
            summary_parts.append("hot theme")

        results.append({
            'ticker': ticker,
            'combined_score': round(combined_score, 1),
            'momentum_score': round(mom_score, 1),
            'finviz_score': round(fvz_score, 1),
            'reddit_score': round(red_score, 1),
            'news_score': round(news_score, 1),
            'google_trends_score': round(trends_score, 1),
            'short_interest_score': round(short_score, 1),
            'options_score': round(opts_score, 1),
            'perplexity_score': round(perp_score, 1),
            'insider_score': round(insd_score, 1),
            'in_hot_theme': in_hot_theme,
            'sources': sources,
            'summary': '; '.join(summary_parts) if summary_parts else 'Low activity',

            # Passthrough fields for detailed view
            'short_float': short.get('short_float'),
            'short_ratio': short.get('short_ratio'),
            'squeeze_risk': short.get('squeeze_risk'),
            'trend_value': trends.get('trend_value'),
            'is_breakout': trends.get('is_breakout', False),
            'options_signal': opts.get('signal'),
            'volume_oi_ratio': opts.get('volume_oi_ratio'),
            'insider_is_buy': insd.get('is_buy'),
            'insider_value': insd.get('transaction_value'),

            # Include raw data for detailed view
            'momentum_data': mom,
            'finviz_data': fvz,
            'reddit_data': red,
            'news_data': news,
            'google_trends_data': trends,
            'short_interest_data': short,
            'options_data': opts,
            'perplexity_data': perp,
            'insider_data': insd,
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
