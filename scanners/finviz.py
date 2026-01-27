"""
Finviz Scanner - Scrapes sector performance and heatmap data from Finviz
"""

import requests
from bs4 import BeautifulSoup
from typing import Dict, List
import logging
import re
import json

logger = logging.getLogger(__name__)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}


def scrape_sector_performance() -> List[Dict]:
    """
    Scrape sector performance data from Finviz groups page.
    Returns list of sectors with performance metrics.
    """
    results = []

    try:
        # Use the sector performance page
        url = "https://finviz.com/groups.ashx?g=sector&v=140&o=-perf1w"
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        # Find the main data table - look for table with sector data
        tables = soup.find_all('table')

        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cols = row.find_all('td')
                # Look for rows with sector names and performance data
                if len(cols) >= 8:
                    # Check if first column looks like a sector link
                    first_col = cols[0]
                    link = first_col.find('a')
                    if link and 'g=sector' in str(link.get('href', '')):
                        try:
                            sector_name = link.get_text(strip=True)

                            # Parse performance values from columns
                            def parse_pct(col):
                                text = col.get_text(strip=True).replace('%', '').replace(',', '')
                                try:
                                    return float(text) if text and text != '-' else 0.0
                                except:
                                    return 0.0

                            # Column positions may vary, try to find percentage values
                            perfs = []
                            for col in cols[1:]:
                                val = parse_pct(col)
                                perfs.append(val)

                            if len(perfs) >= 6 and sector_name:
                                results.append({
                                    'sector': sector_name,
                                    'perf_1d': perfs[0] if len(perfs) > 0 else 0,
                                    'perf_1w': perfs[1] if len(perfs) > 1 else 0,
                                    'perf_1m': perfs[2] if len(perfs) > 2 else 0,
                                    'perf_3m': perfs[3] if len(perfs) > 3 else 0,
                                    'perf_6m': perfs[4] if len(perfs) > 4 else 0,
                                    'perf_1y': perfs[5] if len(perfs) > 5 else 0
                                })
                        except Exception as e:
                            logger.debug(f"Error parsing row: {e}")
                            continue

        # If we didn't find data, try alternative approach
        if not results:
            results = scrape_sector_from_map()

        # Sort by 1-month performance
        results.sort(key=lambda x: x['perf_1m'], reverse=True)

        logger.info(f"Scraped {len(results)} sectors from Finviz")
        return results

    except requests.RequestException as e:
        logger.error(f"Failed to fetch Finviz data: {e}")
        return []


def scrape_sector_from_map() -> List[Dict]:
    """
    Alternative: scrape sector data from the map page.
    """
    results = []

    try:
        # The heatmap page has sector data embedded
        url = "https://finviz.com/map.ashx?t=sec"
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()

        # Look for JavaScript data in the page
        text = response.text

        # Try to find sector performance data in scripts
        # Finviz embeds data in JavaScript variables
        script_pattern = re.compile(r'var\s+map_data\s*=\s*(\[.*?\]);', re.DOTALL)
        match = script_pattern.search(text)

        if match:
            try:
                data = json.loads(match.group(1))
                # Process the map data
                for item in data:
                    if isinstance(item, dict) and 'name' in item:
                        results.append({
                            'sector': item.get('name', ''),
                            'perf_1d': item.get('perf_d', 0),
                            'perf_1w': item.get('perf_w', 0),
                            'perf_1m': item.get('perf_m', 0),
                            'perf_3m': item.get('perf_q', 0),
                            'perf_6m': item.get('perf_h', 0),
                            'perf_1y': item.get('perf_y', 0)
                        })
            except json.JSONDecodeError:
                pass

        return results

    except Exception as e:
        logger.debug(f"Map scrape failed: {e}")
        return []


def scrape_top_gainers(limit: int = 20) -> List[Dict]:
    """
    Scrape top gaining stocks from Finviz screener.
    """
    results = []

    try:
        url = "https://finviz.com/screener.ashx?v=111&s=ta_topgainers"
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        # Find the screener results table
        # Look for table rows with ticker data
        for row in soup.find_all('tr'):
            cols = row.find_all('td')
            if len(cols) >= 10:
                # Check if this looks like a stock row (has ticker link)
                ticker_col = cols[1] if len(cols) > 1 else None
                if ticker_col:
                    ticker_link = ticker_col.find('a')
                    if ticker_link and ticker_link.get('href', '').startswith('quote.ashx'):
                        try:
                            ticker = ticker_link.get_text(strip=True)
                            company = cols[2].get_text(strip=True) if len(cols) > 2 else ''
                            sector = cols[3].get_text(strip=True) if len(cols) > 3 else ''

                            # Find the change column (usually has % sign)
                            change = 0.0
                            for col in cols:
                                text = col.get_text(strip=True)
                                if '%' in text and not text.startswith('$'):
                                    try:
                                        change = float(text.replace('%', '').replace(',', ''))
                                        break
                                    except:
                                        pass

                            results.append({
                                'ticker': ticker,
                                'company': company[:50],
                                'sector': sector,
                                'change': change
                            })

                            if len(results) >= limit:
                                break
                        except:
                            continue

        logger.info(f"Found {len(results)} top gainers from Finviz")
        return results

    except requests.RequestException as e:
        logger.error(f"Failed to fetch top gainers: {e}")
        return []


def scrape_top_losers(limit: int = 20) -> List[Dict]:
    """
    Scrape top losing stocks from Finviz screener.
    """
    results = []

    try:
        url = "https://finviz.com/screener.ashx?v=111&s=ta_toplosers"
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        for row in soup.find_all('tr'):
            cols = row.find_all('td')
            if len(cols) >= 10:
                ticker_col = cols[1] if len(cols) > 1 else None
                if ticker_col:
                    ticker_link = ticker_col.find('a')
                    if ticker_link and ticker_link.get('href', '').startswith('quote.ashx'):
                        try:
                            ticker = ticker_link.get_text(strip=True)
                            company = cols[2].get_text(strip=True) if len(cols) > 2 else ''

                            change = 0.0
                            for col in cols:
                                text = col.get_text(strip=True)
                                if '%' in text and not text.startswith('$'):
                                    try:
                                        change = float(text.replace('%', '').replace(',', ''))
                                        break
                                    except:
                                        pass

                            results.append({
                                'ticker': ticker,
                                'company': company[:50],
                                'change': change
                            })

                            if len(results) >= limit:
                                break
                        except:
                            continue

        logger.info(f"Found {len(results)} top losers from Finviz")
        return results

    except requests.RequestException as e:
        logger.error(f"Failed to fetch top losers: {e}")
        return []


def get_sector_etf_performance() -> List[Dict]:
    """
    Get sector performance using sector ETFs via yfinance.
    More reliable than scraping Finviz.
    """
    try:
        import yfinance as yf
        from datetime import datetime, timedelta

        # Sector ETFs mapping
        sector_etfs = {
            'Technology': 'XLK',
            'Healthcare': 'XLV',
            'Financial': 'XLF',
            'Consumer Cyclical': 'XLY',
            'Communication': 'XLC',
            'Industrials': 'XLI',
            'Consumer Defensive': 'XLP',
            'Energy': 'XLE',
            'Materials': 'XLB',
            'Real Estate': 'XLRE',
            'Utilities': 'XLU'
        }

        results = []
        end_date = datetime.now()
        start_date = end_date - timedelta(days=35)

        # Download all ETFs at once
        tickers = list(sector_etfs.values())
        data = yf.download(tickers, start=start_date, end=end_date, progress=False)

        for sector, etf in sector_etfs.items():
            try:
                if len(tickers) == 1:
                    close = data['Close']
                else:
                    close = data['Close'][etf]

                if len(close) >= 2:
                    perf_1d = ((close.iloc[-1] / close.iloc[-2]) - 1) * 100
                    perf_1m = ((close.iloc[-1] / close.iloc[0]) - 1) * 100

                    results.append({
                        'sector': sector,
                        'etf': etf,
                        'perf_1d': round(perf_1d, 2),
                        'perf_1w': 0,  # Would need more data
                        'perf_1m': round(perf_1m, 2),
                        'perf_3m': 0,
                        'perf_6m': 0,
                        'perf_1y': 0
                    })
            except Exception as e:
                logger.debug(f"Error getting {sector} ETF data: {e}")
                continue

        results.sort(key=lambda x: x['perf_1m'], reverse=True)
        logger.info(f"Got {len(results)} sector performances from ETFs")
        return results

    except ImportError:
        logger.warning("yfinance not available for sector ETF data")
        return []
    except Exception as e:
        logger.error(f"Error getting sector ETF performance: {e}")
        return []


def get_sector_heatmap() -> Dict[str, float]:
    """
    Get sector performance as a simple dict for the report.
    """
    # Try scraping first, fall back to ETFs
    sectors = scrape_sector_performance()
    if not sectors or len(sectors) < 5:
        sectors = get_sector_etf_performance()
    return {s['sector']: s['perf_1m'] for s in sectors}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("\nSECTOR PERFORMANCE (1 Month)")
    print("-" * 40)
    sectors = scrape_sector_performance()
    if sectors:
        for sector in sectors:
            trend = "+" if sector['perf_1m'] >= 0 else ""
            print(f"{sector['sector']:25} | {trend}{sector['perf_1m']:.2f}%")
    else:
        print("Could not fetch sector data")

    print("\n\nTOP GAINERS TODAY")
    print("-" * 40)
    gainers = scrape_top_gainers(10)
    if gainers:
        for g in gainers:
            print(f"{g['ticker']:6} | {g['change']:+6.2f}% | {g.get('sector', '')}")
    else:
        print("Could not fetch gainers")

    print("\n\nTOP LOSERS TODAY")
    print("-" * 40)
    losers = scrape_top_losers(10)
    if losers:
        for l in losers:
            print(f"{l['ticker']:6} | {l['change']:+6.2f}%")
    else:
        print("Could not fetch losers")
