"""
Congressional Trading Scanner

Tracks stock trades by US Congress members (public STOCK Act filings).
Uses Capitol Trades / House/Senate disclosure data (FREE).

Signal Value:
- Politicians often have access to non-public information
- Cluster buying by multiple members = potential insider knowledge
- Large purchases before major legislation = high conviction
- Studies show congressional trades outperform market

Data Source:
- House: https://disclosures-clerk.house.gov/
- Senate: https://efdsearch.senate.gov/
- Aggregators: Capitol Trades, Quiver Quantitative
"""

import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import time
import re
import json

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
}


def scan_congress_trading(days_back: int = 30) -> List[Dict]:
    """
    Scan for recent congressional stock trades.

    Returns list of stocks recently traded by Congress members.
    """
    print("  [Congress] Fetching congressional trading data...")

    results = []

    # Try multiple sources
    quiver_data = fetch_quiver_congress()
    results.extend(quiver_data)

    # Aggregate by ticker
    ticker_trades = {}
    for trade in results:
        ticker = trade.get('ticker', '')
        if not ticker:
            continue

        if ticker not in ticker_trades:
            ticker_trades[ticker] = {
                'ticker': ticker,
                'trades': [],
                'buy_count': 0,
                'sell_count': 0,
                'total_value': 0,
                'politicians': set()
            }

        ticker_trades[ticker]['trades'].append(trade)
        ticker_trades[ticker]['politicians'].add(trade.get('politician', 'Unknown'))

        if trade.get('transaction_type', '').lower() in ['buy', 'purchase']:
            ticker_trades[ticker]['buy_count'] += 1
        else:
            ticker_trades[ticker]['sell_count'] += 1

        # Estimate value (ranges are given, take midpoint)
        value = trade.get('amount_midpoint', 0)
        ticker_trades[ticker]['total_value'] += value

    # Calculate scores
    final_results = []
    for ticker, data in ticker_trades.items():
        score = calculate_congress_score(
            buy_count=data['buy_count'],
            sell_count=data['sell_count'],
            politician_count=len(data['politicians']),
            total_value=data['total_value']
        )

        # Determine overall signal
        if data['buy_count'] > data['sell_count']:
            signal = 'congress_buying'
        elif data['sell_count'] > data['buy_count']:
            signal = 'congress_selling'
        else:
            signal = 'mixed'

        final_results.append({
            'ticker': ticker,
            'score': score,
            'signal': signal,
            'buy_count': data['buy_count'],
            'sell_count': data['sell_count'],
            'politician_count': len(data['politicians']),
            'politicians': list(data['politicians'])[:5],  # Top 5
            'total_value_estimate': data['total_value'],
            'recent_trades': data['trades'][:5]  # Most recent 5
        })

    # Sort by score
    final_results.sort(key=lambda x: x['score'], reverse=True)

    print(f"  [Congress] Found {len(final_results)} stocks with congressional trading activity")

    return final_results


def fetch_quiver_congress() -> List[Dict]:
    """
    Fetch congressional trading data from Quiver Quantitative.
    They provide free access to STOCK Act filings.
    """
    results = []

    try:
        # Quiver has a public API for congressional trades
        url = "https://api.quiverquant.com/beta/live/congresstrading"

        # Try without auth first (limited data)
        response = requests.get(url, headers=HEADERS, timeout=15)

        if response.status_code == 200:
            try:
                data = response.json()
                for trade in data[:100]:  # Recent 100 trades
                    results.append(parse_quiver_trade(trade))
            except:
                pass
        else:
            # Fallback: scrape their public page
            results = scrape_congress_trades_fallback()

    except Exception as e:
        print(f"  [Congress] Quiver API failed: {e}, trying fallback...")
        results = scrape_congress_trades_fallback()

    return results


def scrape_congress_trades_fallback() -> List[Dict]:
    """
    Fallback scraper for congressional trades from public sources.
    """
    results = []

    try:
        # Try Capitol Trades (public page)
        url = "https://www.capitoltrades.com/trades"
        response = requests.get(url, headers=HEADERS, timeout=15)

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')

            # Find trade table
            trade_rows = soup.find_all('tr', class_='q-tr')
            if not trade_rows:
                trade_rows = soup.find_all('tr')[1:51]  # Skip header, get 50 rows

            for row in trade_rows:
                trade = parse_capitol_trades_row(row)
                if trade:
                    results.append(trade)

    except Exception as e:
        print(f"  [Congress] Fallback scrape failed: {e}")

    # If still no results, use known recent trades as example data
    if not results:
        results = get_sample_congress_data()

    return results


def parse_quiver_trade(trade: dict) -> Dict:
    """Parse a trade from Quiver Quantitative API."""
    # Parse amount range to midpoint
    amount_str = trade.get('Range', '$0')
    amount_midpoint = parse_amount_range(amount_str)

    return {
        'ticker': trade.get('Ticker', ''),
        'politician': trade.get('Representative', ''),
        'party': trade.get('Party', ''),
        'chamber': trade.get('House', ''),  # House or Senate
        'transaction_type': trade.get('Transaction', ''),
        'amount_range': amount_str,
        'amount_midpoint': amount_midpoint,
        'trade_date': trade.get('TransactionDate', ''),
        'disclosure_date': trade.get('ReportDate', ''),
        'source': 'quiver'
    }


def parse_capitol_trades_row(row) -> Optional[Dict]:
    """Parse a trade row from Capitol Trades website."""
    try:
        cells = row.find_all('td')
        if len(cells) < 5:
            return None

        # Extract ticker from the row
        ticker_elem = row.find('span', class_='q-field-ticker') or row.find('a', class_='ticker')
        if not ticker_elem:
            # Try to find any element with ticker-like text
            for cell in cells:
                text = cell.get_text(strip=True)
                if re.match(r'^[A-Z]{1,5}$', text):
                    ticker = text
                    break
            else:
                return None
        else:
            ticker = ticker_elem.get_text(strip=True)

        # Extract politician name
        politician_elem = row.find('a', class_='politician-name') or cells[0]
        politician = politician_elem.get_text(strip=True)[:50]

        # Extract transaction type
        tx_type = 'unknown'
        row_text = row.get_text().lower()
        if 'purchase' in row_text or 'buy' in row_text:
            tx_type = 'buy'
        elif 'sale' in row_text or 'sell' in row_text:
            tx_type = 'sell'

        # Extract amount
        amount_midpoint = 50000  # Default estimate
        for cell in cells:
            text = cell.get_text()
            if '$' in text:
                amount_midpoint = parse_amount_range(text)
                break

        return {
            'ticker': ticker,
            'politician': politician,
            'party': '',
            'chamber': '',
            'transaction_type': tx_type,
            'amount_range': '',
            'amount_midpoint': amount_midpoint,
            'trade_date': '',
            'source': 'capitol_trades'
        }

    except Exception:
        return None


def parse_amount_range(amount_str: str) -> float:
    """
    Parse amount range string to midpoint value.
    Examples: "$1,001 - $15,000" -> 8000
              "$50,001 - $100,000" -> 75000
    """
    try:
        # Find all dollar amounts
        amounts = re.findall(r'\$?([\d,]+)', amount_str.replace(',', ''))
        if len(amounts) >= 2:
            low = float(amounts[0])
            high = float(amounts[1])
            return (low + high) / 2
        elif len(amounts) == 1:
            return float(amounts[0])
    except:
        pass

    return 50000  # Default midpoint


def calculate_congress_score(buy_count: int, sell_count: int,
                            politician_count: int, total_value: float) -> float:
    """
    Calculate score based on congressional trading activity.

    Scoring:
    - Net buying: +20 base
    - Multiple politicians buying: +10 per politician (max +30)
    - Large total value (>$500k): +15
    - Net selling: -10
    - Cluster (3+ politicians): +20
    """
    score = 50.0

    # Net direction
    net_buys = buy_count - sell_count
    if net_buys > 0:
        score += 15 + min(net_buys * 5, 15)  # +15 to +30 for buying
    elif net_buys < 0:
        score -= 10  # Selling is less informative (could be diversification)

    # Multiple politicians (cluster signal)
    if politician_count >= 3:
        score += 20  # Strong cluster signal
    elif politician_count == 2:
        score += 10

    # Value-based adjustment
    if total_value >= 500000:
        score += 15
    elif total_value >= 100000:
        score += 10
    elif total_value >= 50000:
        score += 5

    return min(100, max(0, score))


def get_sample_congress_data() -> List[Dict]:
    """
    Return sample congressional trading data when APIs fail.
    Based on typical recent filings structure.
    """
    # This provides structure when live data unavailable
    # In production, this would be empty or trigger an alert
    return []


if __name__ == "__main__":
    trades = scan_congress_trading()
    print(f"\nFound {len(trades)} stocks with congressional activity:")
    for t in trades[:10]:
        direction = "BUY" if t['signal'] == 'congress_buying' else "SELL" if t['signal'] == 'congress_selling' else "MIXED"
        print(f"  {t['ticker']}: {direction} - {t['politician_count']} politicians - Score: {t['score']:.1f}")
