"""
News Scanner - Identifies stocks appearing in financial news
Sources: RSS feeds (CNBC, Yahoo, Google News), yfinance ticker news, web scraping
No API keys required.
"""

import re
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Optional
import logging

from utils.ticker_blacklist import extract_tickers_from_text as blacklist_extract, is_valid_ticker

logger = logging.getLogger(__name__)

try:
    from textblob import TextBlob
    TEXTBLOB_AVAILABLE = True
except ImportError:
    TEXTBLOB_AVAILABLE = False

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

try:
    import yfinance as yf
    YF_AVAILABLE = True
except ImportError:
    YF_AVAILABLE = False

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
}

# RSS feed sources (no API key needed)
RSS_FEEDS = [
    ('https://www.cnbc.com/id/10001147/device/rss/rss.html', 'CNBC'),
    ('https://www.cnbc.com/id/15839069/device/rss/rss.html', 'CNBC Markets'),
    ('https://feeds.finance.yahoo.com/rss/2.0/headline?s=^GSPC&region=US&lang=en-US', 'Yahoo Finance RSS'),
    ('https://news.google.com/rss/search?q=stocks+market+when:1d&hl=en-US&gl=US&ceid=US:en', 'Google News Stocks'),
    ('https://news.google.com/rss/search?q=semiconductor+chip+stocks+when:1d&hl=en-US&gl=US&ceid=US:en', 'Google News Semis'),
    ('https://news.google.com/rss/search?q=gold+silver+mining+stocks+when:1d&hl=en-US&gl=US&ceid=US:en', 'Google News Metals'),
    ('https://news.google.com/rss/search?q=energy+oil+stocks+when:1d&hl=en-US&gl=US&ceid=US:en', 'Google News Energy'),
]

# Expanded ticker to company name mapping
COMPANY_NAMES = {
    # Mega-cap Tech
    "AAPL": ["Apple", "AAPL"],
    "MSFT": ["Microsoft", "MSFT"],
    "GOOGL": ["Google", "Alphabet", "GOOGL", "GOOG"],
    "AMZN": ["Amazon", "AMZN"],
    "META": ["Meta", "Facebook", "META"],
    "TSLA": ["Tesla", "TSLA"],
    "CRM": ["Salesforce", "CRM"],
    "ORCL": ["Oracle", "ORCL"],
    "NFLX": ["Netflix", "NFLX"],
    "DIS": ["Disney", "DIS"],

    # Semiconductors
    "NVDA": ["Nvidia", "NVDA"],
    "AMD": ["AMD", "Advanced Micro"],
    "INTC": ["Intel", "INTC"],
    "MU": ["Micron", "MU"],
    "AVGO": ["Broadcom", "AVGO"],
    "QCOM": ["Qualcomm", "QCOM"],
    "TSM": ["TSMC", "Taiwan Semi", "TSM"],
    "ASML": ["ASML"],
    "LRCX": ["Lam Research", "LRCX"],
    "AMAT": ["Applied Materials", "AMAT"],
    "KLAC": ["KLA", "KLAC"],
    "MRVL": ["Marvell", "MRVL"],
    "TXN": ["Texas Instruments", "TXN"],
    "ADI": ["Analog Devices", "ADI"],
    "ARM": ["Arm Holdings", "ARM"],
    "ON": ["ON Semiconductor", "ON Semi", "onsemi"],
    "NXPI": ["NXP", "NXPI"],
    "SMCI": ["Super Micro", "Supermicro", "SMCI"],
    "SMH": ["VanEck Semiconductor", "SMH"],
    "SOXX": ["iShares Semiconductor", "SOXX"],

    # Precious Metals / Mining
    "NEM": ["Newmont", "NEM"],
    "GOLD": ["Barrick Gold", "Barrick", "GOLD"],
    "AEM": ["Agnico Eagle", "AEM"],
    "WPM": ["Wheaton Precious", "WPM"],
    "FNV": ["Franco-Nevada", "FNV"],
    "AG": ["First Majestic", "First Majestic Silver"],
    "PAAS": ["Pan American Silver", "PAAS"],
    "KGC": ["Kinross Gold", "KGC"],
    "HL": ["Hecla Mining", "Hecla"],
    "SLV": ["iShares Silver", "SLV", "silver ETF"],
    "GLD": ["SPDR Gold", "GLD", "gold ETF"],
    "GDX": ["VanEck Gold Miners", "GDX"],
    "GDXJ": ["VanEck Junior Gold", "GDXJ"],

    # Finance
    "JPM": ["JPMorgan", "JP Morgan", "JPM"],
    "BAC": ["Bank of America", "BofA", "BAC"],
    "GS": ["Goldman Sachs", "Goldman"],
    "V": ["Visa"],
    "MA": ["Mastercard"],

    # Energy
    "XOM": ["Exxon", "ExxonMobil", "XOM"],
    "CVX": ["Chevron", "CVX"],
    "COP": ["ConocoPhillips", "Conoco"],
    "SLB": ["Schlumberger", "SLB"],
    "OXY": ["Occidental", "OXY"],

    # Healthcare / Biotech
    "PFE": ["Pfizer", "PFE"],
    "JNJ": ["Johnson & Johnson", "J&J", "JNJ"],
    "LLY": ["Eli Lilly", "Lilly", "LLY"],
    "MRNA": ["Moderna", "MRNA"],
    "ABBV": ["AbbVie", "ABBV"],

    # Consumer
    "WMT": ["Walmart", "WMT"],
    "HD": ["Home Depot", "HD"],
    "COST": ["Costco", "COST"],

    # Meme / Popular
    "GME": ["GameStop", "GME"],
    "AMC": ["AMC Entertainment", "AMC"],
    "PLTR": ["Palantir", "PLTR"],
    "COIN": ["Coinbase", "COIN"],
    "RIVN": ["Rivian", "RIVN"],
    "SOFI": ["SoFi", "SOFI"],
    "MSTR": ["MicroStrategy", "MSTR"],

    # Steel / Materials
    "CLF": ["Cleveland-Cliffs", "CLF"],
    "NUE": ["Nucor", "NUE"],
    "FCX": ["Freeport-McMoRan", "Freeport", "FCX"],
    "AA": ["Alcoa", "AA"],

    # Uranium / Nuclear
    "CCJ": ["Cameco", "CCJ"],
    "UEC": ["Uranium Energy", "UEC"],
    "SMR": ["NuScale", "SMR"],

    # Defense
    "BA": ["Boeing", "BA"],
    "LMT": ["Lockheed Martin", "Lockheed", "LMT"],
    "RTX": ["Raytheon", "RTX"],
    "NOC": ["Northrop Grumman", "Northrop", "NOC"],

    # China Tech
    "BABA": ["Alibaba", "BABA"],
    "JD": ["JD.com", "JD"],
    "PDD": ["PDD Holdings", "Pinduoduo", "PDD", "Temu"],
    "BIDU": ["Baidu", "BIDU"],
    "NIO": ["NIO", "Nio"],
}

# News categories
NEWS_CATEGORIES = {
    'earnings': ['earnings', 'quarterly', 'revenue', 'profit', 'EPS', 'beat', 'miss'],
    'analyst': ['upgrade', 'downgrade', 'price target', 'rating', 'analyst'],
    'merger': ['merger', 'acquisition', 'acquire', 'M&A', 'buyout', 'deal'],
    'product': ['launch', 'release', 'new product', 'announce', 'unveil'],
    'legal': ['lawsuit', 'SEC', 'investigation', 'settlement', 'fine'],
    'executive': ['CEO', 'CFO', 'resign', 'appoint', 'hire', 'executive'],
    'sector': ['semiconductor', 'chip', 'gold', 'silver', 'oil', 'energy', 'mining',
               'biotech', 'pharma', 'EV', 'electric vehicle', 'AI', 'artificial intelligence'],
}


def analyze_sentiment(text: str) -> str:
    if not TEXTBLOB_AVAILABLE:
        return 'neutral'
    try:
        polarity = TextBlob(text).sentiment.polarity
        if polarity > 0.1:
            return 'positive'
        elif polarity < -0.1:
            return 'negative'
        return 'neutral'
    except:
        return 'neutral'


def categorize_article(text: str) -> str:
    text_lower = text.lower()
    for category, keywords in NEWS_CATEGORIES.items():
        for keyword in keywords:
            if keyword.lower() in text_lower:
                return category
    return 'general'


def extract_tickers_from_text(text: str, ticker_hint: str = None) -> List[str]:
    """
    Extract ticker symbols from article text.

    Three-pass extraction:
    1. ticker_hint from yfinance — always trust (no gate)
    2. Blacklist-filtered pattern matching ($TICKER and standalone)
    3. Company name → ticker enrichment (COMPANY_NAMES, additive only)
    """
    tickers = set()

    # Pass 1: yfinance ticker hint — always trust
    if ticker_hint and ticker_hint.isalpha() and 1 <= len(ticker_hint) <= 5:
        tickers.add(ticker_hint.upper())

    # Pass 2: blacklist-filtered pattern matching
    tickers.update(blacklist_extract(text))

    # Pass 3: company name → ticker enrichment (additive)
    text_lower = text.lower()
    for ticker, names in COMPANY_NAMES.items():
        for name in names:
            if name.lower() in text_lower:
                tickers.add(ticker)
                break

    return list(tickers)


def fetch_rss_news(url: str, source_name: str) -> List[Dict]:
    """Fetch articles from an RSS feed. No API key required."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        root = ET.fromstring(response.content)

        articles = []
        # Standard RSS format: channel > item
        for item in root.iter('item'):
            title = item.findtext('title', '')
            desc = item.findtext('description', '')
            link = item.findtext('link', '')

            if title and len(title) > 5:
                articles.append({
                    'title': title.strip(),
                    'source': {'name': source_name},
                    'url': link,
                    'description': desc[:200] if desc else ''
                })

        logger.info(f"RSS [{source_name}]: {len(articles)} articles")
        return articles

    except Exception as e:
        logger.debug(f"RSS fetch failed for {source_name}: {e}")
        return []


def fetch_yfinance_ticker_news(tickers: List[str]) -> List[Dict]:
    """Fetch news for specific tickers using yfinance .news attribute."""
    if not YF_AVAILABLE:
        return []

    articles = []
    for ticker_sym in tickers[:30]:
        try:
            t = yf.Ticker(ticker_sym)
            news = t.news or []
            for item in news[:5]:
                title = item.get('title', '')
                if not title:
                    continue
                articles.append({
                    'title': title,
                    'source': {'name': item.get('publisher', 'yfinance')},
                    'url': item.get('link', ''),
                    'description': item.get('summary', '')[:200] if item.get('summary') else '',
                    '_ticker_hint': ticker_sym,
                })
        except Exception:
            continue

    logger.info(f"yfinance news: {len(articles)} articles from {min(len(tickers), 30)} tickers")
    return articles


def fetch_yahoo_finance_news() -> List[Dict]:
    """Scrape trending news from Yahoo Finance."""
    if not BS4_AVAILABLE:
        return []

    articles = []
    try:
        url = "https://finance.yahoo.com/topic/stock-market-news/"
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')
        for item in soup.find_all('h3', limit=50):
            link = item.find('a')
            if link and link.get_text(strip=True) and len(link.get_text(strip=True)) > 10:
                articles.append({
                    'title': link.get_text(strip=True),
                    'source': {'name': 'Yahoo Finance'},
                    'url': link.get('href', ''),
                    'description': ''
                })

        logger.info(f"Yahoo Finance HTML: {len(articles)} articles")
        return articles

    except Exception as e:
        logger.debug(f"Yahoo Finance fetch failed: {e}")
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
        for headline in soup.find_all(['h3', 'h2'],
                                       class_=lambda x: x and 'headline' in x.lower(),
                                       limit=30):
            link = headline.find('a')
            if link and link.get_text(strip=True) and len(link.get_text(strip=True)) > 10:
                articles.append({
                    'title': link.get_text(strip=True),
                    'source': {'name': 'MarketWatch'},
                    'url': link.get('href', ''),
                    'description': ''
                })

        logger.info(f"MarketWatch: {len(articles)} articles")
        return articles

    except Exception as e:
        logger.debug(f"MarketWatch fetch failed: {e}")
        return []


def scan_news(theme_tickers: Optional[List[str]] = None) -> List[Dict]:
    """
    Scan news sources for stock mentions.
    Returns list of stocks with news data, sorted by article count.
    """
    articles = []

    # 1. RSS feeds (highest yield, most reliable)
    for url, name in RSS_FEEDS:
        articles.extend(fetch_rss_news(url, name))

    # 2. yfinance ticker-specific news (targeted)
    if theme_tickers:
        articles.extend(fetch_yfinance_ticker_news(theme_tickers))

    # 3. Web scraping fallbacks
    articles.extend(fetch_yahoo_finance_news())
    articles.extend(fetch_marketwatch_headlines())

    logger.info(f"Total articles collected: {len(articles)}")

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

    seen_titles = set()

    for article in articles:
        title = article.get('title', '')
        description = article.get('description', '') or ''
        ticker_hint = article.get('_ticker_hint')

        # Deduplication
        title_key = title[:50].lower()
        if title_key in seen_titles:
            continue
        seen_titles.add(title_key)

        # Extract tickers
        text = f"{title} {description}"
        tickers = extract_tickers_from_text(text, ticker_hint)

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

        if sentiment_score > 0.2:
            sentiment = 'positive'
        elif sentiment_score < -0.2:
            sentiment = 'negative'
        else:
            sentiment = 'neutral'

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

    results.sort(key=lambda x: x['article_count'], reverse=True)

    logger.info(f"News scan complete: {len(results)} tickers in news")
    return results


def format_news_indicator(article_count: int, sentiment: str) -> str:
    if article_count >= 10:
        return "+++"
    elif article_count >= 5:
        return "++"
    elif article_count >= 2:
        return "+"
    return "-"


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("\nNEWS MENTIONS (RSS + yfinance + Scraping)")
    print("-" * 70)

    results = scan_news(theme_tickers=['NVDA', 'AMD', 'MU', 'SMH', 'SLV', 'GDX', 'NEM', 'AG'])

    if not results:
        print("No stock mentions found in news")
    else:
        for i, stock in enumerate(results[:20], 1):
            print(f"{i:2}. {stock['ticker']:6} | Articles: {stock['article_count']:2} | "
                  f"Sentiment: {stock['sentiment']:8} | Category: {stock['top_category']}")
            for headline in stock['headlines'][:1]:
                print(f"    -> {headline['title'][:70]}...")
