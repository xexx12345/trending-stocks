"""
Short Interest Scanner - Detect squeeze setups via short interest data from FinViz.

Scrapes short float % and days-to-cover (short ratio) to identify potential squeeze candidates.
"""

import logging
import random
import re
import time
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# User agents for rotation to avoid blocks
USER_AGENTS = [
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
]

# Delay between requests to avoid rate limiting (seconds)
REQUEST_DELAY = 0.5

# Batch size for processing tickers
BATCH_SIZE = 50


def _get_headers() -> Dict[str, str]:
    """Get request headers with randomized user agent."""
    return {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive',
    }


def _parse_percentage(text: str) -> Optional[float]:
    """Parse a percentage string like '15.23%' to float 15.23."""
    if not text or text == '-':
        return None
    try:
        cleaned = text.replace('%', '').replace(',', '').strip()
        return float(cleaned)
    except (ValueError, AttributeError):
        return None


def _parse_float(text: str) -> Optional[float]:
    """Parse a float string like '3.45' to float."""
    if not text or text == '-':
        return None
    try:
        return float(text.replace(',', '').strip())
    except (ValueError, AttributeError):
        return None


def _calculate_squeeze_score(short_float: Optional[float], short_ratio: Optional[float]) -> float:
    """
    Calculate squeeze potential score (0-100).

    Scoring logic:
    - Base: short_float * 2 (10% float = 20 points, 25% = 50 points)
    - Days-to-cover bonus: +10 if > 5 days, +20 if > 10 days
    - Cap at 100
    """
    if short_float is None:
        return 0.0

    # Base score from short float percentage
    base_score = short_float * 2

    # Days-to-cover bonus
    dtc_bonus = 0
    if short_ratio is not None:
        if short_ratio > 10:
            dtc_bonus = 20
        elif short_ratio > 5:
            dtc_bonus = 10

    return min(100.0, base_score + dtc_bonus)


def _get_squeeze_risk(short_float: Optional[float], short_ratio: Optional[float]) -> str:
    """
    Categorize squeeze risk level.

    - High: >20% short float OR >10 days to cover
    - Medium: >10% short float OR >5 days to cover
    - Low: everything else
    """
    if short_float is None:
        return 'low'

    if short_float > 20 or (short_ratio is not None and short_ratio > 10):
        return 'high'
    elif short_float > 10 or (short_ratio is not None and short_ratio > 5):
        return 'medium'
    else:
        return 'low'


def fetch_short_interest(ticker: str) -> Optional[Dict]:
    """
    Fetch short interest data for a single ticker from FinViz.

    Args:
        ticker: Stock ticker symbol

    Returns:
        Dict with short_float, short_ratio, squeeze_score, squeeze_risk, or None if failed
    """
    url = f"https://finviz.com/quote.ashx?t={ticker}"

    try:
        response = requests.get(url, headers=_get_headers(), timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        short_float = None
        short_ratio = None

        # Find the snapshot table with stock metrics
        # FinViz uses a table with class "snapshot-table2"
        tables = soup.find_all('table', class_='snapshot-table2')

        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all('td')
                # Cells alternate: label, value, label, value, ...
                for i in range(0, len(cells) - 1, 2):
                    label = cells[i].get_text(strip=True).lower()
                    value = cells[i + 1].get_text(strip=True)

                    if 'short float' in label:
                        short_float = _parse_percentage(value)
                    elif 'short ratio' in label:
                        short_ratio = _parse_float(value)

        # If we couldn't find in snapshot-table2, try generic approach
        if short_float is None:
            # Look for any table cell containing "Short Float"
            all_cells = soup.find_all('td')
            for i, cell in enumerate(all_cells):
                text = cell.get_text(strip=True).lower()
                if 'short float' in text and i + 1 < len(all_cells):
                    short_float = _parse_percentage(all_cells[i + 1].get_text(strip=True))
                elif 'short ratio' in text and i + 1 < len(all_cells):
                    short_ratio = _parse_float(all_cells[i + 1].get_text(strip=True))

        # Calculate score even if data is partial
        score = _calculate_squeeze_score(short_float, short_ratio)
        risk = _get_squeeze_risk(short_float, short_ratio)

        return {
            'ticker': ticker,
            'short_float': short_float,
            'short_ratio': short_ratio,
            'score': round(score, 1),
            'squeeze_risk': risk,
        }

    except requests.RequestException as e:
        logger.debug(f"Failed to fetch short interest for {ticker}: {e}")
        return None
    except Exception as e:
        logger.debug(f"Error parsing short interest for {ticker}: {e}")
        return None


def scan_short_interest(
    tickers: List[str],
    min_short_float: float = 5.0,
) -> List[Dict]:
    """
    Scan multiple tickers for short interest data.

    Args:
        tickers: List of ticker symbols to analyze
        min_short_float: Minimum short float % to include in results (default: 5%)

    Returns:
        List of dicts with ticker, score, short_float, short_ratio, squeeze_risk
    """
    if not tickers:
        return []

    results = []
    processed = 0
    total = len(tickers)

    logger.info(f"Scanning short interest for {total} tickers...")

    for i, ticker in enumerate(tickers):
        try:
            data = fetch_short_interest(ticker)

            if data:
                # Only include if short float meets minimum threshold
                if data['short_float'] is not None and data['short_float'] >= min_short_float:
                    results.append(data)
                elif data['short_float'] is None:
                    # Include tickers where we couldn't get data (for completeness)
                    # They'll have score=0 and won't affect ranking much
                    pass

            processed += 1

            # Progress logging every 20 tickers
            if processed % 20 == 0:
                logger.debug(f"Short interest scan progress: {processed}/{total}")

            # Rate limiting
            time.sleep(REQUEST_DELAY)

        except Exception as e:
            logger.debug(f"Error processing {ticker}: {e}")
            continue

    # Sort by score descending
    results.sort(key=lambda x: x['score'], reverse=True)

    logger.info(f"Short interest scan found {len(results)} tickers with >={min_short_float}% short float")
    return results


def get_high_short_interest_tickers() -> List[str]:
    """
    Get a list of known high-short-interest tickers from FinViz screener.
    Useful as a starting point for discovery.
    """
    url = "https://finviz.com/screener.ashx?v=111&f=sh_short_o30&o=-shortinterestshare"

    try:
        response = requests.get(url, headers=_get_headers(), timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')
        tickers = []

        for row in soup.find_all('tr'):
            cols = row.find_all('td')
            if len(cols) >= 2:
                ticker_col = cols[1]
                ticker_link = ticker_col.find('a')
                if ticker_link and ticker_link.get('href', '').startswith('quote.ashx'):
                    ticker = ticker_link.get_text(strip=True)
                    if ticker and ticker.isalpha() and len(ticker) <= 5:
                        tickers.append(ticker)
                        if len(tickers) >= 50:
                            break

        logger.info(f"Found {len(tickers)} high-short-interest tickers from screener")
        return tickers

    except Exception as e:
        logger.warning(f"Failed to fetch high short interest list: {e}")
        return []


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("\nSHORT INTEREST SCAN")
    print("-" * 50)

    # Test with some known high-short stocks
    test_tickers = ['GME', 'AMC', 'TSLA', 'AAPL', 'NVDA', 'BBBY', 'SPCE', 'RIVN', 'LCID']

    results = scan_short_interest(test_tickers, min_short_float=0)

    if results:
        print(f"\nShort Interest Data:\n")
        print(f"{'Ticker':<8} {'Score':<8} {'Short%':<10} {'DTC':<8} {'Risk'}")
        print("-" * 50)
        for r in results:
            sf = f"{r['short_float']:.1f}%" if r['short_float'] else "N/A"
            sr = f"{r['short_ratio']:.1f}" if r['short_ratio'] else "N/A"
            print(f"{r['ticker']:<8} {r['score']:<8.1f} {sf:<10} {sr:<8} {r['squeeze_risk']}")
    else:
        print("No short interest data found")
