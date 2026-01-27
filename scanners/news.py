"""
News Scanner - Identifies stocks appearing in financial news
Uses Yahoo Finance RSS/scraping (no API key required)
"""

import re
import requests
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)

# Try to import textblob for sentiment
try:
    from textblob import TextBlob
    TEXTBLOB_AVAILABLE = True
except ImportError:
    TEXTBLOB_AVAILABLE = False

# Try BeautifulSoup
try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
}

# Ticker to company name mapping for detection
COMPANY_NAMES = {
    "AAPL": ["Apple", "AAPL"],
    "MSFT": ["Microsoft", "MSFT"],
    "GOOGL": ["Google", "Alphabet", "GOOGL", "GOOG"],
    "AMZN": ["Amazon", "AMZN"],
    "NVDA": ["Nvidia", "NVDA"],
    "META": ["Meta", "Facebook", "META"],
    "TSLA": ["Tesla", "TSLA"],
    "AMD": ["AMD", "Advanced Micro"],
    "INTC": ["Intel", "INTC"],
    "JPM": ["JPMorgan", "JP Morgan", "JPM"],
    "BAC": ["Bank of America", "BofA", "BAC"],
    "GS": ["Goldman Sachs", "Goldman"],
    "V": ["Visa"],
    "MA": ["Mastercard"],
    "GME": ["GameStop", "GME"],
    "AMC": ["AMC Entertainment", "AMC"],
    "PLTR": ["Palantir", "PLTR"],
    "COIN": ["Coinbase", "COIN"],
    "RIVN": ["Rivian", "RIVN"],
    "LCID": ["Lucid", "LCID"],
    "NIO": ["NIO", "Nio"],
    "SOFI": ["SoFi", "SOFI"],
    "DIS": ["Disney", "DIS"],
    "NFLX": ["Netflix", "NFLX"],
    "CRM": ["Salesforce", "CRM"],
    "ORCL": ["Oracle", "ORCL"],
    "BA": ["Boeing", "BA"],
    "XOM": ["Exxon", "ExxonMobil", "XOM"],
    "CVX": ["Chevron", "CVX"],
    "PFE": ["Pfizer", "PFE"],
    "JNJ": ["Johnson & Johnson", "J&J", "JNJ"],
    "WMT": ["Walmart", "WMT"],
    "HD": ["Home Depot", "HD"],
    "COST": ["Costco", "COST"],
}

# News categories
NEWS_CATEGORIES = {
    'earnings': ['earnings', 'quarterly', 'revenue', 'profit', 'EPS', 'beat', 'miss'],
    'analyst': ['upgrade', 'downgrade', 'price target', 'rating', 'analyst'],
    'merger': ['merger', 'acquisition', 'acquire', 'M&A', 'buyout', 'deal'],
    'product': ['launch', 'release', 'new product', 'announce', 'unveil'],
    'legal': ['lawsuit', 'SEC', 'investigation', 'settlement', 'fine'],
    'executive': ['CEO', 'CFO', 'resign', 'appoint', 'hire', 'executive'],
}


def analyze_sentiment(text: str) -> str:
    """Analyze sentiment of text."""
    if not TEXTBLOB_AVAILABLE:
        return 'neutral'

    try:
        blob = TextBlob(text)
        polarity = blob.sentiment.polarity

        if polarity > 0.1:
            return 'positive'
        elif polarity < -0.1:
            return 'negative'
        else:
            return 'neutral'
    except:
        return 'neutral'


def categorize_article(text: str) -> str:
    """Categorize article based on keywords."""
    text_lower = text.lower()

    for category, keywords in NEWS_CATEGORIES.items():
        for keyword in keywords:
            if keyword.lower() in text_lower:
                return category

    return 'general'


def extract_tickers_from_text(text: str) -> List[str]:
    """Extract ticker symbols from article text."""
    tickers = []

    # Direct ticker mentions: $TICKER or (TICKER)
    ticker_pattern = re.compile(r'\$([A-Z]{2,5})\b|\(([A-Z]{2,5})\)')
    matches = ticker_pattern.findall(text)
    for match in matches:
        ticker = match[0] or match[1]
        if ticker in COMPANY_NAMES:
            tickers.append(ticker)

    # Company name mentions
    for ticker, names in COMPANY_NAMES.items():
        for name in names:
            if name.lower() in text.lower():
                tickers.append(ticker)
                break

    return list(set(tickers))


def fetch_yahoo_finance_news() -> List[Dict]:
    """
    Scrape trending news from Yahoo Finance.
    """
    if not BS4_AVAILABLE:
        logger.warning("BeautifulSoup not available for news scraping")
        return []

    articles = []

    try:
        # Main news page
        url = "https://finance.yahoo.com/topic/stock-market-news/"
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        # Find news items - Yahoo Finance uses various structures
        # Try multiple selectors
        news_items = soup.find_all('h3', limit=50)

        for item in news_items:
            link = item.find('a')
            if link and link.get_text(strip=True):
                title = link.get_text(strip=True)
                href = link.get('href', '')

                # Skip non-article links
                if not title or len(title) < 10:
                    continue

                articles.append({
                    'title': title,
                    'source': {'name': 'Yahoo Finance'},
                    'url': href,
                    'description': ''
                })

        # Also try the trending tickers section
        trending_url = "https://finance.yahoo.com/trending-tickers/"
        try:
            response2 = requests.get(trending_url, headers=HEADERS, timeout=10)
            soup2 = BeautifulSoup(response2.text, 'html.parser')

            # Find ticker rows
            for row in soup2.find_all('tr', limit=30):
                cells = row.find_all('td')
                if cells:
                    ticker_link = cells[0].find('a')
                    if ticker_link:
                        ticker = ticker_link.get_text(strip=True)
                        if ticker and 2 <= len(ticker) <= 5:
                            articles.append({
                                'title': f'{ticker} trending on Yahoo Finance',
                                'source': {'name': 'Yahoo Trending'},
                                'url': '',
                                'description': f'${ticker} is trending'
                            })
        except:
            pass

        logger.info(f"Fetched {len(articles)} articles from Yahoo Finance")
        return articles

    except Exception as e:
        logger.error(f"Failed to fetch Yahoo Finance news: {e}")
        return []


def fetch_marketwatch_headlines() -> List[Dict]:
    """Scrape headlines from MarketWatch."""
    if not BS4_AVAILABLE:
        return []

    articles = []

    try:
        url = "https://www.marketwatch.com/latest-news"
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        # Find headline elements
        for headline in soup.find_all(['h3', 'h2'], class_=lambda x: x and 'headline' in x.lower(), limit=30):
            link = headline.find('a')
            if link:
                title = link.get_text(strip=True)
                if title and len(title) > 10:
                    articles.append({
                        'title': title,
                        'source': {'name': 'MarketWatch'},
                        'url': link.get('href', ''),
                        'description': ''
                    })

        logger.info(f"Fetched {len(articles)} articles from MarketWatch")
        return articles

    except Exception as e:
        logger.debug(f"MarketWatch fetch failed: {e}")
        return []


def scan_news() -> List[Dict]:
    """
    Scan news sources for stock mentions.
    Returns list of stocks with news data, sorted by article count.
    """
    # Fetch from multiple sources
    articles = []
    articles.extend(fetch_yahoo_finance_news())
    articles.extend(fetch_marketwatch_headlines())

    if not articles:
        logger.warning("No news articles found from any source")
        return []

    # Aggregate by ticker
    ticker_news = defaultdict(lambda: {
        'count': 0,
        'positive': 0,
        'negative': 0,
        'neutral': 0,
        'categories': defaultdict(int),
        'headlines': []
    })

    seen_titles = set()  # Deduplication

    for article in articles:
        title = article.get('title', '')
        description = article.get('description', '') or ''

        # Skip duplicates
        title_key = title[:50].lower()
        if title_key in seen_titles:
            continue
        seen_titles.add(title_key)

        # Extract tickers
        text = f"{title} {description}"
        tickers = extract_tickers_from_text(text)

        if not tickers:
            continue

        sentiment = analyze_sentiment(text)
        category = categorize_article(text)

        for ticker in tickers:
            ticker_news[ticker]['count'] += 1
            ticker_news[ticker][sentiment] += 1
            ticker_news[ticker]['categories'][category] += 1

            if len(ticker_news[ticker]['headlines']) < 3:
                ticker_news[ticker]['headlines'].append({
                    'title': title[:100],
                    'sentiment': sentiment,
                    'category': category,
                    'source': article.get('source', {}).get('name', 'Unknown')
                })

    # Convert to list
    results = []
    for ticker, data in ticker_news.items():
        total_sentiment = data['positive'] + data['negative'] + data['neutral']
        if total_sentiment > 0:
            sentiment_score = (data['positive'] - data['negative']) / total_sentiment
        else:
            sentiment_score = 0

        # Determine overall sentiment
        if sentiment_score > 0.2:
            sentiment = 'positive'
        elif sentiment_score < -0.2:
            sentiment = 'negative'
        else:
            sentiment = 'neutral'

        # Top category
        top_category = max(data['categories'].items(), key=lambda x: x[1])[0] if data['categories'] else 'general'

        results.append({
            'ticker': ticker,
            'article_count': data['count'],
            'sentiment': sentiment,
            'sentiment_score': round(sentiment_score, 2),
            'top_category': top_category,
            'headlines': data['headlines'],
            'score': min(100, data['count'] * 15 + sentiment_score * 20)
        })

    # Sort by article count
    results.sort(key=lambda x: x['article_count'], reverse=True)

    logger.info(f"News scan complete: {len(results)} tickers in news")
    return results


def format_news_indicator(article_count: int, sentiment: str) -> str:
    """Convert news data to visual indicator."""
    if article_count >= 10:
        base = "+++"
    elif article_count >= 5:
        base = "++"
    elif article_count >= 2:
        base = "+"
    else:
        base = "-"

    return base


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("\nNEWS MENTIONS (Yahoo Finance + MarketWatch)")
    print("-" * 70)

    results = scan_news()

    if not results:
        print("No stock mentions found in news")
    else:
        for i, stock in enumerate(results[:15], 1):
            print(f"{i:2}. {stock['ticker']:6} | Articles: {stock['article_count']:2} | "
                  f"Sentiment: {stock['sentiment']:8} | Category: {stock['top_category']}")
            for headline in stock['headlines'][:1]:
                print(f"    -> {headline['title'][:60]}...")
