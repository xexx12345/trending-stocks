"""
Google Trends Scanner - Detect retail interest spikes via Google search trends.

Uses pytrends library to fetch rising/top queries for stock-related keywords.
"""

import logging
import time
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Default keywords to search for stock-related retail interest
DEFAULT_KEYWORDS = [
    "stock to buy",
    "best stocks",
    "trending stocks",
    "meme stocks",
]

# Delay between keyword batches to avoid rate limiting (seconds)
RATE_LIMIT_DELAY = 2.0

# Common stock-related words in queries that map to tickers
QUERY_TICKER_MAP = {
    'nvidia': 'NVDA',
    'tesla': 'TSLA',
    'apple': 'AAPL',
    'amazon': 'AMZN',
    'microsoft': 'MSFT',
    'google': 'GOOGL',
    'meta': 'META',
    'netflix': 'NFLX',
    'palantir': 'PLTR',
    'gamestop': 'GME',
    'amc': 'AMC',
    'bitcoin': 'BTC',
    'ethereum': 'ETH',
    'coinbase': 'COIN',
    'intel': 'INTC',
    'amd': 'AMD',
    'qualcomm': 'QCOM',
    'broadcom': 'AVGO',
    'micron': 'MU',
}


def _extract_tickers_from_query(query: str) -> set:
    """
    Extract tickers from a Google Trends query.

    Handles:
    - Standard $TICKER and uppercase TICKER patterns
    - Company name to ticker mapping (nvidia -> NVDA)
    - Potential ticker patterns in uppercase query text
    """
    from utils.ticker_blacklist import extract_tickers_from_text, is_valid_ticker
    import re

    tickers = set()
    query_lower = query.lower()

    # First try standard extraction
    tickers.update(extract_tickers_from_text(query))

    # Check for known company names
    for name, ticker in QUERY_TICKER_MAP.items():
        if name in query_lower:
            tickers.add(ticker)

    # Try extracting potential tickers from uppercase version
    # Look for 2-5 letter words that could be tickers
    query_upper = query.upper()
    words = re.findall(r'\b([A-Z]{2,5})\b', query_upper)
    for word in words:
        if is_valid_ticker(word, has_dollar_prefix=False):
            tickers.add(word)

    return tickers


def scan_google_trends(
    keywords: Optional[List[str]] = None,
    timeframe: str = 'now 7-d',
    geo: str = 'US',
) -> List[Dict]:
    """
    Scan Google Trends for stock-related queries and extract ticker mentions.

    Args:
        keywords: List of search terms to analyze (defaults to stock-related terms)
        timeframe: Google Trends timeframe (default: past 7 days)
        geo: Geographic region (default: US)

    Returns:
        List of dicts with ticker, score, trend_value, search_term, is_breakout
    """
    try:
        from pytrends.request import TrendReq
    except ImportError:
        logger.warning("pytrends not installed. Run: pip install pytrends")
        return []

    from utils.ticker_blacklist import extract_tickers_from_text, is_valid_ticker

    if keywords is None:
        keywords = DEFAULT_KEYWORDS

    # Initialize pytrends with compatibility workaround for urllib3 2.0+
    try:
        # Try without retry params first (works with newer urllib3)
        pytrends = TrendReq(hl='en-US', tz=360, timeout=(10, 25))
    except Exception as e:
        logger.warning(f"pytrends init with timeout failed: {e}, trying without")
        try:
            pytrends = TrendReq(hl='en-US', tz=360)
        except Exception as e2:
            logger.error(f"Failed to initialize pytrends: {e2}")
            return []

    # Collect all ticker mentions with their trend data
    ticker_data: Dict[str, Dict] = {}  # ticker -> {trend_values: [], search_terms: [], is_breakout: bool}

    for keyword in keywords:
        try:
            logger.debug(f"Fetching Google Trends for: {keyword}")

            # Build payload for single keyword
            pytrends.build_payload([keyword], cat=0, timeframe=timeframe, geo=geo)

            # Get related queries (rising and top)
            related = pytrends.related_queries()

            if not related or keyword not in related:
                logger.debug(f"No related queries for: {keyword}")
                time.sleep(RATE_LIMIT_DELAY)
                continue

            queries = related[keyword]

            # Process rising queries (more indicative of trending interest)
            rising = queries.get('rising')
            if rising is not None and not rising.empty:
                for _, row in rising.iterrows():
                    query_text = str(row.get('query', ''))
                    value = row.get('value', 0)

                    # Check if this is a "Breakout" (300%+ surge)
                    is_breakout = False
                    if isinstance(value, str) and 'Breakout' in value:
                        is_breakout = True
                        trend_value = 100  # Treat breakout as max value
                    else:
                        try:
                            trend_value = int(value)
                        except (ValueError, TypeError):
                            trend_value = 0

                    # Extract tickers from the query text
                    tickers = _extract_tickers_from_query(query_text)

                    for ticker in tickers:
                        if ticker not in ticker_data:
                            ticker_data[ticker] = {
                                'trend_values': [],
                                'search_terms': [],
                                'is_breakout': False,
                            }
                        ticker_data[ticker]['trend_values'].append(trend_value)
                        ticker_data[ticker]['search_terms'].append(query_text)
                        if is_breakout:
                            ticker_data[ticker]['is_breakout'] = True

            # Process top queries (stable interest)
            top = queries.get('top')
            if top is not None and not top.empty:
                for _, row in top.iterrows():
                    query_text = str(row.get('query', ''))
                    value = row.get('value', 0)

                    try:
                        trend_value = int(value)
                    except (ValueError, TypeError):
                        trend_value = 0

                    # Extract tickers from the query text
                    tickers = _extract_tickers_from_query(query_text)

                    for ticker in tickers:
                        if ticker not in ticker_data:
                            ticker_data[ticker] = {
                                'trend_values': [],
                                'search_terms': [],
                                'is_breakout': False,
                            }
                        # Only add if not already seen with higher value
                        if trend_value > 0:
                            ticker_data[ticker]['trend_values'].append(trend_value)
                            if query_text not in ticker_data[ticker]['search_terms']:
                                ticker_data[ticker]['search_terms'].append(query_text)

            # Rate limiting
            time.sleep(RATE_LIMIT_DELAY)

        except Exception as e:
            logger.warning(f"Error fetching trends for '{keyword}': {e}")
            time.sleep(RATE_LIMIT_DELAY)
            continue

    # Convert to result format
    results = []
    for ticker, data in ticker_data.items():
        if not data['trend_values']:
            continue

        # Calculate score: max trend value, with breakout bonus
        max_trend = max(data['trend_values'])
        avg_trend = sum(data['trend_values']) / len(data['trend_values'])

        # Normalize to 0-100 score
        # - Base: average of max and avg trend value
        # - Breakout bonus: +20 points
        # - Multi-mention bonus: +5 per additional mention (capped at +15)
        base_score = (max_trend + avg_trend) / 2
        breakout_bonus = 20 if data['is_breakout'] else 0
        mention_bonus = min((len(data['trend_values']) - 1) * 5, 15)

        score = min(100, base_score + breakout_bonus + mention_bonus)

        results.append({
            'ticker': ticker,
            'score': round(score, 1),
            'trend_value': max_trend,
            'search_term': data['search_terms'][0] if data['search_terms'] else '',
            'is_breakout': data['is_breakout'],
        })

    # Sort by score descending
    results.sort(key=lambda x: x['score'], reverse=True)

    logger.info(f"Google Trends scan found {len(results)} tickers")
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("\nGOOGLE TRENDS SCAN")
    print("-" * 50)

    results = scan_google_trends()

    if results:
        print(f"\nFound {len(results)} trending tickers:\n")
        print(f"{'Ticker':<8} {'Score':<8} {'Trend':<8} {'Breakout':<10} {'Search Term'}")
        print("-" * 70)
        for r in results[:15]:
            breakout = "YES" if r['is_breakout'] else "no"
            term = r['search_term'][:30] + "..." if len(r['search_term']) > 30 else r['search_term']
            print(f"{r['ticker']:<8} {r['score']:<8.1f} {r['trend_value']:<8} {breakout:<10} {term}")
    else:
        print("No trending tickers found (or pytrends rate limited)")
