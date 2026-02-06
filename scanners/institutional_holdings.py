"""
Institutional Holdings Scanner (13F Filings)

Tracks what hedge funds and institutional investors are buying/selling.
Uses SEC EDGAR 13F filings and aggregator data.

Signal Value:
- Smart money accumulation = institutional conviction
- Multiple funds buying same stock = consensus forming
- Top fund position changes = follow the smart money
- New positions by star managers = early signal

Data Sources:
- SEC EDGAR (free, 45-day delay)
- WhaleWisdom / Dataroma (aggregated, easier to parse)

Note: 13F data has ~45 day lag from quarter end, so this
is more of a "smart money thesis confirmation" signal than
a timing signal.
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

# Notable investors to track
SUPER_INVESTORS = [
    'Warren Buffett',
    'Michael Burry',
    'Bill Ackman',
    'David Tepper',
    'Carl Icahn',
    'Seth Klarman',
    'Howard Marks',
    'Ray Dalio',
    'Stanley Druckenmiller',
    'George Soros',
    'Leon Cooperman',
    'David Einhorn',
    'Dan Loeb',
    'Paul Singer',
    'Chase Coleman',
    'Philippe Laffont',
    'Cathie Wood',
]


def scan_institutional_holdings(min_funds: int = 3) -> List[Dict]:
    """
    Scan for stocks with notable institutional activity.

    Returns list of stocks with recent 13F filing changes.
    """
    print("  [13F] Fetching institutional holdings data...")

    results = []

    # Try Dataroma (aggregated superinvestor portfolios)
    dataroma_data = fetch_dataroma_data()
    results.extend(dataroma_data)

    # Try WhaleWisdom-style aggregation
    whale_data = fetch_whale_wisdom_style()
    results.extend(whale_data)

    # Deduplicate by ticker
    ticker_map = {}
    for r in results:
        ticker = r.get('ticker', '')
        if not ticker:
            continue

        if ticker not in ticker_map:
            ticker_map[ticker] = {
                'ticker': ticker,
                'funds_buying': 0,
                'funds_selling': 0,
                'fund_names': [],
                'total_value': 0,
                'is_new_position': False,
                'notable_holders': []
            }

        # Aggregate data
        if r.get('action') == 'buy' or r.get('change_type') == 'new':
            ticker_map[ticker]['funds_buying'] += 1
            ticker_map[ticker]['is_new_position'] = ticker_map[ticker]['is_new_position'] or r.get('change_type') == 'new'
        elif r.get('action') == 'sell':
            ticker_map[ticker]['funds_selling'] += 1

        if r.get('fund_name'):
            ticker_map[ticker]['fund_names'].append(r['fund_name'])

        if r.get('notable_investor'):
            ticker_map[ticker]['notable_holders'].append(r['notable_investor'])

        ticker_map[ticker]['total_value'] += r.get('value', 0)

    # Calculate scores and filter
    final_results = []
    for ticker, data in ticker_map.items():
        score = calculate_institutional_score(
            funds_buying=data['funds_buying'],
            funds_selling=data['funds_selling'],
            is_new_position=data['is_new_position'],
            notable_holders=data['notable_holders'],
            total_value=data['total_value']
        )

        # Determine signal
        net_buys = data['funds_buying'] - data['funds_selling']
        if net_buys >= 2:
            signal = 'institutional_accumulation'
        elif net_buys <= -2:
            signal = 'institutional_distribution'
        elif data['is_new_position']:
            signal = 'new_institutional_position'
        else:
            signal = 'neutral'

        if score >= 50 and (data['funds_buying'] >= min_funds or data['notable_holders']):
            final_results.append({
                'ticker': ticker,
                'score': score,
                'signal': signal,
                'funds_buying': data['funds_buying'],
                'funds_selling': data['funds_selling'],
                'net_fund_activity': net_buys,
                'fund_names': data['fund_names'][:5],
                'notable_holders': data['notable_holders'],
                'is_new_position': data['is_new_position'],
                'total_value_estimate': data['total_value']
            })

    # Sort by score
    final_results.sort(key=lambda x: x['score'], reverse=True)

    print(f"  [13F] Found {len(final_results)} stocks with notable institutional activity")

    return final_results


def fetch_dataroma_data() -> List[Dict]:
    """
    Fetch aggregated superinvestor holdings from Dataroma.
    """
    results = []

    try:
        # Dataroma shows aggregated holdings
        url = "https://www.dataroma.com/m/g/portfolio_b.php"
        response = requests.get(url, headers=HEADERS, timeout=15)

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')

            # Find holdings tables
            tables = soup.find_all('table')
            for table in tables:
                rows = table.find_all('tr')[1:]  # Skip header

                for row in rows[:50]:  # Top 50 holdings
                    cells = row.find_all('td')
                    if len(cells) >= 3:
                        try:
                            # Extract ticker
                            ticker_link = cells[0].find('a')
                            if ticker_link:
                                ticker = ticker_link.get_text(strip=True)
                            else:
                                ticker = cells[0].get_text(strip=True)

                            # Clean ticker
                            ticker = re.sub(r'[^A-Z]', '', ticker.upper())[:5]
                            if not ticker or len(ticker) < 1:
                                continue

                            # Get number of funds holding
                            funds_holding = 0
                            for cell in cells:
                                text = cell.get_text(strip=True)
                                if text.isdigit():
                                    funds_holding = int(text)
                                    break

                            results.append({
                                'ticker': ticker,
                                'fund_name': 'Multiple Super Investors',
                                'action': 'hold',
                                'funds_holding': funds_holding,
                                'value': 0,
                                'source': 'dataroma'
                            })

                        except Exception:
                            continue

    except Exception as e:
        print(f"  [13F] Dataroma fetch failed: {e}")

    return results


def fetch_whale_wisdom_style() -> List[Dict]:
    """
    Fetch institutional holdings from public aggregators.
    """
    results = []

    try:
        # Use FinViz institutional ownership data
        # Stocks with high institutional ownership changes
        url = "https://finviz.com/screener.ashx?v=152&f=sh_instown_o90"
        response = requests.get(url, headers=HEADERS, timeout=15)

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')

            table = soup.find('table', class_='table-light')
            if table:
                rows = table.find_all('tr')[1:]

                for row in rows[:30]:
                    cells = row.find_all('td')
                    if len(cells) >= 8:
                        try:
                            ticker = cells[1].get_text(strip=True)
                            company = cells[2].get_text(strip=True)

                            # Get institutional ownership %
                            inst_own = cells[6].get_text(strip=True) if len(cells) > 6 else "0%"
                            inst_own_pct = float(inst_own.replace('%', '')) if '%' in inst_own else 0

                            if inst_own_pct > 90:  # Very high institutional ownership
                                results.append({
                                    'ticker': ticker,
                                    'company': company,
                                    'action': 'hold',
                                    'institutional_ownership': inst_own_pct,
                                    'fund_name': 'High Institutional Ownership',
                                    'source': 'finviz'
                                })

                        except Exception:
                            continue

    except Exception as e:
        print(f"  [13F] FinViz institutional fetch failed: {e}")

    # Also track recent insider + institutional overlap
    try:
        # Stocks with both insider and institutional buying
        url = "https://finviz.com/screener.ashx?v=152&f=sh_instown_o70,ta_change_u"
        response = requests.get(url, headers=HEADERS, timeout=15)

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')

            table = soup.find('table', class_='table-light')
            if table:
                rows = table.find_all('tr')[1:]

                for row in rows[:20]:
                    cells = row.find_all('td')
                    if len(cells) >= 2:
                        ticker = cells[1].get_text(strip=True)

                        results.append({
                            'ticker': ticker,
                            'action': 'buy',
                            'fund_name': 'Institutional + Momentum',
                            'change_type': 'increase',
                            'source': 'finviz_combo'
                        })

    except Exception:
        pass

    return results


def calculate_institutional_score(funds_buying: int, funds_selling: int,
                                  is_new_position: bool, notable_holders: List[str],
                                  total_value: float) -> float:
    """
    Calculate score based on institutional activity.

    Scoring:
    - Net buying (funds_buying - funds_selling): +10 per net buy (max +30)
    - New position from notable investor: +25
    - Multiple notable holders: +10 per holder (max +30)
    - High total value (>$100M): +10
    """
    score = 50.0

    # Net fund activity
    net_activity = funds_buying - funds_selling
    score += min(net_activity * 10, 30)

    # New position bonus
    if is_new_position:
        score += 15

    # Notable holders bonus
    notable_count = len(notable_holders)
    score += min(notable_count * 15, 30)

    # Value-based adjustment
    if total_value >= 100_000_000:
        score += 10
    elif total_value >= 50_000_000:
        score += 5

    return min(100, max(0, score))


def check_notable_investor(fund_name: str) -> Optional[str]:
    """
    Check if a fund is associated with a notable investor.
    """
    fund_lower = fund_name.lower()

    fund_to_investor = {
        'berkshire': 'Warren Buffett',
        'scion': 'Michael Burry',
        'pershing': 'Bill Ackman',
        'appaloosa': 'David Tepper',
        'icahn': 'Carl Icahn',
        'baupost': 'Seth Klarman',
        'oaktree': 'Howard Marks',
        'bridgewater': 'Ray Dalio',
        'duquesne': 'Stanley Druckenmiller',
        'soros': 'George Soros',
        'omega': 'Leon Cooperman',
        'greenlight': 'David Einhorn',
        'third point': 'Dan Loeb',
        'elliott': 'Paul Singer',
        'tiger global': 'Chase Coleman',
        'coatue': 'Philippe Laffont',
        'ark invest': 'Cathie Wood',
    }

    for key, investor in fund_to_investor.items():
        if key in fund_lower:
            return investor

    return None


if __name__ == "__main__":
    holdings = scan_institutional_holdings(min_funds=2)
    print(f"\nFound {len(holdings)} stocks with institutional activity:")
    for h in holdings[:15]:
        print(f"  {h['ticker']}: Score {h['score']:.1f} - "
              f"{h['funds_buying']} buying, {h['funds_selling']} selling")
        if h['notable_holders']:
            print(f"    Notable: {', '.join(h['notable_holders'])}")
