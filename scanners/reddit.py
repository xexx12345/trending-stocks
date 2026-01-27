"""
Reddit Scanner - Tracks stock mentions on investing subreddits
Uses PRAW (Python Reddit API Wrapper)
"""

import os
import re
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

# Try to import praw, gracefully handle if not installed
try:
    import praw
    PRAW_AVAILABLE = True
except ImportError:
    PRAW_AVAILABLE = False
    logger.warning("PRAW not installed. Reddit scanning disabled.")

# Try to import textblob for sentiment
try:
    from textblob import TextBlob
    TEXTBLOB_AVAILABLE = True
except ImportError:
    TEXTBLOB_AVAILABLE = False

# Common stock tickers to look for (avoid false positives like "A", "IT", "DD")
VALID_TICKERS = set([
    "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "NVDA", "META", "TSLA", "AMD", "INTC",
    "JPM", "BAC", "WFC", "GS", "V", "MA", "PYPL", "SQ", "COIN", "HOOD",
    "GME", "AMC", "BB", "BBBY", "PLTR", "SOFI", "RIVN", "LCID", "NIO", "XPEV",
    "SPY", "QQQ", "IWM", "DIA", "VTI", "VOO", "ARKK", "TQQQ", "SQQQ",
    "MARA", "RIOT", "MSTR", "CLNE", "WISH", "CLOV", "SPCE", "DKNG", "PENN",
    "NET", "SNOW", "DDOG", "CRWD", "ZS", "OKTA", "TWLO", "SHOP", "SNAP",
    "DIS", "NFLX", "ROKU", "SPOT", "RBLX", "U", "MTCH",
    "XOM", "CVX", "COP", "OXY", "DVN", "FANG", "MRO", "APA",
    "LLY", "PFE", "MRNA", "BNTX", "JNJ", "ABBV", "MRK", "BMY",
    "F", "GM", "TM", "LCID", "RIVN", "FSR",
    "COST", "WMT", "TGT", "HD", "LOW", "SBUX", "MCD", "CMG",
    "BA", "LMT", "RTX", "NOC", "GD", "CAT", "DE",
    "CRM", "ORCL", "IBM", "SAP", "NOW", "ADBE", "INTU",
])

# Ticker pattern: $TICKER or standalone TICKER (3-5 uppercase letters)
TICKER_PATTERN = re.compile(r'\$([A-Z]{2,5})\b|\b([A-Z]{3,5})\b')


def get_reddit_client() -> Optional['praw.Reddit']:
    """Create and return a Reddit API client."""
    if not PRAW_AVAILABLE:
        return None

    client_id = os.environ.get('REDDIT_CLIENT_ID')
    client_secret = os.environ.get('REDDIT_CLIENT_SECRET')
    user_agent = os.environ.get('REDDIT_USER_AGENT', 'TrendingStocksScanner/1.0')

    if not client_id or not client_secret:
        logger.warning("Reddit API credentials not set. Set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET")
        return None

    try:
        reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent
        )
        return reddit
    except Exception as e:
        logger.error(f"Failed to create Reddit client: {e}")
        return None


def extract_tickers(text: str) -> List[str]:
    """Extract stock tickers from text."""
    matches = TICKER_PATTERN.findall(text.upper())
    tickers = []
    for match in matches:
        ticker = match[0] or match[1]  # Either $TICKER or TICKER
        if ticker in VALID_TICKERS:
            tickers.append(ticker)
    return list(set(tickers))


def analyze_sentiment(text: str) -> str:
    """Analyze sentiment of text. Returns 'bullish', 'bearish', or 'neutral'."""
    if not TEXTBLOB_AVAILABLE:
        return 'neutral'

    try:
        blob = TextBlob(text)
        polarity = blob.sentiment.polarity

        if polarity > 0.1:
            return 'bullish'
        elif polarity < -0.1:
            return 'bearish'
        else:
            return 'neutral'
    except:
        return 'neutral'


def scan_subreddit(reddit: 'praw.Reddit', subreddit_name: str,
                   time_filter: str = 'day', limit: int = 100) -> Dict[str, Dict]:
    """
    Scan a subreddit for stock mentions.
    Returns dict of ticker -> {count, sentiment, posts}
    """
    results = defaultdict(lambda: {'count': 0, 'bullish': 0, 'bearish': 0, 'neutral': 0, 'posts': []})

    try:
        subreddit = reddit.subreddit(subreddit_name)

        # Get hot and new posts
        posts = list(subreddit.hot(limit=limit)) + list(subreddit.new(limit=limit))

        for post in posts:
            # Combine title and selftext
            text = f"{post.title} {post.selftext}"
            tickers = extract_tickers(text)

            if not tickers:
                continue

            sentiment = analyze_sentiment(text)

            for ticker in tickers:
                results[ticker]['count'] += 1
                results[ticker][sentiment] += 1

                # Store post info (limit to avoid memory issues)
                if len(results[ticker]['posts']) < 5:
                    results[ticker]['posts'].append({
                        'title': post.title[:100],
                        'score': post.score,
                        'comments': post.num_comments,
                        'sentiment': sentiment
                    })

        logger.info(f"Scanned r/{subreddit_name}: found {len(results)} tickers")
        return dict(results)

    except Exception as e:
        logger.error(f"Error scanning r/{subreddit_name}: {e}")
        return {}


def scan_reddit(subreddits: Optional[List[str]] = None) -> List[Dict]:
    """
    Scan multiple subreddits for trending stocks.
    Returns list of stocks with mention data, sorted by count.
    """
    if subreddits is None:
        subreddits = ['wallstreetbets', 'stocks', 'investing', 'options']

    reddit = get_reddit_client()
    if not reddit:
        logger.warning("Reddit client not available, returning empty results")
        return []

    # Aggregate results across subreddits
    combined = defaultdict(lambda: {'count': 0, 'bullish': 0, 'bearish': 0, 'neutral': 0, 'subreddits': set()})

    for sub in subreddits:
        sub_results = scan_subreddit(reddit, sub)

        for ticker, data in sub_results.items():
            combined[ticker]['count'] += data['count']
            combined[ticker]['bullish'] += data['bullish']
            combined[ticker]['bearish'] += data['bearish']
            combined[ticker]['neutral'] += data['neutral']
            combined[ticker]['subreddits'].add(sub)

    # Convert to list and calculate sentiment score
    results = []
    for ticker, data in combined.items():
        total_sentiment = data['bullish'] + data['bearish'] + data['neutral']
        if total_sentiment > 0:
            sentiment_score = (data['bullish'] - data['bearish']) / total_sentiment
        else:
            sentiment_score = 0

        # Determine overall sentiment
        if sentiment_score > 0.2:
            sentiment = 'bullish'
        elif sentiment_score < -0.2:
            sentiment = 'bearish'
        else:
            sentiment = 'neutral'

        results.append({
            'ticker': ticker,
            'mentions': data['count'],
            'sentiment': sentiment,
            'sentiment_score': round(sentiment_score, 2),
            'bullish_count': data['bullish'],
            'bearish_count': data['bearish'],
            'subreddits': list(data['subreddits']),
            'score': min(100, data['count'] * 10 + sentiment_score * 20)  # Simple scoring
        })

    # Sort by mention count
    results.sort(key=lambda x: x['mentions'], reverse=True)

    logger.info(f"Reddit scan complete: {len(results)} tickers found")
    return results


def format_reddit_indicator(mentions: int, sentiment: str) -> str:
    """Convert reddit data to visual indicator."""
    base = ""
    if mentions >= 50:
        base = "+++"
    elif mentions >= 20:
        base = "++"
    elif mentions >= 5:
        base = "+"
    else:
        base = "-"

    # Add sentiment indicator
    if sentiment == 'bullish':
        return base + "B"
    elif sentiment == 'bearish':
        return base + "b"
    return base


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("\nREDDIT STOCK MENTIONS (Last 24h)")
    print("-" * 60)

    results = scan_reddit()

    if not results:
        print("No results - check Reddit API credentials")
    else:
        for i, stock in enumerate(results[:15], 1):
            subs = ', '.join(stock['subreddits'][:2])
            print(f"{i:2}. {stock['ticker']:6} | Mentions: {stock['mentions']:3} | "
                  f"Sentiment: {stock['sentiment']:8} | Subs: {subs}")
