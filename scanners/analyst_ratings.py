"""
Analyst Ratings Scanner

Tracks Wall Street analyst upgrades, downgrades, and price target changes.
Uses FinViz and Yahoo Finance as data sources (FREE).

Signal Value:
- Upgrades from multiple analysts = bullish consensus shift
- Price target increases = Wall Street sees higher fair value
- Initiations at Buy/Strong Buy = new coverage with conviction
"""

import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import time
import re

# Headers to mimic browser
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
}


def scan_analyst_ratings(days_back: int = 7) -> List[Dict]:
    """
    Scan for recent analyst rating changes.

    Returns list of stocks with recent upgrades/downgrades.
    """
    print("  [Analyst] Fetching analyst ratings...")

    results = []

    # Source 1: FinViz analyst ratings
    finviz_ratings = fetch_finviz_ratings()
    results.extend(finviz_ratings)

    # Deduplicate by ticker, keeping the one with more data
    ticker_map = {}
    for r in results:
        ticker = r.get('ticker', '')
        if ticker not in ticker_map:
            ticker_map[ticker] = r
        else:
            # Keep the one with higher score
            if r.get('score', 0) > ticker_map[ticker].get('score', 0):
                ticker_map[ticker] = r

    results = list(ticker_map.values())

    # Sort by score
    results.sort(key=lambda x: x.get('score', 0), reverse=True)

    print(f"  [Analyst] Found {len(results)} stocks with recent analyst activity")

    return results


def fetch_finviz_ratings() -> List[Dict]:
    """
    Fetch analyst ratings from FinViz.
    """
    results = []

    try:
        # FinViz news page shows analyst ratings
        url = "https://finviz.com/news.ashx"
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        # Find analyst rating news items
        # FinViz shows ratings in their news feed with specific patterns
        news_table = soup.find('table', {'id': 'news'})
        if not news_table:
            # Try alternate layout
            news_table = soup.find('table', class_='t-home-table')

        if news_table:
            rows = news_table.find_all('tr')
            for row in rows[:100]:  # Check first 100 news items
                cells = row.find_all('td')
                if len(cells) >= 2:
                    headline = cells[-1].get_text(strip=True)

                    # Look for analyst rating patterns
                    rating_info = parse_analyst_headline(headline)
                    if rating_info:
                        results.append(rating_info)

        # Also fetch from FinViz screener for stocks with recent upgrades
        upgrade_stocks = fetch_finviz_upgrades()
        results.extend(upgrade_stocks)

    except Exception as e:
        print(f"  [Analyst] Warning: FinViz fetch failed: {e}")

    return results


def fetch_finviz_upgrades() -> List[Dict]:
    """
    Fetch stocks with recent analyst upgrades from FinViz screener.
    """
    results = []

    try:
        # FinViz screener for stocks with analyst upgrades
        url = "https://finviz.com/screener.ashx?v=111&f=an_recom_buy&o=-change"
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        # Find the screener table
        table = soup.find('table', class_='table-light')
        if table:
            rows = table.find_all('tr')[1:]  # Skip header

            for row in rows[:30]:  # Top 30
                cells = row.find_all('td')
                if len(cells) >= 10:
                    ticker = cells[1].get_text(strip=True)
                    company = cells[2].get_text(strip=True)

                    # Get recommendation
                    recom = cells[7].get_text(strip=True) if len(cells) > 7 else ""

                    score = calculate_rating_score(
                        action='buy_rating',
                        old_rating=None,
                        new_rating=recom
                    )

                    if score > 50:
                        results.append({
                            'ticker': ticker,
                            'company': company,
                            'score': score,
                            'action': 'Strong Analyst Buy Rating',
                            'new_rating': recom,
                            'source': 'finviz_screener'
                        })

    except Exception as e:
        print(f"  [Analyst] Warning: FinViz screener failed: {e}")

    return results


def parse_analyst_headline(headline: str) -> Optional[Dict]:
    """
    Parse an analyst rating headline to extract actionable info.

    Examples:
    - "Morgan Stanley Upgrades NVDA to Overweight"
    - "Goldman Initiates AAPL at Buy, $200 PT"
    - "JPMorgan Downgrades TSLA to Neutral"
    """
    headline_lower = headline.lower()

    # Check if this is an analyst rating headline
    rating_keywords = ['upgrade', 'downgrade', 'initiate', 'reiterate',
                       'raise', 'lower', 'target', 'rating', 'buy', 'sell',
                       'overweight', 'underweight', 'outperform', 'underperform']

    if not any(kw in headline_lower for kw in rating_keywords):
        return None

    # Extract ticker (usually in all caps, 1-5 letters)
    ticker_match = re.search(r'\b([A-Z]{1,5})\b', headline)
    if not ticker_match:
        return None

    ticker = ticker_match.group(1)

    # Skip common words that look like tickers
    skip_words = {'A', 'I', 'AT', 'TO', 'BY', 'ON', 'IN', 'IT', 'OR', 'AN',
                  'AS', 'PT', 'CEO', 'CFO', 'IPO', 'FDA', 'SEC', 'NYSE', 'USA'}
    if ticker in skip_words:
        # Try to find another ticker
        all_matches = re.findall(r'\b([A-Z]{2,5})\b', headline)
        valid_tickers = [t for t in all_matches if t not in skip_words]
        if valid_tickers:
            ticker = valid_tickers[0]
        else:
            return None

    # Determine action type
    action = 'rating_change'
    sentiment = 'neutral'

    if 'upgrade' in headline_lower:
        action = 'upgrade'
        sentiment = 'bullish'
    elif 'downgrade' in headline_lower:
        action = 'downgrade'
        sentiment = 'bearish'
    elif 'initiate' in headline_lower or 'initiation' in headline_lower:
        action = 'initiation'
        if any(w in headline_lower for w in ['buy', 'overweight', 'outperform']):
            sentiment = 'bullish'
        elif any(w in headline_lower for w in ['sell', 'underweight', 'underperform']):
            sentiment = 'bearish'
    elif 'raise' in headline_lower and 'target' in headline_lower:
        action = 'pt_raise'
        sentiment = 'bullish'
    elif 'lower' in headline_lower and 'target' in headline_lower:
        action = 'pt_lower'
        sentiment = 'bearish'

    # Extract price target if present
    pt_match = re.search(r'\$(\d+(?:\.\d+)?)', headline)
    price_target = float(pt_match.group(1)) if pt_match else None

    # Extract analyst firm (usually at the start)
    firms = ['morgan stanley', 'goldman', 'jpmorgan', 'jp morgan', 'bank of america',
             'bofa', 'citigroup', 'citi', 'wells fargo', 'barclays', 'credit suisse',
             'ubs', 'deutsche bank', 'hsbc', 'rbc', 'td securities', 'jefferies',
             'raymond james', 'piper sandler', 'wedbush', 'needham', 'oppenheimer',
             'bernstein', 'cowen', 'stifel', 'truist', 'mizuho', 'bmo', 'canaccord']

    analyst_firm = None
    for firm in firms:
        if firm in headline_lower:
            analyst_firm = firm.title()
            break

    score = calculate_rating_score(action, None, sentiment)

    return {
        'ticker': ticker,
        'score': score,
        'action': action,
        'sentiment': sentiment,
        'analyst_firm': analyst_firm,
        'price_target': price_target,
        'headline': headline[:200],
        'source': 'finviz_news'
    }


def calculate_rating_score(action: str, old_rating: Optional[str],
                          new_rating: Optional[str]) -> float:
    """
    Calculate a score (0-100) based on analyst action.

    Scoring:
    - Upgrade: +25 base
    - Initiation at Buy: +20
    - PT raise: +15
    - Multiple analysts: +10 each
    - Top-tier firm: +10
    - Downgrade: -15
    - PT lower: -10
    """
    score = 50.0  # Base score

    if action == 'upgrade':
        score += 25
    elif action == 'initiation':
        if new_rating in ['bullish', 'buy', 'overweight', 'outperform']:
            score += 20
        elif new_rating in ['bearish', 'sell', 'underweight', 'underperform']:
            score -= 15
    elif action == 'pt_raise':
        score += 15
    elif action == 'downgrade':
        score -= 15
    elif action == 'pt_lower':
        score -= 10
    elif action == 'buy_rating':
        # From screener - stock has buy rating
        score += 15

    # Sentiment adjustment
    if new_rating == 'bullish':
        score += 5
    elif new_rating == 'bearish':
        score -= 5

    return min(100, max(0, score))


if __name__ == "__main__":
    ratings = scan_analyst_ratings()
    print(f"\nFound {len(ratings)} analyst rating changes:")
    for r in ratings[:10]:
        print(f"  {r['ticker']}: {r.get('action', 'N/A')} - Score: {r['score']:.1f}")
        if r.get('analyst_firm'):
            print(f"    Firm: {r['analyst_firm']}")
        if r.get('price_target'):
            print(f"    PT: ${r['price_target']}")
