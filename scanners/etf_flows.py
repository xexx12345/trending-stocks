"""
ETF Flows Scanner

Tracks money flows into/out of sector and thematic ETFs.
Identifies sector rotation and institutional positioning.

Signal Value:
- Large inflows to sector ETF = institutional allocation to that sector
- Outflows = rotation away from sector
- Thematic ETF flows = emerging trend identification
- Leveraged ETF flows = retail sentiment/speculation

Data Sources:
- ETF.com (flows data)
- FinViz ETF screener
- Yahoo Finance ETF data
"""

import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import time
import re

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
}

# Map ETFs to sectors and their top holdings
ETF_SECTOR_MAP = {
    # Sector SPDRs
    'XLK': {'sector': 'Technology', 'holdings': ['AAPL', 'MSFT', 'NVDA', 'AVGO', 'CRM']},
    'XLF': {'sector': 'Financials', 'holdings': ['BRK.B', 'JPM', 'V', 'MA', 'BAC']},
    'XLE': {'sector': 'Energy', 'holdings': ['XOM', 'CVX', 'COP', 'SLB', 'EOG']},
    'XLV': {'sector': 'Healthcare', 'holdings': ['UNH', 'JNJ', 'LLY', 'PFE', 'ABBV']},
    'XLI': {'sector': 'Industrials', 'holdings': ['GE', 'CAT', 'RTX', 'UNP', 'HON']},
    'XLP': {'sector': 'Consumer Staples', 'holdings': ['PG', 'KO', 'PEP', 'COST', 'WMT']},
    'XLY': {'sector': 'Consumer Discretionary', 'holdings': ['AMZN', 'TSLA', 'HD', 'MCD', 'NKE']},
    'XLU': {'sector': 'Utilities', 'holdings': ['NEE', 'DUK', 'SO', 'D', 'AEP']},
    'XLB': {'sector': 'Materials', 'holdings': ['LIN', 'APD', 'SHW', 'FCX', 'NEM']},
    'XLRE': {'sector': 'Real Estate', 'holdings': ['PLD', 'AMT', 'EQIX', 'SPG', 'PSA']},
    'XLC': {'sector': 'Communications', 'holdings': ['META', 'GOOGL', 'NFLX', 'DIS', 'CMCSA']},

    # Thematic ETFs
    'ARKK': {'sector': 'Disruptive Innovation', 'holdings': ['TSLA', 'COIN', 'ROKU', 'SQ', 'PATH']},
    'ARKG': {'sector': 'Genomics', 'holdings': ['EXAS', 'CRSP', 'NVTA', 'REGN', 'VRTX']},
    'SMH': {'sector': 'Semiconductors', 'holdings': ['NVDA', 'TSM', 'AVGO', 'AMD', 'ASML']},
    'SOXX': {'sector': 'Semiconductors', 'holdings': ['NVDA', 'AVGO', 'AMD', 'QCOM', 'TXN']},
    'IBB': {'sector': 'Biotech', 'holdings': ['VRTX', 'GILD', 'AMGN', 'REGN', 'BIIB']},
    'TAN': {'sector': 'Solar', 'holdings': ['ENPH', 'SEDG', 'FSLR', 'RUN', 'NOVA']},
    'LIT': {'sector': 'Lithium/Battery', 'holdings': ['ALB', 'SQM', 'LTHM', 'LAC', 'PCRFY']},
    'URA': {'sector': 'Uranium', 'holdings': ['CCJ', 'NXE', 'UEC', 'DNN', 'UUUU']},
    'JETS': {'sector': 'Airlines', 'holdings': ['DAL', 'UAL', 'LUV', 'AAL', 'ALK']},
    'KWEB': {'sector': 'China Internet', 'holdings': ['BABA', 'JD', 'PDD', 'BIDU', 'NTES']},
    'GDX': {'sector': 'Gold Miners', 'holdings': ['NEM', 'GOLD', 'AEM', 'FNV', 'WPM']},
    'XBI': {'sector': 'Biotech', 'holdings': ['MRNA', 'EXAS', 'IONS', 'ALNY', 'SGEN']},
    'HACK': {'sector': 'Cybersecurity', 'holdings': ['CRWD', 'PANW', 'FTNT', 'ZS', 'OKTA']},
    'ROBO': {'sector': 'Robotics/AI', 'holdings': ['NVDA', 'ISRG', 'KEYS', 'ROK', 'GNRC']},
    'ICLN': {'sector': 'Clean Energy', 'holdings': ['ENPH', 'PLUG', 'SEDG', 'FSLR', 'VWS']},
    'GAMR': {'sector': 'Gaming', 'holdings': ['RBLX', 'EA', 'TTWO', 'ATVI', 'U']},
    'BOTZ': {'sector': 'Robotics/AI', 'holdings': ['NVDA', 'ISRG', 'INTC', 'ABB', 'FANUY']},

    # Leveraged (sentiment indicator)
    'TQQQ': {'sector': 'Tech 3x Bull', 'holdings': ['AAPL', 'MSFT', 'NVDA', 'META', 'AMZN']},
    'SQQQ': {'sector': 'Tech 3x Bear', 'holdings': []},
    'SPXL': {'sector': 'S&P 3x Bull', 'holdings': []},
    'SPXS': {'sector': 'S&P 3x Bear', 'holdings': []},
}


def scan_etf_flows(days_back: int = 7) -> Dict:
    """
    Scan ETF flows to identify sector rotation and sentiment.

    Returns:
    - sector_signals: Which sectors seeing inflows/outflows
    - hot_holdings: Individual stocks benefiting from flows
    - sentiment_indicator: Bull/bear based on leveraged ETF flows
    """
    print("  [ETF] Analyzing ETF flows and sector rotation...")

    results = {
        'sector_flows': [],
        'hot_holdings': {},
        'sentiment': 'neutral',
        'top_inflows': [],
        'top_outflows': []
    }

    # Fetch ETF performance and volume data
    etf_data = fetch_etf_data()

    # Analyze flows based on volume and price action
    sector_scores = analyze_sector_flows(etf_data)
    results['sector_flows'] = sector_scores

    # Identify stocks benefiting from sector flows
    hot_holdings = identify_hot_holdings(sector_scores)
    results['hot_holdings'] = hot_holdings

    # Analyze leveraged ETF flows for sentiment
    sentiment = analyze_leveraged_sentiment(etf_data)
    results['sentiment'] = sentiment

    # Sort sectors by flow score
    results['top_inflows'] = [s for s in sector_scores if s['flow_signal'] == 'inflow'][:5]
    results['top_outflows'] = [s for s in sector_scores if s['flow_signal'] == 'outflow'][:5]

    print(f"  [ETF] Identified {len(results['top_inflows'])} sectors with inflows, "
          f"{len(results['top_outflows'])} with outflows")

    return results


def fetch_etf_data() -> List[Dict]:
    """
    Fetch ETF price and volume data from FinViz.
    """
    results = []

    for etf, info in ETF_SECTOR_MAP.items():
        try:
            url = f"https://finviz.com/quote.ashx?t={etf}"
            response = requests.get(url, headers=HEADERS, timeout=10)

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')

                # Extract key metrics from FinViz
                data = {
                    'etf': etf,
                    'sector': info['sector'],
                    'holdings': info['holdings'],
                    'change_1d': 0,
                    'change_1w': 0,
                    'change_1m': 0,
                    'volume': 0,
                    'avg_volume': 0,
                    'volume_ratio': 1.0
                }

                # Find the data table
                table = soup.find('table', class_='snapshot-table2')
                if table:
                    cells = table.find_all('td')
                    for i, cell in enumerate(cells):
                        text = cell.get_text(strip=True)

                        if text == 'Change':
                            data['change_1d'] = parse_percent(cells[i + 1].get_text())
                        elif text == 'Perf Week':
                            data['change_1w'] = parse_percent(cells[i + 1].get_text())
                        elif text == 'Perf Month':
                            data['change_1m'] = parse_percent(cells[i + 1].get_text())
                        elif text == 'Volume':
                            data['volume'] = parse_volume(cells[i + 1].get_text())
                        elif text == 'Avg Volume':
                            data['avg_volume'] = parse_volume(cells[i + 1].get_text())

                # Calculate volume ratio
                if data['avg_volume'] > 0:
                    data['volume_ratio'] = data['volume'] / data['avg_volume']

                results.append(data)

            time.sleep(0.1)  # Rate limiting

        except Exception as e:
            continue

    return results


def parse_percent(text: str) -> float:
    """Parse percentage string to float."""
    try:
        return float(text.replace('%', '').replace(',', '').strip())
    except:
        return 0.0


def parse_volume(text: str) -> float:
    """Parse volume string to float."""
    try:
        text = text.replace(',', '').strip().upper()
        multiplier = 1
        if 'K' in text:
            multiplier = 1000
            text = text.replace('K', '')
        elif 'M' in text:
            multiplier = 1000000
            text = text.replace('M', '')
        elif 'B' in text:
            multiplier = 1000000000
            text = text.replace('B', '')
        return float(text) * multiplier
    except:
        return 0


def analyze_sector_flows(etf_data: List[Dict]) -> List[Dict]:
    """
    Analyze ETF data to determine sector flow direction.
    """
    sector_scores = []

    for etf in etf_data:
        # Skip leveraged ETFs for sector analysis
        if etf['etf'] in ['TQQQ', 'SQQQ', 'SPXL', 'SPXS']:
            continue

        # Calculate flow score
        flow_score = calculate_flow_score(
            change_1d=etf.get('change_1d', 0),
            change_1w=etf.get('change_1w', 0),
            change_1m=etf.get('change_1m', 0),
            volume_ratio=etf.get('volume_ratio', 1.0)
        )

        # Determine flow direction
        if flow_score >= 60:
            flow_signal = 'inflow'
        elif flow_score <= 40:
            flow_signal = 'outflow'
        else:
            flow_signal = 'neutral'

        sector_scores.append({
            'etf': etf['etf'],
            'sector': etf['sector'],
            'flow_score': flow_score,
            'flow_signal': flow_signal,
            'change_1d': etf.get('change_1d', 0),
            'change_1w': etf.get('change_1w', 0),
            'change_1m': etf.get('change_1m', 0),
            'volume_ratio': etf.get('volume_ratio', 1.0),
            'holdings': etf.get('holdings', [])
        })

    # Sort by flow score
    sector_scores.sort(key=lambda x: x['flow_score'], reverse=True)

    return sector_scores


def calculate_flow_score(change_1d: float, change_1w: float,
                        change_1m: float, volume_ratio: float) -> float:
    """
    Calculate a flow score (0-100) based on price and volume action.

    Logic:
    - Positive returns + high volume = inflows
    - Negative returns + high volume = outflows
    - High volume amplifies the signal
    """
    score = 50.0  # Base

    # Price momentum (weighted more recent)
    momentum = change_1d * 0.4 + change_1w * 0.35 + change_1m * 0.25

    # Momentum contribution (cap at +/- 25)
    score += min(max(momentum * 5, -25), 25)

    # Volume confirmation
    # High volume with positive momentum = strong inflow signal
    if volume_ratio > 1.5:
        if momentum > 0:
            score += 15
        elif momentum < 0:
            score -= 10  # Outflow confirmed by volume
    elif volume_ratio > 1.2:
        if momentum > 0:
            score += 8
        elif momentum < 0:
            score -= 5

    return min(100, max(0, score))


def identify_hot_holdings(sector_scores: List[Dict]) -> Dict[str, Dict]:
    """
    Identify individual stocks benefiting from sector inflows.
    """
    hot_holdings = {}

    for sector in sector_scores:
        if sector['flow_signal'] != 'inflow':
            continue

        for ticker in sector.get('holdings', [])[:5]:
            if ticker not in hot_holdings:
                hot_holdings[ticker] = {
                    'ticker': ticker,
                    'sectors': [],
                    'combined_flow_score': 0,
                    'etf_exposure': []
                }

            hot_holdings[ticker]['sectors'].append(sector['sector'])
            hot_holdings[ticker]['etf_exposure'].append(sector['etf'])
            hot_holdings[ticker]['combined_flow_score'] += sector['flow_score'] * 0.2

    # Normalize scores
    for ticker, data in hot_holdings.items():
        data['combined_flow_score'] = min(100, 50 + data['combined_flow_score'])

    return hot_holdings


def analyze_leveraged_sentiment(etf_data: List[Dict]) -> str:
    """
    Analyze leveraged ETF flows to gauge retail sentiment.

    High TQQQ volume relative to SQQQ = bullish retail sentiment
    High SQQQ volume relative to TQQQ = bearish retail sentiment
    """
    tqqq_data = None
    sqqq_data = None

    for etf in etf_data:
        if etf['etf'] == 'TQQQ':
            tqqq_data = etf
        elif etf['etf'] == 'SQQQ':
            sqqq_data = etf

    if not tqqq_data or not sqqq_data:
        return 'neutral'

    # Compare volume ratios and price action
    tqqq_vol = tqqq_data.get('volume', 1)
    sqqq_vol = sqqq_data.get('volume', 1)

    if tqqq_vol > 0 and sqqq_vol > 0:
        bull_bear_ratio = tqqq_vol / sqqq_vol

        if bull_bear_ratio > 2.0:
            return 'very_bullish'
        elif bull_bear_ratio > 1.3:
            return 'bullish'
        elif bull_bear_ratio < 0.5:
            return 'very_bearish'
        elif bull_bear_ratio < 0.75:
            return 'bearish'

    return 'neutral'


def get_etf_holdings_exposure(ticker: str) -> List[Dict]:
    """
    Get list of ETFs that hold a given ticker.
    """
    exposures = []

    for etf, info in ETF_SECTOR_MAP.items():
        if ticker in info.get('holdings', []):
            exposures.append({
                'etf': etf,
                'sector': info['sector']
            })

    return exposures


if __name__ == "__main__":
    flows = scan_etf_flows()

    print("\n=== Top Sector Inflows ===")
    for s in flows['top_inflows'][:5]:
        print(f"  {s['etf']} ({s['sector']}): Score {s['flow_score']:.1f}, "
              f"1D: {s['change_1d']:+.1f}%, Vol Ratio: {s['volume_ratio']:.1f}x")

    print("\n=== Top Sector Outflows ===")
    for s in flows['top_outflows'][:5]:
        print(f"  {s['etf']} ({s['sector']}): Score {s['flow_score']:.1f}, "
              f"1D: {s['change_1d']:+.1f}%, Vol Ratio: {s['volume_ratio']:.1f}x")

    print(f"\n=== Retail Sentiment: {flows['sentiment'].upper()} ===")

    print("\n=== Hot Holdings (benefiting from inflows) ===")
    for ticker, data in list(flows['hot_holdings'].items())[:10]:
        print(f"  {ticker}: Sectors: {', '.join(data['sectors'])}, "
              f"Score: {data['combined_flow_score']:.1f}")
