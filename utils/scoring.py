"""
Scoring utilities - Aggregates data from 12 sources into combined scores
"""

from typing import Dict, List, Optional, Set
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)

DEFAULT_WEIGHTS = {
    'momentum': 0.20,
    'finviz': 0.12,
    'reddit': 0.10,
    'news': 0.10,
    'google_trends': 0.06,
    'short_interest': 0.06,
    'options_activity': 0.08,
    'perplexity': 0.06,
    'insider_trading': 0.05,
    'analyst_ratings': 0.06,
    'congress_trading': 0.05,
    'institutional': 0.06,
    # Total: 1.00
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
    analyst_data: Optional[List[Dict]] = None,
    congress_data: Optional[List[Dict]] = None,
    institutional_data: Optional[List[Dict]] = None,
    etf_flows_data: Optional[Dict] = None,
) -> List[Dict]:
    """
    Aggregate scores from 12 sources into a combined ranking.

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
        analyst_data: List of dicts with ticker, score, action, analyst_firm
        congress_data: List of dicts with ticker, score, signal, buy_count, politicians
        institutional_data: List of dicts with ticker, score, signal, funds_buying
        etf_flows_data: Dict with sector_flows, hot_holdings for ETF flow signals

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

    if analyst_data is None:
        analyst_data = []

    if congress_data is None:
        congress_data = []

    if institutional_data is None:
        institutional_data = []

    if etf_flows_data is None:
        etf_flows_data = {}

    # Create lookup dicts by ticker
    momentum_lookup = {d['ticker']: d for d in momentum_data}
    reddit_lookup = {d['ticker']: d for d in reddit_data}
    news_lookup = {d['ticker']: d for d in news_data}
    trends_lookup = {d['ticker']: d for d in google_trends_data}
    short_lookup = {d['ticker']: d for d in short_interest_data}
    options_lookup = {d['ticker']: d for d in options_data}
    perplexity_lookup = {d['ticker']: d for d in perplexity_data}
    insider_lookup = {d['ticker']: d for d in insider_data}
    analyst_lookup = {d['ticker']: d for d in analyst_data}
    congress_lookup = {d['ticker']: d for d in congress_data}
    institutional_lookup = {d['ticker']: d for d in institutional_data}

    # ETF flows hot holdings lookup
    etf_hot_holdings = etf_flows_data.get('hot_holdings', {})

    # Get all unique tickers across 12 sources
    all_tickers = (
        set(momentum_lookup.keys()) |
        set(reddit_lookup.keys()) |
        set(news_lookup.keys()) |
        set(finviz_data.keys()) |
        set(trends_lookup.keys()) |
        set(short_lookup.keys()) |
        set(options_lookup.keys()) |
        set(perplexity_lookup.keys()) |
        set(insider_lookup.keys()) |
        set(analyst_lookup.keys()) |
        set(congress_lookup.keys()) |
        set(institutional_lookup.keys())
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
        anlst = analyst_lookup.get(ticker, {})
        cong = congress_lookup.get(ticker, {})
        inst = institutional_lookup.get(ticker, {})
        etf_hot = etf_hot_holdings.get(ticker, {})

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
        anlst_score = anlst.get('score', 50) if anlst else 50
        cong_score = cong.get('score', 50) if cong else 50
        inst_score = inst.get('score', 50) if inst else 50

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
            insd_score * weights.get('insider_trading', 0) +
            anlst_score * weights.get('analyst_ratings', 0) +
            cong_score * weights.get('congress_trading', 0) +
            inst_score * weights.get('institutional', 0)
        )

        # ETF flow bonus - if stock is in sectors with strong inflows
        if etf_hot:
            combined_score += etf_hot.get('combined_flow_score', 0) * 0.05

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
        if anlst:
            sources.append('analyst')
        if cong:
            sources.append('congress')
        if inst:
            sources.append('institutional')
        if etf_hot:
            sources.append('etf_flows')

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
        if anlst and anlst.get('action') == 'upgrade':
            summary_parts.append(f"analyst upgrade")
        if cong and cong.get('signal') == 'congress_buying':
            summary_parts.append(f"congress buying ({cong.get('politician_count', 0)} members)")
        if inst and inst.get('signal') == 'institutional_accumulation':
            summary_parts.append(f"institutional accumulation")
        if etf_hot:
            sectors = etf_hot.get('sectors', [])
            if sectors:
                summary_parts.append(f"ETF inflows: {sectors[0]}")
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
            'analyst_score': round(anlst_score, 1),
            'congress_score': round(cong_score, 1),
            'institutional_score': round(inst_score, 1),
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
            'analyst_action': anlst.get('action'),
            'congress_signal': cong.get('signal'),
            'institutional_signal': inst.get('signal'),

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
            'analyst_data': anlst,
            'congress_data': cong,
            'institutional_data': inst,
            'etf_flows_data': etf_hot,
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


# ── Short Candidates Scoring ───────────────────────────────────────

DEFAULT_SHORT_WEIGHTS = {
    'bearish_momentum': 0.25,
    'fundamentals': 0.15,
    'analyst_downgrades': 0.12,
    'bearish_options': 0.12,
    'insider_selling': 0.10,
    'institutional_dist': 0.08,
    'finviz_bearish': 0.08,
    'congress_selling': 0.05,
    'negative_news': 0.05,
    # Total: 1.00
}

MULTI_SOURCE_SHORT_BONUS = 4  # Extra points per additional bearish source beyond 1
SQUEEZE_PENALTY_POINTS = 15   # Penalty for crowded shorts (>20% short float)


def aggregate_short_scores(
    bearish_momentum_data: List[Dict],
    fundamentals_data: List[Dict],
    analyst_data: Optional[List[Dict]] = None,
    options_data: Optional[List[Dict]] = None,
    insider_data: Optional[List[Dict]] = None,
    institutional_data: Optional[List[Dict]] = None,
    finviz_data: Optional[Dict] = None,
    congress_data: Optional[List[Dict]] = None,
    news_data: Optional[List[Dict]] = None,
    short_interest_data: Optional[List[Dict]] = None,
    weights: Optional[Dict[str, float]] = None,
    min_score: float = 40,
    squeeze_penalty: bool = True,
) -> List[Dict]:
    """
    Aggregate bearish signals from multiple sources into short candidate scores.

    Uses inverted signal interpretation: selling = bullish for short thesis,
    buying = bearish for short thesis.

    Args:
        bearish_momentum_data: From scan_bearish_momentum()
        fundamentals_data: From scan_fundamentals()
        analyst_data: Existing analyst ratings (look for downgrades)
        options_data: Existing options activity (look for bearish sweeps)
        insider_data: Existing insider trading (look for sells)
        institutional_data: Existing institutional holdings (look for distribution)
        finviz_data: Existing finviz scores dict (look for losers, overbought)
        congress_data: Existing congress trading (look for selling)
        news_data: Existing news data (look for negative sentiment)
        short_interest_data: For squeeze risk detection
        weights: Custom weights (defaults to DEFAULT_SHORT_WEIGHTS)
        min_score: Minimum score to include in results
        squeeze_penalty: Whether to penalize crowded shorts

    Returns:
        List of dicts sorted by short_score descending
    """
    if weights is None:
        weights = DEFAULT_SHORT_WEIGHTS

    if analyst_data is None:
        analyst_data = []
    if options_data is None:
        options_data = []
    if insider_data is None:
        insider_data = []
    if institutional_data is None:
        institutional_data = []
    if finviz_data is None:
        finviz_data = {}
    if congress_data is None:
        congress_data = []
    if news_data is None:
        news_data = []
    if short_interest_data is None:
        short_interest_data = []

    # Build lookups
    bearish_mom_lookup = {d['ticker']: d for d in bearish_momentum_data}
    fund_lookup = {d['ticker']: d for d in fundamentals_data}
    analyst_lookup = {d['ticker']: d for d in analyst_data}
    options_lookup = {d['ticker']: d for d in options_data}
    insider_lookup = {d['ticker']: d for d in insider_data}
    inst_lookup = {d['ticker']: d for d in institutional_data}
    congress_lookup = {d['ticker']: d for d in congress_data}
    news_lookup = {d['ticker']: d for d in news_data}
    short_lookup = {d['ticker']: d for d in short_interest_data}

    # Finviz bearish signals: top_losers + overbought
    finviz_bearish_lookup = {}
    for stock in finviz_data.get('top_losers', []) if isinstance(finviz_data, dict) and 'top_losers' in finviz_data else []:
        ticker = stock.get('ticker', '')
        finviz_bearish_lookup[ticker] = {
            'score': min(abs(stock.get('change', 0)) * 5, 80),
            'signals': ['top_loser'],
        }
    for stock in finviz_data.get('overbought', []) if isinstance(finviz_data, dict) and 'overbought' in finviz_data else []:
        ticker = stock.get('ticker', '')
        if ticker in finviz_bearish_lookup:
            finviz_bearish_lookup[ticker]['score'] = min(finviz_bearish_lookup[ticker]['score'] + 20, 100)
            finviz_bearish_lookup[ticker]['signals'].append('overbought')
        else:
            finviz_bearish_lookup[ticker] = {'score': 60, 'signals': ['overbought']}

    # Collect all tickers with any bearish signal
    all_tickers = (
        set(bearish_mom_lookup.keys()) |
        set(fund_lookup.keys()) |
        {t for t, d in analyst_lookup.items() if d.get('action') in ('downgrade', 'pt_lower')} |
        {t for t, d in options_lookup.items() if d.get('signal') == 'bearish_sweep' or (d.get('put_call_ratio') or 0) > 1.5} |
        {t for t, d in insider_lookup.items() if not d.get('is_buy')} |
        {t for t, d in inst_lookup.items() if d.get('signal') == 'institutional_distribution'} |
        set(finviz_bearish_lookup.keys()) |
        {t for t, d in congress_lookup.items() if d.get('signal') == 'congress_selling'} |
        {t for t, d in news_lookup.items() if d.get('sentiment') == 'negative'}
    )

    results = []

    for ticker in all_tickers:
        bearish_signals = []
        source_scores = {}

        # 1. Bearish momentum
        bm = bearish_mom_lookup.get(ticker)
        bm_score = bm['score'] if bm else 0
        source_scores['bearish_momentum_score'] = round(bm_score, 1)
        if bm:
            bearish_signals.extend(bm.get('signals', []))

        # 2. Fundamentals
        fund = fund_lookup.get(ticker)
        fund_score = fund['score'] if fund else 0
        source_scores['fundamentals_score'] = round(fund_score, 1)
        if fund:
            bearish_signals.extend(fund.get('signals', []))

        # 3. Analyst downgrades
        anlst = analyst_lookup.get(ticker)
        anlst_short_score = 0
        if anlst and anlst.get('action') in ('downgrade', 'pt_lower'):
            anlst_short_score = anlst.get('score', 60)
            bearish_signals.append(f"analyst_{anlst['action']}")
        source_scores['analyst_short_score'] = round(anlst_short_score, 1)

        # 4. Bearish options (bearish sweeps, high put/call)
        opts = options_lookup.get(ticker)
        opts_short_score = 0
        if opts:
            if opts.get('signal') == 'bearish_sweep':
                opts_short_score = opts.get('score', 70)
                bearish_signals.append('bearish_sweep')
            elif (opts.get('put_call_ratio') or 0) > 1.5:
                opts_short_score = min(opts.get('put_call_ratio', 1.5) * 30, 80)
                bearish_signals.append('high_put_call')
        source_scores['options_short_score'] = round(opts_short_score, 1)

        # 5. Insider selling (cluster sells)
        insd = insider_lookup.get(ticker)
        insd_sell_score = 0
        if insd and not insd.get('is_buy'):
            insd_sell_score = insd.get('score', 60)
            val = insd.get('transaction_value', 0)
            if val > 1_000_000:
                insd_sell_score = min(insd_sell_score + 15, 100)
            bearish_signals.append('insider_selling')
        source_scores['insider_sell_score'] = round(insd_sell_score, 1)

        # 6. Institutional distribution
        inst = inst_lookup.get(ticker)
        inst_dist_score = 0
        if inst and inst.get('signal') == 'institutional_distribution':
            inst_dist_score = inst.get('score', 60)
            bearish_signals.append('institutional_distribution')
        source_scores['institutional_dist_score'] = round(inst_dist_score, 1)

        # 7. Finviz bearish
        fvz_bear = finviz_bearish_lookup.get(ticker)
        fvz_bear_score = fvz_bear['score'] if fvz_bear else 0
        source_scores['finviz_bearish_score'] = round(fvz_bear_score, 1)
        if fvz_bear:
            bearish_signals.extend(fvz_bear.get('signals', []))

        # 8. Congress selling
        cong = congress_lookup.get(ticker)
        cong_sell_score = 0
        if cong and cong.get('signal') == 'congress_selling':
            cong_sell_score = cong.get('score', 60)
            bearish_signals.append('congress_selling')
        source_scores['congress_sell_score'] = round(cong_sell_score, 1)

        # 9. Negative news
        news = news_lookup.get(ticker)
        news_neg_score = 0
        if news and news.get('sentiment') == 'negative':
            news_neg_score = news.get('score', 60)
            bearish_signals.append('negative_news')
        source_scores['negative_news_score'] = round(news_neg_score, 1)

        # Weighted combination
        short_score = (
            bm_score * weights.get('bearish_momentum', 0) +
            fund_score * weights.get('fundamentals', 0) +
            anlst_short_score * weights.get('analyst_downgrades', 0) +
            opts_short_score * weights.get('bearish_options', 0) +
            insd_sell_score * weights.get('insider_selling', 0) +
            inst_dist_score * weights.get('institutional_dist', 0) +
            fvz_bear_score * weights.get('finviz_bearish', 0) +
            cong_sell_score * weights.get('congress_selling', 0) +
            news_neg_score * weights.get('negative_news', 0)
        )

        # Multi-source bonus
        active_sources = sum(1 for v in source_scores.values() if v > 0)
        if active_sources > 1:
            short_score += (active_sources - 1) * MULTI_SOURCE_SHORT_BONUS

        # Squeeze risk penalty
        squeeze_warning = False
        si = short_lookup.get(ticker)
        if si and (si.get('short_float') or 0) > 20:
            squeeze_warning = True
            if squeeze_penalty:
                short_score -= SQUEEZE_PENALTY_POINTS

        short_score = max(0, round(short_score, 1))

        if short_score < min_score:
            continue

        # Build summary
        summary_parts = []
        if bm:
            summary_parts.append(bm.get('summary', ''))
        if fund:
            summary_parts.append(fund.get('summary', ''))
        if anlst_short_score > 0:
            firm = anlst.get('analyst_firm', '')
            summary_parts.append(f"{anlst['action']} by {firm}" if firm else anlst['action'])
        if insd_sell_score > 0:
            role = insd.get('role', 'insider')
            val = insd.get('transaction_value', 0)
            summary_parts.append(f"{role} sold ${val:,.0f}" if val else f"{role} sold")

        # Deduplicate signals
        unique_signals = list(dict.fromkeys(bearish_signals))

        results.append({
            'ticker': ticker,
            'short_score': short_score,
            'bearish_signals': unique_signals,
            'short_summary': '; '.join(s for s in summary_parts if s)[:120] or 'Bearish signals detected',
            'squeeze_warning': squeeze_warning,
            **source_scores,
        })

    results.sort(key=lambda x: x['short_score'], reverse=True)
    logger.info(f"Short candidates: {len(results)} stocks scored above {min_score}")
    return results
